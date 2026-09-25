'use strict';
// Receive only the user-requested result archive. Repository/runtime tokens stay
// inside this job. A one-blob, short-lived upload URL is encrypted for the sender.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {Readable} = require('node:stream');
const {pipeline} = require('node:stream/promises');
const repo = 'yellkiin/model_competition';
const branch = 'orion/archive-structure-results-20260925-0455';
const directory = 'research_a_orion_track_structure/results/publication_20260925_0455';
const name = 'orion-existing-results-transfer-20260925-0455';
const expectedBytes = 306823568;
async function api(p, method='GET', body=null) {
  const response = await fetch('https://api.github.com/repos/'+repo+'/'+p, {
    method, headers: {Authorization:'Bearer '+process.env.GH_TOKEN,
      Accept:'application/vnd.github+json','Content-Type':'application/json',
      'X-GitHub-Api-Version':'2022-11-28','User-Agent':'orion-requested-results-archive'},
    body:body===null?undefined:JSON.stringify(body),signal:AbortSignal.timeout(60000)
  });
  if (response.status===404 && method==='GET') return null;
  if (!response.ok) throw new Error('GitHub request failed: '+method+' '+p+' status '+response.status);
  return response.json();
}
async function readJSON(file) {
  const x=await api('contents/'+directory+'/'+file+'?ref='+encodeURIComponent(branch));
  return x ? JSON.parse(Buffer.from(x.content,'base64').toString('utf8')) : null;
}
async function writeJSON(file, value) {
  const p='contents/'+directory+'/'+file;
  const old=await api(p+'?ref='+encodeURIComponent(branch));
  await api(p,'PUT',{message:'chore(results): one-use archive transfer status',branch,
    content:Buffer.from(JSON.stringify(value,null,2)+'\n').toString('base64'),
    ...(old?{sha:old.sha}:{})});
}
(async()=>{
  if(process.env.GITHUB_REPOSITORY!==repo || process.env.GITHUB_HEAD_REF!==branch)
    throw new Error('Unexpected repository or branch');
  const token=process.env.ACTIONS_RUNTIME_TOKEN;
  const origin=process.env.ACTIONS_RESULTS_URL;
  if(!token || !origin || !process.env.GH_TOKEN) throw new Error('Required in-job credentials unavailable');
  const claims=JSON.parse(Buffer.from(token.split('.')[1],'base64url').toString('utf8'));
  const scope=String(claims.scp||'').split(' ').find(s=>s.startsWith('Actions.Results:'));
  if(!scope) throw new Error('Artifact scope unavailable');
  const parts=scope.split(':');
  const ids={workflow_run_backend_id:parts[1],workflow_job_run_backend_id:parts[2]};
  async function rpc(method, data) {
    const u=new URL('/twirp/github.actions.results.api.v1.ArtifactService/'+method,origin);
    const r=await fetch(u,{method:'POST',headers:{Authorization:'Bearer '+token,
      'Content-Type':'application/json','User-Agent':'actions-artifact-result-transfer'},
      body:JSON.stringify(data),signal:AbortSignal.timeout(60000)});
    if(!r.ok) throw new Error('Artifact '+method+' failed, status '+r.status);
    return r.json();
  }
  const created=await rpc('CreateArtifact',{...ids,name,version:4,
    expires_at:new Date(Date.now()+86400000).toISOString()});
  const uploadUrl=created.signed_upload_url||created.signedUploadUrl;
  if(!created.ok || !uploadUrl) throw new Error('Artifact upload session was not created');
  console.log('::add-mask::'+uploadUrl);
  const key=crypto.randomBytes(32),iv=crypto.randomBytes(12);
  const cipher=crypto.createCipheriv('aes-256-gcm',key,iv);
  const plaintext=Buffer.from(JSON.stringify({url:uploadUrl,name,expected_bytes:expectedBytes,
    run_id:process.env.GITHUB_RUN_ID}));
  const encrypted=Buffer.concat([cipher.update(plaintext),cipher.final()]);
  const wrapped=crypto.publicEncrypt({key:fs.readFileSync(path.join(__dirname,'public.pem')),
    oaepHash:'sha256',padding:crypto.constants.RSA_PKCS1_OAEP_PADDING},key);
  await writeJSON('UPLOAD_SESSION.json',{name,expected_bytes:expectedBytes,
    run_id:process.env.GITHUB_RUN_ID,wrapped_key:wrapped.toString('base64'),
    iv:iv.toString('base64'),tag:cipher.getAuthTag().toString('base64'),
    ciphertext:encrypted.toString('base64')});
  console.log('Encrypted single-archive upload session published.');
  const deadline=Date.now()+12*60*1000;
  let ack=null;
  while(Date.now()<deadline) {
    ack=await readJSON('UPLOAD_COMPLETE.json');
    if(ack && ack.name===name && ack.uploaded_bytes===expectedBytes) break;
    await new Promise(r=>setTimeout(r,10000));
  }
  if(!ack || ack.uploaded_bytes!==expectedBytes) throw new Error('No complete archive received before transfer deadline');
  const finalized=await rpc('FinalizeArtifact',{...ids,name,size:String(expectedBytes)});
  if(!finalized.ok) throw new Error('Artifact finalization failed');
  const signed=await rpc('GetSignedArtifactURL',{...ids,name});
  const downloadUrl=signed.signed_url||signed.signedUrl;
  if(!downloadUrl) throw new Error('Artifact download unavailable after finalization');
  console.log('::add-mask::'+downloadUrl);
  const download=await fetch(downloadUrl,{signal:AbortSignal.timeout(180000)});
  if(!download.ok) throw new Error('Finalized archive download failed: '+download.status);
  await pipeline(Readable.fromWeb(download.body),fs.createWriteStream('/tmp/orion_incoming_results.zip'));
  if(fs.statSync('/tmp/orion_incoming_results.zip').size!==expectedBytes) throw new Error('Received archive byte count mismatch');
  fs.writeFileSync('/tmp/orion_ingest_receipt.json',JSON.stringify({
    transfer_workflow_run_id:process.env.GITHUB_RUN_ID,
    transfer_artifact_id:finalized.artifact_id||finalized.artifactId,
    archive_bytes:expectedBytes,purpose:'File transfer only; no experiment executed'
  },null,2));
  await writeJSON('TRANSFER_RECEIVED.json',JSON.parse(fs.readFileSync('/tmp/orion_ingest_receipt.json','utf8')));
  console.log('Existing result archives received intact by byte count; ready for publication.');
})().catch(e=>{console.error(e.message);process.exitCode=1;});
