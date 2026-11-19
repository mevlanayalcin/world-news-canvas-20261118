#!/usr/bin/env python3
"""Build entry.png: a 1024x1024 editorial broadsheet for Wednesday 18 Nov 2026.

The poster is HTML + inline SVG rendered in headless Chrome through Playwright,
then encoded as a 4:4:4 JPEG (quality 92) named entry.png. A 300 px wide preview
is written to /tmp/news18_300.png for the thumbnail legibility check, and the
DOM is audited for overflow / clipped SVG before the JPEG is accepted.

Build-time only. The shipped entrypoint (main.py) is standard-library Python.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
CHROME = "/usr/bin/google-chrome"
SIZE = 1024

# --------------------------------------------------------------------------- #
# Palette
# --------------------------------------------------------------------------- #
PAPER = "#F5F1E6"
INK = "#171A1F"
INK_SOFT = "#4A4438"
CRIMSON = "#9E1B1B"
CRIMSON_DARK = "#771313"
NAVY = "#101E2E"
GOLD = "#D8A94B"
HAIR = "#D8CBB2"

REGION = {
    "me": "#A2262B",
    "am": "#1F4E79",
    "ap": "#0E6B5E",
    "eu": "#5A3A78",
    "cl": "#4C6B2F",
    "te": "#3B4750",
}


# --------------------------------------------------------------------------- #
# SVG artwork
# --------------------------------------------------------------------------- #
def _star(cx: float, cy: float, r: float, fill: str) -> str:
    """A compact 8-point burst, drawn from four crossing spikes."""
    d = (
        f"M{cx},{cy - r} L{cx + r * 0.26},{cy - r * 0.26} L{cx + r},{cy} "
        f"L{cx + r * 0.26},{cy + r * 0.26} L{cx},{cy + r} "
        f"L{cx - r * 0.26},{cy + r * 0.26} L{cx - r},{cy} "
        f"L{cx - r * 0.26},{cy - r * 0.26} Z"
    )
    return f'<path d="{d}" fill="{fill}"/>'


def art_gulf() -> str:
    """Persian Gulf map: Qeshm strike, Bahrain radar, Ali Al Salem base."""
    return f"""
<svg class="art map" viewBox="0 0 628 130" role="img"
     aria-label="Map of the Persian Gulf showing a US strike on Qeshm Island, drone paths to Bahrain and Kuwait, and shipping at the Strait of Hormuz.">
  <defs>
    <linearGradient id="sea" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#193B52"/><stop offset="1" stop-color="#0D2231"/>
    </linearGradient>
    <marker id="arw" viewBox="0 0 8 8" refX="6.4" refY="4" markerWidth="5.4" markerHeight="5.4" orient="auto">
      <path d="M0,0.6 L7.2,4 L0,7.4 Z" fill="#F2765F"/>
    </marker>
  </defs>
  <rect x="0" y="0" width="628" height="130" fill="url(#sea)"/>
  <g stroke="#8FB6CC" stroke-width="0.6" opacity="0.12">
    <path d="M104,0 V130 M208,0 V130 M312,0 V130 M416,0 V130 M520,0 V130"/>
    <path d="M0,44 H628 M0,88 H628"/>
  </g>

  <!-- Arabian peninsula -->
  <path d="M0,52 L40,56 L92,61 L140,67 L186,75 L222,83 L252,89 L286,95 L318,101 L346,111 L372,124 L382,130 L0,130 Z"
        fill="#C8AD7A"/>
  <!-- Qatar -->
  <path d="M276,96 L282,77 L294,79 L300,98 Z" fill="#C8AD7A"/>
  <!-- Musandam -->
  <path d="M468,130 L488,119 L506,107 L522,112 L538,130 Z" fill="#C8AD7A"/>
  <!-- Iran -->
  <path d="M148,0 L628,0 L628,34 L560,42 L520,56 L488,72 L462,85 L438,88 L414,80 L388,70 L360,58 L330,44 L300,30 L268,16 L232,4 L190,0 Z"
        fill="#C8AD7A"/>
  <!-- Qeshm island -->
  <path d="M434,96 q14,-7 29,-3 q9,2 5,7 q-12,6 -28,4 q-10,-2 -6,-8 Z" fill="#B99B6B"/>

  <g font-family="Lato, sans-serif" font-size="7.4" letter-spacing="1.5" fill="#2A2C26" opacity="0.9">
    <text x="298" y="20">IRAN</text>
    <text x="94" y="104">SAUDI ARABIA</text>
    <text x="18" y="70">KUWAIT</text>
    <text x="334" y="116">UAE</text>
    <text x="246" y="110" font-size="6.4">QATAR</text>
  </g>
  <g font-family="Lato, sans-serif" font-size="7.4" letter-spacing="1.5" fill="#9CC0D6" opacity="0.85">
    <text x="250" y="72" transform="rotate(-8 250 72)">PERSIAN GULF</text>
    <text x="506" y="103" font-size="6.4">GULF OF OMAN</text>
  </g>

  <!-- strike paths from Iran -->
  <path d="M404,78 Q318,52 228,72" fill="none" stroke="#F2765F" stroke-width="1.7"
        stroke-dasharray="5 3" marker-end="url(#arw)"/>
  <path d="M434,86 Q268,26 106,56" fill="none" stroke="#F2765F" stroke-width="1.7"
        stroke-dasharray="5 3" marker-end="url(#arw)"/>

  <!-- Bahrain radar -->
  <g transform="translate(214,76)">
    <path d="M-7,6 q7,-11 14,0" fill="none" stroke="#F4E6C8" stroke-width="1.3"/>
    <path d="M-4,6 q4,-7 8,0" fill="none" stroke="#F4E6C8" stroke-width="1.3"/>
    <path d="M0,7 V12 M-5,12 H5" stroke="#F4E6C8" stroke-width="1.2"/>
    <circle cx="0" cy="6" r="1" fill="#F4E6C8"/>
    <text x="13" y="15" font-family="Lato, sans-serif" font-size="6.2" letter-spacing="1" fill="#F4E6C8">BAHRAIN</text>
  </g>

  <!-- Ali Al Salem base -->
  <g transform="translate(100,58)">
    <path d="M-6,4 L-3,-5 L3,-5 L6,4 Z" fill="none" stroke="#F4E6C8" stroke-width="1.2"/>
    <circle cx="0" cy="0" r="1.2" fill="#F4E6C8"/>
    <text x="10" y="9" font-family="Lato, sans-serif" font-size="6.2" letter-spacing="0.8" fill="#F4E6C8">ALI AL SALEM</text>
  </g>

  <!-- Qeshm strike -->
  {_star(452, 96, 7.5, "#E8443A")}
  {_star(452, 96, 3.0, "#FFE9C4")}
  <text x="404" y="124" font-family="Lato, sans-serif" font-size="7" font-weight="700" letter-spacing="1" fill="#FF9C86">QESHM · US STRIKE</text>
  <text x="466" y="82" font-family="Lato, sans-serif" font-size="6.2" letter-spacing="1" fill="#F4E6C8">QESHM I.</text>

  <!-- tanker at Hormuz -->
  <g transform="translate(506,80)">
    <path d="M-10,0 H9 L13,5 H-14 Z" fill="#F0E3C6"/>
    <rect x="-5" y="-4.5" width="11" height="4" fill="#D8A94B"/>
    <path d="M-14,6 H14" stroke="#8FB6CC" stroke-width="1" opacity="0.6"/>
    <text x="20" y="4" font-family="Lato, sans-serif" font-size="6" letter-spacing="0.8" fill="#F4E6C8">HORMUZ</text>
  </g>

  <!-- legend -->
  <rect x="8" y="6" width="252" height="16" rx="1.5" fill="#0A1A26" opacity="0.78"/>
  <g font-family="Lato, sans-serif" font-size="6.6" letter-spacing="0.9" fill="#D6E4EE">
    <circle cx="18" cy="14" r="3" fill="#E8443A"/>
    <text x="26" y="16.4">STRIKE</text>
    <path d="M64,14 H84" stroke="#F2765F" stroke-width="1.6" stroke-dasharray="4 2.6"/>
    <text x="90" y="16.4">DRONE / MISSILE</text>
    <path d="M162,14 h8 M166,10 v8" stroke="#F4E6C8" stroke-width="1.1"/>
    <text x="176" y="16.4">US POSITION</text>
  </g>

  <!-- scale and compass -->
  <g stroke="#5A4A2E" stroke-width="0.9" fill="none" opacity="0.9">
    <path d="M16,116 H64 M16,112 V120 M40,113.5 V118.5 M64,112 V120"/>
    <path d="M598,12 V26 M594,16 L598,12 L602,16"/>
  </g>
  <g font-family="Lato, sans-serif" fill="#5A4A2E" opacity="0.9">
    <text x="70" y="118.5" font-size="6">300 km</text>
    <text x="594.5" y="10" font-size="5.6">N</text>
  </g>
