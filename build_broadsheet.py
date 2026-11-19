#!/usr/bin/env python3
"""Build entry.png: an illustrated one-day world front page for Wednesday 18 November 2026.

Layout (1024x1024, three reading scales):

* header: a giant "WEDNESDAY, 18 NOVEMBER 2026" banner, a seven-region bar
  sized by story count and a "Day in numbers" strip;
* gallery: twelve story cards in rows of 3, 4 and 5, each topped by an
  original inline-SVG scene;
* lower band: a world locator map with pins 1-12 and a two-column digest of
  thirty one-line dispatches (13-42);
* footer: a date check naming the Tue 17 / Thu 19 stories kept off the page,
  and the source list.

The page is HTML + inline SVG, laid out in headless Chrome through Playwright
at 2x device pixel ratio and downsampled with Lanczos. A DOM geometry audit
runs before anything is written:

* the page fits 1024x1024 and every text block sits inside the canvas;
* no card, caption or digest line clips its content;
* no two text blocks overlap, and no SVG label overlaps another or leaves its scene;
* story ids 1..42 all appear exactly once.

Build-time only (needs Playwright, Chrome, Pillow, NumPy). The shipped
entrypoint, main.py, is standard-library Python that copies entry.png.
"""

from __future__ import annotations

import argparse
import html
import io
import math
import sys
import tempfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
CHROME = "/usr/bin/google-chrome"
SIZE = 1024
MAX_BYTES = 1024 * 1024

# --------------------------------------------------------------------------- #
# Palette
# --------------------------------------------------------------------------- #
PAPER = "#FAF6EE"
CARD = "#FFFFFF"
HAIR = "#D9D1C1"
INK = "#111827"
SLATE = "#374151"
MUTED = "#4B5563"

REGIONS = {
    # key: (label, colour)
    "eu": ("Europe", "#1D4ED8"),
    "am": ("Americas", "#B45309"),
    "ap": ("Asia-Pacific", "#0F766E"),
    "af": ("Africa", "#9A3412"),
    "me": ("Middle East", "#B91C1C"),
    "oc": ("Oceania", "#7E22CE"),
    "gl": ("Global / Space", "#334155"),
}
REGION_ORDER = ["eu", "am", "ap", "af", "me", "oc", "gl"]


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def rc(region: str) -> str:
    return REGIONS[region][1]


# --------------------------------------------------------------------------- #
# Stories. Every item was checked against dated wire/outlet reports for
# Wednesday 18 November 2026; stories dated Tue 17 or Thu 19 were dropped.
# --------------------------------------------------------------------------- #
# Gallery cards: (id, region, art, kicker, title, caption, sources)
CARDS = [
    (1, "ap", "apec", "APEC \u00b7 Shenzhen",
     "Xi greets Trump on the Shenzhen tarmac as APEC opens",
     "Xi tells leaders Russia and China should lead a multipolar push, ahead of "
     "Thursday\u2019s three-way talks with Putin.",
     "NBC / Al Jazeera"),
    (2, "me", "gulf", "Persian Gulf",
     "Iran fires missiles and drones at Kuwait and Bahrain",
     "Tehran targets a US air base in Kuwait and sites in Bahrain, widening the "
     "fight over the Strait of Hormuz.",
     "WSJ / The Hill"),
    (3, "gl", "voyager", "Interstellar space",
     "Voyager 1 is now one light-day from Earth",
     "After 49 years, NASA\u2019s probe is 25.9bn km away: its signals take a full "
     "24 hours to reach home.",
     "NASA / PBS"),
    (4, "eu", "ukraine", "Ukraine war",
     "Russia fires 141 drones; 126 shot down",
     "Strikes hit seven sites overnight. Brussels proposes a \u20ac45bn loan for "
     "Kyiv\u2019s 2027 needs.",
     "Ukrainian Air Force / EU"),
    (5, "gl", "markets", "Markets & AI",
     "Anthropic prices a record $81.3bn IPO",
     "Shares set at $83, valuing it at $1.5tn. Hawkish Fed minutes push the Dow "
     "down 1.1%.",
     "NYT / Reuters"),
    (6, "ap", "cyclone", "Bay of Bengal",
     "Cyclone Akvan strengthens off India\u2019s east coast",
     "Odisha and Andhra Pradesh brace for landfall.",
     "Down To Earth / IMD"),
    (7, "af", "sudan", "Sudan",
     "Amnesty: RSF drone strikes killed 37 in El Obeid",
     "The rights group urges a war-crimes probe into the attacks on civilians.",
     "Amnesty International"),
    (8, "eu", "ukcpi", "UK economy",
     "UK inflation rises to 3.6%",
     "October CPI hits a one-year high as diesel prices set records.",
     "ONS / Guardian"),
    (9, "me", "gaza", "Central Gaza",
     "Israeli tanks cross Gaza\u2019s \u2018yellow line\u2019",
     "Armour pushes into Hamas-held central Gaza, testing the truce.",
     "Guardian"),
    (10, "am", "capitol", "US Congress",
     "Jeffries wins Speaker nomination 251\u201311",
     "House Democrats back him to be the first Black Speaker.",
     "NPR / NBC"),
    (11, "oc", "aria", "Sydney \u00b7 Music",
     "Tame Impala sweeps the ARIA Awards",
     "Seven wins, including album and song of the year.",
     "Guardian / Billboard"),
    (12, "ap", "dhaka", "Bangladesh",
     "Garment workers block the Dhaka\u2013Aricha highway",
     "Wage protests at Savar spread; police clash with workers.",
     "Daily Star / Al Jazeera"),
]

# Digest: (region, place, fact). Numbered 13..42 in this order.
DIGEST = [
    ("eu", "Brussels", "EU Council clears signing of EU\u2013Indonesia trade pact"),
    ("eu", "Frankfurt", "UniCredit, Berlin reach broad Commerzbank deal"),
    ("eu", "Warsaw", "P-TEC ministers push Europe off Russian energy"),
    ("eu", "Madrid", "Court opens abuse investigation into Julio Iglesias"),
    ("eu", "Vatican", "Pope Leo reflects on Peru trip at general audience"),
    ("eu", "Ukraine", "Drone strike damages Austria\u2019s honorary consulate"),
    ("eu", "Turin", "Alcaraz eases past Medvedev at the ATP Finals"),
    ("am", "Caracas", "Hegseth signs US\u2013Venezuela military-ties pact"),
    ("am", "Mexico City", "Sheinbaum: US trade talks \u2018very far along\u2019"),
    ("am", "Washington", "Mullin grilled over nationwide FAA ground stop"),
    ("am", "Washington", "Trump asks justices to end Venezuelans\u2019 TPS"),
    ("am", "Toronto", "KPMG Canada confirms hack of client tax files"),
    ("am", "San Francisco", "Bay Area storm breaks century-old rain record"),
    ("am", "Bras\u00edlia", "Senate passes Lula\u2019s $10bn fiscal package"),
    ("am", "Santiago", "Chile\u2019s economy logs worst quarter since 2020"),
    ("ap", "Shenzhen", "Takaichi holds rare talks with Putin, shakes Xi\u2019s hand"),
    ("ap", "Seoul", "Xi backs easing tensions with North Korea, Seoul says"),
    ("ap", "Taipei", "Taiwan in \u2018close contact\u2019 with US before APEC talks"),
    ("ap", "Tokyo", "Japan scrambles jets as Russian aircraft breach airspace"),
    ("ap", "Jakarta", "Bank Indonesia resumes rate hikes to defend rupiah"),
    ("ap", "Flores", "Magnitude 5.9 earthquake strikes eastern Indonesia"),
    ("oc", "Papua New Guinea", "Shallow M6.0 earthquake hits region"),
    ("af", "Addis Ababa", "Ethiopia and Eritrea mass forces along border"),
    ("af", "Cairo", "IMF deal unlocks $2.3bn for Egypt"),
    ("af", "Abuja", "US hails troops\u2019 rescue of 125 kidnap victims"),
    ("af", "Old Dongola", "Vast medieval cathedral floor found in Sudan"),
    ("me", "Riyadh", "Coalition downs Houthi missiles; blast heard"),
    ("me", "Doha", "Qatar condemns Israeli incursions into Syria"),
    ("gl", "Vienna", "Grossi opens IAEA Board of Governors session"),
    ("gl", "Antalya", "UN launches disaster-risk finance platform at COP31"),
]

NUMBERS = [
    ("$81.3B", "record IPO"),
    ("25.9B km", "Voyager 1"),
    ("141/126", "drones / downed"),
    ("3.6%", "UK inflation"),
    ("251\u201311", "Jeffries vote"),
    ("\u20ac45B", "EU loan to Kyiv"),
]

DATE_CHECK = (
    "Kept off as not Wed 18: TUE 17 \u2014 US strike on Qeshm, Nvidia earnings, Alaska Senate call, "
    "Kerch Bridge, An-12 crash \u00b7 THU 19 \u2014 Trump\u2013Xi\u2013Putin talks, ICJ Rohingya verdict, "
    "Anthropic Nasdaq debut")
SOURCES = ("Sources: Reuters \u00b7 AP \u00b7 NYT \u00b7 WSJ \u00b7 NPR \u00b7 NBC \u00b7 Guardian \u00b7 "
           "Al Jazeera \u00b7 ONS \u00b7 NASA \u00b7 IMD \u00b7 Amnesty \u00b7 IAEA \u00b7 UN \u00b7 "
           "EU Council \u00b7 Daily Star \u00b7 Original custom graphics \u00b7 1024\u00d71024")


def region_counts() -> dict[str, int]:
    counts = {k: 0 for k in REGION_ORDER}
    for card in CARDS:
        counts[card[1]] += 1
    for item in DIGEST:
        counts[item[0]] += 1
    return counts


# --------------------------------------------------------------------------- #
# SVG helpers
# --------------------------------------------------------------------------- #
def lab(x, y, text, size=10.0, color="#fff", weight=900, ls=0.8, anchor="start",
        family="Lato", halo=None, italic=False) -> str:
    """An SVG text label; class "sl" puts it in the label-overlap audit."""
    style = "font-style:italic;" if italic else ""
    stroke = (f' stroke="{halo}" stroke-width="2.6" paint-order="stroke" '
              f'stroke-linejoin="round"') if halo else ""
    return (f'<text class="sl" x="{x:.1f}" y="{y:.1f}" font-family="{family}" '
            f'font-size="{size}" font-weight="{weight}" letter-spacing="{ls}" '
            f'fill="{color}" text-anchor="{anchor}" style="{style}"{stroke}>'
            f'{esc(text)}</text>')


def chip(x, y, text, bg, fg="#fff", size=8.5, pad=4, anchor="start") -> str:
    """A filled label chip; width estimated from Lato Black metrics."""
    w = len(text) * size * 0.64 + pad * 2
    x0 = x - w if anchor == "end" else x
    return (f'<rect x="{x0:.1f}" y="{y:.1f}" width="{w:.1f}" height="{size + 6:.1f}" rx="2" '
            f'fill="{bg}"/>' + lab(x0 + w / 2, y + size + 1.6, text, size=size, color=fg,
                                  anchor="middle", ls=0.6))


def lcg(seed: int):
    state = seed
    while True:
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        yield state / 0x7FFFFFFF


def stars(w, h, n, seed, rmax=1.1, color="#fff") -> str:
    r = lcg(seed)
    out = []
    for _ in range(n):
        x, y, s, o = next(r) * w, next(r) * h, 0.3 + next(r) * rmax, 0.35 + next(r) * 0.65
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{s:.2f}" fill="{color}" opacity="{o:.2f}"/>')
    return "".join(out)


def star5(cx, cy, r, color) -> str:
    pts = []
    for i in range(10):
        rad = r if i % 2 == 0 else r * 0.42
        ang = -math.pi / 2 + i * math.pi / 5
        pts.append(f"{cx + rad * math.cos(ang):.2f},{cy + rad * math.sin(ang):.2f}")
    return f'<polygon points="{" ".join(pts)}" fill="{color}"/>'


def burst(x, y, r, color="#FACC15", core="#fff") -> str:
    pts = []
    for i in range(16):
        rad = r if i % 2 == 0 else r * 0.45
        ang = i * math.pi / 8
        pts.append(f"{x + rad * math.cos(ang):.1f},{y + rad * math.sin(ang):.1f}")
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r * 1.8:.1f}" fill="{color}" opacity="0.22"/>'
            f'<polygon points="{" ".join(pts)}" fill="{color}"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r * 0.3:.1f}" fill="{core}"/>')


def drone(x, y, s=1.0, color="#111827", ang=0) -> str:
    """Delta-wing one-way attack drone silhouette."""
    return (f'<g transform="translate({x:.1f},{y:.1f}) rotate({ang}) scale({s})">'
            f'<path d="M6,0 L-5,-5.5 L-3,0 L-5,5.5 Z" fill="{color}"/>'
            f'<rect x="-6.5" y="-0.8" width="3" height="1.6" fill="{color}"/></g>')


