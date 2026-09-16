# Standalone SVG figures written directly: no plotting dependency and no embedded script.
# Each figure is one file that opens in a browser and imports into a document unchanged.
#
# LEGEND
#   W,H,M      : figure width, height and margins (left, right, top, bottom)
#   sc         : linear scale from data units to figure units
#   nice,tks   : rounded tick step, and the tick positions it produces
#   ser        : one series: label, x values, y values
#   CL,DA      : line colours and dash patterns, distinguishable in grey
#   esc        : escape text for XML

from pathlib import Path

import numpy as np

W, H = 900, 480
M = (86, 24, 34, 54)
CL = ("#1f3b73", "#b2182b", "#1b7837", "#d95f02", "#6a3d9a")
DA = ("", "6 3", "2 3", "9 3 2 3", "1 4")
FT = "Georgia, 'Times New Roman', serif"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def nice(x):
    """The 1, 2 or 5 times a power of ten nearest above x."""
    if x <= 0:
        return 1.0
    p = 10 ** np.floor(np.log10(x))
    return float(next(m * p for m in (1, 2, 2.5, 5, 10) if x <= m * p))


def tks(lo, hi, n=6):
    """Tick positions covering the range, on a rounded step."""
    s = nice((hi - lo) / max(n, 1))
    a = np.floor(lo / s) * s
    return np.arange(a, hi + s / 2, s), s


def sc(lo, hi, a, b):
    if hi <= lo:
        hi = lo + 1
    return lambda v: a + (np.asarray(v, dtype=float) - lo) * (b - a) / (hi - lo)


def pts(x, y, gx, gy):
    """A polyline's point list; simpler and smaller than a path of line commands."""
    return " ".join(f"{gx(a):.1f},{gy(b):.1f}" for a, b in zip(x, y))


def num(v):
    """Tick text: an integer when the value is one, else two decimals."""
    return f"{v:,.0f}" if abs(v - round(v)) < 1e-9 else f"{v:,.2f}"


def txt(x, y, s, an="middle", sz=13, w="normal", fill="#111"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{an}" font-family="{FT}" '
            f'font-size="{sz}" font-weight="{w}" fill="{fill}">{esc(s)}</text>')


def _frame(ti, xl, yl, xt, yt, fx, fy, x0, x1, y0, y1):
    """Axes, ticks and labels. Horizontal rules only, which is what a reader needs."""
    o = [f'<rect width="{W}" height="{H}" fill="#fff"/>']
    if ti:
        o.append(txt(W / 2, 22, ti, sz=16, w="bold"))
    for v, y in yt:
        o.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" '
                 f'stroke="{"#333" if abs(v) < 1e-12 else "#ddd"}" stroke-width="1"/>')
        o.append(txt(x0 - 8, y + 4, fy(v), "end", 12))
    for v, x in xt:
        o.append(f'<line x1="{x:.1f}" y1="{y1}" x2="{x:.1f}" y2="{y1 + 5}" '
                 f'stroke="#333" stroke-width="1"/>')
        o.append(txt(x, y1 + 19, fx(v), "middle", 12))
    o.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#333"/>')
    o.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#333"/>')
    if xl:
        o.append(txt((x0 + x1) / 2, H - 8, xl, sz=13))
    if yl:
        o.append(f'<g transform="translate(16,{(y0 + y1) / 2}) rotate(-90)">'
                 + txt(0, 0, yl, sz=13) + "</g>")
    return o


def _legend(names, x, y, dash=True):
    o = []
    for i, n in enumerate(names):
        yy = y + 18 * i
        o.append(f'<line x1="{x}" y1="{yy}" x2="{x + 26}" y2="{yy}" stroke="{CL[i % 5]}" '
                 f'stroke-width="2.2" stroke-dasharray="{DA[i % 5] if dash else ""}"/>')
        o.append(txt(x + 32, yy + 4, n, "start", 12))
    return o


def save(p, body):
    Path(p).write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{W}" height="{H}" viewBox="0 0 {W} {H}">\n' + "\n".join(body) + "\n</svg>\n")


def lines(p, ser, ti="", xl="", yl="", fx=num, xt=None):
    """One line per series on a shared axis."""
    x0, x1, y0, y1 = M[0], W - M[1], M[2], H - M[3]
    xs = np.concatenate([s[1] for s in ser])
    ys = np.concatenate([s[2] for s in ser])
    yv, _ = tks(min(ys.min(), 0), max(ys.max(), 0))
    gx, gy = sc(xs.min(), xs.max(), x0, x1), sc(yv[0], yv[-1], y1, y0)
    xv = tks(xs.min(), xs.max())[0] if xt is None else xt
    o = _frame(ti, xl, yl, [(v, gx(v)) for v in xv],
               [(v, gy(v)) for v in yv], fx, num, y0, x1, y0, y1)
    for i, (n, x, y) in enumerate(ser):
        o.append(f'<polyline points="{pts(x, y, gx, gy)}" fill="none" '
                 f'stroke="{CL[i % 5]}" stroke-width="2.2" '
                 f'stroke-dasharray="{DA[i % 5]}"/>')
    o += _legend([s[0] for s in ser], x0 + 14, y0 + 16)
    save(p, o)


