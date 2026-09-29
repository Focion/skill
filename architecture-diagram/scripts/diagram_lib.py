"""Shared primitives for the architecture-diagram skill.

Both ``build_diagram.py`` and ``validate.py`` import this module so the text-width
formula documented in ``references/layout.md#text-width`` has exactly one
implementation. If the two ever disagree, the generator emits boxes the validator
then rejects — so keep this the only copy.

Standard library only, no third-party dependencies.
"""

from __future__ import annotations

import math
import re
import unicodedata
from html.parser import HTMLParser

# ---------------------------------------------------------------------------
# Grid constants — references/layout.md#the-grid
# ---------------------------------------------------------------------------
MARGIN = 40          # content bbox -> viewBox edge, all four sides
COL_GAP = 60         # between adjacent tier columns
ROW_GAP = 40         # between stacked siblings in one column
PAD_X = 14           # horizontal text inset inside a node
PAD_Y = 10           # vertical text inset inside a node
MIN_W = 110          # floor on node width
MAX_W = 220          # ceiling on node width; exceeding it means wrap, not widen
MIN_H = 50           # floor on node height
NAME_FS = 11         # .t name line
SUB_FS = 9           # .t-sub sublabel lines
TINY_FS = 8          # .t-<type> accent line, badges, legend text
LINE_H = 15          # baseline-to-baseline after the name line
NAME_BLOCK = 22      # vertical space the name line occupies
CHANNEL_GAP = 22     # spacing between reserved routing channels
GROUP_PAD = 18       # boundary inset from its members (left/right/bottom)
GROUP_LABEL_H = 20   # extra headroom at a boundary top for its label

# The name -> first-sub baseline step is 16; every later step is LINE_H (15).
NAME_TO_SUB = 16
CORNER_R = 10        # elbow corner radius
ELBOW_MIN_DY = 24    # below this |dy| a straight line beats an elbow (2*r + 4)
ARROW_STANDOFF = 6   # fixed 10x8 marker projects 4px: leave a 2px tip/node gap
CYL_RY = 8           # cylinder lid radius
HEX_SHOULDER = 12    # hexagon shoulder inset
STACK_OFFSET = 8     # stack back-plate total offset in both axes
CLOUD_W = 140        # cloud shape is a fixed box
CLOUD_H = 70
CLOUD_LABEL_MAX = 90  # a cloud narrows sharply; text wider than this leaves the outline
BADGE_H = 16
BADGE_PAD_X = 8      # text inset each side inside a badge chip
BADGE_LIFT = 8       # how far a corner badge rides above the node's top edge
STEP_R = 9
LEGEND_GAP = 20      # clear space between lowest content and the legend
LEGEND_CHIP_W = 16
LEGEND_CHIP_H = 10
LEGEND_ROW_PITCH = 16

TYPES = (
    "frontend", "backend", "database", "cache", "compute",
    "cloud", "bus", "security", "observability", "generic",
)
SHAPES = ("rect", "cylinder", "hex", "actor", "stack", "cloud")
BOUNDARY_KINDS = ("region", "vpc", "az", "sg")
ARROW_STYLES = ("solid", "dashed", "dotted", "thick", "thin")

# ---------------------------------------------------------------------------
# Text metrics — references/layout.md#text-width
#
# System monospace (ui-monospace / SFMono-Regular / Menlo / Consolas) uses
# approximately 0.6em for ASCII; CJK fallback uses approximately 1em. These are
# conservative layout estimates, NOT browser shaping/font measurements. Combining
# marks, variation selectors and joiners add no advance; joined emoji and flags
# are estimated as one full-width cluster. Font fallback can still differ.
# ---------------------------------------------------------------------------


def is_full_width(ch: str) -> bool:
    """True when the glyph occupies a full 1.0em advance.

    East_Asian_Width 'A' (ambiguous, e.g. U+00B7 MIDDLE DOT) is deliberately
    treated as half-width: that matches how a browser resolves it inside a
    Latin run.
    """
    return unicodedata.east_asian_width(ch) in ("W", "F")


def text_em(s: str) -> float:
    """Approximate cluster advances; not a replacement for a font shaper."""
    widths = []
    joined = False
    regional = False
    for c in s:
        cp = ord(c)
        if c == '\u200d':
            joined = True
            continue
        if unicodedata.category(c) in ('Mn', 'Me', 'Cf') or 0x1F3FB <= cp <= 0x1F3FF:
            continue
        if c in '\r\n':
            continue
        # Mathematical alphanumeric symbols use proportional math fallback fonts
        # even in a monospace stack. Budget 1.2em rather than 0.6em; for example
        # double-struck W occupies about 0.98em in STIX Two Math on macOS.
        if 0x1D400 <= cp <= 0x1D7FF:
            w = 1.2
        else:
            w = 1.0 if is_full_width(c) or 0x1F1E6 <= cp <= 0x1F1FF else 0.6
        if joined and widths:
            widths[-1] = max(widths[-1], w)
        elif 0x1F1E6 <= cp <= 0x1F1FF and regional:
            regional = False
            joined = False
            continue
        else:
            widths.append(w)
        regional = 0x1F1E6 <= cp <= 0x1F1FF
        joined = False
    return sum(widths)


def text_width(s: str, font_size: float) -> float:
    """Approximate pixel advance at ``font_size`` (system monospace + CJK)."""
    return text_em(s) * font_size


def ceil_to_10(v: float) -> int:
    """Round up to a multiple of 10 so column arithmetic stays mental."""
    return int(math.ceil(v / 10.0) * 10)


def ceil_even(v: float) -> int:
    """Round up to the next even number so ``y + H/2`` stays an integer."""
    n = int(math.ceil(v))
    return n + 1 if n % 2 else n


def clamp(lo: float, v: float, hi: float) -> float:
    return max(lo, min(v, hi))


def fits(s: str, font_size: float, box_w: float) -> bool:
    """Does ``s`` fit inside a node of width ``box_w`` with normal padding?"""
    return text_width(s, font_size) + 2 * PAD_X <= box_w + 1e-6