</svg>
"""


def art_ipo() -> str:
    """Nasdaq candles climbing to the $83 offer price."""
    candles = []
    steps = [0.26, 0.34, 0.31, 0.46, 0.55, 0.63, 0.72]
    for i, level in enumerate(steps):
        x = 26 + i * 37
        body = 12 + (i % 3) * 4
        top = 96 - level * 100
        color = CRIMSON if i == len(steps) - 1 else "#21507B"
        candles.append(
            f'<path d="M{x},{top - 6} V{top + body + 6}" stroke="{color}" stroke-width="1.2"/>'
            f'<rect x="{x - 4}" y="{top}" width="8" height="{body}" fill="{color}"/>'
        )
    return f"""
<svg class="art" viewBox="0 0 294 108" role="img"
     aria-label="Candlestick chart rising to the $83 initial public offering price.">
  <g stroke="#E3D7C0" stroke-width="0.8" stroke-dasharray="2 3">
    <path d="M14,24 H280 M14,50 H280 M14,76 H280"/>
  </g>
  <path d="M14,102 H280" stroke="#C9B99B" stroke-width="1"/>
  <path d="M22,94 C90,86 150,58 246,28" stroke="#D8A94B" stroke-width="1.4" fill="none" stroke-dasharray="1 4"/>
  {''.join(candles)}
  <g font-family="Lato, sans-serif" fill="#6B5F49">
    <text x="14" y="15" font-size="6.4" letter-spacing="1.2">VALUATION ON DEBUT</text>
    <text x="14" y="100" font-size="6.2" letter-spacing="1">18 NOV</text>
    <text x="238" y="100" font-size="6.2" letter-spacing="1">NASDAQ</text>
    <g>
      <rect x="238" y="6" width="42" height="13" fill="#F3E8D2" stroke="#DCCBA9" stroke-width="0.7"/>
      <text x="242" y="15.4" font-size="7.4" font-weight="700" fill="{CRIMSON}">$83 IPO</text>
    </g>
  </g>
</svg>
"""


def art_apec() -> str:
    """Shenzhen skyline with three summit flags."""
    windows = []
    for x, y0, y1, w in [(14, 60, 90, 18), (32, 50, 90, 14), (50, 66, 90, 12),
                          (100, 54, 90, 16), (118, 40, 90, 12), (132, 60, 90, 10),
                          (174, 52, 90, 14), (190, 44, 90, 10), (206, 58, 90, 16),
                          (224, 36, 90, 14), (242, 50, 90, 12), (258, 62, 90, 14),
                          (276, 54, 90, 12)]:
        windows.append(f'<rect x="{x}" y="{y0}" width="{w}" height="{y1 - y0}" fill="#1B3B4F"/>')
    for x, y in [(18, 66), (22, 76), (36, 56), (40, 68), (104, 60), (122, 48),
                 (178, 58), (182, 72), (210, 66), (228, 44), (232, 60),
                 (246, 58), (262, 70), (280, 62)]:
        windows.append(f'<rect x="{x}" y="{y}" width="2.4" height="2.4" fill="#F1D49A"/>')
    return f"""
<svg class="art" viewBox="0 0 298 95" role="img"
     aria-label="Shenzhen skyline with US, Chinese and Russian flags marking the three-way summit.">
  <circle cx="102" cy="15" r="9" fill="#E9D9B2"/>
  {''.join(windows)}
  <!-- Ping An tower -->
  <path d="M204,90 L207,36 L212,21 L217,36 L220,90 Z" fill="#122E3E"/>
  <path d="M212,21 V12" stroke="#122E3E" stroke-width="1.2"/>
  <path d="M96,90 V44 h4 V90" fill="#122E3E"/>
  <path d="M0,90 H298" stroke="#122E3E" stroke-width="1.4"/>
  <g font-family="Lato, sans-serif" font-size="6.6" font-weight="700" fill="#4A4438">
    <g transform="translate(28,0)">
      <path d="M0,4 V44" stroke="#6B6250" stroke-width="1"/>
      <rect x="0" y="4" width="26" height="18" fill="#1F4E79"/>
      <g fill="#F5F1E6"><rect x="1" y="6" width="10" height="1.5"/><rect x="1" y="8.8" width="10" height="1.5"/><rect x="1" y="11.6" width="10" height="1.5"/><rect x="1" y="14.4" width="10" height="1.5"/><rect x="1" y="17.2" width="10" height="1.5"/></g>
      <text x="0" y="33">US</text>
    </g>
    <g transform="translate(136,0)">
      <path d="M0,4 V44" stroke="#6B6250" stroke-width="1"/>
      <rect x="0" y="4" width="26" height="18" fill="#C8102E"/>
      {_star(7, 11, 3.2, "#F5D34E")}
      <text x="0" y="33">CHINA</text>
    </g>
    <g transform="translate(244,0)">
      <path d="M0,4 V44" stroke="#6B6250" stroke-width="1"/>
      <rect x="0" y="4" width="26" height="18" fill="#F5F1E6" stroke="#CFC2A8" stroke-width="0.6"/>
      <rect x="0" y="10" width="26" height="6" fill="#1F4E79"/>
      <rect x="0" y="16" width="26" height="6" fill="#C8102E"/>
      <text x="0" y="33">RUSSIA</text>
    </g>
  </g>
