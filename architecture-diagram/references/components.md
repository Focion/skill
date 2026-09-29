# Component Reference

Shapes, types, text and arrows. Coordinate math lives in layout.md.

## Choosing a type

Ten semantic types. Use the **class**; the values below are for auditing the SVG
`<style>` block, never for inlining.

| type | dark stroke / fill | light stroke / fill |
|---|---|---|
| `frontend` | `#22d3ee` / `rgba(8,51,68,.4)` | `#0891b2` / `rgba(6,182,212,.1)` |
| `backend` | `#34d399` / `rgba(6,78,59,.4)` | `#059669` / `rgba(16,185,129,.1)` |
| `database` | `#a78bfa` / `rgba(76,29,149,.4)` | `#7c3aed` / `rgba(139,92,246,.1)` |
| `cache` | `#e879f9` / `rgba(112,26,117,.4)` | `#c026d3` / `rgba(217,70,239,.1)` |
| `compute` | `#60a5fa` / `rgba(30,58,138,.4)` | `#2563eb` / `rgba(59,130,246,.1)` |
| `cloud` | `#fbbf24` / `rgba(120,53,15,.3)` | `#d97706` / `rgba(245,158,11,.12)` |
| `bus` | `#fb923c` / `rgba(251,146,60,.3)` | `#ea580c` / `rgba(249,115,22,.12)` |
| `security` | `#fb7185` / `rgba(136,19,55,.4)` | `#e11d48` / `rgba(244,63,94,.1)` |
| `observability` | `#a3e635` / `rgba(54,83,20,.4)` | `#4d7c0f` / `rgba(132,204,22,.14)` |
| `generic` | `#94a3b8` / `rgba(30,41,59,.5)` | `#475569` / `rgba(100,116,139,.1)` |

Dark mode: deep translucent fill, bright 400-weight stroke. Light mode: pale tint,
600-weight stroke against the `#f8fafc` page.

**Light-mode `observability` is lime-*700* `#4d7c0f`, not lime-600 — do not "fix" it.**
Every other light accent clears 3:1 against `#f8fafc` (amber-600 is the next closest at
3.04:1). Lime-600 `#65a30d` measures **2.95:1** and is the only one that fails; lime-700
measures 4.77:1. Reverting it silently breaks the WCAG check in `validate.py`.

### The palette stops at 10 on purpose

An 11th hue lands in the already-crowded blue/violet/fuchsia region and stops being
distinguishable at 1.5px stroke width. **For anything without a dedicated color, reuse a
type and reach for a different SHAPE.**

| thing | type | shape |
|---|---|---|
| LLM / managed AI API (OpenAI, Bedrock, Vertex) | `cloud` | `cloud` or `rect` |
| self-hosted inference / model server (vLLM, TGI, Triton) | `compute` | `rect` or `stack` |
| vector store (Pinecone, pgvector, Milvus, Qdrant) | `database` | `cylinder` |
| CDN / edge / WAF | `cloud` | `cloud` |
| WAF / edge when the *security* role is the point | `security` | `cloud` |
| message queue / topic / event bus / stream | `bus` | `hex` |
| firewall / NAT / network appliance | `security` | `rect` |
| object storage, managed (S3, GCS, OSS) | `cloud` | `cylinder` |
| object storage, self-hosted (MinIO, Ceph) | `database` | `cylinder` |
| metrics / logs / tracing / alerting | `observability` | `rect` |
| CI runner, batch worker, Lambda, K8s node pool | `compute` | `stack` |
| human user, third-party org | `generic` | `actor` |

Shape carries the "what kind of thing" axis and color carries the "which part of the
stack" axis. A violet cylinder is unambiguously a datastore whether it says `Aurora` or
`Milvus`; two new violets would be ambiguous forever.

### Never inline a hex

```svg
<!-- WRONG: correct in dark, invisible in light -->
<rect x="40" y="40" width="120" height="58" rx="6" fill="rgba(6,78,59,.4)" stroke="#34d399"/>

<!-- RIGHT -->
<rect class="node backend" x="40" y="40" width="120" height="58" rx="6"/>
```

Use semantic classes so both themes can change together. The validator checks
literal color usage and theme-variable consistency in the supported template
structure; it is not a complete CSS interpreter.

### Adding a genuinely new type

Prefer the ten supported types. The JSON generator rejects unknown types; adding
CSS alone does not extend its input enum. For an explicitly authorized manual
output, a new visual type needs both dark/light tokens, `.node.<name>`,
`.t-<name>`, `.arrow.<name>`, and matching end/start marker definitions and fills.
Keep the marker geometry in the Arrows section. Do not edit installed code,
resources or permissions merely to produce a diagram.

