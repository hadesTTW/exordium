#!/usr/bin/env python3
from __future__ import annotations

import copy
import math
import re
import sys
import xml.etree.ElementTree as ET
from typing import Dict, Optional, Set, List, Tuple

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

TEMPLATE_ID = "g16532"

STAR_IDS_TO_DELETE: List[str] = [
    "g16722", "g16712", "g16702", "g16692", "g16682", "g16672", "g16662",
    "g16652", "g16642", "g16632", "g16622", "g16612", "g16602", "g16592",
    "g16582", "g16572", "g16562", "g16552", "g16542"
]

# Center of the star ring in TOP-LEVEL SVG coordinates (your artboard coords)
GLOBAL_CENTER_X = 750.0
GLOBAL_CENTER_Y = 515.0

TOTAL_STARS = 27
STEP_DEG = 360.0 / TOTAL_STARS
DIRECTION = 1  # set to -1 if ring order goes the wrong way


# ----------------------------
# XML helpers
# ----------------------------

def build_parent_map(root: ET.Element) -> Dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in parent}

def find_element_by_id(root: ET.Element, elem_id: str) -> Optional[ET.Element]:
    for elem in root.iter():
        if elem.get("id") == elem_id:
            return elem
    return None

def find_all_ids(root: ET.Element) -> Set[str]:
    out: Set[str] = set()
    for e in root.iter():
        eid = e.get("id")
        if eid:
            out.add(eid)
    return out


# ----------------------------
# Transform math (2D affine)
# matrix form:
# [ a c e ]
# [ b d f ]
# [ 0 0 1 ]
# ----------------------------

_transform_cmd_re = re.compile(r"([a-zA-Z]+)\s*\(([^)]*)\)")

def parse_number_list(s: str) -> List[float]:
    parts = re.split(r"[,\s]+", s.strip())
    return [float(p) for p in parts if p]

def mat_identity() -> List[List[float]]:
    return [[1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0]]

