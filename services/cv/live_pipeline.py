# Cell 9 — single YOLO detector, ByteTrack and explicit occupancy states.
"""Single-detector pipeline with measured, bounded occupancy uncertainty."""
import json,time,tempfile,math,hashlib
from pathlib import Path
from fractions import Fraction
from types import SimpleNamespace
import av,cv2,numpy as np
from ultralytics import YOLO
from ultralytics.engine.results import Boxes
from ultralytics.trackers.byte_tracker import BYTETracker
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
    return not (sb.prod()>2.*sa.prod() and sb[1]>1.25*sa[1]) or same_upper_extent(a,b)


def edge_expansion(a,b,bounds):
    if bounds is None:return False
    a,b=np.asarray(a),np.asarray(b);bounds=np.asarray(bounds)
    size=bounds[2:]-bounds[:2];tolerance=np.maximum(4.,.02*size)
    da=np.r_[a[:2]-bounds[:2],bounds[2:]-a[2:]]
    db=np.r_[b[:2]-bounds[:2],bounds[2:]-b[2:]]
    shared_edge=np.any((np.abs(da)<=np.tile(tolerance,2)) & (np.abs(db)<=np.tile(tolerance,2)))
    intersection=np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2])).prod()
    containment=intersection/max(1.,min(np.prod(a[2:]-a[:2]),np.prod(b[2:]-b[:2])))
    return shared_edge and containment>=.7


class ExtentTracker(BYTETracker):
    bounds=None
    def get_dists(self,tracks,detections):
        costs=matching.iou_distance(tracks,detections)
        for i,a in enumerate(tracks):
            for j,b in enumerate(detections):
                if not compatible_extent(a.xyxy,b.xyxy) and not edge_expansion(a.xyxy,b.xyxy,self.bounds):costs[i,j]=1.
        return costs
    def init_track(self,results,img=None):
        detections=super().init_track(results,img)
        old=self.tracked_stracks+self.lost_stracks
        if not old:return detections
        kept=[]
        for d in detections:
            nearest=max(old,key=lambda p:rectangle_iou(p.xyxy,d.xyxy))
            if (d.score<self.args.track_high_thresh and rectangle_iou(nearest.xyxy,d.xyxy)>.2
                    and not compatible_extent(nearest.xyxy,d.xyxy) and not edge_expansion(nearest.xyxy,d.xyxy,self.bounds)):continue
            kept.append(d)
        return kept


def make_tracker(fps,bounds=None):
    # Confidence still gates new identities. Existing identities match by box
    # position without multiplying overlap by confidence a second time.
    args=SimpleNamespace(track_high_thresh=.25,track_low_thresh=.1,new_track_thresh=.6,
        track_buffer=60,match_thresh=.8,fuse_score=False)
    tracker=ExtentTracker(args,frame_rate=fps);tracker.bounds=bounds
    return tracker


def filter_boxes(rows,minimum=.1,duplicate_iou=.85):
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
    size=int(math.ceil((base*max(width,height)/max(z-x,w-y))/32)*32)
    if size>1024:raise ValueError('Preserving region detail needs input size above 1024; use a larger context crop or disable full-frame context.')
    return size


class YoloDetector:
    def __init__(self,weights='yolo26m.pt',device='cpu',image_size=640):
        import torch
        self.torch=torch;self.device=device;self.weights=weights;self.image_size=image_size
        self.model=YOLO(weights)
    def predict(self,image):
        with self.torch.inference_mode():
            result=self.model.predict(image,device=self.device,half=self.device.startswith('cuda'),
                imgsz=self.image_size,classes=[0],conf=.05,iou=.7,max_det=300,verbose=False)[0].boxes.cpu().numpy()
        if len(result)>=300:raise ValueError('Detector cap reached; cannot trust an incomplete count.')
        return [dict(xyxy=b.tolist(),score=float(s)) for b,s in zip(result.xyxy,result.conf)]


