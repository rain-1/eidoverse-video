"""Small self-contained GLB reader/writer used by the wardrobe builder.
Requires NumPy. Supports ordinary embedded glTF 2 geometry (including strided
accessors and sparse overlays), not Draco/meshopt compressed geometry.
"""
from __future__ import annotations
import copy, json, struct
from pathlib import Path
import numpy as np

DTYPES={5120:np.int8,5121:np.uint8,5122:np.int16,5123:np.uint16,5125:np.uint32,5126:np.float32}
SIZES={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT2':4,'MAT3':9,'MAT4':16}

def transform(points, matrix):
    p=np.asarray(points,dtype=np.float64)
    return p@np.asarray(matrix)[:3,:3].T+np.asarray(matrix)[:3,3]

def norm(v, axis=-1):
    v=np.asarray(v,dtype=np.float64)
    return v/np.maximum(np.linalg.norm(v,axis=axis,keepdims=True),1e-12)

def quat_matrix(q):
    x,y,z,w=norm(q)
    return np.array([[1-2*y*y-2*z*z,2*x*y-2*z*w,2*x*z+2*y*w],
                     [2*x*y+2*z*w,1-2*x*x-2*z*z,2*y*z-2*x*w],
                     [2*x*z-2*y*w,2*y*z+2*x*w,1-2*x*x-2*y*y]])

def node_matrix(node):
    if 'matrix' in node:return np.array(node['matrix'],dtype=float).reshape(4,4).T
    m=np.eye(4);m[:3,:3]=quat_matrix(node.get('rotation',[0,0,0,1]))@np.diag(node.get('scale',[1,1,1]));m[:3,3]=node.get('translation',[0,0,0]);return m

class GLB:
    def __init__(self, doc=None, binary=b''):
        self.d=copy.deepcopy(doc) if doc is not None else {'asset':{'version':'2.0','generator':'Claude Idol Wardrobe v1 / procedural geometry'},'scene':0,'scenes':[{'nodes':[]}],'nodes':[],'meshes':[],'materials':[],'textures':[],'images':[],'samplers':[],'accessors':[],'bufferViews':[],'buffers':[{'byteLength':0}]}
        self.b=bytearray(binary)
    @classmethod
    def read(cls,path):
        raw=Path(path).read_bytes()
        if len(raw)<20 or raw[:4]!=b'glTF':raise ValueError(f'{path}: expected a binary glTF / VRM file')
        magic,version,total=struct.unpack_from('<4sII',raw,0)
        if version!=2 or total!=len(raw):raise ValueError(f'{path}: invalid GLB header')
        j=None;b=b'';off=12
        while off<len(raw):
            ln,typ=struct.unpack_from('<II',raw,off);off+=8
            if off+ln>len(raw):raise ValueError('Truncated GLB chunk')
            chunk=raw[off:off+ln];off+=ln
            if typ==0x4E4F534A:j=json.loads(chunk)
            elif typ==0x004E4942:b=chunk
        if j is None:raise ValueError('Missing JSON chunk')
        if len(j.get('buffers',[]))>1 or any('uri' in q for q in j.get('buffers',[])):raise ValueError('Only one embedded buffer is supported; unpack external buffers first')
        if any(x in j.get('extensionsRequired',[]) for x in ('KHR_draco_mesh_compression','EXT_meshopt_compression','KHR_mesh_quantization')):raise ValueError('Compressed/quantized geometry must be decompressed before wardrobe fitting')
        return cls(j,b)
    def clone(self):return GLB(self.d,self.b)
    def view(self,raw,target=None):
        self.b.extend(b'\0'*((-len(self.b))%4));offset=len(self.b);self.b.extend(raw)
        v={'buffer':0,'byteOffset':offset,'byteLength':len(raw)}
        if target:v['target']=target
        arr=self.d.setdefault('bufferViews',[]);arr.append(v);return len(arr)-1
    def accessor(self,arr,typ,component=5126,target=None,bounds=False):
        a=np.ascontiguousarray(arr,dtype=DTYPES[component]);n=SIZES[typ]
        if a.size % n:raise ValueError('Accessor size mismatch')
        v=self.view(a.tobytes(),target)
        ac={'bufferView':v,'byteOffset':0,'componentType':component,'count':a.size//n,'type':typ}
        if bounds:
            q=a.reshape(-1,n);ac['min']=q.min(0).astype(float).tolist();ac['max']=q.max(0).astype(float).tolist()
        self.d.setdefault('accessors',[]).append(ac);return len(self.d['accessors'])-1
    def array(self,i,normalize=True):
        ac=self.d['accessors'][i];dtype=np.dtype(DTYPES[ac['componentType']]).newbyteorder('<');n=SIZES[ac['type']];count=ac['count']
        if 'bufferView' not in ac:a=np.zeros((count,n),dtype=dtype)
        else:
            v=self.d['bufferViews'][ac['bufferView']];off=v.get('byteOffset',0)+ac.get('byteOffset',0);stride=v.get('byteStride',dtype.itemsize*n)
            a=np.ndarray((count,n),dtype=dtype,buffer=self.b,offset=off,strides=(stride,dtype.itemsize)).copy()
        if 'sparse' in ac:
            s=ac['sparse'];vi=self.d['bufferViews'][s['indices']['bufferView']];vv=self.d['bufferViews'][s['values']['bufferView']]
            ids=np.frombuffer(self.b,dtype=DTYPES[s['indices']['componentType']],count=s['count'],offset=vi.get('byteOffset',0)+s['indices'].get('byteOffset',0))
            vals=np.frombuffer(self.b,dtype=dtype,count=s['count']*n,offset=vv.get('byteOffset',0)+s['values'].get('byteOffset',0)).reshape(-1,n);a[ids]=vals
        if normalize and ac.get('normalized') and ac['componentType']!=5126:
            info=np.iinfo(dtype);a=a.astype(float)/info.max
            if info.min<0:a=np.maximum(a,-1)
        return a[:,0] if n==1 else a
    def image(self,path,name=None):
        path=Path(path);mime='image/png' if path.suffix.lower()=='.png' else 'image/jpeg'
        a=self.d.setdefault('images',[]);a.append({'name':name or path.stem,'mimeType':mime,'bufferView':self.view(path.read_bytes())});idx=len(a)-1
        if not self.d.get('samplers'):self.d['samplers']=[{'magFilter':9729,'minFilter':9987,'wrapS':10497,'wrapT':10497}]
        t=self.d.setdefault('textures',[]);t.append({'source':idx,'sampler':0});return len(t)-1
    def material(self,mat):
        self.d.setdefault('materials',[]).append(copy.deepcopy(mat));return len(self.d['materials'])-1
    def primitive(self,vertices,faces,normals=None,uv=None,mat=0,joints=None,weights=None):
        vertices=np.asarray(vertices,np.float32);faces=np.asarray(faces,np.uint32).reshape(-1,3)
        if normals is None:normals=vertex_normals(vertices,faces)
        attrs={'POSITION':self.accessor(vertices,'VEC3',target=34962,bounds=True),'NORMAL':self.accessor(normals,'VEC3',target=34962)}
        if uv is not None:attrs['TEXCOORD_0']=self.accessor(uv,'VEC2',target=34962)
        if joints is not None:
            attrs['JOINTS_0']=self.accessor(joints,'VEC4',5123,target=34962);attrs['WEIGHTS_0']=self.accessor(weights,'VEC4',target=34962)
        return {'attributes':attrs,'indices':self.accessor(faces.reshape(-1),'SCALAR',5125,target=34963),'material':int(mat),'mode':4}
    def mesh(self,name,primitives):
        self.d.setdefault('meshes',[]).append({'name':name,'primitives':primitives});return len(self.d['meshes'])-1
    def node(self,name,mesh=None,parent=None,**kw):
        node={'name':name,**kw}
        if mesh is not None:node['mesh']=mesh
        self.d.setdefault('nodes',[]).append(node);i=len(self.d['nodes'])-1
        if parent is None:self.d['scenes'][self.d.get('scene',0)]['nodes'].append(i)
        else:self.d['nodes'][parent].setdefault('children',[]).append(i)
        return i
    def worlds(self):
        nodes=self.d['nodes'];parents={c:i for i,n in enumerate(nodes) for c in n.get('children',[])};cache={};visiting=set()
        def go(i):
            if i in cache:return cache[i]
            if i in visiting:raise ValueError('Cycle in node hierarchy')
            visiting.add(i);m=node_matrix(nodes[i]);cache[i]=(go(parents[i])@m) if i in parents else m;visiting.remove(i);return cache[i]
        return np.array([go(i) for i in range(len(nodes))])
    def primitive_world(self,node_i,prim,worlds=None):
        w=self.worlds() if worlds is None else worlds;n=self.d['nodes'][node_i];p=self.array(prim['attributes']['POSITION'])
        if 'skin' in n and 'JOINTS_0' in prim['attributes']:
            skin=self.d['skins'][n['skin']];ib=self.array(skin['inverseBindMatrices']).reshape(-1,4,4).transpose(0,2,1) if 'inverseBindMatrices' in skin else np.repeat(np.eye(4)[None],len(skin['joints']),axis=0)
            m=w[skin['joints']]@ib;j=self.array(prim['attributes']['JOINTS_0']).astype(int);wt=self.array(prim['attributes']['WEIGHTS_0']);ph=np.column_stack([p,np.ones(len(p))]);out=np.zeros((len(p),3))
            for k in range(4):out+=np.einsum('nij,nj->ni',m[j[:,k]],ph)[:,:3]*wt[:,k,None]
            return out
        return transform(p,w[node_i])
    def import_resources(self,other):
        """Import geometry/material resources, but not nodes, skins or animations.
        Return old->new resource offsets; use these when constructing nodes.
        """
        keys=['bufferViews','accessors','images','samplers','textures','materials','meshes'];offset={k:len(self.d.get(k,[])) for k in keys}
        self.b.extend(b'\0'*((-len(self.b))%4));boff=len(self.b);self.b.extend(other.b)
        for k in keys:
            values=copy.deepcopy(other.d.get(k,[]))
            for q in values:
                if k=='bufferViews':q['buffer']=0;q['byteOffset']=q.get('byteOffset',0)+boff
                elif k=='accessors':
                    if 'bufferView'in q:q['bufferView']+=offset['bufferViews']
                    for fld in ('indices','values'):
                        if 'sparse'in q:q['sparse'][fld]['bufferView']+=offset['bufferViews']
                elif k=='images':
                    if 'bufferView'in q:q['bufferView']+=offset['bufferViews']
                    elif 'uri'in q:raise ValueError('External image in accessory GLB')
                elif k=='textures':
                    if 'source'in q:q['source']+=offset['images']
                    if 'sampler'in q:q['sampler']+=offset['samplers']
                elif k=='materials':
                    def fix(x):
                        if isinstance(x,dict):
                            for key,v in x.items():
                                if (key.lower().endswith('texture') or key=='texture') and isinstance(v,dict) and 'index'in v:v['index']+=offset['textures']
                                else:fix(v)
                        elif isinstance(x,list):
                            for z in x:fix(z)
                    fix(q)
                elif k=='meshes':
                    for p in q['primitives']:
                        for a in p['attributes']:p['attributes'][a]+=offset['accessors']
                        if 'indices'in p:p['indices']+=offset['accessors']
                        if 'material'in p:p['material']+=offset['materials']
                        for t in p.get('targets',[]):
                            for a in t:t[a]+=offset['accessors']
            self.d.setdefault(k,[]).extend(values)
        ext=self.d.setdefault('extensionsUsed',[])
        for e in other.d.get('extensionsUsed',[]):
            if e not in ext:ext.append(e)
        return offset
    def save(self,path):
        self.b.extend(b'\0'*((-len(self.b))%4));self.d['buffers']=[{'byteLength':len(self.b)}]
        d=copy.deepcopy(self.d)
        for k in ['textures','images','samplers','materials','skins','animations','extensionsUsed','extensionsRequired']:
            if k in d and not d[k]:del d[k]
        raw=json.dumps(d,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode();raw+=b' '*((-len(raw))%4)
        out=struct.pack('<4sII',b'glTF',2,12+8+len(raw)+8+len(self.b))+struct.pack('<II',len(raw),0x4E4F534A)+raw+struct.pack('<II',len(self.b),0x004E4942)+self.b
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(out)

def vertex_normals(v,f):
    v=np.asarray(v);f=np.asarray(f);n=np.zeros_like(v,dtype=float);c=np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]])
    for k in range(3):np.add.at(n,f[:,k],c)
    return norm(n)
