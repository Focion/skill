'use strict';
// Native Node/CDP; no packages, installs, permission changes, or cleanup commands.
// node tests/browser_generated.cjs /existing/absolute/workspace/output [--online]
// CHROME overrides the installed browser; PYTHON overrides python3. Artifacts and
// the fresh browser profile are confined to a unique directory outside the skill.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { spawn, spawnSync } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const { StringDecoder } = require('node:string_decoder');
const { createHash } = require('node:crypto');
const skill = fs.realpathSync(path.resolve(__dirname, '..'));
const outputArg = process.argv[2];
assert(outputArg && path.isAbsolute(outputArg), 'Provide an existing absolute output directory');
const output = fs.realpathSync(outputArg);
assert(fs.statSync(output).isDirectory());
assert(output !== skill && !output.startsWith(skill + path.sep), 'Artifacts must be outside the skill');
const online = process.argv.includes('--online');
const root = fs.mkdtempSync(path.join(output, 'generated-'));
const allowedURLs = new Set([
  'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js',
  'https://cdn.jsdelivr.net/npm/jspdf@2.5.2/dist/jspdf.umd.min.js'
]);
const out = { root, skill, mode: online ? 'original-CDN' : 'offline', started: new Date().toISOString(),
  builds: [], requests: [], cases: [], failures: [], untested: [], sourceHashes: {} };
const tracked = ['scripts/build_diagram.py', 'scripts/diagram_lib.py', 'scripts/validate.py', 'resources/template.html', 'resources/spec.example.json'];
const hash = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
for (const name of tracked) out.sourceHashes[name] = hash(path.join(skill, name));
function save(name, value) { const file = path.join(root, name); fs.writeFileSync(file, value); return file; }
function check(condition, label, detail) {
  if (!condition) out.failures.push({ label, detail });
  return !!condition;
}
const node = (id, extra = {}) => ({ id, name: id, ...extra });
const spec = (tiers, edges, extra = {}) => ({ title: 'Routing audit', legend: false,
  tiers: tiers.map(nodes => ({ nodes })), edges: edges.map(([from, to, rest = {}]) => ({ from, to, ...rest })), ...extra });
