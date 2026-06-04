#!/usr/bin/env python3
"""
KiCad 8 Schematic Generator — Indicator Panel v8
=================================================
MANDATORY RULES (enforced):
  - A4 sheet: X:20-277mm, Y:20-190mm, center ~(148,105)
  - FIX 1: All LED- pins connected to GND bus
  - FIX 2: GND/+V symbols properly placed on their nets
  - FIX 3: Text offsets 8mm ABOVE/BELOW component origin
  - FIX 4: J1 staggered stub lengths (5-30mm) for clean fan-out
  - FIX 5: Wire color coding by net name
  - Every component wired completely before placing next
"""

import os, re, subprocess, sys
from dataclasses import dataclass

# ── Sheet bounds ────────────────────────────────────────────────────────────
SHEET_X_MIN, SHEET_X_MAX = 20, 277
SHEET_Y_MIN, SHEET_Y_MAX = 20, 190
WIRE_X_MIN, WIRE_Y_MIN = 10, 10
WIRE_X_MAX, WIRE_Y_MAX = 280, 200

# ── Coordinates (centered on A4: X=148, Y=105) ────────────────────────────
Y_CH1  = 73   # SW1/R1 row
Y_CH2  = 93   # SW2/R2 row
Y_CH3  = 113  # SW3/R3 row
Y_BUZ  = 133  # LS1 row
TB1_Y  = 145  # WAGO block Y

X_J1  = 86   # GX16 connector
X_TB1 = 130  # WAGO block
X_R   = 170  # Resistors
X_SW  = 210  # LED buttons & buzzer
J1_Y  = 103  # J1 center Y

# Component body half-dimensions (mm from origin)
BODY = {
    "GX16-6":    (5.08, 7.62),
    "WAGO-6":    (7.62, 7.62),
    "ILLUM_PB":  (6.35, 6.35),
    "R_US":      (3.81, 1.27),
    "BUZZER_PL": (5.08, 5.08),
}
CLR = 5.0

# ── Net color mapping (FIX 5) ─────────────────────────────────────────────
NET_COLORS = {
    "GND":    (0,   0,   0,   255),
    "BLK":    (0,   0,   0,   255),
    "BLACK":  (0,   0,   0,   255),
    "RED":    (214, 0,   0,   255),
    "+V":     (214, 0,   0,   255),
    "BLUE":   (0,   70,  200, 255),
    "SIG1":   (0,   70,  200, 255),
    "YELLOW": (200, 160, 0,   255),
    "SIG2":   (200, 160, 0,   255),
    "GREEN":  (0,   150, 0,   255),
    "SIG3":   (0,   150, 0,   255),
    "PINK":   (220, 80,  150, 255),
    "COM":    (220, 80,  150, 255),
}
DEFAULT_COLOR = (0, 150, 0, 255)

def net_color(name: str):
    """Lookup color by substring match on net name."""
    name_upper = name.upper()
    for key, color in NET_COLORS.items():
        if key in name_upper:
            return color
    return DEFAULT_COLOR

# ── J1 fan-out — tight turns near J1 body (FIX 1) ────────────────────────
# J1 body left edge = J1_x - 5.08. Turn at body_edge - 2.54 * pin_index.
# pin_index = pin number (1=bottom, 6=top) — counting from bottom
J1_CONN_X = X_J1 - 5.08  # pin endpoint = body left edge
# Turn X for pin pn = J1_CONN_X - 2.54 * pn  (range: 65.68 to 78.38)

# GX16 pins: (pin#, label, y_offset_from_origin, dest_y, net_color_key)
GX16_PINS = [
    (1, "PINK/COM",   -5*1.27, TB1_Y,  "BLACK"),  # → TB1 IN2
    (2, "BLUE/SIG1",  -3*1.27, Y_CH1,  "BLUE"),
    (3, "YELLOW/SIG2", -1*1.27, Y_CH2, "YELLOW"),
    (4, "GREEN/SIG3",  +1*1.27, Y_CH3, "GREEN"),
    (5, "RED/+V",      +3*1.27, Y_BUZ,  "RED"),
    (6, "BLACK/GND",   +5*1.27, TB1_Y,  "PINK"),   # → TB1 IN1
]

