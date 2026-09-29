# Pre-Delivery Checklist

Run static checks, then browser and content review. `[static]` means the validator
has relevant checks within the limits below; it does **not** mean every failure
can be found statically or every item necessarily exits 1. `[review]` requires
human/browser evidence. Generated files also need both kinds of review.

## Start with the real result

```bash
# Absolute SKILL_DIR and OUT paths are defined in SKILL.md.
python3 -B "$SKILL_DIR/scripts/validate.py" "$OUT"
# Optional stricter acceptance:
python3 -B "$SKILL_DIR/scripts/validate.py" "$OUT" --strict
```

- Errors exit 1. Warnings normally exit 0, but exit 1 under `--strict`.
- INFO is non-failing even under strict; read it for crossings or missing edge
  semantics. `--quiet` suppresses INFO, not warnings/errors.
- Missing/unreadable input or CLI usage errors exit 2.
- Generator `--validate` checks **after** writing. A failed output remains on disk;
  inspect it, do not deliver it as passed. Regenerate to a fresh output path.

## Geometry and logical identity

- `[static/review]` All parts of each logical node are grouped with unique
  `data-node-id` and actual `data-shape`. Multi-shape actors, cylinders and stacks
  must not be mistaken for several components. Untagged manual nodes use
  heuristics and need closer inspection.
- `[static/review]` Check transformed node outlines, text and viewBox extents,
  including rear stack plates, note/legend text and instantiated markers. Curves
  and text are approximate; a clean exit is not proof of zero visual overlap.
- `[review]` Use the intended 40px sibling gap, accounting for full extents.
  Static short-gap warnings apply only to recognized aligned logical nodes.
- `[static/review]` Text fits actual outlines, not just bounding rectangles.
  Check text/tspan runs, vertical overflow, anchors, baselines and mixed CJK/Latin
  fallback. Clouds have at most two total lines, each at most 90px in generator
  estimates; a hex loses 24px to its shoulders.
- `[static/review]` No text obscures unrelated nodes, labels or visible edges.
  Generator labels are placed after all routes; manual labels need the same
  whole-diagram review.
- `[static/review]` Backings are opaque and geometrically matched, painted
  **edge → mask → shape → text**. An opaque shape may provide its own backing.
  Actor figures have no box mask; stacks need a backing for the full pile.
  Presence of `.mask` alone is not sufficient. Generated routes must still avoid
  unrelated nodes rather than relying on hidden crossings.
- `[static/review]` Boundaries are nested or disjoint, not duplicate/partially
  overlapping. Generator member-set checks reject nonmembers inside a frame;
  static HTML inspection cannot infer the user's intended membership.
- `[static/review]` Legend is below content, frames, channels and notes, normally
  by at least 20px. Inside-boundary chips fail; inadequate below-frame spacing
  may only warn. Review nonstandard side legends manually.

## Edges, ports and markers

- `[review]` Each source and destination has its own allocated port. Incoming,
  outgoing, reciprocal and parallel edges consume side capacity. Resizable node
  heights and gaps expand; actor/cloud capacities are 2/3 ports **per side**.
  No valid route/label/capacity means an explicit generator error, not permission
  to silently merge edges or invent an intermediate business component.
- `[static/review]` Edges carry `data-edge-id`, `data-from`, `data-to` and
  `data-bidirectional="true|false"`; labels use `data-edge-label`. Metadata IDs
  must refer to existing logical nodes. Endpoints and marker direction are
  checked against those nodes with tolerance, not exact generator-pixel equality.
- `[review]` Missing both from/to fields is INFO: **semantic direction was NOT
  validated**. Partial or unknown references are errors. Even valid metadata
  cannot establish that the named dependency is true in the user's system.
- `[static/review]` Non-collinear edge crossings are allowed (INFO), with no
  inferred junction. Unannotated collinear overlap is an error; sharing a target
  alone is not an exemption. The generator does not bundle edges.
- `[review]` The static validator has an explicit manual-sharing opt-in: a pair
  can share the same non-boolean `data-shared-route` or `data-junction` identifier
  (not `true`, `1` or `*`). It bypasses pairwise overlap/marker checks; use only
  for an intentionally documented shared route, never to hide accidental
  overlaps. It is not a JSON generator feature or proof of junction semantics.
- `[static/review]` Marker geometry includes `markerUnits`, viewBox scaling,
  reference point, orientation and child transforms. Check head/shaft connection,
  head/node overlap, other edges through heads and marker viewBox overflow.
- `[review]` Template contract: fixed 10×8 `userSpaceOnUse`, `viewBox="0 0 10 8"`,
  end reference `(6,4)`, start `(4,4)`. Tip projects 4px beyond the endpoint.
  Target and bidirectional-source path setback is **6px**, giving a **2px
  tip-to-node gap**; an ordinary source starts **2px** outside its contour.
  All semantic types, including generic, use `arrowhead-{type}` and
  `arrowhead-start-{type}`. Neutral aliases are for untyped `.arrow` only.
  Thick/thin does not resize heads.

## Theming, structure and accessibility

Before checking styling, review route economy: compare long connectors with the
Manhattan distance between their fixed endpoints, inspect avoidable bends, and
try sliding a label before sending a nearby relation around the whole graph.
Legitimate obstacles may require detours; no universal ratio is a correctness
rule. The default example's orders-to-Aurora route has a dedicated regression
for length, bend count and vertical extent, in addition to collision checks.

