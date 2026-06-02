"""SVG component symbol drawing functions for electrical schematics.

Each function returns (svgwrite.Group, pins_dict) where pins_dict maps
pin ids (str or int) to (x, y) in the global coordinate system.

All dimensions in pixels. Standard component height = 50.

Pin direction conventions (for autorouter):
    'L' — exit left (negative x)
    'R' — exit right (positive x)
    'U' — exit up (negative y)
    'D' — exit down (positive y)
"""

import svgwrite

# --- Style constants ---
WIRE_W = "1.5"
BODY_W = "2"
TEXT_S = "12px"
FONT = "Consolas, 'Courier New', monospace, sans-serif"
PIN_R = 3  # pin dot radius


def _text(dwg, x, y, s, **kw):
    """Text element with defaults."""
    defaults = dict(font_size=TEXT_S, font_family=FONT, fill="#000",
                    text_anchor="start", dominant_baseline="central")
    defaults.update(kw)
    return dwg.text(s, insert=(x, y), **defaults)


# ---------------------------------------------------------------------------
# Pin direction lookup  (exported for the autorouter)
# ---------------------------------------------------------------------------

def get_pin_direction(ctype, pin_id, **kw):
    """Return the exit direction ('L','R','U','D') for a component pin.

    The direction tells the autorouter which way the wire should leave
    the component body so it doesn't clip through the symbol.
    """
    if ctype == "resistor":
        return "L" if pin_id == 1 else "R"
    elif ctype == "led":
        return "L" if pin_id == "A" else "R"
    elif ctype == "capacitor":
        return "L" if pin_id == 1 else "R"
    elif ctype == "diode":
        return "L" if pin_id == 1 else "R"
    elif ctype == "ground":
        return "U"  # wire approaches from above
    elif ctype == "vcc":
        return "D"  # wire approaches from below
    elif ctype == "ic":
        # Left-side pins exit left, right-side pins exit right
        pins_left = kw.get("pins_left", [])
        pins_right = kw.get("pins_right", [])
        for p in pins_left:
            if p["num"] == pin_id:
                return "L"
        for p in pins_right:
            if p["num"] == pin_id:
                return "R"
        return "L"  # default
    elif ctype == "header":
        return "L"
    return "L"


# ---------------------------------------------------------------------------
# Component bounding boxes  (exported for collision detection)
# ---------------------------------------------------------------------------

def get_component_bbox(ctype, x, y, **kw):
    """Return (left, top, right, bottom) in global coordinates.

    These are the screen-space rectangles the autorouter must avoid
    when placing wires through other components.
    """
    pad = 4  # small clearance around the body
    if ctype == "resistor":
        return (x - pad, y - pad, x + 70 + pad, y + 50 + pad)
    elif ctype == "led":
        return (x - pad, y - pad, x + 80 + pad, y + 50 + pad)
    elif ctype == "capacitor":
        return (x - pad, y - pad, x + 40 + pad, y + 50 + pad)
    elif ctype == "diode":
        return (x - pad, y - pad, x + 60 + pad, y + 50 + pad)
    elif ctype == "ground":
        return (x - pad, y - 14 - pad, x + 20 + pad, y + 16 + pad)
    elif ctype == "vcc":
        return (x - pad, y - pad, x + 50 + pad, y + 18 + pad)
    elif ctype == "ic":
        pins_left = kw.get("pins_left", [])
        pins_right = kw.get("pins_right", [])
        max_pins = max(len(pins_left), len(pins_right))
        h = max(60, (max_pins + 1) * 14)
        w = 100
        return (x - pad, y - pad, x + w + pad, y + h + pad)
    elif ctype == "header":
        pins = kw.get("pins", 2)
        h = 25 * (pins - 1) + 20
        return (x - pad, y - pad, x + 30 + pad, y + h + pad)
    return (x, y, x + 50, y + 50)


# ---------------------------------------------------------------------------
# Component drawing functions
# ---------------------------------------------------------------------------

def draw_resistor(dwg, x, y, rotation=0, ref="R?", value=""):
    """IEC zigzag resistor, horizontal orientation.

    Pin 1 = left, Pin 2 = right.
    Returns (group, {1: (px,py), 2: (px,py)}).
    """
    g = svgwrite.container.Group(transform=f"translate({x},{y})")

    w, h = 70, 50
    mid_y = h / 2

    # Lead wires
    g.add(dwg.line((0, mid_y), (10, mid_y), stroke="#000", stroke_width=WIRE_W))
    g.add(dwg.line((w - 10, mid_y), (w, mid_y), stroke="#000", stroke_width=WIRE_W))

    # Zigzag: 5 segments
    seg_w = (w - 20) / 5
    seg_h = 14
    pts = [(10, mid_y)]
    for i in range(5):
        px = 10 + (i + 1) * seg_w
        py = mid_y + (seg_h if i % 2 == 0 else -seg_h)
        pts.append((px, py))
    pts.append((w - 10, mid_y))
    d = "M " + " L ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pts)
    g.add(dwg.path(d=d, stroke="#000", stroke_width=BODY_W, fill="none"))

    if value:
        g.add(_text(dwg, w / 2, mid_y + 18, value, text_anchor="middle", font_size="10px"))
    g.add(_text(dwg, 0, -12, ref, text_anchor="start", font_size="10px"))

    pins = {1: (x, y + mid_y), 2: (x + w, y + mid_y)}
    return g, pins


