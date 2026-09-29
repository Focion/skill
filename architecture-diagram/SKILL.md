---
name: architecture-diagram
name_en: Architecture Diagram
name_zh: 架构图
version: 2.1.1
description: Create offline-viewable HTML and SVG architecture diagrams from a JSON spec or a hand-authored template, with in-memory light/dark themes and conditional PNG/PDF/clipboard export. Use for system, cloud, security, data-pipeline and network topology diagrams.
description_en: Create offline-viewable HTML and SVG architecture diagrams from a JSON spec or a hand-authored template, with in-memory light/dark themes and conditional PNG/PDF/clipboard export. Use for system, cloud, security, data-pipeline and network topology diagrams.
description_zh: 根据 JSON 规格或手工模板创建可离线查看的 HTML 与 SVG 架构图，支持仅在内存中切换明暗主题，以及有条件的 PNG、PDF 和剪贴板导出。适用于系统、云、安全、数据流水线和网络拓扑图。
argument-hint: Describe the components, connections, boundaries, label language and a new output path, or provide a JSON spec
argument-hint-en: Describe the components, connections, boundaries, label language and a new output path, or provide a JSON spec
argument-hint-zh: 描述组件、连接、边界、标签语言和新的输出路径，或提供 JSON 规格
user-invocable: true
---

# Architecture Diagram Skill

Produce one `.html` file with inline SVG, embedded CSS, light/dark themes and an export toolbar. No build step or external images. Viewing and SVG download work offline; raster exports have separate dependencies.

> **Upstream Version 2.1** · MIT License · Originally authored by [Cocoon AI](mailto:hello@cocoon-ai.com)

Local revision **2.1.1** synchronizes routing, static validation, offline/export behavior and bilingual metadata. It preserves the upstream attribution and license declaration without claiming new upstream authorship or additional licensing permission.

## Pick a path

**A. Generator — default for tiered topologies.** Write a JSON spec; the generator sizes nodes, allocates ports at both ends, reserves routing space and places labels. Only `layered-horizontal` is generated. Unplaceable inputs are rejected; there is no guarantee of a solution for every graph. Always validate and review the result.

```bash
# Set these to the installed skill and user-approved absolute paths.
SKILL_DIR="/absolute/path/to/architecture-diagram"
SPEC="/absolute/path/to/spec.json"
OUT="/absolute/path/to/new-diagram.html"
python3 -B "$SKILL_DIR/scripts/build_diagram.py" "$SPEC" -o "$OUT" --validate
```

Start from the [example](resources/spec.example.json) and [JSON Schema](resources/spec.schema.json). The example's services, replica counts and SLOs are illustrative, not facts about the user's system. Required: `title`, non-empty `tiers`, and each node's unique `id` and `name`. `layout` defaults to `layered-horizontal`; optional `language` defaults to `zh-CN` and sets HTML `lang`. It does **not** translate labels, the Chinese toolbar or the English automatic legend. `legend` and `bidirectional` require JSON booleans, not strings/numbers. Self-loops are unsupported; no external layout engine is used.

**B. Hand-authored template — for bespoke layouts.** Copy the [template](resources/template.html) to a new approved output path and edit that copy, not the installed template. Read [layout](references/layout.md) before placing coordinates. Lane bands, sequence flows, mirrored zones and unusual nesting are manual recipes, not extra generator modes.

```bash
python3 -B "$SKILL_DIR/scripts/validate.py" "$OUT"
```

Both paths share theme tokens, markers, CSS and export scripts. The generator replaces the `GEN:CONTENT` and `GEN:CARDS` regions **plus** the viewBox, HTML language, accessible title/description and header/footer placeholders. Not everything outside those markers is copied byte-for-byte; the pinned CDN tags and SRI hashes remain unchanged.

## Scripts and failure handling

| File | Contract |
|---|---|
| [build_diagram.py](scripts/build_diagram.py) | Spec → HTML. `-o/--output` defaults to `diagram.html`; `--validate` runs static checks; `--strict` implies validation and fails on warnings; `--template PATH` selects a custom template; `--quiet` suppresses normal output. |
| [validate.py](scripts/validate.py) | Structure, accessibility, theme, geometry and content checks. `--strict` fails on warnings; `--quiet` suppresses normal output/INFO. `--template` tolerates placeholders and skips content checks, not geometry checks. |
| [diagram_lib.py](scripts/diagram_lib.py) | Shared approximate text measurement, paths, transforms, text runs and marker geometry. Import only. |

