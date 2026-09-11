import unittest
import zipfile
from datetime import date
from io import BytesIO
from unittest.mock import patch

from psd2_tracker.tracker import (
    Observation,
    carry_previous,
    extract_balanced_json,
    expected_report_period,
    finalize_status,
    parse_pdf_metrics,
    parse_first_xlsx_sheet,
    parse_quarter,
    previous_quarter,
)


class TrackerTests(unittest.TestCase):
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
        text = """
        01.04.2026 194,00 685,00

        0,00 100,00 0,19
        02.04.2026 194,00 683,00 1,00 99,00 0,36
        """
        with patch("psd2_tracker.tracker.extract_pdf_text", return_value=text):
            result = parse_pdf_metrics(b"fake", "creditas")
        self.assertAlmostEqual(result["availability_pct"], 99.5)

    def test_jt_pdf_layout_reads_uptime_from_tail(self):
        text = """
        01.04.2026 0 283,33 0 0 100 0
        02.04.2026 0 297,88 0 0,1 80 20
        """
        with patch("psd2_tracker.tracker.extract_pdf_text", return_value=text):
            result = parse_pdf_metrics(b"fake", "jt")
        self.assertAlmostEqual(result["availability_pct"], 90.0)
        self.assertAlmostEqual(result["aisp_response_ms"], (283.33 + 297.88) / 2)


if __name__ == "__main__":
    unittest.main()
