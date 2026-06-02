# Electrical Schematics Skill

A Hermes Agent skill that generates professional electrical/electronic circuit schematics as SVG images. Uses a custom Python SVG renderer with three routing strategies — Manhattan (90°), 45° diagonal, and a Lee maze autorouter with collision detection.

## Quick Start for Hermes

Add this skill to your Hermes Agent skills directory and it becomes available as a tool your agent can call on demand.

### Setup

```bash
# 1. Clone into your Hermes skills directory
git clone https://github.com/abduznik/electrical-schematics-skill /path/to/hermes/data/skills/electrical-schematics-skill

# 2. Install the dependency
pip install svgwrite
```

Your Hermes Agent now has the `electrical-schematics` skill loaded. The agent can generate circuit schematics from natural language descriptions using the Python API below.

### First Use

Once the skill is installed, tell your Hermes agent something like:

> "Draw a schematic: ESP32-C3 with a 330R resistor on GPIO2 driving a red LED to GND, and 3.3V power"

The agent translates that into `SchematicRenderer` calls and outputs an SVG.

---

## How It Works

The pipeline is: component definitions → `symbols.py` (primitives) → `renderer.py` (grid layout + routing) → SVG output.

### Files

| File | Purpose |
|------|---------|
| `SKILL.md` | Hermes skill definition with full documentation |
| `symbols.py` | SVG drawing for resistor, LED, IC, GND, VCC, capacitor, diode, header; plus pin direction metadata and bounding boxes for the autorouter |
| `renderer.py` | Grid layout with 3 routing strategies: Manhattan (90°), 45° diagonal, and Lee maze autorouter with collision avoidance |
| `generate_examples.py` | Demo circuits (horizontal, diagonal, vertical, complex) |

### Routing System

Three-tier routing tried in order:

**1. Manhattan (90°)** — Classic orthogonal H→V→H routing. Used when the direct path is clear of all component bodies.

**2. 45° Diagonal** — Clean single-bend diagonal traces. Two patterns:
- **H→L** (horizontal stub then 45° line): when horizontal distance ≥ vertical distance
- **V→L** (vertical stub then 45° line): when vertical distance > horizontal distance

Produces cleaner, shorter traces than Manhattan, especially for offset pins.

**3. Lee Maze Autorouter** — Breadth-first search on a 10px grid. Finds the shortest path around component bodies when both Manhattan and 45° routes are blocked. Handles dense layouts and tight channel routing.

---

## Usage

```python
from renderer import SchematicRenderer

r = SchematicRenderer(cell_size=110)

# Add components
r.add_component("U1", "ic", grid_x=0, grid_y=1,
    pins_left=[{"num":2,"name":"VDD3P3"}, {"num":7,"name":"CHIP_EN"}],
    pins_right=[{"num":6,"name":"GPIO2"}, {"num":27,"name":"U0RXD"}],
    name="ESP32-C3")
r.add_component("R1", "resistor", grid_x=3, grid_y=2, value="330R")
r.add_component("D1", "led", grid_x=5, grid_y=2, value="RED")
r.add_component("GND1", "ground", grid_x=5, grid_y=5)
r.add_component("VCC1", "vcc", grid_x=1, grid_y=-1, label="+3.3V")

# Define nets
r.add_net("GPIO2", [("U1",6), ("R1",1)])
r.add_net("GND", [("GND1",1), ("D1","K"), ("U1",33)])
r.add_net("+3.3V", [("VCC1",1), ("U1",2), ("U1",3)])

# Render SVG
r.render(filename="schematic.svg")
```

### Running Examples

```bash
pip install svgwrite
python generate_examples.py /tmp/output_dir
```

Generates 4 example schematics: `horizontal`, `diagonal_45`, `vertical`, `complex`.

---

## Key Rules (IEEE 315 / professional practice)

1. **Signal flow**: left-to-right, VCC top, GND bottom
2. **Direction-aware routing**: each pin has exit direction (L/R/U/D). Wire first moves away from component body before turning.
3. **Collision avoidance**: if direct H/V route overlaps a component, 45° is tried; if that also collides, maze router finds a clean path
4. **Hub-and-spoke**: multi-pin nets route pins independently to hub symbol
5. **RefDes above, value below**
6. **Same-mid_y for straight wires**: components on same row should share midpoint y

---

## Pitfalls

- Components on the same row need same height for straight wires
- VCC at grid_y=-1 is above render area (works with offset calc)
- On Windows: sips is not available for SVG→PNG conversion; use Inkscape or browser rendering
- 45° routing only kicks in when Manhattan route would collide with a third-party component body
- Maze router carves a 5×5 cell access path around each pin so pins inside component bboxes are reachable
