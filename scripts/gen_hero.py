"""Generate assets/hero.svg: an ASCII banner whose word is one shape that morphs.

How it works
- Each word is rasterised (Impact) and turned into a signed distance field.
- A transition is real shape deformation, not a glyph swap: the word melts into
  a pill, and the pill opens into the next word (one shape, never cut). The way
  in is an ease-in, the way out is a damped spring with a small overshoot.
- Every frame is rendered through a brightness ramp: a soft halo outside the
  shape, dense characters at the edge, contour bands inside.
- Output is pure SMIL (no JS), so GitHub renders it inside <img>. Only plain
  ASCII characters are used, so any monospace font keeps the columns aligned.

Requirements: numpy, pillow, scipy.
Usage: python scripts/gen_hero.py assets/hero.svg
"""
from __future__ import annotations

import math
import sys
from xml.sax.saxutils import escape

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt

WORDS = ["MATHEUS", "BIOMED", "KEYMATIC", "CONSTA", "CLUEMED", "BUILDER"]
TAGLINES = {
    "MATHEUS": "engineer · founder · builder — São Paulo, BR",
    "BIOMED": "biomedical engineering roots, software builder mindset",
    "KEYMATIC": "business automation + applied AI for real companies",
    "CONSTA": "hospital asset & maintenance management",
    "CLUEMED": "connected healthcare: records, workflows, documents",
    "BUILDER": "LLMs · RAG · agents · MCP · local inference",
}
FONT_PATH = "/System/Library/Fonts/Supplemental/Impact.ttf"

# character grid and the hi-res field behind it (cells are 1:2, like monospace)
COLS, ROWS = 100, 14
CELL_W, CELL_H = 8, 16
FIELD_W, FIELD_H = COLS * CELL_W, ROWS * CELL_H
WORD_H = 11 * CELL_H            # cap height of every word, in field pixels
WORD_MAX_W = int(FIELD_W * 0.92)

# timing (seconds)
HOLD = 2.3
FRAME = 0.055
IN_FRAMES = 8                   # word -> pill
PILL_FRAMES = 2                 # the pill rests for a moment
OUT_FRAMES = 13                 # pill -> next word (spring)
SPRING_F, SPRING_Z = 1.55, 0.70

RAMP = " .:-=+*#%@"
HALO_PX = 6.5                   # half-width of the soft edge, in field pixels
BANDS = "@#"                    # contour bands inside the shape (deep interior only)
BAND_PX = 15.0
CORE_FROM = 5                   # ramp index where the bright layer starts

BG = "#0b0f14"
FRAME_STROKE = "#1f2a37"
ACCENT = "#f97316"
ACCENT_SOFT = "#fdba74"
HIGHLIGHT = "#ffe3c4"
HALO = "#8a4513"
TEXT = "#e6edf3"
MUTED = "#7d8590"
GREEN = "#3fb950"
FONT_STACK = "'JetBrains Mono','Fira Code','SFMono-Regular',Menlo,Consolas,'Liberation Mono',monospace"


def sdf(mask: np.ndarray) -> np.ndarray:
    """Signed distance in pixels: negative inside the shape."""
    return distance_transform_edt(~mask) - distance_transform_edt(mask)


