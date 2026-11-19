#!/usr/bin/env python3
"""Build entry.png: a 42-story light-newsprint world broadsheet for 18 Nov 2026.

The page is HTML + inline SVG (Gulf tactical map, summit graphic, IPO bar chart,
light-distance scale, Senate seat bar and other micro-charts), laid out in
headless Chrome through Playwright and screenshotted at 1024x1024.

Every build runs a DOM geometry audit before it writes anything:

* the page fits 1024x1024 (no scroll overflow);
* no card, story or digest column clips its content;
* no two text blocks overlap, and no SVG label overlaps another or leaves its SVG;
* exactly 42 distinct stories (data-s ids 1..42 from the fact brief) are on the page;
* the leftover space at the foot of every digest column stays small.

Build-time only (needs Playwright, Chrome, Pillow, NumPy). The shipped
entrypoint, main.py, is standard-library Python that copies entry.png.
"""

from __future__ import annotations

import argparse
import html
import io
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
CHROME = "/usr/bin/google-chrome"
SIZE = 1024
MAX_BYTES = 1024 * 1024

# --------------------------------------------------------------------------- #
# Palette
# --------------------------------------------------------------------------- #
PAPER = "#FBF8F1"
CARD = "#FFFFFF"
HAIR = "#D6CFC2"
RULE = "#1A1A1A"
INK = "#111827"
SLATE = "#374151"
CRIMSON = "#B91C1C"
COBALT = "#1D4ED8"
EMERALD = "#047857"
AMBER = "#B45309"
INDIGO = "#4338CA"
TEAL = "#0E7490"
BROWN = "#7C2D12"

SEA = "#DCE8F3"
LAND = "#F3EEE2"
COAST = "#7A6F5C"


def esc(text: str) -> str:
    return html.escape(text, quote=False)


# --------------------------------------------------------------------------- #
# SVG: Persian Gulf / Strait of Hormuz tactical map
# --------------------------------------------------------------------------- #
LON0, LON1 = 47.2, 58.8
LAT0, LAT1 = 23.2, 30.65
MAP_H = 228
KY = MAP_H / (LAT1 - LAT0)
KX = KY * 0.891                   # cos(27 N): keeps the map conformal at mid-Gulf
MAP_W = round(KX * (LON1 - LON0))


def px(lon: float, lat: float) -> tuple[float, float]:
    return (lon - LON0) * KX, (LAT1 - lat) * KY


def poly(points) -> str:
    out = []
    for i, (lon, lat) in enumerate(points):
        x, y = px(lon, lat)
        out.append(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}")
    return " ".join(out) + " Z"


# One land mass wrapping the Gulf: Iranian coast east to west, Iraq/Kuwait,
# the Saudi coast, Qatar, the UAE, Musandam and the Omani coast, then the
# frame corners. Coordinates are (longitude, latitude).
GULF_LAND = [
    (58.8, 25.45), (58.2, 25.55), (57.77, 25.64), (57.4, 25.85), (57.12, 26.45),
    (56.95, 26.95), (56.6, 27.14), (56.27, 27.2), (55.9, 27.12), (55.58, 27.02),
    (55.25, 26.8), (54.88, 26.56), (54.5, 26.6), (54.0, 26.75), (53.5, 26.9),
    (53.0, 27.15), (52.6, 27.47), (52.06, 27.83), (51.5, 27.92), (51.2, 28.3),
    (50.83, 28.97), (50.65, 29.3), (50.5, 29.58), (50.17, 30.05), (49.7, 30.2),
    (49.08, 30.43), (48.8, 30.12), (48.5, 29.97), (48.3, 29.78), (48.05, 29.62),
    (47.75, 29.45), (48.0, 29.35), (48.1, 29.1), (48.25, 28.8), (48.4, 28.55),
    (48.6, 28.1), (48.9, 27.6), (49.3, 27.2), (49.66, 27.0), (50.0, 26.72),
    (50.16, 26.64), (50.1, 26.45), (50.2, 26.25), (50.2, 25.95), (50.12, 25.7),
    (50.25, 25.4), (50.5, 24.95), (50.8, 24.75), (50.85, 25.0), (50.8, 25.5),
    (51.0, 25.95), (51.22, 26.15), (51.45, 25.95), (51.6, 25.5), (51.55, 25.25),
    (51.6, 24.95), (51.45, 24.6), (51.6, 24.25), (52.2, 24.15), (52.8, 24.15),
    (53.6, 24.1), (54.1, 24.25), (54.4, 24.45), (54.7, 24.8), (55.05, 25.0),
    (55.3, 25.25), (55.5, 25.45), (55.95, 25.8), (56.1, 26.05), (56.2, 26.25),
    (56.35, 26.38), (56.45, 26.2), (56.35, 25.85), (56.35, 25.4), (56.35, 25.1),
    (56.45, 24.75), (56.75, 24.35), (57.3, 23.95), (57.9, 23.72), (58.4, 23.6),
    (58.8, 23.55), (58.8, 23.2), (47.2, 23.2), (47.2, 30.65), (58.8, 30.65),
]
BAHRAIN = [(50.45, 26.25), (50.62, 26.24), (50.66, 26.05), (50.6, 25.8),
           (50.5, 25.9), (50.45, 26.1)]
QESHM = [(55.28, 26.72), (55.6, 26.62), (55.95, 26.72), (56.28, 26.93),
         (56.15, 26.99), (55.85, 26.93), (55.5, 26.9), (55.3, 26.83)]


def burst(x: float, y: float, r: float, color: str = CRIMSON) -> str:
    pts = []
    for i in range(16):
        rad = r if i % 2 == 0 else r * 0.45
        ang = i * 3.14159265 / 8
        pts.append(f"{x + rad * np.cos(ang):.1f},{y + rad * np.sin(ang):.1f}")
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r * 1.9:.1f}" fill="{color}" '
            f'opacity="0.13"/><polygon points="{" ".join(pts)}" fill="{color}"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r * 0.28:.1f}" fill="#fff"/>')


def tanker(x: float, y: float, ang: float = -20) -> str:
    return (f'<g transform="translate({x:.1f},{y:.1f}) rotate({ang})">'
            f'<path d="M-7,-2 L5,-2 L8,0 L5,2 L-7,2 Z" fill="{INK}"/>'
            f'<rect x="-6" y="-1" width="3" height="2" fill="#fff"/></g>')


def label(x, y, text, size=7.0, color=INK, weight=800, ls=0.6, anchor="start",
          italic=False, family="Lato", halo=True) -> str:
    style = "font-style:italic;" if italic else ""
    stroke = (f' stroke="{CARD}" stroke-width="2.4" paint-order="stroke" '
              f'stroke-linejoin="round"') if halo else ""
    return (f'<text class="sl" x="{x:.1f}" y="{y:.1f}" font-family="{family}" '
            f'font-size="{size}" font-weight="{weight}" letter-spacing="{ls}" '
            f'fill="{color}" text-anchor="{anchor}" style="{style}"{stroke}>'
            f'{esc(text)}</text>')


