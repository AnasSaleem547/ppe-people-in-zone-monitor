from pathlib import Path
import streamlit as st

PLAYER = st.components.v2.component(
    'people_result_player',
    html='''<div class="result-player">
      <video controls playsinline preload="metadata" aria-label="Processed video"></video>
      <div class="player-tools">
        <button data-play type="button">Play with sound</button>
        <button data-test type="button">Test sound</button>
        <label>Alarm audio <select aria-label="Alarm audio"><option value="video">Video track</option>
        <option value="browser">Browser tone (fallback)</option></select></label>
      </div><p data-status role="status">Sound plays during the reported alarm intervals.</p>
    </div>''',
    css='''.result-player {font-family:var(--st-font);color:var(--st-text-color);width:100%;}
      video {display:block;max-width:100%;max-height:calc(100vh - 190px);object-fit:contain;margin:auto;background:#111;}
      .player-tools {display:flex;align-items:center;flex-wrap:wrap;gap:10px;margin-top:12px;}
      button,select {font:inherit;padding:8px;border:1px solid var(--st-border-color);border-radius:6px;
      background:var(--st-secondary-background-color);color:var(--st-text-color);cursor:pointer;}
      p {font-size:14px;}''',
    js=Path(__file__).with_suffix('.js').read_text(),
)

def result_player(job):
    result=job['result']
    PLAYER(key='player_'+job['job_id'],data={'url':result['video_url'],'alarms':result['alarms']})
