/* Context Crew v1 — attach the REAL GLB props to an already loaded source VRM.
 * Intended for eidoverse globals. Garments require build_vrms.py, not this helper.
 * The fitted matrices must come from output/fitting_report.json for THIS avatar.
 * No guesses about raw-bone rotation, Blender bone roll or VRM version are made.
 */
'use strict';
globalThis.ClaudeWardrobeV1 = (() => {
  function required(name) {
    const value=globalThis[name]; if(!value) throw new Error(`Missing eidoverse interface: ${name}`); return value;
  }
  function parseJSONAsset(base64) {
    return JSON.parse(new TextDecoder().decode(new Uint8Array(required('b64toArrayBuffer')(base64))));
  }
  async function attach(vrm, fittedMember, assetBytes) {
    if(!vrm?.humanoid||!vrm?.scene) throw new TypeError('Expected a loaded VRM.');
    if(!Array.isArray(fittedMember?.attachments)) throw new TypeError('Pass one result from fitting_report.json.');
    if(typeof assetBytes!=='function') throw new TypeError('assetBytes(path) must return a base64 GLB or an ArrayBuffer.');
    const T=required('THREE'),Loader=required('GLTFLoader');
    const added=[];
    try {
      for(const entry of fittedMember.attachments) {
        if(!entry.boneLocalMatrix||entry.boneLocalMatrix.length!==16||!entry.boneLocalMatrix.every(Number.isFinite)) throw new Error(`Invalid fitted matrix: ${entry.id}`);
        if(vrm.scene.getObjectByName(entry.id)) throw new Error(`${entry.id} is already present; do not dress a pre-dressed VRM twice.`);
        const fallback={upperChest:['upperChest','chest','spine'],chest:['chest','spine'],neck:['neck','head']};
        const bone=(fallback[entry.bone]||[entry.bone]).map(n=>vrm.humanoid.getRawBoneNode(n)).find(Boolean);
        if(!bone) throw new Error(`Missing raw humanoid bone ${entry.bone}`);
        let bytes=await assetBytes(entry.asset);
        if(typeof bytes==='string') bytes=required('b64toArrayBuffer')(bytes);
        if(ArrayBuffer.isView(bytes)) bytes=bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength);
        if(!(bytes instanceof ArrayBuffer)) throw new TypeError(`assetBytes(${entry.asset}) did not return binary data.`);
        const loader=new Loader();
        const gltf=await new Promise((resolve,reject)=>loader.parse(bytes,'',resolve,reject));
        const mount=new T.Group(); mount.name=entry.id; mount.matrixAutoUpdate=false;
        mount.matrix.fromArray(entry.boneLocalMatrix); mount.userData.claudeWardrobe={member:fittedMember.member,attachment:entry.id};
        mount.add(gltf.scene); bone.add(mount); added.push(mount);
      }
      vrm.scene.updateMatrixWorld(true);
    } catch(error) { for(const mount of added) disposeMount(mount); throw error; }
    return {mounts:added,dispose(){for(const mount of added)disposeMount(mount);added.length=0;}};
  }
  function disposeMount(mount) {
    mount.removeFromParent(); const seen=new Set();
    mount.traverse(obj=>{ if(obj.geometry&&!seen.has(obj.geometry)){seen.add(obj.geometry);obj.geometry.dispose();}
      for(const mat of Array.isArray(obj.material)?obj.material:(obj.material?[obj.material]:[])) {
        if(seen.has(mat))continue;seen.add(mat);
        for(const value of Object.values(mat))if(value?.isTexture&&!seen.has(value)){seen.add(value);value.dispose();}
        mat.dispose();
      }
    });
  }
  return {attach,parseJSONAsset};
})();