def svg(w, h, body, defs="") -> str:
    return (f'<svg class="scene" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice" '
            f'xmlns="http://www.w3.org/2000/svg"><defs>{defs}</defs>{body}</svg>')


def grad(gid, stops, x2=0, y2=1) -> str:
    s = "".join(f'<stop offset="{o}" stop-color="{c}"/>' for o, c in stops)
    return f'<linearGradient id="{gid}" x1="0" y1="0" x2="{x2}" y2="{y2}">{s}</linearGradient>'


# --------------------------------------------------------------------------- #
# Gulf coastline (lon, lat)
# --------------------------------------------------------------------------- #
GULF_LAND = [
    (62.0, 25.3), (58.8, 25.45), (58.2, 25.55), (57.77, 25.64), (57.4, 25.85), (57.12, 26.45),
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
    (58.8, 23.55), (62.0, 22.5), (62.0, 20.0), (40.0, 20.0), (40.0, 33.0), (62.0, 33.0),
]
BAHRAIN = [(50.45, 26.25), (50.62, 26.24), (50.66, 26.05), (50.6, 25.8),
           (50.5, 25.9), (50.45, 26.1)]
QESHM = [(55.28, 26.72), (55.6, 26.62), (55.95, 26.72), (56.28, 26.93),
         (56.15, 26.99), (55.85, 26.93), (55.5, 26.9), (55.3, 26.83)]


# --------------------------------------------------------------------------- #
# Scenes. Sizes match the rendered art boxes, so 1 SVG unit = 1 CSS px.
# --------------------------------------------------------------------------- #
W1, H1 = 328, 118
W2, H2 = 244, 90
W3, H3 = 194, 76


def flag_us(x, y, w, h) -> str:
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#fff"/>']
    for i in range(0, 7):
        out.append(f'<rect x="{x}" y="{y + i * 2 * h / 13:.2f}" width="{w}" height="{h / 13:.2f}" fill="#B22234"/>')
    out.append(f'<rect x="{x}" y="{y}" width="{w * 0.42:.2f}" height="{h * 7 / 13:.2f}" fill="#3C3B6E"/>')
    for r in range(3):
        for c in range(4):
            out.append(f'<circle cx="{x + 1.6 + c * w * 0.1:.2f}" cy="{y + 1.4 + r * h * 0.16:.2f}" r="0.55" fill="#fff"/>')
    return "".join(out)


def flag_cn(x, y, w, h) -> str:
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#DE2910"/>',
           star5(x + w * 0.17, y + h * 0.27, h * 0.17, "#FFDE00")]
    for dx, dy in ((0.33, 0.1), (0.4, 0.2), (0.4, 0.35), (0.33, 0.45)):
        out.append(star5(x + w * dx, y + h * dy, h * 0.06, "#FFDE00"))
    return "".join(out)


def art_apec() -> str:
    w, h = W1, H1
    d = grad("apsky", [(0, "#1E3A8A"), (0.55, "#C2410C"), (1, "#FDBA74")])
    b = [f'<rect width="{w}" height="{h}" fill="url(#apsky)"/>',
         stars(w, 40, 18, 7, 0.7)]
    # Shenzhen skyline
    sky = [(150, 60, 10), (162, 52, 9), (174, 66, 12), (189, 46, 9), (200, 58, 11),
           (214, 40, 8), (224, 64, 10), (236, 50, 10), (262, 56, 12), (276, 44, 9),
           (287, 62, 11), (300, 50, 10), (312, 66, 16)]
    for x, top, bw in sky:
        b.append(f'<rect x="{x}" y="{top}" width="{bw}" height="{90 - top}" fill="#1F2937"/>')
    # Ping An Finance Centre style supertall
    b.append('<path d="M246,90 L247,30 L250,22 L251,8 L252,22 L255,30 L256,90 Z" fill="#111827"/>')
    for x, top, bw in sky[::2]:
        for yy in range(top + 5, 86, 7):
            b.append(f'<rect x="{x + 2}" y="{yy}" width="{bw - 4}" height="1.4" fill="#FCD34D" opacity="0.55"/>')
    # tarmac
    b.append(f'<rect y="88" width="{w}" height="{h - 88}" fill="#374151"/>')
    b.append(f'<rect y="88" width="{w}" height="2" fill="#4B5563"/>')
    for x in range(6, w, 26):
        b.append(f'<rect x="{x}" y="108" width="13" height="2" fill="#E5E7EB" opacity="0.7"/>')
    # jet (generic presidential livery: white over blue), nose right
    b.append('<g transform="translate(8,58)">'
             '<path d="M0,22 L12,20 L104,18 Q120,18 126,24 Q120,30 104,30 L12,30 Z" fill="#F8FAFC"/>'
             '<path d="M12,26 L104,26 Q118,26 125,26 Q120,30 104,30 L12,30 Z" fill="#1D4ED8"/>'
             '<path d="M8,20 L0,2 L9,2 L26,20 Z" fill="#F8FAFC"/>'
             '<path d="M46,26 L76,26 L58,42 L48,42 Z" fill="#CBD5E1"/>'
             '<path d="M40,20 L60,20 L52,12 L46,12 Z" fill="#CBD5E1" opacity="0.8"/>'
             + "".join(f'<circle cx="{30 + i * 7}" cy="22.5" r="1.1" fill="#1E3A8A"/>' for i in range(11))
             + '<rect x="100" y="30" width="3" height="5" fill="#111827"/>'
             '<rect x="26" y="30" width="3" height="5" fill="#111827"/></g>')
    # stairs + red carpet
    b.append('<path d="M112,88 L120,88 L104,78 L100,78 Z" fill="#E5E7EB"/>')
    b.append('<path d="M118,96 L230,93 L238,106 L110,110 Z" fill="#DC2626"/>')
    # greeting figures
    for x, col in ((200, "#111827"), (213, "#0F172A")):
        b.append(f'<circle cx="{x}" cy="78" r="3.4" fill="{col}"/>'
                 f'<path d="M{x - 4.5},98 L{x - 4},84 Q{x},81 {x + 4},84 L{x + 4.5},98 Z" fill="{col}"/>')
    b.append('<path d="M203,88 L210,88" stroke="#111827" stroke-width="2"/>')
    # flags on poles
    for x, fl in ((292, flag_us), (310, flag_cn)):
        b.append(f'<rect x="{x - 1}" y="66" width="1.4" height="28" fill="#E5E7EB"/>')
        b.append(fl(x, 66, 15, 10))
    b.append(lab(10, 22, "APEC", size=22, color="#fff", ls=2))
    b.append(lab(11, 36, "SHENZHEN \u00b7 18 NOV", size=9, color="#FDE68A", ls=1.4))
    return svg(w, h, "".join(b), d)


def gulf_xy(lon, lat):
    k = 25.0
    return (lon - 45.6) * k * 0.891, (29.9 - lat) * k + 1


def gulf_path(points) -> str:
    out = []
    for i, (lon, lat) in enumerate(points):
        x, y = gulf_xy(lon, lat)
        out.append(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}")
    return " ".join(out) + " Z"


def art_gulf() -> str:
    w, h = W1, H1
    sea, land, coast = "#0B2545", "#D9C9A3", "#8C7A55"
    d = ('<marker id="ahr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" '
         'orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="#F87171"/></marker>')
    b = [f'<rect width="{w}" height="{h}" fill="{sea}"/>']
    b.append(f'<path d="{gulf_path(GULF_LAND)}" fill="{land}" stroke="{coast}" stroke-width="0.9" '
             f'stroke-linejoin="round"/>')
    b.append(f'<path d="{gulf_path(BAHRAIN)}" fill="{land}" stroke="{coast}" stroke-width="0.8"/>')
    b.append(f'<path d="{gulf_path(QESHM)}" fill="#E8B4A8" stroke="#7F1D1D" stroke-width="0.8"/>')
    ox, oy = gulf_xy(51.4, 29.35)
    kx, ky = gulf_xy(47.75, 29.2)
    bx, by = gulf_xy(50.56, 26.12)
    b.append(f'<path d="M{ox:.1f},{oy:.1f} Q{(ox + kx) / 2:.1f},{oy - 26:.1f} {kx + 6:.1f},{ky - 3:.1f}" '
             f'fill="none" stroke="#F87171" stroke-width="2" stroke-dasharray="4 2.5" marker-end="url(#ahr)"/>')
    b.append(f'<path d="M{ox:.1f},{oy:.1f} Q{ox + 6:.1f},{(oy + by) / 2:.1f} {bx + 5:.1f},{by - 6:.1f}" '
             f'fill="none" stroke="#F87171" stroke-width="2" stroke-dasharray="4 2.5" marker-end="url(#ahr)"/>')
    b.append(f'<circle cx="{ox:.1f}" cy="{oy:.1f}" r="3" fill="#DC2626" stroke="#fff" stroke-width="1"/>')
    b.append(burst(kx + 3, ky, 6.5))
    b.append(burst(bx, by, 6.5))
    # tankers at the strait
    for lon, lat, ang in ((53.9, 26.0, -12), (54.9, 26.15, -12), (55.9, 26.4, -20)):
        tx, ty = gulf_xy(lon, lat)
        b.append(f'<g transform="translate({tx:.1f},{ty:.1f}) rotate({ang})">'
                 f'<path d="M-7,-2.2 L5,-2.2 L8.5,0 L5,2.2 L-7,2.2 Z" fill="#F8FAFC"/>'
                 f'<rect x="-6" y="-1" width="3" height="2" fill="#0B2545"/></g>')
    b.append(lab(*gulf_xy(51.6, 28.35), "IRAN", size=20, color="#5B4A2C", ls=6))
    b.append(lab(6, 40, "KUWAIT", size=9.5, color="#0B2545", ls=0.8))
    b.append(lab(6, 108, "SAUDI ARABIA", size=8, color="#5B4A2C", ls=1.2))
    b.append(lab(bx - 4, by + 18, "BAHRAIN", size=9.5, color="#fff", ls=0.8, anchor="middle", halo=sea))
    qx, qy = gulf_xy(55.6, 26.95)
    b.append(lab(qx - 10, qy - 7, "QESHM \u00b7 HIT TUE", size=7, color="#7F1D1D", ls=0.6))
    hx, hy = gulf_xy(57.2, 26.3)
    b.append(lab(hx, hy + 3, "HORMUZ", size=8.5, color="#0B2545", ls=1.6))
    b.append(lab(gulf_xy(51.4, 0)[0], gulf_xy(0, 26.5)[1], "PERSIAN GULF", size=8.5,
                 color="#BFDBFE", ls=1.6, italic=True, family="Noto Serif", weight=700))
    b.append(chip(w - 6, 6, "IRAN RETALIATES", "#DC2626", size=9, anchor="end"))
    return svg(w, h, "".join(b), d)


def art_voyager() -> str:
    w, h = W1, H1
    d = ('<radialGradient id="sun" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#FEF3C7"/>'
         '<stop offset="0.35" stop-color="#FBBF24"/><stop offset="1" stop-color="#F59E0B" stop-opacity="0"/>'
         '</radialGradient>' + grad("vsp", [(0, "#020617"), (1, "#1E1B4B")], x2=1, y2=0))
    b = [f'<rect width="{w}" height="{h}" fill="url(#vsp)"/>', stars(w, h, 120, 42, 1.0)]
    b.append('<circle cx="18" cy="74" r="20" fill="url(#sun)"/>')
    b.append('<circle cx="46" cy="74" r="4.2" fill="#3B82F6" stroke="#BFDBFE" stroke-width="1"/>')
    b.append('<path d="M52,74 L236,74" stroke="#FDE68A" stroke-width="1.6" stroke-dasharray="5 4"/>')
    for i, x in enumerate(range(70, 236, 34)):
        b.append(f'<path d="M{x},70 L{x + 6},74 L{x},78" fill="none" stroke="#FDE68A" stroke-width="1.4"/>')
    # Voyager probe
    b.append('<g transform="translate(262,70) rotate(-12)">'
             '<path d="M-20,-15 Q-7,0 -20,15" fill="none" stroke="#fff" stroke-width="2"/>'
             '<ellipse cx="-17" cy="0" rx="6" ry="16" fill="#E5E7EB"/>'
             '<ellipse cx="-16" cy="0" rx="4" ry="12" fill="#CBD5E1"/>'
             '<circle cx="-12" cy="0" r="1.6" fill="#fff"/>'
             '<rect x="-12" y="-6" width="14" height="12" fill="#D4A017" stroke="#92400E" stroke-width="0.8"/>'
             '<line x1="2" y1="0" x2="52" y2="-18" stroke="#E5E7EB" stroke-width="1.1"/>'
             '<line x1="0" y1="5" x2="18" y2="26" stroke="#E5E7EB" stroke-width="1.6"/>'
             '<rect x="15" y="24" width="8" height="5" fill="#9CA3AF"/>'
             '<line x1="-2" y1="-6" x2="10" y2="-22" stroke="#E5E7EB" stroke-width="1.4"/>'
             '<circle cx="10" cy="-22" r="2.2" fill="#9CA3AF"/></g>')
    b.append(lab(46, 92, "EARTH", size=8, color="#BFDBFE", anchor="middle", ls=1.2))
    b.append(lab(144, 66, "LIGHT TRAVELS 24 HOURS", size=8, color="#FDE68A", anchor="middle", ls=1.2))
    b.append(lab(10, 26, "1 LIGHT-DAY", size=22, color="#fff", ls=1.2))
    b.append(lab(11, 40, "25.9 BILLION KM \u00b7 49 YEARS OUT", size=9, color="#FDE68A", ls=1.2))
    b.append(lab(262, 106, "VOYAGER 1", size=9, color="#fff", anchor="middle", ls=1.4))
    return svg(w, h, "".join(b), d)


