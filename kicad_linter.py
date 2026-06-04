#!/usr/bin/env python3
"""
kicad_linter.py — AI Agent Self-Check Tool for KiCad Schematics
Run after generating any .kicad_sch file. Iterate until PASS.

Checks: grid, wire length, diagonal wires, component overlap,
label overlap, T-intersection junctions, row alignment, color-crossing,
inline symbol definitions, GND_PWR count + clearance, duplicate symbols.

v2.0 — Added inline symbol validation, GND_PWR instance count,
        GND_PWR clearance, duplicate symbol detection.
        Based on 14-revision battle hardening from indicator_panel project.
"""

import sys, re
from collections import defaultdict

GRID_MM = 1.0
MIN_WIRE_LENGTH = 25  # lowered to 25mil to accept short power stubs
GND_PWR_CLEARANCE_MM = 10  # min distance from component bodies (user preference)

def mil(v): return v * 39.3701

def parse(fp):
    with open(fp, encoding="utf-8") as f: return f.read()

def extract_wires(c):
    return [tuple(mil(float(v)) for v in m.groups())
            for m in re.finditer(r'\(wire\s+\(pts\s+\(xy\s+([-\d.]+)\s+([-\d.]+)\)\s+\(xy\s+([-\d.]+)\s+([-\d.]+)\)\)', c)]

def extract_symbols(c):
    """Extract placed symbol instances (lib_id references)."""
    s = []
    inst_start = c.find('\n  (symbol (lib_id')
    if inst_start < 0:
        return s
    scan = c[inst_start:]
    for m in re.finditer(r'\(symbol\s+\(lib_id\s+"([^"]+)"\)\s+\(at\s+([-\d.]+)\s+([-\d.]+)', scan):
        lib_id = m.group(1)
        x_str, y_str = m.group(2), m.group(3)
        # Find reference in the next 200 chars
        tail = scan[m.end():m.end()+200]
        rf = re.search(r'\(property "Reference" "([^"]+)"', tail)
        ref = rf.group(1) if rf else "?"
        vl = re.search(r'\(property "Value" "([^"]+)"', tail)
        val = vl.group(1) if vl else "?"
        s.append({"ref": ref, "value": val, "lib_id": lib_id,
                   "x": mil(float(x_str)), "y": mil(float(y_str))})
    return s

def extract_instances(c):
    """Extract full lib_id references from symbol instances."""
    instances = []
    lib_end = c.find('  (symbol (lib_id')
    if lib_end < 0: lib_end = 0
    scan = c[lib_end:]
    for m in re.finditer(r'\(symbol\s+\(lib_id\s+"([^"]+)"\)', scan):
        instances.append(m.group(1))
    return instances

def extract_lib_symbols(c):
    """Extract all inline symbol definition names from lib_symbols section."""
    # Find the lib_symbols block
    ls_start = c.find('(lib_symbols')
    ls_end = c.find(')\n  (symbol (lib_id')  # first instance after lib_symbols
    if ls_start < 0:
        return set()
    if ls_end < 0:
        ls_end = c.find('\n  (wire')
    block = c[ls_start:ls_end] if ls_end > ls_start else c[ls_start:]
    defs = set()
    for m in re.finditer(r'\(symbol\s+"([^"]+)"\s+\((?:pin_names|power)', block):
        defs.add(m.group(1))
    return defs

def extract_labels(c):
    l = []
    lib_end = c.find('(symbol (lib_id')
    if lib_end < 0: lib_end = c.find('  (symbol (lib_id')
    scan = c[lib_end:] if lib_end > 0 else c
    for m in re.finditer(r'\(label "([^"]+)" \(at ([-\d.]+) ([-\d.]+)', scan):
        t, x, y = m.group(1), float(m.group(2)), float(m.group(3)); l.append((t, mil(x), mil(y)))
    for m in re.finditer(r'\(property "(?:Reference|Value)" "([^"]*)" \(id \d+\) \(at ([-\d.]+) ([-\d.]+)', scan):
        t, x, y = m.group(1), float(m.group(2)), float(m.group(3)); l.append((t, mil(x), mil(y)))
    return l

def extract_junctions(c):
    return set((round(mil(float(m.group(1)))), round(mil(float(m.group(2))))) for m in re.finditer(r'\(junction \(at ([-\d.]+) ([-\d.]+)\)', c))

def extract_power_instances(c):
    """Count GND_PWR and VCC_PWR instances (not the lib_symbols definition)."""
    # Find the lib_symbols closing, then scan instances after it
    ls_end = c.find(')\n  (symbol (lib_id')
    if ls_end < 0:
        ls_end = c.find('  (symbol (lib_id')
    scan = c[ls_end:] if ls_end > 0 else c
    gnd = list(re.finditer(r'\(symbol\s+\(lib_id\s+"GND_PWR"\)', scan))
    vcc = list(re.finditer(r'\(symbol\s+\(lib_id\s+"VCC_PWR"\)', scan))
    return len(gnd), len(vcc)

V = []
def v(msg): V.append(msg)