def max_chars(font_size: float, full_width: bool = False, box_w: float = MAX_W) -> int:
    """Character budget for one line — layout.md's per-font-size table."""
    avail = box_w - 2 * PAD_X
    per = font_size * (1.0 if full_width else 0.6)
    return int(avail // per)


def wrap_text(s: str, font_size: float, box_w: float = MAX_W) -> list[str]:
    """Greedy word wrap to lines that each fit ``box_w``.

    Splits on whitespace for Latin runs and between characters for CJK, which has
    no spaces. A single unbreakable token wider than the box is returned on its
    own line — the caller is responsible for reporting that as an overflow.
    """
    if fits(s, font_size, box_w):
        return [s]
    avail = box_w - 2 * PAD_X
    # Tokenise: keep whitespace-delimited Latin words whole, split CJK per char.
    tokens: list[str] = []
    for word in s.split():
        if any(is_full_width(c) for c in word):
            tokens.extend(word)
        else:
            tokens.append(word)
    lines: list[str] = []
    cur = ""
    for tok in tokens:
        joiner = "" if (cur and is_full_width(tok[0])) or not cur else " "
        cand = cur + joiner + tok
        if text_width(cand, font_size) <= avail or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = tok
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------------------
# Palette — references/components.md#choosing-a-type
#
# These are the authoritative stroke values, mirrored by the two token blocks in
# resources/template.html. validate.py cross-checks the template against them,
# so a drift in either direction is caught.
# ---------------------------------------------------------------------------
DARK_STROKE = {
    "frontend": "#22d3ee", "backend": "#34d399", "database": "#a78bfa",
    "cache": "#e879f9", "compute": "#60a5fa", "cloud": "#fbbf24",
    "bus": "#fb923c", "security": "#fb7185", "observability": "#a3e635",
    "generic": "#94a3b8",
}
LIGHT_STROKE = {
    "frontend": "#0891b2", "backend": "#059669", "database": "#7c3aed",
    "cache": "#c026d3", "compute": "#2563eb", "cloud": "#d97706",
    "bus": "#ea580c", "security": "#e11d48",
    # Deliberately lime-700, NOT lime-600: #65a30d only reaches 2.95:1 on the
    # #f8fafc page and fails the 3:1 non-text threshold, while #4d7c0f reaches
    # 4.77:1. Do not "brighten" this one.
    "observability": "#4d7c0f",
    "generic": "#475569",
}
LIGHT_PAGE = "#f8fafc"   # body background in light mode
DARK_PAGE = "#020617"    # body background in dark mode
DARK_MASK = "#090f21"    # composited .diagram-container surface in dark mode
LIGHT_MASK = "#ffffff"

# WCAG 2.1: 3:1 for non-text / large text (what a 1.5px stroke is judged as).
MIN_CONTRAST = 3.0


def _srgb_to_linear(channel: float) -> float:
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(color: str) -> float:
    """WCAG relative luminance of a ``#rrggbb`` string."""
    h = color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return (0.2126 * _srgb_to_linear(r)
            + 0.7152 * _srgb_to_linear(g)
            + 0.0722 * _srgb_to_linear(b))


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG contrast ratio between two ``#rrggbb`` colors."""
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


# ---------------------------------------------------------------------------
# Parsing helpers
#
# xml.etree cannot be used on the template: XML forbids "--" inside a comment
# and the SVG legitimately documents "--c-arrow" there. html.parser tolerates it,
# reports comments separately (so a "<svg>" mentioned inside a CSS comment in
# <head> is never mistaken for the real element), and hands back attribute
# dicts. Note it LOWERCASES attribute names, so viewBox arrives as "viewbox".
# ---------------------------------------------------------------------------


class GeometryError(ValueError):
    """Invalid numeric geometry with a source line for CLI diagnostics."""

    def __init__(self, message, line=None):
        super().__init__(message)
        self.line = line


def finite_number(raw, context, line=None):
    value = float(raw)
    if not math.isfinite(value):
        raise GeometryError(f'non-finite {context}: {raw!r}', line)
    return value


def _numbers(raw, context, line=None):
    return [finite_number(n, context, line) for n in _NUM_RE.findall(raw)]


class SvgElement:
    """SVG element with local attributes plus inherited style and world CTM.

    ``attrs``/``classes`` remain source-local for API compatibility. ``value``
    resolves presentation properties; geometry helpers return root SVG units.
    """

    __slots__ = ("tag", "attrs", "line", "text", "order", "parent", "children",
                 "ctm", "computed", "in_defs", "hidden", "content", "text_runs")

    def __init__(self, tag: str, attrs: dict, line: int, order: int):
        self.tag, self.attrs, self.line, self.order = tag, attrs, line, order
        self.text = ""
        self.parent = None
        self.children = []
        self.content = []
        self.text_runs = []
        self.ctm = parse_transform(attrs.get('transform', ''), line)
        self.computed = {}
        self.in_defs = self.hidden = False

    @property
    def classes(self) -> list[str]:
        return (self.attrs.get("class") or "").split()

    def value(self, name: str, default=None):
        return self.computed.get(name, self.attrs.get(name, default))

    def num(self, name: str):
        """Number or px length; percentages require a viewport and return None."""
        raw = self.value(name)
        if raw is None:
            return None
        m = re.fullmatch(r"\s*(" + _NUM_RE.pattern + r")(?:px)?\s*", str(raw))
        return finite_number(m.group(1), f'<{self.tag}> {name}', self.line) if m else None

    def bbox(self):
        """World bbox for rect-like elements (zero is SVG's default x/y)."""
        w, h = self.num("width"), self.num("height")
        if w is None or h is None:
            return None
        x, y = self.num("x") or 0, self.num("y") or 0
        return transform_box((x, y, x + w, y + h), self.ctm)

    def geom_key(self):
        """A mask identity includes world geometry, not only local coordinates."""
        return (self.tag, tuple(tuple((round(x, 5), round(y, 5)) for x, y in sub)
                                for sub in element_polylines(self)))

    def ancestor(self, attr: str):
        el = self
        while el is not None:
            if attr in el.attrs:
                return el
            el = el.parent
        return None

    def __repr__(self) -> str:
        return f"<{self.tag} L{self.line} {' '.join(self.classes)}>"


IDENTITY = (1., 0., 0., 1., 0., 0.)


def matrix_multiply(a, b):
    """SVG affine composition a*b: b acts first on column vectors."""
    return (a[0]*b[0]+a[2]*b[1], a[1]*b[0]+a[3]*b[1],
            a[0]*b[2]+a[2]*b[3], a[1]*b[2]+a[3]*b[3],
            a[0]*b[4]+a[2]*b[5]+a[4], a[1]*b[4]+a[3]*b[5]+a[5])


def transform_point(p, m):
    x, y = p
    return (m[0]*x+m[2]*y+m[4], m[1]*x+m[3]*y+m[5])


def bbox_of_points(points):
    pts = list(points)
    return (min(p[0] for p in pts), min(p[1] for p in pts),
            max(p[0] for p in pts), max(p[1] for p in pts)) if pts else None


def transform_box(b, m):
    return bbox_of_points(transform_point(p, m) for p in
                          ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])))


