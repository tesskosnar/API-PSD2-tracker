(() => {
  "use strict";
  const data = window.PSD2_DATA || {};
  const params = new URLSearchParams(location.search);
  const bank = params.get("bank") || "unicredit";
  const period = params.get("period") || data.latest?.find(item => item.bank_id === bank)?.latest_period || "";
  const detail = data.source_details?.[`${bank}:${period}`];
  const row = data.timeseries?.find(item => item.bank_id === bank && item.period === period)
    || data.latest?.find(item => item.bank_id === bank && item.latest_period === period);
  const quarter = /^(\d{4})-Q([1-4])$/.exec(period);
  document.querySelector("#reportPeriod").textContent = quarter ? `${quarter[2]}Q${quarter[1]}` : "Český PSD2 report";
  if (bank !== "unicredit" || !detail || !row || !["CZ", "CZ-B"].includes(detail.country_code) || detail.service !== "Dedicated Interface") {
    document.querySelector("#reportEmpty").hidden = false;
    document.querySelector("#reportContent").hidden = true;
    return;
  }
  if (detail.checked_on) document.querySelector("#reportChecked").textContent = `Ověřeno ${new Intl.DateTimeFormat("cs-CZ", { timeZone: "UTC" }).format(new Date(`${detail.checked_on}T00:00:00Z`))}`;
  const format = (value, digits = 2) => value === null || value === undefined || value === "" ? "—" : new Intl.NumberFormat("cs-CZ", { maximumFractionDigits: digits }).format(Number(value));
  const cards = [
    ["Dostupnost", row.availability_pct, "%", 3],
    ["Odezva AISP", row.aisp_response_ms, "ms", 2],
    ["Odezva PISP", row.pisp_response_ms, "ms", 2],
    ["Společná chybovost", row.aisp_error_pct, "%", 4],
  ];
  for (const [label, value, unit, digits] of cards) {
    const card = document.createElement("article");
    const title = document.createElement("span");
    title.textContent = label;
    const number = document.createElement("strong");
    number.textContent = `${format(value, digits)} ${unit}`;
    card.append(title, number);
    document.querySelector("#reportSummary").append(card);
  }
  for (const month of detail.months) {
    const tr = document.createElement("tr");
    const label = document.createElement("th");
    label.scope = "row";
    label.textContent = new Intl.DateTimeFormat("cs-CZ", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${month.month}-01T00:00:00Z`));
    tr.append(label);
    for (const key of ["availability_pct", "aisp_response_ms", "pisp_response_ms", "shared_error_pct"]) {
      const td = document.createElement("td");
      td.textContent = format(month[key], 4);
      tr.append(td);
    }
    document.querySelector("#reportMonths").append(tr);
  }
})();
