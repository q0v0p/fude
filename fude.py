"""fude (筆) — write Japanese text as an animated brush-calligraphy SVG.

Each character is drawn in the Yuji Boku brush font and revealed stroke by stroke in the
correct stroke order (KanjiVG), like a hand holding a brush. The result is a plain SVG with
CSS animation, so it plays inside a GitHub README <img>.

    python fude.py --text "一期一会" -o out.svg
    python fude.py --date --tz Asia/Tokyo --theme sumi -o today.svg

Glyph outlines and stroke data for characters that are not bundled in data/ are fetched on
first use (KanjiVG from GitHub, the font from google/fonts) and cached. That path needs
`pip install fonttools`.
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import pathlib
import re
import sys
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
CACHE = pathlib.Path(os.environ.get("FUDE_CACHE", pathlib.Path.home() / ".cache" / "fude"))
FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/yujiboku/YujiBoku-Regular.ttf"
KANJIVG_URL = "https://raw.githubusercontent.com/KanjiVG/kanjivg/master/kanji/{:05x}.svg"

CELL = 109  # glyph box, shared by KanjiVG and data/glyphs.json
DIGITS = "〇一二三四五六七八九"
WEEKDAYS = "月火水木金土日"

THEMES = {
    # name: (background, ink, seal, seal text)
    "washi": ("#f4eee0", "#16130f", "#c23a2b", "#f4eee0"),
    "sumi": ("#101014", "#f1ece0", "#d6453a", "#101014"),
    "clear": (None, "#16130f", "#c23a2b", "#ffffff"),  # no background, for light pages
    "clear-dark": (None, "#f1ece0", "#d6453a", "#101014"),  # no background, for dark pages
}


# ---------------------------------------------------------------- glyph data

class Glyphs:
    """Brush outlines (from the font) and stroke-order paths (from KanjiVG), with caching."""

    def __init__(self) -> None:
        self.outlines: dict[str, str] = json.loads((DATA / "glyphs.json").read_text(encoding="utf-8"))
        self._font = None

    def outline(self, ch: str) -> str | None:
        if ch in self.outlines:
            return self.outlines[ch]
        cached = CACHE / "glyphs" / f"{ord(ch):05x}.txt"
        if cached.exists():
            return cached.read_text(encoding="utf-8") or None
        d = self._extract(ch)
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(d or "", encoding="utf-8")
        return d

    def strokes(self, ch: str) -> list[str]:
        name = f"{ord(ch):05x}.svg"
        path = DATA / "kanjivg" / name
        if not path.exists():
            path = CACHE / "kanjivg" / name
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    path.write_bytes(_fetch(KANJIVG_URL.format(ord(ch))))
                except OSError:
                    path.write_text("", encoding="utf-8")  # no stroke data for this character
        svg = path.read_text(encoding="utf-8")
        return re.findall(r'<path id="kvg:[0-9a-f]+-s\d+"[^>]*\sd="([^"]+)"', svg)

    def _extract(self, ch: str) -> str | None:
        try:
            from fontTools.pens.svgPathPen import SVGPathPen
            from fontTools.pens.transformPen import TransformPen
            from fontTools.ttLib import TTFont
        except ImportError:
            sys.exit(f"fude: '{ch}' is not bundled; run `pip install fonttools` so it can be extracted from the font")
        if self._font is None:
            font_path = CACHE / "YujiBoku-Regular.ttf"
            if not font_path.exists():
                font_path.parent.mkdir(parents=True, exist_ok=True)
                font_path.write_bytes(_fetch(FONT_URL))
            self._font = TTFont(font_path)
        font = self._font
        glyph_name = font.getBestCmap().get(ord(ch))
        if glyph_name is None:
            return None
        s = CELL / font["head"].unitsPerEm
        top = font["OS/2"].sTypoAscender
        pen = SVGPathPen(font.getGlyphSet(), ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        font.getGlyphSet()[glyph_name].draw(TransformPen(pen, (s, 0, 0, -s, 0, top * s)))
        return pen.getCommands() or None


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def approx_length(d: str) -> float:
    """Length of a KanjiVG path, approximated by joining segment end points."""
    arity = {"m": 2, "l": 2, "c": 6, "s": 4, "q": 4, "t": 2, "h": 1, "v": 1}
    x = y = total = 0.0
    for cmd, args in re.findall(r"([A-Za-z])([^A-Za-z]*)", d):
        nums = [float(v) for v in re.findall(r"-?\d*\.?\d+(?:e-?\d+)?", args)]
        n = arity.get(cmd.lower(), 2)
        for i in range(0, len(nums) - n + 1, n):
            seg = nums[i : i + n]
            if cmd.lower() == "h":
                nx, ny = (x + seg[0] if cmd == "h" else seg[0]), y
            elif cmd.lower() == "v":
                nx, ny = x, (y + seg[0] if cmd == "v" else seg[0])
            elif cmd.islower():
                nx, ny = x + seg[-2], y + seg[-1]
            else:
                nx, ny = seg[-2], seg[-1]
            if cmd.lower() != "m":
                total += math.hypot(nx - x, ny - y)
            x, y = nx, ny
    return total


# ---------------------------------------------------------------- dates

def to_kanji(n: int) -> str:
    """1..99 as kanji numerals: 31 -> 三十一."""
    tens, ones = divmod(n, 10)
    return (("" if tens == 1 else DIGITS[tens]) + "十" if tens else "") + (DIGITS[ones] if ones else "")


def date_texts(date: datetime.date, era: str) -> tuple[str, str, str]:
    """(main line, sub line, seal) for a date: 九月三十日 / 令和八年　水曜日 / 水"""
    if era == "western":
        year = "".join(DIGITS[int(c)] for c in str(date.year)) + "年"
    else:
        reiwa = date.year - 2018
        year = "令和" + ("元" if reiwa == 1 else to_kanji(reiwa)) + "年"
    wd = WEEKDAYS[date.weekday()]
    return f"{to_kanji(date.month)}月{to_kanji(date.day)}日", f"{year}　{wd}曜日", wd


# ---------------------------------------------------------------- rendering

def render(
    lines: list[str],
    sub: str = "",
    seal: str = "",
    theme: str = "washi",
    width: int = 760,
    speed: float = 1.0,
    hold: float = 4.0,
) -> str:
    bg, ink, shu, seal_ink = THEMES[theme]
    glyphs = Glyphs()
    pad, gap = 28, 14
    brush = 17  # mask stroke width: wide enough to cover the brush outline
    pen_speed = 400 * speed  # glyph units per second
    stroke_min, stroke_gap, char_gap = 0.08 / speed, 0.04 / speed, 0.12 / speed

    lines = [ln for ln in lines if ln.strip()] or [" "]
    longest = max(len(ln) for ln in lines)
    main_scale = min(1.0, (width - pad * 2) / (longest * CELL))
    main_adv = CELL * main_scale
    sub_scale = 0.4 * max(main_scale, 0.75)
    sub_adv = CELL * sub_scale * 0.92
    seal_size = CELL * 0.5 * max(main_scale, 0.75) if seal else 0

    rows = []  # (text, x0, y0, advance, scale)
    y = pad
    for ln in lines:
        rows.append((ln, (width - len(ln) * main_adv) / 2, y, main_adv, main_scale))
        y += main_adv + 4
    foot = max(seal_size, CELL * sub_scale if sub else 0)
    if foot:
        y += gap - 4
        seal_x = width - pad - seal_size - 6
        if sub:
            sub_right = seal_x - 14 if seal else width - pad
            rows.append((sub, sub_right - len(sub) * sub_adv, y + (foot - CELL * sub_scale) / 2, sub_adv, sub_scale))
        seal_y = y + (foot - seal_size) / 2
        y += foot + 4
    height = y + pad - 4

    defs, body, anim = [], [], []  # anim: (selector, kind, start, stop)
    t, n = 0.6, 0
    for text, x0, y0, adv, scale in rows:
        pace = scale ** 0.5
        for i, ch in enumerate(text):
            if ch.isspace():
                continue
            outline = glyphs.outline(ch)
            if not outline:
                continue
            mask = []
            strokes = glyphs.strokes(ch)
            for d in strokes:
                dt = max(stroke_min * pace, approx_length(d) * scale / pen_speed)
                mask.append(f'<path id="s{n}" class="st" pathLength="1" d="{d}"/>')
                anim.append((f"#s{n}", "stroke", t, t + dt))
                n += 1
                t += dt + stroke_gap * pace
            if not strokes:  # no stroke-order data (latin, symbols, ...): sweep left to right
                mask.append(f'<rect id="s{n}" class="sw" x="-10" y="-10" width="{CELL + 20}" height="{CELL + 20}"/>')
                anim.append((f"#s{n}", "sweep", t, t + 0.35 * pace))
                n += 1
                t += 0.35 * pace + stroke_gap
            # once written, open the whole cell so the parts of the brush outline outside the mask show too
            mask.append(f'<rect id="s{n}" class="full" x="-10" y="-10" width="{CELL + 20}" height="{CELL + 20}"/>')
            anim.append((f"#s{n}", "fill", t - stroke_gap * pace, t + 0.25))
            n += 1
            m = len(defs)
            defs.append(
                f'<mask id="m{m}" maskUnits="userSpaceOnUse" x="-10" y="-10" width="{CELL + 20}" '
                f'height="{CELL + 20}">{"".join(mask)}</mask>'
            )
            body.append(
                f'<g transform="translate({x0 + i * adv:.1f} {y0:.1f}) scale({scale:.3f})">'
                f'<path class="ink" mask="url(#m{m})" d="{outline}"/></g>'
            )
            t += char_gap * pace
        t += 0.2 / speed

    seal_at = t + 0.3
    end = seal_at + (0.35 if seal else 0)
    if seal and (seal_d := glyphs.outline(seal[0])):
        s = seal_size / CELL
        body.append(
            f'<g transform="translate({seal_x:.1f} {seal_y:.1f}) rotate(-4 {seal_size / 2:.1f} {seal_size / 2:.1f})">'
            f'<g id="seal"><rect width="{seal_size:.1f}" height="{seal_size:.1f}" rx="5" fill="{shu}"/>'
            f'<g transform="translate({seal_size * 0.12:.1f} {seal_size * 0.1:.1f}) scale({s * 0.76:.3f})">'
            f'<path fill="{seal_ink}" d="{seal_d}"/></g></g></g>'
        )
    cycle = end + hold + 1.2
    pct = lambda v: f"{v / cycle * 100:.3f}%"

    css = [
        f".ink{{fill:{ink}}}",
        f".st{{fill:none;stroke:#fff;stroke-width:{brush};stroke-linecap:round;stroke-linejoin:round;"
        "stroke-dasharray:1 2;stroke-dashoffset:1;opacity:0}",
        ".sw{fill:#fff;transform-box:fill-box;transform-origin:left;transform:scaleX(0)}",
        ".full{fill:#fff;opacity:0}",
        f"mask *,#seal,#all{{animation-duration:{cycle:.2f}s;animation-iteration-count:infinite}}",
        "#all{animation-name:fade}",
        f"@keyframes fade{{0%,{pct(end + hold)}{{opacity:1}}{pct(end + hold + 1.2)},100%{{opacity:0}}}}",
        "#seal{transform-box:fill-box;transform-origin:center;opacity:0;animation-name:seal}",
        f"@keyframes seal{{0%,{pct(seal_at)}{{opacity:0;transform:scale(1.6)}}"
        f"{pct(seal_at + 0.001)}{{opacity:.6;transform:scale(1.6);animation-timing-function:cubic-bezier(.5,0,.8,.3)}}"
        f"{pct(end)}{{opacity:1;transform:scale(.96)}}{pct(end + 0.12)},100%{{opacity:1;transform:scale(1)}}}}",
    ]
    for i, (sel, kind, start, stop) in enumerate(anim):
        if kind == "stroke":
            # linger at the entry, sweep through, ease into the stop — like a brush
            frames = (
                f"0%,{pct(start)}{{stroke-dashoffset:1;opacity:0;animation-timing-function:cubic-bezier(.55,0,.35,1)}}"
                f"{pct(start + 0.001)}{{opacity:1}}{pct(stop)},100%{{stroke-dashoffset:0;opacity:1}}"
            )
        elif kind == "sweep":
            frames = f"0%,{pct(start)}{{transform:scaleX(0)}}{pct(stop)},100%{{transform:scaleX(1)}}"
        else:
            frames = f"0%,{pct(start)}{{opacity:0}}{pct(stop)},100%{{opacity:1}}"
        css.append(f"@keyframes a{i}{{{frames}}}{sel}{{animation-name:a{i}}}")

    title = " ".join(lines + ([sub.replace("　", " ")] if sub else []))
    background = f'<rect width="100%" height="100%" rx="12" fill="{bg}"/>' if bg else ""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height:.0f}" viewBox="0 0 {width} {height:.0f}">
<!-- Made with fude: https://github.com/q0v0p/fude
     Glyphs: Yuji Boku (C) The Yuji Project Authors, SIL OFL 1.1.
     Stroke order: KanjiVG (C) Ulrich Apel, CC BY-SA 3.0, https://kanjivg.tagaini.net -->
<title>{_escape(title)}</title>
<style>{"".join(css)}</style>
<defs>{"".join(defs)}</defs>
{background}
<g id="all">
{chr(10).join(body)}
</g>
</svg>
"""


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------- CLI

