"""Static SVG regressions; all fixtures stay in memory (python3 -B -m unittest).

The audit's 24 scenes are retained, but the wrapper uses in-memory state and the
new fixed-size marker. Expected results describe defects, not the old validator's
incorrect exit codes. Compact hand-authored spacing is legal; side legends warn.
"""
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import diagram_lib as L
import validate as V

CSS = '''.node { fill: rgba(20,30,40,0.2); stroke-width: 1; }
.arrow { fill: none; stroke-width: 2; }
.mask { fill: var(--surface); }
.t { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
'''
MARKER = '''<marker id="head" markerUnits="userSpaceOnUse" viewBox="0 0 10 8"
 markerWidth="10" markerHeight="8" refX="6" refY="4" orient="auto">
 <polygon points="0,0 10,4 0,8"/></marker>'''
START = '''<marker id="start" markerUnits="userSpaceOnUse" viewBox="0 0 10 8"
 markerWidth="10" markerHeight="8" refX="4" refY="4" orient="auto">
 <polygon points="10,0 0,4 10,8"/></marker>'''


def rect(x, y, w, h, extra='', cls='node generic'):
    return f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" {extra}/>'


def line(x1, y1, x2, y2, extra='marker-end="url(#head)"'):
    return f'<line class="arrow" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" {extra}/>'


def document(scene, marker=MARKER, defs='', css='', viewbox='0 0 300 240'):
    return L.DiagramDocument(f'<svg viewBox="{viewbox}"><style>{CSS}{css}</style><defs>{marker}{defs}</defs>{scene}</svg>')


def report(scene, **kwargs):
    doc = document(scene, **kwargs)
    r = V.Reporter(Path('memory.svg'))
    V.check_geometry(doc, r)
    return doc, r


