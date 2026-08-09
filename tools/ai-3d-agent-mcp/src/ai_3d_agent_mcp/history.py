from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobRecord:
    job_id: str
    created_at: str
    updated_at: str
    status: str
    category: str
    prompt: str
    material: str
    printer: str
    width_mm: float
    depth_mm: float
    height_mm: float
    scale_mode: str
    image_paths: list[str]
    warnings: list[str]
    artifacts: dict[str, str]
    meta: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "category": self.category,
            "prompt": self.prompt,
            "material": self.material,
            "printer": self.printer,
            "dimensions": {
                "width_mm": self.width_mm,
                "depth_mm": self.depth_mm,
                "height_mm": self.height_mm,
                "scale_mode": self.scale_mode,
            },
            "image_paths": self.image_paths,
            "warnings": self.warnings,
            "artifacts": self.artifacts,
            "meta": self.meta,
        }


class JobHistory:
    def __init__(self, db_path: Path, workspace: Path) -> None:
        self.db_path = db_path
        self.workspace = workspace
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    category TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    material TEXT NOT NULL,
                    printer TEXT NOT NULL,
                    width_mm REAL NOT NULL,
                    depth_mm REAL NOT NULL,
                    height_mm REAL NOT NULL,
                    scale_mode TEXT NOT NULL,
                    image_paths_json TEXT NOT NULL,
                    warnings_json TEXT NOT NULL,
                    artifacts_json TEXT NOT NULL,
                    meta_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def job_dir(self, job_id: str) -> Path:
        path = self.workspace / job_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def create_job(
        self,
        *,
        category: str,
        prompt: str,
        material: str,
        printer: str,
        width_mm: float,
        depth_mm: float,
        height_mm: float,
        scale_mode: str,
        image_paths: list[str] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> JobRecord:
        job_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        now = _utc_now()
        record = JobRecord(
            job_id=job_id,
            created_at=now,
            updated_at=now,
            status="created",
            category=category,
            prompt=prompt,
            material=material,
            printer=printer,
            width_mm=width_mm,
            depth_mm=depth_mm,
            height_mm=height_mm,
            scale_mode=scale_mode,
            image_paths=list(image_paths or []),
            warnings=[],
            artifacts={},
            meta=dict(meta or {}),
        )
        self.job_dir(job_id)
        self._upsert(record)
        self._write_sidecar(record)
        return record

    def _upsert(self, record: JobRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    job_id, created_at, updated_at, status, category, prompt, material, printer,
                    width_mm, depth_mm, height_mm, scale_mode, image_paths_json, warnings_json,
                    artifacts_json, meta_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    updated_at=excluded.updated_at,
                    status=excluded.status,
                    category=excluded.category,
                    prompt=excluded.prompt,
                    material=excluded.material,
                    printer=excluded.printer,
                    width_mm=excluded.width_mm,
                    depth_mm=excluded.depth_mm,
                    height_mm=excluded.height_mm,
                    scale_mode=excluded.scale_mode,
                    image_paths_json=excluded.image_paths_json,
                    warnings_json=excluded.warnings_json,
                    artifacts_json=excluded.artifacts_json,
                    meta_json=excluded.meta_json
                """,
                (
                    record.job_id,
                    record.created_at,
                    record.updated_at,
                    record.status,
                    record.category,
                    record.prompt,
                    record.material,
                    record.printer,
                    record.width_mm,
                    record.depth_mm,
                    record.height_mm,
                    record.scale_mode,
                    json.dumps(record.image_paths),
                    json.dumps(record.warnings),
                    json.dumps(record.artifacts),
                    json.dumps(record.meta),
                ),
            )
            conn.commit()

    def _write_sidecar(self, record: JobRecord) -> None:
        path = self.job_dir(record.job_id) / "job.json"
        path.write_text(json.dumps(record.as_dict(), indent=2))

    def _row_to_record(self, row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            job_id=row["job_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            status=row["status"],
            category=row["category"],
            prompt=row["prompt"],
            material=row["material"],
            printer=row["printer"],
            width_mm=float(row["width_mm"]),
            depth_mm=float(row["depth_mm"]),
            height_mm=float(row["height_mm"]),
            scale_mode=row["scale_mode"],
            image_paths=json.loads(row["image_paths_json"]),
            warnings=json.loads(row["warnings_json"]),
            artifacts=json.loads(row["artifacts_json"]),
            meta=json.loads(row["meta_json"]),
        )

    def get(self, job_id: str) -> JobRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def require(self, job_id: str) -> JobRecord:
        record = self.get(job_id)
        if not record:
            raise KeyError(f"Unknown job_id: {job_id}")
        return record

    def update(
        self,
        job_id: str,
        *,
        status: str | None = None,
        warnings: list[str] | None = None,
        append_warnings: list[str] | None = None,
        artifacts: dict[str, str] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> JobRecord:
        record = self.require(job_id)
        record.updated_at = _utc_now()
        if status is not None:
            record.status = status
        if warnings is not None:
            record.warnings = list(warnings)
        if append_warnings:
            record.warnings.extend(append_warnings)
        if artifacts:
            record.artifacts.update(artifacts)
        if meta:
            record.meta.update(meta)
        self._upsert(record)
        self._write_sidecar(record)
        return record

    def list_jobs(self, limit: int = 20) -> list[JobRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]