`validate.py` reports missing theme variables and undefined classes, but a pass
does not establish generator support or full browser/CSS compatibility.

## Shape recipes

Six JSON node shapes: `rect`, `cylinder`, `hex`, `actor`, `stack`, `cloud`.
`note`, `badge` and manually placed `step` circles are separate annotations.
Snippets below are geometry fragments, not standalone validated diagrams. Wrap
all parts of each node (shapes, text and badge) in a unique logical group:

```svg
<g data-node-id="gateway" data-shape="rect">
  <rect class="mask" x="220" y="40" width="110" height="58" rx="6"/>
  <rect class="node backend" x="220" y="40" width="110" height="58" rx="6"/>
  <text class="t" x="275" y="60" font-size="11" text-anchor="middle">API Gateway</text>
</g>
```

`W/H` come from the layout reference's approximate text sizing and port-capacity
expansion. Incoming and outgoing incidences both count. Resizable nodes can grow
in height; an actor has at most 2 ports per side and a cloud 3. Unsupported
capacity is an explicit generator error, not permission to merge edge routes.

When an edge passes under translucent fill, place a matching opaque `.mask`
**after the edge, before the node**. For non-rect shapes repeat their contour;
for a stack cover the full pile; do not mask an actor with a rectangle. The
static validator checks opacity and paint order as well as geometry. Generated
routes avoid unrelated nodes rather than relying on masks to hide them.

### `rect` — services, functions, generic components

The generator uses `rx="6"`, including after height expansion. A manual design
may choose a different radius, but its mask must match and ports must clear it.

```svg
<rect class="mask"          x="220" y="40" width="110" height="58" rx="6"/>
<rect class="node backend"  x="220" y="40" width="110" height="58" rx="6"/>
<text class="t"     x="275" y="60" font-size="11" text-anchor="middle">API Gateway</text>
<text class="t-sub" x="275" y="76" font-size="9"  text-anchor="middle">Kong · :443</text>
```

### `cylinder` — any datastore

Relational DBs, vector stores, object storage, warehouses. `ry = 8`. Body path plus a
`.node-lid` arc for the front lip; the lid is stroke-only, so it must be drawn **after**
the body or the body's fill covers it.

```
ry = 8
body = "M {x} {y+ry} V {y+H-ry} A {W/2} {ry} 0 0 0 {x+W} {y+H-ry} V {y+ry} A {W/2} {ry} 0 0 0 {x} {y+ry} Z"
lid  = "M {x} {y+ry} A {W/2} {ry} 0 0 0 {x+W} {y+ry}"
```

Sweep flag 0 travelling left→right bulges **downward**; travelling right→left it bulges
**upward**. That single fact is why both arcs in `body` use `0` and still close correctly:
the bottom arc is drawn L→R (bulges down, the visible front) and the top arc R→L (bulges
up, the visible back edge). Flip a flag and you get a bow-tie.

Worked, `x=390 y=40 W=160 H=58`:

```svg
<path class="mask" d="M 390 48 V 90 A 80 8 0 0 0 550 90 V 48 A 80 8 0 0 0 390 48 Z"/>
<path class="node database" d="M 390 48 V 90 A 80 8 0 0 0 550 90 V 48 A 80 8 0 0 0 390 48 Z"/>
<path class="node-lid database" d="M 390 48 A 80 8 0 0 0 550 48"/>
<text class="t"     x="470" y="68" font-size="11" text-anchor="middle">Milvus</text>
<text class="t-sub" x="470" y="84" font-size="9"  text-anchor="middle">vector · 768d</text>
```

Text sits `ry` lower than in a rect (name baseline `y + 20 + ry`) so it clears the lid.

### `hex` — queue, topic, event bus, stream

12px shoulders on each side.

```
points = "{x+12},{y}  {x+W-12},{y}  {x+W},{y+H/2}  {x+W-12},{y+H}  {x+12},{y+H}  {x},{y+H/2}"
```

Worked, `x=390 y=40 W=110 H=58` → `H/2 = 29`, so `y+H/2 = 69`:

```svg
<polygon class="mask" points="402,40 488,40 500,69 488,98 402,98 390,69"/>
<polygon class="node bus" points="402,40 488,40 500,69 488,98 402,98 390,69"/>
<text class="t"     x="445" y="60" font-size="11" text-anchor="middle">Kafka</text>
<text class="t-sub" x="445" y="76" font-size="9"  text-anchor="middle">orders.v1</text>
```

