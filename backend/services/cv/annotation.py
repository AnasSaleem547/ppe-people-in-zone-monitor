# Cell 7 — large high-contrast labels and a separate status panel.
"""Minimal outlined ID/score labels and a separate condition/status/legend strip."""
from backend.core import config as cfg
import cv2
import numpy as np
FOOTER_HEIGHT=cfg.ANN_FOOTER_HEIGHT
COLORS=cfg.ANN_COLORS

def dashed_box(image,a,b,c,d,color):
    # Dashed last-known bounds cannot be mistaken for a fresh solid detection.
    for x in range(a,c,cfg.ANN_DASH_PERIOD):
        cv2.line(image,(x,b),(min(x+cfg.ANN_DASH_LENGTH,c),b),color,cfg.ANN_BOX_THICKNESS,cfg.ANN_LINE_TYPE)
        cv2.line(image,(x,d),(min(x+cfg.ANN_DASH_LENGTH,c),d),color,cfg.ANN_BOX_THICKNESS,cfg.ANN_LINE_TYPE)
    for y in range(b,d,cfg.ANN_DASH_PERIOD):
        cv2.line(image,(a,y),(a,min(y+cfg.ANN_DASH_LENGTH,d)),color,cfg.ANN_BOX_THICKNESS,cfg.ANN_LINE_TYPE)
        cv2.line(image,(c,y),(c,min(y+cfg.ANN_DASH_LENGTH,d)),color,cfg.ANN_BOX_THICKNESS,cfg.ANN_LINE_TYPE)

def render(image,polygon,tracks,n,observed,estimated,elapsed,target,t,fired,overlap=cfg.ANN_OVERLAP_FRACTION):
    out=cv2.copyMakeBorder(image,0,cfg.ANN_FOOTER_HEIGHT,0,0,cv2.BORDER_CONSTANT,value=cfg.ANN_FOOTER_COLOR)
    h,w=image.shape[:2];font=cfg.ANN_FONT
    cv2.polylines(out,[np.rint(polygon).astype(np.int32)],True,cfg.ANN_POLYGON_COLOR,cfg.ANN_POLYGON_THICKNESS,cfg.ANN_LINE_TYPE)
    for p in tracks:
        a,b,c,d=np.rint(p['xyxy']).astype(int);color=cfg.ANN_COLORS[p['state']]
        uncertain=p['state'] in ('image_supported','possibly_hidden')
        if uncertain:dashed_box(out,a,b,c,d,color)
        else:cv2.rectangle(out,(a,b),(c,d),color,cfg.ANN_BOX_THICKNESS,cfg.ANN_LINE_TYPE)
        # Keep confidence before the optional suffix so it never shifts when
        # a detection becomes retained. Reserve the same width for either state.
        label=f"#{p['id']:<{cfg.ANN_LABEL_ID_WIDTH}} {p['score']:.{cfg.ANN_CONFIDENCE_DECIMALS}f}"+(' (last)' if uncertain and not p.get('score_is_current',False) else '')
        scale=cfg.ANN_LABEL_SCALE_SMALL if w<cfg.ANN_LABEL_WIDE_THRESHOLD else cfg.ANN_LABEL_SCALE_LARGE
        tw,th=cv2.getTextSize(f"#{p['id']:<{cfg.ANN_LABEL_ID_WIDTH}} {0:.{cfg.ANN_CONFIDENCE_DECIMALS}f} (last)",font,scale,cfg.ANN_LABEL_THICKNESS)[0]
        x=max(cfg.ANN_LABEL_MIN_X,min(a,w-tw-cfg.ANN_LABEL_RIGHT_MARGIN));y=min(h-cfg.ANN_LABEL_BOTTOM_MARGIN,max(th+cfg.ANN_LABEL_TOP_MARGIN,b-cfg.ANN_LABEL_BOX_OFFSET))
        # No black label rectangles: black text outline preserves contrast.
        cv2.putText(out,label,(x,y),font,scale,cfg.ANN_LABEL_OUTLINE_COLOR,cfg.ANN_LABEL_OUTLINE_THICKNESS,cfg.ANN_LINE_TYPE)
        cv2.putText(out,label,(x,y),font,scale,cfg.ANN_LABEL_COLOR,cfg.ANN_LABEL_THICKNESS,cfg.ANN_LINE_TYPE)
    status='ALARM' if fired else 'UNCERTAIN' if estimated>observed else 'OBSERVED'
    lines=[f"{status} | observed {observed}, estimated {estimated} / {n} | {elapsed:.{cfg.ANN_TIME_DECIMALS}f}s / >{target:g}s | video {t:.{cfg.ANN_TIME_DECIMALS}f}s | ALARM {'ON' if fired else 'OFF'}",
           'Green solid: detected | Yellow dashed: retained | Blue solid: outside']
    for i,line in enumerate(lines):
        scale=min(cfg.ANN_STATUS_SCALE,(w-cfg.ANN_STATUS_HORIZONTAL_PADDING)/max(1,cv2.getTextSize(line,font,cfg.ANN_STATUS_SCALE,cfg.ANN_STATUS_THICKNESS)[0][0])*cfg.ANN_STATUS_SCALE)
        cv2.putText(out,line,(cfg.ANN_STATUS_X,h+cfg.ANN_STATUS_BASELINE_OFFSET+i*cfg.ANN_STATUS_LINE_SPACING),font,scale,cfg.ANN_STATUS_COLOR,cfg.ANN_STATUS_THICKNESS,cfg.ANN_LINE_TYPE)
    return out
