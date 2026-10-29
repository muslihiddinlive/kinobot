"""Kino qidiruv motori.

Imkoniyatlar
  * lotin ↔ kirill (o'zbek/rus), apostrof variantlari (o'g'ri = oʻgʻri = ogri), tinish belgilari, katta-kichik harf
  * ko'p so'zli qidiruv ("avatar suv" -> "Avatar 2: Suv yo'li"), so'z boshi va ichki bo'lak ("tani" -> Titanik)
  * xatoga chidamlilik ("titnaik" -> Titanik) va "Shuni nazarda tutdingizmi?" takliflari
  * aqlli saralash: aniq kod/nom > nom boshi > ibora > so'zlar > teglar > noaniq; teng bo'lsa mashhurlik
  * faqat ANIQ moslikda avtomatik yuborish (pick), qolganida ro'yxat

Indeks xotirada (kinolar soni o'nlab minggacha bo'lsa ham tez). TTL 120 s + yozishda invalidate().
rapidfuzz o'rnatilgan bo'lsa u ishlatiladi, bo'lmasa difflib (sekinroq, lekin ishlaydi).
"""
import math
import re
import threading
import time
import unicodedata
from collections import OrderedDict, namedtuple

try:                                    # ixtiyoriy tezlatgich
    from rapidfuzz import fuzz as _fuzz, process as _process
except Exception:                       # noqa: BLE001
    _fuzz = _process = None

TTL = 120.0
PAGE = 10
MAX_QUERY = 64

_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "",
    "э": "e", "ю": "yu", "я": "ya", "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
}
_APOS = "'\u02bb\u02bc\u2019\u2018`\u00b4\u02b9\u02bd\u0060"


def norm(s: str) -> str:
    """Qidiruv uchun skelet: kichik harf, kirill->lotin, apostrofsiz, tinish belgisiz,
    o'xshash tovushlar birlashtirilgan (x/kh->h, zh->j, q->k, w->v), qo'sh harflar bitta."""
    s = unicodedata.normalize("NFKC", s or "").casefold()
    s = "".join(_CYR.get(ch, ch) for ch in s)
    for a in _APOS:
        s = s.replace(a, "")
    s = re.sub(r"[^\w\s]|_", " ", s)
    s = s.replace("kh", "h").replace("x", "h").replace("zh", "j").replace("q", "k").replace("w", "v")
    s = re.sub(r"([^\W\d_])\1+", r"\1", s)
    return " ".join(s.split())


Item = namedtuple("Item", "row score kind")
Result = namedtuple("Result", "rows total items fuzzy")


class _Entry:
    __slots__ = ("row", "code", "title", "tokens", "tagtokens", "hashtags", "pool", "pop")

    def __init__(self, row):
        self.row = row
        self.code = norm(row["code"] or "").replace(" ", "")
        self.title = norm(row["title"] or "")
        self.tokens = self.title.split()
        self.tagtokens = norm(row["tags"] or "").split()
        # butun hashtaglar (#patrick_fan -> "patrickfan"): hashtag rejimida har teg yaxlit solishtiriladi
        self.hashtags = [h for h in (norm(r).replace(" ", "") for r in str(row["tags"] or "").split()) if h]
        extra = norm(" ".join(str(row[k] or "") for k in ("year", "country", "language")))
        self.pool = self.tokens + self.tagtokens + extra.split()
        dl = int(row["downloads"] or 0)
        self.pop = min(40.0, math.log1p(dl) * 6) + (25.0 if row["is_trending"] else 0.0)


_lock = threading.Lock()
_index: list = []
_built = 0.0
_titles: list = []
_tok_list: list = []        # noyob sarlavha so'zlari
_tok_map: dict = {}         # so'z -> [entry indekslari]
_tag_list: list = []        # noyob teg so'zlari (normallashgan)
_tag_map: dict = {}         # teg -> [entry indekslari]
_top_tags: list = []        # [("#teg", kinolar soni)] mashhurlik bo'yicha


def invalidate() -> None:
    global _built
    _built = 0.0


