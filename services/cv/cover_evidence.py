# Cell 6 — detect covering movement of any object without another model.
"""Cheap evidence of a covering moving object, regardless of object category.

Fixed-camera image changes are clues, not object recognition. Shadows and camera
shake can fool this check. A frozen image cannot establish physical occupancy.
"""
import cv2
import numpy as np

class CoverEvidence:
 def __init__(self):self.previous=None;self.components=[];self.saved={};self.rings={};self.image=None
 def update(self,image):
  # Work at half resolution to limit CPU and memory; no second neural model.
  self.image=cv2.resize(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),None,fx=.5,fy=.5)
  self.components=[];self.before=self.previous
  if self.previous is not None:
   delta=cv2.absdiff(self.image,self.previous)
   mask=(delta>25).astype(np.uint8)*255
   mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((7,7),np.uint8))
   n,labels,stats,_=cv2.connectedComponentsWithStats(mask)
   for x,y,w,h,area in stats[1:]:
    if area>=30:self.components.append([x,y,x+w,y+h])
  self.previous=self.image.copy()
 def covers(self,person):
  a=np.asarray(person['xyxy'],float)*.5;area=max(1.,np.prod(a[2:]-a[:2]))
  ring=self.rings.get(person['id'])
  if ring is not None:
   x,y,z,w,baseline,mask=ring;now=self.image[y:w,x:z]
   if mask.any() and np.abs(now.astype(float)-baseline.astype(float))[mask].mean()/255<=.08:
    self.saved.pop(person['id'],None);self.rings.pop(person['id'],None);return False
  saved=self.saved.get(person['id'])
  if saved is not None:
   x,y,z,w,old,baseline=saved;now=self.image[y:w,x:z]
   if now.shape==baseline.shape and np.abs(now.astype(float)-baseline.astype(float)).mean()/255<=.10:
    self.saved.pop(person['id'],None);return False
  for b in self.components:
   b=np.asarray(b);overlap=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()/area
   if overlap>=.35 and np.prod(b[2:]-b[:2])>=1.2*area and b[3]>=a[3]:
    # Store only the covered person's footprint, not a large background area.
    x,y,z,w=np.rint(a).astype(int);x=max(0,x);y=max(0,y);z=min(z,self.image.shape[1]);w=min(w,self.image.shape[0])
    patch=self.image[y:w,x:z]
    if patch.size and person['id'] not in self.rings:
     bx,by,bz,bw=np.rint(b).astype(int);mask=np.ones((bw-by,bz-bx),bool)
     ax,ay,az,aw=np.rint(a).astype(int)
     mask[max(0,ay-by):max(0,min(bw,aw)-by),max(0,ax-bx):max(0,min(bz,az)-bx)]=False
     self.rings[person['id']]=(bx,by,bz,bw,self.before[by:bw,bx:bz].copy(),mask)
    if patch.size:self.saved[person['id']]=(x,y,z,w,patch.copy(),self.before[y:w,x:z].copy() if saved is None else saved[5])
    return True
  saved=self.saved.get(person['id'])
  if saved is None:return False
  x,y,z,w,old,baseline=saved;current=self.image[y:w,x:z]
  if current.shape==old.shape and np.abs(current.astype(float)-old.astype(float)).mean()/255<=.10:return True
  self.saved.pop(person['id'],None);return False
 def prune(self,ids):
  self.saved={k:v for k,v in self.saved.items() if k in ids}
  self.rings={k:v for k,v in self.rings.items() if k in ids}
