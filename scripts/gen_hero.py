"""Generate assets/hero.svg: an animated ASCII banner that morphs between words.

Pure SMIL animation (no JS), so GitHub renders it inside <img>.
Each frame is a <g> toggled with a discrete opacity animation.
Column alignment is enforced with textLength on every line, so glyph
width differences between fallback monospace fonts cannot break the art.
"""
from __future__ import annotations

import random
import sys
from xml.sax.saxutils import escape

import pyfiglet

WORDS = ["MATHEUS", "BIOMED", "KEYMATIC", "CONSTA", "CLUEMED", "BUILDER"]
TAGLINES = {
    "MATHEUS": "engineer · founder · builder — São Paulo, BR",
    "BIOMED": "biomedical engineering roots, software builder mindset",
    "KEYMATIC": "business automation + applied AI for real companies",
    "CONSTA": "hospital asset & maintenance management",
    "CLUEMED": "connected healthcare: records, workflows, documents",
    "BUILDER": "LLMs · RAG · agents · MCP · local inference",
}
FONT = "ansi_shadow"
HOLD_FRAMES = 14          # frames a word stays fully resolved
MORPH_FRAMES = 12         # frames per transition
FRAME_SECONDS = 0.11
NOISE = "░▒▓█╬╪╫┼╳"
SEED = 7

BG = "#0b0f14"
FRAME_STROKE = "#1f2a37"
ACCENT = "#f97316"
ACCENT_SOFT = "#fdba74"
TEXT = "#e6edf3"
MUTED = "#7d8590"
GREEN = "#3fb950"


def render(word: str) -> list[str]:
    lines = pyfiglet.figlet_format(word, font=FONT).rstrip("\n").split("\n")
    lines = [ln for ln in lines if ln.strip()]
    return lines


def pad_block(lines: list[str], width: int, height: int) -> list[str]:
    out = []
    for i in range(height):
        ln = lines[i] if i < len(lines) else ""
        left = (width - len(ln)) // 2
        ln = " " * left + ln
        out.append(ln.ljust(width))
    return out


def morph(a: list[str], b: list[str], steps: int, rng: random.Random) -> list[list[str]]:
    """Sweep a -> b from left to right. Each cell gets a resolve time; before it, it shows noise
    (only where either side has ink), after it, the target glyph."""
    h, w = len(a), len(a[0])
    resolve = [[0.16 + 0.72 * (x / (w - 1)) + 0.12 * rng.random() for x in range(w)] for _ in range(h)]
    frames = []
    for s in range(1, steps + 1):
        t = s / (steps + 1)
        rows = []
        for y in range(h):
            row = []
            for x in range(w):
                ca, cb = a[y][x], b[y][x]
                if ca == cb:
                    row.append(ca)
                    continue
                r = resolve[y][x]
                if t < r - 0.14:
                    row.append(ca)
                elif t < r:
                    row.append(rng.choice(NOISE) if (ca != " " or cb != " ") else " ")
                else:
                    row.append(cb)
            rows.append("".join(row))
        frames.append(rows)
    return frames