def _load():
    global _index, _built, _titles, _tok_list, _tok_map, _tag_list, _tag_map, _top_tags
    if time.time() - _built < TTL and _index is not None and _built:
        return _index
    with _lock:
        if time.time() - _built < TTL and _built:
            return _index
        import database as db
        conn = db.get_conn()
        rows = conn.execute("SELECT * FROM movies").fetchall()
        conn.close()
        _index = [_Entry(r) for r in rows]
        _titles = [e.title for e in _index]
        tm: dict = {}
        for i, e in enumerate(_index):
            for tk in set(e.tokens):
                if len(tk) >= 3:
                    tm.setdefault(tk, []).append(i)
        _tok_map, _tok_list = tm, list(tm)
        tg: dict = {}
        shown: dict = {}
        for i, e in enumerate(_index):
            for tk in set(e.hashtags):
                tg.setdefault(tk, []).append(i)
            for raw in str(e.row["tags"] or "").split():       # ko'rinadigan shakl: "#patrick"
                key = norm(raw).replace(" ", "")
                if key:
                    shown.setdefault(key, "#" + raw.lstrip("#").lower())
        _tag_map, _tag_list = tg, list(tg)
        ranked = sorted(tg.items(), key=lambda kv: (-len(kv[1]), -sum(int(_index[i].row["downloads"] or 0) for i in kv[1])))
        _top_tags = [(shown.get(k, "#" + k), len(v)) for k, v in ranked]
        _built = time.time()
    return _index


def _strict(e: _Entry, qn: str, qtokens: list, qcode: str) -> tuple:
    """(score, kind) yoki (0, '')."""
    if qcode and e.code == qcode:
        return 1000, "code"
    if qn == e.title:
        return 900, "exact"
    if len(qn) >= 3 and e.title.startswith(qn):
        return 800, "prefix"
    if all(any(tt.startswith(qt) for tt in e.tokens) for qt in qtokens):
        return (650 if qn in e.title else 600), "tokens"
    if e.tagtokens and all(qt in e.tagtokens for qt in qtokens):
        return 520, "tag"                              # so'rov butunlay teg(lar)ga teng: "Patrick" -> #patrick
    if len(qn) >= 3 and qn in e.title:
        return 500, "substr"
    hit = [any(t.startswith(qt) for t in e.pool) for qt in qtokens]
    if all(hit):
        return 400, "pool"
    if len(qtokens) >= 2 and sum(hit) / len(qtokens) >= 0.6:
        return 200 + int(100 * sum(hit) / len(qtokens)), "partial"
    if len(qn) >= 4 and e.code.startswith(qcode) and qcode:
        return 450, "codeprefix"
    return 0, ""


def _fuzzy_pairs(qn: str, entries: list, limit: int, cutoff: int) -> list:
    """[(entry_index, ratio 0..100)] — eng yaqin sarlavhalar."""
    if len(qn) < 4:
        return []
    if _process is not None:
        res = _process.extract(qn, _titles, scorer=_fuzz.WRatio, limit=limit, score_cutoff=cutoff)
        return [(i, sc) for _, sc, i in res]
    import difflib
    out = []
    for i, t in enumerate(_titles):
        r = difflib.SequenceMatcher(None, qn, t).ratio() * 100
        if r >= cutoff:
            out.append((i, r))
    out.sort(key=lambda x: -x[1])
    return out[:limit]


def _token_fuzzy(qtokens: list) -> dict:
    """{entry_index: o'rtacha ratio} — HAR BIR so'rov so'zi sarlavhadagi biror so'zga yaqin (>=80) bo'lgan kinolar.
    "узбек"(uzbek) ≈ "ўзбек"(ozbek), "avtar" ≈ "avatar"."""
    per_token = []
    for qt in qtokens:
        if len(qt) < 4:
            if qt.isdigit() or len(qt) >= 2:
                per_token.append({i: 100.0 for i in _tok_map.get(qt, [])})
                continue
            return {}
        hits: dict = {}
        if _process is not None:
            cand = [(t, sc) for t, sc, _ in _process.extract(qt, _tok_list, scorer=_fuzz.ratio, limit=8, score_cutoff=80)]
        else:
            import difflib
            cand = [(t, difflib.SequenceMatcher(None, qt, t).ratio() * 100) for t in _tok_list]
            cand = [(t, sc) for t, sc in cand if sc >= 80]
        for t, sc in cand:
            for i in _tok_map[t]:
                hits[i] = max(hits.get(i, 0.0), sc)
        per_token.append(hits)
    if not per_token:
        return {}
    common = set(per_token[0])
    for h in per_token[1:]:
        common &= set(h)
    return {i: sum(h[i] for h in per_token) / len(per_token) for i in common}