</svg>
"""


def art_cop31() -> str:
    """Globe, 1.5C thermometer, and a draft with the phase-out line cut."""
    return f"""
<svg class="art" viewBox="0 0 298 95" role="img"
     aria-label="Globe and 1.5 degree thermometer beside the COP31 draft, where the fossil fuel phase-out line is struck out.">
  <circle cx="52" cy="48" r="32" fill="#DCE6D5"/>
  <g fill="none" stroke="#7E9472" stroke-width="0.8" opacity="0.9">
    <ellipse cx="52" cy="48" rx="12" ry="32"/>
    <ellipse cx="52" cy="48" rx="23" ry="32"/>
    <path d="M20,48 H84 M25,32 H79 M25,64 H79"/>
  </g>
  <path d="M38,29 q8,-7 16,0 q6,6 -1,10 q-4,3 -2,9 q-10,1 -12,-6 q-1,-8 -1,-13 Z" fill="#9DB292"/>
  <path d="M63,53 q9,-3 13,4 q-3,8 -12,5 q-6,-4 -1,-9 Z" fill="#9DB292"/>

  <!-- thermometer -->
  <rect x="92" y="10" width="9" height="54" rx="4.5" fill="#FBF7EC" stroke="#B9A98A" stroke-width="1"/>
  <rect x="94" y="34" width="5" height="30" fill="#C43A2E"/>
  <circle cx="96.5" cy="71" r="7.5" fill="#C43A2E"/>
  <path d="M105,28 H113" stroke="{CRIMSON}" stroke-width="1"/>
  <text x="115" y="30.5" font-family="Lato, sans-serif" font-size="7" font-weight="700" fill="{CRIMSON}">1.5°C</text>

  <!-- draft document -->
  <rect x="138" y="6" width="152" height="82" fill="#FFFDF5" stroke="#DCCCAC" stroke-width="1"/>
  <rect x="138" y="6" width="152" height="10" fill="#E8DFC8"/>
  <text x="144" y="13.2" font-family="Lato, sans-serif" font-size="6.2" font-weight="700" letter-spacing="0.9" fill="#6B6250">COP31 DRAFT · STOCKTAKE II</text>
  <g stroke="#CFC3AA" stroke-width="2.2" stroke-linecap="round">
    <path d="M146,26 H274 M146,34 H258"/>
  </g>
  <text x="146" y="45" font-family="Lato, sans-serif" font-size="7.2" fill="#4A4438">FOSSIL PHASE-OUT</text>
  <path d="M144,43.5 H226" stroke="{CRIMSON}" stroke-width="2.2"/>
  <text x="146" y="58" font-family="Lato, sans-serif" font-size="7.2" fill="#4A4438">ADAPTATION FUNDING</text>
  <rect x="144" y="51.5" width="80" height="8" fill="#E7C25E" opacity="0.55"/>
  <g stroke="#CFC3AA" stroke-width="2.2" stroke-linecap="round">
    <path d="M146,67 H266 M146,74 H240"/>
  </g>
  <text x="268" y="84" font-family="Lato, sans-serif" font-size="6" fill="#8A7C62">p.4</text>
</svg>
"""


def art_caracas() -> str:
    """US and Venezuelan flags joined by a gold link."""
    us_stripes = "".join(
        f'<rect x="64" y="{18 + i * 6.6}" width="72" height="6.6" fill="{"#B22234" if i % 2 == 0 else "#F7F4EA"}"/>'
        for i in range(7)
    )
    return f"""
<svg class="art" viewBox="0 0 298 95" role="img"
     aria-label="The flags of the United States and Venezuela linked by a gold chain, marking restored military ties.">
  <g transform="rotate(-3 100 44)">
    <path d="M62,10 V88" stroke="#6B6250" stroke-width="1.6"/>
    {us_stripes}
    <rect x="64" y="18" width="33" height="20" fill="#1F3A6E"/>
    <g fill="#F7F4EA">
      <circle cx="70" cy="23.5" r="1.1"/><circle cx="77" cy="23.5" r="1.1"/><circle cx="84" cy="23.5" r="1.1"/>
      <circle cx="73.5" cy="29" r="1.1"/><circle cx="80.5" cy="29" r="1.1"/>
      <circle cx="70" cy="34.5" r="1.1"/><circle cx="77" cy="34.5" r="1.1"/><circle cx="84" cy="34.5" r="1.1"/>
    </g>
    <rect x="64" y="18" width="72" height="46.2" fill="none" stroke="#C9B99B" stroke-width="0.8"/>
  </g>
  <g transform="rotate(3 198 44)">
    <path d="M238,10 V88" stroke="#6B6250" stroke-width="1.6"/>
    <rect x="166" y="18" width="72" height="15.4" fill="#F2C300"/>
    <rect x="166" y="33.4" width="72" height="15.4" fill="#16336B"/>
    <rect x="166" y="48.8" width="72" height="15.4" fill="#C8102E"/>
    <g fill="#FFFFFF">
      <circle cx="180" cy="42" r="1"/><circle cx="187" cy="39" r="1"/><circle cx="194" cy="36.8" r="1"/>
      <circle cx="202" cy="36.4" r="1"/><circle cx="210" cy="37.4" r="1"/><circle cx="217" cy="39.2" r="1"/>
      <circle cx="224" cy="42" r="1"/><circle cx="231" cy="41" r="1"/>
    </g>
    <rect x="166" y="18" width="72" height="46.2" fill="none" stroke="#C9B99B" stroke-width="0.8"/>
  </g>
  <g transform="translate(149,44)">
    <rect x="-9" y="-5" width="18" height="10" rx="5" fill="none" stroke="{GOLD}" stroke-width="2.4" transform="rotate(-35)"/>
    <rect x="-9" y="-5" width="18" height="10" rx="5" fill="none" stroke="{GOLD}" stroke-width="2.4" transform="rotate(35)"/>
  </g>
  <g font-family="Lato, sans-serif" font-size="6.2" letter-spacing="1.2" fill="#6B5F49">
    <text x="62" y="92">UNITED STATES</text>
    <text x="196" y="92">VENEZUELA</text>
  </g>
</svg>
"""


def art_gaza() -> str:
    """Security Council horseshoe beside the 12-page Board of Peace report."""
    seats = []
    for i in range(15):
        angle = math.radians(160 + (220 / 14) * i)
        x = 164 + 38 * math.cos(angle)
        y = 52 + 34 * math.sin(angle)
        seats.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.3" fill="#2E5C8A"/>')
    return f"""