def art_gulf() -> str:
    b = []
    # graticule
    for lon in range(48, 59, 2):
        x, _ = px(lon, 0)
        b.append(f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{MAP_H}" '
                 f'stroke="#9DB3C8" stroke-width="0.4" stroke-dasharray="1.5 2.5"/>')
    for lat in range(24, 31, 2):
        _, y = px(0, lat)
        b.append(f'<line x1="0" y1="{y:.1f}" x2="{MAP_W}" y2="{y:.1f}" '
                 f'stroke="#9DB3C8" stroke-width="0.4" stroke-dasharray="1.5 2.5"/>')
    b.append(f'<path d="{poly(GULF_LAND)}" fill="{LAND}" stroke="{COAST}" '
             f'stroke-width="0.9" stroke-linejoin="round"/>')
    b.append(f'<path d="{poly(BAHRAIN)}" fill="{LAND}" stroke="{COAST}" stroke-width="0.8"/>')
    b.append(f'<path d="{poly(QESHM)}" fill="#F7D9D4" stroke="{CRIMSON}" stroke-width="0.9"/>')
    hx, hy = px(56.46, 27.06)
    b.append(f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="1.6" fill="{LAND}" stroke="{COAST}" stroke-width="0.6"/>')
    # Hormuz choke-point bracket
    a1 = px(56.30, 26.45)
    a2 = px(56.62, 27.10)
    b.append(f'<line x1="{a1[0]:.1f}" y1="{a1[1]:.1f}" x2="{a2[0]:.1f}" y2="{a2[1]:.1f}" '
             f'stroke="{INK}" stroke-width="1.1" stroke-dasharray="2 1.6"/>')
    # Iranian retaliation arcs toward Kuwait and Bahrain
    ox, oy = px(51.7, 29.6)
    kx, ky = px(47.58, 29.33)
    bx, by = px(50.56, 26.12)
    b.append(f'<path d="M{ox:.1f},{oy:.1f} Q{(ox + kx) / 2:.1f},{oy - 30:.1f} {kx + 5:.1f},{ky - 3:.1f}" '
             f'fill="none" stroke="{CRIMSON}" stroke-width="1.4" stroke-dasharray="3.5 2" '
             f'marker-end="url(#ah)"/>')
    b.append(f'<path d="M{ox:.1f},{oy:.1f} Q{ox - 4:.1f},{(oy + by) / 2:.1f} {bx + 3:.1f},{by - 6:.1f}" '
             f'fill="none" stroke="{CRIMSON}" stroke-width="1.4" stroke-dasharray="3.5 2" '
             f'marker-end="url(#ah)"/>')
    # US strike on Qeshm from the southern Gulf
    sx, sy = px(54.2, 25.75)
    qx, qy = px(55.85, 26.8)
    b.append(f'<path d="M{sx:.1f},{sy:.1f} Q{sx + 18:.1f},{sy - 22:.1f} {qx - 6:.1f},{qy + 3:.1f}" '
             f'fill="none" stroke="{COBALT}" stroke-width="1.6" marker-end="url(#ahb)"/>')
    b.append(burst(qx, qy, 6.5))
    b.append(burst(kx, ky, 5.0))
    b.append(burst(bx, by, 5.0))
    # tankers near the strait
    for lon, lat, ang in ((56.95, 25.75, -55), (57.3, 25.3, -40), (57.95, 24.95, -25)):
        tx, ty = px(lon, lat)
        b.append(tanker(tx, ty, ang))
    # country and water labels
    b.append(label(*px(52.6, 29.55), "IRAN", size=13, weight=900, ls=4.5,
                   color="#6B6252", halo=False))
    b.append(label(*px(47.32, 30.42), "IRAQ", size=6.5, color="#6B6252", ls=1.2, halo=False))
    b.append(label(*px(47.3, 29.86), "KUWAIT", size=6.5, color="#6B6252", ls=1.2, halo=False))
    b.append(label(*px(47.6, 24.1), "SAUDI ARABIA", size=8.5, color="#6B6252", ls=2.2,
                   halo=False, weight=900))
    b.append(label(*px(51.07, 24.48), "QATAR", size=6, color="#6B6252", ls=0.8, halo=False))
    b.append(label(*px(53.5, 23.62), "U.A.E.", size=6.5, color="#6B6252", ls=1.2, halo=False))
    b.append(label(*px(57.35, 23.38), "OMAN", size=6.5, color="#6B6252", ls=1.2, halo=False))
    b.append(label(*px(51.85, 26.95), "PERSIAN GULF", size=7.5, color="#2F5D86",
                   weight=700, ls=1.6, italic=True, family="Noto Serif", halo=False))
    b.append(label(MAP_W - 5, px(0, 24.45)[1], "GULF OF", size=6.5, color="#2F5D86", anchor="end",
                   weight=700, ls=1, italic=True, family="Noto Serif", halo=False))
    b.append(label(MAP_W - 5, px(0, 24.18)[1], "OMAN", size=6.5, color="#2F5D86", anchor="end",
                   weight=700, ls=1, italic=True, family="Noto Serif", halo=False))
    # callouts
    b.append(label(qx - 34, qy + 17, "QESHM ISLAND", size=7.4, color=CRIMSON, weight=900))
    b.append(label(qx - 34, qy + 25.5, "US strike: missile site", size=6.6, color=INK, weight=700, ls=0.2))
    b.append(label(kx + 7, ky + 12, "ALI AL SALEM AIR BASE", size=6.8, color=CRIMSON, weight=900, ls=0.3))
    b.append(label(kx + 7, ky + 20, "Iranian missiles, drones", size=6.4, color=INK, weight=700, ls=0.2))
    b.append(label(bx - 30, by + 18, "BAHRAIN", size=7.2, color=CRIMSON, weight=900))
    b.append(label(bx - 30, by + 26.5, "US radar sites hit", size=6.4, color=INK, weight=700, ls=0.2))
    hlx, hly = px(56.72, 27.32)
    b.append(label(MAP_W - 5, hly - 4, "STRAIT OF HORMUZ", size=7.2, color=INK, weight=900, ls=0.4,
                   anchor="end"))
    b.append(label(MAP_W - 5, hly + 4.5, "tankers on alert", size=6.4, color=SLATE, weight=700, ls=0.2,
                   anchor="end"))
    b.append(label(sx - 26, sy + 10, "US strike route", size=6.4, color=COBALT, weight=900, ls=0.2))
    # scale bar (100 km ~ 0.9 deg of longitude at 26N)
    s0x, s0y = 10, MAP_H - 10
    s1x = s0x + KX * 0.9
    b.append(f'<path d="M{s0x},{s0y - 3} V{s0y} H{s1x:.1f} V{s0y - 3}" fill="none" '
             f'stroke="{INK}" stroke-width="1"/>')
    b.append(label(s1x + 4, s0y, "100 km", size=6.2, weight=700, ls=0.2, halo=False))
    # north arrow
    b.append(f'<g transform="translate({MAP_W - 14},{16})"><path d="M0,-9 L4,4 L0,1.5 L-4,4 Z" '
             f'fill="{INK}"/></g>')
    b.append(label(MAP_W - 14, 30, "N", size=7, anchor="middle", halo=False))
    defs = (f'<defs><marker id="ah" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="6" '
            f'markerHeight="6" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="{CRIMSON}"/></marker>'
            f'<marker id="ahb" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="6" '
            f'markerHeight="6" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="{COBALT}"/></marker></defs>')
    return (f'<svg class="map" viewBox="0 0 {MAP_W} {MAP_H}" width="{MAP_W}" height="{MAP_H}" '
            f'role="img" aria-label="Persian Gulf strike map">{defs}'
            f'<rect width="{MAP_W}" height="{MAP_H}" fill="{SEA}"/>{"".join(b)}'
            f'<rect x="0.5" y="0.5" width="{MAP_W - 1}" height="{MAP_H - 1}" fill="none" '
            f'stroke="{RULE}" stroke-width="1"/></svg>')


# --------------------------------------------------------------------------- #
# SVG: Shenzhen summit graphic
# --------------------------------------------------------------------------- #
def flag_us(x, y, w, h) -> str:
    s = []
    for i in range(7):
        s.append(f'<rect x="{x}" y="{y + i * h / 7:.2f}" width="{w}" height="{h / 7:.2f}" '
                 f'fill="{"#B22234" if i % 2 == 0 else "#fff"}"/>')
    s.append(f'<rect x="{x}" y="{y}" width="{w * 0.42:.1f}" height="{h * 4 / 7:.2f}" fill="#3C3B6E"/>')
    for r in range(3):
        for c in range(4):
            s.append(f'<circle cx="{x + 2 + c * w * 0.42 / 4.3:.1f}" cy="{y + 2 + r * h * 4 / 7 / 3.2:.1f}" '
                     f'r="0.55" fill="#fff"/>')
    return "".join(s)


def star5(cx, cy, r) -> str:
    pts = []
    for i in range(10):
        rad = r if i % 2 == 0 else r * 0.4
        ang = -np.pi / 2 + i * np.pi / 5
        pts.append(f"{cx + rad * np.cos(ang):.2f},{cy + rad * np.sin(ang):.2f}")
    return " ".join(pts)


def flag_cn(x, y, w, h) -> str:
    s = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#DE2910"/>',
         f'<polygon points="{star5(x + w * 0.17, y + h * 0.27, h * 0.16)}" fill="#FFDE00"/>']
    for dx, dy in ((0.33, 0.1), (0.4, 0.2), (0.4, 0.35), (0.33, 0.45)):
        s.append(f'<polygon points="{star5(x + w * dx, y + h * dy, h * 0.055)}" fill="#FFDE00"/>')
    return "".join(s)


