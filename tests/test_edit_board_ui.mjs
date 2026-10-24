// Exercise the real board event handlers across an API state replacement.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const ids = new Map(), nodes = [];
class Element {
  constructor(tag='div') {this.tagName=tag.toUpperCase();this.children=[];this.dataset={};this.style={};this.value='';this.classList={toggle(){}};nodes.push(this);}
  set id(id){this._id=id;ids.set(id,this);} get id(){return this._id;}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=[...children];}
  setAttribute(k,v){this[k]=v;}
  querySelectorAll(){return this.children.flatMap(c=>c instanceof Element?[c,...c.querySelectorAll()]:[]);}
  querySelector(){return this.querySelectorAll().find(e=>e.dataset.keep==='true');}
}
const document={getElementById(id){if(!ids.has(id)){const el=new Element();el.id=id;}return ids.get(id);},
  createElement:tag=>new Element(tag),createTextNode:text=>text};
const source={schema:1,version:1,edit:'/owned/edit',name:'edit',fps:30,total_frames:120,selected_frames:120,sample:false,
  approved_revision:null, rows:[{id:'row',start_frame:0,end_frame:120,text:'A passage',keep:true,protected:false,note:'',emphasis:'',zoom:1}],
  revisions:[{id:'preview',board_version:1,state:'ready',selected_frames:120,approved:false,native_state:null}]};
let savedRows;
const clone=value=>JSON.parse(JSON.stringify(value));
const fetch=async(path,options)=>{
  const request=options?.body?JSON.parse(options.body):{};
  let result;
  if(path==='/board/projects')result={edits:[{name:'edit',path:'/owned/edit'}]};
  else if(path==='/board/load')result=clone(source);
  else if(path==='/board/approve'){source.approved_revision='preview';source.revisions[0].approved=true;result=clone(source);}
  else if(path==='/board/save'){savedRows=clone(request.rows);source.rows=savedRows;source.version++;source.approved_revision=null;result=clone(source);}
  else throw new Error('Unexpected API: '+path);
  return {ok:true,json:async()=>result};
};
const context=vm.createContext({document,fetch,URLSearchParams,URL,location:{search:'?edit=/owned/edit'},
  window:{addEventListener(){}},setInterval(){},Option:class extends Element{constructor(text,value){super('option');this.textContent=text;this.value=value;}},console});
vm.runInContext(fs.readFileSync(new URL('../plugins/ai-editor/lib/ai_editor/edit-board.js',import.meta.url),'utf8'),context);
const settle=async()=>{for(let i=0;i<6;i++)await new Promise(resolve=>setImmediate(resolve));};
await settle();
// The source strip is actionable, and source playback stops at the passage boundary.
const sourceButton=ids.get('sequence').children[0];
sourceButton.onclick();
assert.equal(ids.get('player-mode').textContent,'Source passage 1');
ids.get('player').play=async()=>{};
ids.get('player').onloadedmetadata();
assert.equal(ids.get('player').currentTime,0);
let paused=false;ids.get('player').pause=()=>{paused=true;};
ids.get('player').currentTime=4;ids.get('player').ontimeupdate();
assert.equal(paused,true,'Source passage playback must stop at its end');
await ids.get('approve').onclick();await settle();
const note=nodes.filter(e=>e['aria-label']==='Visual direction · planning note 1').at(-1);
note.value='Keep this correction after approval';note.oninput();
await ids.get('save').onclick();await settle();
assert.equal(savedRows[0].note,'Keep this correction after approval','Approval must not leave handlers attached to discarded row objects');
assert.equal(source.approved_revision,null);
console.log('edit board UI lifecycle: correction after approval persists');
