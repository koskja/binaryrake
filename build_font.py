#!/usr/bin/env python3
"""Layer binary-rake ligatures onto an existing TrueType font.

The base font is configured in config.py (BASE_FONT_PATH for a local
file, or BASE_FONT_URL + BASE_FONT_TTF_NAME for a remote one, defaulting
to Iosevka). The argv override below beats both.

The base font's letterforms are preserved unchanged; the rake glyphs
(continuous bar + per-bit teeth) only appear inside numeric literals
(0b…/0q…/0o…/0x…) via an OpenType chained-context substitution. A `p`
inside a literal becomes a downward tick (decimal-point analog); an `r`
becomes a tick + rightward stub (repeating-fraction marker).

Usage: python3 build_font.py [PATH_TO_BASE_TTF]
"""
import os
import sys
import urllib.request
import zipfile
from types import SimpleNamespace
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.subset import Subsetter, Options as SubsetOptions

import config


DIR   = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(DIR, ".cache")

HEX_DIGITS = "0123456789ABCDEF"

def fetch_default_base():
    """Resolve the base font from config: local path, or download URL.
    For URLs ending in .zip the archive is extracted; otherwise the file is
    saved directly. Result is cached in .cache/ keyed on the TTF name."""
    if config.BASE_FONT_PATH:
        return config.BASE_FONT_PATH

    os.makedirs(CACHE, exist_ok=True)
    ttf_name = config.BASE_FONT_TTF_NAME
    cached_ttf = os.path.join(CACHE, ttf_name)
    if os.path.exists(cached_ttf) and os.path.getsize(cached_ttf) > 1000:
        return cached_ttf

    url = config.BASE_FONT_URL
    dl_path = os.path.join(CACHE, os.path.basename(url))
    if not (os.path.exists(dl_path) and os.path.getsize(dl_path) > 1000):
        print(f"Downloading {url}")
        urllib.request.urlretrieve(url, dl_path)

    if dl_path.lower().endswith(".zip"):
        with zipfile.ZipFile(dl_path) as z:
            members = z.namelist()
            candidates = [m for m in members if m.endswith(ttf_name)]
            if not candidates:
                candidates = [m for m in members if m.endswith("-Regular.ttf")]
            if not candidates:
                candidates = [m for m in members if m.lower().endswith(".ttf")]
            if not candidates:
                raise SystemExit(f"No .ttf inside {dl_path}: {members[:10]}…")
            chosen = candidates[0]
            print(f"Extracting {chosen}")
            with z.open(chosen) as src, open(cached_ttf, "wb") as dst:
                dst.write(src.read())
    else:
        # Direct .ttf URL: the download IS the font.
        if dl_path != cached_ttf:
            with open(dl_path, "rb") as src, open(cached_ttf, "wb") as dst:
                dst.write(src.read())
    return cached_ttf


def rect(pen, x0, y0, x1, y1):
    pen.moveTo((x0, y0))
    pen.lineTo((x1, y0))
    pen.lineTo((x1, y1))
    pen.lineTo((x0, y1))
    pen.closePath()


def make_bar(advance, geo):
    p = TTGlyphPen(None)
    rect(p, 0, geo["bar_bot"], advance, geo["bar_top"])
    return p.glyph()


def digit_advance(n_bits, geo):
    """Multi-bit digits get extra trailing bar so adjacent digits read as separate."""
    return geo["cell"] if n_bits == 1 else geo["cell"] + geo["inter_extra"]


def last_advance(n_bits, geo):
    """Advance for the .last variant — bar terminates at the rightmost tooth."""
    pitch = geo["cell"] // n_bits
    tw = geo["tooth_w"][n_bits]
    return (n_bits - 1) * pitch + tw


def make_rake_digit(value, n_bits, geo, *, trim=False):
    advance = last_advance(n_bits, geo) if trim else digit_advance(n_bits, geo)
    p = TTGlyphPen(None)
    rect(p, 0, geo["bar_bot"], advance, geo["bar_top"])
    pitch = geo["cell"] // n_bits      # intra-digit pitch — independent of inter_extra
    tw = geo["tooth_w"][n_bits]
    for i in range(n_bits):
        bit = (value >> (n_bits - 1 - i)) & 1
        top = geo["tooth_1"] if bit else geo["tooth_0"]
        x0 = i * pitch
        rect(p, x0, geo["bar_top"], x0 + tw, top)
    return p.glyph()


