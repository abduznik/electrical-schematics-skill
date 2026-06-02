"""Schematic renderer: takes component/net descriptions, lays out on a grid,
routes wires (Manhattan, 45° diagonal, or maze-autorouted with collision
detection), and outputs a single SVG file.

Improvements over v1:
  - 45° diagonal routing for cleaner traces
  - Lee maze autorouter with component-body collision avoidance
  - Channel allocation tracking for even wire distribution
  - Hub-and-spoke for multi-pin nets uses individual autorouting per spoke

Usage:
    from renderer import SchematicRenderer
    r = SchematicRenderer()
    r.add_component("U1", "ic", grid_x=0, grid_y=0, ...)
    r.add_net("GPIO2", [("U1", 6), ("R1", 1)])
    r.render("output.svg")
"""

import svgwrite
from collections import deque

from symbols import (
    draw_resistor, draw_led, draw_capacitor, draw_diode,
    draw_ic, draw_ground, draw_vcc, draw_header,
    get_pin_direction, get_component_bbox,
    WIRE_W, TEXT_S, FONT,
)

# --- Constants ---
CELL = 100           # grid cell size (px)
MARGIN = 40          # page margin
GRID_RES = 10        # resolution of the maze-routing grid (px/cell)

# Grid cell states (autorouter)
CELL_FREE = 0
CELL_BLOCKED = 1     # component body
CELL_WIRE = 2        # occupied by a wire segment (density tracking)
CELL_VISITED = 3     # BFS frontier in maze router


# ---------------------------------------------------------------------------
# Helper: axis-aligned rectangle intersection
# ---------------------------------------------------------------------------

def _rects_overlap(a, b):
    """Return True if axis-aligned rects a and b overlap (inclusive)."""
    (ax1, ay1, ax2, ay2) = a
    (bx1, by1, bx2, by2) = b
    return not (ax2 < bx1 or ax1 > bx2 or ay2 < by1 or ay1 > by2)


def _point_in_rect(px, py, rect):
    """Return True if (px, py) is inside or on the edge of rect."""
    rx1, ry1, rx2, ry2 = rect
    return rx1 <= px <= rx2 and ry1 <= py <= ry2


def _segment_rect_intersect(x1, y1, x2, y2, rect):
    """Check if a horizontal or vertical line segment intersects a rect.

    Only handles axis-aligned segments (H or V) — the building blocks
    of Manhattan and 45° paths.
    """
    rx1, ry1, rx2, ry2 = rect
    if x1 == x2:  # vertical
        if x1 < rx1 or x1 > rx2:
            return False
        ylo, yhi = (y1, y2) if y1 <= y2 else (y2, y1)
        return not (yhi < ry1 or ylo > ry2)
    else:  # horizontal
        y = y1
        if y < ry1 or y > ry2:
            return False
        xlo, xhi = (x1, x2) if x1 <= x2 else (x2, x1)
        return not (xhi < rx1 or xlo > rx2)


# ---------------------------------------------------------------------------
# SchematicRenderer
# ---------------------------------------------------------------------------

