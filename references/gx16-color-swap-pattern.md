# GX16-6 Color-Swap Pattern (v14 project)

When the user's physical cable has non-standard wire-to-signal mapping,
the schematic's WIRE COLORS must match the PHYSICAL CABLE, not the pin names.

## The Setup

- Cable has a BLACK wire carrying the COM signal
- Cable has a PINK wire carrying the GND signal
- Standard mapping would be BLACK=GND, PINK=COM

## The Fix (only 4 bytes changed)

In the GX16_PINS tuple, swap ONLY the `net_color_key` field:

```python
# BEFORE (standard mapping — colors match names)
(1, "PINK/COM",  ..., "PINK"),   # wire renders pink
(6, "BLACK/GND", ..., "BLACK"),  # wire renders black

# AFTER (physical cable mapping — colors swapped vs names)
(1, "PINK/COM",  ..., "BLACK"),  # wire renders black (matches physical black wire on COM)
(6, "BLACK/GND", ..., "PINK"),   # wire renders pink (matches physical pink wire on GND)
```

## What NOT to change

- DO NOT swap pin names in the symbol definition
- DO NOT swap routing destinations (WAGO IN1 vs IN2)
- DO NOT "fix" the GND_PWR triangle direction
- DO NOT touch any other components, wires, or symbols

## Verification

After swapping, check:
```
Pin 1 (PINK/COM): wire color (0,0,0)   = BLACK ✓
Pin 6 (BLACK/GND): wire color (220,80,150) = PINK ✓
```

## Exact File Coordinates (v14 kicad_sch)

### Pin 1 fan-out (Y=96.65, 3 segments)
```
(80.92,96.65)→(76.92,96.65)  color (0,0,0)      ← was (220,80,150)
(76.92,96.65)→(76.92,148.81)  color (0,0,0)      ← was (220,80,150)
(76.92,148.81)→(120.00,148.81) color (0,0,0)     ← was (220,80,150)
```

### Pin 6 fan-out (Y=109.35, 3 segments)
```
(80.92,109.35)→(56.92,109.35)  color (220,80,150) ← was (0,0,0)
(56.92,109.35)→(56.92,141.19)  color (220,80,150) ← was (0,0,0)
(56.92,141.19)→(120.00,141.19) color (220,80,150) ← was (0,0,0)
```
