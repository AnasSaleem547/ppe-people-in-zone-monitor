# Approved scope

Build FastAPI + Streamlit under codebase, with exactly three application APIs:
POST /api/uploads, POST /api/jobs, GET /api/jobs/{job_id}. No v1 prefix.
Extract notebook cells 3–9 as modular services; main.py exposes the API and
the worker calls the existing pipeline through an adapter. Preserve CV module
bodies, except package-relative imports. Keep the original notebook untouched.
Keep cell 2 settings, cell 12 model initialization and cell 13 flags. Preserve
strict >T timing, estimated continuity, direct confirmation and estimated reset.
Return the first preview after the upload finishes and validate the remaining
video in the background. Submitted jobs wait for successful validation; a failed
validation stops them before inference. SQLite is the only queue dependency.
Use the notebook JS in a Streamlit v2 component. Manual status refresh always;
7-second polling for known durations below 30 seconds. Add alarm audio after CV,
copying the annotated video stream. Upload final media to Cloudinary and wait
for H.264 delivery readiness. Return the original preview with the selected
polygon, alarm count, reasons and video timestamps. Credentials go verbatim
in ignored .env only, never committed or returned by API.

Assumptions: one host, one API process, one CV worker; local persistent storage;
alarm-only audio (the notebook drops original audio). No cloud deletion policy.
The preview cannot precede completion of browser → Streamlit → API upload.

## Validation boundaries

Full background validation decodes frames and checks timestamps/gaps with the
notebook's policy; it is extra preflight I/O, not a detector input transform.
The original uploaded bytes feed inference. A damaged file that a decoder
silently conceals cannot be universally identified by this check. Metadata
duration is provisional. No real-time speed or universal accuracy guarantee.
