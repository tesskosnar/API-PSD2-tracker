(() => {
  "use strict";

  const data = window.PSD2_DATA || { latest: [], timeseries: [], expected_period: "" };
  const ui = window.PSD2_UI;
  const latest = data.latest.filter(item => item.scope === "main");
  const history = data.timeseries.filter(item => item.scope === "main");
  const sourceReports = Object.values(data.source_details || {}).flatMap(detail => detail.published_reports || []);
  const allPeriods = [...new Set(history.map(item => item.period))].sort();
  const params = new URLSearchParams(location.search);
  let periods = allPeriods.slice(-8);
  if (allPeriods.includes(params.get("from")) && allPeriods.includes(params.get("to")) && params.get("from") <= params.get("to")) periods = allPeriods.filter(period => period >= params.get("from") && period <= params.get("to"));
  let visibleHistory = history.filter(item => periods.includes(item.period));
  const metrics = ui.metrics;
  const referenceHistory = history.filter(row => row.report_url);
  const metricScales = Object.fromEntries(Object.keys(metrics).map(key => [key, ui.scale(key, referenceHistory)]));

  let activeMetric = metrics[params.get("metric")] ? params.get("metric") : "availability";
  let selectedBanks = new Set();
  let latestSort = { key: params.get("sort") === "bank" || metrics[params.get("sort")] ? params.get("sort") : null, direction: params.get("direction") === "desc" ? "desc" : "asc" };
  let comparisonMode = params.get("mode") === "latest" ? "latest" : "quarter";
  let comparisonQuarter = allPeriods.includes(params.get("quarter")) ? params.get("quarter") : data.expected_period;
  let exportedLatest = [];
  const openCoverage = ui.createCoverageDialog();

  function syncUrl() {
    const url = new URL(location.href);
    url.searchParams.delete("v");
    for (const [key, value] of Object.entries({ metric: activeMetric, from: periods[0], to: periods.at(-1), mode: comparisonMode, quarter: comparisonQuarter, sort: latestSort.key, direction: latestSort.key ? latestSort.direction : null, search: document.getElementById("bankSearch").value, status: document.getElementById("statusFilter").value })) {
      if (value) url.searchParams.set(key, value); else url.searchParams.delete(key);
    }
    if (selectedBanks.size === latest.length) url.searchParams.delete("banks");
    else url.searchParams.set("banks", latest.filter(row => selectedBanks.has(row.bank)).map(row => row.bank_id).join(",") || "none");
    window.history.replaceState(null, "", url);
  }

  function numberOrNull(value) {
    if (value === "" || value === null || value === undefined) return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function availabilityValue(item) {
    const main = numberOrNull(item.availability_pct);
    if (main !== null) return main;
    const values = [numberOrNull(item.aisp_availability_pct), numberOrNull(item.pisp_availability_pct)].filter(value => value !== null);
    return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
  }

  function formatNumber(value, digits = 1) {
    return new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: digits, minimumFractionDigits: 0 }).format(value);
  }

  function formatPeriod(period) {
    const match = /^(\d{4})-Q([1-4])$/.exec(period || "");
    if (match) return `${match[2]}. čtvrtletí ${match[1]}`;
    const rolling = /^rolling-(\d+)d-to-(\d{4})-(\d{2})-(\d{2})$/.exec(period || "");
    if (rolling) return `${rolling[1]} dní do ${Number(rolling[4])}. ${Number(rolling[3])}. ${rolling[2]}`;
    return period || "—";
  }

  function shortPeriod(period) {
    return (period || "").replace(/^(\d{4})-Q([1-4])$/, "$2Q$1");
  }

  function statusLabel(status) {
    return ({ ok: "Aktuální", partial: "Částečná data", outdated: "Zastaralé", missing: "Bez reportu", blocked: "Zdroj blokován", unverified: "CZ rozsah neověřen" })[status] || status;
  }

  function sourceUrl(item) {
    if (item.bank_id === "unicredit") return `report.html?bank=unicredit&period=${encodeURIComponent(item.period || item.latest_period || "")}`;
    return item.report_url || item.source_url;
  }

  function latestPeriodCell(period) {
    const cell = document.createElement("td");
    cell.className = "latest-period";
    const quarter = /^(\d{4})-Q([1-4])$/.exec(period || "");
    const rolling = /^rolling-(\d+)d-to-(\d{4})-(\d{2})-(\d{2})$/.exec(period || "");
    if (quarter) {
      const label = document.createElement("span");
      label.className = "period-quarter";
      label.textContent = shortPeriod(period);
      cell.append(label);
      if (period < data.expected_period) {
        cell.classList.add("latest-period--older");
        const note = document.createElement("small");
        note.className = "period-note";
        note.textContent = "Poslední dostupné";
        cell.append(note);
        cell.title = `Starší report: ${formatPeriod(period)}. Pro ${formatPeriod(data.expected_period)} není novější report doložený.`;
      }
    } else if (rolling) {
      const count = Number(rolling[1]);
      const end = new Date(Date.UTC(Number(rolling[2]), Number(rolling[3]) - 1, Number(rolling[4])));
      const start = new Date(end);
      start.setUTCDate(start.getUTCDate() - count + 1);
      const shortDate = date => `${date.getUTCDate()}. ${date.getUTCMonth() + 1}. ${date.getUTCFullYear()}`;
      const endLabel = document.createElement("span");
      endLabel.textContent = shortDate(end);
      const note = document.createElement("small");
      note.className = "period-note";
      note.textContent = count === 30 ? "30 dní · health-check" : `${count}denní přehled`;
      const range = `${shortDate(start)} – ${shortDate(end)} (${count} dní včetně obou krajních dnů)${count === 30 ? "; PSD2 health-check, nikoli čtvrtletní RTS report" : ""}`;
      cell.title = range;
      cell.setAttribute("aria-label", range);
      cell.append(endLabel, note);
    } else cell.textContent = "—";
    return cell;
  }

  function displayAvailability(item) {
    const overall = numberOrNull(item.availability_pct);
    if (overall !== null) return `${formatNumber(overall, 3)} %`;
    const aisp = numberOrNull(item.aisp_availability_pct);
    const pisp = numberOrNull(item.pisp_availability_pct);
    if (aisp !== null || pisp !== null) {
      return `AISP ${aisp === null ? "—" : formatNumber(aisp, 3) + " %"} / PISP ${pisp === null ? "—" : formatNumber(pisp, 3) + " %"}`;
    }
    return "—";
  }

  function updateSummary() {
    const current = latest.filter(item =>
      (item.status === "ok" || item.status === "blocked")
      && item.latest_period === data.expected_period
      && item.report_url
      && availabilityValue(item) !== null
    ).length;
    document.getElementById("currentCoverage").textContent = `${current} z ${latest.length}`;
    document.getElementById("historyPoints").textContent = formatNumber(history.length, 0);
    const numericReports = history.filter(ui.hasMetrics).length;
    const derived = history.filter(row => row.report_kind === "archive-derived").length;
    document.getElementById("historyContext").textContent = derived ? `${numericReports - derived} s údaji z reportů · ${derived} výpočet z archivu · ${history.length - numericReports} bez hodnoty` : numericReports === history.length ? "součet reportovaných čtvrtletí všech bank" : `${numericReports} s údaji · ${history.length - numericReports} bez čtvrtletní hodnoty`;
    document.getElementById("bankCount").textContent = formatNumber(latest.length, 0);
    document.getElementById("periodLabel").textContent = `Poslední uzavřené období: ${formatPeriod(data.expected_period)}`;
    const checked = data.checked_on ? new Date(`${data.checked_on}T12:00:00`) : null;
    document.getElementById("checkedLabel").textContent = checked
      ? `Data zkontrolována: ${new Intl.DateTimeFormat("cs-CZ", { day: "numeric", month: "long", year: "numeric" }).format(checked)}`
      : "Datum poslední kontroly není dostupné";
  }

  function bankCoverage(metricKey) {
    return ui.bankMetricCoverage(latest, visibleHistory, metricKey);
  }

  function setPeriodRange(from, to) {
    periods = allPeriods.filter(period => period >= from && period <= to);
    visibleHistory = history.filter(item => periods.includes(item.period));
    const fromIndex = allPeriods.indexOf(from), toIndex = allPeriods.indexOf(to);
    document.getElementById("periodFrom").value = fromIndex;
    document.getElementById("periodTo").value = toIndex;
    document.getElementById("periodFromLabel").textContent = shortPeriod(from);
    document.getElementById("periodToLabel").textContent = shortPeriod(to);
    document.getElementById("periodFrom").setAttribute("aria-valuetext", formatPeriod(from));
    document.getElementById("periodTo").setAttribute("aria-valuetext", formatPeriod(to));
    const maximum = Math.max(1, allPeriods.length - 1);
    const fill = document.getElementById("periodSliderFill");
    fill.style.left = `${fromIndex / maximum * 100}%`;
    fill.style.width = `${(toIndex - fromIndex) / maximum * 100}%`;
    // When handles coincide, the earlier half of the track stays reachable.
    document.getElementById("periodFrom").style.zIndex = fromIndex === toIndex && fromIndex > maximum / 2 ? "4" : "2";
    document.querySelectorAll("[data-period-count]").forEach(button => {
      const count = Number(button.dataset.periodCount);
      const preset = count ? allPeriods.slice(-count) : allPeriods;
      const active = from === preset[0] && to === preset.at(-1);
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    document.getElementById("periodRangeInfo").textContent =
      `${shortPeriod(from)} – ${shortPeriod(to)} · ${periods.length} čtvrtletí · Posunutím krajních bodů upravíte rozsah`;
    renderLegend();
    renderGrid();
    syncUrl();
  }

  function initializePeriodControls() {
    ["periodFrom", "periodTo"].forEach(id => {
      const slider = document.getElementById(id);
      slider.max = Math.max(0, allPeriods.length - 1);
      slider.addEventListener("input", () => {
        let from = Number(document.getElementById("periodFrom").value);
        let to = Number(document.getElementById("periodTo").value);
        if (from > to) { if (id === "periodFrom") from = to; else to = from; }
        setPeriodRange(allPeriods[from], allPeriods[to]);
      });
    });
    document.getElementById("periodEarliest").textContent = shortPeriod(allPeriods[0]);
    document.getElementById("periodLatest").textContent = shortPeriod(allPeriods.at(-1));
    document.querySelectorAll("[data-period-count]").forEach(button => {
      button.addEventListener("click", () => {
        const count = Number(button.dataset.periodCount);
        const preset = count ? allPeriods.slice(-count) : allPeriods;
        setPeriodRange(preset[0], preset.at(-1));
      });
    });
    if (periods.length) setPeriodRange(periods[0], periods.at(-1));
  }

  function resetBankSelection() {
    selectedBanks = new Set(bankCoverage(activeMetric).map(([bank]) => bank));
  }

  function renderLegend() {
    const container = document.getElementById("chartLegend");
    container.replaceChildren();
    bankCoverage(activeMetric).forEach(([bank, count]) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = `legend-button${count ? "" : " legend-button--no-data"}`;
      button.setAttribute("aria-pressed", selectedBanks.has(bank) ? "true" : "false");
      button.title = count
        ? `${bank}: ${count} doložených období pro tuto metriku`
        : `${bank}: pro tuto metriku nejsou ve zvoleném období doložené hodnoty`;
      const swatch = document.createElement("span");
      swatch.className = "legend-swatch";
      const label = document.createElement("span");
      label.textContent = bank;
      button.append(swatch, label);
      button.addEventListener("click", () => {
        if (selectedBanks.has(bank)) selectedBanks.delete(bank); else selectedBanks.add(bank);
        renderLegend();
        renderGrid();
        syncUrl();
      });
      container.append(button);
    });
  }

  function renderGrid() {
    const table = document.getElementById("metricGrid");
    const empty = document.getElementById("chartEmpty");
    const metric = metrics[activeMetric];
    document.getElementById("chartNote").textContent = metric.note;
    const referenceScale = metricScales[activeMetric];
    const scaleKey = document.getElementById("scaleKey");
    scaleKey.replaceChildren();
    referenceScale.labels.forEach((label, index) => {
      const entry = document.createElement("span"); entry.className = `scale-band quality-${index}`; entry.textContent = label; entry.title = referenceScale.titles[index]; scaleKey.append(entry);
    });
    const directionLabel = document.createElement("span"); directionLabel.className = "scale-direction";
    directionLabel.textContent = "Tmavší zelená = lepší výsledek";
    scaleKey.append(directionLabel);
    const referenceLabel = document.createElement("span"); referenceLabel.className = "scale-median";
    referenceLabel.textContent = referenceScale.median === null ? "Medián není doložený" : `Medián: ${metric.format(referenceScale.median)}`;
    referenceLabel.title = `Reference: ${referenceScale.count} doložených bankovních čtvrtletí z celé historie této metriky. Střední pásmo: medián ± medián absolutních odchylek. Banky s delší historií mají více podkladů; nejde o společný regulatorní limit.`;
    scaleKey.append(referenceLabel);

    const bankEntries = bankCoverage(activeMetric).filter(([bank]) => selectedBanks.has(bank));
    const banks = bankEntries.map(([bank]) => bank);
    if (!banks.length) {
      table.hidden = true;
      empty.hidden = false;
      return;
    }
    table.hidden = false;
    empty.hidden = true;

    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    ["Banka", ...periods.map(shortPeriod)].forEach((label, index) => {
      const th = document.createElement("th");
      th.textContent = label;
      if (index === 0) th.className = "metric-grid__bank";
      headRow.append(th);
    });
    thead.append(headRow);

    const tbody = document.createElement("tbody");
    let missingSeparator = false;
    bankEntries.forEach(([bank, count]) => {
      if (!count && !missingSeparator) {
        const divider = document.createElement("tr"); divider.className = "metric-grid__divider latest-divider";
        const cell = document.createElement("td"); cell.colSpan = periods.length + 1;
        const label = document.createElement("span");
        label.textContent = `Bez údaje pro metriku: ${metric.label} ve zvoleném období · ${bankEntries.filter(([, value]) => !value).length} bank`;
        cell.append(label); divider.append(cell); tbody.append(divider); missingSeparator = true;
      }
      const row = document.createElement("tr");
      row.dataset.bank = latest.find(item => item.bank === bank).bank_id;
      row.dataset.hasValues = String(count > 0);
      if (!count) row.className = "metric-grid__row--no-data";
      const name = document.createElement("th");
      name.scope = "row";
      name.className = "metric-grid__bank";
      const detail = document.createElement("a"); detail.href = ui.bankUrl(latest.find(row => row.bank === bank).bank_id); detail.textContent = bank; detail.className = "bank-name-link"; name.append(detail);
      const reports = visibleHistory.filter(item => item.bank === bank && item.report_url);
      if (!reports.some(item => metric.value(item) !== null)) {
        const status = document.createElement("small");
        status.className = "metric-grid__status";
        status.textContent = reports.length ? "Metrika není doložená" : latest.find(row => row.bank === bank)?.status === "unverified" ? "CZ rozsah neověřen" : "Bez reportu v období";
        name.append(status);
      }
      row.append(name);
      periods.forEach(period => {
        const item = visibleHistory.find(point => point.bank === bank && point.period === period);
        const value = item ? metric.value(item) : null;
        const cell = document.createElement("td");
        cell.className = value === null ? "metric-grid__cell metric-grid__cell--empty" : `metric-grid__cell quality-${ui.band(activeMetric, value, referenceScale)}`;
        const content = document.createElement(item?.report_url ? "button" : "span");
        content.className = "metric-grid__value";
        content.textContent = value === null ? "—" : metric.format(value);
        content.title = `${bank} · ${formatPeriod(period)} · ${metric.label}: ${content.textContent}`;
        if (item?.metric_method) content.title += ` · ${item.metric_method}`;
        if (content.tagName === "BUTTON") {
          content.type = "button";
          content.addEventListener("click", () => openCoverage(data, item));
          content.title += " · podrobnosti reportu";
        }
        cell.append(content);
        if (item?.report_kind === "archive-derived") {
          const note = document.createElement("small"); note.className = "derived-note";
          note.textContent = `Výpočet · ${item.archived_days}/${item.calendar_days} dní`; cell.append(note);
        }
        row.append(cell);
      });
      tbody.append(row);
    });
    table.replaceChildren(thead, tbody);
  }

  function renderCoverage() {
    const table = document.getElementById("coverageTable");
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    ["Banka", ...allPeriods.map(shortPeriod)].forEach(label => {
      const th = document.createElement("th");
      th.textContent = label;
      headRow.append(th);
    });
    thead.append(headRow);
    const tbody = document.createElement("tbody");
    [...latest].sort((a, b) => a.bank.localeCompare(b.bank, "cs")).forEach(bank => {
      const tr = document.createElement("tr");
      const name = document.createElement("td");
      const detail = document.createElement("a"); detail.href = ui.bankUrl(bank.bank_id); detail.textContent = bank.bank; detail.className = "bank-name-link"; name.append(detail);
      tr.append(name);
      allPeriods.forEach(period => {
        const td = document.createElement("td");
        const item = history.find(row => row.bank_id === bank.bank_id && row.period === period) || sourceReports.find(row => row.bank_id === bank.bank_id && (row.period === period || row.periods?.includes(period)));
        const cell = document.createElement(item?.report_url ? "button" : "span");
        const hasReport = Boolean(item?.report_url);
        const completeness = ui.reportCompleteness(item, data.report_coverage?.[`${bank.bank_id}:${period}`]);
        const coverageState = ({full:"kompletní report",partial:"částečně vyplněn",report:"report bez použitelných metrik",missing:"bez reportu"})[completeness];
        cell.className = `coverage-cell${completeness === "missing" ? "" : ` coverage-cell--${completeness}`}${item?.report_kind === "archive-derived" ? " coverage-cell--derived" : ""}`;
        if (item?.report_kind === "archive-derived") cell.textContent = "Σ";
        cell.setAttribute("aria-label", `${bank.bank}, ${period}: ${coverageState}${hasReport ? "; podrobnosti reportu" : ""}`);
        cell.title = cell.getAttribute("aria-label");
        if (item?.status === "unverified") cell.title += " · veřejný report existuje, samostatný český rozsah čísel je neověřen";
        if (item?.report_kind === "archive-derived") cell.title += " · vypočtený souhrn z archivu, nikoli report zveřejněný bankou";
        if (item?.source_state === "report-error") cell.title += ` · ${item.metric_method}`;
        if (item?.report_url) {
          cell.type = "button";
          cell.addEventListener("click", () => openCoverage(data, item));
          const coverage = data.report_coverage?.[`${bank.bank_id}:${period}`];
          if (coverage) cell.title += ` · archivováno ${coverage.archived_days}/${coverage.calendar_days} dnů`;
        }
        td.append(cell);
        tr.append(td);
      });
      tbody.append(tr);
    });
    table.replaceChildren(thead, tbody);
    const scroll = table.closest(".table-scroll");
    requestAnimationFrame(() => { scroll.scrollLeft = scroll.scrollWidth; });
  }

  function renderLatest() {
    const tbody = document.getElementById("latestRows");
    tbody.replaceChildren();
    const normalize = value => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("cs");
    const search = normalize(document.getElementById("bankSearch").value.trim());
    const status = document.getElementById("statusFilter").value;
    const rows = ui.comparisonRows(latest, history, comparisonMode, comparisonQuarter).filter(item => normalize(item.bank).includes(search) && (!status || item.status === status));
    document.getElementById("latestCount").textContent = `Zobrazeno ${rows.length} z ${latest.length} bank`;
    const sortMetric = latestSort.key && latestSort.key !== "bank" ? metrics[latestSort.key] : null;
    const withValue = sortMetric ? rows.filter(item => sortMetric.value(item) !== null) : rows;
    const older = withValue.filter(item => /^\d{4}-Q[1-4]$/.test(item.latest_period) && item.latest_period < data.expected_period);
    const context = document.getElementById("latestContext");
    context.replaceChildren();
    const sortInfo = document.createElement("strong");
    sortInfo.textContent = sortMetric ? `${sortMetric.label} · ${latestSort.direction === "asc" ? "Od nejnižší" : "Od nejvyšší"} hodnoty · uvnitř skupin` : comparisonMode === "quarter" ? `Údaje ${ui.shortPeriod(comparisonQuarter)} · výpočty odděleně` : "Nejnovější údaje · oddělené typy měření";
    context.append(sortInfo);
    if (sortMetric) {
      const counts = document.createElement("span");
      counts.textContent = `${withValue.length} s hodnotou · ${rows.length - withValue.length} bez údaje`;
      context.append(counts);
    }
    const periodInfo = document.createElement("span");
    periodInfo.className = "latest-context__period";
    periodInfo.textContent = comparisonMode === "quarter" ? `${rows.filter(row => row.comparison_group === "quarter").length} bank s reportem · ${rows.filter(row => row.comparison_group === "derived").length} výpočet z archivu · ${rows.filter(row => row.comparison_group === "missing").length} bez ověřeného CZ reportu` : `${shortPeriod(data.expected_period)} + starší / pohyblivé přehledy${older.length ? ` · ${older.length} starší report` : ""}`;
    context.append(periodInfo);
    document.querySelectorAll("#latestTable [data-sort]").forEach(button => button.closest("th").classList.toggle("sorted-metric", Boolean(sortMetric) && button.dataset.sort === latestSort.key));
    const groupRank = { quarter: 0, derived: 1, older: 2, rolling: 3, healthcheck: 4, missing: 5 };
    rows.sort((a, b) => {
        const aMissing = sortMetric && sortMetric.value(a) === null, bMissing = sortMetric && sortMetric.value(b) === null;
        if (aMissing !== bMissing) return Number(aMissing) - Number(bMissing);
        const groupDifference = groupRank[a.comparison_group] - groupRank[b.comparison_group];
        if (groupDifference) return groupDifference;
        if (!latestSort.key) return a.bank.localeCompare(b.bank, "cs");
        if (latestSort.key === "bank") return a.bank.localeCompare(b.bank, "cs") * (latestSort.direction === "asc" ? 1 : -1);
        const aValue = metrics[latestSort.key].value(a);
        const bValue = metrics[latestSort.key].value(b);
        if (aValue === null && bValue === null) return a.bank.localeCompare(b.bank, "cs");
        if (aValue === null) return 1;
        if (bValue === null) return -1;
        const difference = latestSort.direction === "asc" ? aValue - bValue : bValue - aValue;
        return difference || a.bank.localeCompare(b.bank, "cs");
      });
    exportedLatest = rows;
    if (!rows.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 10;
      cell.className = "empty-state";
      cell.textContent = "Výběru neodpovídá žádná banka. Změňte hledání nebo stav.";
      row.append(cell);
      tbody.append(row);
    }
    let missingSeparator = false;
    let previousGroup = null;
    rows.forEach(item => {
      const missing = sortMetric && sortMetric.value(item) === null;
      if (missing && !missingSeparator) {
        const divider = document.createElement("tr");
        divider.className = "latest-divider";
        const cell = document.createElement("td");
        cell.colSpan = 10;
        const label = document.createElement("span");
        label.textContent = `Bez údaje pro metriku: ${sortMetric.label} · ${rows.length - withValue.length} bank`;
        cell.append(label);
        divider.append(cell);
        tbody.append(divider);
        missingSeparator = true;
      }
      if (!missing && previousGroup !== item.comparison_group && (comparisonMode === "latest" || ["missing", "derived"].includes(item.comparison_group))) {
        const divider = document.createElement("tr"); divider.className = "latest-divider comparison-divider"; divider.dataset.group = item.comparison_group;
        const cell = document.createElement("td"); cell.colSpan = 10; const label = document.createElement("span");
        label.textContent = ({ quarter: `Čtvrtletní reporty · ${shortPeriod(data.expected_period)}`, derived: "Vypočtené souhrny z denního archivu · pokrytí uvedeno u období", older: "Starší čtvrtletní reporty · jiné období", rolling: "Pohyblivé denní přehledy · jiné období", healthcheck: "Doplňkový PSD2 health-check · metodika srovnání nedoložena", missing: `Bez ověřených českých metrik${comparisonMode === "quarter" ? ` pro ${shortPeriod(comparisonQuarter)}` : ""}` })[item.comparison_group];
        cell.append(label); divider.append(cell); tbody.append(divider);
      }
      previousGroup = item.comparison_group;
      const tr = document.createElement("tr");
      tr.dataset.bank = item.bank_id;
      if (missing) tr.classList.add("latest-row--missing-metric");
      const name = document.createElement("th");
      name.scope = "row";
      name.className = "latest-bank";
      const detail = document.createElement("a"); detail.href = ui.bankUrl(item.bank_id); detail.textContent = item.bank; detail.className = "bank-name-link"; name.append(detail);
      const state = document.createElement("td");
      const badge = document.createElement("span");
      badge.className = `status status--${item.status}`;
      badge.textContent = statusLabel(item.status);
      badge.title = "Stav zveřejněných dat, nikoli aktuální provoz bankovního API.";
      if (item.status === "unverified") badge.title = ui.methodNote(item);
      state.append(badge);
      if (item.comparison_group === "healthcheck") state.title = ui.methodNote(item);
      const availability = document.createElement("td");
      availability.className = "latest-availability";
      if (latestSort.key === "availability") availability.classList.add("sorted-metric");
      availability.dataset.value = availabilityValue(item) === null ? "" : String(availabilityValue(item));
      if (numberOrNull(item.availability_pct) === null && availabilityValue(item) !== null) {
        [["AISP", item.aisp_availability_pct], ["PISP", item.pisp_availability_pct]].forEach(([service, raw]) => {
          const line = document.createElement("span");
          line.className = "availability-service";
          const tag = document.createElement("small");
          tag.textContent = service;
          const value = numberOrNull(raw);
          line.append(tag, document.createTextNode(value === null ? "—" : `${formatNumber(value, 3)} %`));
          availability.append(line);
        });
      } else availability.textContent = displayAvailability(item);
      const periodCell = latestPeriodCell(item.latest_period);
      if (item.report_kind === "archive-derived") { const note=document.createElement("small"); note.className="derived-note"; note.textContent=`Výpočet · ${item.archived_days}/${item.calendar_days} dní`; periodCell.append(note); tr.title=ui.methodNote(item); }
      if (item.fallback_period) { const fallback = document.createElement("a"); fallback.href = ui.bankUrl(item.bank_id); fallback.className = "period-note"; fallback.textContent = /^rolling-/.test(item.fallback_period) ? "Denní přehled →" : `Jiné: ${shortPeriod(item.fallback_period)} →`; periodCell.append(fallback); }
      tr.append(name, state, periodCell, availability);
      ["aispResponse", "pispResponse", "aispError", "pispError", "sharedError"].forEach((key, index) => {
        const cell = document.createElement("td");
        cell.className = `numeric-metric${index === 0 || index === 2 ? " numeric-metric--group-start" : ""}${key === "sharedError" ? " numeric-metric--shared" : ""}`;
        const value = metrics[key].value(item);
        const digits = key.endsWith("Response") ? 1 : value > 0 && value < .01 ? 4 : 3;
        cell.textContent = value === null ? "—" : formatNumber(value, digits);
        cell.dataset.value = value === null ? "" : String(value);
        cell.title = `${metrics[key].label}: ${value === null ? "údaj není doložený" : metrics[key].format(value)}`;
        if (value === null) cell.classList.add("numeric-metric--empty");
        if (sortMetric && latestSort.key === key) {
          cell.classList.add("sorted-metric");
          if (value === null) cell.textContent = "Bez údaje";
        }
        tr.append(cell);
      });
      const sourceCell = document.createElement("td");
      sourceCell.className = "latest-source";
      const link = document.createElement("a");
      link.href = comparisonMode === "quarter" && item.comparison_group === "missing" ? ui.bankUrl(item.bank_id) : sourceUrl(item);
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.className = "source-link";
      link.textContent = comparisonMode === "quarter" && item.comparison_group === "missing" ? "Detail →" : item.bank_id === "unicredit" ? "CZ detail ↗" : item.report_url && item.report_url !== item.source_url ? "Report ↗" : "Stránka ↗";
      sourceCell.append(link);
      tr.append(sourceCell);
      tbody.append(tr);
    });
  }

  document.getElementById("metricTabs").addEventListener("click", event => {
    const button = event.target.closest("button[data-metric]");
    if (!button || button.dataset.metric === activeMetric) return;
    activeMetric = button.dataset.metric;
    document.querySelectorAll("#metricTabs button[data-metric]").forEach(item => {
      const isActive = item === button;
      item.classList.toggle("active", isActive);
      item.setAttribute("aria-pressed", String(isActive));
    });
    renderLegend();
    renderGrid();
    syncUrl();
  });

  document.querySelectorAll("button[data-sort]").forEach(button => {
    button.addEventListener("click", () => {
      const key = button.dataset.sort;
      latestSort = latestSort.key === key
        ? { key, direction: latestSort.direction === "asc" ? "desc" : "asc" }
        : { key, direction: key === "availability" ? "desc" : "asc" };
      document.querySelectorAll("button[data-sort]").forEach(item => {
        const isActive = item.dataset.sort === latestSort.key;
        item.classList.toggle("active", isActive);
        item.querySelector(".sort-arrow").textContent = isActive
          ? (latestSort.direction === "asc" ? "↑" : "↓")
          : "↕";
        item.closest("th").setAttribute("aria-sort", isActive
          ? (latestSort.direction === "asc" ? "ascending" : "descending")
          : "none");
      });
      renderLatest();
      syncUrl();
    });
  });

  document.getElementById("bankSearch").value = params.get("search") || "";
  document.getElementById("statusFilter").value = [...document.getElementById("statusFilter").options].some(option => option.value === params.get("status")) ? params.get("status") : "";
  document.getElementById("bankSearch").addEventListener("input", () => { renderLatest(); syncUrl(); });
  document.getElementById("statusFilter").addEventListener("change", () => { renderLatest(); syncUrl(); });
  const quarterSelect = document.getElementById("comparisonQuarter");
  for (const quarter of [...new Set([...allPeriods, data.expected_period])].sort().reverse()) quarterSelect.add(new Option(shortPeriod(quarter), quarter));
  quarterSelect.value = comparisonQuarter;
  function updateComparison() {
    document.querySelectorAll("[data-comparison-mode]").forEach(button => { const active = button.dataset.comparisonMode === comparisonMode; button.classList.toggle("active", active); button.setAttribute("aria-pressed", String(active)); });
    document.getElementById("comparisonQuarterLabel").hidden = comparisonMode !== "quarter";
    document.getElementById("comparisonExplanation").textContent = comparisonMode === "quarter" ? "Shodné období pro všechny banky. Nejnovější jiné reporty a denní přehledy najdete v detailu nebo v režimu Nejnovější údaje. I pro stejné období mohou banky používat rozdílné metodiky." : "Čtvrtletní reporty, starší období a pohyblivá denní měření jsou oddělené. Řazení probíhá uvnitř skupin, ne jako společný žebříček různých metodik.";
    renderLatest();
  }
  document.querySelectorAll("[data-comparison-mode]").forEach(button => button.addEventListener("click", () => { comparisonMode = button.dataset.comparisonMode; updateComparison(); syncUrl(); }));
  quarterSelect.addEventListener("change", () => { comparisonQuarter = quarterSelect.value; updateComparison(); syncUrl(); });
  document.getElementById("shareView").addEventListener("click", event => { syncUrl(); ui.share(event.currentTarget); });
  document.getElementById("exportHistory").addEventListener("click", () => {
    const metric = metrics[activeMetric];
    const rows = visibleHistory.filter(row => selectedBanks.has(row.bank));
    ui.download(`psd2-historie-${activeMetric}.csv`, ["banka", "období", "metrika", "hodnota", "jednotka", "metodika", "archivované_dny", "kalendářní_dny", "zdroj"], rows.map(row => { const coverage = data.report_coverage?.[`${row.bank_id}:${row.period}`]; return [row.bank, row.period, metric.label, metric.value(row), metric.unit, row.metric_method, coverage?.archived_days, coverage?.calendar_days, row.report_url]; }));
  });
  document.getElementById("exportLatest").addEventListener("click", () => ui.download(`psd2-${comparisonMode}.csv`, ["banka", "režim", "srovnávané_čtvrtletí", "období_dat", "typ_měření", "stav", ...Object.values(metrics).map(metric => `${metric.label} (${metric.unit})`), "metodika", "zdroj"], exportedLatest.map(row => [row.bank, comparisonMode, comparisonMode === "quarter" ? comparisonQuarter : "", row.latest_period, row.comparison_group, statusLabel(row.status), ...Object.values(metrics).map(metric => metric.value(row)), row.metric_method, row.report_url || row.source_url])));
  const latestPanel = document.getElementById("latestTitle").closest("section");
  latestPanel.parentElement.insertBefore(latestPanel, document.getElementById("trendTitle").closest("section"));

  updateSummary();
  renderCoverage();
  updateComparison();
  resetBankSelection();
  if (params.has("banks")) selectedBanks = new Set(latest.filter(row => params.get("banks").split(",").includes(row.bank_id)).map(row => row.bank));
  document.querySelectorAll("#metricTabs [data-metric]").forEach(button => { const active = button.dataset.metric === activeMetric; button.classList.toggle("active", active); button.setAttribute("aria-pressed", String(active)); });
  document.querySelectorAll("#latestTable [data-sort]").forEach(button => { const active = button.dataset.sort === latestSort.key; button.classList.toggle("active", active); button.querySelector(".sort-arrow").textContent = active ? latestSort.direction === "asc" ? "↑" : "↓" : "↕"; button.closest("th").setAttribute("aria-sort", active ? latestSort.direction === "asc" ? "ascending" : "descending" : "none"); });
  initializePeriodControls();
  ui.initializeNavigation();
})();