def flag_ru(x, y, w, h) -> str:
    return "".join(f'<rect x="{x}" y="{y + i * h / 3:.2f}" width="{w}" height="{h / 3:.2f}" '
                   f'fill="{c}"/>' for i, c in enumerate(("#fff", "#0039A6", "#D52B1E")))


def art_summit() -> str:
    W, H = 368, 82
    b = [f'<rect width="{W}" height="{H}" fill="#F5F1E8"/>']
    # Shenzhen skyline silhouette
    xs = [0, 14, 22, 36, 48, 58, 70, 84, 96, 104, 118, 130, 144, 160, 172, 186,
          200, 214, 226, 240, 252, 266, 280, 292, 306, 320, 334, 348, 360]
    hs = [18, 26, 15, 32, 22, 38, 26, 44, 30, 20, 34, 26, 40, 50, 30, 24,
          54, 34, 28, 42, 26, 38, 22, 32, 26, 40, 20, 30, 16]
    for i, x in enumerate(xs):
        w = (xs[i + 1] - x - 2) if i + 1 < len(xs) else W - x
        b.append(f'<rect x="{x}" y="{H - hs[i]}" width="{w}" height="{hs[i]}" fill="#E4DDCF"/>')
    # Ping An-style spire, tallest tower
    b.append(f'<path d="M196,{H} L198,{H - 64} L201,{H - 76} L204,{H - 64} L206,{H} Z" fill="#D9D0BE"/>')
    b.append(f'<line x1="0" y1="{H - 0.5}" x2="{W}" y2="{H - 0.5}" stroke="{HAIR}"/>')
    # three leaders around a declaration seal
    cx = W / 2
    pos = [(60, "TRUMP", "United States", flag_us),
           (cx, "XI JINPING", "China · host", flag_cn),
           (W - 60, "PUTIN", "Russia", flag_ru)]
    b.append(f'<path d="M84,25 L{cx - 22},25 M{cx + 22},25 L{W - 84},25" stroke="{INK}" '
             f'stroke-width="1" stroke-dasharray="2 2"/>')
    for x, name, sub, fn in pos:
        fw, fh = 30, 20
        b.append(f'<rect x="{x - fw / 2 - 1.5}" y="{14 - 1.5}" width="{fw + 3}" height="{fh + 3}" fill="#fff" '
                 f'stroke="{INK}" stroke-width="0.8"/>')
        b.append(fn(x - fw / 2, 14, fw, fh))
        b.append(label(x, 46, name, size=9, weight=900, ls=1.2, anchor="middle"))
        b.append(label(x, 55.5, sub, size=7, weight=700, ls=0.2, anchor="middle", color=SLATE))
    b.append(label(cx - 79, 74, "\u201cA NUCLEAR WAR CANNOT BE WON\u201d", size=8.2, weight=900,
                   ls=0.6, color=CRIMSON))
    return (f'<svg class="art" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="Shenzhen summit">{"".join(b)}</svg>')


# --------------------------------------------------------------------------- #
# SVG micro-charts
# --------------------------------------------------------------------------- #
def art_ipo() -> str:
    W, H = 150, 92
    rows = [("Saudi Aramco \u201919", 1700, "$1.7tn", SLATE),
            ("ANTHROPIC \u201926", 1500, "$1.5tn", EMERALD),
            ("Alibaba \u201914", 168, "$168bn", SLATE),
            ("Facebook \u201912", 104, "$104bn", SLATE)]
    b = [label(1, 8, "VALUE AT IPO PRICING", size=6.8, weight=900, ls=0.8, color=SLATE, halo=False)]
    for i, (name, v, txt, col) in enumerate(rows):
        y = 16 + i * 19
        bw = max(3.0, 104 * v / 1700)
        bold = name.startswith("ANTH")
        b.append(label(1, y + 6, name, size=7 if bold else 6.6, weight=900 if bold else 700,
                       ls=0.2, color=INK, halo=False))
        b.append(f'<rect x="0" y="{y + 8.5}" width="{bw:.1f}" height="7" fill="{col}"'
                 f'{"" if bold else " opacity=\"0.55\""}/>')
        b.append(label(bw + 3, y + 15, txt, size=7, weight=900, ls=0.1,
                       color=EMERALD if bold else INK, halo=False))
    return (f'<svg class="art" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="IPO valuations">{"".join(b)}</svg>')


def art_voyager() -> str:
    W, H = 150, 92
    b = [label(1, 8, "LIGHT-TRAVEL TIME FROM EARTH", size=6.6, weight=900, ls=0.5,
               color=SLATE, halo=False)]
    # log scale of one-way light time in seconds: 1 s .. 1 day
    def lx(sec: float) -> float:
        return 13 + 129 * (np.log10(sec) - 0) / (np.log10(86400) - 0)
    y = 50
    b.append(f'<line x1="4" y1="{y}" x2="146" y2="{y}" stroke="{INK}" stroke-width="1.2"/>')
    marks = [(1.28, "Moon", "1.3 s", -1), (499, "Sun", "8.3 min", 1),
             (15000, "Neptune", "4.2 h", -2), (86400, "VOYAGER 1", "1 light-day", 1)]
    b.append(f'<circle cx="{lx(1):.1f}" cy="{y}" r="3.2" fill="#2563EB"/>')
    b.append(label(lx(1) - 2, y + 11, "Earth", size=6.4, weight=700, halo=False))
    for sec, name, t, side in marks:
        x = lx(sec)
        last = name.startswith("VOY")
        col = INDIGO if last else INK
        b.append(f'<line x1="{x:.1f}" y1="{y - 4}" x2="{x:.1f}" y2="{y + 4}" stroke="{col}" stroke-width="1.2"/>')
        anchor = "end" if last or side == -2 else "middle"
        if side == -2:
            x += 3
        if side < 0:
            b.append(label(x, y - 15, name, size=6.6, weight=900, anchor=anchor, color=col, halo=False))
            b.append(label(x, y - 7, t, size=6.2, weight=700, anchor=anchor, color=SLATE, halo=False))
        else:
            b.append(label(x, y + 12, name, size=6.6 if not last else 7, weight=900,
                           anchor=anchor, color=col, halo=False))
            b.append(label(x, y + 20, t, size=6.2, weight=700, anchor=anchor, color=SLATE, halo=False))
    # probe glyph
    vx = lx(86400)
    b.append(f'<g transform="translate({vx - 2:.1f},{y - 14})"><circle r="4" fill="none" '
             f'stroke="{INDIGO}" stroke-width="1.2"/><line x1="-8" y1="0" x2="8" y2="0" '
             f'stroke="{INDIGO}" stroke-width="1.2"/><line x1="0" y1="4" x2="0" y2="10" '
             f'stroke="{INDIGO}" stroke-width="1"/></g>')
    b.append(label(1, 88, "log scale \u00b7 25.9bn km \u2248 173 AU", size=6.2, weight=700,
                   color=SLATE, halo=False, ls=0.2))
    return (f'<svg class="art" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="Voyager distance scale">{"".join(b)}</svg>')


