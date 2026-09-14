(() => {
  "use strict";

  const data = window.PSD2_DATA || { latest: [], timeseries: [], expected_period: "" };
  const latest = data.latest.filter(item => item.scope === "main");
  const history = data.timeseries.filter(item => item.scope === "main");
  const periods = [...new Set(history.map(item => item.period))].sort();
  const palette = ["#0f766e", "#c66b1a", "#3e6d8e", "#8a5d9e", "#b2433f", "#5f7a45", "#7c6352", "#376f69"];

  const metrics = {
    availability: {
      label: "Dostupnost API",
      unit: "%",
      value: availabilityValue,
      format: value => `${formatNumber(value, 3)} %`,
      note: "Vyšší hodnota je lepší. Osa je přiblížená, aby byly rozdíly mezi čtvrtletími čitelné."
    },
    aispResponse: {
      label: "Odezva AISP",
      unit: "ms",
      value: item => numberOrNull(item.aisp_response_ms),
      format: value => `${formatNumber(value, 1)} ms`,
      note: "Nižší hodnota je lepší. Svislá osa je logaritmicky zhuštěná, aby byly vidět běžné hodnoty i extrémy."
    },
    pispResponse: {
      label: "Odezva PISP",
      unit: "ms",
      value: item => numberOrNull(item.pisp_response_ms),
      format: value => `${formatNumber(value, 1)} ms`,
      note: "Nižší hodnota je lepší. Svislá osa je logaritmicky zhuštěná; 0 ms se do průměru nezapočítává."
    },
    aispError: {
      label: "Chybovost AISP",
      unit: "%",
      value: item => item.metric_method?.includes("spolecna error response rate") ? null : numberOrNull(item.aisp_error_pct),
      format: value => `${formatNumber(value, 3)} %`,
      note: "Nižší hodnota je lepší. Svislá osa je logaritmicky zhuštěná, aby jediný extrém neschoval ostatní banky."
    }
  };

  let activeMetric = "availability";
  let selectedBanks = new Set();

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
    const counts = new Map();
    history.forEach(item => {
      if (metric.value(item) !== null) counts.set(item.bank, (counts.get(item.bank) || 0) + 1);
    });
    return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "cs"));
  }

  function resetBankSelection() {
    selectedBanks = new Set(bankCoverage(activeMetric).filter(([, count]) => count >= 3).slice(0, 6).map(([bank]) => bank));
    if (!selectedBanks.size) selectedBanks = new Set(bankCoverage(activeMetric).slice(0, 6).map(([bank]) => bank));
  }

  function renderLegend() {
    const container = document.getElementById("chartLegend");
    container.replaceChildren();
    bankCoverage(activeMetric).forEach(([bank], index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "legend-button";
      button.setAttribute("aria-pressed", selectedBanks.has(bank) ? "true" : "false");
      button.style.setProperty("--series", palette[index % palette.length]);
      const swatch = document.createElement("span");
      swatch.className = "legend-swatch";
      const label = document.createElement("span");
      label.textContent = bank;
      button.append(swatch, label);
      button.addEventListener("click", () => {
        if (selectedBanks.has(bank)) selectedBanks.delete(bank); else selectedBanks.add(bank);
        renderLegend();
        drawChart();
      });
      container.append(button);
    });
  }

  function svgElement(name, attrs = {}) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
    return element;
  }

  function drawChart() {
    const svg = document.getElementById("trendChart");
    const shell = svg.parentElement;
    const empty = document.getElementById("chartEmpty");
    const tooltip = document.getElementById("chartTooltip");
    svg.replaceChildren();
    tooltip.hidden = true;

    const metric = metrics[activeMetric];
    const rows = history.filter(item => selectedBanks.has(item.bank) && metric.value(item) !== null);
    document.getElementById("chartNote").textContent = metric.note;
    if (!rows.length) {
      svg.hidden = true;
      empty.hidden = false;
      return;
    }
    svg.hidden = false;
    empty.hidden = true;

    const width = Math.max(320, shell.clientWidth);
    const height = width < 560 ? 330 : 390;
    const margin = { top: 22, right: 22, bottom: 48, left: width < 560 ? 58 : 76 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

    const values = rows.map(metric.value);
    let min = Math.min(...values);
    let max = Math.max(...values);
    let transform = value => value;
    let ticks = [];
    if (activeMetric === "availability") {
      min = Math.max(0, Math.floor((min - 0.35) * 10) / 10);
      max = Math.min(100.05, Math.max(100, max + 0.05));
      ticks = Array.from({ length: 5 }, (_, index) => min + ((100 - min) * index) / 4);
    } else {
      min = 0;
      const step = activeMetric === "aispError" ? 0.01 : 10;
      transform = value => Math.log10(1 + Math.max(0, value) / step);
      ticks = (activeMetric === "aispError"
        ? [0, 0.01, 0.1, 1, 5, 10, 50, 100]
        : [0, 10, 100, 1000, 10000, 100000]).filter(value => value <= max);
      if (ticks.length < 2) ticks = [0, max || 1];
      max = max === 0 ? 1 : max * 1.1;
    }
    const x = period => margin.left + (periods.indexOf(period) / Math.max(1, periods.length - 1)) * innerWidth;
    const y = value => margin.top + (1 - (transform(value) - transform(min)) / (transform(max) - transform(min) || 1)) * innerHeight;

    ticks.forEach(value => {
      const yy = y(value);
      svg.append(svgElement("line", { x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, class: "chart-grid" }));
      const label = svgElement("text", { x: margin.left - 10, y: yy + 4, "text-anchor": "end", class: "chart-axis" });
      label.textContent = `${formatNumber(value, activeMetric === "availability" ? 1 : value < 1 ? 2 : 0)} ${metric.unit}`;
      svg.append(label);
    });

    periods.forEach((period, index) => {
      if (width < 560 && index % 2 === 1 && index !== periods.length - 1) return;
      const label = svgElement("text", { x: x(period), y: height - 16, "text-anchor": "middle", class: "chart-axis" });
      label.textContent = period.replace("-", " ");
      svg.append(label);
    });

    const coverage = bankCoverage(activeMetric).map(([bank]) => bank);
    selectedBanks.forEach(bank => {
      const bankRows = rows.filter(item => item.bank === bank).sort((a, b) => a.period.localeCompare(b.period));
      const colorIndex = coverage.indexOf(bank);
      const group = svgElement("g", { style: `--series:${palette[(colorIndex < 0 ? 0 : colorIndex) % palette.length]}` });
      let path = "";
      let previousPeriodIndex = -1;
      bankRows.forEach(item => {
        const px = x(item.period);
        const py = y(metric.value(item));
        const currentPeriodIndex = periods.indexOf(item.period);
        path += `${currentPeriodIndex === previousPeriodIndex + 1 ? " L" : " M"}${px.toFixed(2)},${py.toFixed(2)}`;
        previousPeriodIndex = currentPeriodIndex;
      });
      if (bankRows.length > 1) group.append(svgElement("path", { d: path, class: "chart-line" }));
      bankRows.forEach(item => {
        const point = svgElement("circle", { cx: x(item.period), cy: y(metric.value(item)), r: 4.5, class: "chart-point", tabindex: "0" });
        const show = event => {
          const separate = activeMetric === "availability"
            && numberOrNull(item.availability_pct) === null
            && numberOrNull(item.aisp_availability_pct) !== null
            && numberOrNull(item.pisp_availability_pct) !== null;
          tooltip.innerHTML = `<strong>${bank}</strong>${formatPeriod(item.period)}<br>${metric.label}: ${metric.format(metric.value(item))}${separate ? "<br>Průměr AISP a PISP" : ""}`;
          tooltip.hidden = false;
          const box = shell.getBoundingClientRect();
          const target = event.currentTarget.getBoundingClientRect();
          tooltip.style.left = `${Math.min(box.width - 230, Math.max(6, target.left - box.left + 10))}px`;
          tooltip.style.top = `${Math.max(5, target.top - box.top - 64)}px`;
        };
        point.addEventListener("mouseenter", show);
        point.addEventListener("focus", show);
        point.addEventListener("mouseleave", () => { tooltip.hidden = true; });
        point.addEventListener("blur", () => { tooltip.hidden = true; });
        group.append(point);
      });
      svg.append(group);
    });
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
    latest.forEach(bank => {
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
        cell.className = `coverage-cell ${hasAvailability ? "coverage-cell--full" : hasPerformance ? "coverage-cell--partial" : ""}`;
        cell.setAttribute("aria-label", `${bank.bank}, ${period}: ${hasAvailability ? "dostupnost" : hasPerformance ? "jen výkonnost" : "bez dat"}${item?.report_url ? "; otevřít report" : ""}`);
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
    latest.forEach(item => {
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

  document.getElementById("metricSelect").addEventListener("change", event => {
    activeMetric = event.target.value;
    resetBankSelection();
    renderLegend();
    drawChart();
  });

  updateSummary();
  renderCoverage();
  renderLatest();
  resetBankSelection();
  renderLegend();
  drawChart();
  new ResizeObserver(drawChart).observe(document.querySelector(".chart-shell"));
})();
