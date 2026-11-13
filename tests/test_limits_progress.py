import json
from fractions import Fraction
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def test_limits_are_central_defaults_and_reported_duration_is_rejected(video_factory,tmp_path):
    from config import Settings
    from main import create_app
    settings=Settings(_env_file=None,data_dir=tmp_path/'data')
    assert settings.max_upload_mb==50
    assert settings.max_video_minutes==20
    app=create_app(Settings(_env_file=None,data_dir=tmp_path/'short',max_video_minutes=.02))
    with TestClient(app) as client:
        r=client.post('/api/uploads',files={'file':('long.mp4',video_factory().read_bytes())})
        assert r.status_code==422
        assert 'duration' in r.json()['detail'].lower()
        assert not list((tmp_path/'short/uploads').glob('*/source.video'))


def test_decoded_duration_limit_catches_unknown_or_incorrect_metadata(video_factory):
    from services.media import validate_video
    p=video_factory()
    with pytest.raises(ValueError,match='duration'):
        validate_video(p,1,max_duration_seconds=2.4)
    assert validate_video(p,1,max_duration_seconds=2.5)['frames']==25


def test_background_validation_blocks_jobs_for_decoded_duration(video_factory,tmp_path):
    from config import Settings
    from repository import Repository
    from services.validation import ValidationService
    from test_repository import add_upload,request
    settings=Settings(_env_file=None,data_dir=tmp_path/'data',max_video_minutes=.02)
    repo=Repository(settings.database_path)
    add_upload(repo,tmp_path)
    # Inject the decoded result, modelling unreliable metadata in preview.
    service=ValidationService(repo,settings,validator=lambda p,g: {'frames':25,'duration_seconds':2.5})
    job=repo.create_job(request(),'long')
    service.submit('u1');service.close()
    assert repo.get_job(job['id'])['status']=='failed'
    assert repo.claim_job() is None


def test_frame_progress_reads_only_current_attempt_complete_rows(tmp_path):
    from services.progress import job_progress
    root=tmp_path/'job';current=root/'attempt-2';log=current/'gathering_a/diagnostics.jsonl'
    log.parent.mkdir(parents=True)
    old=root/'attempt-1/gathering_old';old.mkdir(parents=True)
    (old/'diagnostics.jsonl').write_text(json.dumps({'frame':99,'video_seconds':9.9})+'\n')
    job={'status':'processing','checkpoint':{'cv_root':str(current)}}
    upload={'metadata':{'validation':{'frames':100}}}
    assert job_progress(job,upload)['frames_analyzed']==0
    log.write_text(json.dumps({'frame':24,'video_seconds':2.4})+'\n'+ '{"frame":25')
    result=job_progress(job,upload)
    assert result=={'frames_analyzed':25,'total_frames':100,'cv_percent':25.,'video_seconds':2.4}
    with log.open('a') as f:
        f.write(',"video_seconds":2.5}\n')
    assert job_progress(job,upload)['frames_analyzed']==26
    job['checkpoint']['report']={'frames':100,'last_video_seconds':9.9}
    job['status']='uploading'
    assert job_progress(job,upload)['cv_percent']==100


def test_get_refresh_reports_changed_frame_counts(video_factory,tmp_path):
    from config import Settings
    from main import create_app
    from test_api import payload
    app=create_app(Settings(_env_file=None,data_dir=tmp_path/'data'))
    with TestClient(app) as client:
        u=client.post('/api/uploads',files={'file':('Front Door #1.MP4',video_factory().read_bytes())}).json()
        repo=app.state.repository
        repo.finish_validation(u['upload_id'],True,details={'frames':25,'duration_seconds':2.5})
        job=client.post('/api/jobs',json=payload(u['upload_id'])).json()
        assert job['job_name'].startswith('Front Door #1.MP4_run_')
        claimed=repo.claim_job();root=tmp_path/'attempt-1';root.mkdir()
        repo.update_job(claimed['id'],checkpoint={'cv_root':str(root)})
        log=root/'gathering_test/diagnostics.jsonl';log.parent.mkdir()
        log.write_text('{"frame":4,"video_seconds":0.4}\n')
        assert client.get(job['status_url']).json()['progress']['cv_percent']==20
        with log.open('a') as f:f.write('{"frame":9,"video_seconds":0.9}\n')
        assert client.get(job['status_url']).json()['progress']['frames_analyzed']==10