def art_ukraine() -> str:
    w, h = W2, H2
    d = grad("uks", [(0, "#0C1E5B"), (0.62, "#1D4ED8"), (1, "#FACC15")])
    b = [f'<rect width="{w}" height="{h}" fill="url(#uks)"/>', stars(w, 40, 14, 3, 0.6)]
    for x0, ang in ((30, -22), (92, 8), (140, -30)):
        b.append(f'<path d="M{x0},{h} L{x0 + 90 * math.sin(math.radians(ang)) - 9:.1f},0 '
                 f'L{x0 + 90 * math.sin(math.radians(ang)) + 9:.1f},0 Z" fill="#FEF9C3" opacity="0.18"/>')
    for x, y, a in ((22, 22, 160), (52, 14, 170), (80, 30, 150), (110, 18, 165), (136, 36, 175),
                    (60, 44, 155), (150, 12, 170)):
        b.append(drone(x, y, 1.15, "#020617", a))
    for x, y in ((40, 34), (96, 22), (126, 46), (70, 18)):
        b.append(burst(x, y, 4.5, "#FDE047"))
    # skyline
    pts = "0,90 0,72 12,72 12,64 20,64 20,74 34,74 34,60 40,56 46,60 46,76 60,76 60,66 74,66 74,78 " \
          "88,78 88,62 96,62 96,70 112,70 112,58 116,50 120,58 120,74 136,74 136,66 150,66 150,78 " \
          "164,78 164,90"
    b.append(f'<polygon points="{pts}" fill="#0F172A"/>')
    # EU loan panel
    b.append(f'<rect x="168" y="0" width="{w - 168}" height="{h}" fill="#003399"/>')
    for i in range(12):
        a = -math.pi / 2 + i * math.pi / 6
        b.append(star5(206 + 26 * math.cos(a), 44 + 26 * math.sin(a), 3.6, "#FFCC00"))
    b.append(lab(206, 49, "\u20ac45bn", size=13, color="#fff", anchor="middle", ls=0.2))
    b.append(lab(206, 86, "EU LOAN 2027", size=7.5, color="#FFCC00", anchor="middle", ls=0.8))
    b.append(lab(8, 64, "126 / 141", size=16, color="#fff", ls=0.6, halo="#0C1E5B"))
    b.append(lab(9, 76, "DRONES DOWNED", size=7.5, color="#FDE68A", ls=1.0, halo="#0C1E5B"))
    return svg(w, h, "".join(b), d)


def art_markets() -> str:
    w, h = W2, H2
    b = [f'<rect width="{w}" height="{h}" fill="#04140E"/>']
    for x in range(0, w, 20):
        b.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{h}" stroke="#14532D" stroke-width="0.5"/>')
    for y in range(0, h, 15):
        b.append(f'<line x1="0" y1="{y}" x2="{w}" y2="{y}" stroke="#14532D" stroke-width="0.5"/>')
    # IPO record bars (left)
    bars = [(14, 22, "#065F46"), (34, 30, "#047857"), (54, 42, "#059669"), (74, 64, "#22C55E")]
    for x, bh, col in bars:
        b.append(f'<rect x="{x}" y="{78 - bh}" width="15" height="{bh}" fill="{col}"/>')
    b.append(lab(8, 18, "$81.3B", size=17, color="#4ADE80", ls=0.3))
    b.append(lab(8, 88, "BIGGEST IPO EVER", size=7, color="#A7F3D0", ls=0.8))
    b.append(chip(66, 26, "$83/SH", "#16A34A", size=8, pad=3))
    # Dow line (right), falling
    pts = [(124, 30), (136, 26), (148, 34), (160, 30), (172, 42), (184, 40), (196, 52), (208, 50),
           (220, 62), (234, 68)]
    path = "M" + " L".join(f"{x},{y}" for x, y in pts)
    b.append(f'<path d="{path} L234,80 L124,80 Z" fill="#7F1D1D" opacity="0.45"/>')
    b.append(f'<path d="{path}" fill="none" stroke="#F87171" stroke-width="2.2"/>')
    b.append('<path d="M228,62 L238,70 L226,72 Z" fill="#F87171"/>')
    b.append(f'<line x1="118" y1="4" x2="118" y2="{h - 4}" stroke="#166534" stroke-width="1"/>')
    b.append(lab(124, 18, "DOW \u22121.1%", size=13, color="#FCA5A5", ls=0.3))
    b.append(lab(124, 88, "HAWKISH FED MINUTES", size=7, color="#FECACA", ls=0.6))
    return svg(w, h, "".join(b))


def art_cyclone() -> str:
    w, h = W2, H2
    d = ('<radialGradient id="cyc" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#fff" stop-opacity="0.95"/>'
         '<stop offset="0.6" stop-color="#E0F2FE" stop-opacity="0.55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>'
         '</radialGradient>')
    b = [f'<rect width="{w}" height="{h}" fill="#0E4D7B"/>']
    # India east coast (Odisha/Andhra) top-left; Bengal delta top
    b.append('<path d="M0,0 L190,0 L184,8 L168,12 L150,10 L134,16 L120,22 L104,32 L90,44 L76,56 '
             'L62,66 L48,74 L36,82 L28,90 L0,90 Z" fill="#4D7C0F"/>')
    b.append('<path d="M0,0 L190,0 L184,8 L168,12 L150,10 L134,16 L120,22 L104,32 L90,44 L76,56 '
             'L62,66 L48,74 L36,82 L28,90" fill="none" stroke="#BEF264" stroke-width="1"/>')
    # cyclone spiral
    cx, cy = 168, 54
    b.append(f'<circle cx="{cx}" cy="{cy}" r="40" fill="url(#cyc)"/>')
    for i in range(4):
        a0 = i * math.pi / 2
        pts = []
        for t in range(0, 26):
            ang = a0 + t * 0.2
            r = 5 + t * 1.45
            pts.append(f"{cx + r * math.cos(ang):.1f},{cy + r * math.sin(ang) * 0.86:.1f}")
        b.append(f'<path d="M{" L".join(pts)}" fill="none" stroke="#fff" stroke-width="{4 - i * 0.4:.1f}" '
                 f'stroke-linecap="round" opacity="0.9"/>')
    b.append(f'<circle cx="{cx}" cy="{cy}" r="4" fill="#0E4D7B"/>')
    b.append(lab(8, 18, "ODISHA", size=11, color="#fff", ls=1.6, halo="#365314"))
    b.append(lab(8, 30, "INDIA", size=7.5, color="#ECFCCB", ls=1.6, halo="#365314"))
    b.append(lab(104, 86, "BAY OF BENGAL", size=7.5, color="#BAE6FD", ls=1.2, italic=True,
                 family="Noto Serif", weight=700, anchor="middle"))
    b.append(chip(w - 4, 4, "AKVAN", "#DC2626", size=9.5, anchor="end"))
    return svg(w, h, "".join(b), d)


def art_sudan() -> str:
    w, h = W2, H2
    d = grad("sds", [(0, "#7C2D12"), (0.55, "#EA580C"), (1, "#FDBA74")])
    b = [f'<rect width="{w}" height="{h}" fill="url(#sds)"/>']
    b.append(f'<circle cx="196" cy="58" r="16" fill="#FED7AA" opacity="0.8"/>')
    # smoke
    for x, y, r in ((70, 40, 12), (78, 28, 10), (88, 18, 9), (150, 44, 10), (156, 32, 8)):
        b.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#44403C" opacity="0.7"/>')
    # town
    pts = "0,90 0,64 18,64 18,58 34,58 34,66 46,66 46,54 52,48 54,30 56,48 62,54 62,66 80,66 80,58 " \
          "100,58 100,68 116,68 116,60 140,60 140,66 158,66 158,56 176,56 176,68 196,68 196,62 " \
          "214,62 214,70 244,70 244,90"
    b.append(f'<polygon points="{pts}" fill="#292524"/>')
    b.append(f'<rect y="80" width="{w}" height="10" fill="#57534E"/>')
    for x, y, a in ((112, 16, 200), (134, 26, 195), (180, 12, 205)):
        b.append(drone(x, y, 1.3, "#1C1917", a))
    b.append(burst(72, 58, 6, "#FDE047", "#FEF3C7"))
    b.append(burst(150, 56, 5, "#FDE047", "#FEF3C7"))
    b.append(lab(8, 20, "37 KILLED", size=15, color="#fff", ls=0.8, halo="#7C2D12"))
    b.append(lab(8, 32, "EL OBEID \u00b7 N. KORDOFAN", size=7.5, color="#FFEDD5", ls=0.8, halo="#7C2D12"))
    return svg(w, h, "".join(b), d)


def art_ukcpi() -> str:
    w, h = W3, H3
    b = [f'<rect width="{w}" height="{h}" fill="#012169"/>']
    vals = [(2.9, "M"), (3.0, "J"), (3.1, "J"), (3.2, "A"), (3.4, "S"), (3.6, "O")]
    for i, (v, m) in enumerate(vals):
        bh = (v - 2.4) * 40
        x = 92 + i * 16
        col = "#C8102E" if i == len(vals) - 1 else "#93A6D8"
        b.append(f'<rect x="{x}" y="{64 - bh:.1f}" width="11" height="{bh:.1f}" fill="{col}"/>')
        b.append(lab(x + 5.5, 73, m, size=6.5, color="#C7D2FE", anchor="middle", ls=0))
    b.append(lab(8, 28, "3.6%", size=24, color="#fff", ls=0.4))
    b.append(lab(9, 44, "UK CPI \u00b7 OCT", size=8, color="#FCA5A5", ls=1.0))
    # fuel pump icon
    b.append('<g transform="translate(10,54)"><rect width="11" height="16" rx="1.5" fill="#C8102E"/>'
             '<rect x="2" y="2.5" width="7" height="4.5" fill="#fff"/>'
             '<path d="M11,4 L15,7 L15,14 Q15,16 13,16" fill="none" stroke="#C8102E" stroke-width="1.6"/></g>')
    b.append(lab(30, 66, "RECORD DIESEL", size=6.5, color="#C7D2FE", ls=0.6))
    return svg(w, h, "".join(b))


def art_gaza() -> str:
    w, h = W3, H3
    d = grad("gzs", [(0, "#78350F"), (0.6, "#D97706"), (1, "#FCD34D")])
    b = [f'<rect width="{w}" height="{h}" fill="url(#gzs)"/>']
    pts = "0,60 0,40 10,40 10,34 22,34 22,46 30,46 30,30 36,30 40,38 44,38 44,50 58,50 58,42 64,36 " \
          "70,42 70,52 194,56 194,76 0,76"
    b.append(f'<polygon points="{pts}" fill="#44403C"/>')
    b.append(f'<rect y="56" width="{w}" height="20" fill="#A16207"/>')
    b.append('<path d="M80,76 L130,40" stroke="#FDE047" stroke-width="3" stroke-dasharray="6 4"/>')
    # tank, heading left across the line
    b.append('<g transform="translate(118,52)">'
             '<path d="M-28,10 L32,10 L36,18 L-32,18 Z" fill="#1C1917"/>'
             '<rect x="-24" y="2" width="44" height="9" rx="2" fill="#292524"/>'
             '<rect x="-12" y="-6" width="22" height="9" rx="3" fill="#1C1917"/>'
             '<rect x="-46" y="-3" width="36" height="3" fill="#1C1917"/>'
             + "".join(f'<circle cx="{x}" cy="14" r="3" fill="#57534E"/>' for x in range(-24, 30, 9))
             + '</g>')
    b.append(lab(8, 16, "YELLOW LINE", size=11, color="#FEF08A", ls=1.2, halo="#78350F"))
    b.append(lab(8, 27, "CENTRAL GAZA", size=7.5, color="#fff", ls=1.2, halo="#78350F"))
    return svg(w, h, "".join(b), d)


