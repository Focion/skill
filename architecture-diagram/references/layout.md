# Layout Reference

Sizing and routing for architecture SVGs. Only `layered-horizontal` is generated;
other archetypes below are manual recipes. Use `python3 -B` with the absolute
paths defined in SKILL.md. Generated coordinates reduce manual work, but are not
a promise of a solution for every graph or correct rendering in every browser.

## Text width

`diagram_lib.text_width` estimates ordinary Latin advances at 0.6em and full-width
CJK at 1em. Mathematical alphanumeric symbols (U+1D400–U+1D7FF) use a conservative
1.2em budget because system monospace falls back to proportional math fonts.
For ordinary, uncombined characters outside that block:

```
width_px(s, fs) ≈ fs * sum(1.0 if EAW(c) in ('W', 'F') else 0.6)
```

Combining marks, variation selectors, joiners and format characters do not add
ordinary advances; joined clusters and regional-indicator pairs receive special
handling. This is not a font shaper. Ambiguous-width characters such as the
middle dot are estimated at 0.6em. Actual glyph fallback and baselines need a
browser. Fonts prefer `ui-monospace`, `SFMono-Regular`, `Menlo`, `Consolas`,
`monospace`, then local CJK fallbacks. No network fonts are required.

### Worked examples

| string | font size | estimated width | width + 28px padding |
|---|---|---|---|
| `API Gateway` | 11 | 72.6 | 100.6 |
| `API 网关` | 11 | 48.4 | 76.4 |
| `用户认证服务` | 11 | 66.0 | 94.0 |
| `消息队列 Kafka` | 11 | 83.6 | 111.6 |
| `Browser / Mobile` | 9 | 86.4 | 114.4 |

`API 网关`: four half-width characters including the space and two full-width
characters give `(4*0.6 + 2)*11 = 48.4px`.

### Sizing rule

```
text_w = max(estimated width of each rendered line)
W = clamp(MIN_W, ceil_to_10(text_w + 2*PAD_X + shape_extra), MAX_W)
shape_extra = 24 for hex; 0 for ordinary boxes
```

Names do not wrap automatically; move an overflowing name's detail into `subs`.
Sublabels accept a string or up to three strings; wrapping must still result in
at most three sub lines. An accent is a separate 8px line. At `MAX_W=220`, rect
text has 192px: about 29 Latin/17 full-width characters at 11px, 35/21 at 9px,
or 40/24 at 8px. A hex loses another 24px to shoulders. A cloud is fixed 140×70,
with a name plus **one** sub or accent, each at most 90px wide. Actors reserve
the label width, not just their 36px figure. Prefer concise text even when more
lines technically fit.

## The grid

| constant | value | use |
|---|---|---|
| `MARGIN` | 40 | content-to-viewBox reserve |
| `COL_GAP` | 60 | minimum column gap; routing may expand it |
| `ROW_GAP` | 40 | sibling gap after full shape extent |
| `PAD_X`, `PAD_Y` | 14, 10 | box text insets |
| `MIN_W`, `MAX_W`, `MIN_H` | 110, 220, 50 | ordinary box limits before port sizing |
| `NAME_FS`, `SUB_FS`, `TINY_FS` | 11, 9, 8 | name, sublabel, accent/legend |
| `NAME_BLOCK`, `NAME_TO_SUB`, `LINE_H` | 22, 16, 15 | text sizing/baseline steps |
| `CHANNEL_GAP` | 22 | exterior lane pitch |
| `GROUP_PAD`, `GROUP_LABEL_H` | 18, 20 | boundary inset/headroom |
| `GUTTER` | 18 | track reserve outside a column envelope |
| `FAN_STEP`, `PORT_STEP` | 12, 12 | separate vertical tracks and side ports |
| `LABEL_PAD`, `ROUTE_CLEARANCE` | 4, 2.5 | label and route clearance |
| `ARROW_STANDOFF` | 6 | setback at arrowhead-bearing path endpoints |

These routing constants are used by `build_diagram.py`. Legacy corner constants
in the shared library do not imply rounded generator routes: the current
renderer emits orthogonal `M`/`L` paths, not Q-cornered elbows.

### Node height

