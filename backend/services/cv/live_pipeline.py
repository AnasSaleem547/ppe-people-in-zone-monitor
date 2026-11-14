# Cell 9 — single YOLO detector, ByteTrack and explicit occupancy states.
"""Single-detector pipeline with measured, bounded occupancy uncertainty."""
import json,time,tempfile,math,hashlib
from pathlib import Path
from fractions import Fraction
from types import SimpleNamespace
import av,cv2,numpy as np
from backend.core import config as cfg
from ultralytics import YOLO
from ultralytics.engine.results import Boxes
from .tracker import ConfigurableBYTETracker
from ultralytics.trackers.basetrack import TrackState
from ultralytics.trackers.utils import matching
from .occupancy import Occupancy,rectangle_iou,same_upper_extent
from .visual_support import VisualSupport
from .cover_evidence import CoverEvidence
from .identity_link import IdentityLinker
from .annotation import render,FOOTER_HEIGHT as READABLE_FOOTER
from .media_utils import AnnotatedVideo,status_frame,bundle_run,Gate,validate_polygon,padded_crop


class Episode:
    def __init__(self,n,seconds):self.gate=Gate(n,seconds);self.n=n
    def step(self,t,estimated,observed):
        elapsed,alarm=self.gate.step(t,estimated)
        if alarm and observed<self.n:self.gate.fired=False;alarm=False
        return elapsed,alarm


def compatible_extent(a,b):
    sa=np.asarray(a)[2:]-np.asarray(a)[:2];sb=np.asarray(b)[2:]-np.asarray(b)[:2]
    return not (sb.prod()>cfg.TRACK_EXPANSION_AREA_RATIO*sa.prod() and sb[1]>cfg.TRACK_EXPANSION_HEIGHT_RATIO*sa[1]) or same_upper_extent(a,b)


def edge_expansion(a,b,bounds):
    if bounds is None:return False
    a,b=np.asarray(a),np.asarray(b);bounds=np.asarray(bounds)
    size=bounds[2:]-bounds[:2];tolerance=np.maximum(cfg.TRACK_EDGE_TOLERANCE_PIXELS,cfg.TRACK_EDGE_TOLERANCE_FRACTION*size)
    da=np.r_[a[:2]-bounds[:2],bounds[2:]-a[2:]]
    db=np.r_[b[:2]-bounds[:2],bounds[2:]-b[2:]]
    shared_edge=np.any((np.abs(da)<=np.tile(tolerance,2)) & (np.abs(db)<=np.tile(tolerance,2)))
    intersection=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
    containment=intersection/max(cfg.OCC_MIN_AREA,min(np.prod(a[2:]-a[:2]),np.prod(b[2:]-b[:2])))
    return shared_edge and containment>=cfg.TRACK_EDGE_MIN_CONTAINMENT


class ExtentTracker(ConfigurableBYTETracker):
    bounds=None
    def get_dists(self,tracks,detections):
        costs=matching.iou_distance(tracks,detections)
        overlaps=1.-costs.copy()
        active=[k for k,p in enumerate(tracks) if p.state==TrackState.Tracked]
        for i,a in enumerate(tracks):
            for j,b in enumerate(detections):
                if not compatible_extent(a.xyxy,b.xyxy) and not edge_expansion(a.xyxy,b.xyxy,self.bounds):costs[i,j]=1.
                # Two boxes around a visible neighbour must not reactivate a
                # missing person at that neighbour's position. Keep the missing
                # person's previous extent available to the image/cover checks.
                if overlaps[i,j]<cfg.TRACK_NEIGHBOUR_OWN_MAX_IOU and any(
                    k!=i and overlaps[k,j]>=cfg.TRACK_NEIGHBOUR_OTHER_MIN_IOU and rectangle_iou(a.xyxy,tracks[k].xyxy)<cfg.TRACK_NEIGHBOUR_PAIR_MAX_IOU
                    for k in active
                ):costs[i,j]=1.
        return costs
    def init_track(self,results,img=None):
        detections=super().init_track(results,img)
        old=self.tracked_stracks+self.lost_stracks
        if not old:return detections
        kept=[]
        for d in detections:
            nearest=max(old,key=lambda p:rectangle_iou(p.xyxy,d.xyxy))
            if (d.score<self.args.track_high_thresh and rectangle_iou(nearest.xyxy,d.xyxy)>cfg.TRACK_LOW_SCORE_MIN_IOU
                    and not compatible_extent(nearest.xyxy,d.xyxy) and not edge_expansion(nearest.xyxy,d.xyxy,self.bounds)):continue
            kept.append(d)
        return kept


