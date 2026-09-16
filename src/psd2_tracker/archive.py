"""Persistent, versioned archive of public reports and published metric days."""
from __future__ import annotations

import csv
import argparse
import gzip
import hashlib
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


DAILY_FIELDS = ["bank_id", "bank", "date", "aisp_response_ms", "pisp_response_ms", "aisp_error_pct", "pisp_error_pct", "source_url", "first_seen_on", "last_seen_on", "versions"]


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


class Archive:
    def __init__(self, directory: Path, observed_on: date):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self.observed_on = observed_on.isoformat()
        self.database = directory / "tracker.sqlite3"
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    sha256 TEXT PRIMARY KEY, path TEXT NOT NULL, byte_length INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS fetches (
                    bank_id TEXT NOT NULL, observed_on TEXT NOT NULL, url TEXT NOT NULL,
                    sha256 TEXT NOT NULL REFERENCES documents(sha256), http_status INTEGER NOT NULL,
                    content_type TEXT NOT NULL,
                    PRIMARY KEY (bank_id, observed_on, url, sha256)
                );
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY, bank_id TEXT NOT NULL, period TEXT NOT NULL,
                    kind TEXT NOT NULL, sha256 TEXT NOT NULL, payload_json TEXT NOT NULL,
                    first_seen_on TEXT NOT NULL, last_seen_on TEXT NOT NULL, last_seen_at TEXT NOT NULL,
                    UNIQUE (bank_id, period, kind, sha256)
                );
                CREATE TABLE IF NOT EXISTS daily_versions (
                    id INTEGER PRIMARY KEY, bank_id TEXT NOT NULL, day TEXT NOT NULL,
                    sha256 TEXT NOT NULL, payload_json TEXT NOT NULL,
                    first_seen_on TEXT NOT NULL, last_seen_on TEXT NOT NULL, last_seen_at TEXT NOT NULL,
                    UNIQUE (bank_id, day, sha256)
                );
                CREATE INDEX IF NOT EXISTS snapshots_period ON snapshots(bank_id, period, kind);
                CREATE INDEX IF NOT EXISTS daily_day ON daily_versions(bank_id, day);
                PRAGMA user_version = 1;
            """)

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.database)
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def record_response(self, bank_id: str, response: Any, observed_on: str | None = None) -> None:
        digest = hashlib.sha256(response.content).hexdigest()
        relative = Path("objects") / digest[:2] / f"{digest}.gz"
        target = self.directory / relative
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            # One immutable object per content hash; no cookies/request headers are stored.
            with target.open("xb") as handle:
                handle.write(gzip.compress(response.content, mtime=0))
        content_type = response.headers.get("Content-Type", "") if response.headers else ""
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO documents VALUES (?, ?, ?)", (digest, relative.as_posix(), len(response.content)))
            db.execute("INSERT OR IGNORE INTO fetches VALUES (?, ?, ?, ?, ?, ?)", (bank_id, observed_on or self.observed_on, response.url, digest, response.status_code, content_type))

    def record_snapshot(self, row: dict[str, Any], kind: str) -> None:
        payload = canonical(row)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        period = row.get("period") or row.get("latest_period") or ""
        with self.connect() as db:
            db.execute("""INSERT INTO snapshots (bank_id, period, kind, sha256, payload_json, first_seen_on, last_seen_on, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bank_id, period, kind, sha256) DO UPDATE SET last_seen_on=excluded.last_seen_on, last_seen_at=excluded.last_seen_at""",
                (row["bank_id"], period, kind, digest, payload, self.observed_on, self.observed_on, datetime.now(timezone.utc).isoformat()))

    def record_daily(self, observation: Any) -> None:
        # Failed retrievals must not turn carried-forward averages into fresh daily data.
        if observation.source_state not in {"ok", "ok-direct-pdf"}:
            return
        with self.connect() as db:
            for record in observation.daily_metrics or []:
                row = {"bank_id": observation.bank_id, "bank": observation.bank, "source_url": observation.source_url, **record}
                date.fromisoformat(row["date"])
                values = {key: value for key, value in row.items() if key.endswith(("_pct", "_ms"))}
                if not any(value is not None for value in values.values()):
                    continue
                for key, value in values.items():
                    if value is not None and (value < 0 or (key.endswith("_pct") and value > 100)):
                        raise ValueError(f"Invalid archived metric {key}: {value}")
                payload = canonical(row)
                digest = hashlib.sha256(payload.encode()).hexdigest()
                db.execute("""INSERT INTO daily_versions (bank_id, day, sha256, payload_json, first_seen_on, last_seen_on, last_seen_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(bank_id, day, sha256) DO UPDATE SET last_seen_on=excluded.last_seen_on, last_seen_at=excluded.last_seen_at""",
                    (observation.bank_id, row["date"], digest, payload, self.observed_on, self.observed_on, datetime.now(timezone.utc).isoformat()))

    def quarterly_rows(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT payload_json FROM snapshots WHERE kind='quarterly-report' ORDER BY last_seen_at, id").fetchall()
        latest = {}
        for (payload,) in rows:
            row = json.loads(payload)
            if row.get("report_url") and row.get("source_state") in {"ok", "ok-direct-pdf"}:
                key = (row["bank_id"], row["period"])
                has_values = lambda item: any(value not in (None, "") for field, value in item.items() if field.endswith(("_pct", "_ms")))
                if key in latest and has_values(latest[key]) and not has_values(row):
                    continue
                latest[key] = row
        return list(latest.values())

    def daily_rows(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("""SELECT payload_json, MIN(first_seen_on) OVER (PARTITION BY bank_id, day), last_seen_on,
                COUNT(*) OVER (PARTITION BY bank_id, day) AS versions,
                ROW_NUMBER() OVER (PARTITION BY bank_id, day ORDER BY last_seen_at DESC, id DESC) AS position
                FROM daily_versions ORDER BY day, bank_id""").fetchall()
        return [{**json.loads(payload), "first_seen_on": first, "last_seen_on": last, "versions": versions}
                for payload, first, last, versions, position in rows if position == 1]

    def latest_rows(self) -> dict[str, dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT payload_json FROM snapshots WHERE kind='latest-check' ORDER BY last_seen_at, id").fetchall()
        return {row["bank_id"]: row for (payload,) in rows if (row := json.loads(payload))}

    def verify(self) -> None:
        with self.connect() as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or db.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Archive database integrity check failed")
            documents = db.execute("SELECT sha256, path, byte_length FROM documents").fetchall()
        for digest, relative, length in documents:
            content = gzip.decompress((self.directory / relative).read_bytes())
            if len(content) != length or hashlib.sha256(content).hexdigest() != digest:
                raise ValueError(f"Archive object integrity check failed: {digest}")

    def summary(self) -> dict[str, Any]:
        daily = self.daily_rows()
        with self.connect() as db:
            counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                      for table in ("documents", "fetches", "snapshots", "daily_versions")}
            first = db.execute("SELECT MIN(first_seen_on) FROM snapshots").fetchone()[0]
        return {"schema_version": 1, "first_archived_on": first, "checked_on": self.observed_on,
                "daily_days": len(daily), "daily_from": daily[0]["date"] if daily else None,
                "daily_to": daily[-1]["date"] if daily else None, **counts}

    def export(self, data_dir: Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        rows = self.daily_rows()
        (data_dir / "daily-history.json").write_text(json.dumps(rows, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        with (data_dir / "daily-history.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=DAILY_FIELDS, lineterminator="\n", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        (self.directory / "summary.json").write_text(json.dumps(self.summary(), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify persistent PSD2 archive")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    archive = Archive(args.data_dir / "archive", date.today())
    archive.verify()
    print(json.dumps(archive.summary(), ensure_ascii=False))


if __name__ == "__main__":
    main()