<svg class="art" viewBox="0 0 218 89" role="img"
     aria-label="UN Security Council horseshoe table beside a 12-page report on Gaza.">
  <g>
    <rect x="12" y="10" width="94" height="68" fill="#FFFDF5" stroke="#DCCCAC" stroke-width="1"/>
    <rect x="12" y="10" width="94" height="10" fill="#2E5C8A"/>
    <text x="17" y="17" font-family="Lato, sans-serif" font-size="5.4" font-weight="700" letter-spacing="0.6" fill="#F5F1E6">BOARD OF PEACE</text>
    <text x="92" y="17" text-anchor="end" font-family="Lato, sans-serif" font-size="5.4" font-weight="700" fill="#F5F1E6">12 PP.</text>
    <g stroke="#CFC3AA" stroke-width="1.7" stroke-linecap="round">
      <path d="M19,27 H99 M19,34 H92 M19,41 H99 M19,48 H88 M19,55 H99 M19,62 H76"/>
    </g>
    <circle cx="93" cy="66" r="5.4" fill="none" stroke="{CRIMSON}" stroke-width="1.2"/>
    <path d="M90.4,66 l2,2.2 l3.6,-4.2" fill="none" stroke="{CRIMSON}" stroke-width="1.2"/>
  </g>
  <g>
    <path d="M131,62 A35,40 0 1 1 197,62" fill="none" stroke="#2E5C8A" stroke-width="6" stroke-linecap="round"/>
    <path d="M137,60 A30,34 0 1 1 191,60" fill="none" stroke="#7FA3C4" stroke-width="0.9"/>
    {''.join(seats)}
    <text x="164" y="11" text-anchor="middle" font-family="Lato, sans-serif" font-size="6" font-weight="700" letter-spacing="1.2" fill="#2E5C8A">UNSC</text>
    <text x="164" y="87" text-anchor="middle" font-family="Lato, sans-serif" font-size="5.4" letter-spacing="0.8" fill="#6B5F49">15 MEMBERS</text>
  </g>
</svg>
"""


def art_kerch() -> str:
    """Kerch Bridge still framed as a video, stamped debunked."""
    return f"""
<svg class="art" viewBox="0 0 218 89" role="img"
     aria-label="A video still of the Kerch Bridge stamped debunked by fact-checkers.">
  <rect x="0" y="56" width="218" height="34" fill="#D6E3E8"/>
  <g stroke="#A9C2CC" stroke-width="0.8" opacity="0.9">
    <path d="M6,64 q8,-4 16,0 t16,0 t16,0 t16,0 t16,0 t16,0 t16,0 t16,0 t16,0 t16,0 t16,0 t16,0"/>
    <path d="M0,78 q8,-4 16,0 t16,0 t16,0 t16,0 t16,0 t16,0 t16,0 t16,0 t16,0 t16,0 t16,0 t16,0"/>
  </g>
  <g>
    <path d="M40,48 H208" stroke="#48545E" stroke-width="4"/>
    <path d="M58,48 q16,-20 34,0" fill="none" stroke="#48545E" stroke-width="2.8"/>
    <path d="M118,48 q16,-20 34,0" fill="none" stroke="#48545E" stroke-width="2.8"/>
    <g stroke="#48545E" stroke-width="2.2">
      <path d="M52,48 V60 M92,48 V60 M112,48 V60 M152,48 V60 M204,48 V62"/>
    </g>
    <path d="M40,14 H208" stroke="#8B9AA4" stroke-width="0.6" stroke-dasharray="2 2"/>
    <rect x="96" y="43" width="10" height="5" rx="1" fill="#6B5F49"/>
  </g>
  <g>
    <rect x="8" y="6" width="80" height="50" rx="2" fill="#0E1B26"/>
    <rect x="8" y="6" width="80" height="50" rx="2" fill="none" stroke="#F2765F" stroke-width="1" stroke-dasharray="3 2"/>
    <path d="M38,21 L38,41 L54,31 Z" fill="#F5F1E6"/>
    <text x="12" y="50" font-family="Lato, sans-serif" font-size="5" letter-spacing="0.8" fill="#9CC0D6">CLIP · 0:14</text>
    <g transform="rotate(-12 48 31)">
      <rect x="10" y="26" width="72" height="11" fill="{CRIMSON}"/>
      <text x="14" y="34.2" font-family="Lato, sans-serif" font-size="8" font-weight="700" letter-spacing="1.3" fill="#FFF8E6">DEBUNKED</text>
    </g>
  </g>
  <g transform="translate(94,8)">
    <rect x="0" y="0" width="16" height="12" rx="1.4" fill="none" stroke="#6B5F49" stroke-width="1"/>
    <text x="3.2" y="8.6" font-family="Lato, sans-serif" font-size="5.6" font-weight="700" fill="#6B5F49">AI</text>
    <g stroke="#6B5F49" stroke-width="0.9">
      <path d="M4,0 V-3 M8,0 V-3 M12,0 V-3 M4,12 V15 M8,12 V15 M12,12 V15 M0,4 H-3 M0,8 H-3 M16,4 H19 M16,8 H19"/>
    </g>
  </g>
  <text x="14" y="86" font-family="Lato, sans-serif" font-size="5.4" letter-spacing="1" fill="#3F5C68">KERCH BRIDGE · CRIMEA</text>
</svg>
"""


def art_duffy() -> str:
    """Grounded airliner, control tower, warning marker."""
    return f"""
<svg class="art" viewBox="0 0 218 89" role="img"
     aria-label="A grounded airliner beside a control tower and a warning marker.">
  <path d="M0,78 H218" stroke="#B7A98E" stroke-width="1"/>
  <path d="M0,86 H218" stroke="#D3C6AC" stroke-width="0.8" stroke-dasharray="9 7"/>
  <g>
    <path d="M18,56 q6,-8 16,-8 h50 l18,-3 l5,5 l-8,7 H40 q-13,0 -22,-1 Z" fill="#1F3A4D"/>
    <path d="M34,48 L24,26 L33,26 L47,48 Z" fill="#1F3A4D"/>
    <path d="M58,56 L50,74 H59 L72,56 Z" fill="#1F3A4D"/>
    <path d="M90,55 L97,74 H102 L99,55 Z" fill="#1F3A4D"/>
    <g fill="#E9DFC8"><circle cx="46" cy="51" r="1.2"/><circle cx="52" cy="51" r="1.2"/><circle cx="58" cy="51" r="1.2"/><circle cx="64" cy="51" r="1.2"/><circle cx="70" cy="51" r="1.2"/></g>
  </g>
  <g>
    <rect x="150" y="36" width="26" height="42" fill="#E8DFC8" stroke="#6B5F49" stroke-width="1"/>
    <path d="M144,36 L150,25 H176 L182,36 Z" fill="#6B5F49"/>
    <rect x="150" y="28" width="26" height="5" fill="#A8C4CE"/>
    <path d="M163,25 V17" stroke="#6B5F49" stroke-width="1.2"/>
    <path d="M163,17 h8" stroke="{CRIMSON}" stroke-width="1.2"/>
    <path d="M152,44 H174 M152,56 H174" stroke="#C9B99B" stroke-width="1"/>
  </g>
  <g transform="translate(196,62)">
    <path d="M0,-9 L8,5 H-8 Z" fill="{CRIMSON}"/>
    <text x="-1.5" y="3" font-family="Lato, sans-serif" font-size="7" font-weight="700" fill="#FFF8E6">!</text>
  </g>
  <text x="18" y="86" font-family="Lato, sans-serif" font-size="5.8" font-weight="700" letter-spacing="1.2" fill="{CRIMSON}">GROUNDED · NATIONWIDE</text>