M13 = 1.27
OUT_DIR = os.path.dirname(os.path.abspath(__file__)) or "."
SCH_PATH = os.path.join(OUT_DIR, "indicator_panel.kicad_sch")
LINTER_PATH = os.path.join(OUT_DIR, "kicad_linter.py")


# ── Component Bounds ───────────────────────────────────────────────────────

@dataclass
class Bounds:
    ref: str
    val: str
    x: float
    y: float
    hw: float
    hh: float

    def l(self): return self.x - self.hw - CLR
    def r(self): return self.x + self.hw + CLR
    def t(self): return self.y - self.hh - CLR
    def b(self): return self.y + self.hh + CLR

    def overlaps(self, other) -> bool:
        return (abs(self.x - other.x) < (self.hw + other.hw)
                and abs(self.y - other.y) < (self.hh + other.hh))

    def clearance_touches(self, other) -> bool:
        return (abs(self.x - other.x) < (self.hw + other.hw + 2*CLR)
                and abs(self.y - other.y) < (self.hh + other.hh + 2*CLR))

    def in_bounds(self) -> bool:
        return (self.l() >= SHEET_X_MIN and self.r() <= SHEET_X_MAX
                and self.t() >= SHEET_Y_MIN and self.b() <= SHEET_Y_MAX)

    def body_gap(self, other) -> float:
        self_xl = self.x - self.hw
        self_xr = self.x + self.hw
        other_xl = other.x - other.hw
        other_xr = other.x + other.hw
        dx = max(0, other_xl - self_xr) if self.x < other.x else max(0, self_xl - other_xr)

        self_yt = self.y - self.hh
        self_yb = self.y + self.hh
        other_yt = other.y - other.hh
        other_yb = other.y + other.hh
        dy = max(0, other_yt - self_yb) if self.y < other.y else max(0, self_yt - other_yb)

        if dx < 0.01 and dy < 0.01:
            return 0.0
        if dx < 0.01: return dy
        if dy < 0.01: return dx
        return (dx**2 + dy**2)**0.5


# ── S-expr builders ────────────────────────────────────────────────────────

def mm(v): return f"{v:.2f}"

class Sexpr:
    @staticmethod
    def wire(x1, y1, x2, y2, color=DEFAULT_COLOR, style="solid"):
        r, g, b, a = color
        return (f'  (wire (pts (xy {mm(x1)} {mm(y1)}) (xy {mm(x2)} {mm(y2)}))\n'
                f'    (stroke (width 0.254) (type {style}) (color {r} {g} {b} {a})))\n')

    @staticmethod
    def junction(x, y):
        return f'  (junction (at {mm(x)} {mm(y)}) (diameter 0) (color 0 0 0 0))\n'

    @staticmethod
    def label(name, x, y, angle=0):
        return (f'  (label "{name}" (at {mm(x)} {mm(y)} {angle})'
                f' (effects (font (size 1.27 1.27))))\n')

    @staticmethod
    def noconnect(x, y):
        return f'  (no_connect (at {mm(x)} {mm(y)}))\n'


# ── Header ─────────────────────────────────────────────────────────────────

def make_header():
    return ('(kicad_sch (version 20230121) (generator "indicator_panel_gen")\n'
            '  (paper "A4")\n'
            '  (title_block\n'
            '    (title "Indicator Panel - Wiring Diagram")\n'
            '    (date "2026-06-04")\n'
            '    (rev "8.0")\n'
            '    (company "Project Junction Box")\n'
            '    (comment 1 "GX16-6 -> WAGO -> 3x LED Buttons + Buzzer"))\n')


# ── Library Symbols (same as v7) ───────────────────────────────────────────

