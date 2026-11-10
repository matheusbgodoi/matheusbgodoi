"""Generate assets/hero.svg: a dot-matrix display that flips between words.

The banner is a board of dim dots. Words are set in a 5x7 pixel font; a lit
dot is a circle whose radius is interpolated by SMIL, so the change between
words is smooth at any frame rate (no frame swapping). Dots switch in a
diagonal wave, lit dots land with a small overshoot, and a band of light
crosses the board with each change. No JavaScript, no dependencies.

Usage: python scripts/gen_hero.py assets/hero.svg
"""
from __future__ import annotations

import sys
from xml.sax.saxutils import escape

WORDS = ["MATHEUS", "BIOMED", "KEYMATIC", "CONSTA", "CLUEMED", "BUILDER"]
TAGLINES = [
    "Engineer, founder and builder in São Paulo, Brazil",
    "Biomedical engineering roots, software builder mindset",
    "Business automation and applied AI for real companies",
    "Hospital asset and maintenance management",
    "Connected healthcare: records, workflows, documents",
    "LLMs · RAG · agents · MCP · local inference",
]

GLYPHS = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": ["###", ".#.", ".#.", ".#.", ".#.", ".#.", "###"],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
}

# board
COLS, ROWS = 60, 11
PITCH = 15.0
R_ON, R_DIM = 5.4, 1.5
WIDTH, HEIGHT = 960, 300
X0 = (WIDTH - (COLS - 1) * PITCH) / 2
Y0 = 70.0

# timing (seconds)
SLOT = 3.4                    # one word, including the change into the next
DOT_DUR = 0.42                # one dot switching
COL_DELAY, ROW_DELAY = 0.010, 0.022
WAVE = (COLS - 1) * COL_DELAY + (ROWS - 1) * ROW_DELAY + DOT_DUR
TOTAL = SLOT * len(WORDS)

BG = "#0a0e13"
STROKE = "#1c2530"
DIM = "#1a232e"
DIM_LIT = "#3a4756"
ACCENT = "#f97316"
ACCENT_SOFT = "#fdba74"
TEXT = "#e6edf3"
MUTED = "#7d8590"
GREEN = "#3fb950"
FONT = "'JetBrains Mono','Fira Code','SFMono-Regular',Menlo,Consolas,'Liberation Mono',monospace"

EASE_ON = "0.2 0.6 0.4 1"     # SMIL splines must stay in 0..1, so the overshoot is its own keyframe
EASE_SETTLE = "0.4 0 0.6 1"
OVERSHOOT = 1.14
EASE_OFF = "0.5 0 0.8 0.5"
LINEAR = "0 0 1 1"


def word_cells(word: str) -> set[tuple[int, int]]:
    cols: list[str] = [""] * 7
    for i, ch in enumerate(word):
        g = GLYPHS[ch]
        for r in range(7):
            cols[r] += ("." if i else "") + g[r]
    width = len(cols[0])
    left = (COLS - width) // 2
    top = (ROWS - 7) // 2
    return {(left + c, top + r) for r in range(7) for c in range(width) if cols[r][c] == "#"}


def f(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".")


def dot_animation(states: list[bool], col: int, row: int) -> str:
    """Radius keyframes for one dot over the whole loop."""
    delay = col * COL_DELAY + row * ROW_DELAY
    keys: list[tuple[float, float, str]] = [(0.0, R_ON if states[0] else 0.0, LINEAR)]
    for i in range(len(states)):
        a, b = states[i], states[(i + 1) % len(states)]
        if a == b:
            continue
        start = (i + 1) * SLOT - WAVE + delay
        keys.append((start, R_ON if a else 0.0, LINEAR))
        if b:
            keys.append((start + DOT_DUR * 0.68, R_ON * OVERSHOOT, EASE_ON))
            keys.append((start + DOT_DUR, R_ON, EASE_SETTLE))
        else:
            keys.append((start + DOT_DUR * 0.8, 0.0, EASE_OFF))
    if keys[-1][0] < TOTAL:
        keys.append((TOTAL, keys[0][1], LINEAR))
    values = ";".join(f(v) for _, v, _ in keys)
    times = ";".join(f(t / TOTAL) for t, _, _ in keys)
    splines = ";".join(s for _, _, s in keys[1:])
    return (
        f'<animate attributeName="r" values="{values}" keyTimes="{times}" keySplines="{splines}" '
        f'calcMode="spline" dur="{f(TOTAL)}s" repeatCount="indefinite"/>'
    )