def make_rake_period(geo):
    p = TTGlyphPen(None)
    rect(p, 0, geo["bar_bot"], geo["comma_p_w"], geo["bar_top"])
    cx = (geo["comma_p_w"] - geo["tick_w"]) // 2
    rect(p, cx, geo["tick_bot"], cx + geo["tick_w"], geo["bar_bot"])
    return p.glyph()


def make_rake_repeat(geo):
    """Same advance as the period, plus a horizontal stub at the tick's base
    that overflows the cell into the following glyph's space."""
    p = TTGlyphPen(None)
    rect(p, 0, geo["bar_bot"], geo["comma_r_w"], geo["bar_top"])
    cx = (geo["comma_r_w"] - geo["tick_w"]) // 2
    rect(p, cx, geo["tick_bot"], cx + geo["tick_w"], geo["bar_bot"])
    stub_right = geo["comma_r_w"] + geo["stub_overflow"]
    rect(p, cx, geo["tick_bot"], stub_right, geo["tick_bot"] + geo["stub_thick"])
    return p.glyph()


def add_rake_glyphs(font, geo):
    glyf  = font["glyf"]
    hmtx  = font["hmtx"]
    order = list(font.getGlyphOrder())

    def add(name, glyph, advance):
        glyf[name] = glyph
        hmtx[name] = (advance, 0)
        order.append(name)

    for tag in "bqox":
        add(f"rake.start.{tag}", make_bar(geo["cell"], geo), geo["cell"])

    for n_bits, label, count in [(1, "b", 2), (2, "q", 4), (3, "o", 8), (4, "h", 16)]:
        for i in range(count):
            tag = HEX_DIGITS[i] if label == "h" else str(i)
            add(f"rake.{label}{tag}",
                make_rake_digit(i, n_bits, geo),
                digit_advance(n_bits, geo))
            add(f"rake.{label}{tag}.last",
                make_rake_digit(i, n_bits, geo, trim=True),
                last_advance(n_bits, geo))

    add("rake.p", make_rake_period(geo), geo["comma_p_w"])
    add("rake.r", make_rake_repeat(geo), geo["comma_r_w"])

    font.setGlyphOrder(order)