def make_tracker(fps,bounds=None):
    # Confidence still gates new identities. Existing identities match by box
    # position without multiplying overlap by confidence a second time.
    args=SimpleNamespace(track_high_thresh=cfg.TRACK_HIGH_CONFIDENCE,track_low_thresh=cfg.TRACK_LOW_CONFIDENCE,new_track_thresh=cfg.TRACK_NEW_CONFIDENCE,
        track_buffer=cfg.TRACK_BUFFER_FRAMES,match_thresh=cfg.TRACK_MATCH_MAX_COST,fuse_score=cfg.TRACK_FUSE_SCORE)
    tracker=ExtentTracker(args,frame_rate=fps);tracker.bounds=bounds
    return tracker


def filter_boxes(rows,minimum=None,duplicate_iou=None):
    minimum=cfg.DETECTION_MIN_CONFIDENCE if minimum is None else minimum
    duplicate_iou=cfg.DETECTION_DUPLICATE_IOU if duplicate_iou is None else duplicate_iou
    kept=[]
    for d in sorted(rows,key=lambda p:-p['score']):
        if d['score']<minimum:continue
        if any(rectangle_iou(d['xyxy'],p['xyxy'])>=duplicate_iou or same_upper_extent(d['xyxy'],p['xyxy']) for p in kept):continue
        kept.append(d)
    return kept




def context_image_size(base,width,height,region_crop):
    # Expanding the field of view at fixed input size shrinks people. Preserve
    # the former crop's person-pixel scale, rounding up to a network stride.
    x,y,z,w=region_crop
    size=int(math.ceil((base*max(width,height)/max(z-x,w-y))/cfg.DETECTOR_STRIDE)*cfg.DETECTOR_STRIDE)
    if size>cfg.DETECTOR_MAX_CONTEXT_SIZE:raise ValueError(f'Preserving region detail needs input size above {cfg.DETECTOR_MAX_CONTEXT_SIZE}; use a larger context crop or disable full-frame context.')
    return size


class YoloDetector:
    def __init__(self,weights=cfg.MODEL_NAME,device=cfg.DETECTOR_DEFAULT_DEVICE,image_size=cfg.DETECTOR_IMAGE_SIZE):
        import torch
        self.torch=torch;self.device=device;self.weights=weights;self.image_size=image_size
        self.model=YOLO(weights)
    def predict(self,image):
        with self.torch.inference_mode():
            result=self.model.predict(image,device=self.device,half=cfg.DETECTOR_CUDA_HALF and self.device.startswith('cuda'),
                imgsz=self.image_size,classes=cfg.DETECTOR_CLASSES,conf=cfg.DETECTOR_CONFIDENCE,iou=cfg.DETECTOR_NMS_IOU,max_det=cfg.DETECTOR_MAX_DETECTIONS,verbose=False)[0].boxes.cpu().numpy()
        if len(result)>=cfg.DETECTOR_MAX_DETECTIONS:raise ValueError('Detector cap reached; cannot trust an incomplete count.')
        return [dict(xyxy=b.tolist(),score=float(s)) for b,s in zip(result.xyxy,result.conf)]


