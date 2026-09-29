'use strict';
// Native CDP only; no packages. OUTPUT_DIR must exist and be outside the source.
// node tests/browser_check.cjs /absolute/workspace/implementation/template [--online]
// Offline by default. --online allows ONLY the two original CDN URLs for real
// PNG/PDF exports; missing CDN access is reported as untested, never substituted.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { pathToFileURL } = require('node:url');
const { StringDecoder } = require('node:string_decoder');
const source = path.resolve(__dirname, '../resources/template.html');
const outputArg = process.argv[2];
assert(outputArg && path.isAbsolute(outputArg) && fs.statSync(outputArg).isDirectory(), 'Provide an existing absolute output directory');
const output = fs.realpathSync(outputArg);
const sourceRoot = fs.realpathSync(path.resolve(__dirname, '..'));
assert(output !== sourceRoot && !output.startsWith(sourceRoot + path.sep), 'Do not write browser artifacts into the source tree');
const online = process.argv.includes('--online');
const root = fs.mkdtempSync(path.join(output, online ? 'online-' : 'offline-'));
const sourceURL = pathToFileURL(source).href;
const allowedURLs = new Set([
  'https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js',
  'https://cdn.jsdelivr.net/npm/jspdf@2.5.2/dist/jspdf.umd.min.js'
]);
const chrome = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browser = spawn(chrome, [
  '--headless=new', '--remote-debugging-pipe', `--user-data-dir=${root}/chrome-profile`,
  '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
  '--disable-component-update', '--disable-sync', '--disable-extensions',
  '--metrics-recording-only', '--disable-domain-reliability',
  ...(!online ? ['--proxy-server=http://127.0.0.1:9', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost'] : []),
  'about:blank'
], { stdio: ['ignore', 'ignore', 'pipe', 'pipe', 'pipe'] });
let seq = 0, buffer = '', sessionId;
const pending = new Map(), events = new Set(), decoder = new StringDecoder('utf8');
const out = { mode: online ? 'original-CDN' : 'offline', source, root, requests: [], checks: {}, untested: [] };
browser.stderr.on('data', d => fs.appendFileSync(path.join(root, 'chrome.log'), d));
browser.on('error', error => { console.error(error); process.exitCode = 1; });
browser.stdio[4].on('data', data => {
  buffer += decoder.write(data);
  let i;
  while ((i = buffer.indexOf('\0')) >= 0) {
    const raw = buffer.slice(0, i); buffer = buffer.slice(i + 1);
    if (!raw) continue;
    const message = JSON.parse(raw);
    if (pending.has(message.id)) {
      const entry = pending.get(message.id); pending.delete(message.id); clearTimeout(entry.timer);
      if (message.error) entry.reject(new Error(JSON.stringify(message.error))); else entry.resolve(message.result);
    } else {
      for (const listener of events) listener(message);
    }
  }
});
function cdp(method, params = {}, sid) {
  const id = ++seq;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 45000);
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
async function navigate(url) {
  await send('Page.navigate', { url });
  await evaluate(`new Promise(resolve => { document.readyState === 'complete' ? resolve(true) : window.addEventListener('load', () => resolve(true), {once:true}); })`);
}
async function screenshot(name) {
  const result = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  fs.writeFileSync(path.join(root, name), Buffer.from(result.data, 'base64'));
}
async function key(key, code = key) {
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key, code, windowsVirtualKeyCode: key === 'Enter' ? 13 : 27, ...(key === 'Enter' ? {text:'\r',unmodifiedText:'\r'} : {}) });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key, code, windowsVirtualKeyCode: key === 'Enter' ? 13 : 27 });
}
async function download(expression, name) {
  let guid, listener, timer;
  const completed = new Promise((resolve, reject) => {
    timer = setTimeout(() => reject(new Error(`Download timeout: ${name}`)), 45000);
    listener = message => {
      if (message.method === 'Browser.downloadWillBegin') guid = message.params.guid;
      if (message.method === 'Browser.downloadProgress' && message.params.guid === guid) {
        if (message.params.state === 'completed') resolve(guid);
        if (message.params.state === 'canceled') reject(new Error(`Download canceled: ${name}`));
      }
    };
    events.add(listener);
  });
  // Attach rejection handler immediately, while Runtime.evaluate is in flight.
  completed.catch(() => {});
  try {
    await evaluate(expression);
    const id = await completed;
    const target = path.join(root, name);
    fs.renameSync(path.join(root, id), target);
    assert(fs.statSync(target).size > 0);
    return target;
  } finally { clearTimeout(timer); events.delete(listener); }
}
const types = 'frontend backend database cache compute cloud bus security observability generic'.split(' ');
const button = kind => `document.querySelector('[onclick="download${kind}(this)"]')`;
async function colors() {
  return evaluate(`(() => {
    const svg = document.querySelector('svg');
    return ${JSON.stringify(types)}.map(type => {
      const edge = document.createElementNS(svg.namespaceURI, 'line');
      edge.setAttribute('class', 'arrow ' + type); svg.append(edge);
      const stroke = getComputedStyle(edge).stroke;
      const end = getComputedStyle(document.getElementById('arrowhead-' + type).firstElementChild).fill;
      const start = getComputedStyle(document.getElementById('arrowhead-start-' + type).firstElementChild).fill;
      edge.remove(); return {type, stroke, end, start};
    });
  })()`);
}
function assertColors(values) {
  for (const item of values) { assert.equal(item.stroke, item.end); assert.equal(item.stroke, item.start); }
}
async function rasterMarkers(theme) {
  const result = await evaluate(`(async () => {
    const source = document.querySelector('svg');
    const ns = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('xmlns', ns); svg.setAttribute('data-theme', '${theme}');
    svg.setAttribute('width', '1600'); svg.setAttribute('height', '1040'); svg.setAttribute('viewBox', '0 0 200 130');
    svg.append(source.querySelector('style').cloneNode(true), source.querySelector('defs').cloneNode(true));
    const add = (tag, attrs) => { const e = document.createElementNS(ns, tag); for (const [k,v] of Object.entries(attrs)) e.setAttribute(k,v); svg.append(e); };
    add('rect', {width:200,height:130,fill:'var(--c-mask)'});
    ['thin','','thick'].forEach((weight, index) => {
      const y = 20 + index * 40;
      add('line', {class:'arrow backend ' + weight,x1:26,y1:y,x2:164,y2:y,'marker-start':'url(#arrowhead-start-backend)','marker-end':'url(#arrowhead-backend)'});
      add('rect', {class:'node backend',x:0,y:y-10,width:20,height:20});
      add('rect', {class:'node backend',x:170,y:y-10,width:30,height:20});
    });
    const image = new Image();
    image.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(svg));
    await image.decode();
    const canvas = document.createElement('canvas'); canvas.width=1600;canvas.height=1040;
    const ctx=canvas.getContext('2d');ctx.drawImage(image,0,0);
    const bg=ctx.getImageData(800,4,1,1).data;
    const rows=[20,60,100].map(y => {
      const pixels=ctx.getImageData(0,y*8,1600,1).data;
      const xs=[];
      for(let x=21*8;x<169*8;x++) {
        const p=pixels.slice(x*4,x*4+3);
        if(p.some((v,i)=>Math.abs(v-bg[i])>20)) xs.push(x);
      }
      return {strokeY:y,left:Math.min(...xs)/8,right:(Math.max(...xs)+1)/8};
    });
    return {rows,png:canvas.toDataURL('image/png').split(',')[1]};
  })()`);
  fs.writeFileSync(path.join(root, `markers-${theme}.png`), Buffer.from(result.png, 'base64'));
  for (const row of result.rows) {
    assert(Math.abs(row.left - 22) < 0.3, JSON.stringify(row));
    assert(Math.abs(row.right - 168) < 0.3, JSON.stringify(row));
  }
  return result.rows;
}
(async () => {
  const { targetId } = await cdp('Target.createTarget', { url: 'about:blank' });
  sessionId = (await cdp('Target.attachToTarget', { targetId, flatten: true })).sessionId;
  await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
  await send('Network.setCacheDisabled', { cacheDisabled: true });
  // The page may request only its source/output files, inline URLs and the
  // original two libraries (online mode). No substitute URLs or font traffic.
  events.add(message => {
    if (message.method !== 'Fetch.requestPaused') return;
    const { requestId, request } = message.params;
    const local = request.url === sourceURL || request.url.startsWith(pathToFileURL(root).href + '/') || /^(data:|blob:|about:)/.test(request.url);
    const allowed = local || (online && allowedURLs.has(request.url));
    out.requests.push({ url: request.url, allowed });
    send(allowed ? 'Fetch.continueRequest' : 'Fetch.failRequest', allowed ? { requestId } : { requestId, errorReason: 'BlockedByClient' }).catch(console.error);
  });
  await send('Fetch.enable', { patterns: [{ urlPattern: '*' }] });
  await cdp('Browser.setDownloadBehavior', { behavior: 'allowAndName', downloadPath: root, eventsEnabled: true });
  await send('Emulation.setDeviceMetricsOverride', { width: 1280, height: 1100, deviceScaleFactor: 1, mobile: false });
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] });
  await navigate(sourceURL);
  assert.equal(await evaluate('currentTheme()'), 'light');
  assert.equal(await evaluate('document.documentElement.lang'), 'zh-CN');
  await evaluate('toggleTheme()'); assert.equal(await evaluate('currentTheme()'), 'dark');
  await navigate(sourceURL); assert.equal(await evaluate('currentTheme()'), 'light');
  out.checks.reloadResetsToSystem = true;
  out.checks.dependencies = await evaluate(`({html2canvas:typeof window.html2canvas,jspdf:typeof window.jspdf?.jsPDF})`);

  await evaluate(`document.getElementById('export-menu-btn').focus()`); await key('Enter');
  assert.equal(await evaluate(`document.getElementById('export-menu-btn').getAttribute('aria-expanded')`), 'true');
  await evaluate(`${button('SVG')}.focus()`); await key('Escape');
  assert.deepEqual(await evaluate(`({expanded:document.getElementById('export-menu-btn').getAttribute('aria-expanded'),focus:document.activeElement.id})`), { expanded: 'false', focus: 'export-menu-btn' });
  out.checks.keyboard = true;

  out.checks.fonts = await evaluate(`(() => {
    const svg=document.getElementById('arch-svg'),t=document.createElementNS(svg.namespaceURI,'text');
    t.setAttribute('font-size','11');t.setAttribute('class','t');t.id='font-probe';svg.append(t);
    const results={};
    for(const s of ['W'.repeat(29),'i'.repeat(29),'API 网关','用户认证服务']) {t.textContent=s;results[s]={actual:t.getComputedTextLength(),font:getComputedStyle(t).fontFamily};}
    t.textContent='W'.repeat(29);return results;
  })()`);
  const wide=out.checks.fonts['W'.repeat(29)].actual, narrow=out.checks.fonts['i'.repeat(29)].actual;
  assert(Math.abs(wide - narrow) < 0.1); assert(Math.abs(wide - 29 * 11 * 0.6) < 4);
  assert(Math.abs(out.checks.fonts['用户认证服务'].actual - 66) < 1);
  await send('DOM.enable'); await send('CSS.enable');
  const dom = (await send('DOM.getDocument')).root.nodeId;
  const fontNode = (await send('DOM.querySelector', { nodeId: dom, selector: '#font-probe' })).nodeId;
  out.checks.platformFont = await send('CSS.getPlatformFontsForNode', { nodeId: fontNode });
  await evaluate(`document.getElementById('font-probe').remove()`);

  for (const theme of ['light', 'dark']) {
    await evaluate(`applyTheme('${theme}')`);
    out.checks[theme] = { colors: await colors(), markerPixels: await rasterMarkers(theme) };
    assertColors(out.checks[theme].colors);
    await screenshot(`template-${theme}.png`);
    out.checks[theme].svg = await download(`downloadSVG(${button('SVG')})`, `diagram-${theme}.svg`);
  }

  if (!online || out.checks.dependencies.html2canvas !== 'function') {
    await evaluate(`downloadPNG(${button('PNG')})`);
    const failure = await evaluate(`({text:document.getElementById('export-status').textContent,visible:document.getElementById('export-status').getBoundingClientRect().height>0})`);
    assert(failure.visible && failure.text.includes('html2canvas') && failure.text.includes('SVG'));
    out.checks.pngFallback = failure;
  }
  if (!online || out.checks.dependencies.jspdf !== 'function') {
    await evaluate(`downloadPDF(${button('PDF')})`);
    const failure = await evaluate(`document.getElementById('export-status').textContent`);
    assert(failure.includes('jsPDF') && failure.includes('SVG')); out.checks.pdfFallback = failure;
  }
  // Exercise a genuine clipboard-denied/missing-dependency path, without granting
  // permissions or pretending that a mocked clipboard write is an end-to-end copy.
  await evaluate(`copyAsImage(document.querySelector('[onclick="copyAsImage(this)"]'))`);
  out.checks.clipboardStatus = await evaluate(`document.getElementById('export-status').textContent`);
  out.untested.push('System clipboard paste round trip (no clipboard permission changes).');

  for (const theme of ['light', 'dark']) {
    await navigate(pathToFileURL(out.checks[theme].svg).href);
    assert.equal(await evaluate('document.documentElement.localName'), 'svg');
    assert.equal(await evaluate(`document.documentElement.getAttribute('data-theme')`), theme);
    assertColors(await colors());
    const other = theme === 'light' ? 'dark' : 'light';
    const before = await evaluate(`getComputedStyle(document.querySelector('.t')).fill`);
    const beforeBackground = await evaluate(`getComputedStyle(document.documentElement.firstElementChild).fill`);
    await evaluate(`document.documentElement.setAttribute('data-theme','${other}')`);
    assert.notEqual(await evaluate(`getComputedStyle(document.querySelector('.t')).fill`), before);
    assert.notEqual(await evaluate(`getComputedStyle(document.documentElement.firstElementChild).fill`), beforeBackground);
    assertColors(await colors());
    await evaluate(`document.documentElement.setAttribute('data-theme','${theme}')`);
    await screenshot(`standalone-${theme}.png`);
    out.checks[theme].standalone = true;
  }

  await navigate(sourceURL);
  if (online && out.checks.dependencies.html2canvas === 'function') {
    out.checks.raster = [];
    for (const width of [1280, 390]) {
      await send('Emulation.setDeviceMetricsOverride', { width, height: 1100, deviceScaleFactor: 1, mobile: width === 390 });
      for (const theme of ['light', 'dark']) {
        await evaluate(`applyTheme('${theme}');showExportStatus('');setExportMenu(false);document.querySelector('.diagram-container').scrollLeft=200`);
        const result = await evaluate(`(async () => {
          const svg=document.getElementById('arch-svg'),wrap=document.querySelector('.diagram-container'),report=document.getElementById('report-container');
          const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};};
          const before={report:rect(report),svg:rect(svg),scroll:wrap.scrollLeft,reportStyle:report.getAttribute('style'),wrapStyle:wrap.getAttribute('style')};
          let mutations=0;const observer=new MutationObserver(list=>mutations+=list.length);observer.observe(report,{subtree:true,attributes:true,childList:true,characterData:true});
          const canvas=await capture();observer.disconnect();
          const after={report:rect(report),svg:rect(svg),scroll:wrap.scrollLeft,reportStyle:report.getAttribute('style'),wrapStyle:wrap.getAttribute('style')};
          const ctx=canvas.getContext('2d');
          // Region right boundary at x=980 proves the complete SVG was rasterized,
          // not just a wider blank canvas around a still-clipped 390px viewport.
          const fullWidth=canvas.width/2-64,svgWidth=fullWidth-50;
          let hits=0;
          const expected=getComputedStyle(svg).getPropertyValue('--cloud').trim();
          const rgb=expected.slice(1).match(/../g).map(v=>parseInt(v,16));
          const x=Math.round((32+25+svgWidth*.98)*2);
          for(let y=0;y<canvas.height;y++) {
            const pixel=ctx.getImageData(x,y,1,1).data;
            if(rgb.every((v,i)=>Math.abs(v-pixel[i])<70)) hits++;
          }
          return {before,after,mutations,width:canvas.width,height:canvas.height,rightBoundaryPixels:hits,png:canvas.toDataURL('image/png').split(',')[1]};
        })()`);
        assert.deepEqual(result.before, result.after); assert.equal(result.mutations, 0);
        assert(result.width >= (900 + 50 + 64) * 2); assert(result.rightBoundaryPixels > 40, JSON.stringify({width,theme,...result,png:undefined}));
        fs.writeFileSync(path.join(root, `capture-${width}-${theme}.png`), Buffer.from(result.png, 'base64')); delete result.png;
        const png = await download(`downloadPNG(${button('PNG')})`, `download-${width}-${theme}.png`);
        const bytes = fs.readFileSync(png);
        assert.equal(bytes.subarray(1,4).toString(), 'PNG');
        assert.equal(bytes.readUInt32BE(16), result.width);
        if (out.checks.dependencies.jspdf === 'function') {
          const pdf = await download(`downloadPDF(${button('PDF')})`, `download-${width}-${theme}.pdf`);
          const content = fs.readFileSync(pdf).toString('latin1');
          assert(content.startsWith('%PDF-'));
          assert.equal((content.match(/\/Type\s*\/Page\b/g) || []).length, 1);
          assert(content.includes('/Subtype /Image'));
          result.pdf = { file: pdf, pages: 1, raster: true };
        }
        out.checks.raster.push({viewport:width,theme,...result});
      }
    }
    if (out.checks.dependencies.jspdf !== 'function') out.untested.push('PDF end-to-end: original jsPDF CDN unavailable.');
  } else {
    out.untested.push(online ? 'PNG/PDF end-to-end: original CDN unavailable; no stubs used.' : 'PNG/PDF end-to-end: offline mode intentionally blocks CDN; rerun --online.');
    await send('Emulation.setDeviceMetricsOverride', {width:390,height:844,deviceScaleFactor:1,mobile:true});
    await screenshot('template-mobile.png');
    out.checks.mobileLayout = await evaluate(`({report:document.getElementById('report-container').getBoundingClientRect().width,svg:document.getElementById('arch-svg').getBoundingClientRect().width,scrollWidth:document.querySelector('.diagram-container').scrollWidth})`);
  }
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'dark' }] });
  await navigate(sourceURL); assert.equal(await evaluate('currentTheme()'), 'dark');
  out.checks.systemDark = true;
  out.passed = true;
})().catch(error => { out.passed=false;out.error=error.stack;process.exitCode=1;console.error(error); }).finally(async () => {
  fs.writeFileSync(path.join(root, 'checks.json'), JSON.stringify(out,null,2));
  console.log(JSON.stringify({passed:out.passed,root,checks:Object.keys(out.checks),untested:out.untested,error:out.error},null,2));
  try { await cdp('Browser.close'); } catch (_) { /* browser may already have exited */ }
  browser.kill();
});
