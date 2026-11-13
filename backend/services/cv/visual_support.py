# Cell 4 — small current-image patch checks instead of a second neural model.
"""Small grayscale patch comparisons for a recently observed stationary person.

This is positive continuity evidence, not a human classifier. A persistent false
initial detection can still survive it; bound the age and audit false positives.
"""
import cv2
import numpy as np


class VisualSupport:
    def __init__(self,max_age=2.,minimum_fraction=.25):
        self.max_age=max_age;self.minimum_fraction=minimum_fraction;self.templates={}
    def _crop(self,image,bounds):
        x1,y1,x2,y2=np.rint(bounds).astype(int)
        x1=max(0,x1);y1=max(0,y1);x2=min(image.shape[1],x2);y2=min(image.shape[0],y2)
        if x2-x1<12 or y2-y1<16:return None
        return cv2.resize(image[y1:y2,x1:x2],(64,96),interpolation=cv2.INTER_AREA)
    def remember(self,person,gray,t,update_template=True):
        if not update_template and person['id'] in self.templates:
            self.templates[person['id']]['time']=t
            return
        crop=self._crop(gray,person['xyxy'])
        if crop is not None:self.templates[person['id']]=dict(image=crop,time=t,xyxy=list(person['xyxy']))
        self.templates={k:p for k,p in self.templates.items() if t-p['time']<=self.max_age}
    def verify(self,person,gray,t,occupied=()):
        saved=self.templates.get(person['id'])
        if saved is None or t-saved['time']>self.max_age:return None
        # Use recent measured extent, never pixels on the rectangle's exterior.
        crop=self._crop(gray,saved['xyxy'])
        if crop is None:return None
        old=saved['image'];hits=eligible=0
        for y in [16,36,56,72]:
            for x in [12,28,44]:
                bounds=np.asarray(saved['xyxy']);size=bounds[2:]-bounds[:2]
                patch=bounds[:2]+np.asarray([x/64,y/96])*size
                extent=bounds[:2]+np.asarray([(x+12)/64,(y+12)/96])*size
                area=max(1.,np.prod(extent-patch))
                # A current person already owns these pixels; they cannot also
                # justify counting a second, unmatched identity.
                if any(np.maximum(0,np.minimum(extent,q['xyxy'][2:])-np.maximum(patch,q['xyxy'][:2])).prod()/area>.25 for q in occupied):continue
                a=old[y:y+12,x:x+12];b=crop[y:y+12,x:x+12]
                if a.std()<6:continue
                eligible+=1
                correlation=float(cv2.matchTemplate(b,a,cv2.TM_CCOEFF_NORMED)[0,0])
                difference=np.abs(a.astype(float)-b.astype(float)).mean()/255
                hits+=int(correlation>=.85 and difference<=.12)
        if hits>=3 and eligible>=3 and hits/eligible>=self.minimum_fraction:
            return saved['xyxy']
        return None
