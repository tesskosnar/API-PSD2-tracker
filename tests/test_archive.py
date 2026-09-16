import gzip
import sqlite3
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from psd2_tracker.archive import Archive
from psd2_tracker.tracker import Observation, collect_timeseries, collect_bank, parse_moneta, timeseries_row, write_dashboard_data
from unittest.mock import patch


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.archive = Archive(self.root / "archive", date(2026, 9, 16))

    def tearDown(self):
        self.temp.cleanup()

    def daily(self, day, value):
        return Observation(bank_id="moneta", bank="MONETA", scope="main", source_url="https://example.test", daily_metrics=[{"date": day, "aisp_response_ms": value}])

    def test_days_survive_removed_rolling_window(self):
        self.archive.record_daily(self.daily("2026-06-18", 250))
        next_run = Archive(self.root / "archive", date(2026, 10, 1))
        next_run.record_daily(self.daily("2026-09-30", 100))
        self.assertEqual([row["date"] for row in next_run.daily_rows()], ["2026-06-18", "2026-09-30"])

    def test_corrections_are_versioned_not_overwritten(self):
        self.archive.record_daily(self.daily("2026-09-15", 250))
        self.archive.record_daily(self.daily("2026-09-15", 250))
        next_run = Archive(self.root / "archive", date(2026, 9, 23))
        next_run.record_daily(self.daily("2026-09-15", 300))
        with next_run.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM daily_versions").fetchone()[0], 2)
        current = next_run.daily_rows()[0]
        self.assertEqual(current["aisp_response_ms"], 300)
        self.assertEqual(current["versions"], 2)
        self.assertEqual(current["first_seen_on"], "2026-09-16")
        self.assertEqual(current["last_seen_on"], "2026-09-23")
        next_run.record_daily(self.daily("2026-09-15", 250))
        self.assertEqual(next_run.daily_rows()[0]["aisp_response_ms"], 250)
        self.assertEqual(next_run.daily_rows()[0]["versions"], 2)

    def test_failed_source_never_erases_daily_data(self):
        self.archive.record_daily(self.daily("2026-09-15", 250))
        failed = self.daily("2026-09-15", 0)
        failed.source_state = "http-403"
        self.archive.record_daily(failed)
        self.assertEqual(self.archive.daily_rows()[0]["aisp_response_ms"], 250)

    def test_raw_sources_are_deduplicated_and_verified(self):
        response = SimpleNamespace(content=b"public report", url="https://example.test/report", status_code=200, headers={"Content-Type": "application/pdf"})
        self.archive.record_response("x", response)
        self.archive.record_response("x", response)
        other = Archive(self.root / "archive", date(2026, 9, 23))
        other.record_response("x", response)
        self.assertEqual(other.summary()["documents"], 1)
        self.assertEqual(other.summary()["fetches"], 2)
        other.verify()
        target = next((other.directory / "objects").rglob("*.gz"))
        self.assertEqual(gzip.decompress(target.read_bytes()), b"public report")
        target.write_bytes(gzip.compress(b"changed"))
        with self.assertRaisesRegex(ValueError, "integrity"):
            other.verify()

    def test_quarterly_archive_survives_source_removal_and_exports_to_dashboard(self):
        row = {"bank_id": "x", "bank": "X", "scope": "main", "period": "2026-Q2", "source_state": "ok", "report_url": "https://example.test/report", "availability_pct": 99.9}
        self.archive.record_snapshot(row, "quarterly-report")
        self.archive.record_snapshot({**row, "source_state": "report-error", "availability_pct": ""}, "quarterly-report")
        self.archive.record_snapshot({**row, "availability_pct": ""}, "quarterly-report")
        self.assertEqual(self.archive.quarterly_rows()[0]["availability_pct"], 99.9)
        self.archive.record_daily(self.daily("2026-09-15", 250))
        write_dashboard_data([], [], "2026-Q2", date(2026, 9, 16), self.root / "data.js", archive=self.archive)
        self.assertIn('"daily_history"', (self.root / "data.js").read_text())
        write_dashboard_data([], [], "2026-Q2", date(2026, 9, 16), self.root / "data.js")
        self.assertIn('"daily_history"', (self.root / "data.js").read_text())
        self.archive.export(self.root)
        self.assertTrue((self.root / "daily-history.csv").exists())

    def test_failed_refresh_keeps_verified_quarterly_value(self):
        bank = {"id": "x", "name": "X", "scope": "main", "parser": "pdf_links", "source_url": "https://example.test", "history_start_period": "2026-Q2"}
        row = {"bank_id": "x", "bank": "X", "scope": "main", "period": "2026-Q2", "source_state": "ok", "report_url": "https://example.test/report", "availability_pct": 99.9}
        failed = Observation(bank_id="x", bank="X", scope="main", source_url=bank["source_url"], latest_period="2026-Q2", report_url=row["report_url"], source_state="report-error")
        with patch("psd2_tracker.tracker.collect_pdf_history", return_value=[failed]):
            rows = collect_timeseries([bank], object(), [], "2026-Q2", [row], refresh=True)
        self.assertEqual(rows[0]["availability_pct"], 99.9)

    def test_moneta_parser_keeps_each_published_day_including_zero(self):
        source = b'<div class="table-accordion__row">15.09.2026 AISP avg. latency (ms) 250 AISP err. rate (%) 0.2 PISP avg. latency (ms) 0 PISP err. rate (%) 0</div>'
        bank = {"id": "moneta", "name": "MONETA", "scope": "main", "source_url": "https://example.test"}
        result = parse_moneta(bank, SimpleNamespace(get=lambda url: SimpleNamespace(content=source)))
        self.assertEqual(result.daily_metrics[0]["date"], "2026-09-15")
        self.assertEqual(result.daily_metrics[0]["pisp_response_ms"], 0)
        self.assertIsNone(result.pisp_response_ms)
        self.archive.record_daily(result)
        self.assertEqual(self.archive.daily_rows()[0]["pisp_response_ms"], 0)

    def test_empty_successful_refresh_keeps_published_values(self):
        bank = {"id": "x", "name": "X", "scope": "main", "parser": "pdf_links", "source_url": "https://example.test", "history_start_period": "2026-Q2"}
        row = {"bank_id": "x", "bank": "X", "scope": "main", "period": "2026-Q2", "latest_period": "2026-Q2", "source_state": "ok", "report_url": "https://example.test/report", "availability_pct": 99.9}
        empty = Observation(bank_id="x", bank="X", scope="main", source_url=bank["source_url"], latest_period="2026-Q2", report_url=row["report_url"])
        with patch("psd2_tracker.tracker.collect_pdf_history", return_value=[empty]):
            self.assertEqual(collect_timeseries([bank], object(), [], "2026-Q2", [row], refresh=True)[0]["availability_pct"], 99.9)
        with patch("psd2_tracker.tracker.parse_report_links", return_value=empty):
            latest = collect_bank(bank, object(), date(2026,9,16), "2026-Q2", row)
        self.assertEqual(latest.availability_pct, 99.9)
        self.assertEqual(latest.status, "blocked")

    def test_archived_quarter_completeness_does_not_age_with_latest_state(self):
        observation = Observation(bank_id="ppf", bank="PPF", scope="main", source_url="https://example.test", latest_period="2026-Q1", status="outdated", aisp_response_ms=250)
        self.assertEqual(timeseries_row(observation)["status"], "partial")
        self.assertEqual(observation.status, "outdated")


if __name__ == "__main__":
    unittest.main()
