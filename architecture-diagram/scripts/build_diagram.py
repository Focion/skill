#!/usr/bin/env python3
"""Generate a self-contained architecture diagram from a JSON spec.

    python3 scripts/build_diagram.py my-spec.json -o diagram.html --validate

The spec describes WHAT the system is (tiers, nodes, edges, boundaries); every
coordinate is derived here from the rules in references/layout.md, so a spec never
contains an x or a y. See resources/spec.schema.json for the field reference and
resources/spec.example.json for a worked input.

Only the ``layered-horizontal`` archetype is generated. The other four archetypes
in references/layout.md are hand-authored from resources/template.html, because
their geometry is not derivable from a tier list.

Standard library only, no third-party dependencies.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

from diagram_lib import (  # noqa: E402
    ARROW_STANDOFF, ARROW_STYLES, BADGE_LIFT, BADGE_PAD_X, BOUNDARY_KINDS,
    CHANNEL_GAP, CLOUD_H, CLOUD_LABEL_MAX, CLOUD_W, COL_GAP, CYL_RY,
    GROUP_LABEL_H, GROUP_PAD, HEX_SHOULDER, LEGEND_CHIP_H,
    LEGEND_CHIP_W, LEGEND_GAP, LEGEND_ROW_PITCH, LINE_H, MARGIN, MAX_W, MIN_H,
    MIN_W, NAME_BLOCK, NAME_FS, NAME_TO_SUB, PAD_X, PAD_Y, ROW_GAP, SHAPES,
    STACK_OFFSET, SUB_FS, TINY_FS, TYPES,
    boxes_overlap, ceil_even, ceil_to_10, clamp, max_chars, text_width, wrap_text,
)

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "resources" / "template.html"

CARD_COLORS = ("cyan", "emerald", "violet", "amber", "rose",
               "blue", "fuchsia", "lime", "slate")
MODIFIERS = ("dimmed", "highlight")


class SpecError(Exception):
    """A problem with the input spec, reported with the offending path."""


def fail(where: str, message: str) -> None:
    raise SpecError(f"{where}: {message}")


# ---------------------------------------------------------------------------
# Spec loading
#
# The JSON Schema is documentation and editor completion; enforcement lives here
# so the tool has no third-party dependency and can report a layout-aware error
# ("name overflows, split it like this") rather than a schema path.
# ---------------------------------------------------------------------------


def _kind_name(kind) -> str:
    """Readable name for a type or a tuple of types, for the error message."""
    if isinstance(kind, tuple):
        return " or ".join(k.__name__ for k in kind)
    return kind.__name__


def _require(obj, key, where, kind=None):
    if key not in obj:
        fail(where, f"missing required field {key!r}")
    val = obj[key]
    if kind is not None and not isinstance(val, kind):
        fail(where, f"{key!r} must be {_kind_name(kind)}, "
                    f"got {type(val).__name__}")
    return val


def _enum(val, allowed, where, key, default=None):
    if val is None:
        return default
    if val not in allowed:
        fail(where, f"{key}={val!r} is not one of {', '.join(sorted(allowed))}")
    return val


def _lines(val, where, key):
    """Accept a string or a list of strings, return a list."""
    if val is None:
        return []
    if isinstance(val, str):
        return [val]
    if isinstance(val, list) and all(isinstance(v, str) for v in val):
        return list(val)
    fail(where, f"{key} must be a string or a list of strings")


class Node:
    """One component, sized from its own text before anything is placed."""

    def __init__(self, raw: dict, tier_index: int, where: str):
        self.id = _require(raw, "id", where, str)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", self.id):
            fail(where, f"id {self.id!r} must start with a letter or _ and contain "
                        "only letters, digits, _ or -")
        where = f"{where} (node {self.id})"
        self.name = _require(raw, "name", where, str).strip()
        if not self.name:
            fail(where, "name is empty")
        self.subs = _lines(raw.get("subs"), where, "subs")
        if len(self.subs) > 3:
            fail(where, f"{len(self.subs)} subs; 3 is the maximum a 50-102px box holds. "
                        "Move the rest into a summary card.")
        self.accent = (raw.get("accent") or "").strip() or None
        self.badge = (raw.get("badge") or "").strip() or None
        self.type = _enum(raw.get("type"), TYPES, where, "type", "generic")
        self.shape = _enum(raw.get("shape"), SHAPES, where, "shape", "rect")
        self.modifier = _enum(raw.get("modifier"), MODIFIERS, where, "modifier")
        self.tier = tier_index
        self.where = where
        for extra in set(raw) - {"id", "name", "subs", "accent", "badge",
                                 "type", "shape", "modifier"}:
            fail(where, f"unknown field {extra!r}")
        # Placement, filled in by the layout pass.
        self.x = self.y = 0.0
        self.w = self.h = 0.0
        self.measure()

    # -- sizing -------------------------------------------------------------
    def measure(self) -> None:
        """Compute w/h from the text, wrapping subs and rejecting a long name."""
        if self.shape == "cloud":
            self.w, self.h = CLOUD_W, CLOUD_H
            self._check_cloud_labels()
            return

        # The name never wraps: a two-line name reads as two components.
        name_w = text_width(self.name, NAME_FS)
        budget = MAX_W - 2 * PAD_X - (24 if self.shape == "hex" else 0)
        if self.shape == "actor":
            budget = MAX_W - 2 * PAD_X   # an actor label is unboxed but still bounded
        if name_w > budget:
            fail(self.where, self._overflow_hint(name_w, budget))

        # Subs may wrap; each produced line then counts toward the height.
        wrapped: list[str] = []
        wrap_w = MAX_W - (24 if self.shape == "hex" else 0)
        for sub in self.subs:
            wrapped.extend(wrap_text(sub, SUB_FS, wrap_w))
        if len(wrapped) > 3:
            fail(self.where, f"subs wrap to {len(wrapped)} lines; shorten them so they "
                             f"fit 3 lines of {max_chars(SUB_FS)} Latin / "
                             f"{max_chars(SUB_FS, True)} full-width characters.")
        self.sub_lines = wrapped

        widest = max([name_w]
                     + [text_width(s, SUB_FS) for s in wrapped]
                     + ([text_width(self.accent, TINY_FS)] if self.accent else []))
        if self.shape == "actor":
            # An actor's figure is only 36px wide; its layout width is the label.
            self.w = max(36.0, widest)
        else:
            extra = 24 if self.shape == "hex" else 0
            self.w = clamp(MIN_W, ceil_to_10(widest + 2 * PAD_X + extra), MAX_W)

        line_count = len(wrapped) + (1 if self.accent else 0)
        if self.shape == "actor":
            # Figure is 40 tall, then the label block hangs below it.
            last = 54 + (NAME_TO_SUB + LINE_H * (line_count - 1) if line_count else 0)
            self.h = last + 4
        else:
            raw_h = NAME_BLOCK + LINE_H * line_count + 2 * PAD_Y
            self.h = ceil_even(max(MIN_H, raw_h))
        if self.shape == "cylinder":
            self.h += 2 * CYL_RY   # lid + front lip eat vertical room
        # A stack's badge rides the front plate, so the extra 8px never counts.
        self._check_badge(self.w)

    def _check_cloud_labels(self) -> None:
        """A cloud narrows sharply above y+40; 90px is the practical label limit.

        Its text baselines are y+44 / y+60 / y+75 against a fixed 70px height, so
        the third line falls 5px *below* the outline. A cloud therefore holds the
        name plus exactly one more line, whether that line is a sub or an accent.
        """
        self.sub_lines = list(self.subs)
        if len(self.subs) > 1:
            fail(self.where, f"a cloud shape holds one sub line, not {len(self.subs)}.")
        if self.subs and self.accent:
            fail(self.where, f"a cloud is {CLOUD_H}px tall and its third text baseline "
                             f"lands {CLOUD_H + 5}px down, outside the outline. Keep "
                             "either the sub or the accent, or use shape=rect.")
        labels = ([(self.name, NAME_FS)]
                  + [(s, SUB_FS) for s in self.sub_lines]
                  + ([(self.accent, TINY_FS)] if self.accent else []))
        for label, fs in labels:
            if text_width(label, fs) > CLOUD_LABEL_MAX:
                fail(self.where, f"{label!r} is {text_width(label, fs):.0f}px wide; a "
                                 f"cloud shape holds about {CLOUD_LABEL_MAX}px before "
                                 "text spills past the outline. Shorten it or use "
                                 "shape=rect.")
        self._check_badge(CLOUD_W)

    @property
    def badge_w(self) -> float:
        """Chip width for this node's badge, or 0 when it has none."""
        if not self.badge:
            return 0.0
        return ceil_to_10(text_width(self.badge, TINY_FS) + 2 * BADGE_PAD_X)

    def _check_badge(self, box_w: float) -> None:
        """A badge rides the top-right corner, so an oversized one runs off the left.

        components.md: an overflowing badge is the same hard error as an
        overflowing node. Without this the chip is emitted at a negative x.
        """
        if not self.badge:
            return
        if self.shape == "actor":
            fail(self.where, f"badge {self.badge!r} has no corner to ride on — an actor "
                             "is an open figure with its label below it. Put the text "
                             "in a sub line instead.")
        bw = self.badge_w
        room = box_w - 12          # 6px inset on the right, 6px of clear box on the left
        if bw > room:
            fits = int((room - 2 * BADGE_PAD_X) // (TINY_FS * 0.6))
            fail(self.where, f"badge {self.badge!r} needs a {bw:.0f}px chip but the "
                             f"{box_w:.0f}px box only offers {room:.0f}px. Shorten it to "
                             f"about {fits} Latin characters, or give the node a longer "
                             "name so its box widens.")

    def _overflow_hint(self, name_w: float, budget: float) -> str:
        """Reject a too-long name with a concrete split, as layout.md prescribes."""
        head = self.name
        while head and text_width(head, NAME_FS) > budget:
            head = head[:-1]
        # Break at a word boundary when there is one, so the suggestion is
        # something you would actually paste back into the spec.
        if " " in head.strip():
            head = head.rsplit(" ", 1)[0]
        tail = self.name[len(head):].strip()
        return (f"name {self.name!r} is {name_w:.0f}px at {NAME_FS}px, over the "
                f"{budget:.0f}px a {MAX_W}px box allows. Widening is not an option — "
                f'split it, e.g. name="{head.strip()}" with "{tail}" as a sub.')

    # -- geometry, valid once placed ----------------------------------------
    @property
    def right(self) -> float:
        return self.x + self.w + (STACK_OFFSET if self.shape == "stack" else 0)

    @property
    def bottom(self) -> float:
        return self.y + self.h + (STACK_OFFSET if self.shape == "stack" else 0)

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        """Preferred attachment height; actors attach to the shoulder, not air."""
        if self.shape == "actor":
            return self.y + 32
        if self.shape == "cloud":
            return self.y + 46
        return self.y + self.h / 2

    @property
    def bbox(self) -> tuple:
        return (self.x, self.y, self.right, self.bottom)

    @property
    def port_range(self) -> tuple:
        """Safe horizontal cross-sections, excluding corners and badge bands."""
        if self.shape == "cloud":
            return (self.y + 30, self.y + 62)
        if self.shape == "actor":
            return (self.y + 27, self.y + 39)
        return (self.y + 16, self.y + self.h - 16)

    def contour_x(self, side: str, y: float) -> float:
        """Intersect a horizontal attachment ray with the *visible* silhouette.

        Cloud ellipses use SVG endpoint-to-centre math, not their layout bbox.
        Actor ports deliberately use the open shoulder arc (not the label box).
        Stack ports follow the union of all three rounded plates.
        """
        local = y - self.y
        if not self.port_range[0] - 1e-7 <= y <= self.port_range[1] + 1e-7:
            fail(self.where, f"no safe {self.shape} port at y={y:g}")
        if self.shape == "cloud":
            xs = []
            for p0, p1, rx, ry in (
                    ((28, 70), (28, 26), 28, 22),
                    ((28, 26), (84, 18), 30, 26),
                    ((84, 18), (112, 70), 32, 32)):
                xs.extend(_arc_cross_section(p0, p1, rx, ry, local))
            if not xs:
                fail(self.where, "cloud contour has no horizontal intersection")
            return self.x + (min(xs) if side == "left" else max(xs))
        if self.shape == "actor":
            half = 18 * math.sqrt(max(0, 1 - ((local - 40) / 16) ** 2))
            return self.cx + (-half if side == "left" else half)
        if self.shape == "hex":
            inset = HEX_SHOULDER * abs(local - self.h / 2) / (self.h / 2)
            return self.x + inset if side == "left" else self.x + self.w - inset
        if self.shape == "stack":
            xs = []
            for off in (0, STACK_OFFSET / 2, STACK_OFFSET):
                yy = local - off
                if 0 <= yy <= self.h:
                    dy = max(6 - yy, yy - (self.h - 6), 0)
                    inset = 6 - math.sqrt(max(0, 36 - dy * dy))
                    xs.append(self.x + off + (inset if side == "left" else self.w - inset))
            return min(xs) if side == "left" else max(xs)
        # Rect and cylinder ports are inside their straight vertical side bands.
        return self.x if side == "left" else self.x + self.w

    @property
    def arrow_left(self) -> float:
        return self.contour_x("left", self.cy)

    @property
    def arrow_right(self) -> float:
        return self.contour_x("right", self.cy)


def _arc_cross_section(p0, p1, rx, ry, y):
    """Exact x intersections of a non-rotated SVG A rx ry 0 0 1 arc."""
    dx, dy = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
    scale = max(1, math.sqrt(dx * dx / (rx * rx) + dy * dy / (ry * ry)))
    rx, ry = rx * scale, ry * scale
    den = rx * rx * dy * dy + ry * ry * dx * dx
    factor = math.sqrt(max(0, (rx * rx * ry * ry - den) / den))
    cx = (p0[0] + p1[0]) / 2 + factor * rx * dy / ry
    cy = (p0[1] + p1[1]) / 2 - factor * ry * dx / rx
    u = (y - cy) / ry
    if abs(u) > 1 + 1e-9:
        return []
    start = math.atan2((p0[1] - cy) / ry, (p0[0] - cx) / rx)
    end = math.atan2((p1[1] - cy) / ry, (p1[0] - cx) / rx)
    sweep = (end - start) % (2 * math.pi)
    half = rx * math.sqrt(max(0, 1 - u * u))
    return [x for x in (cx - half, cx + half)
            if (math.atan2(u, (x - cx) / rx) - start) % (2 * math.pi) <= sweep + 1e-9]


class Edge:
    def __init__(self, raw: dict, where: str, nodes: dict):
        self.src_id = _require(raw, "from", where, str)
        self.dst_id = _require(raw, "to", where, str)
        for ref in (self.src_id, self.dst_id):
            if ref not in nodes:
                fail(where, f"unknown node id {ref!r}")
        if self.src_id == self.dst_id:
            fail(where, "an edge from a node to itself has no routing")
        for extra in set(raw) - {"from", "to", "label", "type", "style", "bidirectional"}:
            fail(where, f"unknown field {extra!r}")
        self.label = (raw.get("label") or "").strip() or None
        self.style = _enum(raw.get("style"), ARROW_STYLES, where, "style", "solid")
        self.bidirectional = raw.get("bidirectional", False)
        if not isinstance(self.bidirectional, bool):
            fail(where, "bidirectional must be true or false (a JSON boolean)")
        if self.bidirectional and self.style == "dashed":
            fail(where, "bidirectional + dashed reads as one confused line; pick one.")
        self.src = nodes[self.src_id]
        self.dst = nodes[self.dst_id]
        # Colour defaults to the TARGET's type so a chain reads as a gradient.
        self.type = _enum(raw.get("type"), TYPES, where, "type", self.dst.type)
        self.channel = None   # assigned by the routing pass
        self.fan = 0.0        # lateral offset so sibling elbows do not coincide


class Boundary:
    def __init__(self, raw: dict, where: str, nodes: dict):
        self.label = _require(raw, "label", where, str).strip()
        self.kind = _enum(raw.get("kind"), BOUNDARY_KINDS, where, "kind", "region")
        members = _require(raw, "members", where, list)
        if not members:
            fail(where, "members is empty")
        for extra in set(raw) - {"label", "kind", "members"}:
            fail(where, f"unknown field {extra!r}")
        for ref in members:
            if ref not in nodes:
                fail(where, f"unknown node id {ref!r}")
        self.member_ids = set(members)
        self.members = [nodes[m] for m in members]
        self.where = where
        self.depth = 0
        self.rect = (0.0, 0.0, 0.0, 0.0)


class Spec:
    """Validated spec: tiers of Nodes plus edges, boundaries, notes and cards."""

    def __init__(self, raw: dict):
        if not isinstance(raw, dict):
            fail("spec", "top level must be a JSON object")
        for extra in set(raw) - {"$schema", "title", "subtitle", "description",
                                 "footer", "layout", "tiers", "edges", "language",
                                 "boundaries", "notes", "legend", "cards"}:
            fail("spec", f"unknown field {extra!r}")
        self.language = raw.get("language", "zh-CN")
        if not isinstance(self.language, str) or not re.fullmatch(
                r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", self.language):
            fail("spec", "language must be a language tag such as zh-CN or en")
        self.title = _require(raw, "title", "spec", str).strip()
        if not self.title:
            fail("spec", "title must not be empty or whitespace")
        self.subtitle = (raw.get("subtitle") or "").strip()
        self.description = (raw.get("description") or "").strip() \
            or self.subtitle or self.title
        self.footer = (raw.get("footer") or "").strip()
        self.layout = _enum(raw.get("layout"), ("layered-horizontal",),
                            "spec", "layout", "layered-horizontal")
        # Explicit bool: "legend": "no" is truthy in Python, so a typo would
        # silently keep the legend it was meant to remove.
        self.show_legend = raw.get("legend", True)
        if not isinstance(self.show_legend, bool):
            fail("spec", f"legend must be true or false, got "
                         f"{type(self.show_legend).__name__}")

        tiers = _require(raw, "tiers", "spec", list)
        if not tiers:
            fail("spec", "tiers is empty")
        self.tiers: list[dict] = []
        self.nodes: dict[str, Node] = {}
        for i, tier in enumerate(tiers):
            where = f"tiers[{i}]"
            if not isinstance(tier, dict):
                fail(where, "each tier must be an object with a 'nodes' array")
            for extra in set(tier) - {"id", "label", "nodes"}:
                fail(where, f"unknown field {extra!r}")
            raw_nodes = _require(tier, "nodes", where, list)
            if not raw_nodes:
                fail(where, "nodes is empty")
            entry = {"label": (tier.get("label") or "").strip(), "nodes": []}
            for j, rn in enumerate(raw_nodes):
                if not isinstance(rn, dict):
                    fail(f"{where}.nodes[{j}]", "must be an object")
                node = Node(rn, i, f"{where}.nodes[{j}]")
                if node.id in self.nodes:
                    fail(node.where, f"duplicate node id {node.id!r}")
                self.nodes[node.id] = node
                entry["nodes"].append(node)
            self.tiers.append(entry)

        self.edges = [Edge(e, f"edges[{i}]", self.nodes)
                      for i, e in enumerate(raw.get("edges") or [])]
        self.boundaries = [Boundary(b, f"boundaries[{i}]", self.nodes)
                           for i, b in enumerate(raw.get("boundaries") or [])]
        self.notes = []
        for i, n in enumerate(raw.get("notes") or []):
            where = f"notes[{i}]"
            if not isinstance(n, dict):
                fail(where, "must be an object with a 'text' field")
            for extra in set(n) - {"text"}:
                fail(where, f"unknown field {extra!r}")
            lines = _lines(_require(n, "text", where, (str, list)), where, "text")
            if not lines:
                fail(where, "text is empty")
            if len(lines) > 4:
                fail(where, f"{len(lines)} lines; a note holds 4. Silently dropping "
                            "the rest would read as a complete annotation, so split "
                            "this into two notes or move it into a summary card.")
            self.notes.append(lines)
        self.cards = []
        for i, c in enumerate(raw.get("cards") or []):
            where = f"cards[{i}]"
            if not isinstance(c, dict):
                fail(where, "must be an object")
            for extra in set(c) - {"title", "color", "items"}:
                fail(where, f"unknown field {extra!r}")
            items = _require(c, "items", where, list)
            if not items or not all(isinstance(v, str) for v in items):
                fail(where, "items must be a non-empty array of strings")
            self.cards.append({
                "title": _require(c, "title", where, str),
                "color": _enum(c.get("color"), CARD_COLORS, where, "color", "cyan"),
                "items": items,
            })
        if len(self.cards) > 4:
            fail("spec", f"{len(self.cards)} cards; the grid holds 4.")


# ---------------------------------------------------------------------------
# Layout — references/layout.md#the-grid, #boundaries-and-nesting, #routing-channels
# ---------------------------------------------------------------------------

TIER_LABEL_H = 18       # headroom for an optional column heading at 10px
TIER_LABEL_FS = 10
GUTTER = 18             # includes the fixed 10px marker body and line clearance
LANE_LABEL_H = 18       # room above the first reserved horizontal lane
FAN_STEP = 12           # distinct tracks and ports; never clamp these together
PORT_STEP = 12
LABEL_PAD = 4
ROUTE_CLEARANCE = 2.5   # maximum stroke width, conservative centreline clearance
BOUNDARY_RX = {"region": 12, "vpc": 12, "az": 10, "sg": 8}
BOUNDARY_LABEL_FS = 10  # inset 12px into the head band, so the frame needs w + 24
# A boundary's label is drawn in the same hue as its frame stroke.
BOUNDARY_TYPE = {"region": "cloud", "vpc": "compute", "az": "generic", "sg": "security"}
NOTE_FOLD = 14
NOTE_PAD_X = 12
NOTE_LINE_H = 15


def expand_box(box, pad):
    return (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)


def segment_box_hit(seg, box, pad=0):
    """Intersection of an orthogonal segment with a padded rectangle."""
    x1, y1, x2, y2 = seg
    left, top, right, bottom = expand_box(box, pad)
    if y1 == y2:
        return top < y1 < bottom and max(min(x1, x2), left) < min(max(x1, x2), right)
    if x1 == x2:
        return left < x1 < right and max(min(y1, y2), top) < min(max(y1, y2), bottom)
    raise ValueError("routing requires orthogonal segments")


def parallel_overlap(a, b, clearance=ROUTE_CLEARANCE):
    """Reject coincident or visually merged runs, but allow perpendicular crossings."""
    if a[1] == a[3] and b[1] == b[3] and abs(a[1] - b[1]) < clearance:
        return max(min(a[0], a[2]), min(b[0], b[2])) < min(max(a[0], a[2]), max(b[0], b[2])) - 1e-7
    if a[0] == a[2] and b[0] == b[2] and abs(a[0] - b[0]) < clearance:
        return max(min(a[1], a[3]), min(b[1], b[3])) < min(max(a[1], a[3]), max(b[1], b[3])) - 1e-7
    return False


def route_points(*points):
    out = []
    for p in points:
        if out and p == out[-1]:
            continue
        if len(out) >= 2:
            a, b = out[-2:]
            # Only collapse a monotone straight run, never erase a U-turn.
            if ((a[0] == b[0] == p[0] and (b[1]-a[1]) * (p[1]-b[1]) > 0)
                    or (a[1] == b[1] == p[1] and (b[0]-a[0]) * (p[0]-b[0]) > 0)):
                out.pop()
        out.append(p)
    return out


def route_segments(points):
    return [(*a, *b) for a, b in zip(points, points[1:])]


def endpoint_box(edge, role):
    """Conservative marker footprint (fixed 10x8 geometry), or source stub."""
    x, y = getattr(edge, role + "_point")
    sign = -1 if getattr(edge, role + "_side") == "left" else 1
    head = role == "dst" or edge.bidirectional
    a, b = (x - sign * 4, x + sign * 6) if head else (x, x + sign * 10)
    half = 4 if head else 1.25
    return (min(a, b), y - half, max(a, b), y + half)


class Layout:
    """Places every element and records the content bbox."""

    def __init__(self, spec: Spec):
        self.spec = spec
        self.channels_forward: list[float] = []
        self.channels_backward: list[float] = []
        self.legend_rows: list[list] = []
        self.legend_right = 0.0
        self.notes: list[tuple] = []
        self._nest_boundaries()
        self._assign_channels()
        self._place_nodes()
        self._place_ports()
        self._place_boundaries()
        self._route_edges()
        self._place_edge_labels()
        self._recompute_content_bbox()
        self._place_notes()
        self._place_legend()

    # -- boundaries ---------------------------------------------------------
    def _nest_boundaries(self) -> None:
        """Infer nesting depth from member-set containment.

        Two frames must be nested or disjoint. Partially overlapping member sets
        cannot both be axis-aligned rects without one swallowing a non-member, so
        that is rejected here rather than drawn wrong.
        """
        bs = self.spec.boundaries
        for i, a in enumerate(bs):
            for b in bs[i + 1:]:
                shared = a.member_ids & b.member_ids
                if shared and not (a.member_ids <= b.member_ids
                                   or b.member_ids <= a.member_ids):
                    fail(b.where, f"members overlap {a.label!r} without nesting inside "
                                  f"it (shared: {', '.join(sorted(shared))}). Two frames "
                                  "must be nested or disjoint.")
                if a.member_ids == b.member_ids:
                    fail(b.where, f"identical members to {a.label!r}; the two frames "
                                  "would be drawn on top of each other.")
        for a in bs:
            a.depth = sum(1 for b in bs if b is not a and b.member_ids < a.member_ids)
        self.depth_levels = (max((b.depth for b in bs), default=-1) + 1) if bs else 0

    # -- channels -----------------------------------------------------------
    def _assign_channels(self) -> None:
        """Budget incidences (not just outgoing edges) before placing any nodes."""
        self.n_forward = self.n_backward = 0
        self.port_groups = {}
        self.gap_tracks = [[] for _ in range(len(self.spec.tiers) + 1)]
        self.gap_label_room = [0.0 for _ in self.gap_tracks]
        for i, e in enumerate(self.spec.edges):
            e.index, e.id = i, f"edge-{i}"
            e.channel = None
            e.label_at = e.label_box = None
            dt = e.dst.tier - e.src.tier
            e.src_side = "right" if dt >= 0 else "left"
            e.dst_side = "left" if dt > 0 else "right"
            if dt > 1:
                e.channel = ("fwd", self.n_forward)
                self.n_forward += 1
            elif dt < 0:
                e.channel = ("back", self.n_backward)
                self.n_backward += 1
            for role, node, side in (("src", e.src, e.src_side),
                                     ("dst", e.dst, e.dst_side)):
                self.port_groups.setdefault((node.id, side), []).append((e, role))
                gap = node.tier + (side == "right")
                token = (i, role)
                self.gap_tracks[gap].append(token)
                setattr(e, role + "_track", (gap, token))
                if e.label:
                    self.gap_label_room[gap] = max(self.gap_label_room[gap],
                                                  text_width(e.label, SUB_FS) + 16)
        # Left-column escapes stay left of right-column escapes. In particular,
        # reciprocal equal-y edges must not overlap their own two terminal stubs.
        for tracks in self.gap_tracks:
            tracks.sort(key=lambda token: (
                getattr(self.spec.edges[token[0]], token[1] + "_side") == "left",
                token[0], token[1]))
        for (node_id, side), incidences in self.port_groups.items():
            node = self.spec.nodes[node_id]
            required = (len(incidences) - 1) * PORT_STEP
            if node.shape in ("cloud", "actor"):
                lo, hi = node.port_range
                if required > hi - lo:
                    fail(node.where, f"{len(incidences)} {side} ports exceed the fixed "
                         f"{node.shape} contour capacity ({int((hi-lo)//PORT_STEP)+1}); "
                         "use rect, stack, cylinder or hex for this hub")
            else:
                node.h = max(node.h, ceil_even(required + 32))
        # Space is reserved for every vertical track AND for labels. A narrow
        # column gap is expanded, never silently saturated by clamping.
        self.gap_widths = [max(COL_GAP, 2 * GUTTER + max(0, len(ts) - 1) * FAN_STEP
                              + self.gap_label_room[g])
                           for g, ts in enumerate(self.gap_tracks)]

    def _place_ports(self) -> None:
        for (node_id, side), incidences in self.port_groups.items():
            node = self.spec.nodes[node_id]
            # Spatial order reduces crossings; the edge index breaks multiedge
            # ties without losing logical edge identity or direction.
            incidences.sort(key=lambda item: (
                (item[0].dst if item[1] == "src" else item[0].src).cy,
                item[0].index, item[1]))
            half = (len(incidences) - 1) * PORT_STEP / 2
            lo, hi = node.port_range
            centre = clamp(lo + half, node.cy, hi - half)
            for k, (e, role) in enumerate(incidences):
                y = centre - half + k * PORT_STEP
                x = node.contour_x(side, y)
                setattr(e, role + "_port", (x, y))
                setback = ARROW_STANDOFF if role == "dst" or e.bidirectional else 2
                setattr(e, role + "_point", (x + (-setback if side == "left" else setback), y))
        for e in self.spec.edges:
            for role in ("src", "dst"):
                gap, token = getattr(e, role + "_track")
                left = (self.spec.tiers[gap - 1]["x"] + self.spec.tiers[gap - 1]["w"]
                        if gap else MARGIN)
                setattr(e, role + "_escape", left + GUTTER
                        + self.gap_tracks[gap].index(token) * FAN_STEP)

    # -- nodes --------------------------------------------------------------
    def _place_nodes(self) -> None:
        spec = self.spec
        self.tier_label_h = TIER_LABEL_H if any(t["label"] for t in spec.tiers) else 0
        # Forward channels live between the tier headings and the outermost frame.
        # Each lane's label sits above its line and borrows the CHANNEL_GAP from
        # the lane above — except the topmost, which has nothing above it, so the
        # band gets one extra LANE_LABEL_H or that label lands on the headings.
        self.frames_top = (MARGIN + self.tier_label_h
                           + (LANE_LABEL_H if self.n_forward else 0)
                           + self.n_forward * CHANNEL_GAP)
        self.channels_forward = [self.frames_top - (k + 1) * CHANNEL_GAP
                                 for k in range(self.n_forward)]
        d = self.depth_levels
        top_reserve = (GROUP_PAD + 10 * (d - 1) + GROUP_LABEL_H * d) if d else 0
        left_reserve = (GROUP_PAD + 10 * (d - 1)) if d else 0
        # A corner badge rides BADGE_LIFT above its node's top edge, so a badge on
        # the first node of any column would otherwise eat into MARGIN.
        badge_pad = (BADGE_LIFT if any(t["nodes"][0].badge for t in spec.tiers)
                     else 0)
        content_top = self.frames_top + top_reserve + badge_pad

        col_x = MARGIN + left_reserve + (self.gap_widths[0] if self.gap_tracks[0] else 0)
        tier_heights = []
        for i, tier in enumerate(spec.tiers):
            nodes = tier["nodes"]
            col_w = max(n.w + (STACK_OFFSET if n.shape == "stack" else 0) for n in nodes)
            tier["x"] = col_x
            tier["w"] = col_w
            h = sum(n.h + (STACK_OFFSET if n.shape == "stack" else 0)
                    for n in nodes) + ROW_GAP * (len(nodes) - 1)
            tier_heights.append(h)
            col_x += col_w + self.gap_widths[i + 1]
        tallest = max(tier_heights)

        for tier, h in zip(spec.tiers, tier_heights):
            # Centre a shorter stack against the tallest tier; keep y integral.
            y = content_top + int((tallest - h) / 2)
            for n in tier["nodes"]:
                n.x = tier["x"]
                if n.shape == "actor":
                    # An actor's width is its label; centre the figure in the column.
                    n.x = tier["x"] + (tier["w"] - n.w) / 2
                n.y = y
                y = n.bottom + ROW_GAP
            tier["label_y"] = MARGIN + TIER_LABEL_FS

        self.content_top = content_top
        self.content_bottom = max(n.bottom for n in spec.nodes.values())
        # A tier heading is left-aligned on its column and can be wider than it;
        # the last column's heading has nothing to its right to absorb the overrun.
        self.content_right = max(
            [n.right for n in spec.nodes.values()]
            + [t["x"] + text_width(t["label"], TIER_LABEL_FS)
               for t in spec.tiers if t["label"]])
        self.channels_backward = [self.content_bottom + (k + 1) * CHANNEL_GAP
                                  for k in range(self.n_backward)]
        if self.channels_backward:
            self.content_bottom = self.channels_backward[-1]

    def _route_edges(self) -> None:
        """Orthogonal, envelope-based routes; crossings are allowed, bundling is not.

        Each gap has exclusive x tracks. Horizontal conflicts are handled with
        alternative y tracks, never by shifting a shape's endpoint off its outline.
        """
        self.routes = []
        self.label_boxes = []
        self.obstacles = [node.bbox for node in self.spec.nodes.values()]
        # Unlike node envelopes, these regions must never exempt a terminal
        # segment: headings and floating badges are visible outside node masks.
        self.route_text_obstacles = []
        for node in self.spec.nodes.values():
            if node.badge:
                self.route_text_obstacles.append((node.x, node.y - BADGE_LIFT,
                                                  node.right, node.y + 8))
        for tier in self.spec.tiers:
            if tier["label"]:
                self.route_text_obstacles.append((tier["x"], tier["label_y"] - TIER_LABEL_FS,
                    tier["x"] + text_width(tier["label"], TIER_LABEL_FS), tier["label_y"] + 2))
        for boundary in self.spec.boundaries:
            if boundary.label:
                x, y, _, _ = boundary.rect
                self.route_text_obstacles.append((x + 10, y + 2,
                    x + 14 + text_width(boundary.label, BOUNDARY_LABEL_FS), y + 17))
        self.text_obstacles = self.obstacles + self.route_text_obstacles
        # Cost is measured against stationary content, never a growing reservation
        # or an earlier detour. Pending lanes remain available until labels settle.
        self.body_boxes = self.text_obstacles + [
            (x, y, x + w, y + h) for x, y, w, h in
            (boundary.rect for boundary in self.spec.boundaries)]
        self.body_bbox = (min(box[0] for box in self.body_boxes),
                          min(box[1] for box in self.body_boxes),
                          max(box[2] for box in self.body_boxes),
                          max(box[3] for box in self.body_boxes))
        # Backward channels must clear the frames as well as their member nodes.
        if self.channels_backward:
            bottom = max([nd.bottom for nd in self.spec.nodes.values()]
                         + [b.rect[1] + b.rect[3] for b in self.spec.boundaries])
            self.channels_backward = [bottom + (k + 1) * CHANNEL_GAP
                                      for k in range(self.n_backward)]
        for e in self.spec.edges:
            # Compare every candidate's cost before testing feasibility; expensive
            # collision checks can stop once the cheapest legal route is found.
            route = next((pts for pts in sorted(self._route_candidates(e), key=self._route_cost)
                          if self._route_clear(e, pts)), None)
            if route is None:
                fail(f"edges[{e.index}]", "no non-overlapping route between the allocated "
                     "ports; reorder the tier nodes or use an intermediate component")
            e.points = route
            self.routes.append(e)
            self._include_route(e)

    def _route_cost(self, points):
        """L1 + bend and exterior penalties; perpendicular crossings cost nothing.

        Equal costs keep candidate order (the semantic lane is proposed first).
        A lane is a useful alternative, not a mandate to circle the whole graph.
        """
        length = sum(abs(x2 - x1) + abs(y2 - y1)
                     for x1, y1, x2, y2 in route_segments(points))
        bends = max(0, len(points) - 2)
        left, top, right, bottom = self.body_bbox
        exterior = (max(0, left - min(x for x, _ in points))
                    + max(0, top - min(y for _, y in points))
                    + max(0, max(x for x, _ in points) - right)
                    + max(0, max(y for _, y in points) - bottom))
        return (round(length + FAN_STEP * bends + 2 * exterior, 7),
                round(length, 7), bends)

    def _route_candidates(self, e):
        s, d = e.src_point, e.dst_point
        gx, dx = e.src_escape, e.dst_escape
        if e.channel:
            lanes = self.channels_forward if e.channel[0] == "fwd" else self.channels_backward
            yield route_points(s, (gx, s[1]), (gx, lanes[e.channel[1]]),
                               (dx, lanes[e.channel[1]]), (dx, d[1]), d)
        # Include direct/single-track alternatives even for backward channels.
        # Fixed ports and both outward tangents are still checked by _route_clear.
        # Equal-y routes collapse naturally; a tiny dy must never be flattened.
        for x in dict.fromkeys((gx, dx, (gx + dx) / 2)):
            yield route_points(s, (x, s[1]), (x, d[1]), d)
        # Adjacent routes can move their middle horizontal leg into an unused
        # y track in the gap. This also fixes equal-y stubs from separate nodes.
        if gx != dx:
            centre = (s[1] + d[1]) / 2
            for k in range(2 * len(self.spec.edges) + 6):
                y = centre + ((k + 1) // 2) * FAN_STEP * (1 if k % 2 else -1)
                if y >= self.content_top - GUTTER:
                    yield route_points(s, (gx, s[1]), (gx, y), (dx, y), (dx, d[1]), d)
            # Static body bottom avoids cascading growth from previous reroutes.
            for k in range(len(self.spec.edges) + 3):
                y = self.body_bbox[3] + (k + 1) * (CHANNEL_GAP + SUB_FS)
                yield route_points(s, (gx, s[1]), (gx, y), (dx, y), (dx, d[1]), d)

    def _route_clear(self, e, points) -> bool:
        segs = route_segments(points)
        if (not segs or points[0] != e.src_point or points[-1] != e.dst_point
                or any(x < MARGIN or y < MARGIN for x, y in points)):
            return False
        # Every first/last tangent points out of its declared contour side.
        for role, p, q in (("src", points[0], points[1]),
                           ("dst", points[-1], points[-2])):
            sign = -1 if getattr(e, role + "_side") == "left" else 1
            if p[1] != q[1] or (q[0] - p[0]) * sign <= 0:
                return False
            if any(boxes_overlap(expand_box(endpoint_box(e, role), ROUTE_CLEARANCE), box, tol=0)
                   for box in self.route_text_obstacles + self.label_boxes):
                return False
        for j, seg in enumerate(segs):
            if any(segment_box_hit(seg, box, ROUTE_CLEARANCE)
                   for box in self.route_text_obstacles):
                return False
            for nd in self.spec.nodes.values():
                if (nd is e.src and j == 0) or (nd is e.dst and j == len(segs) - 1):
                    continue
                if segment_box_hit(seg, nd.bbox, ROUTE_CLEARANCE):
                    return False
            for other in self.spec.edges:
                if other is e:
                    continue
                for role in ("src", "dst"):
                    if segment_box_hit(seg, endpoint_box(other, role), ROUTE_CLEARANCE):
                        return False
                    # Reserve future terminal runs as well as future heads. An
                    # early long run must not trap a later edge's fixed port.
                    p = getattr(other, role + "_point")
                    stub = (*p, getattr(other, role + "_escape"), p[1])
                    if parallel_overlap(seg, stub):
                        return False
            for other in self.routes:
                if other is e:
                    continue
                if any(parallel_overlap(seg, old) for old in route_segments(other.points)):
                    return False
            if any(segment_box_hit(seg, box, LABEL_PAD) for box in self.label_boxes):
                return False
        # Adjacent U-turns are overlaps too: never accept a shelf that goes
        # down and immediately back up the same escape track.
        return not any(parallel_overlap(a, b) for i, a in enumerate(segs)
                       for b in segs[i + 1:])

    def _include_route(self, e):
        self.content_right = max(self.content_right, max(x for x, _ in e.points) + 6)
        self.content_bottom = max(self.content_bottom, max(y for _, y in e.points) + 6)

    def _label_candidates(self, e, points=None):
        """Bounded sliding positions, ranked by distance, orientation and centring.

        Try both ends as well as the middle of every segment before changing the
        route. Small perpendicular offsets stay visually attached to that edge.
        """
        w = text_width(e.label, SUB_FS)
        segments = route_segments(points if points is not None else e.points)
        ranked = []

        def positions(lo, hi):
            mid = (lo + hi) / 2
            return dict.fromkeys(clamp(lo, p, hi) for p in (
                mid, lo, hi, (lo + mid) / 2, (mid + hi) / 2,
                mid - FAN_STEP, mid + FAN_STEP, mid - 2 * FAN_STEP,
                mid + 2 * FAN_STEP, lo + FAN_STEP, hi - FAN_STEP))

        for index, (x1, y1, x2, y2) in enumerate(segments):
            horizontal = y1 == y2
            length = abs(x2 - x1) if horizontal else abs(y2 - y1)
            if horizontal:
                lo, hi = min(x1, x2) + w / 2 + LABEL_PAD, max(x1, x2) - w / 2 - LABEL_PAD
            else:
                lo, hi = min(y1, y2) + SUB_FS + LABEL_PAD, max(y1, y2) - LABEL_PAD - 2
            if hi < lo:
                continue
            for p in positions(lo, hi):
                for offset in (0, LABEL_PAD, 2 * LABEL_PAD):
                    candidates = ((p, y1 - 6 - offset, "middle"),
                                  (p, y1 + SUB_FS + 6 + offset, "middle")) if horizontal else (
                                  (x1 + 7 + offset, p, "start"),
                                  (x1 - 7 - offset, p, "end"))
                    for side, candidate in enumerate(candidates):
                        score = (offset, not horizontal, -length,
                                 abs(p - (lo + hi) / 2), index, side, p)
                        ranked.append((score, candidate))
        for _, candidate in sorted(ranked):
            yield candidate

    def _label_clear(self, e, candidate, points=None):
        x, y, anchor = candidate
        w = text_width(e.label, SUB_FS)
        left = x if anchor == "start" else x - w if anchor == "end" else x - w / 2
        box = (left, y - SUB_FS, left + w, y + 2)
        if left < MARGIN or box[1] < MARGIN:
            return None
        if any(boxes_overlap(expand_box(box, LABEL_PAD), b, tol=0)
               for b in self.text_obstacles + self.label_boxes):
            return None
        for other in self.spec.edges:
            pts = points if other is e and points is not None else other.points
            if any(segment_box_hit(s, box, LABEL_PAD) for s in route_segments(pts)):
                return None
            if any(boxes_overlap(expand_box(box, LABEL_PAD), endpoint_box(other, role), tol=0)
                   for role in ("src", "dst")):
                return None
        return box

    def _best_label(self, e, points):
        return next(((c, box) for c in self._label_candidates(e, points)
                     if (box := self._label_clear(e, c, points)) is not None), None)

    def _place_edge_labels(self) -> None:
        """Slide on the original route first; reroute by cost with ALL edges visible."""
        for e in self.spec.edges:
            if not e.label:
                continue
            chosen = self._best_label(e, e.points)
            if chosen is None:
                # Sort the entire bounded candidate set, including semantic lanes
                # and exterior shelves. First labelled success is thus the minimum
                # geometry cost, NOT whichever long shelf happens to clear first.
                seen = {tuple(e.points)}
                for pts in sorted(self._route_candidates(e), key=self._route_cost):
                    if tuple(pts) in seen:
                        continue
                    seen.add(tuple(pts))
                    if not self._route_clear(e, pts):
                        continue
                    chosen = self._best_label(e, pts)
                    if chosen is not None:
                        e.points = pts
                        self._include_route(e)
                        break
            if chosen is None:
                fail(f"edges[{e.index}]", f"label {e.label!r} has no collision-free position; "
                     "shorten it, reorder tier nodes, or move the detail into a note")
            e.label_at, e.label_box = chosen
            self.label_boxes.append(e.label_box)
            self.content_right = max(self.content_right, e.label_box[2] + LABEL_PAD)
            self.content_bottom = max(self.content_bottom, e.label_box[3] + LABEL_PAD)

    def _recompute_content_bbox(self):
        """Discard unused lane/detour reservations only after all labels are locked.

        Notes and legend are placed afterwards against this actual body extent.
        Keep node silhouettes, frames, headings/badges, strokes, markers and labels.
        """
        boxes = list(self.body_boxes)
        for e in self.spec.edges:
            boxes.extend((x - 6, y - 6, x + 6, y + 6) for x, y in e.points)
            boxes.extend(endpoint_box(e, role) for role in ("src", "dst"))
            if e.label_box:
                boxes.append(expand_box(e.label_box, LABEL_PAD))
        self.content_right = max(box[2] for box in boxes)
        self.content_bottom = max(box[3] for box in boxes)

    def _place_boundaries(self) -> None:
        """Derive each frame from its member bbox, then reject a stray enclosure."""
        member_w = {}
        for b in self.spec.boundaries:
            mx = min(n.x for n in b.members)
            my = min(n.y for n in b.members)
            mr = max(n.right for n in b.members)
            mb = max(n.bottom for n in b.members)
            inset = GROUP_PAD + 10 * b.depth
            head = GROUP_LABEL_H * (b.depth + 1)
            x, y = mx - inset, my - inset - head
            w, h = (mr - mx) + 2 * inset, (mb - my) + 2 * inset + head
            # The label is drawn inset 12px into the head band. A label wider than
            # the members widens the frame rather than hanging out of it, which is
            # what a 10px label at 340px would otherwise do.
            member_w[id(b)] = w
            if b.label:
                w = max(w, text_width(b.label, BOUNDARY_LABEL_FS) + 24)
            b.rect = (x, y, w, h)

        # A label only ever widens a frame, so a widened inner frame has to take
        # its ancestors with it — otherwise the child pokes out through the right
        # edge of the very frame that is supposed to contain it. Nesting is already
        # known to be strict (members nested or disjoint), so a proper subset of
        # members is exactly an ancestor relationship.
        for outer in self.spec.boundaries:
            for inner in self.spec.boundaries:
                if inner is outer or not inner.member_ids < outer.member_ids:
                    continue
                x, y, w, h = outer.rect
                want = inner.rect[0] + inner.rect[2] + 10 - x   # 10 = per-level inset
                if want > w:
                    outer.rect = (x, y, want, h)

        for b in self.spec.boundaries:
            x, y, w, h = b.rect
            for n in self.spec.nodes.values():
                if n.id in b.member_ids:
                    continue
                # A frame is an axis-aligned rect: anything inside it reads as a
                # member. Overlapping a node's box is just as wrong as containing it.
                if (n.x < x + w and x < n.right and n.y < y + h and y < n.bottom):
                    base = member_w[id(b)]
                    if w > base + 0.01:
                        room = int((base - 24) // (BOUNDARY_LABEL_FS * 0.6))
                        fail(b.where, f"the frame widened from {base:.0f}px to {w:.0f}px "
                                      f"to hold a {BOUNDARY_LABEL_FS}px boundary label, "
                                      f"and now covers {n.id!r}, which is not a member. "
                                      f"Shorten the label on this frame (or on one nested "
                                      f"inside it) to about {room} Latin characters, or "
                                      "move the detail into a note.")
                    fail(b.where, f"the frame derived from these members would also "
                                  f"cover {n.id!r}, which is not a member. Reorder the "
                                  "tiers (or the nodes within a tier) so the members "
                                  "are adjacent.")
            if x < MARGIN or y < MARGIN:
                # layout.md: shift ALL content, never the frame. Nothing here can
                # produce it (top_reserve/left_reserve are sized for max depth), so
                # a hit means the reserve maths and the nesting disagree.
                fail(b.where, f"frame at ({x:.0f}, {y:.0f}) escapes the {MARGIN}px "
                              "margin — internal error in the reserve calculation.")
            self.content_bottom = max(self.content_bottom, y + h)
            self.content_right = max(self.content_right, x + w)

    def _place_notes(self) -> None:
        """Notes sit below the diagram body, left to right, wrapping to more rows.

        Same reasoning as the legend: five notes in one row drag the viewBox out to
        1500px for a 150px diagram and the whole thing renders as a letterbox
        strip. The row width follows the content, never the note count. A single
        note wider than the row still gets its own row and widens the diagram —
        that is the note's own fault, and visible.
        """
        if not self.spec.notes:
            return
        avail = max(self.content_right - MARGIN, 600)
        x = MARGIN
        top = self.content_bottom + LEGEND_GAP
        row_h = 0.0
        right = float(MARGIN)
        for lines in self.spec.notes:
            w = ceil_to_10(max(text_width(s, SUB_FS) for s in lines)
                           + 2 * NOTE_PAD_X + NOTE_FOLD)
            h = NOTE_LINE_H * len(lines) + 2 * PAD_Y
            if x > MARGIN and x + w > MARGIN + avail:
                x = MARGIN
                top += row_h + LEGEND_GAP     # same 20px a block gets below it
                row_h = 0.0
            self.notes.append((x, top, w, h, lines))
            row_h = max(row_h, h)
            x += w + ROW_GAP
            right = max(right, x - ROW_GAP)
        self.content_bottom = top + row_h
        self.content_right = max(self.content_right, right)

    def _place_legend(self) -> None:
        """Build the legend from what the diagram actually uses, then place it.

        Wraps to as many rows as the content width allows, because a legend wider
        than the diagram is what pushes the viewBox out of proportion.
        """
        spec = self.spec
        if not spec.show_legend:
            self.legend_bottom = self.content_bottom
            return
        entries: list[tuple[str, str, str]] = []   # (kind, class, label)
        seen = set()

        def add(kind: str, cls: str, label: str) -> None:
            if (kind, cls) not in seen:
                seen.add((kind, cls))
                entries.append((kind, cls, label))

        for tier in spec.tiers:
            for n in tier["nodes"]:
                add("node", n.type, TYPE_LABELS[n.type])
        for e in spec.edges:
            # Keyed on the STYLE alone: the type hue is already explained by the
            # node chips, so one entry per dash pattern, not one per type+pattern.
            if e.style != "solid":
                add("arrow", e.style, STYLE_LABELS[e.style])
        for b in spec.boundaries:
            add("boundary", b.kind, KIND_LABELS[b.kind])
        for n in spec.nodes.values():
            if n.modifier:
                add("mod", n.modifier, MODIFIER_LABELS[n.modifier])

        avail = max(self.content_right - MARGIN, 600)
        rows: list[list] = [[]]
        x = MARGIN
        for kind, cls, label in entries:
            w = LEGEND_CHIP_W + 6 + int(text_width(label, TINY_FS) + 0.999) + 18
            if rows[-1] and x - MARGIN + w > avail:
                rows.append([])
                x = MARGIN
            rows[-1].append((x, kind, cls, label))
            x += w
            # A narrow diagram with many types has a legend wider than its own
            # content, and the viewBox has to cover the legend or the last chips
            # are clipped away. Track the real extent, minus the trailing 18px
            # inter-chip gap the last entry does not need.
            self.legend_right = max(self.legend_right, x - 18)
        top = self.content_bottom + LEGEND_GAP
        self.legend_rows = [(top + r * LEGEND_ROW_PITCH, row)
                            for r, row in enumerate(rows) if row]
        self.legend_bottom = (top + max(len(rows) - 1, 0) * LEGEND_ROW_PITCH
                              + LEGEND_CHIP_H) if rows[0] else self.content_bottom

    # -- viewBox ------------------------------------------------------------
    @property
    def view_w(self) -> int:
        return int(ceil_to_10(max(self.content_right, self.legend_right) + MARGIN))

    @property
    def view_h(self) -> int:
        return int(ceil_to_10(max(self.content_bottom, self.legend_bottom) + MARGIN))


TYPE_LABELS = {
    "frontend": "Frontend", "backend": "Backend / Service", "database": "Datastore",
    "cache": "Cache", "compute": "Compute", "cloud": "Cloud / External",
    "bus": "Queue / Bus", "security": "Security / Auth",
    "observability": "Observability", "generic": "Generic",
}
STYLE_LABELS = {"dashed": "Async / auth", "dotted": "Optional",
                "thick": "Primary path", "thin": "Secondary"}
KIND_LABELS = {"region": "Region", "vpc": "VPC", "az": "Availability Zone",
               "sg": "Security Group"}
MODIFIER_LABELS = {"dimmed": "Deprecated / planned", "highlight": "In focus"}


# ---------------------------------------------------------------------------
# SVG emission
#
# Painting order matters: SVG has no z-index, so the sequence below IS the
# stacking order (references/layout.md#painting-order-and-masks):
#   boundaries (outermost first) -> tier labels -> arrows -> mask+node pairs
#   -> node text -> badges -> notes -> legend
# Arrows are collision-checked before emission. Opaque masks remain paired with
# boxed nodes for compositing; they are never a substitute for obstacle routing.
# ---------------------------------------------------------------------------

def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace('"', "&quot;"))


def n(v: float) -> str:
    """Shortest exact decimal: 40.0 -> '40', 40.5 -> '40.5'."""
    return f"{v:g}"


class Renderer:
    def __init__(self, layout: Layout):
        self.L = layout
        self.spec = layout.spec
        self.out: list[str] = []

    def emit(self, indent: int, line: str) -> None:
        self.out.append(" " * indent + line)

    def blank(self) -> None:
        self.out.append("")

    def render(self) -> str:
        self.boundaries()
        self.tier_labels()
        self.arrows()
        self.nodes()
        self.notes()
        self.legend()
        return "\n".join(self.out)

    # -- boundaries ---------------------------------------------------------
    def boundaries(self) -> None:
        bs = sorted(self.spec.boundaries, key=lambda b: -b.depth)
        if not bs:
            return
        self.emit(8, "<!-- Boundaries, outermost first: a later sibling would "
                     "otherwise paint over the frames inside it. -->")
        for b in bs:
            x, y, w, h = b.rect
            self.emit(8, f'<rect class="boundary {b.kind}" x="{n(x)}" y="{n(y)}" '
                         f'width="{n(w)}" height="{n(h)}" rx="{BOUNDARY_RX[b.kind]}"/>')
            self.emit(8, f'<text class="t-{BOUNDARY_TYPE[b.kind]}" x="{n(x + 12)}" '
                         f'y="{n(y + 14)}" font-size="{BOUNDARY_LABEL_FS}" '
                         f'font-weight="600">'
                         f'{esc(b.label)}</text>')
        self.blank()

    def tier_labels(self) -> None:
        if not self.L.tier_label_h:
            return
        self.emit(8, "<!-- Tier headings -->")
        for tier in self.spec.tiers:
            if not tier["label"]:
                continue
            self.emit(8, f'<text class="t-sub" x="{n(tier["x"])}" '
                         f'y="{n(tier["label_y"])}" font-size="{TIER_LABEL_FS}">'
                         f'{esc(tier["label"])}</text>')
        self.blank()

    # -- nodes --------------------------------------------------------------
    def nodes(self) -> None:
        for tier in self.spec.tiers:
            # Labels belong only in escaped SVG text, never HTML comments.
            self.emit(8, '<!-- Tier nodes -->')
            for node in tier["nodes"]:
                self.node(node)
            self.blank()

    def node(self, d: Node) -> None:
        self.emit(8, f'<g data-node-id="{esc(d.id)}" data-shape="{d.shape}">')
        cls = f"node {d.type}" + (f" {d.modifier}" if d.modifier else "")
        x, y, w, h = d.x, d.y, d.w, d.h
        if d.shape == "rect":
            self.mask(f'<rect class="mask" x="{n(x)}" y="{n(y)}" width="{n(w)}" '
                      f'height="{n(h)}" rx="6"/>')
            self.emit(8, f'<rect class="{cls}" x="{n(x)}" y="{n(y)}" width="{n(w)}" '
                         f'height="{n(h)}" rx="6"/>')
        elif d.shape == "stack":
            self.mask(f'<rect class="mask" x="{n(x)}" y="{n(y)}" '
                      f'width="{n(w + STACK_OFFSET)}" '
                      f'height="{n(h + STACK_OFFSET)}" rx="6"/>')
            for off in (STACK_OFFSET, STACK_OFFSET / 2):
                self.emit(8, f'<rect class="{cls} ghost" x="{n(x + off)}" '
                             f'y="{n(y + off)}" width="{n(w)}" height="{n(h)}" rx="6"/>')
            self.emit(8, f'<rect class="{cls}" x="{n(x)}" y="{n(y)}" width="{n(w)}" '
                         f'height="{n(h)}" rx="6"/>')
        elif d.shape == "cylinder":
            ry, rx = CYL_RY, w / 2
            body = (f"M {n(x)} {n(y + ry)} V {n(y + h - ry)} "
                    f"A {n(rx)} {ry} 0 0 0 {n(x + w)} {n(y + h - ry)} "
                    f"V {n(y + ry)} A {n(rx)} {ry} 0 0 0 {n(x)} {n(y + ry)} Z")
            self.mask(f'<path class="mask" d="{body}"/>')
            self.emit(8, f'<path class="{cls}" d="{body}"/>')
            # Lid last: it is stroke-only, so the body fill would cover it.
            self.emit(8, f'<path class="node-lid {d.type}" d="M {n(x)} {n(y + ry)} '
                         f'A {n(rx)} {ry} 0 0 0 {n(x + w)} {n(y + ry)}"/>')
        elif d.shape == "hex":
            s, my = HEX_SHOULDER, y + h / 2
            pts = (f"{n(x + s)},{n(y)} {n(x + w - s)},{n(y)} {n(x + w)},{n(my)} "
                   f"{n(x + w - s)},{n(y + h)} {n(x + s)},{n(y + h)} {n(x)},{n(my)}")
            self.mask(f'<polygon class="mask" points="{pts}"/>')
            self.emit(8, f'<polygon class="{cls}" points="{pts}"/>')
        elif d.shape == "cloud":
            path = (f"M {n(x + 28)} {n(y + 70)} A 28 22 0 0 1 {n(x + 28)} {n(y + 26)} "
                    f"A 30 26 0 0 1 {n(x + 84)} {n(y + 18)} "
                    f"A 32 32 0 0 1 {n(x + 112)} {n(y + 70)} Z")
            self.mask(f'<path class="mask" d="{path}"/>')
            self.emit(8, f'<path class="{cls}" d="{path}"/>')
        elif d.shape == "actor":
            # Never masked: the shoulder arc is open, so a mask rect would show
            # as a box behind the figure.
            cx = d.cx
            self.emit(8, f'<circle class="{cls}" cx="{n(cx)}" cy="{n(y + 10)}" r="8"/>')
            self.emit(8, f'<path class="{cls}" d="M {n(cx - 18)} {n(y + 40)} '
                         f'A 18 16 0 0 1 {n(cx + 18)} {n(y + 40)}"/>')
        self.node_text(d)
        self.badge(d)
        self.emit(8, '</g>')

    def mask(self, markup: str) -> None:
        self.emit(8, markup)

    def node_text(self, d: Node) -> None:
        """Name, subs and accent, at the baselines in components.md's text table."""
        cx = d.cx
        if d.shape == "actor":
            base = d.y + 54
        elif d.shape == "cloud":
            base = d.y + 44
        elif d.shape == "cylinder":
            base = d.y + 20 + CYL_RY
        else:
            base = d.y + 20
        self.emit(8, f'<text class="t" x="{n(cx)}" y="{n(base)}" '
                     f'font-size="{NAME_FS}" text-anchor="middle">{esc(d.name)}</text>')
        yy = base
        for i, line in enumerate(d.sub_lines):
            yy += NAME_TO_SUB if i == 0 else LINE_H
            self.emit(8, f'<text class="t-sub" x="{n(cx)}" y="{n(yy)}" '
                         f'font-size="{SUB_FS}" text-anchor="middle">'
                         f'{esc(line)}</text>')
        if d.accent:
            yy += NAME_TO_SUB if not d.sub_lines else LINE_H
            self.emit(8, f'<text class="t-{d.type}" x="{n(cx)}" y="{n(yy)}" '
                         f'font-size="{TINY_FS}" text-anchor="middle">'
                         f'{esc(d.accent)}</text>')

    def badge(self, d: Node) -> None:
        if not d.badge or d.shape == "actor":
            return
        bw = ceil_to_10(text_width(d.badge, TINY_FS) + 16)
        bx = d.right - bw - 6 if d.shape != "stack" else d.x + d.w - bw - 6
        by = d.y - 8
        self.emit(8, f'<rect class="badge" x="{n(bx)}" y="{n(by)}" width="{n(bw)}" '
                     f'height="16" rx="8"/>')
        self.emit(8, f'<text class="t-badge" x="{n(bx + bw / 2)}" y="{n(by + 11)}" '
                     f'font-size="{TINY_FS}" text-anchor="middle">'
                     f'{esc(d.badge)}</text>')

    # -- notes and legend ---------------------------------------------------
    def notes(self) -> None:
        if not self.L.notes:
            return
        self.emit(8, "<!-- Notes -->")
        for x, y, w, h, lines in self.L.notes:
            self.emit(8, f'<path class="note" d="M {n(x)} {n(y)} '
                         f'H {n(x + w - NOTE_FOLD)} L {n(x + w)} {n(y + NOTE_FOLD)} '
                         f'V {n(y + h)} H {n(x)} Z"/>')
            self.emit(8, f'<path class="note-fold" d="M {n(x + w - NOTE_FOLD)} {n(y)} '
                         f'V {n(y + NOTE_FOLD)} H {n(x + w)}"/>')
            for i, line in enumerate(lines):
                self.emit(8, f'<text class="t-sub" x="{n(x + NOTE_PAD_X)}" '
                             f'y="{n(y + PAD_Y + 10 + i * NOTE_LINE_H)}" '
                             f'font-size="{SUB_FS}">{esc(line)}</text>')
        self.blank()

    def legend(self) -> None:
        if not self.L.legend_rows:
            return
        self.emit(8, "<!-- Legend: below every other element, one entry per type, "
                     "line style, boundary kind and modifier actually used. -->")
        for y, row in self.L.legend_rows:
            for x, kind, cls, label in row:
                if kind == "node":
                    self.emit(8, f'<rect class="node {cls} legend-swatch" x="{n(x)}" '
                                 f'y="{n(y)}" width="{LEGEND_CHIP_W}" '
                                 f'height="{LEGEND_CHIP_H}" rx="2"/>')
                elif kind == "boundary":
                    self.emit(8, f'<rect class="boundary {cls} legend-swatch" '
                                 f'x="{n(x)}" y="{n(y)}" width="{LEGEND_CHIP_W}" '
                                 f'height="{LEGEND_CHIP_H}" rx="2"/>')
                elif kind == "mod":
                    self.emit(8, f'<rect class="node generic {cls} legend-swatch" '
                                 f'x="{n(x)}" y="{n(y)}" width="{LEGEND_CHIP_W}" '
                                 f'height="{LEGEND_CHIP_H}" rx="2"/>')
                else:   # arrow
                    my = n(y + LEGEND_CHIP_H / 2)
                    self.emit(8, f'<line class="arrow {cls} legend-swatch" '
                                 f'x1="{n(x)}" y1="{my}" '
                                 f'x2="{n(x + LEGEND_CHIP_W)}" y2="{my}"/>')
                self.emit(8, f'<text class="t-sub" x="{n(x + LEGEND_CHIP_W + 6)}" '
                             f'y="{n(y + LEGEND_CHIP_H - 2)}" font-size="{TINY_FS}">'
                             f'{esc(label)}</text>')

    # -- arrows -------------------------------------------------------------
    def arrows(self) -> None:
        """Emit the already-checked routes before painting node shapes."""
        if not self.spec.edges:
            return
        self.emit(8, "<!-- Arrows: ports and routes are collision-checked before "
                     "node masks are painted. -->")
        for e in self.spec.edges:
            self.arrow(e)
        self.blank()

    def arrow(self, e: Edge) -> None:
        cls = "arrow " + e.type + (f" {e.style}" if e.style != "solid" else "")
        suffix = "-" + e.type
        marker = f' marker-end="url(#arrowhead{suffix})"'
        if e.bidirectional:
            marker += f' marker-start="url(#arrowhead-start{suffix})"'
        points = e.points
        attrs = f'M {n(points[0][0])} {n(points[0][1])}'
        for x, y in points[1:]:
            attrs += f' L {n(x)} {n(y)}'
        self.emit(8, f'<path class="{cls}" d="{attrs}"{marker} '
                     f'data-edge-id="{e.id}" data-from="{esc(e.src_id)}" '
                     f'data-to="{esc(e.dst_id)}" '
                     f'data-bidirectional="{str(e.bidirectional).lower()}"/>')
        if e.label:
            lx, ly, anchor = e.label_at
            self.emit(8, f'<text class="t-sub" x="{n(lx)}" y="{n(ly)}" '
                         f'font-size="{SUB_FS}" text-anchor="{anchor}" '
                         f'data-edge-label="{e.id}">{esc(e.label)}</text>')


# ---------------------------------------------------------------------------
# Template substitution
#
# The template is the single source of truth for the theme tokens, <defs> and
# export scripts. The generator only replaces the two GEN: regions, the viewBox,
# the accessible name/description and the header/footer placeholders — so a fix
# to the shared chrome benefits both the generated and the hand-authored path.
# ---------------------------------------------------------------------------

def render_cards(spec: Spec) -> str:
    if not spec.cards:
        return "    <!-- no cards -->"
    out = ['    <div class="cards">']
    for card in spec.cards:
        out.append('      <div class="card">')
        out.append('        <div class="card-header">')
        out.append(f'          <div class="card-dot {card["color"]}"></div>')
        out.append(f'          <h3>{esc(card["title"])}</h3>')
        out.append('        </div>')
        out.append('        <ul>')
        for item in card["items"]:
            out.append(f'          <li>• {esc(item)}</li>')
        out.append('        </ul>')
        out.append('      </div>')
    out.append('    </div>')
    return "\n".join(out)


def _replace_region(src: str, start_marker: str, end_marker: str, body: str,
                    label: str) -> str:
    """Swap the text between two HTML comment markers.

    The start marker's comment spans several lines of prose, so the region begins
    after the '-->' that closes it — not after the marker text itself.
    """
    i = src.find(start_marker)
    if i < 0:
        raise SpecError(f"template is missing the {label} start marker")
    open_end = src.find("-->", i)
    j = src.find(end_marker)
    if open_end < 0 or j < 0 or j < open_end:
        raise SpecError(f"template's {label} markers are malformed")
    return src[:open_end + 3] + "\n" + body + "\n        " + src[j:]


def build(spec: Spec, template: str) -> str:
    layout = Layout(spec)
    body = Renderer(layout).render()
    html = _replace_region(template, "<!-- GEN:CONTENT-START",
                           "<!-- GEN:CONTENT-END -->", body, "GEN:CONTENT")
    html = _replace_region(html, "<!-- GEN:CARDS-START",
                           "<!-- GEN:CARDS-END -->", render_cards(spec), "GEN:CARDS")
    def html_language(match):
        tag = re.sub(r'''\s+lang\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)''',
                     "", match.group(0), flags=re.I)
        return tag[:-1] + f' lang="{esc(spec.language)}">'

    html = re.sub(r'<html\b[^>]*>', html_language, html, count=1, flags=re.I)

    # viewBox: the content bbox plus MARGIN, never the template's placeholder.
    html = re.sub(r'(<svg id="arch-svg" viewBox=")[^"]*"',
                  rf'\g<1>0 0 {layout.view_w} {layout.view_h}"', html, count=1)

    title, sub = esc(spec.title), esc(spec.subtitle)
    html = html.replace("<title>[PROJECT NAME] Architecture Diagram</title>",
                        f"<title>{title} — Architecture Diagram</title>")
    html = html.replace("<h1>[PROJECT NAME] Architecture</h1>", f"<h1>{title}</h1>")
    html = html.replace('<p class="subtitle">[Subtitle description]</p>',
                        f'<p class="subtitle">{sub}</p>')
    html = html.replace('<title id="svg-title">[DIAGRAM TITLE]</title>',
                        f'<title id="svg-title">{title}</title>')
    html = html.replace('<desc id="svg-desc">[DIAGRAM DESCRIPTION]</desc>',
                        f'<desc id="svg-desc">{esc(spec.description)}</desc>')
    html = html.replace("[Project Name] • [Additional metadata]",
                        esc(spec.footer or spec.title))
    left = [p for p in ("[PROJECT NAME]", "[Subtitle description]",
                        "[DIAGRAM TITLE]", "[DIAGRAM DESCRIPTION]",
                        "[Project Name]", "[Additional metadata]") if p in html]
    if left:
        raise SpecError("template placeholders survived substitution: "
                        + ", ".join(left) + " — the template's markup changed "
                        "and build_diagram.py's replacements need updating.")
    return html


def summarize(spec: Spec, layout: Layout) -> str:
    lanes = []
    if layout.n_forward:
        lanes.append(f"{layout.n_forward} forward")
    if layout.n_backward:
        lanes.append(f"{layout.n_backward} backward")
    return (f"{len(spec.nodes)} nodes in {len(spec.tiers)} tiers, "
            f"{len(spec.edges)} edges, {len(spec.boundaries)} boundaries "
            f"({layout.depth_levels} nesting level"
            f"{'' if layout.depth_levels == 1 else 's'}), "
            f"{len(spec.cards)} cards, "
            f"channels: {', '.join(lanes) or 'none'}, "
            f"viewBox 0 0 {layout.view_w} {layout.view_h}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="build_diagram.py",
        description="Generate a self-contained architecture diagram from a JSON spec.")
    ap.add_argument("spec", help="path to the JSON spec (see resources/spec.schema.json)")
    ap.add_argument("-o", "--output", default="diagram.html",
                    help="output HTML path (default: diagram.html)")
    ap.add_argument("--validate", action="store_true",
                    help="run scripts/validate.py on the result and fail on any error")
    ap.add_argument("--strict", action="store_true",
                    help="treat warnings as errors too (implies --validate)")
    ap.add_argument("--template", default=str(TEMPLATE),
                    help=f"template to substitute into (default: {TEMPLATE})")
    ap.add_argument("--quiet", action="store_true", help="only report problems")
    args = ap.parse_args(argv)
    # Asking for strict warnings with no checks to be strict about is never what
    # anyone meant, and silently doing nothing is the worst reading of it.
    if args.strict:
        args.validate = True

    try:
        raw = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: no such spec file: {args.spec}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: cannot read {args.spec}: {exc.strerror}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        print(f"error: {args.spec} is not valid JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(raw, dict):
        print(f"error: {args.spec} must contain a JSON object, got "
              f"{type(raw).__name__}", file=sys.stderr)
        return 2
    raw.pop("$schema", None)

    try:
        template = Path(args.template).read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"error: no such template: {args.template}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: cannot read template {args.template}: {exc.strerror}",
              file=sys.stderr)
        return 2

    try:
        spec = Spec(raw)
        html = build(spec, template)
    except SpecError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    out = Path(args.output)
    try:
        with out.open("x", encoding="utf-8") as stream:
            stream.write(html)
    except FileExistsError:
        print(f"error: output already exists; choose a new path: {out}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: cannot write {out}: {exc.strerror}", file=sys.stderr)
        return 2
    if not args.quiet:
        print(f"wrote {out}: {summarize(spec, Layout(spec))}")

    if args.validate:
        import validate as v
        rc = v.main([str(out)] + (["--strict"] if args.strict else [])
                    + (["--quiet"] if args.quiet else []))
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
