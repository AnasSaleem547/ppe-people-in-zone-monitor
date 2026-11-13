from datetime import datetime, timezone
from urllib.parse import quote
from fastapi.testclient import TestClient


def test_same_dated_name_for_display_and_lookup_with_reserved_filename(video_factory,tmp_path,monkeypatch):
    from config import Settings
    from main import create_app
    from test_api import payload
    # UTC evening is already the next date in Karachi.
    stamp=datetime(2026,11,12,20,30,tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr('repository.time.time',lambda:stamp)
    app=create_app(Settings(_env_file=None,data_dir=tmp_path/'data'))
    with TestClient(app) as client:
        u=client.post('/api/uploads',files={'file':('Front Door #1.MP4',video_factory().read_bytes())}).json()
        a=client.post('/api/jobs',json=payload(u['upload_id'])).json()
        assert a['job_name']==a['job_id']=='Front Door #1.MP4_run_13/11/2026_001'
        b=client.post('/api/jobs',json=payload(u['upload_id'])).json()
        assert b['job_name']=='Front Door #1.MP4_run_13/11/2026_002'
        assert client.get(a['status_url']).json()['job_name']==a['job_name']
        assert client.get('/api/jobs/'+quote(a['job_name'],safe='')).json()['job_name']==a['job_name']


def test_migration_keeps_previous_resume_links(tmp_path):
    from repository import Repository
    from test_repository import add_upload,request
    repo=Repository(tmp_path/'queue.db');add_upload(repo,tmp_path,'valid')
    j=repo.create_job(request(),'a')
    with repo.connection() as db:db.execute('UPDATE jobs SET public_id=? WHERE id=?',('run-0001',j['id']))
    repo=Repository(tmp_path/'queue.db')
    assert repo.get_job('run-0001')['id']==j['id']
    assert '_run_' in repo.get_job('run-0001')['public_id']
