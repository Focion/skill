"""Standard-library template contracts. Run directly with python3 -B (no cache)."""
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

SOURCE = Path(__file__).resolve().parents[1] / "resources" / "template.html"
TEXT = SOURCE.read_text(encoding="utf-8")
SVG = ET.fromstring(re.search(r'<svg id="arch-svg"[\s\S]*?</svg>', TEXT).group())
CSS = SVG.find("style").text
TYPES = "frontend backend database cache compute cloud bus security observability generic".split()
CDN = [
    '<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js" integrity="sha384-ZZ1pncU3bQe8y31yfZdMFdSpttDoPmOZg2wguVK9almUodir1PghgT0eY7Mrty8H" crossorigin="anonymous"></script>',
    '<script src="https://cdn.jsdelivr.net/npm/jspdf@2.5.2/dist/jspdf.umd.min.js" integrity="sha384-en/ztfPSRkGfME4KIm05joYXynqzUgbsG5nMrj/xEFAHXkeZfO3yMK8QQ+mP7p1/" crossorigin="anonymous"></script>',
]


class TemplateContracts(unittest.TestCase):
    def test_marker_geometry(self):
        markers = SVG.findall("./defs/marker")
        self.assertEqual(len(markers), 22)
        ids = [m.attrib["id"] for m in markers]
        self.assertEqual(len(set(ids)), 22)
        for kind in [""] + TYPES:
            for start in [False, True]:
                name = "arrowhead" + ("-start" if start else "") + ("-" + kind if kind else "")
                marker = next(m for m in markers if m.attrib["id"] == name)
                self.assertEqual(marker.attrib, dict(id=name, markerUnits="userSpaceOnUse",
                    viewBox="0 0 10 8", markerWidth="10", markerHeight="8",
                    refX="4" if start else "6", refY="4", orient="auto"))
                polygon = marker.find("polygon")
                self.assertEqual(polygon.attrib["points"], "10 0, 0 4, 10 8" if start else "0 0, 10 4, 0 8")
                self.assertEqual(polygon.attrib["class"], "arrowhead" + (" " + kind if kind else ""))

    def test_semantic_marker_colors(self):
        for kind in TYPES:
            self.assertRegex(CSS, rf"\.arrowhead\.{kind}\s*\{{\s*fill:\s*var\(--{kind}\);")
            self.assertEqual(len(re.findall(rf"--{kind}:\s*#[0-9a-f]{{6}};", CSS)), 2)
        self.assertEqual(re.findall(r"--c-arrow:\s*(#[0-9a-f]+)", CSS), ["#64748b"] * 2)
        self.assertNotRegex(CSS, r"(?:fill|stroke):\s*context-stroke")

    def test_connections_use_matching_markers_and_standoff(self):
        lines = [e for e in SVG.findall("line") if e.get("marker-end")]
        self.assertEqual(len(lines), 5)
        self.assertEqual([(e.get("x2"), e.get("y2")) for e in lines],
                         [("194", "305"), ("354", "305"), ("255", "374"), ("504", "305"), ("694", "305")])
        for edge in SVG:
            if edge.get("marker-end"):
                kind = next(k for k in TYPES if k in edge.get("class", "").split())
                self.assertEqual(edge.get("marker-end"), f"url(#arrowhead-{kind})")
        auth = next(e for e in SVG.findall("path") if "security" in e.get("class", ""))
        self.assertTrue(auth.get("d").endswith("L 220 274"))

    def test_paint_order_and_same_shape_masks(self):
        elements = list(SVG)
        nodes = [e for e in elements if "node" in e.get("class", "").split() and "legend-swatch" not in e.get("class", "")]
        edges = [e for e in elements if "arrow" in e.get("class", "").split() and "legend-swatch" not in e.get("class", "")]
        self.assertEqual(len(nodes), 8)
        self.assertLess(max(elements.index(e) for e in edges), min(elements.index(n) for n in nodes))
        for node in nodes:
            mask = elements[elements.index(node) - 1]
            self.assertEqual(mask.get("class"), "mask")
            self.assertEqual(mask.tag, node.tag)
            self.assertEqual({k: v for k, v in mask.attrib.items() if k != "class"},
                             {k: v for k, v in node.attrib.items() if k != "class"})

    def test_system_fonts_and_no_persistence(self):
        chain = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace, 'PingFang SC', 'Microsoft YaHei', 'Noto Sans CJK SC'"
        self.assertEqual(TEXT.count("font-family: " + chain + ";"), 2)
        self.assertNotRegex(TEXT, r"localStorage|sessionStorage|indexedDB|document\.cookie|navigator\.storage|caches\.|@font-face|fonts\.googleapis|fonts\.gstatic")
        self.assertIn("prefers-color-scheme: light", TEXT.split("<body>")[0])
        self.assertNotRegex(TEXT, "[\U0001f000-\U0001faff\u2600-\u27bf\ufe0f]")

    def test_only_original_cdn_dependencies(self):
        self.assertEqual(re.findall(r'<script src=[^>]+></script>', TEXT), CDN)
        self.assertNotRegex(TEXT, r"<link\b|@import|fetch\(|XMLHttpRequest|WebSocket")

    def test_accessibility_and_generator_hooks(self):
        self.assertIn('<html lang="zh-CN"', TEXT)
        self.assertIn('aria-expanded="false" aria-controls="export-actions"', TEXT)
        self.assertIn('id="export-actions"', TEXT)
        self.assertIn("event.key === 'Escape'", TEXT)
        self.assertIn("document.getElementById('export-menu-btn').focus()", TEXT)
        self.assertIn('role="status" aria-live="polite"', TEXT)
        for token in ["<!-- GEN:CONTENT-START", "<!-- GEN:CONTENT-END -->", "<!-- GEN:CARDS-START -->", "<!-- GEN:CARDS-END -->"]:
            self.assertEqual(TEXT.count(token), 1)
        self.assertEqual(SVG.get("aria-labelledby"), "svg-title svg-desc")

    def test_capture_uses_expanded_clone_not_live_crop(self):
        capture = TEXT.split("function capture() {", 1)[1].split("function copyAsImage", 1)[0]
        self.assertIn("diagram.scrollWidth", capture)
        self.assertIn("onclone: doc =>", capture)
        self.assertIn("window.html2canvas(el,", capture)
        self.assertNotIn("el.style", capture)
        self.assertNotRegex(capture, r"(?:width|height):\s*r\.")
        self.assertIn("diagram.style.overflow = 'visible'", capture)
        self.assertIn("diagram.scrollLeft = 0", capture)

    def test_export_degradation_and_single_page_raster_pdf(self):
        self.assertIn("typeof window.html2canvas !== 'function'", TEXT)
        self.assertIn("typeof window.jspdf.jsPDF !== 'function'", TEXT)
        self.assertIn("SVG 离线下载", TEXT)
        self.assertIn("typeof navigator.clipboard.write !== 'function'", TEXT)
        self.assertIn("if (value) resolve(value)", TEXT)
        self.assertIn("pdf.addImage(imgData, 'PNG'", TEXT)
        self.assertNotIn("pdf.addPage", TEXT)
        self.assertNotIn("pdf.svg", TEXT)
        self.assertIn("URL.revokeObjectURL(url)", TEXT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
