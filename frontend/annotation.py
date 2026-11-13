from pathlib import Path

import streamlit as st

COMPONENT = st.components.v2.component(
    "people_zone_annotation",
    html="""<div class="zone-annotation">
      <p data-note>Click four corners in order, then confirm.</p>
      <canvas aria-label="Select monitoring region"></canvas>
      <div class="actions"><button type="button" data-reset>Reset area</button>
      <button type="button" data-confirm disabled>Confirm area</button></div>
    </div>""",
    css=""".zone-annotation {font-family:var(--st-font); color:var(--st-text-color);}
      canvas {max-width:100%; height:auto; display:block; cursor:crosshair; touch-action:none;}
      .actions {display:flex; gap:12px; margin-top:12px;}
      button {font:inherit; padding:8px 14px; border:1px solid var(--st-border-color);
        border-radius:6px; background:var(--st-secondary-background-color);color:var(--st-text-color);cursor:pointer;}
      button:disabled {opacity:.5;cursor:default;}""",
    js=Path(__file__).with_suffix(".js").read_text(),
)


def annotate(upload):
    key = "annotation_" + upload["upload_id"]
    state = st.session_state.get(key, {})
    result = COMPONENT(data={**upload, "selection": state.get("selection")},
                       default={"selection": None}, key=key, on_selection_change=lambda: None)
    return result.selection
