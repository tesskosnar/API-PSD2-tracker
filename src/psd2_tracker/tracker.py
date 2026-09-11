from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import http.cookiejar
import io
import json
import re
import sys
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlparse, urlsplit, urlunsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener
from xml.etree import ElementTree

from lxml import html
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "banks.json"
DEFAULT_DATA = ROOT / "data"
DEFAULT_README = ROOT / "README.md"

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

STATUS_LABELS = {
    "ok": "OK",
    "partial": "Částečná data",
    "outdated": "Zastaralé",
    "missing": "Nenalezen report",
    "blocked": "Zdroj blokuje automatizaci",
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
                setattr(self, field, round(float(value), 4))
        return self


class Fetcher:
    def __init__(self, timeout: float = 45.0):
        self.timeout = timeout
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
                    return HttpResponse(
                        content=content,
                        url=response.geturl(),
                        status_code=response.status,
                        headers=response.headers,
                    )
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

    if layout == "standard_minutes":
        api_minutes: list[float] = []
        for line in lines:
            match = re.match(rf"^{date_prefix}\s+(\d{{1,4}})\s+(\d{{1,4}})(?:\s|$)", line)
            if match:
                api_minutes.append(float(match.group(2)))
        if api_minutes:
            result["availability_pct"] = sum(api_minutes) / (1440 * len(api_minutes)) * 100
            result["metric_method"] = "soucet minut provozu API / kalendarni minuty"
        return result

    if layout == "fio":
        up_minutes: list[float] = []
        down_minutes: list[float] = []
        for line in lines:
            match = re.match(rf"^{date_prefix}\s+(\d{{1,4}})\s+(\d{{1,4}})(?:\s|$)", line)
            if match:
                up_minutes.append(float(match.group(1)))
                down_minutes.append(float(match.group(2)))
        total = sum(up_minutes) + sum(down_minutes)
        if total:
            result["availability_pct"] = sum(up_minutes) / total * 100
            result["metric_method"] = "soucet PSD2 API provozu / (provoz + vypadek)"
        return result

    if layout == "trinity":
        uptimes: list[float] = []
        for line in lines:
            match = re.match(
                rf"^\S+\s+{date_prefix}\s+\d+\s+[\d,.]+%\s+([\d,.]+)%",
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
                aisp_response_ms=fmean(aisp_responses),
                pisp_response_ms=fmean(pisp_responses),
                aisp_error_pct=fmean(errors),
                pisp_error_pct=fmean(errors),
                metric_method="aritmeticky prumer dennich uptime hodnot",
            )
        return result

    if layout == "creditas":
        uptimes: list[float] = []
        aisp_responses: list[float] = []
        pisp_responses: list[float] = []
        record_pattern = re.compile(
            rf"(?ms)^[ \t]*({date_prefix})\s+(.*?)(?=^[ \t]*{date_prefix}\s+|\Z)"
        )
        value_pattern = re.compile(r"\d+(?: \d{3})*,\d{2}")
        for record in record_pattern.finditer(text):
            values = [parse_number(value) for value in value_pattern.findall(record.group(2))]
            clean = [value for value in values if value is not None]
            if len(clean) < 3:
                continue
            uptimes.append(clean[-2])
            responses = clean[:-3]
            if len(responses) >= 2:
                aisp_responses.append(responses[0])
                pisp_responses.append(responses[1])
        if uptimes:
            result["availability_pct"] = fmean(uptimes)
            result["aisp_response_ms"] = average(aisp_responses)
            result["pisp_response_ms"] = average(pisp_responses)
            result["metric_method"] = "aritmeticky prumer dennich uptime hodnot"
        return result

    if layout == "ppf":
        result["metric_method"] = "banka v PDF nepublikuje uptime"
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
    candidates = find_report_candidates(
        response.text,
        response.url,
        bank.get("report_pattern", r"PSD2|availability|dostupnost|report"),
    )
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
    except (FetchError, ValueError) as exc:
        observation.source_state = "report-error"
        observation.note = f"{observation.note} PDF se nepodarilo zpracovat: {exc}".strip()
    return observation


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
        rows = parse_first_xlsx_sheet(report.content)
        data_rows = [row for row in rows if parse_number(row.get("C")) is not None]
        observation.aisp_response_ms = average(parse_number(row.get("C")) for row in data_rows)
        observation.pisp_response_ms = average(parse_number(row.get("F")) for row in data_rows)
        observation.aisp_error_pct = average(parse_number(row.get("D")) for row in data_rows)
        observation.pisp_error_pct = average(parse_number(row.get("G")) for row in data_rows)
        observation.metric_method = "prumer dennich XLSX hodnot odezvy a chybovosti; uptime chybi"
    except (FetchError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        observation.source_state = "report-error"
        observation.note = f"{observation.note} XLSX se nepodarilo zpracovat: {exc}".strip()
    return observation


def parse_unicredit(bank: dict[str, Any], fetcher: Fetcher) -> Observation:
    observation = base_observation(bank)
    response = fetcher.get(bank["source_url"])
    data = extract_balanced_json(response.text, "var kpiData = {")
    country = data.get("CZ-B") or data.get("CZ")
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
    year, quarter, _, _ = max(dated)
    selected = [row for y, q, _, row in dated if y == year and q == quarter]
    observation.latest_period = f"{year}-Q{quarter}"
    observation.report_url = bank["source_url"]
    observation.availability_pct = average(parse_number(row.get("uptime")) for row in selected)
    observation.aisp_response_ms = average(parse_number(row.get("ais")) for row in selected)
    observation.pisp_response_ms = average(parse_number(row.get("pis")) for row in selected)
    error = average(parse_number(row.get("error_response_rate")) for row in selected)
    observation.aisp_error_pct = error
    observation.pisp_error_pct = error
    observation.metric_method = "prumer mesicnich hodnot CZ Dedicated Interface"
    return observation


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
    observation.aisp_response_ms = average(record.get("aisp_response") for record in records)  # type: ignore[arg-type]
    observation.pisp_response_ms = average(record.get("pisp_response") for record in records)  # type: ignore[arg-type]
    observation.aisp_error_pct = average(record.get("aisp_error") for record in records)  # type: ignore[arg-type]
    observation.pisp_error_pct = average(record.get("pisp_error") for record in records)  # type: ignore[arg-type]
    observation.metric_method = "prumer dennich hodnot v klouzavem 90dennim okne; uptime chybi"
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
            response = fetcher.get(report_url, headers={"Accept": "application/pdf,*/*;q=0.8"})
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
        return observation
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
        elif parser_name == "unicredit":
            observation = parse_unicredit(bank, fetcher)
        elif parser_name == "moneta":
            observation = parse_moneta(bank, fetcher)
        elif parser_name == "creditas":
            observation = parse_creditas(bank, fetcher, today)
        elif parser_name == "oberbank":
            observation = parse_oberbank(bank, fetcher)
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
    observation = carry_previous(observation, previous)
    observation = apply_seed(bank, observation)
    return finalize_status(observation, expected_period)


def observation_row(observation: Observation) -> dict[str, Any]:
    row = asdict(observation)
    return {field: row.get(field, "") if row.get(field) is not None else "" for field in CSV_FIELDS}


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
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
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
            writer = csv.DictWriter(handle, fieldnames=history_fields)
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
) -> list[Observation]:
    today = today or date.today()
    expected = expected_report_period(today)
    banks = json.loads(config_path.read_text(encoding="utf-8"))
    previous_by_id: dict[str, dict[str, Any]] = {}
    previous_file = data_dir / "latest.json"
    if previous_file.exists():
        try:
            previous_by_id = {
                item["bank_id"]: item
                for item in json.loads(previous_file.read_text(encoding="utf-8"))
            }
        except (json.JSONDecodeError, KeyError, TypeError):
            previous_by_id = {}
    fetcher = Fetcher()
    observations: list[Observation] = []
    for bank in banks:
        print(f"Kontroluji {bank['name']}...", flush=True)
        observation = collect_bank(
            bank,
            fetcher,
            today,
            expected,
            previous_by_id.get(bank["id"]),
        )
        observations.append(observation)
        print(
            f"  {observation.status}: {observation.latest_period or '-'}; "
            f"{availability_display(observation)}",
            flush=True,
        )
    write_outputs(observations, data_dir, today)
    update_readme(readme_path, observations, expected)
    return observations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--readme", type=Path, default=DEFAULT_README)
    parser.add_argument("--date", type=date.fromisoformat, help="Datum behu YYYY-MM-DD (pro testy)")
    arguments = parser.parse_args(argv)
    observations = run(arguments.config, arguments.data_dir, arguments.readme, arguments.date)
    if not any(item.source_state.startswith("ok") for item in observations):
        print("Zadny zdroj nebyl dostupny; data nebyla spolehlive overena.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
