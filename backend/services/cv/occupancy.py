# Cell 3 — separate observed people, uncertain concealment and real exits.
"""Separate observed occupancy from short, explicitly uncertain concealment.

No video-specific coordinates or person counts enter these rules. Retained
identities alone never count. An observed departure always overrides a hold.
"""
import numpy as np
from backend.core import config as cfg
from shapely.geometry import Point,Polygon,box


def rectangle_iou(a,b):
    a,b=np.asarray(a),np.asarray(b)
    inter=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
    return float(inter/max(cfg.OCC_MIN_AREA,np.maximum(0,a[2:]-a[:2]).prod()+np.maximum(0,b[2:]-b[:2]).prod()-inter))


def same_upper_extent(a,b):
    """Nested full/partial boxes can describe the same upper body.

    Unlike suppressing every overlap, require close upper centers and unequal
    heights. These are geometric clues, not pose estimates or proof of identity.
    """
    a,b=np.asarray(a),np.asarray(b);sa=a[2:]-a[:2];sb=b[2:]-b[:2]
    intersection=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
    return (intersection/max(cfg.OCC_MIN_AREA,min(sa.prod(),sb.prod()))>=cfg.OCC_UPPER_MIN_CONTAINMENT
            and abs((a[0]+a[2]-b[0]-b[2])/2)<=cfg.OCC_UPPER_MAX_CENTER_OFFSET*min(sa[0],sb[0])
            and abs(a[1]-b[1])<=cfg.OCC_UPPER_MAX_TOP_OFFSET*min(sa[1],sb[1])
            and max(sa[1],sb[1])>=cfg.OCC_UPPER_MIN_HEIGHT_RATIO*min(sa[1],sb[1]))


def replaces_old_extent(old,current):
    """Reject a second retained identity for a newly measured body fragment.

    This conservative geometric rule also requires aligned upper body edges.
    A larger foreground rectangle is an occluder, not a replacement fragment.
    Adjacent people can still be ambiguous without distinguishing appearance.
    """
    if rectangle_iou(old,current)>=cfg.OCC_REPLACEMENT_MIN_IOU:return True
    a,b=np.asarray(old),np.asarray(current)
    size_a=np.maximum(0,a[2:]-a[:2]);size_b=np.maximum(0,b[2:]-b[:2])
    intersection=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
    return (intersection/max(cfg.OCC_MIN_AREA,size_b.prod())>=cfg.OCC_REPLACEMENT_MIN_CONTAINMENT
            and abs(a[1]-b[1])<=cfg.OCC_REPLACEMENT_MAX_TOP_OFFSET*size_a[1]
            and size_b[1]<=cfg.OCC_REPLACEMENT_MAX_HEIGHT_RATIO*size_a[1] and size_b.prod()<=cfg.OCC_REPLACEMENT_MAX_AREA_RATIO*size_a.prod())


