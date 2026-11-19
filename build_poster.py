#!/usr/bin/env python3
"""Build entry.png: a 1024x1024 pictorial front page for Wednesday 18 Nov 2026.

Every panel is a full-bleed illustrated scene drawn as inline SVG (layered
land/sea, multi-stop lighting gradients, engraved hatching, lit windows, glow
and vignette), set in an editorial grid with a serif masthead and a colour-coded
regional rail. The page is rendered in headless Chrome through Playwright, then
encoded as a 4:4:4 JPEG named entry.png.

The build audits the layout (overflow, clipped SVG, line counts, text overlap),
the pixels (per-scene detail energy, tonal range, dead-void grid, WCAG contrast
of every text block) and the thumbnail (300 px OCR), and writes a 300 px preview
for inspection.

Build-time only. The shipped entrypoint (main.py) is standard-library Python.
"""

from __future__ import annotations

import argparse
import math
import random
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
CHROME = "/usr/bin/google-chrome"
SIZE = 1024

# --------------------------------------------------------------------------- #
# Palette and grid
# --------------------------------------------------------------------------- #
PAPER = "#F4EEDF"
INK = "#161A1E"
INK_SOFT = "#463F33"
CRIMSON = "#A32020"
CRIMSON_DARK = "#7C1414"
NAVY = "#0B1B28"
GOLD = "#D9A94A"
HAIR = "#D6C7AC"

REGION = {
    "me": "#A2262B",
    "am": "#1F4E79",
    "ap": "#0E6B5E",
    "eu": "#5A3A78",
    "gs": "#4C6B2F",
    "te": "#33414B",
}

PAD_X = 16
INNER = SIZE - 2 * PAD_X          # 992
GAP = 7
HERO_W = 648
IPO_W = INNER - HERO_W - GAP      # 337
R2_W = (INNER - 2 * GAP) / 3      # 326.0
R3_W = (INNER - 3 * GAP) / 4      # 243.5
R1_H = 328
ART1_H = 186
R2_H = 212
ART2_H = 100
R3_H = 184
ART3_H = 86
WIRE_H = 76


# --------------------------------------------------------------------------- #
# SVG helpers
# --------------------------------------------------------------------------- #
def _stops(stops) -> str:
    out = []
    for stop in stops:
        off, color = stop[0], stop[1]
        alpha = stop[2] if len(stop) > 2 else None
        tail = f' stop-opacity="{alpha}"' if alpha is not None else ""
        out.append(f'<stop offset="{off}" stop-color="{color}"{tail}/>')
    return "".join(out)


def lg(defs, name, stops, x1=0, y1=0, x2=0, y2=1) -> str:
    defs.append(
        f'<linearGradient id="{name}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">'
        f"{_stops(stops)}</linearGradient>"
    )
    return f"url(#{name})"


def rg(defs, name, stops, cx=0.5, cy=0.5, r=0.5) -> str:
    defs.append(
        f'<radialGradient id="{name}" cx="{cx}" cy="{cy}" r="{r}">'
        f"{_stops(stops)}</radialGradient>"
    )
    return f"url(#{name})"


def blur(defs, name, dev) -> str:
    defs.append(
        f'<filter id="{name}" x="-60%" y="-60%" width="220%" height="220%">'
        f'<feGaussianBlur stdDeviation="{dev}"/></filter>'
    )
    return f"url(#{name})"


def star_path(cx, cy, r, waist=0.24):
    w = r * waist
    return (
        f"M{cx},{cy - r} L{cx + w},{cy - w} L{cx + r},{cy} L{cx + w},{cy + w} "
        f"L{cx},{cy + r} L{cx - w},{cy + w} L{cx - r},{cy} L{cx - w},{cy - w} Z"
    )


def burst(cx, cy, r, core="#FFF6DF", halo="#E8452E") -> str:
    """Layered strike burst: soft halo, hard star, hot core."""
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r * 2.6:.1f}" fill="{halo}" opacity="0.22"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r * 1.6:.1f}" fill="{halo}" opacity="0.3"/>'
        f'<path d="{star_path(cx, cy, r)}" fill="{halo}"/>'
        f'<path d="{star_path(cx, cy, r * 0.46)}" fill="{core}"/>'
    )


def hatching(defs, clip_id, path, w, h, step=5.4, color="#6B5426", op=0.1) -> str:
    defs.append(f'<clipPath id="{clip_id}"><path d="{path}"/></clipPath>')
    lines = []
    x = -h
    while x < w:
        lines.append(f'<path d="M{x:.1f},0 L{x + h:.1f},{h}"/>')
        x += step
    return (
        f'<g data-bleed="1" clip-path="url(#{clip_id})" stroke="{color}" '
        f'stroke-width="0.5" opacity="{op}">{"".join(lines)}</g>'
    )


def stars(body, w, n, seed, ymax=None, color="#F6EAD0", op=0.85) -> None:
    rng = random.Random(seed)
    top = ymax if ymax is not None else 0
    for _ in range(n):
        x = rng.uniform(0, w)
        y = rng.uniform(0, top)
        r = rng.uniform(0.35, 1.05)
        body.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" fill="{color}" '
            f'opacity="{rng.uniform(op * 0.3, op):.2f}"/>'
        )


def windows(body, x, y, w, h, seed, color="#F7D08C", p=0.4, maxn=48) -> None:
    """Lit windows scattered on a facade, deterministic."""
    rng = random.Random(seed)
    cw, ch, gx, gy = 2.0, 1.7, 3.2, 3.0
    n = 0
    yy = y + 2.4
    while yy < y + h - 2.4 and n < maxn:
        xx = x + 2.0
        while xx < x + w - 2.0 and n < maxn:
            if rng.random() < p:
                body.append(
                    f'<rect x="{xx:.1f}" y="{yy:.1f}" width="{cw}" '
                    f'height="{ch}" fill="{color}" opacity="{rng.uniform(.35, .95):.2f}"/>'
                )
                n += 1
            xx += gx
        yy += gy


def skyline(body, seed, x0, x1, base, hmin, hmax, fill, wmin=9, wmax=20,
            lit=None, p=0.35, win=True) -> None:
    rng = random.Random(seed)
    x = x0
    while x < x1:
        bw = min(rng.uniform(wmin, wmax), x1 - x)
        bh = rng.uniform(hmin, hmax)
        top = base - bh
        body.append(
            f'<rect x="{x:.1f}" y="{top:.1f}" width="{bw:.1f}" '
            f'height="{bh:.1f}" fill="{fill}"/>'
        )
        if win:
            windows(body, x, top, bw, bh, int(x * 7 + seed), lit or "#F7D08C", p)
        if rng.random() < 0.22 and bw > 12:
            body.append(
                f'<rect x="{x + bw / 2 - 0.5:.1f}" y="{top - rng.uniform(4, 11):.1f}" '
                f'width="1" height="{rng.uniform(4, 11):.1f}" fill="{fill}"/>'
            )
        x += bw + rng.uniform(0.5, 3.0)


def waves(body, w, y0, y1, seed, color="#8FB6CC", n=9, op=0.16) -> None:
    rng = random.Random(seed)
    for _ in range(n):
        y = rng.uniform(y0, y1)
        x = rng.uniform(0, w * 0.4)
        length = rng.uniform(w * 0.18, w * 0.5)
        body.append(
            f'<path d="M{x:.1f},{y:.1f} q{length * 0.25:.1f},-2.2 '
            f'{length * 0.5:.1f},0 t{length * 0.5:.1f},0" fill="none" '
            f'stroke="{color}" stroke-width="{rng.uniform(.5, 1.1):.1f}" '
            f'opacity="{rng.uniform(op * 0.4, op):.2f}"/>'
        )


def frame(w, h, color="#F0C87A", op=0.22) -> str:
    return (f'<rect x="0.5" y="0.5" width="{w - 1}" height="{h - 1}" '
            f'fill="none" stroke="{color}" stroke-width="1" opacity="{op}"/>')


def svg(w, h, label, defs, body, cls="art") -> str:
    return (
        f'<svg class="{cls}" viewBox="0 0 {w} {h}" preserveAspectRatio="none" '
        f'role="img" aria-label="{label}"><defs>{"".join(defs)}</defs>'
        f'{"".join(body)}</svg>'
    )


def label(x, y, text, size=7.4, color="#4A3B22", ls=1.9, weight=700,
          anchor="start", family="Lato, sans-serif", op=1.0, extra="") -> str:
    return (
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
        f'font-weight="{weight}" letter-spacing="{ls}" fill="{color}" '
        f'text-anchor="{anchor}" opacity="{op}" {extra}>{text}</text>'
    )


# --------------------------------------------------------------------------- #
# 01 · Persian Gulf — the hero strike map
# --------------------------------------------------------------------------- #
IRAN = ("M0,0 H648 V74 L610,78 L575,86 L540,96 L505,94 L470,90 L420,86 "
        "L350,80 L280,74 L210,66 L140,58 L70,50 L0,40 Z")
ARABIA = ("M0,186 V128 L60,132 L120,140 L180,148 L240,156 L300,164 L360,172 "
          "L410,180 L440,186 Z")
MUSANDAM = ("M440,186 L452,170 L472,148 L498,130 L520,118 L540,124 L548,140 "
            "L540,160 L528,178 L520,186 Z")
QATAR = "M296,162 L300,140 L312,134 L323,138 L327,160 L315,168 Z"
QESHM = ("M418,104 L436,98 L456,97 L474,101 L484,107 L466,112 L442,112 "
         "L424,109 Z")