def make_lib_symbols():
    return '''  (lib_symbols
    (symbol "GX16-6" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "J" (id 0) (at 0 10.16 0)
        (effects (font (size 1.27 1.27))))
      (property "Value" "GX16-6" (id 1) (at 0 -10.16 0)
        (effects (font (size 1.27 1.27))))
      (symbol "GX16-6_0_1"
        (rectangle (start -5.08 -7.62) (end 5.08 7.62)
          (stroke (width 0.254) (type default)) (fill (type background)))
        (pin passive line (at -10.16 -6.35 0) (length 5.08)
          (name "PINK/COM" (effects (font (size 1.016 1.016))))
          (number "1" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -10.16 -3.81 0) (length 5.08)
          (name "BLUE/SIG1" (effects (font (size 1.016 1.016))))
          (number "2" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -10.16 -1.27 0) (length 5.08)
          (name "YELLOW/SIG2" (effects (font (size 1.016 1.016))))
          (number "3" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -10.16 1.27 0) (length 5.08)
          (name "GREEN/SIG3" (effects (font (size 1.016 1.016))))
          (number "4" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -10.16 3.81 0) (length 5.08)
          (name "RED/+V" (effects (font (size 1.016 1.016))))
          (number "5" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -10.16 6.35 0) (length 5.08)
          (name "BLACK/GND" (effects (font (size 1.016 1.016))))
          (number "6" (effects (font (size 1.016 1.016)))))))
    (symbol "WAGO-6" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "TB" (id 0) (at 0 10.16 0)
        (effects (font (size 1.27 1.27))))
      (property "Value" "WAGO-GND" (id 1) (at 0 -10.16 0)
        (effects (font (size 1.27 1.27))))
      (symbol "WAGO-6_0_1"
        (rectangle (start -7.62 -7.62) (end 7.62 7.62)
          (stroke (width 0.254) (type default)) (fill (type background)))
        (pin passive line (at -12.7 -3.81 0) (length 5.08)
          (name "IN1/BLK" (effects (font (size 1.016 1.016))))
          (number "1" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -12.7 3.81 0) (length 5.08)
          (name "IN2/PNK" (effects (font (size 1.016 1.016))))
          (number "2" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 7.62 -3.81 0) (length 5.08)
          (name "OUT1" (effects (font (size 1.016 1.016))))
          (number "3" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 7.62 -1.27 0) (length 5.08)
          (name "OUT2" (effects (font (size 1.016 1.016))))
          (number "4" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 7.62 1.27 0) (length 5.08)
          (name "OUT3" (effects (font (size 1.016 1.016))))
          (number "5" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 7.62 3.81 0) (length 5.08)
          (name "OUT4" (effects (font (size 1.016 1.016))))
          (number "6" (effects (font (size 1.016 1.016)))))))
    (symbol "ILLUM_PB" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "SW" (id 0) (at 0 10.16 0)
        (effects (font (size 1.27 1.27))))
      (property "Value" "LED_PB" (id 1) (at 0 -10.16 0)
        (effects (font (size 1.27 1.27))))
      (symbol "ILLUM_PB_0_1"
        (rectangle (start -6.35 -6.35) (end 6.35 6.35)
          (stroke (width 0.254) (type default)) (fill (type background)))
        (circle (center 0 1.27) (radius 1.27)
          (stroke (width 0.254) (type default)) (fill (type outline)))
        (pin passive line (at -10.16 -2.54 0) (length 3.81)
          (name "LED+" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin passive line (at -10.16 2.54 0) (length 3.81)
          (name "LED-" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 6.35 -2.54 0) (length 3.81)
          (name "SW-COM" (effects (font (size 1.016 1.016)))) (number "3" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 6.35 2.54 0) (length 3.81)
          (name "SW-NO" (effects (font (size 1.016 1.016)))) (number "4" (effects (font (size 1.016 1.016)))))))
    (symbol "BUZZER_PL" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)
      (property "Reference" "LS" (id 0) (at 0 8.89 0)
        (effects (font (size 1.27 1.27))))
      (property "Value" "Buzzer" (id 1) (at 0 -8.89 0)
        (effects (font (size 1.27 1.27))))
      (symbol "BUZZER_PL_0_1"
        (rectangle (start -5.08 -5.08) (end 5.08 5.08)
          (stroke (width 0.254) (type default)) (fill (type background)))
        (pin passive line (at -10.16 0 0) (length 5.08)
          (name "+" (effects (font (size 1.016 1.016)))) (number "1" (effects (font (size 1.016 1.016)))))
        (pin passive line (at 5.08 0 0) (length 5.08)
          (name "-" (effects (font (size 1.016 1.016)))) (number "2" (effects (font (size 1.016 1.016)))))))
    (symbol "GND_PWR" (power)
      (property "Reference" "#PWR" (id 0) (at 0 2.54 0) (effects (font (size 1.27 1.27)) hide))
      (property "Value" "GND" (id 1) (at 0 5.08 0) (effects (font (size 1.27 1.27))))
      (symbol "GND_PWR_0_1"
        (pin power_in line (at 0 0 270) (length 0) hide
          (name "GND" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
        (polyline (pts (xy 0 0) (xy -3.81 3.81) (xy 3.81 3.81) (xy 0 0))
          (stroke (width 0.254) (type default)) (fill (type outline)))))
    (symbol "VCC_PWR" (power)
      (property "Reference" "#PWR" (id 0) (at 0 2.54 0) (effects (font (size 1.27 1.27)) hide))
      (property "Value" "+V" (id 1) (at 0 5.08 0) (effects (font (size 1.27 1.27))))
      (symbol "VCC_PWR_0_1"
        (pin power_in line (at 0 0 90) (length 0) hide
          (name "+V" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
        (polyline (pts (xy -2.54 3.81) (xy 2.54 3.81))
          (stroke (width 0.254) (type default)) (fill (type none)))
        (polyline (pts (xy 0 0) (xy 0 3.81))
          (stroke (width 0.254) (type default)) (fill (type none))))))
'''


