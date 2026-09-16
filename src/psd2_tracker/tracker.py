from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import http.cookiejar
import io
import json
import math
import re
import sys
import time
import unicodedata
import zipfile
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse, urlsplit, urlunsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener
from xml.etree import ElementTree
from xml.sax.saxutils import escape as xml_escape
from zoneinfo import ZoneInfo

from lxml import html
from pypdf import PdfReader
import pdfplumber
from .archive import Archive


def discover_project_root() -> Path:
    """Najde pracovní kopii i při spuštění nainstalovaného CLI."""
    candidates = (Path.cwd(), *Path(__file__).resolve().parents)
    for candidate in candidates:
        if (candidate / "config" / "banks.json").is_file():
            return candidate
    return Path.cwd()


ROOT = discover_project_root()
DEFAULT_CONFIG = ROOT / "config" / "banks.json"
DEFAULT_DATA = ROOT / "data"
DEFAULT_README = ROOT / "README.md"
DEFAULT_DASHBOARD_DATA = ROOT / "dashboard" / "data.js"
DEFAULT_TREND_SVG = ROOT / "docs" / "trend.svg"

CSV_FIELDS = [
    "bank_id",
    "bank",
    "scope",
    "status",
    "source_state",
    "latest_period",
    "report_url",
    "availability_pct",
    "aisp_availability_pct",
    "pisp_availability_pct",
    "aisp_response_ms",
    "pisp_response_ms",
    "aisp_error_pct",
    "pisp_error_pct",
    "metric_method",
    "note",
    "source_url",
]

TIMESERIES_FIELDS = [
    "bank_id",
    "bank",
    "scope",
    "period",
    "status",
    "source_state",
    "report_url",
    "availability_pct",
    "aisp_availability_pct",
    "pisp_availability_pct",
    "aisp_response_ms",
    "pisp_response_ms",
    "aisp_error_pct",
    "pisp_error_pct",
    "metric_method",
    "source_url",
]
DERIVED_FIELDS = ["report_kind", "archived_days", "calendar_days", "first_day", "last_day"]

STATUS_LABELS = {
    "ok": "OK",
    "partial": "Částečná data",
    "outdated": "Zastaralé",
    "missing": "Nenalezen report",
    "blocked": "Zdroj blokuje automatizaci",
    "unverified": "Český rozsah neověřen",
}

MONTHS = {
    "JANUARY": 1,
    "FEBRUARY": 2,
    "MARCH": 3,
    "APRIL": 4,
    "MAY": 5,
    "JUNE": 6,
    "JULY": 7,
    "AUGUST": 8,
    "SEPTEMBER": 9,
    "OCTOBER": 10,
    "NOVEMBER": 11,
    "DECEMBER": 12,
}

CREDITAS_REPORT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "Chrome/140.0 Safari/537.36"
    ),
    "Referer": "https://www.creditas.cz/povinne-uverejnovane-informace",
    "Accept": "application/pdf,*/*;q=0.8",
}


class FetchError(RuntimeError):
    def __init__(self, url: str, message: str, status: int | None = None):
        super().__init__(message)
        self.url = url
        self.status = status


@dataclass
class HttpResponse:
    content: bytes
    url: str
    status_code: int
    headers: Any

    @property
    def text(self) -> str:
        content_type = self.headers.get_content_charset() if self.headers else None
        return self.content.decode(content_type or "utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)


@dataclass
class Observation:
    bank_id: str
    bank: str
    scope: str
    source_url: str
    source_state: str = "ok"
    status: str = "missing"
    latest_period: str = ""
    report_url: str = ""
    availability_pct: float | None = None
    aisp_availability_pct: float | None = None
    pisp_availability_pct: float | None = None
    aisp_response_ms: float | None = None
    pisp_response_ms: float | None = None
    aisp_error_pct: float | None = None
    pisp_error_pct: float | None = None
    metric_method: str = ""
    note: str = ""
    report_details: dict[str, Any] | None = None
    daily_metrics: list[dict[str, Any]] | None = None

    def rounded(self) -> "Observation":
        for field in (
            "availability_pct",
            "aisp_availability_pct",
            "pisp_availability_pct",
            "aisp_response_ms",
            "pisp_response_ms",
            "aisp_error_pct",
            "pisp_error_pct",
        ):
            value = getattr(self, field)
            if value is not None:
                number = float(value)
                if not math.isfinite(number) or number < 0 or (field.endswith("_pct") and number > 100):
                    raise ValueError(f"Neplatna hodnota {field}: {value}")
                setattr(self, field, round(number, 4))
        return self


class Fetcher:
    def __init__(self, timeout: float = 45.0, archive: Archive | None = None):
        self.timeout = timeout
        self.archive = archive
        self.bank_id = ""
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.default_headers = {
            "User-Agent": (
                "cz-psd2-api-tracker/0.1 "
                "(+https://github.com/; public regulatory statistics monitor)"
            ),
            "Accept-Language": "cs,en;q=0.8",
        }

    def get(self, url: str, **kwargs: Any) -> HttpResponse:
        timeout = kwargs.pop("timeout", self.timeout)
        params = kwargs.pop("params", None)
        headers = {**self.default_headers, **kwargs.pop("headers", {})}
        if kwargs:
            raise TypeError(f"Nepodporovane parametry HTTP pozadavku: {sorted(kwargs)}")
        if params:
            parts = urlsplit(url)
            query = "&".join(part for part in (parts.query, urlencode(params)) if part)
            url = urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))

        for attempt in range(3):
            try:
                request = Request(url, headers=headers, method="GET")
                with self.opener.open(request, timeout=timeout) as response:
                    content = response.read()
                    result = HttpResponse(
                        content=content,
                        url=response.geturl(),
                        status_code=response.status,
                        headers=response.headers,
                    )
                    if self.archive:
                        self.archive.record_response(self.bank_id, result)
                    return result
            except HTTPError as exc:
                if exc.code in {429, 502, 503, 504} and attempt < 2:
                    time.sleep(0.7 * (attempt + 1))
                    continue
                raise FetchError(url, f"HTTP {exc.code}", exc.code) from exc
            except (URLError, TimeoutError, OSError) as exc:
                if attempt < 2:
                    time.sleep(0.7 * (attempt + 1))
                    continue
                raise FetchError(url, f"{type(exc).__name__}: {exc}") from exc
        raise FetchError(url, "Neznamy problem pri stahovani")


