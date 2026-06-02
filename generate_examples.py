#!/usr/bin/env python3
"""Generate example schematics demonstrating diagonal routing + autorouter.

Examples:
  horizontal — classic layout (Manhattan should work cleanly)
  diagonal   — same circuit, components offset to show 45° routing
  vertical   — stacked layout (tests maze router when direct paths are blocked)
  complex    — multiple nets through narrow channels (stresses maze router)
"""

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from renderer import SchematicRenderer


# ---------------------------------------------------------------------------
# Shared pin lists
# ---------------------------------------------------------------------------

def pins_left():
    return [
        {"num": 2, "name": "VDD3P3"},
        {"num": 3, "name": "VDD3P3"},
        {"num": 11, "name": "VDD3P3_RTC"},
        {"num": 17, "name": "VDD3P3_CPU"},
        {"num": 7, "name": "CHIP_EN"},
        {"num": 33, "name": "GND"},
    ]

def pins_right():
    return [
        {"num": 6, "name": "GPIO2"},
        {"num": 8, "name": "GPIO3"},
        {"num": 27, "name": "U0RXD"},
        {"num": 28, "name": "U0TXD"},
        {"num": 25, "name": "GPIO18"},
        {"num": 26, "name": "GPIO19"},
    ]


# ---------------------------------------------------------------------------
# Layouts
# ---------------------------------------------------------------------------

def layout_horizontal():
    """Classic left-to-right: IC -> R -> LED.  Manhattan routing works."""
    r = SchematicRenderer(cell_size=110)
    r.add_component("U1", "ic", grid_x=0, grid_y=1,
                    pins_left=pins_left(), pins_right=pins_right(), name="ESP32-C3")
    r.add_component("R1", "resistor", grid_x=3, grid_y=2, value="330R")
    r.add_component("D1", "led", grid_x=5, grid_y=2, value="RED")
    r.add_component("GND1", "ground", grid_x=5, grid_y=5)
    r.add_component("VCC1", "vcc", grid_x=1, grid_y=-1, label="+3.3V")
    r.add_net("GPIO2", [("U1", 6), ("R1", 1)])
    r.add_net("N$LED", [("R1", 2), ("D1", "A")])
    r.add_net("GND", [("GND1", 1), ("D1", "K"), ("U1", 33)])
    r.add_net("+3.3V", [("VCC1", 1), ("U1", 2), ("U1", 3)])
    return r


def layout_diagonal_45():
    """Offset components to exercise 45° routing.

    R1 is one grid row below U1, D1 one row below R1 — the 45° router
    produces angled traces instead of stepped Manhattan.
    """
    r = SchematicRenderer(cell_size=110)
    r.add_component("U1", "ic", grid_x=0, grid_y=0,
                    pins_left=pins_left(), pins_right=pins_right(), name="ESP32-C3")
    r.add_component("R1", "resistor", grid_x=3, grid_y=2, value="330R")
    r.add_component("D1", "led", grid_x=3, grid_y=4, value="RED")
    r.add_component("GND1", "ground", grid_x=3, grid_y=7)
    r.add_component("VCC1", "vcc", grid_x=0, grid_y=-1, label="+3.3V")
    r.add_net("GPIO2", [("U1", 6), ("R1", 1)])
    r.add_net("N$LED", [("R1", 2), ("D1", "A")])
    r.add_net("GND", [("GND1", 1), ("D1", "K"), ("U1", 33)])
    r.add_net("+3.3V", [("VCC1", 1), ("U1", 2), ("U1", 3)])
    return r


def layout_vertical():
    """Stacked layout: tests maze router when direct paths collide.

    Components are arranged vertically with tight spacing, forcing the
    autorouter to find paths around component bodies.
    """
    r = SchematicRenderer(cell_size=110)
    r.add_component("U1", "ic", grid_x=0, grid_y=0,
                    pins_left=[
                        {"num": 2, "name": "VDD3P3"},
                        {"num": 3, "name": "VDD3P3"},
                        {"num": 7, "name": "CHIP_EN"},
                        {"num": 33, "name": "GND"},
                    ],
                    pins_right=[
                        {"num": 6, "name": "GPIO2"},
                        {"num": 27, "name": "U0RXD"},
                        {"num": 28, "name": "U0TXD"},
                    ],
                    name="ESP32-C3")
    r.add_component("R1", "resistor", grid_x=3, grid_y=3, value="330R")
    r.add_component("D1", "led", grid_x=3, grid_y=5, value="RED")
    r.add_component("GND1", "ground", grid_x=3, grid_y=8)
    r.add_component("VCC1", "vcc", grid_x=0, grid_y=-1, label="+3.3V")
    r.add_net("GPIO2", [("U1", 6), ("R1", 1)])
    r.add_net("N$LED", [("R1", 2), ("D1", "A")])
    r.add_net("GND", [("GND1", 1), ("D1", "K"), ("U1", 33)])
    r.add_net("+3.3V", [("VCC1", 1), ("U1", 2), ("U1", 3)])
    return r


