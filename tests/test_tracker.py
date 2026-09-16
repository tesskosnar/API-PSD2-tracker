import unittest
import json
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from types import SimpleNamespace
from xml.etree import ElementTree

from psd2_tracker.tracker import (
    Observation,
    apply_csob_workbook,
    average_active_response,
    carry_previous,
    collect_timeseries,
    extract_balanced_json,
    extract_borderless_creditas_table,
    expected_report_period,
    finalize_status,
    parse_pdf_metrics,
    parse_pdf_daily,
    parse_partners,
    find_rb_reports,
    parse_rb_report,
    parse_rb,
    rb_report_text,
    parse_report_links,
    collect_pdf_history,
    parse_first_xlsx_sheet,
    parse_quarter,
    parse_unicredit_quarters,
    previous_quarter,
    quarter_range,
    recent_quarters,
    write_trend_svg,
    write_dashboard_data,
)


class TrackerTests(unittest.TestCase):
    def test_mbank_static_report_link_does_not_invent_a_confirmed_czech_quarter(self):
        bank = {"id": "mbank", "name": "mBank", "source_url": "https://developer.api.mbank.cz/reports"}
        fetcher = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(text='<a href="/availability-Q2-2026.pdf">report Q2 2026</a>', url=bank['source_url']))
        item = parse_report_links(bank, fetcher)
        self.assertEqual(item.latest_period, "")
        self.assertIsNone(item.availability_pct)
        self.assertIn("cesky rozsah", item.metric_method)

    def test_rb_zipped_pdf_ignores_macos_metadata_and_rejects_ambiguous_archive(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as packed:
            packed.writestr("source.pdf", b"%PDF-example")
            packed.writestr("__MACOSX/._source.pdf", b"metadata")
        with patch("psd2_tracker.tracker.extract_rb_pdf_text", return_value="report"):
            text, note = rb_report_text(buffer.getvalue())
        self.assertEqual(text, "report")
        self.assertIn("ZIP", note)
        with zipfile.ZipFile(buffer, "a") as packed:
            packed.writestr("second.pdf", b"%PDF-example")
        with self.assertRaisesRegex(ValueError, "jednoznacny"):
            rb_report_text(buffer.getvalue())

    def test_rb_docx_tables_use_daily_dates_and_disclose_conflicting_header(self):
        buffer = BytesIO()
        cells = ["01.07.2021", "759.0439", "90", "99,85%", "728,009", "0", "100,00%"]
        row = "".join(f"<w:tc><w:p><w:r><w:t>{value}</w:t></w:r></w:p></w:tc>" for value in cells)
        xml = f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Statistiky 1.6.2020 – 30.9.2020</w:t></w:r></w:p><w:p><w:r><w:t>AISP odezva PISP odezva</w:t></w:r></w:p><w:tbl><w:tr>{row}</w:tr></w:tbl></w:body></w:document>'
        with zipfile.ZipFile(buffer, "w") as packed:
            packed.writestr("word/document.xml", xml)
        bank = {"id": "rb", "name": "RB", "source_url": "https://www.rb.cz"}
        fetcher = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(content=buffer.getvalue()))
        item = parse_rb_report(bank, "2021-Q3", "https://www.rb.cz/source.pdf", fetcher)
        self.assertEqual(item.aisp_availability_pct, 99.85)
        self.assertEqual(item.daily_metrics[0]["date"], "2021-07-01")
        self.assertIn("hlavicka uvadi 2020-06-01, 2020-09-30", item.metric_method)
        self.assertIn("Word", item.metric_method)
        self.assertIsNone(item.aisp_response_ms)

    def test_rb_split_response_digits_and_missing_first_service_keep_columns(self):
        text = "AISP odezva PISP odezva\n01.07.2020 74 4,1016 17 99,87 % 631 0 100,00 %\n02.07.2020 N/A N/A N/A 500 1 99,00%"
        bank = {"id": "rb", "name": "RB", "source_url": "https://www.rb.cz"}
        fetcher = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(content=b"%PDF"))
        with patch("psd2_tracker.tracker.extract_rb_pdf_text", return_value=text):
            item = parse_rb_report(bank, "2020-Q3", "https://www.rb.cz/source.pdf", fetcher)
        self.assertEqual(item.daily_metrics[0]["aisp_response_reported_without_unit"], 744.1016)
        self.assertEqual(item.daily_metrics[0]["pisp_availability_pct"], 100)
        self.assertNotIn("aisp_availability_pct", item.daily_metrics[1])
        self.assertEqual(item.daily_metrics[1]["pisp_availability_pct"], 99)

    def test_rb_catalogue_includes_archived_names_but_not_foreign_or_other_pdfs(self):
        bank = {"source_url": "https://www.rb.cz/documents", "report_search_url": "https://www.rb.cz/search", "report_search_queries": ["statistiky", "legacy"]}
        items = [{"title": "statistiky-vykonu-Q1-2021", "url": "/attachments/infopovinnost/statistiky-vykonu-Q1-2021.pdf"},
                 {"title": "report Q1 2026", "url": "https://foreign.test/report.pdf"},
                 {"title": "terms", "url": "/attachments/terms.pdf"},
                 {"title": "statistiky", "url": "/attachments/infopovinnost/statistiky-vykonu-rozhrani-otevrenehho-bankovnictvi.pdf"}]
        fetcher = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(json=lambda: {"attachmentResults": {"results": items}}))
        reports = find_rb_reports(bank, fetcher)
        self.assertEqual(len(reports), 2)
        self.assertEqual(reports[0][0], "2021-Q1")
        self.assertEqual(reports[1][0], "")

    def test_rb_preserves_separate_availability_and_derives_errors_from_calls_only(self):
        text = "Statistiky\n1.7.2024 – 30.9.2024\nDatum PISP volání PISP chyb Dostupnost AISP volání AISP chyb Dostupnost\n01.07.2024 100 1 99,00% 1000 2 99,80%\n02.07.2024 300 0 100,00% 0 0 100,00%"
        bank = {"id": "rb", "name": "RB", "source_url": "https://www.rb.cz"}
        fetcher = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(content=b"%PDF"))
        with patch("psd2_tracker.tracker.extract_rb_pdf_text", return_value=text):
            item = parse_rb_report(bank, "2024-Q3", "https://www.rb.cz/report.pdf", fetcher)
        self.assertIsNone(item.availability_pct)
        self.assertEqual(item.aisp_availability_pct, 99.9)
        self.assertEqual(item.pisp_availability_pct, 99.5)
        self.assertEqual(item.pisp_error_pct, .25)  # total errors / calls, not mean daily ratios
        self.assertEqual(item.aisp_error_pct, .2)
        self.assertIsNone(item.daily_metrics[1]["aisp_error_pct"])
        self.assertIsNone(item.aisp_response_ms)

    def test_rb_legacy_does_not_invent_response_units_or_error_denominators(self):
        text = "Datum AISP PISP\nAISP odezva AISP počet chyb AISP dostupnost PISP odezva PISP počet chyb PISP dostupnost\n1 1. 04. 2020 615 44 99,87 % 494 2 99,68 %\n12. 04. 2020 0 0 0,00 % N/A N/A"
        bank = {"id": "rb", "name": "RB", "source_url": "https://www.rb.cz"}
        fetcher = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(content=b"%PDF"))
        with patch("psd2_tracker.tracker.extract_rb_pdf_text", return_value=text):
            item = parse_rb_report(bank, "", "https://www.rb.cz/report.pdf", fetcher)
        self.assertEqual(item.latest_period, "2020-Q2")
        self.assertEqual(item.daily_metrics[0]["date"], "2020-04-11")
        self.assertEqual(item.daily_metrics[1]["aisp_availability_pct"], 0)
        self.assertIsNone(item.aisp_response_ms)
        self.assertIsNone(item.aisp_error_pct)
        self.assertEqual(item.daily_metrics[0]["aisp_response_reported_without_unit"], 615)

    def test_rb_rejects_mislabelled_year_and_uses_previous_verified_report(self):
        bank = {"id": "rb", "name": "RB", "source_url": "https://www.rb.cz"}
        fetcher = SimpleNamespace(get=lambda *a, **k: SimpleNamespace(content=b"%PDF"))
        text = "Statistiky 1.7.2025 – 30.9.2025\nDatum PISP volání PISP chyb Dostupnost AISP volání AISP chyb Dostupnost\n01.07.2024 100 0 100,00% 1000 0 100,00%"
        with patch("psd2_tracker.tracker.extract_rb_pdf_text", return_value=text):
            with self.assertRaisesRegex(ValueError, "obsahuje den 2024-07-01"):
                parse_rb_report(bank, "2025-Q3", "https://www.rb.cz/report.pdf", fetcher)
        previous = Observation(bank_id="rb", bank="RB", scope="main", source_url=bank["source_url"], latest_period="2025-Q1", aisp_availability_pct=99)
        with patch("psd2_tracker.tracker.find_rb_reports", return_value=[("2025-Q3", "bad"), ("2025-Q1", "good")]), patch("psd2_tracker.tracker.parse_rb_report", side_effect=[ValueError("year mismatch"), previous]):
            item = parse_rb(bank, fetcher)
        self.assertEqual(item.latest_period, "2025-Q1")
        self.assertIn("year mismatch", item.note)

    def test_trinity_legacy_percent_without_sign_is_supported(self):
        text = "Tar_01_PSD_API 01.10.2021 7200 8,3 91,7 n/a n/a\nTar_02_PSD_API 01.10.2021 7200 8,3 91,7 n/a n/a"
        with patch("psd2_tracker.tracker.extract_pdf_text", return_value=text):
            self.assertEqual(parse_pdf_metrics(b"", "trinity")["availability_pct"], 91.7)
            daily = parse_pdf_daily(b"", "trinity", "2021-Q4")
        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0]["availability_pct"], 91.7)

    def test_daily_air_services_and_duplicate_source_line(self):
        line = "01/01/24 1440 1440 46 52 1 0,01% 0,02% 0,00%"
        with patch("psd2_tracker.tracker.extract_pdf_text", return_value=line+"\n"+line):
            daily = parse_pdf_daily(b"", "standard_minutes_air", "2024-Q1")
        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0]["aisp_response_ms"], 52)
        self.assertEqual(daily[0]["pisp_response_ms"], 46)
        self.assertEqual(daily[0]["aisp_error_pct"], .02)
        self.assertEqual(daily[0]["availability_pct"], 100)

    def test_daily_conflicting_duplicates_and_foreign_period_are_rejected(self):
        text = "01.04.2026 1 2 3 4 5 6\n01.04.2026 2 2 3 4 5 6"
        with patch("psd2_tracker.tracker.extract_pdf_text", return_value=text):
            with self.assertRaisesRegex(ValueError, "Konfliktni"):
                parse_pdf_daily(b"", "ppf", "2026-Q2")
            with self.assertRaisesRegex(ValueError, "nesouhlasi"):
                parse_pdf_daily(b"", "ppf", "2026-Q1")

    def test_creditas_daily_keeps_empty_metrics_and_never_uses_downtime_as_error(self):
        tables = [[['Date','AISP','PISP','Uptime','POMER_VYPADKU'],['01.04.2026','123',None,'99.5','0.5']]]
        with patch("psd2_tracker.tracker.extract_creditas_tables", return_value=tables):
            daily = parse_pdf_daily(b"", "creditas", "2026-Q2")
        self.assertEqual(daily[0]['aisp_response_ms'],123)
        self.assertIsNone(daily[0]['pisp_response_ms'])
        self.assertEqual(daily[0]['availability_pct'],99.5)
        self.assertNotIn('shared_error_pct',daily[0])

    def test_pdf_archive_follows_only_same_host_next_link(self):
        bank = {"id":"x", "name":"X", "scope":"main", "source_url":"https://example.test/reports", "history_follow_next":True}
        pages = {
            bank["source_url"]: '<a rel="next" href="?page=2">Next</a><a rel="next" href="https://foreign.test/reports">No</a>',
            bank["source_url"]+"?page=2": '<a href="2025-q1.pdf">PSD2 report Q1 2025</a>'
        }
        fetcher = SimpleNamespace(get=lambda url: SimpleNamespace(text=pages[url],content=pages[url].encode(),url=url))
        item = Observation(bank_id="x",bank="X",scope="main",source_url=bank["source_url"])
        with patch("psd2_tracker.tracker.parse_pdf_observation", return_value=item) as parse:
            collect_pdf_history(bank, fetcher, {"2025-Q1"})
        self.assertEqual(parse.call_args.args[1], "2025-Q1")

    def test_partners_daily_healthcheck_is_not_quarterly_rts_report(self):
        from datetime import timedelta
        from html import escape
        days=[date(2026,9,15)-timedelta(days=29-index) for index in range(30)]
        chart={"data":{"labels":[f"{day.day}.{day.month}." for day in days],"datasets":[{"label":"Dostupnost [%]","data":[99.9]*30}]}}
        source=f'<div class="card"><h5>PSD2 status</h5><canvas data-symfony--ux-chartjs--chart-view-value="{escape(json.dumps(chart),quote=True)}"></canvas></div>'
        bank={"id":"partners","name":"Partners", "source_url":"https://example.test"}
        item=parse_partners(bank,SimpleNamespace(get=lambda url:SimpleNamespace(content=source.encode())),date(2026,9,16))
        item=finalize_status(item,"2026-Q2")
        self.assertEqual(item.latest_period,"rolling-30d-to-2026-09-15")
        self.assertEqual(item.status,"partial")
        self.assertEqual(len(item.daily_metrics),30)
        self.assertEqual(item.availability_pct,99.9)

    def test_invalid_percentage_cannot_be_published(self):
        observation = Observation(bank_id="x", bank="X", scope="main", source_url="https://example.test", latest_period="2026-Q2", aisp_error_pct=720)
        with self.assertRaisesRegex(ValueError, "Neplatna hodnota"):
            finalize_status(observation, "2026-Q2")

    def test_failed_source_keeps_previous_metrics_but_stays_blocked(self):
        current = Observation(
            bank_id="x",
            bank="X",
            scope="main",
            source_url="https://example.test",
            source_state="http-403",
        )
        previous = {
            "latest_period": "2026-Q2",
            "availability_pct": 99.9,
            "report_url": "https://example.test/report.pdf",
            "metric_method": "published uptime",
        }
        result = finalize_status(carry_previous(current, previous), "2026-Q2")
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.availability_pct, 99.9)

    def test_parse_first_xlsx_sheet(self):
        workbook = b'''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Data" sheetId="1" r:id="rId1"/></sheets></workbook>'''
        relationships = b'''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>'''
        shared = b'''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Header</t></si></sst>'''
        sheet = b'''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="C1"><v>123.5</v></c></row></sheetData></worksheet>'''
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("xl/workbook.xml", workbook)
            archive.writestr("xl/_rels/workbook.xml.rels", relationships)
            archive.writestr("xl/sharedStrings.xml", shared)
            archive.writestr("xl/worksheets/sheet1.xml", sheet)
        self.assertEqual(parse_first_xlsx_sheet(buffer.getvalue()), [{"A": "Header", "C": "123.5"}])

    def test_extract_balanced_json_keeps_outer_object(self):
        source = 'before var kpiData = {"CZ":{"Dedicated Interface":{}}}; after'
        self.assertEqual(
            extract_balanced_json(source, "var kpiData = {"),
            {"CZ": {"Dedicated Interface": {}}},
        )

    def test_unicredit_accepts_both_formats_and_selects_czech_entity(self):
        month = {"year": 2026, "date": "APRIL", "uptime": "100", "ais": "329.75", "pis": "220.24", "error_response_rate": "0.07"}
        data = {"IT": {"Dedicated Interface": {"0": {**month, "ais": "999"}}}, "SK-B": {"Dedicated Interface": {"0": {**month, "ais": "888"}}}, "CZ": {"Dedicated Interface": {"0": {**month, "ais": "777"}}}, "CZ-B": {"Dedicated Interface": {"0": month}}}
        bank = {"id": "unicredit", "name": "UniCredit Bank", "scope": "main", "source_url": "https://example.test/report"}
        for source in (f"var kpiData = {json.dumps(data)};", f"var kpiData = JSON.parse('{json.dumps(data)}');"):
            with self.subTest(source_format=source[:30]):
                fetcher = SimpleNamespace(get=lambda url: SimpleNamespace(text=source))
                result = parse_unicredit_quarters(bank, fetcher)[0]
                self.assertEqual(result.aisp_response_ms, 329.75)
                self.assertEqual(result.report_details["country_code"], "CZ-B")
                self.assertEqual(result.report_details["months"][0]["month"], "2026-04")

    def test_unicredit_never_falls_back_to_foreign_country(self):
        bank = {"id": "unicredit", "name": "UniCredit Bank", "scope": "main", "source_url": "https://example.test/report"}
        fetcher = SimpleNamespace(get=lambda url: SimpleNamespace(text='var kpiData = {"SK-B":{"Dedicated Interface":{}}};'))
        with self.assertRaisesRegex(ValueError, "CZ Dedicated Interface"):
            parse_unicredit_quarters(bank, fetcher)

    def test_unicredit_czech_quarter_averages_published_months(self):
        months = [
            {"year": 2026, "date": "APRIL", "uptime": 100, "ais": 329.75, "pis": 220.24, "error_response_rate": .07},
            {"year": 2026, "date": "MAY", "uptime": 100, "ais": 367.37, "pis": 299.84, "error_response_rate": .2},
            {"year": 2026, "date": "JUNE", "uptime": 100, "ais": 338.75, "pis": 225.89, "error_response_rate": .2},
        ]
        bank = {"id": "unicredit", "name": "UniCredit Bank", "scope": "main", "source_url": "https://example.test/report"}
        source = "var kpiData = " + json.dumps({"CZ": {"Dedicated Interface": {str(i): month for i, month in enumerate(months)}}})
        result = parse_unicredit_quarters(bank, SimpleNamespace(get=lambda url: SimpleNamespace(text=source)))[0].rounded()
        self.assertEqual(result.latest_period, "2026-Q2")
        self.assertEqual(result.availability_pct, 100)
        self.assertEqual(result.aisp_response_ms, 345.29)
        self.assertEqual(result.pisp_response_ms, 248.6567)
        self.assertEqual(result.aisp_error_pct, .1567)
        self.assertEqual(result.report_details["country_code"], "CZ")

    def test_dashboard_preserves_archived_source_details_and_refreshes_both_pages(self):
        observation = Observation(bank_id="unicredit", bank="UniCredit Bank", scope="main", source_url="https://example.test", latest_period="2026-Q2", report_details={"country_code": "CZ-B"})
        with TemporaryDirectory() as directory:
            output = Path(directory) / "data.js"
            for filename in ("index.html", "report.html"):
                (output.parent / filename).write_text('<script src="data.js"></script>', encoding="utf-8")
            write_dashboard_data([observation], [], "2026-Q2", date(2026, 9, 16), output)
            observation.latest_period = "2026-Q3"
            observation.report_details = None
            write_dashboard_data([observation], [], "2026-Q3", date(2026, 10, 16), output)
            payload = json.loads(output.read_text().removeprefix("window.PSD2_DATA = "))
            self.assertEqual(payload["source_details"]["unicredit:2026-Q2"]["country_code"], "CZ-B")
            self.assertNotIn("report_details", payload["latest"][0])
            self.assertEqual((output.parent / "index.html").read_text(), (output.parent / "report.html").read_text())
            self.assertIn('data.js?v=', (output.parent / "report.html").read_text())

    def test_parse_quarter_variants(self):
        cases = {
            "Statistiky pro 2Q 2026": "2026-Q2",
            "kb-psd2-2026-q2-cz.pdf": "2026-Q2",
            "PSD2_2026Q2.pdf": "2026-Q2",
            "Dostupnost API - II.Q / 2026": "2026-Q2",
            "Q2-2026_psd2_unavailability.pdf": "2026-Q2",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(parse_quarter(source), expected)

    def test_expected_period_uses_publication_grace(self):
        self.assertEqual(expected_report_period(date(2026, 7, 20)), "2026-Q1")
        self.assertEqual(expected_report_period(date(2026, 9, 11)), "2026-Q2")

    def test_previous_quarter_crosses_year(self):
        self.assertEqual(previous_quarter("2026-Q1"), "2025-Q4")
        self.assertEqual(previous_quarter("2026-Q2", 2), "2025-Q4")
        self.assertEqual(recent_quarters("2026-Q2", 4), ["2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2"])
        self.assertEqual(quarter_range("2019-Q3", "2020-Q2"), ["2019-Q3", "2019-Q4", "2020-Q1", "2020-Q2"])

    def test_zero_response_is_not_instant_api_call(self):
        self.assertEqual(average_active_response([0, 100, 200]), 150)
        self.assertIsNone(average_active_response([0, 0, None]))

    def test_standard_minutes_pdf_layout(self):
        text = """
        1.4.2026 1440 1440 0 0 100 100 100 0% 0% 0%
        2.4.2026 1440 720 0 720 100 100 100 0% 0% 0%
        """
        with patch("psd2_tracker.tracker.extract_pdf_text", return_value=text):
            result = parse_pdf_metrics(b"fake", "standard_minutes")
        self.assertAlmostEqual(result["availability_pct"], 75.0)

    def test_trinity_pdf_layout_averages_services_and_days(self):
        text = """
        Tarvos_PSD_01_API 01.04.2026 0 0,0% 100,0% n/a n/a
        Tarvos_PSD_02_API 01.04.2026 300 0,3% 99,7% n/a n/a
        """
        with patch("psd2_tracker.tracker.extract_pdf_text", return_value=text):
            result = parse_pdf_metrics(b"fake", "trinity")
        self.assertAlmostEqual(result["availability_pct"], 99.85)

    def test_creditas_pdf_layout_uses_penultimate_trailing_value(self):
        tables = [[
            ["Datum", "AISP average time [ms]", "PISP average time [ms]", "CISP average time [ms]", "Downtime [%]", "Uptime [%]", "Poměr výpadků"],
            ["01.04.2026", "194,00", "685,00", None, "0,00", "100,00", "0,19"],
            ["02.04.2026", "194,00", "683,00", None, "1,00", "99,00", "0,36"],
            ["03.04.2026", None, "728,00", None, "0,00", "100,00", "0,00"],
        ]]
        with patch("psd2_tracker.tracker.extract_creditas_tables", return_value=tables):
            result = parse_pdf_metrics(b"fake", "creditas")
        self.assertAlmostEqual(result["availability_pct"], (100 + 99 + 100) / 3)
        self.assertAlmostEqual(result["aisp_response_ms"], 194)
        self.assertAlmostEqual(result["pisp_response_ms"], (685 + 683 + 728) / 3)
        self.assertIsNone(result["aisp_error_pct"])

    def test_creditas_legacy_pdf_layout(self):
        tables = [[
            ["Date", "AISP average time [ms]", "PISP average time [ms]", "CISP average time [ms]", "Uptime [%]", "Downtime [%]", "Error response rate [%]"],
            ["01.07.2019", "645", "653", None, "96%", "3,740%", "0,09%"],
            ["02.07.2019", "1 816", "347", None, "100%", None, "0,41%"],
            ["03.07.2019", "81", "569", None, "98%", "2,00%", "0,02%"],
        ]]
        with patch("psd2_tracker.tracker.extract_creditas_tables", return_value=tables):
            result = parse_pdf_metrics(b"fake", "creditas")
        self.assertAlmostEqual(result["availability_pct"], 98)
        self.assertAlmostEqual(result["aisp_response_ms"], (645 + 1816 + 81) / 3)
        self.assertAlmostEqual(result["pisp_response_ms"], (653 + 347 + 569) / 3)
        self.assertAlmostEqual(result["aisp_error_pct"], (0.09 + 0.41 + 0.02) / 3)

    def test_creditas_empty_error_does_not_shift_uptime(self):
        tables = [[
            ["Date", "AISP average time [ms]", "PISP average time [ms]", "CISP average time [ms]", "Downtime [%]", "Uptime [%]", "Error response rate [%]"],
            ["01.07.2021", "129", None, None, "0,00", "100,00", None],
            ["02.07.2021", None, "573", None, "0,00", "100,00", "0,01"],
        ]]
        with patch("psd2_tracker.tracker.extract_creditas_tables", return_value=tables):
            result = parse_pdf_metrics(b"fake", "creditas")
        self.assertEqual(result["availability_pct"], 100)
        self.assertEqual(result["aisp_response_ms"], 129)
        self.assertEqual(result["pisp_response_ms"], 573)

    def test_jt_pdf_layout_reads_uptime_from_tail(self):
        text = """
        01.04.2026 0 283,33 0 0 100 0
        02.04.2026 1482 297,88 0 0,1 80 20
        """
        with patch("psd2_tracker.tracker.extract_pdf_text", return_value=text):
            result = parse_pdf_metrics(b"fake", "jt")
        self.assertAlmostEqual(result["availability_pct"], 90.0)
        self.assertAlmostEqual(result["aisp_response_ms"], (283.33 + 297.88) / 2)
        self.assertEqual(result["pisp_response_ms"], 1482)
        self.assertAlmostEqual(result["aisp_error_pct"], 5.0)

    def test_ppf_ignores_zero_traffic_days_for_error_rate(self):
        text = """
        01.03.2026 0 0% 0 0% 0 0%
        02.03.2026 146 100% 0 0% 0 0%
        03.03.2026 209 100% 0 0% 0 0%
        """
        with patch("psd2_tracker.tracker.extract_pdf_text", return_value=text):
            result = parse_pdf_metrics(b"fake", "ppf")
        self.assertEqual(result["aisp_error_pct"], 100)
        self.assertIsNone(result["pisp_error_pct"])

    def test_csob_xlsx_error_ratio_is_converted_to_percent(self):
        observation = Observation(bank_id="csob", bank="ČSOB", scope="main", source_url="https://example.test")
        rows = [
            {"C": "PSD2 AISP › Response time", "D": "PSD2 AISP › Error rate", "F": "PSD2 PISP › Response time", "G": "PSD2 PISP › Error rate"},
            {"A": "46113", "C": "200", "D": "0.05", "F": "300", "G": "0.01"},
        ]
        with patch("psd2_tracker.tracker.parse_first_xlsx_sheet", return_value=rows):
            result = apply_csob_workbook(observation, b"fake")
        self.assertEqual(result.aisp_error_pct, 5)
        self.assertEqual(result.pisp_error_pct, 1)

    def test_csob_legacy_columns_and_total_row(self):
        observation = Observation(bank_id="csob", bank="ČSOB", scope="main", source_url="https://example.test")
        rows = [
            {"B": "PSD2 AISP", "D": "PSD2 CISP", "F": "PSD2 PISP"},
            {"A": "2021-01-01", "B": "650", "C": "0.06", "D": "836", "F": "740", "G": "0.02"},
            {"A": "Celkový součet", "B": "9999", "C": "1", "F": "9999", "G": "1"},
        ]
        with patch("psd2_tracker.tracker.parse_first_xlsx_sheet", return_value=rows):
            result = apply_csob_workbook(observation, b"fake")
        self.assertEqual(result.aisp_response_ms, 650)
        self.assertEqual(result.pisp_response_ms, 740)
        self.assertEqual(result.aisp_error_pct, 6)
        self.assertEqual(result.pisp_error_pct, 2)

    def test_csob_merged_headers_include_calls(self):
        observation = Observation(bank_id="csob", bank="ČSOB", scope="main", source_url="https://example.test")
        rows = [
            {"B": "PSD2 AISP", "E": "PSD2 PISP"},
            {"B": "Call", "C": "Response time", "D": "Error rate", "E": "Call", "F": "Response time", "G": "Error rate"},
            {"A": "44743", "B": "220.261", "C": "730.571", "D": "0.05", "E": "4.458", "F": "797.422", "G": "0.01"},
        ]
        with patch("psd2_tracker.tracker.parse_first_xlsx_sheet", return_value=rows):
            result = apply_csob_workbook(observation, b"fake")
        self.assertEqual(result.aisp_response_ms, 730.571)
        self.assertEqual(result.pisp_response_ms, 797.422)
        self.assertEqual(result.aisp_error_pct, 5)
        self.assertEqual(result.pisp_error_pct, 1)

    def test_standard_minutes_ignores_page_footer_numbers(self):
        text = "1.4.2026 1440 1440 0 0 323 332 363 0,04% 0,14% 0,00%\nKomerční banka 33 969 114 07 45317054 2 / 4\n2.4.2026 1440 1440 0 0 349 363 361 0,01% 0,14% 0,00%"
        with patch("psd2_tracker.tracker.extract_pdf_text", return_value=text):
            result = parse_pdf_metrics(b"fake", "standard_minutes_kb")
        self.assertEqual(result["aisp_response_ms"], 336)
        self.assertAlmostEqual(result["aisp_error_pct"], .025)

    def test_creditas_borderless_preserves_empty_columns_and_page_layout(self):
        from types import SimpleNamespace
        header = "DateAISP average time [ms]PISP average time [ms]CISP average time [ms]Downtime [%]Uptime [%]Error response rate [%]"
        starts = {"Date": 50, "AISP": 110, "PISP": 230, "CISP": 350, "Downtime": 470, "Uptime": 535, "Error": 620}
        chars = []
        column_start = 50
        for index, char in enumerate(header):
            for label, start in starts.items():
                if header.startswith(label, index):
                    column_start = start
            chars.append({"text": char, "x0": column_start, "top": 58})
        words = [
            {"text": "01.10.2021", "x0": 55, "x1": 105, "top": 72},
            {"text": "30", "x0": 185, "x1": 195, "top": 72},
            {"text": "782,00", "x0": 199, "x1": 229, "top": 72},
            {"text": "0,00", "x0": 511, "x1": 531, "top": 72},
            {"text": "100,00", "x0": 584, "x1": 615, "top": 72},
            {"text": "0,03", "x0": 718, "x1": 738, "top": 72},
        ]
        page = SimpleNamespace(chars=chars, width=842, extract_words=lambda: words)
        table, layout = extract_borderless_creditas_table(page)
        self.assertEqual(table[1], ["01.10.2021", "30 782,00", None, None, "0,00", "100,00", "0,03"])
        page.chars = []
        self.assertEqual(extract_borderless_creditas_table(page, layout)[0][1], table[1])

    def test_air_archive_without_line_breaks(self):
        text = "Den Response 01.01.19 1440 1440 56 115 1 0,00% 0,03% 0,00% 02.01.19 1410 1410 30 30 25 989 1 0,10% 0,09% 0,00%"
        with patch("psd2_tracker.tracker.extract_pdf_text", return_value=text):
            result = parse_pdf_metrics(b"fake", "standard_minutes_air")
        self.assertAlmostEqual(result["availability_pct"], (1440 + 1410) / 2880 * 100)
        self.assertEqual(result["aisp_response_ms"], 552)
        self.assertEqual(result["pisp_response_ms"], 40.5)
        self.assertEqual(result["aisp_error_pct"], 0.06)
        self.assertEqual(result["pisp_error_pct"], 0.05)

    def test_history_requires_a_report_link(self):
        bank = {"id": "rb", "name": "Raiffeisenbank", "scope": "main", "parser": "report_links", "source_url": "https://example.test"}
        latest = Observation(bank_id="rb", bank="Raiffeisenbank", scope="main", source_url="https://example.test", latest_period="2024-Q3", availability_pct=100)
        cached = [{"bank_id": "rb", "bank": "Raiffeisenbank", "period": "2024-Q3", "availability_pct": 100, "report_url": ""}]
        rows = collect_timeseries([bank], object(), [latest], "2026-Q2", cached)
        self.assertEqual(rows, [])

    def test_failed_historical_report_is_retried(self):
        bank = {"id": "air", "name": "Air Bank", "scope": "main", "parser": "pdf_links", "source_url": "https://example.test", "history_start_period": "2026-Q2"}
        cached = [{"bank_id": "air", "bank": "Air Bank", "scope": "main", "period": "2026-Q2", "source_state": "report-error", "report_url": "https://example.test/report.pdf"}]
        recovered = Observation(bank_id="air", bank="Air Bank", scope="main", source_url=bank["source_url"], latest_period="2026-Q2", report_url=cached[0]["report_url"], availability_pct=99.9)
        with patch("psd2_tracker.tracker.collect_pdf_history", return_value=[recovered]) as collect:
            rows = collect_timeseries([bank], object(), [], "2026-Q2", cached)
        collect.assert_called_once()
        self.assertEqual(rows[0]["availability_pct"], 99.9)

    def test_public_report_is_kept_even_without_measurable_traffic(self):
        cached = [{"bank_id": "ppf", "bank": "PPF banka", "period": "2025-Q1", "report_url": "https://example.test/report.pdf", "aisp_error_pct": "0", "pisp_error_pct": "0"}]
        bank = {"id": "ppf", "name": "PPF banka", "scope": "main", "parser": "report_links", "source_url": "https://example.test", "history_start_period": "2024-Q1"}
        rows = collect_timeseries([bank], object(), [], "2026-Q2", cached)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["report_url"], "https://example.test/report.pdf")

    def test_readme_trend_svg_escapes_names_and_breaks_missing_quarters(self):
        rows = [
            {"bank": "Bank & Test", "scope": "main", "report_url": "https://example.test/q3.pdf", "period": "2025-Q3", "availability_pct": 99.1},
            {"bank": "Bank & Test", "scope": "main", "report_url": "https://example.test/q1.pdf", "period": "2026-Q1", "availability_pct": 99.8},
        ]
        with TemporaryDirectory() as directory:
            output = Path(directory) / "trend.svg"
            write_trend_svg(rows, "2026-Q2", output)
            source = output.read_text(encoding="utf-8")
            root = ElementTree.fromstring(source)
        self.assertIn("Bank &amp; Test", source)
        path = root.find("{http://www.w3.org/2000/svg}path")
        self.assertIsNotNone(path)
        self.assertEqual(path.attrib["d"].count("M"), 2)


if __name__ == "__main__":
    unittest.main()