def _timezone(name: str) -> datetime.tzinfo:
    """An IANA name (Asia/Tokyo) or a fixed offset (+09:00)."""
    if m := re.fullmatch(r"(?:UTC)?([+-])(\d{1,2})(?::?(\d{2}))?", name):
        sign = 1 if m[1] == "+" else -1
        return datetime.timezone(sign * datetime.timedelta(hours=int(m[2]), minutes=int(m[3] or 0)))
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        if name == "Asia/Tokyo":  # the default; Windows has no tz database unless tzdata is installed
            return datetime.timezone(datetime.timedelta(hours=9))
        sys.exit(f"fude: unknown time zone '{name}' (pass an offset such as +09:00, or `pip install tzdata`)")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="fude", description="Animated brush-calligraphy SVG for Japanese text.")
    what = p.add_mutually_exclusive_group(required=True)
    what.add_argument("--text", help='text to write; use "\\n" for a line break')
    what.add_argument("--date", nargs="?", const="today", metavar="YYYY-MM-DD", help="write a date (default: today)")
    p.add_argument("--sub", default=None, help="small line under the text (date mode: year and weekday)")
    p.add_argument("--seal", default=None, help="one character stamped as a red seal (date mode: the weekday)")
    p.add_argument("--no-seal", action="store_true", help="do not stamp a seal")
    p.add_argument("--tz", default="Asia/Tokyo", help="time zone for --date (default: Asia/Tokyo)")
    p.add_argument("--era", choices=["reiwa", "western"], default="reiwa", help="year style for --date")
    p.add_argument("--theme", choices=sorted(THEMES), default="washi")
    p.add_argument("--width", type=int, default=760)
    p.add_argument("--speed", type=float, default=1.0, help="writing speed multiplier")
    p.add_argument("--hold", type=float, default=4.0, help="seconds to show the finished text before it restarts")
    p.add_argument("-o", "--output", default="fude.svg")
    a = p.parse_args(argv)

    if a.date is not None:
        if a.date == "today":
            date = datetime.datetime.now(_timezone(a.tz)).date()
        else:
            date = datetime.date.fromisoformat(a.date)
        main_text, sub, seal = date_texts(date, a.era)
        lines = [main_text]
        sub = sub if a.sub is None else a.sub
        seal = seal if a.seal is None else a.seal
    else:
        lines = a.text.replace("\\n", "\n").split("\n")
        sub = a.sub or ""
        seal = a.seal or ""
    if a.no_seal:
        seal = ""

    out = pathlib.Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render(lines, sub=sub, seal=seal, theme=a.theme, width=a.width, speed=a.speed, hold=a.hold),
        encoding="utf-8",
        newline="\n",
    )
    print(f"fude: wrote {out}")


if __name__ == "__main__":
    main()