def build_fea(font):
    """Resolve input glyph names from the base font's cmap and assemble the FEA."""
    cmap = font.getBestCmap()

    def gn(c):
        cp = ord(c)
        if cp not in cmap:
            raise SystemExit(f"Base font has no glyph for {c!r} (U+{cp:04X}); "
                             f"can't build rake rules.")
        return cmap[cp]

    digits    = [gn(str(i)) for i in range(10)]
    hex_lower = [gn(c) for c in "abcdef"]
    hex_upper = [gn(c) for c in "ABCDEF"]
    g_b, g_q, g_o, g_x = gn('b'), gn('q'), gn('o'), gn('x')
    g_p, g_r = gn('p'), gn('r')

    bin_bt  = ["rake.start.b", "rake.b0", "rake.b1", "rake.p", "rake.r"]
    quat_bt = ["rake.start.q"] + [f"rake.q{i}" for i in range(4)] + ["rake.p", "rake.r"]
    oct_bt  = ["rake.start.o"] + [f"rake.o{i}" for i in range(8)] + ["rake.p", "rake.r"]
    hex_bt  = ["rake.start.x"] + [f"rake.h{c}" for c in HEX_DIGITS] + ["rake.p", "rake.r"]

    # Trim a digit whenever the next glyph isn't another digit of the same base.
    # Periods and repeats are NOT continuations — the digit before them gets trimmed too.
    bin_cont  = ["rake.b0", "rake.b1"]
    quat_cont = [f"rake.q{i}" for i in range(4)]
    oct_cont  = [f"rake.o{i}" for i in range(8)]
    hex_cont  = [f"rake.h{c}" for c in HEX_DIGITS]
    bin_digits   = ["rake.b0", "rake.b1"]
    quat_digits  = [f"rake.q{i}" for i in range(4)]
    oct_digits   = [f"rake.o{i}" for i in range(8)]
    hex_digits_g = [f"rake.h{c}" for c in HEX_DIGITS]

    cls = lambda items: "[" + " ".join(items) + "]"

    bin_pairs  = [(digits[0], "rake.b0"), (digits[1], "rake.b1"),
                  (g_p, "rake.p"), (g_r, "rake.r")]
    quat_pairs = [(digits[i], f"rake.q{i}") for i in range(4)] + \
                 [(g_p, "rake.p"), (g_r, "rake.r")]
    oct_pairs  = [(digits[i], f"rake.o{i}") for i in range(8)] + \
                 [(g_p, "rake.p"), (g_r, "rake.r")]
    hex_pairs  = [(digits[i], f"rake.h{HEX_DIGITS[i]}") for i in range(10)] + \
                 [(hex_lower[i], f"rake.h{HEX_DIGITS[10+i]}") for i in range(6)] + \
                 [(hex_upper[i], f"rake.h{HEX_DIGITS[10+i]}") for i in range(6)] + \
                 [(g_p, "rake.p"), (g_r, "rake.r")]

    # `subtable;` between rules forces feaLib to emit separate Format 3
    # subtables. All rules live in ONE outer lookup so propagation chains
    # through them in a single left-to-right sweep.
    def emit_prop(name, bt, pairs):
        rule_lines = [f"    sub {cls(bt)} {inp}' by {target};" for inp, target in pairs]
        body = "\n    subtable;\n".join(rule_lines)
        return f"lookup {name} {{\n{body}\n}} {name};"

    def emit_trim(name, digits, cont):
        c = cls(cont)
        chunks = [f"    ignore sub {d}' {c};\n    sub {d}' by {d}.last;" for d in digits]
        body = "\n    subtable;\n".join(chunks)
        return f"lookup {name} {{\n{body}\n}} {name};"

    bin_prop_src  = emit_prop("BinProp",  bin_bt,  bin_pairs)
    quat_prop_src = emit_prop("QuatProp", quat_bt, quat_pairs)
    oct_prop_src  = emit_prop("OctProp",  oct_bt,  oct_pairs)
    hex_prop_src  = emit_prop("HexProp",  hex_bt,  hex_pairs)

    bin_trim_src  = emit_trim("TrimBin",  bin_digits,   bin_cont)
    quat_trim_src = emit_trim("TrimQuat", quat_digits,  quat_cont)
    oct_trim_src  = emit_trim("TrimOct",  oct_digits,   oct_cont)
    hex_trim_src  = emit_trim("TrimHex",  hex_digits_g, hex_cont)

    feature_block = """\
    lookup BinStart;  lookup QuatStart;  lookup OctStart;  lookup HexStart;
    lookup BinProp;   lookup QuatProp;   lookup OctProp;   lookup HexProp;
    lookup TrimBin;   lookup TrimQuat;   lookup TrimOct;   lookup TrimHex;"""
    return f"""
languagesystem DFLT dflt;
languagesystem latn dflt;

lookup BinStart  {{ sub {digits[0]} {g_b} by rake.start.b; }} BinStart;
lookup QuatStart {{ sub {digits[0]} {g_q} by rake.start.q; }} QuatStart;
lookup OctStart  {{ sub {digits[0]} {g_o} by rake.start.o; }} OctStart;
lookup HexStart  {{ sub {digits[0]} {g_x} by rake.start.x; }} HexStart;

{bin_prop_src}

{quat_prop_src}

{oct_prop_src}

{hex_prop_src}

{bin_trim_src}

{quat_trim_src}

{oct_trim_src}

{hex_trim_src}

feature calt {{
{feature_block}
}} calt;
"""


def fix_overlap_simple_flags(font):
    """OTS (browser font sanitizer) rejects the OVERLAP_SIMPLE bit (0x40)
    when it appears on any glyph point other than the first. fontTools'
    glyf recompile preserves this bit verbatim from input, so a font that
    set OVERLAP_SIMPLE on multiple points (e.g., Iosevka) ends up rejected
    after a save round-trip — the browser silently disables GSUB.
    Clear the bit on every non-first point."""
    glyf = font["glyf"]
    OVERLAP_SIMPLE = 0x40
    fixed = 0
    for name in font.getGlyphOrder():
        g = glyf[name]
        if g.numberOfContours <= 0 or not hasattr(g, "flags"):
            continue
        flags = g.flags
        for i in range(1, len(flags)):
            if flags[i] & OVERLAP_SIMPLE:
                flags[i] &= ~OVERLAP_SIMPLE
                fixed += 1
    if fixed:
        print(f"  cleared OVERLAP_SIMPLE on {fixed} non-first points")


