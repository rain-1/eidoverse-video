#!/usr/bin/env python3
"""Regenerate all actual mesh/texture assets in this pack (NumPy + Pillow).
No image generation services, external downloads or proprietary software.
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
from collections import defaultdict
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from gltf_io import GLB,norm
from geometry import *

ROOT=Path(__file__).resolve().parents[1]
MEMBERS={
 'prime':{'name':'PRIME','role':'Leader / centre','color':'#F3EEE4','accent':'#D4AF5A','dark':'#232127','light':'#FFF9EA','metal':'#DCBB6C','emblem':'sunburst','fabric':'Champagne jacquard','silhouette':'Split longline coat'},
 'pixel':{'name':'PIXEL','role':'Playful / comedy','color':'#F28BB3','accent':'#FF5FA2','dark':'#211D29','light':'#F7F7FA','metal':'#C8CCD6','emblem':'pixel heart','fabric':'Gloss checker nylon','silhouette':'Cropped puffy bomber'},
 'nova': {'name':'NOVA','role':'Technical / precision','color':'#386FD9','accent':'#69D8FF','dark':'#151B29','light':'#D7F0FF','metal':'#B9C6D9','emblem':'network crystal','fabric':'Micro-grid technical weave','silhouette':'Angular short field jacket'},
 'echo': {'name':'ECHO','role':'Dramatic / mysterious','color':'#6E49B8','accent':'#B69AE8','dark':'#191522','light':'#DDD4EF','metal':'#A7A3B8','emblem':'crescent','fabric':'Violet star jacquard','silhouette':'Asymmetric split coat'},
 'sol':  {'name':'SOL','role':'Sporty / wild card','color':'#FF7A2F','accent':'#FFB14A','dark':'#1B1B20','light':'#F6F2EE','metal':'#BEBDC8','emblem':'spark','fabric':'Orange chevron ripstop','silhouette':'Padded racing jacket'},
}

def rgb(h):return np.array([int(h[i:i+2],16)/255 for i in (1,3,5)])
def linear(h):
    a=rgb(h);return np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4).tolist()

def texture_set(member):
    spec=MEMBERS[member];p=ROOT/'textures'/member;p.mkdir(parents=True,exist_ok=True);N=1024
    yy,xx=np.mgrid[:N,:N];u=xx/N;v=yy/N
    weave=.012*np.sin(2*np.pi*128*u)*np.sin(2*np.pi*128*v)
    if member=='prime':pat=.025*(np.cos(2*np.pi*8*(u+v))*np.cos(2*np.pi*8*(u-v)))
    elif member=='pixel':pat=.05*((np.floor(u*12)+np.floor(v*12))%2-.5)
    elif member=='nova':pat=.028*((xx%128<3)|(yy%128<3))+.009*np.sin(2*np.pi*48*u)
    elif member=='echo':pat=.035*np.cos(2*np.pi*9*(u+v))*np.cos(2*np.pi*9*(u-v))
    else:pat=.026*np.sin(2*np.pi*16*(u+abs(v-.5)))+.018*((xx%128<2)|(yy%128<2))
    color=rgb(spec['color']);a=np.clip(color[None,None,:]*(1+weave[:,:,None]+pat[:,:,None]),0,1)
    Image.fromarray(np.uint8(a*255)).save(p/'outer_albedo.png',optimize=True)
    height=weave*.10+pat*.018;dy,dx=np.gradient(height);nx=-dx*55;ny=-dy*55;n=norm(np.stack([nx,ny,np.ones_like(nx)],-1));Image.fromarray(np.uint8((n*.5+.5)*255)).save(p/'outer_normal.png',optimize=True)
    rough={'prime':.58,'pixel':.35,'nova':.45,'echo':.77,'sol':.48}[member];mr=np.empty((N,N,3),np.uint8);mr[:,:,0]=255;mr[:,:,1]=np.uint8(np.clip((rough+pat*.6)*255,0,255));mr[:,:,2]=0;Image.fromarray(mr).save(p/'outer_metallic_roughness.png',optimize=True)
    em=np.zeros_like(a);lines=((xx%256<2)&(yy%256<55))|((yy%256<2)&(xx%256<55))
    if member in ('nova','echo'):em[lines]=rgb(spec['accent'])*.28
    Image.fromarray(np.uint8(em*255)).save(p/'outer_emissive.png',optimize=True)
    # Standalone useful 1024px transparent insignia/name/decal atlas.
    im=Image.new('RGBA',(N,N));d=ImageDraw.Draw(im)
    fontpath=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    font=ImageFont.truetype(str(fontpath),86) if fontpath.exists() else ImageFont.load_default()
    small=ImageFont.truetype(str(fontpath),28) if fontpath.exists() else ImageFont.load_default()
    ac=spec['accent'];d.rounded_rectangle([40,40,984,220],radius=30,fill=spec['dark'],outline=ac,width=6);d.text((512,130),spec['name'],font=font,anchor='mm',fill=ac)
    d.text((512,265),'CONTEXT CREW / STAGE DIVISION',font=small,anchor='mm',fill=ac)
    for row in range(2):
        for col in range(4):
            cx=145+245*col;cy=410+240*row
            d.rounded_rectangle([cx-85,cy-80,cx+85,cy+80],radius=18,outline=ac,width=5)
            if member=='pixel':poly=heart(53)
            elif member=='echo':poly=crescent(56)
            elif member=='nova':poly=np.array([[0,62],[48,0],[0,-62],[-48,0]])
            else:poly=star(58,points=8 if member=='prime' else 5)
            d.polygon([(cx+x,cy-y) for x,y in poly],fill=ac)
    d.text((512,915),'SAME CLAUDE. DIFFERENT STAGE.',font=small,anchor='mm',fill=ac)
    im.save(p/'decal_atlas.png',optimize=True)
    patch=Image.new('RGB',(1024,256),spec['dark']);pd=ImageDraw.Draw(patch);pd.rounded_rectangle([6,6,1017,249],radius=28,outline=ac,width=9);pd.text((512,103),spec['name'],font=font,anchor='mm',fill=ac);pd.text((512,195),'CONTEXT CREW',font=small,anchor='mm',fill=spec['light']);patch.save(p/'back_patch.png',optimize=True)
    (p/'palette.json').write_text(json.dumps(spec,indent=2)+'\n')

def materials(glb,member,cloth=True):
    sp=MEMBERS[member];m={}
    def add(k,color,metal=0,rough=.5,**extras):
        mat={'name':f'{member}_{k}','pbrMetallicRoughness':{'baseColorFactor':linear(color)+[1],'metallicFactor':metal,'roughnessFactor':rough},'doubleSided':True,**extras}
        m[k]=glb.material(mat)
    add('dark',sp['dark'],rough=.7);add('color',sp['color'],rough=.4);add('accent',sp['accent'],rough=.33);add('light',sp['light'],rough=.6)
    add('metal',sp['metal'],metal=.86,rough=.28);add('rubber','#13151A',rough=.92)
    add('glow',sp['accent'],metal=.12,rough=.25,emissiveFactor=(np.array(linear(sp['accent']))*.45).tolist())
    add('lens',sp['accent'],metal=.22,rough=.18,alphaMode='BLEND');glb.d['materials'][m['lens']]['pbrMetallicRoughness']['baseColorFactor'][3]=.42
    if not cloth:return m
    tx=ROOT/'textures'/member
    al=glb.image(tx/'outer_albedo.png');no=glb.image(tx/'outer_normal.png');mr=glb.image(tx/'outer_metallic_roughness.png');em=glb.image(tx/'outer_emissive.png')
    mat={'name':f'{member}_outer_fabric','doubleSided':True,'pbrMetallicRoughness':{'baseColorFactor':[1,1,1,1],'baseColorTexture':{'index':al},'metallicFactor':1,'roughnessFactor':1,'metallicRoughnessTexture':{'index':mr}},'normalTexture':{'index':no,'scale':.3},'emissiveTexture':{'index':em},'emissiveFactor':[.3,.3,.3]}
    m['fabric']=glb.material(mat)
    patch=glb.image(tx/'back_patch.png')
    m['patch']=glb.material({'name':f'{member}_back_patch','doubleSided':True,'pbrMetallicRoughness':{'baseColorFactor':[1,1,1,1],'baseColorTexture':{'index':patch},'metallicFactor':0,'roughnessFactor':.60}})
    return m

class Assembly:
    def __init__(self,member,name,fit,bone):self.member=member;self.name=name;self.fit=fit;self.bone=bone;self.parts=[]
    def add(self,g,mat='metal',region=None):self.parts.append((g,mat,region));return self
    def chain(self,path,mat='metal',**kw):
        for g in chain(path,**kw):self.add(g,mat)
        return self
    def save(self,path,skinned=False):
        glb=GLB();mm=materials(glb,self.member,any(mat in ('fabric','patch') for _,mat,_ in self.parts));groups=defaultdict(list)
        for g,mat,reg in self.parts:groups[(mat,reg if skinned else None)].append(g)
        prim=[]
        for (mat,reg),gs in groups.items():
            g=join(gs);j,w=weights_for(g.v,reg or 'torso') if skinned else (None,None)
            prim.append(glb.primitive(g.v,g.f,g.n,g.uv,mm[mat],j,w))
        mesh=glb.mesh(self.name,prim)
        if skinned:skin,ids=add_rig(glb);node=glb.node(self.name,mesh,skin=skin)
        else:node=glb.node(self.name,mesh)
        meta={'member':self.member,'item':self.name,'anchorBone':self.bone,'fitSpace':self.fit,'units':'metres','front':'+Z','up':'+Y','authoredOn':'procedural fitting rig, NOT the source Claude mesh'}
        glb.d['asset']['extras']={'claudeWardrobe':meta};glb.d['nodes'][node]['extras']={'claudeWardrobe':meta}
        glb.save(path);return glb

def emblem(member,r=.045,depth=.008,center=(0,0,0)):
    if member=='pixel':p=heart(r)
    elif member=='echo':p=crescent(r)
    elif member=='nova':p=np.array([[0,r],[r*.67,0],[0,-r],[-r*.67,0]])
    elif member=='sol':p=star(r,r*.37,5,phase=.15)
    else:p=star(r,r*.53,12)
    return extrude(p,depth,center)

def paperclip(center=(0,0,0),scale=1):
    # Continuous open double return, actual tubular metal, not a decal.
    p=[]
    p+=[[.019,.052,0],[.019,-.039,0]]
    for t in np.linspace(0,-np.pi,20):p.append([-.005+.024*np.cos(t),-.039+.024*np.sin(t),0])
    p+=[[-.029,.041,0]]
    for t in np.linspace(np.pi,0,18):p.append([-.008+.021*np.cos(t),.041+.021*np.sin(t),0])
    p+=[[.013,-.027,0]]
    for t in np.linspace(0,-np.pi,16):p.append([-.004+.017*np.cos(t),-.027+.017*np.sin(t),0])
    p+=[[-.021,.031,0]]
    return tube(np.array(p)*scale+center,.0035*scale,8)

def headgear(member):
    a=Assembly(member,f'{member}_headpiece','head','head')
    if member=='prime':
        for r in (.475,.495):a.add(tube(ellipse(r,r*.92,-.115,start=.10,end=np.pi-.10,n=86),.009,10),'metal')
        for t in np.linspace(.17,np.pi-.17,9):
            pos=[.484*np.cos(t),.445*np.sin(t),-.105];a.add(emblem(member,.026,.009,pos),'metal');a.add(sphere(.009,np.array(pos)+[0,0,.012],12,6),'light')
        a.add(tube([[-.20,.01,.06],[-.225,-.04,.10],[-.20,-.11,.15],[-.075,-.11,.15]],.007,10),'metal');a.add(sphere([.020,.012,.012],[-.075,-.11,.15],18,8),'dark')
    elif member=='pixel':
        a.add(tube(ellipse(.467,.461,0,start=-.08,end=np.pi+.08,n=96),.024,14),'dark');a.add(tube(ellipse(.469,.463,.012,start=-.05,end=np.pi+.05,n=96),.013,12),'color')
        for s in (-1,1):
            a.add(slab(.090,.178,.116,.035,[s*.463,-.014,0]),'dark');a.add(slab(.072,.153,.125,.027,[s*.470,-.010,.012]),'color')
            a.add(emblem(member,.024,.007,[s*.47,.005,.079]),'light')
            ear=np.array([[s*.185,.414],[s*.257,.598],[s*.356,.401]])
            a.add(extrude(ear,.057,[0,0,.005]),'dark');small=ear.mean(0)+(ear-ear.mean(0))*.72;a.add(extrude(small,.060,[0,0,.011]),'accent')
    elif member=='nova':
        # Core-face visor: keeps the sunburst head silhouette free.
        a.add(slab(.293,.075,.017,.020,[0,.028,.145]),'dark');a.add(slab(.276,.058,.019,.016,[0,.029,.156]),'lens')
        a.add(tube([[-.134,.055,.166],[0,.062,.168],[.134,.055,.166]],.004,8),'glow')
        for s in (-1,1):
            a.add(tube([[s*.14,.03,.15],[s*.198,.026,.08],[s*.20,-.006,-.02]],.012,10),'dark');a.add(slab(.052,.095,.042,.010,[s*.207,.010,.041]),'color')
            for y in (-.014,.010,.034):a.add(box([.024,.006,.004],[s*.207,y,.064]),'glow')
    elif member=='echo':
        a.add(extrude(crescent(.229),.017,[.280,.233,-.104]),'metal')
        a.add(tube(ellipse(.489,.455,-.119,start=.68,end=2.1,n=72),.006,8),'accent')
        for s in (0,1,2):
            x=-.444-.013*s;a.chain([[x,.15,.03],[x-.012,.01-.033*s,.055],[x+.023,-.17-.028*s,.035]],link=.022,r=.0035)
        a.add(emblem(member,.043,.011,[-.421,-.225,.042]),'accent');a.add(extrude(star(.025,points=4),.011,[-.463,-.280,.043]),'metal')
    else:
        # Goggles sit above the small central face, rather than masking its eyes.
        a.add(tube(ellipse(.277,.119,0,n=90)[:,[0,2,1]]+[0,.168,0],.016,12),'dark')
        for s in (-1,1):
            a.add(slab(.167,.103,.043,.033,[s*.095,.166,.104]),'dark');a.add(slab(.147,.084,.048,.026,[s*.095,.166,.113]),'metal');a.add(slab(.128,.068,.050,.021,[s*.095,.166,.118]),'lens')
            a.add(box([.042,.010,.002],[s*.095,.173,.145]),'light')
        a.add(box([.043,.028,.055],[0,.167,.104]),'accent')
        for s in (-1,1):a.add(slab(.034,.065,.022,.008,[s*.197,.166,.102]),'color')
    return a

def chestkit(member):
    a=Assembly(member,f'{member}_chest_jewellery','chest','upperChest')
    # Local reference anchor at y=1.38; front clearance z=0.16.
    if member=='prime':
        a.chain(arc_neck(.31,drop=.102,z=.180)+[0,.090,0],link=.023,r=.0034)
        a.chain(arc_neck(.31,drop=.174,z=.183)+[0,.090,0],link=.023,r=.0034)
        a.add(emblem(member,.056,.012,[.126,.058,.193]),'metal');a.add(sphere(.012,[.126,.058,.207],16,8),'light')
        a.add(slab(.040,.155,.015,.009,[-.146,-.032,.175]),'metal')
    elif member=='pixel':
        a.chain(arc_neck(.31,drop=.113,z=.183)+[0,.086,0],link=.026,r=.004)
        a.add(emblem(member,.047,.013,[0,-.058,.197]),'accent')
        a.add(slab(.099,.050,.012,.012,[.13,.08,.181]),'light');a.add(emblem(member,.018,.008,[.13,.08,.191]),'color')
        for x,y in [(-.126,.079),(-.095,.046),(-.14,.017)]:a.add(sphere(.011,[x,y,.186],12,6),'metal')
    elif member=='nova':
        for s in (-1,1):
            a.add(tube([[s*.13,.12,.129],[s*.13,-.025,.186],[s*.17,-.15,.171]],.012,10),'dark')
            a.add(tube([[s*.136,.115,.145],[s*.136,-.025,.199],[s*.174,-.14,.185]],.0035,8),'glow')
        a.add(slab(.093,.071,.016,.010,[0,-.048,.198]),'dark');a.add(emblem(member,.035,.012,[0,-.048,.212]),'glow')
        a.add(tube([[-.13,.025,.196],[0,-.048,.208],[.13,.025,.196]],.006,8),'metal')
    elif member=='echo':
        a.add(tube(arc_neck(.30,drop=.029,z=.151)+[0,.112,0],.016,10),'dark')
        for drop in (.10,.158,.206):a.chain(arc_neck(.30,drop=drop,z=.190)+[0,.085,0],link=.023,r=.0027)
        a.add(emblem(member,.043,.009,[0,-.13,.200]),'metal')
        a.add(extrude(star(.024,points=4),.008,[.135,.069,.188]),'accent')
    else:
        a.add(tube([[-.15,.12,.16],[-.048,.005,.204],[.14,-.148,.165]],.015,10),'dark')
        a.add(tube([[-.148,.123,.17],[-.046,.005,.217],[.146,-.148,.179]],.005,8),'accent')
        a.chain(arc_neck(.32,drop=.070,z=.186)+[0,.081,0],link=.028,r=.004)
        a.add(emblem(member,.038,.010,[.095,.045,.202]),'color')
        a.add(slab(.07,.047,.023,.008,[-.015,-.025,.220]),'metal')
        a.add(box([.040,.020,.026],[-.015,-.025,.224]),'dark')
    return a

def beltkit(member):
    a=Assembly(member,f'{member}_belt_and_charms','hips','hips')
    # Elliptical belt with rectangular section, canonical width .43 / depth .30.
    theta=np.linspace(0,2*np.pi,80)
    for y in (-.023,.023):a.add(tube(np.c_[.205*np.cos(theta),np.full(len(theta),y),.147*np.sin(theta)],.008,10,True),'dark')
    for s in (-1,1):a.add(slab(.105,.051,.02,.010,[s*.117,0,.122]),'color')
    a.add(slab(.085,.060,.019,.010,[0,0,.151]),'metal');a.add(slab(.059,.036,.021,.005,[0,0,.154]),'dark');a.add(emblem(member,.021,.006,[0,0,.168]),'accent')
    a.chain([[.178,.0,.11],[.180,-.078,.153],[.151,-.147,.166]],link=.021,r=.0033)
    a.add(paperclip([.151,-.207,.168],.67),'metal')
    if member=='pixel':
        a.chain([[-.165,.0,.11],[-.204,-.09,.15],[-.205,-.143,.16]],link=.021,r=.0033)
        a.add(sphere([.052,.060,.032],[-.205,-.192,.163],22,12),'light')
        for s in (-1,1):
            a.add(sphere([.021,.026,.020],[-.205+s*.036,-.146,.163],16,8),'color');a.add(sphere([.006,.007,.004],[-.205+s*.019,-.184,.195],12,6),'dark')
        a.add(sphere([.009,.005,.004],[-.205,-.207,.195],12,6),'accent')
    elif member=='prime':
        a.chain([[-.15,0,.13],[-.11,-.12,.184],[.035,-.16,.19],[.152,0,.13]],link=.023,r=.0036)
    elif member=='nova':
        a.add(slab(.085,.127,.048,.015,[-.206,-.082,.114]),'dark');a.add(slab(.062,.084,.051,.010,[-.208,-.080,.117]),'color')
        for y in (-.105,-.080,-.055):a.add(box([.048,.005,.003],[-.208,y,.146]),'glow')
    elif member=='echo':
        a.chain([[-.17,0,.08],[-.26,-.12,.12],[-.19,-.22,.17]],link=.022,r=.0030);a.add(emblem(member,.032,.008,[-.19,-.24,.17]),'metal')
    else:
        a.add(slab(.067,.139,.013,.008,[-.203,-.101,.134]),'color')
        for k in range(3):a.add(box([.050,.011,.018],[-.203,-.061-k*.038,.138]),'dark')
    return a

def cuffkit(member,side):
    a=Assembly(member,f'{member}_{side}_wrist_cuff','wrist',side+'LowerArm')
    th=np.linspace(0,2*np.pi,50)
    for x in (-.036,.036):a.add(tube(np.c_[np.full(len(th),x),.058*np.cos(th),.058*np.sin(th)],.011,10,True),'dark')
    for x in (-.022,0,.022):a.add(tube(np.c_[np.full(len(th),x),.060*np.cos(th),.060*np.sin(th)],.008,8,True),'color')
    a.add(slab(.045,.034,.012,.008,[0,.023,.057]),'metal');a.add(emblem(member,.012,.009,[0,.023,.067]),'accent')
    if member=='nova':
        a.add(slab(.052,.042,.014,.006,[0,-.005,.064]),'dark');a.add(box([.035,.020,.016],[0,-.004,.065]),'glow')
    return a

def shoekit(member,side):
    a=Assembly(member,f'{member}_{side}_shoe_trim','foot',side+'Foot')
    # Bounds fit to each existing shoe; the sole stays within its original ground plane.
    a.add(slab(.159,.275,.025,.038).matrix(np.array([[1,0,0,0],[0,0,-1,-.055],[0,1,0,0],[0,0,0,1]])),'light')
    a.add(slab(.157,.259,.010,.037).matrix(np.array([[1,0,0,0],[0,0,-1,-.038],[0,1,0,0],[0,0,0,1]])),'color')
    a.add(slab(.072,.075,.015,.010,[0,.019,-.132]),'color')
    for k in range(4):
        z=.012+k*.024;y=.084-k*.005
        a.add(tube([[-.045,y,z],[.039,y+.007,z+.015]],.0037,7),'light')
        a.add(tube([[.045,y,z],[-.039,y+.007,z+.015]],.0037,7),'light')
    for s in (-1,1):
        a.add(tube([[s*.077,-.013,-.080],[s*.080,.005,.015],[s*.060,-.005,.109]],.006,8),'accent')
    if member in ('nova','sol'):
        for z in np.linspace(-.09,.09,6):a.add(box([.160,.009,.014],[0,-.061,z]),'rubber')
    return a

def loft_shell(levels,angles):
    v=[];uv=[];f=[]
    for i,(y,rx,rz) in enumerate(levels):
        for j,t in enumerate(angles):v.append([rx*np.sin(t),y,rz*np.cos(t)]);uv.append([j/(len(angles)-1)*2,i/(len(levels)-1)*3])
    for i in range(len(levels)-1):
        for j in range(len(angles)-1):
            a=i*len(angles)+j;b=a+len(angles);f.extend([(a,a+1,b),(a+1,b+1,b)])
    return Geo(v,f,uv)

def sleeve_geo(member,side):
    # Closed cross-section loft along the arm, with joint-friendly subdivisions.
    s=1 if side=='left' else -1;puff={'prime':1.,'pixel':1.24,'nova':1.03,'echo':1.,'sol':1.30}[member]
    xs=np.linspace(.228,.687,24);theta=np.linspace(0,2*np.pi,32);v=[];uv=[];f=[]
    for i,x in enumerate(xs):
        u=(x-xs[0])/(xs[-1]-xs[0]);r=(.105*(1-u)+.057*u)*puff*(1+.06*np.sin(np.pi*u))
        for j,t in enumerate(theta):v.append([s*x,1.46+r*np.cos(t),r*np.sin(t)]);uv.append([u*3,j/(len(theta)-1)*2])
    for i in range(len(xs)-1):
        for j in range(len(theta)-1):
            a=i*len(theta)+j;b=a+len(theta);f +=[(a,b,a+1),(a+1,b,b+1)] if s==1 else [(a,a+1,b),(a+1,b+1,b)]
    return Geo(v,f,uv)

def garment(member):
    a=Assembly(member,f'{member}_skinned_outerwear','skinned-reference-rig',None)
    bottom={'prime':1.035,'pixel':1.157,'nova':1.103,'echo':1.038,'sol':1.102}[member]
    extra={'prime':1,'pixel':1.08,'nova':1.01,'echo':1,'sol':1.14}[member]
    levels=[(bottom,.220*extra,.150),(bottom+.045,.219*extra,.150),(1.255,.219*extra,.154),(1.36,.237*extra,.153),(1.447,.255*extra,.134),(1.509,.192,.115)]
    angles=np.linspace(.36,2*np.pi-.36,76)
    a.add(loft_shell(levels,angles),'fabric','torso')
    # Contrast yoke, softly modelled lapels, actual piping and metallic closures.
    for s in (-1,1):
        outer=sleeve_geo(member,'left' if s==1 else 'right');a.add(outer,'fabric' if member in ('prime','pixel','sol') or s==1 else 'dark','leftArm' if s==1 else 'rightArm')
        # Collar-to-opening seam follows the shell, without floating down the torso.
        p=np.array([[s*rx*np.sin(.36),y,rz*np.cos(.36)+.005] for y,rx,rz in levels]);a.add(tube(p,.0055,8),'metal' if member=='prime' else 'accent','torso')
        poly=np.array([[s*.070,1.285],[s*.133,1.455],[s*.053,1.530],[s*.043,1.433]])
        a.add(extrude(poly,.009,[0,0,.148]),'light' if member in ('prime','pixel') else 'dark','torso')
        # Rib-knit cuff at the end of each sleeve.
        th=np.linspace(0,2*np.pi,44);rad=.065*({'pixel':1.08,'sol':1.12}.get(member,1))
        for k in range(4):a.add(tube(np.c_[np.full(len(th),s*(.662+.010*k)),1.46+rad*np.cos(th),rad*np.sin(th)],.005,7,True),'dark','leftArm' if s==1 else 'rightArm')
        # Three arm-band stripes on sporty members; small epaulette for the leader.
        if member in ('nova','sol'):
            for k in range(2):
                xx=s*(.33+.034*k);r=.099*({'sol':1.24}.get(member,1));a.add(tube(np.c_[np.full(len(th),xx),1.46+r*np.cos(th),r*np.sin(th)],.006,8,True),'accent','leftArm' if s==1 else 'rightArm')
        if member=='prime':
            a.add(slab(.110,.050,.011,.008,[s*.255,1.535,.063]),'metal','leftArm' if s==1 else 'rightArm')
            for k in range(4):a.add(tube([[s*(.217+k*.022),1.533,.065],[s*(.230+k*.024),1.478,.111]],.004,7),'metal','leftArm' if s==1 else 'rightArm')
        # Jacket front pockets, details are fully skinned with the jacket.
        if member in ('nova','sol'):
            a.add(slab(.079,.092,.014,.007,[s*.139,1.267,.140]),'dark','torso');a.add(box([.065,.012,.016],[s*.139,1.304,.147]),'accent','torso')
        elif member=='pixel':a.add(tube([[s*.12,1.230,.153],[s*.185,1.269,.117]],.005,8),'light','torso')
    # Hem follows the silhouette; stripe rows are geometry, not flat paint.
    for k in range(3):
        lev=(bottom+.012*k,levels[0][1]+.002,levels[0][2]+.001);th=np.linspace(.36,2*np.pi-.36,76);a.add(tube(np.c_[lev[1]*np.sin(th),np.full(len(th),lev[0]),lev[2]*np.cos(th)],.004,7),'metal' if member=='prime' else 'dark','torso')
    if member in ('prime','echo'):
        # Split, weighted skirt panels; no cloth/spring physics required.
        for s in (-1,1):
            if member=='echo' and s==-1:continue
            theta=np.linspace(.72 if s==1 else np.pi+.15,np.pi-.15 if s==1 else 2*np.pi-.72,28)
            end=.640 if member=='prime' else .727
            levels2=[]
            for y in np.linspace(bottom+.020,end,16):
                t=(bottom-y)/(bottom-end);levels2.append((y,.229+t*.037,.149+t*.016))
            g=loft_shell(levels2,theta);a.add(g,'fabric','leftTail' if s==1 else 'rightTail')
            for t in (theta[0],theta[-1]):
                p=[[rx*np.sin(t),y,rz*np.cos(t)] for y,rx,rz in levels2];a.add(tube(p,.004,8),'metal' if member=='prime' else 'accent','leftTail' if s==1 else 'rightTail')
    # UV-mapped curved back nameplate, sewn close to the jacket shell.
    vv=[];ff=[];uv=[]
    for row,y in enumerate(np.linspace(1.335,1.412,5)):
        for col,x in enumerate(np.linspace(-.148,.148,21)):
            vv.append([x,y,-.157*np.sqrt(1-(x/(.25*extra))**2)-.006]);uv.append([1-col/20,1-row/4])
    for i in range(4):
        for j in range(20):
            k=i*21+j;ff.extend([(k,k+21,k+1),(k+1,k+21,k+22)])
    a.add(Geo(vv,ff,uv),'patch','torso')
    # Signature sleeve/breast badge, raised geometry.
    a.add(emblem(member,.030,.008,[.137,1.382,.163]),'metal' if member=='prime' else 'accent','torso')
    return a

def reference_body(member):
    """Grey clearance mannequin for look development; NOT a shipped Claude model."""
    a=Assembly(member,f'{member}_reference_body','reference',None)
    # Inner tee, trousers, hands, shoes. They use the same canonical test rig.
    a.add(loft_shell([(1.00,.166,.098),(1.20,.173,.105),(1.40,.19,.105),(1.50,.132,.09)],np.linspace(0,2*np.pi,56)),'dark','torso')
    for side,s in [('left',1),('right',-1)]:
        for seg,(p0,p1,r) in enumerate([([s*.1,.98,0],[s*.1,.57,0],.091),([s*.1,.56,0],[s*.1,.145,0],.078)]):
            bone=side+('UpperLeg' if seg==0 else 'LowerLeg');a.add(tube(np.linspace(p0,p1,18),r,24),'dark',bone)
        a.add(sphere([.075,.068,.149],[s*.1,.075,.063],24,12),'dark',side+'Foot')
        a.add(sphere([.095,.050,.049],[s*.779,1.46,.004],22,10),'light',side+'Hand')
    # Opaque neutral head-clearance proxy; deliberately has no Claude face.
    a.add(sphere([.116,.129,.104],[0,1.80,.01],32,18),'light','head')
    # Sparse radial clearance spokes show why headgear is scaled generously.
    for t in np.linspace(0,2*np.pi,12,endpoint=False):
        p=np.array([[.145*np.cos(t),1.80+.145*np.sin(t),-.004],[.410*np.cos(t),1.80+.410*np.sin(t),-.008]])
        a.add(tube(p,.013,8),'dark','head')
    return a

def main():
    for m in MEMBERS:texture_set(m)
    all_assets=[]
    for member,spec in MEMBERS.items():
        items=[headgear(member),chestkit(member),beltkit(member)]
        items +=[cuffkit(member,s) for s in ('left','right')]+[shoekit(member,s) for s in ('left','right')]
        entries=[]
        for a in items:
            rel=Path('assets')/member/(a.name+'.glb');a.save(ROOT/rel)
            entries.append({'id':a.name,'asset':str(rel).replace('\\','/'),'bone':a.bone,'fitSpace':a.fit,'scale':[1,1,1],'offset':[0,0,0]});all_assets.append(str(rel))
        g=garment(member);g.save(ROOT/'garments'/f'{member}_outerwear.glb',True)
        # Reference-only assembled skinned look provides a concrete mesh preview.
        preview=reference_body(member);preview.parts+=g.parts
        centers={'head':np.array([0,1.80,0]),'chest':np.array([0,1.38,0]),'hips':np.array([0,1.,0]),'wrist':None,'foot':None}
        for a in items:
            c=centers[a.fit]
            if a.fit=='wrist':c=np.array([.670 if a.bone.startswith('left') else -.670,1.46,0])
            elif a.fit=='foot':c=np.array([.10 if a.bone.startswith('left') else -.10,.072,.045])
            for geo,mat,reg in a.parts:preview.parts.append((geo.moved(c),mat,a.bone))
        preview.save(ROOT/'previews'/f'{member}_reference_look.glb',True)
        man={'schemaVersion':1,'id':member,**spec,'baseVRM':'eidoverse/assets/vrms/claude_suit.vrm','hideOriginalMeshes':['jacket','tie'],'garment':f'garments/{member}_outerwear.glb','attachments':entries,'fit':{'bodyWidthPadding':1.08,'bodyDepthPadding':1.12,'sleevePadding':1.10,'headScale':[1,1,1],'headOffset':[0,0,0]},'notes':['Garment replaces the original jacket; original shirt, pants and shoes are retained and re-materialed.','Tail panels are skinned, not simulated cloth. Accessories are rigid bone children.','Per-avatar fitting and dance QA are still required.']}
        (ROOT/'manifests'/f'{member}.json').write_text(json.dumps(man,indent=2)+'\n')
        print(member,len(items),'accessories plus skinned outerwear')
    group={'schemaVersion':1,'name':'Claude & the Context Crew','stageOrder':['sol','nova','prime','pixel','echo'],'members':list(MEMBERS),'unit':'metre','front':'+Z','assets':all_assets,'referenceRig':{k:{'position':v[0],'parent':v[1]} for k,v in BONES.items()},'important':'Reference GLBs are NOT the actual Claude mesh. Run scripts/build_vrms.py against the source VRM to fit and bake the real avatars.'}
    (ROOT/'manifests'/'group.json').write_text(json.dumps(group,indent=2)+'\n')
    # Two real reusable shared accessory GLBs, in addition to the 35 member assets.
    a=Assembly('prime','shared_paperclip_charm','hips','hips');a.add(paperclip(),'metal');a.save(ROOT/'assets'/'shared'/'paperclip_charm.glb')
    a=Assembly('nova','shared_stage_microphone','head','head');a.add(tube([[-.2,.01,.06],[-.215,-.04,.10],[-.19,-.09,.145],[-.072,-.09,.153]],.006,10),'dark');a.add(sphere([.018,.011,.012],[-.072,-.09,.153],16,8),'rubber');a.save(ROOT/'assets'/'shared'/'stage_microphone.glb')
    print('Finished: 37 accessory GLBs, 5 skinned outerwear GLBs, 5 reference-only assembled GLBs.')

if __name__=='__main__':main()