For ordinary boxes, before port sizing:

```
H_raw = NAME_BLOCK + LINE_H*(sub_line_count + bool(accent)) + 2*PAD_Y
H = ceil_even(max(MIN_H, H_raw))
```

No subs/accent gives 50px; one sub 58px; one sub plus accent 72px. Cylinders add
16px for curved ends. Stacks reserve another 8px beyond front-plate width/height.
Actor height includes the 40px figure and labels below; cloud height stays 70px.

For each resizable side with `n` incident edges:

```
H >= ceil_even((n-1)*PORT_STEP + 32)
```

Both sides are checked. Reciprocal and parallel edges remain distinct, each
consuming a source and destination port. Height has no fixed 102px maximum after
capacity expansion.

### Column and row advance

```
col_w[i] = max(full node width, including stack offsets, in tier i)
gap_width[g] = max(60, 2*18 + max(0, track_count[g]-1)*12 + label_room[g])
label_room[g] = max(label_width + 16 for incident labels, default=0)
x[i+1] = x[i] + col_w[i] + gap_width[i+1]
y[j+1] = node[j].bottom + ROW_GAP
```

The first column gains boundary reserve and left-track space when needed.
Shorter tiers are vertically centered against the tallest tier. Ordinary nodes
are left-aligned; actors are centered. The viewBox includes routes, labels, notes
and legend plus margin, rounded up to multiples of 10. It is not fixed at 1200px.

### Worked 3-tier example

For a manual baseline with widths `[120,110,160]`, 60px gaps and no boundaries,
column starts are `[40,220,390]`. Two 58px nodes per column start at `y=40,138`,
with centers `69,167`. Adding edges to JSON can expand gaps or redistribute ports.

For a single edge from a rect ending at `x=330` to one starting at `x=390`,
ordinary source is `332`, target path end `384`, and target marker tip `388`:

```svg
<line class="arrow database" x1="332" y1="69" x2="384" y2="69"
      marker-end="url(#arrowhead-database)"
      data-edge-id="edge-0" data-from="gateway" data-to="store"
      data-bidirectional="false"/>
```

This assumes matching `gateway`/`store` node groups and unchanged template
markers. Curved shapes require ports on their actual contour, not these numbers.

## Vertical stacking and the gap rule

Use 40px between full sibling extents, including rear stack plates. Port-driven
height expansion happens before stacking. A 20px inline annotation may fit in
the gap with 10px clearance each side; a full hex needs a row/column of its own.
The validator warns about short gaps for recognized aligned logical nodes.
40px is a design convention, not universal SVG validity or a guaranteed check
for all manual layouts.

## Painting order and masks

SVG paints in document order:

1. Grid/background and optional lanes.
2. Boundaries outermost first, then headings.
3. All edges and their labels.
4. Per logical node: opaque backing, shape(s), text, badge.
5. Notes/manually placed steps; legend last.

Wrap parts in `<g data-node-id="..." data-shape="rect">` with the actual shape
and a unique node ID. This keeps multi-shape cylinders, actors and stacks one
logical component. A `.mask` is an opaque backing shape, not an SVG `<mask>`.
Repeat rect `x/y/width/height/rx`, or the path/polygon contour. A stack uses one
`(W+8)×(H+8)` backing; an actor has no rectangular mask.

For a manual edge under translucent fill, the matching opaque mask must paint
**after the edge and before the shape**. An opaque shape can itself be backing.
Static checks examine geometry, opacity and order, not mere class presence.
Generated routes still avoid unrelated nodes; hiding a route does not make its
relationship correct.

## Boundaries and nesting

| class | meaning | dash | label type |
|---|---|---|---|
| `boundary region` | region/account/datacenter | `8,4` | `cloud` |
| `boundary vpc` | VPC/VNet | `10,5` | `compute` |
| `boundary az` | availability zone | `6,3` | `generic` |
| `boundary sg` | security group/subnet | `4,4` | `security` |

Member sets must be disjoint or strictly nested; identical/partially intersecting
sets fail. Members must also be contiguous in the picture: a rectangular frame
cannot exclude a bystander inside it. Reorder nodes or shorten a label when its
frame covers a nonmember.