def art_gulf() -> str:
    W, H = HERO_W, ART1_H
    d, b = [], []
    sea = lg(d, "gsea", [(0, "#0E2C40"), (0.42, "#124058"), (1, "#05131E")])
    land = lg(d, "gland", [(0, "#EFDDB6"), (0.42, "#DCC191"), (1, "#A98C5C")],
              0, 0, 0.12, 1)
    land2 = lg(d, "gland2", [(0, "#E0CB9F"), (1, "#9C8052")], 0, 0, 1, 1)
    ember = rg(d, "gember", [(0, "#F2684A", 0.6), (0.4, "#C03526", 0.22),
                             (1, "#C03526", 0)], 0.7, 0.56, 0.5)
    goldg = rg(d, "ggold", [(0, "#F6D293", 0.4), (1, "#F6D293", 0)])
    vig = rg(d, "gvig", [(0.6, "#04101A", 0), (0.86, "#04101A", 0.12), (1, "#04101A", 0.34)])
    coast = blur(d, "gcoast", 2.6)
    glow = blur(d, "gglow", 2.0)

    b.append(f'<rect width="{W}" height="{H}" fill="{sea}"/>')
    b.append(f'<rect width="{W}" height="{H}" fill="{ember}"/>')
    b.append(f'<ellipse cx="516" cy="120" rx="132" ry="66" fill="{goldg}"/>')
    grid = "".join(f'<path d="M{x},0 V{H}"/>' for x in range(0, W + 1, 62))
    grid += "".join(f'<path d="M0,{y} H{W}"/>' for y in range(0, H + 1, 43))
    b.append(f'<g stroke="#8FB6CC" stroke-width="0.5" opacity="0.1">{grid}</g>')
    waves(b, W, 60, H - 14, 11, "#9FC6DC", 12, 0.14)
    waves(b, 300, 88, H - 12, 23, "#9FC6DC", 11, 0.2)
    for cx_, cy_ in ((26, 130), (34, 133), (41, 129), (48, 134), (55, 131),
                     (63, 136), (72, 133), (80, 138)):
        b.append(f'<circle cx="{cx_}" cy="{cy_}" r="1.1" fill="#FFDFA8" opacity="0.75"/>')
    b.append(f'<path d="M18,140 H96" stroke="#F9E0AE" stroke-width="0.7" '
             f'stroke-dasharray="2 3" opacity="0.5"/>')

    for path, cid, seed in ((IRAN, "cpIran", 3), (ARABIA, "cpArab", 5),
                            (MUSANDAM, "cpMus", 7), (QATAR, "cpQat", 9)):
        b.append(f'<path d="{path}" fill="url(#gland)" stroke="#F7D9A0" '
                 f'stroke-width="5" filter="{coast}" opacity="0.35"/>')
        b.append(f'<path d="{path}" fill="url(#gland)" stroke="#F9E0AE" '
                 f'stroke-width="1.4" stroke-linejoin="round"/>')
        b.append(hatching(d, cid, path, W, H, 4.6, "#6B5426", 0.11))
        rng = random.Random(seed)
        ridges = []
        for _ in range(5):
            y0 = rng.uniform(8, H * 0.5)
            ridges.append(f'<path d="M0,{y0:.0f} q{W * 0.3:.0f},{rng.uniform(-7, 7):.0f} '
                          f'{W * 0.62:.0f},{rng.uniform(-6, 9):.0f} '
                          f'T{W},{rng.uniform(-6, 10):.0f}"/>')
        b.append(f'<g data-bleed="1" clip-path="url(#{cid})" fill="none" '
                 f'stroke="#6B5426" stroke-width="0.7" opacity="0.19">'
                 f'{"".join(ridges)}</g>')

    b.append(f'<path d="{QESHM}" fill="url(#gland2)" stroke="#F9E0AE" stroke-width="1.1"/>')
    b.append(f'<path d="M226,150 q8,-7 15,0 q2,5 -5,7 q-9,1 -10,-7 Z" fill="url(#gland2)" '
             f'stroke="#F9E0AE" stroke-width="0.9"/>')

    b.append(f'<path d="M20,132 C150,150 300,158 430,158 C500,158 545,148 596,142" '
             f'fill="none" stroke="#BFE0F0" stroke-width="1" stroke-dasharray="6 6" '
             f'opacity="0.38"/>')
    b.append(label(112, 124, "SHIPPING LANE", 5.0, "#EAF6FF", 1.4, op=0.95,
          extra='transform="rotate(-4 112 124)" stroke="#0B2233" '
                'stroke-width="1.6" stroke-opacity="0.85" paint-order="stroke"'))
    b.append(f'<rect width="{W}" height="{H}" fill="{vig}"/>')

    arc = 'stroke="#F2765F" stroke-width="1.6" fill="none" stroke-dasharray="5 4" opacity="0.92"'
    b.append(f'<g filter="{glow}" opacity="0.6">'
             f'<path d="M436,100 Q340,138 250,148" {arc}/>'
             f'<path d="M436,108 Q300,168 70,140" {arc}/>'
             f'<path d="M460,106 Q520,112 548,124" {arc}/></g>')
    b.append(f'<path d="M436,100 Q340,138 250,148" {arc} marker-end="url(#garw)"/>')
    b.append(f'<path d="M436,108 Q300,168 70,140" {arc} marker-end="url(#garw)"/>')
    b.append(f'<path d="M460,106 Q520,112 548,124" {arc} marker-end="url(#garw)"/>')
    d.append('<marker id="garw" viewBox="0 0 8 8" refX="6.4" refY="4" '
             'markerWidth="5" markerHeight="5" orient="auto">'
             '<path d="M0,0.6 L7.2,4 L0,7.4 Z" fill="#F2765F"/></marker>')

    for gx, gy, ang in ((352, 128, -8), (196, 154, 2), (508, 112, 22)):
        b.append(f'<g transform="translate({gx},{gy}) rotate({ang})" opacity="0.92">'
                 f'<path d="M-6,0 H6 M0,-3.6 V0" stroke="#FBD9C2" stroke-width="1"/>'
                 f'<circle cx="-6" cy="0" r="1.5" fill="none" stroke="#FBD9C2" stroke-width="0.8"/>'
                 f'<circle cx="6" cy="0" r="1.5" fill="none" stroke="#FBD9C2" stroke-width="0.8"/>'
                 f'<rect x="-1.4" y="-1.5" width="2.8" height="3" fill="#FBD9C2"/></g>')

    b.append(f'<circle cx="442" cy="104" r="34" fill="{ember}"/>')
    b.append(f'<g fill="none" stroke="#FF8A6A" stroke-width="1">'
             f'<circle cx="442" cy="104" r="16" opacity="0.75"/>'
             f'<circle cx="442" cy="104" r="23" opacity="0.45"/>'
             f'<circle cx="442" cy="104" r="30" opacity="0.22"/></g>')
    b.append(burst(442, 104, 10.5))
    b.append(label(474, 98, "QESHM", 6.8, "#FFD9C0", 1.4))
    b.append(label(474, 106, "US STRIKE", 5.6, "#FFE6D2", 1.2, op=1.0,
          extra='stroke="#7C1414" stroke-width="1.5" stroke-opacity="0.75" '
                'paint-order="stroke"'))

    b.append(f'<g transform="translate(240,146)">'
             f'<path d="M-7,6 q7,-12 14,0" fill="none" stroke="#F7EBD0" stroke-width="1.4"/>'
             f'<path d="M-4,6 q4,-7 8,0" fill="none" stroke="#F7EBD0" stroke-width="1.2"/>'
             f'<path d="M0,7 V12 M-5,12 H5" stroke="#F7EBD0" stroke-width="1.1"/>'
             f'<circle cx="0" cy="5" r="1.2" fill="#FFE6C0"/></g>')
    b.append(f'<g fill="none" stroke="#F7EBD0" stroke-width="0.6" opacity="0.4">'
             f'<circle cx="240" cy="151" r="13"/><circle cx="240" cy="151" r="21"/></g>')
    b.append(label(214, 172, "BAHRAIN · RADAR", 5.6, "#F7EBD0", 1.1))

    b.append(f'<g transform="translate(54,138)">'
             f'<path d="M-6.5,4.5 L-3,-4.5 L3,-4.5 L6.5,4.5 Z" fill="#F7EBD0" opacity="0.92"/>'
             f'<path d="M-3.6,4.5 V1 H3.6 V4.5" fill="none" stroke="#7C1414" stroke-width="0.9"/>'
             f'<circle cx="0" cy="-6.6" r="2" fill="#F7EBD0"/></g>')
    b.append(label(30, 156, "ALI AL SALEM", 5.6, "#3E3220", 1.1))
    b.append(label(30, 164, "KUWAIT", 5.0, "#F6E7C6", 1.2, op=1.0,
          extra='stroke="#3E3220" stroke-width="1.4" stroke-opacity="0.8" '
                'paint-order="stroke"'))

    b.append(f'<g transform="translate(560,132)">'
             f'<path d="M-12,0 H10 L15,5 H-17 Z" fill="#F4E4C2"/>'
             f'<rect x="-5" y="-4.6" width="12" height="4.6" fill="#D9A94A"/>'
             f'<rect x="-2.6" y="-9" width="6.4" height="4.4" fill="#C0392B"/>'
             f'<path d="M-18,7 H17" stroke="#BFE0F0" stroke-width="0.9" opacity="0.5"/></g>')
    b.append(label(570, 120, "HORMUZ", 5.6, "#F7EBD0", 1.3))
    b.append(label(570, 149, "TANKER", 4.8, "#BFE0F0", 1.1, op=0.7))

    b.append(label(268, 34, "I R A N", 8.6, "#4A3B22", 3.2, op=0.95, extra='stroke="#F9E3B8" stroke-width="1.7" stroke-opacity="0.6" paint-order="stroke"'))
    b.append(label(336, 66, "ZAGROS", 5.0, "#6B5426", 1.7, op=0.55, extra='stroke="#F9E3B8" stroke-width="1.7" stroke-opacity="0.6" paint-order="stroke"'))
    b.append(label(74, 174, "SAUDI ARABIA", 7.4, "#4A3B22", 2.4, op=0.95, extra='stroke="#F9E3B8" stroke-width="1.7" stroke-opacity="0.6" paint-order="stroke"'))
    b.append(label(296, 172, "QATAR", 4.8, "#4A3B22", 1.3, op=0.9, extra='stroke="#F9E3B8" stroke-width="1.7" stroke-opacity="0.6" paint-order="stroke"'))
    b.append(label(368, 182, "UAE", 6.0, "#4A3B22", 2.0, op=0.9, extra='stroke="#F9E3B8" stroke-width="1.7" stroke-opacity="0.6" paint-order="stroke"'))
    b.append(label(492, 180, "OMAN", 5.4, "#4A3B22", 1.8, op=0.9, extra='stroke="#F9E3B8" stroke-width="1.7" stroke-opacity="0.6" paint-order="stroke"'))
    b.append(label(196, 126, "PERSIAN GULF", 6.8, "#A8CFE2", 2.6, op=0.7,
                   extra='transform="rotate(-6 196 126)"'))
    b.append(label(622, 178, "GULF OF OMAN", 5.0, "#A8CFE2", 1.8, op=0.55,
                   extra='transform="rotate(-80 622 178)"'))

    b.append(f'<g stroke="#F0D3A0" stroke-width="0.9" opacity="0.7" fill="none">'
             f'<path d="M18,178 H74 M18,174 V182 M46,175 V181 M74,174 V182"/></g>')
    b.append(label(80, 181, "200 KM", 5.0, "#F0D3A0", 1.1, op=0.7))
    b.append(f'<g transform="translate(614,34)" opacity="0.9">'
             f'<path d="M0,-12 L3.4,0 L0,12 L-3.4,0 Z" fill="#4A3B22"/>'
             f'<path d="M0,-12 L3.4,0 L0,0 Z" fill="#A32020"/>'
             f'<circle cx="0" cy="0" r="1.4" fill="#4A3B22"/></g>')
    b.append(label(614, 17, "N", 5.8, "#4A3B22", 0, 700, "middle", op=0.9))

    b.append(frame(W, H))
    return svg(W, H, "Map of the Persian Gulf: a US strike on Qeshm Island, "
                     "drone and missile arcs to Bahrain, Kuwait and Hormuz "
                     "shipping.", d, b)


# --------------------------------------------------------------------------- #
# 02 · Anthropic IPO — the Nasdaq night board
# --------------------------------------------------------------------------- #
def art_ipo() -> str:
    W, H = IPO_W, ART1_H
    d, b = [], []
    sky = lg(d, "isky", [(0, "#050B14"), (0.38, "#0F1D30"), (0.68, "#2C2136"),
                         (1, "#54222A")])
    tower = lg(d, "itow", [(0, "#1E3348"), (1, "#0A1522")])
    board = lg(d, "iboard", [(0, "#3B0F16"), (0.5, "#8E1D1F"), (1, "#C9993F")], 0, 0, 1, 1)
    halo = rg(d, "ihalo", [(0, "#F6C878", 0.42), (0.45, "#E08A3A", 0.14),
                           (1, "#E08A3A", 0)])
    cloud = lg(d, "icloud", [(0, "#8A5A50", 0.32), (1, "#8A5A50", 0)], 0, 1, 0, 0)
    vig = rg(d, "ivig", [(0.6, "#040A12", 0), (0.86, "#040A12", 0.12), (1, "#040A12", 0.34)])

    b.append(f'<rect width="{W}" height="{H}" fill="{sky}"/>')
    stars(b, W, 40, 21, 92)
    b.append(f'<ellipse cx="172" cy="76" rx="132" ry="76" fill="{halo}"/>')

    # stacked cloud bands for depth
    for i, (cy, rx, ry, op) in enumerate(((112, 168, 18, 0.30),
                                          (132, 168, 14, 0.22),
                                          (150, 160, 10, 0.16))):
        b.append(f'<ellipse cx="{W / 2}" cy="{cy}" rx="{rx}" ry="{ry}" '
                 f'fill="{cloud}" opacity="{op}"/>')
        b.append(f'<path d="M0,{cy + ry * 0.5:.0f} H{W}" stroke="#F0B47A" '
                 f'stroke-width="0.7" opacity="{op * 0.7:.2f}"/>')

    skyline(b, 41, 0, W, 158, 18, 52, "#22384E", 9, 18, "#F2C079", 0.18)
    skyline(b, 43, 0, W, 172, 26, 74, "#122336", 10, 22, "#F7D08C", 0.26)
    b.append(f'<rect width="{W}" height="{H}" fill="{vig}"/>')

    # hero tower with the LED board
    b.append(f'<rect x="126" y="40" width="82" height="132" fill="{tower}"/>')
    b.append(f'<path d="M126,40 L167,18 L208,40 Z" fill="#1A2E42"/>')
    b.append(f'<path d="M167,20 V4" stroke="#1A2E42" stroke-width="1.8"/>')
    b.append(f'<circle cx="167" cy="3.4" r="1.6" fill="#FF9A6A"/>')
    b.append(f'<rect x="134" y="50" width="66" height="76" fill="{board}"/>')
    b.append(f'<rect x="134" y="50" width="66" height="76" fill="none" '
             f'stroke="#F7D08C" stroke-width="0.8" opacity="0.65"/>')
    b.append(label(167, 61, "ANTHROPIC", 5.0, "#FFE9C8", 0.6, 700, "middle"))
    b.append(f'<text x="167" y="89" font-family="Noto Serif, Georgia, serif" '
             f'font-size="27" font-weight="700" fill="#FFF7E6" text-anchor="middle">$83</text>')
    b.append(label(167, 98, "PER SHARE", 4.2, "#FFD9A8", 1.0, 700, "middle"))
    b.append(f'<path d="M139,104 H196" stroke="#FFE9C8" stroke-width="0.6" opacity="0.5"/>')
    b.append(f'<text x="167" y="118" font-family="Noto Serif, Georgia, serif" '
             f'font-size="14" font-weight="700" fill="#FFE9C8" text-anchor="middle">$1.5tn</text>')
    b.append(label(167, 124, "VALUATION", 3.4, "#FFC98F", 0.7, 700, "middle"))
    windows(b, 128, 130, 78, 42, 77, "#F7D08C", 0.45, 30)

    b.append('<rect x="2" y="64" width="38" height="122" fill="#122436"/>')
    b.append('<path d="M21,64 V50" stroke="#122436" stroke-width="1.6"/>')
    b.append('<circle cx="21" cy="49" r="1.4" fill="#FF9A6A"/>')
    windows(b, 2, 64, 38, 118, 91, "#F7D08C", 0.5, 34)

    # the chart across the sky
    b.append(f'<path d="M6,158 C60,154 92,132 128,116 C172,96 240,62 328,24" '
             f'fill="none" stroke="#F2C46A" stroke-width="8" opacity="0.14"/>')
    b.append(f'<path d="M6,158 C60,154 92,132 128,116 C172,96 240,62 328,24" '
             f'fill="none" stroke="#F6D08A" stroke-width="1.8"/>')
    rng = random.Random(5)
    for i in range(6):
        x = 22 + i * 52
        top = 150 - i * 18 + rng.uniform(-6, 6)
        hgt = 8 + (i % 3) * 3
        b.append(f'<path d="M{x},{top - 5:.0f} V{top + hgt + 5:.0f}" stroke="#EFE2C6" '
                 f'stroke-width="1" opacity="0.42"/>')
        b.append(f'<rect x="{x - 3.2}" y="{top:.0f}" width="6.4" height="{hgt}" '
                 f'fill="{"#E0493B" if i % 2 == 0 else "#6FA9C7"}" opacity="0.85"/>')

    skyline(b, 45, 0, W, 186, 10, 30, "#070F19", 8, 16, "#FFC98F", 0.3)
    b.append(f'<rect x="0" y="0" width="{W}" height="16" fill="#8E1D1F"/>')
    b.append(label(7, 11, "NASDAQ · ANTHROPIC · $83.00 · $1.5TN · 18 NOV 2026",
                   6.2, "#FFE7C4", 0.9, 700, op=0.95))
    b.append(f'<rect x="0" y="16" width="{W}" height="1" fill="#D9A94A" opacity="0.5"/>')

    b.append(frame(W, H, "#D9A94A", 0.3))
    return svg(W, H, "A night-time Nasdaq board showing Anthropic's $83 offer price "
                     "and $1.5 trillion valuation above a rising candlestick chart.",
               d, b)