def word_field(word: str) -> np.ndarray:
    font = ImageFont.truetype(FONT_PATH, 400)
    tracking = 34                                   # open the letters up so they read as ASCII
    boxes = [font.getbbox(ch) for ch in word]
    top = min(b[1] for b in boxes)
    bottom = max(b[3] for b in boxes)
    width = sum(font.getlength(ch) for ch in word) + tracking * (len(word) - 1)
    img = Image.new("L", (int(width) + 8, bottom - top), 0)
    draw = ImageDraw.Draw(img)
    x = 0.0
    for ch in word:
        draw.text((x, -top), ch, font=font, fill=255)
        x += font.getlength(ch) + tracking
    w = min(WORD_MAX_W, round(img.width * WORD_H / img.height))
    img = img.resize((w, WORD_H), Image.LANCZOS)
    canvas = Image.new("L", (FIELD_W, FIELD_H), 0)
    canvas.paste(img, ((FIELD_W - w) // 2, (FIELD_H - WORD_H) // 2))
    return sdf(np.asarray(canvas) > 127)


def pill_field() -> np.ndarray:
    half_w, half_h = FIELD_W * 0.17, CELL_H * 1.6
    y, x = np.mgrid[0:FIELD_H, 0:FIELD_W]
    qx = np.abs(x - FIELD_W / 2) - (half_w - half_h)
    qy = np.abs(y - FIELD_H / 2)
    return np.hypot(np.maximum(qx, 0), qy) - half_h


def spring(t: float) -> float:
    """Step response of a damped spring, t in 0..1."""
    w = 2 * math.pi * SPRING_F
    wd = w * math.sqrt(1 - SPRING_Z**2)
    return 1 - math.exp(-SPRING_Z * w * t) * (math.cos(wd * t) + SPRING_Z * w / wd * math.sin(wd * t))


def to_ascii(field: np.ndarray) -> list[list[int]]:
    """Field -> grid of codes: 0..len(RAMP)-1 on the edge, 100+band inside."""
    cells = field.reshape(ROWS, CELL_H, COLS, CELL_W).mean(axis=(1, 3))
    grid = []
    for row in cells:
        out = []
        for d in row:
            if d < -(HALO_PX + 2):
                out.append(100 + int((-d - HALO_PX) / BAND_PX) % len(BANDS))
            else:
                v = min(1.0, max(0.0, 0.5 - d / (2 * HALO_PX)))
                out.append(round(v * (len(RAMP) - 1)))
        grid.append(out)
    return grid


def layers(grid: list[list[int]]) -> tuple[list[str], list[str]]:
    """Split a grid into the dim halo layer and the bright core layer."""
    halo, core = [], []
    for row in grid:
        h, c = [], []
        for code in row:
            if code >= 100:
                h.append(" "); c.append(BANDS[code - 100])
            elif code >= CORE_FROM:
                h.append(" "); c.append(RAMP[code])
            else:
                h.append(RAMP[code]); c.append(" ")
        halo.append("".join(h).rstrip())
        core.append("".join(c).rstrip())
    return halo, core


def blink(intervals: list[tuple[float, float]], total: float) -> str:
    """Discrete opacity animation that is 1 inside the intervals, 0 outside."""
    pts = [(0.0, 0)]
    for a, b in sorted(intervals):
        if a <= 0:
            pts[0] = (0.0, 1)
        else:
            pts.append((a / total, 1))
        if b < total:
            pts.append((b / total, 0))
    values = ";".join(str(v) for _, v in pts)
    times = ";".join(f"{t:.5f}" for t, _ in pts)
    return (
        f'<animate attributeName="opacity" values="{values}" keyTimes="{times}" '
        f'calcMode="discrete" dur="{total:.3f}s" repeatCount="indefinite"/>'
    )


def build_frames() -> tuple[list[tuple[float, float, list[list[int]]]], list[float], float]:
    words = [word_field(w) for w in WORDS]
    pill = pill_field()
    frames: list[tuple[float, float, list[list[int]]]] = []
    mids: list[float] = []      # moment each transition is a pill (tagline swaps here)
    t = 0.0
    for i, a in enumerate(words):
        b = words[(i + 1) % len(words)]
        frames.append((t, HOLD, to_ascii(a)))
        t += HOLD
        for k in range(1, IN_FRAMES + 1):
            e = (k / (IN_FRAMES + 1)) ** 2.2                  # ease-in: slow start, fast collapse
            frames.append((t, FRAME, to_ascii(a + e * (pill - a))))
            t += FRAME
        mids.append(t)
        pulse = [0.0, -2.5]
        for k in range(PILL_FRAMES):
            frames.append((t, FRAME, to_ascii(pill + pulse[k % 2])))
            t += FRAME
        for k in range(1, OUT_FRAMES + 1):
            s = spring(k / (OUT_FRAMES + 1))
            frames.append((t, FRAME, to_ascii(pill + s * (b - pill))))
            t += FRAME
    return frames, mids, t


def main(out_path: str) -> None:
    frames, mids, total = build_frames()

    font_px = 10.0
    char_w = font_px * 0.6
    line_h = 12
    pad_x = 36
    art_w = COLS * char_w
    svg_w = int(art_w + pad_x * 2)
    art_top = 84
    art_h = ROWS * line_h
    tag_y = art_top + art_h + 30
    svg_h = tag_y + 66
    bar_y = svg_h - 38

    p: list[str] = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" '
        f'viewBox="0 0 {svg_w} {svg_h}" role="img" aria-labelledby="t d">'
    )
    p.append('<title id="t">Matheus Godoi — ASCII banner</title>')
    p.append(
        '<desc id="d">One ASCII shape morphing between MATHEUS, BIOMED, KEYMATIC, '
        "CONSTA, CLUEMED and BUILDER.</desc>"
    )
    p.append(
        "<style>"
        f"text{{font-family:{FONT_STACK};}}"
        f".a{{font-size:{font_px}px;font-weight:700;white-space:pre;}}"
        f".ui{{font-size:14px;fill:{MUTED};}}"
        f".cmd{{font-size:15px;fill:{TEXT};}}"
        f".tag{{font-size:16px;fill:{ACCENT_SOFT};}}"
        f".ok{{fill:{GREEN};}}"
        "</style>"
    )
    span = svg_w * 2
    p.append("<defs>")
    p.append(
        f'<linearGradient id="g" gradientUnits="userSpaceOnUse" x1="0" y1="{art_top}" x2="{span}" y2="{art_top + art_h}">'
        f'<stop offset="0" stop-color="{ACCENT}"/><stop offset="0.36" stop-color="{ACCENT_SOFT}"/>'
        f'<stop offset="0.5" stop-color="{HIGHLIGHT}"/><stop offset="0.64" stop-color="{ACCENT_SOFT}"/>'
        f'<stop offset="1" stop-color="{ACCENT}"/>'
        f'<animateTransform attributeName="gradientTransform" type="translate" '
        f'values="{-span} 0;{svg_w} 0" dur="5.2s" repeatCount="indefinite"/>'
        "</linearGradient>"
    )
    p.append(
        '<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">'
        '<rect width="4" height="2" fill="#ffffff" fill-opacity="0.025"/></pattern>'
    )
    p.append("</defs>")

    # window chrome
    p.append(f'<rect x="0.5" y="0.5" width="{svg_w-1}" height="{svg_h-1}" rx="12" fill="{BG}" stroke="{FRAME_STROKE}"/>')
    p.append(f'<rect x="1" y="1" width="{svg_w-2}" height="{svg_h-2}" rx="12" fill="url(#scan)"/>')
    for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        p.append(f'<circle cx="{22 + i*20}" cy="22" r="6" fill="{c}"/>')
    p.append(f'<text x="{svg_w/2}" y="26" text-anchor="middle" class="ui">matheusbgodoi@github — ~/profile — zsh</text>')
    p.append(f'<line x1="1" y1="42" x2="{svg_w-1}" y2="42" stroke="{FRAME_STROKE}"/>')
    p.append(
        f'<text x="{pad_x}" y="68" class="cmd"><tspan class="ok">➜</tspan> <tspan fill="{ACCENT}">~</tspan> '
        f'<tspan fill="{MUTED}">$</tspan> whoami | morph --ascii</text>'
    )

    # frames: two text layers each (dim halo, bright core)
    def text_block(rows: list[str], fill: str) -> str:
        spans = []
        for r, row in enumerate(rows):
            if row:
                spans.append(f'<tspan x="{pad_x}" y="{art_top + (r + 1) * line_h}">{escape(row)}</tspan>')
        return f'<text class="a" fill="{fill}" xml:space="preserve">{"".join(spans)}</text>'

    for idx, (start, dur, grid) in enumerate(frames):
        halo, core = layers(grid)
        p.append(f'<g opacity="{1 if idx == 0 else 0}">')
        p.append(blink([(start, start + dur)], total))
        p.append(text_block(halo, HALO))
        p.append(text_block(core, "url(#g)"))
        p.append("</g>")

    # taglines swap while the shape is a pill
    n = len(WORDS)
    for i, w in enumerate(WORDS):
        a, b = mids[i - 1], mids[i]
        intervals = [(a, b)] if i > 0 else [(0.0, b), (mids[-1], total)]
        p.append(f'<g opacity="{1 if i == 0 else 0}">')
        p.append(blink(intervals, total))
        p.append(
            f'<text x="{pad_x}" y="{tag_y}" class="cmd"><tspan fill="{MUTED}">// </tspan>'
            f'<tspan class="tag">{escape(TAGLINES[w])}</tspan></text>'
        )
        p.append("</g>")

    # status bar
    p.append(f'<line x1="1" y1="{bar_y}" x2="{svg_w-1}" y2="{bar_y}" stroke="{FRAME_STROKE}"/>')
    p.append(
        f'<text x="{pad_x}" y="{bar_y+25}" class="ui">'
        f'<tspan fill="{ACCENT}">●</tspan> main  '
        f'<tspan fill="{MUTED}">│</tspan>  biomed → software  '
        f'<tspan fill="{MUTED}">│</tspan>  São Paulo, BR</text>'
    )
    p.append(
        f'<text x="{svg_w - pad_x}" y="{bar_y+25}" text-anchor="end" class="ui">'
        f'<tspan class="ok">●</tspan> building'
        f'<tspan fill="{ACCENT}">_<animate attributeName="opacity" values="1;0" dur="1s" calcMode="discrete" repeatCount="indefinite"/></tspan>'
        "</text>"
    )
    p.append("</svg>")

    svg = "\n".join(p)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"{out_path}: {len(svg.encode())/1024:.0f} KB, {len(frames)} frames, {total:.1f}s loop, {COLS}x{ROWS} chars, {n} words")


if __name__ == "__main__":
    main(sys.argv[1])
