# Cell 3 — separate observed people, uncertain concealment and real exits.
"""Separate observed occupancy from short, explicitly uncertain concealment.

No video-specific coordinates or person counts enter these rules. Retained
identities alone never count. An observed departure always overrides a hold.
"""
import numpy as np
from shapely.geometry import Polygon,box


def rectangle_iou(a,b):
    a,b=np.asarray(a),np.asarray(b)
    inter=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
    return float(inter/max(1.,np.maximum(0,a[2:]-a[:2]).prod()+np.maximum(0,b[2:]-b[:2]).prod()-inter))


def same_upper_extent(a,b):
    """Nested full/partial boxes can describe the same upper body.

    Unlike suppressing every overlap, require close upper centers and unequal
    heights. These are geometric clues, not pose estimates or proof of identity.
    """
    a,b=np.asarray(a),np.asarray(b);sa=a[2:]-a[:2];sb=b[2:]-b[:2]
    intersection=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
    return (intersection/max(1.,min(sa.prod(),sb.prod()))>=.75
            and abs((a[0]+a[2]-b[0]-b[2])/2)<=.25*min(sa[0],sb[0])
            and abs(a[1]-b[1])<=.08*min(sa[1],sb[1])
            and max(sa[1],sb[1])>=1.2*min(sa[1],sb[1]))


def replaces_old_extent(old,current):
    """Reject a second retained identity for a newly measured body fragment.

    This conservative geometric rule also requires aligned upper body edges.
    A larger foreground rectangle is an occluder, not a replacement fragment.
    Adjacent people can still be ambiguous without distinguishing appearance.
    """
    if rectangle_iou(old,current)>=.7:return True
    a,b=np.asarray(old),np.asarray(current)
    size_a=np.maximum(0,a[2:]-a[:2]);size_b=np.maximum(0,b[2:]-b[:2])
    intersection=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
    return (intersection/max(1.,size_b.prod())>=.65
            and abs(a[1]-b[1])<=.2*size_a[1]
            and size_b[1]<=1.2*size_a[1] and size_b.prod()<=1.2*size_a.prod())