def art_capitol() -> str:
    w, h = W3, H3
    d = grad("cps", [(0, "#1E3A8A"), (1, "#60A5FA")])
    b = [f'<rect width="{w}" height="{h}" fill="url(#cps)"/>']
    g = ['<g fill="#F8FAFC">',
         '<rect x="6" y="54" width="112" height="22"/>',
         '<rect x="20" y="46" width="84" height="8"/>',
         '<path d="M38,46 Q62,8 86,46 Z"/>',
         '<rect x="58" y="10" width="8" height="10"/>',
         '<path d="M60,10 L62,2 L64,10 Z"/></g>']
    b.extend(g)
    for x in range(24, 104, 7):
        b.append(f'<rect x="{x}" y="57" width="2.4" height="17" fill="#93C5FD"/>')
    for x in range(42, 84, 6):
        b.append(f'<rect x="{x}" y="36" width="1.8" height="10" fill="#93C5FD"/>')
    b.append(lab(156, 34, "251\u201311", size=20, color="#fff", anchor="middle", ls=0.2))
    b.append(lab(156, 47, "CAUCUS VOTE", size=7.5, color="#DBEAFE", anchor="middle", ls=1.0))
    b.append(chip(126, 54, "SPEAKER PICK", "#B91C1C", size=7.5, pad=3))
    return svg(w, h, "".join(b), d)


def art_aria() -> str:
    w, h = W3, H3
    b = [f'<rect width="{w}" height="{h}" fill="#2E1065"/>']
    for i, col in enumerate(("#F472B6", "#FB923C", "#FACC15", "#4ADE80", "#38BDF8", "#A78BFA")):
        b.append(f'<circle cx="160" cy="26" r="{44 - i * 7}" fill="none" stroke="{col}" '
                 f'stroke-width="3.2" opacity="0.85"/>')
    b.append('<path d="M40,0 L10,76 L70,76 Z" fill="#FDE68A" opacity="0.12"/>')
    for i in range(7):
        x = 10 + i * 18
        b.append(f'<g transform="translate({x},48)">'
                 f'<path d="M0,0 L12,0 L10,8 Q6,12 2,8 Z" fill="#FACC15"/>'
                 f'<rect x="5" y="10" width="2" height="5" fill="#FACC15"/>'
                 f'<rect x="2" y="15" width="8" height="3" fill="#EAB308"/></g>')
    b.append(f'<rect y="70" width="{w}" height="6" fill="#1E1B4B"/>')
    b.append(lab(8, 22, "7 ARIAs", size=19, color="#fff", ls=0.4, halo="#2E1065"))
    b.append(lab(9, 35, "TAME IMPALA", size=8, color="#FBCFE8", ls=1.4, halo="#2E1065"))
    return svg(w, h, "".join(b))


def art_dhaka() -> str:
    w, h = W3, H3
    b = [f'<rect width="{w}" height="{h}" fill="#006A4E"/>',
         '<circle cx="150" cy="24" r="17" fill="#F42A41"/>']
    # factory sawtooth roof
    b.append('<path d="M104,48 L104,34 L116,26 L116,34 L128,26 L128,34 L140,26 L140,34 L152,26 '
             'L152,34 L164,26 L164,34 L176,26 L176,34 L194,34 L194,48 Z" fill="#064E3B"/>')
    b.append('<rect x="180" y="12" width="5" height="22" fill="#064E3B"/>')
    # highway in perspective
    b.append(f'<path d="M0,76 L76,46 L118,46 L{w},76 Z" fill="#374151"/>')
    b.append('<path d="M97,48 L97,52 M97,56 L97,61 M97,65 L97,72" stroke="#FDE047" stroke-width="1.6"/>')
    # crowd with placards
    r = lcg(11)
    for i in range(26):
        x = 6 + i * 7.1 + next(r) * 3
        y = 62 + next(r) * 6
        b.append(f'<circle cx="{x:.1f}" cy="{y - 6:.1f}" r="2.3" fill="#111827"/>'
                 f'<rect x="{x - 2.4:.1f}" y="{y - 3.6:.1f}" width="4.8" height="10" rx="1.5" fill="#111827"/>')
        if i % 4 == 1:
            b.append(f'<rect x="{x - 0.5:.1f}" y="{y - 20:.1f}" width="1" height="12" fill="#111827"/>'
                     f'<rect x="{x - 6:.1f}" y="{y - 24:.1f}" width="12" height="7" fill="#FEF3C7"/>')
    b.append(lab(8, 18, "WAGE PROTEST", size=11.5, color="#fff", ls=0.8, halo="#006A4E"))
    b.append(lab(8, 30, "SAVAR \u00b7 DHAKA", size=7.5, color="#D1FAE5", ls=1.2, halo="#006A4E"))
    return svg(w, h, "".join(b))


ART = {
    "apec": art_apec, "gulf": art_gulf, "voyager": art_voyager,
    "ukraine": art_ukraine, "markets": art_markets, "cyclone": art_cyclone, "sudan": art_sudan,
    "ukcpi": art_ukcpi, "gaza": art_gaza, "capitol": art_capitol, "aria": art_aria, "dhaka": art_dhaka,
}


