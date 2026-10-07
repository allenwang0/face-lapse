#!/usr/bin/env python3
import argparse, json, math, os, re, shutil
from datetime import datetime
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent.parent; WORK=ROOT/'work'; OUT=1080; EYE=250.; MID=np.array([540.,500.]); W=np.array([2.,2.,1.,1.])
PY=os.environ.get('PHOTO_LAPSE_PYTHON', 'python3')
def date_for(name):
 s=name.replace('\u202f',' '); m=re.search(r'(\d{1,2})-(\d{1,2})-(\d{2,4}).*?(\d{1,2})\.(\d{2})\s*([AP]M)',s,re.I)
 if m:
  mo,d,y,h,mi,ap=m.groups(); y=int(y)+(2000 if int(y)<100 else 0); h=int(h)%12+(12 if ap.upper()=='PM' else 0); return datetime(y,int(mo),int(d),h,int(mi))
 m=re.search(r'(20\d\d)[-_](\d\d)[-_](\d\d)',s)
 if m:return datetime(*map(int,m.groups()))
 return datetime.fromtimestamp((ROOT/name).stat().st_birthtime)
def fit(src,dst):
 sm=(src*W[:,None]).sum(0)/W.sum(); dm=(dst*W[:,None]).sum(0)/W.sum(); s=src-sm; d=dst-dm; den=(W[:,None]*s*s).sum(); a=(W[:,None]*s*d).sum()/den;b=(W*(s[:,0]*d[:,1]-s[:,1]*d[:,0])).sum()/den
 R=np.array([[a,-b],[b,a]]); t=dm-R@sm; pred=src@R.T+t; resid=np.sqrt((W[:,None]*(pred-dst)**2).sum()/W.sum());return R,t,resid
def inventory():
 fs=[p for p in ROOT.iterdir() if p.is_file() and p.suffix.lower() in ('.jpg','.jpeg','.png','.heic')]; rec=[]
 for p in fs:rec.append({'file':p.name,'t':date_for(p.name).isoformat()})
 rec.sort(key=lambda x:(x['t'],x['file']));(WORK/'inventory.json').write_text(json.dumps(rec,indent=2));print('inventory:',len(rec),'range:',rec[0]['t'][:10],rec[-1]['t'][:10])