For an innermost frame `d=0`. The implementation computes `d` as the **number of
declared strict-subset boundaries inside it**, not always the longest nesting
chain. These coincide for a chain but can differ for sibling subframes. With
member bbox `(mx,my,mr,mb)`:

```
inset = 18 + 10*d
x = mx-inset; y = my-inset-20*(d+1)
w = max(mr-mx+2*inset, text_width(label,10)+24)
h = mb-my+2*inset+20*(d+1)
```

Label: `x+12,y+14`, 10px semibold. Global `D=max(d)+1` gives top reserve
`18+10*(D-1)+20*D`, left reserve `18+10*(D-1)`. No boundaries means no reserve.
For a three-frame chain the top reserve is 98px. Inspect sibling-frame output;
this heuristic is not a general containment solver.

### When the label is wider than the frame

Long labels widen frames; enclosing frames gain child right-edge space plus
10px. The generator checks nonmembers after widening. Do not let labels
float beyond frames or accept partial frame overlap. The static validator checks
duplicate/partial overlaps, but cannot infer intended membership from an
arbitrary manual picture.

## The notes row

Notes sit below body/routes and above legend with 20px separation. Each accepts
a string or one to four pre-split lines; text inside a note does not auto-wrap.

```
w = ceil_to_10(max(text_width(line,9)) + 2*12 + 14)
h = 15*line_count + 20
advance_x = w + 40
available_row_width = max(content_right-MARGIN, 600)
```

The **row of notes** wraps at that available width. One very wide note can still
widen the diagram. Empty arrays and more than four lines are rejected.

## Badges

```
badge_w = ceil_to_10(text_width(text,8) + 16)
badge_x = node.x + node.w - badge_w - 6; badge_y = node.y - 8
height = 16; rx = 8; text_baseline = badge_y + 11
```

A badge must fit `node.w-12`. It is inset 6px from the right edge and rides a
stack's **front** plate, not the rear extent. Reserve 8px above the first row.
Actors reject badges; use a sublabel.

## Legend placement

Place the legend 20px below body, frames, routes, labels and notes. Use
`legend-swatch` 16×10 chips and 8px text at `top+8`; wrapped rows have 16px pitch.
Include its actual rightmost text and bottom row in the viewBox. The generator
uses at least 600px available row width and deduplicates node types, non-solid
edge styles, boundary kinds and modifiers. A solid edge is not a separate entry.
Automatic legend labels remain English regardless of HTML language. Set JSON
`legend:false` only when clear; missing legends are not always diagnosed.

## Routing channels

Budget **all endpoint incidences**, not just outgoing edges. Each endpoint gets
a distinct side port and vertical escape track.

| tier difference | source side | target side | available local/exterior routes |
|---|---|---|---|
| adjacent forward `+1` | right | left | gap elbow; straight if actual port heights match |
| same tier `0`, different nodes | right | right | right gutter |
| forward skip `>1` | right | left | short local tracks or lane above frames |
| backward `<0` | left | right | short local tracks or lane below frames |

Ports per side are ordered by the other node's vertical position, then edge
index. Safe bands: actor `y+27..39` (**2 ports**), cloud `y+30..62` (**3 ports**),
resizable boxes `y+16..y+H-16`. Incoming and outgoing incidences share a side's
capacity. Fixed-shape excess is a hard error; choose an appropriate resizable
hub rather than clamping or merging ports.

Actors attach to the shoulder arc, clouds to ellipse intersections, hexes to
sloping sides, stacks to the union of plates. Never attach to the label box or
a curved shape's rectangular layout envelope.

### Marker setback

Markers: `markerUnits="userSpaceOnUse"`, `viewBox="0 0 10 8"`, size 10×8.
End reference `(6,4)`, mirrored start reference `(4,4)`. Each tip projects **4px**
beyond its path endpoint toward the node. Set arrowhead-bearing endpoints back
**6px**, leaving a **2px tip-to-contour gap**. An ordinary source starts **2px**
outside its contour. Subtract the setback on a left side; add it on a right
side. Bidirectional edges use 6px at both ends. First/last tangents stay
horizontal, out of the allocated side when viewed toward the route interior.