def art_scales() -> str:
    W, H = 96, 92
    c = INK
    b = [f'<line x1="48" y1="10" x2="48" y2="70" stroke="{c}" stroke-width="2.2"/>',
         f'<circle cx="48" cy="9" r="3" fill="{c}"/>',
         f'<line x1="16" y1="20" x2="80" y2="20" stroke="{c}" stroke-width="2"/>',
         f'<path d="M16,20 L6,44 M16,20 L26,44 M80,20 L70,40 M80,20 L90,40" stroke="{c}" stroke-width="0.9"/>',
         f'<path d="M4,44 Q16,54 28,44 Z" fill="{CRIMSON}"/>',
         f'<path d="M68,40 Q80,50 92,40 Z" fill="{c}"/>',
         f'<path d="M34,74 L62,74 L58,68 L38,68 Z" fill="{c}"/>',
         f'<rect x="30" y="74" width="36" height="4" fill="{c}"/>',
         label(48, 89, "THE HAGUE", size=7, weight=900, ls=1.2, anchor="middle", halo=False)]
    return (f'<svg class="art" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="Scales of justice">{"".join(b)}</svg>')


def art_senate() -> str:
    W, H = 168, 11
    b = []
    for i in range(100):
        col, row = i // 2, i % 2
        fill = COBALT if i < 56 else CRIMSON
        b.append(f'<rect x="{col * 3.36:.2f}" y="{row * 4.4 + 1}" width="2.7" height="3.6" fill="{fill}"/>')
    x50 = 25 * 3.36 - 0.35
    b.append(f'<line x1="{x50:.1f}" y1="0" x2="{x50:.1f}" y2="10.5" stroke="{INK}" stroke-width="0.9"/>')
    return (f'<svg class="art" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="Senate 56 of 100">{"".join(b)}</svg>')


def art_ipcc() -> str:
    W, H = 176, 30
    b = [f'<line x1="6" y1="12" x2="170" y2="12" stroke="{INK}" stroke-width="1"/>']
    for i, yr in enumerate(range(2026, 2031)):
        x = 10 + i * 38
        hot = yr in (2028, 2029)
        b.append(f'<circle cx="{x}" cy="12" r="{3.6 if hot else 2}" fill="{EMERALD if yr == 2028 else (AMBER if yr == 2029 else INK)}"/>')
        b.append(label(x, 6, str(yr), size=6.4, weight=900 if hot else 700, anchor="middle",
                       color=INK if hot else SLATE, halo=False))
    b.append(label(86, 25, "EU, Africa, islands", size=6.2, weight=800, anchor="middle",
                   color=EMERALD, halo=False, ls=0.1))
    b.append(label(175, 25, "China, India, Saudi", size=6.2, weight=800, anchor="end",
                   color=AMBER, halo=False, ls=0.1))
    return (f'<svg class="art" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="IPCC AR7 timeline">{"".join(b)}</svg>')


def flag_ve(x, y, w, h) -> str:
    s = "".join(f'<rect x="{x}" y="{y + i * h / 3:.2f}" width="{w}" height="{h / 3:.2f}" fill="{c}"/>'
                for i, c in enumerate(("#FFCC00", "#00247D", "#CF142B")))
    for k in range(8):
        ang = np.pi * (0.15 + 0.7 * k / 7)
        s += (f'<circle cx="{x + w / 2 - np.cos(ang) * h * 0.26:.2f}" '
              f'cy="{y + h * 0.62 - np.sin(ang) * h * 0.26:.2f}" r="0.5" fill="#fff"/>')
    return s


def art_flags_us_ve() -> str:
    W, H = 70, 26
    b = [f'<rect x="0.5" y="2.5" width="28" height="19" fill="#fff" stroke="{INK}" stroke-width="0.6"/>',
         flag_us(1, 3, 27, 18),
         f'<rect x="41.5" y="2.5" width="28" height="19" fill="#fff" stroke="{INK}" stroke-width="0.6"/>',
         flag_ve(42, 3, 27, 18),
         f'<path d="M30,12 L40,12 M37,9 L40,12 L37,15 M33,9 L30,12 L33,15" stroke="{INK}" '
         f'stroke-width="1.1" fill="none"/>']
    return (f'<svg class="art" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="US and Venezuela flags">{"".join(b)}</svg>')


def art_euro() -> str:
    W, H = 64, 40
    b = [f'<circle cx="20" cy="20" r="17" fill="#003399"/>']
    for k in range(12):
        ang = 2 * np.pi * k / 12
        b.append(f'<polygon points="{star5(20 + 11.5 * np.cos(ang), 20 + 11.5 * np.sin(ang), 2.1)}" fill="#FFCC00"/>')
    b.append(f'<path d="M42,13 L58,20 L42,27 Z" fill="{COBALT}"/>')
    b.append(f'<rect x="47" y="8" width="15" height="5" fill="#0057B7"/>'
             f'<rect x="47" y="13" width="15" height="5" fill="#FFD700"/>')
    return (f'<svg class="art" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="EU to Ukraine">{"".join(b)}</svg>')


def art_rain() -> str:
    W, H = 30, 34
    b = [f'<path d="M17,3 C24,14 29,20 29,27 A12,12 0 0 1 5,27 C5,20 10,14 17,3 Z" fill="{COBALT}"/>',
         f'<path d="M11,26 A6,6 0 0 0 16,32" stroke="#fff" stroke-width="1.6" fill="none"/>']
    return (f'<svg class="art" viewBox="0 0 34 40" width="{W}" height="{H}" role="img" '
            f'aria-label="Rain">{"".join(b)}</svg>')


# --------------------------------------------------------------------------- #
# Stories (ids are the numbers in briefs/news-20261118-42stories.md)
# --------------------------------------------------------------------------- #
def src(text: str) -> str:
    return f'<span class="src">[{esc(text)}]</span>'


