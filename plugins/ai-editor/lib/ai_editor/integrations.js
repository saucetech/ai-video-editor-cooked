/* Explicit actions only: opening this panel never uploads media or generates an asset. */
(() => {
  'use strict';
  const panel = document.getElementById('codex-panel'); if (!panel) return;
  const details = document.createElement('details'); details.id = 'editor-integrations';
  details.innerHTML = `<summary style="cursor:pointer;padding:12px 0;border-top:1px solid #8884">Resolve &amp; Higgsfield</summary>
    <button id="int-check" type="button">Check connections</button><p id="int-status" role="status"></p>
    <h3 style="font-size:15px">DaVinci Resolve</h3><p class="cx-muted">Creates a separate native timeline from an approved source cut. Checks for manual changes before updating managed zooms.</p>
    <button id="int-resolve-setup" type="button">Set up local Resolve connection</button>
    <button id="int-resolve-stop" type="button">Stop Resolve connection</button>
    <div class="cx-row"><label for="int-edit">Source-cut edit</label><button id="int-refresh-edits" type="button">Refresh</button></div>
    <select id="int-edit" aria-label="Source-cut edit" style="width:100%;padding:8px"><option value="">Choose an edit</option></select>
    <button id="int-board" type="button">Open edit board</button>
    <div class="cx-row"><button id="int-resolve-create" type="button">Create timeline</button><button id="int-resolve-update" type="button">Update managed zooms</button></div>
    <h3 style="font-size:15px">Higgsfield assets</h3><p class="cx-muted">Import an existing result, or request a credit quote before generating.</p>
    <div class="cx-row"><select id="int-kind" aria-label="Higgsfield media type"><option value="video">Video</option><option value="image">Image</option></select><button id="int-results" type="button">Load recent results</button></div>
    <div id="int-result-list"></div>
    <details><summary style="cursor:pointer;padding:10px 0">Generate a new asset</summary>
      <p class="cx-muted">Text-only requests. Quotes do not submit a job; generation uses your Higgsfield credits.</p>
      <button id="int-models" type="button">Load models for selected media type</button>
      <label for="int-model" style="display:block;margin:8px 0">Model</label><select id="int-model" style="width:100%;padding:8px"><option value="">Load models first</option></select>
      <label for="int-prompt" style="display:block;margin:8px 0">Asset description</label><textarea id="int-prompt" placeholder="Describe the image or video you want"></textarea>
      <button id="int-quote" type="button">Get credit quote</button><div id="int-quote-view" style="margin:10px 0"></div>
    </details><p id="int-message" role="status" style="white-space:pre-wrap;overflow-wrap:anywhere"></p>`;
  panel.append(details);
  const el = id => document.getElementById(id);
  let quote = null, balance = null, busy = false;
  async function api(path, body) {
    const response = await fetch('/integrations/' + path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const result = await response.json();
    if (!response.ok || result.ok === false) throw new Error(result.error || result.message || 'The integration could not finish.');
    return result;
  }
  async function action(button, run) {
    if (busy) return;
    busy = true; button.disabled = true; el('int-message').textContent = 'Working…';
    try { await run(); }
    catch(error) { el('int-message').textContent = error.message; }
    finally { busy = false; button.disabled = false; }
  }
  function bind(id, run) { el(id).addEventListener('click', () => action(el(id), run)); }
  async function edits() {
    const result = await api('edits'); const select = el('int-edit'), previous = select.value;
    select.replaceChildren(new Option('Choose an edit', ''));
    for (const edit of result.edits) select.append(new Option(edit.name, edit.path));
    if (result.edits.some(edit => edit.path === previous)) select.value = previous;
    return result.edits.length;
  }
  bind('int-check', async () => {
    const result = await api('status'); balance = result.higgsfield.credits;
    el('int-status').textContent = `Resolve: ${result.resolve.connected ? 'Connected' : result.resolve.message || 'Not connected'}\nHiggsfield: ${result.higgsfield.connected ? 'Connected · ' + balance + ' credits' : result.higgsfield.error || 'Not connected'}`;
    el('int-status').style.whiteSpace = 'pre-wrap'; el('int-message').textContent = 'Connection check complete. No media was uploaded or generated.';
  });
  bind('int-refresh-edits', async () => {
    const count = await edits(); el('int-message').textContent = count ? 'Source-cut edits refreshed.' : 'No source-cut edits yet. Make and approve a cut first.';
  });
  bind('int-board', async () => {
    const target = new URL('/edit-board', location.href);
    if (!document.getElementById('steps')) {
      const response = await fetch('/home', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
      const result = await response.json();
      if (!response.ok || !result.url) throw new Error('Open the editor home page to use the edit board.');
      const home = new URL(result.url); target.host = home.host; target.search = home.search;
    }
    if (el('int-edit').value) target.searchParams.set('edit', el('int-edit').value);
    location.assign(target.href);
  });
  bind('int-resolve-setup', async () => {
    const result = await api('resolve/setup', {}); el('int-message').textContent = result.message + '\n\n' + (result.console_command || result.path);
  });
  bind('int-resolve-stop', async () => {
    const result = await api('resolve/stop', {}); el('int-message').textContent = result.message; el('int-status').textContent = result.stopped ? 'Resolve connection stopped.' : 'Resolve stop requested; waiting for acknowledgement.';
  });
  for (const [id, path] of [['int-resolve-create','create'], ['int-resolve-update','update']]) bind(id, async () => {
    const result = await api('resolve/' + path, {edit:el('int-edit').value}); el('int-message').textContent = result.message || 'Resolve timeline updated.';
  });
  bind('int-results', async () => {
    const result = await api('higgsfield/recent', {kind:el('int-kind').value}), list = el('int-result-list'); list.replaceChildren();
    for (const job of result.results) {
      const row = document.createElement('div'); row.className = 'cx-row';
      const label = document.createElement('span'); label.textContent = `${job.display_name || job.model || job.id} · ${job.status}`;
      const button = document.createElement('button'); button.type = 'button'; button.textContent = 'Import'; button.disabled = !job.importable;
      button.addEventListener('click', () => action(button, async () => {
        const imported = await api('higgsfield/import', {job_id:job.id}); el('int-message').textContent = 'Imported into your library:\n' + imported.path;
        window.dispatchEvent(new Event('integrationsUpdated'));
      })); row.append(label,button); list.append(row);
    }
    el('int-message').textContent = result.results.length ? 'Choose a completed result to import.' : 'No recent results for this media type.';
  });
  bind('int-models', async () => {
    const result = await api('higgsfield/models', {kind:el('int-kind').value}), select = el('int-model'); select.replaceChildren(new Option('Choose a model',''));
    for (const model of result.models) select.append(new Option(model.display_name || model.job_type, model.job_type));
    el('int-message').textContent = 'Current models loaded. Models that require source media cannot use this text-only generation form.';
  });
  const clearQuote = () => {quote = null; el('int-quote-view').replaceChildren();};
  el('int-model').addEventListener('change',clearQuote); el('int-prompt').addEventListener('input',clearQuote); el('int-kind').addEventListener('change',clearQuote);
  bind('int-quote', async () => {
    quote = await api('higgsfield/quote', {model:el('int-model').value, params:{prompt:el('int-prompt').value}});
    const holder = el('int-quote-view'), text = document.createElement('p'), submit = document.createElement('button'); holder.replaceChildren();
    text.textContent = `${quote.credits} Higgsfield credits. Quote expires in 10 minutes. No job has been submitted.`;
    submit.type = 'button'; submit.textContent = `Generate for ${quote.credits} credits`;
    if (balance !== null && quote.credits > balance) {submit.disabled = true; text.textContent += ' Your checked balance is below this quote.';}
    const quotedId = quote.quote_id;
    submit.addEventListener('click', () => action(submit, async () => {
      const result = await api('higgsfield/generate', {quote_id:quotedId, confirmed:true});
      clearQuote(); el('int-message').textContent = `Submitted ${result.job_id} · ${result.status}. Refresh recent results to check completion.`;
    })); holder.append(text,submit); el('int-message').textContent = 'Quote only. Generation requires the separate button above.';
  });
  details.addEventListener('toggle', () => {if(details.open) edits().catch(error => {el('int-message').textContent = error.message;});});
})();