- `[static/review]` Preserve both SVG theme-token blocks and semantic classes;
  check missing variables, undefined classes, literal colors and contrast.
  Existing lime-700 `observability` in light mode is deliberate. Small accent
  text is emphasis, not the only place for important information.
- `[review]` Inspect both themes end to end. Refresh after a manual toggle:
  theme should resolve system preference again (dark fallback), not persist.
- `[static/review]` No browser storage or network fonts. System monospace comes
  before local CJK fallbacks. No Google Fonts. Text controls replace emoji.
- `[static/review]` Keep styles inside SVG and both HTML/SVG theme selectors.
  Preserve `report-container`, toolbar, print hiding and required export/theme
  functions. A validator token match does not prove full behavior.
- `[review]` Verify the system-preference script before first paint, HTML `lang`,
  SVG `role="img"`, `aria-labelledby` resolving to its own title/description,
  useful descriptions, keyboard controls, status announcements and reduced motion.
  Static checks cover only part of accessibility, not a complete audit.
- `[static]` No remaining project/title/card template placeholders. `--template`
  deliberately tolerates placeholders and skips content checks; do not use it
  to certify a finished diagram.
- `[review]` Disable JavaScript and confirm the diagram still renders. Toggles
  and exports need JavaScript. Theme state is in-memory, not browser storage.

## Export

- `[review]` Save standalone SVG offline and reopen it in both themes: styles,
  marker colors, current theme, local fonts, language and opaque background
  survive. It is the diagram only, not the surrounding report/cards.
- `[static/review]` Keep the original pinned html2canvas 1.4.1 and jsPDF 2.5.2
  jsDelivr URLs, SRI hashes and `crossorigin="anonymous"`. Static comparison is
  not evidence that the network loaded them in this run. Do not replace a CDN
  or install packages to simulate success.
- `[review]` PNG needs html2canvas. PDF needs both libraries and is a **single-page
  raster image**, not vector PDF. Network-blocked tests leave these end-to-end
  exports untested while HTML viewing and SVG download remain available.
- `[review]` Real raster capture should include the full horizontally scrolled
  content and report cards, with 32 CSS px padding at scale 2, no toolbar/status,
  and correct colors in both themes. Inspect right/bottom edges for clipping.
- `[review]` Capture expands only an offscreen clone. Check live page size,
  theme and scroll state before/after both successful and failed exports.
- `[review]` Clipboard needs secure context, supported APIs, user activation and
  permission. Test paste separately if allowed; never grant permissions just to
  claim success. Failure should leave readable feedback and an SVG alternative.

## Static validation limits

The parser handles common SVG paths (including relative/repeated commands),
cumulative transform matrices, supported primitive contours, grouped multi-shape
nodes, text/tspan runs and instantiated marker geometry. Definition-only shapes
are not treated as ordinary scene nodes. Text width uses approximate advances;
curves are sampled, not proven continuous collision-free geometry.

Simple type/id/class/descendant CSS and common inherited properties are handled,
not the complete browser cascade. Complex CSS, nested SVG viewports, `use`,
`textPath`, per-glyph coordinate/rotation lists, clipping/masking and complex/bidi
text shaping need browser review. Some unsupported constructs warn; absence of
a warning does not mean all unsupported features were detected. Neither static
nor browser geometry checks can infer business semantics from appearance.

## Content and delivery

- `[review]` Names, directions, member boundaries, ports, versions, counts and
  SLOs come from the user/evidence. The bundled example is fictional input;
  omit unknown facts rather than copying its operational claims.
- `[static/review]` Legend matches used types/styles/modifiers. Coverage warnings
  are conditional on legend chips existing; no legend is not universal proof of
  an error or a pass. Review unnecessary entries and ambiguous emphasis.
- `[review]` Update page title, subtitle, SVG title/description, cards and footer.
  `language` sets `lang`, not automatic translation of UI/legend/content.
- `[review]` Confirm a non-empty final HTML at a new approved absolute path.
  Report validation status and all untested browser/export items. Do not label
  partial checks as full acceptance. Leave source caches and `.claude` alone;
  exclude them from any separately authorized package.

## Regression commands

```bash
python3 -B -m unittest discover -s "$SKILL_DIR/tests" -p 'test_*.py'
# BROWSER_OUT: existing absolute directory outside the source tree.
node "$SKILL_DIR/tests/browser_check.cjs" "$BROWSER_OUT"
# Optional real-CDN checks, only when network access is authorized:
node "$SKILL_DIR/tests/browser_check.cjs" "$BROWSER_OUT" --online
```

The CLI exclusive-output regression is skipped by default. Set
`ROUTING_TEST_OUTPUT` to an existing approved directory outside the source to
enable it; it writes test HTML and a symlink there. Do not mistake a skipped
safety test for a passing one.

Use an existing Node.js and Chrome; `CHROME` overrides the standard macOS Chrome
path. No npm/pip installation. The smoke check targets the template and creates
artifacts plus an isolated browser profile in the supplied directory. It defaults
to offline; `--online` permits the two original CDN URLs. Missing CDN access and
system clipboard paste remain explicitly untested, never substituted with stubs.
Run browser review on the actual final diagram as well.

Regression fixtures must be shipped in the tests (in-memory inputs or bundled
fixed JSON), not read from a workspace `research` path. If a prerequisite is
missing, record the untested scope instead of installing or changing permissions.
