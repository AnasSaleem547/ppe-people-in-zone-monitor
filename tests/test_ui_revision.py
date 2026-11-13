import pytest
from fastapi.testclient import TestClient


def test_video_filename_names_runs_and_existing_links_still_work(video_factory, tmp_path):
    from config import Settings
    from main import create_app
    from test_api import payload
    app = create_app(Settings(_env_file=None, data_dir=tmp_path/'data'))
    with TestClient(app) as client:
        upload = client.post('/api/uploads', files={'file': ('Front Door.MP4', video_factory().read_bytes())}).json()
        a = client.post('/api/jobs', json=payload(upload['upload_id'])).json()
        assert a['job_id'] == 'front-door-run-0001'
        b = client.post('/api/jobs', json=payload(upload['upload_id'])).json()
        assert b['job_id'] == 'front-door-run-0002'
        assert a['video_name'] == 'Front Door.MP4'
        internal = app.state.repository.get_job(a['job_id'])['id']
        assert client.get('/api/jobs/'+internal).json()['job_id'] == a['job_id']
        assert client.get(a['status_url']).status_code == 200


def test_result_is_immediately_playable_without_postprocessing_confirmation():
    from streamlit.testing.v1 import AppTest
    import base64, cv2, numpy as np
    jpeg = cv2.imencode('.jpg', np.zeros((20,20,3), np.uint8))[1].tobytes()
    job = dict(job_id='front-door-run-0001', region_preview='data:image/jpeg;base64,'+base64.b64encode(jpeg).decode(),
               result=dict(video_url='https://example.com/video.mp4',alarm_count=0,alarms=[]))
    # Exercise actual result rendering, omitting reference image decoding.
    script = "from frontend.app import display_result\nimport streamlit as st\nst.session_state['j']="+repr(job)+"\ndisplay_result(st.session_state['j'])"
    at=AppTest.from_string(script).run()
    assert not at.exception
    assert not at.checkbox
    assert any('Submitted region' in x.label for x in at.expander)


def test_public_run_name_survives_sqlite_row_relocation(tmp_path):
    from repository import Repository
    from test_repository import add_upload, request
    repo=Repository(tmp_path/'db.sqlite')
    add_upload(repo,tmp_path,'valid')
    job=repo.create_job(request(),'one')
    public_name=repo.public_identity(job)[0]
    with repo.connection() as db:
        db.execute('UPDATE jobs SET rowid=123 WHERE id=?',(job['id'],))
    assert repo.get_job(public_name)['id']==job['id']
    assert repo.public_identity(repo.get_job(job['id']))[0]==public_name
