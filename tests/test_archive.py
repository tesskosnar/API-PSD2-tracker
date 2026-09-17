import gzip
import sqlite3
import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from psd2_tracker.archive import Archive
from psd2_tracker.tracker import Observation, Fetcher, build_report_coverage, collect_timeseries, collect_mbank_history, collect_bank, parse_moneta, timeseries_row, write_dashboard_data, derive_archived_quarters, merge_derived_quarters, finalize_status
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

    def test_report_coverage_counts_unique_days_and_preserves_zero(self):
        reports = [{"bank_id": "x", "period": "2024-Q1"}, {"bank_id": "x", "period": "2024-Q2"}]
        daily = [{"bank_id": "x", "date": "2024-01-01", "aisp_response_ms": 0}, {"bank_id": "x", "date": "2024-01-01", "aisp_response_ms": 0}, {"bank_id": "x", "date": "2024-01-02", "aisp_response_ms": None, "availability_pct": 99}, {"bank_id": "other", "date": "2024-01-03", "aisp_response_ms": 10}]
        coverage = build_report_coverage(reports, daily)
        self.assertEqual(coverage["x:2024-Q1"]["calendar_days"], 91)
        self.assertEqual(coverage["x:2024-Q1"]["archived_days"], 2)
        self.assertEqual(coverage["x:2024-Q1"]["metric_days"]["aisp_response_ms"], 1)
        self.assertEqual(coverage["x:2024-Q1"]["metric_days"]["availability_pct"], 1)
        self.assertEqual(coverage["x:2024-Q2"]["archived_days"], 0)

    def test_coverage_and_bank_page_cache_survive_offline_refresh(self):
        output = self.root / "data.js"
        bank_page = self.root / "bank.html"
        bank_page.write_text('<script src="data.js?v=old"></script><script src="daily-data.js?v=old"></script>')
        report = {"bank_id": "moneta", "period": "2026-Q3"}
        self.archive.record_daily(self.daily("2026-09-15", 100))
        write_dashboard_data([], [report], "2026-Q2", date(2026, 9, 16), output, archive=self.archive)
        self.assertIn('"report_coverage"', output.read_text())
        self.assertNotIn('v=old', bank_page.read_text())
        write_dashboard_data([], [report], "2026-Q2", date(2026, 9, 16), output)
        self.assertIn('"archived_days": 1', output.read_text())

    def test_scope_unverified_report_evidence_survives_catalog_removal(self):
        import json
        output=self.root / "data.js"
        old={"period":"2026-Q2","report_url":"https://example.test/same.pdf"}
        new={"period":"2026-Q3","report_url":"https://example.test/same.pdf"}
        item=Observation(bank_id="oberbank",bank="Oberbank",scope="main",source_url="https://example.test",report_details={"published_reports":[old]})
        write_dashboard_data([item],[],"2026-Q2",date(2026,9,16),output)
        item.report_details={"published_reports":[new]}
        write_dashboard_data([item],[],"2026-Q3",date(2026,10,1),output)
        payload=json.loads(output.read_text().removeprefix("window.PSD2_DATA = "))
        reports=payload["source_details"]["oberbank:"]["published_reports"]
        self.assertEqual([r["period"] for r in reports],["2026-Q2","2026-Q3"])
        self.assertFalse(reports[0]["catalog_present"])
        self.assertTrue(reports[1]["catalog_present"])

    def test_days_survive_removed_rolling_window(self):
        self.archive.record_daily(self.daily("2026-06-18", 250))
        next_run = Archive(self.root / "archive", date(2026, 10, 1))
        next_run.record_daily(self.daily("2026-09-30", 100))
        self.assertEqual([row["date"] for row in next_run.daily_rows()], ["2026-06-18", "2026-09-30"])

    def test_retained_source_uses_latest_copy_and_checks_integrity(self):
        url="https://example.test/report.pdf"
        self.assertIsNone(self.archive.response_content("mbank",url))
        for content in [b"old report",b"new report"]:
            self.archive.record_response("mbank",SimpleNamespace(content=content,url=url,status_code=200,headers={}))
        self.assertEqual(self.archive.response_content("mbank",url),b"new report")
        with self.archive.connect() as db:
            relative=db.execute("SELECT d.path FROM fetches f JOIN documents d ON d.sha256=f.sha256 ORDER BY f.rowid DESC LIMIT 1").fetchone()[0]
        (self.archive.directory/relative).write_bytes(gzip.compress(b"changed"))
        with self.assertRaisesRegex(ValueError,"integrity"):
            self.archive.response_content("mbank",url)

    def test_mbank_import_uses_retained_pdf_offline_and_preserves_unknown_country(self):
        report={"period":"2026-Q2","periods":["2026-Q2"],"first_day":"2026-04-01","last_day":"2026-06-30","report_url":"https://example.test/report.pdf"}
        self.archive.record_response("mbank",SimpleNamespace(content=b"%PDF-test",url=report["report_url"],status_code=200,headers={}))
        fetcher=Fetcher(archive=self.archive)
        fetcher.get=lambda *a,**k:self.fail("Archived import must not use the network")
        bank={"id":"mbank","name":"mBank","source_url":"https://developer.api.mbank.cz/reports"}
        with patch("psd2_tracker.tracker.extract_pdf_text",return_value="mBank API\n01.04.2026 100 100 0 0 300 400 - 0.1"):
            item=collect_mbank_history(bank,fetcher,{"2026-Q2"},[report])[0]
        self.archive.record_daily(item)
        self.assertEqual(self.archive.daily_rows()[0]["country_code"],"unverified")
        self.assertEqual(item.country_scope,"unverified")
        self.assertEqual(item.report_kind,"summary")
        self.assertEqual(item.shared_error_pct,.1)
        self.assertIsNone(item.aisp_error_pct)

    def test_weekly_mbank_history_preserves_scope_and_imports_new_quarter(self):
        bank={"id":"mbank","name":"mBank","parser":"report_links","source_url":"https://example.test","include_summary_statistics":True,"history_start_period":"2026-Q1"}
        first=Observation(bank_id="mbank",bank="mBank",scope="main",source_url=bank["source_url"],latest_period="2026-Q1",report_url="https://example.test/old.pdf",country_scope="unverified",report_kind="summary",status="unverified",availability_pct=99,archived_days=90,calendar_days=90)
        new=Observation(bank_id="mbank",bank="mBank",scope="main",source_url=bank["source_url"],latest_period="2026-Q2",report_url="https://example.test/new.pdf",country_scope="unverified",report_kind="summary",status="unverified",availability_pct=100,archived_days=91,calendar_days=91)
        reports=[{"period":"2026-Q2","report_url":new.report_url}]
        first.report_details={"country_scope":"unverified","published_reports":reports}
        with patch("psd2_tracker.tracker.collect_mbank_history",return_value=[new]) as collect:
            result=collect_timeseries([bank],object(),[first],"2026-Q2",[timeseries_row(first)])
        self.assertEqual(collect.call_args.args[2],{"2026-Q2"})
        self.assertEqual(collect.call_args.args[3],reports)
        self.assertEqual([r["period"] for r in result],["2026-Q1","2026-Q2"])
        self.assertTrue(all(r["country_scope"]=="unverified" and r["report_kind"]=="summary" and r["status"]=="unverified" for r in result))
        self.assertEqual(result[1]["archived_days"],91)

    def test_derived_closed_quarter_counts_unique_czech_days_and_not_open_quarter(self):
        banks = [{"id":"moneta", "name":"MONETA", "source_url":"https://example.test", "derive_quarters_from_daily":True}]
        daily = [{"bank_id":"moneta", "country_code":"CZ", "date":"2026-06-18", "aisp_response_ms":100, "aisp_error_pct":0}, {"bank_id":"moneta", "country_code":"CZ", "date":"2026-06-18", "aisp_response_ms":200, "aisp_error_pct":0}, {"bank_id":"moneta", "country_code":"CZ", "date":"2026-06-19", "aisp_response_ms":0, "aisp_error_pct":2}, {"bank_id":"moneta", "country_code":"CZ", "date":"2026-07-01", "aisp_response_ms":900}, {"bank_id":"moneta", "country_code":"PL", "date":"2026-06-20", "aisp_response_ms":900}]
        rows = derive_archived_quarters(banks, daily, date(2026,9,16))
        self.assertEqual(len(rows),1)
        row = rows[0]
        self.assertEqual(row["period"],"2026-Q2")
        self.assertEqual(row["report_kind"],"archive-derived")
        self.assertEqual((row["archived_days"],row["calendar_days"]),(2,91))
        self.assertEqual(row["aisp_response_ms"],200)
        self.assertEqual(row["aisp_error_pct"],1)
        self.assertEqual(row["availability_pct"],"")
        self.assertEqual(row["pisp_error_pct"],"")
        self.assertEqual(len(derive_archived_quarters(banks,daily,date(2026,10,1))),2)

    def test_derived_quarters_survive_removed_window_and_recompute_corrections(self):
        banks=[{"id":"moneta","name":"MONETA","source_url":"https://example.test","derive_quarters_from_daily":True}]
        self.archive.record_daily(self.daily("2026-06-18",100))
        self.archive.record_daily(self.daily("2026-06-19",300))
        self.assertEqual(derive_archived_quarters(banks,self.archive.daily_rows(),date(2026,10,1))[0]["aisp_response_ms"],200)
        next_run=Archive(self.root / "archive",date(2026,10,1))
        next_run.record_daily(self.daily("2026-09-30",1000))
        next_run.record_daily(self.daily("2026-06-18",500))
        rows=derive_archived_quarters(banks,next_run.daily_rows(),date(2026,10,1))
        self.assertEqual(rows[0]["aisp_response_ms"],400)
        next_run.record_snapshot(rows[0],"quarterly-derived")
        self.assertEqual(next_run.quarterly_rows(),[])
        official={**rows[0],"report_kind":"published","aisp_response_ms":999}
        self.assertEqual(merge_derived_quarters([official],rows)[0],official)

    def test_unverified_czech_scope_is_not_report_absence(self):
        item=Observation(bank_id="mbank",bank="mBank",scope="main",source_url="https://example.test",report_details={"country_scope":"unverified"})
        self.assertEqual(finalize_status(item,"2026-Q2").status,"unverified")

    def test_complete_quarter_and_leap_year_days(self):
        from datetime import timedelta
        banks=[{"id":"moneta","name":"MONETA","source_url":"https://example.test","derive_quarters_from_daily":True}]
        days=[{"bank_id":"moneta","country_code":"CZ","date":(date(2024,1,1)+timedelta(days=i)).isoformat(),"aisp_response_ms":10,"aisp_error_pct":0} for i in range(91)]
        self.assertEqual(derive_archived_quarters(banks,days,date(2024,3,31)),[])
        row=derive_archived_quarters(banks,days,date(2024,4,1))[0]
        self.assertEqual((row["archived_days"],row["calendar_days"]),(91,91))
        self.assertEqual(row["aisp_error_pct"],0)

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
        self.assertIn('"daily_history_asset"', (self.root / "data.js").read_text())
        self.assertIn('"aisp_response_ms"', (self.root / "daily-data.js").read_text())
        write_dashboard_data([], [], "2026-Q2", date(2026, 9, 16), self.root / "data.js")
        self.assertIn('"daily_history_asset"', (self.root / "data.js").read_text())
        self.archive.export(self.root)
        self.assertTrue((self.root / "daily-history.csv").exists())

    def test_failed_refresh_keeps_verified_quarterly_value(self):
        bank = {"id": "x", "name": "X", "scope": "main", "parser": "pdf_links", "source_url": "https://example.test", "history_start_period": "2026-Q2"}
        row = {"bank_id": "x", "bank": "X", "scope": "main", "period": "2026-Q2", "source_state": "ok", "report_url": "https://example.test/report", "availability_pct": 99.9}
        failed = Observation(bank_id="x", bank="X", scope="main", source_url=bank["source_url"], latest_period="2026-Q2", report_url=row["report_url"], source_state="report-error")
        with patch("psd2_tracker.tracker.collect_pdf_history", return_value=[failed]):
            rows = collect_timeseries([bank], object(), [], "2026-Q2", [row], refresh=True)
        self.assertEqual(rows[0]["availability_pct"], 99.9)

    def test_rejected_published_report_survives_export_without_numeric_data(self):
        row = {"bank_id": "rb", "bank": "RB", "scope": "main", "period": "2025-Q3", "source_state": "report-error", "report_url": "https://example.test/bad.pdf", "availability_pct": "", "metric_method": "date mismatch"}
        self.archive.record_snapshot(row, "quarterly-report")
        self.assertEqual(self.archive.quarterly_rows(), [row])
        self.archive.record_snapshot({**row, "availability_pct": 100}, "quarterly-report")
        self.assertEqual(self.archive.quarterly_rows(), [row])
        failed = self.daily("2025-07-01", 0)
        failed.source_state = "report-error"
        self.archive.record_daily(failed)
        self.assertEqual(self.archive.daily_rows(), [])

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
