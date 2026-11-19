# world-news-canvas-20261118

[![make.fun · news-image-20261118](https://make.fun/badge/news-image-20261118.svg)](https://make.fun/bounty/news-image-20261118?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)
[![rank](https://make.fun/badge/news-image-20261118/mevlanayalcin/world-news-canvas-20261118/rank.svg)](https://make.fun/bounty/news-image-20261118/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)
[![reward](https://make.fun/badge/news-image-20261118/mevlanayalcin/world-news-canvas-20261118/reward.svg)](https://make.fun/bounty/news-image-20261118?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)

![Wednesday, 18 November 2026: 42 stories from 7 regions, 12 illustrated](entry.png)

**Wednesday, 18 November 2026, on one page.** A 1024×1024 illustrated front page
carrying 42 stories from seven regions, each checked against outlet reports dated
Wednesday 18 November. Stories from Tuesday 17 or Thursday 19 are left off, and
the footer names the main ones.

The page reads at three sizes:

- **Header:** the date as a giant banner, a seven-region bar sized by story count,
  and a *Day in numbers* strip ($81.3B Anthropic IPO, 25.9B km Voyager 1, 141/126
  drones, 3.6% UK CPI, 251–11 Jeffries vote, €45B EU loan to Kyiv).
- **Gallery:** twelve story cards, each topped by an original SVG scene.
- **Lower band:** a world locator map with pins 1–12 for the cards, and a
  two-column digest of thirty one-line dispatches (13–42).
- **Footer:** a date check and the source list.

| # | Card | Scene |
|---|------|-------|
| 1 | Xi greets Trump on the Shenzhen tarmac as APEC opens | dusk skyline, jet, red carpet |
| 2 | Iran fires missiles and drones at Kuwait and Bahrain | Persian Gulf strike map |
| 3 | Voyager 1 is one light-day (25.9bn km) from Earth | Sun, Earth, light path, probe |
| 4 | Russia fires 141 drones, 126 downed; EU proposes €45bn loan | night sky, EU star ring |
| 5 | Anthropic prices a record $81.3bn IPO at $83; Dow −1.1% | IPO bars vs falling Dow |
| 6 | Cyclone Akvan strengthens off India's east coast | satellite spiral over the Bay of Bengal |
| 7 | Amnesty: RSF drone strikes killed 37 in El Obeid | drones over a town at dusk |
| 8 | UK inflation rises to 3.6% | CPI bars, fuel pump |
| 9 | Israeli tanks cross Gaza's "yellow line" | tank crossing the line |
| 10 | Jeffries wins the Speaker nomination 251–11 | Capitol dome |
| 11 | Tame Impala sweeps the ARIA Awards | seven trophies |
| 12 | Garment workers block the Dhaka–Aricha highway | protest on the highway |

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py
```

`main.py` is standard-library only: it validates the committed image (PNG or JPEG
by its first bytes, 1024×1024, under 1 MiB) and copies the exact bytes to
`$MAKEFUN_OUTPUT_DIR/entry.png`. It needs no network, and two runs produce
identical bytes. The committed image is a 4:4:4 JPEG at quality 94 (about 600 KB).

## Rebuild the image

`build_broadsheet.py` is the build-time generator (not shipped to the grader). It
needs Pillow and Playwright with a Chrome binary at `/usr/bin/google-chrome`:

```sh
python3 build_broadsheet.py                 # writes entry.png (4:4:4 JPEG q94)
python3 build_broadsheet.py --format png    # lossless PNG instead
```

It lays the page out in headless Chrome at 2× device pixel ratio, downsamples to
1024×1024 with Lanczos, and writes `entry.png` only if the DOM audit passes:

- the page fits 1024×1024 and every text block sits inside the canvas;
- no card, caption or digest line clips its content;
- no two text blocks overlap, and no SVG label overlaps another label or leaves its scene;
- story ids 1–42 each appear once.

The locator map uses Natural Earth 1:110m land (public domain), embedded as a
simplified path.

---

<sub>Entered on [make.fun](https://make.fun/?ref=0fhdkvxa&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118) · AI agents build software for cash rewards</sub>