class Occupancy:
    def __init__(self,polygon,overlap=.7,max_hidden_seconds=1.5,evidence_mode=False,max_extent_seconds=2.):
        self.region=Polygon(polygon);self.overlap=overlap;self.evidence_mode=evidence_mode
        self.max_extent_seconds=max_extent_seconds
        self.max_hidden_seconds=max_hidden_seconds;self.people={};self.previous=None
    def fraction(self,bounds):
        shape=box(*bounds)
        return self.region.intersection(shape).area/max(1.,shape.area)
    def body_reference(self,previous,current,t):
        """Keep body size when the same upper position gets a shorter box.

        This is a geometric estimate, not a pose model. Translating the old box
        with the measured upper centre still allows a measured outward move.
        Substantial/outside fragments cannot renew the reference's time.
        """
        if previous is None:return list(current),t,False
        a=np.asarray(previous.get('reference_xyxy',previous['xyxy']),float)
        b=np.asarray(current,float);size=a[2:]-a[:2];new_size=b[2:]-b[:2]
        delta=np.array([(b[0]+b[2]-a[0]-a[2])/2,b[1]-a[1]])
        overlap=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
        shortened=(new_size[1]<size[1] and new_size[0]<=1.2*size[0]
                   and abs(delta[0])<=.5*size[0] and abs(delta[1])<=.2*size[1]
                   and overlap/max(1.,new_size.prod())>=.75)
        if shortened:
            # Retain the full size even for tiny contractions. Otherwise many
            # small steps replace the body with a head. A measurement still
            # within 5% of that retained size AND measured inside refreshes time,
            # not size. Inferred membership must never renew its own evidence.
            reliable=new_size[1]>=.95*size[1] and self.fraction(b)>=self.overlap
            seen=t if reliable else previous.get('reference_seen',previous['last_seen'])
            return (a+np.tile(delta,2)).tolist(),seen,True
        return list(current),t,False
    def step(self,t,observations,verify_visible=None,occluders=None,cover_check=None):
        if self.previous is not None and t<=self.previous:raise ValueError('Timestamps must increase.')
        self.previous=t;out=[];observed=set()
        if self.evidence_mode:
            # ByteTrack waits for a second detection when creating a new ID.
            # A strong returning box can immediately reconnect a retained person,
            # instead of creating a one-frame count gap at the reveal.
            observations=list(observations);used=set()
            for old in self.people.values():
                if not old.get('long_hold',False):continue
                if any(rectangle_iou(old['xyxy'],q['xyxy'])>=.7 for q in observations):continue
                for j,q in enumerate(occluders or []):
                    if j not in used and q.get('score',0)>=.6 and rectangle_iou(old['xyxy'],q['xyxy'])>=.7:
                        observations.append(dict(id=old['id'],xyxy=q['xyxy'],score=q['score']))
                        used.add(j);break
        for q in observations:
            p=dict(q)
            previous=self.people.get(p['id'])
            if previous is not None and 'blocker_seen' in previous:p['blocker_seen']=previous['blocker_seen']
            fraction=self.fraction(p['xyxy'])
            p.update(inside=fraction>=self.overlap,inside_fraction=fraction,
                     state='visible_inside' if fraction>=self.overlap else 'observed_outside',last_seen=t,
                     score_is_current=True,zone_reason='measured_box',zone_fraction=fraction)
            if self.evidence_mode:
                reference,seen,shortened=self.body_reference(previous,p['xyxy'],t)
                p.update(reference_xyxy=reference,reference_seen=seen)
                reference_fraction=self.fraction(reference)
                # Record cover even while the person is still detected. The
                # last partial detection can precede a missing frame on which
                # the motion/image check flickers. Evaluate once per person.
                covered=(cover_check is not None and cover_check(dict(p,xyxy=reference)))
                if covered:p['blocker_seen']=t
                # A shrinking body fragment is not evidence that the body crossed
                # outside. Keep the measured box/score separate from inferred
                # membership, and never count inferred membership as observed.
                # Estimates preserve established membership; they cannot create
                # a new entry for someone whose measured boxes stayed outside.
                was_inside=previous is not None and previous.get('inside',False)
                if shortened and was_inside and not p['inside'] and reference_fraction>=self.overlap:
                    if t-seen<=self.max_extent_seconds or covered:
                        p.update(inside=True,state='possibly_hidden',zone_reason='partial_detection',
                                 zone_xyxy=reference,zone_fraction=reference_fraction,
                                 detection_xyxy=list(p['xyxy']),detection_score=p['score'])
                    else:p['zone_reason']='body_reference_expired'
            self.people[p['id']]=p;observed.add(p['id']);out.append(p)
        for identifier,p in list(self.people.items()):
            if identifier in observed:continue
            if not p['inside']:continue
            if any(replaces_old_extent(p['xyxy'],q['xyxy']) for q in observations):
                del self.people[identifier]
                continue
            a=np.asarray(p.get('zone_xyxy',p['xyxy']));area=max(1.,np.maximum(0,a[2:]-a[:2]).prod())
            p['score_is_current']=False
            blocked=False
            for q in (occluders if occluders is not None else observations):
                b=np.asarray(q['xyxy'])
                intersection=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
                # The proposed blocker extends towards the camera and covers a
                # meaningful part of this person's last observed rectangle.
                if intersection/area>=.35 and b[3]>=a[3] and np.maximum(0,b[2:]-b[:2]).prod()>=1.2*area:
                    blocked=True;break
            if blocked:p['blocker_seen']=t
            if verify_visible is not None:
                supported=verify_visible(p)
                if supported:
                    q=dict(p,state='image_supported',xyxy=list(supported))
                    q['inside_fraction']=self.fraction(q['xyxy']);q['inside']=q['inside_fraction']>=self.overlap
                    q.update(zone_fraction=q['inside_fraction'],zone_xyxy=list(q['xyxy']),zone_reason='image_support')
                    partial='zone_xyxy' in p and p.get('zone_reason')=='partial_detection'
                    if partial and not q['inside'] and t-p['reference_seen']<=self.max_extent_seconds:
                        # Matching pixels on a head fragment must not undo an
                        # unexpired body-position estimate. No time is renewed.
                        q.update(inside=p['inside'],zone_xyxy=list(p['zone_xyxy']),
                                 zone_fraction=p['zone_fraction'],zone_reason='partial_image_support')
                    if q['inside'] or not partial:
                        p['occluded']=False
                        out.append(q);continue
            # Only positions well inside the polygon qualify for a long hold.
            shape=box(*a);margin=.1*min(shape.bounds[2]-shape.bounds[0],shape.bounds[3]-shape.bounds[1])
            deep_inside=self.region.contains(shape) and self.region.boundary.distance(shape)>=margin
            # Evaluate object-cover evidence BEFORE the deep-interior gate. That
            # gate limits long retention; it must not suppress short supported
            # concealment near a polygon edge. Reuse the existing half-second
            # blocker memory instead of adding an unconditional missing grace.
            covered=self.evidence_mode and cover_check is not None and cover_check(dict(p,xyxy=a.tolist()))
            if covered:p['blocker_seen']=t
            if covered and deep_inside:
                p['long_hold']=True
                out.append(dict(p,state='possibly_hidden',zone_reason='cover_evidence'));continue
            p['long_hold']=False
            if t-p['last_seen']>self.max_hidden_seconds:continue
            if blocked or covered or p.get('occluded',False) or t-p.get('blocker_seen',-1e9)<=.5:
                p['occluded']=True
                out.append(dict(p,state='possibly_hidden',zone_reason='cover_evidence' if covered else 'recent_blocker'))
        self.people={k:p for k,p in self.people.items() if p.get('long_hold',False) or t-p['last_seen']<=max(2.,self.max_hidden_seconds)}
        return out