def merge_calt_into_gsub(font, fea_text):
    """Compile FEA in a temp font, then graft its calt lookups onto the
    existing GSUB. Preserves the base font's GDEF, GPOS, and all of its
    other GSUB features (programming ligatures, character variants, etc.)."""
    temp = TTFont()
    temp.setGlyphOrder(list(font.getGlyphOrder()))
    addOpenTypeFeaturesFromString(temp, fea_text)

    new_gsub = temp["GSUB"].table
    existing_gsub = font["GSUB"].table

    # Append new lookups to existing LookupList; renumber any internal
    # cross-references in the new lookups. References live in different
    # spots depending on lookup type / format:
    #   - Format 1/3 (chained) context: subtable.SubstLookupRecord
    #   - Format 2 (chained) context:   subtable.[Chain]SubClassSet[N].
    #                                       [Chain]SubClassRule[M].SubstLookupRecord
    #   - Type 7 extension lookup:      subtable.ExtSubTable (recurse)
    n_old = len(existing_gsub.LookupList.Lookup)

    def shift_records(records):
        if records:
            for r in records:
                r.LookupListIndex += n_old

    def shift_subtable(st):
        if hasattr(st, "ExtSubTable") and st.ExtSubTable is not None:
            shift_subtable(st.ExtSubTable)
            return
        for attr in ("SubstLookupRecord", "PosLookupRecord"):
            shift_records(getattr(st, attr, None))
        for set_attr, rule_attr in (
            ("ChainSubClassSet", "ChainSubClassRule"),
            ("SubClassSet",      "SubClassRule"),
            ("ChainPosClassSet", "ChainPosClassRule"),
            ("PosClassSet",      "PosClassRule"),
        ):
            class_sets = getattr(st, set_attr, None) or []
            for cs in class_sets:
                if cs is None:
                    continue
                rules = getattr(cs, rule_attr, []) or []
                for rule in rules:
                    for attr in ("SubstLookupRecord", "PosLookupRecord"):
                        shift_records(getattr(rule, attr, None))
        # Format 1 (rule sets keyed on first glyph)
        for set_attr, rule_attr in (
            ("ChainSubRuleSet", "ChainSubRule"),
            ("SubRuleSet",      "SubRule"),
            ("ChainPosRuleSet", "ChainPosRule"),
            ("PosRuleSet",      "PosRule"),
        ):
            rule_sets = getattr(st, set_attr, None) or []
            for rs in rule_sets:
                if rs is None:
                    continue
                rules = getattr(rs, rule_attr, []) or []
                for rule in rules:
                    for attr in ("SubstLookupRecord", "PosLookupRecord"):
                        shift_records(getattr(rule, attr, None))

    for lk in new_gsub.LookupList.Lookup:
        for st in lk.SubTable:
            shift_subtable(st)

    existing_gsub.LookupList.Lookup.extend(new_gsub.LookupList.Lookup)
    existing_gsub.LookupList.LookupCount = len(existing_gsub.LookupList.Lookup)

    # Find which lookup indices our new calt feature points to (after shift).
    new_calt_indices = []
    for fr in new_gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == "calt":
            new_calt_indices.extend(i + n_old for i in fr.Feature.LookupListIndex)

    # Extend every existing `calt` feature record so the rake fires under
    # all script/language pairs the base font already declares calt for.
    extended = 0
    for fr in existing_gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == "calt":
            fr.Feature.LookupListIndex.extend(new_calt_indices)
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
            extended += 1

    if extended == 0:
        # Base font has no calt — create a new feature record and link it
        # from every script's DefaultLangSys.
        new_fr = ot.FeatureRecord()
        new_fr.FeatureTag = "calt"
        new_fr.Feature = ot.Feature()
        new_fr.Feature.FeatureParams = None
        new_fr.Feature.LookupListIndex = new_calt_indices
        new_fr.Feature.LookupCount = len(new_calt_indices)
        feat_idx = len(existing_gsub.FeatureList.FeatureRecord)
        existing_gsub.FeatureList.FeatureRecord.append(new_fr)
        existing_gsub.FeatureList.FeatureCount += 1
        for sr in existing_gsub.ScriptList.ScriptRecord:
            langsystems = []
            if sr.Script.DefaultLangSys:
                langsystems.append(sr.Script.DefaultLangSys)
            langsystems.extend(ls.LangSys for ls in sr.Script.LangSysRecord)
            for ls in langsystems:
                ls.FeatureIndex.append(feat_idx)
                ls.FeatureCount = len(ls.FeatureIndex)


