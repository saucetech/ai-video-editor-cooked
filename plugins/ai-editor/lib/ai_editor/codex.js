/* Shared home/review connection panel. Model output is always rendered as text. */
(() => {
  'use strict';
  const css = document.createElement('style');
  css.textContent = `
  #codex-toggle{position:fixed;right:22px;bottom:20px;z-index:95;padding:11px 17px;border:1px solid #444;border-radius:10px;background:#1e2825;color:#f5f7f5;font:600 14px system-ui;cursor:pointer;box-shadow:0 4px 16px #0002}
  #codex-panel{position:fixed;right:20px;bottom:72px;width:min(430px,calc(100vw - 32px));max-height:76vh;z-index:96;background:var(--panel,#faf9f6);color:var(--ink,#20231f);border:1px solid #7777;border-radius:14px;box-shadow:0 12px 50px #0003;padding:18px;overflow:auto;font:14px/1.5 system-ui}
  #codex-panel[hidden]{display:none}#codex-panel h2{font-size:18px;margin:0}#codex-panel button{font:inherit;cursor:pointer;padding:7px 12px;border:1px solid #8888;border-radius:7px;background:transparent;color:inherit}#codex-panel button:disabled{opacity:.45;cursor:default}
  #codex-panel .cx-row{display:flex;gap:8px;align-items:center;justify-content:space-between;margin:10px 0}#codex-panel .cx-muted{color:var(--t2,var(--body,#57534e));font-size:12px}#codex-error{color:#b14235;white-space:pre-wrap}#codex-messages{max-height:30vh;overflow:auto;margin:14px 0}#codex-messages article{padding:10px 0;border-top:1px solid #8883;white-space:pre-wrap;overflow-wrap:anywhere}#codex-panel textarea,#codex-panel input{box-sizing:border-box;width:100%;border:1px solid #8888;border-radius:7px;padding:9px;background:transparent;color:inherit;font:inherit}#codex-panel textarea{resize:vertical;min-height:76px}#codex-pending{padding:12px;border:1px solid #9c9f82;border-radius:8px;margin:12px 0}#codex-pending:empty{display:none}#codex-pending pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}#codex-pending label{display:block;margin:10px 0}#codex-panel a{color:inherit;text-decoration:underline}
  @media(max-width:500px){#codex-toggle{right:16px;bottom:14px}#codex-panel{right:16px;bottom:66px;padding:14px}}
  `;
  document.head.append(css);
  const toggle = document.createElement('button');
  toggle.id = 'codex-toggle'; toggle.textContent = 'Connect Codex';
  toggle.setAttribute('aria-controls', 'codex-panel'); toggle.setAttribute('aria-expanded', 'false');
  const panel = document.createElement('section');
  panel.id = 'codex-panel'; panel.setAttribute('aria-label', 'Codex connection'); panel.hidden = true;
  panel.innerHTML = `<div class="cx-row"><h2>Codex</h2><button type="button" id="codex-close" aria-label="Close Codex panel">Close</button></div>
  <div class="cx-muted">Use your ChatGPT account to work on this edit.</div>
  <div class="cx-row"><span id="codex-status" role="status">Disconnected</span><button id="codex-connect" type="button">Connect Codex</button></div>
  <a id="codex-login" target="_blank" rel="noopener" hidden>Sign in with ChatGPT</a><p id="codex-error" role="alert"></p>
  <div id="codex-messages" aria-label="Codex messages"></div><div id="codex-pending"></div>
  <form id="codex-form"><label for="codex-input">Ask Codex about this edit</label><textarea id="codex-input" placeholder="Describe the edit or change you want…"></textarea>
  <div class="cx-row"><button id="codex-send" type="submit">Send</button><button id="codex-stop" type="button">Stop</button><button id="codex-disconnect" type="button">Disconnect</button></div></form>`;
  document.body.append(toggle, panel);
  let state = null, polling = false, pendingId = '', sending = false;
  const el = id => document.getElementById(id);
  const show = open => { panel.hidden = !open; if(open)panel.scrollTop=0; toggle.setAttribute('aria-expanded', String(open)); };
  toggle.addEventListener('click', () => show(panel.hidden));
  el('codex-close').addEventListener('click', () => show(false));
  window.openCodex = () => show(true);
  async function api(path, body) {
    const response = await fetch('/codex/' + path, body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Codex could not complete that action.');
    return data;
  }
  async function act(path, body) {
    el('codex-error').textContent = '';
    try { await api(path, body); await poll(); }
    catch (error) { el('codex-error').textContent = error.message; }
  }
  el('codex-connect').addEventListener('click', async () => {
    el('codex-connect').disabled = true; el('codex-status').textContent = 'Connecting…';
    await act('connect', {}); el('codex-connect').disabled = false;
  });
  el('codex-disconnect').addEventListener('click', () => act('disconnect', {}));
  el('codex-stop').addEventListener('click', () => act('cancel', {}));
  el('codex-form').addEventListener('submit', async event => {
    event.preventDefault(); if (sending) return;
    const input = el('codex-input'), text = input.value.trim(); if (!text) return;
    sending = true; el('codex-send').disabled = true; el('codex-error').textContent = '';
    try { await api('message', {text}); input.value = ''; }
    catch (error) { el('codex-error').textContent = error.message; }
    finally { sending = false; await poll(); }
  });
  function renderPending(pending) {
    const card = el('codex-pending'); if ((pending?.id || '') === pendingId) return;
    pendingId = pending?.id || ''; card.replaceChildren(); if (!pending) return;
    const title = document.createElement('strong'); title.textContent = pending.question || 'Codex needs your answer'; card.append(title);
    if (pending.kind === 'approval') {
      const command = document.createElement('pre'); command.textContent = pending.command; card.append(command);
      for (const [label, approved] of [['Allow once', true], ['Deny', false]]) {
        const button = document.createElement('button'); button.textContent = label;
        button.addEventListener('click', () => act('respond', {id: pending.id, approved})); card.append(button, ' ');
      }
      return;
    }
    const questions = pending.kind === 'questions' ? pending.questions : [{id: 'answer', question: pending.question, options: pending.options}];
    const inputs = {};
    for (const question of questions) {
      const label = document.createElement('label'); label.textContent = question.question;
      const input = document.createElement('input'); input.type = 'text'; input.setAttribute('aria-label', question.question);
      if (question.options?.length) input.placeholder = question.options.map(option => typeof option === 'string' ? option : option.label).join(' / ');
      label.append(input); card.append(label); inputs[question.id] = input;
    }
    const answer = document.createElement('button'); answer.textContent = 'Send answer';
    answer.addEventListener('click', () => {
      const answers = Object.fromEntries(Object.entries(inputs).map(([id, input]) => [id, input.value]));
      act('respond', {id: pending.id, ...(pending.kind === 'questions' ? {answers} : {answer: answers.answer})});
    }); card.append(answer);
  }
  function render() {
    const labels = {disconnected: 'Disconnected', connecting: 'Connecting…', signing_in: 'Finish ChatGPT sign-in', connected: 'Connected with ChatGPT', working: 'Codex is working', waiting: 'Your answer is needed', failed: 'Connection needs attention'};
    el('codex-status').textContent = labels[state.status] || state.status;
    toggle.textContent = ['connected', 'working', 'waiting'].includes(state.status) ? (state.pending ? 'Codex needs you' : 'Codex · Connected') : 'Connect Codex';
    el('codex-connect').hidden = ['connected', 'working', 'waiting'].includes(state.status);
    el('codex-send').disabled = sending || state.status !== 'connected'; el('codex-stop').disabled = !state.active;
    el('codex-disconnect').disabled = state.status === 'disconnected';
    const login = el('codex-login'); login.hidden = !state.loginUrl;
    if (state.loginUrl && /^https:\/\//.test(state.loginUrl)) login.href = state.loginUrl;
    if (state.error) el('codex-error').textContent = state.error;
    const messages = el('codex-messages'), nearBottom = messages.scrollHeight - messages.scrollTop - messages.clientHeight < 50;
    const signature = JSON.stringify(state.messages);
    if (signature !== messages.dataset.signature) {
      messages.dataset.signature = signature; messages.replaceChildren();
      for (const message of state.messages) {
        const article = document.createElement('article'), name = document.createElement('strong'), text = document.createElement('div');
        name.textContent = message.role === 'user' ? 'You' : 'Codex'; text.textContent = message.text;
        article.append(name, text); messages.append(article);
      } if (nearBottom) messages.scrollTop = messages.scrollHeight;
    }
    renderPending(state.pending); if (state.pending) show(true);
  }
  async function poll() {
    if (polling) return; polling = true;
    try { state = await api('state'); render(); }
    catch (error) { if (!panel.hidden) el('codex-error').textContent = error.message; }
    finally { polling = false; }
  }
  poll(); setInterval(poll, 1500);
})();