</svg>
"""


def art_houthi() -> str:
    """East-West pipeline across the peninsula, drone path, pumping stations."""
    return f"""
<svg class="art" viewBox="0 0 218 89" role="img"
     aria-label="Saudi Arabia's East-West oil pipeline with pumping stations, a drone and a strike marker.">
  <path d="M0,90 V26 L34,22 L70,28 L104,24 L140,30 L176,26 L218,30 V90 Z" fill="#E6D4A9"/>
  <g stroke="#C9B589" stroke-width="0.7" opacity="0.8">
    <path d="M0,44 H218 M0,68 H218"/>
  </g>
  <path d="M200,54 H24" stroke="#B26A2E" stroke-width="3.6"/>
  <path d="M200,54 H24" stroke="#E8A35C" stroke-width="1.2" stroke-dasharray="5 3"/>
  <g fill="#7A4A1E">
    <rect x="28" y="50.4" width="7" height="7.2" rx="1"/>
    <rect x="92" y="50.4" width="7" height="7.2" rx="1"/>
    <rect x="156" y="50.4" width="7" height="7.2" rx="1"/>
  </g>
  {_star(102, 52, 6.4, "#D2402F")}
  <g font-family="Lato, sans-serif" font-size="5.4" letter-spacing="0.8" fill="#6B5A3A">
    <text x="6" y="46">YANBU</text>
    <text x="180" y="46">ABQAIQ</text>
    <text x="86" y="70">RIYADH</text>
    <circle cx="82" cy="73" r="1.3" fill="#6B5A3A"/>
  </g>
  <text x="60" y="87" font-family="Lato, sans-serif" font-size="5.6" letter-spacing="1.1" fill="#6B5A3A">EAST–WEST PIPELINE</text>
  <g transform="translate(148,16)">
    <path d="M0,0 L16,10 M16,0 L0,10" stroke="#3B4750" stroke-width="1.2"/>
    <circle cx="0" cy="0" r="3" fill="none" stroke="#3B4750" stroke-width="1.1"/>
    <circle cx="16" cy="0" r="3" fill="none" stroke="#3B4750" stroke-width="1.1"/>
    <circle cx="0" cy="10" r="3" fill="none" stroke="#3B4750" stroke-width="1.1"/>
    <circle cx="16" cy="10" r="3" fill="none" stroke="#3B4750" stroke-width="1.1"/>
    <rect x="6" y="3.4" width="4" height="3.2" fill="#3B4750"/>
    <path d="M12,14 Q16,28 14,40" fill="none" stroke="{CRIMSON}" stroke-width="1" stroke-dasharray="2 2"/>
  </g>
</svg>
"""


def wire_icon_tfl() -> str:
    return f"""
<svg class="wicon" viewBox="0 0 26 26" aria-hidden="true">
  <circle cx="13" cy="13" r="9.5" fill="none" stroke="{CRIMSON}" stroke-width="2.6"/>
  <rect x="4" y="11" width="18" height="4" fill="{CRIMSON}"/>
</svg>
"""


def wire_icon_chip() -> str:
    return """
<svg class="wicon" viewBox="0 0 26 26" aria-hidden="true">
  <rect x="7" y="7" width="12" height="12" rx="1.6" fill="none" stroke="#3B4750" stroke-width="1.6"/>
  <g stroke="#3B4750" stroke-width="1.3">
    <path d="M10,7 V3 M13,7 V3 M16,7 V3 M10,19 V23 M13,19 V23 M16,19 V23 M7,10 H3 M7,13 H3 M7,16 H3 M19,10 H23 M19,13 H23 M19,16 H23"/>
  </g>
  <path d="M10.5,15.5 V10.5 L13,13 L15.5,10.5 V15.5" fill="none" stroke="#3B4750" stroke-width="1.4"/>
</svg>
"""


def wire_icon_un() -> str:
    return f"""
<svg class="wicon" viewBox="0 0 26 26" aria-hidden="true">
  <circle cx="13" cy="13" r="9.5" fill="none" stroke="#2E5C8A" stroke-width="1.4"/>
  <g stroke="#2E5C8A" stroke-width="0.8" opacity="0.85">
    <path d="M13,3.5 V22.5 M3.5,13 H22.5 M6,6 L20,20 M20,6 L6,20"/>
  </g>
  <path d="M8,18 V13 M13,18 V9 M18,18 V11" stroke="{CRIMSON}" stroke-width="2.1" stroke-linecap="round"/>
</svg>
"""


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #
def _panel(kind: str, region: str, kicker: str, headline: str,
           standfirst: str, art: str, num: str) -> str:
    return f"""
<section class="panel {kind}" style="--rc:{REGION[region]}">
  <div class="kick"><span class="chip"></span>{kicker}<span class="num">{num}</span></div>
  <h2>{headline}</h2>
  <p class="sf">{standfirst}</p>
  {art}
</section>"""


def build_html() -> str:
    hero = f"""
<section class="panel hero">
  <div class="kick"><span class="chip"></span>PERSIAN GULF · CONFLICT<span class="num">01</span></div>
  <h2>US AND IRAN TRADE STRIKES<br>ACROSS THE PERSIAN GULF</h2>
  <p class="sf">The US strikes an Iranian missile launch site on Qeshm Island; drones hit a US radar in Bahrain; Iran retaliates against Bahrain and Kuwait's Ali Al Salem Air Base.</p>
  {art_gulf()}
</section>"""

    ipo = f"""
<section class="panel ipo" style="--rc:{REGION['am']}">
  <div class="kick"><span class="chip"></span>NEW YORK · MARKETS &amp; AI<span class="num">02</span></div>
  <h2>ANTHROPIC VALUED<br>AT $1.5tn IN IPO</h2>
  <p class="sf">The AI company set its offer at $83 a share, valuing it near $1.5 trillion ahead of its Nasdaq debut.</p>
  <div class="stats">
    <div><b>$83</b><span>per share</span></div>
    <div><b>$1.5tn</b><span>valuation</span></div>
  </div>
  {art_ipo()}
