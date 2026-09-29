<h1 align="center">fude 筆</h1>

<p align="center">
  <b>Animated Japanese brush calligraphy for your GitHub profile.</b><br/>
  Each character is written stroke by stroke, in the correct stroke order, with a real brush-shaped glyph.
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/q0v0p/fude/output/today.svg" alt="Today's date written with a brush" width="560"/>
</p>

<p align="center">
  <sub>☝️ This is today's date (JST), re-written every day by this action.</sub>
</p>

## Examples

| | |
|---|---|
| <img src="assets/ichigo.svg" width="380" alt="一期一会"/> | <img src="assets/western.svg" width="380" alt="十二月二十九日"/> |
| `text: 一期一会` `sub: いちごいちえ` `seal: 縁` `theme: sumi` | `date: 2026-12-29` `era: western` `theme: sumi` |
| <img src="assets/kachou.svg" width="380" alt="花鳥風月"/> | <img src="assets/date.svg" width="380" alt="九月三十日"/> |
| `text: 花鳥風月` `seal: none` | `date: today` (default) |

Any kanji, hiragana or katakana works. Characters are pulled from the font and KanjiVG on the fly.

## How it works

1. The visible shape of each character is the outline of [Yuji Boku](https://github.com/Kinutafontfactory/Yuji), a brush font with real *irie*, *hane*, *harai* and dry-brush texture.
2. That outline is masked by the character's centre-line strokes from [KanjiVG](https://kanjivg.tagaini.net), drawn one by one in stroke order with a thick "brush".
3. Each stroke's speed depends on its length, easing in at the entry and settling at the stop, so the rhythm feels hand-written.
4. It is a single SVG with CSS animation — no JavaScript, no external requests — so it plays inside a README `<img>`.

## Use it in your profile README

Add `.github/workflows/fude.yml` to your `<username>/<username>` repository:

```yaml
name: fude
on:
  schedule:
    - cron: "5 15 * * *" # 00:05 JST, every day
  workflow_dispatch:

permissions:
  contents: write

jobs:
  write:
    runs-on: ubuntu-latest
    steps:
      - uses: q0v0p/fude@v1
        with:
          output: dist/today.svg

      - name: Publish to the output branch
        working-directory: dist
        run: |
          git init -q -b output
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add . && git commit -q -m "fude"
          git push -f "https://x-access-token:${{ github.token }}@github.com/${{ github.repository }}.git" output
```

Then show it in your README:

```html
<img src="https://raw.githubusercontent.com/<username>/<username>/output/today.svg" width="480"/>
```

For fixed text you do not need a schedule: run it once and commit the SVG, or run the script locally.

### Light and dark mode

The `washi` and `sumi` themes carry their own background, so they read well on both. For a transparent background, render both `clear` and `clear-dark` and let GitHub pick:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".../output/today-dark.svg">
  <img src=".../output/today.svg" width="480">
</picture>
```

## Options

| input | default | |
|---|---|---|
| `text` | *(empty)* | Text to write. `\n` for a line break. Empty means "write the date". |
| `date` | `today` | `today` or `YYYY-MM-DD`, used when `text` is empty. |
| `timezone` | `Asia/Tokyo` | Decides what "today" is. |
| `era` | `reiwa` | `reiwa` → 令和八年, `western` → 二〇二六年 |
| `sub` | year and weekday for dates | Small line under the text. |
| `seal` | weekday for dates | One character stamped as a red seal. `none` for no seal. |
| `theme` | `washi` | `washi` (paper), `sumi` (ink black), `clear`, `clear-dark` |
| `speed` | `1.0` | Writing speed multiplier. |
| `width` | `760` | Width in pixels. Long text is scaled to fit. |
| `output` | `dist/fude.svg` | Where to write the SVG. |

## Run locally

```sh
pip install fonttools
python fude.py --text "一期一会" --sub "いちごいちえ" --seal 縁 --theme sumi -o ichigo.svg
python fude.py --date --era western -o today.svg
```

The font and stroke data for characters that are not bundled are downloaded once and cached in `~/.cache/fude` (`FUDE_CACHE` to change it).

## License

- Code: [MIT](LICENSE)
- Stroke-order data: [KanjiVG](https://kanjivg.tagaini.net) © Ulrich Apel, [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/). Generated SVGs contain data derived from it, so they are CC BY-SA 3.0 as well; the credit is embedded in each SVG.
- Glyphs: [Yuji Boku](https://github.com/Kinutafontfactory/Yuji) © The Yuji Project Authors, [SIL Open Font License 1.1](data/OFL.txt).