# --------------------------------------------------------------------------- #
# 03 · Shenzhen APEC
# --------------------------------------------------------------------------- #
def _flag_us(x, y, w, h):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#F7F2E4"/>']
    stripes = 6
    sh = h / stripes
    for i in range(stripes):
        if i % 2 == 0:
            out.append(f'<rect x="{x}" y="{y + i * sh:.1f}" width="{w}" '
                       f'height="{sh:.1f}" fill="#B22234"/>')
    out.append(f'<rect x="{x}" y="{y}" width="{w * 0.45:.1f}" height="{h * 0.52:.1f}" '
               f'fill="#1F3A6E"/>')
    return "".join(out)


def _flag_cn(x, y, w, h):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#C8102E"/>'
            f'<path d="{star_path(x + w * 0.24, y + h * 0.32, h * 0.2)}" fill="#F5D34E"/>')


def _flag_ru(x, y, w, h):
    t = h / 3
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{t:.1f}" fill="#F4F1E8"/>'
            f'<rect x="{x}" y="{y + t:.1f}" width="{w}" height="{t:.1f}" fill="#1F4E79"/>'
            f'<rect x="{x}" y="{y + 2 * t:.1f}" width="{w}" height="{t:.1f}" fill="#C8102E"/>')


def art_apec() -> str:
    W, H = R2_W, ART2_H
    d, b = [], []
    sky = lg(d, "asky", [(0, "#0B1E30"), (0.4, "#204458"), (0.7, "#7A5A4A"),
                         (1, "#E0954E")])
    water = lg(d, "awater", [(0, "#15384D"), (1, "#061520")])
    sun = rg(d, "asun", [(0, "#FFE2AF", 0.98), (0.26, "#F2A85E", 0.6),
                         (1, "#E08A4A", 0)])
    vig = rg(d, "avig", [(0.6, "#040E16", 0), (0.86, "#040E16", 0.12), (1, "#040E16", 0.34)])

    b.append(f'<rect width="{W}" height="{H}" fill="{sky}"/>')
    b.append(f'<circle cx="238" cy="40" r="38" fill="{sun}"/>')
    b.append(f'<circle cx="238" cy="40" r="10" fill="#FFEDCB" opacity="0.92"/>')
    for cy_, rx_, ry_, op in ((30, 158, 8, 0.30), (50, 158, 7, 0.22), (66, 140, 5, 0.18)):
        b.append(f'<ellipse cx="{W / 2}" cy="{cy_}" rx="{rx_}" ry="{ry_}" '
                 f'fill="#5A3A38" opacity="{op}"/>')
        b.append(f'<path d="M0,{cy_ + ry_ * 0.7:.0f} Q{W * 0.4},{cy_ + ry_ * 0.7 - 2} {W},'
                 f'{cy_ + ry_ * 0.7:.0f}" fill="none" stroke="#F2A85E" stroke-width="0.8" '
                 f'opacity="{op * 0.8:.2f}"/>')
    for i, (x0, x1) in enumerate(((200, 158), (226, 214), (252, 282))):
        b.append(f'<path d="M238,46 L{x1},0 L{x1 + 13},0 L238,46 Z" fill="#FFD9A0" '
                 f'opacity="{0.07 - i * 0.015:.2f}"/>')

    skyline(b, 31, 0, W, 88, 14, 38, "#2E4E63", 8, 15, "#F2C079", 0.12)
    skyline(b, 33, 0, W, 93, 12, 50, "#1B3648", 9, 17, "#F7D08C", 0.2)
    b.append(f'<path d="M104,92 L107,30 L112,14 L117,30 L120,92 Z" fill="#0E2231"/>')
    b.append(f'<path d="M112,14 V6" stroke="#0E2231" stroke-width="1.2"/>')
    b.append(f'<circle cx="112" cy="5.4" r="1.6" fill="#FF9A6A"/>')
    skyline(b, 35, 0, W, 96, 10, 32, "#0A1A26", 7, 13, "#FFC98F", 0.26)

    # bay
    b.append(f'<rect x="0" y="94" width="{W}" height="{H - 94}" fill="{water}"/>')
    for i in range(3):
        y = 96.5 + i * 1.8
        b.append(f'<path d="M0,{y:.1f} H{W}" stroke="#6FA0BA" stroke-width="0.7" '
                 f'opacity="{0.22 - i * 0.05:.2f}"/>')
    b.append(f'<path d="M214,94 h46 v{H - 94} h-46 Z" fill="#F2B96E" opacity="0.22"/>')
    b.append(f'<path d="M0,94 H{W}" stroke="#FFD9A0" stroke-width="1" opacity="0.55"/>')
    b.append(f'<rect width="{W}" height="{H}" fill="{vig}"/>')

    b.append(f'<path d="M252,94 q22,-24 44,0 Z" fill="#0A1A26"/>')
    b.append(f'<path d="M252,94 q22,-24 44,0" fill="none" stroke="#F2C079" '
             f'stroke-width="0.9" opacity="0.55"/>')
    b.append(label(258, 90, "APEC 2026", 4.8, "#FFD9A0", 0.9, 700, op=0.9))

    d.append('<filter id="aflagsh" x="-25%" y="-25%" width="150%" height="150%">'
             '<feDropShadow dx="1.2" dy="1.8" stdDeviation="1.2" flood-color="#04101A" '
             'flood-opacity="0.55"/></filter>')
    for x, fn, lab, col in ((12, _flag_us, "US", "#F7F2E4"),
                            (58, _flag_cn, "CHINA", "#FFD9A0"),
                            (116, _flag_ru, "RUSSIA", "#F0D3A0")):
        b.append(f'<path d="M{x + 1},7 V{H - 2}" stroke="#2A2018" stroke-width="1.5"/>')
        b.append(f'<g filter="url(#aflagsh)">{fn(x + 2, 10, 38, 23)}</g>')
        b.append(f'<rect x="{x + 2}" y="10" width="38" height="23" fill="none" '
                 f'stroke="#1A1208" stroke-width="0.5" opacity="0.5"/>')
        b.append(label(x + 2, 41, lab, 4.8, col, 1.0, 700))

    b.append(frame(W, H))
    return svg(W, H, "Shenzhen at dusk: the APEC summit skyline and bay with the "
                     "flags of the United States, China and Russia on tall poles.",
               d, b)