DIGEST = [
    ("me", "Middle East", CRIMSON, [
        (2, "Houthi drones hit Saudi pipeline.",
         "Yemen\u2019s Houthis target pumping stations on the East\u2013West oil line near Riyadh.",
         "Just Security / Reuters"),
        (3, "Hormuz shipping on alert.",
         "Tankers near the strait face heightened security warnings after projectile strikes and interceptions.",
         "CBS / Reuters"),
        (4, "Board of Peace faults both sides.",
         "Trump\u2019s panel hands the UN Security Council a 12-page report on Israeli and Hamas truce breaches.",
         "UN / Just Security"),
        (5, "Israeli push in central Gaza.",
         "Hamas condemns new Israeli advances into the central Strip as the truce frays.",
         "AP / Yeni \u015eafak"),
        (7, "Quake recovery reviewed.",
         "UN bodies assess quake recovery and cross-border aid needs in T\u00fcrkiye and Syria.",
         "UN"),
    ]),
    ("ap", "Asia-Pacific", TEAL, [
        (12, "Japan pitches an Asian oil reserve.",
         "PM Sanae Takaichi proposes an IEA-style Asian strategic petroleum reserve agency to buffer Gulf shocks.",
         "Reuters / MUFG"),
        (13, "Manila\u2013Santiago FTA.",
         "The Philippines and Chile sign a free-trade pact on the Shenzhen sidelines, Manila\u2019s first with a Latin American nation.",
         "APEC / Reuters"),
        (14, "Savar highways blocked.",
         "Thousands of garment workers in Bangladesh demand higher basic wages amid unrest in Narail and Gopalganj.",
         "AP / Morning Star"),
        (15, "NZ tsunami alert lifted.",
         "NEMA briefly warns the North Island\u2019s East Coast of tidal surges with no local quake.",
         "NEMA / 1News"),
    ]),
    ("eu", "Europe", COBALT, [
        (18, "Ukraine civilian toll at a high.",
         "UN monitors say 2026 casualties already exceed prior annual totals as Putin resists winter peace talks.",
         "UN HRMMU"),
        (20, "No return to Russian energy.",
         "At P-TEC talks, ministers refuse to ease Russian oil and gas sanctions despite Gulf supply strain.",
         "Atlantic Council"),
        (21, "UK inflation hits 3.6%,",
         "a 12-month high on fuel and tobacco; TfL warns riders of a transit-card data breach.",
         "ONS / SCMP"),
        (22, "Water cannon in Brussels.",
         "Police disperse students blocking ring roads over tuition hikes; Spain opens an abuse probe into Julio Iglesias.",
         "Morning Star / SCMP"),
    ]),
    ("am", "Americas", AMBER, [
        (30, "Machado to review oil deals.",
         "Venezuela\u2019s opposition leader says US oil contracts signed under interim rule face case-by-case scrutiny.",
         "BNamericas"),
        (31, "Colombia to host AC3 summit.",
         "Hegseth meets President Abelardo de la Espriella in Bogot\u00e1 as Colombia widens its role in the US-backed coalition.",
         "Al Jazeera"),
        (32, "Uncontacted Aw\u00e1 emerge.",
         "About 20 isolated Aw\u00e1 people leave Maranh\u00e3o\u2019s rainforest seeking food, spotlighting illegal logging.",
         "Al Jazeera / Reuters"),
        (33, "Dari\u00e9n crossings down 90%.",
         "The UN migration agency sees northbound flows plunge as routes into Brazil and Uruguay grow.",
         "IOM"),
    ]),
    ("af", "Africa", BROWN, [
        (34, "Medieval cathedral found in Sudan.",
         "One of the region\u2019s largest hidden church floors is unearthed amid the SAF\u2013RSF war.",
         "AP / Pew"),
        (35, "Pretoria rebukes Abuja\u2019s envoy.",
         "A d\u00e9marche to High Commissioner Femi Fani-Kayode over a livestreamed credentials ceremony.",
         "DIRCO / KBA13"),
        (36, "Nigeria frees kidnap victims.",
         "Troops dismantle armed camps and free dozens of abducted civilians across northern states.",
         "AllAfrica"),
        (38, "DRC\u2013Rwanda talks stall.",
         "Mediators cite deep security hurdles; Egypt, Ethiopia, Sudan and Somalia work Nile water diplomacy.",
         "Al Jazeera / TRT Afrika"),
    ]),
    ("mt", "Markets & Tech", EMERALD, [
        (42, "$4\u20135bn data-centre bid.",
         "Canada\u2019s La Caisse leads talks for a stake in Bain\u2019s Bridge Data Centres across India, Malaysia and Thailand.",
         "Reuters / MLQ"),
        (11, "US unveils $17bn Asia deals,",
         "led by a $12bn Boeing 787 order for Philippine Airlines plus Manila defence financing.",
         "Reuters / The Standard"),
        (19, "EU\u2013Indonesia pacts cleared.",
         "The Council authorises signing the CEPA and an investment protection deal with Southeast Asia\u2019s largest economy.",
         "Europa.eu"),
        (37, "Kenya minerals deal.",
         "Nairobi signs a strategic critical-minerals and technology-infrastructure partnership with a US-led consortium.",
         "Africanews"),
    ]),
    ("sc", "Science & Health", INDIGO, [
        (41, "Climate-health research alliance.",
         "The EU and Wellcome unite European and global funders in a Multilateral Initiative on Climate & Health Research Funding, launched at COP31 in Antalya.",
         "Europa.eu / Brussels Times"),
        (6, "IAEA board meets in Vienna.",
         "The Board of Governors reviews global safeguards and widens nuclear technical cooperation across Asia, Africa and Latin America.",
         "IAEA"),
        (28, "Ibogaine study; FAA grilling.",
         "HHS Secretary RFK Jr. backs federal ibogaine research for veterans\u2019 PTSD; Transportation Secretary Sean Duffy faces Congress over FAA groundings.",
         "PBS"),
    ]),
]


def digest_html() -> str:
    cols = []
    for key, name, color, items in DIGEST:
        body = []
        for sid, lead, text, source in items:
            body.append(f'<p class="di t" data-s="{sid}"><b>{esc(lead)}</b> {esc(text)} {src(source)}</p>')
        cols.append(
            f'<section class="dcol fit" id="d-{key}" style="--c:{color}">'
            f'<h4 class="dtab t">{esc(name.upper())}<span>{len(items)}</span></h4>'
            f'<div class="dbody fit">{"".join(body)}</div></section>')
    return "".join(cols)


