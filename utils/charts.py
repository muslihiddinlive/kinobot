"""Kichik diagramma chizuvchi (faqat Pillow): ustun va chiziq, bir rasmda bir nechta panel."""
import io

from PIL import Image, ImageDraw, ImageFont

BG, FG, GRID, MUTED = (255, 255, 255), (33, 37, 41), (225, 229, 234), (120, 128, 138)
PALETTE = [(37, 99, 235), (16, 185, 129), (245, 158, 11), (239, 68, 68), (139, 92, 246)]


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                       # eski Pillow
        return ImageFont.load_default()


def _nice_max(v: float) -> float:
    if v <= 0:
        return 1.0
    import math
    exp = 10 ** int(math.floor(math.log10(v)))
    for m in (1, 2, 4, 8, 10):
        if v <= m * exp:
            return m * exp
    return 10 * exp


def _fmt(v: float) -> str:
    v = float(v)
    if v >= 1_000_000: return f"{v / 1_000_000:.1f}M"
    if v >= 10_000:    return f"{v / 1000:.0f}k"
    if v >= 1000:      return f"{v / 1000:.1f}k"
    return f"{v:.0f}"


def _panel(d: ImageDraw.ImageDraw, box, title, labels, series):
    """box=(x0,y0,x1,y1). series: [{"name","values","kind":"bar"|"line","color"}]"""
    x0, y0, x1, y1 = box
    ft, fs, fl = _font(22), _font(14), _font(15)
    d.text((x0, y0), title, fill=FG, font=ft)
    # legend
    lx = x1
    for i, s in enumerate(reversed(series)):
        col = s.get("color") or PALETTE[(len(series) - 1 - i) % len(PALETTE)]
        w = int(d.textlength(s["name"], font=fl))
        lx -= w + 28
        d.rectangle((lx, y0 + 7, lx + 14, y0 + 21), fill=col)
        d.text((lx + 20, y0 + 5), s["name"], fill=MUTED, font=fl)
    top, left, bottom, right = y0 + 44, x0 + 52, y1 - 30, x1 - 8
    n = max(len(labels), 1)
    vmax = _nice_max(max([max(s["values"] or [0]) for s in series] + [0]))
    for i in range(5):
        y = bottom - (bottom - top) * i / 4
        d.line((left, y, right, y), fill=GRID, width=1)
        d.text((x0, y - 8), _fmt(vmax * i / 4), fill=MUTED, font=fs)
    slot = (right - left) / n
    bars = [s for s in series if s.get("kind", "bar") == "bar"]
    for si, s in enumerate(bars):
        col = s.get("color") or PALETTE[series.index(s) % len(PALETTE)]
        bw = max(2, slot * 0.7 / max(len(bars), 1))
        for i, v in enumerate(s["values"]):
            cx = left + slot * i + slot * 0.15 + bw * si
            h = (bottom - top) * (v / vmax) if vmax else 0
            if h > 0:
                d.rectangle((cx, bottom - h, cx + bw, bottom), fill=col)
    for s in [s for s in series if s.get("kind") == "line"]:
        col = s.get("color") or PALETTE[series.index(s) % len(PALETTE)]
        pts = [(left + slot * (i + 0.5), bottom - (bottom - top) * (v / vmax if vmax else 0)) for i, v in enumerate(s["values"])]
        if len(pts) > 1:
            d.line(pts, fill=col, width=3)
        for x, y in pts:
            d.ellipse((x - 3, y - 3, x + 3, y + 3), fill=col)
    step = max(1, n // 8)
    for i in range(0, n, step):
        lab = str(labels[i])
        d.text((left + slot * (i + 0.5) - d.textlength(lab, font=fs) / 2, bottom + 6), lab, fill=MUTED, font=fs)


def render(panels, width=940, panel_h=330) -> bytes:
    """panels: [{"title","labels","series":[...]}] -> PNG bytes."""
    h = panel_h * len(panels) + 20
    img = Image.new("RGB", (width, h), BG)
    d = ImageDraw.Draw(img)
    for i, p in enumerate(panels):
        _panel(d, (24, 14 + i * panel_h, width - 24, 14 + (i + 1) * panel_h - 10), p["title"], p["labels"], p["series"])
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
