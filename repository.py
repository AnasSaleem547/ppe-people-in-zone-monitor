"""Small, transactional SQLite upload registry and FIFO job queue."""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


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

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
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

    def create_job(self, request, request_key):
        serialized = json.dumps(request, sort_keys=True, separators=(",", ":"))
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
            db.execute("INSERT INTO jobs(id,request_key,upload_id,request,status,phase,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                       (job_id, request_key, request["upload_id"], serialized, status, status, now, now))
            return self.decode(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def get_job(self, job_id):
        with self.connection() as db:
            return self.decode(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

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
