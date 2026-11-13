from pathlib import Path
import streamlit as st

PLAYER = st.components.v2.component(
    'people_result_native_player',
    html='''<div class="result-player">
      <video controls playsinline preload="metadata" aria-label="Processed video"></video>
    </div>''',
    css='''.result-player {width:100%;}
      video {display:block;max-width:100%;max-height:calc(100vh - 190px);object-fit:contain;margin:auto;background:#111;}''',
    js=Path(__file__).with_suffix('.js').read_text(),
)


def result_player(job):
    PLAYER(key='player_'+job['job_id'],data={'url':job['result']['video_url']})
