# Cell 8 — reconnect nearby returns using small colour summaries, without a second model.
"""Conservative, lightweight colour-and-position linking across tracker IDs.

No neural model. Similar clothes are not proof of identity; ambiguous candidates
remain separate. This helps short fixed-camera returns, not arbitrary re-ID.
"""
from backend.core import config as cfg
import cv2
import numpy as np

class IdentityLinker:
 def __init__(self,max_age=cfg.IDENTITY_MAX_AGE_SECONDS,max_distance=cfg.IDENTITY_MAX_APPEARANCE_DISTANCE,minimum_margin=cfg.IDENTITY_MINIMUM_MARGIN):
  self.max_age=max_age;self.max_distance=max_distance;self.minimum_margin=minimum_margin
  self.bounds=None;self.aliases={};self.alias_time={};self.people={};self.next_id=1;self.events=[]
 def feature(self,image,bounds):
  a=np.asarray(bounds,float).copy();size=a[2:]-a[:2]
  # A detector crop can show only trousers or only a torso. Read surrounding
  # ORIGINAL camera pixels for colour context; no additional detector call.
  if self.bounds is not None:
   border=np.asarray(self.bounds);tolerance=np.maximum(cfg.IDENTITY_EDGE_TOLERANCE_PIXELS,cfg.IDENTITY_EDGE_TOLERANCE_FRACTION*(border[2:]-border[:2]))
   for axis in [0,1]:
    if abs(a[axis]-border[axis])<=tolerance[axis] and border[axis]>0:a[axis]-=cfg.IDENTITY_CROP_CONTEXT_EXPANSION*size[axis]
    if abs(a[axis+2]-border[axis+2])<=tolerance[axis] and border[axis+2]<image.shape[1-axis]:a[axis+2]+=cfg.IDENTITY_CROP_CONTEXT_EXPANSION*size[axis]
   size=a[2:]-a[:2]
  x,y=np.maximum(0,np.rint(a[:2]+size*cfg.IDENTITY_FEATURE_INSET)).astype(int)
  z,w=np.minimum([image.shape[1],image.shape[0]],np.rint(a[2:]-size*cfg.IDENTITY_FEATURE_INSET)).astype(int)
  if z-x<cfg.IDENTITY_MIN_CROP_SIDE or w-y<cfg.IDENTITY_MIN_CROP_SIDE:return None
  hsv=cv2.cvtColor(cv2.resize(image[y:w,x:z],cfg.IDENTITY_FEATURE_SIZE),cv2.COLOR_BGR2HSV)
  hs=cv2.calcHist([hsv],[0,1],None,cfg.IDENTITY_HS_HISTOGRAM_BINS,cfg.IDENTITY_HS_HISTOGRAM_RANGES).ravel();v=cv2.calcHist([hsv],[2],None,cfg.IDENTITY_VALUE_HISTOGRAM_BINS,cfg.IDENTITY_VALUE_HISTOGRAM_RANGE).ravel()
  feature=np.r_[cfg.IDENTITY_HS_FEATURE_WEIGHT*hs/max(cfg.IDENTITY_HISTOGRAM_SUM_FLOOR,hs.sum()),cfg.IDENTITY_VALUE_FEATURE_WEIGHT*v/max(cfg.IDENTITY_HISTOGRAM_SUM_FLOOR,v.sum())]
  return np.sqrt(feature)
 def remember(self,t,tracks,image):
  for q in tracks:
   if q.get('state','visible_inside') not in ('visible_inside','observed_outside'):continue
   k=q['id'];old=self.people.setdefault(k,dict(features=[],parts=[],feature_time=cfg.IDENTITY_NEVER_SEEN_TIME))
   old.update(time=t,xyxy=list(q['xyxy']))
   if q['score']>=cfg.IDENTITY_REMEMBER_MIN_CONFIDENCE and (not old['features'] or t-old['feature_time']>=cfg.IDENTITY_FEATURE_INTERVAL_SECONDS):
    f=self.feature(image,q['xyxy'])
    if f is not None:
     old['features']=(old['features']+[f])[-cfg.IDENTITY_FEATURE_HISTORY_SIZE:];old['feature_time']=t
     a=np.asarray(q['xyxy'],float);height=a[3]-a[1];parts=[]
     for lo,hi in cfg.IDENTITY_BODY_PART_FRACTIONS:
      bounds=[a[0],a[1]+lo*height,a[2],a[1]+hi*height];part=self.feature(image,bounds)
      if part is not None:parts.append((bounds,part))
     old['parts']=(old['parts']+parts)[-cfg.IDENTITY_PART_HISTORY_SIZE:]
 def duplicate_extent(self,a,b):
  a,b=np.asarray(a),np.asarray(b);sa=a[2:]-a[:2];sb=b[2:]-b[:2]
  overlap=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
  iou=overlap/max(cfg.IDENTITY_MIN_AREA,sa.prod()+sb.prod()-overlap)
  return iou>=cfg.IDENTITY_DUPLICATE_MIN_IOU and abs(a[1]-b[1])<=cfg.IDENTITY_DUPLICATE_TOP_TOLERANCE*min(sa[1],sb[1]) and abs((a[0]+a[2]-b[0]-b[2])/2)<=cfg.IDENTITY_DUPLICATE_CENTER_TOLERANCE*min(sa[0],sb[0])
 def partial_crop_return(self,a,b,image):
  if self.bounds is None:return False
  border=np.asarray(self.bounds);a,b=np.asarray(a),np.asarray(b)
  tolerance=np.maximum(cfg.IDENTITY_EDGE_TOLERANCE_PIXELS,cfg.IDENTITY_EDGE_TOLERANCE_FRACTION*(border[2:]-border[:2]));shared=False
  for axis in [0,1]:
   if border[axis]>0 and abs(a[axis]-border[axis])<=tolerance[axis] and abs(b[axis]-border[axis])<=tolerance[axis]:shared=True
   if border[axis+2]<image.shape[1-axis] and abs(a[axis+2]-border[axis+2])<=tolerance[axis] and abs(b[axis+2]-border[axis+2])<=tolerance[axis]:shared=True
  intersection=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
  containment=intersection/max(cfg.IDENTITY_MIN_AREA,min(np.prod(a[2:]-a[:2]),np.prod(b[2:]-b[:2])))
  distance=np.linalg.norm((a[:2]+a[2:]-b[:2]-b[2:])/2)
  return shared and containment>=cfg.IDENTITY_PARTIAL_MIN_CONTAINMENT and distance<=cfg.IDENTITY_PARTIAL_MAX_DISTANCE_HEIGHTS*max(a[3]-a[1],b[3]-b[1])
 def update(self,t,observations,image,protected=()):
  self.people={k:p for k,p in self.people.items() if t-p['time']<=self.max_age or k in protected}
  self.aliases={k:v for k,v in self.aliases.items() if v in self.people and t-self.alias_time.get(k,t)<=self.max_age}
  self.alias_time={k:v for k,v in self.alias_time.items() if k in self.aliases}
  self.events=[]
  groups={}
  for q in observations:
   if q['id'] in self.aliases:groups.setdefault(self.aliases[q['id']],[]).append(q)
  for group in groups.values():
   group.sort(key=lambda q:-q['score'])
   for q in group[1:]:
    if not self.duplicate_extent(group[0]['xyxy'],q['xyxy']):
     self.aliases.pop(q['id'],None)
  used={self.aliases[q['id']] for q in observations if q['id'] in self.aliases};out={}
  for q in sorted(observations,key=lambda q:(q['id'] not in self.aliases,-q['score'])):
   raw=q['id'];stable=self.aliases.get(raw);self.alias_time[raw]=t
   if stable is None:
    f=self.feature(image,q['xyxy']);duplicates=set()
    if f is not None:
     for other in observations:
      if other['id']==raw or other['id'] not in self.aliases:continue
      if not self.duplicate_extent(q['xyxy'],other['xyxy']):continue
      g=self.feature(image,other['xyxy'])
      if g is not None and np.linalg.norm(f-g)/np.sqrt(2)<=cfg.IDENTITY_DUPLICATE_MAX_COLOR_DISTANCE:duplicates.add(self.aliases[other['id']])
    if len(duplicates)==1:
     stable=duplicates.pop();self.events.append(dict(seconds=t,tracker_id=raw,id=stable,reason='current_duplicate_extent_and_colour'))
    else:
     candidates=[];a=np.asarray(q['xyxy']);center=(a[:2]+a[2:])/2
     if f is not None:
      for k,p in self.people.items():
       if k in used or not p['features']:continue
       b=np.asarray(p['xyxy'])
       if np.prod(a[2:]-a[:2])>cfg.IDENTITY_EXPANSION_AREA_RATIO*np.prod(b[2:]-b[:2]) and a[3]-a[1]>cfg.IDENTITY_EXPANSION_HEIGHT_RATIO*(b[3]-b[1]):continue
       distance=np.linalg.norm(center-(b[:2]+b[2:])/2)
       if distance>cfg.IDENTITY_MAX_DISTANCE_HEIGHT_SUM*((a[3]-a[1])+(b[3]-b[1])):continue
       score=min(float(np.linalg.norm(f-g)/np.sqrt(2)) for g in p['features'])
       if a[3]-a[1]<=cfg.IDENTITY_PARTIAL_HEIGHT_RATIO*(b[3]-b[1]):
        for bounds,g in p.get('parts',[]):
         shared=max(0.,min(a[3],bounds[3])-max(a[1],bounds[1]))
         if shared>=cfg.IDENTITY_PART_MIN_VERTICAL_OVERLAP*min(a[3]-a[1],bounds[3]-bounds[1]):
          score=min(score,float(np.linalg.norm(f-g)/np.sqrt(2)))
       candidates.append((score,k,cfg.IDENTITY_PARTIAL_MAX_COLOR_DISTANCE if self.partial_crop_return(a,b,image) else self.max_distance))
     candidates.sort()
     if candidates and candidates[0][0]<=candidates[0][2] and (len(candidates)==1 or candidates[1][0]-candidates[0][0]>=self.minimum_margin):
      score,stable,limit=candidates[0];self.events.append(dict(seconds=t,tracker_id=raw,id=stable,appearance_distance=score,reason='partial_crop_return' if limit>self.max_distance else 'colour_and_nearby_return'))
     else:stable=self.next_id;self.next_id+=1
    self.aliases[raw]=stable
   used.add(stable)
   if stable not in out or q['score']>out[stable]['score']:out[stable]=dict(q,id=stable,tracker_id=raw)
  result=list(out.values());self.remember(t,result,image);return result
