(() => {
  "use strict";

  const data = window.PSD2_DATA || { latest: [], timeseries: [], expected_period: "" };
  const latest = data.latest.filter(item => item.scope === "main");
  const history = data.timeseries.filter(item => item.scope === "main");
  const periods = [...new Set(history.map(item => item.period))].sort();
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
      note: "Nižší hodnota je lepší. Barva řadí hodnoty; přesné procento je vždy uvedené v políčku. Společná chybovost J&T se sem nemíchá."
    },
    pispError: {
      label: "Chybovost PISP",
      unit: "%",
      value: item => item.metric_method?.includes("spolecna error response rate") ? null : numberOrNull(item.pisp_error_pct),
      format: value => `${formatNumber(value, value > 0 && value < 0.01 ? 4 : 3)} %`,
      note: "Nižší hodnota je lepší. Barva řadí hodnoty; přesné procento je vždy uvedené v políčku. Společná chybovost J&T se sem nemíchá."
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
    const rolling = /^rolling-90d-to-(\d{4})-(\d{2})-(\d{2})$/.exec(period || "");
    if (rolling) return `90 dní do ${Number(rolling[3])}. ${Number(rolling[2])}. ${rolling[1]}`;
    return period || "—";
  }

  function statusLabel(status) {
    return ({ ok: "Aktuální", partial: "Částečná data", outdated: "Zastaralé", missing: "Bez reportu", blocked: "Zdroj blokován" })[status] || status;
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
    history.forEach(item => {
      if (metric.value(item) !== null) counts.set(item.bank, (counts.get(item.bank) || 0) + 1);
    });
    return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0], "cs"));
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

    const distinctValues = [...new Set(history.map(metric.value).filter(value => value !== null))].sort((a, b) => a - b);
    const shade = value => distinctValues.length < 2
      ? 3
      : 1 + Math.round(distinctValues.indexOf(value) / (distinctValues.length - 1) * 4);

    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    ["Banka", ...periods.map(period => period.replace("-", " "))].forEach((label, index) => {
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
      row.append(name);
      periods.forEach(period => {
        const item = history.find(point => point.bank === bank && point.period === period);
        const value = item ? metric.value(item) : null;
        const cell = document.createElement("td");
        cell.className = value === null ? "metric-grid__cell metric-grid__cell--empty" : `metric-grid__cell metric-grid__cell--${shade(value)}`;
        const content = document.createElement(value !== null && item.report_url ? "a" : "span");
        content.className = "metric-grid__value";
        content.textContent = value === null ? "—" : metric.format(value);
        content.title = `${bank} · ${formatPeriod(period)} · ${metric.label}: ${content.textContent}`;
        if (content.tagName === "A") {
          content.href = item.report_url;
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
    ["Banka", ...periods].forEach(label => {
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
      periods.forEach(period => {
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
          cell.href = item.report_url;
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
    const pairedCell = (aisp, pisp, unit, shared = false) => {
      const cell = document.createElement("td");
      cell.className = "paired-metric";
      if (shared && aisp !== null) {
        const line = document.createElement("span");
        line.textContent = `Společná: ${formatNumber(aisp, unit === "%" ? 3 : 1)} ${unit}`;
        cell.append(line);
        return cell;
      }
      [["AISP", aisp], ["PISP", pisp]].forEach(([label, value]) => {
        const line = document.createElement("span");
        const tag = document.createElement("small");
        tag.textContent = label;
        line.append(tag, document.createTextNode(value === null ? "—" : `${formatNumber(value, unit === "%" ? 3 : 1)} ${unit}`));
        cell.append(line);
      });
      return cell;
    };
    const sortValue = (item, key) => {
      const fields = key === "response"
        ? [item.aisp_response_ms, item.pisp_response_ms]
        : [item.aisp_error_pct, item.pisp_error_pct];
      const values = fields.map(numberOrNull).filter(value => value !== null);
      return values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null;
    };
    const rows = [...latest];
    if (latestSort.key) {
      rows.sort((a, b) => {
        const aValue = sortValue(a, latestSort.key);
        const bValue = sortValue(b, latestSort.key);
        if (aValue === null && bValue === null) return a.bank.localeCompare(b.bank, "cs");
        if (aValue === null) return 1;
        if (bValue === null) return -1;
        const difference = latestSort.direction === "asc" ? aValue - bValue : bValue - aValue;
        return difference || a.bank.localeCompare(b.bank, "cs");
      });
    }
    rows.forEach(item => {
      const tr = document.createElement("tr");
      const source = item.report_url || item.source_url;
      const cells = [
        item.bank,
        statusLabel(item.status),
        formatPeriod(item.latest_period),
        displayAvailability(item)
      ];
      cells.forEach((value, index) => {
        const td = document.createElement("td");
        if (index === 1) {
          const span = document.createElement("span");
          span.className = `status status--${item.status}`;
          span.textContent = value;
          td.append(span);
        } else td.textContent = value;
        tr.append(td);
      });
      tr.append(pairedCell(numberOrNull(item.aisp_response_ms), numberOrNull(item.pisp_response_ms), "ms"));
      tr.append(pairedCell(numberOrNull(item.aisp_error_pct), numberOrNull(item.pisp_error_pct), "%", item.metric_method?.includes("spolecna error response rate")));
      const sourceCell = document.createElement("td");
      const link = document.createElement("a");
      link.href = source;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.className = "source-link";
      link.textContent = item.report_url && item.report_url !== item.source_url ? "Report ↗" : "Stránka ↗";
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
    resetBankSelection();
    renderLegend();
    renderGrid();
  });

  document.querySelectorAll("button[data-sort]").forEach(button => {
    button.addEventListener("click", () => {
      const key = button.dataset.sort;
      latestSort = latestSort.key === key
        ? { key, direction: latestSort.direction === "asc" ? "desc" : "asc" }
        : { key, direction: "asc" };
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

  updateSummary();
  renderCoverage();
  renderLatest();
  resetBankSelection();
  renderLegend();
  renderGrid();
})();
