#!/usr/bin/env python3
"""Routing regression tests. Run with python3 -B; no dependencies or caches.

Set ROUTING_TEST_OUTPUT to an existing directory to exercise the CLI there.
Test artifacts are deliberately retained; tests never remove user files.
"""
from __future__ import annotations

import copy
import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_diagram as b
import diagram_lib as lib
import validate as validator


def node(id, **kw):
    return {"id": id, "name": id, **kw}


def edge(src, dst, **kw):
    return {"from": src, "to": dst, **kw}


def spec(tiers, edges):
    return {"title": "Routing audit", "legend": False,
            "tiers": [{"nodes": ns} for ns in tiers], "edges": edges}


# The original sixteen research/routing/reproduce.py fixtures, with the two
# deliberately invalid inputs retained as rejection regressions.
CASES = {
    "01_many_to_one": spec([[node("A"), node("B")], [node("D")]],
                           [edge("A", "D"), edge("B", "D")]),
    "02_reciprocal_adjacent": spec([[node("A")], [node("B")]],
                                  [edge("A", "B"), edge("B", "A")]),
    "03_reciprocal_same_tier": spec([[node("A"), node("B")]],
                                   [edge("A", "B"), edge("B", "A")]),
    "04_same_tier_obstacle": spec([[node("A"), node("W", name="W" * 29), node("C")]],
                                 [edge("A", "C")]),
    "05_skip_obstacle": spec([[node("W", name="W" * 29), node("A")], [node("X")], [node("D")]],
                            [edge("A", "D")]),
    "06_backward_obstacle": spec([[node("A"), node("W", name="W" * 29)], [node("D")]],
                                [edge("D", "A")]),
    "07_cloud_port": spec([[node("C", shape="cloud")], [node("D")], [node("E")]],
                          [edge("C", "E")]),
    "08_actor_port": spec([[node("A", shape="actor")], [node("B")], [node("C")]],
                          [edge("A", "C")]),
    "09_fan_saturation": spec([[node("A")], [node("D" + str(i)) for i in range(7)]],
                              [edge("A", "D" + str(i)) for i in range(7)]),
    "10_skip_shared_stem": spec([[node("A")], [node("X")], [node("C")], [node("D")]],
                               [edge("A", "C"), edge("A", "D")]),
    "11_self_loop": spec([[node("A")]], [edge("A", "A")]),
    "12_string_false": spec([[node("A")], [node("B")]], [edge("A", "B", bidirectional="false")]),
    "13_hex_midpoint": spec([[node("A"), node("B")],
                             [node("H", shape="hex"), node("D", subs=["a", "b", "c"])]],
                            [edge("A", "H")]),
    "14_marker_styles": spec([[node("A"), node("B"), node("C")], [node("D"), node("E"), node("F")]],
                             [edge("A", "D", style="thin", bidirectional=True),
                              edge("B", "E", style="solid", bidirectional=True),
                              edge("C", "F", style="thick", bidirectional=True)]),
    "15_rect_control": spec([[node("A")], [node("B")]], [edge("A", "B")]),
    "16_mixed_shape_control": spec([[node("A", shape="actor")], [node("R")],
                                    [node("Y", shape="cylinder")], [node("H", shape="hex")],
                                    [node("S", shape="stack")], [node("C", shape="cloud")]],
                                   [edge("A", "R"), edge("R", "Y"), edge("Y", "H"),
                                    edge("H", "S"), edge("S", "C")]),
}


def segments(points):
    return [(*a, *c) for a, c in zip(points, points[1:])]


def l1(points):
    return sum(abs(x2 - x1) + abs(y2 - y1) for x1, y1, x2, y2 in segments(points))


def positive_overlap(a, c):
    # Independent exact interval test: endpoint contact is not a shared run.
    if a[1] == a[3] == c[1] == c[3]:
        return min(max(a[0], a[2]), max(c[0], c[2])) - max(min(a[0], a[2]), min(c[0], c[2])) > 1e-6
    if a[0] == a[2] == c[0] == c[2]:
        return min(max(a[1], a[3]), max(c[1], c[3])) - max(min(a[1], a[3]), min(c[1], c[3])) > 1e-6
    return False