def layout_complex():
    """Denser circuit: multiple ICs + passives to stress the channel allocator.

    Three nets running between components that are partially blocking each
    other's direct routes — forces the maze router to find free channels.
    """
    r = SchematicRenderer(cell_size=100)

    # MCU on the left
    r.add_component("U1", "ic", grid_x=0, grid_y=0,
                    pins_left=[
                        {"num": 1, "name": "VDD"},
                        {"num": 2, "name": "GND"},
                        {"num": 3, "name": "SDA"},
                        {"num": 4, "name": "SCL"},
                    ],
                    pins_right=[
                        {"num": 5, "name": "TX"},
                        {"num": 6, "name": "RX"},
                        {"num": 7, "name": "GPIO1"},
                        {"num": 8, "name": "GPIO2"},
                    ],
                    name="MCU")

    # Sensor IC on the top-right
    r.add_component("U2", "ic", grid_x=5, grid_y=0,
                    pins_left=[
                        {"num": 1, "name": "VDD"},
                        {"num": 2, "name": "GND"},
                        {"num": 3, "name": "SDA"},
                        {"num": 4, "name": "SCL"},
                    ],
                    pins_right=[
                        {"num": 5, "name": "INT"},
                        {"num": 6, "name": "ADDR"},
                    ],
                    name="SENSOR")

    # Driver IC on bottom-right
    r.add_component("U3", "ic", grid_x=5, grid_y=4,
                    pins_left=[
                        {"num": 1, "name": "VDD"},
                        {"num": 2, "name": "GND"},
                        {"num": 3, "name": "IN1"},
                        {"num": 4, "name": "IN2"},
                    ],
                    pins_right=[
                        {"num": 5, "name": "OUT1"},
                        {"num": 6, "name": "OUT2"},
                    ],
                    name="DRV")

    # LEDs + resistors driven by U3
    r.add_component("R1", "resistor", grid_x=8, grid_y=4, value="330R")
    r.add_component("D1", "led", grid_x=10, grid_y=4, value="RED")
    r.add_component("R2", "resistor", grid_x=8, grid_y=6, value="330R")
    r.add_component("D2", "led", grid_x=10, grid_y=6, value="GRN")

    # GND
    r.add_component("GND1", "ground", grid_x=3, grid_y=8)
    r.add_component("VCC1", "vcc", grid_x=0, grid_y=-1, label="+3.3V")

    # I2C bus (multi-point)
    r.add_net("SDA", [("U1", 3), ("U2", 3)])
    r.add_net("SCL", [("U1", 4), ("U2", 4)])

    # Power (multi-point)
    r.add_net("VDD", [("VCC1", 1), ("U1", 1), ("U2", 1), ("U3", 1)])
    r.add_net("GND", [("GND1", 1), ("U1", 2), ("U2", 2), ("U3", 2)])

    # UART from MCU
    r.add_net("TX", [("U1", 5), ("U3", 3)])
    r.add_net("RX", [("U1", 6), ("U3", 4)])

    # Driver outputs -> LEDs
    r.add_net("OUT1", [("U3", 5), ("R1", 1)])
    r.add_net("N$R1D1", [("R1", 2), ("D1", "A")])
    r.add_net("OUT2", [("U3", 6), ("R2", 1)])
    r.add_net("N$R2D2", [("R2", 2), ("D2", "A")])

    # LED cathodes to GND
    r.add_net("N$D1GND", [("D1", "K"), ("GND1", 1)])
    r.add_net("N$D2GND", [("D2", "K"), ("GND1", 1)])

    return r


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "/tmp"

    layouts = [
        ("horizontal", layout_horizontal),
        ("diagonal_45", layout_diagonal_45),
        ("vertical", layout_vertical),
        ("complex", layout_complex),
    ]

    for name, fn in layouts:
        print(f"Rendering {name}...", end=" ")
        r = fn()
        svg = r.render(filename=os.path.join(output_dir, f"schematic_{name}.svg"))
        print(f"SVG: {svg}")

        png = os.path.join(output_dir, f"schematic_{name}.png")
        result = os.system(
            f'sips -s format png "{svg}" --out "{png}" 2>/dev/null'
        )
        if result == 0 and os.path.exists(png):
            print(f"  PNG: {png} ({os.path.getsize(png)} bytes)")
        else:
            print(f"  (png skipped - sips not available)")

    print("Done.")
