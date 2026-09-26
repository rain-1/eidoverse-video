#!/usr/bin/env python3
"""Fit the supplied wardrobe meshes to a local Claude VRM and write new avatars.

Usage (from the eidoverse repository root):
  python eidoverse/claude_pop/wardrobe/scripts/build_vrms.py \
      --source eidoverse/assets/vrms/claude_suit.vrm

The source is never overwritten. Original bone indices, humanoid mapping,
face geometry, expressions, skinning and license metadata are preserved.
Only named clothing layers are hidden/re-materialed. New garments are mapped
to the source rest skeleton, with fresh inverse bind matrices. Accessories
are transformed into their raw bone's local space and parented to that bone.

Dependencies: NumPy. Regenerating the original accessory meshes/textures also
requires Pillow, but ordinary fitting does not.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,math,re,sys
from pathlib import Path
import numpy as np
from gltf_io import GLB,norm,transform,vertex_normals
from geometry import BONES,BONE_NAMES
ROOT=Path(__file__).resolve().parents[1]
REQUIRED=['hips','spine','head','leftUpperArm','leftLowerArm','leftHand','rightUpperArm','rightLowerArm','rightHand','leftUpperLeg','leftLowerLeg','leftFoot','rightUpperLeg','rightLowerLeg','rightFoot']


def humanoid(g):
    ex=g.d.get('extensions',{})
    if 'VRMC_vrm'in ex:return {k:v['node'] for k,v in ex['VRMC_vrm']['humanoid']['humanBones'].items()},'1'
    if 'VRM'in ex:return {q['bone']:q['node'] for q in ex['VRM']['humanoid']['humanBones']},'0'
    raise ValueError('Input has no VRM humanoid extension. Supply the original .vrm, not an animation .vrma or plain .glb.')


def fallback_bones(b):
    missing=[k for k in REQUIRED if k not in b]
    if missing:raise ValueError('Required humanoid bones are missing: '+', '.join(missing))
    b=dict(b);b.setdefault('chest',b['spine']);b.setdefault('upperChest',b['chest']);b.setdefault('neck',b['head'])
    for side in ('left','right'):b.setdefault(side+'Shoulder',b[side+'UpperArm']);b.setdefault(side+'Toes',b[side+'Foot'])
    return b


def find_layers(g,mesh_map=None):
    layers={k:[] for k in ['jacket','tie','shirt','pants','shoes']};override=mesh_map or {}
    for i,n in enumerate(g.d['nodes']):
        if 'mesh'not in n:continue
        me=g.d['meshes'][n['mesh']];names=[n.get('name',''),me.get('name','')]
        for k in layers:
            allowed=override.get(k)
            matched=any(x in allowed for x in names) if allowed else any(re.search(r'(^|[^a-z])'+k+r'([^a-z]|$)',s.lower()) for s in names)
            if matched:layers[k].append(i)
    return layers


def frame_at(origin,F,scale=(1,1,1)):
    m=np.eye(4);m[:3,:3]=F@np.diag(scale);m[:3,3]=origin;return m


class Fit:
    def __init__(self,g,mesh_map=None):
        self.g=g;original,self.version=humanoid(g);self.original_bones=original;self.b=fallback_bones(original);self.W=g.worlds();self.p={k:self.W[i,:3,3] for k,i in self.b.items()};self.layers=find_layers(g,mesh_map);self.warnings=[]
        x=norm(self.p['leftUpperArm']-self.p['rightUpperArm']);up=self.p['neck']-self.p['hips'];up=norm(up-x*np.dot(up,x));z=norm(np.cross(x,up));self.F=np.column_stack([x,up,z]);self.origin=self.p['hips'];self.scale=float(np.linalg.norm(self.p['leftUpperLeg']-self.p['leftFoot'])/.87)
        if not np.isfinite(self.scale) or not .02<self.scale<100:raise ValueError('Implausible source skeleton scale; inspect the input units.')
        self.points={};self.all=[];self.head_points=[];parents={c:i for i,n in enumerate(g.d['nodes']) for c in n.get('children',[])}
        def below(i,parent):
            while True:
                if i==parent:return True
                if i not in parents:return False
                i=parents[i]
        for i,n in enumerate(g.d['nodes']):
            if 'mesh'not in n:continue
            pp=[]
            for prim in g.d['meshes'][n['mesh']]['primitives']:
                if 'POSITION'not in prim.get('attributes',{}):continue
                v=g.primitive_world(i,prim,self.W);pp.append(v);self.all.append(v)
                if below(i,self.b['head']):self.head_points.append(v)
                elif 'skin'in n and 'JOINTS_0'in prim['attributes']:
                    skin=g.d['skins'][n['skin']];j=g.array(prim['attributes']['JOINTS_0']).astype(int);w=g.array(prim['attributes']['WEIGHTS_0']);hs=np.array([below(q,self.b['head']) for q in skin['joints']]);mask=(hs[j]*w).sum(1)>.50
                    if np.any(mask):self.head_points.append(v[mask])
                elif re.search('head|face|bloom',n.get('name',''),re.I):self.head_points.append(v)
            if pp:self.points[i]=np.vstack(pp)
        if not self.all:raise ValueError('The source contains no readable mesh positions.')
        # Reference shoulder/torso dimensions, refined from named jacket geometry.
        armspan=np.linalg.norm(self.p['leftUpperArm']-self.p['rightUpperArm']);self.width_scale=armspan/.48
        torso_up=np.dot(self.p['upperChest']-self.p['hips'],up);self.height_scale=torso_up/.47 if torso_up>.08*self.scale else self.scale
        self.depth_scale=self.width_scale
        jp=self.layer_points('jacket')
        if len(jp):
            c=self.canonical(jp);h=np.dot(self.p['upperChest']-self.origin,up);s=np.abs(c[:,0])<armspan*.43; s &= (c[:,1]>h*.20)&(c[:,1]<h*.83)
            if s.sum()>20:
                deep=np.percentile(c[s,2],99)-np.percentile(c[s,2],1)
                if deep>.035*self.scale:self.depth_scale=deep/.30
        self.hip_center=self.p['hips'].copy();self.hip_scale=np.array([self.width_scale,self.height_scale,self.depth_scale])
        pants=self.layer_points('pants')
        if len(pants):
            c=self.canonical(pants);cut=c[(c[:,1]>-.14*self.scale)&(c[:,1]<.14*self.scale)]
            if len(cut)>20:
                size=np.ptp(cut,axis=0);self.hip_scale=np.array([size[0]/.410,self.height_scale,size[2]/.294])
                self.hip_center=self.origin+self.F[:,1]*(float(np.quantile(c[:,1],.998))-.012*self.scale)
        self.head_center,self.head_size=self.bounds(self.head_points,refcenter=self.p['head'],fallback=np.array([.84,.84,.16])*self.scale,label='head')
        self.sleeve_scale={}
        for side in ('left','right'):
            pa=self.p[side+'UpperArm'];pb=self.p[side+'LowerArm'];axis=norm(pb-pa);length=np.linalg.norm(pb-pa);value=self.width_scale
            if len(jp):
                rel=jp-pa;along=rel@axis;rad=np.linalg.norm(rel-along[:,None]*axis,axis=1);mask=(along>length*.25)&(along<length*.75)&(rad<length*.85)
                if mask.sum()>15:value=float(np.percentile(rad[mask],93)/.092)
            self.sleeve_scale[side]=np.clip(value,self.scale*.40,self.scale*2.2)
        self.feet={}
        shoe_points=self.layer_points('shoes')
        for side,s in [('left',1),('right',-1)]:
            if len(shoe_points):c=self.canonical(shoe_points);sel=shoe_points[c[:,0]*s>0]
            else:sel=np.empty((0,3))
            self.feet[side]=self.bounds([sel] if len(sel) else [],refcenter=self.p[side+'Foot']+self.F@np.array([0,-.038,.045])*self.scale,fallback=np.array([.17,.14,.31])*self.scale,label=side+' shoe')
    def canonical(self,v):return (np.asarray(v)-self.origin)@self.F
    def layer_points(self,k):
        out=[self.points[i] for i in self.layers[k] if i in self.points];return np.vstack(out) if out else np.empty((0,3))
    def bounds(self,parts,refcenter,fallback,label):
        if not parts:
            self.warnings.append(f'No isolated {label} geometry found; using skeleton-scaled clearance estimate.');return np.array(refcenter),np.array(fallback)
        c=self.canonical(np.vstack(parts));mi=c.min(0);ma=c.max(0);size=ma-mi
        if np.any(size<1e-6):size=np.maximum(size,fallback*.2)
        return self.origin+self.F@((mi+ma)/2),size
    def garment_transforms(self,settings):
        sx=self.width_scale*float(settings.get('bodyWidthPadding',1.08));sz=self.depth_scale*float(settings.get('bodyDepthPadding',1.12));sy=self.height_scale
        transforms=[]
        for name in BONE_NAMES:
            F=self.F.copy();sc=np.array([sx,sy,sz]);origin=self.p[name]
            for side,s in [('left',1),('right',-1)]:
                if name in (side+'UpperArm',side+'LowerArm',side+'Hand'):
                    child=side+('LowerArm' if name.endswith('UpperArm') else 'Hand');other=self.p[child] if child!=name else origin+(self.p[side+'Hand']-self.p[side+'LowerArm'])
                    x=norm(other-origin)*s;y=norm(self.F[:,1]-x*np.dot(self.F[:,1],x));F=np.c_[x,y,norm(np.cross(x,y))]
                    ref=.25 if name.endswith('UpperArm') else .23
                    radial=self.sleeve_scale[side]*float(settings.get('sleevePadding',1.10));sc=[np.linalg.norm(other-origin)/ref,radial,radial]
                elif name in (side+'UpperLeg',side+'LowerLeg'):
                    child=side+('LowerLeg' if name.endswith('UpperLeg') else 'Foot');y=norm(origin-self.p[child]);x=norm(self.F[:,0]-y*np.dot(self.F[:,0],y));F=np.c_[x,y,norm(np.cross(x,y))];ref=.44 if name.endswith('UpperLeg') else .43;sc=[sx,np.linalg.norm(origin-self.p[child])/ref,sz]
            m=frame_at(origin,F,sc);r=np.eye(4);r[:3,3]=-np.array(BONES[name][0]);transforms.append(m@r)
        return np.array(transforms)
    def attachment(self,item,settings):
        fit=item['fitSpace'];bone=item['bone'];F=self.F.copy();scale=np.array([1.,1.,1.]);center=self.p[bone]
        if fit=='head':
            center=self.head_center;scale=self.head_size/np.array([.84,.84,.16]);scale[2]=np.clip(scale[2],self.scale*.65,self.scale*2.)
            scale*=np.array(settings.get('headScale',[1,1,1]));center=center+F@np.array(settings.get('headOffset',[0,0,0]))*self.scale
        elif fit=='chest':
            center=.65*self.p['chest']+.35*self.p['upperChest'];scale=np.array([self.width_scale,self.height_scale,self.depth_scale])*[1.06,1,1.08]
        elif fit=='hips':
            center=self.hip_center;scale=self.hip_scale*[1.02,1,1.04]
        elif fit=='wrist':
            side='left' if bone.startswith('left') else 'right';s=1 if side=='left' else -1;pa=self.p[side+'LowerArm'];pb=self.p[side+'Hand'];center=pa+.78*(pb-pa);x=norm(pb-pa)*s;y=norm(self.F[:,1]-x*np.dot(self.F[:,1],x));F=np.c_[x,y,norm(np.cross(x,y))];radial=self.sleeve_scale[side];scale=[np.linalg.norm(pb-pa)/.23,radial,radial]
        elif fit=='foot':
            side='left' if bone.startswith('left') else 'right';center,extent=self.feet[side];scale=extent/np.array([.17,.14,.31]);scale=np.array(scale);scale[0]*=1.045;scale[2]*=1.02
        else:raise ValueError(f'Unknown fitSpace {fit!r}')
        scale=np.asarray(scale)*np.array(item.get('scale',[1,1,1]));center=center+F@np.array(item.get('offset',[0,0,0]))*self.scale
        if not np.all(np.isfinite(scale)) or np.min(scale)<=0:raise ValueError('Invalid attachment scale')
        return frame_at(center,F,scale)
    def report(self):
        return {'vrmVersion':self.version,'scaleEstimate':self.scale,'referenceFrameWorld':self.F.tolist(),'sourceHeadCenter':self.head_center.tolist(),'sourceHeadExtent':self.head_size.tolist(),'widthScale':float(self.width_scale),'heightScale':float(self.height_scale),'depthScale':float(self.depth_scale),'sleeveScale':{k:float(v) for k,v in self.sleeve_scale.items()},'namedLayers':{k:[self.g.d['nodes'][i].get('name',str(i)) for i in v] for k,v in self.layers.items()},'warnings':self.warnings}


def append_shader_entries(out):
    if 'VRM'not in out.d.get('extensions',{}):return
    mats=out.d['materials'];props=out.d['extensions']['VRM'].setdefault('materialProperties',[])
    while len(props)<len(mats):
        m=mats[len(props)];props.append({'name':m.get('name',f'wardrobe_{len(props)}'),'shader':'VRM_USE_GLTFSHADER','renderQueue':-1,'floatProperties':{},'vectorProperties':{},'textureProperties':{},'keywordMap':{},'tagMap':{}})


def apply_member(source,fit,manifest,output,attachments_only=False):
    out=source.clone();initial_nodes=len(out.d['nodes']);settings=manifest['fit'];made=[]
    # Garment materials also supply deliberate new PBR materials for source layers.
    template=GLB.read(ROOT/manifest['garment']);offset=out.import_resources(template)
    mat_names={m.get('name'):i for i,m in enumerate(out.d['materials'])};member=manifest['id']
    # Re-material source clothes, never head/face/skin or other anonymous meshes.
    for layer,key in [('shirt','dark'),('pants','dark'),('shoes','rubber')]:
        for ni in fit.layers[layer]:
            node=out.d['nodes'][ni];mi=node['mesh'];new=copy.deepcopy(out.d['meshes'][mi]);new['name']=new.get('name',layer)+'__'+member
            for p in new['primitives']:p['material']=mat_names[f'{member}_{key}']
            out.d['meshes'].append(new);node['mesh']=len(out.d['meshes'])-1
    if not attachments_only:
        if not fit.layers['jacket']:raise ValueError('No separately named jacket mesh was found. Use --inspect and --mesh-map, or --attachments-only. Nothing was written.')
        for layer in manifest['hideOriginalMeshes']:
            for ni in fit.layers.get(layer,[]):
                out.d['nodes'][ni].pop('mesh',None);out.d['nodes'][ni].pop('skin',None)
                out.d['nodes'][ni].setdefault('extras',{})['wardrobeHiddenOriginalLayer']=layer
        # Unique raw joint indices; missing optional bones map to their parents.
        target=[];remap=[]
        for b in BONE_NAMES:
            ni=fit.b[b]
            if ni not in target:target.append(ni)
            remap.append(target.index(ni))
        ib=[np.linalg.inv(fit.W[i]).T.reshape(-1) for i in target]
        out.d.setdefault('skins',[]).append({'name':member+'_wardrobe_skin','joints':target,'inverseBindMatrices':out.accessor(ib,'MAT4'),'skeleton':fit.b['hips']});skinidx=len(out.d['skins'])-1
        T=fit.garment_transforms(settings)
        for tnode in template.d['nodes']:
            if 'mesh'not in tnode:continue
            meshidx=tnode['mesh']+offset['meshes'];mesh=out.d['meshes'][meshidx]
            for p in mesh['primitives']:
                a=p['attributes'];v=out.array(a['POSITION']);j=out.array(a['JOINTS_0']).astype(int);w=out.array(a['WEIGHTS_0']);ph=np.c_[v,np.ones(len(v))];newv=np.zeros_like(v,dtype=float)
                for k in range(4):newv+=np.einsum('nij,nj->ni',T[j[:,k]],ph)[:,:3]*w[:,k,None]
                faces=out.array(p['indices']).reshape(-1,3);a['POSITION']=out.accessor(newv,'VEC3',target=34962,bounds=True);a['NORMAL']=out.accessor(vertex_normals(newv,faces),'VEC3',target=34962);a['JOINTS_0']=out.accessor(np.asarray(remap)[j],'VEC4',5123,target=34962)
            ni=out.node(member+'_fitted_outerwear',meshidx,skin=skinidx,extras={'claudeWardrobe':{'member':member,'type':'fitted skinned outerwear'}});made.append({'node':ni,'mesh':meshidx,'type':'garment'})
    else:
        fit.warnings.append('Attachments-only build: original jacket/tie retained; no fitted replacement garment added.')
    transforms=[]
    for item in manifest['attachments']:
        asset=GLB.read(ROOT/item['asset']);off=out.import_resources(asset);Wanchor=fit.attachment(item,settings);bone=fit.b[item['bone']];local=np.linalg.inv(fit.W[bone])@Wanchor;worlds=asset.worlds()
        for ai,an in enumerate(asset.d['nodes']):
            if 'mesh'not in an:continue
            if 'skin'in an:raise ValueError('Rigid accessory unexpectedly contains a skin')
            m=local@worlds[ai];ni=out.node(item['id'],an['mesh']+off['meshes'],parent=bone,matrix=m.T.reshape(-1).tolist(),extras={'claudeWardrobe':{'member':member,'attachmentId':item['id'],'bone':item['bone'],'fitSpace':item['fitSpace']}})
            made.append({'node':ni,'mesh':an['mesh']+off['meshes'],'type':'accessory'})
        transforms.append({'id':item['id'],'asset':item['asset'],'bone':item['bone'],'boneLocalMatrix':local.T.reshape(-1).tolist()})
    # Keep the animation/expressions metadata and original humanoid mapping intact.
    append_shader_entries(out)
    vrm=out.d['extensions'].get('VRM',out.d['extensions'].get('VRMC_vrm'))
    meta=vrm.setdefault('meta',{});title='title' if fit.version=='0' else 'name';meta[title]=meta.get(title,'Claude')+' / '+manifest['name']+' wardrobe'
    fp=vrm.setdefault('firstPerson',{});ann=fp.setdefault('meshAnnotations',[])
    for q in made:
        if fit.version=='0':ann.append({'mesh':q['mesh'],'firstPersonFlag':'Both'})
        else:ann.append({'node':q['node'],'type':'both'})
    out.d['asset'].setdefault('extras',{})['claudeWardrobe']={'version':'1.0','member':member,'modifications':'Added fitted skinned outerwear, rigid accessories and replacement clothing materials. Original face/humanoid/license retained.','sourceCredit':'Claude suit model by digi; claudesona design by voooooogel. Source repository states CC-BY.'}
    assert humanoid(out)[0]==fit.original_bones,'Humanoid mapping changed unexpectedly'
    if len(out.d['nodes'])<=initial_nodes:raise AssertionError('No assets added')
    output=Path(output)
    # Atomic replacement of this generated derivative, never the source file.
    tmp=output.with_suffix('.building.vrm');out.save(tmp);GLB.read(tmp);tmp.replace(output)
    return {'member':member,'path':str(output),'bytes':output.stat().st_size,'addedNodes':len(out.d['nodes'])-initial_nodes,'attachments':transforms,'sourceHumanoidUnchanged':True}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--source',type=Path,default=Path('eidoverse/assets/vrms/claude_suit.vrm'));p.add_argument('--output',type=Path,default=Path('work/claude_pop/vrms'));p.add_argument('--only',nargs='+',choices=['prime','pixel','nova','echo','sol']);p.add_argument('--inspect',action='store_true');p.add_argument('--attachments-only',action='store_true');p.add_argument('--mesh-map',type=Path,help='JSON mapping layer names to exact source node/mesh names');p.add_argument('--fit-config',type=Path,help='JSON: {member:{fit:{...},attachments:{attachment_id:{scale:[...],offset:[...]}}}}')
    a=p.parse_args(argv)
    if not a.source.is_file():p.error(f'Source VRM not found: {a.source}. Run from your repository root, or pass its full path.')
    source=GLB.read(a.source);mesh_map=json.loads(a.mesh_map.read_text()) if a.mesh_map else None;fit=Fit(source,mesh_map)
    if a.inspect:
        print(json.dumps({'fit':fit.report(),'bones':fit.original_bones,'meshNodes':[{'index':i,'node':n.get('name'),'mesh':source.d['meshes'][n['mesh']].get('name')} for i,n in enumerate(source.d['nodes']) if 'mesh'in n]},indent=2));return 0
    if a.source.resolve() in [(a.output/f'claude_{m}.vrm').resolve() for m in (a.only or ['prime','pixel','nova','echo','sol'])]:p.error('Refusing to overwrite the source VRM')
    if not a.attachments_only and not fit.layers['jacket']:p.error('No named jacket mesh. Run --inspect, supply --mesh-map, or choose --attachments-only for another avatar.')
    a.output.mkdir(parents=True,exist_ok=True);override=json.loads(a.fit_config.read_text()) if a.fit_config else {};results=[]
    for member in a.only or ['prime','pixel','nova','echo','sol']:
        man=json.loads((ROOT/'manifests'/f'{member}.json').read_text());ov=override.get(member,{});man['fit'].update(ov.get('fit',{}))
        for item in man['attachments']:item.update(ov.get('attachments',{}).get(item['id'],{}))
        result=apply_member(source,fit,man,a.output/f'claude_{member}.vrm',a.attachments_only);results.append(result);print(f'Wrote {result["path"]} ({result["bytes"]/1048576:.2f} MiB)')
    report={'version':'1.0','source':str(a.source.resolve()),'sourceSHA256':hashlib.sha256(a.source.read_bytes()).hexdigest(),'fit':fit.report(),'results':results,'status':'Geometry/rest-skeleton fit completed. Actual Claude dance/render QA still required.'}
    (a.output/'fitting_report.json').write_text(json.dumps(report,indent=2)+'\n');print('Source untouched. Inspect the lineup and an arms-up dance probe before final rendering.')
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,KeyError,IndexError,OSError,np.linalg.LinAlgError) as e:print(f'Wardrobe build failed: {e}',file=sys.stderr);sys.exit(1)