The 12px shoulders eat horizontal room, so add 24 to the width you computed from the text:
`W_hex = clamp(MIN_W, ceil_to_10(text_w + 2*PAD_X + 24), MAX_W)`.

### `actor` — human user or external organisation

Circle head `r=8` plus a shoulders arc; **label goes below the figure**, not inside it.
Total figure height 40, then the label block.

```svg
<circle class="node generic" cx="100" cy="50" r="8"/>
<path class="node generic" d="M 82 80 A 18 16 0 0 1 118 80"/>
<text class="t"     x="100" y="94"  font-size="11" text-anchor="middle">Users</text>
<text class="t-sub" x="100" y="110" font-size="9"  text-anchor="middle">Browser / Mobile</text>
```

Here `x=82, y=40, W=36`: head centre `(x+18, y+10)`, shoulder arc from `(x, y+40)` to
`(x+W, y+40)` with sweep 1 (L→R bulges up, giving a dome). The figure is only 36px wide but
`Browser / Mobile` at 9px is 86.4px, so **reserve the label width for column arithmetic**,
centred on `cx`: effective bbox `x = cx - 43.2` to `cx + 43.2`. Actors are the one shape
whose layout width is driven entirely by the label.

Never mask an actor — the arc is open and a mask rect would show as a box behind it.

### `stack` — multi-instance, replica set, node pool, autoscaling group

Two `.node.ghost` plates behind the real one. Draw back-to-front or the offsets vanish.

```
back  = (x+8, y+8)   mid = (x+4, y+4)   front = (x, y)     # all W x H
bbox  = x .. x+W+8,  y .. y+H+8         # reserve the extra 8px in both axes
mask  = (x, y, W+8, H+8)
```

Worked, `x=220 y=40 W=110 H=58`:

```svg
<rect class="mask" x="220" y="40" width="118" height="66" rx="6"/>
<rect class="node compute ghost" x="228" y="48" width="110" height="58" rx="6"/>
<rect class="node compute ghost" x="224" y="44" width="110" height="58" rx="6"/>
<rect class="node compute"       x="220" y="40" width="110" height="58" rx="6"/>
<text class="t"     x="275" y="60" font-size="11" text-anchor="middle">Workers</text>
<text class="t-sub" x="275" y="76" font-size="9"  text-anchor="middle">6 pods · HPA</text>
```

Two plates, not three: at 4px offsets a third is indistinguishable from the second.

### `cloud` — the internet, an external network, a managed edge

Three outward arcs on a flat base. The generator keeps a fixed 140×70 box and
at most three ports per side; it does not resize clouds for capacity. A manual
rescaling requires rechecking text, actual contours, ports and marker clearance.

```
d = "M {x+28} {y+70} A 28 22 0 0 1 {x+28} {y+26} A 30 26 0 0 1 {x+84} {y+18} A 32 32 0 0 1 {x+112} {y+70} Z"
```

All three arcs use sweep 1, which bulges outward for a clockwise traversal. Worked,
`x=200 y=40`:

```svg
<path class="mask" d="M 228 110 A 28 22 0 0 1 228 66 A 30 26 0 0 1 284 58 A 32 32 0 0 1 312 110 Z"/>
<path class="node cloud" d="M 228 110 A 28 22 0 0 1 228 66 A 30 26 0 0 1 284 58 A 32 32 0 0 1 312 110 Z"/>
<text class="t"     x="270" y="84"  font-size="11" text-anchor="middle">Internet</text>
<text class="t-sub" x="270" y="100" font-size="9"  text-anchor="middle">public</text>
```

Reserve `x .. x+140`, `y .. y+70`. Two limits, both from the outline rather than the bbox:

- **Every line at most 90px** (`CLOUD_LABEL_MAX`), name, sub and accent alike.
  The shape narrows above `y+40`; the rectangle's width is not usable text space.
  The generator enforces this estimate, and the static validator tests text
  against sampled outlines. Confirm font fallback and curved-edge clearance in
  a browser rather than relying on either estimate alone.
- **A name plus one more line, never two.** The third baseline lands at `y+75` on a shape
  that is 70px tall, i.e. below the flat base, drawing the accent in mid-air. If you need
  name + sub + accent, the thing wants `shape=rect`.

### `note` — annotation with a folded corner

Two paths: the outline with the corner cut, then the fold triangle. `.note` is styled as a
muted surface, so it never competes with a `.node`.

```
outline = "M {x} {y} H {x+W-14} L {x+W} {y+14} V {y+H} H {x} Z"
fold    = "M {x+W-14} {y} V {y+14} H {x+W}"
```

Worked, `x=600 y=300 W=160 H=52`:

