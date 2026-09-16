const { test } = require('node:test');
const assert = require('node:assert/strict');
const ui = require('../dashboard/core.js');

test('separate service availability is not invented from an overall value', () => {
  const row = {availability_pct: 99.9};
  assert.equal(ui.metrics.aispAvailability.value(row), null);
  assert.equal(ui.metrics.pispAvailability.value(row), null);
  assert.equal(ui.metrics.availability.value({aisp_availability_pct:99,pisp_availability_pct:98}),98.5);
});
test('median and MAD create three bands with correct metric direction', () => {
  const availability = ui.scale('availability', [90,97,98,99,100].map(value => ({availability_pct:value})));
  assert.equal(availability.median,98);
  assert.equal(availability.deviation,1);
  assert.deepEqual([availability.low,availability.high],[97,99]);
  assert.equal(availability.labels.length,3);
  assert.equal(ui.band('availability',100,availability),0);
  assert.equal(ui.band('availability',98,availability),1);
  assert.equal(ui.band('availability',97,availability),2);
  assert.equal(ui.band('availability',99,availability),0);
  assert.equal(ui.band('availability',90,availability),2);
  const errors = ui.scale('aispError', [0,1,2,3,8].map(value => ({aisp_error_pct:value})));
  assert.equal(ui.band('aispError',0,errors),0);
  assert.equal(ui.band('aispError',2,errors),1);
  assert.equal(ui.band('aispError',8,errors),2);
  assert.equal(ui.band('aispError',null,errors),null);
  const response = ui.scale('aispResponse', [10,20,30,40,50].map(value => ({aisp_response_ms:value})));
  assert.equal(ui.band('aispResponse',10,response),0);
  assert.equal(ui.band('aispResponse',30,response),1);
  assert.equal(ui.band('aispResponse',50,response),2);
});
test('median ignores blanks and invalid values, retains genuine zero and duplicates', () => {
  assert.equal(ui.median([null,'',undefined,NaN,Infinity,'invalid']),null);
  assert.equal(ui.median([null,'',0,0,10]),0);
  assert.equal(ui.median([1,2,3,4]),2.5);
  const source=[4,2,1,3];ui.median(source);assert.deepEqual(source,[4,2,1,3]);
  const empty=ui.scale('availability',[]);
  assert.equal(empty.median,null);
  assert.equal(ui.band('availability',null,empty),null);
});
test('flat and zero-heavy histories use a neutral median without invented limits', () => {
  const flat=ui.scale('availability',[{availability_pct:100},{availability_pct:100}]);
  assert.equal(flat.deviation,0);
  assert.equal(ui.band('availability',100,flat),1);
  assert.equal(ui.band('availability',99.99,flat),2);
  const zero=ui.scale('aispError',[0,0,0,0,1].map(value=>({aisp_error_pct:value})));
  assert.equal(zero.median,0);
  assert.equal(ui.band('aispError',0,zero),1);
  assert.equal(ui.band('aispError',1,zero),2);
  const floating=ui.scale('aispError',[.1,.2,.3].map(value=>({aisp_error_pct:value})));
  assert.equal(ui.band('aispError',.3,floating),2);
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
test('history orders banks by actual selected metric values, then Czech alphabet', () => {
  const banks=[{bank:'Air Bank'},{bank:'ČSOB'},{bank:'Fio banka'},{bank:'Trinity Bank'}];
  const history=[
    {bank:'Air Bank',period:'2026-Q2',report_url:'air',availability_pct:99},
    {bank:'ČSOB',period:'2026-Q2',report_url:'csob',aisp_response_ms:200},
    {bank:'Fio banka',period:'2026-Q2',report_url:'fio',availability_pct:99,aisp_response_ms:0},
    {bank:'Trinity Bank',period:'2026-Q2',report_url:'trinity',availability_pct:99},
  ];
  assert.deepEqual(ui.bankMetricCoverage(banks,history,'availability'),[['Air Bank',1],['Fio banka',1],['Trinity Bank',1],['ČSOB',0]]);
  assert.deepEqual(ui.bankMetricCoverage(banks,history,'aispResponse'),[['ČSOB',1],['Fio banka',1],['Air Bank',0],['Trinity Bank',0]]);
  assert.deepEqual(ui.bankMetricCoverage(banks,history.filter(row=>row.bank==='Air Bank'),'aispResponse'),[['Air Bank',0],['ČSOB',0],['Fio banka',0],['Trinity Bank',0]]);
  assert.deepEqual(ui.bankMetricCoverage(banks,history,'aispAvailability'),[['Air Bank',0],['ČSOB',0],['Fio banka',0],['Trinity Bank',0]]);
});
test('CSV quotes Czech text, nulls and formula-like values safely', () => {
  assert.equal(ui.csv(['banka','hodnota'],[['Česká "banka"',null],['=formula',0]]),'\ufeff"banka","hodnota"\r\n"Česká ""banka""",""\r\n"\'=formula","0"');
});
test('daily selection uses an actual measured day, including gaps, edges and ties', () => {
  const rows = [{date:'2026-06-01',value:0},{date:'2026-06-02',value:1},{date:'2026-06-05',value:2}];
  const time = value => Date.parse(`${value}T00:00:00Z`);
  assert.equal(ui.nearestDailyPoint(rows,time('2026-06-02')),rows[1]);
  assert.equal(ui.nearestDailyPoint(rows,time('2026-05-01')),rows[0]);
  assert.equal(ui.nearestDailyPoint(rows,time('2026-07-01')),rows[2]);
  assert.equal(ui.nearestDailyPoint(rows,time('2026-06-03')),rows[1]);
  assert.equal(ui.nearestDailyPoint(rows,time('2026-06-04')),rows[2]);
  assert.equal(ui.nearestDailyPoint(rows,(time('2026-06-02')+time('2026-06-05'))/2),rows[1]);
  assert.equal(ui.nearestDailyPoint([rows[0]],time('2026-06-05')),rows[0]);
  assert.equal(ui.nearestDailyPoint([],time('2026-06-01')),null);
  assert.equal(ui.nearestDailyPoint(rows,NaN),null);
});
