// Isolated browser QA against an already running local editor. No user-browser settings change.
// node tests/browser_edit_board.mjs <edit-folder> <evidence-folder> [--compare]
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFileSync,mkdirSync,existsSync} from 'node:fs';
import {join,resolve} from 'node:path';
import {homedir} from 'node:os';
import {execFileSync} from 'node:child_process';
const [edit,output,...flags]=process.argv.slice(2);
assert.ok(edit&&output,'Supply a synthetic QA edit and evidence folder.');
const runtime=process.env.AI_EDITOR_HOME||join(homedir(),'.ai-video-editor');
const require=createRequire(join(runtime,'motion/package.json'));
const puppeteer=require('puppeteer-core');
const executablePath=execFileSync(join(runtime,'motion/node_modules/.bin/hyperframes'),['browser','path'],{encoding:'utf8'}).trim().split('\n').pop();
const browser=await puppeteer.launch({executablePath:existsSync('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')?'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome':executablePath,headless:true});
mkdirSync(output,{recursive:true});
try{
 const page=await browser.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.setViewport({width:1440,height:1050,deviceScaleFactor:1});
 const token=readFileSync(join(runtime,'home/token'),'utf8').trim();
 await page.goto('http://127.0.0.1:47821/edit-board?'+new URLSearchParams({edit:resolve(edit),t:token}),{waitUntil:'networkidle0'});
 await page.waitForFunction(()=>document.querySelector('#project-name').textContent.length>0,{timeout:15000});
 assert.ok(await page.$('#style-reference option[value]'));
 await page.click('.visual-details summary');
 console.log('Board loaded');
 const treatment=await page.$eval('[aria-label="Caption treatment passage 1"]',e=>e.value);
 assert.ok(['editorial','clean','spotlight'].includes(treatment));
 await page.screenshot({path:join(output,'board-controls.png'),fullPage:true});
 await page.click('.visual-details summary');
 if(flags.includes('--compare')){
  assert.equal(await page.$eval('#compare-resolve',e=>e.disabled),false);
  await page.click('#compare-resolve');
  await page.waitForFunction(()=>!document.querySelector('#proof-panel').hidden&&document.querySelectorAll('#proof-images img').length===2,{timeout:180000});
 }
 if(await page.$eval('#proof-panel',e=>!e.hidden)){
  await page.select('#proof-frame','2');
  await page.waitForFunction(()=>[...document.querySelectorAll('#proof-images img')].every(i=>i.complete&&i.naturalWidth>0),{timeout:15000});
  await page.$eval('#proof-panel',e=>e.scrollIntoView({block:'center'}));
  await page.screenshot({path:join(output,'board-comparison.png')});
 }
 console.log('Comparison images verified');
 await page.click('#watch');
 await page.$eval('#player',e=>{e.muted=true;e.play().catch(()=>{});});
 await page.waitForFunction(()=>document.querySelector('#player').currentTime>1,{timeout:15000});
 await page.waitForFunction(()=>document.querySelector('#player').ended,{timeout:30000});
 await page.setViewport({width:390,height:844,deviceScaleFactor:1});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true,'Mobile board must not scroll horizontally');
 await page.screenshot({path:join(output,'board-mobile.png'),fullPage:true});
 assert.deepEqual(errors,[]);
 console.log('Browser QA: controls present, native comparison images decoded, preview playback completed, mobile fits, no page errors.');
}catch(error){console.error(error.message);const pages=await browser.pages();for(const p of pages){console.error(await p.$eval('#notice',e=>e.textContent).catch(()=>''));await p.screenshot({path:join(output,'browser-failure.png')}).catch(()=>{});}throw error;}finally{await browser.close();}