def parse_transform(raw: str, line=None):
    m = IDENTITY
    for name, values in re.findall(r"([A-Za-z]+)\s*\(([^)]*)\)", raw or ""):
        v = _numbers(values, f'transform {raw!r}', line)
        t = IDENTITY
        if name == 'matrix' and len(v) == 6:
            t = tuple(v)
        elif name == 'translate' and v:
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == 'scale' and v:
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == 'rotate' and v:
            c, s = math.cos(math.radians(v[0])), math.sin(math.radians(v[0]))
            t = (c, s, -s, c, 0, 0)
            if len(v) == 3:
                x, y = v[1:]
                t = (c, s, -s, c, x-c*x+s*y, y-s*x-c*y)
        elif name in ('skewX', 'skewY') and v:
            k = math.tan(math.radians(v[0]))
            t = (1, 0, k, 1, 0, 0) if name == 'skewX' else (1, k, 0, 1, 0, 0)
        m = matrix_multiply(m, t)
        if not all(math.isfinite(n) for n in m):
            raise GeometryError(f'non-finite transform result: {raw!r}', line)
    return m


def normalize_path(d: str) -> str:
    """Collapse whitespace/commas so two equal paths compare equal."""
    return re.sub(r"[\s,]+", " ", d).strip()


# Include explicit non-finite spellings so they are rejected, not skipped by
# tokenization (as well as ordinary exponents that overflow float conversion).
_NUM_RE = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?|[-+]?(?i:infinity|inf|nan)")
_CMD_RE = re.compile(r"([MmLlHhVvCcSsQqTtAaZz])|" + _NUM_RE.pattern)


def _tokens(d: str):
    """Yield ('cmd', letter) and ('num', float) in source order."""
    for m in _CMD_RE.finditer(d):
        if m.group(1):
            yield ("cmd", m.group(1))
        else:
            yield ("num", finite_number(m.group(0), 'path d'))


def _bezier(p0, ctrl, p1, steps: int):
    """Sample a quadratic or cubic Bézier, endpoints excluded from ``ctrl``."""
    pts = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1 - t
        if len(ctrl) == 1:
            c = ctrl[0]
            x = u * u * p0[0] + 2 * u * t * c[0] + t * t * p1[0]
            y = u * u * p0[1] + 2 * u * t * c[1] + t * t * p1[1]
        else:
            c1, c2 = ctrl
            x = (u ** 3 * p0[0] + 3 * u * u * t * c1[0]
                 + 3 * u * t * t * c2[0] + t ** 3 * p1[0])
            y = (u ** 3 * p0[1] + 3 * u * u * t * c1[1]
                 + 3 * u * t * t * c2[1] + t ** 3 * p1[1])
        pts.append((x, y))
    return pts


