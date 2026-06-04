# Single GND_PWR Placement Pattern (v14 project)

## User Preference

When the GND bus already interconnects all ground returns via a shared trunk
(e.g. WAGO → vertical trunk → per-channel horizontal stubs), the user prefers
**ONE GND_PWR symbol on the trunk**, not one per component.

## Placement (v14_final coordinates)

```
GND trunk:   X=157.78,  Y=141.19 (bottom of trunk)
GND_PWR:     X=157.78,  Y=155.00 (symbol center)
Wire stub:   (157.78, 141.19) → (157.78, 155.00), color BLACK (0,0,0)
```

- **12mm below WAGO body bottom** (TB1 at Y=145, body bottom at Y=152.62)
- Symbol polyline extends to Y=158.81 (3.81mm below symbol center)
- Clear of all component bodies and signal wires

## What Was Removed

4 per-component GND_PWR symbols, each with a connecting wire + junction:
| Ref | Old Position | Connected To |
|-----|-------------|--------------|
| #PWR01 | (198.65, 83.00) | SW1 LED- (Y=75.54) |
| #PWR02 | (198.65, 103.00) | SW2 LED- (Y=95.54) |
| #PWR03 | (198.65, 123.00) | SW3 LED- (Y=115.54) |
| #PWR04 | (230.24, 140.46) | LS1 buzzer - (Y=133.00) |

## Pitfall

After removing per-component GND_PWR instances, the horizontal GND stub wires
that connected to them become redundant IF a GND bus already spans the same
range. Remove both the symbol AND its connecting wire + junction. Failing to
remove the redundant wires creates T-junction violations (linter will flag).

## Verification
```
grep -c 'GND_PWR' file.kicad_sch  # should be 3 (1 def + 1 unit + 1 instance)
grep 'GND_PWR.*at ' file.kicad_sch  # should show exactly 1 instance
```