Semantic marker pairs match every edge type, including generic:
`arrowhead-{type}`/`arrowhead-start-{type}`. Neutral `arrowhead`/`arrowhead-start`
are only for untyped `.arrow` elements. Thick strokes do not resize markers.
Do not reuse the end triangle at the start with
`orient="auto"`; it needs the mirrored triangle.

### Reserved channels

```
frames_top = 40 + tier_label_h + (18 if forward_count else 0) + forward_count*22
forward_y(k) = frames_top - (k+1)*22
backward_y(k) = max(node_bottoms, frame_bottoms) + (k+1)*22
```

`tier_label_h` is 18 if any tier is labeled, otherwise zero. First-row badges add
8px to node placement. Skip/return edges initially receive separate lanes.
Actual port heights are preserved even for tiny offsets: no mean-y flattening
or 24px elbow threshold is used in the current generator.

Bounded candidates include single-track routes, local y tracks and exterior
shelves. Rank them by L1 length + `FAN_STEP × bends` + twice the outward extent
beyond stationary content, then select the lowest-cost feasible route. An
exterior lane is an alternative, not a mandate to circle the whole graph.
Checks include nodes, future endpoint stubs/markers, parallel runs and placed
labels. Non-collinear crossings are allowed without a routing-cost penalty;
collinear or visually merged parallel spans are not bundled. If no candidate
works, return a `SpecError`. There is no self-loop routing, global shortest-path
guarantee, complete graph-layout guarantee or external-engine fallback.

### Where the label goes

Labels are placed **after all edges**. First slide along the original segments:
try middle, ends and bounded nearby positions, above/below horizontal segments
or beside vertical ones, with small perpendicular offsets. Candidates clear
nodes, badges, headings, boundary labels, other labels, all edges and marker
envelopes. Only when no local label position works, compare alternative routes
by the same geometry cost and choose one that also fits the label. Exterior
shelves are a last resort, not the immediate response to an obstructed midpoint.
Failure is explicit: shorten text, move detail into a note, or reorder nodes.
After labels settle, recompute actual content bounds before placing notes and
the legend, so unused reservations do not leave empty space. Review long detours
and bend counts as well as collisions; a static pass alone is insufficient.

## The 5 layout archetypes

These are communication patterns, not five generator modes.

### 1. Layered horizontal

Request paths: client → edge → service → data. The only generated layout. Start
with the grid but allow tracks, ports and labels to expand dimensions. Many
tiers produce a wide scrollable SVG; split a large system rather than shrinking
text beyond readability.

### 2. Layered vertical (lane bands)

Manual presentation/application/domain/data layers. Full-width lanes reserve
label headroom plus the tallest node; keep 40px between bands and center each
node row. Distinguish actors, external systems and the software-system boundary
for a C4-style view; a lane alone does not establish C4 semantics.

### 3. Request sequence flow

Manual ordered story: participants in a row, separated routes and numbered
`.step` circles (`r=9`, 8px text baseline `cy+3`). There is no generator step
field. Put returns below content. Many repeated visits/steps are better served
by a dedicated sequence representation; do not invent order or concurrency.

### 4. Data pipeline

Source → ingest → transform → store → serve can use the horizontal generator
when expressed as tiers. Label edges with known formats/rates. Full hex buses
need columns; cylinders denote storage. Branches need distinct ports and lanes.
Differentiate batch/streaming only when factual, and avoid emphasizing all edges
as the primary path.

### 5. Network topology

Containment-first manual views may mirror AZs/subnets, derive member frames and
route replication outside them. Tier-compatible containment can use the
generator. Symmetric dimensions do not prove equal capacity. Preserve known
peerings, firewall scopes and directions rather than inferring them from
proximity.

## Static and browser review

Static coverage includes paths, cumulative transforms, multi-shape nodes,
approximate text/tspan runs, marker footprints and mask order. Curves are
sampled; text is estimated. Complex CSS, per-glyph positioning, nested SVG,
`use`, `textPath`, clipping and complex shaping need a browser. Without from/to
metadata there is no endpoint-semantic guarantee; metadata cannot prove the
business relationship itself. Run validation and the checklist linked from
SKILL.md, not just a visual glance or an exit-code assertion.