class Occupancy:
    def __init__(self,polygon,overlap=cfg.OCC_DEFAULT_OVERLAP,max_hidden_seconds=cfg.OCC_DEFAULT_MAX_HIDDEN_SECONDS,evidence_mode=cfg.OCC_DEFAULT_EVIDENCE_MODE,max_extent_seconds=cfg.OCC_DEFAULT_MAX_EXTENT_SECONDS,
                 membership_mode=None,anchor=None,boundary_margin_fraction=None,boundary_max_seconds=None):
        self.region=Polygon(polygon);self.overlap=overlap;self.evidence_mode=evidence_mode
        self.membership_mode=cfg.OCC_DEFAULT_MEMBERSHIP_MODE if membership_mode is None else membership_mode
        self.anchor=cfg.OCC_DEFAULT_ANCHOR if anchor is None else anchor
        self.boundary_margin_fraction=cfg.OCC_BOUNDARY_MARGIN_FRACTION if boundary_margin_fraction is None else boundary_margin_fraction
        self.boundary_max_seconds=cfg.OCC_BOUNDARY_MAX_SECONDS if boundary_max_seconds is None else boundary_max_seconds
        if self.membership_mode not in ('box_overlap','anchor'):raise ValueError('Unknown zone membership mode.')
        if self.anchor not in ('center','bottom_center'):raise ValueError('Unknown zone anchor.')
        if not np.isfinite(self.boundary_margin_fraction) or self.boundary_margin_fraction<0:raise ValueError('Boundary margin must be finite and nonnegative.')
        if not np.isfinite(self.boundary_max_seconds) or self.boundary_max_seconds<0:raise ValueError('Boundary duration must be finite and nonnegative.')
        self.max_extent_seconds=max_extent_seconds
        self.max_hidden_seconds=max_hidden_seconds;self.people={};self.previous=None
    def fraction(self,bounds):
        shape=box(*bounds)
        return self.region.intersection(shape).area/max(cfg.OCC_MIN_AREA,shape.area)
    def membership(self,bounds,t,previous=None,confirm=True):
        """Evaluate every measured, image-supported and estimated position alike.

        The signed distance is positive inside the polygon. The uncertainty
        width scales with the box's shorter side, not the whole image. A point
        in that band can only preserve an unexpired, established inside state.
        Estimated body positions never refresh the clear-inside timestamp.
        Box-overlap mode intentionally retains the legacy area decision.
        """
        a=np.asarray(bounds,float)
        point=Point((a[0]+a[2])/2,a[3] if self.anchor=='bottom_center' else (a[1]+a[3])/2)
        distance=self.region.boundary.distance(point)
        if not self.region.contains(point):distance=-distance
        margin=self.boundary_margin_fraction*max(0,min(a[2]-a[0],a[3]-a[1]))
        fraction=self.fraction(bounds)
        confirmed=previous.get('zone_confirmed_inside_at') if previous is not None else None
        data=dict(inside_fraction=fraction,zone_fraction=fraction,
                  zone_anchor=[point.x,point.y],zone_boundary_distance=distance,
                  zone_boundary_margin=margin,zone_uncertain=False)
        if self.membership_mode=='box_overlap':
            inside=fraction>=self.overlap
            reason='measured_box'
        elif abs(distance)<=margin:
            data['zone_uncertain']=True
            established=previous is not None and previous.get('inside',False) and confirmed is not None
            inside=established and t-confirmed<=self.boundary_max_seconds
            reason='boundary_uncertain' if inside else ('boundary_uncertain_expired' if established else 'boundary_uncertain_no_entry')
        else:
            inside=distance>0
            reason='measured_anchor'
        if not inside:confirmed=None
        elif confirm and not data['zone_uncertain']:confirmed=t
        data.update(inside=bool(inside),zone_reason=reason,zone_confirmed_inside_at=confirmed)
        return data
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
        shortened=(new_size[1]<size[1] and new_size[0]<=cfg.OCC_REFERENCE_MAX_WIDTH_RATIO*size[0]
                   and abs(delta[0])<=cfg.OCC_REFERENCE_MAX_CENTER_OFFSET*size[0] and abs(delta[1])<=cfg.OCC_REFERENCE_MAX_TOP_OFFSET*size[1]
                   and overlap/max(cfg.OCC_MIN_AREA,new_size.prod())>=cfg.OCC_REFERENCE_MIN_CONTAINMENT)
        if shortened:
            # Retain the full size even for tiny contractions. Otherwise many
            # small steps replace the body with a head. A measurement still
            # within the configured retained-height fraction AND measured inside refreshes time,
            # not size. Inferred membership must never renew its own evidence.
            membership=self.membership(b,t,previous,confirm=False)
            reliable=(new_size[1]>=cfg.OCC_REFERENCE_RELIABLE_HEIGHT_RATIO*size[1]
                      and membership['inside'] and not membership['zone_uncertain'])
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
                if any(rectangle_iou(old['xyxy'],q['xyxy'])>=cfg.OCC_RECONNECT_MIN_IOU for q in observations):continue
                for j,q in enumerate(occluders or []):
                    if j not in used and q.get('score',0)>=cfg.OCC_RECONNECT_MIN_CONFIDENCE and rectangle_iou(old['xyxy'],q['xyxy'])>=cfg.OCC_RECONNECT_MIN_IOU:
                        observations.append(dict(id=old['id'],xyxy=q['xyxy'],score=q['score']))
                        used.add(j);break
        for q in observations:
            p=dict(q)
            previous=self.people.get(p['id'])
            if previous is not None and 'blocker_seen' in previous:p['blocker_seen']=previous['blocker_seen']
            p.update(self.membership(p['xyxy'],t,previous))
            p.update(state=('possibly_hidden' if p['zone_uncertain'] else 'visible_inside') if p['inside'] else 'observed_outside',
                     last_seen=t,score_is_current=True)
            if self.evidence_mode:
                reference,seen,shortened=self.body_reference(previous,p['xyxy'],t)
                p.update(reference_xyxy=reference,reference_seen=seen)
                reference_membership=self.membership(reference,t,previous,confirm=False)
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
                if shortened and was_inside and not p['inside'] and not p['zone_uncertain'] and reference_membership['inside']:
                    if t-seen<=self.max_extent_seconds or covered:
                        p.update(inside=True,state='possibly_hidden',zone_reason='partial_detection',
                                 zone_xyxy=reference,zone_fraction=reference_membership['zone_fraction'],
                                 zone_anchor=reference_membership['zone_anchor'],
                                 zone_boundary_distance=reference_membership['zone_boundary_distance'],
                                 zone_boundary_margin=reference_membership['zone_boundary_margin'],
                                 zone_uncertain=reference_membership['zone_uncertain'],
                                 zone_confirmed_inside_at=reference_membership['zone_confirmed_inside_at'],
                                 detection_xyxy=list(p['xyxy']),detection_score=p['score'])
                    else:p['zone_reason']='body_reference_expired'
            self.people[p['id']]=p;observed.add(p['id']);out.append(p)
        for identifier,p in list(self.people.items()):
            if identifier in observed:continue
            if not p['inside']:continue
            if any(replaces_old_extent(p['xyxy'],q['xyxy']) for q in observations):
                del self.people[identifier]
                continue
            a=np.asarray(p.get('zone_xyxy',p['xyxy']));area=max(cfg.OCC_MIN_AREA,np.maximum(0,a[2:]-a[:2]).prod())
            # Ambiguous detections do not buy missing-person time. Recheck their
            # original clear-inside deadline even if cover evidence is present.
            if p.get('zone_uncertain',False):
                membership=self.membership(a,t,p,confirm=False)
                p.update({k:v for k,v in membership.items() if k!='inside_fraction'})
                if not p['inside']:continue
            p['score_is_current']=False
            blocked=False
            for q in (occluders if occluders is not None else observations):
                b=np.asarray(q['xyxy'])
                intersection=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
                # The proposed blocker extends towards the camera and covers a
                # meaningful part of this person's last observed rectangle.
                if intersection/area>=cfg.OCC_BLOCKER_MIN_OVERLAP and b[3]>=a[3] and np.maximum(0,b[2:]-b[:2]).prod()>=cfg.OCC_BLOCKER_MIN_AREA_RATIO*area:
                    blocked=True;break
            if blocked:p['blocker_seen']=t
            if verify_visible is not None:
                supported=verify_visible(p)
                if supported:
                    q=dict(p,state='image_supported',xyxy=list(supported))
                    q.update(self.membership(q['xyxy'],t,p))
                    q['zone_xyxy']=list(q['xyxy'])
                    if not q['zone_uncertain']:q['zone_reason']='image_support'
                    elif q['inside']:q['state']='possibly_hidden'
                    partial='zone_xyxy' in p and p.get('zone_reason') in ('partial_detection','partial_image_support')
                    reference_membership=self.membership(p.get('zone_xyxy',p['xyxy']),t,p,confirm=False)
                    if partial and not q['inside'] and not q['zone_uncertain'] and reference_membership['inside'] and t-p['reference_seen']<=self.max_extent_seconds:
                        # Matching pixels on a head fragment must not undo an
                        # unexpired body-position estimate. No time is renewed.
                        q.update(inside=p['inside'],zone_xyxy=list(p['zone_xyxy']),
                                 zone_fraction=p['zone_fraction'],zone_reason='partial_image_support',
                                 zone_anchor=reference_membership['zone_anchor'],
                                 zone_boundary_distance=reference_membership['zone_boundary_distance'],
                                 zone_boundary_margin=reference_membership['zone_boundary_margin'],
                                 zone_uncertain=reference_membership['zone_uncertain'],
                                 zone_confirmed_inside_at=reference_membership['zone_confirmed_inside_at'])
                    if q['inside'] or not partial:
                        q['occluded']=False
                        if not q['inside']:q['long_hold']=False
                        self.people[identifier]=q
                        out.append(q);continue
            # Only positions well inside the polygon qualify for a long hold.
            shape=box(*a);margin=cfg.OCC_DEEP_INTERIOR_MARGIN*min(shape.bounds[2]-shape.bounds[0],shape.bounds[3]-shape.bounds[1])
            deep_inside=self.region.contains(shape) and self.region.boundary.distance(shape)>=margin
            # Evaluate object-cover evidence BEFORE the deep-interior gate. That
            # gate limits long retention; it must not suppress short supported
            # concealment near a polygon edge. Reuse the configured short
            # blocker memory instead of adding an unconditional missing grace.
            covered=self.evidence_mode and cover_check is not None and cover_check(dict(p,xyxy=a.tolist()))
            if covered:p['blocker_seen']=t
            if covered and deep_inside:
                p['long_hold']=True
                out.append(dict(p,state='possibly_hidden',zone_reason='boundary_uncertain' if p.get('zone_uncertain',False) else 'cover_evidence'));continue
            p['long_hold']=False
            if t-p['last_seen']>self.max_hidden_seconds:continue
            if blocked or covered or p.get('occluded',False) or t-p.get('blocker_seen',cfg.OCC_NEVER_SEEN_TIME)<=cfg.OCC_BLOCKER_MEMORY_SECONDS:
                p['occluded']=True
                out.append(dict(p,state='possibly_hidden',zone_reason='boundary_uncertain' if p.get('zone_uncertain',False) else ('cover_evidence' if covered else 'recent_blocker')))
        self.people={k:p for k,p in self.people.items() if p.get('long_hold',False) or t-p['last_seen']<=max(cfg.OCC_MIN_IDENTITY_RETENTION_SECONDS,self.max_hidden_seconds)}
        return out
