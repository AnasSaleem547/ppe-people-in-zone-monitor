"""Run from codebase: python -m streamlit run frontend/app.py"""
import base64
import sys
from pathlib import Path

# Streamlit adds the script directory, so expose the application root explicitly.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from config import Settings
from frontend.annotation import annotate
from frontend.api_client import APIClient, APIError
from frontend.state import TERMINAL, polling_interval, submission_key


def show_image(data_uri, **kwargs):
    st.image(base64.b64decode(data_uri.split(",", 1)[1]), **kwargs)


def display_result(job):
    st.subheader("Verify your marked region")
    show_image(job["region_preview"], caption="The first-frame preview with the region submitted for this run.")
    result = job["result"]
    st.metric("Alarm episodes in the output video", result["alarm_count"])
    if st.checkbox("This is the region I marked", key="verified_" + job["job_id"]):
        st.video(result["video_url"], autoplay=False, muted=False)
        st.caption("Press Play and keep sound unmuted to hear the alarms.")
        st.link_button("Open video", result["video_url"])
    for alarm in result["alarms"]:
        st.markdown(f"**Alarm {alarm['index']}** — triggered at {alarm['start_seconds']:.3f}s; "
                    f"ended at {alarm['end_seconds']:.3f}s ({alarm['duration_seconds']:.3f}s).")
        st.write(alarm["condition"])
        st.caption(f"Observed at trigger: {alarm['observed_at_trigger']}; estimated: {alarm['estimated_at_trigger']}. "
                   f"Ended because: {alarm['end_reason'].replace('_', ' ')}.")
    if not result["alarms"]:
        st.info("No alarm episodes were recorded under the submitted N/T rule.")


def main():
    st.set_page_config(page_title="People in Zone Monitor", layout="wide")
    settings = Settings()
    client = APIClient(settings.api_base_url)
    st.title("People in Zone Monitor")
    st.write("Upload a recording, mark four corners, and check when the people-count rule is met.")
    st.caption("The timer follows estimated occupancy. A new alarm requires direct observations; it resets when estimated occupancy drops below N.")
    with st.sidebar:
        st.subheader("Resume a run")
        resume = st.text_input("Job ID", value=st.query_params.get("job", ""))
        if st.button("Load run", disabled=not resume):
            try:
                st.session_state["job"] = client.status(resume.strip())
                st.query_params["job"] = resume.strip()
            except APIError as exc:
                st.error(str(exc))
        st.caption("One local worker processes videos in order. Closing this page does not cancel an accepted job.")

    st.subheader("1. Upload a video")
    file = st.file_uploader("Video recording", type=["mp4", "mov", "avi", "mkv", "webm", "m4v"],
                            max_upload_size=settings.max_upload_mb)
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
        selection = annotate(upload)
        left, right = st.columns(2)
        n = left.number_input("N — minimum people inside the region", min_value=1, value=2, step=1)
        seconds = right.number_input("T — count must stay at least N for MORE THAN these video seconds",
                                     min_value=.001, value=5., step=.5, format="%.3f")
        active = st.session_state.get("job", {}).get("status") not in (None, *TERMINAL)
        if st.button("Start processing", type="primary", disabled=not (selection and selection.get("confirmed")) or active):
            body = dict(upload_id=upload["upload_id"], n_people=int(n), threshold_seconds=float(seconds), polygon=selection["points"])
            try:
                job = client.submit(body, submission_key(st.session_state, body))
                st.session_state["job"] = job
                st.query_params["job"] = job["job_id"]
            except APIError as exc:
                st.error(str(exc))

    if "job" not in st.session_state and st.query_params.get("job"):
        try:
            st.session_state["job"] = client.status(st.query_params["job"])
        except APIError as exc:
            st.error(str(exc))
    job = st.session_state.get("job")
    if not job:
        return
    st.subheader("3. Processing status")
    st.code(job["job_id"], language=None)
    interval = polling_interval(job.get("duration_seconds"), job["status"], settings.short_video_seconds, settings.status_poll_seconds)

    @st.fragment(run_every=interval)
    def status_panel():
        st.button("Check status", key="manual_status")
        try:
            fresh = client.status(job["job_id"])
        except APIError as exc:
            st.error(str(exc))
            return
        st.session_state["job"] = fresh
        st.write(fresh["message"])
        if fresh.get("queue_position"):
            st.caption(f"Queue position: {fresh['queue_position']}")
        if fresh["error"]:
            st.error(fresh["error"])
        if interval:
            st.caption(f"Checks automatically every {interval} seconds while this page is active.")
        elif fresh["status"] not in TERMINAL:
            st.caption("Use Check status to request an update.")
        if fresh["status"] in TERMINAL and job["status"] not in TERMINAL:
            st.rerun()

    status_panel()
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