def point_segment_distance(p, a, c):
    dx, dy = c[0] - a[0], c[1] - a[1]
    t = max(0, min(1, ((p[0]-a[0])*dx + (p[1]-a[1])*dy) / (dx*dx+dy*dy))) if dx or dy else 0
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def outline_distance(point, group):
    """Measure against rendered SVG, independent of Node.contour_x."""
    distances = []
    for el in group:
        if "node" not in el.get("class", "").split():
            continue
        attrs = el.attrib
        if el.tag == "rect":
            x, y, w, h = (float(attrs[k]) for k in ("x", "y", "width", "height"))
            r = float(attrs.get("rx", 0))
            pts = []
            for cx, cy, angle in ((x+w-r, y+r, -90), (x+w-r, y+h-r, 0),
                                  (x+r, y+h-r, 90), (x+r, y+r, 180)):
                pts.extend((cx+r*math.cos(math.radians(angle+k*90/64)),
                            cy+r*math.sin(math.radians(angle+k*90/64))) for k in range(65))
            pts.append(pts[0])
        elif el.tag == "circle":
            cx, cy, r = (float(attrs[k]) for k in ("cx", "cy", "r"))
            distances.append(abs(math.hypot(point[0]-cx, point[1]-cy)-r))
            continue
        elif el.tag == "path":
            pts = lib.path_points(attrs["d"])
        elif el.tag == "polygon":
            pts = lib.points_polyline(attrs["points"])[0]
        else:
            continue
        distances.extend(point_segment_distance(point, a, c) for a, c in zip(pts, pts[1:]))
    return min(distances)