def fade(intervals: list[tuple[float, float]], ramp: float = 0.28) -> str:
    """Opacity that is 1 inside the intervals, with short fades."""
    pts: list[tuple[float, float]] = []
    for a, b in sorted(intervals):
        if a <= 0:
            pts.append((0.0, 1))
        else:
            pts += [(a, 0), (a + ramp, 1)]
        if b >= TOTAL:
            pts.append((TOTAL, 1))
        else:
            pts += [(b - ramp, 1), (b, 0)]
    if pts[0][0] > 0:
        pts.insert(0, (0.0, 0))
    if pts[-1][0] < TOTAL:
        pts.append((TOTAL, pts[0][1]))
    values = ";".join(f(v) for _, v in pts)
    times = ";".join(f(t / TOTAL) for t, _ in pts)
    return f'<animate attributeName="opacity" values="{values}" keyTimes="{times}" dur="{f(TOTAL)}s" repeatCount="indefinite"/>'


def main(out_path: str) -> None:
    cells = [word_cells(w) for w in WORDS]
    used = sorted(set().union(*cells), key=lambda c: (c[1], c[0]))
    board_w = (COLS - 1) * PITCH
    board_h = (ROWS - 1) * PITCH

    p: list[str] = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="t d">'
    )
    p.append('<title id="t">Matheus Godoi</title>')
    p.append(
        '<desc id="d">A dot-matrix display flipping between MATHEUS, BIOMED, KEYMATIC, '
        "CONSTA, CLUEMED and BUILDER.</desc>"
    )
    p.append(
        "<style>"
        f"text{{font-family:{FONT};}}"
        f".label{{font-size:12px;fill:{MUTED};letter-spacing:2.4px}}"
        f".tag{{font-size:16px;fill:{TEXT}}}"
        "</style>"
    )

    p.append("<defs>")
    p.append(
        f'<linearGradient id="lit" gradientUnits="userSpaceOnUse" x1="{X0}" y1="{Y0}" x2="{X0 + board_w}" y2="{Y0 + board_h}">'
        f'<stop offset="0" stop-color="{ACCENT}"/><stop offset="1" stop-color="{ACCENT_SOFT}"/></linearGradient>'
    )
    half = PITCH / 2
    for pid, color, r in (("dim", DIM, R_DIM), ("dimlit", DIM_LIT, R_DIM + 0.5)):
        p.append(
            f'<pattern id="{pid}" x="{X0 - half}" y="{Y0 - half}" width="{PITCH}" height="{PITCH}" patternUnits="userSpaceOnUse">'
            f'<circle cx="{half}" cy="{half}" r="{r}" fill="{color}"/></pattern>'
        )
    p.append(
        '<linearGradient id="band" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset="0.5" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
    )
    # the light band crosses the board once per word change
    band_w = 260
    xs, ts = [], []
    for i in range(len(WORDS)):
        start = (i + 1) * SLOT - WAVE
        end = start + WAVE
        if i == 0:
            xs.append(-band_w); ts.append(0.0)
        xs += [-band_w, WIDTH]; ts += [start, end]
        if i < len(WORDS) - 1:
            xs.append(-band_w); ts.append(end + 0.001)
    p.append(
        f'<mask id="sweep"><rect x="{-band_w}" y="0" width="{band_w}" height="{HEIGHT}" fill="url(#band)">'
        f'<animate attributeName="x" values="{";".join(str(x) for x in xs)}" keyTimes="{";".join(f(min(t / TOTAL, 1)) for t in ts)}" '
        f'dur="{f(TOTAL)}s" repeatCount="indefinite"/></rect></mask>'
    )
    p.append(
        '<filter id="glow" x="-10%" y="-40%" width="120%" height="180%">'
        '<feGaussianBlur stdDeviation="5" result="b"/>'
        '<feColorMatrix in="b" type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 0.55 0" result="g"/>'
        '<feMerge><feMergeNode in="g"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
    )
    p.append("</defs>")

    # card
    p.append(f'<rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="14" fill="{BG}" stroke="{STROKE}"/>')

    # header
    p.append(f'<text x="{X0 - half + 2}" y="40" class="label">MATHEUS GODOI</text>')
    p.append(
        f'<text x="{X0 + board_w + half - 2}" y="40" text-anchor="end" class="label">'
        f'<tspan fill="{GREEN}">●<animate attributeName="opacity" values="1;0.25;1" dur="2.4s" repeatCount="indefinite"/></tspan> BUILDING</text>'
    )

    # board: dim dots, the light band, then the lit dots
    bx, by = X0 - half, Y0 - half
    bw, bh = COLS * PITCH, ROWS * PITCH
    p.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="url(#dim)"/>')
    p.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="url(#dimlit)" mask="url(#sweep)"/>')
    p.append('<g fill="url(#lit)" filter="url(#glow)">')
    for col, row in used:
        states = [(col, row) in c for c in cells]
        cx, cy = X0 + col * PITCH, Y0 + row * PITCH
        if all(states):
            p.append(f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{R_ON}"/>')
        else:
            p.append(
                f'<circle cx="{f(cx)}" cy="{f(cy)}" r="{R_ON if states[0] else 0}">'
                f"{dot_animation(states, col, row)}</circle>"
            )
    p.append("</g>")

    # footer: tagline for the current word, and one progress segment per word
    foot_y = HEIGHT - 34
    mid = WAVE / 2
    for i, line in enumerate(TAGLINES):
        a = i * SLOT - mid
        b = (i + 1) * SLOT - mid
        intervals = [(a, b)] if i else [(0.0, b), (TOTAL - mid, TOTAL)]
        p.append(f'<text x="{X0 - half + 2}" y="{foot_y}" class="tag" opacity="{1 if i == 0 else 0}">{escape(line)}{fade(intervals)}</text>')

    seg_w, seg_gap = 28, 6
    seg_x = X0 + board_w + half - 2 - (len(WORDS) * seg_w + (len(WORDS) - 1) * seg_gap)
    for i in range(len(WORDS)):
        x = seg_x + i * (seg_w + seg_gap)
        p.append(f'<rect x="{f(x)}" y="{foot_y - 7}" width="{seg_w}" height="3" rx="1.5" fill="{STROKE}"/>')
        a, b = i * SLOT, (i + 1) * SLOT
        vals, times = ["0"], ["0"]
        if a > 0:
            vals.append("0"); times.append(f(a / TOTAL))
        vals.append(str(seg_w)); times.append(f(b / TOTAL))
        if b < TOTAL:
            vals.append(str(seg_w)); times.append("1")
        p.append(
            f'<rect x="{f(x)}" y="{foot_y - 7}" width="0" height="3" rx="1.5" fill="{ACCENT}">'
            f'<animate attributeName="width" values="{";".join(vals)}" keyTimes="{";".join(times)}" dur="{f(TOTAL)}s" repeatCount="indefinite"/></rect>'
        )

    p.append("</svg>")
    svg = "\n".join(p)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"{out_path}: {len(svg.encode()) / 1024:.0f} KB, {len(used)} dots, {TOTAL:.1f}s loop")


if __name__ == "__main__":
    main(sys.argv[1])