def bars(p, cats, ser, ti="", xl="", yl=""):
    """Grouped bars: one group per category, one bar per series."""
    x0, x1, y0, y1 = M[0], W - M[1], M[2], H - M[3]
    ys = np.concatenate([s[1] for s in ser])
    yv, _ = tks(min(ys.min(), 0), max(ys.max(), 0))
    gy = sc(yv[0], yv[-1], y1, y0)
    n, k = len(cats), len(ser)
    wd = (x1 - x0) / max(n, 1)
    bw = wd * 0.8 / k
    o = _frame(ti, xl, yl, [(i, x0 + wd * (i + 0.5)) for i in range(n)],
               [(v, gy(v)) for v in yv], lambda i: cats[int(i)], num, y0, x1, y0, y1)
    for i, (_, y) in enumerate(ser):
        for j, v in enumerate(y):
            xx = x0 + wd * (j + 0.1) + bw * i
            a, b = gy(0), gy(v)
            o.append(f'<rect x="{xx:.1f}" y="{min(a, b):.1f}" width="{bw:.1f}" '
                     f'height="{abs(b - a):.1f}" fill="{CL[i % 5]}" fill-opacity="0.85"/>')
    for i, s in enumerate(ser):
        yy = y0 + 16 + 18 * i
        o.append(f'<rect x="{x0 + 14}" y="{yy - 9}" width="20" height="11" '
                 f'fill="{CL[i % 5]}" fill-opacity="0.85"/>')
        o.append(txt(x0 + 40, yy, s[0], "start", 12))
    save(p, o)


def trace(p, t, prt, pda, e, g, ti="", cap=""):
    """Two panels sharing one clock: prices above, stored energy and dispatch below."""
    x0, x1 = M[0], W - M[1]
    ya, yb = M[2] + 6, H / 2 - 22
    yc, yd = H / 2 + 22, H - M[3]
    h = (t - t[0]) / 3600
    gx = sc(h[0], h[-1], x0, x1)
    xt = [(v, gx(v)) for v in np.arange(0, h[-1] + 1e-9, 6)]
    pv, _ = tks(min(prt.min(), pda.min(), 0), max(prt.max(), pda.max()))
    gp = sc(pv[0], pv[-1], yb, ya)
    o = [f'<rect width="{W}" height="{H}" fill="#fff"/>']
    if ti:
        o.append(txt(W / 2, 20, ti, sz=15, w="bold"))
    o += _frame("", "", "", [], [(v, gp(v)) for v in pv], num, num, x0, x1, ya, yb)[1:]
    for i, y in enumerate((prt, pda)):
        o.append(f'<polyline points="{pts(h, y, gx, gp)}" fill="none" stroke="{CL[i]}" '
                 f'stroke-width="1.6" stroke-dasharray="{DA[i]}"/>')
    o += _legend(["real time $/MWh", "day ahead $/MWh"], x0 + 14, ya + 14)
    ev, _ = tks(min(g.min(), 0), max(e.max(), g.max()))
    ge = sc(ev[0], ev[-1], yd, yc)
    o += _frame("", "", "", xt, [(v, ge(v)) for v in ev],
                num, lambda v: f"{v:,.1f}", x0, x1, yc, yd)[1:]
    o.append(txt((x0 + x1) / 2, yd + 38, "hour of the local day", sz=13))
    for i, (n, y) in enumerate((("stored MWh", e), ("grid MW", g))):
        o.append(f'<polyline points="{pts(h, y, gx, ge)}" fill="none" '
                 f'stroke="{CL[i + 2]}" stroke-width="1.8" '
                 f'stroke-dasharray="{DA[i + 2]}"/>')
        o.append(f'<line x1="{x0 + 14}" y1="{yc + 14 + 18 * i}" x2="{x0 + 40}" '
                 f'y2="{yc + 14 + 18 * i}" stroke="{CL[i + 2]}" stroke-width="1.8" '
                 f'stroke-dasharray="{DA[i + 2]}"/>')
        o.append(txt(x0 + 46, yc + 18 + 18 * i, n, "start", 12))
    if cap:
        o.append(txt(x0, H - 6, cap, "start", 11, fill="#444"))
    save(p, o)