def draw_led(dwg, x, y, rotation=0, ref="D?", value=""):
    """LED symbol, anode left, cathode right.

    Pin A = anode (left), Pin K = cathode (right).
    Returns (group, {'A': (px,py), 'K': (px,py)}).
    """
    g = svgwrite.container.Group(transform=f"translate({x},{y})")

    w, h = 80, 50
    mid_y = h / 2

    # Lead wires
    g.add(dwg.line((0, mid_y), (12, mid_y), stroke="#000", stroke_width=WIRE_W))
    g.add(dwg.line((w - 12, mid_y), (w, mid_y), stroke="#000", stroke_width=WIRE_W))

    # Triangle pointing right
    tri_left = 12
    tri_apex = 48
    tri_top = mid_y - 14
    tri_bot = mid_y + 14
    d = f"M {tri_left},{mid_y} L {tri_apex},{tri_top} L {tri_apex},{tri_bot} Z"
    g.add(dwg.path(d=d, stroke="#000", stroke_width=BODY_W, fill="none"))

    # Cathode bar
    bar_x = tri_apex + 8
    g.add(dwg.line((bar_x, tri_top), (bar_x, tri_bot), stroke="#000", stroke_width=BODY_W))

    # Two emission arrows
    for dy in (-8, 8):
        ax, ay = tri_apex + 2, mid_y + dy
        g.add(dwg.line((ax, ay), (ax + 18, ay + dy), stroke="#000", stroke_width="1.2"))
        g.add(dwg.line((ax + 18, ay + dy), (ax + 12, ay + dy - 4), stroke="#000", stroke_width="1.2"))
        g.add(dwg.line((ax + 18, ay + dy), (ax + 12, ay + dy + 4), stroke="#000", stroke_width="1.2"))

    if value:
        g.add(_text(dwg, w / 2, mid_y + 22, value, text_anchor="middle", font_size="9px"))
    g.add(_text(dwg, 0, -12, ref, text_anchor="start", font_size="10px"))

    pins = {"A": (x, y + mid_y), "K": (x + w, y + mid_y)}
    return g, pins


def draw_capacitor(dwg, x, y, rotation=0, polarized=False, ref="C?", value=""):
    """Capacitor: two parallel lines (or one curved for polarized). Pin 1=left, 2=right."""
    g = svgwrite.container.Group(transform=f"translate({x},{y})")

    w, h = 40, 50
    mid_y = h / 2

    g.add(dwg.line((0, mid_y), (10, mid_y), stroke="#000", stroke_width=WIRE_W))
    g.add(dwg.line((w - 10, mid_y), (w, mid_y), stroke="#000", stroke_width=WIRE_W))

    plate1_x = 12
    plate2_x = w - 12
    plate_top = mid_y - 14
    plate_bot = mid_y + 14

    if polarized:
        g.add(dwg.line((plate1_x, plate_top), (plate1_x, plate_bot), stroke="#000", stroke_width=BODY_W))
        dy = plate_bot - plate_top
        g.add(dwg.path(d=f"M {plate2_x},{plate_top} A 4,{dy/2} 0 0,1 {plate2_x},{plate_bot}",
                       stroke="#000", stroke_width=BODY_W, fill="none"))
    else:
        g.add(dwg.line((plate1_x, plate_top), (plate1_x, plate_bot), stroke="#000", stroke_width=BODY_W))
        g.add(dwg.line((plate2_x, plate_top), (plate2_x, plate_bot), stroke="#000", stroke_width=BODY_W))

    if value:
        g.add(_text(dwg, w / 2, mid_y + 18, value, text_anchor="middle", font_size="10px"))
    g.add(_text(dwg, 0, -12, ref, text_anchor="start", font_size="10px"))

    pins = {1: (x, y + mid_y), 2: (x + w, y + mid_y)}
    return g, pins


def draw_diode(dwg, x, y, rotation=0, ref="D?", value=""):
    """Generic diode. Pin 1=anode(left), 2=cathode(right)."""
    g = svgwrite.container.Group(transform=f"translate({x},{y})")

    w, h = 60, 50
    mid_y = h / 2

    g.add(dwg.line((0, mid_y), (10, mid_y), stroke="#000", stroke_width=WIRE_W))
    g.add(dwg.line((w - 10, mid_y), (w, mid_y), stroke="#000", stroke_width=WIRE_W))

    tri_apex = 42
    tri_top = mid_y - 14
    tri_bot = mid_y + 14
    d = f"M 10,{mid_y} L {tri_apex},{tri_top} L {tri_apex},{tri_bot} Z"
    g.add(dwg.path(d=d, stroke="#000", stroke_width=BODY_W, fill="none"))

    g.add(dwg.line((tri_apex + 2, tri_top), (tri_apex + 2, tri_bot), stroke="#000", stroke_width=BODY_W))

    if value:
        g.add(_text(dwg, w / 2, mid_y + 18, value, text_anchor="middle", font_size="10px"))
    g.add(_text(dwg, 0, -12, ref, text_anchor="start", font_size="10px"))

    pins = {1: (x, y + mid_y), 2: (x + w, y + mid_y)}
    return g, pins