def search(query: str, limit: int = PAGE, offset: int = 0, fuzzy: bool = True) -> Result:
    q = (query or "").strip()[:MAX_QUERY]
    qn = norm(q)
    if not qn:
        return Result([], 0, [], False)
    entries = _load()
    qtokens = qn.split()
    if q.lstrip().startswith("#"):
        return _tag_search(q, qtokens, entries, limit, offset, fuzzy)
    qcode = qn.replace(" ", "")
    scored = []
    for e in entries:
        s, kind = _strict(e, qn, qtokens, qcode)
        if s:
            # teg/yil kabi past aniqlikdagi moslikda mashhurlik ta'siri kamroq (nom o'xshashligi ustun turadi)
            scored.append(Item(e.row, s + (e.pop if s >= 500 else e.pop / 2), kind))
    used_fuzzy = False
    title_hit = any(it.kind in ("code", "exact", "prefix", "tokens", "substr") for it in scored)
    if fuzzy and not title_hit:
        # nom bo'yicha aniq mos kelmasa (faqat teg/yil mos kelgan yoki hech narsa topilmagan bo'lsa) yaqin sarlavhalar qidiriladi:
        # "узбек" (у) ≈ "Ўзбек" (ў), "titnaik" ≈ "Titanik"
        seen = {it.row["id"] for it in scored}
        # 1) so'z darajasida yaqinlik (eng ishonchli): "uzbek" ≈ "ozbek", "avtar" ≈ "avatar"
        for i, avg in sorted(_token_fuzzy(qtokens).items(), key=lambda kv: -kv[1])[:10]:
            e = entries[i]
            if e.row["id"] not in seen:
                scored.append(Item(e.row, 450 + (avg - 80) * 1.5 + e.pop / 4, "fuzzy"))
                seen.add(e.row["id"])
                used_fuzzy = True
        # 2) butun sarlavha bo'yicha yaqinlik: "titnaik" ≈ "Titanik"
        for i, ratio in _fuzzy_pairs(qn, entries, 10, 76):
            e = entries[i]
            if e.row["id"] not in seen:
                # juda yaqin (>=88) sarlavha teg mosligidan (400) yuqori turadi
                base = 420 + (ratio - 88) * 3 if ratio >= 88 else 100 + ratio / 2
                scored.append(Item(e.row, base + e.pop / 4, "fuzzy"))
                seen.add(e.row["id"])
                used_fuzzy = True
    scored.sort(key=lambda it: -it.score)
    page = scored[offset: offset + limit]
    return Result([it.row for it in page], len(scored), page, used_fuzzy)


def _tag_search(q: str, qtokens: list, entries: list, limit: int, offset: int, fuzzy: bool) -> Result:
    """Hashtag rejimi ("#patrick", "#pat", "#patrick #spongebob"): faqat teglar bo'yicha; hamma teglar mos kelishi kerak."""
    wanted = [norm(p).replace(" ", "") for p in q.replace(",", " ").split() if norm(p)]
    if not wanted:
        return Result([], 0, [], False)
    last = len(wanted) - 1
    scored = []
    for e in entries:
        exact = True
        ok = True
        for i, w in enumerate(wanted):
            # oxirgi teg yozilayotgan bo'lishi mumkin: so'z boshi bo'yicha ham mos keladi (aniq mosdan pastroq)
            if w in e.hashtags:
                continue
            if i == last and len(w) >= 2 and any(t.startswith(w) for t in e.hashtags):
                exact = False
                continue
            ok = False
            break
        if ok:
            scored.append(Item(e.row, (700 if exact else 650) + e.pop, "tag"))
    used_fuzzy = False
    if not scored and fuzzy and len(wanted) == 1 and len(wanted[0]) >= 4:
        near = _process.extract(wanted[0], _tag_list, scorer=_fuzz.ratio, limit=3, score_cutoff=80) if _process is not None else []
        for tag, sc, _ in near:
            for i in _tag_map[tag]:
                scored.append(Item(entries[i].row, 450 + (sc - 80) + entries[i].pop / 4, "fuzzy"))
                used_fuzzy = True
    scored.sort(key=lambda it: -it.score)
    page = scored[offset: offset + limit]
    return Result([it.row for it in page], len(scored), page, used_fuzzy)