Python tools use only the standard library. Use `python3 -B` to avoid creating bytecode caches; do not install dependencies.

- **Generator 0:** generated, and any requested validation passed. Without `--validate`, this is not a validation result.
- **Generator 1:** caught spec/layout/template-substitution errors, or failed validation (warnings too with strict). Invalid booleans and unsupported layouts are spec errors.
- **Generator 2:** unreadable/missing input or template, malformed JSON or non-object top level, output conflict/write failure, or CLI usage error. Not every input failure exits 1.
- **Validator:** 0 for no errors (warnings allowed unless strict), 1 for failed checks, 2 for missing/unreadable input or CLI usage errors. INFO never fails, even with strict.

The generator uses exclusive output creation (`open("x")`), refuses existing files/symlinks and does not create parent directories. Verify the parent and choose a new path. Validation runs **after writing**; failed validation leaves the output for inspection, not delivery as a validated result. Read the diagnostic, fix only within the agreed scope and retry with a new path. Do not overwrite, delete, install engines, bypass permissions or retry indefinitely. Unexpected exceptions are not a documented diagnostic contract. If a command times out or the user stops the task, stop work and do not automatically resume. Preserve partial artifacts as unverified, report the last completed step and pending checks, and wait for an explicit continuation request.

## Geometry and SVG invariants

1. **Logical identity:** node shapes, text and badge belong to `<g data-node-id="..." data-shape="...">`. Each edge carries `data-edge-id`, `data-from`, `data-to`, `data-bidirectional="true|false"`; its label uses `data-edge-label`. Edge IDs (`edge-0`, etc.) are generated from input order, not spec fields.
2. **Capacity at both ends:** incoming, outgoing, reciprocal and parallel edges all consume side ports. High-degree resizable nodes gain height, and column gaps expand for tracks/labels. Actors have **2 ports per side**, clouds **3**; excess capacity is an explicit error, not a clamped overlap.
3. **Crossings versus overlap:** non-collinear crossings are allowed and reported as INFO, with no inferred junction. Unannotated collinear overlap fails. The generator never bundles edges; see the [checklist](references/checklist.md) for the static validator's explicit hand-authored sharing exception. Rank feasible routing candidates by length, bend count and exterior detour. Slide labels along the original route before rerouting; an obstructed midpoint is not a reason to circle the entire graph. Review excessive detours even when static validation passes.
4. **Marker geometry:** `markerUnits="userSpaceOnUse"`, `viewBox="0 0 10 8"`, size `10×8`; end `refX=6/refY=4`, start `refX=4/refY=4`. Tips project 4px beyond path endpoints. Target and bidirectional-source endpoints are set back **6px**, leaving a **2px tip-to-contour gap**. An ordinary source starts **2px** outside its contour. Colored edges, including `generic`, use `arrowhead-{type}` / `arrowhead-start-{type}`. Neutral aliases are for untyped hand-authored `.arrow` elements only. Stroke width does not resize these markers.
5. **SVG-local styles:** keep `<style>` inside `<svg>`, with paired `html[data-theme="x"] svg` and `svg[data-theme="x"]` selectors. Theme changes mirror onto HTML and SVG; standalone SVG serialization has no page stylesheet.
6. **Semantic colors:** keep tokens in both theme blocks. Use classes rather than inline color literals. CSS beats presentation attributes: use `.thin` / `.legend-swatch`, not an ineffective `stroke-width` attribute.
7. **Paint order:** edges → matching opaque `.mask` → shape(s) → text. Non-rect masks repeat the contour, stacks use one backing for the pile, actors have no box mask. Masks aid compositing; they do not authorize generated routes through unrelated nodes.
8. **Export structure:** preserve the system-preference pre-paint script, `id="report-container"`, accessible toolbar/status, print hiding rules and original CDN/SRI tags. Capture expands an offscreen clone, not live dimensions or scroll state.

## Design system at a glance

Ten types: `frontend`, `backend`, `database`, `cache`, `compute`, `cloud`, `bus`, `security`, `observability`, `generic`. Prefer shape over a new hue: managed AI API → cloud; inference → compute; vector store → database cylinder; queue → bus hex.

Six node shapes: `rect`, `cylinder`, `hex`, `actor`, `stack`, `cloud`. Notes, badges and manually placed step circles are separate annotations, not additional JSON node shapes. Recipes and palette: [components](references/components.md).