def _arc(p0, rx, ry, phi_deg, laf, sf, p1, steps: int = 16):
    """Sample an SVG elliptical arc, endpoint parameterization (F.6.5).

    Sampling rather than a closed-form extremum search: 16 points hold a cylinder
    lid or a cloud lobe to well under a pixel, and a bbox that is slightly *tight*
    on a decorative curve is far better than the wildly wrong box you get from
    treating the 7 arc parameters as coordinate pairs.
    """
    x1, y1 = p0
    x2, y2 = p1
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0 or (x1 == x2 and y1 == y2):
        return [p1]
    phi = math.radians(phi_deg)
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    dx2, dy2 = (x1 - x2) / 2.0, (y1 - y2) / 2.0
    x1p = cos_p * dx2 + sin_p * dy2
    y1p = -sin_p * dx2 + cos_p * dy2
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:                      # radii too small: scale up, per spec
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coef = math.sqrt(max(num / den, 0.0)) * (-1 if laf == sf else 1)
    cxp = coef * rx * y1p / ry
    cyp = -coef * ry * x1p / rx
    cx = cos_p * cxp - sin_p * cyp + (x1 + x2) / 2.0
    cy = sin_p * cxp + cos_p * cyp + (y1 + y2) / 2.0

    def angle(ux, uy, vx, vy):
        dot = ux * vx + uy * vy
        n1 = math.hypot(ux, uy) * math.hypot(vx, vy)
        a = math.acos(max(-1.0, min(1.0, dot / n1))) if n1 else 0.0
        return -a if ux * vy - uy * vx < 0 else a

    t1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = angle((x1p - cxp) / rx, (y1p - cyp) / ry,
               (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sf and dt > 0:
        dt -= 2 * math.pi
    elif sf and dt < 0:
        dt += 2 * math.pi
    out = []
    for i in range(1, steps + 1):
        t = t1 + dt * i / steps
        out.append((cx + rx * math.cos(t) * cos_p - ry * math.sin(t) * sin_p,
                    cy + rx * math.cos(t) * sin_p + ry * math.sin(t) * cos_p))
    return out


def path_polylines(d: str) -> list[list[tuple[float, float]]]:
    """Flatten a path's ``d`` into one polyline per subpath.

    Curves are sampled, so the result is a faithful outline rather than the
    control-point soup you get from reading every number as a coordinate. Note
    ``M`` starts a NEW polyline: joining across a move-to would invent a segment
    the renderer never draws, and every mask/overlap check would see it.
    """
    subs: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []
    pos = (0.0, 0.0)
    start = (0.0, 0.0)
    cmd = None
    prev_ctrl = None            # control point and command family must both match
    prev_cmd = None
    args: list[float] = []
    toks = list(_tokens(d))
    i = 0

    def flush():
        if len(cur) > 1:
            subs.append(list(cur))

    while i < len(toks):
        kind, val = toks[i]
        if kind == "cmd":
            cmd = val
            i += 1
            if cmd in "Zz":
                if cur:
                    cur.append(start)
                    flush()
                    cur = [start]
                    pos = start
                prev_ctrl = None
                prev_cmd = 'Z'
                cmd = None
            continue
        if cmd is None:
            return subs                     # malformed: no leading command
        need = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4,
                "Q": 4, "T": 2, "A": 7}[cmd.upper()]
        args = []
        while len(args) < need and i < len(toks) and toks[i][0] == "num":
            args.append(toks[i][1])
            i += 1
        if len(args) < need:
            break                           # truncated command
        rel = cmd.islower()
        px, py = pos
        c = cmd.upper()
        if c == "M":
            x, y = (px + args[0], py + args[1]) if rel else (args[0], args[1])
            flush()
            cur = [(x, y)]
            start = pos = (x, y)
            cmd = "l" if rel else "L"       # implicit line-to for repeats
            prev_ctrl = None
            continue
        if c == "L":
            pt = (px + args[0], py + args[1]) if rel else (args[0], args[1])
            new = [pt]
            prev_ctrl = None
        elif c == "H":
            pt = (px + args[0], py) if rel else (args[0], py)
            new = [pt]
            prev_ctrl = None
        elif c == "V":
            pt = (px, py + args[0]) if rel else (px, args[0])
            new = [pt]
            prev_ctrl = None
        elif c in ("C", "S"):
            if c == "C":
                c1 = (px + args[0], py + args[1]) if rel else (args[0], args[1])
                c2 = (px + args[2], py + args[3]) if rel else (args[2], args[3])
                pt = (px + args[4], py + args[5]) if rel else (args[4], args[5])
            else:
                c1 = (2 * px - prev_ctrl[0], 2 * py - prev_ctrl[1]) \
                    if prev_ctrl and prev_cmd in ('C', 'S') else (px, py)
                c2 = (px + args[0], py + args[1]) if rel else (args[0], args[1])
                pt = (px + args[2], py + args[3]) if rel else (args[2], args[3])
            new = _bezier((px, py), (c1, c2), pt, 12)
            prev_ctrl = c2
        elif c in ("Q", "T"):
            if c == "Q":
                c1 = (px + args[0], py + args[1]) if rel else (args[0], args[1])
                pt = (px + args[2], py + args[3]) if rel else (args[2], args[3])
            else:
                c1 = (2 * px - prev_ctrl[0], 2 * py - prev_ctrl[1]) \
                    if prev_ctrl and prev_cmd in ('Q', 'T') else (px, py)
                pt = (px + args[0], py + args[1]) if rel else (args[0], args[1])
            new = _bezier((px, py), (c1,), pt, 8)
            prev_ctrl = c1
        else:                               # A
            pt = (px + args[5], py + args[6]) if rel else (args[5], args[6])
            new = _arc((px, py), args[0], args[1], args[2],
                       int(args[3]) != 0, int(args[4]) != 0, pt)
            prev_ctrl = None
        if not cur:
            cur = [(px, py)]
        cur.extend(new)
        pos = new[-1]
        prev_cmd = c
    flush()
    return subs


def points_polyline(points: str, closed: bool = True) -> list[list[tuple[float, float]]]:
    """Parse points; polygons close, polylines MUST pass ``closed=False``."""
    nums = _numbers(points, 'points')
    pts = [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
    if closed and len(pts) > 2 and pts[-1] != pts[0]:
        pts.append(pts[0])
    return [pts] if pts else []


def path_points(d: str) -> list[tuple[float, float]]:
    """Every sampled vertex of a path, flattened — used for bounding boxes."""
    return [p for sub in path_polylines(d) for p in sub]


def element_polylines(el: SvgElement, world: bool = True):
    """Sample drawable contours (curves approximate, typically subpixel error)."""
    n = lambda key, default=0: el.num(key) if el.num(key) is not None else default
    polys = []
    if el.tag in ('path', 'polygon', 'polyline'):
        try:
            polys = (path_polylines(el.attrs.get('d', '')) if el.tag == 'path' else
                     points_polyline(el.attrs.get('points', ''), el.tag == 'polygon'))
        except GeometryError as exc:
            raise GeometryError(f'<{el.tag}> {exc}', el.line) from exc
    elif el.tag == 'line':
        polys = [[(n('x1'), n('y1')), (n('x2'), n('y2'))]]
    elif el.tag in ('circle', 'ellipse'):
        cx, cy = n('cx'), n('cy')
        rx, ry = (n('r'), n('r')) if el.tag == 'circle' else (n('rx'), n('ry'))
        if rx > 0 and ry > 0:
            polys = [[(cx + rx*math.cos(i*math.pi/32), cy + ry*math.sin(i*math.pi/32))
                      for i in range(65)]]
    elif el.tag == 'rect':
        x, y, w, h = n('x'), n('y'), n('width'), n('height')
        if w <= 0 or h <= 0:
            return []
        rx = min(max(n('rx', n('ry')), 0), w/2)
        ry = min(max(n('ry', rx), 0), h/2)
        if rx and ry:
            pts = []
            for cx, cy, angle in ((x+w-rx, y+ry, -90), (x+w-rx, y+h-ry, 0),
                                  (x+rx, y+h-ry, 90), (x+rx, y+ry, 180)):
                pts.extend((cx+rx*math.cos(math.radians(angle+i*90/8)),
                            cy+ry*math.sin(math.radians(angle+i*90/8))) for i in range(9))
            polys = [pts + [pts[0]]]
        else:
            polys = [[(x,y), (x+w,y), (x+w,y+h), (x,y+h), (x,y)]]
    return [[transform_point(p, el.ctm) for p in sub] for sub in polys] if world else polys


def geometry_bbox(el: SvgElement):
    """Root-coordinate bbox; definition children are measured only on request."""
    return bbox_of_points(p for sub in element_polylines(el) for p in sub)


def segments_of(el: SvgElement) -> list[tuple[float, float, float, float]]:
    """World segments; neither polylines nor separate M subpaths are joined."""
    return [(*a, *b) for sub in element_polylines(el) for a, b in zip(sub, sub[1:])
            if math.dist(a, b) > 1e-9]


def point_segment_distance(p, seg):
    x, y, xx, yy = seg
    dx, dy = xx-x, yy-y
    den = dx*dx+dy*dy
    t = clamp(0, ((p[0]-x)*dx+(p[1]-y)*dy)/den, 1) if den else 0
    return math.hypot(p[0]-x-t*dx, p[1]-y-t*dy)


def segment_relation(a, b, tol=1e-6):
    """Return ('overlap', length), ('point', (x,y)), or (None, None)."""
    p, q = a[:2], b[:2]
    u, v = (a[2]-a[0], a[3]-a[1]), (b[2]-b[0], b[3]-b[1])
    cross = lambda x,y: x[0]*y[1]-x[1]*y[0]
    w = (q[0]-p[0], q[1]-p[1])
    den = cross(u, v)
    length = math.hypot(*u)
    if length < tol or math.hypot(*v) < tol:
        return None, None
    if abs(den) <= tol*length*math.hypot(*v):
        if abs(cross(w,u))/length > tol:
            return None, None
        t0 = (w[0]*u[0]+w[1]*u[1])/(length*length)
        t1 = t0+(v[0]*u[0]+v[1]*u[1])/(length*length)
        lo, hi = max(0,min(t0,t1)), min(1,max(t0,t1))
        if hi-lo > tol/length:
            return 'overlap', (hi-lo)*length
        if hi >= lo-tol/length:
            return 'point', (p[0]+lo*u[0],p[1]+lo*u[1])
        return None, None
    t, s = cross(w,v)/den, cross(w,u)/den
    if -tol <= t <= 1+tol and -tol <= s <= 1+tol:
        return 'point', (p[0]+t*u[0],p[1]+t*u[1])
    return None, None


def polygon_segments(poly):
    return [(*a,*b) for a,b in zip(poly, poly[1:]+poly[:1]) if math.dist(a,b)>1e-9]


def point_in_polygon(p, poly, inset=0.0):
    """Even/odd containment; positive inset excludes border-only contact."""
    if not poly:
        return False
    edges = polygon_segments(poly)
    distance = min((point_segment_distance(p,s) for s in edges), default=0)
    if distance <= 1e-7:
        return inset <= 0
    if distance < inset:
        return False
    inside = False
    x,y = p
    for x1,y1,x2,y2 in edges:
        if (y1>y) != (y2>y) and x < (x2-x1)*(y-y1)/(y2-y1)+x1:
            inside = not inside
    return inside


def segment_hits_polygon(seg, poly, inset=0.5):
    """Test interval interiors, not just bbox intersection or curve vertices."""
    length = math.dist(seg[:2], seg[2:])
    if not length:
        return False
    ts = [0.,1.]
    for side in polygon_segments(poly):
        kind, p = segment_relation(seg, side)
        if kind == 'point':
            ts.append(clamp(0, math.dist(seg[:2],p)/length, 1))
    ts = sorted(set(ts))
    for t in [0.,1.] + [(a+b)/2 for a,b in zip(ts,ts[1:])]:
        p = (seg[0]+t*(seg[2]-seg[0]), seg[1]+t*(seg[3]-seg[1]))
        if point_in_polygon(p, poly, inset):
            return True
    return False


def polygons_overlap(a, b, tol=0.5):
    if not a or not b or not boxes_overlap(bbox_of_points(a), bbox_of_points(b), tol):
        return False
    if any(segment_hits_polygon(s,b,tol) for s in polygon_segments(a)):
        return True
    if any(segment_hits_polygon(s,a,tol) for s in polygon_segments(b)):
        return True
    # Coincident contours can have every vertex on a border.
    for poly, other in ((a,b),(b,a)):
        center = (sum(p[0] for p in poly)/len(poly), sum(p[1] for p in poly)/len(poly))
        if point_in_polygon(center,poly,tol) and point_in_polygon(center,other,tol):
            return True
    return False


def seg_hits_box(seg, box, inset: float = 2.0) -> bool:
    """Does a segment pass through a box, ignoring a hairline at its edge?

    ``inset`` shrinks the box so an arrow that merely *terminates* on the border
    (every arrow does, by design) is not reported as passing underneath.
    """
    x1, y1, x2, y2 = seg
    bx, by, br, bb = box
    bx, by, br, bb = bx + inset, by + inset, br - inset, bb - inset
    if br <= bx or bb <= by:
        return False
    # Liang-Barsky clip of the segment against the shrunken box.
    dx, dy = x2 - x1, y2 - y1
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x1 - bx), (dx, br - x1), (-dy, y1 - by), (dy, bb - y1)):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