# --------------------------------------------------------------------------- #
# 04 · COP31 Antalya
# --------------------------------------------------------------------------- #
def art_cop31() -> str:
    W, H = R2_W, ART2_H
    d, b = [], []
    sky = lg(d, "csky", [(0, "#F7E5C4"), (0.42, "#F1C48C"), (1, "#C4643C")])
    earth = lg(d, "cearth", [(0, "#B2764A"), (1, "#7C4A2C")])
    sun = rg(d, "csun", [(0, "#FFF8E2", 0.98), (0.28, "#FFD89A", 0.72),
                         (1, "#F2A85E", 0)])
    vig = rg(d, "cvig", [(0.6, "#3A1A0E", 0), (0.86, "#3A1A0E", 0.12), (1, "#3A1A0E", 0.34)])
    shade = rg(d, "cglobe", [(0, "#9CC2B2"), (1, "#2F5A56")], 0.34, 0.32, 0.74)

    b.append(f'<rect width="{W}" height="{H}" fill="{sky}"/>')
    b.append(f'<circle cx="64" cy="48" r="44" fill="{sun}"/>')
    b.append(f'<g fill="none" stroke="#FFE7BE" stroke-width="0.8" opacity="0.4">'
             f'<circle cx="64" cy="48" r="22"/><circle cx="64" cy="48" r="29"/></g>')
    b.append(f'<path d="M0,66 L28,50 L52,60 L78,42 L104,58 L128,46 L156,62 L182,50 '
             f'L206,64 L232,52 L262,66 L290,56 L326,68 V{H} H0 Z" fill="#C98F62" '
             f'opacity="0.55"/>')
    b.append(f'<path d="M0,78 L36,64 L70,74 L104,60 L140,76 L176,64 L212,78 L250,66 '
             f'L286,78 L326,70 V{H} H0 Z" fill="#A56442" opacity="0.72"/>')
    for i, hy in enumerate((22, 32, 44, 56)):
        b.append(f'<path d="M0,{hy} Q{W * 0.3},{hy - 4} {W * 0.55},{hy} '
                 f'T{W},{hy - 2}" fill="none" stroke="#FFF0CE" stroke-width="1.4" '
                 f'opacity="{0.28 - i * 0.05:.2f}"/>')
    b.append(f'<rect x="0" y="86" width="{W}" height="{H - 86}" fill="{earth}"/>')
    rng = random.Random(12)
    cracks = []
    for _ in range(18):
        x = rng.uniform(4, W - 6)
        y = rng.uniform(88, H - 2)
        cracks.append(f'<path d="M{x:.0f},{y:.0f} l{rng.uniform(-9, 9):.0f},'
                      f'{rng.uniform(0.8, 3):.0f} l{rng.uniform(-7, 7):.0f},'
                      f'{rng.uniform(0.8, 3):.0f}"/>')
    b.append(f'<g stroke="#5B2F1B" stroke-width="0.7" fill="none" opacity="0.55">'
             f'{"".join(cracks)}</g>')
    b.append(f'<rect width="{W}" height="{H}" fill="{vig}"/>')

    b.append(f'<circle cx="96" cy="52" r="30" fill="{shade}"/>')
    b.append(f'<g fill="none" stroke="#EAF3EA" stroke-width="0.55" opacity="0.33">'
             f'<ellipse cx="96" cy="52" rx="11" ry="30"/>'
             f'<ellipse cx="96" cy="52" rx="21" ry="30"/>'
             f'<path d="M66,52 H126 M70,37 H122 M70,67 H122"/></g>')
    b.append(f'<path d="M84,34 q10,-7 18,0 q5,5 -3,8 q-5,3 -3,9 q-9,0 -11,-7 Z" '
             f'fill="#6E8F5C" opacity="0.9"/>')
    b.append(f'<path d="M106,58 q9,-2 12,5 q-4,6 -11,3 q-5,-4 -1,-8 Z" fill="#6E8F5C" '
             f'opacity="0.85"/>')

    b.append('<g transform="translate(138,12)">'
             '<rect x="0" y="0" width="8.6" height="48" rx="4.3" fill="#FFF9EC" '
             'stroke="#8A5A3C" stroke-width="1"/>'
             '<rect x="1.9" y="18" width="4.8" height="32" fill="#C0392B"/>'
             '<circle cx="4.3" cy="52" r="7" fill="#C0392B"/>'
             '<path d="M9,16 H16" stroke="#C0392B" stroke-width="1"/></g>')
    b.append(label(156, 30, "1.5°C", 8.6, "#8E1D1F", 0.5))
    b.append(label(156, 38, "LIMIT", 4.8, "#7C4A2C", 1.1, op=0.9))

    b.append(f'<g transform="rotate(-4 250 48)">'
             f'<rect x="196" y="4" width="116" height="80" fill="#FFFCF1" '
             f'stroke="#C2A277" stroke-width="1"/>'
             f'<rect x="196" y="4" width="116" height="10" fill="#2F5A56"/>'
             f'<rect x="196" y="14" width="116" height="1" fill="#D9A94A"/>')
    b.append(label(200, 11.4, "COP31 · STOCKTAKE II", 4.4, "#FFF3D6", 0.6, 700))
    b.append(f'<g stroke="#C9B79A" stroke-width="1.7" stroke-linecap="round">'
             f'<path d="M202,25 H298 M202,32 H286 M202,39 H294"/></g>')
    b.append(f'<text x="202" y="51" font-family="Lato, sans-serif" font-size="7" '
             f'font-weight="700" fill="#3B2A1C">FOSSIL PHASE-OUT</text>')
    b.append(f'<path d="M200,49 H288" stroke="#A32020" stroke-width="2.4"/>')
    b.append(f'<rect x="200" y="56" width="86" height="8" fill="#E7C25E" opacity="0.5"/>')
    b.append(f'<text x="202" y="62.4" font-family="Lato, sans-serif" font-size="6.4" '
             f'font-weight="700" fill="#5B4A2E">ADAPTATION FUNDING</text>')
    b.append(f'<g stroke="#C9B79A" stroke-width="1.7" stroke-linecap="round">'
             f'<path d="M202,72 H298 M202,79 H270"/></g>')
    b.append("</g>")
    b.append(label(196, 95, "ANTALYA · DEADLOCK", 5.0, "#FFE3C2", 1.1, 700, op=0.92))

    b.append(frame(W, H, "#FFE3C2", 0.2))
    return svg(W, H, "A warming globe and thermometer at 1.5 degrees over cracked "
                     "earth beside the COP31 draft with its fossil phase-out line "
                     "struck through.", d, b)


# --------------------------------------------------------------------------- #
# 05 · Caracas
# --------------------------------------------------------------------------- #
def art_caracas() -> str:
    W, H = R2_W, ART2_H
    d, b = [], []
    sky = lg(d, "vsky", [(0, "#152232"), (0.42, "#33506A"), (0.76, "#B57A54"),
                         (1, "#E0A45E")])
    mtn = lg(d, "vmtn", [(0, "#2A3E4E"), (1, "#16242F")])
    mtn2 = lg(d, "vmtn2", [(0, "#1B2C39"), (1, "#0C1922")])
    glow = rg(d, "vglow", [(0, "#FFD9A0", 0.5), (1, "#FFD9A0", 0)])
    vig = rg(d, "vvig", [(0.6, "#050F18", 0), (0.86, "#050F18", 0.12), (1, "#050F18", 0.34)])

    b.append(f'<rect width="{W}" height="{H}" fill="{sky}"/>')
    stars(b, W, 22, 8, 34)
    b.append(f'<ellipse cx="168" cy="60" rx="146" ry="40" fill="{glow}"/>')

    b.append(f'<path d="M0,70 L22,56 L40,64 L62,42 L82,56 L104,36 L126,54 L148,44 '
             f'L170,60 L194,48 L216,62 L240,50 L262,64 L288,52 L310,66 L326,56 V{H} H0 Z" '
             f'fill="{mtn}" opacity="0.92"/>')
    b.append(f'<path d="M0,82 L26,70 L48,78 L74,60 L96,74 L120,62 L144,76 L168,66 '
             f'L192,80 L218,68 L244,82 L270,70 L296,84 L326,74 V{H} H0 Z" fill="{mtn2}"/>')
    rng = random.Random(3)
    for _ in range(44):
        x = rng.uniform(0, W)
        y = rng.uniform(84, H - 2)
        b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rng.uniform(.4, 1.0):.2f}" '
                 f'fill="#FFD08A" opacity="{rng.uniform(.3, .9):.2f}"/>')

    b.append(f'<rect width="{W}" height="{H}" fill="{vig}"/>')
    b.append('<g transform="rotate(-4 84 56)">')
    b.append(f'<path d="M46,16 V{H - 3}" stroke="#2A2018" stroke-width="1.8"/>')
    b.append(_flag_us(48, 20, 58, 36))
    b.append(f'<rect x="48" y="20" width="58" height="36" fill="none" stroke="#241A10" '
             f'stroke-width="0.6" opacity="0.5"/>')
    b.append("</g>")
    b.append('<g transform="rotate(4 240 56)">')
    b.append(f'<path d="M282,16 V{H - 3}" stroke="#2A2018" stroke-width="1.8"/>')
    b.append(f'<rect x="222" y="20" width="60" height="12" fill="#F2C300"/>')
    b.append(f'<rect x="222" y="32" width="60" height="12" fill="#16336B"/>')
    b.append(f'<rect x="222" y="44" width="60" height="12" fill="#C8102E"/>')
    b.append('<g fill="#FFFFFF">'
             + "".join(f'<circle cx="{226 + i * 7:.1f}" cy="{34 + math.sin(i) * 1.4:.1f}" '
                       f'r="0.85"/>' for i in range(8))
             + '</g>')
    b.append(f'<rect x="222" y="20" width="60" height="36" fill="none" stroke="#241A10" '
             f'stroke-width="0.6" opacity="0.5"/>')
    b.append("</g>")
    b.append(f'<g transform="translate(166,40)" stroke="#F2C46A" stroke-width="2.4" '
             f'fill="none">'
             f'<rect x="-8.5" y="-4.6" width="17" height="9.2" rx="4.6" transform="rotate(-34)"/>'
             f'<rect x="-8.5" y="-4.6" width="17" height="9.2" rx="4.6" transform="rotate(34)"/></g>')
    b.append(label(48, 92, "UNITED STATES", 5.0, "#F7EBD6", 1.1, 700, op=0.9))
    b.append(label(244, 92, "VENEZUELA", 5.0, "#F7EBD6", 1.1, 700, op=0.9))

    b.append(frame(W, H, "#F2C46A", 0.2))
    return svg(W, H, "The flags of the United States and Venezuela linked by a gold "
                     "chain above the lights of Caracas and the Ávila ridge.", d, b)


# --------------------------------------------------------------------------- #
# 06 · UN Security Council / Gaza report
# --------------------------------------------------------------------------- #
def art_gaza() -> str:
    W, H = R3_W, ART3_H
    d, b = [], []
    room = lg(d, "zroom", [(0, "#173650"), (1, "#07131F")])
    spot = lg(d, "zspot", [(0, "#D8E8F4", 0.24), (1, "#D8E8F4", 0)])
    stone = lg(d, "zstone", [(0, "#2A6E5E"), (1, "#123A34")])
    vig = rg(d, "zvig", [(0.6, "#030C14", 0), (0.86, "#030C14", 0.12), (1, "#030C14", 0.34)])

    b.append(f'<rect width="{W}" height="{H}" fill="{room}"/>')
    b.append(f'<path d="M104,0 L192,0 L168,86 L120,86 Z" fill="{spot}"/>')
    b.append(f'<rect x="88" y="4" width="116" height="54" fill="{stone}" opacity="0.5"/>')
    b.append(f'<g stroke="#D9A94A" stroke-width="0.6" opacity="0.28">'
             f'<path d="M88,22 H204 M88,40 H204"/></g>')
    b.append(label(146, 17, "UNITED NATIONS", 4.8, "#CBE0EE", 1.3, 700, "middle", op=0.85))
    b.append(f'<rect width="{W}" height="{H}" fill="{vig}"/>')

    b.append(f'<path d="M98,88 A50,52 0 1 1 194,88" fill="none" stroke="#2E5C8A" '
             f'stroke-width="8" stroke-linecap="round"/>')
    b.append(f'<path d="M104,86 A44,45 0 1 1 188,86" fill="none" stroke="#6F9BC4" '
             f'stroke-width="0.9" opacity="0.7"/>')
    for i in range(13):
        ang = math.radians(196 + (148 / 12) * i)
        x = 146 + 49 * math.cos(ang)
        y = 58 + 36 * math.sin(ang)
        b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.4" fill="#E4EEF6"/>')
        b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.1" fill="#3A6E9E"/>')

    b.append('<g transform="rotate(-6 40 58)">'
             '<rect x="10" y="30" width="52" height="50" fill="#FFFCF1" '
             'stroke="#C9B79A" stroke-width="0.8"/>'
             '<rect x="10" y="30" width="52" height="7.4" fill="#2E5C8A"/>')
    b.append(label(13, 35.6, "BOARD OF PEACE", 3.3, "#EAF3FA", 0.25, 700))
    b.append(f'<g stroke="#C9B79A" stroke-width="1.2" stroke-linecap="round">'
             f'<path d="M14,45 H58 M14,51 H52 M14,57 H58 M14,63 H46"/></g>')
    b.append(f'<circle cx="52" cy="70" r="5" fill="none" stroke="#A32020" stroke-width="1.3"/>')
    b.append(f'<path d="M49.6,70 l1.9,2 l3.4,-4" fill="none" stroke="#A32020" '
             f'stroke-width="1.3"/></g>')
    b.append(label(10, 14, "GAZA · 12 PP.", 5.0, "#FFD9A0", 1.0, 700, op=0.9))

    b.append(frame(W, H, "#9CC0DA", 0.18))
    return svg(W, H, "The UN Security Council horseshoe table and a twelve-page "
                     "Board of Peace report on Gaza.", d, b)