```svg
<path class="note" d="M 600 300 H 746 L 760 314 V 352 H 600 Z"/>
<path class="note-fold" d="M 746 300 V 314 H 760"/>
<text class="t-sub" x="612" y="320" font-size="9">Cross-AZ replication</text>
<text class="t-sub" x="612" y="335" font-size="9">is async (RPO ~1s)</text>
```

Notes are left-aligned (no `text-anchor`), inset `PAD_X`+(-2) = 12 from the left edge.
Never route an arrow under a note; move the note instead.

Four lines maximum, and the row of notes wraps once it is as wide as the diagram
(layout.md#the-notes-row). A fifth line is a hard error rather than a silent truncation:
a note missing its last line still reads as a finished sentence.

### `badge` — status / version chip

Rides on the top-right corner of a node, lifted `BADGE_LIFT = 8` above its top edge.

```
W_badge = ceil_to_10(width_px(text, 8) + 2 * BADGE_PAD_X)   # text + 16
x = node.x + node.w - W_badge - 6,   y = node.y - 8
H = 16, rx = 8, text baseline = y + 11, centred
```

The chip is inset 6px from the front plate's right edge, including on stacks.
`W_badge` must fit `node_w - 12`; the generator rejects oversized badges rather
than allowing them to hang into the gap. It automatically reserves another 8px
of headroom when a first-row node has a badge. Badge text itself does not widen
the node; shorten it or use a sublabel/card.

Never on an `actor`: an open figure has no corner, and the label is already below it. Put
the fact in a sub line.

Worked, `healthy` at 8px is 4.20em = 33.6px:
`ceil_to_10(33.6 + 16) = 50px`.

```svg
<rect class="badge" x="460" y="44" width="50" height="16" rx="8"/>
<text class="t-badge" x="485" y="55" font-size="8" text-anchor="middle">healthy</text>
```

`deprecated` is 6.00em = 48px, so `ceil_to_10(48 + 16) = 70px`.
Recompute each string. The generator rejects a badge that exceeds its node's
budget; the static validator estimates text/outline overlap, not font shaping.

### `step` — numbered circle for sequence flows

```svg
<circle class="step" cx="190" cy="91" r="9"/>
<text class="t-step" x="190" y="94" font-size="8" text-anchor="middle">3</text>
```

`r=9` fits one or two digits; past 9 steps the number still fits but the diagram usually
shouldn't (layout.md#3-request-sequence-flow). Baseline is `cy + 3`, not `cy` — the
optical centre of an 8px digit sits ~3px below the geometric centre.

## Text inside a node

Prefer concise text. The generator accepts a name, up to three wrapped sub lines
and an optional accent (clouds are limited to two total lines). Move long detail
into summary cards rather than treating the maximum as a target.

```svg
<text class="t"          x="{cx}" y="{y+20}" font-size="11" text-anchor="middle">Order Service</text>
<text class="t-sub"      x="{cx}" y="{y+36}" font-size="9"  text-anchor="middle">Go 1.22 · :8080</text>
<text class="t-backend"  x="{cx}" y="{y+51}" font-size="8"  text-anchor="middle">3 replicas</text>
```

| line | class | font-size | baseline | carries |
|---|---|---|---|---|
| name | `t` | 11 (12 for a hero node) | `y + 20` | what the thing is called |
| sub 1 | `t-sub` | 9 | `y + 36` | runtime, port, protocol, version |
| sub n | `t-sub` | 9 | previous `+ LINE_H` (15) | more of the same |
| accent | `t-<type>` | 8 | previous `+15`, or name `+16` if there are no subs | one type-colored fact (domain, SLO, count) |

The first line after the name advances **16px**, whether it is a sub or accent;
each later line advances `LINE_H = 15`. These are the generator's explicit
baseline steps, not browser-measured text extents.

Font-size ladder: **12** hero/section names · **11** node names · **9** sublabels ·
**8** annotations, accents, badges, legend · **7** inline connector labels only.

`cx = x + W/2` with `text-anchor="middle"` for every in-node line. Boundary labels and
notes are the exceptions — they are left-aligned with no `text-anchor`.

**Prefer explicit geometry and font-size attributes for portable recipes.** The
static validator resolves common inherited font sizes, inline declarations and
simple CSS selectors, plus text/tspan positions and transforms. This is not a
complete cascade or text shaper. Complex CSS, per-glyph positions, nested SVG,
`use` and `textPath` need browser checks. Keep colors in semantic classes.
The template's system-monospace-first stack and local CJK fallback are offline;
0.6em Latin/1em full-width advances remain estimates, not guaranteed glyph widths.

The accent line must never carry information that isn't also available elsewhere: light-mode
accents clear 3:1 against `#f8fafc` but most do **not** clear the 4.5:1 small-text
threshold (cyan-600 3.52, emerald-600 3.60, orange-600 3.40, amber-600 3.04). Treat
`t-<type>` as emphasis, not as the only copy of a fact.

## Arrows

For a source contour at `x=330` and target contour at `x=390`:

```svg
<line class="arrow backend" x1="332" y1="69" x2="384" y2="69"
      marker-end="url(#arrowhead-backend)"
      data-edge-id="edge-0" data-from="client" data-to="gateway"
      data-bidirectional="false"/>
```

The referenced nodes must have matching `data-node-id` groups. Generated paths
use orthogonal `M`/`L` segments; a hand-authored straight edge may be a line.

| class | meaning |
|---|---|
| `arrow` | neutral connection, `--c-arrow` |
| `arrow <type>` | semantic color; JSON defaults to the target's type |
| `arrow dashed` | asynchronous or auth/token flow |
| `arrow dotted` | optional/conditional flow |
| `arrow thick` | primary request path; prefer at most one |
| `arrow thin` | secondary/inline connector; also accepted as a JSON style |

### Fixed marker geometry

| property | end marker | start marker |
|---|---|---|
| `markerUnits` | `userSpaceOnUse` | `userSpaceOnUse` |
| `viewBox` | `0 0 10 8` | `0 0 10 8` |
| width × height | 10 × 8 | 10 × 8 |
| `refX`, `refY` | 6, 4 | 4, 4 |
| triangle points | `0 0, 10 4, 0 8` | `10 0, 0 4, 10 8` |
| `orient` | `auto` | `auto` |

Each tip projects **4px** beyond the path endpoint toward its node. Target path
endpoints and bidirectional source endpoints are set back **6px**, leaving a
**2px tip-to-contour gap**. An ordinary source starts **2px** outside the contour.
These are user-space distances, independent of thick/thin stroke width. Ports
meet the actual shape contour, not a cloud/actor's rectangular layout envelope.

Use `arrowhead-{type}` / `arrowhead-start-{type}` for every semantic type,
including `generic`. The neutral aliases `arrowhead` / `arrowhead-start` are for
untyped `.arrow` elements, not `.arrow.generic`. Matching marker fills keep heads the same
semantic color as shafts in both themes. A start marker is a mirrored triangle;
reusing the end marker with `orient="auto"` points the wrong way.

For a bidirectional edge between the same `x=330`/`390` contours:

```svg
<line class="arrow database" x1="336" y1="163" x2="384" y2="163"
      marker-start="url(#arrowhead-start-database)"
      marker-end="url(#arrowhead-database)"
      data-edge-id="edge-1" data-from="primary" data-to="replica"
      data-bidirectional="true"/>
```

JSON `bidirectional` must be a boolean; `true` with `style="dashed"` is rejected.
Use explicit `true`/`false` strings for the emitted HTML data attribute. Missing
from/to metadata leaves semantic endpoint direction unvalidated; unknown IDs
are errors, and correct IDs cannot prove the business relationship itself.

Labels use `t-sub` at 9px, normally above/below a horizontal segment or beside a
vertical one. The generator searches positions after routing all edges, may
reroute onto a shelf and errors if no position clears other content. It emits
`data-edge-label="edge-N"` for label ownership. Manual labels also need checks
against nodes, text, lines and marker footprints.

Non-collinear crossings are permitted and reported as INFO, without junction
semantics. Unannotated collinear overlaps fail. The generator uses independent
tracks, not shared routes; the checklist documents the validator's explicit
manual-sharing exception and why it must not be used to hide routing defects.

**CSS beats presentation attributes:** `.arrow` and `.node` stroke widths are
CSS declarations. Use the `thin` class for secondary connectors and
`legend-swatch` for legend chips, not an overridden `stroke-width="1"` attribute.

## Modifiers

| modifier | renders as | earns its place when |
|---|---|---|
| `ghost` | very low opacity, no fill | it is a `stack` back plate. Nothing else — a ghost node reads as a rendering bug |
| `dimmed` | reduced opacity, still legible | the component is deprecated, planned, or explicitly out of scope, **and** the legend says which |
| `highlight` | thicker stroke + subtle glow | the user asked about one specific component and you are answering with the whole diagram; at most one node |
| `thin` | `stroke-width: 1` | inline gap connectors |

`dimmed` and `highlight` are claims about importance, so they need a legend entry or a
sublabel that says why. An unexplained dimmed node just looks like a mistake, and two
highlighted nodes highlight nothing.