def check_grid(s, w):
    for s2 in s:
        for val, axis in [(s2["x"],"X"),(s2["y"],"Y")]:
            if val % (GRID_MM*39.3701) > 39.3701: v(f"GRID: {s2['ref']} ({s2['value']}) {axis}={val:.0f}mil off grid")
    for i,(x1,y1,x2,y2) in enumerate(w):
        for val, a in [(x1,"x1"),(y1,"y1"),(x2,"x2"),(y2,"y2")]:
            if val % (GRID_MM*39.3701) > 39.3701: v(f"GRID: Wire #{i} {a}={val:.0f}mil off grid")

def check_wl(w):
    for i,(x1,y1,x2,y2) in enumerate(w):
        d = ((x2-x1)**2+(y2-y1)**2)**.5
        if d < MIN_WIRE_LENGTH: v(f"SHORT: Wire #{i} length={d:.0f}mil (min {MIN_WIRE_LENGTH})")

def check_diag(w):
    for i,(x1,y1,x2,y2) in enumerate(w):
        if abs(x1-x2)>1 and abs(y1-y2)>1: v(f"DIAGONAL: Wire #{i}")

def check_ol(s):
    for i,a in enumerate(s):
        for j,b in enumerate(s):
            if i<j:
                dx,dy = abs(a["x"]-b["x"]),abs(a["y"]-b["y"])
                if dx<300 and dy<300: v(f"OVERLAP: {a['ref']} near {b['ref']} dx={dx:.0f} dy={dy:.0f}mil")

def check_ll(l):
    for i,(ta,xa,ya) in enumerate(l):
        for j,(tb,xb,yb) in enumerate(l):
            if i<j and abs(xa-xb)<50 and abs(ya-yb)<50: v(f"LABEL: '{ta}' and '{tb}' at ({xa:.0f},{ya:.0f})")

def check_tj(w, j):
    for (px,py) in [*[(round(x1),round(y1)) for (x1,y1,x2,y2) in w], *[(round(x2),round(y2)) for (x1,y1,x2,y2) in w]]:
        for (x1,y1,x2,y2) in w:
            rx1,ry1,rx2,ry2 = round(x1),round(y1),round(x2),round(y2)
            if (px==rx1 and py==ry1) or (px==rx2 and py==ry2): continue
            on = (abs(py-ry1)<2 and abs(ry1-ry2)<2 and min(rx1,rx2)-2<px<max(rx1,rx2)+2) or \
                 (abs(px-rx1)<2 and abs(rx1-rx2)<2 and min(ry1,ry2)-2<py<max(ry1,ry2)+2)
            if on and (px,py) not in j: v(f"TJUNCTION: ({px},{py})mil missing junction")

def check_color_crossings(c, w):
    """Check that wire endpoints of different net colors don't overlap without junctions."""
    lines = c.split('\n')
    colors = []
    idx = 0
    while idx < len(lines):
        if '  (wire (pts' in lines[idx] and idx + 1 < len(lines):
            cm = re.search(r'\(color\s+(\d+)\s+(\d+)\s+(\d+)', lines[idx + 1])
            colors.append((int(cm.group(1)), int(cm.group(2)), int(cm.group(3))) if cm else None)
            idx += 2
        else:
            idx += 1
    junctions = set((round(x2), round(y2)) for x1,y1,x2,y2 in w)
    eps_mil = 20
    for i, (x1,y1,x2,y2) in enumerate(w):
        ci = colors[i] if i < len(colors) else None
        if ci is None: continue
        for ep_x, ep_y in [(x2,y2)]:
            for j, (ox1,oy1,ox2,oy2) in enumerate(w):
                if i == j: continue
                cj = colors[j] if j < len(colors) else None
                if cj is None or ci == cj: continue
                rx1, ry1, rx2, ry2 = round(ox1), round(oy1), round(ox2), round(oy2)
                on_h = abs(ry1-ry2)<eps_mil and abs(round(ep_y)-ry1)<eps_mil and min(rx1,rx2)-eps_mil<round(ep_x)<max(rx1,rx2)+eps_mil
                on_v = abs(rx1-rx2)<eps_mil and abs(round(ep_x)-rx1)<eps_mil and min(ry1,ry2)-eps_mil<round(ep_y)<max(ry1,ry2)+eps_mil
                if (on_h or on_v) and (round(ep_x),round(ep_y)) not in junctions:
                    v(f"COLOR-CROSS: Wire #{i} ({ci}) endpoint at ({round(ep_x)},{round(ep_y)})mil lies on Wire #{j} ({cj}) - DIFFERENT NET!")

def check_rows(s):
    g = defaultdict(list)
    for s2 in s:
        p = re.match(r'[A-Z]+', s2["ref"])
        if p: g[p.group()].append(s2)
    for p,grp in g.items():
        if len(grp)<2: continue
        ys = sorted(set(round(s2["y"]) for s2 in grp))
        for i in range(len(ys)-1):
            if ys[i+1]-ys[i] < 300: v(f"ROWS: {p} gap {ys[i+1]-ys[i]}mil (min 300)")

