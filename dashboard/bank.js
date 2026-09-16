(() => {
  "use strict";
  const ui = window.PSD2_UI, data = window.PSD2_DATA;
  const params = new URLSearchParams(location.search);
  const banks = data.latest.filter(row => row.scope === "main").sort((a,b) => a.bank.localeCompare(b.bank, "cs"));
  const bank = banks.find(row => row.bank_id === params.get("bank"));
  const selector = document.getElementById("detailBank");
  banks.forEach(row => selector.add(new Option(row.bank, row.bank_id)));
  selector.addEventListener("change", () => { location.href = ui.bankUrl(selector.value); });
  if (!bank) { document.getElementById("bankNotFound").hidden = false; document.querySelectorAll("main section").forEach(el => { el.hidden = true; }); return; }
  selector.value = bank.bank_id;
  document.title = `${bank.bank} · PSD2 API tracker`;
  document.getElementById("bankTitle").textContent = bank.bank;
  document.getElementById("bankMeta").textContent = `Poslední kontrola ${ui.dateLabel(data.checked_on)} · nejnovější údaje ${ui.periodLabel(bank.latest_period) || "nedoloženy"}`;
  const history = data.timeseries.filter(row => row.bank_id === bank.bank_id && row.report_url).sort((a,b) => a.period.localeCompare(b.period));
  let selectedPeriod = history.some(row => row.period === params.get("period")) ? params.get("period") : "latest";
  if (params.has("period") && selectedPeriod === "latest") { document.getElementById("bankNotFound").hidden = false; document.getElementById("bankNotFound").textContent = "Požadované čtvrtletí není doložené. Níže jsou nejnovější dostupné údaje banky."; }
  let activeMetric = ui.metrics[params.get("bankMetric")] ? params.get("bankMetric") : "availability";
  const periodSelect = document.getElementById("bankPeriods");
  periodSelect.add(new Option(`Nejnovější · ${ui.periodLabel(bank.latest_period) || "bez údaje"}`, "latest"));
  [...history].reverse().forEach(row => periodSelect.add(new Option(ui.shortPeriod(row.period), row.period)));
  periodSelect.value = selectedPeriod;
  const openCoverage = ui.createCoverageDialog();
  function syncUrl() {
    const url = new URL(location.href); url.searchParams.delete("v"); url.searchParams.set("bank", bank.bank_id); url.searchParams.set("bankMetric", activeMetric);
    if (selectedPeriod === "latest") url.searchParams.delete("period"); else url.searchParams.set("period", selectedPeriod);
    window.history.replaceState(null, "", url);
  }
  function renderReport() {
    const row = selectedPeriod === "latest" ? bank : history.find(item => item.period === selectedPeriod);
    document.getElementById("bankMethod").textContent = ui.methodNote(row);
    const cards = document.getElementById("bankMetrics"); cards.replaceChildren();
    Object.values(ui.metrics).forEach(metric => {
      const value = metric.value(row), card = document.createElement("article"); card.className = `bank-metric-card${value === null ? " bank-metric-card--empty" : ""}`;
      const label = document.createElement("span"); label.textContent = metric.label;
      const number = document.createElement("strong"); number.textContent = value === null ? "Údaj nedoložen" : metric.format(value);
      card.append(label, number);
      if (metric.key === "availability" && value !== null && ui.number(row.availability_pct) === null) { const note = document.createElement("small"); note.textContent = "Nevážený průměr AISP/PISP"; card.append(note); }
      cards.append(card);
    });
    ui.coverageContent(document.getElementById("bankReportCoverage"), data, row);
  }
  function rank(period) { const [year, quarter] = period.split("-Q").map(Number); return year * 4 + quarter; }
  function svg(tag, attrs, text) {
    const el = document.createElementNS("http://www.w3.org/2000/svg", tag); for (const [key,value] of Object.entries(attrs)) el.setAttribute(key,value);
    if (text !== undefined) el.textContent = text; document.getElementById("bankChart").append(el); return el;
  }
  function renderHistory() {
    const available = key => history.some(row => ui.metrics[key].value(row) !== null);
    if (!available(activeMetric) && !params.has("bankMetric")) activeMetric = Object.keys(ui.metrics).find(available) || "availability";
    document.querySelectorAll("#bankHistoryMetrics [data-metric]").forEach(button => {
      button.disabled = !available(button.dataset.metric); const active = button.dataset.metric === activeMetric; button.classList.toggle("active", active); button.setAttribute("aria-pressed", String(active)); button.title = button.disabled ? "V ověřené čtvrtletní historii není tato metrika doložená" : ui.metrics[button.dataset.metric].label;
    });
    const metric = ui.metrics[activeMetric], points = history.filter(row => metric.value(row) !== null);
    document.getElementById("bankHistoryInfo").textContent = history.length ? `${history.length} doložených čtvrtletí · ${metric.label} (${metric.unit}) · ${metric.note}` : "Český čtvrtletní report není doložený. Pokud jsou dostupné denní hodnoty, najdete je níže.";
    document.getElementById("bankHistoryMetricHeader").textContent = `${metric.label} (${metric.unit})`;
    const chart = document.getElementById("bankChart"); chart.replaceChildren(); chart.toggleAttribute("hidden", !points.length);
    if (points.length) {
      const width = Math.max(300, Math.min(1080, chart.parentElement.clientWidth));
      chart.setAttribute("viewBox", `0 0 ${width} 260`);
      const left = 70, right = width - 20;
      const min = Math.min(...points.map(metric.value)), max = Math.max(...points.map(metric.value)); const padding = (max-min) * .1 || 1;
      const low = Math.max(0, min-padding), high = metric.higher ? Math.min(100, max+padding) : max+padding;
      const first = rank(history[0].period), last = rank(history.at(-1).period);
      const x = row => last === first ? (left+right)/2 : left + (rank(row.period)-first) / (last-first) * (right-left), y = row => 210 - (metric.value(row)-low) / (high-low || 1) * 170;
      svg("title", {}, `${bank.bank} · ${metric.label}`);
      for (let index=0; index<=4; index++) { const position=40+index*42.5; svg("line", {x1:left,x2:right,y1:position,y2:position,stroke:"#dce2df"}); svg("text", {x:left-8,y:position+5,"text-anchor":"end",fill:"#53666d","font-size":13}, ui.format(high-index/4*(high-low), metric.unit === "ms" ? 0 : 3)); }
      if (first === last) svg("text", {x:(left+right)/2,y:247,"text-anchor":"middle",fill:"#53666d","font-size":13}, ui.shortPeriod(history[0].period));
      else { svg("text", {x:left,y:247,fill:"#53666d","font-size":13}, ui.shortPeriod(history[0].period)); svg("text", {x:right,y:247,"text-anchor":"end",fill:"#53666d","font-size":13}, ui.shortPeriod(history.at(-1).period)); }
      let path="", previous=null;
      points.forEach(row => { path += `${previous && rank(row.period)-rank(previous.period) === 1 ? "L" : "M"}${x(row).toFixed(2)},${y(row).toFixed(2)} `; previous=row; });
      svg("path", {d:path,fill:"none",stroke:"#0f766e","stroke-width":2.5});
      points.forEach(row => { const dot=svg("circle",{cx:x(row),cy:y(row),r:4,fill:"#0f766e"}); const title=document.createElementNS("http://www.w3.org/2000/svg","title"); title.textContent=`${ui.shortPeriod(row.period)}: ${metric.format(metric.value(row))}`; dot.append(title); });
    }
    const rows = document.getElementById("bankHistoryRows"); rows.replaceChildren();
    for (const report of [...history].reverse()) {
      const row = document.createElement("tr"); const period = document.createElement("th"); period.scope="row"; period.textContent=ui.shortPeriod(report.period);
      const value=document.createElement("td"); value.textContent=metric.value(report) === null ? "—" : metric.format(metric.value(report));
      const coverage=data.report_coverage?.[`${bank.bank_id}:${report.period}`], days=document.createElement("td"); days.textContent=coverage ? `${coverage.archived_days} / ${coverage.calendar_days}` : "Nedoloženo";
      const source=document.createElement("td"), button=document.createElement("button"); button.type="button"; button.className="text-button"; button.textContent="Podrobnosti →"; button.addEventListener("click",()=>openCoverage(data,report)); source.append(button); row.append(period,value,days,source); rows.append(row);
    }
  }
  ui.appendMetricButtons(document.getElementById("bankHistoryMetrics"), activeMetric);
  document.getElementById("bankHistoryMetrics").addEventListener("click",event=>{ const button=event.target.closest("[data-metric]"); if (!button || button.disabled) return; activeMetric=button.dataset.metric; renderHistory(); syncUrl(); });
  periodSelect.addEventListener("change",()=>{selectedPeriod=periodSelect.value; renderReport(); syncUrl();});
  document.getElementById("shareBank").addEventListener("click",event=>ui.share(event.currentTarget));
  document.getElementById("exportBankHistory").addEventListener("click",()=>{ const metric=ui.metrics[activeMetric]; ui.download(`psd2-${bank.bank_id}-${activeMetric}.csv`,["banka","období","metrika","hodnota","jednotka","metodika","zdroj"],history.map(row=>[bank.bank,row.period,metric.label,metric.value(row),metric.unit,row.metric_method,row.report_url])); });
  window.addEventListener("resize", renderHistory);
  renderReport(); renderHistory(); syncUrl();
})();