def parse_number(value: str | int | float | None) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = value.strip().replace("\u00a0", "").replace(" ", "").replace("%", "")
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_quarter(value: str) -> str:
    text = value.replace("\\/", "/")
    patterns = [
        r"(?P<q>[1-4])\s*Q\D{0,12}(?P<year>20\d{2})",
        r"Q\s*(?P<q>[1-4])\D{0,12}(?P<year>20\d{2})",
        r"(?P<year>20\d{2})\D{0,12}Q\s*(?P<q>[1-4])",
        r"(?P<year>20\d{2})\D{0,12}(?P<q>[1-4])\s*Q",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return f"{match.group('year')}-Q{match.group('q')}"

    romans = {"I": 1, "II": 2, "III": 3, "IV": 4}
    for pattern in (
        r"(?P<roman>IV|III|II|I)\.?\s*Q\D{0,12}(?P<year>20\d{2})",
        r"(?P<year>20\d{2})\D{0,12}(?P<roman>IV|III|II|I)\.?\s*Q",
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return f"{match.group('year')}-Q{romans[match.group('roman').upper()]}"
    return ""


def quarter_rank(period: str) -> int:
    match = re.fullmatch(r"(20\d{2})-Q([1-4])", period)
    if not match:
        return -1
    return int(match.group(1)) * 4 + int(match.group(2))


def previous_quarter(period: str, steps: int = 1) -> str:
    match = re.fullmatch(r"(20\d{2})-Q([1-4])", period)
    if not match:
        raise ValueError(f"Neplatne ctvrtleti: {period}")
    year, quarter = int(match.group(1)), int(match.group(2))
    for _ in range(steps):
        quarter -= 1
        if quarter == 0:
            year -= 1
            quarter = 4
    return f"{year}-Q{quarter}"


def recent_quarters(latest_period: str, count: int = 8) -> list[str]:
    return [previous_quarter(latest_period, step) for step in reversed(range(count))]


def quarter_range(first_period: str, last_period: str) -> list[str]:
    """Vratí všechna čtvrtletí včetně hranic, chronologicky."""
    first_rank = quarter_rank(first_period)
    last_rank = quarter_rank(last_period)
    if first_rank < 0 or last_rank < 0 or first_rank > last_rank:
        raise ValueError(f"Neplatny rozsah ctvrtleti: {first_period}..{last_period}")
    periods: list[str] = []
    for rank in range(first_rank, last_rank + 1):
        year = (rank - 1) // 4
        quarter = (rank - 1) % 4 + 1
        periods.append(f"{year}-Q{quarter}")
    return periods


def expected_report_period(today: date | None = None, grace_days: int = 45) -> str:
    today = today or date.today()
    current_quarter = (today.month - 1) // 3 + 1
    previous = f"{today.year}-Q{current_quarter - 1}" if current_quarter > 1 else f"{today.year - 1}-Q4"
    year = int(previous[:4])
    quarter = int(previous[-1])
    end_month = quarter * 3
    if end_month == 12:
        quarter_end = date(year, 12, 31)
    else:
        quarter_end = date(year, end_month + 1, 1) - timedelta(days=1)
    return previous if today > quarter_end + timedelta(days=grace_days) else previous_quarter(previous)


def period_from_datetime_range(start: str, end: str) -> str:
    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
    middle = start_dt + (end_dt - start_dt) / 2
    quarter = (middle.month - 1) // 3 + 1
    return f"{middle.year}-Q{quarter}"


def average(values: Iterable[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return fmean(clean) if clean else None


def average_active_response(values: Iterable[float | None]) -> float | None:
    """Nulova odezva znamena den bez volani, nikoli okamzitou odpoved."""
    clean = [float(value) for value in values if value is not None and value > 0]
    return fmean(clean) if clean else None


def extract_balanced_json(source: str, marker: str) -> dict[str, Any]:
    marker_position = source.find(marker)
    if marker_position < 0:
        raise ValueError(f"JSON marker nenalezen: {marker}")
    start = source.find("{", marker_position)
    if start < 0:
        raise ValueError("Zacatek JSON objektu nenalezen")
    depth = 0
    in_string = False
    escaped = False
    for position in range(start, len(source)):
        char = source[position]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return json.loads(source[start : position + 1])
    raise ValueError("Konec JSON objektu nenalezen")


def find_report_candidates(
    source: str, page_url: str, report_pattern: str
) -> list[tuple[int, str, str, str]]:
    pattern = re.compile(report_pattern, re.IGNORECASE)
    raw: list[tuple[str, str]] = []
    try:
        document = html.fromstring(source)
        for anchor in document.xpath("//a[@href]"):
            label = " ".join(" ".join(anchor.itertext()).split())
            href = urljoin(page_url, anchor.get("href", ""))
            raw.append((label, href))
    except (ValueError, TypeError):
        pass

    normalized = source.replace('\\"', '"').replace("\\/", "/")
    asset_pattern = re.compile(
        r'"name":"(?P<name>[^"]+)"\s*,\s*"description":"(?P<description>[^"]*)"'
        r'.{0,350}?"url":"(?P<url>https?://[^"]+)"',
        re.IGNORECASE | re.DOTALL,
    )
    for match in asset_pattern.finditer(normalized):
        raw.append(
            (
                f"{match.group('name')} {match.group('description')}",
                match.group("url"),
            )
        )

    candidates: list[tuple[int, str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for label, href in raw:
        combined = f"{label} {href}"
        if not pattern.search(combined):
            continue
        period = parse_quarter(combined)
        if not period:
            continue
        key = (period, href)
        if key in seen:
            continue
        seen.add(key)
        candidates.append((quarter_rank(period), period, href, label))
    return sorted(candidates, reverse=True)


def extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_creditas_tables(content: bytes) -> list[list[list[str | None]]]:
    with pdfplumber.open(io.BytesIO(content)) as document:
        tables = []
        previous_layout = None
        for page in document.pages:
            page_tables = page.extract_tables()
            usable = any(parse_number(cell) is not None
                         for table in page_tables for row in table[1:] for cell in row[1:])
            if usable:
                tables.extend(page_tables)
            else:
                table, previous_layout = extract_borderless_creditas_table(page, previous_layout)
                tables.append(table)
        return tables


def extract_borderless_creditas_table(page: Any, previous_layout: Any = None) -> tuple[list[list[str | None]], Any]:
    """Keep empty cells in older borderless reports using PDF coordinates."""
    words = page.extract_words()
    days = [word for word in words if re.fullmatch(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}", word["text"])]
    if not days:
        return [], previous_layout
    first_top = min(word["top"] for word in days)
    # Drawing order keeps overlapping header text intact (e.g. [%]Uptime),
    # unlike visual word extraction. It also handles multi-line headings.
    chars = [char for char in page.chars if char["top"] < first_top - 1]
    heading = "".join(char["text"] for char in chars)
    groups = []
    for match in re.finditer(r"Date|Datum|AISP|PISP|CISP|Downtime|Uptime|Error|POM[EĚ]R[_\s]V[YÝ]PADK[UŮ]", heading, re.I):
        label = match.group()
        if label.lower() == "error":
            label = "Error response rate [%]"
        groups.append((chars[match.start()]["x0"], label))
    if any(label.upper() == "AISP" for _, label in groups):
        if not any(label.lower() in {"date", "datum"} for _, label in groups):
            groups.append((min(word["x0"] for word in days), "Date"))
        groups.sort()
        headers = [label for _, label in groups]
        # Numbers are right-aligned just before the next column heading.
        boundaries = [0] + [start - 1 for start, _ in groups[1:]] + [page.width]
        previous_layout = (headers, boundaries)
    elif previous_layout:
        headers, boundaries = previous_layout
    else:
        return [], previous_layout
    table: list[list[str | None]] = [headers]
    for day in days:
        cells: list[list[str]] = [[] for _ in headers]
        for word in sorted((word for word in words if abs(word["top"] - day["top"]) < 2), key=lambda word: word["x0"]):
            center = (word["x0"] + word["x1"]) / 2
            for index, (left, right) in enumerate(zip(boundaries, boundaries[1:])):
                if left <= center < right:
                    cells[index].append(word["text"])
                    break
        table.append([" ".join(cell) or None for cell in cells])
    return table, previous_layout


def parse_creditas_metrics(content: bytes) -> dict[str, float | str | None]:
    columns: dict[str, int] = {}
    values: dict[str, list[float]] = {
        "availability_pct": [], "aisp_response_ms": [],
        "pisp_response_ms": [], "shared_error_pct": [],
    }
    published_days = 0
    for table in extract_creditas_tables(content):
        for row in table:
            for index, cell in enumerate(row):
                header = " ".join(unicodedata.normalize("NFKD", cell or "").encode("ascii", "ignore").decode().upper().split())
                if "AISP" in header:
                    columns["aisp_response_ms"] = index
                elif "PISP" in header:
                    columns["pisp_response_ms"] = index
                elif "UPTIME" in header or "DOSTUPNOST" in header or "PROVOZUSCHOPNOST" in header:
                    columns["availability_pct"] = index
                elif "ERROR RESPONSE" in header or "MIRA CHYB" in header:
                    columns["shared_error_pct"] = index
            if not row or not re.fullmatch(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}", (row[0] or "").strip()):
                continue
            published_days += 1
            for field, index in columns.items():
                if index >= len(row):
                    continue
                value = parse_number(row[index])
                if value is not None:
                    values[field].append(value)
    if not values["availability_pct"]:
        raise ValueError("PDF CREDITAS nema rozpoznanou tabulku dennich uptime hodnot")
    result: dict[str, float | str | None] = {
        "availability_pct": fmean(values["availability_pct"]),
        "aisp_response_ms": average_active_response(values["aisp_response_ms"]),
        "pisp_response_ms": average_active_response(values["pisp_response_ms"]),
        "aisp_error_pct": average(values["shared_error_pct"]),
        "pisp_error_pct": average(values["shared_error_pct"]),
        "metric_method": "prumer dennich hodnot z PDF tabulky se zachovanymi prazdnymi sloupci",
    }
    if values["shared_error_pct"]:
        result["metric_method"] += "; spolecna error response rate v procentech"
    if len(values["availability_pct"]) < published_days:
        result["metric_method"] += f"; neuplny denni uptime: {len(values['availability_pct'])}/{published_days} dni"
    return result


def parse_first_xlsx_sheet(content: bytes) -> list[dict[str, str]]:
    spreadsheet_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    relationship_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    package_relationship_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    ns = {"m": spreadsheet_ns}
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relation_map = {
            relation.attrib["Id"]: relation.attrib["Target"]
            for relation in relationships.findall(f"{{{package_relationship_ns}}}Relationship")
        }
        sheet = workbook.find("m:sheets/m:sheet", ns)
        if sheet is None:
            return []
        relation_id = sheet.attrib[f"{{{relationship_ns}}}id"]
        target = relation_map[relation_id].lstrip("/")
        sheet_path = target if target.startswith("xl/") else f"xl/{target}"

        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_root.findall("m:si", ns):
                shared.append(
                    "".join(
                        node.text or ""
                        for node in item.iter(f"{{{spreadsheet_ns}}}t")
                    )
                )

        sheet_root = ElementTree.fromstring(archive.read(sheet_path))
        rows: list[dict[str, str]] = []
        for row in sheet_root.findall(".//m:sheetData/m:row", ns):
            values: dict[str, str] = {}
            for cell in row.findall("m:c", ns):
                reference = cell.attrib.get("r", "")
                column_match = re.match(r"[A-Z]+", reference)
                if not column_match:
                    continue
                column = column_match.group(0)
                value_node = cell.find("m:v", ns)
                value = value_node.text if value_node is not None and value_node.text else ""
                if cell.attrib.get("t") == "s" and value:
                    value = shared[int(value)]
                elif cell.attrib.get("t") == "inlineStr":
                    value = "".join(
                        node.text or ""
                        for node in cell.iter(f"{{{spreadsheet_ns}}}t")
                    )
                values[column] = value
            if values:
                rows.append(values)
        return rows


def parse_pdf_metrics(content: bytes, layout: str) -> dict[str, float | str | None]:
    if layout == "creditas":
        return parse_creditas_metrics(content)
    text = extract_pdf_text(content)
    date_prefix = r"\d{1,2}[./]\d{1,2}[./]\d{2,4}"
    lines = [" ".join(line.split()) for line in text.splitlines()]
    result: dict[str, float | str | None] = {
        "availability_pct": None,
        "aisp_response_ms": None,
        "pisp_response_ms": None,
        "aisp_error_pct": None,
        "pisp_error_pct": None,
        "metric_method": "",
    }

    if layout in {"standard_minutes", "standard_minutes_kb", "standard_minutes_air"}:
        api_minutes: list[float] = []
        aisp_responses: list[float] = []
        pisp_responses: list[float] = []
        aisp_errors: list[float] = []
        pisp_errors: list[float] = []
        # Starší PDF Air Bank neuchovávájí konce řádků. Datum je
        # spolehlivější hranicí záznamu než konec textového řádku.
        records = re.findall(rf"{date_prefix}\s+(.*?)(?={date_prefix}\s+|\Z)", text, re.S)
        for record in records:
            # The daily error columns finish the record. Page footers and
            # headings between days must not become extra numerical cells.
            performance = re.match(r".*?(?:[\d,.]+%\s+){2}[\d,.]+%", record, re.S)
            line = " ".join((performance.group() if performance else record.splitlines()[0]).split())
            match = re.match(r"^(\d{1,4})\s+(\d{1,4})(?:\s|$)", line)
            if match:
                api_minutes.append(float(match.group(2)))
            values = [parse_number(token) for token in line.split()]
            clean = [value for value in values if value is not None]
            if len(clean) < 8:
                continue
            responses = clean[-6:-3]
            errors = clean[-3:]
            if layout == "standard_minutes_air":
                pisp_responses.append(responses[0])
                aisp_responses.append(responses[1])
                pisp_errors.append(errors[0])
                aisp_errors.append(errors[1])
            else:
                aisp_responses.append(responses[0])
                pisp_responses.append(responses[1])
                aisp_errors.append(errors[0])
                pisp_errors.append(errors[1])
        if api_minutes:
            result["availability_pct"] = sum(api_minutes) / (1440 * len(api_minutes)) * 100
            result["metric_method"] = "soucet minut provozu API / kalendarni minuty"
        result["aisp_response_ms"] = average_active_response(aisp_responses)
        result["pisp_response_ms"] = average_active_response(pisp_responses)
        result["aisp_error_pct"] = average(aisp_errors)
        result["pisp_error_pct"] = average(pisp_errors)
        return result

    if layout == "fio":
        up_minutes: list[float] = []
        down_minutes: list[float] = []
        aisp_responses: list[float] = []
        pisp_responses: list[float] = []
        aisp_errors: list[float] = []
        pisp_errors: list[float] = []
        for line in lines:
            match = re.match(rf"^{date_prefix}\s+(\d{{1,4}})\s+(\d{{1,4}})(?:\s|$)", line)
            if match:
                up_minutes.append(float(match.group(1)))
                down_minutes.append(float(match.group(2)))
            row_match = re.match(rf"^{date_prefix}\s+(.+)$", line)
            if not row_match:
                continue
            values = [parse_number(token) for token in row_match.group(1).split()]
            if len(values) < 8 or any(value is None for value in values[:8]):
                continue
            pisp_responses.append(float(values[2]))
            pisp_errors.append(float(values[3]))
            aisp_responses.append(float(values[4]))
            aisp_errors.append(float(values[5]))
        total = sum(up_minutes) + sum(down_minutes)
        if total:
            result["availability_pct"] = sum(up_minutes) / total * 100
            result["metric_method"] = "soucet PSD2 API provozu / (provoz + vypadek)"
        result["aisp_response_ms"] = average_active_response(aisp_responses)
        result["pisp_response_ms"] = average_active_response(pisp_responses)
        result["aisp_error_pct"] = average(aisp_errors)
        result["pisp_error_pct"] = average(pisp_errors)
        return result

    if layout == "trinity":
        uptimes: list[float] = []
        for line in lines:
            match = re.match(
                rf"^\S+\s+{date_prefix}\s+\d+\s+[\d,.]+%?\s+([\d,.]+)%?(?:\s|$)",
                line,
            )
            if match:
                value = parse_number(match.group(1))
                if value is not None:
                    uptimes.append(value)
        if uptimes:
            result["availability_pct"] = fmean(uptimes)
            result["metric_method"] = "aritmeticky prumer dennich uptime hodnot vsech PSD2 sluzeb"
        return result

    if layout == "jt":
        uptimes: list[float] = []
        aisp_responses: list[float] = []
        pisp_responses: list[float] = []
        errors: list[float] = []
        for line in lines:
            match = re.match(rf"^{date_prefix}\s+(.+)$", line)
            if not match:
                continue
            tokens = match.group(1).split()
            if len(tokens) < 6:
                continue
            values = [parse_number(token) for token in tokens]
            if any(value is None for value in values[-3:]):
                continue
            pisp_responses.append(values[0] or 0.0)
            aisp_responses.append(values[1] or 0.0)
            errors.append(values[-3] or 0.0)
            uptimes.append(values[-2] or 0.0)
        if uptimes:
            result.update(
                availability_pct=fmean(uptimes),
                aisp_response_ms=average_active_response(aisp_responses),
                pisp_response_ms=average_active_response(pisp_responses),
                aisp_error_pct=fmean(errors) * 100,
                pisp_error_pct=fmean(errors) * 100,
                metric_method="prumer dennich uptime; spolecna error response rate prevedena z podilu na procenta",
            )
        return result

    if layout == "ppf":
        aisp_responses: list[float] = []
        pisp_responses: list[float] = []
        aisp_errors: list[float] = []
        pisp_errors: list[float] = []
        for line in lines:
            match = re.match(rf"^{date_prefix}\s+(.+)$", line)
            if not match:
                continue
            values = [parse_number(token) for token in match.group(1).split()]
            if len(values) < 6 or any(value is None for value in values[:6]):
                continue
            aisp_response = float(values[0])
            pisp_response = float(values[2])
            aisp_responses.append(aisp_response)
            pisp_responses.append(pisp_response)
            # Banka uvadi 0 % i ve dnech bez jedineho volani. Tyto dny
            # nesmeji snizit prumer chybovosti pri aktivnim provozu.
            if aisp_response > 0:
                aisp_errors.append(float(values[1]))
            if pisp_response > 0:
                pisp_errors.append(float(values[3]))
        result["aisp_response_ms"] = average_active_response(aisp_responses)
        result["pisp_response_ms"] = average_active_response(pisp_responses)
        result["aisp_error_pct"] = average(aisp_errors)
        result["pisp_error_pct"] = average(pisp_errors)
        result["metric_method"] = "prumer odezvy a chybovosti jen ve dnech s volanimi; banka nepublikuje uptime"
        return result

    raise ValueError(f"Neznamy PDF layout: {layout}")


def base_observation(bank: dict[str, Any]) -> Observation:
    return Observation(
        bank_id=bank["id"],
        bank=bank["name"],
        scope=bank.get("scope", "main"),
        source_url=bank["source_url"],
        note=bank.get("note", ""),
    )


def parse_report_links(bank: dict[str, Any], fetcher: Fetcher) -> Observation:
    observation = base_observation(bank)
    response = fetcher.get(bank["source_url"])
    candidates = find_report_candidates(response.text, response.url, bank.get("report_pattern", r"PSD2|availability|dostupnost|report"))
    if bank["id"] == "mbank":
        # A .cz host and an EN/PL portal locale do not establish a CZ data cut.
        # Public reports were audited, but must not become Czech observations
        # just because the SPA later exposes static links.
        observation.metric_method = "verejne reporty mBank existuji; cesky rozsah metrik neni jednoznacne dolozen, proto cisla nejsou prevzata"
        observation.report_url = bank["source_url"]
        observation.report_details = {"country_scope": "unverified", "catalog_url": bank["source_url"]}
        if bank.get("report_catalog_url"):
            catalog = fetcher.get(bank["report_catalog_url"], headers={"mode": bank["report_catalog_mode"]}).json()
            catalog_reports = {item.get("resource", {}).get("url", ""): item for item in catalog.get("reports", [])}
            for extra in bank.get("additional_report_catalogs", []):
                extra_catalog = fetcher.get(extra["url"], headers={"mode": extra["mode"]}).json()
                catalog_reports.update({item.get("resource", {}).get("url", ""): item for item in extra_catalog.get("reports", [])})
            reports = []
            for item in catalog_reports.values():
                dates = re.findall(r"\b\d{2}\.\d{2}\.20\d{2}\b", item.get("name", ""))
                url = item.get("resource", {}).get("url", "")
                if len(dates) != 2 or not url.startswith("https://"):
                    continue
                start, end = [datetime.strptime(value, "%d.%m.%Y").date() for value in dates]
                if end < start:
                    continue
                first_period = f"{start.year}-Q{(start.month - 1) // 3 + 1}"
                last_period = f"{end.year}-Q{(end.month - 1) // 3 + 1}"
                period = first_period if first_period == last_period else f"{first_period}–{last_period}"
                reports.append({"bank_id": "mbank", "bank": bank["name"], "period": period, "periods": quarter_range(first_period, last_period), "first_day": start.isoformat(), "last_day": end.isoformat(), "report_url": url, "source_url": bank["source_url"], "status": "unverified", "source_state": "ok", "metric_method": observation.metric_method, "note": observation.note})
            observation.report_details["published_reports"] = sorted(reports, key=lambda row: row["period"])
            if isinstance(fetcher, Fetcher) and fetcher.archive:
                newest = max((row["period"] for row in reports), default="")
                for row in reports:
                    # Archive public evidence separately; no foreign/unknown-scope
                    # report is converted to Czech daily observations.
                    if row["period"] == newest or not fetcher.archive.has_response("mbank", row["report_url"]):
                        try:
                            fetcher.get(row["report_url"])
                        except FetchError as exc:
                            observation.note += f" Zdrojova kopie {row['period']} nebyla stazena: {exc}."
        return observation
    if not candidates:
        return observation

    _, period, report_url, _ = candidates[0]
    observation.latest_period = period
    observation.report_url = report_url
    layout = bank.get("pdf_layout")
    if not layout:
        observation.metric_method = "nalezen report; bez parseru metrik"
        return observation

    try:
        report = fetcher.get(report_url, headers={"Accept": "application/pdf,*/*;q=0.8"})
        if not report.content.startswith(b"%PDF"):
            raise ValueError("odkaz nevratil PDF")
        metrics = parse_pdf_metrics(report.content, layout)
        for key, value in metrics.items():
            setattr(observation, key, value)
        observation.daily_metrics = [{**row, "source_url": report_url} for row in parse_pdf_daily(report.content, layout, period)]
    except (FetchError, ValueError) as exc:
        observation.source_state = "report-error"
        observation.note = f"{observation.note} PDF se nepodarilo zpracovat: {exc}".strip()
    return observation


def find_rb_reports(bank: dict[str, Any], fetcher: Fetcher) -> list[tuple[str, str]]:
    """Use the same public attachment catalogue as the bank's document UI.

    Categories omit archived reports and a broad query returns only 20 hits.
    Narrow queries cover legacy and newer names without guessing PDF paths.
    """
    found = {}
    for query in bank["report_search_queries"]:
        response = fetcher.get(bank["report_search_url"], params={
            "searchIn": "ATTACHMENTS", "lang": "cs", "maxCountDocuments": 50, "q": query,
        })
        for item in response.json().get("attachmentResults", {}).get("results", []):
            url = urljoin(bank["source_url"], item.get("url", ""))
            if (urlparse(url).hostname != urlparse(bank["source_url"]).hostname
                    or not re.search(r"/attachments/infopovinnost/statistiky-vykonu[^/]*\.pdf$", url, re.I)):
                continue
            found[url] = parse_quarter(f"{item.get('title', '')} {url}") or ""
    return sorted(((period, url) for url, period in found.items()), reverse=True)


def extract_rb_pdf_text(content: bytes) -> str:
    # Coordinate-based extraction keeps legacy split digits in their cells.
    try:
        with pdfplumber.open(io.BytesIO(content)) as document:
            return "\n".join(page.extract_text(x_tolerance=2, y_tolerance=3) or "" for page in document.pages)
    except Exception as exc:
        raise ValueError(f"RB PDF nelze precist: {type(exc).__name__}") from exc


def rb_report_text(content: bytes) -> tuple[str, str]:
    """The public catalogue includes ZIP/DOCX downloads labelled .pdf."""
    if content.startswith(b"%PDF"):
        return extract_rb_pdf_text(content), ""
    if not content.startswith(b"PK"):
        raise ValueError("RB odkaz nevratil PDF ani podporovany archiv")
    with zipfile.ZipFile(io.BytesIO(content)) as packed:
        if len(packed.infolist()) > 50 or sum(item.file_size for item in packed.infolist()) > 20_000_000:
            raise ValueError("RB archiv prekrocil bezpecnou velikost")
        if "word/document.xml" in packed.namelist():
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            root = ElementTree.fromstring(packed.read("word/document.xml"))
            parts = []
            cell_text = lambda node: " ".join("".join(t.text or "" for t in p.findall(".//w:t", ns)) for p in node.findall(".//w:p", ns))
            body = root.find("w:body", ns)
            if body is None:
                raise ValueError("RB dokument Word nema telo dokumentu")
            for node in body:
                if node.tag == f"{{{ns['w']}}}p":
                    parts.append("".join(t.text or "" for t in node.findall(".//w:t", ns)))
                elif node.tag == f"{{{ns['w']}}}tbl":
                    parts.extend(" ".join(cell_text(cell) for cell in row.findall("w:tc", ns)) for row in node.findall("w:tr", ns))
            return "\n".join(parts), "; obsah odkazu s priponou PDF je dokument Word"
        pdfs = [item for item in packed.infolist() if item.filename.lower().endswith(".pdf") and not item.filename.startswith("__MACOSX/")]
        if len(pdfs) != 1:
            raise ValueError("RB ZIP neobsahuje jednoznacny PDF report")
        pdf = packed.read(pdfs[0])
        if not pdf.startswith(b"%PDF"):
            raise ValueError("RB ZIP neobsahuje platne PDF")
        return extract_rb_pdf_text(pdf), "; PDF ulozene uvnitr ZIP archivu"


def parse_rb_report(bank: dict[str, Any], period: str, url: str, fetcher: Fetcher) -> Observation:
    response = fetcher.get(url, headers={"Accept": "application/pdf,*/*;q=0.8"})
    text, packaging_note = rb_report_text(response.content)
    # Some legacy PDFs split the day digits ("1 1. 04. 2020").
    text = re.sub(r"(?m)^(\d)\s+(\d)(?=\s*\.)", r"\1\2", text)
    daily_pattern = re.compile(r"^(\d{1,2}\s*\.\s*\d{1,2}\s*\.\s*\d{4})\s+((?:[\d,.]+|[Nn]/[Aa])\s+.+)$", re.M)
    records = list(daily_pattern.finditer(text))
    if not records:
        raise ValueError("RB PDF nema rozpoznane denni radky")
    header = text[:records[0].start()]
    first_day = datetime.strptime(re.sub(r"\s", "", records[0].group(1)), "%d.%m.%Y").date()
    period = period or f"{first_day.year}-Q{(first_day.month - 1) // 3 + 1}"
    services = re.findall(r"AISP|PISP", header, re.I)
    first_service = services[0].lower() if services else ""
    if first_service not in {"aisp", "pisp"}:
        raise ValueError("RB PDF nema dolozene poradi AISP/PISP")
    order = [first_service, "pisp" if first_service == "aisp" else "aisp"]
    calls_layout = bool(re.search(r"vol[aá]n[ií]", header, re.I))
    daily = {}
    for match in records:
        day = datetime.strptime(re.sub(r"\s", "", match.group(1)), "%d.%m.%Y").date()
        actual_period = f"{day.year}-Q{(day.month - 1) // 3 + 1}"
        if actual_period != period:
            raise ValueError(f"RB report oznaceny {period} obsahuje den {day} ({actual_period}); datumy se neprepisuji")
        raw = re.sub(r"(?<=\d)\s+%", "%", match.group(2))
        row = {"date": day.isoformat(), "country_code": "CZ", "source_url": url}
        # Anchor groups to their percentage: PDF text can split response digits
        # ("74 4,1016") and legacy N/A rows omit the third placeholder.
        groups = list(re.finditer(r"((?:[\d.,]+\s+){2,})([\d.,]+)%", raw))
        for index, group in enumerate(groups):
            service_index = index + (1 if index == 0 and "N/A" in raw[:group.start()].upper() else 0)
            if service_index >= len(order):
                raise ValueError(f"RB report ma nejasne sloupce pro {day}")
            service = order[service_index]
            row[f"{service}_availability_pct"] = parse_number(group[2])
            if row[f"{service}_availability_pct"] is None or not 0 <= row[f"{service}_availability_pct"] <= 100:
                raise ValueError(f"RB report ma neplatnou dostupnost pro {day}")
            prefix = group[1].split()
            count, errors = parse_number("".join(prefix[:-1])), parse_number(prefix[-1])
            row[f"{service}_reported_error_count"] = errors
            if calls_layout:
                if count is None or errors is None or count < 0 or errors < 0 or errors > count:
                    raise ValueError(f"RB report ma neplatne pocty volani/chyb pro {day}")
                row[f"{service}_reported_call_count"] = count
                row[f"{service}_error_pct"] = errors / count * 100 if count > 0 else None
            else:
                # Legacy headings say "odezva" but do not state a unit or
                # the number of calls. Do not invent milliseconds or error %.
                row[f"{service}_response_reported_without_unit"] = count
        if day in daily and daily[day] != row:
            raise ValueError(f"RB PDF obsahuje ruzne radky pro den {day}")
        daily[day] = row
    observation = base_observation(bank)
    observation.latest_period = period
    observation.report_url = url
    observation.daily_metrics = list(daily.values())
    for service in order:
        setattr(observation, f"{service}_availability_pct", average(row.get(f"{service}_availability_pct") for row in daily.values()))
        if calls_layout:
            calls = sum(row.get(f"{service}_reported_call_count", 0) or 0 for row in daily.values())
            errors = sum(row.get(f"{service}_reported_error_count", 0) or 0 for row in daily.values())
            setattr(observation, f"{service}_error_pct", errors / calls * 100 if calls else None)
    observation.metric_method = "prumer publikovane denni dostupnosti AISP/PISP; nejde o dolozene minuty uptime"
    observation.metric_method += "; chybovost = soucet poctu chyb / soucet poctu volani x 100" if calls_layout else "; odezva bez uvedene jednotky a chyby bez poctu volani se neprevadeji na ms ani procenta"
    observation.metric_method += packaging_note
    header_dates = re.findall(r"\d{1,2}\s*\.\s*\d{1,2}\s*\.\s*\d{4}", header)
    conflicts = []
    for raw_day in header_dates:
        header_day = datetime.strptime(re.sub(r"\s", "", raw_day), "%d.%m.%Y").date()
        if f"{header_day.year}-Q{(header_day.month - 1) // 3 + 1}" != period:
            conflicts.append(header_day.isoformat())
    if conflicts:
        observation.metric_method += f"; upozorneni: hlavicka uvadi {', '.join(conflicts)}, denni datumy i katalog uvadeji {period}; datumy nebyly prepsany"
    return finalize_status(observation, period)


def collect_rb_history(bank: dict[str, Any], fetcher: Fetcher, periods: set[str]) -> list[Observation]:
    observations = []
    for period, url in find_rb_reports(bank, fetcher):
        if period and period not in periods:
            continue
        try:
            observation = parse_rb_report(bank, period, url, fetcher)
        except (FetchError, ValueError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
            if not period:
                continue
            observation = base_observation(bank)
            observation.latest_period = period
            observation.report_url = url
            observation.source_state = "report-error"
            observation.metric_method = f"verejny report nalezen; metriky nejsou pouzity: {exc}"
            observation.note += f" {exc}"
        if observation.latest_period in periods:
            observations.append(observation)
    return observations


def parse_rb(bank: dict[str, Any], fetcher: Fetcher) -> Observation:
    issues = []
    for period, url in find_rb_reports(bank, fetcher):
        try:
            observation = parse_rb_report(bank, period, url, fetcher)
        except (FetchError, ValueError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
            issues.append(str(exc))
            continue
        if has_reported_metrics(observation):
            if issues:
                observation.note += " Novejsi report nebyl pouzit: " + "; ".join(issues)
            return observation
    raise ValueError("RB nema overeny meritelny report: " + "; ".join(issues))


def parse_csas(bank: dict[str, Any], fetcher: Fetcher) -> Observation:
    observation = base_observation(bank)
    page = fetcher.get(bank["source_url"])
    document = html.fromstring(page.content)
    encoded = document.xpath("string(//meta[@name='ersteEnvs']/@content)")
    if not encoded:
        raise ValueError("Portal neobsahuje konfiguraci ersteEnvs")
    encoded += "=" * (-len(encoded) % 4)
    environment = json.loads(base64.b64decode(encoded).decode("utf-8"))
    api_key = environment["WEB_API_KEY"]
    base_url = environment["BASE_URL_HUB_STATISTICS"].rstrip("/")
    endpoint = f"{base_url}/hub-statistics/apiOverviewStatus/bank/bank.csas/"
    response = fetcher.get(
        endpoint,
        params={"granularity": "quarter"},
        headers={"web-api-key": api_key, "Accept": "application/json"},
    )
    items = response.json().get("items", [])
    if not items:
        raise ValueError("JSON neobsahuje zadne statistiky")
    observation.latest_period = period_from_datetime_range(items[0]["from"], items[0]["to"])
    observation.report_url = bank["source_url"]

    by_scope: dict[str, list[float]] = {"aisp": [], "pisp": []}
    for item in items:
        scopes = {str(scope).lower() for scope in item.get("api", {}).get("scopes", [])}
        histories = [
            parse_number(entry.get("availability"))
            for entry in item.get("statusHistory", [])
        ]
        values = [value * 100 for value in histories if value is not None]
        for scope in by_scope:
            if scope in scopes:
                by_scope[scope].extend(values)
    observation.aisp_availability_pct = average(by_scope["aisp"])
    observation.pisp_availability_pct = average(by_scope["pisp"])
    observation.metric_method = "prumer dennich hodnot z verejneho JSON podle AISP/PISP"
    daily = {}
    for item in items:
        scopes = {str(scope).lower() for scope in item.get("api", {}).get("scopes", [])}
        for entry in item.get("statusHistory", []):
            value = parse_number(entry.get("availability"))
            if value is None or not entry.get("from"):
                continue
            # Bank reports midnight in Prague, represented as the preceding UTC day.
            day = datetime.fromisoformat(entry["from"].replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Prague")).date().isoformat()
            row = daily.setdefault(day, {"aisp": [], "pisp": []})
            for scope in row:
                if scope in scopes:
                    row[scope].append(value * 100)
    observation.daily_metrics = [{"date": day, "aisp_availability_pct": average(values["aisp"]), "pisp_availability_pct": average(values["pisp"]), "country_code": "CZ", "metric_method": observation.metric_method} for day, values in sorted(daily.items())]
    return observation


def apply_csob_workbook(observation: Observation, content: bytes) -> Observation:
    rows = parse_first_xlsx_sheet(content)
    columns: dict[str, str] = {}
    service_groups: dict[str, str] = {}
    for row in rows[:10]:
        for column, value in row.items():
            header = " ".join(value.upper().split())
            if header == "PSD2 CISP":
                service_groups[column] = "cisp"
            for service in ("AISP", "PISP"):
                if service not in header:
                    continue
                prefix = service.lower()
                if "RESPONSE" in header:
                    columns.setdefault(f"{prefix}_response", column)
                elif "ERROR" in header or "FAILURE" in header:
                    columns.setdefault(f"{prefix}_error", column)
                elif header == f"PSD2 {service}" and len(column) == 1:
                    # Starší pivotové reporty mají dvouřádkové záhlaví
                    # a nemají sloupec Calls před odezvou.
                    columns[f"{prefix}_response"] = column
                    columns[f"{prefix}_error"] = chr(ord(column) + 1)
                    service_groups[column] = prefix
    # Some reports put the service in a merged cell above Calls/Response/Error.
    # Resolve the leaf header within that service's column group.
    for row in rows[:10]:
        for column, value in row.items():
            header = " ".join(value.upper().split())
            preceding = [start for start in service_groups if start <= column]
            if not preceding or "PSD2" in header:
                continue
            prefix = service_groups[max(preceding)]
            if prefix == "cisp":
                continue
            if "RESPONSE TIME" in header:
                columns[f"{prefix}_response"] = column
            elif "ERROR RATE" in header or "FAILURE RATE" in header:
                columns[f"{prefix}_error"] = column
    if len(columns) != 4:
        raise ValueError("XLSX nema rozpoznane AISP/PISP sloupce odezvy a chybovosti")
    data_rows = []
    for row in rows:
        day = row.get("A", "")
        serial = parse_number(day)
        if (serial is not None and 30000 <= serial <= 70000) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            data_rows.append(row)
    if not data_rows:
        raise ValueError("XLSX neobsahuje rozpoznane denni zaznamy")
    observation.aisp_response_ms = average_active_response(parse_number(row.get(columns["aisp_response"])) for row in data_rows)
    observation.pisp_response_ms = average_active_response(parse_number(row.get(columns["pisp_response"])) for row in data_rows)
    aisp_error_ratio = average(parse_number(row.get(columns["aisp_error"])) for row in data_rows)
    pisp_error_ratio = average(parse_number(row.get(columns["pisp_error"])) for row in data_rows)
    observation.aisp_error_pct = aisp_error_ratio * 100 if aisp_error_ratio is not None else None
    observation.pisp_error_pct = pisp_error_ratio * 100 if pisp_error_ratio is not None else None
    observation.metric_method = "prumer dennich XLSX hodnot; chybovost prevedena z podilu na procenta; uptime chybi"
    observation.daily_metrics = []
    for row in data_rows:
        raw = row["A"]
        day = raw if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw) else (date(1899, 12, 30) + timedelta(days=int(float(raw)))).isoformat()
        observation.daily_metrics.append({"date": day, "aisp_response_ms": parse_number(row.get(columns["aisp_response"])), "pisp_response_ms": parse_number(row.get(columns["pisp_response"])), "aisp_error_pct": (value * 100 if (value := parse_number(row.get(columns["aisp_error"]))) is not None else None), "pisp_error_pct": (value * 100 if (value := parse_number(row.get(columns["pisp_error"]))) is not None else None), "country_code": "CZ", "metric_method": observation.metric_method, "source_url": observation.report_url or observation.source_url})
    return observation


def parse_csob(bank: dict[str, Any], fetcher: Fetcher) -> Observation:
    observation = base_observation(bank)
    page = fetcher.get(bank["source_url"])
    candidates = find_report_candidates(
        page.text,
        page.url,
        bank.get("report_pattern", r"PSD2|report"),
    )
    if not candidates:
        return observation
    _, period, report_url, _ = candidates[0]
    observation.latest_period = period
    observation.report_url = report_url
    try:
        report = fetcher.get(
            report_url,
            headers={
                "Referer": page.url,
                "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*;q=0.8",
            },
        )
        apply_csob_workbook(observation, report.content)
    except (FetchError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        observation.source_state = "report-error"
        observation.note = f"{observation.note} XLSX se nepodarilo zpracovat: {exc}".strip()
    return observation


def parse_unicredit_quarters(bank: dict[str, Any], fetcher: Fetcher) -> list[Observation]:
    response = fetcher.get(bank["source_url"])
    data = extract_balanced_json(response.text, "var kpiData =")
    country_code = "CZ-B" if data.get("CZ-B") else "CZ"
    country = data.get(country_code)
    if not country or "Dedicated Interface" not in country:
        raise ValueError("UniCredit JSON neobsahuje CZ Dedicated Interface")
    rows = list(country["Dedicated Interface"].values())
    dated: list[tuple[int, int, int, dict[str, Any]]] = []
    for row in rows:
        year = int(row.get("year", 0))
        month = MONTHS.get(str(row.get("date", "")).upper(), 0)
        if year and month:
            dated.append((year, (month - 1) // 3 + 1, month, row))
    if not dated:
        raise ValueError("UniCredit JSON nema datovane CZ zaznamy")
    observations: list[Observation] = []
    daily_source = extract_balanced_json(response.text, "var kpiDataDaily =") if "var kpiDataDaily =" in response.text else {}
    daily_country = daily_source.get(country_code, {}).get("Dedicated Interface", {})
    daily_rows = [row for month in daily_country.values() if isinstance(month, dict) for row in month.values() if isinstance(row, dict) and row.get("date")]
    for year, quarter in sorted({(year, quarter) for year, quarter, _, _ in dated}):
        selected_months = sorted((month, row) for y, q, month, row in dated if y == year and q == quarter)
        selected = [row for _, row in selected_months]
        observation = base_observation(bank)
        observation.latest_period = f"{year}-Q{quarter}"
        observation.report_url = bank["source_url"]
        observation.availability_pct = average(parse_number(row.get("uptime")) for row in selected)
        observation.aisp_response_ms = average_active_response(parse_number(row.get("ais")) for row in selected)
        observation.pisp_response_ms = average_active_response(parse_number(row.get("pis")) for row in selected)
        error = average(parse_number(row.get("error_response_rate")) for row in selected)
        observation.aisp_error_pct = error
        observation.pisp_error_pct = error
        observation.metric_method = "prumer mesicnich hodnot CZ Dedicated Interface; spolecna error response rate v procentech"
        observation.daily_metrics = []
        for row in daily_rows:
            day = datetime.strptime(row["date"], "%m-%d-%Y").date()
            if day.year == year and (day.month - 1) // 3 + 1 == quarter:
                observation.daily_metrics.append({"date": day.isoformat(), "availability_pct": parse_number(row.get("uptime")), "aisp_response_ms": parse_number(row.get("ais")), "pisp_response_ms": parse_number(row.get("pis")), "shared_error_pct": parse_number(row.get("error_response_rate")), "country_code": "CZ", "metric_method": "publikovana denni hodnota CZ Dedicated Interface; spolecna error response rate v procentech"})
        observation.report_details = {
            "country_code": country_code,
            "country": "UniCredit Bank Czech Republic",
            "service": "Dedicated Interface",
            "source_url": bank["source_url"],
            "checked_on": date.today().isoformat(),
            "months": [
                {
                    "month": f"{year}-{month:02d}",
                    "availability_pct": parse_number(row.get("uptime")),
                    "aisp_response_ms": parse_number(row.get("ais")),
                    "pisp_response_ms": parse_number(row.get("pis")),
                    "shared_error_pct": parse_number(row.get("error_response_rate")),
                }
                for month, row in selected_months
            ],
        }
        observations.append(observation)
    return observations


def parse_unicredit(bank: dict[str, Any], fetcher: Fetcher) -> Observation:
    observations = parse_unicredit_quarters(bank, fetcher)
    return max(observations, key=lambda item: quarter_rank(item.latest_period))


def parse_moneta(bank: dict[str, Any], fetcher: Fetcher) -> Observation:
    observation = base_observation(bank)
    response = fetcher.get(bank["source_url"])
    document = html.fromstring(response.content)
    records: list[dict[str, float | date]] = []
    for row in document.xpath(
        "//div[contains(concat(' ', normalize-space(@class), ' '), ' table-accordion__row ')]"
    ):
        text = " ".join(" ".join(row.itertext()).split())
        date_match = re.search(r"\b(\d{2}\.\d{2}\.20\d{2})\b", text)
        if not date_match:
            continue

        def labelled(label: str) -> float | None:
            match = re.search(label + r"\s+([\d.,]+)%?", text, re.IGNORECASE)
            return parse_number(match.group(1)) if match else None

        record: dict[str, float | date] = {
            "date": datetime.strptime(date_match.group(1), "%d.%m.%Y").date(),
        }
        labels = {
            "aisp_response": r"AISP avg\. latency \(ms\)",
            "aisp_error": r"AISP err\. rate \(%\)",
            "pisp_response": r"PISP avg\. latency \(ms\)",
            "pisp_error": r"PISP err\. rate \(%\)",
        }
        for key, label in labels.items():
            value = labelled(label)
            if value is not None:
                record[key] = value
        records.append(record)
    if not records:
        raise ValueError("MONETA tabulka neobsahuje denni zaznamy")
    latest = max(record["date"] for record in records)
    assert isinstance(latest, date)
    observation.latest_period = f"rolling-90d-to-{latest.isoformat()}"
    observation.report_url = bank["source_url"]
    observation.aisp_response_ms = average_active_response(record.get("aisp_response") for record in records)  # type: ignore[arg-type]
    observation.pisp_response_ms = average_active_response(record.get("pisp_response") for record in records)  # type: ignore[arg-type]
    observation.aisp_error_pct = average(record.get("aisp_error") for record in records)  # type: ignore[arg-type]
    observation.pisp_error_pct = average(record.get("pisp_error") for record in records)  # type: ignore[arg-type]
    observation.metric_method = "prumer dennich hodnot v klouzavem 90dennim okne; uptime chybi"
    observation.daily_metrics = [
        {
            "date": record["date"].isoformat(),
            "aisp_response_ms": record.get("aisp_response"),
            "pisp_response_ms": record.get("pisp_response"),
            "aisp_error_pct": record.get("aisp_error"),
            "pisp_error_pct": record.get("pisp_error"),
        }
        for record in sorted(records, key=lambda item: item["date"])
    ]
    return observation


def parse_creditas(bank: dict[str, Any], fetcher: Fetcher, today: date) -> Observation:
    observation = base_observation(bank)
    expected = expected_report_period(today)
    for step in range(8):
        period = previous_quarter(expected, step)
        year = period[:4]
        quarter = period[-1]
        report_url = (
            "https://www.creditas.cz/files/"
            f"statisticke-udaje-o-dostupnosti-a-vykonu-rozhrani-{quarter}q-{year}.pdf"
        )
        try:
            response = fetcher.get(report_url, headers=CREDITAS_REPORT_HEADERS)
        except FetchError as exc:
            if exc.status == 404:
                continue
            raise
        if not response.content.startswith(b"%PDF"):
            continue
        observation.source_state = "ok-direct-pdf"
        observation.latest_period = period
        observation.report_url = report_url
        metrics = parse_pdf_metrics(response.content, bank["pdf_layout"])
        for key, value in metrics.items():
            setattr(observation, key, value)
        observation.daily_metrics = [{**row, "source_url": report_url} for row in parse_pdf_daily(response.content, bank["pdf_layout"], period)]
        return observation
    return observation


def parse_partners(bank: dict[str, Any], fetcher: Fetcher, today: date) -> Observation:
    observation = base_observation(bank)
    response = fetcher.get(bank["source_url"])
    document = html.fromstring(response.content)
    charts = document.xpath('//div[contains(@class,"card")][.//h5[normalize-space(text())="PSD2 status"]]//canvas/@data-symfony--ux-chartjs--chart-view-value')
    selected = None
    for raw in charts:
        chart = json.loads(raw).get("data", {})
        labels = chart.get("labels", [])
        if len(labels) == 30 and all(re.fullmatch(r"\d{1,2}\.\d{1,2}\.", label) for label in labels):
            selected = chart
            break
    if not selected:
        raise ValueError("Partners nema rozpoznany 30denni PSD2 graf")
    datasets = selected.get("datasets", [])
    if len(datasets) != 1 or datasets[0].get("label") != "Dostupnost [%]":
        raise ValueError("Partners PSD2 graf nema overenou metriku")
    values = datasets[0].get("data", [])
    if len(values) != 30:
        raise ValueError("Partners PSD2 graf ma nesouhlasne pocty dnu a hodnot")
    observation.daily_metrics = []
    for label, raw in zip(selected["labels"], values):
        day, month = [int(part) for part in label.rstrip(".").split(".")]
        candidate = date(today.year, month, day)
        if candidate >= today:
            candidate = date(today.year - 1, month, day)
        observation.daily_metrics.append({"date": candidate.isoformat(), "availability_pct": parse_number(raw), "country_code": "CZ", "metric_method": "publikovana denni dostupnost PSD2 health-check; nikoli ctvrtletni RTS report"})
    dates = [date.fromisoformat(row["date"]) for row in observation.daily_metrics]
    if any(b - a != timedelta(days=1) for a, b in zip(dates, dates[1:])) or today - dates[-1] > timedelta(days=7):
        raise ValueError("Partners PSD2 graf nema aktualni souvisle datumy")
    observation.latest_period = f"rolling-30d-to-{dates[-1].isoformat()}"
    observation.report_url = bank["source_url"]
    observation.availability_pct = average(row["availability_pct"] for row in observation.daily_metrics)
    observation.metric_method = "prumer 30 publikovanych dennich PSD2 health-check hodnot; nikoli ctvrtletni RTS report"
    return observation


def parse_oberbank(bank: dict[str, Any], fetcher: Fetcher) -> Observation:
    observation = base_observation(bank)
    response = fetcher.get(bank["source_url"])
    document = html.fromstring(response.content)
    for anchor in document.xpath("//a[@href]"):
        label = " ".join(" ".join(anchor.itertext()).split())
        if "statistik" not in label.lower():
            continue
        href = urljoin(response.url, anchor.get("href", ""))
        observation.report_url = href
        hostname = urlparse(href).hostname or ""
        if "redaktionsproduktion" in hostname or ":12080" in href:
            observation.metric_method = "odkaz na statistiku je chybne publikovan"
        break
    if bank.get("statistics_url"):
        observation.report_url = bank["statistics_url"]
        observation.metric_method = "verejny produkcni report Oberbank AG existuje; samostatny cesky rozsah metrik neni dolozen, proto cisla nejsou prevzata"
        observation.report_details = {"country_scope": "unverified", "catalog_url": observation.report_url}
        content = fetcher.get(observation.report_url).content
        text = " ".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
        dates = re.findall(r"\b\d{2}\.\d{2}\.20\d{2}\b", text)
        if dates:
            first = datetime.strptime(dates[0], "%d.%m.%Y").date()
            period = f"{first.year}-Q{(first.month - 1) // 3 + 1}"
            digest = hashlib.sha256(content).hexdigest()
            observation.report_details["published_reports"] = [{"bank_id": observation.bank_id, "bank": observation.bank, "period": period, "report_url": observation.report_url, "source_url": observation.source_url, "status": "unverified", "source_state": "ok", "metric_method": observation.metric_method, "note": observation.note, "archived_source_url": f"https://github.com/tesskosnar/API-PSD2-tracker/blob/main/data/archive/objects/{digest[:2]}/{digest}.gz"}]
    return observation


def apply_seed(bank: dict[str, Any], observation: Observation) -> Observation:
    if observation.latest_period or not bank.get("seed_period"):
        return observation
    observation.latest_period = bank["seed_period"]
    observation.availability_pct = parse_number(bank.get("seed_availability_pct"))
    observation.report_url = bank.get("seed_report_url", observation.report_url)
    observation.metric_method = "posledni rucne overena vychozi hodnota"
    return observation


def carry_previous(observation: Observation, previous: dict[str, Any] | None) -> Observation:
    if observation.source_state in {"ok", "ok-direct-pdf"} or not previous:
        return observation
    if not previous.get("latest_period"):
        return observation
    for field in (
        "latest_period",
        "report_url",
        "availability_pct",
        "aisp_availability_pct",
        "pisp_availability_pct",
        "aisp_response_ms",
        "pisp_response_ms",
        "aisp_error_pct",
        "pisp_error_pct",
        "metric_method",
    ):
        value = previous.get(field)
        if value not in (None, ""):
            setattr(observation, field, value)
    observation.note = (
        f"{observation.note} Posledni zname metriky byly zachovany z predchoziho behu."
    ).strip()
    return observation


def finalize_status(observation: Observation, expected_period: str) -> Observation:
    if observation.source_state not in {"ok", "ok-direct-pdf"}:
        observation.status = "blocked"
        return observation.rounded()
    if (observation.report_details or {}).get("country_scope") == "unverified":
        observation.status = "unverified"
        return observation.rounded()
    if not observation.latest_period:
        observation.status = "missing"
        return observation.rounded()
    if quarter_rank(observation.latest_period) >= 0 and quarter_rank(observation.latest_period) < quarter_rank(expected_period):
        observation.status = "outdated"
        return observation.rounded()
    has_availability = any(
        value is not None
        for value in (
            observation.availability_pct,
            observation.aisp_availability_pct,
            observation.pisp_availability_pct,
        )
    )
    observation.status = "ok" if has_availability else "partial"
    if "neuplny denni uptime" in observation.metric_method:
        observation.status = "partial"
    if "health-check" in observation.metric_method:
        observation.status = "partial"
    return observation.rounded()


def collect_bank(
    bank: dict[str, Any],
    fetcher: Fetcher,
    today: date,
    expected_period: str,
    previous: dict[str, Any] | None = None,
) -> Observation:
    parser_name = bank["parser"]
    try:
        if parser_name in {"report_links", "pdf_links"}:
            observation = parse_report_links(bank, fetcher)
        elif parser_name == "csas":
            observation = parse_csas(bank, fetcher)
        elif parser_name == "csob":
            observation = parse_csob(bank, fetcher)
        elif parser_name == "rb":
            observation = parse_rb(bank, fetcher)
        elif parser_name == "unicredit":
            observation = parse_unicredit(bank, fetcher)
        elif parser_name == "moneta":
            observation = parse_moneta(bank, fetcher)
        elif parser_name == "creditas":
            observation = parse_creditas(bank, fetcher, today)
        elif parser_name == "oberbank":
            observation = parse_oberbank(bank, fetcher)
        elif parser_name == "partners":
            observation = parse_partners(bank, fetcher, today)
        else:
            raise ValueError(f"Neznamy parser: {parser_name}")
    except FetchError as exc:
        observation = base_observation(bank)
        observation.source_state = f"http-{exc.status}" if exc.status else "network-error"
        observation.note = f"{observation.note} Automaticke nacteni selhalo: {exc}".strip()
    except Exception as exc:  # Izolace bank je zamerna: jeden format nesmi zastavit cely tracker.
        observation = base_observation(bank)
        observation.source_state = "parse-error"
        observation.note = f"{observation.note} Parser selhal: {type(exc).__name__}: {exc}".strip()
    if (observation.source_state in {"ok", "ok-direct-pdf"}
        and parser_name in {"csas", "csob", "unicredit", "moneta", "creditas", "pdf_links"}
        and previous and row_has_metrics(previous) and not has_reported_metrics(observation)):
        observation.source_state = "parse-error"
        observation.note = f"{observation.note} Novy zdroj neobsahuje ocekavane meritelne hodnoty.".strip()
    observation = carry_previous(observation, previous)
    observation = apply_seed(bank, observation)
    return finalize_status(observation, expected_period)


def observation_row(observation: Observation) -> dict[str, Any]:
    row = asdict(observation)
    return {field: row.get(field, "") if row.get(field) is not None else "" for field in CSV_FIELDS}


def has_reported_metrics(observation: Observation) -> bool:
    return any(
        getattr(observation, field) is not None
        for field in (
            "availability_pct",
            "aisp_availability_pct",
            "pisp_availability_pct",
            "aisp_response_ms",
            "pisp_response_ms",
            "aisp_error_pct",
            "pisp_error_pct",
        )
    )


def row_has_metrics(row: dict[str, Any]) -> bool:
    return any(row.get(field) not in (None, "") for field in TIMESERIES_FIELDS if field.endswith(("_pct", "_ms")))


def parse_pdf_daily(content: bytes, layout: str, period: str) -> list[dict[str, Any]]:
    """Additional daily detail; the existing quarterly calculation stays independent."""
    if layout == "creditas":
        columns = {}
        daily = []
        for table in extract_creditas_tables(content):
            for cells in table:
                for index, cell in enumerate(cells):
                    header = " ".join(unicodedata.normalize("NFKD", cell or "").encode("ascii", "ignore").decode().upper().split())
                    if "AISP" in header: columns["aisp_response_ms"] = index
                    elif "PISP" in header: columns["pisp_response_ms"] = index
                    elif "UPTIME" in header or "DOSTUPNOST" in header or "PROVOZUSCHOPNOST" in header: columns["availability_pct"] = index
                    elif "ERROR RESPONSE" in header or "MIRA CHYB" in header: columns["shared_error_pct"] = index
                raw = (cells[0] or "").strip() if cells else ""
                if not re.fullmatch(r"\d{1,2}[./]\d{1,2}[./]\d{2,4}", raw): continue
                normalized = raw.replace("/", ".")
                day = datetime.strptime(normalized, "%d.%m.%y" if len(normalized.split(".")[-1]) == 2 else "%d.%m.%Y").date()
                if f"{day.year}-Q{(day.month-1)//3+1}" != period: raise ValueError(f"Den {day} nesouhlasi s obdobim {period}")
                daily.append({"date": day.isoformat(), "country_code": "CZ", "metric_method": "publikovane denni hodnoty PDF se zachovanymi prazdnymi sloupci; pomer vypadku neni chybovost", **{field: parse_number(cells[index]) if index < len(cells) else None for field, index in columns.items()}})
        if len({row["date"] for row in daily}) != len(daily): raise ValueError("Duplicitni den v PDF CREDITAS")
        return sorted(daily, key=lambda row: row["date"])
    text = extract_pdf_text(content)
    date_prefix = r"\d{1,2}[./]\d{1,2}[./]\d{2,4}"
    records = []
    if layout.startswith("standard_minutes"):
        records = re.findall(rf"({date_prefix})\s+(.*?)(?={date_prefix}\s+|\Z)", text, re.S)
    else:
        for line in text.splitlines():
            pattern = rf"^\S+\s+({date_prefix})\s+(.+)$" if layout == "trinity" else rf"^({date_prefix})\s+(.+)$"
            if match := re.match(pattern, " ".join(line.split())):
                records.append(match.groups())
    days = {}
    for raw_date, raw_values in records:
        raw_date = raw_date.replace("/", ".")
        day = datetime.strptime(raw_date, "%d.%m.%y" if len(raw_date.split(".")[-1]) == 2 else "%d.%m.%Y").date()
        if f"{day.year}-Q{(day.month - 1) // 3 + 1}" != period:
            raise ValueError(f"Den {day} nesouhlasi s obdobim {period}")
        if layout.startswith("standard_minutes"):
            end = re.match(r".*?(?:[\d,.]+%\s+){2}[\d,.]+%", raw_values, re.S)
            raw_values = " ".join((end.group() if end else raw_values.splitlines()[0]).split())
        values = [parse_number(token) for token in raw_values.split()]
        row = {"date": day.isoformat(), "country_code": "CZ"}
        if layout.startswith("standard_minutes"):
            clean = [v for v in values if v is not None]
            if len(clean) < 8 or len(values) < 2 or values[1] is None: continue
            row["availability_pct"] = values[1] / 1440 * 100
            responses, errors = clean[-6:-3], clean[-3:]
            ais, pis = (1, 0) if layout == "standard_minutes_air" else (0, 1)
            row.update(aisp_response_ms=responses[ais], pisp_response_ms=responses[pis], aisp_error_pct=errors[ais], pisp_error_pct=errors[pis])
            row["metric_method"] = "denni provoz API / 1440 minut; publikovana odezva a chybovost"
        elif layout == "fio":
            if len(values) < 8 or any(v is None for v in values[:8]): continue
            row.update(availability_pct=values[0] / (values[0] + values[1]) * 100 if values[0] + values[1] else None, pisp_response_ms=values[2], pisp_error_pct=values[3], aisp_response_ms=values[4], aisp_error_pct=values[5], metric_method="denni PSD2 provoz / (provoz + vypadek); publikovana odezva a chybovost")
        elif layout == "jt":
            if len(values) < 6 or any(v is None for v in values[-3:]): continue
            row.update(pisp_response_ms=values[0], aisp_response_ms=values[1], shared_error_pct=values[-3] * 100, availability_pct=values[-2], metric_method="denni uptime; spolecna chybovost prevedena z podilu na procenta")
        elif layout == "ppf":
            if len(values) < 6 or any(v is None for v in values[:6]): continue
            row.update(aisp_response_ms=values[0], aisp_error_pct=values[1], pisp_response_ms=values[2], pisp_error_pct=values[3], metric_method="publikovane denni hodnoty vcetne nul ve dnech bez volani; uptime chybi")
        elif layout == "trinity":
            if len(values) < 3 or values[2] is None: continue
            days.setdefault(day.isoformat(), []).append(values[2])
            continue
        else: continue
        if row["date"] in days:
            if days[row["date"]] == row: continue
            raise ValueError(f"Konfliktni duplicitni den {day}")
        days[row["date"]] = row
    if layout == "trinity":
        return [{"date": day, "country_code": "CZ", "availability_pct": average(values), "metric_method": "prumer publikovane denni dostupnosti PSD2 sluzeb"} for day, values in sorted(days.items())]
    return [row for _, row in sorted(days.items())]


def parse_pdf_observation(
    bank: dict[str, Any], period: str, report_url: str, fetcher: Fetcher
) -> Observation:
    observation = base_observation(bank)
    observation.latest_period = period
    observation.report_url = report_url
    headers = CREDITAS_REPORT_HEADERS if bank.get("id") == "creditas" else {
        "Accept": "application/pdf,*/*;q=0.8"
    }
    report = fetcher.get(report_url, headers=headers)
    if not report.content.startswith(b"%PDF"):
        raise ValueError("odkaz nevratil PDF")
    metrics = parse_pdf_metrics(report.content, bank["pdf_layout"])
    for key, value in metrics.items():
        setattr(observation, key, value)
    observation.daily_metrics = [{**row, "source_url": report_url} for row in parse_pdf_daily(report.content, bank["pdf_layout"], period)]
    return finalize_status(observation, period)


def collect_pdf_history(
    bank: dict[str, Any], fetcher: Fetcher, periods: set[str]
) -> list[Observation]:
    candidates = []
    pending = [bank["source_url"], *bank.get("history_source_urls", [])]
    visited = set()
    while pending and len(visited) < 30:
        source_url = pending.pop(0)
        if source_url in visited:
            continue
        visited.add(source_url)
        response = fetcher.get(source_url)
        candidates.extend(find_report_candidates(response.text, response.url, bank.get("report_pattern", r"PSD2|availability|dostupnost|report")))
        if bank.get("history_follow_next"):
            document = html.fromstring(response.content)
            for href in document.xpath('//a[@rel="next"]/@href'):
                url = urljoin(response.url, href)
                if urlparse(url).hostname == urlparse(bank["source_url"]).hostname and url not in visited:
                    pending.append(url)
    observations: list[Observation] = []
    seen: set[str] = set()
    for _, period, report_url, _ in candidates:
        if period not in periods or period in seen:
            continue
        seen.add(period)
        try:
            observations.append(parse_pdf_observation(bank, period, report_url, fetcher))
        except (FetchError, ValueError) as exc:
            # Odkaz na report z oficiálního archivu je sám o sobě důležitý.
            # Zachováme jej i tehdy, když se změnil formát PDF nebo je jeho
            # stažení dočasně blokované; v tabulce tak nevznikne falešná mezera.
            observation = base_observation(bank)
            observation.latest_period = period
            observation.report_url = report_url
            observation.status = "partial"
            observation.source_state = "report-error"
            observation.metric_method = "verejny report nalezen; metriky se nepodarilo zpracovat"
            observation.note = f"{observation.note} Historicky report se nepodarilo zpracovat: {exc}".strip()
            observations.append(observation)
    return observations


def collect_csob_history(
    bank: dict[str, Any], fetcher: Fetcher, periods: set[str]
) -> list[Observation]:
    pattern = bank.get("history_url_pattern")
    if not pattern:
        return []
    observations: list[Observation] = []
    for period in sorted(periods, key=quarter_rank):
        year = period[:4]
        quarter = period[-1]
        report_url = pattern.format(year=year, quarter=quarter)
        try:
            report = fetcher.get(
                report_url,
                headers={
                    "Referer": bank["source_url"],
                    "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*;q=0.8",
                },
            )
            observation = base_observation(bank)
            observation.latest_period = period
            observation.report_url = report_url
            try:
                apply_csob_workbook(observation, report.content)
                observations.append(finalize_status(observation, period))
            except (ValueError, KeyError, zipfile.BadZipFile) as exc:
                observation.status = "partial"
                observation.source_state = "report-error"
                observation.metric_method = "verejny report nalezen; metriky se nepodarilo zpracovat"
                observation.note = f"{observation.note} Historicky XLSX se nepodarilo zpracovat: {exc}".strip()
                observations.append(observation)
        except FetchError:
            continue
    return observations


def collect_creditas_history(
    bank: dict[str, Any], fetcher: Fetcher, periods: set[str]
) -> list[Observation]:
    observations: list[Observation] = []
    verified_through = quarter_rank(str(bank.get("history_verified_through", "")))
    discovered: dict[str, str] = {}
    try:
        page = fetcher.get(bank["source_url"])
        candidates = find_report_candidates(
            page.text,
            page.url,
            bank.get(
                "history_report_pattern",
                r"Statistick[eé].*dostupnosti|[1-4]Q\s*20[0-9]{2}|monitoring-mch",
            ),
        )
        discovered = {period: report_url for _, period, report_url, _ in candidates}
    except FetchError:
        pass
    overrides = bank.get("history_url_overrides", {})
    for period in sorted(periods, key=quarter_rank):
        year = period[:4]
        quarter = period[-1]
        report_url = str(
            discovered.get(period)
            or overrides.get(period)
            or (
                "https://www.creditas.cz/files/"
                f"statisticke-udaje-o-dostupnosti-a-vykonu-rozhrani-{quarter}q-{year}.pdf"
            )
        )
        try:
            observations.append(parse_pdf_observation(bank, period, report_url, fetcher))
        except FetchError as exc:
            known_public = (
                period in discovered
                or period in overrides
                or quarter_rank(period) <= verified_through
            )
            if not known_public:
                continue
            observation = base_observation(bank)
            observation.latest_period = period
            observation.report_url = report_url
            observation.status = "partial"
            observation.source_state = "report-error"
            observation.metric_method = "verejny report overen v archivu; automaticke stazeni je blokovane"
            observations.append(observation)
        except ValueError as exc:
            observation = base_observation(bank)
            observation.latest_period = period
            observation.report_url = report_url
            observation.status = "partial"
            observation.source_state = "report-error"
            observation.metric_method = "verejny report nalezen; metriky se nepodarilo zpracovat"
            observation.note = f"{observation.note} Historicky report se nepodarilo zpracovat: {exc}".strip()
            observations.append(observation)
    return observations


def timeseries_row(observation: Observation) -> dict[str, Any]:
    # Historical completeness is relative to its own quarter, not today's latest quarter.
    if quarter_rank(observation.latest_period) >= 0:
        observation = finalize_status(replace(observation), observation.latest_period)
    values = asdict(observation)
    values["period"] = values.pop("latest_period")
    return {
        field: values.get(field, "") if values.get(field) is not None else ""
        for field in TIMESERIES_FIELDS
    }


def collect_timeseries(
    banks: list[dict[str, Any]],
    fetcher: Fetcher,
    latest: list[Observation],
    expected_period: str,
    existing_rows: list[dict[str, Any]] | None = None,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    starts = [
        str(bank["history_start_period"])
        for bank in banks
        if bank.get("scope", "main") == "main"
        and quarter_rank(str(bank.get("history_start_period", ""))) >= 0
    ]
    first_period = min(starts, key=quarter_rank) if starts else expected_period
    periods = set(quarter_range(first_period, expected_period))
    periods_by_bank = {
        bank["id"]: set(
            quarter_range(str(bank.get("history_start_period", first_period)), expected_period)
        )
        for bank in banks
        if bank.get("scope", "main") == "main"
    }
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for row in existing_rows or []:
        if row.get("report_kind") == "archive-derived":
            continue  # Always recompute derived summaries from current retained days.
        period = str(row.get("period", ""))
        bank_id = str(row.get("bank_id", ""))
        if period in periods_by_bank.get(bank_id, periods) and bank_id and row.get("report_url"):
            rows[(bank_id, period)] = {
                field: row.get(field, "") for field in TIMESERIES_FIELDS
            }

    for bank in banks:
        if bank.get("scope", "main") != "main":
            continue
        bank_periods = periods_by_bank.get(bank["id"], periods)
        wanted = bank_periods if refresh else {
            period for period in bank_periods
            if (bank["id"], period) not in rows
            or rows[(bank["id"], period)].get("source_state") not in {"ok", "ok-direct-pdf"}
        }
        if not wanted:
            continue
        if isinstance(fetcher, Fetcher):
            fetcher.bank_id = bank["id"]
        print(f"Doplnuji historii {bank['name']}...", flush=True)
        try:
            if bank["parser"] == "pdf_links":
                observations = collect_pdf_history(bank, fetcher, wanted)
            elif bank["parser"] == "csob":
                observations = collect_csob_history(bank, fetcher, wanted)
            elif bank["parser"] == "rb":
                observations = collect_rb_history(bank, fetcher, wanted)
            elif bank["parser"] == "creditas":
                observations = collect_creditas_history(bank, fetcher, wanted)
            elif bank["parser"] == "unicredit":
                observations = [
                    item
                    for item in parse_unicredit_quarters(bank, fetcher)
                    if item.latest_period in wanted
                ]
                observations = [finalize_status(item, item.latest_period) for item in observations]
            else:
                observations = []
            for observation in observations:
                if isinstance(fetcher, Fetcher) and fetcher.archive:
                    fetcher.archive.record_daily(observation)
                if observation.report_url:
                    row = timeseries_row(observation)
                    key = (observation.bank_id, observation.latest_period)
                    previous = rows.get(key)
                    if previous and previous.get("source_state") in {"ok", "ok-direct-pdf"} and (observation.source_state not in {"ok", "ok-direct-pdf"} or (row_has_metrics(previous) and not has_reported_metrics(observation))):
                        continue
                    rows[key] = row
        except Exception as exc:  # Historicky archiv nesmi zablokovat aktualni prehled.
            print(f"  Historii se nepodarilo nacist: {type(exc).__name__}: {exc}", flush=True)

    for observation in latest:
        if (
            observation.latest_period in periods_by_bank.get(observation.bank_id, periods)
            and observation.report_url
            and observation.source_state in {"ok", "ok-direct-pdf"}
        ):
            row = timeseries_row(observation)
            key = (observation.bank_id, observation.latest_period)
            if row_has_metrics(rows.get(key, {})) and not has_reported_metrics(observation):
                continue
            rows[key] = row

    return sorted(
        rows.values(),
        key=lambda row: (quarter_rank(str(row["period"])), str(row["bank"])),
    )


def write_timeseries(rows: list[dict[str, Any]], data_dir: Path) -> None:
    json_path = data_dir / "timeseries.json"
    csv_path = data_dir / "timeseries.csv"
    json_path.write_text(stable_json(rows), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TIMESERIES_FIELDS + DERIVED_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def derive_archived_quarters(banks: list[dict[str, Any]], daily: list[dict[str, Any]], as_of: date) -> list[dict[str, Any]]:
    """MONETA: labelled daily means for closed quarters, never invented uptime.

    Inputs are the latest retained versions. Missing dates are not zero; error
    percentages cannot be traffic-weighted because the source has no call counts.
    """
    configured = {bank["id"]: bank for bank in banks if bank.get("derive_quarters_from_daily")}
    groups: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    fields = ["aisp_response_ms", "pisp_response_ms", "aisp_error_pct", "pisp_error_pct"]
    for row in daily:
        if row.get("bank_id") not in configured or row.get("country_code") != "CZ":
            continue
        day = date.fromisoformat(row["date"])
        quarter = (day.month - 1) // 3 + 1
        end = date(day.year + 1, 1, 1) if quarter == 4 else date(day.year, quarter * 3 + 1, 1)
        if end > as_of:
            continue  # An ongoing quarter is not a completed quarterly summary.
        if not any(row.get(field) not in (None, "") for field in fields):
            continue
        groups.setdefault((row["bank_id"], f"{day.year}-Q{quarter}"), {})[row["date"]] = row
    summaries = []
    for (bank_id, period), by_day in sorted(groups.items()):
        bank = configured[bank_id]
        year, quarter = map(int, period.split("-Q"))
        start = date(year, (quarter - 1) * 3 + 1, 1)
        end = date(year + 1, 1, 1) if quarter == 4 else date(year, quarter * 3 + 1, 1)
        days = sorted(by_day)
        total = (end - start).days
        observation = base_observation(bank)
        observation.latest_period = period
        observation.report_url = bank["source_url"]
        observation.status = "partial"  # Uptime is not published by this source.
        for field in fields:
            values = [parse_number(row.get(field)) for row in by_day.values()]
            if any(value is not None and (not math.isfinite(value) or value < 0 or (field.endswith("_pct") and value > 100)) for value in values):
                raise ValueError(f"Invalid derived input {bank_id} {period} {field}")
            setattr(observation, field, average_active_response(values) if field.endswith("_ms") else average(values))
        observation.metric_method = (
            f"vypocet trackeru z trvaleho denniho archivu; {len(days)}/{total} kalendarnich dni; "
            "neuverejneny ctvrtletni souhrn banky; odezva je prumer publikovanych dennich odezev > 0 ms; "
            "chybovost je nevazeny prumer publikovanych dennich procent vcetne nul, nikoli pomer vsech chyb ke vsem volanim; "
            "chybejici dny se nedoplnuji; uptime neni uveden"
        )
        summaries.append({**timeseries_row(observation.rounded()), "report_kind": "archive-derived", "archived_days": len(days), "calendar_days": total, "first_day": days[0], "last_day": days[-1]})
    return summaries


def merge_derived_quarters(published: list[dict[str, Any]], derived: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = {(row["bank_id"], row["period"]): row for row in published if row.get("report_kind") != "archive-derived"}
    for row in derived:
        rows.setdefault((row["bank_id"], row["period"]), row)  # Never replace a bank's published report.
    return sorted(rows.values(), key=lambda row: (quarter_rank(row["period"]), row["bank"]))


def build_report_coverage(timeseries: list[dict[str, Any]], daily: list[dict[str, Any]]) -> dict[str, Any]:
    """Count retained measurement days, not presumed completeness of bank reporting."""
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in daily:
        day = date.fromisoformat(row["date"])
        period = f"{day.year}-Q{(day.month - 1) // 3 + 1}"
        grouped.setdefault((row["bank_id"], period), []).append(row)
    result = {}
    for report in timeseries:
        year, quarter = report["period"].split("-Q")
        year, quarter = int(year), int(quarter)
        start = date(year, (quarter - 1) * 3 + 1, 1)
        end = date(year + 1, 1, 1) if quarter == 4 else date(year, quarter * 3 + 1, 1)
        rows = grouped.get((report["bank_id"], report["period"]), [])
        days = sorted({row["date"] for row in rows})
        fields = ["availability_pct", "aisp_availability_pct", "pisp_availability_pct", "aisp_response_ms", "pisp_response_ms", "aisp_error_pct", "pisp_error_pct", "shared_error_pct"]
        result[f'{report["bank_id"]}:{report["period"]}'] = {
            "calendar_days": (end - start).days, "archived_days": len(days),
            "first_day": days[0] if days else None, "last_day": days[-1] if days else None,
            "metric_days": {field: len({row["date"] for row in rows if row.get(field) not in (None, "")}) for field in fields},
        }
    return result


def write_dashboard_data(
    observations: list[Observation],
    timeseries: list[dict[str, Any]],
    expected_period: str,
    checked_on: date,
    output_path: Path = DEFAULT_DASHBOARD_DATA,
    archive: Archive | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_details = {}
    previous = {}
    if output_path.exists():
        try:
            previous = json.loads(output_path.read_text(encoding="utf-8").removeprefix("window.PSD2_DATA = ").rstrip().removesuffix(";"))
            if isinstance(previous.get("source_details"), dict):
                source_details = previous["source_details"]
        except (ValueError, AttributeError):
            pass
    for item in observations:
        if item.report_details:
            key = f"{item.bank_id}:{item.latest_period}"
            details = dict(item.report_details)
            if isinstance(details.get("published_reports"), list):
                retained = {(row["period"], row["report_url"]): {**row, "catalog_present": False} for row in source_details.get(key, {}).get("published_reports", [])}
                retained.update({(row["period"], row["report_url"]): {**row, "catalog_present": True} for row in details["published_reports"]})
                details["published_reports"] = sorted(retained.values(), key=lambda row: (row["period"], row["report_url"]))
                details["catalog_checked_on"] = checked_on.isoformat()
            source_details[key] = details
    payload = {
        "expected_period": expected_period,
        "checked_on": checked_on.isoformat(),
        "latest": [observation_row(item) for item in observations],
        "timeseries": timeseries,
        "source_details": source_details,
    }
    daily_version = None
    if archive:
        daily_rows = archive.daily_rows()
        payload["report_coverage"] = build_report_coverage(timeseries, daily_rows)
        daily_source = "window.PSD2_DAILY_DATA = " + stable_json(daily_rows)
        (output_path.parent / "daily-data.js").write_text(daily_source, encoding="utf-8")
        daily_version = hashlib.sha256(daily_source.encode()).hexdigest()[:12]
        payload["daily_history_asset"] = f"daily-data.js?v={daily_version}"
        payload["archive"] = archive.summary()
    elif isinstance(previous, dict):
        for key in ("daily_history", "daily_history_asset", "archive", "report_coverage"):
            if key in previous:
                payload[key] = previous[key]
    source = "window.PSD2_DATA = " + stable_json(payload)
    output_path.write_text(source, encoding="utf-8")
    cache_version = hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]
    for index_path in (output_path.parent / "index.html", output_path.parent / "report.html", output_path.parent / "archive.html", output_path.parent / "bank.html"):
        if not index_path.exists():
            continue
        content = index_path.read_text(encoding="utf-8")
        updated = re.sub(
            r'<script src="data\.js(?:\?v=[^"]+)?"></script>',
            f'<script src="data.js?v={cache_version}"></script>',
            content,
        )
        if daily_version and index_path.name in {"archive.html", "bank.html"}:
            updated = re.sub(r'<script src="daily-data\.js(?:\?v=[^"]+)?"></script>', f'<script src="daily-data.js?v={daily_version}"></script>', updated)
        if updated != content:
            index_path.write_text(updated, encoding="utf-8")


def history_availability(row: dict[str, Any]) -> float | None:
    """Jedna vykreslovaná hodnota; oddělené AISP/PISP jsou jen vizuální průměr."""
    def number(field: str) -> float | None:
        value = row.get(field)
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    overall = number("availability_pct")
    if overall is not None:
        return overall
    values = [value for field in ("aisp_availability_pct", "pisp_availability_pct")
              if (value := number(field)) is not None]
    return fmean(values) if values else None


def write_trend_svg(
    rows: list[dict[str, Any]], expected_period: str,
    output_path: Path = DEFAULT_TREND_SVG,
) -> None:
    """Statický graf fungující i v soukromém GitHub README bez JavaScriptu."""
    periods = recent_quarters(expected_period, 8)
    period_index = {period: index for index, period in enumerate(periods)}
    by_bank: dict[str, dict[str, float]] = {}
    for row in rows:
        value = history_availability(row)
        if row.get("scope") == "main" and row.get("report_url") and row.get("period") in period_index and value is not None:
            by_bank.setdefault(str(row["bank"]), {})[str(row["period"])] = value
    selected = sorted(by_bank, key=lambda bank: (-len(by_bank[bank]), bank))
    selected = [bank for bank in selected if len(by_bank[bank]) >= 3][:6]
    if not selected:
        selected = sorted(by_bank, key=lambda bank: (-len(by_bank[bank]), bank))[:6]

    width, height = 1100, 520
    left, right, top, bottom = 88, 755, 139, 399
    palette = ["#0F766E", "#C66B1A", "#3E6D8E", "#8A5D9E", "#B2433F", "#5F7A45"]
    values = [value for bank in selected for value in by_bank[bank].values()]
    minimum = max(0.0, (int((min(values) - 0.35) * 10) / 10) if values else 95.0)
    maximum = max(100.0, max(values) + 0.05) if values else 100.0
    if maximum - minimum < 0.5:
        minimum = maximum - 0.5

    x = lambda index: left + index * (right - left) / (len(periods) - 1)
    y = lambda value: bottom - (value - minimum) * (bottom - top) / (maximum - minimum)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Dostupnost PSD2 API v čase</title>',
        '<desc id="desc">Čtvrtletní dostupnost dle publikovaných reportů bank. Chybějící reporty přerušují čáru; samotný graf neměří živý provoz.</desc>',
        '<rect width="1100" height="520" rx="24" fill="#F8FAF9"/>',
        '<rect x="22" y="20" width="1056" height="480" rx="20" fill="#FFFFFF" stroke="#DCE8E4"/>',
        '<text x="61" y="64" font-family="Arial,sans-serif" font-size="14" font-weight="700" letter-spacing="2" fill="#0F766E">PSD2 / ČESKÉ BANKY</text>',
        '<text x="61" y="105" font-family="Arial,sans-serif" font-size="29" font-weight="700" fill="#172C37">Dostupnost API v čase</text>',
        '<text x="816" y="105" font-family="Arial,sans-serif" font-size="13" fill="#58707A">Posledních 8 čtvrtletí</text>',
        f'<rect x="{x(len(periods) - 1) - 32:.1f}" y="132" width="64" height="272" rx="10" fill="#F0F8F5"/>',
    ]
    for tick in range(5):
        value = minimum + (maximum - minimum) * tick / 4
        yy = y(value)
        parts.extend([
            f'<line x1="{left}" y1="{yy:.1f}" x2="{right}" y2="{yy:.1f}" stroke="#DFE9E6"/>',
            f'<text x="{left - 13}" y="{yy + 4:.1f}" text-anchor="end" font-family="Arial,sans-serif" font-size="12" fill="#667D83">{value:.1f} %</text>',
        ])
    for period, index in period_index.items():
        parts.append(
            f'<text x="{x(index):.1f}" y="426" text-anchor="middle" font-family="Arial,sans-serif" font-size="12" fill="#5C737A">{xml_escape(period.replace("-", " "))}</text>'
        )
    for color_index, bank in enumerate(selected):
        color = palette[color_index]
        points = sorted(((period_index[period], value) for period, value in by_bank[bank].items()), key=lambda item: item[0])
        path = ""
        previous_index = -2
        for index, value in points:
            path += f'{"L" if index == previous_index + 1 else "M"}{x(index):.1f},{y(value):.1f} '
            previous_index = index
        parts.append(f'<path d="{path.strip()}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>')
        for index, value in points:
            parts.append(f'<circle cx="{x(index):.1f}" cy="{y(value):.1f}" r="4.5" fill="{color}" stroke="#FFFFFF" stroke-width="2"/>')
        legend_y = 162 + color_index * 44
        parts.extend([
            f'<circle cx="818" cy="{legend_y - 4}" r="5" fill="{color}"/>',
            f'<text x="834" y="{legend_y}" font-family="Arial,sans-serif" font-size="14" fill="#253E47">{xml_escape(bank)}</text>',
            f'<text x="834" y="{legend_y + 17}" font-family="Arial,sans-serif" font-size="11" fill="#789096">{len(points)} doložených čtvrtletí</text>',
        ])
    parts.extend([
        '<line x1="61" y1="452" x2="1039" y2="452" stroke="#E6EFEC"/>',
        '<text x="61" y="476" font-family="Arial,sans-serif" font-size="12" fill="#657B82">Zveřejněné bankovní statistiky, nikoli živé měření. Mezery v datech nejsou automaticky výpadek API.</text>',
        '</svg>',
    ])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def row_fingerprint(row: dict[str, Any]) -> str:
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_outputs(observations: list[Observation], data_dir: Path, today: date) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    latest_json = data_dir / "latest.json"
    latest_csv = data_dir / "latest.csv"
    history_csv = data_dir / "history.csv"

    previous_rows: dict[str, dict[str, Any]] = {}
    if latest_json.exists():
        try:
            previous_rows = {
                item["bank_id"]: {field: item.get(field, "") for field in CSV_FIELDS}
                for item in json.loads(latest_json.read_text(encoding="utf-8"))
            }
        except (json.JSONDecodeError, KeyError, TypeError):
            previous_rows = {}

    rows = [observation_row(observation) for observation in observations]
    latest_json.write_text(stable_json(rows), encoding="utf-8")
    with latest_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    changed = [
        row
        for row in rows
        if row_fingerprint(row) != row_fingerprint(previous_rows.get(row["bank_id"], {}))
    ]
    if changed:
        history_fields = ["observed_on", *CSV_FIELDS]
        exists = history_csv.exists() and history_csv.stat().st_size > 0
        with history_csv.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=history_fields, lineterminator="\n")
            if not exists:
                writer.writeheader()
            for row in changed:
                writer.writerow({"observed_on": today.isoformat(), **row})


def display_number(value: float | None, suffix: str = "") -> str:
    if value is None:
        return "—"
    rendered = f"{value:.4f}".rstrip("0").rstrip(".")
    return f"{rendered}{suffix}"


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def availability_display(observation: Observation) -> str:
    if observation.availability_pct is not None:
        return display_number(observation.availability_pct, " %")
    parts = []
    if observation.aisp_availability_pct is not None:
        parts.append(f"AISP {display_number(observation.aisp_availability_pct, ' %')}")
    if observation.pisp_availability_pct is not None:
        parts.append(f"PISP {display_number(observation.pisp_availability_pct, ' %')}")
    return " / ".join(parts) if parts else "—"


def generated_dashboard(observations: list[Observation], expected: str) -> str:
    main = [item for item in observations if item.scope == "main"]
    candidates = [item for item in observations if item.scope != "main"]
    counts = {status: sum(item.status == status for item in main) for status in STATUS_LABELS}
    lines = [
        f"Očekávané poslední zveřejněné období: **{expected}** (po 45denní lhůtě na publikaci).",
        "",
        (
            f"Souhrn hlavního seznamu: **{counts['ok']} s aktuální dostupností**, "
            f"**{counts['partial']} s částečnými daty**, **{counts['outdated']} zastaralé**, "
            f"**{counts['missing']} bez nalezeného reportu**, **{counts['blocked']} blokováno**."
            f" **{counts['unverified']} s neověřeným českým rozsahem reportu**."
        ),
        "",
        "| Banka | Stav | Poslední období | Dostupnost | Odezva AISP / PISP | Zdroj |",
        "|---|---|---:|---:|---:|---|",
    ]
    for item in main:
        response = " / ".join(
            [display_number(item.aisp_response_ms, " ms"), display_number(item.pisp_response_ms, " ms")]
        )
        links = f"[stránka]({item.source_url})"
        if item.report_url and item.report_url != item.source_url:
            links += f" · [report]({item.report_url})"
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_escape(item.bank),
                    STATUS_LABELS[item.status],
                    item.latest_period or "—",
                    availability_display(item),
                    response,
                    links,
                ]
            )
            + " |"
        )

    if candidates:
        lines.extend(
            [
                "",
                "### Kandidáti na rozšíření rozsahu",
                "",
                "| Instituce | Stav | Proč je zde | Zdroj |",
                "|---|---|---|---|",
            ]
        )
        for item in candidates:
            lines.append(
                f"| {markdown_escape(item.bank)} | {STATUS_LABELS[item.status]} | "
                f"{markdown_escape(item.note)} | [stránka]({item.source_url}) |"
            )
    return "\n".join(lines)


def update_readme(readme_path: Path, observations: list[Observation], expected: str) -> None:
    start = "<!-- TRACKER:START -->"
    end = "<!-- TRACKER:END -->"
    generated = generated_dashboard(observations, expected)
    if readme_path.exists():
        content = readme_path.read_text(encoding="utf-8")
    else:
        content = "# CZ PSD2 API tracker\n\n"
    block = f"{start}\n{generated}\n{end}"
    if start in content and end in content:
        content = re.sub(
            re.escape(start) + r".*?" + re.escape(end),
            block,
            content,
            flags=re.DOTALL,
        )
    else:
        content = content.rstrip() + "\n\n" + block + "\n"
    readme_path.write_text(content, encoding="utf-8")


def run(
    config_path: Path = DEFAULT_CONFIG,
    data_dir: Path = DEFAULT_DATA,
    readme_path: Path = DEFAULT_README,
    today: date | None = None,
    refresh_history: bool = False,
) -> list[Observation]:
    today = today or date.today()
    expected = expected_report_period(today)
    banks = json.loads(config_path.read_text(encoding="utf-8"))
    archive = Archive(data_dir / "archive", today)
    previous_by_id: dict[str, dict[str, Any]] = archive.latest_rows()
    previous_file = data_dir / "latest.json"
    if previous_file.exists():
        try:
            previous_by_id = {
                item["bank_id"]: item
                for item in json.loads(previous_file.read_text(encoding="utf-8"))
            }
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # A damaged latest export must not discard the persistent fallback.
    fetcher = Fetcher(archive=archive)
    observations: list[Observation] = []
    for bank in banks:
        fetcher.bank_id = bank["id"]
        print(f"Kontroluji {bank['name']}...", flush=True)
        observation = collect_bank(
            bank,
            fetcher,
            today,
            expected,
            previous_by_id.get(bank["id"]),
        )
        observations.append(observation)
        archive.record_snapshot({**observation_row(observation), "report_details": observation.report_details}, "latest-check")
        archive.record_daily(observation)
        print(
            f"  {observation.status}: {observation.latest_period or '-'}; "
            f"{availability_display(observation)}",
            flush=True,
        )
    write_outputs(observations, data_dir, today)
    existing_timeseries: list[dict[str, Any]] = []
    timeseries_file = data_dir / "timeseries.json"
    if timeseries_file.exists():
        try:
            loaded = json.loads(timeseries_file.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing_timeseries = loaded
        except json.JSONDecodeError:
            existing_timeseries = []
    archived_timeseries = {(row["bank_id"], row["period"]): row for row in archive.quarterly_rows()}
    archived_timeseries.update({(row["bank_id"], row["period"]): row for row in existing_timeseries})
    timeseries = collect_timeseries(
        banks,
        fetcher,
        observations,
        expected,
        list(archived_timeseries.values()),
        refresh=refresh_history,
    )
    timeseries = merge_derived_quarters(timeseries, derive_archived_quarters(banks, archive.daily_rows(), today))
    write_timeseries(timeseries, data_dir)
    for row in timeseries:
        archive.record_snapshot(row, "quarterly-derived" if row.get("report_kind") == "archive-derived" else "quarterly-report")
    archive.export(data_dir)
    write_dashboard_data(observations, timeseries, expected, today, archive=archive)
    write_trend_svg(timeseries, expected)
    update_readme(readme_path, observations, expected)
    return observations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--readme", type=Path, default=DEFAULT_README)
    parser.add_argument("--date", type=date.fromisoformat, help="Datum behu YYYY-MM-DD (pro testy)")
    parser.add_argument("--refresh-history", action="store_true", help="Znovu nacist i archivni reporty")
    arguments = parser.parse_args(argv)
    observations = run(
        arguments.config,
        arguments.data_dir,
        arguments.readme,
        arguments.date,
        arguments.refresh_history,
    )
    if not any(item.source_state.startswith("ok") for item in observations):
        print("Zadny zdroj nebyl dostupny; data nebyla spolehlive overena.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
