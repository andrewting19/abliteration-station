import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const [root,source,modulePath]=process.argv.slice(2);
if (!root || !source || !modulePath) throw new Error('root, source session, and Pi module required');
process.umask(0o077);
const snapshot=path.join(root,'source-copy.jsonl');
fs.copyFileSync(source,snapshot,fs.constants.COPYFILE_EXCL);
fs.chmodSync(snapshot,0o600);
const pi=await import(pathToFileURL(modulePath).href);
const entries=pi.parseSessionEntries(fs.readFileSync(snapshot,'utf8'));
const reference=entries.find(e=>{
  const m=e.message,u=m?.usage;
  return m?.role==='assistant' && m.stopReason==='toolUse' && u &&
    (u.input??0)+(u.cacheRead??0)+(u.cacheWrite??0)===201715;
});
if (!reference?.parentId) throw new Error('Historical request boundary not found');
const manager=pi.SessionManager.open(snapshot,path.join(root,'sessions'),path.join(root,'project'));
const fork=manager.createBranchedSession(reference.parentId);
if (!fork) throw new Error('Pi did not persist the branch');
fs.writeFileSync(path.join(root,'session-path'),fork+'\n',{mode:0o600,flag:'wx'});
fs.writeFileSync(path.join(root,'agent','settings.json'),JSON.stringify({compaction:{enabled:false},retry:{enabled:false}}),{mode:0o600,flag:'wx'});
console.log(JSON.stringify({fork,referencePromptTokens:201715,scope:'private session branch; original unchanged'}));
