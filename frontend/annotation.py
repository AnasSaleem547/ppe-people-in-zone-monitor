from pathlib import Path

import streamlit as st

from backend.core import config as cfg

COMPONENT = st.components.v2.component(
    "people_zone_annotation",
    html=f"""<div class="zone-annotation">
      <p data-note>Click {cfg.JOB_POLYGON_POINT_COUNT} corners in order. Review the region and settings below.</p>
      <canvas aria-label="Select monitoring region"></canvas>
      <div class="actions"><button type="button" data-reset>Reset area</button>
</div>
    </div>""",
    css=cfg.FRONTEND_ANNOTATION_CSS,
    js=Path(__file__).with_suffix(".js").read_text(),
)


def annotate(upload):
    key = "annotation_" + upload["upload_id"]
    state = st.session_state.get(key, {})
    config = {
        "corner_count": cfg.JOB_POLYGON_POINT_COUNT,
        "fill_style": cfg.FRONTEND_ANNOTATION_FILL_STYLE,
        "stroke_style": cfg.FRONTEND_ANNOTATION_STROKE_STYLE,
        "line_width": cfg.FRONTEND_ANNOTATION_LINE_WIDTH,
        "font": cfg.FRONTEND_ANNOTATION_FONT,
        "point_style": cfg.FRONTEND_ANNOTATION_POINT_STYLE,
        "point_radius": cfg.FRONTEND_ANNOTATION_POINT_RADIUS,
        "label_offset_x": cfg.FRONTEND_ANNOTATION_LABEL_OFFSET_X,
        "label_offset_y": cfg.FRONTEND_ANNOTATION_LABEL_OFFSET_Y,
    }
    result = COMPONENT(data={**upload, "selection": state.get("selection"), "config": config},
                       default={"selection": None}, key=key, on_selection_change=lambda: None)
    return result.selection
