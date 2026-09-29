#!/usr/bin/env python3
"""Validate a generated architecture diagram HTML file.

    python3 scripts/validate.py diagram.html
    python3 scripts/validate.py diagram.html --strict   # warnings become errors

Exits 0 when clean, 1 when any error fires. Every check here is one that is
either invisible in a browser or only shows up after a theme toggle / an export —
the failures nobody catches by eye. What it cannot check for you: whether the
labels match the user's real system, and whether the light theme *looks* right.

Checks, grouped as in references/checklist.md:
  geometry  cumulative CTM, logical node contours, positioned text runs,
            edge overlap, marker instances, viewBox overflow, mask paint order
  theming   token-block parity, undefined vars, hardcoded colors, palette drift,
            undefined classes, WCAG contrast
  export    SRI hashes, style-inside-svg, required JS functions, no foreignObject
  structure report-container, pre-paint theme script, toolbar + print rule
  content   leftover template placeholders
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import math
import diagram_lib as L  # noqa: E402


class Reporter:
    """Collects findings so one run reports everything, not just the first fault."""

    def __init__(self, path: Path, strict: bool = False):
        self.path = path
        self.strict = strict
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.infos: list[str] = []
        self.checks = 0

    def info(self, msg: str, line: int | None = None) -> None:
        self.infos.append(f'{self.path}:{line or 1}: {msg}')

    def error(self, msg: str, line: int | None = None, hint: str = "") -> None:
        loc = f"{self.path}:{line}" if line else str(self.path)
        entry = f"{loc}: {msg}"
        if hint:
            entry += f"\n      -> {hint}"
        self.errors.append(entry)

    def warn(self, msg: str, line: int | None = None, hint: str = "") -> None:
        loc = f"{self.path}:{line}" if line else str(self.path)
        entry = f"{loc}: {msg}"
        if hint:
            entry += f"\n      -> {hint}"
        self.warnings.append(entry)

    def ok(self) -> bool:
        return not self.errors and not (self.strict and self.warnings)

    def report(self, quiet: bool = False) -> int:
        for e in self.errors:
            print(f"  ERROR  {e}")
        for w in self.warnings:
            print(f"  WARN   {w}")
        if not quiet:
            for info in self.infos:
                print(f"  INFO   {info}")
        n_e, n_w = len(self.errors), len(self.warnings)
        if self.ok():
            if quiet and not n_w:
                return 0            # nothing to say, so say nothing
            tail = f" ({n_w} warning{'s' if n_w != 1 else ''})" if n_w else ""
            print(f"\nOK  {self.path}{tail}")
            return 0
        print(f"\nFAILED  {self.path}  —  {n_e} error{'s' if n_e != 1 else ''}, "
              f"{n_w} warning{'s' if n_w != 1 else ''}")
        return 1


# ---------------------------------------------------------------------------
# Structure & export integrity
# ---------------------------------------------------------------------------

# Verified against the live CDN. To bump a version, recompute with:
#   curl -sL <url> | openssl dgst -sha384 -binary | openssl base64 -A
EXPECTED_SRI = {
    "html2canvas@1.4.1": "sha384-ZZ1pncU3bQe8y31yfZdMFdSpttDoPmOZg2wguVK9almUodir1PghgT0eY7Mrty8H",
    "jspdf@2.5.2": "sha384-en/ztfPSRkGfME4KIm05joYXynqzUgbsG5nMrj/xEFAHXkeZfO3yMK8QQ+mP7p1/",
}

REQUIRED_JS = ("applyTheme", "toggleTheme", "capture",
               "copyAsImage", "downloadPNG", "downloadPDF", "downloadSVG")

PLACEHOLDERS = ("[PROJECT NAME]", "[Subtitle description]", "[Additional metadata]",
                "[Project Name]", "Card Title 1", "Card Title 2", "Card Title 3",
                "Item one", "Item two", "[DIAGRAM TITLE]", "[DIAGRAM DESCRIPTION]")


def _balanced_block(src: str, at: int) -> str:
    """Text of the {...} block starting at or after ``at``, brace-matched.

    A plain ``[^}]*`` regex cannot be used for @media: it stops at the closing
    brace of the first nested rule.
    """
    start = src.find("{", at)
    if start < 0:
        return ""
    depth = 0
    for i in range(start, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start + 1:i]
    return src[start + 1:]


def check_structure(doc: L.DiagramDocument, r: Reporter, is_template: bool = False) -> None:
    src, js = doc.raw, doc.all_scripts

    if "report-container" not in doc.ids:
        r.error('id="report-container" is missing',
                hint="capture() measures that element; without it every export is blank.")

    # Themes are deliberately in-memory; no persistence is required in <head>.
    active_js = re.sub(r'/\*.*?\*/|(?m:^\s*//[^\n]*)', '', js, flags=re.S)
    if re.search(r'\b(localStorage|sessionStorage|indexedDB)\b|\bdocument\s*\.\s*cookie\b|\bcaches\s*\.', active_js):
        r.error('browser storage is forbidden; keep theme/export state in memory')
    css = doc.head_css + '\n' + doc.svg_css
    if re.search(r'fonts\.(?:googleapis|gstatic)\.com|@import\s+(?:url\()?\s*[\'\"]?https?://', src, re.I) or re.search(r'@font-face\s*\{[^}]*url\(\s*[\'\"]?https?://', css, re.I):
        r.error('external/network fonts are forbidden; use system monospace and local CJK fallback')
    families = re.findall(r'font-family\s*:\s*([^;}]+)', L.strip_comments(doc.svg_css))
    if families and not any(re.search(r'ui-monospace|SFMono-Regular|Menlo|Consolas|monospace', f, re.I) for f in families):
        r.warn('SVG uses non-monospace fonts; the 0.6em ASCII text estimate may differ')
    if is_template:
        system_mono = {'ui-monospace', 'sfmono-regular', 'menlo', 'consolas', 'monospace'}
        if not families or any(f.split(',')[0].strip().strip('\"\'').lower() not in system_mono for f in families):
            r.error('template SVG text must prefer system monospace before CJK fallback')

    if "toolbar" not in src:
        r.error(".toolbar markup is missing")
    m = re.search(r"@media\s+print", src)
    print_block = _balanced_block(src, m.end()) if m else ""
    print_rules = re.findall(r'([^{}]+)\{([^{}]*)\}', print_block)
    hides_toolbar = any('.toolbar' in [s.strip() for s in selectors.split(',')]
                        and re.search(r'display\s*:\s*none\s*!important', body)
                        for selectors, body in print_rules)
    if not hides_toolbar:
        r.error("the @media print rule hiding .toolbar is missing or altered",
                hint="Printing otherwise puts the export buttons in the PDF.")

    for fn in REQUIRED_JS:
        if not re.search(rf"function\s+{fn}\s*\(", js):
            r.error(f"required function {fn}() is missing")

    if "<foreignObject" in src or "<foreignobject" in src:
        r.error("<foreignObject> found — html2canvas renders it inconsistently",
                hint="Use <text> with explicit font-size instead.")

    # The SVG <style> must live inside the <svg>, never in <head>.
    if not doc.svg_css.strip():
        r.error("no <style> inside the <svg>",
                hint="html2canvas serializes the <svg> alone, so styling in <head> "
                     "never reaches the PNG. Move the theme tokens inside the <svg>.")
    for token in ("--frontend", "--c-mask"):
        if token in doc.head_css and token not in doc.svg_css:
            r.error(f"{token} is declared in <head> but not inside the <svg>",
                    hint="Exports would lose it. Duplicate the token block into the SVG.")

    # SRI drift.
    for tag in re.findall(r"<script\b[^>]*>", src):
        m = re.search(r'src="[^"]*?/npm/([^/"]+)/', tag)
        if not m:
            continue
        pkg = m.group(1)
        want = EXPECTED_SRI.get(pkg)
        got = re.search(r'integrity="([^"]+)"', tag)
        if want is None:
            r.warn(f"CDN script {pkg} is not one of the two pinned dependencies")
            continue
        if not got:
            r.error(f"{pkg} has no integrity= hash")
        elif got.group(1) != want:
            r.error(f"{pkg} integrity hash does not match the verified value",
                    hint=f"expected {want}")
        if 'crossorigin="anonymous"' not in tag:
            r.error(f"{pkg} is missing crossorigin=\"anonymous\"",
                    hint="SRI is not enforced without it.")

    if not is_template:
        for ph in PLACEHOLDERS:
            if ph in src:
                line = src[:src.index(ph)].count("\n") + 1
                r.error(f"leftover template placeholder {ph!r}", line)


def check_a11y(doc: L.DiagramDocument, r: Reporter) -> None:
    root = doc.svg_root
    if root is None:
        r.error("no <svg> element found")
        return
    if root.attrs.get("role") != "img":
        r.error('the <svg> needs role="img"', root.line)
    titles = [e for e in doc.svg_elements if e.tag == "title"]
    descs = [e for e in doc.svg_elements if e.tag == "desc"]
    if not titles or not titles[0].text.strip():
        r.error("the <svg> needs a non-empty <title>", root.line,
                hint="It is the accessible name; screen readers announce nothing without it.")
    if not descs or not descs[0].text.strip():
        r.error("the <svg> needs a non-empty <desc>", root.line,
                hint="One sentence summarising the topology.")
    labelled = root.attrs.get("aria-labelledby")
    if titles and descs and labelled:
        for ref in labelled.split():
            if ref not in doc.ids:
                r.error(f'aria-labelledby="{labelled}" points at unknown id {ref!r}', root.line)
    if "prefers-reduced-motion" not in doc.raw:
        r.warn("no prefers-reduced-motion block — the pulse dot animates regardless")


# ---------------------------------------------------------------------------
# Theming
# ---------------------------------------------------------------------------

HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b(?![0-9a-fA-F])")
FUNC_COLOR_RE = re.compile(r"\brgba?\s*\(")


def check_theming(doc: L.DiagramDocument, r: Reporter) -> None:
    css = doc.svg_css
    dark_body = L.css_block(css, L.DARK_SELECTOR)
    light_body = L.css_block(css, L.LIGHT_SELECTOR)

    if dark_body is None:
        r.error("the dark token block is missing from the SVG <style>",
                hint=f"expected selector: {L.DARK_SELECTOR}")
    if light_body is None:
        r.error("the light token block is missing from the SVG <style>",
                hint=f"expected selector: {L.LIGHT_SELECTOR}")
    if dark_body is None or light_body is None:
        return

    dark = L.declared_vars(dark_body)
    light = L.declared_vars(light_body)

    # 1. Parity. A var in one block only yields black shapes after a theme
    #    toggle — the bug nobody catches by eye.
    for name in sorted(set(dark) - set(light)):
        r.error(f"{name} is defined in the dark block but not the light block",
                hint="Shapes using it go unstyled in light mode. Add it to both.")
    for name in sorted(set(light) - set(dark)):
        r.error(f"{name} is defined in the light block but not the dark block",
                hint="Shapes using it go unstyled in dark mode. Add it to both.")

    # 2. Referenced but never declared.
    referenced = set(re.findall(r"var\((--[a-z0-9-]+)\)", css))
    for name in sorted(referenced - set(dark) - set(light)):
        r.error(f"var({name}) is referenced but declared in neither token block")

    # 3. No literal colors outside the two token blocks.
    rest = css.replace(dark_body, "").replace(light_body, "")
    rest = L.strip_comments(rest)
    for m in HEX_RE.finditer(rest):
        r.error(f"hardcoded color {m.group(0)} in the SVG <style> outside the token blocks",
                hint="Color must come from a CSS custom property or it is wrong in one theme.")
    if FUNC_COLOR_RE.search(rest):
        r.error("hardcoded rgb()/rgba() in the SVG <style> outside the token blocks",
                hint="Move it into both token blocks as a --var.")

    # 4. No presentation-attribute colors on shapes.
    for el in doc.svg_elements:
        for attr in ("fill", "stroke"):
            val = el.attrs.get(attr)
            if not val:
                continue
            if HEX_RE.search(val) or FUNC_COLOR_RE.search(val):
                r.error(f'inline {attr}="{val}" on <{el.tag}>', el.line,
                        hint="Use a semantic class; an inlined color is wrong in one theme.")

    # 5. Palette drift against components.md#choosing-a-type.
    for t in L.TYPES:
        for block, table, label in ((dark, L.DARK_STROKE, "dark"),
                                    (light, L.LIGHT_STROKE, "light")):
            got, want = block.get(f"--{t}"), table[t]
            if got is not None and got.lower() != want:
                r.error(f"--{t} in the {label} block is {got}, expected {want}",
                        hint="references/components.md is the authority for the palette.")

    # 6. WCAG contrast of every light accent against the light page.
    for t in L.TYPES:
        val = light.get(f"--{t}")
        if not val or not val.startswith("#"):
            continue
        ratio = L.contrast_ratio(val, L.LIGHT_PAGE)
        if ratio < L.MIN_CONTRAST:
            r.error(f"light --{t} ({val}) is {ratio:.2f}:1 on {L.LIGHT_PAGE}, "
                    f"below the {L.MIN_CONTRAST}:1 minimum",
                    hint="Drop one Tailwind step darker (e.g. lime-600 -> lime-700 #4d7c0f).")

    arrow_color = light.get('--c-arrow')
    if arrow_color and re.fullmatch(r'#[0-9a-fA-F]{6}', arrow_color) and L.contrast_ratio(arrow_color, L.LIGHT_PAGE) < L.MIN_CONTRAST:
        r.error('light --c-arrow contrast is below the 3:1 minimum')

    # 7. Every class used in markup must have a rule; a typo'd `node datbase`
    #    renders unstyled and looks merely 'plain' rather than broken.
    defined = L.defined_classes(css)
    for el in doc.svg_elements:
        for c in el.classes:
            if c not in defined:
                r.error(f"class {c!r} on <{el.tag}> has no CSS rule", el.line,
                        hint="A new component type needs .node.<name>, .t-<name> and "
                             ".arrow.<name> rules plus both token blocks.")

    # 8. Types must come from the fixed set; an 11th hue stops being
    #    distinguishable at a 1.5px stroke.
    for el in doc.svg_elements:
        cs = el.classes
        if "node" in cs and not any(t in cs for t in L.TYPES):
            r.warn(f"<{el.tag}> has class 'node' but no semantic type", el.line)


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

def _real_nodes(doc: L.DiagramDocument) -> list[L.SvgElement]:
    """Node shapes that participate in layout: no legend chips, no stack plates."""
    def marked(el):
        node = el
        while node is not None:
            if 'node' in node.classes:
                return True
            node = node.parent
        return False
    return [el for el in doc.rendered_elements
            if marked(el)
            and "legend-swatch" not in el.classes
            and "ghost" not in el.classes and 'mask' not in el.classes
            and el.tag in ("rect", "path", "polygon", "circle", "ellipse", "line", "polyline")]


def _node_box(el: L.SvgElement):
    """Bounding box of any node shape, whatever its geometry.

    Curves are flattened by diagram_lib.path_polylines, so a cylinder lid or a
    cloud lobe gets its true extent instead of a box drawn round the raw arc
    parameters.
    """
    return L.geometry_bbox(el)


def _is_closed(el: L.SvgElement) -> bool:
    """Can this shape be masked at all?

    A mask is an opaque copy painted underneath. That only works for a closed,
    filled outline: behind an actor's open shoulder arc — or behind a cylinder
    lid, which is deliberately ``fill:none`` — the copy shows as a visible box.
    """
    if el.tag in ("rect", "polygon", "circle", "ellipse"):
        return True
    if el.tag == "path":
        return ("z" in el.attrs.get("d", "").lower()
                or (el.value('fill', 'black') != 'none'
                    and any(len(poly) >= 3 for poly in L.element_polylines(el))))
    if el.tag == 'polyline':
        return el.value('fill', 'black') != 'none' and any(len(poly) >= 3 for poly in L.element_polylines(el))
    return False


def _text_hosts(boxes) -> list:
    """Node shapes that can host in-node text.

    Closed outlines only, and never a circle: an actor is labelled *below* the
    figure (components.md#shape-recipes, `actor`), so its head is not a text container.
    """
    return [(el, b) for el, b in boxes
            if el.tag in ("rect", "polygon", "path") and _is_closed(el)]


def _shape_kind(el: L.SvgElement) -> str:
    """``rect`` | ``hex`` | ``cloud`` | ``cylinder``, inferred from the geometry.

    The class carries the semantic *type* (`cloud`, `database`) and never the
    shape, so a `.node.cloud` is quite often a plain rect. Arc count is the
    discriminator: a cloud is three outward arcs with no straight run, a cylinder
    two arcs joined by two vertical sides.
    """
    owner = el.ancestor('data-shape')
    if owner:
        return owner.attrs['data-shape']
    if el.tag == "rect":
        return "rect"
    if el.tag == "polygon":
        return "hex"
    d = el.attrs.get("d", "").upper()
    return "cloud" if d.count("A") >= 3 and "V" not in d else "cylinder"


def _text_box(el: L.SvgElement):
    """Bbox of a `<text>`, honouring `text-anchor`. None if unmeasurable."""
    if el.text_runs:
        return L.text_bbox(el)
    tx, ty, fs = el.num("x"), el.num("y"), el.num("font-size")
    if None in (tx, ty, fs) or not el.text.strip():
        return None
    w = L.text_width(el.text.strip(), fs)
    anchor = el.value("text-anchor")
    left = tx - w / 2 if anchor == "middle" else (tx - w if anchor == "end" else tx)
    return L.transform_box((left, ty - .8*fs, left + w, ty + .2*fs), el.ctm)


def _is_actor_label(t: L.SvgElement, circles: list) -> bool:
    """Is this the label an actor hangs underneath itself?

    Centred on a head circle, below it. Those labels are wider than the figure by
    design, so they are exempt from the fit and overlap checks.
    """
    owner = t.ancestor('data-shape')
    if owner:
        return owner.attrs['data-shape'] == 'actor'
    tx, ty = t.num("x"), t.num("y")
    if None in (tx, ty):
        return False
    tx, ty = L.transform_point((tx, ty), t.ctm)
    return any(b and abs(tx - (b[0] + b[2]) / 2) <= 1 and b[3] < ty < b[3] + 90
               for _el, b in circles)


def _stack_mask_matches(mask: L.SvgElement, node: L.SvgElement) -> bool:
    """Is ``mask`` the documented backing shape for a ``stack``?

    A stack is three plates at 0/4/8px offsets, so its mask covers the whole pile
    — ``W + STACK_OFFSET`` by ``H + STACK_OFFSET`` at the front plate's origin —
    not the front plate alone. components.md#shape-recipes, `stack`.
    """
    if mask.tag != "rect" or node.tag != "rect" or mask.ctm != node.ctm:
        return False
    for attr in ("x", "y"):
        if mask.num(attr) != node.num(attr):
            return False
    if mask.attrs.get("rx") != node.attrs.get("rx"):
        return False
    for attr in ("width", "height"):
        mv, nv = mask.num(attr), node.num(attr)
        if mv is None or nv is None or abs(mv - nv - L.STACK_OFFSET) > 0.01:
            return False
    return True


class LogicalNode:
    def __init__(self, owner, shapes):
        self.owner, self.shapes = owner, shapes
        self.key = owner.attrs.get('data-node-id') or owner.attrs.get('id')
        self.kind = owner.attrs.get('data-shape', '')
        self.contours = [(s, p) for s in shapes for p in L.element_polylines(s)]
        self.closed = [(s, p) for s, p in self.contours if _is_closed(s)]
        self.box = L.bbox_of_points(p for _, poly in self.contours for p in poly)

    def contains(self, point, inset=0):
        return any(L.point_in_polygon(point, p, inset) for _, p in self.closed)

    def distance(self, point):
        return min((L.point_segment_distance(point, seg) for s in self.shapes
                    for seg in L.segments_of(s)), default=float('inf'))


def logical_nodes(doc):
    grouped = {}
    for el in _real_nodes(doc):
        owner = el.ancestor('data-node-id')
        if owner is None:
            ancestor = el.parent
            while ancestor and ancestor.tag != 'svg':
                if ancestor.tag == 'g' and 'node' in ancestor.classes:
                    owner = ancestor
                    break
                ancestor = ancestor.parent
        owner = owner or el
        grouped.setdefault(owner, []).append(el)
    for owner in doc.rendered_elements:
        if owner.tag != 'g' or not owner.attrs.get('data-node-id'):
            continue
        shapes = [e for e in doc.rendered_elements if e.tag in ('rect','path','polygon','circle','ellipse','line','polyline')
                  and e.ancestor('data-node-id') is owner
                  and not {'mask','arrow','legend-swatch'} & set(e.classes)]
        grouped[owner] = shapes
    return [LogicalNode(owner, shapes) for owner, shapes in grouped.items() if shapes]


def _arrows(doc):
    return [e for e in doc.rendered_elements if e.tag in ('line','path','polyline')
            and ('arrow' in e.classes or e.attrs.get('data-edge-id')) and 'legend-swatch' not in e.classes]


def _explicit_shared(a, b):
    """Pair-scoped opt-in; sharing a target NEVER grants an exemption by itself."""
    for attr in ('data-shared-route','data-junction'):
        value = a.attrs.get(attr)
        if value and value == b.attrs.get(attr) and value.lower() not in ('true','1','*'):
            return True
    return False


def _opaque_background(doc, el):
    """Conservative opacity check including composited parent group opacity."""
    parent = el
    while parent is not None:
        if parent.num('opacity') is not None and parent.num('opacity') < 1:
            return False
        parent = parent.parent
    if el.num('fill-opacity') is not None and el.num('fill-opacity') < 1:
        return False
    value = el.value('fill', 'black') or 'black'
    values = [value]
    ref = re.fullmatch(r'var\((--[\w-]+)\)', value)
    if ref:
        values = re.findall(re.escape(ref[1])+r'\s*:\s*([^;}]+)', doc.head_css+'\n'+doc.svg_css) or [value]
    for value in values:
        value = value.strip()
        if value in ('none', 'transparent') or value.startswith('url('):
            return False
        if value.startswith(('rgba(', 'hsla(')) or '/' in value:
            alpha = re.search(r'[,/]\s*([\d.]+)(%)?\s*\)$', value)
            if alpha and float(alpha[1])/(100 if alpha[2] else 1) < 1:
                return False
        if re.fullmatch(r'#[\da-fA-F]{8}', value) and value[-2:].lower() != 'ff':
            return False
    return True


def _covered_by_mask(doc, node, shape, edge):
    if edge.order < shape.order and _opaque_background(doc, shape):
        return True  # an opaque hand-drawn node is its own backing, no .mask needed
    for mask in doc.rendered_elements:
        if 'mask' not in mask.classes or not edge.order < mask.order < shape.order:
            continue
        if not _opaque_background(doc, mask):
            continue
        if mask.geom_key() == shape.geom_key() or _stack_mask_matches(mask, shape):
            return True
        if node.kind == 'stack' and mask.tag == 'rect' and node.box and mask.bbox() and L.box_contains(mask.bbox(),node.box,.01):
            return True
    return False


def _check_nodes(doc, nodes, arrows, r):
    for i,a in enumerate(nodes):
        for b in nodes[i+1:]:
            if not a.box or not b.box or not L.boxes_overlap(a.box,b.box):
                continue
            hit = any(L.polygons_overlap(pa,pb) for _,pa in a.closed for _,pb in b.closed)
            if not hit:
                hit = any(L.segment_hits_polygon(seg,poly) for s in a.shapes if not _is_closed(s)
                          for seg in L.segments_of(s) for _,poly in b.closed)
                hit |= any(L.segment_hits_polygon(seg,poly) for s in b.shapes if not _is_closed(s)
                           for seg in L.segments_of(s) for _,poly in a.closed)
                if not hit:
                    hit = any(L.segment_relation(sa,sb)[0] is not None
                              for ea in a.shapes if not _is_closed(ea) for sa in L.segments_of(ea)
                              for eb in b.shapes if not _is_closed(eb) for sb in L.segments_of(eb))
            if hit:
                r.error(f'node overlaps the node at line {b.owner.line}',a.owner.line)
    for node in nodes:
        for shape,poly in node.closed:
            for edge in arrows:
                if any(L.segment_hits_polygon(seg,poly,1.) for seg in L.segments_of(edge)) and not _covered_by_mask(doc,node,shape,edge):
                    r.error(f'arrow at line {edge.line} crosses node interior without an effective .mask (geometry/paint order)',shape.line,
                            hint='Paint the edge, then a matching opaque mask, then the node; or reroute.')
    shapes = [s for node in nodes for s in node.shapes]
    for mask in [e for e in doc.rendered_elements if 'mask' in e.classes]:
        if not any(mask.geom_key() == s.geom_key() or _stack_mask_matches(mask,s) for s in shapes):
            if not any(n.kind == 'stack' and n.box and mask.bbox() and L.box_contains(mask.bbox(),n.box) for n in nodes):
                r.warn('this .mask matches no node geometry',mask.line)


def _check_text(doc, nodes, arrows, r):
    runs = [run for el in doc.rendered_elements if el.tag == 'text' for run in el.text_runs]
    circles = [(s,L.geometry_bbox(s)) for n in nodes for s in n.shapes if s.tag == 'circle']
    for run in runs:
        el,root,poly,box = run['element'],run['root'],run['polygon'],run['bbox']
        owner = el.ancestor('data-node-id')
        host = next((n for n in nodes if n.owner is owner),None) if owner else None
        if host is None:
            host = next((n for n in nodes if n.kind != 'actor' and n.closed and n.contains(run['origin'])),None)
        actor_label = (host and host.kind == 'actor') or _is_actor_label(root,circles)
        if host and not actor_label:
            samples = poly + [((a[0]+b[0])/2,(a[1]+b[1])/2) for a,b in zip(poly,poly[1:]+poly[:1])]
            if not all(host.contains(p) for p in samples):
                r.error(f'text {run["text"]!r} overflows node outline horizontally or vertically',el.line,
                        hint='Approximate bounds (ASCII 0.6em/CJK 1em): adjust anchor, wrap or enlarge the shape.')
        for other in nodes:
            if other is host or not other.box or not L.boxes_overlap(box,other.box):
                continue
            if actor_label and any(s.tag == 'circle' for s in other.shapes) and not owner:
                continue
            if any(L.polygons_overlap(poly,p) for _,p in other.closed):
                r.error(f'text {run["text"]!r} overlaps unrelated node at line {other.owner.line}',el.line)
        for edge in arrows:
            if not any(L.segment_hits_polygon(seg,poly,.7) for seg in L.segments_of(edge)):
                continue
            # Text on a masked node is not actually crossed by the hidden edge.
            if host and all(_covered_by_mask(doc,host,s,edge) for s,_ in host.closed):
                continue
            backgrounds = [e for e in doc.rendered_elements if e.tag == 'rect' and edge.order < e.order < root.order
                           and _opaque_background(doc, e) and e.bbox() and L.box_contains(e.bbox(),box)]
            if not backgrounds:
                r.error(f'arrow at line {edge.line} crosses text {run["text"]!r}',el.line)
    for i,a in enumerate(runs):
        for b in runs[i+1:]:
            if L.polygons_overlap(a['polygon'],b['polygon'],.7):
                r.error(f'text {a["text"]!r} overlaps text {b["text"]!r} at line {b["element"].line}',a['element'].line)


def _check_edges(doc, nodes, arrows, r):
    segments = {e:L.segments_of(e) for e in arrows}
    markers = []
    for edge in arrows:
        instances,issues = L.marker_instances(doc,edge)
        markers.extend(instances)
        for issue in issues:
            if issue.startswith('unresolved '):
                r.warn(issue, edge.line)
            else:
                r.error(issue, edge.line)
        for instance in instances:
            if instance['position'] == 'mid':
                continue
            d,expected = instance['direction'],instance['expected_direction']
            if d and math.hypot(*expected):
                cosine = (d[0]*expected[0]+d[1]*expected[1])/(math.hypot(*d)*math.hypot(*expected))
                if cosine < .5:
                    r.error(f'marker orientation points away from the {instance["position"]} direction',edge.line)
                sw = edge.num('stroke-width') or 1
                a,b,c,d,_,_ = edge.ctm
                det = a*d-b*c
                if abs(det) < 1e-12:
                    continue
                local_tangent = ((d*expected[0]-c*expected[1])/det,
                                 (-b*expected[0]+a*expected[1])/det)
                length = math.hypot(*local_tangent)
                nx,ny = -local_tangent[1]/length*sw/2,local_tangent[0]/length*sw/2
                ox,oy = a*nx+c*ny,b*nx+d*ny
                px,py = instance['point']
                sides = [(px+sign*ox,py+sign*oy) for sign in (-1,1)]
                if not all(any(L.point_in_polygon(p,poly) for poly in instance['polygons']) for p in sides):
                    r.error('marker is too small or misreferenced to cover the line cap (shaft protrusion)',edge.line)
    for i,a in enumerate(arrows):
        for b in arrows[i+1:]:
            if _explicit_shared(a,b):
                continue
            overlap,crossing = 0.,False
            for sa in segments[a]:
                for sb in segments[b]:
                    kind,value = L.segment_relation(sa,sb)
                    if kind == 'overlap' and value > .5:
                        overlap = max(overlap,value)
                    elif kind == 'point':
                        ea = [segments[a][0][:2],segments[a][-1][2:]]
                        eb = [segments[b][0][:2],segments[b][-1][2:]]
                        common = any(math.dist(value,p)<.5 for p in ea) and any(math.dist(value,p)<.5 for p in eb)
                        if not common:
                            crossing = True
            if overlap:
                r.error(f'collinear edge overlap with line {b.line} ({overlap:.1f}px)',a.line,
                        hint='Reroute; intentional shared channels need the same non-boolean data-shared-route ID on both edges.')
            elif crossing:
                r.info(f'non-collinear edge crossing with line {b.line}; no junction semantics inferred',a.line)
    for instance in markers:
        owner = instance['edge']
        for edge in arrows:
            if edge is owner or _explicit_shared(owner,edge):
                continue
            point = instance['point']
            common = segments[edge] and any(math.dist(point,p)<.5 for p in (segments[edge][0][:2],segments[edge][-1][2:]))
            for seg in segments[edge]:
                if not any(L.segment_hits_polygon(seg,poly,.3) for poly in instance['polygons']):
                    continue
                # Only the contacting segment at the shared endpoint is exempt.
                if common and (math.dist(seg[:2],point)<.5 or math.dist(seg[2:],point)<.5):
                    continue
                r.error(f'edge passes through another marker on line {owner.line}',edge.line)
                break
        for node in nodes:
            if any(L.polygons_overlap(poly,outline,.5) and not _covered_by_mask(doc,node,shape,owner)
                   for poly in instance['polygons'] for shape,outline in node.closed):
                r.error(f'marker overlaps node outline at line {node.owner.line}',owner.line)
    _check_semantic_edges(nodes,arrows,segments,markers,r)
    return markers


def _check_semantic_edges(nodes, arrows, segments, markers, r):
    node_by_id = {n.key:n for n in nodes if n.key}
    if len(node_by_id) != sum(bool(n.key) for n in nodes):
        r.error('duplicate logical node IDs make edge endpoint metadata ambiguous')
    unchecked = 0
    for edge in arrows:
        source,target = edge.attrs.get('data-from'),edge.attrs.get('data-to')
        if not source and not target:
            unchecked += 1
            continue
        if not source or not target or source not in node_by_id or target not in node_by_id:
            r.error('edge data-from/data-to must reference existing logical node IDs',edge.line)
            continue
        if len(L.element_polylines(edge, world=False)) > 1:
            r.error('edge with data-from/data-to has multiple subpaths; semantic endpoints require a single subpath',edge.line,
                    hint='Split disconnected routes into separate edges with their own endpoint metadata.')
            continue
        segs = segments[edge]
        if not segs:
            r.error('edge has no non-zero path for its declared endpoints',edge.line)
            continue
        own = [m for m in markers if m['edge'] is edge]
        start_head = next((m for m in own if m['position']=='start'),None)
        end_head = next((m for m in own if m['position']=='end'),None)
        bidirectional = edge.attrs.get('data-bidirectional','false').lower() in ('true','1','yes')
        if not end_head:
            r.error('declared directed edge needs a valid marker-end',edge.line)
        if bidirectional and not start_head:
            r.error('declared bidirectional edge needs marker-start and marker-end',edge.line)
        if not bidirectional and start_head:
            r.error('marker-start conflicts with declared unidirectional edge',edge.line)
        for name,node_id,point,head,tangent in (
                ('from',source,segs[0][:2],start_head,(segs[0][0]-segs[0][2],segs[0][1]-segs[0][3])),
                ('to',target,segs[-1][2:],end_head,(segs[-1][2]-segs[-1][0],segs[-1][3]-segs[-1][1]))):
            node = node_by_id[node_id]
            tip = (head['tip'] or head['point']) if head else point
            distance = node.distance(tip)
            # Clearance tolerance permits ordinary manual ports; not tied to the
            # generator's fixed 10x8 heads. Wrong endpoints remain far away.
            if distance > 10 or node.contains(tip,1):
                r.error(f'data-{name} endpoint does not meet declared node {node_id!r} (outline distance {distance:.1f}px)',edge.line)
                continue
            d = head['direction'] if head and head['direction'] else tangent
            length = math.hypot(*d)
            if length:
                probe = (tip[0]+d[0]/length*(distance+2),tip[1]+d[1]/length*(distance+2))
                if node.closed and not node.contains(probe) and node.distance(probe)>node.distance(tip)+.5:
                    r.error(f'data-{name} marker/path direction points away from node {node_id!r}',edge.line)
    if unchecked:
        r.info(f'{unchecked} edge(s) have no from/to metadata: semantic direction was NOT validated')


def _check_frames(doc, nodes, r):
    bounds = [(e,L.geometry_bbox(e)) for e in doc.by_class('boundary',exclude=('legend-swatch',)) if not e.in_defs and not e.hidden]
    bounds = [(e,b) for e,b in bounds if b]
    for i,(ea,ba) in enumerate(bounds):
        for eb,bb in bounds[i+1:]:
            if not L.boxes_overlap(ba,bb):
                continue
            if all(abs(u-v)<.51 for u,v in zip(ba,bb)):
                r.error(f'this frame duplicates the frame at line {eb.line}',ea.line)
            elif not (L.box_contains(ba,bb) or L.box_contains(bb,ba)):
                r.error(f'frame partially overlaps the frame at line {eb.line}',ea.line)
    for chip in [e for e in doc.rendered_elements if 'legend-swatch' in e.classes]:
        cb = L.geometry_bbox(chip)
        if not cb:
            continue
        for bel,bb in bounds:
            if L.box_contains(bb,cb):
                r.error(f'legend chip is inside boundary at line {bel.line}',chip.line)
                break
        else:
            if bounds and cb[1]<max(b[3] for _,b in bounds)+L.LEGEND_GAP-.5:
                r.warn('legend is not below boundaries by LEGEND_GAP; verify intentional side-legend placement',chip.line)
    # The 40px grid is a generator convention, not a universal SVG validity rule.
    for i,a in enumerate(nodes):
        for b in nodes[i+1:]:
            if not a.box or not b.box or not a.owner.attrs.get('data-node-id') or not b.owner.attrs.get('data-node-id'):
                continue
            if abs(a.box[0]-b.box[0])<.5 and abs(a.box[2]-b.box[2])<.5:
                gap = max(a.box[1],b.box[1])-min(a.box[3],b.box[3])
                if 0<=gap<L.ROW_GAP-.5:
                    r.warn(f'aligned siblings have only {gap:g}px vertical gap (recommended {L.ROW_GAP})',a.owner.line)


def check_geometry(doc: L.DiagramDocument, r: Reporter) -> None:
    """Validate paint, not source-local bboxes; text/curves are static estimates."""
    nodes, arrows = logical_nodes(doc), _arrows(doc)
    _check_nodes(doc, nodes, arrows, r)
    _check_text(doc, nodes, arrows, r)
    markers = _check_edges(doc, nodes, arrows, r)
    _check_frames(doc, nodes, r)
    vb = doc.viewbox()
    if vb and vb[2] > 0 and vb[3] > 0:
        box = (vb[0], vb[1], vb[0]+vb[2], vb[1]+vb[3])
        for el in doc.rendered_elements:
            b = _text_box(el) if el.tag == 'text' else L.geometry_bbox(el)
            if b and not L.box_contains(box, b, .5):
                r.error(f'<{el.tag}> extends past the viewBox (bounds {b})', el.line)
        for instance in markers:
            if instance['bbox'] and not L.box_contains(box, instance['bbox'], .5):
                r.error('marker instance extends past the viewBox', instance['edge'].line)
    elif doc.svg_root:
        r.error('SVG needs a valid positive-size viewBox', doc.svg_root.line)
    for feature in sorted(doc.limitations):
        r.warn(f'<{feature}> is not resolved by the static geometry validator; verify in a browser')


def check_content(doc: L.DiagramDocument, r: Reporter) -> None:
    """Soft checks on whether the diagram says anything."""
    logical = logical_nodes(doc)
    nodes = [node.shapes[0] for node in logical]
    if not nodes:
        r.error("the SVG contains no .node shapes")
    if len(nodes) > 40:
        r.warn(f"{len(nodes)} nodes — past roughly 40 the diagram stops being readable")
    if not [el for el in doc.svg_elements if "arrow" in el.classes]:
        r.warn("no arrows: a diagram with no edges shows no relationships")
    thick = [el for el in doc.svg_elements if "thick" in el.classes
             and "arrow" in el.classes and "legend-swatch" not in el.classes]
    if len(thick) > 1:
        r.warn(f"{len(thick)} 'arrow thick' edges — at most one primary path, "
               "or the emphasis stops meaning anything")
    # The legend's own swatch for the 'highlight' modifier is required, so it must
    # not count toward the one-highlight-per-diagram rule.
    hl = [node for node in logical if 'highlight' in node.owner.classes
          or any('highlight' in shape.classes for shape in node.shapes)]
    if len(hl) > 1:
        r.warn(f"{len(hl)} highlighted nodes — two highlights highlight nothing")
    # A type used in the diagram but absent from the legend, and vice versa.
    used = {t for el in nodes for t in el.classes if t in L.TYPES}
    chips = [el for el in doc.svg_elements if "legend-swatch" in el.classes]
    if chips:
        shown = {t for el in chips for t in el.classes if t in L.TYPES}
        for t in sorted(used - shown):
            r.warn(f"type {t!r} is used but has no legend entry")
        for t in sorted(shown - used):
            r.warn(f"the legend lists {t!r} but no node uses it")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("file", type=Path, help="the generated .html diagram")
    ap.add_argument("--strict", action="store_true",
                    help="treat warnings as errors")
    ap.add_argument("--quiet", action="store_true",
                    help="print findings only, no header")
    ap.add_argument("--template", action="store_true",
                    help="lint resources/template.html itself: its [PROJECT NAME] "
                         "placeholders and example shapes are intentional, so the "
                         "placeholder and legend-coverage checks are skipped")
    args = ap.parse_args(argv)

    if not args.file.is_file():
        print(f"validate.py: no such file: {args.file}", file=sys.stderr)
        return 2

    try:
        source = args.file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"validate.py: cannot read {args.file}: {exc}", file=sys.stderr)
        return 2
    r = Reporter(args.file, strict=args.strict)
    try:
        doc = L.DiagramDocument(source)
        if not args.quiet:
            print(f"validating {args.file} "
                  f"({len(doc.svg_elements)} SVG elements, {doc.svg_count} <svg>)")

        check_structure(doc, r, is_template=args.template)
        check_a11y(doc, r)
        check_theming(doc, r)
        check_geometry(doc, r)
        if not args.template:
            check_content(doc, r)
    except L.GeometryError as exc:
        r.error(str(exc), exc.line)
    return r.report(quiet=args.quiet)


if __name__ == "__main__":
    sys.exit(main())