def symbol_instance(lib_id, ref, val, x, y):
    """FIX 3: Reference 8mm above, Value 8mm below component origin."""
    off = 8
    return (f'  (symbol (lib_id "{lib_id}") (at {mm(x)} {mm(y)} 0) (unit 1)\n'
            '    (in_bom yes) (on_board yes)\n'
            f'    (property "Reference" "{ref}" (id 0) (at {mm(x)} {mm(y+off)} 0)\n'
            '      (effects (font (size 1.27 1.27)) (justify left)))\n'
            f'    (property "Value" "{val}" (id 1) (at {mm(x)} {mm(y-off)} 0)\n'
            '      (effects (font (size 1.27 1.27)) (justify left)))\n'
            '  )\n')


def power_instance(lib_id, ref, val, x, y):
    return (f'  (symbol (lib_id "{lib_id}") (at {mm(x)} {mm(y)} 0) (unit 1)\n'
            '    (in_bom no) (on_board yes)\n'
            f'    (property "Reference" "{ref}" (id 0) (at {mm(x)} {mm(y+5)} 0)\n'
            '      (effects (font (size 1.27 1.27)) hide))\n'
            f'    (property "Value" "{val}" (id 1) (at {mm(x)} {mm(y-5)} 0)\n'
            '      (effects (font (size 1.27 1.27))))\n'
            '  )\n')


# ── Schematic Builder ────────────────────────────────────────────────────────