def process(video_path,polygon,n,seconds,detector,output_root,overlap=cfg.ZONE_OVERLAP_FRACTION,
            max_hidden_seconds=cfg.HIDDEN_MAX_SECONDS,max_image_seconds=cfg.IMAGE_MAX_SECONDS,capture_frames=(),
            write_video=True,crop=None,max_frame_gap=cfg.VIDEO_MAX_FRAME_GAP_SECONDS,evidence_mode=False,readable_labels=False,full_frame_context=False,stable_ids=False,max_extent_seconds=cfg.BODY_MAX_REFERENCE_SECONDS,zone_policy=None):
    """Uploaded-video runner; the same occupancy step is reusable for live frames.

    Estimated occupancy includes bounded uncertainty. Alarm confirmation requires
    N direct current detections; it still assumes continuity during a hidden gap.
    This is not a proof of physical presence behind an opaque object.
    """
    root=Path(output_root);root.mkdir(parents=True,exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='gathering_',dir=root))
    zone_policy=dict(mode=cfg.OCC_DEFAULT_MEMBERSHIP_MODE,anchor=cfg.OCC_DEFAULT_ANCHOR,
                     boundary_margin_fraction=cfg.OCC_BOUNDARY_MARGIN_FRACTION,
                     boundary_max_seconds=cfg.OCC_BOUNDARY_MAX_SECONDS,
                     overlap_fraction=overlap) if zone_policy is None else dict(zone_policy)
    overlap=zone_policy.get('overlap_fraction',overlap)
    state=Occupancy(polygon,overlap,max_hidden_seconds,evidence_mode=evidence_mode,max_extent_seconds=max_extent_seconds,
                    membership_mode=zone_policy['mode'],anchor=zone_policy.get('anchor',cfg.OCC_DEFAULT_ANCHOR),
                    boundary_margin_fraction=zone_policy.get('boundary_margin_fraction',cfg.OCC_BOUNDARY_MARGIN_FRACTION),
                    boundary_max_seconds=zone_policy.get('boundary_max_seconds',cfg.OCC_BOUNDARY_MAX_SECONDS))
    visual=VisualSupport(max_image_seconds);cover=CoverEvidence();identity=IdentityLinker()
    episode=Episode(n,seconds);events=[];resets=[];previous=0;origin=None;last_stamp=None
    detector_seconds=tracking_seconds=encoding_seconds=0.;frames=0;writer=None
    status='processing';error=None;started=time.perf_counter();last_t=0.;identity_ids=set()
    try:
        with av.open(str(video_path)) as video,open(folder/'diagnostics.jsonl','w') as log:
            if not video.streams.video:raise ValueError('No video stream.')
            stream=video.streams.video[0];stream.codec_context.thread_count=cfg.VIDEO_DECODE_THREADS
            fps=float(stream.average_rate or cfg.VIDEO_FALLBACK_FPS)
            # Convert retention seconds to source-frame units; no per-video tuning.
            tracker=make_tracker(fps)
            for i,frame in enumerate(video.decode(stream)):
                if frame.pts is None:raise ValueError('Frame has no timestamp.')
                stamp=Fraction(frame.pts)*frame.time_base
                if origin is None:origin=stamp
                if last_stamp is not None and (stamp<=last_stamp or stamp-last_stamp>max_frame_gap):
                    raise ValueError('Unusable timestamp order or excessive video gap.')
                last_stamp=stamp;t=stamp-origin;last_t=float(t)
                image=frame.to_ndarray(format='bgr24');height,width=image.shape[:2]
                if i==0:
                    validate_polygon(polygon,width,height)
                    if full_frame_context:crop=[0,0,width,height]
                    elif crop is None:crop=padded_crop(polygon,width,height)
                    tracker.bounds=crop
                    identity.bounds=crop
                    left,top,right,bottom=map(int,crop)
                    if write_video:writer=AnnotatedVideo(str(folder/'annotated.mp4'),width,height+(READABLE_FOOTER if readable_labels else cfg.LEGACY_FOOTER_HEIGHT))
                mark=time.perf_counter();raw=detector.predict(image[top:bottom,left:right])
                raw=[dict(d,xyxy=(np.asarray(d['xyxy'])+[left,top,left,top]).tolist()) for d in raw]
                detector_seconds+=time.perf_counter()-mark
                mark=time.perf_counter();gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
                if evidence_mode:cover.update(image)
                selected=filter_boxes(raw)
                values=np.asarray([[*d['xyxy'],d['score'],0] for d in selected],np.float32).reshape(-1,6)
                current=tracker.update(Boxes(values,image.shape[:2]))
                observed=[dict(xyxy=p[:4].tolist(),id=int(p[4]),score=float(p[5])) for p in current]
                if stable_ids:observed=identity.update(last_t,observed,image,protected=set(state.people))
                # Occupancy evaluates cover once per visible/missing person and
                # remembers it. A separate discarded pre-check loses that history.
                tracks=state.step(last_t,observed,verify_visible=lambda p:visual.verify(p,gray,last_t,occupied=observed),occluders=selected,cover_check=cover.covers if evidence_mode else None)
                cover.prune(set(state.people))
                if stable_ids:identity.remember(last_t,tracks,image)
                estimated=sum(p['inside'] for p in tracks)
                confirmed=sum(p['inside'] and p['state']=='visible_inside' for p in tracks)
                elapsed,alarm=episode.step(t,estimated,confirmed)
                if alarm:events.append(dict(seconds=last_t,estimated=estimated,observed=confirmed))
                if previous>=n and estimated<n:resets.append(last_t)
                previous=estimated
                for p in observed:visual.remember(p,gray,last_t,update_template=p['score']>=cfg.VISUAL_TEMPLATE_MIN_CONFIDENCE)
                identity_ids.update(p['id'] for p in tracks)
                tracking_seconds+=time.perf_counter()-mark
                record=dict(frame=i,video_seconds=last_t,count=estimated,observed_count=confirmed,
                    elapsed_seconds=float(elapsed),alarm=bool(alarm),tracks=tracks,raw_model=raw,identity_links=identity.events if stable_ids else [])
                print(json.dumps(record),file=log)
                mark=time.perf_counter()
                if write_video or i in capture_frames:
                    camera_image=image.copy() if readable_labels else None
                    cv2.polylines(image,[np.rint(polygon).astype(np.int32)],True,cfg.LEGACY_POLYGON_COLOR,cfg.LEGACY_POLYGON_THICKNESS)
                    for p in tracks:
                        a,b,c,d=np.rint(p['xyxy']).astype(int)
                        color=cfg.LEGACY_VISIBLE_COLOR if p['state']=='visible_inside' else cfg.LEGACY_HIDDEN_COLOR if p['inside'] else cfg.LEGACY_OUTSIDE_COLOR
                        cv2.rectangle(image,(a,b),(c,d),color,cfg.LEGACY_BOX_THICKNESS)
                        label=f"{p['id']} {p['score']:.{cfg.ANN_CONFIDENCE_DECIMALS}f} {p['state']}"
                        cv2.putText(image,label,(a,max(cfg.LEGACY_LABEL_MIN_Y,b-cfg.LEGACY_LABEL_OFFSET)),cfg.LEGACY_LABEL_FONT,cfg.LEGACY_LABEL_SCALE,color,cfg.LEGACY_LABEL_THICKNESS)
                    label='ALARM' if episode.gate.fired else 'UNCERTAIN' if estimated>confirmed else 'OBSERVED'
                    text=f'{label} | observed {confirmed}, estimated {estimated} / {n} | {float(elapsed):.{cfg.ANN_TIME_DECIMALS}f}s / >{seconds:g}s | {last_t:.{cfg.ANN_TIME_DECIMALS}f}s'
                    output=render(camera_image,polygon,tracks,n,confirmed,estimated,float(elapsed),seconds,last_t,episode.gate.fired,overlap=overlap) if readable_labels else status_frame(image,text,cfg.LEGACY_STATUS_COLOR)
                    if write_video:writer.write(output,stamp)
                    if i in capture_frames:cv2.imwrite(str(folder/f'frame-{i:0{cfg.CAPTURE_FRAME_NUMBER_WIDTH}d}.jpg'),output)
                encoding_seconds+=time.perf_counter()-mark;frames+=1
                if i%cfg.PROGRESS_LOG_EVERY_FRAMES==0:print('FRAME',i,'observed',confirmed,'estimated',estimated,flush=True)
            if not frames:raise ValueError('No readable video frames.')
            status='decoder_reached_end'
    except Exception as exc:error=f'{type(exc).__name__}: {exc}';status='error'
    finally:
        if writer is not None:writer.close()
    report=dict(status=status,error=error,video=str(video_path),N=n,T=seconds,polygon=polygon,
        overlap_fraction=overlap,zone_policy=zone_policy,crop_xyxy=crop,frames=frames,last_video_seconds=last_t,
        events=events,resets=resets,unique_ids=len(identity_ids),model=getattr(detector,'weights','recorded'),
        device=getattr(detector,'device','recorded'),image_size=getattr(detector,'image_size',None),model_seconds=detector_seconds,
        tracking_seconds=tracking_seconds,encoding_seconds=encoding_seconds,
        wall_seconds=time.perf_counter()-started,write_video=write_video,
        max_hidden_seconds=max_hidden_seconds,max_image_seconds=max_image_seconds,max_extent_seconds=max_extent_seconds,evidence_mode=evidence_mode,readable_labels=readable_labels,full_frame_context=full_frame_context,stable_ids=stable_ids,
        timer_policy='estimated_continuity_confirm_alarm_with_direct_detections',output_dir=str(folder),
        source_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')})
    (folder/'summary.json').write_text(json.dumps(report,indent=2));bundle_run(folder)
    if error:raise RuntimeError(f'{error}; partial outputs saved in {folder}')
    return report