</section>"""

    row2 = "".join([
        _panel("m", "ap", "SHENZHEN · DIPLOMACY", "APEC SUMMIT SETS UP<br>TRUMP–XI–PUTIN TALKS",
               "Leaders gather for the APEC summit, with security, trade and nuclear risk on the table.",
               art_apec(), "03"),
        _panel("m", "cl", "ANTALYA · CLIMATE", "COP31 STOCKTAKE<br>DEADLOCKS",
               "A mid-week draft drops fossil-fuel phase-out language; vulnerable nations press on adaptation funding.",
               art_cop31(), "04"),
        _panel("m", "am", "CARACAS · DIPLOMACY", "US AND VENEZUELA<br>MOVE TO RESTORE TIES",
               "Defense officials led by Pete Hegseth announce a deal to re-establish formal military relations.",
               art_caracas(), "05"),
    ])

    row3 = "".join([
        _panel("s", "me", "UNITED NATIONS · GAZA", "GAZA REPORT<br>FAULTS BOTH SIDES",
               "A 12-page Board of Peace report says Israel and Hamas failed to keep ceasefire commitments.",
               art_gaza(), "06"),
        _panel("s", "eu", "KYIV · INFORMATION", "KERCH CLIPS<br>DEBUNKED",
               "Fact-checkers say viral AI deepfakes exaggerated damage to the Kerch Bridge.",
               art_kerch(), "07"),
        _panel("s", "am", "WASHINGTON · AVIATION", "DUFFY GRILLED<br>ON GROUNDINGS",
               "The transportation secretary faces a Capitol Hill grilling on nationwide groundings.",
               art_duffy(), "08"),
        _panel("s", "me", "RIYADH · ENERGY", "HOUTHIS TARGET<br>SAUDI PIPELINE",
               "The Yemeni group claims drone attacks on pumping stations on the East–West line near Riyadh.",
               art_houthi(), "09"),
    ])

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>The World Today — Wednesday 18 November 2026</title>
<style>
  @page {{ size: 1024px 1024px; margin: 0; }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; background: {PAPER}; }}
  body {{ width: {SIZE}px; height: {SIZE}px; overflow: hidden; }}
  .poster {{
    position: relative; width: {SIZE}px; height: {SIZE}px; padding: 12px 20px 10px;
    background: {PAPER};
    color: {INK};
    font-family: "Lato", "Noto Sans", sans-serif;
    display: flex; flex-direction: column;
    -webkit-font-smoothing: antialiased;
  }}
  .poster::after {{
    content: ""; position: absolute; inset: 0; pointer-events: none;
    box-shadow: inset 0 0 0 1px rgba(23,26,31,0.16);
  }}
  .rule {{ height: 5px; background: {CRIMSON}; flex: none; }}
  .rail {{
    display: flex; align-items: center; justify-content: space-between;
    height: 21px; font-size: 9.4px; font-weight: 700; letter-spacing: 1.7px;
    color: {CRIMSON_DARK}; text-transform: uppercase; flex: none;
  }}
  .rail .mid {{ color: #6F6553; font-weight: 700; letter-spacing: 2.1px; }}
  .hair {{ height: 1px; background: {HAIR}; flex: none; }}
  h1 {{
    margin: 6px 0 0; font-family: "Noto Serif", Georgia, serif; font-weight: 700;
    font-size: 57px; line-height: 1.0; letter-spacing: -1.9px; white-space: nowrap;
  }}
  h1 .day {{ color: {CRIMSON}; }}
  h1 .sep {{ color: {GOLD}; padding: 0 6px; }}
  .deck {{
    margin: 6px 0 0; font-size: 14.8px; line-height: 1.34; color: #352F26;
    max-width: 930px; letter-spacing: 0.05px;
  }}
  .deck em {{ font-style: normal; font-weight: 700; color: {CRIMSON_DARK}; }}
  .strip {{
    margin-top: 8px; display: flex; border-top: 1px solid {HAIR};
    border-bottom: 1px solid {HAIR}; flex: none; height: 25px;
  }}
  .strip div {{
    flex: 1; display: flex; align-items: center; gap: 7px; height: 100%;
    padding: 0 9px 0 0; font-size: 9.6px; font-weight: 700; letter-spacing: 1.35px;
    color: #3B342A; text-transform: uppercase; white-space: nowrap;
  }}
  .strip div + div {{ border-left: 1px solid {HAIR}; padding-left: 9px; }}
  .strip i {{ width: 7px; height: 7px; display: inline-block; flex: none; }}
  .strip b {{ margin-left: auto; font-family: "Noto Serif", Georgia, serif;
              font-size: 10.5px; font-weight: 700; color: #6F6553; }}

  .sheet {{ margin-top: 10px; display: flex; flex-direction: column; gap: 8px; }}
  .row {{ display: flex; gap: 8px; }}
  .row1 {{ height: 300px; }}
  .row2 {{ height: 222px; }}
  .row3 {{ height: 204px; }}

  .panel {{
    position: relative; background: transparent; border: 1px solid #D8CBB2;
    padding: 13px; display: flex; flex-direction: column; min-width: 0;
  }}
  .panel::before {{
    content: ""; position: absolute; left: 0; right: 0; top: 0; height: 4px;
    background: var(--rc); z-index: 1;
  }}
  .hero {{
    flex: 0 0 656px; background: {NAVY}; border-color: #1B3044; color: #F7F2E4;
    padding: 14px 14px 12px; --rc: #C0392B !important;
  }}
  .ipo {{ flex: 1 1 auto; }}
  .row2 .panel {{ flex: 1 1 0; padding: 12px; }}
  .row3 .panel {{ flex: 1 1 0; padding: 11px; }}

  .kick {{
    display: flex; align-items: center; gap: 6px; flex: none;
    font-size: 8.9px; font-weight: 700; letter-spacing: 1.25px;
    color: var(--rc); text-transform: uppercase;
  }}
  .kick .chip {{ width: 6px; height: 6px; background: var(--rc); display: inline-block; }}
  .kick .num {{
    margin-left: auto; font-family: "Noto Serif", Georgia, serif; font-weight: 700;
    font-size: 12.5px; letter-spacing: 0; color: #8C7A5C; line-height: 1;
  }}
  .hero .kick {{ color: #E9C687; }}
  .hero .kick .chip {{ background: #E9C687; }}
  .hero .kick .num {{ color: #7E94A6; }}

  h2 {{
    margin: 3px 0 0; font-family: "Noto Serif", Georgia, serif; font-weight: 700;
    color: {INK}; letter-spacing: -0.45px;
  }}
  .hero h2 {{ font-size: 35px; line-height: 1.06; color: #FBF6EA; letter-spacing: -0.6px; margin-top: 5px; }}
  .ipo h2 {{ font-size: 25.5px; line-height: 1.07; }}
  .row2 h2 {{ font-size: 22.2px; line-height: 1.07; }}
  .row3 h2 {{ font-size: 19px; line-height: 1.08; }}

  .sf {{
    margin: 4px 0 0; font-size: 9.9px; line-height: 1.3; color: {INK_SOFT};
    letter-spacing: 0.02px;
  }}
  .hero .sf {{ font-size: 12.2px; line-height: 1.32; color: #C9D4DE; margin-top: 6px; max-width: 610px; }}
  .ipo .sf {{ font-size: 10.3px; }}
  .row2 .sf {{ font-size: 9.8px; margin-top: 5px; }}
  .row3 .sf {{ font-size: 9.2px; margin-top: 5px; }}

  .stats {{ display: flex; gap: 10px; margin: 8px 0 2px; flex: none; }}
  .stats div {{
    flex: 1; border-top: 2px solid #21507B; padding-top: 4px;
    display: flex; flex-direction: column; line-height: 1;
  }}
  .stats b {{ font-family: "Noto Serif", Georgia, serif; font-size: 25px; color: #173E60; letter-spacing: -0.6px; }}
  .stats span {{ font-size: 7.6px; letter-spacing: 1.2px; color: #6B5F49; text-transform: uppercase; margin-top: 3px; }}

  .art {{ display: block; width: 100%; height: auto; margin-top: auto; flex: 0 0 auto; }}
  .hero .art {{ margin-top: 7px; }}
  .map {{ border: 1px solid #24435A; }}
  .row3 .art {{ margin-top: auto; }}
  svg {{ overflow: hidden; }}

  .wire {{
    margin-top: 6px; height: 82px; flex: none; display: flex;
    background: #EFE7D4; border-top: 3px solid {CRIMSON}; border-bottom: 1px solid {HAIR};
  }}
  .wire-label {{
    flex: 0 0 96px; padding: 10px 10px 8px 2px; border-right: 1px solid #D3C4A8;
    display: flex; flex-direction: column; justify-content: center;
  }}
  .wire-label b {{
    font-family: "Noto Serif", Georgia, serif; font-size: 15px; line-height: 1.02;
    color: {CRIMSON_DARK}; letter-spacing: -0.2px; text-transform: uppercase;
  }}
  .wire-label span {{ font-size: 6.8px; letter-spacing: 1.4px; color: #6B5F49; margin-top: 4px; }}
  .wires {{ flex: 1; display: flex; }}
  .witem {{ flex: 1; display: flex; gap: 7px; padding: 8px 9px 6px; min-width: 0; }}
  .witem + .witem {{ border-left: 1px solid #D3C4A8; }}
  .wicon {{ width: 24px; height: 24px; flex: none; margin-top: 2px; }}
  .wtext {{ min-width: 0; }}
  .wtext .wk {{ font-size: 7.2px; font-weight: 700; letter-spacing: 1.1px; color: #6B5F49; text-transform: uppercase; }}
  .wtext h3 {{ margin: 2px 0 0; font-family: "Noto Serif", Georgia, serif; font-size: 12.7px; line-height: 1.14; color: {INK}; }}
  .wtext p {{ margin: 2px 0 0; font-size: 8.4px; line-height: 1.26; color: #4A4438; }}

  .foot {{
    margin-top: 3px; display: flex; justify-content: space-between; align-items: baseline;
    font-size: 7.4px; letter-spacing: 0.5px; color: #6B5F49; flex: none;
  }}
  .foot b {{ color: {CRIMSON_DARK}; letter-spacing: 1.2px; }}
</style>
</head>
<body>
<div class="poster" id="poster">
  <div class="rule"></div>
  <div class="rail">
    <span>THE WORLD TODAY · A BROADSHEET OF RECORD</span>
    <span class="mid">TWELVE STORIES · SIX REGIONS · SEVEN BEATS</span>
    <span>VOL. VII · NO. 322</span>
  </div>
  <div class="hair"></div>

  <h1><span class="day">WEDNESDAY</span><span class="sep">·</span>18 NOVEMBER 2026</h1>
  <p class="deck">Strikes across the Gulf and Hormuz, Anthropic’s $1.5tn listing, a climate stocktake in deadlock: twelve dispatches from one Wednesday.</p>

  <div class="strip">
    <div><i style="background:{REGION['me']}"></i>Middle East<b>3</b></div>
    <div><i style="background:{REGION['am']}"></i>Americas<b>3</b></div>
    <div><i style="background:{REGION['ap']}"></i>Asia-Pacific<b>1</b></div>
    <div><i style="background:{REGION['eu']}"></i>Europe<b>3</b></div>
    <div><i style="background:{REGION['cl']}"></i>Climate<b>1</b></div>
    <div><i style="background:{REGION['te']}"></i>Global Tech<b>1</b></div>
  </div>

  <div class="sheet">
    <div class="row row1">
      {hero}
      {ipo}
    </div>
    <div class="row row2">{row2}</div>
    <div class="row row3">{row3}</div>
  </div>

  <div class="wire">
    <div class="wire-label"><b>World<br>Wire</b><span>ALSO ON 18 NOV</span></div>
    <div class="wires">
      <div class="witem">{wire_icon_tfl()}
        <div class="wtext"><div class="wk">10 · LONDON · CYBERSECURITY</div>
          <h3>TfL warns riders of a data breach</h3>
          <p>Suspicious activity hit transit cards; account details may be compromised.</p></div>
      </div>
      <div class="witem">{wire_icon_chip()}
        <div class="wtext"><div class="wk">11 · GLOBAL · SEMICONDUCTORS</div>
          <h3>Nvidia shake-up ripples through chip markets</h3>
          <p>Leadership fallout reverberates across US–China tech relations.</p></div>
      </div>
      <div class="witem">{wire_icon_un()}
        <div class="wtext"><div class="wk">12 · KYIV · HUMAN RIGHTS</div>
          <h3>UN: Ukraine civilian toll passes prior years</h3>
          <p>HRMMU says 2026 casualties have significantly surpassed earlier tolls.</p></div>
      </div>
    </div>
  </div>

  <div class="foot">
    <span>Sources: AP · Reuters · BBC · PBS · The Guardian · The Hindu · ISW · Just Security. Events of Wednesday 18 November 2026.</span>
    <span><b>WORLD NEWS CANVAS</b> · 01</span>
  </div>
</div>
</body>
</html>
"""