class RoutingTests(unittest.TestCase):
    def assert_sound(self, raw):
        s = b.Spec(copy.deepcopy(raw))
        layout = b.Layout(s)
        fragment = b.Renderer(layout).render()
        xml = ET.fromstring("<svg>" + fragment + "</svg>")
        groups = {g.get("data-node-id"): g for g in xml.findall("g")}
        self.assertEqual(set(groups), set(s.nodes))
        paths = [p for p in xml.findall("path") if p.get("data-edge-id")]
        self.assertEqual(len(paths), len(raw["edges"]))
        for i, (e, path) in enumerate(zip(s.edges, paths)):
            self.assertEqual(path.get("data-edge-id"), f"edge-{i}")
            self.assertEqual(path.get("data-from"), raw["edges"][i]["from"])
            self.assertEqual(path.get("data-to"), raw["edges"][i]["to"])
            self.assertEqual(path.get("data-bidirectional"), str(e.bidirectional).lower())
            suffix = "-" + e.type
            self.assertEqual(path.get("marker-end"), f"url(#arrowhead{suffix})")
            self.assertEqual(path.get("marker-start"), f"url(#arrowhead-start{suffix})" if e.bidirectional else None)
            emitted = lib.path_points(path.get("d"))
            for actual, expected in zip(emitted, e.points):
                self.assertAlmostEqual(actual[0], expected[0], delta=0.005)
                self.assertAlmostEqual(actual[1], expected[1], delta=0.005)
            for role, nd in (("src", e.src), ("dst", e.dst)):
                port = getattr(e, role + "_port")
                point = getattr(e, role + "_point")
                self.assertEqual(groups[nd.id].get("data-shape"), nd.shape)
                self.assertLess(outline_distance(port, groups[nd.id]), 0.35, (e.id, role, nd.shape, port))
                has_head = role == "dst" or e.bidirectional
                self.assertAlmostEqual(abs(point[0]-port[0]), 6 if has_head else 2)
                self.assertEqual(point[1], port[1])
                tangent = e.points[1] if role == "src" else e.points[-2]
                sign = -1 if getattr(e, role + "_side") == "left" else 1
                self.assertEqual(tangent[1], point[1])
                self.assertGreater(sign * (tangent[0]-point[0]), 0)
                if has_head:
                    tip = point[0] - sign * 4
                    self.assertAlmostEqual(sign * (tip-port[0]), 2)
            own_segments = segments(e.points)
            for j, seg in enumerate(own_segments):
                self.assertTrue(seg[0] == seg[2] or seg[1] == seg[3])
                for old in own_segments[j + 1:]:
                    self.assertFalse(positive_overlap(seg, old), (e.id, "self-overlap", seg, old))
                for nd in s.nodes.values():
                    if nd not in (e.src, e.dst):
                        self.assertFalse(lib.seg_hits_box(seg, nd.bbox, inset=0), (e.id, nd.id, seg))
                for other in s.edges:
                    if other is e:
                        continue
                    for old in segments(other.points):
                        self.assertFalse(positive_overlap(seg, old), (e.id, other.id, seg, old))
                    for role in ("src", "dst"):
                        if role == "src" and not other.bidirectional:
                            continue
                        # Exact axis-aligned marker bbox from the agreed 10x8
                        # geometry. This over-approximates its triangle interior.
                        p = getattr(other, role + "_point")
                        sign = -1 if getattr(other, role + "_side") == "left" else 1
                        xx = (p[0] - sign*4, p[0] + sign*6)
                        box = (min(xx), p[1]-4, max(xx), p[1]+4)
                        self.assertFalse(lib.seg_hits_box(seg, box, inset=0.01), (e.id, other.id, role))
            for x, y in e.points:
                self.assertGreaterEqual(x, b.MARGIN)
                self.assertGreaterEqual(y, b.MARGIN)
                self.assertLess(x, layout.view_w)
                self.assertLess(y, layout.view_h)
            if e.label:
                box = e.label_box
                self.assertIsNotNone(box)
                for nd in s.nodes.values():
                    self.assertFalse(lib.boxes_overlap(box, nd.bbox, tol=0))
                for other in s.edges:
                    if other is not e and other.label_box:
                        self.assertFalse(lib.boxes_overlap(box, other.label_box, tol=0))
                    for seg in segments(other.points):
                        self.assertFalse(lib.seg_hits_box(seg, box, inset=-3.9), (e.id, other.id, "label-line"))
        ports = {}
        for e in s.edges:
            for role, nd in (("src", e.src), ("dst", e.dst)):
                key = (nd.id, getattr(e, role + "_side"))
                y = getattr(e, role + "_port")[1]
                for old in ports.setdefault(key, []):
                    self.assertGreaterEqual(abs(y-old), b.PORT_STEP - 1e-6)
                ports[key].append(y)
        # Same object and fresh object are both deterministic/idempotent.
        snapshot = [(e.points[:], e.label_at) for e in s.edges]
        b.Layout(s)
        self.assertEqual(snapshot, [(e.points, e.label_at) for e in s.edges])
        fresh = b.Spec(copy.deepcopy(raw))
        b.Layout(fresh)
        self.assertEqual(snapshot, [(e.points, e.label_at) for e in fresh.edges])
        return s, layout

    def assert_geometry(self, s, labels=()):
        """Validate emitted SVG, not the router's own obstacle approximation."""
        html = b.build(s, b.TEMPLATE.read_text())
        doc = lib.DiagramDocument(html)
        report = validator.Reporter(Path(__file__), strict=True)
        validator.check_geometry(doc, report)
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])
        runs = [run for el in doc.rendered_elements if el.tag == "text"
                for run in el.text_runs if run["text"] in labels]
        self.assertEqual({run["text"] for run in runs}, set(labels))
        arrows = [el for el in doc.rendered_elements if el.attrs.get("data-edge-id")]
        for arrow in arrows:
            markers, issues = lib.marker_instances(doc, arrow)
            self.assertEqual(issues, [])
            for run in runs:
                for seg in lib.segments_of(arrow):
                    self.assertFalse(lib.seg_hits_box(seg, run["bbox"], inset=0),
                                     (arrow.attrs["data-edge-id"], run["text"], seg))
                for marker in markers:
                    self.assertFalse(lib.boxes_overlap(marker["bbox"], run["bbox"], tol=0),
                                     (arrow.attrs["data-edge-id"], run["text"], marker["position"]))
        return doc

    def test_boundary_header_minimal(self):
        title = "A long boundary header here"
        raw = spec([[node("A")], [node("B")], [node("C")]], [edge("A", "C")])
        raw["boundaries"] = [{"label": title, "members": ["A", "B", "C"]}]
        s, layout = self.assert_sound(raw)
        e = s.edges[0]
        src, dst = e.src_point, e.dst_point
        y = layout.channels_forward[0]
        original = b.route_points(src, (e.src_escape, src[1]), (e.src_escape, y),
                                  (e.dst_escape, y), (e.dst_escape, dst[1]), dst)
        self.assertFalse(layout._route_clear(e, original))
        self.assertNotEqual(e.points, original)
        self.assertEqual(s.boundaries[0].label, title)
        doc = self.assert_geometry(s, [title])
        run = next(run for el in doc.rendered_elements if el.tag == "text"
                   for run in el.text_runs if run["text"] == title)
        self.assertTrue(any(lib.seg_hits_box(seg, run["bbox"], inset=0)
                            for seg in segments(original)))

    def test_boundary_header_directions_and_shapes(self):
        title = "A long boundary header here"
        for shape in lib.SHAPES:
            for es in ([edge("C", "A")], [edge("A", "C", bidirectional=True)],
                       [edge("A", "C", label="request"), edge("C", "A", label="reply")]):
                with self.subTest(shape=shape, edges=es):
                    raw = spec([[node("A", shape=shape)], [node("B")], [node("C")]], es)
                    raw["boundaries"] = [{"label": title, "members": ["A", "B", "C"]}]
                    s, _ = self.assert_sound(raw)
                    self.assert_geometry(s, [title])

    def test_tier_heading_and_badge_obstacles(self):
        for kind, title in (("tier", "A long tier heading here"), ("badge", "LIVE")):
            for reverse in (False, True):
                with self.subTest(kind=kind, reverse=reverse):
                    raw = spec([[node("A")], [node("B")], [node("C")]],
                               [edge("C", "A", bidirectional=True) if reverse
                                else edge("A", "C", bidirectional=True)])
                    if kind == "tier":
                        raw["tiers"][0]["label"] = title
                    else:
                        raw["tiers"][1]["nodes"][0]["badge"] = title
                    s, layout = self.assert_sound(raw)
                    doc = self.assert_geometry(s, [title])
                    run = next(run for el in doc.rendered_elements if el.tag == "text"
                               for run in el.text_runs if run["text"] == title)
                    # Cross the rendered heading/badge, staying outside all node
                    # boxes. Removing ONLY the text obstacles makes it legal.
                    y = (sum(run["bbox"][1::2]) / 2 if kind == "tier"
                         else run["bbox"][1] + 0.2)
                    e = s.edges[0]
                    src, dst = e.src_point, e.dst_point
                    crossing = b.route_points(src, (e.src_escape, src[1]), (e.src_escape, y),
                                              (e.dst_escape, y), (e.dst_escape, dst[1]), dst)
                    self.assertTrue(any(lib.seg_hits_box(seg, run["bbox"], inset=0)
                                        for seg in segments(crossing)))
                    self.assertFalse(layout._route_clear(e, crossing))
                    protected = layout.route_text_obstacles
                    try:
                        layout.route_text_obstacles = []
                        self.assertTrue(layout._route_clear(e, crossing))
                    finally:
                        layout.route_text_obstacles = protected
                    self.assertTrue(layout._route_clear(e, e.points))

    def test_route_text_checks_marker_body_not_just_shaft(self):
        s, layout = self.assert_sound(spec([[node("A")], [node("B")]],
                                          [edge("A", "B", bidirectional=True)]))
        e = s.edges[0]
        for role in ("src", "dst"):
            with self.subTest(role=role):
                x, y = getattr(e, role + "_point")
                sign = -1 if getattr(e, role + "_side") == "left" else 1
                xx = sorted((x + sign * 5, x + sign * 6))
                box = (xx[0], y + 3, xx[1], y + 3.5)
                self.assertFalse(any(b.segment_box_hit(seg, box, b.ROUTE_CLEARANCE)
                                     for seg in segments(e.points)))
                self.assertTrue(lib.boxes_overlap(b.endpoint_box(e, role), box, tol=0))
                layout.route_text_obstacles = [box]
                self.assertFalse(layout._route_clear(e, e.points))
                layout.route_text_obstacles = [(xx[0], y + 7, xx[1], y + 8)]
                self.assertTrue(layout._route_clear(e, e.points))
        layout.route_text_obstacles = []

    def test_original_sixteen(self):
        for name, raw in CASES.items():
            with self.subTest(case=name):
                if name.startswith(("11_", "12_")):
                    with self.assertRaisesRegex(b.SpecError, "has no routing|JSON boolean"):
                        b.Layout(b.Spec(copy.deepcopy(raw)))
                else:
                    self.assert_sound(raw)

    def test_default_example(self):
        raw = json.loads((ROOT / "resources/spec.example.json").read_text())
        s, layout = self.assert_sound(raw)
        self.assertEqual(len(s.edges), 13)
        html = b.build(b.Spec(raw), b.TEMPLATE.read_text())
        self.assertIn('lang="zh-CN"', html)
        self.assertNotIn("[PROJECT NAME]", html)
        self.assertLess(layout.view_w, 1800)

    def test_example_short_routes_contract(self):
        raw = json.loads((ROOT / "resources/spec.example.json").read_text())
        s, layout = self.assert_sound(raw)
        e = s.edges[7]
        self.assertEqual((e.src_id, e.dst_id, e.label, e.type),
                         ("orders", "aurora", "TLS · 连接池", "database"))
        self.assertEqual(e.src_point, (898, 190))
        self.assertEqual(e.dst_point, (1167.4, 206))
        self.assertLessEqual(l1(e.points), 300)
        self.assertLessEqual(len(e.points) - 2, 2)
        self.assertEqual((min(y for _, y in e.points), max(y for _, y in e.points)), (190, 206))
        self.assertAlmostEqual(l1(s.edges[11].points), 285.4)
        self.assertLessEqual(len(s.edges[11].points) - 2, 2)
        self.assertLessEqual(l1(s.edges[9].points), 272.483)
        self.assertLessEqual(len(s.edges[9].points) - 2, 2)
        # The crossing at x=1056 blocks the old centre, not the original route.
        layout.label_boxes.remove(e.label_box)
        old_centre = ((960 + 1167.4) / 2, 200, "middle")
        self.assertIsNone(layout._label_clear(e, old_centre))
        self.assertIsNotNone(layout._label_clear(e, e.label_at))
        self.assertTrue(layout._route_clear(e, e.points))
        layout.label_boxes.append(e.label_box)
        self.assertLess(layout.view_h, 780)
        self.assert_geometry(s, [item["label"] for item in raw["edges"] if item.get("label")])

    def test_horizontal_label_slides_to_either_end(self):
        for obstacle, left in (((280, 170, 410, 230), True),
                               ((190, 170, 320, 230), False)):
            with self.subTest(left=left):
                s = b.Spec(spec([[node("A")], [node("B")]], [edge("A", "B", label="slide")]))
                layout = b.Layout(s)
                e = s.edges[0]
                layout.label_boxes = []
                layout.text_obstacles = [obstacle]
                points = [(200, 200), (400, 200)]
                self.assertIsNone(layout._label_clear(e, (300, 194, "middle"), points))
                c, box = layout._best_label(e, points)
                self.assertLess(c[0], 280) if left else self.assertGreater(c[0], 320)
                self.assertFalse(lib.boxes_overlap(b.expand_box(box, b.LABEL_PAD), obstacle, tol=0))
                self.assertEqual(points, [(200, 200), (400, 200)])

    def test_vertical_label_slides_to_either_end(self):
        for obstacle, top in (((250, 260, 350, 410), True),
                              ((250, 190, 350, 340), False)):
            with self.subTest(top=top):
                s = b.Spec(spec([[node("A")], [node("B")]], [edge("A", "B", label="slide")]))
                layout = b.Layout(s)
                e = s.edges[0]
                layout.label_boxes = []
                layout.text_obstacles = [obstacle]
                points = [(300, 200), (300, 400)]
                for anchor, x in (("start", 307), ("end", 293)):
                    self.assertIsNone(layout._label_clear(e, (x, 304.5, anchor), points))
                c, box = layout._best_label(e, points)
                self.assertLess(c[1], 260) if top else self.assertGreater(c[1], 340)
                self.assertFalse(lib.boxes_overlap(b.expand_box(box, b.LABEL_PAD), obstacle, tol=0))

    def test_label_local_offset_before_reroute(self):
        s = b.Spec(spec([[node("A")], [node("B")]], [edge("A", "B", label="slide")]))
        layout = b.Layout(s)
        e = s.edges[0]
        layout.label_boxes = []
        layout.text_obstacles = [(190, 196, 410, 225)]
        points = [(200, 200), (400, 200)]
        self.assertIsNone(layout._label_clear(e, (300, 194, "middle"), points))
        c, _ = layout._best_label(e, points)
        self.assertEqual(c, (300, 190, "middle"))

    def test_route_cost_length_bends_and_exterior(self):
        layout = b.Layout(b.Spec(spec([[node("A")]], [])))
        layout.body_bbox = (40, 40, 500, 500)
        direct = [(100, 100), (400, 100)]
        elbow = [(100, 100), (200, 100), (200, 200), (300, 200), (300, 100), (400, 100)]
        exterior = [(x, 0 if y == 200 else y) for x, y in elbow]
        self.assertEqual(layout._route_cost(direct), (300, 300, 0))
        self.assertEqual(layout._route_cost(elbow), (500 + 4 * b.FAN_STEP, 500, 4))
        self.assertEqual(layout._route_cost(exterior)[0] - layout._route_cost(elbow)[0], 80)
        self.assertLess(layout._route_cost(direct), layout._route_cost(elbow))
        # All alternatives are monotone and equally long, so bends break ties.
        fewer = [(100, 100), (200, 100), (200, 200), (400, 200)]
        more = [(100, 100), (200, 100), (200, 150), (300, 150), (300, 200), (400, 200)]
        self.assertEqual(l1(fewer), l1(more))
        self.assertLess(layout._route_cost(fewer), layout._route_cost(more))

    def test_route_selection_is_cost_not_first_legal(self):
        class LongFirst(b.Layout):
            def _route_candidates(self, e):
                yield from sorted(super()._route_candidates(e), key=self._route_cost, reverse=True)

        for reverse in (False, True):
            s = b.Spec(spec([[node("A")], [node("B")]],
                            [edge("B", "A") if reverse else edge("A", "B")]))
            layout = LongFirst(s)
            e = s.edges[0]
            legal = [p for p in layout._route_candidates(e) if layout._route_clear(e, p)]
            self.assertGreater(layout._route_cost(legal[0]), layout._route_cost(e.points))
            self.assertEqual(layout._route_cost(e.points), min(map(layout._route_cost, legal)))
            self.assertAlmostEqual(l1(e.points), l1([e.src_point, e.dst_point]))

    def test_short_backward_fixed_ports(self):
        for shape in lib.SHAPES:
            for heads in (False, True):
                with self.subTest(shape=shape, heads=heads):
                    s, layout = self.assert_sound(spec([[node("A", shape=shape)], [node("B")]],
                        [edge("B", "A", label="reply", bidirectional=heads)]))
                    e = s.edges[0]
                    self.assertEqual(e.channel[0], "back")
                    self.assertAlmostEqual(l1(e.points), l1([e.src_point, e.dst_point]))
                    self.assertLessEqual(len(e.points) - 2, 2)
                    self.assertLess(max(y for _, y in e.points), layout.channels_backward[0])
                    # Direction and exact endpoints are hard constraints, not cost.
                    self.assertFalse(layout._route_clear(e, list(reversed(e.points))))
                    spt, dpt = e.src_point, e.dst_point
                    wrong = b.route_points(spt, (spt[0] + 12, spt[1]),
                        (spt[0] + 12, dpt[1] + 20), (dpt[0] - 12, dpt[1] + 20),
                        (dpt[0] - 12, dpt[1]), dpt)
                    self.assertFalse(layout._route_clear(e, wrong))
                    self.assert_geometry(s, ["reply"])

    def test_route_respects_margin_and_fixed_endpoints(self):
        s, layout = self.assert_sound(spec([[node("A")], [node("B")]], [edge("A", "B")]))
        e = s.edges[0]
        for y in (b.MARGIN - 1, b.MARGIN):
            pts = b.route_points(e.src_point, (e.src_escape, e.src_point[1]),
                (e.src_escape, y), (e.dst_escape, y),
                (e.dst_escape, e.dst_point[1]), e.dst_point)
            self.assertEqual(layout._route_clear(e, pts), y == b.MARGIN)
        shifted = [(x, y + 1) for x, y in e.points]
        self.assertFalse(layout._route_clear(e, shifted))

    def test_label_reroute_minimum_legal_cost(self):
        raw = copy.deepcopy(CASES["03_reciprocal_same_tier"])
        for item in raw["edges"]:
            item["label"] = "a moderately long label"
        test = self

        class Inspect(b.Layout):
            def _place_edge_labels(self):
                e = self.spec.edges[0]
                original = e.points[:]
                test.assertIsNone(self._best_label(e, original))
                legal = [p for p in self._route_candidates(e)
                         if self._route_clear(e, p) and self._best_label(e, p)]
                test.assertGreater(len(legal), 1)
                expected = min(map(self._route_cost, legal))
                super()._place_edge_labels()
                test.assertNotEqual(e.points, original)
                test.assertEqual(self._route_cost(e.points), expected)
                test.assertLessEqual(l1(e.points), l1(original) + 2 * b.FAN_STEP)

        Inspect(b.Spec(raw))
        s, _ = self.assert_sound(raw)
        self.assert_geometry(s, ["a moderately long label"])

    def test_bbox_shrinks_unused_lanes_and_transient_growth(self):
        class Inflated(b.Layout):
            def _place_edge_labels(self):
                super()._place_edge_labels()
                self.content_right += 10000
                self.content_bottom += 10000

        raw = json.loads((ROOT / "resources/spec.example.json").read_text())
        normal = b.Layout(b.Spec(copy.deepcopy(raw)))
        inflated = Inflated(b.Spec(copy.deepcopy(raw)))
        self.assertEqual((normal.view_w, normal.view_h), (inflated.view_w, inflated.view_h))
        self.assertEqual(normal.notes, inflated.notes)
        self.assertEqual(normal.legend_rows, inflated.legend_rows)
        self.assertEqual(normal.legend_bottom, inflated.legend_bottom)
        raw = spec([[node("A")], [node("B")]], [edge("B", "A")])
        s, layout = self.assert_sound(raw)
        self.assertEqual(layout.content_bottom, max(n.bottom for n in s.nodes.values()))
        self.assertLess(layout.content_bottom, layout.channels_backward[0])
        # Empty diagrams still retain frame/heading/badge extents without lanes.
        raw["edges"] = []
        raw["tiers"][1]["label"] = "Long heading beyond the last column"
        raw["tiers"][0]["nodes"][0]["badge"] = "LIVE"
        raw["boundaries"] = [{"label": "Region", "members": ["A", "B"]}]
        s, layout = self.assert_sound(raw)
        self.assertEqual(layout.content_right, max(box[2] for box in layout.body_boxes))
        self.assertEqual(layout.content_bottom, max(box[3] for box in layout.body_boxes))
        self.assert_geometry(s, ["Long heading beyond the last column", "LIVE", "Region"])

    def test_candidate_bounds_and_full_output_determinism(self):
        raw = json.loads((ROOT / "resources/spec.example.json").read_text())
        s = b.Spec(raw)
        layout = b.Layout(s)
        for e in s.edges:
            candidates = list(layout._route_candidates(e))
            self.assertLessEqual(len(candidates), 3 * len(s.edges) + 13)
            self.assertEqual(candidates, list(layout._route_candidates(e)))
            if e.label:
                labels = list(layout._label_candidates(e))
                self.assertLessEqual(len(labels), (len(e.points) - 1) * 66)
                self.assertEqual(labels, list(layout._label_candidates(e)))
        template = b.TEMPLATE.read_text()
        first = b.build(s, template)
        self.assertEqual(first, b.build(s, template))
        self.assertEqual(first, b.build(b.Spec(copy.deepcopy(raw)), template))

    def test_degree_capacity(self):
        for degree in (7, 12):
            for shape in ("rect", "stack", "cylinder", "hex"):
                for mode in ("out", "in", "both", "multiedge", "labelled"):
                    with self.subTest(degree=degree, shape=shape, mode=mode):
                        es = []
                        for i in range(degree):
                            dst = "D0" if mode == "multiedge" else f"D{i}"
                            es.append(edge(dst, "A") if mode == "in" else edge("A", dst))
                            if mode == "labelled":
                                es[-1]["label"] = f"flow {i}"
                            if mode == "both":
                                es.append(edge(dst, "A"))
                        s, layout = self.assert_sound(spec(
                            [[node("A", shape=shape)], [node(f"D{i}") for i in range(degree)]], es))
                        self.assertGreater(s.nodes["A"].h, 50)
                        self.assertGreater(layout.gap_widths[1], b.COL_GAP)

    def test_six_shapes_both_sides_and_heads(self):
        for shape in lib.SHAPES:
            for style in ("thin", "solid", "thick"):
                with self.subTest(shape=shape, style=style):
                    self.assert_sound(spec([[node("A")], [node("B", shape=shape)], [node("C")]],
                        [edge("A", "B", bidirectional=True, style=style),
                         edge("B", "C", bidirectional=True, style=style)]))
        s, _ = self.assert_sound(CASES["13_hex_midpoint"])
        self.assertGreater(abs(s.edges[0].src_point[1] - s.edges[0].dst_point[1]), 0)
        self.assertLess(abs(s.edges[0].src_point[1] - s.edges[0].dst_point[1]), 24)

    def test_fixed_shapes_report_capacity(self):
        for shape, capacity in (("actor", 2), ("cloud", 3)):
            with self.subTest(shape=shape):
                self.assert_sound(spec([[node("A", shape=shape)], [node("B")]],
                                      [edge("A", "B") for _ in range(capacity)]))
                with self.assertRaisesRegex(b.SpecError, "fixed .* contour capacity"):
                    b.Layout(b.Spec(spec([[node("A", shape=shape)], [node("B")]],
                                         [edge("A", "B") for _ in range(capacity + 1)])))

    def test_dense_and_same_column_multiedges(self):
        self.assert_sound(spec([[node(f"A{i}") for i in range(4)],
                                [node(f"B{i}") for i in range(4)]],
                               [edge(f"A{i}", f"B{j}") for i in range(4) for j in range(4)]))
        for degree in (7, 12):
            with self.subTest(degree=degree):
                self.assert_sound(spec([[node("A"), node("wide", name="W" * 29), node("B")]],
                    [edge("A", "B") if i % 2 else edge("B", "A") for i in range(degree)]))

    def test_shelf_cannot_retrace_its_escape(self):
        s = b.Spec(copy.deepcopy(CASES["03_reciprocal_same_tier"]))
        layout = b.Layout(s)
        e = s.edges[0]
        src, dst, gx = e.src_point, e.dst_point, e.src_escape
        retraced = b.route_points(src, (gx, src[1]), (gx, layout.content_bottom + 100),
                                 (gx, dst[1]), dst)
        self.assertFalse(layout._route_clear(e, retraced))

    def test_skip_backward_wide_and_labels(self):
        self.assert_sound(spec([
            [node("A"), node("W", name="W" * 29), node("B")],
            [node("X"), node("Y")], [node("C"), node("D")], [node("Z")]],
            [edge("A", "C", label="first"), edge("A", "D", label="second"),
             edge("Z", "B", label="back"), edge("D", "A", label="reply"),
             edge("A", "B", label="local"), edge("B", "A", label="return"),
             edge("B", "Z", label="report")]))

    def test_boolean_validation(self):
        for value in ("false", "true", 0, 1, None, [], {}):
            with self.subTest(value=value):
                with self.assertRaisesRegex(b.SpecError, r"edges\[0\].*bidirectional"):
                    b.Spec(spec([[node("A")], [node("B")]], [edge("A", "B", bidirectional=value)]))
        for value in (True, False):
            self.assert_sound(spec([[node("A")], [node("B")]], [edge("A", "B", bidirectional=value)]))
        with self.assertRaisesRegex(b.SpecError, "bidirectional.*dashed"):
            b.Spec(spec([[node("A")], [node("B")]], [edge("A", "B", bidirectional=True, style="dashed")]))

    def test_language_and_semantic_markers(self):
        raw = spec([[node("A")], [node("B", type="database")]], [edge("A", "B", bidirectional=True)])
        raw["language"] = "en"
        self.assert_sound(raw)
        html = b.build(b.Spec(raw), b.TEMPLATE.read_text())
        self.assertIn('lang="en"', html)
        self.assertIn('marker-end="url(#arrowhead-database)"', html)
        self.assertIn('marker-start="url(#arrowhead-start-database)"', html)
        for language in (None, "", 'en\" bad', 42):
            raw["language"] = language
            with self.assertRaisesRegex(b.SpecError, "language"):
                b.Spec(raw)

    def test_math_fallback_and_generic_markers(self):
        with self.assertRaisesRegex(b.SpecError, "over the"):
            b.Spec(spec([[node("math", name="\U0001d54e" * 28)]], []))
        raw = spec([[node("A", name="\U0001d54e" * 14)], [node("B")]],
                   [edge("A", "B", bidirectional=True)])
        self.assert_sound(raw)
        html = b.build(b.Spec(raw), b.TEMPLATE.read_text())
        self.assertIn('marker-end="url(#arrowhead-generic)"', html)
        self.assertIn('marker-start="url(#arrowhead-start-generic)"', html)

    def test_tier_label_cannot_escape_html_comment(self):
        # Parse generated HTML without executing scripts or loading resources.
        # Compare structure with a normal label, not only escaped substrings.
        class MarkupProbe(HTMLParser):
            def __init__(self, source):
                super().__init__()
                self.elements = []
                self.comments = []
                self.feed(source)
                self.close()

            def handle_starttag(self, tag, attrs):
                self.elements.append((tag, dict(attrs)))

            def handle_comment(self, data):
                self.comments.append(data)

        raw = spec([[node("A")]], [])
        raw["tiers"][0]["label"] = "Safe heading"
        template = b.TEMPLATE.read_text()
        baseline = MarkupProbe(b.build(b.Spec(raw), template))
        payloads = (
            '--><g id="comment-injection-probe"></g><!--',
            '--!><g id="comment-injection-probe"></g><!--',
            '--><script>x()</script><!--',
            '--><g onload="x()"></g><!--',
            '--></svg><div id="comment-injection-probe"></div><svg><!--',
        )
        for label in payloads:
            with self.subTest(label=label):
                raw["tiers"][0]["label"] = label
                html = b.build(b.Spec(raw), template)
                parsed = MarkupProbe(html)
                self.assertEqual([tag for tag, _ in parsed.elements],
                                 [tag for tag, _ in baseline.elements])
                self.assertEqual([attrs["id"] for _, attrs in parsed.elements if "id" in attrs],
                                 [attrs["id"] for _, attrs in baseline.elements if "id" in attrs])
                self.assertEqual([(tag, key, value) for tag, attrs in parsed.elements
                                  for key, value in attrs.items() if key.startswith("on")],
                                 [(tag, key, value) for tag, attrs in baseline.elements
                                  for key, value in attrs.items() if key.startswith("on")])
                self.assertEqual(parsed.comments, baseline.comments)
                self.assertIn('<!-- Tier nodes -->', html)
                self.assertNotIn('<!-- tier:', html)
                self.assertIn(b.esc(label), html)

    def test_tier_label_double_hyphen_is_valid_xml(self):
        for label in ("service--tier", "--", "尾部--", "研发与设计 <review> & \"delivery\"",
                      '--><g id="comment-injection-probe"></g><!--'):
            with self.subTest(label=label):
                raw = spec([[node("A")]], [])
                raw["tiers"][0]["label"] = label
                fragment = b.Renderer(b.Layout(b.Spec(raw))).render()
                # Strict XML parsing detects invalid '--' inside comments and
                # demonstrates that user markup remains literal heading text.
                svg = ET.fromstring("<svg>" + fragment + "</svg>")
                self.assertEqual(svg.find("text").text, label)
                self.assertEqual([g.get("data-node-id") for g in svg.findall("g")], ["A"])
                self.assertIsNone(svg.find(".//*[@id='comment-injection-probe']"))

    def test_tier_comments_do_not_depend_on_label(self):
        for label in ("", "正常标题", "<>&\"", "--!>"):
            with self.subTest(label=label):
                raw = spec([[node("A")], [node("B")]], [])
                raw["tiers"][0]["label"] = label
                raw["tiers"][1]["label"] = label
                html = b.build(b.Spec(raw), b.TEMPLATE.read_text())
                self.assertEqual(html.count("<!-- Tier nodes -->"), 2)
                self.assertNotIn("<!-- tier:", html)

    def test_title_is_not_empty(self):
        for title in ("", "  ", "\n\t"):
            raw = spec([[node("A")]], [])
            raw["title"] = title
            with self.assertRaisesRegex(b.SpecError, "title must not be empty"):
                b.Spec(raw)

    @unittest.skipUnless(os.environ.get("ROUTING_TEST_OUTPUT"), "set ROUTING_TEST_OUTPUT for CLI safety test")
    def test_cli_exclusive_output(self):
        requested = Path(os.environ["ROUTING_TEST_OUTPUT"])
        self.assertTrue(requested.is_absolute(), "use an absolute output directory")
        parent = requested.resolve()
        self.assertTrue(parent.is_dir())
        self.assertNotEqual(parent, ROOT.resolve(), "test output must be outside the skill")
        self.assertNotIn(ROOT.resolve(), parent.parents, "test output must be outside the skill")
        out = Path(tempfile.mkdtemp(prefix="routing-cli-", dir=parent))
        html = out / "diagram.html"
        command = [sys.executable, "-B", str(ROOT / "scripts/build_diagram.py"),
                   str(ROOT / "resources/spec.example.json"), "-o", str(html), "--quiet"]
        first = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        original = html.read_bytes()
        second = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(second.returncode, 2)
        self.assertIn("already exists", second.stderr)
        self.assertEqual(html.read_bytes(), original)
        link = out / "link.html"
        link.symlink_to(html)
        linked_command = command[:]
        linked_command[linked_command.index(str(html))] = str(link)
        third = subprocess.run(linked_command, capture_output=True, text=True)
        self.assertEqual(third.returncode, 2)
        self.assertEqual(html.read_bytes(), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