def boxes_overlap(a, b, tol: float = 0.5) -> bool:
    """Strict bbox intersection with a sub-pixel tolerance."""
    return (a[0] + tol < b[2] and b[0] + tol < a[2]
            and a[1] + tol < b[3] and b[1] + tol < a[3])


def box_contains(outer, inner, tol: float = 0.5) -> bool:
    return (outer[0] - tol <= inner[0] and inner[2] <= outer[2] + tol
            and outer[1] - tol <= inner[1] and inner[3] <= outer[3] + tol)


# Void/self-closing SVG tags never carry children, so an unterminated one must
# not be treated as opening a scope.
_SELF_CLOSING = {"rect", "circle", "ellipse", "line", "path", "polygon",
                 "polyline", "use", "image", "stop", "feoffset", "fegaussianblur"}


class DiagramDocument(HTMLParser):
    """Parsed view of a generated diagram HTML file.

    Collects, in one pass:
      * every element inside every ``<svg>`` (``self.svg_elements``)
      * the CSS text of ``<style>`` blocks inside an ``<svg>`` (``self.svg_css``)
      * the CSS text of ``<style>`` blocks in ``<head>`` (``self.head_css``)
      * ``<script>`` bodies and the raw source (``self.scripts`` / ``self.raw``)
      * ids seen anywhere in the document (``self.ids``)
    """

    def __init__(self, source: str):
        super().__init__(convert_charrefs=True)
        self.raw = source
        self.svg_elements: list[SvgElement] = []
        self.svg_css = ""
        self.head_css = ""
        self.scripts: list[str] = []
        self.ids: set[str] = set()
        self.svg_count = 0
        self._svg_depth = 0
        self._in_style = False
        self._in_script = False
        self._order = 0
        self._stack = []
        self.elements_by_id = {}
        self.limitations = set()
        self.feed(source)
        self.close()
        self._resolve()

    # -- HTMLParser hooks ---------------------------------------------------
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "svg":
            self._svg_depth += 1
            self.svg_count += 1
        if self._svg_depth:
            self._order += 1
            el = SvgElement(tag, a, self.getpos()[0], self._order)
            if self._stack:
                el.parent = self._stack[-1]
                el.parent.children.append(el)
                el.parent.content.append(el)
            self.svg_elements.append(el)
            if a.get('id'):
                self.elements_by_id[a['id']] = el
            if tag not in _SELF_CLOSING:
                self._stack.append(el)
        if tag == "style":
            self._in_style = True
        elif tag == "script":
            self._in_script = True

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag not in _SELF_CLOSING:
            for i in range(len(self._stack)-1, -1, -1):
                if self._stack[i].tag == tag:
                    del self._stack[i:]
                    break
        if tag == "svg":
            self._svg_depth = max(0, self._svg_depth - 1)
        if tag == "style":
            self._in_style = False
        elif tag == "script":
            self._in_script = False

    def handle_data(self, data):
        if self._in_style:
            if self._svg_depth:
                self.svg_css += data
            else:
                self.head_css += data
        elif self._in_script:
            self.scripts.append(data)
        elif self._stack and self._stack[-1].tag in ('text', 'tspan', 'title', 'desc'):
            self._stack[-1].content.append(data)
            # Aggregate text also on the parent <text>, preserving tspan tails.
            for el in reversed(self._stack):
                if el.tag in ('text', 'tspan', 'title', 'desc'):
                    el.text += data

    def _resolve(self):
        rules = []
        for selector, body in re.findall(r'([^{}]+)\{([^{}]*)\}', strip_comments(self.head_css+'\n'+self.svg_css)):
            props = parse_declarations(body)
            for sel in selector.split(','):
                sel = sel.strip()
                if sel and not any(c in sel for c in ':@[]>+~'):
                    score = 100*sel.count('#') + 10*sel.count('.') + len(re.findall(r'(?:^|\s)[a-z]',sel))
                    rules.append((score, len(rules), sel, props))
        rules.sort(key=lambda rule: rule[:2])
        for el in self.svg_elements:
            parent = el.parent
            el.computed = {k:v for k,v in (parent.computed.items() if parent else []) if k in INHERITED}
            el.computed.update({k:v for k,v in el.attrs.items() if k in PRESENTATION})
            for _,_,sel,props in rules:
                if selector_matches(el,sel):
                    el.computed.update(props)
            el.computed.update(parse_declarations(el.attrs.get('style','')))
            for k,v in list(el.computed.items()):
                if v == 'inherit':
                    el.computed[k] = parent.value(k) if parent else None
            fs = el.value('font-size','16') or '16'
            if str(fs).endswith(('%','em')):
                base = parent.num('font-size') or 16 if parent else 16
                try:
                    fs = float(fs[:-1])*base/100 if fs.endswith('%') else float(fs[:-2])*base
                except ValueError:
                    fs = base
            if isinstance(fs, (int, float)):
                finite_number(fs, f'<{el.tag}> font-size', el.line)
            el.computed['font-size'] = str(fs)
            el.ctm = matrix_multiply(parent.ctm if parent else IDENTITY,
                                     parse_transform(el.attrs.get('transform',''), el.line))
            if not all(math.isfinite(n) for n in el.ctm):
                raise GeometryError(f'non-finite cumulative transform on <{el.tag}>', el.line)
            el.in_defs = (parent.in_defs if parent else False) or el.tag in DEFINITION_TAGS
            el.hidden = ((parent.hidden if parent else False) or el.value('display') == 'none'
                         or el.value('visibility') in ('hidden','collapse') or el.value('opacity') == '0')
            if el.tag in ('use','textpath','image','foreignobject') and not el.in_defs:
                self.limitations.add(el.tag)
            if not el.in_defs:
                if el.tag == 'svg' and parent:
                    self.limitations.add('nested SVG viewport')
                if el.value('clip-path') or el.attrs.get('mask'):
                    self.limitations.add('clipping/masking')
                if el.tag in ('text','tspan') and (el.attrs.get('textlength') or el.attrs.get('rotate')
                        or any(len(_NUM_RE.findall(el.attrs.get(k,''))) > 1 for k in ('x','y','dx','dy'))):
                    self.limitations.add('per-glyph text positioning')
                if el.value('direction') == 'rtl':
                    self.limitations.add('bidirectional text shaping')
        for el in self.svg_elements:
            if el.tag == 'text' and not el.in_defs and not el.hidden:
                el.text_runs = layout_text(el)

    @property
    def rendered_elements(self):
        """Actual elements only: defs/marker/clipPath/mask contents are not paint."""
        return [el for el in self.svg_elements if not el.in_defs and not el.hidden]

    # -- convenience --------------------------------------------------------
    @property
    def svg_root(self) -> SvgElement | None:
        for el in self.svg_elements:
            if el.tag == "svg":
                return el
        return None

    def viewbox(self):
        root = self.svg_root
        if root is None:
            return None
        raw = root.attrs.get("viewbox")  # html.parser lowercases attribute names
        if not raw:
            return None
        parts = _numbers(raw, '<svg> viewbox', root.line)
        return tuple(parts) if len(parts) == 4 else None

    def by_class(self, *required: str, exclude: tuple = ()) -> list[SvgElement]:
        out = []
        for el in self.svg_elements:
            cs = el.classes
            if all(r in cs for r in required) and not any(x in cs for x in exclude):
                out.append(el)
        return out

    @property
    def all_scripts(self) -> str:
        return "\n".join(self.scripts)