AUDIT_JS = r"""
() => {
  const round = (n) => Math.round(n * 10) / 10;
  const report = { doc: {}, header: {}, panels: [], svg: [], text: [], overlaps: [] };
  const de = document.documentElement;
  report.doc = { w: de.scrollWidth, h: de.scrollHeight,
                 bw: document.body.scrollWidth, bh: document.body.scrollHeight };
  const poster = document.getElementById('poster');
  const pr = poster.getBoundingClientRect();
  report.poster = { w: round(pr.width), h: round(pr.height) };

  const mast = document.querySelector('h1');
  const mr = mast.getBoundingClientRect();
  const rng = document.createRange(); rng.selectNodeContents(mast);
  const tr = rng.getBoundingClientRect();
  report.header = { masthead: { left: round(mr.left), right: round(mr.right),
                                textRight: round(tr.right),
                                rightGap: round(mr.right - tr.right),
                                size: getComputedStyle(mast).fontSize,
                                scrollW: mast.scrollWidth, clientW: mast.clientWidth } };

  document.querySelectorAll('.panel').forEach((p, i) => {
    const r = p.getBoundingClientRect();
    const cs = getComputedStyle(p);
    const padR = parseFloat(cs.paddingRight), padB = parseFloat(cs.paddingBottom);
    const padL = parseFloat(cs.paddingLeft), padT = parseFloat(cs.paddingTop);
    const entry = {
      i, cls: p.className,
      box: { w: round(r.width), h: round(r.height) },
      overflowY: p.scrollHeight - p.clientHeight,
      overflowX: p.scrollWidth - p.clientWidth,
      children: [], gaps: [], artH: 0
    };
    const content = { left: r.left + padL, top: r.top + padT,
                      right: r.right - padR, bottom: r.bottom - padB };
    let prevBottom = content.top;
    p.querySelectorAll(':scope > *').forEach((el) => {
      const b = el.getBoundingClientRect();
      const over = {
        tag: el.tagName.toLowerCase(),
        cls: el.className.baseVal !== undefined ? el.className.baseVal : el.className,
        left: round(b.left - content.left), top: round(b.top - content.top),
        right: round(content.right - b.right), bottom: round(content.bottom - b.bottom)
      };
      if (b.left < content.left - 0.6 || b.right > content.right + 0.6 ||
          b.top < content.top - 0.6 || b.bottom > content.bottom + 0.6) {
        entry.children.push(over);
      }
      const gap = b.top - prevBottom;
      if (b.top > content.top + 1) entry.gaps.push(round(gap));
      prevBottom = Math.max(prevBottom, b.bottom);
      if (el.tagName === 'svg') entry.artH = round(b.height);
    });
    entry.bottomSlack = round(content.bottom - prevBottom);
    report.panels.push(entry);
  });

  document.querySelectorAll('svg').forEach((svg, i) => {
    const sr = svg.getBoundingClientRect();
    const bad = [];
    let n = 0;
    svg.querySelectorAll('path,rect,circle,ellipse,line,polygon,polyline,text,image').forEach((el) => {
      const b = el.getBoundingClientRect();
      if (!b.width && !b.height) return;
      n++;
      const tol = 2.0;
      if (b.left < sr.left - tol || b.top < sr.top - tol ||
          b.right > sr.right + tol || b.bottom > sr.bottom + tol) {
        bad.push({ tag: el.tagName, l: round(b.left - sr.left), t: round(b.top - sr.top),
                   r: round(b.right - sr.right), b: round(b.bottom - sr.bottom) });
      }
    });
    if (bad.length) report.svg.push({ i, cls: svg.getAttribute('class'), n, bad: bad.slice(0, 8) });
  });

  document.querySelectorAll('.panel h2, .panel .sf, .panel .kick, .wtext h3, .wtext p, .witem .wk, .strip div, .rail span, .deck, .foot span, h1').forEach((el) => {
    if (el.scrollWidth > el.clientWidth + 1) {
      report.text.push({ text: el.textContent.trim().slice(0, 48),
                         scrollW: el.scrollWidth, clientW: el.clientWidth });
    }
  });

  const els = [...document.querySelectorAll('.panel h2, .panel .sf, .panel .kick, .wtext h3, .wtext p, .witem .wk, .strip div, .rail span, .deck, .foot span, h1')];
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
            executable_path=CHROME,
            headless=True,
            args=["--force-device-scale-factor=1", "--hide-scrollbars",
                  "--font-render-hinting=none", "--disable-lcd-text"],
        )
        page = browser.new_page(viewport={"width": SIZE, "height": SIZE},
                                device_scale_factor=1)
        page.goto(html_path.as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(180)
        audit = page.evaluate(AUDIT_JS)
        page.locator("#poster").screenshot(path=str(out_png))
        browser.close()
    return audit


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "entry.png"))
    ap.add_argument("--preview", default="/tmp/news18_300.png")
    ap.add_argument("--html", default="/tmp/news18_poster.html")
    ap.add_argument("--keep-png", default="/tmp/news18_1024.png")
    args = ap.parse_args()

    html = build_html()
    html_path = Path(args.html)
    html_path.write_text(html, encoding="utf-8")

    png_path = Path(args.keep_png)
    audit = render(html_path, png_path)

    failures = []
    if audit["doc"]["w"] != SIZE or audit["doc"]["h"] != SIZE:
        failures.append(f"document is {audit['doc']['w']}x{audit['doc']['h']}")
    if abs(audit["poster"]["w"] - SIZE) > 0.5 or abs(audit["poster"]["h"] - SIZE) > 0.5:
        failures.append(f"poster is {audit['poster']['w']}x{audit['poster']['h']}")
    for p in audit["panels"]:
        if p["overflowX"] > 1 or p["overflowY"] > 1:
            failures.append(f"{p['cls']} overflows x={p['overflowX']} y={p['overflowY']}")
        if p["children"]:
            failures.append(f"{p['cls']} child outside padding: {p['children']}")
    for s in audit["svg"]:
        failures.append(f"svg clipped: {s}")
    for t in audit["text"]:
        failures.append(f"text overflows horizontally: {t}")
    for o in audit["overlaps"]:
        failures.append(f"text overlaps: {o['a']!r} / {o['b']!r} ({o['ox']}x{o['oy']})")

    img = Image.open(png_path).convert("RGB")
    if img.size != (SIZE, SIZE):
        failures.append(f"screenshot is {img.size}")
    out = Path(args.out)
    img.save(out, format="JPEG", quality=92, subsampling=0, optimize=True,
             progressive=True)

    preview = img.resize((300, 300), Image.LANCZOS)
    preview.save(args.preview, format="PNG", optimize=True)

    # 300 px legibility strip: the top 300 px of the poster, at 300 px wide.
    top = img.crop((0, 0, SIZE, 300)).resize((300, 88), Image.LANCZOS)
    top.save("/tmp/news18_300_top.png", format="PNG", optimize=True)

    size_kb = out.stat().st_size / 1024
    print(f"entry.png: {img.size[0]}x{img.size[1]} {size_kb:.1f} KB")
    print(f"preview:   {args.preview}")
    if not 220 <= size_kb <= 360:
        print(f"WARN: {size_kb:.1f} KB is outside the 220-360 KB target band")
    for p in audit["panels"]:
        if p["gaps"] and max(p["gaps"]) > 16:
            print(f"layout:   {p['cls']} inner gap {max(p['gaps'])}px, art {p['artH']}px, slack {p['bottomSlack']}px")
    if failures:
        print("AUDIT FAILURES:")
        for f in failures:
            print(" -", f)
        return 1
    print("audit:     clean (no overflow, no clipped svg, no text overflow, no overlaps)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