def top_tags(limit: int = 24) -> list:
    """Mashhur teglar: [("#patrick", kinolar_soni)]."""
    _load()
    return _top_tags[:limit]


def suggest(query: str, n: int = 3) -> list:
    """Natija bo'lmaganda: eng yaqin n ta kino (qator)."""
    qn = norm((query or "")[:MAX_QUERY])
    if len(qn) < 3:
        return []
    entries = _load()
    out = []
    for i, ratio in _fuzzy_pairs(qn, entries, n, 62):
        out.append(entries[i].row)
    return out


def pick(res: Result):
    """Faqat ANIQ moslikda avtomatik yuboriladigan kinoni qaytaradi (aks holda None)."""
    its = res.items
    if not its:
        return None
    top = its[0]
    if top.kind in ("code", "exact"):
        return top.row
    if res.total == 1 and top.kind in ("prefix", "tokens"):
        return top.row
    if top.kind == "prefix" and res.total > 1 and its[1].score < top.score - 150:
        return top.row
    return None


# ── Foydalanuvchining oxirgi qidiruvi (sahifalash uchun) ──
_last: "OrderedDict[int, str]" = OrderedDict()


def remember(user_id: int, query: str) -> None:
    _last[user_id] = query[:MAX_QUERY]
    _last.move_to_end(user_id)
    while len(_last) > 5000:
        _last.popitem(last=False)


def recall(user_id: int):
    return _last.get(user_id)


def matches_watch(movie_row, watch_query: str) -> bool:
    """Foydalanuvchi so'ragan matn yangi qo'shilgan kinoga mos keladimi?"""
    qn = norm(watch_query or "")
    if not qn:
        return False
    e = _Entry(movie_row)
    s, _ = _strict(e, qn, qn.split(), qn.replace(" ", ""))
    if s >= 400:
        return True
    pairs = _fuzzy_pairs_single(qn, e.title)
    return pairs >= 85


def _fuzzy_pairs_single(qn: str, title: str) -> float:
    if len(qn) < 4:
        return 0.0
    if _fuzz is not None:
        return _fuzz.WRatio(qn, title)
    import difflib
    return difflib.SequenceMatcher(None, qn, title).ratio() * 100


def missing_queries(days: int = 30, limit: int = 20) -> list:
    """Oxirgi `days` kunda TOPILMAGAN va hozir ham topilmaydigan so'rovlar: [(matn, so'rovlar soni, noyob userlar)].
    Imlosi har xil yozilganlar (Titanik/титаник/titanic) bitta so'rov sifatida birlashtiriladi."""
    import database as db
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT query, user_id FROM search_logs WHERE found=0 AND searched_at >= datetime('now', ?)",
        (f"-{int(days)} day",)).fetchall()
    conn.close()
    groups: dict = {}
    for r in rows:
        key = norm(r["query"] or "")
        if len(key) < 2:
            continue
        g = groups.setdefault(key, {"names": {}, "n": 0, "users": set()})
        g["names"][r["query"].strip()] = g["names"].get(r["query"].strip(), 0) + 1
        g["n"] += 1
        g["users"].add(r["user_id"])
    out = []
    for key, g in groups.items():
        text = max(g["names"], key=g["names"].get)
        if search(text, limit=1, fuzzy=False).total:      # bu orada kino qo'shilgan bo'lishi mumkin
            continue
        out.append((text, g["n"], len(g["users"])))
    out.sort(key=lambda x: (-x[1], -x[2]))
    return out[:limit]
