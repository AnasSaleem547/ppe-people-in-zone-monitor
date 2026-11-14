from pathlib import Path
import streamlit as st

from backend.core import config as cfg

PLAYER = st.components.v2.component(
    'people_result_native_player',
    html='''<div class="result-player">
      <video controls playsinline preload="metadata" aria-label="Processed video"></video>
    </div>''',
    css=cfg.FRONTEND_PLAYER_CSS.format(viewport_margin=cfg.FRONTEND_PLAYER_VIEWPORT_MARGIN),
    js=Path(__file__).with_suffix('.js').read_text(),
)


def result_player(job):
    PLAYER(key='player_'+job['job_id'], data={
        'url': job['result']['video_url'],
        'config': {
            'minimum_height': cfg.FRONTEND_PLAYER_MINIMUM_HEIGHT,
            'viewport_margin': cfg.FRONTEND_PLAYER_VIEWPORT_MARGIN,
            'muted': cfg.FRONTEND_PLAYER_MUTED,
            'volume': cfg.FRONTEND_PLAYER_VOLUME,
        },
    })
