# Routing Patterns & Symbol Definitions

## R_US Resistor — Continuous Zigzag, Hidden Pins (v11+)

**PREFER INLINE over Device:R_US (v13 update).** The KiCad built-in `Device:R_US` showed as question marks because the schematic had no library table configuration. Inline symbols are self-contained and work on any KiCad install without setup. Only use `Device:` references if you also configure the project's library symbol table in the .kicad_pro file.

The inline R_US symbol must use a single continuous polyline from left pin origin to right pin origin, with the zigzag (3 humps) in between. Pins are hidden (length 0) — they are connection points only, the polyline provides the visible body.

```sexpr
(symbol "R_US" (pin_names (offset 0)) (in_bom yes) (on_board yes)
  (property "Reference" "R" (id 0) (at 0 5.08 0)
    (effects (font (size 1.27 1.27))))
  (property "Value" "R" (id 1) (at 0 -5.08 0)
    (effects (font (size 1.27 1.27))))
  (symbol "R_US_0_1"
    (polyline (pts (xy -7.62 0) (xy -3.81 0) (xy -2.54 1.27) (xy -1.27 -1.27)
                   (xy 0 1.27) (xy 1.27 -1.27) (xy 2.54 1.27) (xy 3.81 0) (xy 7.62 0))
      (stroke (width 0.254) (type default)) (fill (type none)))
    (pin passive line (at -7.62 0 0) (length 0) hide
      (name "~" (effects (font (size 1.016 1.016)))) (number "1" ...))
    (pin passive line (at 7.62 0 0) (length 0) hide
      (name "~" (effects (font (size 1.016 1.016)))) (number "2" ...))))
```

Key points:
- **Continuous polyline:** from (-7.62,0) → horizontal to (-3.81,0) → zigzag → (3.81,0) → horizontal to (7.62,0). No gaps between pin and body.
- **Hidden pins:** `(length 0) hide` — the polyline IS the visual body. The pins just mark connection points.
- **No rectangle:** Do NOT use `(rectangle ...)`. The user rejected rectangle bodies as not matching real components.
- **No visible pin lines:** Old versions had `(length 3.81)` which drew separate pin lines appearing disconnected from the zigzag.
- **Inline only:** Do NOT use `Device:R_US` as lib_id unless you configure the project library table. Inline symbols work without config.

## VCC/+V Power Symbol — Bar, NOT Triangle (v9+)

The VCC_PWR symbol must be a **horizontal bar with vertical stub**, NOT a triangle:

```sexpr
(symbol "VCC_PWR" (power)
  (property "Reference" "#PWR" (id 0) (at 0 2.54 0) (effects (font (size 1.27 1.27)) hide))
  (property "Value" "+V" (id 1) (at 0 5.08 0) (effects (font (size 1.27 1.27))))
  (symbol "VCC_PWR_0_1"
    (pin power_in line (at 0 0 90) (length 0) hide
      (name "+V" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
    (polyline (pts (xy -2.54 3.81) (xy 2.54 3.81))
      (stroke (width 0.254) (type default)) (fill (type none)))
    (polyline (pts (xy 0 0) (xy 0 3.81))
      (stroke (width 0.254) (type default)) (fill (type none)))))
```

## GND_PWR Symbol — Triangle (standard)