// Independent equivalents of the routing regressions; never read a research tree.
const fixtures = [
  ['01_many_to_one', spec([[node('A'), node('B')], [node('D')]], [['A', 'D'], ['B', 'D']])],
  ['02_reciprocal_adjacent', spec([[node('A')], [node('B')]], [['A', 'B'], ['B', 'A']])],
  ['07_cloud_port', spec([[node('C', { shape: 'cloud' })], [node('D')], [node('E')]], [['C', 'E']])],
  ['08_actor_port', spec([[node('A', { shape: 'actor' })], [node('B')], [node('C')]], [['A', 'C']])],
  ['13_hex_midpoint', spec([[node('A'), node('B')], [node('H', { shape: 'hex' }), node('D', { subs: ['a', 'b', 'c'] })]], [['A', 'H']])],
  ['six_shapes', spec([
    [node('actor', { name: '用户', shape: 'actor', type: 'frontend', subs: ['Web / App'] }), node('cloud', { shape: 'cloud', type: 'cloud', subs: ['TLS'] })],
    [node('rect', { name: 'API 网关', type: 'security', badge: 'v2' }), node('stack', { name: '计算服务', shape: 'stack', type: 'compute', subs: ['worker'] })],
    [node('cylinder', { name: '数据库', shape: 'cylinder', type: 'database' }), node('hex', { name: '消息总线', shape: 'hex', type: 'bus' })]
  ], [['actor', 'rect', { type: 'frontend', style: 'thin', bidirectional: true }],
    ['cloud', 'stack', { type: 'cloud', style: 'thick', bidirectional: true }],
    ['rect', 'cylinder', { type: 'database', bidirectional: true }],
    ['stack', 'hex', { type: 'bus', style: 'dotted', bidirectional: true }]], { title: '六种轮廓 / Six shapes' })],
  ['font_fallback', spec([[node('latin', { name: 'W'.repeat(29), subs: ['i'.repeat(29), '用户认证服务'] })],
    [node('math', { name: '\u{1D54E}'.repeat(14), subs: ['Math font fallback'] })]], [['latin', 'math']], { title: 'Unicode 字体度量' })]
];
const longMath = spec([[node('math', {name:'\u{1D54E}'.repeat(28)})]], []);
const longMathInput = save('font-overflow-rejected.json', JSON.stringify(longMath));
const longMathResult = spawnSync(process.env.PYTHON || 'python3', ['-B', path.join(skill, 'scripts/build_diagram.py'),
  longMathInput, '-o', path.join(root, 'font-overflow-rejected.html'), '--strict'],
  {cwd:root, encoding:'utf8', timeout:30000, env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'}});
out.fontOverflowRejected = {status:longMathResult.status,stderr:longMathResult.stderr};
check(longMathResult.status === 1 && /name.*over the/s.test(longMathResult.stderr),
  'long mathematical label rejected before rendering', out.fontOverflowRejected);
check(!fs.existsSync(path.join(root, 'font-overflow-rejected.html')), 'invalid label creates no output');
const inputs = [['default-example', path.join(skill, 'resources/spec.example.json')]];
for (const [name, value] of fixtures) inputs.push([name, save(name + '.json', JSON.stringify(value, null, 2))]);
for (const [name, input] of inputs) {
  const html = path.join(root, name + '.html');
  const args = ['-B', path.join(skill, 'scripts/build_diagram.py'), input, '-o', html, '--strict'];
  const result = spawnSync(process.env.PYTHON || 'python3', args, { cwd: root, encoding: 'utf8', timeout: 30000,
    maxBuffer: 2 * 1024 * 1024, env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' } });
  const record = { name, input, html, args, status: result.status, stdout: result.stdout, stderr: result.stderr, error: result.error?.message };
  out.builds.push(record);
  save(name + '-build.json', JSON.stringify(record, null, 2));
  check(result.status === 0, name + ': strict build', record);
}
const defaults = process.platform === 'darwin' ? ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']
  : process.platform === 'win32' ? [path.join(process.env.PROGRAMFILES || 'C:\\Program Files', 'Google/Chrome/Application/chrome.exe')]
    : ['/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'];
const chrome = process.env.CHROME || defaults.find(file => fs.existsSync(file));
assert(chrome, 'Set CHROME to an existing Chrome executable');
const browser = spawn(chrome, ['--headless=new', '--remote-debugging-pipe', `--user-data-dir=${path.join(root, 'chrome-profile')}`,
  '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--disable-component-update',
  '--disable-sync', '--disable-extensions', '--metrics-recording-only', '--disable-domain-reliability',
  ...(!online ? ['--proxy-server=http://127.0.0.1:9', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost'] : []),
  'about:blank'], { cwd: root, stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe'] });
let seq = 0, buffer = '', sessionId;
const pending = new Map(), events = new Set(), decoder = new StringDecoder('utf8');
let fatal;
browser.stderr.on('data', d => fs.appendFileSync(path.join(root, 'chrome.log'), d));
function rejectPending(error) { fatal = error; for (const p of pending.values()) { clearTimeout(p.timer); p.reject(error); } pending.clear(); }
browser.on('error', rejectPending);
browser.on('exit', (code, signal) => rejectPending(new Error(`Chrome exited: ${code} ${signal}`)));
browser.stdio[4].on('data', data => {
  buffer += decoder.write(data);
  let i;
  while ((i = buffer.indexOf('\0')) >= 0) {
    const raw = buffer.slice(0, i); buffer = buffer.slice(i + 1);
    if (!raw) continue;
    const message = JSON.parse(raw);
    if (pending.has(message.id)) {
      const p = pending.get(message.id); pending.delete(message.id); clearTimeout(p.timer);
      if (message.error) p.reject(new Error(JSON.stringify(message.error))); else p.resolve(message.result);
    } else for (const listener of events) listener(message);
  }
});
function cdp(method, params = {}, sid) {
  if (fatal) return Promise.reject(fatal);
  const id = ++seq;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 30000);
    pending.set(id, { resolve, reject, timer });
    browser.stdio[3].write(JSON.stringify({ id, method, params, ...(sid ? { sessionId: sid } : {}) }) + '\0');
  });
}
const send = (method, params) => cdp(method, params, sessionId);
async function evaluate(expression) {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true, userGesture: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function invoke(fn, ...args) { return evaluate(`(${fn.toString()})(...${JSON.stringify(args)})`); }
async function navigate(file) {
  await send('Page.navigate', { url: pathToFileURL(file).href });
  await evaluate(`new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('load deadline')),20000);
    const done=()=>{clearTimeout(t);document.fonts.ready.then(()=>resolve(true));};
    document.readyState==='complete'?done():addEventListener('load',done,{once:true});})`);
}
async function viewport(width) {
  await send('Emulation.setDeviceMetricsOverride', { width, height: 1100, deviceScaleFactor: 1, mobile: width === 390 });
}
async function screenshot(name) {
  const result = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  const file = save(name, Buffer.from(result.data, 'base64'));
  return { file, data: result.data };
}
const button = kind => `document.querySelector('[onclick="download${kind}(this)"]')`;
async function download(kind, name) {
  let guid, listener, timer;
  const complete = new Promise((resolve, reject) => {
    timer = setTimeout(() => reject(new Error('Download timeout: ' + name)), 30000);
    listener = message => {
      if (message.method === 'Browser.downloadWillBegin') guid = message.params.guid;
      if (message.method === 'Browser.downloadProgress' && message.params.guid === guid) {
        if (message.params.state === 'completed') resolve(guid);
        if (message.params.state === 'canceled') reject(new Error('Download canceled: ' + name));
      }
    };
    events.add(listener);
  });
  complete.catch(() => {});
  try {
    await evaluate(`download${kind}(${button(kind)})`);
    const id = await complete;
    const file = path.join(root, name);
    assert(!fs.existsSync(file));
    fs.renameSync(path.join(root, id), file);
    assert(fs.statSync(file).size > 0);
    return file;
  } finally { clearTimeout(timer); events.delete(listener); }
}
// Everything below runs against real generated elements. No marker probes or
// replacement geometry are appended; native SVG APIs measure actual outlines.
function inspectSVG() {
  const svg = document.getElementById('arch-svg');
  const vb = svg.viewBox.baseVal;
  const box = r => ({ x: r.x, y: r.y, width: r.width, height: r.height });
  const textRecords = [];
  const overflow = [];
  for (const text of svg.querySelectorAll('text')) {
    const leaves = text.querySelectorAll('tspan').length ? [...text.querySelectorAll('tspan')].filter(t => !t.querySelector('tspan')) : [text];
    for (const leaf of leaves) {
      const b = leaf.getBBox(), group = text.closest('[data-node-id]');
      const row = { node: group?.dataset.nodeId, text: leaf.textContent, tag: leaf.localName,
        markup: leaf.outerHTML, bbox: box(b), length: leaf.getComputedTextLength(),
        font: getComputedStyle(leaf).fontFamily, fontSize: getComputedStyle(leaf).fontSize,
        tspans: [...text.querySelectorAll('tspan')].map(t => ({ text: t.textContent, markup: t.outerHTML, bbox: box(t.getBBox()) })) };
      row.outsideViewBox = b.x < vb.x - 0.5 || b.y < vb.y - 0.5 || b.x + b.width > vb.x + vb.width + 0.5 || b.y + b.height > vb.y + vb.height + 0.5;
      if (group && group.dataset.shape !== 'actor') {
        const contour = text.classList.contains('t-badge') ? group.querySelector('.badge')
          : [...group.querySelectorAll('.node')].filter(e => !e.classList.contains('ghost')).at(-1);
        const cb = contour.getBBox();
        row.container = box(cb);
        row.bboxOverrun = { left: Math.max(0, cb.x - b.x), right: Math.max(0, b.x + b.width - cb.x - cb.width),
          top: Math.max(0, cb.y - b.y), bottom: Math.max(0, b.y + b.height - cb.y - cb.height) };
        const corners = [[b.x + 0.5, b.y + 0.5], [b.x + b.width - 0.5, b.y + 0.5],
          [b.x + 0.5, b.y + b.height - 0.5], [b.x + b.width - 0.5, b.y + b.height - 0.5]];
        row.outsideContour = corners.some(([x, y]) => !contour.isPointInFill(new DOMPoint(x, y)));
      }
      if (row.outsideViewBox || row.outsideContour) overflow.push(row);
      textRecords.push(row);
    }
  }
  const groups = [...svg.querySelectorAll('[data-node-id]')];
  const nodes = groups.map(g => ({ id: g.dataset.nodeId, shape: g.dataset.shape, bbox: box(g.getBBox()),
    outlines: [...g.querySelectorAll('.node')].map(e => ({ tag: e.localName, bbox: box(e.getBBox()), stroke: getComputedStyle(e).stroke })) }));
  const edges = [...svg.querySelectorAll('[data-edge-id]')].map(edge => {
    const len = edge.getTotalLength(), style = getComputedStyle(edge);
    const endpoints = [['from', 0, Math.min(0.1, len)], ['to', len, Math.max(0, len - 0.1)]].map(([role, at, near]) => {
      const p = edge.getPointAtLength(at), q = edge.getPointAtLength(near);
      const g = groups.find(n => n.dataset.nodeId === edge.dataset[role]);
      const outlines = [...g.querySelectorAll('.node')];
      const outward = Math.sign(q.x - p.x);
      const hasMarker = role === 'to' || edge.dataset.bidirectional === 'true';
      const markerAttr = role === 'to' ? 'marker-end' : 'marker-start';
      const id = edge.getAttribute(markerAttr)?.match(/#([^\)]+)/)?.[1];
      const marker = id ? document.getElementById(id) : null;
      const markerFill = marker ? getComputedStyle(marker.firstElementChild).fill : null;
      // Locate real continuous outlines via point-in-stroke. For dashed shapes,
      // intersect the browser-flattened path instead; a dash hole is not a gap
      // in the geometric silhouette. Nothing in the live SVG is modified.
      const dashed = outlines.some(e => getComputedStyle(e).strokeDasharray !== 'none');
      let firstStroke = null;
      if (dashed) {
        const intersections = [];
        for (const shape of outlines) {
          const length = shape.getTotalLength(), steps = Math.min(20000, Math.ceil(length * 5));
          let a = shape.getPointAtLength(0);
          for (let i = 1; i <= steps; i++) {
            const b = shape.getPointAtLength(length * i / steps);
            if ((a.y <= p.y && b.y >= p.y || b.y <= p.y && a.y >= p.y) && Math.abs(b.y - a.y) > 1e-7) {
              const x = a.x + (p.y - a.y) * (b.x - a.x) / (b.y - a.y);
              const distance = (p.x - x) * outward;
              if (distance >= 0) intersections.push(distance - parseFloat(getComputedStyle(shape).strokeWidth) / 2);
            }
            a = b;
          }
        }
        if (intersections.length) firstStroke = Math.min(...intersections);
      } else for (let d = 0; d <= 40; d += 0.05) {
        if (outlines.some(e => e.isPointInStroke(new DOMPoint(p.x - outward * d, p.y)))) { firstStroke = d; break; }
      }
      const markerProjection = marker ? (() => {
        const b = marker.firstElementChild.getBBox(), ref = marker.refX.baseVal.value;
        const start = role === 'from';
        return start ? ref - b.x : b.x + b.width - ref;
      })() : 0;
      const visibleGap = firstStroke === null ? null : firstStroke - markerProjection;
      return { role, node: g.dataset.nodeId, shape: g.dataset.shape, x: p.x, y: p.y,
        horizontal: Math.abs(q.y - p.y) < 0.001, outward, firstStroke,
        contourMethod: dashed ? 'browser path intersection (dash-independent)' : 'native point-in-stroke',
        hasMarker, markerId: id,
        markerUnits: marker?.getAttribute('markerUnits'), markerProjection, visibleGap, stroke: style.stroke, markerFill };
    });
    return { id: edge.dataset.edgeId, from: edge.dataset.from, to: edge.dataset.to, path: edge.getAttribute('d'),
      stroke: style.stroke, width: style.strokeWidth, endpoints };
  });
  return { viewBox: box(vb), theme: svg.getAttribute('data-theme'), nodes, edges, text: textRecords, overflow,
    tspanCount: svg.querySelectorAll('tspan').length };
}
// Build a pixel reference from a genuine desktop screenshot, including samples
// near the furthest actual node outline. SVG points are transformed by the live
// screen CTM; the same viewBox coordinates are used in downloaded PNG checks.
async function referencePixels(base64) {
  const image = new Image(); image.src = 'data:image/png;base64,' + base64; await image.decode();
  const canvas = document.createElement('canvas'); canvas.width = image.width; canvas.height = image.height;
  const ctx = canvas.getContext('2d'); ctx.drawImage(image, 0, 0);
  const svg = document.getElementById('arch-svg'), matrix = svg.getScreenCTM(), inverse = matrix.inverse();
  const shapes = [...svg.querySelectorAll('[data-node-id] .node')];
  const rightmost = shapes.reduce((a, b) => a.getBBox().x + a.getBBox().width > b.getBBox().x + b.getBBox().width ? a : b);
  const rb = rightmost.getBBox(), right = rb.x + rb.width;
  const bgHex = getComputedStyle(svg).getPropertyValue('--c-mask').trim();
  const bg = bgHex.match(/[a-f0-9]{2}/gi).map(v => parseInt(v, 16));
  const samples = [], used = new Set();
  const add = (shape, p, boundary) => {
    const screen = new DOMPoint(p.x, p.y).matrixTransform(matrix);
    if (screen.x < 2 || screen.x >= canvas.width - 2 || screen.y < 2 || screen.y >= canvas.height - 2) return;
    let best;
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
      const x = Math.round(screen.x) + dx, y = Math.round(screen.y) + dy;
      const rgb = [...ctx.getImageData(x, y, 1, 1).data].slice(0, 3);
      const contrast = rgb.reduce((sum, v, i) => sum + Math.abs(v - bg[i]), 0);
      if (!best || contrast > best.contrast) best = { x, y, rgb, contrast };
    }
    if (best.contrast < 80) return;
    const key = best.x + ',' + best.y;
    if (used.has(key)) return;
    used.add(key);
    const point = new DOMPoint(best.x + 0.5, best.y + 0.5).matrixTransform(inverse);
    samples.push({ x: point.x, y: point.y, rgb: best.rgb, boundary, node: shape.closest('[data-node-id]').dataset.nodeId });
  };
  for (const shape of shapes) {
    const len = shape.getTotalLength();
    for (let i = 0; i < 64; i++) add(shape, shape.getPointAtLength(len * i / 64), false);
  }
  // Keep the boundary subset distinct even if another sample hit the same pixel.
  used.clear();
  for (let i = 0; i < 500; i++) {
    const p = rightmost.getPointAtLength(rightmost.getTotalLength() * i / 500);
    if (p.x > right - 5) add(rightmost, p, true);
  }
  const markerPixels = [];
  for (const edge of svg.querySelectorAll('[data-edge-id]')) for (const role of ['start', 'end']) {
    const id = edge.getAttribute('marker-' + role)?.match(/#([^\\)]+)/)?.[1];
    if (!id) continue;
    const marker = document.getElementById(id), polygon = marker.firstElementChild;
    const vertices = [...polygon.points];
    const cx = vertices.reduce((n, p) => n + p.x, 0) / vertices.length;
    const cy = vertices.reduce((n, p) => n + p.y, 0) / vertices.length;
    const end = role === 'end', length = edge.getTotalLength();
    const p = edge.getPointAtLength(end ? length : 0), q = edge.getPointAtLength(end ? length - 0.1 : 0.1);
    const sign = Math.sign(end ? p.x - q.x : q.x - p.x);
    const point = new DOMPoint(p.x + sign * (cx - marker.refX.baseVal.value),
      p.y + sign * (cy - marker.refY.baseVal.value)).matrixTransform(matrix);
    const fill = getComputedStyle(polygon).fill, expected = (fill.match(/[0-9.]+/g) || []).slice(0, 3).map(Number);
    if (expected.length !== 3) { markerPixels.push({ edge: edge.dataset.edgeId, role, id, fill, sample: null, error: 255 }); continue; }
    let sample = null, error = Infinity;
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) {
      const x = Math.round(point.x) + dx, y = Math.round(point.y) + dy;
      if (x < 0 || y < 0 || x >= canvas.width || y >= canvas.height) continue;
      const rgb = [...ctx.getImageData(x, y, 1, 1).data].slice(0, 3);
      const d = Math.max(...rgb.map((v, i) => Math.abs(v - expected[i])));
      if (d < error) { sample = rgb; error = d; }
    }
    markerPixels.push({ edge: edge.dataset.edgeId, role, id, fill, stroke: getComputedStyle(edge).stroke, sample, error });
  }
  const s = getComputedStyle(document.querySelector('.diagram-container'));
  return { samples, markerPixels, rightmost: { node: rightmost.closest('[data-node-id]').dataset.nodeId, tag: rightmost.localName,
    x: rb.x, y: rb.y, width: rb.width, height: rb.height }, viewBox: { x: svg.viewBox.baseVal.x, y: svg.viewBox.baseVal.y,
    width: svg.viewBox.baseVal.width, height: svg.viewBox.baseVal.height },
    insetLeft: parseFloat(s.paddingLeft) + parseFloat(s.borderLeftWidth),
    insetRight: parseFloat(s.paddingRight) + parseFloat(s.borderRightWidth), screenshotWidth: image.width };
}
async function comparePNG(base64, reference) {
  const image = new Image(); image.src = 'data:image/png;base64,' + base64; await image.decode();
  const canvas = document.createElement('canvas'); canvas.width = image.width; canvas.height = image.height;
  const ctx = canvas.getContext('2d'); ctx.drawImage(image, 0, 0);
  const pixels = ctx.getImageData(0, 0, image.width, image.height).data;
  const vb = reference.viewBox, pad = 32, ratio = 2;
  const svgWidth = image.width / ratio - 2 * pad - reference.insetLeft - reference.insetRight;
  const scale = svgWidth * ratio / vb.width, x0 = (pad + reference.insetLeft) * ratio;
  const points = reference.samples.map(s => ({ ...s, px: Math.round(x0 + (s.x - vb.x) * scale), py: Math.round((s.y - vb.y) * scale) }));
  const difference = (point, offset) => {
    let best = 255;
    for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) {
      const x = point.px + dx, y = point.py + offset + dy;
      if (x < 0 || y < 0 || x >= image.width || y >= image.height) continue;
      const at = (y * image.width + x) * 4;
      best = Math.min(best, (Math.abs(pixels[at] - point.rgb[0]) + Math.abs(pixels[at + 1] - point.rgb[1]) + Math.abs(pixels[at + 2] - point.rgb[2])) / 3);
    }
    return best;
  };
  const shortlist = points.filter((_, i) => i % Math.max(1, Math.floor(points.length / 100)) === 0);
  let best = { error: Infinity, y: 0 };
  // Unknown header reflow is resolved by screenshot/PNG correlation, not an
  // assumed template y coordinate. Search is bounded by the actual image size.
  for (let y = 0; y <= Math.min(image.height - vb.height * scale, 1000); y++) {
    const error = shortlist.reduce((sum, p) => sum + difference(p, y), 0) / shortlist.length;
    if (error < best.error) best = { error, y };
  }
  const results = points.map(p => ({ node: p.node, boundary: p.boundary, error: difference(p, best.y) }));
  const boundary = results.filter(p => p.boundary);
  const perNode = Object.fromEntries([...new Set(results.map(p => p.node))].map(id => {
    const values = results.filter(p => p.node === id);
    return [id, { samples: values.length, hits: values.filter(p => p.error < 40).length }];
  }));
  const r = reference.rightmost;
  const crop = document.createElement('canvas');
  crop.width = Math.ceil((r.width + 16) * scale); crop.height = Math.ceil((r.height + 16) * scale);
  crop.getContext('2d').drawImage(canvas, x0 + (r.x - vb.x - 8) * scale, best.y + (r.y - vb.y - 8) * scale,
    crop.width, crop.height, 0, 0, crop.width, crop.height);
  return { width: image.width, height: image.height, viewBox: vb, svgScale: scale, svgOrigin: { x: x0, y: best.y },
    alignmentMeanError: best.error, samples: results.length, hits: results.filter(p => p.error < 40).length,
    boundarySamples: boundary.length, boundaryHits: boundary.filter(p => p.error < 40).length, perNode,
    rightmost: r, crop: crop.toDataURL('image/png').split(',')[1] };
}
function liveState() {
  const report = document.getElementById('report-container'), wrap = document.querySelector('.diagram-container');
  const b = e => { const r = e.getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height }; };
  return { report: b(report), svg: b(document.getElementById('arch-svg')), scroll: wrap.scrollLeft,
    reportStyle: report.getAttribute('style'), wrapStyle: wrap.getAttribute('style') };
}
function validateSVG(info, name) {
  check(info.nodes.length > 0, name + ': generated node identity');
  for (const node of info.nodes) for (const outline of node.outlines) {
    const b = outline.bbox, v = info.viewBox;
    check(b.x >= v.x && b.y >= v.y && b.x + b.width <= v.x + v.width && b.y + b.height <= v.y + v.height,
      name + ': visible node outline inside viewBox', { node: node.id, outline, viewBox: v });
  }
  for (const e of info.edges) for (const p of e.endpoints) {
    check(p.horizontal && p.firstStroke !== null && p.visibleGap >= 0.2 && p.visibleGap <= 2.2,
      name + ': contour gap', { edge: e.id, ...p });
    if (p.hasMarker) check(p.stroke === p.markerFill, name + ': marker color', { edge: e.id, ...p });
  }
  check(info.overflow.length === 0, name + ': actual text bbox overflow', info.overflow);
}
let finished = false;
function writeChecks() {
  out.completed = new Date().toISOString();
  out.passed = out.failures.length === 0 && !out.error;
  save('checks.json', JSON.stringify(out, null, 2));
}
const watchdog = setTimeout(() => {
  out.error = 'Whole-run deadline (10 minutes)'; writeChecks(); browser.kill(); process.exitCode = 1;
}, 10 * 60 * 1000);
(async () => {
  out.browser = await cdp('Browser.getVersion');
  const { targetId } = await cdp('Target.createTarget', { url: 'about:blank' });
  sessionId = (await cdp('Target.attachToTarget', { targetId, flatten: true })).sessionId;
  await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
  await send('Network.setCacheDisabled', { cacheDisabled: true });
  events.add(message => {
    if (message.method !== 'Fetch.requestPaused') return;
    const { requestId, request } = message.params;
    const local = request.url.startsWith(pathToFileURL(root).href + '/') || /^(data:|blob:|about:)/.test(request.url);
    const allowed = local || (online && allowedURLs.has(request.url));
    out.requests.push({ url: request.url, allowed });
    send(allowed ? 'Fetch.continueRequest' : 'Fetch.failRequest', allowed ? { requestId } : { requestId, errorReason: 'BlockedByClient' }).catch(error => out.failures.push({ label: 'request interception', detail: error.message }));
  });
  await send('Fetch.enable', { patterns: [{ urlPattern: '*' }] });
  await cdp('Browser.setDownloadBehavior', { behavior: 'allowAndName', downloadPath: root, eventsEnabled: true });
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] });
  for (const build of out.builds) {
    if (build.status !== 0) { out.untested.push(build.name + ': browser skipped because strict build failed'); continue; }
    const test = { name: build.name, html: build.html, states: [], exports: [], standalone: [] };
    out.cases.push(test);
    try {
      await viewport(1280); await navigate(build.html);
      test.dependencies = await evaluate(`({html2canvas:typeof window.html2canvas,jspdf:typeof window.jspdf?.jsPDF})`);
      check(await evaluate('currentTheme()') === 'light', build.name + ': initial system light');
      const refs = {};
      for (const width of [1280, 390]) {
        await viewport(width);
        for (const theme of ['light', 'dark']) {
          const stem = `${build.name}-${width}-${theme}`;
          await evaluate(`applyTheme('${theme}');showExportStatus('');setExportMenu(false);document.querySelector('.diagram-container').scrollLeft=0;window.scrollTo(0,0)`);
          const info = await invoke(inspectSVG);
          validateSVG(info, stem);
          const input = JSON.parse(fs.readFileSync(build.input, 'utf8'));
          check(JSON.stringify(info.nodes.map(n => n.id)) === JSON.stringify(input.tiers.flatMap(t => t.nodes.map(n => n.id))),
            stem + ': generated inventory matches input');
          check(info.edges.length === (input.edges || []).length, stem + ': generated edges match input');
          const shot = await screenshot(stem + '.png');
          const state = { width, theme, screenshot: shot.file, svg: info };
          test.states.push(state);
          if (width === 1280) {
            refs[theme] = await invoke(referencePixels, shot.data);
            state.pixelReference = save(stem + '-reference.json', JSON.stringify(refs[theme], null, 2));
            check(refs[theme].samples.filter(p => p.boundary).length >= 8, stem + ': screenshot right contour visible');
            check(refs[theme].markerPixels.every(p => p.sample && p.error < 35), stem + ': actual marker raster fill', refs[theme].markerPixels);
            state.svgFile = await download('SVG', stem + '.svg');
          } else {
            await evaluate(`document.querySelector('.diagram-container').scrollLeft=document.querySelector('.diagram-container').scrollWidth`);
            state.rightEdgeScreenshot = (await screenshot(stem + '-right-edge.png')).file;
          }
          if (!online || test.dependencies.html2canvas !== 'function') {
            out.untested.push(stem + ': real PNG/PDF unavailable; no substitute');
            continue;
          }
          const before = await invoke(liveState);
          await evaluate(`window.__browserAcceptanceMutations=0;window.__browserAcceptanceObserver=new MutationObserver(l=>window.__browserAcceptanceMutations+=l.length);
            window.__browserAcceptanceObserver.observe(document.getElementById('report-container'),{subtree:true,attributes:true,childList:true,characterData:true});`);
          // Calling the original capture is intentional: verifies real html2canvas
          // and no live report mutation. No library or export function is mocked.
          const captureResult = await evaluate(`(async()=>{try{const c=await capture();return {width:c.width,height:c.height};}
            finally{window.__browserAcceptanceObserver.disconnect();}})()`);
          const after = await invoke(liveState);
          const mutations = await evaluate('window.__browserAcceptanceMutations');
          check(JSON.stringify(before) === JSON.stringify(after) && mutations === 0, stem + ': capture leaves live layout unchanged', { before, after, mutations });
          const pngFile = await download('PNG', stem + '-download.png');
          const bytes = fs.readFileSync(pngFile);
          check(bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])), stem + ': PNG signature');
          const pixels = await invoke(comparePNG, bytes.toString('base64'), refs[theme]);
          pixels.rightContourCrop = save(stem + '-right-contour.png', Buffer.from(pixels.crop, 'base64')); delete pixels.crop;
          check(pixels.width === captureResult.width && pixels.height === captureResult.height, stem + ': capture/download dimensions');
          check(pixels.boundarySamples >= 8 && pixels.boundaryHits / pixels.boundarySamples >= 0.75,
            stem + ': exported rightmost contour matches screenshot', pixels);
          check(pixels.hits / pixels.samples >= 0.8 && Object.values(pixels.perNode).every(p => p.hits / p.samples >= 0.65),
            stem + ': all node outlines match screenshot', pixels);
          const exported = { width, theme, pngFile, capture: captureResult, before, after, mutations, pixels };
          test.exports.push(exported);
          if (test.dependencies.jspdf === 'function') {
            const pdfFile = await download('PDF', stem + '.pdf');
            const pdf = fs.readFileSync(pdfFile).toString('latin1');
            const pages = (pdf.match(/\/Type\s*\/Page\b/g) || []).length;
            const imageSizes = [...pdf.matchAll(/\/Subtype\s*\/Image\s*\/Width\s+(\d+)\s*\/Height\s+(\d+)/g)].map(m => ({ width: +m[1], height: +m[2] }));
            const mediaBox = pdf.match(/\/MediaBox\s*\[([^\]]+)\]/)?.[1].trim().split(/\s+/).map(Number);
            exported.pdf = { pdfFile, pages, imageSizes, mediaBox, bytes: Buffer.byteLength(pdf, 'latin1') };
            check(pdf.startsWith('%PDF-') && pages === 1 && imageSizes.some(s => s.width === pixels.width && s.height === pixels.height),
              stem + ': real PDF single page and full raster dimensions', exported.pdf);
            check(mediaBox && Math.abs(mediaBox[2] - pixels.width * 0.75) < 0.01 && Math.abs(mediaBox[3] - pixels.height * 0.75) < 0.01,
              stem + ': PDF page fits image without clipping', exported.pdf);
          } else out.untested.push(stem + ': real PDF unavailable: original jsPDF CDN');
        }
      }
      // Re-open actual downloaded SVG in Chrome: no HTML styles or replacement
      // diagram content. Validate semantic edges and geometry again in both themes.
      await viewport(1280);
      for (const state of test.states.filter(s => s.width === 1280)) {
        await navigate(state.svgFile);
        const info = await invoke(inspectSVG);
        check(await evaluate('document.documentElement.localName') === 'svg', build.name + ': standalone SVG root');
        check(info.theme === state.theme, build.name + ': standalone theme');
        validateSVG(info, build.name + '-standalone-' + state.theme);
        test.standalone.push({ theme: state.theme, file: state.svgFile, svg: info,
          screenshot: (await screenshot(build.name + '-standalone-' + state.theme + '.png')).file });
      }
      await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'dark' }] });
      await navigate(build.html);
      check(await evaluate('currentTheme()') === 'dark', build.name + ': system dark');
      await evaluate('toggleTheme()');
      check(await evaluate('currentTheme()') === 'light', build.name + ': user theme toggle');
      await navigate(build.html);
      check(await evaluate('currentTheme()') === 'dark', build.name + ': reload discards theme toggle');
      if (build.name === 'font_fallback') {
        // Supplemental diagnostic ONLY, after all untouched generated-output
        // acceptance. Wrap the same text without changing font, position, or
        // contents, so the saved tspan reproducer cannot masquerade as a build.
        const original = await invoke(inspectSVG);
        await evaluate(`(() => {
          const text=document.querySelector('[data-node-id="math"] text.t');
          const span=document.createElementNS(text.namespaceURI,'tspan');span.textContent=text.textContent;
          text.replaceChildren(span);
        })()`);
        const diagnostic = await invoke(inspectSVG);
        const beforeText = original.text.find(t => t.node === 'math');
        const afterText = diagnostic.text.find(t => t.node === 'math');
        check(JSON.stringify(beforeText.bbox) === JSON.stringify(afterText.bbox), 'tspan wrapper preserves measured bbox', { beforeText, afterText });
        test.tspanDiagnostic = { supplemental: true, notGeneratorOutput: true, beforeText, afterText,
          file: await download('SVG', 'font-fallback-tspan-diagnostic.svg'),
          screenshot: (await screenshot('font-fallback-tspan-diagnostic.png')).file };
        await send('DOM.enable'); await send('CSS.enable');
        const dom = (await send('DOM.getDocument')).root.nodeId;
        const fontNode = (await send('DOM.querySelector', { nodeId: dom, selector: '[data-node-id="math"] text.t' })).nodeId;
        test.tspanDiagnostic.platformFonts = await send('CSS.getPlatformFontsForNode', { nodeId: fontNode });
        save('font-fallback-tspan-diagnostic.json', JSON.stringify(test.tspanDiagnostic, null, 2));
      }
      await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] });
    } catch (error) { test.error = error.stack; out.failures.push({ label: build.name + ': browser execution', detail: error.stack }); }
    save(build.name + '-checks.json', JSON.stringify(test, null, 2));
    writeChecks();
  }
  out.untested.push('System clipboard paste round trip; no permissions changed.',
    'Other browsers, OS/font stacks, physical mobile devices, PDF viewer rendering/printing.',
    'Screenshot comparison tests sampled visible node outlines; not exhaustive per-pixel equivalence or glyph-outline containment.');
  out.sourceHashesAfter = Object.fromEntries(tracked.map(name => [name, hash(path.join(skill, name))]));
  check(JSON.stringify(out.sourceHashes) === JSON.stringify(out.sourceHashesAfter), 'Source remained stable during run', out.sourceHashesAfter);
  finished = true;
})().catch(error => { out.error = error.stack; }).finally(async () => {
  clearTimeout(watchdog); writeChecks();
  console.log(JSON.stringify({ completed: finished, passed: out.passed, root, builds: out.builds.length,
    cases: out.cases.length, failures: out.failures.length, untested: out.untested, error: out.error }, null, 2));
  process.exitCode = out.passed ? 0 : 1;
  try { await cdp('Browser.close'); } catch (_) { /* already exited */ }
  browser.kill();
});
