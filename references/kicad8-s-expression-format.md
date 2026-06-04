# KiCad 8 S-Expression Grammar Reference — Verified from Source

Key grammar rules verified from 'sch_io_kicad_sexpr.cpp' and 'sch_io_kicad_sexpr_parser.cpp' (KiCad 8/10).

## no_connect
```
(no_connect (at x y) [uuid] [locked])
```
- NO stroke sub-element
- uuid and locked are optional (auto-generated on import if absent)

## junction
```
(junction (at x y) (diameter N) (color R G B A) [uuid] [locked])
```

## wire
```
(wire (pts (xy x1 y1) (xy x2 y2)) (stroke ...) [uuid] [locked])
```
- stroke includes width, type (solid/dash/dotted), color

## label (net label for single-sheet)
```
(label "TEXT" (at x y 0) (effects (font (size 1.27 1.27))))
```

## global_label (for cross-sheet only)
```
(global_label "TEXT" (shape input) (at x y 0) (effects (font (size 1.27 1.27))))
```

## symbol instance (placed component)
```
(symbol (lib_id "LIB_ID") (at x y rotation) (unit N) (body_style N)
        (in_bom yes) (on_board yes) [uuid]
        (property "Reference" "REF" (id N) (at x y 0) (effects ...))
        (property "Value" "VAL" (id N) (at x y 0) (effects ...)))
```
- body_style defaults to 0 (normal) if omitted

## pin (inside lib_symbols)
```
(pin <type> <shape> (at x y rotation) (length N) [hide]
  (name "TEXT" (effects (font (size 1.016 1.016))) [at x y rotation])
  (number "N" (effects (font (size 1.016 1.016)))))
```
- name: (effects ...) MUST come before (at ...) if both present
- type: passive, input, output, bidirectional, tri_state, power_in, power_out, etc.
- shape: line, inverted, clock, etc.
- hide keyword can be bare after (length N) or in a (hide BoolExpr) inside the pin

## Pin name parsing (critical):
From KiCad source (parseSymbolPin):
1. After T_name, read the name string
2. NextTok() - if T_RIGHT, name field done (just 'name "TEXT"')
3. If not T_RIGHT, NextTok() again - MUST be T_effects
4. If not T_effects, Expecting("effects") - parse error

So: (name "TEXT" (at x y) (effects ...)) ALWAYS fails because the parser
finds T_at instead of T_effects as the first sub-element.