```sexpr
(symbol "GND_PWR" (power)
  (property "Reference" "#PWR" (id 0) (at 0 2.54 0) (effects (font (size 1.27 1.27)) hide))
  (property "Value" "GND" (id 1) (at 0 5.08 0) (effects (font (size 1.27 1.27))))
  (symbol "GND_PWR_0_1"
    (pin power_in line (at 0 0 270) (length 0) hide
      (name "GND" (effects (font (size 1.27 1.27)))) (number "1" (effects (font (size 1.27 1.27)))))
    (polyline (pts (xy -3.81 0) (xy 3.81 0) (xy 0 3.81) (xy -3.81 0))
      (stroke (width 0.254) (type default)) (fill (type outline)))))

**CRITICAL — orientation (v14.1+):** The polyline MUST have the **flat bar at Y=0** (connection point) and **tip at Y=+3.81** (pointing DOWN). The correct polyline is `(pts (xy -3.81 0) (xy 3.81 0) (xy 0 3.81) (xy -3.81 0))`.

**WRONG (upside down — user will reject immediately):**
```
(polyline (pts (xy 0 0) (xy -3.81 3.81) (xy 3.81 3.81) (xy 0 0))
```
This puts the TIP at Y=0 (connection) and the flat bar at Y=+3.81. The triangle appears to point UP, which is the wrong orientation for GND.

**CRITICAL — fill type (v13):** Must use `(fill (type outline))`, NOT `(fill (type none))`. The outline fill makes the triangle direction clearly visible (flat bar at top, tip down). With `(fill (type none))`, the triangle appears as an open outline and can look ambiguous or upside-down.

**GND placement (v13):** Place GND symbols at least 5mm away from signal wires. Use `ledm_y - 5.08` (5.08mm below LED- wire) PLUS an additional 5mm clearance = ~10mm below the wire. This ensures the triangle doesn't touch the signal wire at the component center Y.

## GX16-6 Aviation Connector — Pin Mapping (real-world wiring)

The GX16-6 is a 16mm, 6-pin aviation connector with M16 thread. The 6 pins are arranged in a circle inside the shell. Pin numbering (viewed from socket face): pin 1 is typically the keyed position, counting clockwise.

**Real-world wiring (Indicator Panel project, verified):**

| Pin | Label | Wire Color | Destination |
|-----|-------|-----------|-------------|
| 1 | BLACK/GND | Black (0,0,0) | WAGO IN1/BLK (GND bus) |
| 2 | BLUE/SIG1 | Blue (0,70,200) | R1 left pin -> RED LED button |
| 3 | YELLOW/SIG2 | Yellow (200,160,0) | R2 left pin -> GREEN LED button |
| 4 | GREEN/SIG3 | Green (0,150,0) | R3 left pin -> WHITE LED button |
| 5 | RED/+V | Red (214,0,0) | LS1 + (Buzzer power) |
| 6 | PINK/COM | Pink (220,80,150) | WAGO IN2/PNK (COM bus) |

**Common mistake:** Reversing pins 1 and 6 (BLACK/GND vs PINK/COM). Pin 1 = BLACK/GND, Pin 6 = PINK/COM. The draw.io diagram had them swapped -- always verify physical wiring against schematic before finalizing.

**Connector fan-out:** All 6 pins exit LEFT from the symbol. Staggered stub lengths using 4mm x pin_number spacing (pin 1 closest to body at ~77mm, pin 6 farthest at ~57mm from sheet left edge).

## J1 Connector Fan-Out — 4mm Spacing (v13+)

J1 pins exit LEFT at offset (-10.16mm from symbol origin), length 5.08mm RIGHT. Pin endpoint: `X = J1_x - 10.16 + 5.08 = J1_x - 5.08`.

Routing: 1) LEFT stub by `4 * pin_number` mm, 2) vertical to target Y (unique X per pin), 3) RIGHT to destination.

```python
turn_x = (J1_x - 5.08) - 4.0 * pin_number  # pin 1=76.92, pin 6=56.92
```

**History:** 2.54mm (v10, too cramped) → 4mm (v13, clean space). 5mm (v9) was also tried but was too wide relative to the 5mm-per-pin model.

## LED+ Signal Routing (Resistor → LED+ pin) — v10+ Pattern

ILLUM_PB LED+ pin endpoint: X = SW_x - 6.35, Y = SW_y - 2.54.

Route: 1) Jog vertically at R_US right pin endpoint (X = R_x + 11.43), 2) Horizontal to LED+.

```python
wire(R_x + 11.43, ch_y, R_x + 11.43, ch_y - 2.54, color)  # jog at resistor pin
wire(R_x + 11.43, ch_y - 2.54, SW_x - 6.35, ch_y - 2.54, color)  # to LED+
```

**Jog at resistor right pin, NOT at LED+ pin.** Do NOT route to LED+ first then jog.

## WAGO Output Routing — Right Side Exit (v12+)

WAGO output pins at body edge X=7.62, length 5.08 right. Pin endpoint: X = TB1_x + 12.70.

Route: 1) RIGHT stub from endpoint, 2) vertical to target, 3) RIGHT to pin. No LEFT travel.

## Pin Endpoint Reference — v12 Corrections (pins at body edge)

| Component | Pin | Origin | Length | X endpoint | Y endpoint |
|-----------|-----|--------|--------|-----------|-----------|
| R_US inline | P1 | -7.62,0 | 0 hide | X_R - 7.62 | sym_Y |
| R_US inline | P2 | +7.62,0 | 0 hide | X_R + 7.62 | sym_Y |
| ILLUM_PB | LED+ | -10.16,-2.54 | 3.81 R | X_SW - 6.35 | SW_Y - 2.54 |
| ILLUM_PB | LED- | -10.16,+2.54 | 3.81 R | X_SW - 6.35 | SW_Y + 2.54 |
| ILLUM_PB | SW-COM | **+6.35**,-2.54 | 3.81 R | X_SW + 10.16 | SW_Y - 2.54 |
| ILLUM_PB | SW-NO | **+6.35**,+2.54 | 3.81 R | X_SW + 10.16 | SW_Y + 2.54 |
| BUZZER | + | -10.16,0 | 5.08 R | X_SW - 5.08 | BUZ_Y |
| BUZZER | - | **+5.08**,0 | 5.08 R | X_SW + 10.16 | BUZ_Y |
| WAGO | IN1 | -12.7,-3.81 | 5.08 R | X_TB1 - 7.62 | TB1_Y - 3.81 |
| WAGO | OUT1 | **+7.62**,-3.81 | 5.08 R | X_TB1 + 12.70 | TB1_Y - 3.81 |
| WAGO | OUT2 | **+7.62**,-1.27 | 5.08 R | X_TB1 + 12.70 | TB1_Y - 1.27 |
| WAGO | OUT3 | **+7.62**,+1.27 | 5.08 R | X_TB1 + 12.70 | TB1_Y + 1.27 |
| WAGO | OUT4 | **+7.62**,+3.81 | 5.08 R | X_TB1 + 12.70 | TB1_Y + 3.81 |

**Bold = v12 corrections.** Previously had pin origins outside the body rectangle (e.g., WAGO OUT at X=12.7 with body ending at 7.62, BUZZER - at X=10.16 with body ending at 5.08). Always verify: `pin_origin_X + length == body_edge_X`.

**v14 correction:** R_US pins are hidden (length 0) with connection at ±7.62 from origin. Wires must connect to X = R_x ± 7.62, NOT R_x ± 3.81 or R_x ± 11.43.