DEFINITION_TAGS = {'defs', 'marker', 'pattern', 'clippath', 'mask', 'symbol',
                   'lineargradient', 'radialgradient', 'filter'}
INHERITED = {'fill', 'fill-opacity', 'fill-rule', 'stroke', 'stroke-width', 'stroke-opacity',
             'font-size', 'font-family', 'font-weight', 'text-anchor', 'dominant-baseline',
             'alignment-baseline', 'visibility', 'writing-mode', 'direction', 'letter-spacing',
             'marker-start', 'marker-mid', 'marker-end'}
PRESENTATION = INHERITED | {'opacity', 'display', 'overflow', 'baseline-shift'}


def parse_declarations(body):
    return {k.strip().lower(): v.strip().removesuffix('!important').strip()
            for part in body.split(';') if ':' in part for k,v in [part.split(':',1)]
            if not k.strip().startswith('--')}


def selector_matches(el, selector):
    """Small static CSS subset: type/id/class compounds and descendant selectors."""
    def simple(node, sel):
        tag = re.match(r'^([\w-]+|\*)', sel)
        if tag and tag[1] not in ('*',node.tag):
            return False
        ids = re.findall(r'#([\w-]+)',sel)
        classes = re.findall(r'\.([\w-]+)',sel)
        return all(node.attrs.get('id') == x for x in ids) and all(x in node.classes for x in classes)
    parts = selector.split()
    if not parts or not simple(el,parts[-1]):
        return False
    parent = el.parent
    for part in reversed(parts[:-1]):
        while parent and not simple(parent,part):
            parent = parent.parent
        if not parent:
            return False
        parent = parent.parent
    return True


