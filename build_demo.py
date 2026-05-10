#!/usr/bin/env python3
"""Generate demo.html with BinaryRake.ttf inlined as a data URL."""
import base64
import html as html_lib
import os

DIR  = os.path.dirname(os.path.abspath(__file__))
TTF  = os.path.join(DIR, "BinaryRake.ttf")
HTML = os.path.join(DIR, "demo.html")


def esc(s):
    return html_lib.escape(s)


CODE_SAMPLE = """\
// Minimal RV32I decoder. Heavy on bit-twiddling: opcode masks and
// function codes in binary, machine code and memory addresses in hex.

const OPCODE_MASK: u32 = 0b01111111;
const FUNCT3_MASK: u32 = 0b00000111;
const FUNCT7_MASK: u32 = 0b01111111;
const REG_MASK:    u32 = 0b00011111;

const OP_LOAD:    u32 = 0b0000011;
const OP_STORE:   u32 = 0b0100011;
const OP_BRANCH:  u32 = 0b1100011;
const OP_JAL:     u32 = 0b1101111;
const OP_JALR:    u32 = 0b1100111;
const OP_OP_IMM:  u32 = 0b0010011;
const OP_OP:      u32 = 0b0110011;
const OP_LUI:     u32 = 0b0110111;
const OP_AUIPC:   u32 = 0b0010111;
const OP_SYSTEM:  u32 = 0b1110011;

const F3_ADD_SUB: u32 = 0b000;
const F3_SLL:     u32 = 0b001;
const F3_XOR:     u32 = 0b100;
const F3_OR:      u32 = 0b110;
const F3_AND:     u32 = 0b111;

const F7_ADD: u32 = 0b0000000;
const F7_SUB: u32 = 0b0100000;

// Encoded test programs (RV32I machine code)
const NOP:    u32 = 0x00000013; // addi x0, x0, 0
const RET:    u32 = 0x00008067; // jalr x0, 0(x1)
const EBREAK: u32 = 0x00100073;
const ECALL:  u32 = 0x00000073;

// QEMU virt board memory map
const RAM_BASE:    usize = 0x80000000;
const UART_BASE:   usize = 0x10000000;
const VIRTIO_BASE: usize = 0x10001000;
const CLINT_BASE:  usize = 0x02000000;
const PLIC_BASE:   usize = 0x0C000000;

// Page-table entry flags (Sv39)
const PTE_V: u64 = 0b00000001;  // valid
const PTE_R: u64 = 0b00000010;  // read
const PTE_W: u64 = 0b00000100;  // write
const PTE_X: u64 = 0b00001000;  // execute
const PTE_U: u64 = 0b00010000;  // user
const PTE_PPN_MASK: u64 = 0x003FFFFFFFFFFC00;

fn decode(insn: u32) -> Op {
    let opcode = insn & OPCODE_MASK;
    let rd     = (insn >> 0b00111) & REG_MASK;
    let funct3 = (insn >> 0b01100) & FUNCT3_MASK;
    let rs1    = (insn >> 0b01111) & REG_MASK;
    let rs2    = (insn >> 0b10100) & REG_MASK;
    let funct7 = (insn >> 0b11001) & FUNCT7_MASK;

    match opcode {
        OP_OP => match (funct3, funct7) {
            (F3_ADD_SUB, F7_ADD) => Op::Add { rd, rs1, rs2 },
            (F3_ADD_SUB, F7_SUB) => Op::Sub { rd, rs1, rs2 },
            (F3_AND,     F7_ADD) => Op::And { rd, rs1, rs2 },
            (F3_OR,      F7_ADD) => Op::Or  { rd, rs1, rs2 },
            (F3_XOR,     F7_ADD) => Op::Xor { rd, rs1, rs2 },
            _ => Op::Illegal,
        },
        OP_LUI => Op::Lui { rd, imm: insn & 0xFFFFF000 },
        OP_OP_IMM => Op::Addi { rd, rs1, imm: (insn as i32 >> 0b10100) as u32 },
        OP_SYSTEM if insn == ECALL  => Op::Ecall,
        OP_SYSTEM if insn == EBREAK => Op::Ebreak,
        _ => Op::Illegal,
    }
}

// PCI vendor IDs we care about
const VID_INTEL:    u16 = 0x8086;
const VID_AMD:      u16 = 0x1022;
const VID_NVIDIA:   u16 = 0x10DE;
const VID_REALTEK:  u16 = 0x10EC;
const VID_BROADCOM: u16 = 0x14E4;

// IPv4 private-range checks (network byte order)
fn is_private_v4(addr: u32) -> bool {
    addr & 0xFF000000 == 0x0A000000      // 10.0.0.0/8
 || addr & 0xFFF00000 == 0xAC100000      // 172.16.0.0/12
 || addr & 0xFFFF0000 == 0xC0A80000      // 192.168.0.0/16
}

// SHA-256 round constants K[0..16] — fractional parts of cube roots of primes
const K: [u32; 16] = [
    0x428A2F98, 0x71374491, 0xB5C0FBCF, 0xE9B5DBA5,
    0x3956C25B, 0x59F111F1, 0x923F82A4, 0xAB1C5ED5,
    0xD807AA98, 0x12835B01, 0x243185BE, 0x550C7DC3,
    0x72BE5D74, 0x80DEB1FE, 0x9BDC06A7, 0xC19BF174,
];
"""