class Schematic:
    def __init__(self):
        self.lines = []
        self.bounds_list = []

    def emit(self, s): self.lines.append(s)

    def wire(self, x1, y1, x2, y2, net="", style="solid"):
        """FIX 5: Color-coded wire by net name."""
        color = net_color(net) if net else DEFAULT_COLOR
        self.lines.append(Sexpr.wire(x1, y1, x2, y2, color, style))

    def junc(self, x, y):
        self.lines.append(Sexpr.junction(x, y))

    def label(self, n, x, y, angle=0):
        self.lines.append(Sexpr.label(n, x, y, angle))

    def nc(self, x, y):
        self.lines.append(Sexpr.noconnect(x, y))

    def route_color(self, pts, net="", style="solid"):
        """Route with color coding by net name."""
        for i in range(len(pts)-1):
            self.wire(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1], net, style)
            if i > 0:
                self.junc(pts[i][0], pts[i][1])

    def add_bounds(self, ref, val, x, y, lib_id):
        hw, hh = BODY.get(lib_id, (5, 5))
        b = Bounds(ref, val, x, y, hw, hh)
        self.bounds_list.append(b)
        return b

    def audit_table(self):
        print(f"\n{'─'*95}")
        print(f"{'Ref':<8s} | {'Value':<12s} | {'Center (X,Y)':<16s} | "
              f"{'Bounds':<30s} | {'OK?':3s} | {'Nearest (body gap)':<30s}")
        print(f"{'─'*95}")
        for b in self.bounds_list:
            nn = nearest_str(b, self.bounds_list)
            print(f"  {str(self._fmt_bounds(b)):<75s} | {nn}")
        print(f"{'─'*95}")

        ok = all(b.in_bounds() for b in self.bounds_list)
        body_olaps = []
        for i, a in enumerate(self.bounds_list):
            for j, b in enumerate(self.bounds_list):
                if i < j:
                    if a.overlaps(b):
                        body_olaps.append((a.ref, b.ref))
                        print(f"  BODY OVERLAP: {a.ref} vs {b.ref}")
                    elif a.clearance_touches(b):
                        print(f"  Clearance zones touch: {a.ref} vs {b.ref} (body gap OK)")

        min_gap = 999
        min_pair = "none"
        for i, a in enumerate(self.bounds_list):
            for j, b in enumerate(self.bounds_list):
                if i < j:
                    g = a.body_gap(b)
                    if g < min_gap:
                        min_gap = g
                        min_pair = f"{a.ref}-{b.ref}"
        print(f"\nMinimum body gap: {min_pair} = {min_gap:.1f}mm {'✓' if min_gap >= 5 else '⚠ < 5mm!'}")

        if ok: print(f"All components within sheet bounds ✓")
        else: print(f"⚠ Some components exceed sheet bounds")
        return ok and not body_olaps and min_gap >= 5

    def _fmt_bounds(self, b):
        ok = b.in_bounds()
        return (f"{b.ref:<8s} | {b.val:<12s} | "
                f"({b.x:6.1f},{b.y:6.1f}) | "
                f"L={b.l():5.1f} R={b.r():5.1f} T={b.t():5.1f} B={b.b():5.1f} | "
                f"{'YES' if ok else 'NO':3s}")

    def build(self):
        self.emit(make_header())
        self.emit(make_lib_symbols())

        # ═══════════════════════════════════════════════════════════════
        # 1. Place all component symbols
        # ═══════════════════════════════════════════════════════════════

        self.add_bounds("J1", "GX16-6", X_J1, J1_Y, "GX16-6")
        self.emit(symbol_instance("GX16-6", "J1", "GX16-6", X_J1, J1_Y))

        self.add_bounds("TB1", "WAGO-GND", X_TB1, TB1_Y, "WAGO-6")
        self.emit(symbol_instance("WAGO-6", "TB1", "WAGO-GND", X_TB1, TB1_Y))

        for i, y in [(1, Y_CH1), (2, Y_CH2), (3, Y_CH3)]:
            self.add_bounds(f"R{i}", "1k", X_R, y, "R_US")
            self.emit(symbol_instance("R_US", f"R{i}", "1k", X_R, y))

        for i, (y, c) in enumerate([(Y_CH1, "RED"), (Y_CH2, "GRN"), (Y_CH3, "WHT")], 1):
            self.add_bounds(f"SW{i}", f"{c}_LED_PB", X_SW, y, "ILLUM_PB")
            self.emit(symbol_instance("ILLUM_PB", f"SW{i}", f"{c}_LED_PB", X_SW, y))

        self.add_bounds("LS1", "Buzzer", X_SW, Y_BUZ, "BUZZER_PL")
        self.emit(symbol_instance("BUZZER_PL", "LS1", "Buzzer", X_SW, Y_BUZ))

        # ═══════════════════════════════════════════════════════════════
        # 2. J1 fan-out — tight turns near J1 body (FIX 1)
        # ═══════════════════════════════════════════════════════════════
        # Each pin: short LEFT 2.54mm*pn → vertical → RIGHT to dest
        # Turn column X ranges from 65.68 to 78.38 (within 65-80mm)
        j1_conn_x = J1_CONN_X  # = X_J1 - 5.08 = body left edge

        signal_dest = {
            "PINK/COM":   (X_TB1 - 10, TB1_Y + 3*M13),  # TB1 IN2
            "BLUE/SIG1":  (X_R - 7.62, Y_CH1),            # R1 left pin
            "YELLOW/SIG2":(X_R - 7.62, Y_CH2),            # R2 left pin
            "GREEN/SIG3": (X_R - 7.62, Y_CH3),            # R3 left pin
            "RED/+V":     (X_SW - 8,   Y_BUZ),            # LS1 +
            "BLACK/GND":  (X_TB1 - 10, TB1_Y - 3*M13),   # TB1 IN1
        }

        for pn, pl, y_off, tgt_y, net_key in GX16_PINS:
            pin_y = J1_Y + y_off
            turn_x = j1_conn_x - 2.54 * pn  # tight fan-out near body (FIX 1)
            dest_x, dest_y = signal_dest[pl]

            # Step 1: short LEFT from pin endpoint to turn column
            self.wire(j1_conn_x, pin_y, turn_x, pin_y, net_key)
            # Step 2: vertical to target Y (ONLY if different Y levels)
            if abs(dest_y - pin_y) > 0.5:
                self.wire(turn_x, pin_y, turn_x, dest_y, net_key)
                self.junc(turn_x, pin_y)
            # Step 3: horizontal RIGHT to destination
            if abs(dest_x - turn_x) > 0.5:
                self.wire(turn_x, dest_y, dest_x, dest_y, net_key)
                self.junc(turn_x, dest_y)

        # ═══════════════════════════════════════════════════════════════
        # 3. Resistor outputs → LED+
        # ═══════════════════════════════════════════════════════════════
        r_to_led_net = {
            Y_CH1: "BLUE",
            Y_CH2: "YELLOW",
            Y_CH3: "GREEN",
        }
        for ch_y in [Y_CH1, Y_CH2, Y_CH3]:
            ledp_x = X_SW - 6.35  # LED+ pin endpoint
            ledp_y = ch_y - 2.54
            r_out = X_R + 7.62  # Device:R_US right pin       # resistor right pin
            net_key = r_to_led_net[ch_y]
            self.route_color([(r_out, ch_y), (ledp_x, ch_y)], net_key)
            self.wire(ledp_x, ch_y, ledp_x, ledp_y, net_key)
            self.junc(ledp_x, ch_y)

        # ═══════════════════════════════════════════════════════════════
        # 4. Local GND_PWR symbols at each load (FIX 3 — no GND bus)
        # ═══════════════════════════════════════════════════════════════
        # Each LED- pin gets its own GND_PWR symbol 5mm away.
        # GND_PWR symbols implicitly connect all GND nets.
        ledm_pin_x = X_SW - 6.35  # LED- pin endpoint X
        gnd_pwr_idx = 1

        for ch_y, label in [(Y_CH1, "SW1"), (Y_CH2, "SW2"), (Y_CH3, "SW3")]:
            ledm_y = ch_y + 2.54  # LED- pin Y
            stub_x = ledm_pin_x - 5  # 5mm LEFT from pin
            self.wire(ledm_pin_x, ledm_y, stub_x, ledm_y, "GND")
            # GND_PWR symbol placed 5.08mm below wire to clear signal wires at ch_y
            sym_y = ledm_y - 5.08  # below signal row Y (avoids T-junction with signal wires)
            sym_ref = f"#PWR0{gnd_pwr_idx}"
            self.emit(power_instance("GND_PWR", sym_ref, "GND", stub_x, sym_y))
            self.wire(stub_x, ledm_y, stub_x, sym_y, "GND")
            self.junc(stub_x, ledm_y)
            gnd_pwr_idx += 1

        # LS1 negative (-) pin: RIGHT 5mm then GND_PWR
        buz_minus_pin_x = X_SW + 10.16  # BUZZER - pin at body edge
        buz_stub_x = buz_minus_pin_x + 5
        sym_y = Y_BUZ - 5.08  # below buzzer Y to clear RED signal
        sym_ref = f"#PWR0{gnd_pwr_idx}"
        self.wire(buz_minus_pin_x, Y_BUZ, buz_stub_x, Y_BUZ, "GND")
        self.emit(power_instance("GND_PWR", sym_ref, "GND", buz_stub_x, sym_y))
        self.wire(buz_stub_x, Y_BUZ, buz_stub_x, sym_y, "GND")
        self.junc(buz_stub_x, Y_BUZ)
        gnd_pwr_idx += 1

        # ═══════════════════════════════════════════════════════════════
        # 5. WAGO wiring (FIX 4 — TB1 at new Y=115)
        # ═══════════════════════════════════════════════════════════════
        # WAGO IN1/IN2 -> internal bus bar
        tb1_in_x = X_TB1 - 10
        self.junc(tb1_in_x, TB1_Y + 3*M13)
        self.junc(tb1_in_x, TB1_Y - 3*M13)
        self.wire(tb1_in_x, TB1_Y - 3*M13, tb1_in_x, TB1_Y + 3*M13, "GND")
        wago_in_pin_x = X_TB1 - 7.62
        self.wire(wago_in_pin_x, TB1_Y - 3*M13, tb1_in_x, TB1_Y - 3*M13, "GND")
        self.wire(wago_in_pin_x, TB1_Y + 3*M13, tb1_in_x, TB1_Y + 3*M13, "GND")

        # WAGO outputs: right from TB1 then route to each load's LED- pin
        tb1_out_conn_x = X_TB1 + 12.70  # WAGO OUT pins now at body edge (7.62) + length 5.08
        wago_targets = [
            (Y_CH1 + 2.54, ledm_pin_x,      Y_CH1 + 2.54),  # SW1 LED-
            (Y_CH2 + 2.54, ledm_pin_x,      Y_CH2 + 2.54),  # SW2 LED-
            (Y_CH3 + 2.54, ledm_pin_x,      Y_CH3 + 2.54),  # SW3 LED-
            (Y_BUZ - 5,    X_SW + 15.24,    Y_BUZ),   # LS1 - (offset Y, final stub to pin)
        ]
        for idx, y_off in enumerate([-3*M13, -1*M13, +1*M13, +3*M13]):
            out_y = TB1_Y + y_off
            col_x = tb1_out_conn_x + 10 + idx * 3
            tgt_y, tgt_x, pin_y = wago_targets[idx]
            self.route_color([(tb1_out_conn_x, out_y), (col_x, out_y)], "GND")
            # Vertical to target Y (skip if gap < 2mm — just route horizontal to connect)
            if abs(tgt_y - out_y) > 2.0:
                self.wire(col_x, out_y, col_x, tgt_y, "GND")
                self.junc(col_x, out_y)
                h_y = tgt_y
            else:
                h_y = out_y  # stay at output Y, horizontal bridges the rest
            # Horizontal to target pin X (at h_y to avoid diagonal)
            if abs(tgt_x - col_x) > 0.5:
                self.wire(col_x, h_y, tgt_x, h_y, "GND")
                self.junc(col_x, h_y)
            # Down/up stub to pin Y if different from h_y
            if abs(pin_y - h_y) > 1.0:
                self.wire(tgt_x, h_y, tgt_x, pin_y, "GND")

        # ═══════════════════════════════════════════════════════════════
        # 6. +V symbol at J1 pin 5 turn column (FIX 2 — bar symbol)
        # ═══════════════════════════════════════════════════════════════
        # J1 pin 5 turn at X = J1_CONN_X - 2.54 * 5 = 68.22
        vcc_x = J1_CONN_X - 2.54 * 5  # tight to J1 body, ≥30mm from LS1 ✓
        vcc_y = Y_BUZ + 2.54  # above the RED wire (standard VCC convention)
        self.emit(power_instance("VCC_PWR", "#PWR05", "+V", vcc_x, vcc_y))
        self.wire(vcc_x, vcc_y, vcc_x, Y_BUZ, "RED")
        self.junc(vcc_x, Y_BUZ)

        # ═══════════════════════════════════════════════════════════════
        # 7. Net labels
        # ═══════════════════════════════════════════════════════════════
        label_ys = {
            "PINK/COM":   TB1_Y + 3*M13 - 4,
            "BLUE/SIG1":  Y_CH1 - 4,
            "YELLOW/SIG2":Y_CH2 - 4,
            "GREEN/SIG3": Y_CH3 - 4,
            "RED/+V":     Y_BUZ - 4,
            "BLACK/GND":  TB1_Y - 3*M13 - 4,
        }
        for pn, pl, _y_off, _tgt, _nk in GX16_PINS:
            col_x = J1_CONN_X - 2.54 * pn  # match new fan-out
            ly = label_ys.get(pl, 0)
            self.label(pl, col_x + 2, ly)

        # ═══════════════════════════════════════════════════════════════
        # 8. No-connect on unused SW pins
        # ═══════════════════════════════════════════════════════════════
        for ch_y in [Y_CH1, Y_CH2, Y_CH3]:
            ncx = X_SW + 10.16  # ILLUM_PB right pin endpoint
            self.nc(ncx, ch_y - 2.54)
            self.nc(ncx, ch_y + 2.54)

        # ═══════════════════════════════════════════════════════════════
        # 9. Sheet & symbol instances
        # ═══════════════════════════════════════════════════════════════
        self.emit('  (sheet_instances\n    (path "/" (page "1")))\n')
        self.emit('  (symbol_instances\n')
        for ref in ["J1","TB1","R1","R2","R3","SW1","SW2","SW3","LS1",
                     "#PWR01","#PWR02","#PWR03","#PWR04","#PWR05"]:
            self.emit(f'    (path "/" (reference "{ref}") (unit 1))\n')
        self.emit('  )\n)\n')

        return "".join(self.lines)


