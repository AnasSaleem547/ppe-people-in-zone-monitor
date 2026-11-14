# Cell 4 — small current-image patch checks instead of a second neural model.
"""Small grayscale patch comparisons for a recently observed stationary person.

This is positive continuity evidence, not a human classifier. A persistent false
initial detection can still survive it; bound the age and audit false positives.
"""
import cv2
import numpy as np
from backend.core import config as cfg


class VisualSupport:
    def __init__(self,max_age=cfg.VIS_DEFAULT_MAX_AGE,minimum_fraction=cfg.VIS_DEFAULT_MINIMUM_FRACTION):
        self.max_age=max_age;self.minimum_fraction=minimum_fraction;self.templates={}
    def _crop(self,image,bounds):
        x1,y1,x2,y2=np.rint(bounds).astype(int)
        x1=max(0,x1);y1=max(0,y1);x2=min(image.shape[1],x2);y2=min(image.shape[0],y2)
        if x2-x1<cfg.VIS_MIN_CROP_WIDTH or y2-y1<cfg.VIS_MIN_CROP_HEIGHT:return None
        return cv2.resize(image[y1:y2,x1:x2],(cfg.VIS_TEMPLATE_WIDTH,cfg.VIS_TEMPLATE_HEIGHT),interpolation=cv2.INTER_AREA)
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
        for y in cfg.VIS_PATCH_ROWS:
            for x in cfg.VIS_PATCH_COLUMNS:
                bounds=np.asarray(saved['xyxy']);size=bounds[2:]-bounds[:2]
                patch=bounds[:2]+np.asarray([x/cfg.VIS_TEMPLATE_WIDTH,y/cfg.VIS_TEMPLATE_HEIGHT])*size
                extent=bounds[:2]+np.asarray([(x+cfg.VIS_PATCH_SIZE)/cfg.VIS_TEMPLATE_WIDTH,(y+cfg.VIS_PATCH_SIZE)/cfg.VIS_TEMPLATE_HEIGHT])*size
                area=max(cfg.VIS_MIN_AREA,np.prod(extent-patch))
                # A current person already owns these pixels; they cannot also
                # justify counting a second, unmatched identity.
                if any(np.maximum(0,np.minimum(extent,q['xyxy'][2:])-np.maximum(patch,q['xyxy'][:2])).prod()/area>cfg.VIS_MAX_OCCUPIED_FRACTION for q in occupied):continue
                a=old[y:y+cfg.VIS_PATCH_SIZE,x:x+cfg.VIS_PATCH_SIZE];b=crop[y:y+cfg.VIS_PATCH_SIZE,x:x+cfg.VIS_PATCH_SIZE]
                if a.std()<cfg.VIS_MIN_PATCH_STDDEV:continue
                eligible+=1
                correlation=float(cv2.matchTemplate(b,a,cv2.TM_CCOEFF_NORMED)[0,0])
                difference=np.abs(a.astype(float)-b.astype(float)).mean()/cfg.VIS_INTENSITY_MAX
                hits+=int(correlation>=cfg.VIS_MIN_CORRELATION and difference<=cfg.VIS_MAX_DIFFERENCE)
        if hits>=cfg.VIS_MIN_MATCHING_PATCHES and eligible>=cfg.VIS_MIN_ELIGIBLE_PATCHES and hits/eligible>=self.minimum_fraction:
            return saved['xyxy']
        return None