# --------------------------------------------------------------------------- #
# 07 · Kerch Bridge deepfake
# --------------------------------------------------------------------------- #
def art_kerch() -> str:
    W, H = R3_W, ART3_H
    d, b = [], []
    sky = lg(d, "ksky", [(0, "#132430"), (0.5, "#33505F"), (1, "#8A7460")])
    water = lg(d, "kwater", [(0, "#33505F"), (1, "#0B1922")])
    vig = rg(d, "kvig", [(0.6, "#040E16", 0), (0.86, "#040E16", 0.12), (1, "#040E16", 0.34)])

    b.append(f'<rect width="{W}" height="{H}" fill="{sky}"/>')
    b.append(f'<circle cx="198" cy="34" r="30" fill="#F2C48A" opacity="0.22"/>')
    b.append(f'<circle cx="198" cy="34" r="11" fill="#FFE0AE" opacity="0.5"/>')
    b.append(f'<path d="M0,54 H{W} V{H} H0 Z" fill="{water}"/>')
    waves(b, W, 58, H - 2, 15, "#9CC0DA", 7, 0.24)

    b.append(f'<path d="M0,54 H{W}" stroke="#3C4A54" stroke-width="3.2"/>')
    b.append(f'<path d="M0,47 H{W}" stroke="#54626C" stroke-width="1.4" opacity="0.8"/>')
    for x in (26, 78, 130, 182):
        b.append(f'<path d="M{x},54 q15,-20 30,0" fill="none" stroke="#4A5862" '
                 f'stroke-width="2.4"/>')
        b.append(f'<path d="M{x + 5},54 V62 M{x + 25},54 V62" stroke="#4A5862" '
                 f'stroke-width="1.4"/>')
    b.append(f'<path d="M0,47 H{W}" stroke="#94A2AC" stroke-width="0.5" '
             f'stroke-dasharray="3 3" opacity="0.6"/>')
    b.append(f'<path d="M0,58 H{W}" stroke="#F2C48A" stroke-width="0.8" opacity="0.18"/>')
    b.append(f'<rect width="{W}" height="{H}" fill="{vig}"/>')

    rng = random.Random(15)
    for i in range(5):
        b.append(f'<path d="M{24 + i * 44},64 v{rng.uniform(12, 20):.0f}" '
                 f'stroke="#F2C48A" stroke-width="{rng.uniform(1, 2.2):.1f}" '
                 f'opacity="0.1"/>')

    b.append(f'<rect x="10" y="6" width="70" height="42" fill="none" stroke="#F2765F" '
             f'stroke-width="0.9" stroke-dasharray="3 2" opacity="0.85"/>')
    b.append(f'<path d="M38,19 L38,35 L51,27 Z" fill="#F5EBD8" opacity="0.9"/>')
    b.append(label(14, 46, "AI CLIP · 0:14", 4.0, "#F2C48A", 0.6, 700, op=0.9))

    b.append('<g transform="rotate(-8 128 62)">'
             '<rect x="60" y="55" width="136" height="14" fill="#A32020"/>'
             '<rect x="60" y="53.8" width="136" height="0.8" fill="#F5EBD8" opacity="0.5"/>')
    b.append(label(66, 65.6, "DEBUNKED", 9.8, "#FFF3DC", 1.5, 700))
    b.append("</g>")
    b.append(label(12, 82, "KERCH BRIDGE", 4.6, "#C7D8E2", 1.1, 700, op=0.85))
    b.append(label(158, 82, "CRIMEA", 4.6, "#9FB6C2", 1.1, 700, op=0.7))

    b.append(frame(W, H, "#F2765F", 0.22))
    return svg(W, H, "A video frame of the Kerch Bridge in Crimea stamped "
                     "debunked after AI deepfakes exaggerated the damage.", d, b)


# --------------------------------------------------------------------------- #
# 08 · Washington aviation
# --------------------------------------------------------------------------- #
def art_duffy() -> str:
    W, H = R3_W, ART3_H
    d, b = [], []
    sky = lg(d, "dsky", [(0, "#0E1C28"), (0.45, "#2A4453"), (1, "#9A7452")])
    tarmac = lg(d, "dtar", [(0, "#2C333B"), (1, "#12161B")])
    vig = rg(d, "dvig", [(0.6, "#040C12", 0), (0.86, "#040C12", 0.12), (1, "#040C12", 0.34)])

    b.append(f'<rect width="{W}" height="{H}" fill="{sky}"/>')
    b.append(f'<circle cx="52" cy="44" r="36" fill="#F2B96E" opacity="0.14"/>')
    b.append(f'<rect x="0" y="62" width="{W}" height="{H - 62}" fill="{tarmac}"/>')
    b.append(f'<path d="M0,62 H{W}" stroke="#C7B08A" stroke-width="0.9" opacity="0.55"/>')
    for i in range(5):
        b.append(f'<path d="M{8 + i * 50},80 h20" stroke="#E8C98A" stroke-width="1.4" '
                 f'opacity="0.32"/>')
    b.append(f'<rect width="{W}" height="{H}" fill="{vig}"/>')

    b.append('<g transform="translate(4,44)">'
             '<path d="M4,18 q8,-8 21,-8 h54 l23,-4 l6,5 l-9,7 H35 q-15,0 -31,0 Z" '
             'fill="#E6E9EC"/>'
             '<path d="M4,18 q8,-8 21,-8 h54 l23,-4 l6,5 l-9,7 H35 q-15,0 -31,0 Z" '
             'fill="#0E1A24" opacity="0.16"/>'
             '<path d="M38,10 q6,-5 15,-5 h19 l-4,5 Z" fill="#9FB4C4"/>'
             '<path d="M42,18 L28,-2 L38,-2 L56,18 Z" fill="#DDE2E6"/>'
             '<path d="M60,18 L48,40 H58 L72,18 Z" fill="#C9D1D8"/>'
             '<path d="M93,17 L101,38 H106 L101,17 Z" fill="#C9D1D8"/>'
             '<g fill="#1E3A4E">'
             + "".join(f'<rect x="{32 + i * 7}" y="13" width="3.2" height="2.4"/>'
                       for i in range(9))
             + '</g></g>')

    b.append('<g transform="translate(178,16)">'
             '<rect x="10" y="26" width="15" height="40" fill="#1A2836"/>'
             '<path d="M4,26 L12,14 H23 L31,26 Z" fill="#243546"/>'
             '<rect x="6" y="14" width="25" height="5.4" fill="#9CC0DA" opacity="0.7"/>'
             '<path d="M18,14 V6" stroke="#243546" stroke-width="1.3"/>'
             '<circle cx="18" cy="5" r="2" fill="#E8452E"/>'
             '<circle cx="18" cy="5" r="4.8" fill="#E8452E" opacity="0.28"/>'
             '<g stroke="#7C93A4" stroke-width="0.8" opacity="0.7">'
             '<path d="M8,44 h18 M8,51 h11"/></g></g>')

    for x, y in ((150, 72), (161, 75)):
        b.append(f'<path d="M{x},{y - 5.4} L{x + 2.7},{y} H{x - 2.7} Z" fill="#E07A2E"/>')
    b.append(label(10, 82, "GROUNDED · NATIONWIDE", 4.9, "#FF9C82", 1.2, 700))

    b.append(frame(W, H, "#E8C98A", 0.2))
    return svg(W, H, "A grounded airliner on a dusk apron beside a control tower "
                     "with a red beacon, marking nationwide aviation groundings.",
               d, b)


# --------------------------------------------------------------------------- #
# 09 · Houthi drone strike on the East–West pipeline
# --------------------------------------------------------------------------- #
def art_houthi() -> str:
    W, H = R3_W, ART3_H
    d, b = [], []
    sky = lg(d, "hsky", [(0, "#2B1B24"), (0.4, "#7C3C2E"), (0.76, "#CE7B32"),
                         (1, "#EFB268")])
    sand = lg(d, "hsand", [(0, "#BE8A54"), (1, "#6E4526")])
    glow = rg(d, "hglow", [(0, "#FFD9A0", 0.5), (1, "#FFD9A0", 0)])
    vig = rg(d, "hvig", [(0.6, "#1A0A06", 0), (0.86, "#1A0A06", 0.12), (1, "#1A0A06", 0.34)])

    b.append(f'<rect width="{W}" height="{H}" fill="{sky}"/>')
    b.append(f'<circle cx="206" cy="44" r="38" fill="{glow}"/>')
    b.append(f'<circle cx="206" cy="44" r="9" fill="#FFEBC6" opacity="0.85"/>')
    b.append(f'<path d="M0,54 Q45,44 90,52 Q140,44 190,54 Q220,58 {W},50 V{H} H0 Z" '
             f'fill="{sand}" opacity="0.85"/>')
    b.append(f'<path d="M0,66 Q60,60 120,66 Q180,72 {W},66 V{H} H0 Z" fill="#7C4C28"/>')
    b.append(f'<path d="M0,74 Q70,68 140,76 Q200,70 {W},78 V{H} H0 Z" fill="#5B351C"/>')
    b.append(f'<rect width="{W}" height="{H}" fill="{vig}"/>')

    b.append(f'<path d="M240,64 H14" stroke="#22150C" stroke-width="6.4" opacity="0.5"/>')
    b.append(f'<path d="M240,62 H14" stroke="#8A5A2E" stroke-width="4.2"/>')
    b.append(f'<path d="M240,60.6 H14" stroke="#E8A35C" stroke-width="1.1" opacity="0.8"/>')
    for x in (30, 78, 126, 174, 222):
        b.append(f'<rect x="{x}" y="59" width="3.6" height="8" fill="#2C1A10"/>')
    b.append('<rect x="104" y="48" width="19" height="13" fill="#2C1A10"/>')
    b.append('<rect x="107" y="51" width="13" height="2" fill="#E8A35C" opacity="0.6"/>')

    b.append(f'<circle cx="150" cy="62" r="22" fill="{glow}"/>')
    b.append(burst(150, 62, 6.8))
    b.append(f'<path d="M150,40 q5,-9 2,-14" stroke="#FFB18A" stroke-width="1.3" '
             f'fill="none" opacity="0.6"/>')

    b.append('<g transform="translate(196,20)">'
             '<path d="M-13,0 H13 M0,-9 V9" stroke="#1A0F0A" stroke-width="1.5"/>'
             '<circle cx="-13" cy="-6" r="3.6" fill="none" stroke="#1A0F0A" stroke-width="1.1"/>'
             '<circle cx="13" cy="-6" r="3.6" fill="none" stroke="#1A0F0A" stroke-width="1.1"/>'
             '<circle cx="-13" cy="6" r="3.6" fill="none" stroke="#1A0F0A" stroke-width="1.1"/>'
             '<circle cx="13" cy="6" r="3.6" fill="none" stroke="#1A0F0A" stroke-width="1.1"/>'
             '<rect x="-3.6" y="-2.8" width="7.2" height="5.6" rx="1.2" fill="#1A0F0A"/></g>')
    b.append(f'<path d="M190,32 Q168,52 156,58" fill="none" stroke="#FF9C82" '
             f'stroke-width="0.9" stroke-dasharray="3 2" opacity="0.8"/>')
    b.append(label(10, 82, "EAST–WEST LINE · RIYADH", 4.8, "#FFD9A0", 1.1, 700))

    b.append(frame(W, H, "#E8A35C", 0.22))
    return svg(W, H, "A drone above the Saudi East-West oil pipeline at dusk with a "
                     "strike on a pumping station near Riyadh.", d, b)


# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# World Wire vignettes (44 x 44)
# --------------------------------------------------------------------------- #
def _corner(defs, name) -> str:
    fill = rg(defs, name, [(0, "#04101A", 0.0), (0.62, "#04101A", 0.05),
                           (1, "#04101A", 0.42)], 0.32, 0.28, 0.85)
    return fill


def wire_tfl() -> str:
    d, b = [], []
    tun = lg(d, "wtun", [(0, "#0B1822"), (0.6, "#16303F"), (1, "#071219")])
    b.append(f'<rect width="44" height="44" fill="{tun}"/>')
    b.append(f'<path d="M14,44 L19,10 H25 L30,44 Z" fill="#1E3E50" opacity="0.6"/>')
    b.append(f'<circle cx="22" cy="22" r="11.5" fill="none" stroke="#D2352C" '
             f'stroke-width="3.6"/>')
    b.append(f'<rect x="9.5" y="19.6" width="25" height="4.8" fill="#D2352C"/>')
    b.append(f'<circle cx="22" cy="22" r="15" fill="none" stroke="#D2352C" '
             f'stroke-width="0.6" opacity="0.35"/>')
    b.append(f'<rect x="30" y="30" width="11" height="7" rx="1" fill="#E8D9BE"/>')
    b.append(f'<rect x="31.4" y="31.6" width="8" height="1.2" fill="#8A6A3A"/>')
    b.append(f'<rect width="44" height="44" fill="{_corner(d, "wtv")}"/>')
    return svg(44, 44, "A London transport roundel in a tunnel beside a transit card.",
               d, b, "wnart")


def wire_chip() -> str:
    d, b = [], []
    board = lg(d, "wbrd", [(0, "#123024"), (1, "#061410")])
    b.append(f'<rect width="44" height="44" fill="{board}"/>')
    for i in range(7):
        b.append(f'<path d="M{4 + i * 6},0 V44" stroke="#2F6B4A" stroke-width="0.7" '
                 f'opacity="0.55"/>')
        b.append(f'<path d="M0,{4 + i * 6} H44" stroke="#2F6B4A" stroke-width="0.7" '
                 f'opacity="0.4"/>')
    b.append(f'<rect x="10" y="10" width="24" height="24" rx="2" fill="#0C1A22" '
             f'stroke="#C9A24A" stroke-width="1"/>')
    b.append(f'<rect x="15" y="15" width="14" height="14" fill="#7BE0A8" opacity="0.85"/>')
    b.append(f'<rect x="18" y="18" width="8" height="8" fill="#FFF3C8"/>')
    for i in range(4):
        b.append(f'<path d="M{13 + i * 6},10 V4 M{13 + i * 6},34 V40" '
                 f'stroke="#C9A24A" stroke-width="1.2"/>')
        b.append(f'<path d="M10,{13 + i * 6} H4 M34,{13 + i * 6} H40" '
                 f'stroke="#C9A24A" stroke-width="1.2"/>')
    b.append(f'<rect width="44" height="44" fill="{_corner(d, "wcv")}"/>')
    return svg(44, 44, "A glowing semiconductor die on a circuit board.", d, b, "wnart")