class AuditRegression(unittest.TestCase):
    def check(self, scene, error=None, warning=None, **kwargs):
        doc, r = report(scene, **kwargs)
        if error:
            self.assertTrue(any(error in e for e in r.errors), '\n'.join(r.errors) or 'No errors')
        else:
            self.assertFalse(r.errors, '\n'.join(r.errors))
        if warning:
            self.assertTrue(any(warning in e for e in r.warnings), '\n'.join(r.warnings))
        return doc, r

    def test_00_control(self):
        self.check(rect(10,190,80,30)+line(110,205,180,205))

    def test_01_noncollinear_crossing_is_information(self):
        _, r = self.check(line(20,60,220,60)+line(100,20,100,140))
        self.assertTrue(any('non-collinear' in x for x in r.infos))
        r.strict = True
        self.assertTrue(r.ok())

    def test_02_collinear_overlap(self):
        self.check(line(20,60,160,60)+line(100,60,220,60), 'collinear')

    def test_03_reversed_semantic_direction(self):
        self.check(rect(20,20,50,50,'id="a"')+rect(200,20,50,50,'id="b"')+
                   line(198,45,72,45,'data-from="a" data-to="b" marker-end="url(#head)"'), 'endpoint does not meet')

    def test_04_marker_viewport_clipping(self):
        self.check(line(20,60,160,60), 'clipped', marker='<marker id="head" markerWidth="4" markerHeight="4" refX="4" refY="2" orient="auto" overflow="hidden"><polygon points="0,0 10,2 0,4"/></marker>')

    def test_05_marker_root_overflow(self):
        self.check(line(270,60,299,60), 'marker instance extends')

    def test_06_mask_paint_order(self):
        self.check(rect(80,30,50,60,cls='mask')+rect(80,30,50,60)+line(20,60,200,60), 'paint order')

    def test_07_unmasked_collision(self):
        self.check(rect(80,30,50,60)+line(20,60,200,60), 'effective .mask')

    def test_08_transform_hidden_overlap(self):
        self.check(rect(20,20,60,40)+'<g transform="translate(-120,0)">'+rect(140,20,60,40)+'</g>', 'node overlaps')

    def test_09_transform_false_overlap_fixed(self):
        self.check(rect(20,20,60,40)+'<g transform="translate(120,0)">'+rect(20,20,60,40)+'</g>')

    def test_10_mixed_shape_overlap(self):
        self.check(rect(20,20,80,60)+'<polygon class="node generic" points="40,20 80,20 100,50 80,80 40,80 20,50"/>', 'node overlaps')

    def test_11_text_anchor_spill(self):
        self.check(rect(20,20,80,40)+'<text class="t" x="95" y="45" font-size="10" text-anchor="start">LONGTEXT</text>', 'overflows node')

    def test_12_tspan_overflow(self):
        self.check(rect(20,20,80,40)+'<text class="t" x="60" y="45" font-size="10" text-anchor="middle"><tspan>ABCDEFGHIJKLMNOPQRSTUVWXYZABCDEFGHIJKLMNOPQRSTUVWXYZ</tspan></text>', 'overflows node')

    def test_13_label_overlap_and_line(self):
        _,r = self.check(line(20,95,250,95)+'<text class="t" x="100" y="100" font-size="10">ALPHA</text><text class="t" x="100" y="100" font-size="10">BETA</text>', 'overlaps text')
        self.assertTrue(any('crosses text' in e for e in r.errors))

    def test_14_vertical_spill(self):
        self.check(rect(20,20,80,40)+'<text class="t" x="60" y="22" font-size="20" text-anchor="middle">A</text>', 'overflows node')

    def test_15_open_polyline(self):
        doc,_ = self.check(rect(80,65,30,20)+'<polyline class="arrow" points="20,20 180,20 180,140"/>')
        self.assertEqual(len(L.segments_of(V._arrows(doc)[0])), 2)

    def test_16_Q_then_S_does_not_reflect(self):
        self.check(rect(175,94,30,20)+'<path class="arrow" d="M20 80 Q80 20 140 80 S200 80 260 80"/>')
        self.assertTrue(all(abs(p[1]-80)<1e-6 for p in L.path_polylines('M20 80 Q80 20 140 80 S200 80 260 80')[0][9:]))

    def test_17_unused_defs_not_painted(self):
        self.check('', defs='<marker id="unused"><polygon class="node generic" points="350,0 360,5 350,10"/></marker>')

    def test_18_side_legend_warns_not_invalid_svg(self):
        self.check(rect(20,20,100,100,cls='boundary')+rect(180,30,16,10,cls='node generic legend-swatch'), warning='legend is not below')

    def test_19_manual_compact_spacing_is_legal(self):
        self.check(rect(20,20,60,30)+rect(20,52,60,30))

    def test_20_missing_marker_reference(self):
        self.check(line(20,60,180,60,'marker-end="url(#missing)"'), 'marker reference')

    def test_21_rect_overlap(self):
        self.check(rect(20,20,80,40)+rect(30,30,80,40), 'node overlaps')

    def test_22_wrong_marker_orientation(self):
        self.check(line(72,45,194,45), 'marker orientation', marker=MARKER.replace('orient="auto"','orient="180"'))

    def test_23_separated_subpaths(self):
        doc,_ = self.check(rect(80,65,30,20)+'<path class="arrow" d="M20 20 L180 20 M180 140 L220 140"/>')
        self.assertEqual(len(L.segments_of(V._arrows(doc)[0])),2)

    def test_mask_effective_order_and_ctm(self):
        scene = line(20,60,200,60)+rect(80,30,50,60,cls='mask')+rect(80,30,50,60)
        self.check(scene)
        self.check(line(20,60,200,60)+'<g transform="translate(100)">'+rect(80,30,50,60,cls='mask')+'</g>'+rect(80,30,50,60), 'paint order')

    def test_parent_style_nested_transform_and_tspan_tail(self):
        doc,r = self.check('<g transform="translate(50 30)" font-size="10" text-anchor="middle"><g transform="scale(2)">'+rect(0,0,80,40)+'<text x="40" y="20">A<tspan>B</tspan>C</text></g></g>')
        text = next(e for e in doc.svg_elements if e.tag=='text')
        self.assertEqual(text.text,'ABC')
        self.assertEqual(len(text.text_runs),3)
        self.assertEqual(L.text_bbox(text),(112.,54.,148.,74.))

    def test_C_then_T_does_not_reflect_and_T_chain_does(self):
        pts = L.path_polylines('M0 0 C10 30 20 30 30 0 T60 0')[0]
        self.assertTrue(all(abs(y)<1e-6 for _,y in pts[13:]))
        pts = L.path_polylines('M0 0 Q10 20 20 0 T40 0')[0]
        self.assertLess(min(y for _,y in pts),0)

    def test_multipart_node_does_not_overlap_itself(self):
        self.check('<g data-node-id="x" data-shape="cylinder">'+rect(30,30,80,60)+'<ellipse class="node generic" cx="70" cy="35" rx="40" ry="10"/></g>')

    def test_outline_not_bbox_collision(self):
        self.check('<circle class="node generic" cx="60" cy="60" r="30"/>'+rect(86,86,15,15))

    def test_thick_marker_and_bidirectional_metadata(self):
        scene = '<g data-node-id="a" data-shape="rect">'+rect(20,20,50,50)+'</g><g data-node-id="b" data-shape="rect">'+rect(200,20,50,50)+'</g>'
        scene += line(76,45,194,45,'style="stroke-width:2.5" data-edge-id="edge-0" data-from="a" data-to="b" data-bidirectional="true" marker-start="url(#start)" marker-end="url(#head)"')
        self.check(scene,defs=START)
        self.assertEqual(L.ARROW_STANDOFF,6)

    def test_marker_units_scale_viewbox_and_child_transform(self):
        marker = '<marker id="head" markerUnits="strokeWidth" viewBox="0 0 20 16" markerWidth="10" markerHeight="8" refX="12" refY="8" orient="auto"><g transform="scale(2)"><polygon points="0,0 10,4 0,8"/></g></marker>'
        doc,_ = self.check('<g transform="translate(20 20) scale(2)">'+line(10,20,70,20)+'</g>',marker=marker)
        instances,issues = L.marker_instances(doc,V._arrows(doc)[0])
        self.assertFalse(issues)
        self.assertEqual(instances[0]['tip'],(176.,60.))

    def test_marker_auto_start_reverse(self):
        marker = MARKER.replace('orient="auto"','orient="auto-start-reverse"')
        self.check(line(40,60,160,60,'marker-start="url(#head)" marker-end="url(#head)"'),marker=marker)

    def test_marker_size_zero_and_shaft_protrusion(self):
        self.check(line(20,60,160,60),'non-positive',marker=MARKER.replace('markerWidth="10"','markerWidth="0"'))
        self.check(line(20,60,160,60,'style="stroke-width:8" marker-end="url(#head)"'),'shaft protrusion')

    def test_line_through_other_marker(self):
        self.check(line(20,60,160,60)+line(158,20,158,100,''),'another marker')

    def test_shared_endpoint_and_own_head_are_legal(self):
        self.check(line(20,60,160,60)+line(160,60,160,140))

    def test_explicit_route_exemption_not_shared_target(self):
        scene = line(20,60,160,60,'data-to="b"')+line(100,60,220,60,'data-to="b"')
        self.check(scene,'collinear')
        self.check(line(20,60,160,60,'data-shared-route="bus-1"')+line(100,60,220,60,'data-shared-route="bus-1"'))
        self.check(line(20,60,160,60,'data-shared-route="true"')+line(100,60,220,60,'data-shared-route="true"'),'collinear')

    def test_self_connection_metadata(self):
        scene = '<g data-node-id="a">'+rect(100,100,50,50)+'</g><path class="arrow" data-from="a" data-to="a" d="M150 125 H200 V60 H125 V94" marker-end="url(#head)"/>'
        self.check(scene)

    def test_no_metadata_never_claims_semantics(self):
        _,r = self.check(line(20,60,160,60))
        self.assertTrue(any('semantic direction was NOT validated' in x for x in r.infos))

    def test_text_vertical_writing_and_multiline(self):
        self.check(rect(20,20,80,70)+'<text x="60" y="35" font-size="10" text-anchor="middle"><tspan>AB</tspan><tspan x="60" dy="20">CD</tspan></text>')
        self.check(rect(20,20,80,70)+'<text x="60" y="30" font-size="10" writing-mode="vertical-rl">ABC</text>')

    def test_unicode_metrics(self):
        self.assertAlmostEqual(L.text_width('ABC中文',10),38)
        self.assertAlmostEqual(L.text_width('e\u0301',10),6)
        self.assertAlmostEqual(L.text_width('\U0001f469\u200d\U0001f4bb',10),10)
        self.assertAlmostEqual(L.text_width('\U0001f1e8\U0001f1f3',10),10)
        self.assertAlmostEqual(L.text_width('\U0001d54e' * 28,11),369.6)

    def test_group_opacity_does_not_make_an_effective_mask(self):
        scene = line(20,60,200,60)+'<g opacity="0.5">'+rect(80,30,50,60,cls='mask')+'</g>'+rect(80,30,50,60)
        self.check(scene, 'effective .mask')
        scene = line(20,60,200,60)+rect(80,30,50,60,'style="fill:white"')
        self.check(scene)

    def test_anchored_adjacent_runs_stay_in_one_host(self):
        self.check(rect(20,20,80,40)+'<text x="60" y="45" font-size="10" text-anchor="middle"><tspan>ABCDE</tspan><tspan>FGHIJ</tspan></text>')

    def test_print_selector_list_is_supported(self):
        r = V.Reporter(Path('memory.html'))
        V.check_structure(L.DiagramDocument('<style>@media print {.toolbar, .export-status {display:none !important;}}</style>'),r)
        self.assertFalse(any('print rule' in x for x in r.errors))

    def test_direct_element_transform(self):
        el = L.SvgElement('rect', {'x':'10','y':'20','width':'30','height':'40','transform':'translate(5 6)'},1,1)
        self.assertEqual(L.geometry_bbox(el),(15.,26.,45.,66.))

    def test_nonuniform_marker_transform(self):
        self.check('<g transform="translate(30 20) scale(0.5 3)">'+line(20,30,200,30)+'</g>')

    def test_stack_backplate_is_part_of_logical_outline(self):
        stack = '<g data-node-id="stack" data-shape="stack">'+rect(28,28,60,40,cls='node generic ghost')+rect(20,20,60,40)+'</g>'
        self.check(stack)
        self.check(stack+rect(82,30,40,30), 'node overlaps')

    def test_mask_alpha_and_world_identity(self):
        scene = line(20,60,200,60)+rect(80,30,50,60,'style="fill:rgba(255,255,255,0.4)"',cls='mask')+rect(80,30,50,60)
        self.check(scene, 'effective .mask')
        self.check('<g transform="translate(10 10)">'+line(10,50,190,50)+rect(70,20,50,60,cls='mask')+rect(70,20,50,60)+'</g>')

    def test_storage_and_network_font_policy(self):
        r = V.Reporter(Path('memory.html'))
        V.check_structure(L.DiagramDocument('<script>sessionStorage.getItem("theme")</script>'),r)
        self.assertTrue(any('storage is forbidden' in x for x in r.errors))
        r = V.Reporter(Path('memory.html'))
        V.check_structure(L.DiagramDocument('<style>@import url("https://fonts.example.net/font.css");</style>'),r)
        self.assertTrue(any('external/network fonts' in x for x in r.errors))
        r = V.Reporter(Path('memory.html'))
        V.check_structure(L.DiagramDocument('<script>let theme="light";</script>'),r)
        self.assertFalse(any('pre-paint' in x or 'storage' in x for x in r.errors))

    def test_every_subpath_has_start_and_end_markers(self):
        scene = '<path class="arrow" d="M270 60 L299 60 M20 100 L100 100" marker-end="url(#head)"/>'
        doc, r = self.check(scene, 'marker instance extends past the viewBox')
        instances, issues = L.marker_instances(doc, V._arrows(doc)[0])
        self.assertFalse(issues)
        self.assertEqual([m['tip'] for m in instances], [(303., 60.), (104., 100.)])
        r.strict = True
        self.assertFalse(r.ok())
        scene = '<path class="arrow" d="M40 60 L100 60 M100 100 L100 160" marker-start="url(#start)" marker-end="url(#head)"/>'
        doc, r = self.check(scene, defs=START)
        instances, issues = L.marker_instances(doc, V._arrows(doc)[0])
        self.assertFalse(issues)
        self.assertEqual([m['position'] for m in instances], ['start', 'end', 'start', 'end'])
        for instance, tip in zip(instances, [(36,60), (104,60), (100,96), (100,164)]):
            self.assertAlmostEqual(instance['tip'][0], tip[0])
            self.assertAlmostEqual(instance['tip'][1], tip[1])
        r.strict = True
        self.assertTrue(r.ok())
        self.check(scene.replace('M100 100 L100 160', 'M1 100 L100 100'),
                   'marker instance extends past the viewBox', defs=START)

    def test_subpath_tangents_skip_zero_length_segments(self):
        scene = '<path class="arrow" d="M40 40 L40 40 L40 100 L40 100 M100 100 L100 100 L180 100 L180 100" marker-start="url(#start)" marker-end="url(#head)"/>'
        doc, _ = self.check(scene, defs=START)
        instances, issues = L.marker_instances(doc, V._arrows(doc)[0])
        self.assertFalse(issues)
        self.assertEqual(len(instances), 4)
        for instance, tip in zip(instances, [(40,36), (40,104), (96,100), (184,100)]):
            self.assertAlmostEqual(instance['tip'][0], tip[0])
            self.assertAlmostEqual(instance['tip'][1], tip[1])
        doc, _ = self.check('<path class="arrow" d="M40 40 L40 40 M100 100 L180 100" marker-end="url(#head)"/>')
        instances, issues = L.marker_instances(doc, V._arrows(doc)[0])
        self.assertFalse(issues)
        self.assertEqual(len(instances), 2)
        self.assertEqual(instances[0]['tip'], (44., 40.))

    def test_multipart_metadata_is_not_silently_validated(self):
        nodes = rect(20,20,50,50,'id="a"') + rect(200,20,50,50,'id="b"')
        scene = nodes + '<path class="arrow" data-from="a" data-to="b" d="M72 45 L100 45 M160 45 L194 45" marker-end="url(#head)"/>'
        _, r = self.check(scene, 'multiple subpaths')
        r.strict = True
        self.assertFalse(r.ok())
        self.check(scene.replace('M72 45 L100 45 M160 45 L194 45', 'M72 45 L194 45'))

    def test_marker_requires_visible_paint(self):
        for style in ('fill:none;stroke:none', 'fill:transparent;stroke:none',
                      'fill:rgba(1,2,3,0);stroke:none', 'fill:#fff0;stroke:none',
                      'opacity:0.0', 'fill-opacity:0%', 'fill:none;stroke:black;stroke-opacity:0',
                      'fill:none;stroke:black;stroke-width:0'):
            with self.subTest(style=style):
                marker = MARKER.replace('<polygon', f'<polygon style="{style}"')
                doc, _ = self.check(line(20,60,160,60), 'no measurable painted geometry', marker=marker)
                instances, _ = L.marker_instances(doc, V._arrows(doc)[0])
                self.assertFalse(instances[0]['polygons'])
        for style in ('opacity:0.0', 'opacity:0%', 'fill:none;stroke:none'):
            with self.subTest(group_style=style):
                marker = MARKER.replace('<polygon', f'<g style="{style}"><polygon').replace('</marker>', '</g></marker>')
                self.check(line(20,60,160,60), 'no measurable painted geometry', marker=marker)

    def test_marker_inherited_and_css_paint_remain_visible(self):
        for style in ('fill:black', 'fill-opacity:0.5', 'opacity:0.5', 'fill:none;stroke:black'):
            with self.subTest(style=style):
                marker = MARKER.replace('<polygon', f'<g style="{style}"><polygon').replace('</marker>', '</g></marker>')
                self.check(line(20,60,160,60), marker=marker)
        self.check(line(20,60,160,60), css='marker { fill: var(--surface); } svg { --surface: #fff; }')
        self.check(line(20,60,160,60), css='marker { fill:none; } marker polygon { fill:var(--surface); } svg { --surface:#fff; }')
        self.check(line(20,60,160,60), marker=MARKER.replace('<polygon', '<polygon style="fill:inherit"'),
                   css='marker { fill:var(--surface); } svg { --surface:#fff; }')
        self.check(line(20,60,160,60), marker=MARKER.replace('</marker>', '<polygon points="0,0 100,4 0,8" style="fill:none;stroke:none"/></marker>'))
        self.check(line(20,60,160,60), 'no measurable painted geometry',
                   css='marker { fill:var(--surface); } svg { --surface:transparent; }')

    def test_label_background_must_be_effectively_opaque(self):
        text = '<text class="t" x="100" y="100" font-size="10">ALPHA</text>'
        for style in ('fill:transparent', 'fill:rgba(255,255,255,0)', 'fill-opacity:0',
                      'fill:white;opacity:0.5', 'fill:var(--surface)'):
            with self.subTest(style=style):
                scene = line(20,95,250,95) + rect(95,85,50,25,f'style="{style}"',cls='') + text
                _, r = self.check(scene, "crosses text 'ALPHA'", css='svg { --surface:transparent; }')
                r.strict = True
                self.assertFalse(r.ok())
        background = rect(95,85,50,25,'style="fill:white"',cls='')
        self.check(line(20,95,250,95) + '<g opacity="0.5">' + background + '</g>' + text,
                   "crosses text 'ALPHA'")
        for style in ('fill:white', 'fill:rgba(255,255,255,1)', 'fill:var(--surface)', ''):
            with self.subTest(opaque=style):
                _, r = self.check(line(20,95,250,95) + rect(95,85,50,25,f'style="{style}"',cls='') + text,
                                  css='svg { --surface:#fff; }')
                r.strict = True
                self.assertTrue(r.ok())


class ValidationMainRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import build_diagram as builder
        root = Path(__file__).resolve().parents[1]
        spec = json.loads((root / 'resources/spec.example.json').read_text(encoding='utf-8'))
        cls.generated = builder.build(builder.Spec(spec), builder.TEMPLATE.read_text(encoding='utf-8'))

    def validate_source(self, source):
        path = Path(__file__).resolve().with_name('memory.html')
        output = io.StringIO()
        with patch.object(Path, 'is_file', return_value=True), patch.object(Path, 'read_text', return_value=source), redirect_stdout(output):
            code = V.main([str(path), '--strict', '--quiet'])
        return code, output.getvalue(), path

    def test_generated_control_and_invisible_markers_strict(self):
        code, output, _ = self.validate_source(self.generated)
        self.assertEqual(code, 0, output)
        mutated = self.generated.replace('<polygon class="arrowhead', '<polygon style="fill:none;stroke:none" class="arrowhead')
        self.assertNotEqual(mutated, self.generated)
        code, output, _ = self.validate_source(mutated)
        self.assertEqual(code, 1, output)
        self.assertIn('no measurable painted geometry', output)

    def test_nonfinite_inputs_report_source_location_without_traceback(self):
        cases = []
        for transform in ('rotate(1e309)', 'rotate(-1e309)', 'translate(1e309 0)',
                          'scale(1e309)', 'skewX(1e309)', 'matrix(1 0 0 1 1e309 0)',
                          'scale(1e308) scale(1e308)', 'rotate(inf)', 'rotate(nan)'):
            cases.append((f'<g transform="{transform}"></g>', 'transform'))
        for orient in ('1e309', '-1e309', '1e309deg', '1e309rad', '1e309turn', 'nan', 'inf', '1e308turn'):
            cases.append((MARKER.replace('orient="auto"', f'orient="{orient}"') + line(20,60,160,60), 'orient'))
        cases.extend([
            (rect(20,20,'1e309',40), 'width'),
            (rect(20,20,'nan',40), 'width'),
            ('<g transform="scale(1e308)"><g transform="scale(1e308)"></g></g>', 'transform'),
            ('<path class="arrow" d="M20 60 L1e309 60"/>', 'd'),
            ('<path class="arrow" d="M20 60 A10 10 1e309 0 0 80 60"/>', 'd'),
            ('<polygon points="20,20 1e309,40 20,60"/>', 'points'),
            (MARKER.replace('markerWidth="10"', 'markerWidth="1e309"') + line(20,60,160,60), 'markerwidth'),
            (MARKER.replace('refX="6"', 'refX="1e309"') + line(20,60,160,60), 'refx'),
            (MARKER.replace('viewBox="0 0 10 8"', 'viewBox="0 0 1e309 8"') + line(20,60,160,60), 'viewbox'),
            ('<text x="20" y="20" style="font-size:1e309">A</text>', 'font-size'),
            ('<text x="20" y="20" style="font-size:1e309em">A</text>', 'font-size'),
        ])
        for scene, field in cases:
            with self.subTest(scene=scene):
                source = '<svg viewBox="0 0 300 240">\n' + scene + '</svg>'
                code, output, path = self.validate_source(source)
                self.assertEqual(code, 1, output)
                self.assertIn('non-finite', output)
                self.assertIn(field, output)
                self.assertIn(f'{path}:2:', output)
                self.assertNotIn('Traceback', output)
        code, output, path = self.validate_source('<svg viewBox="0 0 1e309 240"></svg>')
        self.assertEqual(code, 1, output)
        self.assertIn('non-finite', output)
        self.assertIn('viewbox', output)
        self.assertIn(f'{path}:1:', output)

    def test_finite_numeric_controls(self):
        self.assertEqual(L.parse_transform('translate(1e2 -2e1)'), (1,0,0,1,100,-20))
        for orient in ('0', '0deg', '0rad', '0turn'):
            with self.subTest(orient=orient):
                _, r = report(line(20,60,160,60), marker=MARKER.replace('orient="auto"', f'orient="{orient}"'))
                self.assertFalse(r.errors, '\n'.join(r.errors))


if __name__ == '__main__':
    unittest.main()