class SchematicRenderer:
    """Grid-based schematic renderer with 45° routing + autorouter."""

    def __init__(self, cell_size=CELL, enable_45=True, enable_autorouter=True):
        self.cell_size = cell_size
        self.enable_45 = enable_45
        self.enable_autorouter = enable_autorouter
        self.components = {}
        self.nets = {}
        self._cw = 3   # grid columns
        self._ch = 3   # grid rows
        # Accumulated wire segments for collision/occupancy tracking
        self._placed_segments = []  # [(x1,y1,x2,y2), ...]
        self._obstacles = []        # component bboxes
        self._all_pin_positions = {}  # populated during render

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_component(self, ref, ctype, grid_x, grid_y, **kw):
        """Register a component on the grid."""
        self.components[ref] = dict(type=ctype, grid_x=grid_x, grid_y=grid_y, **kw)
        self._cw = max(self._cw, grid_x + 2)
        self._ch = max(self._ch, grid_y + 2)

    def add_net(self, name, connections):
        """Add a net. connections = [(ref, pin_id), ...]"""
        self.nets[name] = connections

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _px(self, gx):
        return MARGIN + gx * self.cell_size

    def _py(self, gy):
        return MARGIN + gy * self.cell_size

    # ------------------------------------------------------------------
    # Build components - populate obstacles + pin map
    # ------------------------------------------------------------------

    def _build_components(self, dwg):
        """Render all components, return {ref: {pin_id: (x,y)}}.

        Also populates self._obstacles with component bounding boxes
        for collision detection.
        """
        all_pins = {}

        for ref, c in self.components.items():
            px = self._px(c["grid_x"])
            py = self._py(c["grid_y"])
            ctype = c["type"]

            if ctype == "resistor":
                grp, pins = draw_resistor(dwg, px, py, ref=ref, value=c.get("value", ""))
            elif ctype == "led":
                grp, pins = draw_led(dwg, px, py, ref=ref, value=c.get("value", ""))
            elif ctype == "capacitor":
                grp, pins = draw_capacitor(dwg, px, py, polarized=c.get("polarized", False),
                                           ref=ref, value=c.get("value", ""))
            elif ctype == "diode":
                grp, pins = draw_diode(dwg, px, py, ref=ref, value=c.get("value", ""))
            elif ctype == "ground":
                grp, pins = draw_ground(dwg, px, py, ref=ref)
            elif ctype == "vcc":
                grp, pins = draw_vcc(dwg, px, py, label=c.get("label", "VCC"))
            elif ctype == "header":
                grp, pins = draw_header(dwg, px, py, pins=c.get("pins", 2), ref=ref)
            elif ctype == "ic":
                max_pins = max(len(c.get("pins_left", [])), len(c.get("pins_right", [])))
                h = max(60, (max_pins + 1) * 14)
                w = 100
                grp, pins = draw_ic(dwg, px, py, w, h,
                                    pins_left=c.get("pins_left", []),
                                    pins_right=c.get("pins_right", []),
                                    ref=ref, name=c.get("name", ""))
                self._cw = max(self._cw, c["grid_x"] + 2)
            else:
                continue

            dwg.add(grp)
            all_pins[ref] = pins
            self._all_pin_positions[ref] = pins

            # Build obstacle bbox
            bbox = get_component_bbox(ctype, px, py, **c)
            self._obstacles.append(bbox)

        return all_pins

    # ------------------------------------------------------------------
    # 45° diagonal route
    # ------------------------------------------------------------------

    def _route_45_path(self, p1, p2):
        """Return SVG path 'd' string for a 1-bend 45° route.

        Pattern:
          If |dx| >= |dy|:  H-stub then 45° diagonal to target
          else:              V-stub then 45° diagonal to target
        """
        x1, y1 = p1
        x2, y2 = p2
        dx = x2 - x1
        dy = y2 - y1
        adx, ady = abs(dx), abs(dy)

        if adx == 0 and ady == 0:
            return ""
        if adx == 0:
            return f"M {x1},{y1} V {y2}"
        if ady == 0:
            return f"M {x1},{y1} H {x2}"

        if adx >= ady and ady > 0:
            sx = 1 if dx > 0 else -1
            x_ext = x1 + sx * (adx - ady)
            if adx == ady:
                return f"M {x1},{y1} L {x2},{y2}"
            return f"M {x1},{y1} H {x_ext} L {x2},{y2}"
        elif ady > adx and adx > 0:
            sy = 1 if dy > 0 else -1
            y_ext = y1 + sy * (ady - adx)
            return f"M {x1},{y1} V {y_ext} L {x2},{y2}"
        return ""

    def _route_45_segments(self, p1, p2):
        """Return list of (x1,y1,x2,y2) segments for a 45° route.

        Used for collision checking.
        """
        x1, y1 = p1
        x2, y2 = p2
        dx = x2 - x1
        dy = y2 - y1
        adx, ady = abs(dx), abs(dy)

        if adx == 0 or ady == 0:
            return [(x1, y1, x2, y2)]

        if adx >= ady:
            sx = 1 if dx > 0 else -1
            x_ext = x1 + sx * (adx - ady)
            return [(x1, y1, x_ext, y1), (x_ext, y1, x2, y2)]
        else:
            sy = 1 if dy > 0 else -1
            y_ext = y1 + sy * (ady - adx)
            return [(x1, y1, x1, y_ext), (x1, y_ext, x2, y2)]

    # ------------------------------------------------------------------
    # Manhattan route (classic)
    # ------------------------------------------------------------------

    def _route_manhattan_path(self, p1, p2):
        """Return SVG path 'd' for Manhattan H-V-H route."""
        x1, y1 = p1
        x2, y2 = p2
        mid_x = (x1 + x2) / 2
        return f"M {x1},{y1} H {mid_x} V {y2} H {x2}"

    def _route_manhattan_segments(self, p1, p2):
        """Return list of (x1,y1,x2,y2) for Manhattan route (collision checks)."""
        x1, y1 = p1
        x2, y2 = p2
        mid_x = (x1 + x2) / 2
        return [(x1, y1, mid_x, y1), (mid_x, y1, mid_x, y2), (mid_x, y2, x2, y2)]

    # ------------------------------------------------------------------
    # Collision detection
    # ------------------------------------------------------------------

    def _segments_clear(self, segments, skip_bboxes=None):
        """Check that none of the line segments intersect any obstacle.

        Args:
            segments: list of (x1,y1,x2,y2) axis-aligned segments
            skip_bboxes: optional set of bbox tuples to ignore (e.g., the
                         source/target component's own body)
        Returns: True if all segments avoid all obstacles.
        """
        skip_set = set(skip_bboxes or [])
        for seg in segments:
            for obst in self._obstacles:
                if obst in skip_set:
                    continue
                if _segment_rect_intersect(seg[0], seg[1], seg[2], seg[3], obst):
                    return False
        return True

    def _find_bboxes_for_refs(self, refs):
        """Return obstacle bboxes owned by component refs (to skip them)."""
        results = []
        for ref in refs:
            c = self.components.get(ref)
            if c is None:
                continue
            px = self._px(c["grid_x"])
            py = self._py(c["grid_y"])
            bbox = get_component_bbox(c["type"], px, py, **c)
            results.append(bbox)
        return results

    # ------------------------------------------------------------------
    # Lee maze router (breadth-first on a grid)
    # ------------------------------------------------------------------

    def _build_route_grid(self, extra_padding=5):
        """Create 2D array marking blocked cells (component bodies + margin)."""
        total_w = self._cw * self.cell_size + 2 * MARGIN
        total_h = self._ch * self.cell_size + 2 * MARGIN
        cols = int(total_w / GRID_RES) + 1
        rows = int(total_h / GRID_RES) + 1

        grid = [[CELL_FREE] * cols for _ in range(rows)]

        # Mark component bodies as blocked
        for obst in self._obstacles:
            rx1, ry1, rx2, ry2 = obst
            # Expand by extra_padding for clearance
            rx1 -= extra_padding
            ry1 -= extra_padding
            rx2 += extra_padding
            ry2 += extra_padding
            c1 = max(0, int(rx1 / GRID_RES))
            r1 = max(0, int(ry1 / GRID_RES))
            c2 = min(cols - 1, int(rx2 / GRID_RES))
            r2 = min(rows - 1, int(ry2 / GRID_RES))
            for r in range(r1, r2 + 1):
                for c in range(c1, c2 + 1):
                    grid[r][c] = CELL_BLOCKED
        return grid

    def _grid_coord(self, px, py):
        """Convert SVG pixel coordinate to (row, col) on the routing grid."""
        col = int(px / GRID_RES)
        row = int(py / GRID_RES)
        return row, col

    def _maze_route(self, p1, p2, grid):
        """Lee BFS maze router. Returns SVG path 'd' or None if blocked."""
        sr, sc = self._grid_coord(*p1)
        tr, tc = self._grid_coord(*p2)

        # Carve a small access path around endpoints so the BFS can
        # enter/exit component bodies at pin locations.
        for r_off in range(-2, 3):
            for c_off in range(-2, 3):
                for (rr, cc) in [(sr + r_off, sc + c_off), (tr + r_off, tc + c_off)]:
                    if 0 <= rr < len(grid) and 0 <= cc < len(grid[0]):
                        if grid[rr][cc] != CELL_FREE:
                            grid[rr][cc] = CELL_FREE

        rows = len(grid)
        cols = len(grid[0])

        # BFS
        q = deque()
        q.append((sr, sc))
        grid[sr][sc] = CELL_VISITED
        prev = {}  # (r,c) -> (pr,pc)
        found = False

        while q:
            r, c = q.popleft()
            if r == tr and c == tc:
                found = True
                break
            for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < rows and 0 <= nc < cols):
                    continue
                if nr == tr and nc == tc:
                    prev[(nr, nc)] = (r, c)
                    found = True
                    break
                if grid[nr][nc] == CELL_FREE:
                    grid[nr][nc] = CELL_VISITED
                    prev[(nr, nc)] = (r, c)
                    q.append((nr, nc))
            if found:
                break

        if not found:
            return None

        # Trace back
        path = [(tr, tc)]
        cur = (tr, tc)
        while cur != (sr, sc):
            cur = prev[cur]
            path.append(cur)
        path.reverse()

        # Convert to SVG path
        pts = []
        for r, c in path:
            px = c * GRID_RES + GRID_RES / 2
            py = r * GRID_RES + GRID_RES / 2
            if not pts:
                px, py = p1
            pts.append((px, py))

        if pts:
            pts[-1] = p2

        # Simplify: remove collinear points
        pts = self._simplify_path(pts)
        if len(pts) < 2:
            return None

        d = f"M {pts[0][0]},{pts[0][1]}"
        for (x, y) in pts[1:]:
            d += f" L {x},{y}"
        return d

    def _simplify_path(self, pts):
        """Remove collinear intermediate points from a polyline.

        If three consecutive points are collinear (same x or same y),
        remove the middle one.
        """
        if len(pts) < 3:
            return pts
        simplified = [pts[0]]
        for i in range(1, len(pts) - 1):
            x0, y0 = pts[i - 1]
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            if not ((x0 == x1 == x2) or (y0 == y1 == y2)):
                simplified.append((x1, y1))
        simplified.append(pts[-1])
        return simplified

    def _mark_route_on_grid(self, grid, path_d):
        """Mark cells touched by a route as occupied (channel allocation)."""
        if not path_d:
            return
        parts = path_d.replace("M ", "").replace(" H ", ",").replace(" V ", ",").replace(" L ", ",")
        tokens = parts.replace("M ", "").split()
        coords = []
        for t in tokens:
            if "," in t:
                try:
                    x, y = t.split(",")
                    coords.append((float(x), float(y)))
                except ValueError:
                    pass

        if len(coords) < 2:
            return

        for i in range(len(coords) - 1):
            x1, y1 = coords[i]
            x2, y2 = coords[i + 1]
            steps = max(int(abs(x2 - x1) / GRID_RES), int(abs(y2 - y1) / GRID_RES), 1)
            for t in range(steps + 1):
                frac = t / steps if steps > 0 else 1
                x = x1 + (x2 - x1) * frac
                y = y1 + (y2 - y1) * frac
                r, c = self._grid_coord(x, y)
                if 0 <= r < len(grid) and 0 <= c < len(grid[0]):
                    if grid[r][c] == CELL_FREE:
                        grid[r][c] = CELL_WIRE

    # ------------------------------------------------------------------
    # Pick best route for a 2-pin net
    # ------------------------------------------------------------------

    def _route_2pin(self, dwg, p1, p2, skip_bboxes):
        """Try routing strategies in order; draw the first that works.

        Strategy order: Manhattan -> 45° diagonal -> maze -> direct line
        Returns True if a route was placed.
        """
        # --- 1) Try Manhattan ---
        segs = self._route_manhattan_segments(p1, p2)
        if self._segments_clear(segs, skip_bboxes):
            path_d = self._route_manhattan_path(p1, p2)
            dwg.add(dwg.path(d=path_d, stroke="#000", stroke_width=WIRE_W, fill="none"))
            self._placed_segments.extend(segs)
            return True

        # --- 2) Try 45° diagonal ---
        if self.enable_45:
            segs45 = self._route_45_segments(p1, p2)
            if self._segments_clear(segs45, skip_bboxes):
                path_d = self._route_45_path(p1, p2)
                dwg.add(dwg.path(d=path_d, stroke="#000", stroke_width=WIRE_W, fill="none"))
                self._placed_segments.extend(segs45)
                return True

        # --- 3) Maze autorouter ---
        if self.enable_autorouter:
            grid = self._build_route_grid()
            path_d = self._maze_route(p1, p2, grid)
            if path_d:
                dwg.add(dwg.path(d=path_d, stroke="#000", stroke_width=WIRE_W, fill="none"))
                self._mark_route_on_grid(grid, path_d)
                return True

        # --- 4) Absolute fallback: straight line ---
        dwg.add(dwg.line(p1, p2, stroke="#000", stroke_width=WIRE_W))
        self._placed_segments.append((p1[0], p1[1], p2[0], p2[1]))
        return True

    # ------------------------------------------------------------------
    # Hub-and-spoke for multi-pin nets
    # ------------------------------------------------------------------

    def _route_hub_spoke(self, dwg, positions, skip_bboxes):
        """Route 3+ pins with hub-and-spoke, using _route_2pin per spoke."""
        hub_x = sum(p[0] for p in positions) / len(positions)
        hub_y = sum(p[1] for p in positions) / len(positions)
        hub = (hub_x, hub_y)

        for p in positions:
            dx = hub_x - p[0]
            dy = hub_y - p[1]
            if abs(dx) < 10 and abs(dy) < 10:
                # Very close - direct line
                dwg.add(dwg.line(p, hub, stroke="#000", stroke_width=WIRE_W))
                continue
            self._route_2pin(dwg, p, hub, skip_bboxes)

    # ------------------------------------------------------------------
    # Net label
    # ------------------------------------------------------------------

    def _place_net_labels(self, dwg, name, pin_positions):
        """Net name label near the first pin."""
        if not pin_positions or not name:
            return
        x, y = pin_positions[0]
        dwg.add(dwg.text(name, insert=(x + 10, y - 12),
                         font_size="9px", font_family=FONT, fill="#666",
                         text_anchor="start", dominant_baseline="central",
                         font_weight="normal", font_style="italic"))

    # ------------------------------------------------------------------
    # Render entry point
    # ------------------------------------------------------------------

    def render(self, filename=None):
        """Build and return the SVG drawing, saving to filename if given."""
        total_w = self._cw * self.cell_size + 2 * MARGIN
        total_h = self._ch * self.cell_size + 2 * MARGIN

        dwg = svgwrite.Drawing(filename, size=(total_w, total_h),
                               viewBox=f"0 0 {total_w} {total_h}")

        # White background
        dwg.add(dwg.rect(insert=(0, 0), size=(total_w, total_h), fill="#fff", stroke="none"))

        # Build components (populates self._obstacles, self._all_pin_positions)
        all_pins = self._build_components(dwg)

        for net_name, connections in self.nets.items():
            positions = []
            refs_in_net = set()
            for (ref, pin_id) in connections:
                if ref in all_pins and pin_id in all_pins[ref]:
                    positions.append(all_pins[ref][pin_id])
                    refs_in_net.add(ref)
            if not positions:
                continue

            skip_bboxes = self._find_bboxes_for_refs(refs_in_net)

            if len(positions) == 2:
                self._route_2pin(dwg, positions[0], positions[1], skip_bboxes)
            elif len(positions) >= 3:
                self._route_hub_spoke(dwg, positions, skip_bboxes)
            else:
                continue

            # Only label nets with a meaningful name
            if net_name and not net_name.startswith("N$"):
                self._place_net_labels(dwg, net_name, positions)

        if filename:
            dwg.save()
            return filename
        return dwg
