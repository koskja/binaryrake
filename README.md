# BinaryRake

A monospace TrueType font that renders integer literals as a **rake ligature** —
a continuous bar at the bottom of each digit, with one upward tooth per bit.
Tall tooth = bit `1`, short tooth = bit `0`.

**Live demo:** <https://koskja.github.io/binaryrake/>

```
0xDE        0o755        0b11110000    0q0123
┃┃ ┃┃┃┃     ┃┃┃┃ ┃┃ ┃    ┃┃┃┃             ┃┃ ┃┃
┃┃ ┃┃┃┃     ┃┃┃┃ ┃┃ ┃    ┃┃┃┃             ┃┃ ┃┃
┃┃┃┃┃┃┃┃    ┃┃┃┃┃┃┃┃┃    ┃┃┃┃┃┃┃┃      ┃┃┃┃┃┃┃┃
━━━━━━━━    ━━━━━━━━━    ━━━━━━━━      ━━━━━━━━
```

The plain glyphs are untouched — rakes only fire inside numeric literals via
OpenType chained-context substitution (`calt`). Outside a literal the
underlying base font (Iosevka by default) is used unchanged, so this is a
drop-in monospace font for editors and terminals.

| Base | prefix | teeth/digit | example   |
|------|--------|-------------|-----------|
| 2    | `0b`   | 1           | `0b1010`  |
| 4    | `0q`   | 2           | `0q0123`  |
| 8    | `0o`   | 3           | `0o755`   |
| 16   | `0x`   | 4           | `0xDEADBEEF` |

Inside a literal, `p` becomes a downward tick (decimal-point analog) and `r`
adds a rightward stub (repeating-fraction marker): `0b1010p0101`, `0xFFp00r1A`.

## Build

```sh
pip install -r requirements.txt
python3 build_font.py        # → BinaryRake.ttf
python3 build_demo.py        # → demo.html (font inlined as base64)
open demo.html               # macOS; or just open in any browser
```

The first run downloads Iosevka v34.5.0 (~16 MB extracted) into `.cache/`.
Pass a different base font as `python3 build_font.py /path/to/Mono.ttf`, or
configure `BASE_FONT_PATH` / `BASE_FONT_URL` in `config.py`.

## Configure

All visual knobs live in [`config.py`](config.py): tooth heights, bar position
and thickness, comma cell widths, repeat-marker stub, output filename, and the
base font source. Each value is either a plain int or a `lambda m: ...`
expression taking font metrics — `m.upm`, `m.cap`, `m.xh`, `m.cell` — so the
same config adapts across base fonts with different UPMs.

```python
TOOTH_1       = lambda m: m.cap // 2     # half-cap-height tall teeth
BAR_THICKNESS = 40                       # absolute units instead of a ratio
FAMILY_NAME   = "MyRake"
```

## How it works

- **Glyphs.** `build_font.py` adds 66 glyphs to the base font: 4 prefix bars
  (`rake.start.{b,q,o,x}`), digit rakes (`rake.b{0,1}`, `rake.q{0..3}`,
  `rake.o{0..7}`, `rake.h{0..F}`), `.last` trim variants for the final digit
  in a run, and `rake.{p,r}` for the comma markers.
- **GSUB.** A new `calt` lookup chain matches `0[bqox]` to collapse the
  prefix, then walks the run left-to-right substituting each subsequent digit,
  `p`, or `r` based on a chained-context backtrack. All rules live in one
  outer lookup so a single sweep handles propagation. The base font's existing
  GSUB features (programming ligatures, character variants) are preserved by
  grafting the new lookups onto its existing `LookupList` rather than
  replacing the table.
- **OTS workaround.** fontTools' glyf recompile preserves the
  `OVERLAP_SIMPLE` flag on every point verbatim. Browsers' OTS sanitizer
  rejects that bit on any point past the first, so `fix_overlap_simple_flags`
  clears it before save — without this, Firefox and Chrome silently disable
  GSUB on the output font.

## Files

```
build_font.py    layer rake glyphs + GSUB onto base font, write BinaryRake.ttf
build_demo.py    render demo.html with the font inlined as a data URL
config.py        all geometry & identity knobs
.cache/          downloaded base font (gitignored)
```

## Authorship

Vibecoded end to end with Claude — the FEA chained-context structure, the
`OVERLAP_SIMPLE` browser workaround, this README, the CI workflow. It works
(the deploy badge above is the proof), but the source is closer to an
iterative sketch than a polished artifact.

Inspired by ["the best way to count"][yt] — the rake treatment of binary
numbers comes from there.

[yt]: https://www.youtube.com/watch?v=rDDaEVcwIJM

## License

[MIT](LICENSE) for the code in this repository.

The built `BinaryRake.ttf` is a derived work of [Iosevka][i] (SIL OFL-1.1)
and inherits OFL terms; this project is not affiliated with or endorsed by
the Iosevka project. The output keeps Iosevka's Reserved Font Name compliance
by renaming the family to `BinaryRake`. Iosevka is fetched at build time and
not redistributed in this repository.

[i]: https://github.com/be5invis/Iosevka