def process(video_path,polygon,n,seconds,detector,output_root,overlap=.7,
            max_hidden_seconds=1.5,max_image_seconds=2.,capture_frames=(),
            write_video=True,crop=None,max_frame_gap=1.,evidence_mode=False,readable_labels=False,full_frame_context=False,stable_ids=False,max_extent_seconds=2.):
    """Uploaded-video runner; the same occupancy step is reusable for live frames.

    Estimated occupancy includes bounded uncertainty. Alarm confirmation requires
    N direct current detections; it still assumes continuity during a hidden gap.
    This is not a proof of physical presence behind an opaque object.
    """
    root=Path(output_root);root.mkdir(parents=True,exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='gathering_',dir=root))
    state=Occupancy(polygon,overlap,max_hidden_seconds,evidence_mode=evidence_mode,max_extent_seconds=max_extent_seconds);visual=VisualSupport(max_image_seconds);cover=CoverEvidence();identity=IdentityLinker()
    episode=Episode(n,seconds);events=[];resets=[];previous=0;origin=None;last_stamp=None
    detector_seconds=tracking_seconds=encoding_seconds=0.;frames=0;writer=None
    status='processing';error=None;started=time.perf_counter();last_t=0.;identity_ids=set()
    try:
        with av.open(str(video_path)) as video,open(folder/'diagnostics.jsonl','w') as log:
            if not video.streams.video:raise ValueError('No video stream.')
            stream=video.streams.video[0];stream.codec_context.thread_count=2
            fps=float(stream.average_rate or 25)
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
                    if write_video:writer=AnnotatedVideo(str(folder/'annotated.mp4'),width,height+(READABLE_FOOTER if readable_labels else 32))
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
                for p in observed:visual.remember(p,gray,last_t,update_template=p['score']>=.6)
                identity_ids.update(p['id'] for p in tracks)
                tracking_seconds+=time.perf_counter()-mark
                record=dict(frame=i,video_seconds=last_t,count=estimated,observed_count=confirmed,
                    elapsed_seconds=float(elapsed),alarm=bool(alarm),tracks=tracks,raw_model=raw,identity_links=identity.events if stable_ids else [])
                print(json.dumps(record),file=log)
                mark=time.perf_counter()
                if write_video or i in capture_frames:
                    camera_image=image.copy() if readable_labels else None
                    cv2.polylines(image,[np.rint(polygon).astype(np.int32)],True,(0,220,220),2)
                    for p in tracks:
                        a,b,c,d=np.rint(p['xyxy']).astype(int)
                        color=(0,210,0) if p['state']=='visible_inside' else (0,160,255) if p['inside'] else (200,130,30)
                        cv2.rectangle(image,(a,b),(c,d),color,1)
                        label=f"{p['id']} {p['score']:.2f} {p['state']}"
                        cv2.putText(image,label,(a,max(12,b-3)),cv2.FONT_HERSHEY_SIMPLEX,.38,color,1)
                    label='ALARM' if episode.gate.fired else 'UNCERTAIN' if estimated>confirmed else 'OBSERVED'
                    text=f'{label} | observed {confirmed}, estimated {estimated} / {n} | {float(elapsed):.2f}s / >{seconds:g}s | {last_t:.2f}s'
                    output=render(camera_image,polygon,tracks,n,confirmed,estimated,float(elapsed),seconds,last_t,episode.gate.fired,overlap=overlap) if readable_labels else status_frame(image,text,(255,255,255))
                    if write_video:writer.write(output,stamp)
                    if i in capture_frames:cv2.imwrite(str(folder/f'frame-{i:04d}.jpg'),output)
                encoding_seconds+=time.perf_counter()-mark;frames+=1
                if i%250==0:print('FRAME',i,'observed',confirmed,'estimated',estimated,flush=True)
            if not frames:raise ValueError('No readable video frames.')
            status='decoder_reached_end'
    except Exception as exc:error=f'{type(exc).__name__}: {exc}';status='error'
    finally:
        if writer is not None:writer.close()
    report=dict(status=status,error=error,video=str(video_path),N=n,T=seconds,polygon=polygon,
        overlap_fraction=overlap,crop_xyxy=crop,frames=frames,last_video_seconds=last_t,
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