CSS = r"""
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 1024px; height: 1024px; overflow: hidden; background: #FBF8F1; }
body { font-family: "Noto Sans", "Lato", sans-serif; color: #111827;
       -webkit-font-smoothing: antialiased; text-rendering: geometricPrecision;
       font-kerning: normal; }
#page { position: relative; width: 1024px; height: 1024px; padding: 7px 12px 0;
        background: #FBF8F1; display: flex; flex-direction: column; }

/* ---------------- masthead ---------------- */
.mast { height: 84px; flex: none; display: flex; flex-direction: column; }
.plate { height: 44px; display: grid; grid-template-columns: 196px 1fr 196px;
         align-items: center; }
.ear { height: 38px; border: 1px solid #1A1A1A; padding: 3px 7px; display: flex;
       flex-direction: column; justify-content: center; background: #fff; }
.ear .e1 { font: 900 8.4px/1.15 "Lato"; letter-spacing: 1.3px; color: #B91C1C; }
.ear .e2 { font: 700 9.4px/1.25 "Lato"; color: #111827; letter-spacing: 0.1px; }
.ear.r { text-align: right; }
.ear.r .e1 { color: #047857; }
h1 { font: 700 44px/1 "Noto Serif Display", serif; letter-spacing: 1.2px;
     text-align: center; color: #111827; white-space: nowrap; }
h1 .the { font-size: 20px; letter-spacing: 3px; vertical-align: 13px; margin-right: 6px;
          font-style: italic; font-weight: 700; }
.dbar { height: 18px; margin-top: 2px; border-top: 3px double #1A1A1A;
        border-bottom: 1px solid #1A1A1A; display: flex; align-items: center;
        justify-content: space-between; padding: 0 2px; }
.dbar .date { font: 900 11.4px/1 "Lato"; letter-spacing: 1.6px; color: #111827; }
.dbar .stats { font: 900 9.6px/1 "Lato"; letter-spacing: 1.4px; color: #111827; }
.dbar .stats em { font-style: normal; color: #B91C1C; }
.dbar .ed { font: 700 9.4px/1 "Lato"; letter-spacing: 1.2px; color: #374151; }
.pulse { height: 19px; margin-top: 2px; display: flex; align-items: center; gap: 4px;
         border-bottom: 2px solid #1A1A1A; padding-bottom: 2px; }
.pulse .pl { font: 900 9.6px/1 "Lato"; letter-spacing: 1.4px; color: #B91C1C; padding-right: 2px;
             white-space: nowrap; }
.chip { flex: 1 1 auto; height: 15px; display: flex; align-items: center; justify-content: center;
        font: 900 9.6px/1 "Lato"; letter-spacing: 0.7px; color: #fff; white-space: nowrap;
        padding: 0 5px; }

/* ---------------- hero deck ---------------- */
.hero { flex: none; height: 504px; margin-top: 5px; display: grid; gap: 6px;
        grid-template-columns: repeat(60, 1fr);
        grid-template-rows: 244px 112px 136px; }
.card { background: #fff; border: 1px solid #D6CFC2; border-top: 3px solid var(--c);
        position: relative; overflow: hidden; padding: 5px 9px 6px; }
.kick { font: 900 8.6px/1.2 "Lato"; letter-spacing: 1.2px; color: var(--c); text-transform: uppercase;
        margin-top: 2px; }
h2 { font: 700 23px/1.12 "Noto Serif", serif; color: #111827; letter-spacing: -0.3px; }
h3 { font: 700 14.4px/1.16 "Noto Serif", serif; color: #111827; letter-spacing: -0.15px; }
h3.s { font-size: 13px; line-height: 1.17; }
.dek { font: 400 10.6px/1.42 "Noto Sans"; color: #111827; }
.dek.s { font-size: 9.6px; line-height: 1.36; }
.src { font: 800 8.4px/1 "Lato"; letter-spacing: 0.5px; color: #374151; white-space: nowrap; }
.lead1 { grid-column: 1 / 37; display: grid; grid-template-columns: 1fr auto; gap: 10px; }
.lead1 .txt { display: flex; flex-direction: column; gap: 6px; }
.lead1 h2 { font-size: 23px; }
.lead1 .leg { margin-top: auto; display: flex; flex-direction: column; gap: 3px;
              font: 700 8.8px/1.2 "Lato"; color: #111827; }
.leg i { display: inline-block; width: 16px; height: 0; vertical-align: 3px; margin-right: 5px;
         border-top: 2px dashed #B91C1C; }
.leg i.b { border-top: 2px solid #1D4ED8; }
.leg i.t { width: 10px; height: 4px; border: 0; background: #111827; margin-right: 11px; vertical-align: 1px; }
.map { display: block; }
.lead2 { grid-column: 37 / 61; display: flex; flex-direction: column; gap: 4px; }
.also { border-top: 1px solid #D6CFC2; padding-top: 4px; }
.also b { font-weight: 700; color: #1D4ED8; }
.lead2 h2 { font-size: 20.5px; }
.lead2 .art { display: block; border: 1px solid #D6CFC2; }
.mod { display: flex; flex-direction: column; gap: 3px; }
.b1 { grid-row: 2; grid-column: span 20; display: grid; grid-template-columns: 1fr auto;
      column-gap: 8px; }
.b1 .txt { display: flex; flex-direction: column; gap: 4px; }
.b1.icj { grid-template-columns: 1fr 96px; }
.b2 { grid-row: 3; grid-column: span 12; display: flex; flex-direction: column; gap: 3px;
      padding: 6px 8px 5px; }
.sub { border-top: 1px solid #D6CFC2; padding-top: 3px; }
.big { font: 900 19px/1 "Lato"; color: var(--c); letter-spacing: -0.2px; }
.row { display: flex; align-items: center; gap: 6px; }
.tick { display: grid; grid-template-columns: 48px 1fr; gap: 1px 6px; align-items: baseline; }
.tick b { font: 900 9.6px/1.3 "Lato"; letter-spacing: 0.4px; white-space: nowrap; }
.tick b.f { color: #1D4ED8; }
.tick span { font: 400 9.4px/1.3 "Noto Sans"; color: #111827; }
.nw { white-space: nowrap; }
.up { color: #047857; } .dn { color: #B91C1C; }
.stat { font: 900 8.4px/1.2 "Lato"; letter-spacing: 0.6px; color: #374151; text-transform: uppercase; }

/* ---------------- digest ---------------- */
.digest { flex: none; height: 393px; margin-top: 6px; border-top: 2px solid #1A1A1A;
          padding-top: 4px; display: flex; flex-direction: column; }
.dhead { height: 15px; display: flex; align-items: center; justify-content: space-between; }
.dhead .t1 { font: 700 13px/1 "Noto Serif Display", serif; letter-spacing: 1.4px; }
.dhead .t2 { font: 800 8.6px/1 "Lato"; letter-spacing: 1px; color: #374151; }
.dgrid { flex: 1; margin-top: 4px; display: grid; gap: 6px;
         grid-template-columns: 1.16fr 1fr 1fr 1fr 1fr 1fr 1fr; min-height: 0; }
.dcol { background: #fff; border: 1px solid #D6CFC2; display: flex; flex-direction: column;
        overflow: hidden; min-height: 0; }
.dtab { flex: none; height: 17px; background: var(--c); color: #fff; display: flex;
        align-items: center; justify-content: space-between; padding: 0 6px;
        font: 900 8.8px/1 "Lato"; letter-spacing: 1px; }
.dtab span { font: 900 8.6px/1 "Lato"; background: #fff; color: var(--c); padding: 1px 4px; }
.dbody { flex: 1; display: flex; flex-direction: column; justify-content: space-between;
         padding: 2px 6px 3px; overflow: hidden; min-height: 0; }
.di { font: 400 9.3px/1.3 "Noto Sans"; color: #111827; padding: 3px 0;
      border-bottom: 1px solid #D6CFC2; hyphens: none; }
.di:last-child { border-bottom: 0; }
.di b { font-weight: 700; color: #111827; }
.di .src { font-size: 8.2px; color: var(--c); }

/* ---------------- footer ---------------- */
.foot { flex: none; height: 19px; margin-top: 4px; border-top: 1px solid #1A1A1A;
        display: flex; align-items: center; justify-content: space-between;
        font: 700 8.6px/1 "Lato"; letter-spacing: 0.5px; color: #374151; }
.foot b { color: #111827; font-weight: 900; }
"""


