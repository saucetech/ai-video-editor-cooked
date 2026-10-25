/* The board makes source-cut revisions. Planning annotations never pretend to be rendered graphics. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  let state = null, dirty = false, busy = false, selected = '', watchEnd = null, polling = false, activeRow = -1, assets = [], styles = [], defaultStyle = {}, proofData = null, proofKey = '';
  const notice = (text, error = false) => { $('notice').textContent = text; $('notice').classList.toggle('error', error); };
  const time = seconds => `${Math.floor(seconds / 60)}:${(seconds % 60).toFixed(3).padStart(6, '0')}`;
  async function api(path, body) {
    const response = await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const result = await response.json();
    if (!response.ok || result.ok === false) throw new Error(result.error || result.message || 'This action did not finish.');
    return result;
  }
  function payload() { return {edit:state.edit,version:state.version,revision:selected}; }
  async function action(message, run) {
    if (busy) return;
    busy = true; controls(); notice(message);
    try { await run(); } catch (error) { notice(error.message, true); }
    finally { busy = false; controls(); }
  }
  const currentRevision = () => state?.revisions.find(r => r.id === selected);
  function controls() {
    const rev = currentRevision(), current = rev && state && rev.board_version === state.version;
    $('save').disabled = busy || !dirty;
    $('preview').disabled = busy || !state || dirty || state.revisions.some(r => r.board_version === state.version && r.state === 'rendering');
    $('watch').disabled = busy || !rev || rev.state !== 'ready';
    $('captions-download').hidden=!(rev?.state==='ready'&&rev.visual_digest);
    if(state&&rev)$('captions-download').href='/board/captions?'+new URLSearchParams({edit:state.edit,revision:rev.id});
    $('approve').disabled = busy || dirty || !current || rev.state !== 'ready' || state.approved_revision === selected;
    $('send-resolve').disabled = busy || dirty || !current || state.approved_revision !== selected || rev.native_state === 'sending' || rev.native_state === 'blocked';
    $('compare-resolve').disabled=busy||dirty||!current||state?.approved_revision!==selected||rev?.native_state!=='ready'||!rev?.visual_digest;
    $('apply-style').disabled=busy||!state||!$('style-reference').value;
    $('send-resolve').textContent = rev?.native_state === 'ready' ? 'View timeline details' : 'Create Resolve timeline';
    $('resolve-status').textContent = rev?.native_state === 'blocked' ? 'Inspect the incomplete Resolve timeline before continuing. This revision will not be retried.' : rev?.native_state === 'sending' ? 'Creating the timeline. Leave the Resolve connection running.' : rev?.native_state === 'ready' ? 'Timeline created. Open Resolve to continue finishing.' : state?.approved_revision === selected && selected ? 'Preview approved. Ready to create a separate timeline.' : 'Approve a preview to create its timeline.';
    for (const id of ['project','reload','sample','revision','setup-resolve','check-resolve','upload-broll','style-reference','proof-frame']) $(id).disabled = busy;
    $('rows').querySelectorAll('input,textarea,select,button').forEach(el => { el.disabled = busy || (el.dataset.keep === 'true' && state.rows[Number(el.dataset.index)].protected); });
    $('sequence').querySelectorAll('button').forEach(el => { el.disabled = busy; });
    $('save-state').textContent = dirty ? 'Unsaved changes · approval required again' : state ? `Board version ${state.version} · saved` : 'Choose a project';
    if (!state) return;
    drawCompiledSummary();
    const frames = state.rows.filter(r => r.keep).reduce((n,r) => n + r.end_frame - r.start_frame, 0);
    $('duration').textContent = `${time(frames / state.fps)} selected`;
    $('step-draft').className = 'done';
    $('step-preview').className = rev?.state === 'ready' && current && !dirty ? 'done' : 'active';
    $('step-approve').className = state.approved_revision === selected && !dirty ? 'done' : '';
    $('step-resolve').className = rev?.native_state === 'ready' ? 'done' : '';
  }
  function changed(sequence = false) { dirty = true; if(sequence)drawSequence(); controls(); }
  function media(revision = '') {
    const q = new URLSearchParams({edit:state.edit}); if (revision) q.set('revision',revision);
    return '/board/media?' + q;
  }
  function node(tag, text, className) {const el = document.createElement(tag); if (text) el.textContent = text; if(className)el.className=className; return el;}
  function watchSource(row, index) {
    activeRow = index;
    const player = $('player'); watchEnd = row.end_frame/state.fps; player.src=media();
    player.onloadedmetadata = () => {player.currentTime=row.start_frame/state.fps;player.play().catch(()=>{});};
    $('player-mode').textContent=`Source passage ${index+1}`;
    $('rows').querySelectorAll('article').forEach((card,i)=>card.classList.toggle('current',i===index));
    drawSequence(); controls();
  }
  function drawSequence() {
    $('sequence').replaceChildren();
    state.rows.forEach((row,index)=>{
      const button=node('button',String(index+1).padStart(2,'0'));
      button.type='button'; button.style.flexGrow=String(row.end_frame-row.start_frame);
      button.setAttribute('aria-label',`Watch source passage ${index+1}: ${row.keep?'kept':'removed'}, ${time(row.start_frame/state.fps)} to ${time(row.end_frame/state.fps)}`);
      button.setAttribute('aria-pressed',String(index===activeRow));
      button.classList.toggle('omitted',!row.keep);button.classList.toggle('current',index===activeRow);
      button.onclick=()=>watchSource(row,index);$('sequence').append(button);
    });
  }
  function drawRows() {
    $('rows').replaceChildren();
    state.rows.forEach((row, index) => {
      const card = node('article',null,'passage'), top = node('div',null,'passage-top');
      const restyle = () => {card.classList.toggle('dropped',!row.keep);card.classList.toggle('protected',row.protected);card.classList.toggle('current',index===activeRow);}; restyle();
      top.append(node('span',`${String(index+1).padStart(2,'0')}  ${time(row.start_frame/state.fps)} → ${time(row.end_frame/state.fps)}`,'timecode'));
      const play = node('button','Watch source','subtle'); play.type='button'; play.setAttribute('aria-label',`Watch source passage ${index+1}`);
      play.onclick = () => watchSource(row,index); top.append(play); card.append(top,node('p',row.text || 'No transcript text for this source interval.','passage-text'));
      const toggles=node('div',null,'passage-controls');
      for(const [key,label] of [['keep','Keep passage'],['protected','Protect hold']]) {
        const wrap=node('label'), input=node('input'); input.type='checkbox';input.checked=row[key]; input.id=`${key}-${index}`;
        input.setAttribute('aria-label',`${label} ${index+1}`); input.dataset.index=String(index); if(key==='keep')input.dataset.keep='true';
        input.onchange=()=>{row[key]=input.checked;if(key==='protected'&&input.checked){row.keep=true;card.querySelector('[data-keep]').checked=true;}restyle();changed(true);};
        wrap.append(input,document.createTextNode(label));toggles.append(wrap);
      }
      card.append(toggles);
      const visual=node('details',null,'visual-details'), visualSummary=node('summary');
      const updateVisual=()=>{visualSummary.textContent='Captions & visuals'+(row.caption_enabled?' · caption':'')+(row.motion&&row.motion!=='none'?' · '+row.motion.replace('_',' '):'')+(row.broll?' · B-roll':'');};updateVisual();visual.append(visualSummary);
      const visualFields=node('div',null,'visual-fields');
      const captionLabel=node('label',null,'caption-toggle'), captionToggle=node('input');captionToggle.type='checkbox';captionToggle.checked=!!row.caption_enabled;
      captionToggle.setAttribute('aria-label',`Show caption passage ${index+1}`);captionToggle.onchange=()=>{row.caption_enabled=captionToggle.checked;updateVisual();changed();};captionLabel.append(captionToggle,document.createTextNode('Show caption'));visualFields.append(captionLabel);
      const captionLabelText=node('label','Caption text'),caption=node('textarea');caption.value=row.caption??row.text.slice(0,500);caption.maxLength=500;caption.rows=2;
      caption.setAttribute('aria-label',`Caption text passage ${index+1}`);caption.oninput=()=>{row.caption=caption.value;changed();};captionLabelText.append(caption);visualFields.append(captionLabelText);
      const treatmentLabel=node('label','Caption treatment'),treatment=node('select');treatment.setAttribute('aria-label',`Caption treatment passage ${index+1}`);
      [['panel','Original panel'],['clean','Clean'],['editorial','Editorial serif'],['spotlight','Word spotlight']].forEach(([v,t])=>treatment.append(new Option(t,v)));treatment.value=row.caption_treatment||'panel';treatment.onchange=()=>{row.caption_treatment=treatment.value;changed();};treatmentLabel.append(treatment);visualFields.append(treatmentLabel);
      const ensureStyle=()=>{if(!row.caption_style)row.caption_style=JSON.parse(JSON.stringify(defaultStyle));return row.caption_style;};
      for(const [key,text,type,min,max,step] of [['words_per_phrase','Words per phrase','number',1,8,1],['size_pct','Text size · % of long side','number',2,8,.1],['y_pct','Caption position · % from top','number',60,90,1],['accent','Spotlight / hook accent','color'],['color','Text color','color']]){
        const wrap=node('label',text),input=node('input');input.type=type;input.value=String((row.caption_style||defaultStyle)[key]??'');input.setAttribute('aria-label',`${text} passage ${index+1}`);
        if(type==='number'){input.min=min;input.max=max;input.step=step;}
        input.oninput=()=>{const style=ensureStyle();style[key]=type==='number'?Number(input.value):input.value;changed();};wrap.append(input);visualFields.append(wrap);
      }
      const contrastLabel=node('label',null,'caption-toggle'),contrast=node('input');contrast.type='checkbox';contrast.checked=!!(row.caption_style?.box||row.caption_style?.shadow||row.caption_style?.stroke);contrast.setAttribute('aria-label',`Contrast panel passage ${index+1}`);contrast.onchange=()=>{const style=ensureStyle();style.box=contrast.checked;style.shadow=false;style.stroke=false;changed();};contrastLabel.append(contrast,document.createTextNode('Contrast panel'));visualFields.append(contrastLabel);
      const captionHint=node('p',row.caption_style?.source?`Reference: ${row.caption_style.source.name}. Editable native text; approximations listed below.`:'Word spotlight needs matching source word timestamps. Corrected or untimed text uses a static passage.','field-hint');visualFields.append(captionHint);
      if(row.caption_style?.transfer?.notes?.length){const info=node('details'),summary=node('summary','Style transfer details'),list=node('ul');row.caption_style.transfer.notes.forEach(text=>list.append(node('li',text)));info.append(summary,list,node('p','Board settings above are the current values. Reflow after native text edits requires a board rebuild.','field-hint'));visualFields.append(info);}
      const motionLabel=node('label','Motion graphic'),motion=node('select');motion.setAttribute('aria-label',`Motion graphic passage ${index+1}`);
      [['none','None'],['title','Fade title'],['lower_third','Fade lower third'],['hero','Hero reveal'],['outline','Outline draw'],['prompt_result','Prompt → result']].forEach(([v,t])=>motion.append(new Option(t,v)));motion.value=row.motion||'none';motion.onchange=()=>{row.motion=motion.value;updateVisual();changed();};motionLabel.append(motion);visualFields.append(motionLabel);
      const titleLabel=node('label','Motion text'),title=node('input');title.type='text';title.maxLength=180;title.value=row.motion_text||'';title.setAttribute('aria-label',`Motion text passage ${index+1}`);title.oninput=()=>{row.motion_text=title.value;changed();};titleLabel.append(title);visualFields.append(titleLabel);
      const resultLabel=node('label','Hook result'),resultText=node('input');resultText.type='text';resultText.maxLength=180;resultText.value=row.motion_result||'';resultText.setAttribute('aria-label',`Hook result passage ${index+1}`);resultText.oninput=()=>{row.motion_result=resultText.value;changed();};resultLabel.append(resultText);visualFields.append(resultLabel);
      const brollLabel=node('label','B-roll · covers this passage'),broll=node('select');broll.setAttribute('aria-label',`B-roll passage ${index+1}`);broll.append(new Option('Original source',''));
      const choices=[...assets];if(row.broll&&!choices.some(a=>a.path===row.broll))choices.push({path:row.broll,name:row.broll.split('/').pop()});choices.forEach(a=>broll.append(new Option(a.name,a.path)));broll.value=row.broll||'';broll.onchange=()=>{row.broll=broll.value;updateVisual();changed();};brollLabel.append(broll);visualFields.append(brollLabel);
      const pointLabel=node('label','B-roll in-point · seconds'),point=node('input');point.type='number';point.min=0;point.step=.01;point.value=String(row.broll_start||0);point.setAttribute('aria-label',`B-roll in-point passage ${index+1}`);point.oninput=()=>{row.broll_start=Number(point.value);changed();};pointLabel.append(point);visualFields.append(pointLabel);
      visual.append(visualFields);card.append(visual);const compiled=node('div',null,'field-hint compiled-summary');compiled.id=`compiled-${index}`;card.append(compiled);

      const details=node('details',null,'direction-details'), summary=node('summary');
      const directionSummary=()=>{summary.textContent='Visual direction'+(row.zoom!==1?` · ${row.zoom.toFixed(2)}× zoom`:'')+([row.note,row.emphasis].some(Boolean)?' · notes':'');};
      directionSummary();
      details.append(summary);
      const fields=node('div',null,'row-fields');
      for(const [key,label,type] of [['note','Visual direction · planning note','textarea'],['emphasis','Emphasis text · planning note','input']]) {
        const wrap=node('label',label), input=node(type); if(type==='input')input.type='text';input.value=row[key];input.maxLength=key==='note'?4000:200;
        input.setAttribute('aria-label',`${label} ${index+1}`);input.oninput=()=>{row[key]=input.value;directionSummary();changed();};wrap.append(input);fields.append(wrap);
      }
      const zoomLabel=node('label','Static zoom · in Resolve'), zoom=node('select'); zoom.setAttribute('aria-label',`Static zoom passage ${index+1}`);
      const scales=[1,1.1,1.2,1.35,1.5,2];if(!scales.includes(row.zoom))scales.push(row.zoom);
      scales.sort((a,b)=>a-b).forEach(n=>zoom.append(new Option(`${n.toFixed(2)}×`,String(n))));zoom.value=String(row.zoom);
      zoom.onchange=()=>{row.zoom=Number(zoom.value);directionSummary();changed();};zoomLabel.append(zoom);fields.append(zoomLabel);details.append(fields);card.append(details);$('rows').append(card);
    });
    drawSequence();
  }
  function drawRevisions() {
    const options=$('revision');options.replaceChildren(new Option('Choose a preview',''));
    for(const r of state.revisions) options.append(new Option(`v${r.board_version} · ${r.id.slice(0,6)} · ${r.state}${r.approved?' · approved':''}${r.native_state==='ready'?' · Resolve':''}`,r.id));
    if(!state.revisions.some(r=>r.id===selected)) selected=state.revisions.find(r=>r.board_version===state.version)?.id||'';
    options.value=selected;
    const rev=currentRevision();
    loadProof();drawCompiledSummary();
    $('revision-info').textContent = rev ? rev.error || (rev.native_state==='blocked'?'Resolve outcome needs inspection. No automatic retry.':rev.native_result?.timeline_name || (rev.state==='rendering'?'Rendering captions and visual layers…':`${rev.selected_frames} frames · ${rev.approved?'approved':'awaiting approval'}`)) : 'Build a preview after saving your choices.';
  }
  function drawCompiledSummary(){
    if(!state)return;const rev=currentRevision();
    state.rows.forEach((row,index)=>{const target=$(`compiled-${index}`);target.replaceChildren();target.textContent='';if(!rev||rev.state!=='ready')return;
      if(dirty||rev.board_version!==state.version){target.textContent='Current changes need a new saved preview.';return;}
      const entries=(rev.visual_summary||[]).filter(v=>v.passage_id===row.id);if(!entries.length)return;
      target.textContent=entries.map(v=>`${v.kind} · ${v.timing}`).join(' / ');
      const notes=[...new Set(entries.flatMap(v=>v.notes||[]))];if(notes.length){const details=node('details'),summary=node('summary','Compiled preview adjustments & limits'),list=node('ul');notes.forEach(t=>list.append(node('li',t)));details.append(summary,list);target.append(details);}
    });
  }
  function display(next) {
    state=next;dirty=false;selected='';activeRow=-1;$('workspace').hidden=false;$('empty').hidden=true;
    if (window.history) { const url=new URL(location.href);url.searchParams.set('edit',state.edit);url.searchParams.delete('t');window.history.replaceState({},'',url); }
    $('project-name').textContent=state.name;$('sample-note').hidden=!state.sample;
    $('player').onloadedmetadata=null;$('player').src=media();watchEnd=null;$('player-mode').textContent='Original source';
    drawRows();drawRevisions();controls();
  }
  async function loadAssets() {assets=(await api('/board/assets')).assets;}
  async function loadStyles(){const data=await api('/board/styles');styles=data.styles;defaultStyle=data.default_style;const select=$('style-reference');select.replaceChildren(new Option('Choose an analyzed style',''));styles.forEach(s=>select.append(new Option(s.name,s.id)));}
  $('style-reference').onchange=()=>{const chosen=styles.find(s=>s.id===$('style-reference').value);$('style-summary').textContent=chosen?`${chosen.style.font} · ${chosen.style.treatment}. ${chosen.style.transfer.notes[0]}`:'';controls();};
  $('apply-style').onclick=()=>{if(busy||!state)return;const chosen=styles.find(s=>s.id===$('style-reference').value);if(!chosen)return;state.rows.filter(r=>r.keep).forEach(r=>{r.caption_style=JSON.parse(JSON.stringify(chosen.style));r.caption_treatment=chosen.style.treatment;});drawRows();changed();notice('Supported style choices applied. Review transfer details, save and build a new preview.');};
  function drawProof(){
    const panel=$('proof-panel');panel.hidden=!proofData;if(!proofData)return;
    if(!proofData.frames?.length){$('proof-status').textContent='No frames were captured. Run Compare Resolve again.';$('proof-frame').replaceChildren();$('proof-images').replaceChildren();return;}
    $('proof-status').textContent=`${proofData.control_status==='matches'?'Declared native controls matched':'Native changes detected · review differences'} · captured ${new Date(proofData.created*1000).toLocaleString()}`;
    const select=$('proof-frame');select.replaceChildren();proofData.frames.forEach((f,i)=>select.append(new Option(`${time(f.seconds)} · frame ${f.frame}`,String(i))));select.value='0';
    const notes=$('proof-notes');notes.replaceChildren();proofData.notes.forEach(t=>notes.append(node('li',t)));proofData.differences.forEach(d=>notes.append(node('li',`${d.node||'Timeline'} · ${d.input}: ${JSON.stringify(d.actual)}`)));showProofFrame();
  }
  function showProofFrame(){if(!proofData?.frames?.length)return;const pair=proofData.frames[Number($('proof-frame').value)||0],images=$('proof-images');images.replaceChildren();for(const [key,label] of [['preview','Board preview'],['native','DaVinci Resolve']]){const figure=node('figure'),image=node('img');image.alt=`${label} at frame ${pair.frame}`;image.src='/board/proof?'+new URLSearchParams({edit:state.edit,revision:selected,proof:proofData.id,file:pair[key]});figure.append(image,node('figcaption',label));images.append(figure);}}
  $('proof-frame').onchange=showProofFrame;
  async function loadProof(){const rev=currentRevision(),key=rev?.resolve_proof?`${rev.id}:${rev.resolve_proof.id}`:'';if(key===proofKey)return;proofKey=key;proofData=null;drawProof();if(!key)return;try{const result=await api('/board/proof?'+new URLSearchParams({edit:state.edit,revision:rev.id,proof:rev.resolve_proof.id}));if(proofKey===key){proofData=result.proof;drawProof();}}catch(error){notice(error.message,true);}}
  $('compare-resolve').onclick=()=>action('Capturing actual Resolve frames and checking editable controls…',async()=>{const result=await api('/board/compare',payload());state=await api('/board/load',{edit:state.edit});proofKey='';drawRevisions();notice(result.proof.control_status==='matches'?'Comparison captured. Inspect the paired frames and transfer limits.':'Native changes were found. Review the comparison; your native edits were preserved.');});

  $('upload-broll').onclick=()=>{if(!busy)$('broll-file').click();};
  $('broll-file').onchange=()=>action('Copying B-roll into your local library…',async()=>{const file=$('broll-file').files?.[0];if(!file)return;const response=await fetch('/upload?stage=1&name='+encodeURIComponent(file.name),{method:'POST',body:file});const result=await response.json();if(!response.ok||result.error)throw new Error(result.error||'The local copy failed.');await api('/board/import-asset',{path:result.path});await loadAssets();if(state)drawRows();$('broll-file').value='';notice('B-roll added. Choose it in a passage’s Captions & visuals.');});
  async function projects(chosen='') {
    const data=await api('/board/projects'), select=$('project');select.replaceChildren(new Option('Choose a project',''));
    data.edits.forEach(edit=>select.append(new Option(edit.name,edit.path)));if(chosen)select.value=chosen;
  }
  async function loadProject(path) {
    if(!path)return;
    if(dirty){$('project').value=state.edit;throw new Error('Save your current board before changing projects. Reload discards unsaved changes.');}
    display(await api('/board/load',{edit:path}));notice('Board loaded. Keep or restore passages, then save and preview.');
  }
  $('project').onchange=()=>action('Loading source decisions…',()=>loadProject($('project').value));
  $('reload').onclick=()=>action('Reloading saved decisions…',async()=>{const p=state?.edit||$('project').value;dirty=false;await projects(p);if(p)await loadProject(p);});
  $('sample').onclick=()=>action('Preparing the original synthetic sample…',async()=>{if(dirty)throw new Error('Save your board before opening the sample.');const result=await api('/board/sample',{});await projects(result.edit);display(result);notice('Synthetic sample ready. Restore passage 2 and protect its demonstration hold to try a revision.');});
  $('save').onclick=()=>action('Saving your board…',async()=>{state=await api('/board/save',{...payload(),rows:state.rows});dirty=false;selected='';drawRows();drawRevisions();notice('Board saved. Build a preview of these choices.');});
  $('preview').onclick=()=>action('Starting the visual preview…',async()=>{const result=await api('/board/preview',payload());selected=result.revision.id;state.revisions=[result.revision,...state.revisions.filter(r=>r.id!==selected)];drawRevisions();notice('Preview started. You can keep reviewing while it renders.');});
  $('revision').onchange=()=>{selected=$('revision').value;drawRevisions();controls();};
  $('watch').onclick=()=>{watchEnd=null;$('player').onloadedmetadata=null;$('player').src=media(selected);$('player-mode').textContent='Saved cut preview';$('player').play().catch(()=>{});};
  $('player').ontimeupdate=()=>{if(watchEnd!==null&&$('player').currentTime>=watchEnd){$('player').pause();watchEnd=null;}};
  $('approve').onclick=()=>action('Approving this saved preview…',async()=>{state=await api('/board/approve',payload());drawRows();drawRevisions();notice('Preview approved. It is ready for a separate Resolve timeline.');});
  $('send-resolve').onclick=()=>action('Creating a native timeline in Resolve. Leave the connection running…',async()=>{const result=await api('/board/resolve',payload());state=await api('/board/load',{edit:state.edit});drawRows();drawRevisions();notice(`${result.message} ${result.timeline_name}`);$('resolve-status').textContent='Timeline: '+result.timeline_name;});
  $('check-resolve').onclick=()=>action('Checking Resolve…',async()=>{const result=await api('/integrations/status');$('resolve-status').textContent=result.resolve.connected?'Resolve connected.':result.resolve.message;notice(result.resolve.connected?'Resolve is connected.':result.resolve.message);});
  $('setup-resolve').onclick=()=>action('Preparing the local connection command…',async()=>{const result=await api('/integrations/resolve/setup',{});$('connection-command').textContent=result.console_command;notice(result.message);});
  async function poll() {
    if(polling||busy||!state||!state.revisions.some(r=>r.state==='rendering'||r.native_state==='sending'))return;
    polling=true;
    try {const next=await api('/board/load',{edit:state.edit});state.revisions=next.revisions;drawRevisions();controls();}
    catch(error){notice(error.message,true);}finally{polling=false;}
  }
  setInterval(poll,1800);
  window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
  action('Loading source-cut projects…',async()=>{await Promise.all([projects(),loadAssets(),loadStyles()]);const path=new URLSearchParams(location.search).get('edit');if(path){$('project').value=path;await loadProject(path);}else notice('Choose a source-cut project, or try the synthetic sample.');});
})();