def rename_font(font, family, style):
    """Update the name table per OFL Reserved Font Name compliance."""
    nm = font["name"]
    records = {
        1:  family,
        2:  style,
        3:  f"{family}-{style}",
        4:  f"{family} {style}",
        6:  f"{family.replace(' ', '')}-{style}",
        16: family,
        17: style,
    }
    nm.names = [r for r in nm.names if r.nameID not in records]
    for nameID, value in records.items():
        nm.setName(value, nameID, 1, 0, 0)         # Mac Roman / English
        nm.setName(value, nameID, 3, 1, 0x409)     # Windows Unicode / English


def _resolve(val, m):
    """Knob → int. Accepts a callable lambda m: ... or a plain number."""
    return int(val(m)) if callable(val) else int(val)


def build_geo(upm, cap, xh, cell):
    m = SimpleNamespace(upm=upm, cap=cap, xh=xh, cell=cell)
    bar_bot = _resolve(config.BAR_BOT, m)
    bar_top = bar_bot + _resolve(config.BAR_THICKNESS, m)
    return {
        "upm":           upm,
        "cell":          cell,
        "bar_bot":       bar_bot,
        "bar_top":       bar_top,
        "tooth_0":       _resolve(config.TOOTH_0, m),
        "tooth_1":       _resolve(config.TOOTH_1, m),
        "tooth_w":       {k: _resolve(v, m) for k, v in config.TOOTH_W.items()},
        "inter_extra":   _resolve(config.INTER_EXTRA, m),
        "comma_p_w":     _resolve(config.COMMA_P_WIDTH, m),
        "comma_r_w":     _resolve(config.COMMA_R_WIDTH, m),
        "tick_w":        _resolve(config.TICK_WIDTH, m),
        "tick_bot":      _resolve(config.TICK_BOT, m),
        "stub_overflow": _resolve(config.STUB_OVERFLOW, m),
        "stub_thick":    _resolve(config.STUB_THICKNESS, m),
    }


def main():
    base_path = sys.argv[1] if len(sys.argv) > 1 else fetch_default_base()
    print(f"Loading base font: {base_path}")
    font = TTFont(base_path)

    upm = font["head"].unitsPerEm
    os2 = font["OS/2"]
    cap = os2.sCapHeight or (700 * upm // 1000)
    xh  = os2.sxHeight   or (500 * upm // 1000)

    cmap = font.getBestCmap()
    if ord('0') not in cmap:
        raise SystemExit("Base font does not cmap U+0030 ('0'); can't proceed.")
    cell = font["hmtx"][cmap[ord('0')]][0]

    geo = build_geo(upm, cap, xh, cell)
    print(f"  UPM={upm} cap={cap} x-height={xh} cell={cell} "
          f"bar=[{geo['bar_bot']},{geo['bar_top']}] "
          f"tooth_0_top={geo['tooth_0']} tooth_1_top={geo['tooth_1']}")

    add_rake_glyphs(font, geo)
    fea = build_fea(font)
    merge_calt_into_gsub(font, fea)

    # Make sure descender accommodates the comma tick
    tick_bot = geo["tick_bot"]
    if font["hhea"].descent > tick_bot:
        font["hhea"].descent = tick_bot - 50
        os2.usWinDescent = max(os2.usWinDescent, abs(tick_bot) + 50)
        os2.sTypoDescender = font["hhea"].descent

    fix_overlap_simple_flags(font)
    rename_font(font, config.FAMILY_NAME, config.STYLE_NAME)

    # Subset to a configured Unicode range so the inline-data-URI demo stays small.
    # GSUB-reachable glyphs (our rake.*) are kept automatically.
    # Use minimal-override options — earlier custom options broke GSUB processing
    # in browsers (uharfbuzz still worked, but Firefox/Chrome did not fire calt
    # for the resulting font; CLI pyftsubset defaults work).
    if os.environ.get("BR_SKIP_SUBSET") != "1":
        opts = SubsetOptions()
        opts.layout_features = ["*"]
        sub = Subsetter(options=opts)
        sub.populate(unicodes=list(config.SUBSET_UNICODES))
        sub.subset(font)

    output = config.OUTPUT or os.path.join(DIR, "BinaryRake.ttf")
    font.save(output)
    print(f"Wrote {output} ({os.path.getsize(output)} bytes)")


if __name__ == "__main__":
    main()