def layout_text(root):
    """Approximate positioned runs, with tspan tails, inherited metrics and CTM.

    Handles x/y/dx/dy, chunk-level anchoring and common baselines/writing modes.
    Per-glyph coordinate/rotation lists, bidi shaping and textPath need a browser.
    """
    cursor = [0.,0.]
    chunks = []
    chunk = []

    def visit(el):
        nonlocal chunk
        if el.hidden:
            return
        if 'x' in el.attrs or 'y' in el.attrs:
            if chunk:
                chunks.append(chunk)
                chunk = []
            for i,k in enumerate(('x','y')):
                if el.num(k) is not None:
                    cursor[i] = el.num(k)
        cursor[0] += el.num('dx') or 0
        cursor[1] += el.num('dy') or 0
        for part in el.content:
            if isinstance(part, SvgElement):
                if part.tag == 'tspan':
                    visit(part)
                continue
            text = re.sub(r'\s+', ' ',part)
            if not text.strip():
                continue
            fs = el.num('font-size') or 16
            width = text_width(text,fs)
            spacing = el.num('letter-spacing') or 0
            width += max(0,len(text)-1)*spacing
            vertical = str(el.value('writing-mode','')).startswith(('vertical','tb'))
            chunk.append({'element':el, 'root':root, 'text':text, 'x':cursor[0], 'y':cursor[1],
                          'width':width, 'fs':fs, 'vertical':vertical})
            cursor[1 if vertical else 0] += width
    visit(root)
    if chunk:
        chunks.append(chunk)
    runs = []
    for chunk in chunks:
        first = chunk[0]
        axis = 'y' if first['vertical'] else 'x'
        total = max(p[axis]+p['width'] for p in chunk)-first[axis]
        anchor = first['element'].value('text-anchor','start')
        shift = total/2 if anchor == 'middle' else total if anchor == 'end' else 0
        for p in chunk:
            el,fs,w = p['element'],p['fs'],p['width']
            x,y = p['x'],p['y']
            # The whole anchored chunk belongs at its anchor, even when later
            # tspan advances would place the pre-anchor cursor outside the node.
            anchor_point = (x, first['y']) if p['vertical'] else (first['x'], y)
            p['origin'] = transform_point(anchor_point,el.ctm)
            baseline = el.value('dominant-baseline',el.value('alignment-baseline','alphabetic'))
            delta = 0.3*fs if baseline in ('middle','central') else 0.8*fs if baseline in ('hanging','text-before-edge') else -0.2*fs if baseline == 'text-after-edge' else 0
            y += delta - (el.num('baseline-shift') or 0)
            if p['vertical']:
                b = (x-fs/2,y-shift,x+fs/2,y-shift+w)
            else:
                b = (x-shift,y-0.8*fs,x-shift+w,y+0.2*fs)
            poly = [(b[0],b[1]),(b[2],b[1]),(b[2],b[3]),(b[0],b[3])]
            p['polygon'] = [transform_point(pt,el.ctm) for pt in poly]
            p['bbox'] = bbox_of_points(p['polygon'])
            runs.append(p)
    return runs


def _positive_opacity(el, name):
    raw = str(el.value(name, '1') or '1').strip().removesuffix('%')
    return finite_number(raw, f'<{el.tag}> {name}', el.line) > 0 if _NUM_RE.fullmatch(raw) else True


def _visible_marker_paint(doc, el):
    """Reject known invisible paint, preserving inherited/default/CSS-var fills.

    This is an alpha/paint check, not color resolution or stroke tessellation.
    Unknown paint servers remain measurable rather than being assumed invisible.
    """
    parent = el
    while parent is not None:
        if parent.hidden or not _positive_opacity(parent, 'opacity'):
            return False
        parent = parent.parent

    def visible(value, seen=()):
        value = str(value).strip()
        ref = re.fullmatch(r'var\((--[\w-]+)\)', value)
        if ref and ref[1] not in seen:
            values = re.findall(re.escape(ref[1])+r'\s*:\s*([^;}]+)', doc.head_css+'\n'+doc.svg_css)
            return all(visible(v, seen+(ref[1],)) for v in values)
        value = value.lower()
        if value in ('none', 'transparent'):
            return False
        if re.fullmatch(r'#[\da-f]{4}|#[\da-f]{8}', value):
            return int(value[-1:] if len(value) == 5 else value[-2:], 16) > 0
        if value.startswith(('rgba(', 'hsla(')) or '/' in value:
            alpha = re.search(r'[,/]\s*('+_NUM_RE.pattern+r')(%)?\s*\)$', value)
            if alpha:
                return finite_number(alpha[1], f'<{el.tag}> paint alpha', el.line) > 0
        return True

    fill = (el.tag != 'line' and visible(el.value('fill', 'black') or 'black')
            and _positive_opacity(el, 'fill-opacity'))
    width = el.num('stroke-width')
    stroke = (visible(el.value('stroke', 'none') or 'none')
              and _positive_opacity(el, 'stroke-opacity') and (width is None or width > 0))
    return fill or stroke


