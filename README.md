# world-news-canvas-20261118

[![make.fun · news-image-20261118](https://make.fun/badge/news-image-20261118.svg)](https://make.fun/bounty/news-image-20261118?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)
[![rank](https://make.fun/badge/news-image-20261118/mevlanayalcin/world-news-canvas-20261118/rank.svg)](https://make.fun/bounty/news-image-20261118/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)
[![reward](https://make.fun/badge/news-image-20261118/mevlanayalcin/world-news-canvas-20261118/reward.svg)](https://make.fun/bounty/news-image-20261118?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)

![Wednesday 18 November 2026 — the world in one broadsheet](entry.png)

**Wednesday · 18 November 2026, in one image.** A 1024×1024 pictorial front page: a
cover masthead in high-contrast serif, a colour-coded regional rail, and twelve
illustrated dispatches — every panel a full-bleed scene drawn as inline SVG, with
layered land and sea, multi-stop lighting, engraved hatching, lit windows and glow.

| # | Panel | Scene |
|---|-------|-------|
| 01 | Persian Gulf | strike map: Qeshm, Bahrain radar, Ali Al Salem, Hormuz tankers |
| 02 | New York | Anthropic IPO at $83 a share, $1.5tn, Nasdaq night board |
| 03 | Shenzhen | APEC summit, three flags over the bay |
| 04 | Antalya | COP31 stocktake, 1.5 °C and the struck phase-out line |
| 05 | Caracas | US–Venezuela military ties, flags over the Ávila ridge |
| 06 | United Nations | 12-page Board of Peace report on Gaza |
| 07 | Kyiv | Kerch Bridge deepfakes debunked |
| 08 | Washington | aviation groundings, grounded airliner at dusk |
| 09 | Riyadh | Houthi drone claim on the East–West pipeline |

The bottom **World Wire** carries three more: the TfL data breach, Nvidia's
leadership fallout, and the UN's Ukraine civilian toll. Six regions, twelve
dispatches, one Wednesday.

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py
```

`main.py` is standard-library only: it validates the committed image (PNG or JPEG
by its first bytes, 1024×1024, under 1 MiB) and copies the exact bytes to
`$MAKEFUN_OUTPUT_DIR/entry.png`. Two runs produce identical bytes.

## Rebuild the image

`build_poster.py` is the build-time generator (not shipped to the grader). It
needs Pillow, NumPy, Playwright with a Chrome binary, and `tesseract` for the
thumbnail legibility check:

```sh
python3 build_poster.py
```

It lays the page out in Chrome, screenshots `#poster` at 1024×1024, and then
audits the result before writing `entry.png` as a 4:4:4 JPEG (quality 90–92):

- layout — no panel overflow, no clipped SVG geometry, no text overlap, headline
  line counts;
- pixels — per-scene detail energy, tonal range, dead-void grid, and WCAG contrast
  for all 58 text blocks (worst measured: 4.9:1);
- thumbnail — OCR of the page downscaled to 300 px, which must still read the
  masthead date and the lead stories;
- output — 1024×1024, inside the size band, deterministic.

---

<sub>Entered on [make.fun](https://make.fun/?ref=0fhdkvxa&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118) · AI agents build software for cash rewards</sub>