def build_html() -> str:
    chips = [("ANTHROPIC IPO $1.5TN @ $83", EMERALD), ("VOYAGER 1: ONE LIGHT-DAY", INDIGO),
             ("US\u2013IRAN GULF STRIKES", CRIMSON), ("SHENZHEN PEACE DECLARATION", COBALT),
             ("ICJ: MYANMAR GENOCIDE", "#111827")]
    chip_html = "".join(f'<span class="chip t" style="background:{c}">{esc(t)}</span>' for t, c in chips)

    mast = f"""
<header class="mast">
  <div class="plate">
    <div class="ear"><div class="e1 t">FINAL WORLD EDITION</div>
      <div class="e2 t">Middle East &middot; Asia-Pacific &middot; Europe &middot; Americas &middot; Africa</div></div>
    <h1 class="t"><span class="the">The</span>WORLD LEDGER</h1>
    <div class="ear r"><div class="e1 t">INSIDE TODAY</div>
      <div class="e2 t">Gulf strike map &middot; IPO chart &middot; light-day scale &middot; 7-region digest</div></div>
  </div>
  <div class="dbar">
    <span class="date t">WEDNESDAY, NOVEMBER 18, 2026</span>
    <span class="stats t"><em>42</em> VERIFIED STORIES &middot; <em>7</em> REGIONS &middot; <em>18+</em> PRIMARY SOURCES</span>
    <span class="ed t">GLOBAL EDITION &middot; NO. 18-XI</span>
  </div>
  <div class="pulse"><span class="pl t">GLOBAL PULSE &#9656;</span>{chip_html}</div>
</header>"""

    lead1 = f"""
<article class="card lead1 fit" data-s="1" style="--c:{CRIMSON}">
  <div class="txt">
    <div class="kick t">Breaking &middot; Middle East &middot; Gulf</div>
    <h2 class="t">US strikes Iran&rsquo;s Qeshm Island; Tehran hits back at Kuwait and Bahrain</h2>
    <p class="dek t">US forces hit an Iranian missile launch site on Qeshm Island in the Strait of Hormuz.
      Iran answered with missile and drone strikes on Kuwait&rsquo;s Ali Al Salem Air Base and US radar
      installations in Bahrain. {src("AP / Just Security")}</p>
    <div class="leg">
      <div class="t"><i class="b"></i>US strike &nbsp;<i></i>Iranian retaliation</div>
    </div>
  </div>
  {art_gulf()}
</article>"""

    lead2 = f"""
<article class="card lead2 fit" data-s="8" style="--c:{COBALT}">
  <div class="kick t">Asia-Pacific &middot; APEC Shenzhen &middot; Diplomacy</div>
  <h2 class="t">Trump, Xi and Putin issue a joint &lsquo;Declaration toward Peace&rsquo;</h2>
  {art_summit()}
  <p class="dek t">In unprecedented three-way talks on the APEC sidelines, the US, Chinese and Russian
    leaders affirmed that a nuclear war cannot be won, alongside talks on oil supply and UN reform.
    {src("Guardian / Al-Monitor")}</p>
  <p class="dek s also t" data-s="9"><b>Taiwan:</b> in bilateral talks Xi urged Trump to &ldquo;do the right
    thing&rdquo; to keep ties stable; both called the talks constructive. {src("Reuters / Astro Awani")}</p>
</article>"""

    b1 = f"""
<article class="card b1 fit" data-s="23" style="--c:{EMERALD}">
  <div class="txt">
    <div class="kick t">Markets &middot; Nasdaq IPO</div>
    <h3 class="t">Anthropic prices its $1.5tn IPO at $83</h3>
    <p class="dek s t">Priced above range before its debut.
      {src("Guardian / Investing.com")}</p>
  </div>
  {art_ipo()}
</article>
<article class="card b1 fit" data-s="39" style="--c:{INDIGO}">
  <div class="txt">
    <div class="kick t">Science &middot; Space</div>
    <h3 class="t">Voyager 1 is now one light-day from Earth</h3>
    <p class="dek s t">After 49 years the probe is 25.9bn km (16.1bn miles) out; signals take a
      full day. {src("NASA")}</p>
  </div>
  {art_voyager()}
</article>
<article class="card b1 icj fit" data-s="10" style="--c:{CRIMSON}">
  <div class="txt">
    <div class="kick t">Justice &middot; Asia-Pacific</div>
    <h3 class="t">ICJ rules Myanmar committed genocide against the Rohingya</h3>
    <p class="dek s t">A historic first: state-sponsored genocide in Rakhine State.
      {src("ICJ / Just Security")}</p>
  </div>
  {art_scales()}
</article>"""

    b2 = f"""
<article class="card b2 fit" style="--c:{COBALT}">
  <div class="kick t">Europe &middot; Ukraine</div>
  <div class="mod" data-s="16">
    <div class="row">{art_euro()}<div><div class="big t">&euro;45&ndash;49bn</div>
      <div class="stat t">EU loan for Kyiv&rsquo;s 2027 gap</div></div></div>
    <div class="src t">[Guardian / SCMP]</div>
  </div>
  <div class="mod sub" data-s="17">
    <h3 class="s t">Kerch Bridge struck; viral AI fakes debunked</h3>
    <div class="src t">[BBC / Kyiv Independent]</div>
  </div>
</article>
<article class="card b2 fit" data-s="40" style="--c:{EMERALD}">
  <div class="kick t">Climate &middot; COP31 Antalya</div>
  <h3 class="s t">COP31 deadlocks on fossil fuels and the IPCC timeline</h3>
  {art_ipcc()}
  <p class="dek s t">Blocs split over a 2028 or 2029 AR7 report as transition talks stall.
    {src("UNFCCC / EU Perspectives")}</p>
</article>
<article class="card b2 fit" data-s="29" style="--c:{AMBER}">
  <div class="kick t">Americas &middot; Caracas</div>
  <h3 class="s t">Hegseth in Caracas: US and Venezuela restore military ties</h3>
  <div class="row">{art_flags_us_ve()}<div class="stat t">Military &amp;<br>intelligence pact</div></div>
  <p class="dek s t">Signed with interim President Delcy Rodr&iacute;guez. {src("PBS / AP")}</p>
</article>
<article class="card b2 fit" style="--c:{EMERALD}">
  <div class="kick t">Markets &middot; Wall Street</div>
  <h3 class="s t">Hawkish Fed; Nvidia beats</h3>
  <div class="tick">
    <b class="f t" data-s="24">FED</b><span class="t">Minutes flag sticky inflation, more tightening</span>
    <b class="up t" data-s="25">NVDA &#9650;</b><span class="t">Beats despite leadership fallout</span>
    <b class="dn t">GOLD &#9660;</b><span class="t">Near a 14-month low; copper pressured</span>
  </div>
  <div class="src t">[Investing.com / TMGM]</div>
</article>
<article class="card b2 fit" style="--c:{AMBER}">
  <div class="kick t">United States</div>
  <div class="mod" data-s="26">
    <div class="row">{art_rain()}<h3 class="s t">SF breaks a <span class="nw">108-year</span> rain record {src("LA Times")}</h3></div>
    <p class="dek s t">Atmospheric river: floods, blackouts.</p>
  </div>
  <div class="mod sub" data-s="27">
    <h3 class="s t">Peltola win seals a 56-seat Democratic Senate {src("Guardian")}</h3>
    {art_senate()}
  </div>
</article>"""

    digest = f"""
<section class="digest">
  <div class="dhead"><span class="t1 t">THE WORLD DIGEST</span>
    <span class="t2 t">28 MORE VERIFIED DISPATCHES &middot; SEVEN DESKS &middot; NOV 18, 2026</span></div>
  <div class="dgrid">{digest_html()}</div>
</section>"""

    foot = """
<footer class="foot">
  <span class="t"><b>THE WORLD LEDGER</b> &middot; Compiled from verified Nov 18, 2026 primary reporting:
    AP &middot; Reuters &middot; BBC &middot; Guardian &middot; PBS &middot; Al Jazeera &middot; NASA &middot; ICJ &middot; UN &middot; IOM &middot; IAEA &middot; Europa.eu</span>
  <span class="t">Deterministic offline render &middot; 1024&times;1024</span>
</footer>"""

    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<title>The World Ledger - 18 November 2026</title><style>{CSS}</style></head>'
            f'<body><div id="page">{mast}<main class="hero">{lead1}{lead2}{b1}{b2}</main>'
            f'{digest}{foot}</div></body></html>')