def wire_ukr() -> str:
    d, b = [], []
    bg = lg(d, "wukr", [(0, "#0E2036"), (1, "#060F1A")])
    glow = rg(d, "wflame", [(0, "#FFD08A", 0.9), (0.5, "#F2A03A", 0.35), (1, "#F2A03A", 0)])
    b.append(f'<rect width="44" height="44" fill="{bg}"/>')
    b.append(f'<circle cx="18" cy="20" r="18" fill="{glow}"/>')
    b.append(f'<rect x="12" y="22" width="6" height="16" fill="#E8DCC0"/>')
    b.append(f'<path d="M15,8 q4,6 0,10 q-4,-4 0,-10 Z" fill="#FFE9B8"/>')
    b.append(f'<path d="M15,12 q2,4 0,6 q-2,-2 0,-6 Z" fill="#FFF8E6"/>')
    for i, h in enumerate((10, 15, 20, 26)):
        b.append(f'<rect x="{26 + i * 4.4}" y="{38 - h}" width="2.8" height="{h}" '
                 f'fill="#C0392B" opacity="{0.5 + i * 0.12:.2f}"/>')
    b.append(f'<path d="M25,38 H43" stroke="#C7D8E2" stroke-width="0.8" opacity="0.5"/>')
    b.append(f'<rect width="44" height="44" fill="{_corner(d, "wuv")}"/>')
    return svg(44, 44, "A candle beside a rising bar chart for the UN count of "
                       "civilian casualties in Ukraine.", d, b, "wnart")


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #
def _panel(cls: str, region: str, num: str, kicker: str, headline: str,
           sf: str, art: str, tag: str) -> str:
    return f"""
<section class="panel {cls}" style="--rc:{REGION[region]}">
  <div class="artwrap">{art}</div>
  <div class="pbody">
    <div class="kick"><span class="chip"></span>{kicker}<span class="num">{num}</span></div>
    <h2>{headline}</h2>
    <p class="sf">{sf}</p>
    <div class="tag">{tag}</div>
  </div>
</section>"""


def _wire(num: str, kicker: str, headline: str, text: str, art: str) -> str:
    return f"""<div class="witem">{art}
  <div class="wtext"><div class="wk">{num} · {kicker}</div>
    <h3>{headline}</h3><p>{text}</p></div></div>"""


CSS = """
@page { size: 1024px 1024px; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: __PAPER__; }
body { width: 1024px; height: 1024px; overflow: hidden; }
.poster {
  position: relative; width: 1024px; height: 1024px; padding: 12px 16px 10px;
  background-color: __PAPER__;
  color: __INK__;
  font-family: "Lato", "Noto Sans", sans-serif;
  display: flex; flex-direction: column;
  -webkit-font-smoothing: antialiased; text-rendering: geometricPrecision;
}
.poster::after {
  content: ""; position: absolute; inset: 0; pointer-events: none;
  box-shadow: inset 0 0 0 1px rgba(22,26,30,0.14);
}
.rule { height: 4px; background: __CRIMSON__; margin: 0 -16px; flex: none; }
.rail {
  margin-top: 4px; height: 18px; flex: none;
  display: flex; align-items: center; justify-content: space-between;
  font-weight: 700; font-size: 8.4px; letter-spacing: 2.1px;
  color: __CRIMSON_DARK__; text-transform: uppercase; white-space: nowrap;
}
.rail .mid { color: #6F6553; letter-spacing: 2.4px; }
.hair { height: 1px; background: __HAIR__; flex: none; }
h1 {
  margin: 3px 0 0; font-family: "Noto Serif", Georgia, serif; font-weight: 700;
  font-size: 59px; line-height: 0.94; letter-spacing: -0.9px;
  white-space: nowrap; flex: none;
}
h1 .day { color: __CRIMSON__; }
h1 .sep { color: __GOLD__; padding: 0 9px; }
.deck {
  margin: 5px 0 0; font-size: 14.4px; line-height: 1.3; color: #352F26;
  letter-spacing: 0.05px; flex: none;
}
.deck em { font-style: normal; font-weight: 700; color: __CRIMSON_DARK__; }
.deck b { font-weight: 700; color: #1E2833; }
.strip {
  margin-top: 6px; height: 22px; flex: none; display: flex;
  border-top: 1px solid __HAIR__; border-bottom: 1px solid __HAIR__;
}
.strip div {
  flex: 1; display: flex; align-items: center; gap: 6px; height: 100%;
  padding-right: 8px; font-weight: 700; font-size: 8.4px; letter-spacing: 1.3px;
  color: #3B342A; text-transform: uppercase; white-space: nowrap;
}
.strip div + div { border-left: 1px solid __HAIR__; padding-left: 8px; }
.strip i { width: 6px; height: 6px; display: inline-block; flex: none; }
.strip b {
  margin-left: auto; font-family: "Noto Serif", Georgia, serif; font-size: 9.6px;
  font-weight: 700; color: #6F6553; letter-spacing: 0;
}

.sheet { margin-top: 8px; flex: 1 1 auto; min-height: 0;
         display: flex; flex-direction: column; gap: 7px; }
.row { display: flex; gap: 7px; min-height: 0; }
.row1 { flex: 0 0 __R1__px; }
.row2 { flex: 0 0 __R2__px; }
.row3 { flex: 1 1 184px; }
.row2 .panel, .row3 .panel { flex: 1 1 0; }

.panel {
  position: relative; background: __PAPER__; overflow: hidden; min-width: 0;
  display: flex; flex-direction: column;
  box-shadow: inset 0 0 0 1px rgba(22,26,30,0.17);
}
.panel > .artwrap { position: relative; flex: none; width: 100%; overflow: hidden; }
.panel > .artwrap svg { display: block; width: 100%; height: 100%; }
.artwrap::after {
  content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 3px;
  background: var(--rc);
}
.r2 .artwrap { height: __ART2__px; }
.r3 .artwrap { height: __ART3__px; }
.hero > .artwrap, .ipo > .artwrap { height: __ART1__px; }

.pbody { padding: 6px 9px 7px; display: flex; flex-direction: column;
         flex: 1 1 auto; min-height: 0; }
.kick {
  display: flex; align-items: center; gap: 6px; flex: none;
  font-weight: 700; font-size: 8.1px; letter-spacing: 1.15px;
  color: var(--rc); text-transform: uppercase; white-space: nowrap;
}
.kick .chip { width: 6px; height: 6px; background: var(--rc); flex: none; }
.kick .num {
  margin-left: auto; font-family: "Noto Serif", Georgia, serif; font-weight: 700;
  font-size: 12px; letter-spacing: 0; color: #8C7A5C; line-height: 1;
}
h2 { margin: 3px 0 0; font-family: "Noto Serif", Georgia, serif; font-weight: 700;
     color: __INK__; letter-spacing: -0.4px; }
.r2 h2 { font-size: 19.4px; line-height: 1.06; }
.r3 h2 { font-size: 16.2px; line-height: 1.07; }
.sf { margin: 4px 0 0; color: __INK_SOFT__; letter-spacing: 0.02px; }
.r2 .sf { font-size: 9.2px; line-height: 1.28; }
.r3 .sf { font-size: 8.4px; line-height: 1.26; }
.hero .tag, .ipo .tag { border-color: rgba(240,200,122,0.28); color: #C9B793; }
.tag {
  margin-top: auto; padding-top: 3px; border-top: 1px solid __HAIR__;
  font-weight: 700; font-size: 7.3px; letter-spacing: 1.15px;
  text-transform: uppercase; color: var(--rc); white-space: nowrap;
}

.hero { flex: 0 0 648px; background: #0B1B28; }
.ipo { flex: 1 1 auto; background: #0B1B28; }
.hero .pbody, .ipo .pbody {
  background: linear-gradient(180deg, #10263A 0%, #0B1B28 46%, #081520 100%);
  padding: 7px 14px 6px;
}
.hero .kick, .ipo .kick { color: #F0C87A; }
.hero .kick .chip, .ipo .kick .chip { background: #F0C87A; }
.hero .kick .num, .ipo .kick .num { color: #8FA6B6; }
.hero h2 {
  font-size: 26px; line-height: 1.02; color: #FCF7EB; letter-spacing: -0.7px;
  margin-top: 4px;
}
.hero .sf { font-size: 9.4px; line-height: 1.3; color: #C6D4DF; margin-top: 4px; }
.chips { display: flex; gap: 5px; margin-top: 6px; }
.chips span {
  font-weight: 700; font-size: 7.3px; letter-spacing: 1.15px; color: #F3E2BE;
  border: 1px solid rgba(240,200,122,0.4); padding: 2px 5px; white-space: nowrap;
}
.ipo h2 { font-size: 20.8px; line-height: 1.04; color: #FCF7EB;
          letter-spacing: -0.55px; margin-top: 2px; }
.ipo .sf { font-size: 9.1px; line-height: 1.28; color: #C6D4DF; margin-top: 5px; }
.istats { display: flex; gap: 8px; margin-top: 4px; }
.istats div { flex: 1; border-top: 2px solid __GOLD__; padding-top: 3px; }
.istats b { display: block; font-family: "Noto Serif", Georgia, serif;
            font-size: 19px; font-weight: 700; color: #F6D08A; letter-spacing: -0.5px;
            line-height: 1.1; }
.istats span { font-weight: 700; font-size: 6.5px; letter-spacing: 1.1px;
               color: #C9B793; text-transform: uppercase; }

.wire {
  margin-top: 7px; height: __WIRE__px; flex: none; display: flex;
  background: #EDE4CE; border-top: 3px solid __CRIMSON__;
  border-bottom: 1px solid __HAIR__;
}
.wire-label {
  flex: 0 0 92px; padding: 8px 10px 6px 2px; border-right: 1px solid #D3C4A8;
  display: flex; flex-direction: column; justify-content: center;
}
.wire-label b {
  font-family: "Noto Serif", Georgia, serif; font-size: 14px; line-height: 1.02;
  color: __CRIMSON_DARK__; letter-spacing: -0.2px; text-transform: uppercase;
}
.wire-label span { font-weight: 700; font-size: 6.3px; letter-spacing: 1.4px;
                   color: #6B5F49; margin-top: 4px; }
.wires { flex: 1; display: flex; min-width: 0; }
.witem { flex: 1; display: flex; gap: 6px; padding: 7px 8px 5px; min-width: 0; }
.witem + .witem { border-left: 1px solid #D3C4A8; }
.wnart { width: 44px; height: 44px; flex: none; display: block; }
.wtext { min-width: 0; }
.wk { font-weight: 700; font-size: 6.5px; letter-spacing: 0.95px;
      color: #6B5F49; text-transform: uppercase; white-space: nowrap; }
.wtext h3 { margin: 2px 0 0; font-family: "Noto Serif", Georgia, serif;
            font-size: 11.6px; line-height: 1.12; color: __INK__; }
.wtext p { margin: 2px 0 0; font-size: 8.1px; line-height: 1.24; color: #4A4438; }

.foot {
  margin-top: 4px; flex: none;
  display: flex; justify-content: space-between; align-items: baseline;
  font-size: 7.2px; letter-spacing: 0.45px; color: #6B5F49;
}
.foot b { color: __CRIMSON_DARK__; letter-spacing: 1.2px; }
"""