def draw_ground(dwg, x, y, ref=""):
    """GND symbol: three descending bars decreasing in width."""
    g = svgwrite.container.Group(transform=f"translate({x},{y})")

    g.add(dwg.line((0, 0), (0, -12), stroke="#000", stroke_width=WIRE_W))
    g.add(dwg.line((-16, 2), (16, 2), stroke="#000", stroke_width=BODY_W))
    g.add(dwg.line((-10, 8), (10, 8), stroke="#000", stroke_width=BODY_W))
    g.add(dwg.line((-4, 14), (4, 14), stroke="#000", stroke_width=BODY_W))

    if ref:
        g.add(_text(dwg, 20, 0, ref, text_anchor="start", font_size="10px"))

    pins = {1: (x, y - 12)}
    return g, pins


def draw_vcc(dwg, x, y, label="VCC"):
    """VCC symbol: upward arrow with label."""
    g = svgwrite.container.Group(transform=f"translate({x},{y})")

    g.add(dwg.line((0, 0), (0, 16), stroke="#000", stroke_width=WIRE_W))
    g.add(dwg.line((0, 16), (-8, 8), stroke="#000", stroke_width="1.2"))
    g.add(dwg.line((0, 16), (8, 8), stroke="#000", stroke_width="1.2"))

    g.add(_text(dwg, 14, 0, label, text_anchor="start", font_size="10px"))

    pins = {1: (x, y)}
    return g, pins


def draw_ic(dwg, x, y, width, height, pins_left, pins_right,
            ref="U?", name=""):
    """IC/MCU rectangle with labeled pins.

    Args:
        pins_left: list of dicts [{"num": N, "name": "..."}, ...] top-to-bottom
        pins_right: same, top-to-bottom
    Returns (group, {(num, side): (px,py), ...}).
    """
    g = svgwrite.container.Group(transform=f"translate({x},{y})")

    stub_len = 10
    body_x = stub_len
    body_y = 0
    body_w = width - 2 * stub_len
    body_h = height

    # Body
    g.add(dwg.rect(insert=(body_x, body_y), size=(body_w, body_h),
                   rx=3, ry=3, stroke="#000", stroke_width=BODY_W, fill="none"))

    # Labels
    if ref:
        g.add(_text(dwg, body_x + body_w / 2, body_y - 12, ref,
                    text_anchor="middle", font_size="10px"))
    if name:
        g.add(_text(dwg, body_x + body_w / 2, body_y + body_h + 14, name,
                    text_anchor="middle", font_size="9px", font_weight="normal"))

    pins = {}
    for side, pin_list in [("L", pins_left), ("R", pins_right)]:
        if not pin_list:
            continue
        spacer = body_h / (len(pin_list) + 1)
        for i, pin in enumerate(pin_list):
            py = (i + 1) * spacer
            if side == "L":
                px = 0
                g.add(dwg.line((px, py), (px + stub_len, py), stroke="#000", stroke_width=WIRE_W))
                g.add(_text(dwg, -4, py, str(pin["num"]), text_anchor="end", font_size="9px"))
                g.add(_text(dwg, body_x + 4, py, pin.get("name", ""), text_anchor="start",
                            font_size="8px", font_weight="normal"))
                pins[pin["num"]] = (x + px, y + py)
            else:
                px = width - stub_len
                g.add(dwg.line((px, py), (px + stub_len, py), stroke="#000", stroke_width=WIRE_W))
                g.add(_text(dwg, px + stub_len + 4, py, str(pin["num"]), text_anchor="start", font_size="9px"))
                g.add(_text(dwg, px - 4, py, pin.get("name", ""), text_anchor="end",
                            font_size="8px", font_weight="normal"))
                pins[pin["num"]] = (x + px + stub_len, y + py)

    return g, pins


def draw_header(dwg, x, y, pins=2, ref="J?"):
    """Pin header: row of circles."""
    g = svgwrite.container.Group(transform=f"translate({x},{y})")
    spacing = 25
    h = spacing * (pins - 1) + 20

    for i in range(pins):
        py = 10 + i * spacing
        g.add(dwg.circle(center=(10, py), r=5, stroke="#000", stroke_width=BODY_W, fill="none"))
        g.add(_text(dwg, 20, py, str(i + 1), text_anchor="start", font_size="9px"))

    if ref:
        g.add(_text(dwg, 0, -12, ref, text_anchor="start", font_size="10px"))

    g.add(dwg.rect(insert=(0, 0), size=(30, h), rx=2, ry=2,
                   stroke="#666", stroke_width="0.5", fill="none", stroke_dasharray="3,3"))

    pins_dict = {}
    for i in range(pins):
        pins_dict[i + 1] = (x + 10, y + 10 + i * spacing)
    return g, pins_dict
