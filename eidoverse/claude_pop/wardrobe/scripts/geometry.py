"""Procedural, editable wardrobe geometry. Coordinates: metres, +Y up, +Z front."""
from __future__ import annotations
import numpy as np
from gltf_io import norm, vertex_normals, transform

class Geo:
    def __init__(self,v,f,uv=None,n=None):
        self.v=np.asarray(v,dtype=float);self.f=np.asarray(f,dtype=np.uint32).reshape(-1,3)
        self.uv=np.asarray(uv,dtype=float) if uv is not None else np.column_stack([self.v[:,0]*2,self.v[:,1]*2])
        self.n=np.asarray(n,dtype=float) if n is not None else vertex_normals(self.v,self.f)
    def moved(self,p):return Geo(self.v+np.array(p),self.f,self.uv,self.n)
    def scaled(self,s):
        s=np.broadcast_to(s,(3,));return Geo(self.v*s,self.f,self.uv,norm(self.n/s))
    def matrix(self,m):return Geo(transform(self.v,m),self.f,self.uv,norm(self.n@np.linalg.inv(m[:3,:3])))

def box(size,center=(0,0,0)):
    x,y,z=np.array(size)/2;v=[];f=[];uv=[];n=[]
    sides=[([(x,-y,-z),(x,y,-z),(x,y,z),(x,-y,z)],(1,0,0)),([(-x,-y,z),(-x,y,z),(-x,y,-z),(-x,-y,-z)],(-1,0,0)),
           ([(-x,y,-z),(-x,y,z),(x,y,z),(x,y,-z)],(0,1,0)),([(-x,-y,z),(-x,-y,-z),(x,-y,-z),(x,-y,z)],(0,-1,0)),
           ([(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)],(0,0,1)),([(x,-y,-z),(-x,-y,-z),(-x,y,-z),(x,y,-z)],(0,0,-1))]
    for vs,no in sides:
        st=len(v);v+=vs;n += [no]*4;uv +=[(0,0),(1,0),(1,1),(0,1)];f +=[(st,st+1,st+2),(st,st+2,st+3)]
    return Geo(np.array(v)+center,f,uv,n)

def sphere(radius=1,center=(0,0,0),segments=24,rings=12):
    v=[];uv=[];f=[]
    for i in range(rings+1):
        th=np.pi*i/rings
        for j in range(segments+1):
            ph=2*np.pi*j/segments;v.append([np.sin(th)*np.cos(ph),np.cos(th),np.sin(th)*np.sin(ph)]);uv.append([j/segments,i/rings])
    for i in range(rings):
        for j in range(segments):
            a=i*(segments+1)+j;b=a+segments+1
            if i>0:f.append((a,a+1,b))
            if i<rings-1:f.append((a+1,b+1,b))
    v=np.array(v);return Geo(v*np.broadcast_to(radius,(3,))+center,f,uv,norm(v/np.broadcast_to(radius,(3,))))

def tube(points,radius=.01,sides=10,closed=False):
    p=np.asarray(points,float)
    if closed and np.linalg.norm(p[0]-p[-1])>1e-9:p=np.vstack([p,p[0]])
    tang=norm(np.gradient(p,axis=0));ref=np.array([0,0,1.])
    if np.max(np.abs(tang@ref))>.97:ref=np.array([0,1,0.])
    u=norm(np.cross(tang,ref));v=norm(np.cross(tang,u));theta=np.linspace(0,2*np.pi,sides+1)
    rad=np.broadcast_to(radius,(len(p),));verts=[];uv=[];faces=[]
    dist=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
    for i in range(len(p)):
        for j,t in enumerate(theta):verts.append(p[i]+rad[i]*(u[i]*np.cos(t)+v[i]*np.sin(t)));uv.append([j/sides,dist[i]*5])
    for i in range(len(p)-1):
        for j in range(sides):
            a=i*(sides+1)+j;b=a+sides+1;faces.extend([(a,b,a+1),(a+1,b,b+1)])
    # Cap ends to avoid open silhouettes; normals smooth at caps deliberately.
    if not closed:
        for end,rev in [(0,True),(len(p)-1,False)]:
            c=len(verts);verts.append(p[end]);uv.append([.5,.5]);base=end*(sides+1)
            for j in range(sides):faces.append((c,base+j+1,base+j) if rev else (c,base+j,base+j+1))
    return Geo(verts,faces,uv)

def ellipse(rx,ry,z=0,center=(0,0,0),start=0,end=2*np.pi,n=80):
    t=np.linspace(start,end,n);return np.column_stack([rx*np.cos(t),ry*np.sin(t),np.full(n,z)])+center

