import base64
from pathlib import Path

import cv2
import httpx
import numpy as np
from streamlit.testing.v1 import AppTest


def test_status_get_happens_only_when_check_or_load_is_clicked(monkeypatch):
    from frontend.api_client import APIClient
    import frontend.app as app
    requests=[]
    job=dict(job_id='run-0001',job_name='clip.mp4',video_name='clip.mp4',status='processing',
             message='Processing started.',progress={'frames_analyzed':10,'total_frames':100,'cv_percent':10},
             region_preview='data:image/jpeg;base64,'+base64.b64encode(cv2.imencode('.jpg',np.zeros((20,20,3),np.uint8))[1]).decode(),
             result=None,error=None,queue_position=None,duration_seconds=20)
    def handle(r):
        requests.append((r.method,r.url.path))
        return httpx.Response(200,json=job)
    monkeypatch.setattr('frontend.api_client.APIClient',lambda url:APIClient('http://test',transport=httpx.MockTransport(handle)))
    at=AppTest.from_file(str(Path(app.__file__)))
    at.session_state['job']=job
    at.run()
    assert not at.exception
    assert requests==[]
    at.text_input[0].set_value('run-0001').run()
    assert requests==[]
    next(b for b in at.button if b.label=='Check status').click().run()
    assert requests==[('GET','/api/jobs/run-0001')]
    at.run()
    assert len(requests)==1
    next(b for b in at.button if b.label=='Load job').click().run()
    assert len(requests)==2


def test_saved_url_does_not_fetch_without_user_click(monkeypatch):
    from frontend.api_client import APIClient
    import frontend.app as app
    requests=[]
    def handle(r):
        requests.append(r.url.path)
        return httpx.Response(404,json={'detail':'not found'})
    monkeypatch.setattr('frontend.api_client.APIClient',lambda url:APIClient('http://test',transport=httpx.MockTransport(handle)))
    at=AppTest.from_file(str(Path(app.__file__)))
    at.query_params['job']='run-0001'
    at.run()
    assert not at.exception
    assert requests==[]