# --------------------------------------------------------------------------- #
# World locator map
# --------------------------------------------------------------------------- #
# Natural Earth 1:110m land (public domain), Miller projection, lon -128..166,
# lat 80..-56, 300 px wide, simplified (Ramer-Douglas-Peucker, 0.4 px).
WORLD_PATH = (
    "M61.5,168.1L64.2,169.3L63.8,170.0L62.3,169.6L61.1,170.6L58.2,169.8L55.8,168.3L54.4,166.7L58."
    "1,168.4L59.9,166.3L60.6,166.5L61.5,168.1ZM70.9,164.4L71.7,165.0L71.4,165.4L70.0,165.9L69.5,1"
    "65.4L68.7,166.0L68.2,165.4L70.9,164.4ZM279.0,151.2L281.9,151.3L282.0,152.8L281.5,154.2L281.2"
    ",153.8L280.5,154.7L279.6,154.6L278.3,151.7L278.3,151.1L279.0,151.2ZM307.2,151.4L308.4,151.9L"
    "306.8,154.4L307.2,155.0L305.6,155.5L304.7,157.6L302.5,158.5L300.7,158.0L301.1,156.5L304.6,15"
    "3.9L306.2,151.4L306.9,150.8L307.2,151.4ZM301.1,130.1L299.5,129.6L298.0,127.9L301.1,130.1ZM18"
    "1.7,121.0L182.0,123.3L181.3,123.3L181.4,124.5L178.7,133.1L176.9,133.8L175.6,133.2L174.9,129."
    "2L175.9,127.9L175.5,125.1L176.0,123.8L177.9,123.4L179.3,122.1L180.8,119.5L181.7,121.0ZM277.1"
    ",121.3L277.5,122.1L278.1,121.7L279.0,122.5L280.0,126.7L282.5,128.2L283.3,130.3L284.4,130.4L2"
    "84.6,131.5L286.9,134.3L287.3,136.6L286.6,140.5L283.1,147.6L281.9,147.6L279.9,149.1L278.4,148"
    ".4L278.6,147.7L277.2,148.8L274.1,147.9L273.0,145.7L271.6,145.1L271.6,143.6L270.2,144.7L271.2"
    ",141.9L269.4,144.2L267.6,141.6L264.6,140.4L259.3,141.2L257.4,142.0L256.8,143.1L253.0,143.2L2"
    "51.0,144.4L249.6,144.4L248.0,143.4L248.8,141.2L247.6,137.0L246.3,134.4L246.7,134.9L246.4,133"
    ".9L247.2,134.6L246.3,132.5L247.1,129.7L247.2,130.5L249.7,128.6L253.9,127.5L256.1,124.0L256.6"
    ",124.9L257.0,124.7L256.6,124.2L258.9,121.7L260.3,121.3L261.6,122.4L262.9,122.5L262.7,121.9L2"
    "63.9,120.0L265.9,119.6L265.1,118.7L265.7,118.5L268.7,119.7L269.9,119.3L270.4,119.8L269.3,120"
    ".8L268.9,122.5L273.7,125.4L274.4,125.0L275.2,122.6L275.7,118.4L276.0,118.1L276.3,118.6L277.1"
    ",121.3ZM257.6,117.5L256.6,117.6L257.1,116.6L259.1,115.8L260.5,115.7L257.6,117.5ZM241.5,114.1"
    "L243.6,113.7L248.7,115.7L247.5,116.1L243.5,115.4L238.1,114.1L238.8,113.2L241.5,114.1ZM285.7,"
    "112.7L283.4,113.6L282.0,113.0L283.7,112.3L284.5,112.7L285.2,111.4L285.9,111.4L285.7,112.7ZM2"
    "86.9,111.7L286.6,112.0L284.6,109.7L286.9,111.7ZM267.5,108.3L267.8,110.0L268.8,110.6L269.7,10"
    "9.5L271.8,108.9L278.1,111.1L279.6,112.7L281.3,113.3L281.5,113.9L280.6,114.0L280.8,114.7L284."
    "5,117.7L283.7,118.0L281.5,117.5L279.6,115.4L278.3,114.9L276.8,115.6L277.0,116.3L276.2,116.7L"
    "272.6,115.4L271.0,115.7L272.1,114.6L271.4,112.6L267.0,110.7L266.3,111.3L265.3,110.0L267.0,10"
    "9.4L265.5,109.4L263.8,108.1L265.7,107.5L267.5,108.3ZM258.4,105.7L256.8,106.9L253.2,106.9L253"
    ".1,107.7L254.0,108.6L256.5,107.8L254.6,109.1L256.3,112.6L255.3,112.5L255.8,111.7L254.6,111.8"
    "L254.1,109.8L253.4,110.1L253.5,112.8L252.4,112.6L252.5,110.7L251.8,110.0L253.1,106.6L254.0,1"
    "05.8L256.0,106.2L258.4,105.7ZM261.9,106.0L261.2,107.4L261.6,107.9L260.9,107.4L260.8,105.3L26"
    "1.2,104.9L261.9,106.0ZM238.6,113.1L237.5,113.1L235.3,111.4L231.2,105.3L227.9,102.1L227.9,101"
    ".5L230.1,101.8L233.3,105.0L234.3,105.0L236.6,107.0L236.2,107.9L238.9,110.3L238.6,113.1ZM250."
    "9,105.3L252.0,106.2L250.8,106.3L250.5,108.0L249.6,108.6L249.1,111.2L247.8,111.3L246.2,110.3L"
    "245.0,110.7L243.1,110.1L241.8,106.7L242.5,105.1L243.3,105.4L244.0,105.2L244.3,104.4L245.9,10"
    "4.0L249.7,100.1L252.2,101.6L250.3,103.8L250.9,105.3ZM259.6,98.5L259.7,99.8L259.4,100.7L259.0"
    ",99.7L258.5,100.2L258.6,101.4L257.4,100.8L257.4,99.6L256.7,99.1L255.9,99.5L255.2,100.1L255.4"
    ",98.9L258.6,97.9L258.6,97.1L259.6,98.5ZM213.5,100.8L212.6,101.0L212.1,100.2L212.4,97.1L213.1"
    ",97.6L214.1,99.4L213.5,100.8ZM251.5,97.6L250.2,98.6L252.0,96.5L252.6,95.5L252.7,96.3L251.5,9"
    "7.6ZM254.4,88.0L255.4,88.1L255.6,89.5L254.8,90.7L254.8,92.4L257.1,93.0L257.2,94.3L256.4,93.8"
    "L256.0,93.2L255.8,93.6L253.7,92.9L254.1,92.2L253.1,91.7L252.9,90.3L253.4,90.6L253.8,88.0L254"
    ".4,88.0ZM56.6,86.6L59.2,86.8L60.9,87.9L58.2,88.3L57.8,89.0L54.6,88.2L56.8,87.9L55.7,86.8L56."
    "6,86.6ZM243.2,87.9L242.3,88.4L241.5,88.0L241.5,87.1L243.1,86.3L243.9,86.8L243.2,87.9ZM49.3,8"
    "3.5L54.9,86.1L51.3,86.6L52.0,86.0L49.7,84.8L47.1,84.1L47.1,83.6L43.9,84.4L46.7,83.0L49.3,83."
    "5ZM254.3,83.5L253.8,84.4L253.3,83.4L253.8,81.6L254.6,80.8L255.1,81.1L254.3,83.5ZM268.0,70.9L"
    "267.6,72.0L267.1,71.6L266.3,72.5L265.7,72.2L266.2,71.0L268.0,70.9ZM146.4,66.1L146.0,68.0L144"
    ".7,67.5L143.3,66.9L143.4,66.2L146.4,66.1ZM140.0,62.5L140.6,63.4L140.5,65.0L139.2,65.0L138.9,"
    "62.9L140.0,62.5ZM274.5,67.4L273.7,69.7L270.6,70.4L269.2,71.7L268.4,70.4L264.3,71.2L265.3,72."
    "0L264.0,74.4L263.5,74.0L263.7,73.0L262.7,71.9L265.9,69.4L269.1,69.3L270.1,67.2L270.8,67.8L27"
    "2.9,66.1L273.8,62.6L274.9,62.3L275.4,64.0L274.5,67.4ZM277.5,58.9L278.9,58.6L279.1,60.0L277.6"
    ",60.4L276.7,61.6L275.1,60.7L274.6,62.1L273.4,62.1L273.3,60.9L273.8,59.9L274.9,59.9L275.5,57."
    "2L277.5,58.9ZM4.6,53.3L2.4,52.9L-0.1,51.4L-0.4,50.3L2.3,51.0L4.6,53.3ZM73.3,50.5L72.7,51.6L7"
    "3.3,51.2L74.0,51.5L73.7,51.9L76.0,52.4L75.7,53.3L76.4,53.1L76.9,54.6L76.5,55.7L75.3,55.6L75."
    "3,54.3L74.1,55.5L73.5,55.4L74.2,54.8L73.2,54.5L70.1,54.5L70.6,53.7L70.2,53.3L72.1,50.4L73.6,"
    "49.2L74.1,49.2L73.3,50.5ZM277.2,50.4L278.2,52.7L276.7,52.3L276.1,54.2L277.0,56.4L276.3,55.6L"
    "275.6,56.6L275.6,51.9L275.1,48.8L275.2,46.9L276.1,46.2L275.7,45.6L276.2,45.4L277.2,50.4ZM123"
    ".7,48.3L121.9,49.1L120.4,48.9L121.3,47.5L120.7,46.1L122.9,44.3L124.8,45.1L123.7,48.3ZM127.5,"
    "39.2L126.5,40.8L128.6,40.6L127.4,43.1L128.5,43.2L131.1,47.4L132.3,47.7L131.7,48.9L132.1,49.6"
    "L131.2,50.4L124.7,51.2L127.1,49.5L125.2,48.7L126.3,48.3L125.9,46.6L127.5,46.7L127.6,45.9L126"
    ".9,45.1L125.7,44.8L125.5,43.4L124.9,44.1L124.3,41.9L125.5,39.2L127.5,39.2ZM43.7,28.1L43.9,28"
    ".9L44.4,28.6L47.3,30.1L47.4,30.9L48.9,31.3L48.0,31.8L46.4,31.4L45.8,30.7L43.3,32.4L43.0,31.4"
    "L41.6,31.6L42.5,30.8L43.0,28.0L43.7,28.1ZM115.8,26.8L115.6,27.9L116.7,29.0L115.4,30.3L111.6,"
    "31.7L107.4,30.9L108.4,30.2L106.2,29.4L108.0,29.1L107.9,28.6L105.8,28.2L106.5,27.1L108.0,26.8"
    "L109.6,28.0L111.2,27.1L112.5,27.6L114.1,26.6L115.8,26.8ZM53.2,25.6L52.1,25.7L51.8,24.8L52.2,"
    "23.8L53.2,23.6L54.0,24.1L54.0,24.8L53.2,25.6ZM33.0,22.1L32.4,22.8L30.2,22.4L28.8,21.6L29.7,2"
    "1.1L30.4,20.3L33.0,22.1ZM38.2,21.4L38.2,23.3L39.6,21.9L40.8,23.0L40.5,24.3L41.5,25.5L43.3,22"
    ".7L43.3,20.7L46.3,21.1L47.7,22.0L47.0,23.9L47.7,24.8L47.6,25.6L45.6,26.8L44.1,27.1L43.1,26.6"
    "L41.5,29.6L40.3,30.7L38.9,30.8L38.1,31.5L38.0,32.5L36.8,32.7L35.6,34.0L34.4,35.8L34.0,38.7L3"
    "5.5,39.0L36.4,41.5L37.9,41.2L43.9,44.1L46.7,44.3L46.8,46.9L49.1,49.8L50.4,47.9L49.2,45.0L50."
    "8,44.3L52.5,42.3L51.7,40.1L50.5,39.0L51.7,37.4L50.9,33.6L55.3,33.4L57.8,35.4L59.6,35.5L59.9,"
    "38.7L61.6,39.8L63.1,39.0L64.7,36.6L68.0,41.7L67.6,42.6L72.1,45.0L72.5,46.2L73.7,46.9L73.8,48"
    ".5L69.4,51.1L62.9,51.1L58.1,55.5L62.7,52.5L64.2,52.4L65.1,53.0L64.2,53.9L64.8,56.3L66.1,56.9"
    "L67.8,56.7L68.9,55.3L69.6,56.7L63.9,59.7L63.1,59.6L63.1,58.5L64.9,57.5L62.1,57.7L62.3,58.1L5"
    "9.1,59.5L58.5,60.3L58.3,61.2L59.2,62.0L55.4,62.9L57.2,62.9L55.2,63.1L54.2,65.3L53.5,64.6L54."
    "0,65.9L53.1,67.3L52.7,65.0L52.7,66.3L52.1,66.1L52.8,66.5L53.3,69.3L47.6,74.0L48.9,79.0L48.6,"
    "80.9L47.2,80.1L46.0,76.6L44.8,75.5L43.8,76.0L42.4,75.1L39.6,75.2L39.2,75.4L39.6,76.4L38.6,76"
    ".6L34.8,75.9L31.3,78.5L30.7,83.8L31.4,85.8L32.8,87.7L34.3,88.4L38.0,87.2L38.5,85.4L41.8,84.8"
    "L42.0,85.5L41.0,88.3L40.5,88.0L40.5,90.1L39.9,90.8L43.9,90.7L45.5,91.4L45.1,95.8L46.7,97.9L4"
    "8.0,98.1L49.4,97.3L52.2,98.3L53.4,97.5L54.2,95.8L55.7,95.6L57.4,94.4L58.0,94.7L57.2,95.4L57."
    "5,97.8L58.1,97.0L57.8,95.9L59.0,95.5L59.2,94.7L61.0,96.3L64.4,96.8L65.0,96.2L67.5,96.2L66.6,"
    "96.5L67.0,96.9L68.5,97.5L68.7,98.4L70.3,99.0L72.3,101.0L75.6,101.3L78.2,102.8L79.6,105.4L79."
    "2,107.2L81.0,107.4L81.0,108.4L81.8,107.7L84.8,108.7L85.1,109.9L89.8,110.1L92.6,112.1L94.3,11"
    "2.4L95.2,114.6L94.8,116.3L91.1,120.5L90.5,125.6L88.8,129.9L87.8,131.0L85.1,131.4L82.0,133.1L"
    "81.1,134.1L80.7,137.2L75.7,143.7L73.2,144.2L71.0,143.1L70.9,143.7L72.2,144.7L72.7,146.6L71.7"
    ",148.1L70.2,148.7L67.0,148.8L67.2,151.1L66.6,151.5L64.2,151.5L64.3,152.8L65.6,152.7L65.9,153"
    ".4L64.1,154.5L63.7,156.5L61.9,157.1L61.7,158.1L63.6,159.3L63.3,160.4L60.1,163.9L61.1,166.1L5"
    "9.7,166.0L58.3,166.8L57.7,168.1L54.1,165.9L53.8,165.1L53.5,161.1L55.0,158.9L53.4,158.5L54.4,"
    "157.4L54.7,155.3L55.9,155.7L56.4,153.1L55.7,152.8L55.4,154.4L54.8,154.2L55.9,149.4L55.5,146."
    "9L57.7,141.4L57.7,137.4L58.3,136.1L59.0,127.6L58.8,126.1L57.7,125.0L53.1,122.2L49.2,114.5L47"
    ".7,113.4L47.5,112.0L49.2,109.8L48.0,109.4L48.0,108.2L48.9,106.3L50.1,105.7L51.9,103.2L50.8,9"
    "8.6L49.4,98.0L48.5,98.9L49.0,99.4L48.1,99.8L47.9,99.1L45.4,98.5L43.9,96.8L43.8,97.3L43.2,97."
    "0L43.2,95.8L41.3,93.5L37.5,92.8L34.0,90.5L32.1,91.0L25.0,88.3L23.0,86.5L23.2,84.9L22.4,83.5L"
    "19.1,80.5L19.1,79.5L16.1,76.7L15.2,74.3L14.4,73.8L13.5,73.6L13.6,75.4L16.7,79.3L17.7,81.8L19"
    ".0,82.9L18.3,83.4L16.1,81.4L16.0,80.0L13.2,78.1L14.1,77.2L12.7,76.1L10.9,72.1L9.7,71.0L7.5,7"
    "0.4L3.7,63.6L4.2,57.2L3.4,53.8L5.0,54.0L5.5,55.2L5.3,52.7L0.6,50.3L0.2,48.2L-1.2,47.6L-1.3,4"
    "6.5L-4.0,43.8L-6.2,40.0L-8.8,39.8L-12.1,37.9L-16.3,37.2L-19.5,35.8L-20.6,36.1L-20.4,37.2L-24"
    ".2,38.4L-23.9,36.0L-22.8,35.6L-23.1,35.2L-26.6,38.1L-25.8,38.9L-26.8,39.9L-31.1,43.1L-37.7,4"
    "5.1L-31.3,41.6L-30.3,40.8L-29.6,38.8L-31.7,39.5L-33.0,38.6L-34.7,39.2L-34.6,37.7L-35.2,37.2L"
    "-36.5,37.5L-38.1,36.4L-38.9,34.8L-38.5,33.9L-37.3,32.2L-35.8,32.4L-33.4,31.2L-34.2,30.2L-33."
    "4,29.6L-35.5,30.3L-37.7,30.1L-39.2,29.7L-40.9,28.1L-37.2,26.6L-36.4,26.6L-36.5,27.4L-34.4,27"
    ".3L-39.6,23.5L-39.0,22.5L-37.2,22.5L-35.9,21.7L-34.6,19.9L-30.7,19.0L-29.2,18.0L-26.9,19.2L-"
    "24.7,19.0L-24.8,19.4L-23.2,19.7L-15.9,20.2L-8.7,22.5L-6.5,21.2L-5.0,21.4L-1.8,20.2L-1.1,20.9"
    "L-0.1,19.6L2.3,21.5L3.6,20.2L3.8,21.6L5.4,20.8L6.7,20.9L10.6,22.3L13.0,22.5L14.4,23.4L13.0,2"
    "4.3L14.8,24.6L18.4,24.1L19.5,25.2L20.6,24.3L19.6,23.6L20.2,22.9L22.3,22.7L24.1,24.1L27.1,24."
    "7L30.2,24.5L30.0,23.4L30.9,23.1L32.5,23.7L32.5,25.3L33.2,23.9L34.0,24.0L34.5,22.2L32.2,20.4L"
    "32.3,18.3L33.5,16.9L35.8,18.1L37.2,20.2L36.3,21.1L38.2,21.4ZM14.1,14.6L13.6,15.5L15.9,15.0L1"
    "7.3,15.9L18.4,14.9L20.2,17.5L20.7,16.7L20.0,14.7L20.9,14.4L23.1,15.5L24.0,18.7L27.6,20.5L27."
    "5,21.3L25.8,21.4L26.4,22.1L26.1,22.8L21.3,22.1L15.0,23.2L14.4,22.3L12.1,22.0L10.9,20.6L15.9,"
    "19.9L10.3,19.5L9.8,18.9L12.1,18.1L8.8,17.6L10.3,15.4L13.1,14.3L14.1,14.6ZM24.0,14.1L23.1,15."
    "3L21.5,14.0L21.8,13.7L24.0,14.1ZM52.7,14.7L52.8,15.2L49.2,15.3L48.1,14.2L48.6,13.4L51.0,13.6"
    "L52.7,14.7ZM42.3,14.6L43.1,15.8L44.0,14.2L46.6,13.4L48.4,15.4L48.2,16.7L51.2,15.4L54.9,17.2L"
    "55.0,18.1L56.9,17.6L58.0,18.8L61.3,20.3L62.3,22.0L60.4,22.8L64.4,24.4L65.9,26.0L67.5,26.1L67"
    ".2,27.3L65.4,29.2L62.5,26.9L61.2,27.1L61.1,28.1L64.0,30.2L64.6,31.8L64.3,33.0L60.4,31.3L63.1"
    ",34.2L58.1,32.6L56.9,31.8L57.3,31.4L54.3,29.7L54.3,30.2L51.3,30.5L50.5,29.9L51.1,28.7L55.1,2"
    "8.5L54.8,27.9L56.5,25.3L56.2,24.6L54.2,23.1L52.2,22.5L52.8,22.1L50.0,20.2L47.6,21.0L40.1,19."
    "8L39.3,19.1L40.3,18.3L38.9,18.3L38.6,16.3L40.4,13.8L43.0,13.3L42.3,14.6ZM28.2,13.2L31.2,13.4"
    "L31.5,14.0L30.6,14.9L32.1,15.7L31.9,17.4L30.2,18.2L26.0,15.8L26.0,15.2L28.1,15.4L27.0,14.2L2"
    "8.2,13.2ZM277.1,14.5L273.5,14.3L274.3,13.4L275.6,13.2L277.1,14.5ZM35.5,15.3L34.4,16.8L33.3,1"
    "6.7L32.6,15.0L33.2,13.2L34.2,12.6L38.3,13.2L36.7,14.9L35.5,15.3ZM7.7,17.9L5.0,18.9L4.5,18.0L"
    "2.1,17.0L4.1,13.5L3.1,12.3L6.6,12.0L10.7,12.5L12.7,13.9L9.0,15.8L7.7,17.1L7.7,17.9ZM284.4,10"
    ".7L283.2,11.5L279.7,10.5L280.0,9.9L284.4,10.7ZM35.1,10.9L34.5,11.7L33.1,11.6L31.8,11.0L32.4,"
    "10.1L33.8,9.6L35.1,10.9ZM278.7,9.7L277.9,11.3L272.4,11.7L270.4,10.3L270.9,8.9L272.3,8.5L275."
    "0,8.6L278.7,9.7ZM30.1,7.3L30.9,8.3L30.4,10.9L27.7,10.8L27.7,9.6L26.0,9.7L26.0,8.1L30.1,7.3ZM"
    "20.2,8.4L20.6,9.1L22.6,8.9L22.1,10.9L14.5,12.1L14.4,11.5L16.5,10.6L11.9,10.8L10.5,10.4L12.9,"
    "7.8L15.7,8.5L17.5,9.8L19.3,9.9L17.9,7.9L18.8,7.1L19.8,7.4L20.2,8.4ZM189.3,19.2L185.4,19.1L18"
    "5.1,18.3L183.3,17.8L183.1,16.8L184.2,16.4L184.1,15.3L186.2,13.6L185.2,13.4L187.7,11.6L187.4,"
    "10.7L193.0,8.3L200.2,6.8L200.9,7.7L193.5,10.4L190.3,12.3L187.2,16.1L187.4,17.7L189.3,19.2ZM3"
    "4.0,6.5L35.1,7.2L37.1,7.2L38.0,7.9L37.8,8.7L39.6,9.6L47.8,9.4L48.9,10.2L49.1,11.0L48.5,11.6L"
    "40.7,12.1L36.3,11.2L35.8,9.1L34.8,8.1L31.5,7.2L31.9,6.4L34.0,6.5ZM12.0,5.3L11.9,7.0L11.1,7.7"
    "L6.6,9.0L5.3,8.6L9.1,5.6L12.0,5.3ZM239.8,6.8L240.0,7.8L244.0,7.3L247.1,9.1L246.8,10.2L242.2,"
    "12.5L245.0,13.3L245.9,12.9L246.5,14.2L248.5,13.4L251.8,13.7L252.1,14.6L256.3,14.9L256.4,13.4"
    "L260.2,13.8L261.8,14.8L262.3,16.0L261.7,16.8L264.6,19.1L265.6,17.1L267.2,18.0L268.9,17.5L270"
    ".9,18.0L271.7,17.5L273.3,17.8L272.6,16.0L273.9,15.2L283.2,16.4L284.0,17.5L286.7,19.0L292.9,1"
    "8.9L293.7,19.7L293.6,21.0L294.8,21.5L301.9,21.3L303.7,22.9L304.9,22.3L304.1,21.2L304.5,20.3L"
    "309.9,20.7L312.9,21.6L314.3,22.4L314.3,29.2L313.0,30.0L311.6,29.9L313.6,32.5L313.5,33.6L311."
    "6,33.2L307.8,34.6L304.4,37.3L303.0,36.3L300.3,37.5L299.8,36.9L298.9,37.6L297.5,37.4L295.9,39"
    ".8L296.0,40.4L297.1,40.7L297.0,42.8L296.1,42.9L295.6,44.1L296.0,44.7L294.3,45.4L293.9,47.0L2"
    "92.4,47.4L292.1,48.8L290.6,50.0L289.2,44.0L289.7,42.0L290.6,40.4L292.2,40.1L297.6,35.4L298.4"
    ",33.2L297.2,33.3L296.6,34.6L294.0,36.3L293.2,34.4L290.5,34.9L288.0,37.5L288.8,38.5L285.0,39."
    "0L285.0,37.9L283.5,37.7L282.2,38.4L275.7,38.6L268.5,44.9L270.1,45.1L271.6,46.3L272.2,45.6L27"
    "3.4,45.7L274.8,47.2L274.9,48.4L274.1,49.7L273.5,53.4L271.7,56.2L268.2,59.9L266.9,60.6L265.6,"
    "60.0L263.2,61.7L263.0,62.9L260.7,64.3L260.6,65.0L262.7,67.8L262.3,69.8L259.7,70.6L259.3,67.9"
    "L260.1,67.7L259.4,66.7L257.9,66.3L258.5,64.5L257.4,64.1L254.1,65.3L255.3,63.5L254.7,62.9L252"
    ".1,64.9L251.1,65.0L250.5,65.5L252.0,67.0L252.8,67.4L253.9,66.5L255.5,67.0L255.6,67.7L254.2,6"
    "8.0L252.2,70.0L253.3,70.6L255.0,73.7L255.0,74.5L254.4,74.8L255.2,75.8L254.8,77.6L251.7,81.6L"
    "248.9,83.5L243.7,85.0L243.3,86.1L242.7,86.2L242.7,85.0L241.3,84.6L238.7,86.7L238.4,87.4L241."
    "7,91.4L242.2,93.3L242.0,95.2L237.9,98.3L237.8,97.0L236.2,96.2L235.3,94.6L233.5,94.2L233.7,93"
    ".4L232.8,93.4L231.9,97.7L232.5,97.7L233.1,99.5L235.7,101.5L237.0,105.8L234.1,104.3L232.7,100"
    ".5L231.1,98.6L231.0,99.2L231.4,95.4L229.8,89.7L227.9,91.0L226.7,90.6L226.9,88.3L223.9,83.5L2"
    "23.0,83.5L222.7,84.5L219.4,84.9L218.9,86.3L217.4,87.0L214.5,90.1L212.6,90.8L212.1,96.5L209.7"
    ",99.0L208.8,98.0L205.6,90.7L204.7,85.0L202.5,85.5L201.2,84.2L201.4,83.4L199.4,82.2L198.3,80."
    "6L193.4,81.0L189.2,80.3L188.3,78.7L186.4,79.5L185.2,79.1L183.2,78.0L181.8,75.4L180.6,75.2L17"
    "9.6,75.6L180.4,78.1L181.8,79.2L182.5,81.4L182.7,80.0L183.3,80.2L183.5,82.1L185.7,82.0L188.1,"
    "79.6L188.6,81.9L190.5,82.6L191.6,84.0L189.6,86.2L189.5,87.6L187.0,89.4L184.1,90.3L183.8,91.1"
    "L180.3,92.7L175.0,94.2L174.1,89.9L170.6,85.1L169.9,82.5L166.0,77.7L166.2,76.1L165.2,78.2L163"
    ".7,75.7L167.0,82.2L166.9,83.1L168.2,84.3L168.9,87.9L169.8,88.6L170.7,90.7L174.8,94.4L174.2,9"
    "5.1L176.1,96.4L182.8,94.8L182.2,97.7L180.2,101.7L178.1,104.2L171.7,109.8L170.1,113.2L170.9,1"
    "14.1L170.6,115.8L171.9,118.2L172.2,122.2L170.9,124.3L168.8,125.3L166.1,127.6L166.9,130.0L166"
    ".8,132.2L163.9,134.0L164.2,134.5L163.5,137.3L159.4,141.8L156.9,143.1L153.6,143.1L151.1,144.1"
    "L149.4,143.4L149.2,140.5L146.1,135.5L144.8,129.6L142.6,125.8L142.5,124.3L144.6,118.1L142.8,1"
    "12.3L139.6,108.3L140.6,104.0L140.2,103.3L139.3,102.3L136.6,102.8L135.0,100.7L132.5,100.9L128"
    ".6,102.3L125.9,101.9L122.9,102.7L121.4,102.2L117.9,99.7L115.5,96.0L113.7,94.7L113.6,93.2L112"
    ".6,92.0L113.8,90.5L114.1,88.5L113.3,84.4L115.9,79.7L120.9,75.7L121.1,72.7L123.6,70.9L124.6,6"
    "9.0L128.4,69.7L132.1,68.0L140.3,67.2L141.0,67.3L141.0,67.9L141.9,67.7L141.2,71.3L146.2,73.0L"
    "146.6,74.0L150.1,75.3L151.1,74.5L151.2,73.1L152.6,72.4L160.1,74.6L162.2,73.8L163.2,74.5L165."
    "1,74.5L167.3,70.3L167.5,68.0L166.0,67.8L163.8,68.6L163.0,68.0L160.9,68.6L158.8,68.0L157.5,66"
    ".1L158.0,65.2L157.3,64.7L158.4,63.5L160.0,63.5L160.4,62.5L162.4,62.7L164.8,61.6L166.5,61.5L1"
    "69.7,62.9L171.8,62.8L173.2,61.6L172.9,60.8L168.0,57.5L169.6,56.3L169.1,55.8L170.5,55.0L166.3"
    ",56.2L166.3,57.0L167.9,57.3L167.7,57.7L165.2,58.7L164.6,58.4L164.8,57.8L163.7,57.4L164.9,56."
    "8L164.6,56.5L162.0,55.8L160.8,57.8L160.0,58.0L158.9,60.9L160.0,62.7L158.8,62.8L157.5,63.8L15"
    "7.2,63.0L156.0,62.9L154.8,63.2L155.5,63.9L155.0,64.1L153.7,63.7L155.1,66.8L154.2,66.5L154.2,"
    "68.3L153.6,68.3L150.4,63.7L150.6,61.9L147.0,59.7L145.8,57.8L145.2,57.6L144.8,58.1L144.8,57.1"
    "L144.0,56.9L143.2,57.4L143.5,59.0L146.1,61.6L146.9,61.6L146.8,62.1L149.5,63.8L149.3,64.2L147"
    ".8,63.5L147.4,64.3L148.1,64.7L148.0,65.3L147.0,66.4L146.6,66.5L147.1,65.3L146.3,64.0L143.0,6"
    "1.9L141.3,60.4L141.0,59.2L139.7,58.7L137.3,60.2L133.8,60.3L133.7,61.7L131.4,62.8L130.3,64.8L"
    "130.7,65.5L128.4,68.0L126.2,68.0L125.1,68.8L124.0,67.6L121.5,67.7L121.6,66.1L120.9,65.5L121."
    "7,63.1L121.0,60.3L122.5,59.4L128.7,59.8L129.4,56.6L127.6,54.6L126.0,54.1L125.9,53.1L129.0,53"
    ".2L128.6,51.7L129.6,52.2L132.0,51.2L132.3,50.1L134.5,49.2L135.4,47.2L137.9,46.3L138.9,46.6L1"
    "39.6,45.9L138.9,43.8L139.3,41.5L141.4,40.6L141.1,41.8L141.7,42.4L140.5,43.8L140.8,45.1L141.8"
    ",45.9L143.4,45.3L145.0,46.3L148.6,44.7L150.7,45.3L152.3,44.2L152.1,41.9L152.6,41.0L153.6,40."
    "5L154.4,41.6L155.2,41.6L155.5,39.6L154.5,39.3L154.4,38.4L157.0,37.7L159.2,38.0L160.3,37.1L15"
    "9.3,36.4L153.9,37.4L152.4,36.1L152.1,33.1L152.6,32.2L156.5,29.0L156.4,28.3L155.0,27.5L153.2,"
    "28.0L152.3,29.2L152.4,30.2L148.8,32.9L148.1,35.1L149.8,37.0L148.8,38.7L147.8,39.1L146.8,42.9"
    "L145.6,42.8L145.0,43.9L143.8,44.0L141.2,38.0L139.2,39.7L137.8,40.0L136.4,39.3L135.7,34.1L141"
    ".4,30.1L145.7,24.4L150.2,20.9L154.1,20.2L155.7,18.6L159.4,18.3L162.5,19.7L161.2,20.2L162.3,2"
    "1.3L163.4,20.7L171.7,24.2L172.6,26.2L171.4,27.1L169.8,27.5L164.5,26.5L166.1,27.7L166.3,30.2L"
    "168.4,31.1L167.9,29.6L168.5,29.0L171.0,30.0L171.9,29.6L171.2,28.4L173.6,26.7L175.5,27.4L176."
    "1,26.3L175.2,25.2L175.7,24.2L175.0,23.1L177.8,23.7L178.4,24.6L177.1,24.9L177.1,25.8L177.9,26"
    ".4L179.5,26.0L179.7,24.9L185.4,22.6L186.2,22.7L185.2,23.7L186.5,23.9L190.6,22.5L191.8,23.6L1"
    "92.9,22.4L191.9,21.4L192.4,20.8L195.4,21.3L200.5,23.9L201.2,23.0L200.1,21.7L198.9,21.5L199.2"
    ",20.7L198.7,18.6L202.0,14.8L204.7,15.3L204.9,16.4L203.9,17.9L204.9,19.8L204.7,22.3L205.8,23."
    "4L203.3,27.0L204.5,27.2L207.2,24.5L206.6,23.5L207.1,22.4L206.0,22.2L205.7,21.2L206.5,19.4L20"
    "5.2,17.8L207.0,16.6L206.8,15.2L207.8,16.2L207.4,18.1L208.5,18.4L208.1,17.0L209.8,16.3L211.9,"
    "16.2L213.8,17.3L212.9,15.7L212.8,13.6L219.2,13.0L218.4,12.0L219.6,10.6L225.4,9.3L225.7,8.7L2"
    "28.4,8.5L229.3,9.0L231.6,7.9L233.4,7.9L234.7,6.1L237.1,5.2L238.8,5.9L237.5,6.4L239.8,6.8ZM18"
    ".2,5.2L16.3,5.8L14.8,5.1L15.6,4.4L18.5,4.5L18.2,5.2ZM155.8,4.8L153.6,5.7L151.8,5.2L152.5,4.7"
    "L151.8,4.0L154.0,3.5L154.4,4.4L155.8,4.8ZM32.8,4.4L31.3,4.9L30.5,4.3L30.0,2.6L31.9,2.8L33.1,"
    "3.6L32.8,4.4ZM28.5,3.8L28.9,4.7L27.2,4.5L23.3,3.7L24.3,3.0L23.0,2.5L23.0,1.6L25.0,1.9L27.7,2"
    ".7L28.5,3.8ZM237.8,3.8L232.1,4.7L233.9,1.8L234.8,1.5L238.1,2.9L237.8,3.8ZM149.2,0.7L152.6,2."
    "4L150.0,3.3L148.1,7.1L146.9,7.2L144.7,5.9L145.6,5.1L144.1,4.5L142.1,2.6L141.3,0.8L144.1,-0.0"
    "L144.6,0.8L146.1,0.8L146.5,-0.0L147.9,-0.1L149.2,0.7ZM156.6,-1.0L158.6,-0.1L157.1,1.1L154.1,"
    "1.4L149.5,0.3L148.3,-0.7L151.5,-1.4L153.0,-0.8L154.0,-1.5L156.6,-1.0ZM182.8,-1.3L179.2,-0.0L"
    "178.1,-0.6L178.6,-1.3L176.4,-1.4L179.9,-1.8L180.1,-1.2L181.7,-2.2L183.2,-1.6L182.8,-1.3ZM232"
    ".6,2.6L230.4,2.8L227.5,2.2L225.8,1.3L225.0,-0.3L223.7,-0.8L226.3,-2.4L228.5,-3.0L232.8,0.5L2"
    "32.6,2.6ZM41.8,0.8L43.0,1.5L39.8,3.9L38.0,4.1L35.8,3.8L34.7,2.9L35.6,1.4L33.7,1.4L32.6,0.7L3"
    "1.9,-0.4L33.3,-2.1L34.4,-2.3L33.9,-2.9L36.3,-3.0L37.6,-1.7L41.0,-0.7L41.8,0.8ZM60.7,-7.6L65."
    "6,-7.0L67.5,-6.4L67.5,-5.7L61.6,-3.6L63.8,-3.6L59.7,-1.4L58.0,0.5L52.1,1.6L53.5,1.8L52.8,2.3"
    "L53.7,3.4L49.2,6.3L49.4,6.7L51.1,6.7L51.1,7.2L48.4,8.4L39.3,7.8L39.2,6.8L41.1,6.3L40.6,4.7L4"
    "3.9,5.5L42.5,4.1L40.9,3.7L43.5,2.3L43.8,1.5L42.3,0.6L41.9,-0.6L45.5,-0.2L47.1,-1.1L41.2,-1.2"
    "L39.4,-2.0L37.2,-4.5L41.9,-5.5L43.4,-6.4L45.7,-5.6L46.5,-6.9L49.7,-7.6L60.7,-7.6ZM103.0,-8.6"
    "L109.3,-6.6L107.5,-5.6L98.1,-5.3L98.6,-4.8L102.2,-5.1L105.3,-4.3L107.2,-5.0L108.1,-4.1L107.0"
    ",-2.7L114.5,-4.6L117.6,-4.1L118.2,-3.1L113.4,-0.8L110.2,-0.4L112.5,-0.3L110.5,2.9L110.5,5.3L"
    "111.8,6.7L108.5,7.5L110.4,8.6L110.6,10.4L109.5,10.6L110.8,12.3L108.6,12.5L109.8,13.3L109.4,1"
    "4.0L106.6,14.3L107.8,15.6L107.9,16.4L105.8,15.7L105.3,16.2L108.0,17.8L108.4,19.3L106.6,19.7L"
    "104.5,17.9L104.9,19.1L103.7,20.1L107.8,20.3L102.3,23.3L98.2,23.9L95.7,26.4L90.0,28.5L88.6,31"
    ".7L86.9,33.0L87.3,34.2L86.3,37.0L84.9,37.1L83.4,35.8L81.4,35.8L80.4,35.0L77.9,31.5L77.3,28.9"
    "L75.9,27.4L76.2,26.1L75.5,25.5L76.6,23.5L78.1,22.8L78.7,20.7L76.1,21.8L74.8,21.2L75.1,19.0L7"
    "8.2,19.5L75.5,17.7L73.6,17.5L74.8,15.7L72.1,11.5L70.8,10.7L70.8,9.8L68.1,8.6L60.7,8.7L57.8,6"
    ".7L62.5,5.9L58.1,5.3L55.8,4.4L56.0,3.6L63.6,1.4L64.0,0.6L61.2,-0.3L62.1,-1.2L67.1,-3.1L66.7,"
    "-4.2L69.1,-4.9L75.4,-5.3L76.5,-4.5L79.2,-5.9L85.2,-4.0L82.8,-5.3L82.9,-6.4L86.3,-7.9L89.9,-7"
    ".8L91.2,-8.7L94.8,-9.0L103.0,-8.6Z"
)
MAP_W = 300
M_LON0, M_LAT0, M_LAT1 = -128.0, 80.0, -56.0
M_KX = MAP_W / 294.0
M_KY = M_KX * 180 / math.pi


