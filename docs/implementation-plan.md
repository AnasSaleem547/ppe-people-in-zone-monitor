# Notebook Web Wrapper Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline. Test first;
> run and observe each failing group before implementing it. Commit each group.

**Goal:** Serve the unchanged CV techniques through a local FastAPI/Streamlit app.
**Architecture:** A small API persists uploads/jobs in SQLite. API background
threads validate video; a separately locked worker runs CV, adds sound and
uploads the completed result. Streamlit owns annotation and status display.
**Tech stack:** FastAPI, SQLite stdlib, Streamlit v2 components, PyAV, FFmpeg,
Ultralytics 8.4.37, Cloudinary Python SDK.
**Spec:** docs/approved-design.md

## Global constraints
- All deliverables live in codebase; no changes to original notebook/project.
- Source notebook: /home/anas/PPE_YOLO_continuity_finalister.ipynb.
- Core modules retain source bodies; only package imports differ.
- N positive integer; T finite positive; four ordered valid points inside image.
- Cell 13 evidence_mode/readable_labels/stable_ids all True; crop context False.
- Strict video time > T; audio follows notebook trigger/reset records.
- Three APIs, no v1; 7-second short-video polling; exact secret in ignored .env.

## Review focus
- A job submitted during validation must not start before a valid result.
- Different requests sharing an idempotency key must produce a conflict.
- Resized previews and nonzero/variable timestamps must stay aligned.
- Worker restart/upload retry must not falsely report success or mix artifacts.
- Uncertain occupancy must retain the existing audio/visual alarm policy.

## Task 1: CV preservation and configuration
Files: services/cv/*.py, services/pipeline.py, config.py, provenance/*,
tests/test_cv_contract.py, tests/test_pipeline.py, requirements*.txt.
Interfaces: Settings; PipelineRunner.run(path, polygon, n, seconds, output_root).
- [ ] Write failing source-preservation, timer, adapter-call and rendering tests.
- [ ] Run tests; observe missing implementation failures.
- [ ] Extract seven modules, configuration and adapter with lazy model loading.
- [ ] Run tests; commit with Codex co-author.

## Task 2: Persistent queue and background validation
Files: repository.py, schemas.py, services/media.py, tests/test_repository.py,
tests/test_media.py. Interfaces: Repository upload/job CRUD, claim/recovery;
inspect_video, validate_video, region_preview.
- [ ] Write failing queue durability/claim/idempotency/validation-gate tests and
      real video timestamp/preview/invalid media tests.
- [ ] Run tests; implement SQLite transactions and media handling; run suite.
- [ ] Commit with Codex co-author.

## Task 3: API routes
Files: main.py, routes/*.py, tests/test_api.py.
Interfaces: create_app(settings), three routes, JSON with inline image previews.
- [ ] Write failing upload/job/status tests including pending and failed validation,
      invalid coordinates, oversized upload, repeated key and unknown identifiers.
- [ ] Run tests; implement routes and background-validator lifecycle; run suite.
- [ ] Commit with Codex co-author.

## Task 4: Audio, cloud and worker
Files: services/alarms.py, services/cloud_storage.py, worker.py,
tests/test_alarms.py, tests/test_worker.py, tests/test_cloud.py.
Interfaces: build_intervals(report, endpoint); add_alarm_audio(...);
CloudStorage.upload(...); Worker.run_once().
- [ ] Write failing trigger/reset/EOF tests, real FFmpeg waveform/timestamp tests,
      delivery-URL tests and checkpoint/retry/restart worker tests.
- [ ] Run tests; implement independent postprocessing and single-worker queue loop.
- [ ] Run suite; commit with Codex co-author.

## Task 5: Streamlit UI and documentation
Files: frontend/app.py, frontend/api_client.py, frontend/annotation.py,
frontend/annotation.js, tests/test_frontend.py, tests/annotation.test.mjs, README.md.
Interfaces: JS canvas ↔ original-coordinate points; Python API client; UI state.
- [ ] Write/run failing coordinate, component-event and API client/polling tests.
- [ ] Implement upload/annotation/status/result flow, region verification and audio
      playback. Document setup, env, worker operation and guarantees.
- [ ] Run all tests, browser smoke, real short inference and authorized small
      Cloudinary integration test. Review full code and fix important findings
      test-first. Commit with Codex co-author.

## Progress
Approved implementation proceeds without another approval round.
Ruling: use a new Git repository inside codebase because its parent has no Git
repository and the user requested all implementation in that folder.