def render():
 det={x['file']:x for x in json.loads((WORK/'detect.json').read_text())}; inv=json.loads((WORK/'inventory.json').read_text()); good=[]
 excluded_files=set();excluded_dates=set();exclude_path=ROOT/'exclude.txt'
 if exclude_path.exists():
  for raw in exclude_path.read_text().splitlines():
   line=raw.strip()
   if not line or line.startswith('#'):continue
   if line.startswith('date:'):excluded_dates.add(line[5:].strip())
   else:excluded_files.add(line)
 for z in inv:
  if z['file'] in excluded_files or z['t'][:10] in excluded_dates:continue
  d=det.get(z['file'],{});
  if 'error' in d or not all(k in d for k in ['eyeL','eyeR','nose','mouth']):continue
  pts=np.array([d[k] for k in ['eyeL','eyeR','nose','mouth']],float); ed=np.linalg.norm(pts[1]-pts[0]); u=(pts[1]-pts[0])/ed; no=np.dot(pts[2]-(pts[0]+pts[1])/2,u)/ed
  if abs(no)>=.12 or ed/d['boxW']<=.30 or d['boxW']/d['w']<=.10:continue
  smile=np.linalg.norm(np.array(d['mouthR'])-d['mouthL'])/ed;mopen=d['innerLips'][1]/ed;eopen=np.mean([d['eyeBoxL'][1]/d['eyeBoxL'][0],d['eyeBoxR'][1]/d['eyeBoxR'][0]])
  qim=ImageOps.exif_transpose(Image.open(ROOT/z['file'])).convert('L').resize((256,256),Image.Resampling.BILINEAR)
  qa=np.asarray(qim,dtype=float)/255.; sharp=float(np.mean(np.diff(qa,axis=0)**2)+np.mean(np.diff(qa,axis=1)**2)); exposure=float(np.mean(qa))
  q=dict(z,**d);q.update(pts=pts.tolist(),smile=smile,mopen=mopen,eopen=eopen,sharp=sharp,exposure=exposure);good.append(q)
 if len(good)<2:raise SystemExit('fewer than two frontal photos')
 norm=[]
 for q in good:
  p=np.array(q['pts']);v=p[1]-p[0];R=np.array([[v[0],v[1]],[-v[1],v[0]]])/np.dot(v,v);norm.append((p-(p[0]+p[1])/2)@R.T)
 templ=np.median(norm,0); target=templ*EYE+MID
 vals=np.array([[q[x] for x in ('smile','mopen','eopen','sharp','exposure')] for q in good]);med=np.median(vals,0);mad=np.maximum(1e-6,1.4826*np.median(abs(vals-med),0))
 for q in good:
  R,t,res=fit(np.array(q['pts']),target);q['score']=.5*res/EYE/.004+abs(q['smile']-med[0])/mad[0]+max(0,q['mopen']-med[1])/mad[1]+1.5*max(0,med[2]-q['eopen'])/mad[2]+.75*max(0,med[3]-q['sharp'])/mad[3]+.35*abs(q['exposure']-med[4])/mad[4]+(2 if q['w']<2000 else 0)+(4 if q['faces']>1 else 0)
 by={}
 for q in good:by.setdefault(q['t'][:10],[]).append(q)
 chosen=[min(v,key=lambda x:x['score']) for k,v in sorted(by.items())]
 if len(chosen)>180:
  # Keep all sparse early-year material, then water-fill the remaining quota evenly by year.
  groups={};
  for q in chosen:groups.setdefault(q['t'][:4],[]).append(q)
  quota={y:0 for y in groups}; left=180; active=set(groups)
  while active:
   share=math.ceil(left/len(active)); capped=[y for y in active if len(groups[y])<=share]
   if not capped:
    for y in sorted(active):quota[y]=left//len(active)
    for y in sorted(active)[:left%len(active)]:quota[y]+=1
    break
   for y in capped:quota[y]=len(groups[y]);left-=quota[y];active.remove(y)
  picked=[]
  for y,items in sorted(groups.items()):
   q=quota[y]
   if q>=len(items):picked.extend(items);continue
   days=np.array([datetime.fromisoformat(x['t']).timestamp() for x in items]);targets=np.linspace(days[0],days[-1],q);available=set(range(len(items)))
   for t in targets:
    j=min(available,key=lambda k:abs(days[k]-t));picked.append(items[j]);available.remove(j)
  chosen=sorted(picked,key=lambda x:x['t'])
 dst=WORK/'warp';dst.mkdir(parents=True,exist_ok=True); rows=[]
 for i,q in enumerate(chosen):
  im=ImageOps.exif_transpose(Image.open(ROOT/q['file'])).convert('RGB'); src=np.array(q['pts']);R,t,res=fit(src,target); invR=np.linalg.inv(R); c=-invR@t; data=(invR[0,0],invR[0,1],c[0],invR[1,0],invR[1,1],c[1]); out=im.transform((OUT,OUT),Image.Transform.AFFINE,data,Image.Resampling.BICUBIC,fillcolor=tuple(np.asarray(im.resize((1,1)))[0,0]));out.save(dst/f'{i:04}.png')
  rows.append({k:q[k] for k in ['file','t','smile','mopen','eopen','sharp','exposure','score']}|{'resid':res,'scale':math.sqrt((R*R).sum()/2),'rot_deg':math.degrees(math.atan2(R[1,0],R[0,0])),'orig_w':q['w'],'faces':q['faces']})
 (WORK/'chosen.json').write_text(json.dumps({'target':target.tolist(),'frames':rows},indent=2));print('with face:',len(det)-sum('error'in x for x in det.values()),'frontal:',len(good),'days:',len(chosen))
