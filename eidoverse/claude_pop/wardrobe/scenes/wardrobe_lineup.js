/* Silent wardrobe inspection, not a finished music video.
 * Uses complete VRMs written by scripts/build_vrms.py. No additional attachments
 * or material overrides are needed. This scene owns the normalized humanoids.
 */
'use strict';
const wardrobeActors=[];
globalThis.setup=async function(){
  const renderer=new THREE.WebGPURenderer({canvas,antialias:true,adapter:GPU_ADAPTER,device:GPU_DEVICE});
  renderer.setSize(WIDTH,HEIGHT);renderer.outputColorSpace=THREE.SRGBColorSpace;
  renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.05;await renderer.init();
  const scene=new THREE.Scene();scene.background=new THREE.Color(0x101827);
  scene.add(new THREE.HemisphereLight(0xe9f2ff,0x303849,2.1));
  for(const [position,intensity,color] of [[[4,6,5],3,0xfff0df],[[-4,4,3],2,0xd9e6ff],[[1,5,-4],2.5,0xc5d7ff]]){
    const light=new THREE.DirectionalLight(color,intensity);light.position.fromArray(position);scene.add(light);
  }
  const floor=new THREE.Mesh(new THREE.PlaneGeometry(24,24),new THREE.MeshStandardNodeMaterial({color:0x263147,roughness:.78,metalness:.12}));floor.rotation.x=-Math.PI/2;scene.add(floor);
  const keys=['character_1','character_2','character_3','character_4','character_5'].filter(k=>ASSETS[k]);
  if(!keys.length)throw new Error('No dressed characters supplied. Run scripts/build_vrms.py first.');
  for(let i=0;i<keys.length;i++){
    const loader=new globalThis.GLTFLoader();loader.register(parser=>new globalThis.VRMLoaderPlugin(parser));
    const gltf=await new Promise((resolve,reject)=>loader.parse(b64toArrayBuffer(ASSETS[keys[i]]),'',resolve,reject));
    const vrm=gltf.userData?.vrm;if(!vrm)throw new Error(`${keys[i]} is not a VRM.`);
    if(globalThis.VRMUtils?.rotateVRM0)globalThis.VRMUtils.rotateVRM0(vrm);
    vrm.scene.updateMatrixWorld(true);
    const hips=vrm.humanoid.getNormalizedBoneNode('hips'),p=new THREE.Vector3(),o=new THREE.Vector3();
    if(!hips)throw new Error('No normalized hips.');hips.getWorldPosition(p);vrm.scene.getWorldPosition(o);
    const h=Math.abs(p.y-o.y);if(h>.001)vrm.scene.scale.multiplyScalar(1/h);
    const root=new THREE.Group();root.position.x=(i-(keys.length-1)/2)*1.7;root.add(vrm.scene);scene.add(root);
    wardrobeActors.push({vrm,root});
  }
  const camera=new THREE.PerspectiveCamera(34,WIDTH/HEIGHT,.04,100);
  camera.position.set(keys.length===1?.6:.25,1.8,keys.length===1?4.4:9.0);camera.lookAt(0,1.15,0);
  globalThis._mixer=null;globalThis._vrm=null;globalThis._r=renderer;globalThis._s=scene;globalThis._c=camera;
};
function setBone(vrm,name,x,y,z){const n=vrm.humanoid.getNormalizedBoneNode(name);if(n)n.quaternion.setFromEuler(new THREE.Euler(x,y,z,'XYZ'));}
globalThis.renderFrame=async function(t){
  // 0..3: arms lowered. 3..7: arm/torso clearance test. 7..12: slow turn.
  const blend=Math.max(0,Math.min(1,(t-3)/1.2));
  for(const {vrm,root} of wardrobeActors){
    setBone(vrm,'leftUpperArm',0,0,-1.20+blend*(.65+.28*Math.sin(t*1.5)));
    setBone(vrm,'rightUpperArm',0,0,1.20-blend*(.65+.28*Math.sin(t*1.5+.5)));
    setBone(vrm,'leftLowerArm',0,-.12-blend*.45,0);setBone(vrm,'rightLowerArm',0,.12+blend*.45,0);
    setBone(vrm,'chest',0,blend*.09*Math.sin(t),0);setBone(vrm,'head',0,blend*.10*Math.sin(t*.8),0);
    root.rotation.y=t>7?(t-7)*.46:0;
    vrm.humanoid.update();vrm.scene.updateMatrixWorld(true);
  }
  await globalThis._r.renderAsync(globalThis._s,globalThis._c);
};
// preflight: ASSETS['character_1']