def rounded_rect(w,h,r,z=0,n=8):
    p=[]
    for (cx,cy),ang in [((w/2-r,h/2-r),0),((-w/2+r,h/2-r),90),((-w/2+r,-h/2+r),180),((w/2-r,-h/2+r),270)]:
        for t in np.linspace(ang,ang+90,n,endpoint=False)*np.pi/180:p.append([cx+r*np.cos(t),cy+r*np.sin(t),z])
    return np.array(p)

def extrude(poly,depth=.01,center=(0,0,0)):
    p=np.array(poly,float)
    if p.shape[1]==3:p=p[:,:2]
    # Ear clipping handles concave hearts, stars and crescents without dependencies.
    area=np.sum(p[:,0]*np.roll(p[:,1],-1)-np.roll(p[:,0],-1)*p[:,1]);p=p if area>0 else p[::-1]
    ids=list(range(len(p)));tris=[]
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    guard=0
    while len(ids)>3:
        found=False
        for k,b in enumerate(ids):
            a=ids[k-1];c=ids[(k+1)%len(ids)]
            if cross(p[a],p[b],p[c])<=1e-12:continue
            inside=False
            for q in ids:
                if q in (a,b,c):continue
                if min(cross(p[a],p[b],p[q]),cross(p[b],p[c],p[q]),cross(p[c],p[a],p[q]))>=-1e-12:inside=True;break
            if not inside:tris.append((a,b,c));ids.pop(k);found=True;break
        guard+=1
        if not found or guard>len(p)*2:raise ValueError('Non-simple polygon in extrusion')
    tris.append(tuple(ids));n=len(p);v=np.vstack([np.c_[p,np.full(n,depth/2)],np.c_[p,np.full(n,-depth/2)]])
    f=list(tris)+[(c+n,b+n,a+n) for a,b,c in tris]
    for i in range(n):j=(i+1)%n;f +=[(i,i+n,j),(j,i+n,j+n)]
    return Geo(v+center,f,np.tile((p-p.min(0))/np.maximum(np.ptp(p,axis=0),1e-8),(2,1)))

def slab(w,h,d=.015,r=.015,center=(0,0,0)):
    return extrude(rounded_rect(w,h,min(r,w*.45,h*.45),n=5),d,center)

def star(r=.05,r2=None,points=8,phase=np.pi/2):
    r2=r*.42 if r2 is None else r2;t=np.arange(points*2)*np.pi/points+phase;rr=np.where(np.arange(len(t))%2==0,r,r2);return np.c_[rr*np.cos(t),rr*np.sin(t)]

def heart(r=.05,n=52):
    t=np.linspace(0,2*np.pi,n,endpoint=False);x=16*np.sin(t)**3;y=13*np.cos(t)-5*np.cos(2*t)-2*np.cos(3*t)-np.cos(4*t);return np.c_[x,y]*r/16

def crescent(r=.06):
    # Crescent with a clean tip-to-tip polygon (inner circle clipped at intersections).
    d=.036*r/.06;ri=.052*r/.06;a=(r*r-ri*ri+d*d)/(2*d);h=np.sqrt(max(0,r*r-a*a));th=np.arctan2(h,a);thi=np.arctan2(h,a-d)
    outer=np.c_[r*np.cos(np.linspace(th,2*np.pi-th,48)),r*np.sin(np.linspace(th,2*np.pi-th,48))]
    inner=np.c_[d+ri*np.cos(np.linspace(-thi,thi,40)),ri*np.sin(np.linspace(-thi,thi,40))]
    # inner must follow the LEFT arc of the inner circle from lower to upper tip
    inner=np.c_[d+ri*np.cos(np.linspace(-thi,-2*np.pi+thi,40)),ri*np.sin(np.linspace(-thi,-2*np.pi+thi,40))]
    return np.vstack([outer,inner[1:-1]])

def chain(points,r=.006,link=.020,steps=80):
    # Interlocking ellipse links, alternating their plane around the tangent.
    p=np.asarray(points);d=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))];count=max(2,int(d[-1]/link));out=[]
    for i,s in enumerate(np.linspace(0,d[-1],count)):
        c=np.array([np.interp(s,d,p[:,k]) for k in range(3)]);ds=.001
        t=norm(np.array([np.interp(min(s+ds,d[-1]),d,p[:,k])-np.interp(max(s-ds,0),d,p[:,k]) for k in range(3)]));u=norm(np.cross(t,[0,0,1]) if abs(t[2])<.9 else np.cross(t,[0,1,0]));v=np.cross(t,u);ang=.15 if i%2==0 else 1.3;axis=np.cos(ang)*u+np.sin(ang)*v
        th=np.linspace(0,2*np.pi,14);loop=c+np.outer(np.cos(th)*link*.67,t)+np.outer(np.sin(th)*link*.43,axis);out.append(tube(loop,r,6,True))
    return out