def build_html() -> str:
    hero = f"""
<section class="panel hero" style="--rc:{REGION['me']}">
  <div class="artwrap">{art_gulf()}</div>
  <div class="pbody">
    <div class="kick"><span class="chip"></span>01 · PERSIAN GULF · ESCALATION</div>
    <h2>US AND IRAN TRADE STRIKES<br>ACROSS THE GULF</h2>
    <p class="sf">A US strike hits an Iranian missile site on Qeshm Island; drones
      strike a US radar in Bahrain; Iran answers against Bahrain and Kuwait’s
      Ali Al Salem base as tankers run the Hormuz strait.</p>
    <div class="chips"><span>QESHM STRIKE</span><span>BAHRAIN RADAR</span>
      <span>HORMUZ SHIPPING</span><span>KUWAIT BASE</span></div>
  </div>
</section>"""

    ipo = f"""
<section class="panel ipo" style="--rc:{REGION['am']}">
  <div class="artwrap">{art_ipo()}</div>
  <div class="pbody">
    <div class="kick"><span class="chip"></span>02 · NEW YORK · MARKETS &amp; AI</div>
    <h2>ANTHROPIC VALUED<br>AT $1.5tn IN IPO</h2>
    <p class="sf">Its landmark listing priced at $83 a share.</p>
    <div class="istats">
      <div><b>$83</b><span>per share</span></div>
      <div><b>$1.5tn</b><span>valuation</span></div>
    </div>
    <div class="tag">NASDAQ DEBUT · 18 NOVEMBER 2026</div>
  </div>
</section>"""

    row2 = "".join([
        _panel("r2", "ap", "03", "SHENZHEN · DIPLOMACY",
               "APEC SETS UP TRUMP–XI–PUTIN TALKS",
               "Leaders gather on the Shenzhen waterfront with security, trade and "
               "nuclear risk on the table.",
               art_apec(), "APEC 2026 · THREE LEADERS"),
        _panel("r2", "gs", "04", "ANTALYA · CLIMATE &amp; GLOBAL SOUTH",
               "COP31 STOCKTAKE ENDS<br>IN DEADLOCK",
               "A mid-week draft drops fossil-fuel phase-out language; vulnerable "
               "nations press for adaptation funding.",
               art_cop31(), "STOCKTAKE II · 1.5°C LIMIT"),
        _panel("r2", "am", "05", "CARACAS · DIPLOMACY",
               "US AND VENEZUELA RESTORE MILITARY TIES",
               "Defense officials led by Pete Hegseth announce a deal to re-establish "
               "formal military relations.",
               art_caracas(), "MILITARY TIES RESTORED"),
    ])

    row3 = "".join([
        _panel("r3", "me", "06", "UNITED NATIONS · GAZA",
               "GAZA REPORT FAULTS BOTH SIDES",
               "A 12-page Board of Peace report says Israel and Hamas failed to keep "
               "ceasefire commitments.",
               art_gaza(), "12 PP. · 15 MEMBERS"),
        _panel("r3", "eu", "07", "KYIV · INFORMATION",
               "KERCH BRIDGE DEEPFAKES<br>DEBUNKED",
               "Fact-checkers say viral AI deepfakes exaggerated damage to the "
               "Kerch Bridge.",
               art_kerch(), "AI VIDEO · DEBUNKED"),
        _panel("r3", "am", "08", "WASHINGTON · AVIATION",
               "DUFFY GRILLED ON GROUNDINGS",
               "The transportation secretary faces a Capitol Hill grilling on "
               "nationwide groundings.",
               art_duffy(), "CAPITOL HILL · NATIONWIDE"),
        _panel("r3", "me", "09", "RIYADH · ENERGY",
               "HOUTHIS TARGET SAUDI PIPELINE",
               "The Yemeni group claims drone attacks on pumping stations on the "
               "East–West line near Riyadh.",
               art_houthi(), "EAST–WEST LINE"),
    ])

    wire = "".join([
        _wire("10", "LONDON · CYBERSECURITY", "TfL warns riders of a data breach",
              "Suspicious activity hit transit cards; account details may be exposed.",
              wire_tfl()),
        _wire("11", "GLOBAL · SEMICONDUCTORS", "Nvidia fallout hits US–China tech",
              "A leadership shake-up reverberates through chip supply and policy.",
              wire_chip()),
        _wire("12", "KYIV · HUMAN RIGHTS", "UN: Ukraine toll tops prior years",
              "HRMMU says 2026 civilian casualties have passed earlier tolls.",
              wire_ukr()),
    ])

    css = (CSS.replace("__PAPER__", PAPER).replace("__INK__", INK)
              .replace("__INK_SOFT__", INK_SOFT).replace("__CRIMSON__", CRIMSON)
              .replace("__CRIMSON_DARK__", CRIMSON_DARK).replace("__GOLD__", GOLD)
              .replace("__HAIR__", HAIR).replace("__R1__", str(R1_H))
              .replace("__R2__", str(R2_H)).replace("__R3__", str(R3_H))
              .replace("__ART1__", str(ART1_H)).replace("__ART2__", str(ART2_H))
              .replace("__ART3__", str(ART3_H)).replace("__WIRE__", str(WIRE_H)))

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>The World Today — Wednesday 18 November 2026</title>
<style>{css}</style>
</head>
<body>
<div class="poster" id="poster">
  <div class="rule"></div>
  <div class="rail">
    <span>THE WORLD TODAY · A PICTORIAL BROADSHEET</span>
    <span class="mid">TWELVE DISPATCHES · SIX REGIONS</span>
    <span>VOL. VII · NO. 322</span>
  </div>
  <div class="hair"></div>

  <h1><span class="day">WEDNESDAY</span><span class="sep">·</span>18 NOVEMBER 2026</h1>
  <p class="deck">Strikes across the Gulf and Hormuz, Anthropic’s <b>$1.5tn</b>
    Nasdaq listing, a <em>deadlocked</em> climate stocktake in Antalya, and restored
    US–Venezuela military ties: twelve dispatches, six regions, one Wednesday.</p>

  <div class="strip">
    <div><i style="background:{REGION['me']}"></i>Middle East<b>3</b></div>
    <div><i style="background:{REGION['am']}"></i>Americas<b>3</b></div>
    <div><i style="background:{REGION['ap']}"></i>Asia-Pacific<b>1</b></div>
    <div><i style="background:{REGION['eu']}"></i>Europe<b>3</b></div>
    <div><i style="background:{REGION['gs']}"></i>Global South<b>1</b></div>
    <div><i style="background:{REGION['te']}"></i>Global Tech<b>1</b></div>
  </div>

  <div class="sheet">
    <div class="row row1">{hero}{ipo}</div>
    <div class="row row2">{row2}</div>
    <div class="row row3">{row3}</div>
  </div>

  <div class="wire">
    <div class="wire-label"><b>World<br>Wire</b><span>ALSO ON 18 NOV</span></div>
    <div class="wires">{wire}</div>
  </div>

  <div class="foot">
    <span>Sources: AP · Reuters · BBC · PBS · The Guardian · The Hindu · ISW ·
      Just Security. Events of Wednesday 18 November 2026.</span>
    <span><b>WORLD NEWS CANVAS</b> · 02</span>
  </div>
</div>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
AUDIT_JS = r"""
() => {
  const round = (n) => Math.round(n * 10) / 10;
  const report = { doc: {}, poster: {}, header: {}, panels: [], svg: [],
                   text: [], overlaps: [], boxes: [], tboxes: [], svgt: [] };
  const de = document.documentElement;
  report.doc = { w: de.scrollWidth, h: de.scrollHeight,
                 bw: document.body.scrollWidth, bh: document.body.scrollHeight };
  const poster = document.getElementById('poster');
  const pr = poster.getBoundingClientRect();
  report.poster = { w: round(pr.width), h: round(pr.height) };

  const lines = (el) => {
    const r = document.createRange(); r.selectNodeContents(el);
    const rects = [...r.getClientRects()].filter(x => x.height > 1 && x.width > 1);
    const tops = [...new Set(rects.map(x => Math.round(x.top)))];
    return tops.length;
  };

  const mast = document.querySelector('h1');
  const mr = mast.getBoundingClientRect();
  const rng = document.createRange(); rng.selectNodeContents(mast);
  const tr = rng.getBoundingClientRect();
  report.header = { masthead: { left: round(mr.left), right: round(mr.right),
                                textRight: round(tr.right),
                                rightGap: round(mr.right - tr.right),
                                size: getComputedStyle(mast).fontSize,
                                lines: lines(mast),
                                scrollW: mast.scrollWidth, clientW: mast.clientWidth },
                    deck: { lines: lines(document.querySelector('.deck')),
                            h: round(document.querySelector('.deck').getBoundingClientRect().height) } };

  document.querySelectorAll('.panel').forEach((p, i) => {
    const r = p.getBoundingClientRect();
    const art = p.querySelector('.artwrap');
    const ar = art.getBoundingClientRect();
    const entry = {
      i, cls: p.className.replace(/\s+/g, '.'),
      box: { x: round(r.left - pr.left), y: round(r.top - pr.top),
             w: round(r.width), h: round(r.height) },
      artBottom: round(ar.bottom - pr.top),
      overflowY: p.scrollHeight - p.clientHeight,
      overflowX: p.scrollWidth - p.clientWidth,
      children: [], lines: {}
    };
    p.querySelectorAll(':scope > *').forEach((el) => {
      const b = el.getBoundingClientRect();
      if (b.left < r.left - 0.6 || b.right > r.right + 0.6 ||
          b.top < r.top - 0.6 || b.bottom > r.bottom + 0.6) {
        entry.children.push({ tag: el.tagName.toLowerCase(),
          cls: String(el.className).slice(0, 24),
          l: round(b.left - r.left), t: round(b.top - r.top),
          r: round(r.right - b.right), b: round(r.bottom - b.bottom) });
      }
    });
    const h2 = p.querySelector('h2'), sf = p.querySelector('.sf');
    entry.lines.h2 = lines(h2); entry.lines.sf = lines(sf);
    entry.lines.h2h = round(h2.getBoundingClientRect().height);
    entry.lines.sfh = round(sf.getBoundingClientRect().height);
    const tag = p.querySelector('.tag');
    entry.tagBottom = tag ? round(tag.getBoundingClientRect().bottom - pr.top)
                          : round(r.bottom - pr.top);
    entry.panelBottom = round(r.bottom - pr.top);
    entry.boxes = true;
    report.panels.push(entry);
    report.boxes.push({ cls: entry.cls, x: entry.box.x, y: entry.box.y,
                        w: entry.box.w, h: entry.box.h,
                        artBottom: entry.artBottom });
  });

  document.querySelectorAll('.witem').forEach((w, i) => {
    const r = w.getBoundingClientRect();
    const a = w.querySelector('.wnart').getBoundingClientRect();
    report.boxes.push({ cls: 'witem' + i, x: round(a.left - pr.left),
                        y: round(a.top - pr.top), w: round(a.width),
                        h: round(a.height),
                        artBottom: round(a.bottom - pr.top) });
    const h3 = w.querySelector('h3'), pp = w.querySelector('p');
    report.text.push({ text: 'wire-h3-' + i, lines: lines(h3),
                       h: round(h3.getBoundingClientRect().height) });
    report.text.push({ text: 'wire-p-' + i, lines: lines(pp),
                       h: round(pp.getBoundingClientRect().height) });
  });

  document.querySelectorAll('svg').forEach((svg, i) => {
    const sr = svg.getBoundingClientRect();
    const bad = [];
    let n = 0;
    svg.querySelectorAll('path,rect,circle,ellipse,line,polygon,polyline,text').forEach((el) => {
      if (el.closest('[data-bleed]')) return;
      const b = el.getBoundingClientRect();
      if (!b.width && !b.height) return;
      n++;
      const tol = 2.0;
      if (b.left < sr.left - tol || b.top < sr.top - tol ||
          b.right > sr.right + tol || b.bottom > sr.bottom + tol) {
        bad.push({ tag: el.tagName, l: round(b.left - sr.left),
                   t: round(b.top - sr.top), r: round(b.right - sr.right),
                   b: round(b.bottom - sr.bottom) });
      }
    });
    if (bad.length) report.svg.push({ i, cls: svg.getAttribute('class'), n,
                                      bad: bad.slice(0, 6) });
  });

  document.querySelectorAll('svg text').forEach((el) => {
    const b = el.getBoundingClientRect();
    if (b.width < 2 || b.height < 2) return;
    report.svgt.push({ t: el.textContent.slice(0, 18),
                       x: round(b.left - pr.left), y: round(b.top - pr.top),
                       w: round(b.width), h: round(b.height),
                       size: round(parseFloat(getComputedStyle(el).fontSize)),
                       fill: el.getAttribute('fill') || '#000000' });
  });

  document.querySelectorAll('.panel h2, .panel .sf, .panel .kick, .panel .tag, h1, .deck, .wtext h3, .wtext p, .witem .wk, .strip div, .foot span, .chips span').forEach((el) => {
    const b = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    report.tboxes.push({ t: el.textContent.trim().slice(0, 24),
      x: round(b.left - pr.left), y: round(b.top - pr.top),
      w: round(b.width), h: round(b.height),
      size: round(parseFloat(cs.fontSize)), color: cs.color });
  });

  const els = [...document.querySelectorAll(
    '.panel h2, .panel .sf, .panel .kick, .panel .tag, .wtext h3, .wtext p, .witem .wk, .strip div, .rail span, .deck, .foot span, h1, .chips span')];
  for (let i = 0; i < els.length; i++) {
    for (let j = i + 1; j < els.length; j++) {
      const a = els[i].getBoundingClientRect(), b = els[j].getBoundingClientRect();
      if (els[i].contains(els[j]) || els[j].contains(els[i])) continue;
      const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (ox > 1.2 && oy > 1.2) {
        report.overlaps.push({ a: els[i].textContent.trim().slice(0, 30),
                               b: els[j].textContent.trim().slice(0, 30),
                               ox: round(ox), oy: round(oy) });
      }
    }
  }
  return report;
}
"""


