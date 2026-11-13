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
        assert a['job_name'] == 'Front Door.MP4'
        b = client.post('/api/jobs', json=payload(upload['upload_id'])).json()
        assert b['job_name'] == 'Front Door.MP4'
        assert b['job_id'] != a['job_id']
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
    assert not at.expander
    assert at.get('link_button')[0].proto.label == 'Watch output video in a new tab'


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


def test_processing_reference_is_above_dynamic_frame_progress():
    from streamlit.testing.v1 import AppTest
    import base64,cv2,numpy as np
    image=base64.b64encode(cv2.imencode('.jpg',np.zeros((20,20,3),np.uint8))[1]).decode()
    job=dict(job_id='run-0001',job_name='Front Door.MP4',region_preview='data:image/jpeg;base64,'+image,
             status='processing',phase='processing',message='Processing started.',
             progress={'frames_analyzed':25,'total_frames':100,'cv_percent':25.0})
    script='from frontend.app import processing_reference, progress_details\nj='+repr(job)+'\nprocessing_reference(j)\nprogress_details(j)'
    at=AppTest.from_string(script).run()
    assert not at.exception
    assert any('25 / 100' in x.value for x in at.subheader)
    types=[x.type for x in at.main]
    assert types.index('image') < types.index('progress')