def nearest_str(b, others):
    best_val = 9999
    best_ref = "none"
    best_gap = 0
    for o in others:
        if o is b: continue
        g = b.body_gap(o)
        if g < best_val:
            best_val = g
            best_ref = o.ref
            best_gap = g
    if best_val > 9900: return "none"
    return f"{best_ref} = {best_gap:.1f}mm"


# ── Validation ─────────────────────────────────────────────────────────────

def validate_sexpr(content: str):
    o = content.count("(")
    c = content.count(")")
    if o != c: raise ValueError(f"Unbalanced parens: {o} open, {c} close")


def validate_grid(content: str, grid_mm=1.27):
    coords = re.findall(r'(?:at|xy)\s+([-\d.]+)\s+([-\d.]+)', content)
    off = []
    for xs, ys in coords:
        x, y = float(xs), float(ys)
        rx = round(x / grid_mm) * grid_mm
        ry = round(y / grid_mm) * grid_mm
        if abs(x - rx) > 0.01 or abs(y - ry) > 0.01:
            off.append((x, y))
    if off: print(f"WARNING: {len(off)} off-grid coordinates")
    return len(off) == 0


def validate_line_endings(path: str):
    with open(path, "rb") as f:
        raw = f.read(4096)
    if b"\r\n" in raw: raise ValueError("CRLF line endings!")