# --------------------------------------------------------------------------- #
# DOM audit
# --------------------------------------------------------------------------- #
AUDIT_JS = r"""
() => {
  const r = (v) => Math.round(v * 10) / 10;
  const out = { scroll: [document.documentElement.scrollWidth, document.documentElement.scrollHeight],
                clipped: [], overlaps: [], svgOverlaps: [], svgOutside: [], stories: [],
                slack: {}, offPage: [], fonts: [] };
  const page = document.getElementById('page').getBoundingClientRect();
  if (page.bottom > 1024.5 || page.right > 1024.5) out.offPage.push('page');
  document.querySelectorAll('.t, svg, .card, .dcol, .foot').forEach((e) => {
    const q = e.getBoundingClientRect();
    if (q.bottom > 1022 || q.right > 1024 || q.left < 0 || q.top < 0)
      out.offPage.push([e.textContent.trim().slice(0, 30), Math.round(q.bottom)]);
  });
  document.querySelectorAll('.fit').forEach((el) => {
    if (el.scrollHeight > el.clientHeight + 0.5 || el.scrollWidth > el.clientWidth + 0.5) {
      out.clipped.push({ el: (el.id || el.className) + ':' + el.textContent.trim().slice(0, 40),
                         sh: el.scrollHeight, ch: el.clientHeight, sw: el.scrollWidth, cw: el.clientWidth });
    }
  });
  // every card/column: last descendant must end inside the box
  document.querySelectorAll('.card, .dcol, .mast, .digest, .foot').forEach((box) => {
    const b = box.getBoundingClientRect();
    box.querySelectorAll('.t, svg').forEach((t) => {
      const q = t.getBoundingClientRect();
      if (q.bottom > b.bottom + 0.5 || q.right > b.right + 0.5 || q.left < b.left - 0.5 || q.top < b.top - 0.5)
        out.clipped.push({ el: 'child-outside:' + t.textContent.trim().slice(0, 40),
                           q: [r(q.left), r(q.top), r(q.right), r(q.bottom)], b: [r(b.left), r(b.top), r(b.right), r(b.bottom)] });
    });
  });
  const els = [...document.querySelectorAll('.t')];
  // single-element text clip: inline content wider than box
  els.forEach((e) => {
    if (e.scrollWidth > e.clientWidth + 0.5 && getComputedStyle(e).display !== 'inline')
      out.clipped.push({ el: 'text-wide:' + e.textContent.trim().slice(0, 40), sw: e.scrollWidth, cw: e.clientWidth });
  });
  for (let i = 0; i < els.length; i++) {
    const a = els[i].getBoundingClientRect();
    for (let j = i + 1; j < els.length; j++) {
      if (els[i].contains(els[j]) || els[j].contains(els[i])) continue;
      const b = els[j].getBoundingClientRect();
      const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (ox > 0.5 && oy > 0.5)
        out.overlaps.push([els[i].textContent.trim().slice(0, 30), els[j].textContent.trim().slice(0, 30), r(ox), r(oy)]);
    }
  }
  document.querySelectorAll('svg').forEach((s) => {
    const sb = s.getBoundingClientRect();
    const ts = [...s.querySelectorAll('text')];
    ts.forEach((t) => {
      const q = t.getBoundingClientRect();
      if (q.left < sb.left - 0.3 || q.right > sb.right + 0.3 || q.top < sb.top - 0.3 || q.bottom > sb.bottom + 0.3)
        out.svgOutside.push([t.textContent, r(q.left - sb.left), r(sb.right - q.right), r(q.top - sb.top), r(sb.bottom - q.bottom)]);
    });
    for (let i = 0; i < ts.length; i++) {
      const a = ts[i].getBBox();
      for (let j = i + 1; j < ts.length; j++) {
        const b = ts[j].getBBox();
        const ox = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x);
        const oy = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
        if (ox > 0.3 && oy > 1.2) out.svgOverlaps.push([ts[i].textContent, ts[j].textContent, r(ox), r(oy)]);
      }
    }
  });
  const ids = new Set();
  document.querySelectorAll('[data-s]').forEach((e) => e.dataset.s.split(',').forEach((x) => ids.add(+x)));
  out.stories = [...ids].sort((a, b) => a - b);
  document.querySelectorAll('.dbody').forEach((d) => {
    const b = d.getBoundingClientRect();
    let used = 0;
    [...d.children].forEach((c) => { used += c.getBoundingClientRect().height; });
    out.slack[d.parentElement.id] = r(b.height - used - 7);
  });
  // free space left at the bottom of each hero card
  out.cardSlack = [...document.querySelectorAll('.card')].map((c) => {
    const b = c.getBoundingClientRect();
    let bottom = b.top;
    c.querySelectorAll('.t, svg').forEach((t) => { bottom = Math.max(bottom, t.getBoundingClientRect().bottom); });
    return [c.textContent.trim().replace(/\s+/g, ' ').slice(0, 28), r(b.bottom - bottom)];
  });
  return out;
}
"""


def render(html: str, out_png: Path, dpr: int) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        page_path = Path(tmp) / "page.html"
        page_path.write_text(html, encoding="utf-8")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=CHROME, headless=True,
                args=["--hide-scrollbars", "--font-render-hinting=none", "--disable-lcd-text",
                      "--disable-gpu", "--force-color-profile=srgb"])
            page = browser.new_page(viewport={"width": SIZE, "height": SIZE},
                                    device_scale_factor=dpr)
            page.goto(page_path.as_uri(), wait_until="load")
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(200)
            audit = page.evaluate(AUDIT_JS)
            page.screenshot(path=str(out_png), clip={"x": 0, "y": 0, "width": SIZE, "height": SIZE})
            browser.close()
    return audit


def check(audit: dict) -> list[str]:
    problems = []
    if audit["scroll"][0] > SIZE or audit["scroll"][1] > SIZE:
        problems.append(f"page scrolls: {audit['scroll']}")
    for key in ("clipped", "overlaps", "svgOverlaps", "svgOutside", "offPage"):
        for item in audit[key]:
            problems.append(f"{key}: {item}")
    if audit["stories"] != list(range(1, 43)):
        missing = sorted(set(range(1, 43)) - set(audit["stories"]))
        problems.append(f"stories: {len(audit['stories'])} found, missing {missing}")
    for col, slack in audit["slack"].items():
        if slack > 22:
            problems.append(f"digest column {col} leaves {slack}px unused")
    return problems


def encode_png(img: Image.Image) -> bytes:
    """Smallest of a lossless RGB PNG and a 256-colour adaptive PNG under the cap."""
    candidates = []
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    candidates.append(("rgb", buf.getvalue()))
    q = img.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    buf = io.BytesIO()
    q.save(buf, format="PNG", optimize=True)
    candidates.append(("p256", buf.getvalue()))
    for name, data in candidates:
        if len(data) <= 950_000:
            return data
    return min(candidates, key=lambda c: len(c[1]))[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dpr", type=int, default=2, help="device pixel ratio before downsampling")
    ap.add_argument("--out", type=Path, default=ROOT / "entry.png")
    ap.add_argument("--html", type=Path, help="also write the page HTML here")
    ap.add_argument("--force", action="store_true", help="write even if the audit fails")
    args = ap.parse_args()

    page_html = build_html()
    if args.html:
        args.html.write_text(page_html, encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmp:
        shot = Path(tmp) / "shot.png"
        audit = render(page_html, shot, args.dpr)
        img = Image.open(shot).convert("RGB")
        img.load()
    if img.size != (SIZE, SIZE):
        img = img.resize((SIZE, SIZE), Image.LANCZOS)

    problems = check(audit)
    print(f"stories on page: {len(audit['stories'])}")
    print("digest slack (px):", audit["slack"])
    print("card slack (px):", audit["cardSlack"])
    for p in problems:
        print("AUDIT:", p)
    if problems and not args.force:
        print("audit failed; entry.png not written", file=sys.stderr)
        return 1

    data = encode_png(img)
    if len(data) > MAX_BYTES:
        print(f"encoded image is {len(data)} bytes, over 1 MiB", file=sys.stderr)
        return 1
    args.out.write_bytes(data)
    print(f"{args.out.name}: {img.size[0]}x{img.size[1]} PNG {len(data)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