def render(html_path: Path, out_png: Path) -> dict:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=CHROME, headless=True,
            args=["--force-device-scale-factor=1", "--hide-scrollbars",
                  "--font-render-hinting=none", "--disable-lcd-text"],
        )
        page = browser.new_page(viewport={"width": SIZE, "height": SIZE},
                                device_scale_factor=1)
        page.goto(html_path.as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(220)
        audit = page.evaluate(AUDIT_JS)
        page.locator("#poster").screenshot(path=str(out_png))
        browser.close()
    return audit


def _rel_lum(rgb: np.ndarray) -> np.ndarray:
    c = np.clip(rgb / 255.0, 0.0, 1.0)
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return c @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def pixel_audit(img: Image.Image, boxes: list[dict]) -> list[str]:
    """Per-scene detail energy, tonal range and a dead-cell grid."""
    problems = []
    rgb = np.asarray(img.convert("RGB")).astype(np.float32)
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    mx = rgb.max(axis=2)
    sat = (mx - rgb.min(axis=2)) / np.maximum(mx, 1)

    for box in boxes:
        x0, y0 = int(round(box["x"])), int(round(box["y"]))
        x1, y1 = int(round(box["x"] + box["w"])), int(round(box["y"] + box["h"]))
        art_end = int(round(box["artBottom"]))
        art = lum[y0:art_end, x0:x1]
        if art.size == 0:
            continue
        gy, gx = np.gradient(art)
        edge = float(np.abs(gx).mean() + np.abs(gy).mean())
        std = float(art.std())
        colour = float(sat[y0:art_end, x0:x1].mean())
        ah, aw = art.shape
        voids, cells = [], 0
        for j in range(3):
            for i in range(5):
                cy0, cy1 = int(j * ah / 3), int((j + 1) * ah / 3)
                cx0, cx1 = int(i * aw / 5), int((i + 1) * aw / 5)
                cell = art[cy0:cy1, cx0:cx1]
                if cell.size == 0:
                    continue
                cells += 1
                if cell.std() < 3.2 and np.abs(np.gradient(cell)[0]).mean() < 0.5:
                    voids.append(f"{i},{j}")
        cls = box["cls"]
        print(f"  px {cls:24s} edge={edge:5.2f} std={std:5.1f} sat={colour:.2f} "
              f"voids={len(voids)}/{cells}")
        if edge < 1.1:
            problems.append(f"{cls}: scene lacks detail (edge {edge:.2f})")
        if std < 16:
            problems.append(f"{cls}: flat tonality (std {std:.1f})")
        if len(voids) > (2 if aw < 60 else 0):
            problems.append(f"{cls}: dead cells at {voids}")
    return problems


def _hex_rgb(value: str):
    m = re.match(r"#([0-9A-Fa-f]{6})", value.strip())
    if not m:
        return None
    n = int(m.group(1), 16)
    return np.array([[n >> 16 & 255, n >> 8 & 255, n & 255]], dtype=np.float32)


def contrast_audit(img: Image.Image, tboxes: list[dict],
                   svgt: list[dict] | None = None) -> list[str]:
    """WCAG ratio of each text block's own colour against its backdrop."""
    problems = []
    lum = np.asarray(_rel_lum(np.asarray(img.convert("RGB")).astype(np.float32)))
    worst = 99.0
    for tb in tboxes:
        x0, y0 = int(round(tb["x"])), int(round(tb["y"]))
        x1 = int(round(tb["x"] + tb["w"]))
        y1 = int(round(tb["y"] + tb["h"]))
        crop = lum[max(y0, 0):y1, max(x0, 0):x1]
        if crop.size < 24:
            continue
        m = re.match(r"rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)", tb["color"])
        if not m:
            continue
        ink = float(_rel_lum(np.array([[float(m.group(1)), float(m.group(2)),
                                       float(m.group(3))]], dtype=np.float32))[0])
        if ink > 0.35:                      # light type on a dark plate
            bg = float(np.percentile(crop, 12))
        else:                               # dark type on paper
            bg = float(np.percentile(crop, 88))
        hi, lo = max(ink, bg), min(ink, bg)
        ratio = (hi + 0.05) / (lo + 0.05)
        size = tb["size"]
        need = 3.0 if size >= 18 else 4.0
        worst = min(worst, ratio)
        if ratio < need:
            problems.append(f"low contrast {ratio:.1f}:1 on {tb['t']!r} "
                            f"({size}px, need {need})")
    worst_label = 99.0
    for tb in svgt or []:
        x0, y0 = int(round(tb["x"])), int(round(tb["y"]))
        x1 = int(round(tb["x"] + tb["w"]))
        y1 = int(round(tb["y"] + tb["h"]))
        crop = lum[max(y0, 0):y1, max(x0, 0):x1]
        rgb = _hex_rgb(tb["fill"])
        if crop.size < 16 or rgb is None:
            continue
        ink = float(_rel_lum(rgb)[0])
        bg = float(np.percentile(crop, 12 if ink > 0.35 else 90))
        ratio = (max(ink, bg) + 0.05) / (min(ink, bg) + 0.05)
        worst_label = min(worst_label, ratio)
        if ratio < 3.0:
            problems.append(f"low contrast {ratio:.1f}:1 on map label {tb['t']!r}")
    print(f"  contrast: worst {worst:.1f}:1 across {len(tboxes)} text blocks, "
          f"{worst_label:.1f}:1 across {len(svgt or [])} in-scene labels")
    return problems


def _fuzzy(token: str, key: str) -> bool:
    if token == key:
        return True
    if len(key) < 5 or abs(len(token) - len(key)) > 2:
        return False
    a, b = token, key
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] <= 2


def ocr_audit(img: Image.Image, path: Path) -> tuple[set[str], list[str]]:
    """Read the page after a 300 px downscale, as a viewer would see it."""
    thumb = img.resize((300, 300), Image.LANCZOS)
    big = thumb.resize((1500, 1500), Image.LANCZOS)
    big.save(path, format="PNG")
    raw = []
    try:
        for psm in ("3", "11"):
            out = subprocess.run(
                ["tesseract", str(path), "-", "--psm", psm, "-l", "eng"],
                capture_output=True, text=True, timeout=120, check=False)
            raw.append(out.stdout)
    except (OSError, subprocess.SubprocessError) as exc:
        return set(), [f"ocr unavailable: {exc}"]
    text = re.sub(r"[^A-Z0-9$%.]+", " ", " ".join(raw).upper())
    return set(text.split()), []


KEY_TOKENS = ["WEDNESDAY", "NOVEMBER", "2026", "IRAN", "GULF", "ANTHROPIC", "$1.5TN",
              "APEC", "PUTIN", "STOCKTAKE", "VENEZUELA", "GAZA", "KERCH",
              "DUFFY", "HOUTHIS", "MILITARY", "STRIKES"]


def encode_jpeg(img: Image.Image, out: Path) -> int:
    """Highest quality in 90..92 that keeps the file inside the size target."""
    from io import BytesIO
    best = None
    for quality in (92, 91, 90):
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality, subsampling=0,
                 optimize=True, progressive=True)
        data = buf.getvalue()
        if best is None or len(data) < len(best[1]):
            best = (quality, data)
        if len(data) <= 348 * 1024:
            best = (quality, data)
            break
    out.write_bytes(best[1])
    return best[0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "entry.png"))
    ap.add_argument("--preview", default="/tmp/news18_300.png")
    ap.add_argument("--html", default="/tmp/news18_poster.html")
    ap.add_argument("--keep-png", default="/tmp/news18_1024.png")
    args = ap.parse_args()

    html_path = Path(args.html)
    html_path.write_text(build_html(), encoding="utf-8")
    png_path = Path(args.keep_png)
    audit = render(html_path, png_path)

    failures = []
    if audit["doc"]["w"] != SIZE or audit["doc"]["h"] != SIZE:
        failures.append(f"document is {audit['doc']['w']}x{audit['doc']['h']}")
    if abs(audit["poster"]["w"] - SIZE) > 0.5 or abs(audit["poster"]["h"] - SIZE) > 0.5:
        failures.append(f"poster is {audit['poster']['w']}x{audit['poster']['h']}")
    mast = audit["header"]["masthead"]
    if mast["lines"] != 1 or mast["rightGap"] < 4:
        failures.append(f"masthead needs one line with room: {mast}")
    if audit["header"]["deck"]["lines"] > 2:
        failures.append(f"deck wraps to {audit['header']['deck']['lines']} lines")
    for p in audit["panels"]:
        if p["overflowX"] > 1 or p["overflowY"] > 1:
            failures.append(f"{p['cls']} overflows x={p['overflowX']} y={p['overflowY']}")
        if p["children"]:
            failures.append(f"{p['cls']} child outside the panel: {p['children']}")
        if p["lines"]["h2"] > 2:
            failures.append(f"{p['cls']} headline runs to {p['lines']['h2']} lines")
        if p["lines"]["sf"] > 3:
            failures.append(f"{p['cls']} standfirst runs to {p['lines']['sf']} lines")
        if p["tagBottom"] > p["panelBottom"] + 0.6:
            failures.append(f"{p['cls']} tag spills past the panel")
    for s in audit["svg"]:
        failures.append(f"svg clipped: {s}")
    for t in audit["text"]:
        if t.get("lines", 0) > 2:
            failures.append(f"{t['text']} runs to {t['lines']} lines")
    for o in audit["overlaps"]:
        failures.append(f"text overlaps: {o['a']!r} / {o['b']!r} ({o['ox']}x{o['oy']})")

    img = Image.open(png_path).convert("RGB")
    if img.size != (SIZE, SIZE):
        failures.append(f"screenshot is {img.size}")

    print("pixel audit:")
    failures += pixel_audit(img, audit["boxes"])
    failures += contrast_audit(img, audit["tboxes"], audit["svgt"])

    out = Path(args.out)
    quality = encode_jpeg(img, out)
    size_kb = out.stat().st_size / 1024

    thumb = img.resize((300, 300), Image.LANCZOS)
    thumb.save(args.preview, format="PNG", optimize=True)
    tokens, errs = ocr_audit(img, Path("/tmp/news18_300_ocr.png"))
    failures += errs
    found = [k for k in KEY_TOKENS if any(_fuzzy(t, k) for t in tokens)]
    print(f"300px ocr: {len(found)}/{len(KEY_TOKENS)} key tokens "
          f"-> {' '.join(found)}")
    month_ok = any(_fuzzy(t, "NOVEMBER") for t in tokens)
    year_ok = any(re.fullmatch(r"20\d\d", t) for t in tokens) or \
        any(_fuzzy(t, "2026") for t in tokens)
    if len(found) < 10 or not (month_ok and year_ok):
        failures.append(f"thumbnail OCR read {len(found)} key tokens "
                        f"(month={month_ok}, year={year_ok}): {found}")

    print(f"entry.png: {img.size[0]}x{img.size[1]} q{quality} {size_kb:.1f} KB")
    if not 235 <= size_kb <= 350:
        print(f"WARN: {size_kb:.1f} KB is outside the 235-350 KB target band")
    for p in audit["panels"]:
        print(f"layout:   {p['cls']:22s} box {p['box']['w']:.0f}x{p['box']['h']:.0f} "
              f"h2={p['lines']['h2']} sf={p['lines']['sf']} "
              f"tagBottom={p['tagBottom']:.0f}/{p['panelBottom']:.0f}")
    if failures:
        print("AUDIT FAILURES:")
        for f in failures:
            print(" -", f)
        return 1
    print("audit:     clean (layout, svg, text, pixels, thumbnail)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
