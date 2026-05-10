"""Geometry and identity knobs for build_font.py.

Each numeric knob is either:
  - an int (absolute font units), or
  - a callable `lambda m: ...` taking a metrics object with attributes
      m.upm   font UPM (typically 1000)
      m.cap   sCapHeight
      m.xh    sxHeight
      m.cell  monospace advance width

Lambdas let the same config adapt to base fonts with different UPMs/metrics.
"""

# --- Output identity --------------------------------------------------------
FAMILY_NAME = "BinaryRake"
STYLE_NAME  = "Regular"
OUTPUT      = None      # None = ./BinaryRake.ttf next to build_font.py

# --- Base font source -------------------------------------------------------
# If BASE_FONT_PATH points at a local .ttf, it's used directly.
# Otherwise build_font.py downloads BASE_FONT_URL into .cache/ and extracts
# BASE_FONT_TTF_NAME (the URL may point at a .ttf directly, or a .zip
# archive containing it).
# CLI override: `python3 build_font.py /path/to/font.ttf` beats both.
BASE_FONT_PATH     = None
BASE_FONT_URL      = ("https://github.com/be5invis/Iosevka/releases/download/"
                      "v34.5.0/PkgTTF-Iosevka-34.5.0.zip")
BASE_FONT_TTF_NAME = "Iosevka-Regular.ttf"

# --- Tooth heights (top of upward stroke, measured up from baseline) --------
TOOTH_0 = lambda m: m.xh // 2      # bit = 0 (short)
TOOTH_1 = lambda m: m.cap          # bit = 1 (tall, cap-height)

# --- Continuous bar at the base of the rake ---------------------------------
BAR_BOT       = lambda m: -m.upm // 10
BAR_THICKNESS = lambda m: max(m.upm // 50, 30)

# --- Tooth widths per base (keys are bits-per-digit) ------------------------
TOOTH_W = {
    1: lambda m: m.cell // 5,    # binary
    2: lambda m: m.cell // 6,    # quaternary
    3: lambda m: m.cell // 8,    # octal
    4: lambda m: m.cell // 10,   # hex
}

# Trailing-bar padding on multi-bit digit cells — visual separator between digits.
INTER_EXTRA = lambda m: m.cell // 4

# --- Period / repeat comma cells (narrow ~half-cell) ------------------------
COMMA_P_WIDTH = lambda m: m.cell // 2
COMMA_R_WIDTH = lambda m: m.cell // 2

# Tick = the downstroke of `p` and `r` (descends below the bar).
TICK_WIDTH = lambda m: max(m.upm // 25, 30)
TICK_BOT   = lambda m: -m.upm // 10 - m.upm // 4

# Repeat-marker stub — horizontal extension past the cell into the next glyph.
STUB_OVERFLOW  = lambda m: m.cell // 3
STUB_THICKNESS = lambda m: max(m.upm // 50, 20)

# --- Subsetter --------------------------------------------------------------
# Unicode codepoints kept in the output font. Rake glyphs (GSUB-reachable) are
# preserved automatically by fontTools regardless of this list.
SUBSET_UNICODES = range(0x20, 0x7F)
