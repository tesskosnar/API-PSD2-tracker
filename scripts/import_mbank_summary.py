"""Import the retained mBank PDFs only; never rescrape or revise other banks."""
from dataclasses import fields
from datetime import date
import json
from pathlib import Path

from psd2_tracker.archive import Archive
from psd2_tracker.tracker import (
    ROOT, Fetcher, Observation, collect_mbank_history, observation_row,
    timeseries_row, write_timeseries, write_outputs, write_dashboard_data,
    write_trend_svg, update_readme, stable_json, MBANK_SUMMARY_METHOD,
)


def main():
    data_dir = ROOT / "data"
    dashboard_path = ROOT / "dashboard/data.js"
    dashboard = json.loads(dashboard_path.read_text().removeprefix("window.PSD2_DATA = ").rstrip().removesuffix(";"))
    before_history = json.loads((data_dir / "timeseries.json").read_text())
    before_daily = json.loads((data_dir / "daily-history.json").read_text())
    before_latest = json.loads((data_dir / "latest.json").read_text())
    bank = next(row for row in json.loads((ROOT / "config/banks.json").read_text()) if row["id"] == "mbank")
    reports = {row["report_url"]: row for key, detail in dashboard["source_details"].items() if key.startswith("mbank:") for row in detail.get("published_reports", [])}
    archive = Archive(data_dir / "archive", date.today())
    # Fail before writing if any original document was not retained.
    for report in reports.values():
        if archive.response_content("mbank", report["report_url"]) is None:
            raise ValueError(f"Missing retained PDF: {report['report_url']}")
    fetcher = Fetcher(archive=archive)
    fetcher.bank_id = "mbank"
    periods = {period for report in reports.values() for period in report.get("periods", [report["period"]])}
    imported = collect_mbank_history(bank, fetcher, periods, list(reports.values()))
    if len(imported) != len(periods) or len({item.latest_period for item in imported}) != len(imported):
        raise ValueError("Incomplete or overlapping mBank extraction")
    imported.sort(key=lambda item: item.latest_period)
    latest_mbank = imported[-1]
    catalog = [{**row, "country_scope": "unverified", "report_kind": "summary", "metric_method": MBANK_SUMMARY_METHOD, "note": bank["note"]} for row in reports.values()]
    latest_mbank.report_details = {"country_scope": "unverified", "catalog_url": bank["source_url"], "published_reports": catalog}
    allowed = {field.name for field in fields(Observation)}
    observations = []
    for row in before_latest:
        if row["bank_id"] == "mbank":
            observations.append(latest_mbank)
        else:
            detail = dashboard["source_details"].get(f"{row['bank_id']}:{row.get('latest_period', '')}")
            values = {key: (None if value == "" and key.endswith(("_pct", "_ms")) else value) for key, value in row.items() if key in allowed}
            observations.append(Observation(**values, report_details=detail))
    history = sorted([row for row in before_history if row["bank_id"] != "mbank"] + [timeseries_row(item) for item in imported], key=lambda row: (row["period"], row["bank"]))
    for item in imported:
        archive.record_daily(item)
        archive.record_snapshot(timeseries_row(item), "quarterly-report")
    archive.record_snapshot({**observation_row(latest_mbank), "report_details": latest_mbank.report_details}, "latest-check")
    write_outputs(observations, data_dir, date.today())
    write_timeseries(history, data_dir)
    archive.export(data_dir)
    write_dashboard_data(observations, history, dashboard["expected_period"], date.today(), archive=archive)
    # Retained older catalog metadata must not claim the new numbers are excluded.
    payload = json.loads(dashboard_path.read_text().removeprefix("window.PSD2_DATA = ").rstrip().removesuffix(";"))
    for key, detail in payload["source_details"].items():
        if key.startswith("mbank:"):
            for row in detail.get("published_reports", []):
                row.update(country_scope="unverified", report_kind="summary", metric_method=MBANK_SUMMARY_METHOD, note=bank["note"])
    dashboard_path.write_text("window.PSD2_DATA = " + stable_json(payload))
    write_dashboard_data(observations, history, dashboard["expected_period"], date.today(), archive=archive)
    write_trend_svg(history, dashboard["expected_period"])
    update_readme(ROOT / "README.md", observations, dashboard["expected_period"])
    after_daily = archive.daily_rows()
    if [row for row in after_daily if row["bank_id"] != "mbank"] != [row for row in before_daily if row["bank_id"] != "mbank"]:
        raise ValueError("Unrelated daily data changed")
    after_latest = json.loads((data_dir / "latest.json").read_text())
    after_by_id = {row["bank_id"]: row for row in after_latest}
    for row in before_latest:
        if row["bank_id"] != "mbank" and any(after_by_id[row["bank_id"]][key] != value for key, value in row.items()):
            raise ValueError(f"Unrelated latest values changed: {row['bank_id']}")
    archive.verify()
    print(json.dumps({"documents": len(reports), "quarters": len(imported), "daily_rows": sum(len(item.daily_metrics) for item in imported), "first_day": imported[0].first_day, "last_day": latest_mbank.last_day, "latest": observation_row(latest_mbank), "unrelated_data": "unchanged"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