Text width is an **estimate**, not browser measurement: Latin about `0.6em`, full-width CJK about `1em`, with special handling for combining marks/joiners and a conservative `1.2em` budget for Mathematical Alphanumeric Symbols. `API 网关` at 11px is estimated at 48.4px plus 28px padding. Fonts prefer system monospace, then local CJK fallbacks. No Google Fonts or network fonts; actual glyph shaping can differ.

## Output and export contract

| Capability | Availability and scope |
|---|---|
| HTML viewing | Offline inline SVG/CSS; diagram visible without JavaScript, controls require it. Theme follows system preference at load (dark fallback). Toggle state is memory-only; reload resolves system preference again. No browser storage. |
| SVG download | Offline vector diagram with embedded styles, markers, current theme, language and background. Does not include page header/cards/footer. Fonts are local, not embedded. |
| PNG download | Needs the original `html2canvas@1.4.1` script. Raster report capture includes cards, excludes toolbar/status, uses scale 2 and 32 CSS px padding. |
| PDF download | Needs html2canvas and `jspdf@2.5.2`, both original pinned jsDelivr scripts. **One-page PNG raster in PDF, not vector PDF.** |
| Copy image | Needs html2canvas plus secure-context clipboard APIs, user activation and browser permission. Do not change permissions or promise success. |

The HTML references two CDN scripts; offline viewing does not mean opening it makes no attempted requests. Failed exports show a visible status and offer SVG. Do not substitute CDNs or install dependencies to conceal a failed check. Controls use text, not emoji.

## Deeper references

Load as needed; required material is directly reachable here.

| File | Read it when |
|---|---|
| [Layout](references/layout.md) | Sizing, port/track routing, boundaries, labels and manual archetypes. |
| [Components](references/components.md) | Palette, six node shapes, annotations and markers. |
| [Checklist](references/checklist.md) | Static coverage, browser review and test limitations. |
| [Schema](resources/spec.schema.json), [example](resources/spec.example.json), [template](resources/template.html) | Preparing a spec or output copy. |
| [Browser check](tests/browser_check.cjs) | Offline template smoke check; optional original-CDN tests. |
| [Generated-output browser check](tests/browser_generated.cjs) | Eight built fixtures, both themes, actual contours/text, standalone SVG and optional real PNG/PDF exports. |

## Before delivering

1. Match labels, directions and membership to the user's evidence. Omit unstated ports, versions, counts and SLOs; clarify or label assumptions, never invent facts.
2. Validate the final file and work the [checklist](references/checklist.md). Static coverage includes path parsing, cumulative transforms (CTM), multi-shape nodes, text/tspan runs, mask order and instantiated marker geometry. Missing from/to metadata means semantic direction is **not** validated; unknown references fail. Sampled curves, approximate text, complex CSS, nested SVG, `use` and `textPath` need browser review. A pass is not an overlap-free guarantee.
3. Review both themes and supported exports in a browser. Confirm the HTML exists and is non-empty; return its absolute path, validation status, untested items and assumptions.
4. Do not overwrite, submit, upload or package without authorization. If packaging is requested separately, exclude `.claude`, caches, bytecode and local permissions while leaving source copies untouched.

Regression commands:

```bash
python3 -B -m unittest discover -s "$SKILL_DIR/tests" -p 'test_*.py'
# Node.js and an already installed Chrome; no npm install.
# BROWSER_OUT must exist, be absolute and be outside the skill source.
node "$SKILL_DIR/tests/browser_check.cjs" "$BROWSER_OUT"
# Optional, only with authorization to access the two original CDN URLs:
node "$SKILL_DIR/tests/browser_check.cjs" "$BROWSER_OUT" --online
```

The CLI overwrite/symlink safety regression is skipped unless `ROUTING_TEST_OUTPUT` points to an existing approved directory outside the source; enabling it creates test artifacts there. The default command still runs the in-memory regressions.

`CHROME` selects an existing Chrome executable; the default is the macOS Chrome application path. The check writes artifacts and an isolated profile under `BROWSER_OUT`. It tests the template, not arbitrary final diagrams. Offline is the default; real PNG/PDF and clipboard round trips may remain untested. Keep cases in shipped tests or bundled fixed JSON fixtures, never depend on a workspace `research` directory. If Python, Node or Chrome is unavailable, report checks untested; do not install dependencies.
