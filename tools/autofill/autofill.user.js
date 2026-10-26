// ==UserScript==
// @name         Autofill From TXT
// @namespace    local.autofill
// @version      1.0
// @description  Pick a .txt file and a text box on any page; types each line into the box.
// @match        *://*/*
// @grant        none
// ==/UserScript==

(function () {
  if (window.__autofillTxt) return;
  window.__autofillTxt = true;

  const host = document.createElement('div');
  host.style.cssText = 'position:fixed;top:10px;right:10px;z-index:2147483647';
  const root = host.attachShadow({ mode: 'open' });
  root.innerHTML = `
<style>
  .p{font:13px system-ui,sans-serif;background:#1e1e24;color:#eee;border-radius:8px;padding:8px;width:210px;box-shadow:0 2px 12px #0008}
  .h{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;font-weight:600}
  button{background:#3a3a46;color:#eee;border:0;border-radius:5px;padding:5px 8px;margin:2px 0;width:100%;cursor:pointer}
  button:hover{background:#4c4c5c}
  .row{display:flex;gap:6px;align-items:center;margin:4px 0}
  input[type=number]{width:70px;background:#2c2c36;color:#eee;border:1px solid #555;border-radius:4px;padding:2px}
  .s{margin-top:6px;color:#9ad;min-height:16px}
  .min .b{display:none}
</style>
<div class="p" id="p">
  <div class="h"><span>Autofill</span><span id="min" style="cursor:pointer">_</span></div>
  <div class="b">
    <button id="load">1. Load .txt</button>
    <button id="pick">2. Pick text box</button>
    <div class="row"><label>Delay ms</label><input id="delay" type="number" value="500" min="0"></div>
    <div class="row"><input id="enter" type="checkbox" checked><label for="enter">Press Enter after each</label></div>
    <button id="start">Start</button>
    <button id="stop">Stop</button>
    <div class="s" id="s">Load a file.</div>
  </div>
  <input id="file" type="file" accept=".txt,text/plain" hidden>
</div>`;
  document.documentElement.appendChild(host);

  const $ = (id) => root.getElementById(id);
  let lines = [], target = null, running = false, idx = 0, picking = false;
  const say = (t) => ($('s').textContent = t);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  $('min').onclick = () => $('p').classList.toggle('min');
  $('load').onclick = () => $('file').click();
  $('file').onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    lines = (await f.text()).split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    idx = 0;
    say(`${lines.length} lines loaded.`);
  };

  $('pick').onclick = () => {
    picking = true;
    document.body.style.cursor = 'crosshair';
    say('Click the text box...');
  };
  document.addEventListener('click', (e) => {
    if (!picking || e.composedPath().includes(host)) return;
    e.preventDefault();
    e.stopPropagation();
    const el = e.target.closest('input:not([type=checkbox]):not([type=radio]):not([type=file]),textarea,[contenteditable=""],[contenteditable="true"]');
    if (!el) return say('Not a text box. Try again.');
    target = el;
    picking = false;
    document.body.style.cursor = '';
    say('Box picked.');
  }, true);

  function setText(el, text) {
    el.focus();
    if (el.isContentEditable) {
      document.execCommand('selectAll');
      document.execCommand('insertText', false, text);
      return;
    }
    const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, text);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  function pressEnter(el) {
    for (const type of ['keydown', 'keypress', 'keyup']) {
      el.dispatchEvent(new KeyboardEvent(type, { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true }));
    }
  }

  $('start').onclick = async () => {
    if (running) return;
    if (!lines.length) return say('Load a file first.');
    if (!target || !target.isConnected) return say('Pick a text box first.');
    if (idx >= lines.length) idx = 0;
    running = true;
    while (running && idx < lines.length) {
      setText(target, lines[idx]);
      if ($('enter').checked) pressEnter(target);
      idx++;
      say(`${idx}/${lines.length}`);
      await sleep(Math.max(0, +$('delay').value || 0));
    }
    if (idx >= lines.length) say(`Done, ${lines.length} lines.`);
    running = false;
  };
  $('stop').onclick = () => {
    running = false;
    say(`Stopped at ${idx}/${lines.length}. Start resumes.`);
  };
})();
