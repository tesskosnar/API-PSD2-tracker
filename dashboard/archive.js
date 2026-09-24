(() => {
  "use strict";
  const data = window.PSD2_DATA || {};
  const ui = window.PSD2_UI;
  const params = new URLSearchParams(location.search);
  const history = window.PSD2_DAILY_DATA || data.daily_history || [];
  const bank = document.querySelector("#archiveBank");
  const from = document.querySelector("#archiveFrom");
  const to = document.querySelector("#archiveTo");
  const chart = document.querySelector("#dailyChart");
  const pointDetails = document.querySelector("#dailyPointDetails");
  let plottedPoints = [], plot = null, selection = null;
  let metric = "aisp_response_ms";
  let exportedRows = [];
  const labels = { availability_pct: "Dostupnost", aisp_availability_pct: "Dostupnost AISP", pisp_availability_pct: "Dostupnost PISP", aisp_response_ms: "Odezva AISP", pisp_response_ms: "Odezva PISP", aisp_error_pct: "Chybovost AISP", pisp_error_pct: "Chybovost PISP", shared_error_pct: "Společná chybovost" };
  const format = (value, digits = 2) => value === "" || value === null || value === undefined ? "—" : new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: digits }).format(Number(value));
  const day = value => new Date(`${value}T00:00:00Z`);
  const dateLabel = value => new Intl.DateTimeFormat("cs-CZ", { timeZone: "UTC" }).format(day(value));
  const unit = () => metric.endsWith("_ms") ? "ms" : "%";
  const number = ui.number;
  const bankNames = new Map(history.map(row => [row.bank_id, row.bank]));
  for (const [id, name] of [...bankNames].sort((a,b) => a[1].localeCompare(b[1], "cs"))) bank.add(new Option(name, id));
  if (bankNames.has("moneta")) bank.value = "moneta";
  if (bankNames.has(params.get("bank"))) bank.value = params.get("bank");
  if (document.body.classList.contains("bank-page")) {
    const selected = (data.latest || []).find(row => row.bank_id === params.get("bank") && row.scope === "main");
    if (selected && !bankNames.has(selected.bank_id)) { bank.add(new Option(selected.bank, selected.bank_id)); bankNames.set(selected.bank_id, selected.bank); }
    bank.value = selected?.bank_id || "";
  }
  if (Object.hasOwn(labels, params.get("dailyMetric"))) metric = params.get("dailyMetric");
  else if (document.body.classList.contains("bank-page") && ui.metrics[params.get("bankMetric")]) metric = ui.metrics[params.get("bankMetric")].field;
  document.querySelector("#archiveMeta").textContent = data.archive?.checked_on ? `Poslední sběr ${dateLabel(data.archive.checked_on)}` : "Archiv se naplní při nejbližším sběru";

  function setRange(full = false) {
    const dates = history.filter(row => row.bank_id === bank.value).map(row => row.date).sort();
    [from, to, document.querySelector("#archiveAll"), document.querySelector("#exportDaily")].filter(Boolean).forEach(control => { control.disabled = !dates.length; });
    if (!dates.length) { from.value = to.value = ""; return; }
    from.min = to.min = dates[0];
    from.max = to.max = dates.at(-1);
    to.value = dates.at(-1);
    const start = day(to.value);
    start.setUTCFullYear(start.getUTCFullYear() - 1);
    from.value = full ? dates[0] : [dates[0], start.toISOString().slice(0,10)].sort().at(-1);
  }
  function svg(tag, attrs, text) {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
    if (text !== undefined) el.textContent = text;
    chart.append(el);
    return el;
  }
  function showPoint(row) {
    chart.querySelector(".daily-selection")?.remove();
    pointDetails.hidden = !row;
    if (!row) { selection = null; return; }
    selection = { bank: bank.value, metric, date: row.date };
    const date = document.querySelector("#dailyPointDate");
    date.dateTime = row.date;
    date.textContent = new Intl.DateTimeFormat("cs-CZ", { timeZone: "UTC", weekday: "long", day: "numeric", month: "numeric", year: "numeric" }).format(day(row.date));
    document.querySelector("#dailyPointMetric").textContent = labels[metric];
    document.querySelector("#dailyPointValue").textContent = `${format(row[metric], 20)} ${unit()}`;
    const marker = svg("g", { class: "daily-selection", "pointer-events": "none", "aria-hidden": "true" });
    const line = svg("line", { x1: plot.x(row), x2: plot.x(row), y1: 35, y2: 285, stroke: "#0f766e", "stroke-width": 1.5, "stroke-dasharray": "4 4" });
    const dot = svg("circle", { cx: plot.x(row), cy: plot.y(row), r: 6, fill: "#0f766e", stroke: "#fff", "stroke-width": 2.5 });
    marker.append(line, dot);
  }
  function renderSummary(rows) {
    const summary = ui.dailySummary(rows, from.value, to.value);
    const context = document.querySelector("#dailySummaryCoverage");
    context.textContent = summary.calendarDays
      ? `${dateLabel(from.value)} – ${dateLabel(to.value)} · archivováno ${summary.archivedDays} z ${summary.calendarDays} dnů${summary.archivedDays < summary.calendarDays ? " · neúplné pokrytí období" : " · úplné denní pokrytí archivu"}`
      : "Vyberte platné datumové období.";
    context.classList.toggle("archive-summary__coverage--partial", summary.archivedDays < summary.calendarDays);
    const cards = document.querySelector("#dailySummaryCards");
    cards.replaceChildren();
    for (const definition of Object.values(ui.metrics)) {
      const item = summary.metrics[definition.key];
      const card = document.createElement("article");
      card.className = `bank-metric-card${item.value === null ? " bank-metric-card--empty" : ""}${ui.benchmarkAlert(definition.key, item.value) ? " bank-metric-card--alert" : ""}`;
      card.dataset.summaryMetric = definition.key;
      const label = document.createElement("span"); label.textContent = definition.label;
      const value = document.createElement("strong"); value.textContent = item.value === null ? item.zeroDays ? "Jen 0 ms" : "Údaj nedoložen" : definition.format(item.value);
      const coverage = document.createElement("small");
      coverage.textContent = `${item.count} z ${summary.calendarDays} dnů ve výpočtu${item.zeroDays ? ` · ${item.zeroDays} dnů s 0 ms vynecháno` : ""}`;
      card.append(label, value, coverage);
      if (ui.benchmarkAlert(definition.key, item.value)) { const alert=document.createElement("small"); alert.className="benchmark-alert-note"; alert.textContent=ui.benchmarkLabel(definition.key); card.append(alert); }
      if (item.derivedDays) { const note=document.createElement("small"); note.textContent=`${item.derivedDays} dnů: odvozený průměr AISP/PISP`; card.append(note); }
      cards.append(card);
    }
    document.querySelector("#dailySummaryMethod").textContent = "Výpočet trackeru, nikoli nový report banky: nevážené průměry publikovaných denních hodnot. Chybějící dny se nedoplňují. Odezva vynechává 0 ms; skutečné nuly u dostupnosti a chybovosti se započítávají. Bez počtů volání není průměr denní chybovosti podílem všech chybných volání.";
    if (bank.value === "mbank" && history.some(row=>row.bank_id === "mbank" && row.country_code === "unverified")) document.querySelector("#dailySummaryMethod").textContent += " Souhrnný report mBank – samostatný český rozsah nepotvrzen.";
    if (bank.value === "partners") document.querySelector("#dailySummaryMethod").textContent += " Partners: doplňkový health-check, nikoli srovnatelný čtvrtletní RTS report.";
  }
  function render() {
    const available = key => history.some(row => row.bank_id === bank.value && number(row[key]) !== null);
    if (!available(metric)) metric = Object.keys(labels).find(available) || "availability_pct";
    document.querySelectorAll("[data-daily-metric]").forEach(button => {
      button.disabled = !available(button.dataset.dailyMetric);
      button.classList.toggle("active", button.dataset.dailyMetric === metric);
      button.setAttribute("aria-pressed", String(button.dataset.dailyMetric === metric));
      button.title = button.disabled ? "V uloženém denním archivu není tato metrika doložená" : labels[button.dataset.dailyMetric];
    });
    const rows = history.filter(row => row.bank_id === bank.value && row.date >= from.value && row.date <= to.value).sort((a,b) => a.date.localeCompare(b.date));
    renderSummary(rows);
    exportedRows = rows;
    const points = rows.filter(row => Number.isFinite(number(row[metric])));
    plottedPoints = points;
    plot = null;
    chart.replaceChildren();
    chart.toggleAttribute("hidden", !points.length);
    document.querySelector("#dailyEmpty").hidden = Boolean(points.length);
    document.querySelector("#dailyChartHint").hidden = !points.length;
    document.querySelector("#dailyRange").textContent = rows.length ? `${dateLabel(from.value)} – ${dateLabel(to.value)} · ${rows.length} uložených dnů · ${labels[metric]} (${unit()})` : "Žádné uložené dny ve výběru";
    if (rows.some(row=>row.bank_id==="mbank" && row.country_code==="unverified")) document.querySelector("#dailyRange").textContent += " · Souhrnný report mBank – samostatný český rozsah nepotvrzen";
    if (points.length) {
      const width = Math.max(300, Math.min(1080, chart.parentElement.clientWidth));
      chart.setAttribute("viewBox", `0 0 ${width} 340`);
      const right = width - 30;
      const min = Math.min(...points.map(row => number(row[metric])));
      const max = Math.max(...points.map(row => number(row[metric])));
      const padding = (max - min) * .1 || Math.max(max * .05, 1);
      const low = Math.max(0, min - padding), high = metric.includes("availability") ? Math.min(100, max + padding) : max + padding;
      const start = day(from.value).getTime(), end = day(to.value).getTime();
      const x = row => start === end ? (80 + right) / 2 : 80 + (day(row.date).getTime() - start) / (end - start) * (right - 80);
      const y = row => 285 - (number(row[metric]) - low) / (high - low || 1) * 250;
      plot = { x, y, start, end, right };
      chart.setAttribute("aria-label", `${bankNames.get(bank.value)} · ${labels[metric]} · interaktivní denní graf`);
      svg("title", {}, `${bankNames.get(bank.value)} · ${labels[metric]}`);
      for (let index = 0; index <= 4; index++) {
        const position = 35 + index * 62.5;
        svg("line", { x1: 80, x2: right, y1: position, y2: position, stroke: "#dce2df" });
        const digits = metric.endsWith("_ms") ? 0 : high < .001 ? 6 : high < .01 ? 4 : 3;
        svg("text", { x: 67, y: position + 5, "text-anchor": "end", fill: "#53666d", "font-size": 15 }, format(high - index / 4 * (high - low), digits));
      }
      svg("text", { x: 80, y: 320, fill: "#53666d", "font-size": 15 }, dateLabel(from.value));
      svg("text", { x: right, y: 320, "text-anchor": "end", fill: "#53666d", "font-size": 15 }, dateLabel(to.value));
      let path = "", previous = null;
      for (const row of points) {
        const adjacent = previous && day(row.date) - day(previous.date) === 86400000;
        path += `${adjacent ? "L" : "M"}${x(row).toFixed(2)},${y(row).toFixed(2)} `;
        previous = row;
      }
      svg("path", { d: path, fill: "none", stroke: "#0f766e", "stroke-width": 2.5, "stroke-linejoin": "round" });
      for (const row of points) {
        const point = svg("circle", { cx: x(row), cy: y(row), r: points.length > 400 ? 1.5 : 3, fill: "#0f766e", "data-date": row.date });
        const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
        title.textContent = `${dateLabel(row.date)}: ${format(row[metric], 4)} ${unit()}`;
        point.append(title);
      }
    }
    showPoint(selection?.bank === bank.value && selection.metric === metric ? points.find(row => row.date === selection.date) : null);
    const tbody = document.querySelector("#dailyRows");
    document.querySelector("#dailyMethod").textContent = bank.value === "partners" ? ui.methodNote({bank_id:"partners"}) : bank.value === "ppf" ? "PPF: publikované nuly často znamenají dny bez volání, nikoli okamžitou odezvu. Uptime banka v reportu neuvádí." : "";
    if (document.querySelector("#dailyBankDetail")) document.querySelector("#dailyBankDetail").href = ui.bankUrl(bank.value);
    tbody.replaceChildren();
    document.querySelector("#dailyTableSummary").textContent = `Jednotlivé uložené dny (${rows.length})`;
    for (const row of [...rows].reverse()) {
      const tr = document.createElement("tr");
      const date = document.createElement("th");
      date.scope = "row";
      date.textContent = dateLabel(row.date);
      tr.append(date);
      for (const key of Object.keys(labels)) {
        const td = document.createElement("td");
        td.textContent = format(row[key], 4);
        tr.append(td);
      }
      for (const key of ["first_seen_on", "last_seen_on", "versions"]) {
        const td = document.createElement("td");
        td.textContent = key === "versions" ? row[key] : dateLabel(row[key]);
        tr.append(td);
      }
      tbody.append(tr);
    }
    syncUrl();
  }
  chart.addEventListener("click", event => {
    if (!plot) return;
    const matrix = chart.getScreenCTM();
    if (!matrix) return;
    const point = chart.createSVGPoint(); point.x = event.clientX; point.y = event.clientY;
    const position = point.matrixTransform(matrix.inverse());
    if (position.x < 72 || position.x > plot.right + 8 || position.y < 25 || position.y > 295) return;
    const ratio = Math.max(0, Math.min(1, (position.x - 80) / (plot.right - 80)));
    const timestamp = plot.start + ratio * (plot.end - plot.start);
    showPoint(ui.nearestDailyPoint(plottedPoints, timestamp));
  });
  chart.addEventListener("keydown", event => {
    if (!plottedPoints.length || !["ArrowLeft", "ArrowRight", "Home", "End", "Escape"].includes(event.key)) return;
    event.preventDefault();
    if (event.key === "Escape") { showPoint(null); return; }
    const current = plottedPoints.findIndex(row => row.date === selection?.date);
    const index = event.key === "Home" ? 0 : event.key === "End" ? plottedPoints.length - 1 : current < 0 ? event.key === "ArrowLeft" ? plottedPoints.length - 1 : 0 : Math.max(0, Math.min(plottedPoints.length - 1, current + (event.key === "ArrowLeft" ? -1 : 1)));
    showPoint(plottedPoints[index]);
  });
  document.querySelector("#clearDailyPoint").addEventListener("click", () => { showPoint(null); chart.focus({ preventScroll: true }); });
  function syncUrl() {
    const url = new URL(location.href); url.searchParams.delete("v");
    for (const [key,value] of Object.entries({bank:bank.value, dailyMetric:metric, dayFrom:from.value, dayTo:to.value})) { if(value) url.searchParams.set(key,value); else url.searchParams.delete(key); }
    window.history.replaceState(null,"",url);
  }
  bank.addEventListener("change", () => { setRange(); render(); });
  from.addEventListener("change", () => { if (!from.value || !to.value) setRange(true); if (from.value > to.value) to.value = from.value; render(); });
  to.addEventListener("change", () => { if (!from.value || !to.value) setRange(true); if (to.value < from.value) from.value = to.value; render(); });
  document.querySelector("#archiveAll").addEventListener("click", () => { setRange(true); render(); });
  document.querySelector("#archiveMetrics").addEventListener("click", event => {
    const button = event.target.closest("[data-daily-metric]");
    if (!button || button.disabled) return;
    metric = button.dataset.dailyMetric;
    document.querySelectorAll("[data-daily-metric]").forEach(el => {
      el.classList.toggle("active", el === button);
      el.setAttribute("aria-pressed", String(el === button));
    });
    render();
  });
  setRange();
  const dates = history.filter(row => row.bank_id === bank.value).map(row => row.date);
  if (/^\d{4}-\d{2}-\d{2}$/.test(params.get("dayFrom") || "") && /^\d{4}-\d{2}-\d{2}$/.test(params.get("dayTo") || "") && params.get("dayFrom") <= params.get("dayTo") && dates.length) { from.value=params.get("dayFrom"); to.value=params.get("dayTo"); }
  document.querySelector("#exportDaily")?.addEventListener("click",()=>ui.download(`psd2-${bank.value}-${metric}.csv`,["banka","den","metrika","hodnota","jednotka","metodika","zdroj","první_uložení","poslední_ověření","verze"],exportedRows.map(row=>[row.bank,row.date,labels[metric],row[metric],unit(),row.metric_method,row.source_url,row.first_seen_on,row.last_seen_on,row.versions])));
  document.querySelector("#shareDaily")?.addEventListener("click",event=>ui.share(event.currentTarget));
  window.addEventListener("resize", render);
  render();
  ui.initializeNavigation();
})();
