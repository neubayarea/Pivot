// Records takes of the live site with headless Chrome (CDP screencast).
// usage: node rec.mjs <take|probe> [url]
import { spawn, execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const BASE = path.dirname(new URL(import.meta.url).pathname).replace(/^\/([A-Za-z]:)/, '$1');
const W = 1920, H = 1080;
const SITE = 'https://pivot.in-stacks.com/';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const take = process.argv[2];

const CURSOR_JS = `(() => {
  const install = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div'); c.id = '__cur';
    c.innerHTML = '<svg width="30" height="30" viewBox="0 0 24 24"><path d="M4 2 L4 19 L8.5 14.8 L11.6 21.6 L14.4 20.4 L11.4 13.8 L17.6 13.8 Z" fill="#111" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg>';
    c.style.cssText = 'position:fixed;left:' + (window.__mx||960) + 'px;top:' + (window.__my||540) + 'px;width:30px;height:30px;margin:-3px 0 0 -5px;z-index:2147483647;pointer-events:none;filter:drop-shadow(0 1px 2px rgba(0,0,0,.45));transition:transform .12s ease;transform-origin:5px 3px;';
    const halo = document.createElement('div'); halo.id = '__halo';
    halo.style.cssText = 'position:fixed;width:44px;height:44px;margin:-22px 0 0 -22px;border-radius:50%;background:rgba(250,204,21,.38);z-index:2147483646;pointer-events:none;opacity:0;transition:opacity .25s ease, transform .25s ease;transform:scale(.4);';
    document.documentElement.appendChild(halo);
    document.documentElement.appendChild(c);
    addEventListener('mousemove', e => { window.__mx = e.clientX; window.__my = e.clientY; c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; halo.style.left = e.clientX + 'px'; halo.style.top = e.clientY + 'px'; }, true);
    addEventListener('mousedown', () => { c.style.transform = 'scale(.82)'; halo.style.opacity = '1'; halo.style.transform = 'scale(1)'; }, true);
    addEventListener('mouseup', () => { c.style.transform = 'scale(1)'; setTimeout(() => { halo.style.opacity = '0'; halo.style.transform = 'scale(.4)'; }, 180); }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install); else install();
})();`;

const port = 9300 + Math.floor(Math.random() * 500);
const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'pivotrec-'));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`,
  `--window-size=${W},${H}`, '--hide-scrollbars', '--force-device-scale-factor=1', '--mute-audio',
  '--no-first-run', '--no-default-browser-check', '--disable-extensions', 'about:blank'], { stdio: 'ignore' });

async function getWs() {
  for (let i = 0; i < 150; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const pg = list.find(t => t.type === 'page');
      if (pg) return pg.webSocketDebuggerUrl;
    } catch {}
    await sleep(100);
  }
  throw new Error('chrome did not start');
}
const ws = new WebSocket(await getWs());
await new Promise(r => ws.addEventListener('open', r, { once: true }));
let seq = 0; const pending = new Map(); const listeners = [];
ws.addEventListener('message', ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { const { res, rej } = pending.get(m.id); pending.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
  else if (m.method) for (const f of [...listeners]) f(m);
});
const send = (method, params = {}) => new Promise((res, rej) => { const i = ++seq; pending.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });

// frames
const fdir = path.join(BASE, 'takes', take);
let frames = [], marks = [], recording = false;
listeners.push(m => {
  if (m.method !== 'Page.screencastFrame') return;
  const { data, metadata, sessionId } = m.params;
  send('Page.screencastFrameAck', { sessionId }).catch(() => {});
  if (!recording) return;
  const f = `f${String(frames.length).padStart(6, '0')}.jpg`;
  fs.writeFileSync(path.join(fdir, f), Buffer.from(data, 'base64'));
  frames.push({ f, t: metadata.timestamp });
});
const mark = name => { marks.push({ name, t: Date.now() / 1000 }); console.log('mark', name); };

await send('Page.enable'); await send('Runtime.enable');
await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
await send('Page.addScriptToEvaluateOnNewDocument', { source: CURSOR_JS });

async function evaluate(expr) {
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error('eval: ' + JSON.stringify(r.exceptionDetails).slice(0, 400));
  return r.result.value;
}
async function goto(url, settle = 1500) {
  const loaded = new Promise(r => { const f = m => { if (m.method === 'Page.loadEventFired') { listeners.splice(listeners.indexOf(f), 1); r(); } }; listeners.push(f); });
  await send('Page.navigate', { url });
  await Promise.race([loaded, sleep(25000)]);
  await sleep(settle);
}
async function waitFor(expr, timeout = 30000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeout) { try { if (await evaluate(expr)) return true; } catch {} await sleep(200); }
  throw new Error('timeout: ' + expr.slice(0, 160));
}
const hasText = s => `!!document.body && document.body.innerText.includes(${JSON.stringify(s)})`;
const waitText = (s, t) => waitFor(hasText(s), t);

// find an element by its visible text; returns its centre after scrolling it into view if needed
const FIND = `(q) => {
  const norm = s => (s || '').replace(/\\s+/g, ' ').trim();
  const sel = q.sel || 'button,a,[role=tab],[role=button],[role=option],summary,label,li,span,div,p,h1,h2,h3,h4,td,th,text,tspan,g';
  const all = [...document.querySelectorAll(sel)];
  let m = all.filter(e => {
    if (e.id === '__cur') return false;
    const t = norm(e.innerText ?? e.textContent) || norm(e.getAttribute && (e.getAttribute('aria-label') || e.getAttribute('title')));
    const ok = q.exact === false ? t.includes(q.text) : (t === q.text || norm(e.getAttribute && e.getAttribute('aria-label')) === q.text);
    if (!ok) return false;
    const r = e.getBoundingClientRect();
    if (!(r.width > 0 && r.height > 0)) return false;
    const st = getComputedStyle(e); if (st.visibility === 'hidden' || st.display === 'none' || +st.opacity === 0) return false;
    if (q.minY != null && r.top < q.minY) return false;
    if (q.maxY != null && r.top > q.maxY) return false;
    return true;
  });
  m = m.filter(e => !m.some(o => o !== e && e.contains(o)));
  const el = m[q.nth || 0];
  if (!el) return null;
  const tok = 'r' + Math.random().toString(36).slice(2);
  el.setAttribute('data-rec', tok);
  return tok;
}`;
async function locate(q, { scroll = true } = {}) {
  if (typeof q === 'string') q = { text: q };
  let tok = null; const t0 = Date.now();
  while (!tok && Date.now() - t0 < (q.timeout || 20000)) { tok = await evaluate(`(${FIND})(${JSON.stringify(q)})`); if (!tok) await sleep(250); }
  if (!tok) throw new Error('not found: ' + JSON.stringify(q));
  let r = await evaluate(`(() => { const r = document.querySelector('[data-rec=${tok}]').getBoundingClientRect(); return {x: r.left + r.width/2, y: r.top + r.height/2, top: r.top, bottom: r.bottom}; })()`);
  if (scroll && (r.top < 90 || r.bottom > H - 40)) {
    const target = await evaluate(`scrollY + ${r.y} - ${q.at ?? H * 0.45}`);
    await scrollToY(target, q.scrollMs || 900);
    r = await evaluate(`(() => { const r = document.querySelector('[data-rec=${tok}]').getBoundingClientRect(); return {x: r.left + r.width/2, y: r.top + r.height/2, top: r.top, bottom: r.bottom}; })()`);
  }
  return { x: r.x + (q.dx || 0), y: r.y + (q.dy || 0) };
}
let mx = W * 0.55, my = H * 0.55;
async function moveTo(x, y, ms = 650) {
  const steps = Math.max(10, Math.round(ms / 16)); const sx = mx, sy = my;
  for (let i = 1; i <= steps; i++) {
    const p = i / steps; const e = p < .5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: sx + (x - sx) * e, y: sy + (y - sy) * e });
    await sleep(ms / steps);
  }
  mx = x; my = y;
}
async function clickAt(x, y, ms) {
  await moveTo(x, y, ms); await sleep(220);
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 });
  await sleep(90);
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 });
}
async function click(q, ms) { const p = await locate(q); await clickAt(p.x, p.y, ms); }
async function hover(q, ms = 750) { try { const p = await locate({ timeout: 4000, ...(typeof q === 'string' ? { text: q } : q) }); await moveTo(p.x, p.y, ms); } catch (e) { console.log('hover skipped', e.message.slice(0, 120)); } }
async function scrollToY(y, ms = 1200) {
  const y0 = await evaluate('scrollY'); const steps = Math.max(10, Math.round(ms / 16));
  for (let i = 1; i <= steps; i++) {
    const p = i / steps; const e = p < .5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
    await evaluate(`scrollTo(0, ${y0 + (y - y0) * e})`); await sleep(ms / steps);
  }
}
async function scrollToText(text, at = 140, ms = 1200, extra = {}) {
  const tok = await evaluate(`(${FIND})(${JSON.stringify({ text, exact: false, ...extra })})`);
  if (!tok) { console.log('scroll skipped', text); return; }
  const y = await evaluate(`scrollY + document.querySelector('[data-rec=${tok}]').getBoundingClientRect().top - ${at}`);
  await scrollToY(y, ms);
}
async function shot(file) {
  const r = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(path.join(BASE, 'probe', file), Buffer.from(r.data, 'base64'));
}
async function startRec() {
  fs.rmSync(fdir, { recursive: true, force: true }); fs.mkdirSync(fdir, { recursive: true });
  await send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
  await sleep(200); recording = true; mark('start');
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: mx, y: my });
}
async function stopRec() {
  mark('end'); await sleep(300); recording = false;
  await send('Page.stopScreencast');
  fs.writeFileSync(path.join(fdir, 'frames.json'), JSON.stringify({ frames, marks }));
  // build mp4 at constant 30 fps
  const lines = ['ffconcat version 1.0'];
  frames.forEach((fr, i) => { const d = i + 1 < frames.length ? frames[i + 1].t - fr.t : 0.5; lines.push(`file ${fr.f}`, `duration ${Math.max(d, 0.001).toFixed(4)}`); });
  if (frames.length) lines.push(`file ${frames.at(-1).f}`);
  fs.writeFileSync(path.join(fdir, 'list.ffconcat'), lines.join('\n'));
  execFileSync('ffmpeg', ['-y', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', 'list.ffconcat', '-vf', 'fps=30,format=yuv420p', '-c:v', 'libx264', '-preset', 'fast', '-crf', '16', path.join(BASE, 'takes', `${take}.mp4`)], { cwd: fdir });
  const t0 = frames.length ? frames[0].t : 0;
  console.log('frames', frames.length, 'marks', marks.map(m => `${m.name}@${(m.t - t0).toFixed(2)}`).join(' '));
}

const DEMO = 'S2026-27-TES-VAN', LIVE = 'S2026-29-BRI-FAL';
const url = (q) => SITE + '?' + new URLSearchParams(q).toString();

const at = async (t0, sec) => { const d = t0 + sec * 1000 - Date.now(); if (d > 0) await sleep(d); };
const TOP = { minY: 0, maxY: 60 };
const takes = {
  // shots 1 + 2: live match, fan then analyst
  async live() {
    await goto(url({ match: LIVE, live: 1, tab: 'replay', mode: 'fan', team: 'none', player: 'none', lang: 'en' }), 9000);
    await waitText('Right now');
    await moveTo(1500, 700, 10);
    await startRec(); const t0 = Date.now();
    await moveTo(780, 640, 1800);
    await at(t0, 9.0); await hover({ text: 'Right now', sel: 'h2' }, 900);
    await at(t0, 11.0); await hover({ text: 'The big moments', exact: false, sel: 'h3' }, 900);
    await at(t0, 13.6); mark('s2'); await click({ text: 'Analyst', ...TOP }, 700);
    await at(t0, 17.5); await hover({ text: 'xG', sel: 'abbr,span,div,dt,p', minY: 300, maxY: 420 }, 700);
    await at(t0, 19.0); await hover({ text: 'PPDA', sel: 'abbr,span,div,dt,p', minY: 300, maxY: 420 }, 900);
    await at(t0, 21.4); await click({ text: 'Pressing zones', sel: 'button' }, 800);
    await at(t0, 24.2); await click({ text: 'Passing lanes', sel: 'button' }, 600);
    await at(t0, 26.6); await stopRec();
  },
  // shot 3: turning point explained and checked
  async explain() {
    await goto(url({ match: DEMO, tab: 'overview', mode: 'analyst', team: 'none', player: 'none', lang: 'en' }), 5000);
    await waitText('Why it turned');
    await startRec(); const t0 = Date.now();
    await scrollToText('Momentum', 110, 1300, { sel: 'h2' });
    await moveTo(980, 330, 900);
    await at(t0, 4.6); await scrollToText('Vantry Town gains control with sharp attack', 150, 1300, { sel: 'h2' });
    await moveTo(700, 140, 700);
    await at(t0, 9.4);
    const p = await evaluate(`(() => {
      const nb = String.fromCharCode(160);
      const tx = e => (e.textContent || '').split(nb).join(' ').trim();
      const els = [...document.querySelectorAll('*')].filter(e => tx(e).startsWith('4 to 14') && e.getBoundingClientRect().width < 200);
      const el = els.sort((a, b) => a.getBoundingClientRect().width - b.getBoundingClientRect().width)[0];
      if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    })()`);
    if (p) await moveTo(p.x, p.y, 900);
    await at(t0, 16.6); await hover({ text: 'Judged, written and checked by the AI', exact: false, sel: 'p,div,span,small' }, 900);
    await at(t0, 20.6); await stopRec();
  },
  // shot 4a: pick a team, then the language
  async personal() {
    await goto(url({ match: DEMO, tab: 'overview', mode: 'fan', team: 'none', player: 'none', lang: 'en' }), 5000);
    await waitText('The story of the match');
    await startRec(); const t0 = Date.now();
    await at(t0, 0.6); await click({ text: '♡', sel: 'button' }, 800);
    await at(t0, 2.4); await moveTo(560, 900, 1200);
    await at(t0, 4.8); await click({ text: '中文', ...TOP }, 800);
    await at(t0, 6.8); await click({ text: 'ES', ...TOP }, 500);
    await at(t0, 8.0); await moveTo(560, 930, 600);
    await at(t0, 8.6); await stopRec();
  },
  // shot 4b: a followed player
  async follow() {
    await goto(url({ match: DEMO, tab: 'stats', mode: 'fan', player: 'h11', lang: 'en' }), 5000);
    await click({ text: '♡', sel: 'button' }, 10);
    await waitText('Player spotlight');
    await scrollToY(0, 10); await sleep(1200);
    await startRec(); const t0 = Date.now();
    await at(t0, 0.8); await scrollToText('In the turning points', 1100, 1400);
    await hover({ text: '★ Following', exact: false, sel: 'button' }, 900);
    await at(t0, 4.6); await stopRec();
  },
  // shot 5: what-if, fan then analyst
  async whatif() {
    await goto(url({ match: DEMO, tab: 'whatif', mode: 'fan', player: 'none', lang: 'en' }), 5000);
    await click({ text: '♡', sel: 'button' }, 10);
    await waitText('The biggest what-ifs'); await sleep(1500);
    await startRec(); const t0 = Date.now();
    await moveTo(620, 610, 1200);
    await at(t0, 3.4); await moveTo(560, 800, 900);
    await at(t0, 5.4); await scrollToY(300, 1300);
    await at(t0, 8.0); await scrollToY(0, 800);
    await at(t0, 9.0); mark('ana'); await click({ text: 'Analyst', ...TOP }, 600);
    await waitText('What if: Disallow', 15000); mark('anaReady'); const t1 = Date.now();
    await moveTo(450, 500, 800);
    await at(t1, 1.6); await scrollToY(330, 1300);
    await moveTo(990, 560, 900);
    await at(t1, 5.6); await moveTo(1530, 545, 900);
    await at(t1, 8.0); await stopRec();
  },
  // shot 6: analyst deep dive on Stats
  async report() {
    await goto(url({ match: DEMO, tab: 'stats', mode: 'analyst', team: 'none', player: 'none', lang: 'en' }), 5000);
    await waitText('Style profile'); await sleep(1500);
    await scrollToText('Match phases', 90, 10, { sel: 'h2' }); await sleep(800);
    await startRec(); const t0 = Date.now();
    await at(t0, 1.6); await scrollToText('Game state', 90, 1100, { sel: 'h2' });
    await at(t0, 3.2); await scrollToText('Shot quality', 90, 1100, { sel: 'h2' });
    await at(t0, 4.8); await scrollToText('Attacking lanes', 90, 1100, { sel: 'h2' });
    await at(t0, 6.6); await scrollToText('Style profile', 90, 1100, { sel: 'h2' });
    await at(t0, 9.4); await stopRec();
  },
  async evalurl() {
    await goto(process.argv[3], 6000);
    console.log(JSON.stringify(await evaluate(process.argv[4])));
  },
  async probe() {
    fs.mkdirSync(path.join(BASE, 'probe'), { recursive: true });
    const u = process.argv[3]; const name = process.argv[4] || 'p';
    await goto(u, 6000);
    await shot(name + '.png');
    const items = await evaluate(`[...document.querySelectorAll('button,a,[role=tab],[role=button],summary,select,input,h1,h2,h3,h4')].map(e => { const r = e.getBoundingClientRect(); return [e.tagName, (e.innerText||e.getAttribute('aria-label')||e.getAttribute('title')||'').replace(/\\s+/g,' ').trim().slice(0,70), Math.round(r.left), Math.round(r.top + scrollY)]; }).filter(x => x[1])`);
    fs.writeFileSync(path.join(BASE, 'probe', name + '.txt'), items.map(i => i.join(' | ')).join('\n') + '\n\n' + (await evaluate('document.body.innerText')).slice(0, 6000));
    console.log('probe saved', name, items.length);
  },
};

try {
  if (!takes[take]) throw new Error('unknown take ' + take);
  await takes[take]();
} catch (e) { console.error('ERROR', e.message); if (recording) await stopRec().catch(() => {}); process.exitCode = 1; }
finally { try { await send('Browser.close'); } catch {} chrome.kill(); }