def mat_mul(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    return [
        [
            a[0][0]*b[0][0] + a[0][1]*b[1][0] + a[0][2]*b[2][0],
            a[0][0]*b[0][1] + a[0][1]*b[1][1] + a[0][2]*b[2][1],
            a[0][0]*b[0][2] + a[0][1]*b[1][2] + a[0][2]*b[2][2],
        ],
        [
            a[1][0]*b[0][0] + a[1][1]*b[1][0] + a[1][2]*b[2][0],
            a[1][0]*b[0][1] + a[1][1]*b[1][1] + a[1][2]*b[2][1],
            a[1][0]*b[0][2] + a[1][1]*b[1][2] + a[1][2]*b[2][2],
        ],
        [0.0, 0.0, 1.0],
    ]

def mat_translate(tx: float, ty: float) -> List[List[float]]:
    return [[1.0, 0.0, tx],
            [0.0, 1.0, ty],
            [0.0, 0.0, 1.0]]

def mat_rotate(angle_deg: float) -> List[List[float]]:
    a = math.radians(angle_deg)
    c = math.cos(a)
    s = math.sin(a)
    return [[c, -s, 0.0],
            [s,  c, 0.0],
            [0.0, 0.0, 1.0]]

def parse_transform(transform: Optional[str]) -> List[List[float]]:
    if not transform or not transform.strip():
        return mat_identity()

    result = mat_identity()
    for cmd, argstr in _transform_cmd_re.findall(transform):
        vals = parse_number_list(argstr)
        c = cmd.lower()

        if c == "matrix":
            if len(vals) != 6:
                raise ValueError(f"matrix expects 6 values, got {len(vals)}")
            a, b, cc, d, e, f = vals
            m = [[a, cc, e], [b, d, f], [0.0, 0.0, 1.0]]

        elif c == "translate":
            if len(vals) == 1:
                m = mat_translate(vals[0], 0.0)
            elif len(vals) == 2:
                m = mat_translate(vals[0], vals[1])
            else:
                raise ValueError(f"translate expects 1 or 2 values, got {len(vals)}")

        elif c == "rotate":
            if len(vals) == 1:
                m = mat_rotate(vals[0])
            elif len(vals) == 3:
                ang, cx, cy = vals
                m = mat_mul(mat_translate(cx, cy),
                            mat_mul(mat_rotate(ang), mat_translate(-cx, -cy)))
            else:
                raise ValueError(f"rotate expects 1 or 3 values, got {len(vals)}")

        elif c == "scale":
            if len(vals) == 1:
                sx = sy = vals[0]
            elif len(vals) == 2:
                sx, sy = vals
            else:
                raise ValueError(f"scale expects 1 or 2 values, got {len(vals)}")
            m = [[sx, 0.0, 0.0], [0.0, sy, 0.0], [0.0, 0.0, 1.0]]

        else:
            # Illustrator exports mostly matrix/translate/scale/rotate
            raise ValueError(f"Unsupported transform cmd: {cmd}")

        # SVG applies transforms left-to-right
        result = mat_mul(result, m)

    return result

def mat_apply(m: List[List[float]], x: float, y: float) -> Tuple[float, float]:
    return (
        m[0][0]*x + m[0][1]*y + m[0][2],
        m[1][0]*x + m[1][1]*y + m[1][2],
    )

def mat_inv(m: List[List[float]]) -> List[List[float]]:
    a, c, e = m[0]
    b, d, f = m[1]
    det = a*d - b*c
    if abs(det) < 1e-12:
        raise ValueError("Non-invertible transform matrix")
    inv_det = 1.0 / det
    ai =  d * inv_det
    bi = -b * inv_det
    ci = -c * inv_det
    di =  a * inv_det
    ei = -(ai*e + ci*f)
    fi = -(bi*e + di*f)
    return [[ai, ci, ei], [bi, di, fi], [0.0, 0.0, 1.0]]

def matrix_to_svg(m: List[List[float]]) -> str:
    a, c, e = m[0]
    b, d, f = m[1]
    return f"matrix({a:.12g} {b:.12g} {c:.12g} {d:.12g} {e:.12g} {f:.12g})"


def cumulative_transform_to_element(elem: ET.Element, parent_map: Dict[ET.Element, ET.Element]) -> List[List[float]]:
    """
    Transform from root SVG coordinate space down to this element's local coordinate space?
    We build root->...->elem cumulative, i.e. local(elem) -> global.
    """
    chain: List[ET.Element] = []
    cur: Optional[ET.Element] = elem
    while cur is not None:
        chain.append(cur)
        cur = parent_map.get(cur)
    chain.reverse()

    m = mat_identity()
    for node in chain:
        m = mat_mul(m, parse_transform(node.get("transform")))
    return m


def cumulative_transform_to_parent(parent: ET.Element, parent_map: Dict[ET.Element, ET.Element]) -> List[List[float]]:
    """
    Local(parent) -> global cumulative transform.
    """
    chain: List[ET.Element] = []
    cur: Optional[ET.Element] = parent
    while cur is not None:
        chain.append(cur)
        cur = parent_map.get(cur)
    chain.reverse()

    m = mat_identity()
    for node in chain:
        m = mat_mul(m, parse_transform(node.get("transform")))
    return m


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python make_27_star_svg.py input.svg output.svg", file=sys.stderr)
        return 2

    input_svg, output_svg = sys.argv[1], sys.argv[2]

    tree = ET.parse(input_svg)
    root = tree.getroot()

    # Find template before deletion
    template_live = find_element_by_id(root, TEMPLATE_ID)
    if template_live is None:
        print(f"ERROR: template {TEMPLATE_ID} not found", file=sys.stderr)
        return 1

    # Snapshot template geometry
    template_snapshot = copy.deepcopy(template_live)

    # Parent where stars live
    pmap = build_parent_map(root)
    star_parent = pmap.get(template_live)
    if star_parent is None:
        print("ERROR: template has no parent", file=sys.stderr)
        return 1

    # Convert global ring center -> star_parent local coordinates
    # because wrappers will be inserted under star_parent
    parent_to_global = cumulative_transform_to_parent(star_parent, pmap)
    global_to_parent = mat_inv(parent_to_global)
    local_cx, local_cy = mat_apply(global_to_parent, GLOBAL_CENTER_X, GLOBAL_CENTER_Y)

    print(f"Using parent-local rotation center: ({local_cx:.6f}, {local_cy:.6f})")

    # Delete the 19 listed stars + the template itself
    all_to_delete = list(STAR_IDS_TO_DELETE) + [TEMPLATE_ID]
    deleted = 0
    for sid in all_to_delete:
        elem = find_element_by_id(root, sid)
        if elem is None:
            continue
        pmap = build_parent_map(root)
        par = pmap.get(elem)
        if par is None:
            continue
        par.remove(elem)
        deleted += 1

    existing_ids = find_all_ids(root)

    # Build 27 fresh stars as wrappers
    for i in range(TOTAL_STARS):
        angle = DIRECTION * STEP_DEG * i

        star = copy.deepcopy(template_snapshot)
        star_id = f"{TEMPLATE_ID}_new{i:02d}"
        suffix = 2
        while star_id in existing_ids:
            star_id = f"{TEMPLATE_ID}_new{i:02d}_{suffix}"
            suffix += 1
        star.set("id", star_id)
        existing_ids.add(star_id)

        # Wrapper group with rotation in parent-local coordinates
        wrapper = ET.Element(f"{{{SVG_NS}}}g")
        wrapper_id = f"{star_id}_wrap"
        while wrapper_id in existing_ids:
            wrapper_id += "_x"
        wrapper.set("id", wrapper_id)
        existing_ids.add(wrapper_id)

        wrapper.set("transform", f"rotate({angle:.12g} {local_cx:.12g} {local_cy:.12g})")
        wrapper.append(star)

        star_parent.append(wrapper)

    tree.write(output_svg, encoding="utf-8", xml_declaration=True)
    print(f"Deleted {deleted} old stars and created {TOTAL_STARS} new stars.")
    print("If the order is reversed, set DIRECTION = -1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())