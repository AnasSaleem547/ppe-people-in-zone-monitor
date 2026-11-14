"""Run from codebase: python -m streamlit run frontend/app.py"""
import base64
import sys
from pathlib import Path

# Streamlit adds the script directory, so expose the application root explicitly.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from backend.core import config as cfg
from frontend.annotation import annotate
from frontend.player import result_player
from frontend.api_client import APIClient, APIError
from frontend.state import TERMINAL, submission_key


def show_image(data_uri, **kwargs):
    st.image(base64.b64decode(data_uri.split(",", 1)[1]), **kwargs)


def show_zone_policy(policy):
    if not policy:
        return
    if policy["mode"] == "anchor":
        anchor = "bottom center" if policy["anchor"] == "bottom_center" else "center"
        st.caption(f"Counts a person when the {anchor} of their detected box is inside the region.")
    else:
        st.caption("Counts a person when enough of their detected box overlaps the region.")


def display_result(job):
    st.subheader(job.get("job_name", job.get("video_name", "Processed video")))
    result = job["result"]
    show_zone_policy(job.get("zone_policy") or result.get("zone_policy"))
    result_player(job)
    st.link_button("Watch output video in a new tab", result["video_url"])
    st.metric("Alarm episodes in the output video", result["alarm_count"])
    decimals = cfg.FRONTEND_ALARM_TIME_DECIMALS
    for alarm in result["alarms"]:
        st.markdown(f"**Alarm {alarm['index']}** — triggered at {alarm['start_seconds']:.{decimals}f}s; "
                    f"ended at {alarm['end_seconds']:.{decimals}f}s ({alarm['duration_seconds']:.{decimals}f}s).")
        st.write(alarm["condition"])
    if not result["alarms"]:
        st.info("No alarm episodes were recorded under the submitted N/T rule.")


def processing_reference(job):
    st.write(job.get("job_name", job.get("video_name", "Video")))
    st.caption("Submitted region")
    with st.container(key="submitted-region"):
        show_image(job["region_preview"], width=cfg.FRONTEND_REGION_PREVIEW_WIDTH)
    st.html(f"<style>{cfg.FRONTEND_REGION_PREVIEW_CSS}</style>")


def progress_details(job):
    progress = job.get("progress", {})
    frames, total = progress.get("frames_analyzed", 0), progress.get("total_frames")
    percent = progress.get("cv_percent")
    if job["status"] == "processing":
        title = f"Analyzing video — {frames:,} / {total:,} frames ({percent:g}%)" if total and percent is not None else f"Analyzing video — {frames:,} frames"
        st.subheader(title)
    else:
        st.subheader(job["message"])
    if percent is not None:
        st.progress(percent / 100, text=f"Frames analyzed: {frames:,} / {total:,} ({percent:g}%)")
    if job["status"] in ("processing", "adding_audio", "uploading"):
        st.caption("Frame progress covers CV analysis. Audio and upload finish separately.")


def main():
    st.set_page_config(page_title="People in Zone Monitor", layout="wide", initial_sidebar_state="expanded")
    settings = cfg.Settings()
    client = APIClient(cfg.BACKEND_URL)
    st.title("People in Zone Monitor")
    st.write(f"Upload a recording, mark {cfg.JOB_POLYGON_POINT_COUNT} corners, and check when the people-count rule is met.")
    with st.sidebar:
        st.subheader("Query Previous Jobs")
        resume = st.text_input("Job name", value=st.query_params.get("job", ""), label_visibility="collapsed", placeholder="Enter job name")
        if st.button("Load job", disabled=not resume):
            try:
                st.session_state["job"] = client.status(resume.strip())
                st.query_params["job"] = st.session_state["job"]["job_id"]
            except APIError as exc:
                st.error(str(exc))

    st.subheader("1. Upload a video")
    file = st.file_uploader("Video recording", type=list(cfg.FRONTEND_VIDEO_EXTENSIONS),
                            max_upload_size=settings.max_upload_mb)
    st.caption(f"Maximum {settings.max_upload_mb} MB and {settings.max_video_minutes:g} minutes per video.")
    if st.button("Get first frame", disabled=file is None):
        try:
            with st.spinner("Uploading and reading the first frame…"):
                st.session_state["upload"] = client.upload(file, file.name)
            for key in ("job", "submission_signature", "submission_key"):
                st.session_state.pop(key, None)
            st.query_params.clear()
        except APIError as exc:
            st.error(str(exc))

    upload = st.session_state.get("upload")
    if upload:
        st.subheader("2. Mark the monitoring region")
        st.caption("Full video validation runs in the background. Processing waits for it to pass.")
        show_zone_policy(settings.zone_policy)
        selection = annotate(upload)
        left, right = st.columns(2)
        n = left.number_input("N — minimum people inside the region", min_value=cfg.JOB_MIN_PEOPLE, value=cfg.FRONTEND_COUNT_DEFAULT, step=cfg.FRONTEND_COUNT_STEP)
        seconds = right.number_input("T — count must stay at least N for MORE THAN these video seconds",
                                     min_value=cfg.FRONTEND_SECONDS_MIN, value=cfg.FRONTEND_SECONDS_DEFAULT,
                                     step=cfg.FRONTEND_SECONDS_STEP, format=f"%.{cfg.FRONTEND_TIME_INPUT_DECIMALS}f")
        st.caption(f"Review the shaded region above: at least {int(n)} people for more than {seconds:g} seconds. Confirm below to submit.")
        active = st.session_state.get("job", {}).get("status") not in (None, *TERMINAL)
        if st.button("Confirm region & process", type="primary", disabled=not (selection and len(selection.get("points", [])) == cfg.JOB_POLYGON_POINT_COUNT) or active):
            body = dict(upload_id=upload["upload_id"], n_people=int(n), threshold_seconds=float(seconds), polygon=selection["points"])
            try:
                job = client.submit(body, submission_key(st.session_state, body))
                st.session_state["job"] = job
                st.query_params["job"] = job["job_id"]
            except APIError as exc:
                st.error(str(exc))

    job = st.session_state.get("job")
    if not job:
        return
    st.subheader("3. Processing status")
    processing_reference(job)
    if st.button("Check status", key="manual_status"):
        try:
            st.session_state["job"] = client.status(job["job_id"])
        except APIError as exc:
            st.error(str(exc))
    job = st.session_state["job"]
    progress_details(job)
    if job.get("queue_position"):
        st.caption(f"Queue position: {job['queue_position']}")
    if job.get("error"):
        st.error(job["error"])
    if job["status"] not in TERMINAL:
        st.caption("Click Check status to fetch the latest update.")
    job = st.session_state["job"]
    if job["status"] == "succeeded":
        display_result(job)
    elif job["status"] == "failed":
        if st.button("Prepare a new attempt"):
            for key in ("job", "submission_signature", "submission_key"):
                st.session_state.pop(key, None)
            st.query_params.clear()
            st.rerun()


if __name__ == "__main__":
    main()