def grade():
 wd=WORK/'warp';md=WORK/'mask';od=WORK/'graded';od.mkdir(exist_ok=True);fs=sorted(wd.glob('*.png')); skins=[];bgs=[]
 for p in fs:
  a=np.asarray(Image.open(p)).astype(float)/255; m=np.asarray(Image.open(md/p.name).resize((OUT,OUT),Image.Resampling.BILINEAR)).astype(float)/255; box=a[540:860,380:700];skins.append(np.median(box.reshape(-1,3),0));bgs.append(np.median(a[m<.1]) if np.any(m<.1) else .4)
 st=np.median(skins,0);bt=np.median(bgs)
 for p,sk,bg in zip(fs,skins,bgs):
  im=Image.open(p).convert('RGB');a=np.asarray(im).astype(float)/255;m=Image.open(md/p.name).resize((OUT,OUT),Image.Resampling.BILINEAR).filter(ImageFilter.MinFilter(5)).filter(ImageFilter.GaussianBlur(1.5));alpha=np.asarray(m).astype(float)[...,None]/255; gain=np.clip(st/np.maximum(sk,.01),.6,1.7);fg=np.clip(a**2.2*gain,0,1)**(1/2.2);blur=np.asarray(im.resize((270,270)).filter(ImageFilter.GaussianBlur(8)).resize((OUT,OUT),Image.Resampling.BICUBIC)).astype(float)/255;blur=np.clip(blur*np.clip(bt/max(bg,.01),.6,1.7),0,1);y=(blur*np.array([.2126,.7152,.0722])).sum(2)[...,None];blur=y+.65*(blur-y);o=np.clip((fg*alpha+blur*(1-alpha))*255,0,255).astype('uint8');Image.fromarray(o).save(od/p.name)
 print('grade skin target',st.tolist(),'background target',bt)
def compose():
 meta=json.loads((WORK/'chosen.json').read_text())['frames'];src=sorted((WORK/'graded').glob('*.png')); font='/System/Library/Fonts/Helvetica.ttc';fb=ImageFont.truetype(font,46,index=1);fr=ImageFont.truetype(font,26)
 for layout,size in [('square',(1080,1080)),('story',(1080,1920))]:
  od=WORK/('out_'+layout);od.mkdir(exist_ok=True)
  for i,p in enumerate(src):
   im=Image.open(p).convert('RGB');canvas=im if layout=='square' else Image.new('RGB',size,(20,20,20)); yoff=0 if layout=='square' else 300
   if layout=='story':canvas.paste(im,(0,yoff))
   d=ImageDraw.Draw(canvas,'RGBA'); yy=970 if layout=='square' else 1420; label=datetime.fromisoformat(meta[i]['t']).strftime('%b %-d, %Y');d.text((540,yy),label,font=fb,anchor='mm',fill='white');by=1022 if layout=='square' else 1478;d.rounded_rectangle((70,by,1010,by+8),4,fill=(255,255,255,80));x=70+940*i/max(1,len(src)-1);d.rounded_rectangle((70,by,x,by+8),4,fill='white');d.ellipse((x-11,by-7,x+11,by+15),fill='white');d.text((70,by+30),datetime.fromisoformat(meta[0]['t']).strftime('%b %-d, %Y'),font=fr,anchor='la',fill=(255,255,255,200));d.text((1010,by+30),datetime.fromisoformat(meta[-1]['t']).strftime('%b %-d, %Y'),font=fr,anchor='ra',fill=(255,255,255,200));canvas.save(od/f'{i:04}.jpg',quality=93)
  # Keep the finished videos exactly seven seconds (210 frames), with at least a one-second hold.
  for j in range(max(30,210-len(src))):shutil.copy2(od/f'{len(src)-1:04}.jpg',od/f'{len(src)+j:04}.jpg')
 # GIF uses 180 motion frames + 16 hold = 7.84 s at requested 40ms
 imgs=[Image.open(p).resize((480,480),Image.Resampling.LANCZOS) for p in sorted((WORK/'out_square').glob('*.jpg'))[:-30]];imgs += [imgs[-1]]*16;imgs[0].save(ROOT/'face_timelapse_square.gif',save_all=True,append_images=imgs[1:],duration=40,loop=0,optimize=True)
def main():
 a=argparse.ArgumentParser();a.add_argument('stage',choices=['inventory','render','grade','compose']);x=a.parse_args();globals()[x.stage]()
if __name__=='__main__':main()
