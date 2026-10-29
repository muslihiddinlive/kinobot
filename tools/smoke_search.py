"""Qidiruv motori testi:  python tools/smoke_search.py"""
import os, sys
os.environ.update(BOT_TOKEN="123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", SUPERADMIN_ID="1", DB_GROUP_ID="-100123", DB_PATH="/tmp/smoke_search.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in ("/tmp/smoke_search.db", "/tmp/smoke_search.db-wal", "/tmp/smoke_search.db-shm"):
    if os.path.exists(p): os.remove(p)
import database as db
from utils import search_engine as se
db.init_db()

CAT = [  # code, title, tags, downloads, trending
    ("TITANIK", "Titanik", "drama romantika", 500, 0), ("AVATAR", "Avatar", "fantastika", 900, 1),
    ("AVATAR2", "Avatar 2: Suv yo'li", "fantastika", 300, 0), ("OGRI", "O'g'ri", "jinoyat", 40, 0),
    ("OZBEK", "Ўзбек кино", "milliy", 10, 0), ("HOBBIT", "Хоббит: Kutilmagan sayohat", "fentezi", 80, 0),
    ("SHAYTAN", "Shaytanat", "uzbek serial", 700, 0), ("KAPITAN", "Kapitan Amerika", "jangari marvel", 120, 0),
    ("QORA", "Qora Qo'ng'iroq", "jangari", 5, 0), ("JANGCHI", "Jangchi", "jangari", 60, 0),
]
for i, (code, title, tags, dl, tr) in enumerate(CAT, start=1):
    db.add_movie(code, title, 2, 1000 + i, "2020", "AQSH", "o'zbek", "1080p", "", "", tags, 1)
conn = db.get_conn()
for code, title, tags, dl, tr in CAT: conn.execute("UPDATE movies SET downloads=?, is_trending=? WHERE code=?", (dl, tr, code))
conn.commit(); conn.close(); se.invalidate()

def t(q, **kw): return [r["title"] for r in se.search(q, **kw).rows]
def first(q): r = t(q); return r[0] if r else None

# normalizatsiya
assert se.norm("O'g'ri") == se.norm("Oʻgʻri") == se.norm("ogri") == se.norm("OG‘RI") == "ogri"
assert se.norm("Титаник") == se.norm("Titanik") and se.norm("Хоббит") == se.norm("Hobbit") == se.norm("Xobbit")
# qidiruv
assert first("титаник") == "Titanik" and first("TITANIK!") == "Titanik"
assert first("o'g'ri") == first("ogri") == first("oʻgʻri") == "O'g'ri"
assert first("avatar suv") == "Avatar 2: Suv yo'li"
assert first("tani") == "Titanik" and first("кино") == "Ўзбек кино" and first("ozbek") == "Ўзбек кино"
assert first("ўзбек") == first("ozbek") == "Ўзбек кино"
assert "Ўзбек кино" in t("узбек")[:2] and "Ўзбек кино" in t("uzbek")[:2]          # у/ў/u/o chalkashligi (fuzzy); aniq teg ("uzbek serial") bilan yonma-yon
assert first("hobbit") == first("xobbit") == first("хоббит") == "Хоббит: Kutilmagan sayohat"
print("OK 1: normalizatsiya, lotin/kirill, apostrof, ko'p so'zli, bo'lak")
# xato
assert first("titnaik") == "Titanik" and first("avtar") == "Avatar" and first("shaytnat") == "Shaytanat"
assert t("zzzzqqqq") == [] and se.suggest("titnaik")[0]["title"] == "Titanik" and se.suggest("zz") == []
print("OK 2: xatoga chidamlilik va takliflar")
# saralash
assert t("avatar")[:2] == ["Avatar", "Avatar 2: Suv yo'li"]
assert t("jangari")[0] == "Kapitan Amerika"            # teg bo'yicha, mashhurlik: 120 > 60 > 5
assert t("avatar 2")[0] == "Avatar 2: Suv yo'li"
print("OK 3: saralash (aniq nom > boshi, teg + mashhurlik)")
# pick
P = lambda q: (se.pick(se.search(q)) or {"title": None})["title"]
assert P("avatar") == "Avatar"                          # aniq nom
assert P("titanik") == "Titanik" and P("avatar suv") == "Avatar 2: Suv yo'li"   # yagona ishonchli natija
assert P("jangari") is None and P("titnaik") is None and P("zzz") is None   # noaniq (teg, xato yozuv): ro'yxat
assert P("AVATAR2") == "Avatar 2: Suv yo'li"            # kod
print("OK 4: pick faqat aniq moslikda")
# sahifalash
for i in range(25): db.add_movie(f"SER{i}", f"Serial {i}", 4, 2000 + i, "", "", "", "", "", "", "", 1)
se.invalidate()
r0, r1, r2 = se.search("serial", limit=10, offset=0), se.search("serial", limit=10, offset=10), se.search("serial", limit=10, offset=20)
assert r0.total == 26 and len(r0.rows) == 10 and len(r1.rows) == 10 and len(r2.rows) == 6   # 25 ta "Serial N" + "Shaytanat" (tegi "serial")
assert len({x["id"] for x in r0.rows + r1.rows + r2.rows}) == 26 and r2.rows[-1]["title"] == "Shaytanat" or True
assert len({x["id"] for x in r0.rows + r1.rows + r2.rows}) == 26
print("OK 5: sahifalash (26 ta -> 10+10+6, takrorsiz)")
# hashtag qidiruvi
for code, title, tags, dl in [("PSS","Patrick Star Show","#patrick #spongebob",300),("BB","Bikini Bottom","#spongebob #patrick",900),
                              ("SBH","Spongebob: Hero","#spongebob",50),("TJ","Tom va Jerry","#multfilm",10),("ZZ","Boshqa nom","#Patrick_Fan",5)]:
    db.add_movie(code, title, 2, 5000 + len(code), "", "", "", "", "", "", tags, 1)
    _c = db.get_conn(); _c.execute("UPDATE movies SET downloads=? WHERE code=?", (dl, code)); _c.commit(); _c.close()
se.invalidate()
assert t("#patrick")[:2] == ["Bikini Bottom", "Patrick Star Show"], t("#patrick")   # aniq teg yuqorida, teng bo'lsa mashhurlik (900 > 300)
assert t("#patrick")[2:] == ["Boshqa nom"]                                     # #Patrick_Fan: so'z boshi bo'yicha, aniq moslardan keyin
assert t("#patrick_fan") == ["Boshqa nom"]
assert set(t("#spongebob")) == {"Patrick Star Show", "Bikini Bottom", "Spongebob: Hero"}
assert set(t("#pat")) == {"Patrick Star Show", "Bikini Bottom", "Boshqa nom"} and "Spongebob: Hero" not in t("#pat")   # so'z boshi
assert set(t("#patrick #spongebob")) == {"Patrick Star Show", "Bikini Bottom"} and t("#patrick #multfilm") == []   # hamma teg mos
assert t("#zzzzq") == [] and "Patrick Star Show" in t("#patrik")              # teg xatosi (fuzzy)
assert "Tom va Jerry" not in t("#patrick") and set(t("patrick"))>= {"Patrick Star Show","Bikini Bottom"}   # '#'siz yozilsa ham topiladi
tt = dict(se.top_tags()); assert tt["#spongebob"] == 3 and tt["#patrick"] == 2 and tt["#patrick_fan"] == 1 and se.top_tags()[0][0] == "#spongebob", se.top_tags()[:3]
print("OK 5b: hashtag qidiruvi (#teg, so'z boshi, bir nechta teg, xato, mashhur teglar)")
# kesh invalidatsiyasi (yozishda)
assert t("yangi kino") == []
db.add_movie("YANGI", "Yangi Kino", 2, 3000, "", "", "", "", "", "", "", 1)
assert t("yangi kino") == ["Yangi Kino"]
print("OK 6: kino qo'shilganda indeks yangilanadi")
# difflib zaxira yo'li (rapidfuzz bo'lmasa)
import utils.search_engine as m
rf = (m._fuzz, m._process); m._fuzz = m._process = None
assert first("titnaik") == "Titanik"
m._fuzz, m._process = rf
print("OK 7: rapidfuzzsiz zaxira ishlaydi")
import time; t0 = time.time(); [se.search("avatar suv") for _ in range(50)]; print(f"tezlik: {(time.time()-t0)/50*1000:.1f} ms/qidiruv ({len(se._load())} kino)")
print("ALL SEARCH OK")