def arc_neck(width=.32,depth=.14,drop=.11,z=.145):
    t=np.linspace(-1,1,70);return np.c_[t*width/2,-drop*(1-t*t),z-.055*t*t]

def join(geos):
    vv=[];ff=[];nn=[];uv=[];off=0
    for g in geos:vv.append(g.v);ff.append(g.f+off);nn.append(g.n);uv.append(g.uv);off+=len(g.v)
    return Geo(np.vstack(vv),np.vstack(ff),np.vstack(uv),np.vstack(nn))

BONES={
 'hips':([0,1.,0],None),'spine':([0,1.15,0],'hips'),'chest':([0,1.33,0],'spine'),'upperChest':([0,1.47,0],'chest'),
 'neck':([0,1.56,0],'upperChest'),'head':([0,1.80,0],'neck'),
 'leftShoulder':([.11,1.47,0],'upperChest'),'leftUpperArm':([.24,1.46,0],'leftShoulder'),'leftLowerArm':([.49,1.46,0],'leftUpperArm'),'leftHand':([.72,1.46,0],'leftLowerArm'),
 'rightShoulder':([-.11,1.47,0],'upperChest'),'rightUpperArm':([-.24,1.46,0],'rightShoulder'),'rightLowerArm':([-.49,1.46,0],'rightUpperArm'),'rightHand':([-.72,1.46,0],'rightLowerArm'),
 'leftUpperLeg':([.10,.98,0],'hips'),'leftLowerLeg':([.10,.54,0],'leftUpperLeg'),'leftFoot':([.10,.11,0],'leftLowerLeg'),'leftToes':([.10,.055,.16],'leftFoot'),
 'rightUpperLeg':([-.10,.98,0],'hips'),'rightLowerLeg':([-.10,.54,0],'rightUpperLeg'),'rightFoot':([-.10,.11,0],'rightLowerLeg'),'rightToes':([-.10,.055,.16],'rightFoot')}
BONE_NAMES=list(BONES)

def weights_for(v,region='torso'):
    v=np.asarray(v);j=np.zeros((len(v),4),np.uint16);w=np.zeros((len(v),4),float)
    if region in ('leftArm','rightArm'):
        side=region[:-3];x=np.abs(v[:,0]);t=np.clip((x-.44)/.10,0,1)
        j[:,0]=BONE_NAMES.index(side+'UpperArm');j[:,1]=BONE_NAMES.index(side+'LowerArm');w[:,0]=1-t;w[:,1]=t
        blend=np.clip((.30-x)/.10,0,1);w[:,:2]*=1-blend[:,None];j[:,2]=BONE_NAMES.index('upperChest');w[:,2]=blend
    elif region.endswith('Tail'):
        side=region[:-4];t=np.clip((1.03-v[:,1])/.32,0,.88);j[:,0]=0;j[:,1]=BONE_NAMES.index(side+'UpperLeg');w[:,0]=1-t;w[:,1]=t
    elif region in BONE_NAMES:j[:,0]=BONE_NAMES.index(region);w[:,0]=1
    else:
        knots=np.array([1.,1.15,1.33,1.47]);y=np.clip(v[:,1],knots[0],knots[-1]);i=np.clip(np.searchsorted(knots,y,side='right')-1,0,2);t=(y-knots[i])/(knots[i+1]-knots[i]);j[:,0]=i;j[:,1]=i+1;w[:,0]=1-t;w[:,1]=t
    return j,w

def add_rig(glb):
    ids={}
    for name,(p,parent) in BONES.items():
        pp=np.array(BONES[parent][0]) if parent else np.zeros(3)
        ids[name]=glb.node('wardrobe_'+name,parent=ids.get(parent),translation=(np.array(p)-pp).tolist(),extras={'humanoidBone':name})
    ib=[]
    for name in BONE_NAMES:
        m=np.eye(4);m[:3,3]=-np.array(BONES[name][0]);ib.append(m.T.reshape(-1))
    skin={'name':'Wardrobe reference T-pose rig','joints':[ids[n] for n in BONE_NAMES],'inverseBindMatrices':glb.accessor(ib,'MAT4'),'skeleton':ids['hips']}
    glb.d.setdefault('skins',[]).append(skin);return len(glb.d['skins'])-1,ids
