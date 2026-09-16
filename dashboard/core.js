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
  const methodNote = row => row.bank_id === "partners"
    ? "Partners publikuje 30denní PSD2 API health-check, nikoli zde doložený čtvrtletní report. Zdroj neuvádí výpočet procenta, četnost kontrol ani pravidla započítání výpadků. Období je jiné a shoda metodiky s čtvrtletními statistikami není doložená. Údaj zachováváme jako doplňkový, nikoli jako hodnocení kvality banky."
    : row.bank_id === "moneta" ? "Pohyblivý 90denní přehled odezvy a chybovosti, nikoli měření dostupnosti za celé vybrané čtvrtletí."
      : "Banky používají různé publikované metodiky. Shodné období samo o sobě nezaručuje shodný způsob měření.";
  const hasMetrics = row => Object.values(metrics).some(metric => metric.value(row) !== null);
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
      if (report) return { ...row, ...report, latest_period: quarter, comparison_group: "quarter", status: hasMetrics(report) ? number(report.availability_pct) !== null || availability(report) !== null ? "ok" : "partial" : "partial" };
      const empty = Object.fromEntries(definitions.map(([, , field]) => [field, ""]));
      return { ...row, ...empty, latest_period: "", report_url: "", status: "missing", comparison_group: "missing", fallback_period: row.latest_period, metric_method: "Pro vybrané čtvrtletí není doložený report." };
    });
  }
  const bankUrl = (id, period = "") => `bank.html?bank=${encodeURIComponent(id)}${period ? `&period=${encodeURIComponent(period)}` : ""}`;
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
  function coverageContent(container, data, row) {
    container.replaceChildren();
    const add = (tag, text, className = "") => { const el = document.createElement(tag); el.textContent = text; el.className = className; container.append(el); return el; };
    const period = row.period || row.latest_period || "";
    add("p", `${row.bank} · ${periodLabel(period) || "období nedoloženo"}`, "report-eyebrow");
    const coverage = data.report_coverage?.[`${row.bank_id}:${period}`];
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
    if (row.note) add("p", row.note, "chart-note");
    if (row.bank_id === "partners" || row.bank_id === "moneta") add("p", methodNote(row), "method-notice");
    if (coverage && coverage.archived_days < coverage.calendar_days) add("p", "Denní archiv nepokrývá všechny kalendářní dny. Důvodem může být kratší report, prázdné metriky nebo omezení extrakce; úplné znění ověřte ve zdroji.", "method-notice");
    if (row.report_url || row.source_url) { const source = add("a", "Otevřít zdroj / report ↗", "report-source-button"); source.href = reportUrl(row); source.target = "_blank"; source.rel = "noopener noreferrer"; }
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
  const api = { number, format, shortPeriod, dateLabel, periodLabel, metrics, availability, median, scale, band, methodNote, hasMetrics, bankMetricCoverage, comparisonRows, bankUrl, reportUrl, csv, download, share, appendMetricButtons, coverageContent, createCoverageDialog };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PSD2_UI = api;
})(typeof window === "undefined" ? globalThis : window);