def marker_instances(doc, edge):
    """Instantiate marker paint in root units; return (instances, diagnostics).

    Honors markerUnits, refX/refY, orient, viewBox/preserveAspectRatio and child
    transforms. Arbitrary marker drawings are bounded, but directional checks
    are intentionally limited to recognizable triangular arrowheads.
    """
    polys = [p for p in element_polylines(edge, world=False) if len(p)>1]
    if not polys:
        return [], []
    instances, issues = [], []
    placements = []
    for sub in polys:
        # Repeated endpoint vertices have no tangent. Search within this subpath,
        # never across M; an entirely zero-length subpath uses SVG's +x fallback.
        start_adjacent = next((p for p in sub[1:] if math.dist(p, sub[0]) > 1e-9),
                              (sub[0][0]+1, sub[0][1]))
        end_adjacent = next((p for p in reversed(sub[:-1]) if math.dist(p, sub[-1]) > 1e-9),
                            (sub[-1][0]-1, sub[-1][1]))
        placements.extend([('start', sub[0], start_adjacent), ('end', sub[-1], end_adjacent)])
    curve_mid = edge.tag == 'path' and re.search(r'[CcSsQqTtAa]', edge.attrs.get('d',''))
    if edge.value('marker-mid') not in (None, 'none') and curve_mid:
        issues.append('unresolved marker-mid on a sampled curve; verify vertex orientation in a browser')
    elif edge.value('marker-mid') not in (None, 'none'):
        for sub in polys:
            for i in range(1,len(sub)-1):
                incoming = (sub[i][0]-sub[i-1][0], sub[i][1]-sub[i-1][1])
                outgoing = (sub[i+1][0]-sub[i][0], sub[i+1][1]-sub[i][1])
                ni, no = math.hypot(*incoming) or 1, math.hypot(*outgoing) or 1
                adjacent = (sub[i][0]+incoming[0]/ni+outgoing[0]/no,
                            sub[i][1]+incoming[1]/ni+outgoing[1]/no)
                placements.append(('mid',sub[i],adjacent))
    checked = set()
    for position,point,adjacent in placements:
        raw = edge.value('marker-'+position)
        if not raw or raw == 'none':
            continue
        match = re.fullmatch(r"url\(\s*['\"]?#([^'\"\s)]+)['\"]?\s*\)",raw)
        marker = doc.elements_by_id.get(match[1]) if match else None
        if marker is None or marker.tag != 'marker':
            if raw not in checked:
                issues.append(f'marker reference {raw!r} is missing or is not a local <marker>')
                checked.add(raw)
            continue
        mw, mh = marker.num('markerwidth'), marker.num('markerheight')
        mw, mh = 3 if mw is None else mw, 3 if mh is None else mh
        if mw <= 0 or mh <= 0:
            issues.append(f'marker #{match[1]} has non-positive dimensions')
            continue
        vb = _numbers(marker.attrs.get('viewbox',''), f'marker #{match[1]} viewbox', marker.line)
        vm = IDENTITY
        if 'viewbox' in marker.attrs:
            if len(vb) != 4 or vb[2] <= 0 or vb[3] <= 0:
                issues.append(f'marker #{match[1]} has invalid viewBox')
                continue
            vx,vy,vw,vh = vb
            sx,sy = mw/vw,mh/vh
            par = marker.attrs.get('preserveaspectratio','xMidYMid meet')
            ox = oy = 0
            if par != 'none':
                sx = sy = max(sx,sy) if 'slice' in par else min(sx,sy)
                ox = (mw-vw*sx)*(0 if 'xMin' in par else 1 if 'xMax' in par else .5)
                oy = (mh-vh*sy)*(0 if 'YMin' in par else 1 if 'YMax' in par else .5)
            vm = (sx,0,0,sy,ox-vx*sx,oy-vy*sy)
        rx,ry = marker.num('refx') or 0,marker.num('refy') or 0
        ref = transform_point((rx,ry),vm)
        dx,dy = ((point[0]-adjacent[0],point[1]-adjacent[1]) if position == 'end'
                 else (adjacent[0]-point[0],adjacent[1]-point[1]))
        orient = marker.attrs.get('orient','0')
        if orient in ('auto','auto-start-reverse'):
            angle = math.degrees(math.atan2(dy,dx))
            if orient == 'auto-start-reverse' and position == 'start':
                angle += 180
        else:
            try:
                if orient.endswith('rad'):
                    value, factor = float(orient[:-3]), 180/math.pi
                elif orient.endswith('turn'):
                    value, factor = float(orient[:-4]), 360
                else:
                    value, factor = float(orient.removesuffix('deg')), 1
            except ValueError:
                issues.append(f'marker #{match[1]} has invalid orient {orient!r}')
                continue
            angle = finite_number(value, f'marker #{match[1]} orient {orient!r}', marker.line)*factor
            finite_number(angle, f'marker #{match[1]} orient {orient!r}', marker.line)
        units = marker.attrs.get('markerunits','strokeWidth')
        if units not in ('strokeWidth','userSpaceOnUse'):
            issues.append(f'marker #{match[1]} has invalid markerUnits {units!r}')
            continue
        scale = (edge.num('stroke-width') or 1) if units == 'strokeWidth' else 1
        c,s = math.cos(math.radians(angle))*scale,math.sin(math.radians(angle))*scale
        place = matrix_multiply(edge.ctm,(c,s,-s,c,point[0],point[1]))
        offset = (1,0,0,1,-ref[0],-ref[1])
        instance = {'edge':edge,'marker':marker,'position':position,'polygons':[],
                    'tip':None,'direction':None,'point':transform_point(point,edge.ctm)}
        descendants = list(marker.children)
        clipped = False
        while descendants:
            child = descendants.pop(0)
            descendants.extend(child.children)
            if not _visible_marker_paint(doc, child):
                continue
            chain = []
            node = child
            while node is not marker:
                chain.append(node)
                node = node.parent
            local = vm
            for node in reversed(chain):
                local = matrix_multiply(local,parse_transform(node.attrs.get('transform',''), node.line))
            source_polys = element_polylines(child,world=False)
            viewport_polys = [[transform_point(p,local) for p in sub] for sub in source_polys]
            for poly, source_poly in zip(viewport_polys, source_polys):
                bb = bbox_of_points(poly)
                if marker.value('overflow','hidden') != 'visible' and bb and not box_contains((0,0,mw,mh),bb,.01):
                    clipped = True
                rendered = [transform_point(p,matrix_multiply(place,offset)) for p in poly]
                instance['polygons'].append(rendered)
                unique = rendered[:-1] if len(rendered)>1 and math.dist(rendered[0],rendered[-1])<1e-6 else rendered
                source_unique = source_poly[:-1] if len(source_poly)>1 and math.dist(source_poly[0],source_poly[-1])<1e-6 else source_poly
                if len(unique) == len(source_unique) == 3:
                    # Recognize the isosceles tip BEFORE non-uniform CTM scaling.
                    candidates = [i for i in range(3) if abs(math.dist(source_unique[(i+2)%3],source_unique[i])
                                  -math.dist(source_unique[(i+2)%3],source_unique[(i+1)%3])) < 1e-5]
                    if len(candidates) != 1:
                        continue  # equilateral/scalene artwork has no unique arrow tip
                    base = candidates[0]
                    tip = unique[(base+2)%3]
                    center = tuple((unique[base][i]+unique[(base+1)%3][i])/2 for i in (0,1))
                    instance['tip'] = tip
                    instance['direction'] = (tip[0]-center[0],tip[1]-center[1])
        if clipped:
            issues.append(f'marker #{match[1]} artwork is clipped by its viewport/viewBox')
        if not instance['polygons']:
            issues.append(f'marker #{match[1]} has no measurable painted geometry')
        instance['bbox'] = bbox_of_points(p for poly in instance['polygons'] for p in poly)
        tangent = transform_point((point[0]+dx,point[1]+dy),edge.ctm)
        origin = instance['point']
        sign = -1 if position == 'start' else 1
        instance['expected_direction'] = (sign*(tangent[0]-origin[0]),sign*(tangent[1]-origin[1]))
        instances.append(instance)
    return instances, list(dict.fromkeys(issues))


def text_bbox(el):
    return bbox_of_points(pt for run in el.text_runs for pt in run['polygon'])


def css_block(css: str, selector: str) -> str | None:
    """Body of the first rule whose selector list matches ``selector`` exactly."""
    pattern = re.escape(selector) + r"\s*\{(.*?)\}"
    m = re.search(pattern, css, re.S)
    return m.group(1) if m else None


DARK_SELECTOR = 'svg, html[data-theme="dark"] svg, svg[data-theme="dark"]'
LIGHT_SELECTOR = 'html[data-theme="light"] svg, svg[data-theme="light"]'


def declared_vars(block: str) -> dict[str, str]:
    """``--name: value`` pairs declared in a CSS block body."""
    return {m.group(1): m.group(2).strip()
            for m in re.finditer(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", block)}


def strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def defined_classes(css: str) -> set[str]:
    """Class names that have at least one rule, ignoring comment prose."""
    body = strip_comments(css)
    # Only look at selector text, i.e. what precedes each '{'.
    selectors = re.findall(r"([^{}]+)\{", body)
    out: set[str] = set()
    for sel in selectors:
        out.update(re.findall(r"\.([A-Za-z][\w-]*)", sel))
    return out
