# Cell 7 — large high-contrast labels and a separate status panel.
"""Minimal outlined ID/score labels and a separate condition/status/legend strip."""
import cv2
import numpy as np
FOOTER_HEIGHT=72
COLORS={'visible_inside':(80,220,90),'image_supported':(0,255,255),'possibly_hidden':(0,255,255),'observed_outside':(230,180,100)}

def dashed_box(image,a,b,c,d,color):
    # Dashed last-known bounds cannot be mistaken for a fresh solid detection.
    for x in range(a,c,16):
        cv2.line(image,(x,b),(min(x+9,c),b),color,2,cv2.LINE_AA)
        cv2.line(image,(x,d),(min(x+9,c),d),color,2,cv2.LINE_AA)
    for y in range(b,d,16):
        cv2.line(image,(a,y),(a,min(y+9,d)),color,2,cv2.LINE_AA)
        cv2.line(image,(c,y),(c,min(y+9,d)),color,2,cv2.LINE_AA)

def render(image,polygon,tracks,n,observed,estimated,elapsed,target,t,fired,overlap=.7):
    out=cv2.copyMakeBorder(image,0,FOOTER_HEIGHT,0,0,cv2.BORDER_CONSTANT,value=(22,22,22))
    h,w=image.shape[:2];font=cv2.FONT_HERSHEY_SIMPLEX
    cv2.polylines(out,[np.rint(polygon).astype(np.int32)],True,(20,230,240),2,cv2.LINE_AA)
    for p in tracks:
        a,b,c,d=np.rint(p['xyxy']).astype(int);color=COLORS[p['state']]
        uncertain=p['state'] in ('image_supported','possibly_hidden')
        if uncertain:dashed_box(out,a,b,c,d,color)
        else:cv2.rectangle(out,(a,b),(c,d),color,2,cv2.LINE_AA)
        # Keep confidence before the optional suffix so it never shifts when
        # a detection becomes retained. Reserve the same width for either state.
        label=f"#{p['id']:<3} {p['score']:.2f}"+(' (last)' if uncertain and not p.get('score_is_current',False) else '')
        scale=.75 if w<1100 else .8
        tw,th=cv2.getTextSize(f"#{p['id']:<3} 0.00 (last)",font,scale,2)[0]
        x=max(2,min(a,w-tw-5));y=min(h-8,max(th+8,b-5))
        # No black label rectangles: black text outline preserves contrast.
        cv2.putText(out,label,(x,y),font,scale,(0,0,0),5,cv2.LINE_AA)
        cv2.putText(out,label,(x,y),font,scale,(255,255,255),2,cv2.LINE_AA)
    status='ALARM' if fired else 'UNCERTAIN' if estimated>observed else 'OBSERVED'
    lines=[f"{status} | observed {observed}, estimated {estimated} / {n} | {elapsed:.2f}s / >{target:g}s | video {t:.2f}s | ALARM {'ON' if fired else 'OFF'}",
           'Green solid: detected | Yellow dashed: retained | Blue solid: outside']
    for i,line in enumerate(lines):
        scale=min(.60,(w-24)/max(1,cv2.getTextSize(line,font,.60,1)[0][0])*.60)
        cv2.putText(out,line,(12,h+25+i*32),font,scale,(245,245,245),1,cv2.LINE_AA)
    return out
