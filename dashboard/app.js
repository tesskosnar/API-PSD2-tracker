(() => {
  "use strict";

  const data = window.PSD2_DATA || { latest: [], timeseries: [], expected_period: "" };
  const latest = data.latest.filter(item => item.scope === "main");
  const history = data.timeseries.filter(item => item.scope === "main");
  const allPeriods = [...new Set(history.map(item => item.period))].sort();
  let periods = allPeriods.slice(-8);
  let visibleHistory = history.filter(item => periods.includes(item.period));
  const metrics = {
    availability: {
      label: "Dostupnost API",
      unit: "%",
      value: availabilityValue,
      format: value => `${formatNumber(value, 3)} %`,
      note: "Vyšší hodnota je lepší. Každá banka má vlastní řádek; prázdné políčko znamená, že údaj chybí."
    },
    aispResponse: {
      label: "Odezva AISP",
      unit: "ms",
      value: item => numberOrNull(item.aisp_response_ms),
      format: value => `${formatNumber(value, 1)} ms`,
      note: "Nižší hodnota je lepší. Čísla jsou průměrná doba odezvy v milisekundách."
    },
    pispResponse: {
      label: "Odezva PISP",
      unit: "ms",
      value: item => numberOrNull(item.pisp_response_ms),
      format: value => `${formatNumber(value, 1)} ms`,
      note: "Nižší hodnota je lepší. Dny bez PISP volání se do průměru odezvy nezapočítávají."
    },
    aispError: {
      label: "Chybovost AISP",
      unit: "%",
      value: item => item.metric_method?.includes("spolecna error response rate") ? null : numberOrNull(item.aisp_error_pct),
      format: value => `${formatNumber(value, value > 0 && value < 0.01 ? 4 : 3)} %`,
      note: "Nižší hodnota je lepší. Společná chybovost služeb má vlastní metriku a sem se nemíchá."
    },
    pispError: {
      label: "Chybovost PISP",
      unit: "%",
      value: item => item.metric_method?.includes("spolecna error response rate") ? null : numberOrNull(item.pisp_error_pct),
      format: value => `${formatNumber(value, value > 0 && value < 0.01 ? 4 : 3)} %`,
      note: "Nižší hodnota je lepší. Společná chybovost služeb má vlastní metriku a sem se nemíchá."
    },
    sharedError: {
      label: "Společná chybovost",
      unit: "%",
      value: item => item.metric_method?.includes("spolecna error response rate") ? numberOrNull(item.aisp_error_pct) : null,
      format: value => `${formatNumber(value, value > 0 && value < 0.01 ? 4 : 3)} %`,
      note: "Chybovost zveřejněná společně pro PSD2 služby. Nelze ji vydávat za samostatnou míru AISP nebo PISP."
    }
  };

  let activeMetric = "availability";
  let selectedBanks = new Set();
  let latestSort = { key: null, direction: "asc" };

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
    return ({ ok: "Aktuální", partial: "Částečná data", outdated: "Zastaralé", missing: "Bez reportu", blocked: "Zdroj blokován" })[status] || status;
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
    document.getElementById("currentCoverage").textContent = formatNumber(current, 0);
    document.getElementById("historyPoints").textContent = formatNumber(history.length, 0);
    document.getElementById("bankCount").textContent = formatNumber(latest.length, 0);
    document.getElementById("periodLabel").textContent = `Poslední uzavřené období: ${formatPeriod(data.expected_period)}`;
    const checked = data.checked_on ? new Date(`${data.checked_on}T12:00:00`) : null;
    document.getElementById("checkedLabel").textContent = checked
      ? `Data zkontrolována: ${new Intl.DateTimeFormat("cs-CZ", { day: "numeric", month: "long", year: "numeric" }).format(checked)}`
      : "Datum poslední kontroly není dostupné";
  }

  function bankCoverage(metricKey) {
    const metric = metrics[metricKey];
    const counts = new Map(latest.map(item => [item.bank, 0]));
    visibleHistory.forEach(item => {
      if (metric.value(item) !== null) counts.set(item.bank, (counts.get(item.bank) || 0) + 1);
    });
    const withReport = new Set(visibleHistory.filter(item => item.report_url).map(item => item.bank));
    return [...counts.entries()].sort((a, b) =>
      Number(withReport.has(b[0])) - Number(withReport.has(a[0])) || a[0].localeCompare(b[0], "cs"));
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
        : `${bank}: pro tuto metriku zatím není doložená historie`;
      const swatch = document.createElement("span");
      swatch.className = "legend-swatch";
      const label = document.createElement("span");
      label.textContent = bank;
      button.append(swatch, label);
      button.addEventListener("click", () => {
        if (selectedBanks.has(bank)) selectedBanks.delete(bank); else selectedBanks.add(bank);
        renderLegend();
        renderGrid();
      });
      container.append(button);
    });
  }

  function renderGrid() {
    const table = document.getElementById("metricGrid");
    const empty = document.getElementById("chartEmpty");
    const metric = metrics[activeMetric];
    document.getElementById("chartNote").textContent = metric.note;

    const banks = bankCoverage(activeMetric).map(([bank]) => bank).filter(bank => selectedBanks.has(bank));
    if (!banks.length) {
      table.hidden = true;
      empty.hidden = false;
      return;
    }
    table.hidden = false;
    empty.hidden = true;

    const distinctValues = [...new Set(visibleHistory.map(metric.value).filter(value => value !== null))].sort((a, b) => a - b);
    const shade = value => distinctValues.length < 2
      ? 3
      : 1 + Math.round(distinctValues.indexOf(value) / (distinctValues.length - 1) * 4);

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
    banks.forEach(bank => {
      const row = document.createElement("tr");
      const name = document.createElement("th");
      name.scope = "row";
      name.className = "metric-grid__bank";
      name.textContent = bank;
      const reports = visibleHistory.filter(item => item.bank === bank && item.report_url);
      if (!reports.some(item => metric.value(item) !== null)) {
        const status = document.createElement("small");
        status.className = "metric-grid__status";
        status.textContent = reports.length ? "Metrika není doložená" : "Bez reportu v období";
        name.append(status);
        if (!reports.length) row.className = "metric-grid__row--no-report";
      }
      row.append(name);
      periods.forEach(period => {
        const item = visibleHistory.find(point => point.bank === bank && point.period === period);
        const value = item ? metric.value(item) : null;
        const cell = document.createElement("td");
        cell.className = value === null ? "metric-grid__cell metric-grid__cell--empty" : `metric-grid__cell metric-grid__cell--${shade(value)}`;
        const content = document.createElement(value !== null && item.report_url ? "a" : "span");
        content.className = "metric-grid__value";
        content.textContent = value === null ? "—" : metric.format(value);
        content.title = `${bank} · ${formatPeriod(period)} · ${metric.label}: ${content.textContent}`;
        if (item?.metric_method) content.title += ` · ${item.metric_method}`;
        if (content.tagName === "A") {
          content.href = sourceUrl(item);
          content.target = "_blank";
          content.rel = "noopener noreferrer";
          content.title += " · otevřít report";
        }
        cell.append(content);
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
      name.textContent = bank.bank;
      tr.append(name);
      allPeriods.forEach(period => {
        const td = document.createElement("td");
        const item = history.find(row => row.bank_id === bank.bank_id && row.period === period);
        const cell = document.createElement(item?.report_url ? "a" : "span");
        const hasAvailability = item && availabilityValue(item) !== null;
        const hasPerformance = item && [item.aisp_response_ms, item.pisp_response_ms, item.aisp_error_pct, item.pisp_error_pct].some(value => numberOrNull(value) !== null);
        const hasReport = Boolean(item?.report_url);
        const coverageState = hasAvailability
          ? "dostupnost"
          : hasPerformance
            ? "jen výkonnost"
            : hasReport
              ? "report bez měřitelné hodnoty"
              : "bez reportu";
        cell.className = `coverage-cell ${hasAvailability ? "coverage-cell--full" : hasPerformance ? "coverage-cell--partial" : hasReport ? "coverage-cell--report" : ""}`;
        cell.setAttribute("aria-label", `${bank.bank}, ${period}: ${coverageState}${hasReport ? "; otevřít report" : ""}`);
        cell.title = cell.getAttribute("aria-label");
        if (item?.report_url) {
          cell.href = sourceUrl(item);
          cell.target = "_blank";
          cell.rel = "noopener noreferrer";
        }
        td.append(cell);
        tr.append(td);
      });
      tbody.append(tr);
    });
    table.replaceChildren(thead, tbody);
  }

  function renderLatest() {
    const tbody = document.getElementById("latestRows");
    tbody.replaceChildren();
    const normalize = value => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("cs");
    const search = normalize(document.getElementById("bankSearch").value.trim());
    const status = document.getElementById("statusFilter").value;
    const rows = latest.filter(item => normalize(item.bank).includes(search) && (!status || item.status === status));
    document.getElementById("latestCount").textContent = `Zobrazeno ${rows.length} z ${latest.length} bank`;
    const sortMetric = latestSort.key && latestSort.key !== "bank" ? metrics[latestSort.key] : null;
    const withValue = sortMetric ? rows.filter(item => sortMetric.value(item) !== null) : rows;
    const older = withValue.filter(item => /^\d{4}-Q[1-4]$/.test(item.latest_period) && item.latest_period < data.expected_period);
    const context = document.getElementById("latestContext");
    context.replaceChildren();
    const sortInfo = document.createElement("strong");
    sortInfo.textContent = sortMetric ? `${sortMetric.label} · ${latestSort.direction === "asc" ? "Od nejnižší" : "Od nejvyšší"} hodnoty` : "Nejnovější dostupné údaje každé banky";
    context.append(sortInfo);
    if (sortMetric) {
      const counts = document.createElement("span");
      counts.textContent = `${withValue.length} s hodnotou · ${rows.length - withValue.length} bez údaje`;
      context.append(counts);
    }
    const periodInfo = document.createElement("span");
    periodInfo.className = "latest-context__period";
    periodInfo.textContent = `${shortPeriod(data.expected_period)} + denní přehledy${older.length ? ` · ${older.length} ${older.length === 1 ? "starší report zvýrazněn" : "starší reporty zvýrazněny"}` : ""}`;
    context.append(periodInfo);
    document.querySelectorAll("#latestTable [data-sort]").forEach(button => button.closest("th").classList.toggle("sorted-metric", Boolean(sortMetric) && button.dataset.sort === latestSort.key));
    if (latestSort.key) {
      rows.sort((a, b) => {
        if (latestSort.key === "bank") return a.bank.localeCompare(b.bank, "cs") * (latestSort.direction === "asc" ? 1 : -1);
        const aValue = metrics[latestSort.key].value(a);
        const bValue = metrics[latestSort.key].value(b);
        if (aValue === null && bValue === null) return a.bank.localeCompare(b.bank, "cs");
        if (aValue === null) return 1;
        if (bValue === null) return -1;
        const difference = latestSort.direction === "asc" ? aValue - bValue : bValue - aValue;
        return difference || a.bank.localeCompare(b.bank, "cs");
      });
    } else rows.sort((a, b) => a.bank.localeCompare(b.bank, "cs"));
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
      const tr = document.createElement("tr");
      tr.dataset.bank = item.bank_id;
      if (missing) tr.classList.add("latest-row--missing-metric");
      const name = document.createElement("th");
      name.scope = "row";
      name.className = "latest-bank";
      name.textContent = item.bank;
      const state = document.createElement("td");
      const badge = document.createElement("span");
      badge.className = `status status--${item.status}`;
      badge.textContent = statusLabel(item.status);
      state.append(badge);
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
      tr.append(name, state, latestPeriodCell(item.latest_period), availability);
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
      link.href = sourceUrl(item);
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.className = "source-link";
      link.textContent = item.bank_id === "unicredit" ? "CZ detail ↗" : item.report_url && item.report_url !== item.source_url ? "Report ↗" : "Stránka ↗";
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
    });
  });

  document.getElementById("bankSearch").addEventListener("input", renderLatest);
  document.getElementById("statusFilter").addEventListener("change", renderLatest);

  updateSummary();
  renderCoverage();
  renderLatest();
  resetBankSelection();
  initializePeriodControls();
})();
