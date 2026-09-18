(function (root) {
  "use strict";
  const number = value => value === "" || value === null || value === undefined || !Number.isFinite(Number(value)) ? null : Number(value);
  const format = (value, digits = 3) => number(value) === null ? "—" : new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: digits }).format(Number(value));
  const shortPeriod = period => (period || "").replace(/^(\d{4})-Q([1-4])$/, "$2Q$1");
  const dateLabel = value => /^\d{4}-\d{2}-\d{2}$/.test(value || "") ? new Intl.DateTimeFormat("cs-CZ", {timeZone:"UTC"}).format(new Date(`${value}T00:00:00Z`)) : "—";
  const periodLabel = period => { const rolling = /^rolling-(\d+)d-to-(\d{4}-\d{2}-\d{2})$/.exec(period || ""); return rolling ? `${rolling[1]}denní přehled do ${dateLabel(rolling[2])}` : shortPeriod(period); };
  const availability = row => {
    const overall = number(row.availability_pct);
    if (overall !== null) return overall;
    const parts = [number(row.aisp_availability_pct), number(row.pisp_availability_pct)].filter(value => value !== null);
    return parts.length ? parts.reduce((sum, value) => sum + value, 0) / parts.length : null;
  };
  const shared = row => (row.metric_method || "").includes("spolecna error response rate");
  const definitions = [
    ["availability", "Dostupnost", "availability_pct", "%", true],
    ["aispAvailability", "Dostupnost AISP", "aisp_availability_pct", "%", true],
    ["pispAvailability", "Dostupnost PISP", "pisp_availability_pct", "%", true],
    ["aispResponse", "Odezva AISP", "aisp_response_ms", "ms", false],
    ["pispResponse", "Odezva PISP", "pisp_response_ms", "ms", false],
    ["aispError", "Chybovost AISP", "aisp_error_pct", "%", false],
    ["pispError", "Chybovost PISP", "pisp_error_pct", "%", false],
    ["sharedError", "Společná chybovost", "shared_error_pct", "%", false],
  ];
  const metrics = Object.fromEntries(definitions.map(([key, label, field, unit, higher]) => [key, {
    key, label, field, unit, higher,
    value: row => key === "availability" ? availability(row) : key === "sharedError" ? number(row.shared_error_pct ?? (shared(row) ? row.aisp_error_pct : null)) : key.endsWith("Error") && shared(row) ? null : number(row[field]),
    format: value => `${format(value, unit === "ms" ? 1 : number(value) > 0 && number(value) < .01 ? 4 : 3)} ${unit}`,
    note: higher ? "Vyšší hodnota je lepší." : "Nižší hodnota je lepší.",
  }]));
  metrics.availability.note += " Pokud banka publikuje jen oddělené AISP/PISP hodnoty, souhrn je jejich nevážený průměr. Samostatné hodnoty najdete v dalších metrikách; nevypočítáváme je ze souhrnu.";
  metrics.sharedError.note += " Společná chybovost není samostatnou chybovostí AISP ani PISP.";
  const median = values => {
    const sorted = values.map(number).filter(value => value !== null).sort((a, b) => a - b);
    if (!sorted.length) return null;
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  };
  const scale = (key, reference = []) => {
    const metric = metrics[key];
    const values = reference.map(metric.value).filter(value => value !== null);
    const center = median(values);
    // A central band of median ± median absolute deviation avoids treating
    // every tiny difference from the median as better or worse. Zero MAD is
    // valid for a flat series or a zero-heavy metric: equal values stay neutral.
    const deviation = center === null ? null : median(values.map(value => Math.abs(value - center)));
    const low = center === null ? null : Math.max(0, center - deviation);
    const high = center === null ? null : Math.min(metric.unit === "%" ? 100 : Infinity, center + deviation);
    const threshold = value => `${format(value, 6)} ${metric.unit}`;
    const titles = center === null ? ["Referenční údaje chybí", "Referenční údaje chybí", "Referenční údaje chybí"] : [
      `${metric.higher ? (deviation ? "≥ " : "> ") + threshold(high) : (deviation ? "≤ " : "< ") + threshold(low)}`,
      deviation ? `Mezi ${threshold(low)} a ${threshold(high)}; hranice patří krajním barvám. Medián ± medián absolutních odchylek.` : `Přesně na mediánu ${threshold(center)}; běžná odchylka je nulová.`,
      `${metric.higher ? (deviation ? "≤ " : "< ") + threshold(low) : (deviation ? "≥ " : "> ") + threshold(high)}`,
    ];
    return { median: center, deviation, low, high, count: values.length, labels: ["Lepší než obvyklé", "Kolem mediánu", "Horší než obvyklé"], titles };
  };
  const band = (key, value, referenceScale) => {
    const parsed = number(value);
    if (parsed === null) return null;
    if (!referenceScale || referenceScale.median === null) return 1;
    const tolerance = Number.EPSILON * Math.max(1, Math.abs(parsed), Math.abs(referenceScale.median)) * 8;
    if (referenceScale.deviation <= tolerance) {
      if (parsed < referenceScale.median - tolerance) return metrics[key].higher ? 2 : 0;
      if (parsed > referenceScale.median + tolerance) return metrics[key].higher ? 0 : 2;
      return 1;
    }
    if (parsed <= referenceScale.low + tolerance) return metrics[key].higher ? 2 : 0;
    if (parsed >= referenceScale.high - tolerance) return metrics[key].higher ? 0 : 2;
    return 1;
  };
  const isSummaryReport = row => row?.bank_id === "mbank" && row.report_kind === "summary" && row.country_scope === "unverified";
  const summaryNote = "Souhrnný report mBank – samostatný český rozsah nepotvrzen. Údaje jsou zahrnuty do statistik trackeru, nikoli doloženy jako samostatné metriky ČR.";
  const methodNote = row => isSummaryReport(row) || (row.bank_id === "mbank" && row.country_code === "unverified") ? summaryNote : row.report_kind === "archive-derived"
    ? `Vypočtený souhrn trackeru z denního archivu (${row.archived_days}/${row.calendar_days} dnů), nikoli čtvrtletní report banky. Odezva je průměr denních hodnot nad 0 ms; chybovost je nevážený průměr denních procent, ne podíl všech chybných volání. Chybějící dny se nedoplňují a dostupnost nelze z těchto údajů odvodit.`
    : row.status === "unverified" ? "Veřejné reporty existují, ale jejich samostatný český rozsah není jednoznačně doložen. Čísla proto nejsou vydávána za české metriky."
    : row.bank_id === "partners"
    ? "Partners publikuje 30denní PSD2 API health-check, nikoli zde doložený čtvrtletní report. Zdroj neuvádí výpočet procenta, četnost kontrol ani pravidla započítání výpadků. Období je jiné a shoda metodiky s čtvrtletními statistikami není doložená. Údaj zachováváme jako doplňkový, nikoli jako hodnocení kvality banky."
    : row.bank_id === "moneta" ? "Pohyblivý 90denní přehled odezvy a chybovosti, nikoli měření dostupnosti za celé vybrané čtvrtletí."
      : "Banky používají různé publikované metodiky. Shodné období samo o sobě nezaručuje shodný způsob měření.";
  const hasMetrics = row => Object.values(metrics).some(metric => metric.value(row) !== null);
  const isCzReport = row => Boolean(row?.report_url) && row.status !== "unverified" && (!row.country_code || row.country_code === "CZ") && (!row.country_scope || row.country_scope === "CZ");
  const isIncludedReport = row => isCzReport(row) || Boolean(row?.report_url && isSummaryReport(row));
  // A document on a Czech portal is not proof that its statistics cover CZ.
  // Catalog-only documents require an explicit, verified country scope.
  const czSourceReports = details => Object.values(details || {}).filter(detail => detail.country_scope === "CZ").flatMap(detail => (detail.published_reports || []).filter(isCzReport));
  // Supplementary documents stay separate from Czech numeric history and report counts.
  function supplementaryReports(details, bankId) {
    const seen = new Set();
    return Object.values(details || {}).flatMap(detail => (detail.published_reports || []).map(row => ({
      ...row, country_scope: row.country_code || row.country_scope || detail.country_scope || "unverified"
    }))).filter(row => {
      if (row.bank_id !== bankId || !row.report_url || isCzReport(row) || seen.has(row.report_url)) return false;
      seen.add(row.report_url); return true;
    }).sort((a, b) => (b.last_day || b.period || "").localeCompare(a.last_day || a.period || ""));
  }
  const reportCountryLabel = row => row.country_scope === "CZ" && row.status === "unverified"
    ? "Český rozsah neověřen"
    : ({ CZ: "Česko", PL: "Polsko", SK: "Slovensko", AT: "Rakousko" })[row.country_scope] || "Země neověřena · CZ nepotvrzeno";
  function bankMetricCoverage(banks, history, metricKey) {
    const metric = metrics[metricKey];
    const counts = new Map(banks.map(row => [row.bank, 0]));
    for (const row of history) {
      if (counts.has(row.bank) && metric.value(row) !== null) counts.set(row.bank, counts.get(row.bank) + 1);
    }
    return [...counts.entries()].sort((a, b) => Number(b[1] > 0) - Number(a[1] > 0) || a[0].localeCompare(b[0], "cs"));
  }
  function comparisonRows(latest, history, mode, quarter) {
    if (mode === "latest") return latest.map(row => ({ ...row, comparison_group: row.bank_id === "partners" ? "healthcheck" : /^rolling-/.test(row.latest_period || "") ? "rolling" : row.latest_period === quarter ? "quarter" : /^\d{4}-Q[1-4]$/.test(row.latest_period || "") ? "older" : "missing" }));
    return latest.map(row => {
      const report = history.find(item => item.bank_id === row.bank_id && item.period === quarter && item.report_url);
      if (report) return { ...row, ...report, latest_period: quarter, comparison_group: report.report_kind === "archive-derived" ? "derived" : "quarter", status: isSummaryReport(report) ? "unverified" : hasMetrics(report) ? number(report.availability_pct) !== null || availability(report) !== null ? "ok" : "partial" : "partial" };
      const empty = Object.fromEntries(definitions.map(([, , field]) => [field, ""]));
      return { ...row, ...empty, latest_period: "", report_url: row.status === "unverified" ? row.report_url : "", status: row.status === "unverified" ? "unverified" : "missing", comparison_group: "missing", fallback_period: row.latest_period, metric_method: row.status === "unverified" ? row.metric_method : "Pro vybrané čtvrtletí není doložený report." };
    });
  }
  const bankUrl = (id, period = "") => `bank.html?bank=${encodeURIComponent(id)}${period ? `&period=${encodeURIComponent(period)}` : ""}`;
  // Rows must contain measured days in ascending date order. Gaps are not interpolated.
  function nearestDailyPoint(rows, timestamp) {
    if (!rows.length || !Number.isFinite(timestamp)) return null;
    const time = row => new Date(`${row.date}T00:00:00Z`).getTime();
    let left = 0, right = rows.length;
    while (left < right) {
      const middle = Math.floor((left + right) / 2);
      if (time(rows[middle]) < timestamp) left = middle + 1;
      else right = middle;
    }
    if (!left) return rows[0];
    if (left === rows.length) return rows.at(-1);
    return timestamp - time(rows[left - 1]) <= time(rows[left]) - timestamp ? rows[left - 1] : rows[left];
  }
  const quarterRank = period => /^\d{4}-Q[1-4]$/.test(period || "")
    ? Number(period.slice(0, 4)) * 4 + Number(period.at(-1)) : NaN;
  function quarterDates(period) {
    if (!Number.isFinite(quarterRank(period))) return null;
    const year = Number(period.slice(0, 4)), quarter = Number(period.at(-1));
    return { from: new Date(Date.UTC(year, (quarter - 1) * 3, 1)).toISOString().slice(0, 10),
      to: new Date(Date.UTC(year, quarter * 3, 0)).toISOString().slice(0, 10) };
  }
  // Only supplied, measured quarters are selectable; gaps are not interpolated.
  function nearestQuarterPoint(rows, position) {
    if (!rows.length || !Number.isFinite(position)) return null;
    let left = 0, right = rows.length;
    while (left < right) {
      const middle = Math.floor((left + right) / 2);
      if (quarterRank(rows[middle].period) < position) left = middle + 1;
      else right = middle;
    }
    if (!left) return rows[0];
    if (left === rows.length) return rows.at(-1);
    return position - quarterRank(rows[left - 1].period) <= quarterRank(rows[left].period) - position ? rows[left - 1] : rows[left];
  }
  const reportUrl = row => row.bank_id === "unicredit" ? `report.html?bank=unicredit&period=${encodeURIComponent(row.period || row.latest_period || "")}` : row.report_url || row.source_url;
  const csvCell = value => {
    let text = String(value ?? "");
    if (/^[=+@\-]/.test(text)) text = "'" + text;
    return `"${text.replace(/"/g, '""')}"`;
  };
  const csv = (headers, rows) => "\ufeff" + [headers, ...rows].map(row => row.map(csvCell).join(",")).join("\r\n");
  function download(filename, headers, rows) {
    const url = URL.createObjectURL(new Blob([csv(headers, rows)], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = filename; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function share(button) {
    try { await navigator.clipboard.writeText(location.href); button.textContent = "Odkaz zkopírován ✓"; }
    catch { window.prompt("Zkopírujte odkaz na tento výběr:", location.href); }
    setTimeout(() => { button.textContent = "Sdílet výběr ↗"; }, 2500);
  }
  function appendMetricButtons(container, active, attribute = "metric") {
    for (const metric of Object.values(metrics)) {
      const button = document.createElement("button"); button.type = "button"; button.className = "metric-button";
      button.dataset[attribute] = metric.key; button.textContent = metric.label;
      button.classList.toggle("active", metric.key === active); button.setAttribute("aria-pressed", String(metric.key === active));
      container.append(button);
    }
  }
  function initializeNavigation() {
    const nav = document.querySelector(".top-nav");
    if (!nav || nav.dataset.initialized) return;
    nav.dataset.initialized = "true";
    const links = [...nav.querySelectorAll('.top-nav__sections a[href^="#"]')].map(link => ({ link, section: document.querySelector(link.getAttribute("href")) })).filter(item => item.section);
    let scheduled = false;
    const update = () => {
      scheduled = false;
      const height = Math.ceil(nav.getBoundingClientRect().height);
      document.documentElement.style.setProperty("--nav-offset", `${height + 16}px`);
      let current = null;
      for (const item of links) if (item.section.getBoundingClientRect().top <= height + 24) current = item.link;
      for (const { link } of links) {
        if (link === current) link.setAttribute("aria-current", "location");
        else link.removeAttribute("aria-current");
      }
    };
    const schedule = () => { if (!scheduled) { scheduled = true; requestAnimationFrame(update); } };
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    if (typeof ResizeObserver !== "undefined") new ResizeObserver(schedule).observe(nav);
    schedule();
    const alignInitialSection = () => requestAnimationFrame(() => {
      update();
      const target = links.find(({ link }) => link.getAttribute("href") === location.hash);
      if (target) target.section.scrollIntoView({ block: "start", behavior: "instant" });
      update();
    });
    if (document.readyState === "complete") alignInitialSection();
    else window.addEventListener("load", alignInitialSection, { once: true });
  }
  function coverageContent(container, data, row) {
    container.replaceChildren();
    const add = (tag, text, className = "") => { const el = document.createElement(tag); el.textContent = text; el.className = className; container.append(el); return el; };
    const period = row.period || row.latest_period || "";
    add("p", `${row.bank} · ${periodLabel(period) || "období nedoloženo"}`, "report-eyebrow");
    const coverage = data.report_coverage?.[`${row.bank_id}:${period}`];
    if (row.report_kind === "archive-derived") add("p", "Vypočtený souhrn · není publikovaným čtvrtletním reportem banky", "method-notice");
    if (row.report_kind === "archive-derived") { const daily=add("a", "Denní podklady výpočtu →", "bank-detail-link"); daily.href=`archive.html?bank=${encodeURIComponent(row.bank_id)}&dayFrom=${encodeURIComponent(row.first_day)}&dayTo=${encodeURIComponent(row.last_day)}&dailyMetric=aisp_response_ms`; }
    add("h3", coverage ? `Archivováno ${coverage.archived_days} z ${coverage.calendar_days} kalendářních dnů` : "Denní pokrytí není doložené");
    if (coverage?.archived_days) add("p", `Uložené dny: ${dateLabel(coverage.first_day)} až ${dateLabel(coverage.last_day)}.`, "chart-note");
    add("p", "Počet archivovaných dnů vyjadřuje vytěžené neprázdné denní záznamy, ne úplnost měření banky. Prázdné buňky ani chybějící dny nepovažujeme za nulu nebo výpadek.", "report-explanation");
    const list = add("dl", "", "coverage-metrics");
    for (const metric of Object.values(metrics)) {
      const value = metric.value(row), count = coverage?.metric_days?.[metric.field];
      if (value === null && !count) continue;
      const dt = document.createElement("dt"); dt.textContent = metric.label;
      const derived = metric.key === "availability" && number(row.availability_pct) === null && value !== null;
      const dd = document.createElement("dd"); dd.textContent = `${value === null ? "Souhrn není uveden" : metric.format(value)}${derived ? " · odvozený průměr AISP/PISP; původní metriky níže" : count ? ` · ${count} dnů s denním údajem` : " · denní pokrytí nedoloženo"}`;
      list.append(dt, dd);
    }
    add("p", `Publikovaná metodika / zpracování: ${row.metric_method || "Neuvedeno"}`, "chart-note");
    if (row.source_state === "report-error") add("p", `Report je uložen jako zdrojový doklad, jeho čísla však nejsou použita. ${row.metric_method || "Údaje nebylo možné spolehlivě ověřit."}`, "method-notice");
    else if (row.metric_method?.includes("hlavicka uvadi")) add("p", "Záhlaví reportu uvádí jiné období. Denní data jsou zařazena podle datumů řádků, která souhlasí s názvem v katalogu; původní datumy nebyly přepsány. Podrobnost je uvedena v metodice výše.", "method-notice");
    if (row.note) add("p", row.note, "chart-note");
    if (row.status === "unverified") add("p", methodNote(row), "method-notice");
    if (row.status === "unverified" && !isSummaryReport(row) && row.first_day && row.last_day) add("p", `Období skutečně uvedené v katalogu: ${dateLabel(row.first_day)} až ${dateLabel(row.last_day)}. Tento dokument není přeznačen na samostatná čtvrtletí.`, "chart-note");
    if (row.catalog_present === false) add("p", "Dokument je zachován z dřívějšího sběru; v aktuálním katalogu již uveden není. Živý zdroj mohl být odstraněn nebo změněn.", "method-notice");
    if (row.archived_source_url) { const archived=add("a", "Uchovaná zdrojová kopie (gzip) ↗", "bank-detail-link"); archived.href=row.archived_source_url; archived.target="_blank"; archived.rel="noopener noreferrer"; }
    if (row.bank_id === "partners" || row.bank_id === "moneta") add("p", methodNote(row), "method-notice");
    if (coverage && coverage.archived_days < coverage.calendar_days) add("p", "Denní archiv nepokrývá všechny kalendářní dny. Důvodem může být kratší report, prázdné metriky nebo omezení extrakce; úplné znění ověřte ve zdroji.", "method-notice");
    if (row.report_url || row.source_url) { const source = add("a", "Otevřít zdroj / report ↗", "report-source-button"); source.href = reportUrl(row); source.target = "_blank"; source.rel = "noopener noreferrer"; }
  }
  function reportCompleteness(row, coverage) {
    if (!isIncludedReport(row)) return "missing";
    if (row.source_state === "report-error" || !hasMetrics(row)) return "report";
    const supplied = Object.values(metrics).filter(metric => metric.value(row) !== null && (metric.key !== "availability" || number(row.availability_pct) !== null));
    return coverage && coverage.archived_days === coverage.calendar_days && supplied.every(metric => coverage.metric_days?.[metric.field] === coverage.calendar_days) ? "full" : "partial";
  }
  function createCoverageDialog() {
    const dialog = document.createElement("dialog"); dialog.className = "coverage-dialog"; dialog.setAttribute("aria-labelledby", "coverageDialogTitle");
    const heading = document.createElement("h2"); heading.id = "coverageDialogTitle"; heading.textContent = "Podrobnosti reportu";
    const close = document.createElement("button"); close.type = "button"; close.className = "dialog-close"; close.textContent = "Zavřít ×";
    const content = document.createElement("div"); content.className = "coverage-dialog-content";
    dialog.append(close, heading, content); document.body.append(dialog);
    close.addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", event => { if (event.target === dialog && (event.clientX < dialog.getBoundingClientRect().left || event.clientX > dialog.getBoundingClientRect().right || event.clientY < dialog.getBoundingClientRect().top || event.clientY > dialog.getBoundingClientRect().bottom)) dialog.close(); });
    return (data, row) => { coverageContent(content, data, row); const link = document.createElement("a"); link.href = bankUrl(row.bank_id, row.period); link.className = "bank-detail-link"; link.textContent = "Celý detail banky →"; content.append(link); dialog.showModal(); };
  }
  const api = { number, format, shortPeriod, dateLabel, periodLabel, metrics, availability, median, scale, band, methodNote, hasMetrics, isCzReport, isSummaryReport, isIncludedReport, summaryNote, czSourceReports, supplementaryReports, reportCountryLabel, bankMetricCoverage, comparisonRows, nearestDailyPoint, quarterRank, quarterDates, nearestQuarterPoint, bankUrl, reportUrl, csv, download, share, appendMetricButtons, initializeNavigation, coverageContent, reportCompleteness, createCoverageDialog };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PSD2_UI = api;
})(typeof window === "undefined" ? globalThis : window);