def miller(lat: float) -> float:
    return 1.25 * math.log(math.tan(math.pi / 4 + 0.4 * math.radians(lat)))


MAP_H = round((miller(M_LAT0) - miller(M_LAT1)) * M_KY, 1)


def mxy(lon: float, lat: float) -> tuple[float, float]:
    return (lon - M_LON0) * M_KX, (miller(M_LAT0) - miller(lat)) * M_KY


# (story id, lon, lat, badge dx, badge dy)
PINS = [
    (1, 114.06, 22.54, 13, 6),
    (2, 49.6, 27.6, 14, -2),
    (4, 31.0, 49.0, 9, -13),
    (5, -74.0, 40.7, 14, -9),
    (6, 85.8, 20.3, -4, 15),
    (7, 30.2, 13.2, -8, 14),
    (8, -0.1, 51.5, -12, -11),
    (9, 34.4, 31.4, -14, 5),
    (10, -77.0, 38.9, 6, 15),
    (11, 151.2, -33.9, -15, -4),
    (12, 90.3, 23.9, 6, -14),
]


def world_map() -> str:
    color = {c[0]: rc(c[1]) for c in CARDS}
    b = [f'<rect width="{MAP_W}" height="{MAP_H}" fill="#DCE8F3"/>']
    for lon in range(-120, 166, 30):
        x, _ = mxy(lon, 0)
        b.append(f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{MAP_H}" stroke="#B9CDE0" stroke-width="0.5"/>')
    for lat in (60, 30, 0, -30):
        _, y = mxy(0, lat)
        dash = "" if lat == 0 else ' stroke-dasharray="2 2"'
        b.append(f'<line x1="0" y1="{y:.1f}" x2="{MAP_W}" y2="{y:.1f}" stroke="#B9CDE0" '
                 f'stroke-width="{0.8 if lat == 0 else 0.5}"{dash}/>')
    b.append(f'<path d="{WORLD_PATH}" fill="#EFE7D6" stroke="#8C7F66" stroke-width="0.5" '
             f'stroke-linejoin="round"/>')
    for sid, lon, lat, dx, dy in PINS:
        x, y = mxy(lon, lat)
        bx, by = x + dx, y + dy
        c = color[sid]
        b.append(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{c}" stroke-width="1.1"/>')
        b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.1" fill="{c}" stroke="#fff" stroke-width="0.8"/>')
        b.append(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="6.6" fill="{c}" stroke="#fff" stroke-width="1.2"/>')
        b.append(lab(bx, by + 3.3, str(sid), size=9, color="#fff", anchor="middle", ls=0))
    # 3: Voyager 1 is off the map, in deep space
    c3 = color[3]
    b.append(f'<path d="M{MAP_W - 70},18 L{MAP_W - 14},8" stroke="{c3}" stroke-width="1.4" '
             f'stroke-dasharray="3 2" marker-end="url(#mah)"/>')
    b.append(f'<circle cx="{MAP_W - 80}" cy="20" r="6.6" fill="{c3}" stroke="#fff" stroke-width="1.2"/>')
    b.append(lab(MAP_W - 80, 23.3, "3", size=9, color="#fff", anchor="middle", ls=0))
    b.append(lab(MAP_W - 70, 32, "VOYAGER 1 \u00b7 DEEP SPACE", size=6.8, color=c3, ls=0.6,
                 halo="#DCE8F3", anchor="middle"))
    defs = (f'<marker id="mah" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" '
            f'orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="{c3}"/></marker>')
    return (f'<svg class="map" width="{MAP_W}" height="{MAP_H}" viewBox="0 0 {MAP_W} {MAP_H}" '
            f'xmlns="http://www.w3.org/2000/svg"><defs>{defs}</defs>{"".join(b)}</svg>')


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #
CSS = r"""
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 1024px; height: 1024px; overflow: hidden; }
body { background: %(paper)s; color: %(ink)s; font-family: 'Lato', sans-serif;
       -webkit-font-smoothing: antialiased; position: relative; }
.band { position: absolute; left: 12px; width: 1000px; }

/* ---------- header ---------- */
#date { position: absolute; left: 12px; top: 5px; width: 738px; height: 62px;
        font: 700 %(datesize)spx/62px 'Liberation Sans Narrow', 'Nimbus Sans Narrow', sans-serif;
        letter-spacing: -0.5px; white-space: nowrap; color: %(ink)s; }
#datebox { position: absolute; left: 760px; top: 8px; width: 252px; height: 58px;
           background: %(ink)s; color: #fff; padding: 5px 10px 0; }
#datebox .big { font: 900 22px/24px 'Lato'; letter-spacing: 0.6px; white-space: nowrap; }
#datebox .big em { font-style: normal; color: #FCD34D; }
#datebox .sub { font: 900 8.6px/13px 'Lato'; letter-spacing: 0.9px; color: #E5E7EB; white-space: nowrap; }
#datebox .mast { font: 700 8px/11px 'Lato'; letter-spacing: 2px; color: #9CA3AF; white-space: nowrap; }
#rbar { top: 71px; height: 15px; display: flex; gap: 2px; }
#rbar div { color: #fff; font: 900 8.4px/15px 'Lato'; letter-spacing: 0.7px; text-align: center;
            white-space: nowrap; overflow: hidden; }
#nums { top: 89px; height: 24px; display: flex; border-top: 2px solid %(ink)s;
        border-bottom: 1px solid %(ink)s; align-items: center; }
#nums .tab { background: #B91C1C; color: #fff; font: 900 8.6px/11px 'Lato'; letter-spacing: 1px;
             height: 100%%; padding: 1px 8px 0; display: flex; flex-direction: column;
             justify-content: center; white-space: nowrap; }
#nums .cell { flex: 1 1 0; display: flex; align-items: baseline; gap: 5px; padding: 0 7px;
              border-left: 1px solid %(hair)s; white-space: nowrap; overflow: hidden; height: 100%%;
              align-items: center; }
#nums .cell:first-of-type { border-left: 0; }
#nums b { font: 900 15px/1 'Lato'; color: %(ink)s; letter-spacing: -0.2px; }
#nums span { font: 700 8.6px/1 'Lato'; color: %(muted)s; }

/* ---------- gallery ---------- */
.row { display: flex; gap: 8px; }
.card { flex: 1 1 0; min-width: 0; background: %(card)s; border: 1px solid %(hair)s;
        border-top: 3px solid var(--c); display: flex; flex-direction: column; overflow: hidden; }
.art { flex: none; overflow: hidden; line-height: 0; }
.art svg { width: 100%%; height: 100%%; display: block; }
.tx { flex: 1 1 auto; padding: 5px 8px 0; overflow: hidden; }
.kick { display: flex; align-items: center; gap: 5px; height: 15px; white-space: nowrap; }
.kick .n { flex: none; width: 15px; height: 15px; border-radius: 50%%; background: var(--c); color: #fff;
           font: 900 9px/15px 'Lato'; text-align: center; }
.kick .k { font: 900 8.6px/15px 'Lato'; letter-spacing: 1px; text-transform: uppercase; color: var(--c); }
.card h3 { font-weight: 900; color: %(ink)s; letter-spacing: -0.1px; margin-top: 2px; }
.card p { color: %(slate)s; margin-top: 2px; }
.src { color: #6B7280; font-weight: 700; font-size: 0.9em; white-space: nowrap; }
.r1 .art { height: 118px; } .r1 h3 { font-size: 15.5px; line-height: 18px; }
.r1 p { font-size: 11px; line-height: 13.6px; }
.r2 .art { height: 90px; } .r2 h3 { font-size: 13px; line-height: 15px; }
.r2 p { font-size: 10.2px; line-height: 12.6px; }
.r3 .art { height: 76px; } .r3 h3 { font-size: 12.6px; line-height: 14.6px; }
.r3 p { font-size: 10.3px; line-height: 12.6px; }
.r3 .tx { padding: 4px 7px 0; }

/* ---------- lower band ---------- */
.ph { font: 900 9.6px/16px 'Lato'; letter-spacing: 1.4px; color: %(ink)s; border-bottom: 2px solid %(ink)s;
      white-space: nowrap; display: flex; justify-content: space-between; }
.ph span { color: %(muted)s; font-weight: 700; letter-spacing: 0.8px; }
#mapcol { position: absolute; left: 12px; width: 305px; }
#mapcol .map { display: block; margin: 5px 0 0 2px; border: 1px solid %(hair)s; }
#legend { display: grid; grid-template-columns: 1fr 1fr; column-gap: 10px; row-gap: 2px; margin-top: 6px; }
#legend div { display: flex; align-items: center; gap: 5px; font: 700 9.6px/15px 'Lato';
              color: %(ink)s; white-space: nowrap; }
#legend i { flex: none; width: 11px; height: 11px; background: var(--c); }
#legend b { color: var(--c); font-weight: 900; margin-left: auto; }
#digest { position: absolute; left: 329px; width: 683px; }
#dcols { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); column-gap: 16px; margin-top: 4px; }
.dl { display: flex; align-items: center; gap: 6px; height: 17.4px; white-space: nowrap; overflow: hidden;
      border-bottom: 1px dotted %(hair)s; }
.dl .n { flex: none; width: 18px; height: 13px; background: var(--c); color: #fff;
         font: 900 8.6px/13px 'Lato'; text-align: center; border-radius: 2px; }
.dl .pl { flex: none; font: 900 9px/1 'Lato'; letter-spacing: 0.6px; text-transform: uppercase; color: var(--c); }
.dl .f { font: 400 11px/13px 'Lato'; color: %(ink)s; overflow: hidden; }

/* ---------- footer ---------- */
#foot { top: 990px; height: 32px; border-top: 2px solid %(ink)s; padding-top: 3px; }
#foot div { white-space: nowrap; overflow: hidden; font: 700 8.6px/13.5px 'Lato'; color: %(slate)s; }
#foot .dc b { background: #047857; color: #fff; padding: 0 4px; letter-spacing: 0.8px; margin-right: 4px;
              font-weight: 900; }
#foot .so { color: %(muted)s; font-weight: 400; }
"""

ROW_TOPS = {1: (118, 212), 2: (336, 180), 3: (522, 172)}
LOWER_TOP = 702


def card_html(card, row) -> str:
    sid, region, art, kicker, title, caption, source = card
    return (f'<article class="card fit" data-s="{sid}" style="--c:{rc(region)}">'
            f'<div class="art">{ART[art]()}</div>'
            f'<div class="tx fit">'
            f'<div class="kick t"><span class="n">{sid}</span><span class="k">{esc(kicker)}</span></div>'
            f'<h3 class="t">{esc(title)}</h3>'
            f'<p class="t">{esc(caption)} <span class="src">[{esc(source)}]</span></p>'
            f'</div></article>')


def build_html(datesize: float = 55) -> str:
    counts = region_counts()
    total = sum(counts.values())
    p = []
    p.append(f'<div id="date" class="t fit">WEDNESDAY, 18 NOVEMBER 2026</div>')
    p.append('<div id="datebox" class="fit">'
             '<div class="big t">NOV 18 <em>\u00b7</em> WED 2026</div>'
             f'<div class="sub t">{total} STORIES \u00b7 {len(REGIONS)} REGIONS \u00b7 {len(CARDS)} ILLUSTRATED</div>'
             '<div class="mast t">THE WORLD LEDGER \u00b7 ONE DAY, ONE PAGE</div></div>')
    segs = "".join(
        f'<div class="t" style="flex:{counts[k] + 1.6:g} 1 0;background:{rc(k)}">'
        f'{esc(REGIONS[k][0].upper())} {counts[k]}</div>' for k in REGION_ORDER)
    p.append(f'<div id="rbar" class="band">{segs}</div>')
    cells = "".join(f'<div class="cell fit t"><b>{esc(n)}</b><span>{esc(lbl)}</span></div>'
                    for n, lbl in NUMBERS)
    p.append(f'<div id="nums" class="band"><div class="tab t">DAY IN<br>NUMBERS</div>{cells}</div>')

    rows = {1: CARDS[0:3], 2: CARDS[3:7], 3: CARDS[7:12]}
    for r, cards in rows.items():
        top, height = ROW_TOPS[r]
        p.append(f'<section class="band row r{r}" style="top:{top}px;height:{height}px">'
                 + "".join(card_html(c, r) for c in cards) + '</section>')

    legend = "".join(
        f'<div class="t" style="--c:{rc(k)}"><i></i>{esc(REGIONS[k][0])}<b>{counts[k]}</b></div>'
        for k in REGION_ORDER)
    p.append(f'<section id="mapcol" style="top:{LOWER_TOP}px">'
             f'<h2 class="ph t">WORLD LOCATOR<span>PINS 1\u201312 = CARDS</span></h2>'
             f'{world_map()}<div id="legend">{legend}'
             f'<div class="t" style="--c:{INK}"><i></i>All stories<b>{total}</b></div></div></section>')

    lines = []
    for i, (region, place, fact) in enumerate(DIGEST):
        sid = 13 + i
        lines.append(f'<div class="dl fit" data-s="{sid}" style="--c:{rc(region)}">'
                     f'<span class="n t">{sid}</span><span class="pl t">{esc(place)}</span>'
                     f'<span class="f t fit">{esc(fact)}</span></div>')
    half = (len(lines) + 1) // 2
    p.append(f'<section id="digest" style="top:{LOWER_TOP}px">'
             f'<h2 class="ph t">WORLD DIGEST \u00b7 30 MORE DISPATCHES<span>ALL DATED WEDNESDAY 18 NOVEMBER 2026</span></h2>'
             f'<div id="dcols"><div>{"".join(lines[:half])}</div><div>{"".join(lines[half:])}</div></div>'
             f'</section>')

    p.append(f'<footer id="foot" class="band">'
             f'<div class="dc t fit"><b>DATE CHECK</b>{esc(DATE_CHECK)}</div>'
             f'<div class="so t fit">{esc(SOURCES)}</div></footer>')

    css = CSS % dict(paper=PAPER, ink=INK, card=CARD, hair=HAIR, slate=SLATE, muted=MUTED,
                     datesize=f"{datesize:g}")
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<title>Wednesday, 18 November 2026</title>'
            f'<style>{css}</style></head><body>{"".join(p)}</body></html>')


# --------------------------------------------------------------------------- #
# Audit + render
# --------------------------------------------------------------------------- #
AUDIT_JS = r"""
() => {
  const out = {scroll: [document.documentElement.scrollWidth, document.documentElement.scrollHeight],
               clipped: [], overlaps: [], svgOverlaps: [], svgOutside: [], offPage: [], stories: [],
               cardSlack: {}, lowerBottom: {}, dateWidth: 0};
  const tag = e => (e.id ? '#' + e.id : e.className.baseVal !== undefined ? e.tagName : '.' + e.className)
                   + ' "' + e.textContent.trim().slice(0, 38) + '"';
  document.querySelectorAll('.fit').forEach(e => {
    if (e.scrollHeight > e.clientHeight + 0.5 || e.scrollWidth > e.clientWidth + 0.5)
      out.clipped.push(tag(e) + ` ${e.scrollWidth}x${e.scrollHeight} > ${e.clientWidth}x${e.clientHeight}`);
  });
  const textRect = e => { const r = document.createRange(); r.selectNodeContents(e); return r.getBoundingClientRect(); };
  const ts = [...document.querySelectorAll('.t')].map(e => [e, textRect(e)]);
  ts.forEach(([e, r]) => {
    if (r.left < -0.5 || r.top < -0.5 || r.right > 1024.5 || r.bottom > 1024.5) out.offPage.push(tag(e));
  });
  const hit = (a, b, tol) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > tol &&
                              Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > tol;
  for (let i = 0; i < ts.length; i++) for (let j = i + 1; j < ts.length; j++) {
    const [a, ra] = ts[i], [b, rb] = ts[j];
    if (a.contains(b) || b.contains(a)) continue;
    if (hit(ra, rb, 0.5)) out.overlaps.push(tag(a) + ' x ' + tag(b));
  }
  document.querySelectorAll('svg').forEach((s, si) => {
    const sr = s.getBoundingClientRect();
    const ls = [...s.querySelectorAll('text.sl')].map(e => [e, e.getBoundingClientRect()]);
    ls.forEach(([e, r]) => {
      if (r.left < sr.left - 0.5 || r.right > sr.right + 0.5 || r.top < sr.top - 0.5 || r.bottom > sr.bottom + 0.5)
        out.svgOutside.push(`svg${si} "${e.textContent}"`);
    });
    for (let i = 0; i < ls.length; i++) for (let j = i + 1; j < ls.length; j++)
      if (hit(ls[i][1], ls[j][1], 0.5)) out.svgOverlaps.push(`svg${si} "${ls[i][0].textContent}" x "${ls[j][0].textContent}"`);
  });
  document.querySelectorAll('[data-s]').forEach(e => out.stories.push(+e.dataset.s));
  out.stories.sort((a, b) => a - b);
  document.querySelectorAll('.card').forEach(c => {
    const tx = c.querySelector('.tx'), last = tx.lastElementChild;
    out.cardSlack[c.dataset.s] = Math.round(tx.getBoundingClientRect().bottom - textRect(last).bottom);
  });
  ['mapcol', 'digest'].forEach(id => {
    out.lowerBottom[id] = Math.round(document.getElementById(id).getBoundingClientRect().bottom);
  });
  out.dateWidth = Math.round(textRect(document.getElementById('date')).width);
  return out;
}
"""


def render(page_html: str, out_png: Path, dpr: int) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        page_path = Path(tmp) / "page.html"
        page_path.write_text(page_html, encoding="utf-8")
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=CHROME, headless=True,
                args=["--hide-scrollbars", "--font-render-hinting=none", "--disable-lcd-text",
                      "--disable-gpu", "--force-color-profile=srgb"])
            page = browser.new_page(viewport={"width": SIZE, "height": SIZE}, device_scale_factor=dpr)
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
        problems.append(f"stories: expected ids 1..42 once each, got {audit['stories']}")
    for col, bottom in audit["lowerBottom"].items():
        if bottom > 988:
            problems.append(f"{col} runs into the footer (bottom {bottom}px)")
    return problems


def encode(img: Image.Image, fmt: str) -> bytes:
    buf = io.BytesIO()
    if fmt == "jpeg":
        img.save(buf, format="JPEG", quality=94, subsampling=0, optimize=True)
    else:
        img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dpr", type=int, default=2, help="device pixel ratio before downsampling")
    ap.add_argument("--format", choices=("jpeg", "png"), default="jpeg",
                    help="container written to entry.png (default: 4:4:4 JPEG q94)")
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
    print(f"stories on page: {len(audit['stories'])}; date banner width {audit['dateWidth']}px")
    print("card text slack (px):", audit["cardSlack"])
    print("lower band bottoms (px):", audit["lowerBottom"])
    for p in problems:
        print("AUDIT:", p)
    if problems and not args.force:
        print("audit failed; entry.png not written", file=sys.stderr)
        return 1

    data = encode(img, args.format)
    if len(data) > MAX_BYTES:
        print(f"encoded image is {len(data)} bytes, over 1 MiB", file=sys.stderr)
        return 1
    args.out.write_bytes(data)
    print(f"{args.out.name}: {img.size[0]}x{img.size[1]} {args.format.upper()} {len(data)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
