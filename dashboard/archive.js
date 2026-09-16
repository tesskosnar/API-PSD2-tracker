(() => {
  "use strict";
  const data = window.PSD2_DATA || {};
  const history = data.daily_history || [];
  const bank = document.querySelector("#archiveBank");
  const from = document.querySelector("#archiveFrom");
  const to = document.querySelector("#archiveTo");
  const chart = document.querySelector("#dailyChart");
  let metric = "aisp_response_ms";
  const labels = { aisp_response_ms: "Odezva AISP", pisp_response_ms: "Odezva PISP", aisp_error_pct: "Chybovost AISP", pisp_error_pct: "Chybovost PISP" };
  const format = (value, digits = 2) => value === "" || value === null || value === undefined ? "—" : new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: digits }).format(Number(value));
  const day = value => new Date(`${value}T00:00:00Z`);
  const dateLabel = value => new Intl.DateTimeFormat("cs-CZ", { timeZone: "UTC" }).format(day(value));
  const unit = () => metric.endsWith("_ms") ? "ms" : "%";
  const number = value => value === "" || value === null || value === undefined ? null : Number(value);
  const bankNames = new Map(history.map(row => [row.bank_id, row.bank]));
  for (const [id, name] of [...bankNames].sort((a,b) => a[1].localeCompare(b[1], "cs"))) bank.add(new Option(name, id));
  document.querySelector("#archiveMeta").textContent = data.archive?.checked_on ? `Poslední sběr ${dateLabel(data.archive.checked_on)}` : "Archiv se naplní při nejbližším sběru";

  function setRange(full = false) {
    const dates = history.filter(row => row.bank_id === bank.value).map(row => row.date).sort();
    if (!dates.length) return;
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
  function render() {
    const rows = history.filter(row => row.bank_id === bank.value && row.date >= from.value && row.date <= to.value).sort((a,b) => a.date.localeCompare(b.date));
    const points = rows.filter(row => Number.isFinite(number(row[metric])));
    chart.replaceChildren();
    chart.hidden = !points.length;
    document.querySelector("#dailyEmpty").hidden = Boolean(points.length);
    document.querySelector("#dailyRange").textContent = rows.length ? `${dateLabel(from.value)} – ${dateLabel(to.value)} · ${rows.length} uložených dnů · ${labels[metric]} (${unit()})` : "Žádné uložené dny ve výběru";
    if (points.length) {
      const width = Math.max(650, Math.min(1080, chart.parentElement.clientWidth));
      chart.setAttribute("viewBox", `0 0 ${width} 340`);
      const right = width - 30;
      const min = Math.min(...points.map(row => number(row[metric])));
      const max = Math.max(...points.map(row => number(row[metric])));
      const padding = (max - min) * .1 || Math.max(max * .05, 1);
      const low = Math.max(0, min - padding), high = max + padding;
      const start = day(from.value).getTime(), end = day(to.value).getTime();
      const x = row => 80 + (day(row.date).getTime() - start) / (end - start || 86400000) * (right - 80);
      const y = row => 285 - (number(row[metric]) - low) / (high - low) * 250;
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
        const point = svg("circle", { cx: x(row), cy: y(row), r: points.length > 400 ? 1.5 : 3, fill: "#0f766e" });
        const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
        title.textContent = `${dateLabel(row.date)}: ${format(row[metric], 4)} ${unit()}`;
        point.append(title);
      }
    }
    const tbody = document.querySelector("#dailyRows");
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
  }
  bank.addEventListener("change", () => { setRange(); render(); });
  from.addEventListener("change", () => { if (!from.value || !to.value) setRange(true); if (from.value > to.value) to.value = from.value; render(); });
  to.addEventListener("change", () => { if (!from.value || !to.value) setRange(true); if (to.value < from.value) from.value = to.value; render(); });
  document.querySelector("#archiveAll").addEventListener("click", () => { setRange(true); render(); });
  document.querySelector("#archiveMetrics").addEventListener("click", event => {
    const button = event.target.closest("[data-daily-metric]");
    if (!button) return;
    metric = button.dataset.dailyMetric;
    document.querySelectorAll("[data-daily-metric]").forEach(el => {
      el.classList.toggle("active", el === button);
      el.setAttribute("aria-pressed", String(el === button));
    });
    render();
  });
  setRange();
  window.addEventListener("resize", render);
  render();
})();
