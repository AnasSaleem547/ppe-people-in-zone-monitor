"""Small, transactional SQLite upload registry and FIFO job queue."""
import json
import sqlite3
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from contextlib import contextmanager
from pathlib import Path

from backend.core import config as cfg


class Conflict(ValueError):
    pass


class Repository:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS uploads (
                    id TEXT PRIMARY KEY, file_path TEXT NOT NULL,
                    preview_path TEXT NOT NULL, metadata TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending', error TEXT,
                    created_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, request_key TEXT NOT NULL UNIQUE,
                    upload_id TEXT NOT NULL REFERENCES uploads(id),
                    request TEXT NOT NULL, status TEXT NOT NULL, phase TEXT NOT NULL,
                    error TEXT, attempts INTEGER NOT NULL DEFAULT 0,
                    retry_at REAL NOT NULL DEFAULT 0,
                    checkpoint TEXT NOT NULL DEFAULT '{}', result TEXT,
                    created_at REAL NOT NULL, updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS job_queue ON jobs(status, retry_at, created_at);
            """)

        # One additive migration; legacy UUIDs and cloud paths stay unchanged.
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if "public_id" not in {r[1] for r in db.execute("PRAGMA table_info(jobs)")}:
                db.execute("ALTER TABLE jobs ADD COLUMN public_id TEXT")
            db.execute("CREATE TABLE IF NOT EXISTS job_aliases (alias TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id))")
            rows = db.execute("SELECT jobs.id,jobs.public_id,jobs.created_at,uploads.metadata FROM jobs JOIN uploads ON jobs.upload_id=uploads.id ORDER BY jobs.created_at,jobs.rowid").fetchall()
            for row in rows:
                if row[1] and "_run_" in row[1]:
                    continue
                name = json.loads(row[3]).get("filename", "Video")
                if row[1]:
                    db.execute("INSERT OR IGNORE INTO job_aliases VALUES(?,?)", (row[1],row[0]))
                public_id = self._allocate_name(db, name, row[2])
                db.execute("UPDATE jobs SET public_id=? WHERE id=?", (public_id,row[0]))
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS public_job_name ON jobs(public_id)")

    @staticmethod
    def _allocate_name(db, filename, created_at):
        date = datetime.fromtimestamp(created_at, ZoneInfo("Asia/Karachi")).strftime("%d/%m/%Y")
        prefix = f"{filename}_run_{date}_"
        number = 1
        while db.execute("SELECT 1 FROM jobs WHERE public_id=?", (f"{prefix}{number:0{cfg.JOB_PUBLIC_RUN_NUMBER_WIDTH}d}",)).fetchone():
            number += 1
        return f"{prefix}{number:0{cfg.JOB_PUBLIC_RUN_NUMBER_WIDTH}d}"

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=cfg.DATABASE_CONNECT_TIMEOUT_SECONDS)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def decode(row):
        if row is None:
            return None
        result = dict(row)
        for key in ("metadata", "request", "checkpoint", "result"):
            if key in result and result[key] is not None:
                result[key] = json.loads(result[key])
        return result

    def add_upload(self, upload_id, file_path, preview_path, metadata):
        with self.connection() as db:
            db.execute("INSERT INTO uploads(id,file_path,preview_path,metadata,created_at) VALUES(?,?,?,?,?)",
                       (upload_id, file_path, preview_path, json.dumps(metadata), time.time()))

    def get_upload(self, upload_id):
        with self.connection() as db:
            return self.decode(db.execute("SELECT * FROM uploads WHERE id=?", (upload_id,)).fetchone())

    def pending_uploads(self, recover=False):
        with self.connection() as db:
            if recover:
                db.execute("UPDATE uploads SET status='pending' WHERE status='validating'")
            return [r[0] for r in db.execute("SELECT id FROM uploads WHERE status='pending'")]

    def start_validation(self, upload_id):
        with self.connection() as db:
            cursor = db.execute("UPDATE uploads SET status='validating' WHERE id=? AND status='pending'", (upload_id,))
            return cursor.rowcount == 1

    def finish_validation(self, upload_id, valid, error=None, details=None):
        with self.connection() as db:
            if details is not None:
                row = db.execute("SELECT metadata FROM uploads WHERE id=?", (upload_id,)).fetchone()
                metadata = json.loads(row[0])
                metadata["validation"] = details
                db.execute("UPDATE uploads SET metadata=? WHERE id=?", (json.dumps(metadata), upload_id))
            db.execute("UPDATE uploads SET status=?,error=? WHERE id=?",
                       ("valid" if valid else "invalid", error, upload_id))
            db.execute("UPDATE jobs SET status=?,phase=?,error=?,updated_at=? WHERE upload_id=? AND status='waiting_validation'",
                       ("queued" if valid else "failed", "queued" if valid else "validation",
                        error, time.time(), upload_id))

    def create_job(self, request, request_key, zone_policy=None):
        serialized = json.dumps(request, sort_keys=True, separators=(",", ":"))
        checkpoint = json.dumps({"zone_policy": zone_policy} if zone_policy is not None else {})
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = self.decode(db.execute("SELECT * FROM jobs WHERE request_key=?", (request_key,)).fetchone())
            if existing:
                if existing["request"] != request:
                    raise Conflict("This idempotency key was already used with different inputs.")
                return existing
            upload = self.decode(db.execute("SELECT * FROM uploads WHERE id=?", (request["upload_id"],)).fetchone())
            if upload is None:
                raise LookupError("Upload not found.")
            if upload["status"] == "invalid":
                raise ValueError(upload["error"] or "Video validation failed.")
            job_id, now = uuid.uuid4().hex, time.time()
            status = "queued" if upload["status"] == "valid" else "waiting_validation"
            db.execute("INSERT INTO jobs(id,request_key,upload_id,request,status,phase,checkpoint,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                       (job_id, request_key, request["upload_id"], serialized, status, status, checkpoint, now, now))
            name = self._allocate_name(db, upload["metadata"].get("filename", "Video"), now)
            db.execute("UPDATE jobs SET public_id=? WHERE id=?", (name, job_id))
            return self.decode(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def public_identity(self, job):
        upload = self.get_upload(job["upload_id"])
        return job["public_id"], upload["metadata"].get("filename", "Video")

    def get_job(self, job_id):
        with self.connection() as db:
            return self.decode(db.execute("SELECT * FROM jobs WHERE id=? OR public_id=? OR id IN (SELECT job_id FROM job_aliases WHERE alias=?)", (job_id,job_id,job_id)).fetchone())

    def get_job_by_key(self, request_key):
        with self.connection() as db:
            return self.decode(db.execute("SELECT * FROM jobs WHERE request_key=?", (request_key,)).fetchone())

    def claim_job(self):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT jobs.id FROM jobs JOIN uploads ON jobs.upload_id=uploads.id
                WHERE jobs.status='queued' AND jobs.retry_at<=? AND uploads.status='valid'
                ORDER BY jobs.created_at,jobs.rowid LIMIT 1""", (time.time(),)).fetchone()
            if row is None:
                return None
            db.execute("UPDATE jobs SET status='processing',phase='processing',attempts=attempts+1,updated_at=? WHERE id=?",
                       (time.time(), row[0]))
            return self.decode(db.execute("SELECT * FROM jobs WHERE id=?", (row[0],)).fetchone())

    def update_job(self, job_id, **values):
        allowed = {"status", "phase", "error", "retry_at", "checkpoint", "result"}
        if not values or not set(values) <= allowed:
            raise ValueError("Unsupported job update.")
        values["updated_at"] = time.time()
        values = {k: json.dumps(v) if k in ("checkpoint", "result") and v is not None else v
                  for k, v in values.items()}
        columns = ",".join(f"{key}=?" for key in values)
        with self.connection() as db:
            db.execute(f"UPDATE jobs SET {columns} WHERE id=?", (*values.values(), job_id))

    def recover_jobs(self):
        with self.connection() as db:
            db.execute("""UPDATE jobs SET status='queued',phase='recovered',retry_at=0,updated_at=?
                WHERE status IN ('processing','adding_audio','uploading','preparing_delivery')""", (time.time(),))

    def queue_position(self, job_id):
        with self.connection() as db:
            row = db.execute("SELECT created_at,status FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None or row["status"] not in ("queued", "waiting_validation"):
                return None
            return db.execute("SELECT count(*) FROM jobs WHERE status='queued' AND created_at<=?", (row["created_at"],)).fetchone()[0]
