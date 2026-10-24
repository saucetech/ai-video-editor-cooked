// A capture browser that ignores graceful termination must not keep its caller alive.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';
if(process.platform==='win32'){console.log('capture shutdown fixture skipped: requires a POSIX executable');process.exit(0);}
const root=fs.mkdtempSync(path.join(os.tmpdir(),'capture-shutdown-'));
const fixture=path.join(root,'browser');
const pidFile=path.join(root,'pid');
const moduleURL=pathToFileURL(path.resolve('plugins/ai-editor/skills/style-edit/scripts/capture.mjs')).href;
let caller;
try {
  // Launch is tested with a real, harmless process that deliberately ignores SIGTERM.
  fs.writeFileSync(fixture,`#!${process.execPath}\nimport fs from 'node:fs';\nif(process.argv.includes('--dump-dom'))process.exit(0);\nprocess.on('SIGTERM',()=>{});\nfs.writeFileSync(${JSON.stringify(pidFile)},String(process.pid));\nsetInterval(()=>{},1000);\n`,{mode:0o700});
  const driver=path.join(root,'driver.mjs');
  fs.writeFileSync(driver,`import {launch} from ${JSON.stringify(moduleURL)};\nimport fs from 'node:fs';\nconst c=launch(${JSON.stringify(fixture)});\nconst wait=setInterval(()=>{if(fs.existsSync(${JSON.stringify(pidFile)})){clearInterval(wait);c.close();}},20);\n`);
  caller=spawn(process.execPath,[driver],{stdio:['ignore','ignore','pipe']});
  let error='';caller.stderr.on('data',d=>error+=d);
  const outcome=await Promise.race([
    new Promise(resolve=>caller.once('exit',(code,signal)=>resolve({code,signal}))),
    new Promise(resolve=>setTimeout(()=>resolve({timeout:true}),6000).unref())
  ]);
  assert.equal(outcome.timeout,undefined,'capture.close left its browser/caller running after six seconds');
  assert.equal(outcome.code,0,error);
  console.log('capture shutdown ok: an unresponsive browser is terminated');
} finally {
  if(fs.existsSync(pidFile)){try{process.kill(Number(fs.readFileSync(pidFile,'utf8')),'SIGKILL');}catch{}}
  caller?.kill('SIGKILL');
  fs.rmSync(root,{recursive:true,force:true});
}
