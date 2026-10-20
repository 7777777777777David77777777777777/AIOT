// No real camera, permission grant, or upload: exercise stream lifecycle and capture.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
function fixture(getUserMedia) {
  const nodes = {}, events = {}, added = []; let stopped = 0;
  const stream = { getTracks: () => [{ stop: () => stopped++ }] };
  for (const id of ['cameraDialog','cameraVideo','cameraCanvas','cameraError','cameraCapture','cameraUse','cameraRetake','sourceFiles','sourceCamera','photoSourceDialog']) {
    nodes[id] = { open:false, videoWidth:640, videoHeight:480, addEventListener:(name, fn) => events[id+name]=fn,
      close(){this.open=false;events[id+'close']?.();}, showModal(){this.open=true;}, play:async()=>{},
      getContext:()=>({drawImage:()=>{}}), toBlob:fn=>fn({size:20}) };
  }
  const context = {$:id=>nodes[id], state:{busy:false,images:[]}, toast:()=>{}, choose:()=>{},
    addFiles:files=>added.push(...files), File:class {constructor(parts,name,opts){this.name=name;this.type=opts.type;}},
    navigator:{mediaDevices:{getUserMedia:()=>getUserMedia(stream)}},
    window:{isSecureContext:true,addEventListener:()=>{}}, document:{addEventListener:()=>{}}};
  vm.runInNewContext(fs.readFileSync('app/static/js/camera.js','utf8'),context);
  return {nodes,stream,added,stopped:()=>stopped};
}
(async()=>{
  let f=fixture(async stream=>stream);
  await f.nodes.sourceCamera.onclick();assert.equal(f.nodes.cameraVideo.srcObject,f.stream);
  f.nodes.cameraCapture.onclick();assert.equal(f.nodes.cameraCanvas.width,640);
  f.nodes.cameraUse.onclick();assert.equal(f.added.length,1);assert.equal(f.added[0].type,'image/jpeg');assert.equal(f.stopped(),1);
  let resolve;f=fixture(()=>new Promise(r=>resolve=r));const pending=f.nodes.sourceCamera.onclick();
  f.nodes.cameraDialog.close();resolve(f.stream);await pending;assert.equal(f.stopped(),1);assert.equal(f.nodes.cameraVideo.srcObject,null);
  f=fixture(async()=>{throw {name:'NotAllowedError'};});await f.nodes.sourceCamera.onclick();
  assert(f.nodes.cameraError.textContent);assert.equal(f.nodes.cameraCapture.disabled,true);assert.equal(f.added.length,0);
  console.log('Camera capture, close-before-permission, and denied-permission checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
