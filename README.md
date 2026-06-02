# Electrical Schematic Generator

Generate professional electrical/electronic circuit schematics as SVG images using a custom Python renderer with 45° diagonal routing, Lee maze autorouter with collision detection, and channel allocation.

## Files

| File | Purpose |
|------|---------|
| `symbols.py` | SVG drawing for resistor, LED, IC, GND, VCC, capacitor, diode, header; plus pin direction metadata and component bounding boxes for the autorouter |
| `renderer.py` | Grid layout with 3 routing strategies: Manhattan (90°), 45° diagonal, and Lee maze autorouter with collision avoidance |
| `generate_examples.py` | Demo circuits (horizontal, diagonal, vertical, complex) |

## Routing System

Three-tier routing tried in order:

### 1. Manhattan (90°)
Classic H-V-H orthogonal routing. Used when the direct path is clear of all component bodies.

### 2. 45° Diagonal
Clean single-bend diagonal traces. Two patterns:
- **H-L** (horizontal stub then 45° line): when horizontal distance ≥ vertical distance
- **V-L** (vertical stub then 45° line): when vertical distance > horizontal distance

Produces cleaner, shorter traces than Manhattan, especially for offset pins.

### 3. Lee Maze Autorouter
Breadth-first search on a 10px grid. Finds the shortest path around component bodies when both Manhattan and 45° routes are blocked. Handles:
- Component bodies between source and sink
- Dense layouts with multiple components
- Tight channel routing through available gaps

After routing, the path is simplified (collinear points removed) and marked on the occupancy grid for channel allocation tracking.

## Key Rules (IEEE 315 / professional practice)

1. **Signal flow**: left-to-right, VCC top, GND bottom
2. **Direction-aware routing**: each pin has exit dir (L/R/U/D). Wire first moves away from component body before turning.
3. **Collision avoidance**: if direct H/V route overlaps a component, 45° is tried; if that also collides, maze router finds a clean path
4. **Hub-and-spoke**: multi-pin nets route pins independently to hub symbol (each spoke routed via the 3-tier system)
5. **No floating power labels**: GND/VCC labels suppressed — symbols speak for themselves
6. **RefDes above, value below**
7. **Same-mid_y for straight wires**: components on same row should share midpoint y

## Usage

```python
from renderer import SchematicRenderer

r = SchematicRenderer(cell_size=110)

# Add components
r.add_component("U1", "ic", grid_x=0, grid_y=1,
    pins_left=[{"num":2,"name":"VDD3P3"}, ...],
    pins_right=[{"num":6,"name":"GPIO2"}, ...], name="ESP32-C3")
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

## Running Examples

```bash
pip install svgwrite
cd scripts/
python generate_examples.py /tmp/output_dir
```

Generates 4 example schematics: `horizontal`, `diagonal_45`, `vertical`, `complex`.

## Dependency

- `svgwrite` (Python library for SVG generation)

## Pitfalls

- Components on the same row need same height for straight wires
- VCC at grid_y=-1 is above render area (works with offset calc)
- On Windows: `sips` is not available for SVG→PNG conversion; use Inkscape or browser rendering
- 45° routing only kicks in when Manhattan route would collide with a third-party component body
- Maze router carves a 5×5 cell access path around each pin so pins inside component bboxes are reachable