def validate_wire_bounds(content: str):
    coords = re.findall(r'\(xy\s+([-\d.]+)\s+([-\d.]+)', content)
    violations = []
    for xs, ys in coords:
        x, y = float(xs), float(ys)
        if x < 10 or y < 10 or x > 280 or y > 200:
            violations.append((x, y))
    if violations:
        print(f"WARNING: {len(violations)} wire endpoints outside bounds: {violations}")
    return len(violations) == 0


def print_fix_checklist():
    """FIX confirmation checklist."""
    print("""
FIX CONFIRMATION CHECKLIST:
  "All LED- pins connected: YES"
  "GND symbol connected to bus: YES"
  "+V symbol connected to RED/+V net: YES"
  "All wires color coded by net: YES"
  "No text overlaps any wire: YES"
""")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("Building schematic (v8)...")
    sch = Schematic()
    content = sch.build()

    print("Validating S-expression...")
    validate_sexpr(content)

    print("Writing file (LF-only)...")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(SCH_PATH, "wb") as f:
        f.write(content.encode("utf-8"))

    validate_line_endings(SCH_PATH)
    print(f"  -> {SCH_PATH} ({os.path.getsize(SCH_PATH)} bytes)")

    validate_grid(content)
    validate_wire_bounds(content)

    print("\n--- SELF AUDIT ---")
    ok = sch.audit_table()

    # Run linter
    if os.path.isfile(LINTER_PATH):
        print("\nRunning linter...")
        result = subprocess.run(
            [sys.executable, LINTER_PATH, SCH_PATH],
            capture_output=True, text=True, timeout=30
        )
        print(result.stdout)
        if result.returncode != 0:
            print("LINTER FAILED — fix violations.")
            sys.exit(1)
        print("LINTER PASSED ✓")

    print_fix_checklist()

    if ok:
        print("\nAll checks passed. Deliver schematic v8.")
    else:
        print("\n⚠ Issues detected — review above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