def check_inline_symbols(c, instances):
    """Every lib_id used must have a matching definition in lib_symbols."""
    defs = extract_lib_symbols(c)
    for lib_id in set(instances):
        if lib_id not in defs:
            v(f"SYMBOL: '{lib_id}' has no inline definition in lib_symbols — KiCad will show '?'")

def check_duplicate_defs(c):
    """Warn if any symbol is defined more than once in lib_symbols."""
    ls_start = c.find('(lib_symbols')
    if ls_start < 0:
        return
    # Find end of lib_symbols (where first instance starts)
    inst_start = c.find('\n  (symbol (lib_id')
    block = c[ls_start:inst_start] if inst_start > ls_start else c[ls_start:]
    names = list(re.finditer(r'\(symbol\s+"([^"]+)"\s+\((?:pin_names|power)', block))
    seen = {}
    for m in names:
        name = m.group(1)
        if name in seen:
            print(f"  ⚠ WARNING: '{name}' defined twice in lib_symbols (line ~{c[:m.start()].count(chr(10))+1} and ~{seen[name]})")
            print(f"    -> KiCad uses the LAST definition. This is accepted but wastes bytes.")
        else:
            seen[name] = c[:m.start()].count(chr(10)) + 1

def check_power_counts(c):
    """Check GND_PWR and VCC_PWR instance counts match expected patterns."""
    gnd_count, vcc_count = extract_power_instances(c)
    if gnd_count > 1:
        v(f"GND_PWR: {gnd_count} instances found — typically only 1 is needed when GND bus interconnects everything")
    if gnd_count == 0:
        v(f"GND_PWR: no instance found — add one to label the GND net")
    if vcc_count > 1:
        v(f"VCC_PWR: {vcc_count} instances found — typically only 1 is needed")

def check_gnd_clearance(c):
    """Check GND_PWR has minimum clearance from component bodies."""
    clearence_mil = GND_PWR_CLEARANCE_MM * 39.3701
    # Find GND_PWR instance positions (after lib_symbols)
    ls_end = c.find(')\n  (symbol (lib_id')
    if ls_end < 0:
        ls_end = c.find('  (symbol (lib_id')
    scan = c[ls_end:] if ls_end > 0 else c
    gnd_positions = []
    for m in re.finditer(r'\(symbol\s+\(lib_id\s+"GND_PWR"\)\s+\(at\s+([-\d.]+)\s+([-\d.]+)', scan):
        gnd_positions.append((mil(float(m.group(1))), mil(float(m.group(2)))))
    
    if not gnd_positions:
        return
    
    # Get all component positions
    for m in re.finditer(r'\(symbol\s+\(lib_id\s+"([^"]+)"\)\s+\(at\s+([-\d.]+)\s+([-\d.]+)', scan):
        lib_id = m.group(1)
        sx, sy = mil(float(m.group(2))), mil(float(m.group(3)))
        # Find reference in remaining text
        slice = scan[m.end():m.end()+200]
        rf = re.search(r'\(property "Reference" "([^"]+)"', slice)
        if not rf:
            continue
        ref = rf.group(1)
        if ref.startswith('#PWR'):  # skip power symbols themselves
            continue
        for gx, gy in gnd_positions:
            dx, dy = abs(sx - gx), abs(sy - gy)
            if dx < clearence_mil and dy < clearence_mil:
                v(f"GND_CLR: GND_PWR too close to {ref} — dx={dx/39.3701:.0f}mm dy={dy/39.3701:.0f}mm (min {GND_PWR_CLEARANCE_MM}mm)")

def main():
    if len(sys.argv)<2: print("Usage: python kicad_linter.py <file>"); sys.exit(1)
    fp = sys.argv[1]
    try: c = parse(fp)
    except FileNotFoundError: print(f"ERROR: File not found: {fp}"); sys.exit(1)
    w = extract_wires(c)
    s = extract_symbols(c)
    l = extract_labels(c)
    j = extract_junctions(c)
    instances = extract_instances(c)
    
    print(f"Linting: {fp}\n{'='*60}")
    print(f"Found: {len(s)} symbols, {len(w)} wires, {len(l)} labels, {len(j)} junctions\n")
    
    check_grid(s,w)
    check_wl(w)
    check_diag(w)
    check_ol(s)
    check_ll(l)
    check_tj(w,j)
    check_color_crossings(c,w)
    check_rows(s)
    check_inline_symbols(c, instances)
    check_duplicate_defs(c)
    check_power_counts(c)
    check_gnd_clearance(c)
    
    gnd_count, vcc_count = extract_power_instances(c)
    print(f"Power symbols: GND_PWR={gnd_count}, VCC_PWR={vcc_count}")
    
    if not V:
        print("\nPASS: No violations found.")
    else:
        print(f"\nFAIL: {len(V)} violation(s):\n")
        for i,v2 in enumerate(V,1): print(f"  [{i:02d}] {v2}")
        print(f"\n{'='*60}\nFix all violations, re-run."); sys.exit(1)

if __name__ == "__main__": main()
