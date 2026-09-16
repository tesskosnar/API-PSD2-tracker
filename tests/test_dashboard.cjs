const { test } = require('node:test');
const assert = require('node:assert/strict');
const ui = require('../dashboard/core.js');

test('separate service availability is not invented from an overall value', () => {
  const row = {availability_pct: 99.9};
  assert.equal(ui.metrics.aispAvailability.value(row), null);
  assert.equal(ui.metrics.pispAvailability.value(row), null);
  assert.equal(ui.metrics.availability.value({aisp_availability_pct:99,pisp_availability_pct:98}),98.5);
});
test('stable scales preserve zero, direction and boundaries', () => {
  assert.equal(ui.band('availability',100),0);
  assert.equal(ui.band('availability',99.99),0);
  assert.equal(ui.band('availability',99.9),1);
  assert.equal(ui.band('availability',0),4);
  assert.equal(ui.band('aispError',0),0);
  assert.equal(ui.band('aispError',.01),1);
  assert.equal(ui.band('aispError',5),4);
  assert.equal(ui.band('aispResponse',250),1);
  assert.equal(ui.band('aispResponse',null),null);
});
test('quarter comparison cannot carry rolling or old values into selected quarter', () => {
  const latest=[{bank_id:'ppf',latest_period:'2026-Q1',aisp_error_pct:100},{bank_id:'partners',latest_period:'rolling-30d-to-2026-09-15',availability_pct:99.9},{bank_id:'x',latest_period:'2026-Q2',availability_pct:99.8}];
  const history=[{bank_id:'x',period:'2026-Q2',report_url:'https://example.test',availability_pct:99.8}];
  const rows=ui.comparisonRows(latest,history,'quarter','2026-Q2');
  assert.equal(rows[0].aisp_error_pct,'');
  assert.equal(rows[1].availability_pct,'');
  assert.equal(rows[2].availability_pct,99.8);
  assert.equal(ui.comparisonRows(latest,history,'latest','2026-Q2')[1].comparison_group,'healthcheck');
  assert.equal(latest[0].aisp_error_pct,100);
});
test('shared error stays separate from individual services', () => {
  const row={aisp_error_pct:.3,pisp_error_pct:.3,metric_method:'spolecna error response rate'};
  assert.equal(ui.metrics.aispError.value(row),null);
  assert.equal(ui.metrics.pispError.value(row),null);
  assert.equal(ui.metrics.sharedError.value(row),.3);
});
test('CSV quotes Czech text, nulls and formula-like values safely', () => {
  assert.equal(ui.csv(['banka','hodnota'],[['Česká "banka"',null],['=formula',0]]),'\ufeff"banka","hodnota"\r\n"Česká ""banka""",""\r\n"\'=formula","0"');
});