def main(out_path: str) -> None:
    rng = random.Random(SEED)
    blocks = [render(w) for w in WORDS]
    width = max(len(ln) for b in blocks for ln in b)
    height = max(len(b) for b in blocks)
    blocks = [pad_block(b, width, height) for b in blocks]

    # frame sequence: (lines, tagline_index_or_None)
    seq: list[tuple[list[str], int | None]] = []
    for i, blk in enumerate(blocks):
        seq.extend([(blk, i)] * HOLD_FRAMES)
        nxt = blocks[(i + 1) % len(blocks)]
        seq.extend([(f, None) for f in morph(blk, nxt, MORPH_FRAMES, rng)])

    n = len(seq)
    total = n * FRAME_SECONDS

    # geometry
    char_w = 9.2
    line_h = 17
    pad_x, pad_y = 36, 98
    art_w = width * char_w
    svg_w = int(art_w + pad_x * 2)
    art_h = height * line_h
    svg_h = int(pad_y + art_h + 122)

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}" height="{svg_h}" '
        f'viewBox="0 0 {svg_w} {svg_h}" role="img" aria-labelledby="t d">'
    )
    parts.append("<title id=\"t\">Matheus Godoi — ASCII banner</title>")
    parts.append(
        "<desc id=\"d\">Animated ASCII art morphing between MATHEUS, BIOMED, KEYMATIC, "
        "CONSTA, CLUEMED and BUILDER.</desc>"
    )
    parts.append(
        "<style>"
        f"text{{font-family:'JetBrains Mono','Fira Code','SFMono-Regular',Menlo,Consolas,'Liberation Mono',monospace;}}"
        f".art{{font-size:14px;fill:url(#g);white-space:pre;}}"
        f".ui{{font-size:14px;fill:{MUTED};}}"
        f".cmd{{font-size:15px;fill:{TEXT};}}"
        f".tag{{font-size:16px;fill:{ACCENT_SOFT};}}"
        f".ok{{fill:{GREEN};}}"
        "</style>"
    )
    parts.append("<defs>")
    parts.append(
        f'<linearGradient id="g" gradientUnits="userSpaceOnUse" x1="0" y1="{pad_y - 14}" x2="0" y2="{pad_y + art_h - 10}">'
        f'<stop offset="0" stop-color="{ACCENT}"/><stop offset="1" stop-color="{ACCENT_SOFT}"/></linearGradient>'
    )
    parts.append(
        '<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse">'
        '<rect width="4" height="2" fill="#ffffff" fill-opacity="0.025"/></pattern>'
    )
    parts.append("</defs>")

    # window chrome
    parts.append(
        f'<rect x="0.5" y="0.5" width="{svg_w-1}" height="{svg_h-1}" rx="12" fill="{BG}" stroke="{FRAME_STROKE}"/>'
    )
    parts.append(f'<rect x="1" y="1" width="{svg_w-2}" height="{svg_h-2}" rx="12" fill="url(#scan)"/>')
    for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        parts.append(f'<circle cx="{22 + i*20}" cy="22" r="6" fill="{c}"/>')
    parts.append(
        f'<text x="{svg_w/2}" y="26" text-anchor="middle" class="ui">matheusbgodoi@github — ~/profile — zsh</text>'
    )
    parts.append(f'<line x1="1" y1="42" x2="{svg_w-1}" y2="42" stroke="{FRAME_STROKE}"/>')

    # prompt line
    parts.append(
        f'<text x="{pad_x}" y="68" class="cmd"><tspan class="ok">➜</tspan> <tspan fill="{ACCENT}">~</tspan> '
        f'<tspan fill="{MUTED}">$</tspan> figlet --morph "whoami"</text>'
    )

    # frames
    for idx, (lines, tag_i) in enumerate(seq):
        t0 = idx / n
        t1 = (idx + 1) / n
        parts.append('<g opacity="0">' if idx > 0 else '<g opacity="1">')
        parts.append(
            f'<animate attributeName="opacity" values="0;1;0" keyTimes="0;{t0:.5f};{t1:.5f}" '
            f'calcMode="discrete" dur="{total:.2f}s" repeatCount="indefinite"/>'
            if idx > 0
            else f'<animate attributeName="opacity" values="1;0" keyTimes="0;{t1:.5f}" '
            f'calcMode="discrete" dur="{total:.2f}s" repeatCount="indefinite"/>'
        )
        for li, ln in enumerate(lines):
            y = pad_y + li * line_h
            parts.append(
                f'<text x="{pad_x}" y="{y}" class="art" xml:space="preserve" '
                f'textLength="{art_w:.1f}" lengthAdjust="spacingAndGlyphs">{escape(ln)}</text>'
            )
        parts.append("</g>")

    # taglines (one per word, shown during hold + following morph)
    per_word = HOLD_FRAMES + MORPH_FRAMES
    tag_y = pad_y + art_h + 24
    for i, w in enumerate(WORDS):
        t0 = (i * per_word) / n
        t1 = ((i + 1) * per_word) / n
        parts.append('<g opacity="0">' if i > 0 else '<g opacity="1">')
        parts.append(
            f'<animate attributeName="opacity" values="0;1;0" keyTimes="0;{t0:.5f};{t1:.5f}" '
            f'calcMode="discrete" dur="{total:.2f}s" repeatCount="indefinite"/>'
            if i > 0
            else f'<animate attributeName="opacity" values="1;0" keyTimes="0;{t1:.5f}" '
            f'calcMode="discrete" dur="{total:.2f}s" repeatCount="indefinite"/>'
        )
        parts.append(
            f'<text x="{pad_x}" y="{tag_y}" class="cmd"><tspan fill="{MUTED}">// </tspan>'
            f'<tspan class="tag">{escape(TAGLINES[w])}</tspan></text>'
        )
        parts.append("</g>")

    # status bar
    bar_y = svg_h - 38
    parts.append(f'<line x1="1" y1="{bar_y}" x2="{svg_w-1}" y2="{bar_y}" stroke="{FRAME_STROKE}"/>')
    parts.append(
        f'<text x="{pad_x}" y="{bar_y+25}" class="ui">'
        f'<tspan fill="{ACCENT}">●</tspan> main  '
        f'<tspan fill="{MUTED}">│</tspan>  biomed → software  '
        f'<tspan fill="{MUTED}">│</tspan>  São Paulo, BR</text>'
    )
    parts.append(
        f'<text x="{svg_w - pad_x}" y="{bar_y+25}" text-anchor="end" class="ui">'
        f'<tspan class="ok">●</tspan> building'
        f'<tspan fill="{ACCENT}">_<animate attributeName="opacity" values="1;0" dur="1s" calcMode="discrete" repeatCount="indefinite"/></tspan>'
        f'</text>'
    )

    parts.append("</svg>")
    svg = "\n".join(parts)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"{out_path}: {len(svg)/1024:.1f} KB, {n} frames, {total:.1f}s loop, {width}x{height} chars")


if __name__ == "__main__":
    main(sys.argv[1])