# Each per-base section: a hero sample shown side-by-side (calt on / off),
# plus a few extra calt-on samples for scale variation.
BASE_SECTIONS = [
    ("Binary — 1 tooth per digit",      "0b11110000",  ["0b1010", "0b" + "01" * 16]),
    ("Quaternary — 2 teeth per digit",  "0q0123",      ["0q3210", "0q" + "0123" * 4]),
    ("Octal — 3 teeth per digit",       "0o755",       ["0o12345670"]),
    ("Hex — 4 teeth per digit",         "0xDEADBEEF",  ["0xCAFEBABE", "0x0123456789ABCDEF"]),
]

# 255 in each base — same value, four tooth densities.
SHOWCASE_255 = ["0b11111111", "0q3333", "0o377", "0xFF"]

# Period (p) — decimal-point analog. Repeat (r) — repeating-fraction marker.
PERIOD_REPEAT = ["0b1010p1010", "0o12p34", "0b101r01", "0xFFp00r1A"]

EDGE_CASES = [
    "0b",                            # bare prefix — no digits, nothing fires
    "0bf",                           # f isn't a binary digit — stays plain
    "0xff",                          # both f's ARE hex digits
    "0b2 (2 isn't a binary digit)",
]


def build():
    with open(TTF, "rb") as f:
        font_b64 = base64.b64encode(f.read()).decode("ascii")

    parts = []
    parts.append("<!doctype html>")
    parts.append("<html lang='en'><head><meta charset='utf-8'>")
    parts.append("<title>BinaryRake — font demo</title>")
    parts.append("<style>")
    parts.append("@font-face {")
    parts.append("  font-family: 'BinaryRake';")
    parts.append(f"  src: url(data:font/ttf;base64,{font_b64}) format('truetype');")
    parts.append("}")
    parts.append("""
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body {
  background: #0e0f12; color: #d6d6d6;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  padding: 32px; max-width: 1200px; margin: 0 auto;
  line-height: 1.5;
}
h1 { font-weight: 300; font-size: 32px; margin: 0 0 4px; letter-spacing: -0.5px; }
.lede { color: #9aa; max-width: 760px; margin-bottom: 28px; }
h2 { font-weight: 500; font-size: 13px; text-transform: uppercase;
     color: #6a7a8a; letter-spacing: 1px; margin: 36px 0 8px;
     border-bottom: 1px solid #1f2937; padding-bottom: 6px; }
.sample {
  font-family: 'BinaryRake', 'Menlo', monospace;
  font-feature-settings: 'calt' 1;
  background: #f6f6f3; color: #111;
  padding: 14px 18px; border-radius: 6px;
  margin: 4px 0;
  overflow-x: auto; white-space: nowrap;
}
.sample.raw { font-feature-settings: 'calt' 0; opacity: 0.85; }
.s24 { font-size: 24px; } .s32 { font-size: 32px; } .s48 { font-size: 48px; }
pre.code {
  font-family: 'BinaryRake', 'Menlo', monospace;
  font-feature-settings: 'calt' 1;
  background: #f6f6f3; color: #111;
  padding: 18px 20px; border-radius: 6px;
  margin: 6px 0; font-size: 18px; line-height: 1.45;
  overflow-x: auto; tab-size: 4;
}
pre.code.raw { font-feature-settings: 'calt' 0; }
pre.code .com { color: #6a8a6a; }
.toggle-row { display: flex; align-items: center; gap: 12px; margin: 8px 0; }
.toggle-btn {
  background: #1a1f28; color: #d4af37;
  border: 1px solid #2a3140; padding: 6px 14px; border-radius: 4px;
  cursor: pointer; font-family: 'SF Mono', Menlo, monospace; font-size: 13px;
  letter-spacing: 0.5px;
}
.toggle-btn:hover { background: #232a36; border-color: #3a4458; }
.toggle-btn[aria-pressed="false"] { color: #6a7a8a; }
.pair { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 4px 0; }
.pair > div { margin: 0; }
.pair-label { color: #6a7a8a; font-size: 11px; font-family: monospace;
              text-transform: uppercase; letter-spacing: 1px; padding: 2px 4px; }
code { background: #1a1f28; padding: 1px 6px; border-radius: 3px;
       font-size: 0.9em; color: #d4af37; }
.legend {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px 16px;
  margin: 12px 0 24px; font-size: 13px; color: #aab;
  background: #161922; padding: 12px 16px; border-radius: 6px;
}
.legend > div { line-height: 1.35; }
.legend strong { color: #ddd; font-family: 'SF Mono', Menlo, monospace;
                 display: block; margin-bottom: 2px; }
.legend small { color: #6a7a8a; font-size: 11px; }
""")
    parts.append("</style></head><body>")

    parts.append("<h1>BinaryRake</h1>")
    parts.append("<p class='lede'>A TrueType font that collapses numeric literals into a "
                 "<em>rake ligature</em> — a continuous bar with one tooth per bit. The four "
                 "bases share the same bar pitch but pack 1 / 2 / 3 / 4 teeth per digit cell. "
                 "Inside a literal, <code>p</code> is a downward tick (decimal-point analog) and "
                 "<code>r</code> adds a rightward stub (repeating-fraction marker).</p>")

    parts.append(
        "<div class='legend'>"
        "<div><strong>0b…</strong>1 tooth / digit</div>"
        "<div><strong>0q…</strong>2 teeth / digit</div>"
        "<div><strong>0o…</strong>3 teeth / digit</div>"
        "<div><strong>0x…</strong>4 teeth / digit</div>"
        "<div><strong>tall</strong>bit = 1</div>"
        "<div><strong>short</strong>bit = 0</div>"
        "<div><strong>p</strong>decimal point</div>"
        "<div><strong>r</strong>repeat marker</div>"
        "</div>")

    def pair(s):
        return ("<div class='pair'>"
                f"<div class='sample s32'>{esc(s)}</div>"
                f"<div class='sample raw s32'>{esc(s)}</div>"
                "</div>")

    pair_header = ("<div class='pair'>"
                   "<div class='pair-label'>calt on  (rake)</div>"
                   "<div class='pair-label'>calt off (raw)</div>"
                   "</div>")

    def section(title, samples):
        parts.append(f"<h2>{esc(title)}</h2>")
        parts.append(pair_header)
        for s in samples:
            parts.append(pair(s))

    for title, hero, extras in BASE_SECTIONS:
        section(title, [hero] + extras)

    section("Same value, four densities — 255 in each base", SHOWCASE_255)
    section("Period and repeat markers", PERIOD_REPEAT)
    section("Edge cases", EDGE_CASES)

    parts.append("<h2>Realistic code — RV32I decoder, page-table flags, SHA-256 K[]</h2>")
    parts.append("<p style='color:#9aa;font-size:13px;margin:0 0 12px;'>"
                 "Every <code>0b…</code> and <code>0x…</code> is a rake; the rest is the "
                 "base font (Iosevka). Toggle <code>calt</code> to see the underlying glyphs.</p>")
    # Lightly highlight comments to make the code easier to read.
    code_lines = []
    for line in CODE_SAMPLE.splitlines():
        # Naive comment split: only the line-comment style "// ..." appears here.
        if "//" in line:
            head, _, tail = line.partition("//")
            code_lines.append(esc(head) + "<span class='com'>" + esc("//" + tail) + "</span>")
        else:
            code_lines.append(esc(line))
    parts.append(
        "<div class='toggle-row'>"
        "<button class='toggle-btn' id='caltBtn' aria-pressed='true' "
        "onclick=\"const c=document.getElementById('codeBlock');"
        "const on=this.getAttribute('aria-pressed')!=='true';"
        "this.setAttribute('aria-pressed', on?'true':'false');"
        "c.classList.toggle('raw', !on);"
        "this.textContent = on ? 'calt: ON' : 'calt: OFF';"
        "\">calt: ON</button>"
        "<span style='color:#6a7a8a;font-size:12px;'>"
        "toggle the rake substitution for the code block</span>"
        "</div>")
    parts.append("<pre class='code' id='codeBlock'>" + "\n".join(code_lines) + "</pre>")

    parts.append("</body></html>")

    with open(HTML, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"Wrote {HTML} ({os.path.getsize(HTML)} bytes)")


if __name__ == "__main__":
    build()
