const { test } = require('node:test');
const assert = require('node:assert/strict');
const ui = require('../dashboard/core.js');

test('report completeness uses days for supplied metrics, not mere uptime presence', () => {
  const row={report_url:'https://example.test',aisp_response_ms:10};
  const coverage={archived_days:91,calendar_days:91,metric_days:{aisp_response_ms:91}};
  assert.equal(ui.reportCompleteness(row,coverage),'full');
  assert.equal(ui.reportCompleteness({...row,availability_pct:99},coverage),'partial');
  assert.equal(ui.reportCompleteness(row,{...coverage,archived_days:90}),'partial');
  assert.equal(ui.reportCompleteness({...row,status:'unverified'},coverage),'missing');
  assert.equal(ui.reportCompleteness({report_url:row.report_url},coverage),'report');
  assert.equal(ui.reportCompleteness(null,coverage),'missing');
  assert.equal(ui.reportCompleteness({report_url:row.report_url,aisp_error_pct:.3,pisp_error_pct:.3,metric_method:'spolecna error response rate'},{archived_days:91,calendar_days:91,metric_days:{shared_error_pct:91}}),'full');
});
test('CZ report matrix excludes foreign and country-unverified catalogs without deleting them', () => {
  const cz={bank_id:'cz',report_url:'https://example.test/cz',status:'ok'};
  const foreign={bank_id:'mbank',report_url:'https://example.test/pl',status:'ok',country_code:'PL'};
  const unknown={bank_id:'oberbank',report_url:'https://example.test/unknown',status:'unverified'};
  const details={cz:{country_scope:'CZ',published_reports:[cz,unknown,foreign]},pl:{country_scope:'PL',published_reports:[foreign]},unknown:{country_scope:'unverified',published_reports:[unknown]},legacy:{published_reports:[cz]}};
  const before=JSON.stringify(details);
  assert.deepEqual(ui.czSourceReports(details),[cz]);
  assert.equal(ui.reportCompleteness(foreign,null),'missing');
  assert.equal(ui.reportCompleteness({...cz,country_scope:'PL'},null),'missing');
  assert.equal(ui.reportCompleteness(unknown,null),'missing');
  assert.equal(JSON.stringify(details),before);
  assert.deepEqual(ui.czSourceReports(null),[]);
});
test('calculated quarter is separated and never borrows rolling uptime', () => {
  const latest=[{bank_id:'moneta',latest_period:'rolling-90d-to-2026-09-15',availability_pct:'',aisp_response_ms:500}];
  const history=[{bank_id:'moneta',period:'2026-Q2',report_kind:'archive-derived',archived_days:13,calendar_days:91,report_url:'https://example.test',aisp_response_ms:100,availability_pct:''}];
  const row=ui.comparisonRows(latest,history,'quarter','2026-Q2')[0];
  assert.equal(row.comparison_group,'derived');
  assert.equal(row.aisp_response_ms,100);
  assert.equal(ui.availability(row),null);
  assert.match(ui.methodNote(row),/13\/91/);
});

test('supplementary documents retain country scope, are deduplicated, and stay outside CZ counts', () => {
  const unknown={bank_id:'mbank',report_url:'https://example.test/unknown',period:'2026-Q2',status:'unverified'};
  const pl={bank_id:'mbank',report_url:'https://example.test/pl',period:'2026-Q1',country_code:'PL',status:'ok'};
  const cz={bank_id:'mbank',report_url:'https://example.test/cz',period:'2025-Q4',country_scope:'CZ',status:'ok'};
  const details={mbank:{country_scope:'unverified',published_reports:[unknown,pl,cz,unknown]},ober:{country_scope:'unverified',published_reports:[{...unknown,bank_id:'oberbank'}]}};
  const before=JSON.stringify(details);
  const rows=ui.supplementaryReports(details,'mbank');
  assert.deepEqual(rows.map(row=>row.report_url),[unknown.report_url,pl.report_url]);
  assert.deepEqual(rows.map(ui.reportCountryLabel),['Země neověřena · CZ nepotvrzeno','Polsko']);
  rows.forEach(row=>assert.equal(ui.reportCompleteness(row,null),'missing'));
  assert.deepEqual(ui.czSourceReports(details),[]);
  assert.equal(JSON.stringify(details),before);
  assert.deepEqual(ui.supplementaryReports(null,'mbank'),[]);
  assert.equal(ui.reportCountryLabel({...unknown,country_scope:'CZ'}),'Český rozsah neověřen');
});

test('actual mBank catalog supplies summary statistics without claiming verified CZ scope', () => {
  const fs=require('node:fs');
  const path=require('node:path');
  const data=JSON.parse(fs.readFileSync(path.join(__dirname,'../dashboard/data.js'),'utf8').replace(/^window\.PSD2_DATA\s*=\s*/,'').trim().replace(/;$/,''));
  const rows=ui.supplementaryReports(data.source_details,'mbank');
  assert.equal(rows.length,28);
  assert.equal(new Set(rows.map(row=>row.report_url)).size,28);
  assert.ok(rows.every(row=>row.country_scope==='unverified'));
  assert.equal(ui.czSourceReports(data.source_details).filter(row=>row.bank_id==='mbank').length,0);
  const history=data.timeseries.filter(row=>row.bank_id==='mbank');
  assert.equal(history.length,29);
  assert.ok(history.every(row=>ui.isSummaryReport(row) && ui.hasMetrics(row) && !ui.isCzReport(row)));
  assert.equal(data.latest.filter(row=>row.bank_id==='mbank' && ui.hasMetrics(row)).length,1);
  const latest=data.latest.find(row=>row.bank_id==='mbank');
  assert.equal(latest.latest_period,'2026-Q2');
  assert.equal(ui.comparisonRows([latest],history,'quarter','2026-Q2')[0].status,'unverified');
  assert.equal(ui.reportCompleteness(history.at(-1),data.report_coverage['mbank:2026-Q2']),'full');
  assert.equal(ui.reportCompleteness(history[0],data.report_coverage['mbank:2019-Q2']),'partial');
  assert.ok(history.every(row=>ui.metrics.aispError.value(row)===null && ui.metrics.pispError.value(row)===null && ui.metrics.aispAvailability.value(row)===null));
  assert.match(ui.methodNote(latest),/český rozsah nepotvrzen/);
});

test('mBank catalog uses the summary report label while retaining scope disclosure', () => {
  const fs=require('node:fs');
  const path=require('node:path');
  const read=file=>fs.readFileSync(path.join(__dirname,'../dashboard',file),'utf8');
  const app=read('app.js'), bank=read('bank.js'), html=read('bank.html');
  assert.equal((app.match(/link\.textContent = "Souhrnný report →"/g)||[]).length,2);
  assert.doesNotMatch(app,/reportů mimo CZ|Reporty mimo CZ/);
  assert.match(bank,/psd2-mbank-souhrnny-report\.csv/);
  assert.match(html,/>Souhrnný report<\/a>/);
  assert.match(html,/>Souhrnný report mBank<\/h2>/);
  assert.match(html,/nejsou doložené jako samostatné české statistiky/);
  assert.match(html,/denní hodnoty a čtvrtletní souhrny jsou zahrnuty do statistik/);
});

test('separate service availability is not invented from an overall value', () => {
  const row = {availability_pct: 99.9};
  assert.equal(ui.metrics.aispAvailability.value(row), null);
  assert.equal(ui.metrics.pispAvailability.value(row), null);
  assert.equal(ui.metrics.availability.value({aisp_availability_pct:99,pisp_availability_pct:98}),98.5);
});
test('median and MAD create three green bands below the fixed alert threshold', () => {
  const availability = ui.scale('availability', [99,99.25,99.5,99.75,100].map(value => ({availability_pct:value})));
  assert.equal(availability.median,99.5);
  assert.equal(availability.deviation,.25);
  assert.deepEqual([availability.low,availability.high],[99.25,99.75]);
  assert.equal(availability.labels.length,4);
  assert.equal(ui.band('availability',100,availability),0);
  assert.equal(ui.band('availability',99.5,availability),1);
  assert.equal(ui.band('availability',99.25,availability),2);
  assert.equal(ui.band('availability',99.75,availability),0);
  assert.equal(ui.band('availability',98.999,availability),3);
  const errors = ui.scale('aispError', [0,.25,.5,.75,1].map(value => ({aisp_error_pct:value})));
  assert.equal(ui.band('aispError',0,errors),0);
  assert.equal(ui.band('aispError',.5,errors),1);
  assert.equal(ui.band('aispError',1,errors),2);
  assert.equal(ui.band('aispError',1.001,errors),3);
  assert.equal(ui.band('aispError',null,errors),null);
  const response = ui.scale('aispResponse', [10,20,30,40,50].map(value => ({aisp_response_ms:value})));
  assert.equal(ui.band('aispResponse',10,response),0);
  assert.equal(ui.band('aispResponse',30,response),1);
  assert.equal(ui.band('aispResponse',50,response),2);
});
test('fixed benchmark thresholds override median bands only after the exact limit', () => {
  const availability=ui.scale('availability',[98,99,100].map(availability_pct=>({availability_pct})));
  assert.equal(ui.benchmarkAlert('availability',99),false);
  assert.equal(ui.benchmarkAlert('aispAvailability',98.999),true);
  assert.equal(ui.band('availability',98.999,availability),3);
  const response=ui.scale('aispResponse',[100,500,1500].map(aisp_response_ms=>({aisp_response_ms})));
  assert.equal(ui.benchmarkAlert('aispResponse',1000),false);
  assert.equal(ui.benchmarkAlert('pispResponse',1000.01),true);
  assert.equal(ui.band('aispResponse',1000.01,response),3);
  const error=ui.scale('aispError',[0,.5,2].map(aisp_error_pct=>({aisp_error_pct})));
  assert.equal(ui.benchmarkAlert('aispError',1),false);
  assert.equal(ui.benchmarkAlert('sharedError',1.001),true);
  assert.equal(ui.band('aispError',1.001,error),3);
  assert.equal(ui.benchmarkAlert('aispError',null),false);
  assert.equal(ui.benchmarkLabel('availability'),'Výpadek > 1 %');
  assert.equal(ui.benchmarkLabel('pispResponse'),'Odezva > 1 000 ms');
  assert.equal(ui.benchmarkLabel('sharedError'),'Chybovost > 1 %');
});
test('current ČSOB and CREDITAS values cross the intended benchmark cells', () => {
  const fs=require('node:fs'),path=require('node:path');
  const data=JSON.parse(fs.readFileSync(path.join(__dirname,'../dashboard/data.js'),'utf8').replace(/^window\.PSD2_DATA\s*=\s*/,'').trim().replace(/;$/,''));
  const csob=data.latest.find(row=>row.bank_id==='csob');
  const creditas=data.latest.find(row=>row.bank_id==='creditas');
  assert.equal(ui.benchmarkAlert('aispError',ui.metrics.aispError.value(csob)),true);
  assert.equal(ui.benchmarkAlert('pispError',ui.metrics.pispError.value(csob)),true);
  assert.equal(ui.benchmarkAlert('aispResponse',ui.metrics.aispResponse.value(creditas)),true);
  assert.equal(ui.benchmarkAlert('pispResponse',ui.metrics.pispResponse.value(creditas)),false);
  assert.equal(ui.benchmarkAlert('availability',ui.metrics.availability.value(creditas)),false);
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

test('quarter selection uses actual supplied periods, including gaps, ties and endpoints', () => {
  const rows=[{period:'2024-Q1'},{period:'2024-Q3'},{period:'2025-Q1'}];
  assert.equal(ui.nearestQuarterPoint(rows,ui.quarterRank('2024-Q3')),rows[1]);
  assert.equal(ui.nearestQuarterPoint(rows,ui.quarterRank('2024-Q2')),rows[0]);
  assert.equal(ui.nearestQuarterPoint(rows,ui.quarterRank('2024-Q2')+.1),rows[1]);
  assert.equal(ui.nearestQuarterPoint(rows,ui.quarterRank('2023-Q4')),rows[0]);
  assert.equal(ui.nearestQuarterPoint(rows,ui.quarterRank('2026-Q2')),rows[2]);
  assert.equal(ui.nearestQuarterPoint([rows[0]],ui.quarterRank('2026-Q2')),rows[0]);
  assert.equal(ui.nearestQuarterPoint([],ui.quarterRank('2024-Q1')),null);
  assert.equal(ui.nearestQuarterPoint(rows,NaN),null);
  assert.ok(Number.isNaN(ui.quarterRank('2024-Q5')));
});

test('quarter dates describe the aggregate period, including leap years and year end', () => {
  assert.deepEqual(ui.quarterDates('2024-Q1'),{from:'2024-01-01',to:'2024-03-31'});
  assert.deepEqual(ui.quarterDates('2026-Q2'),{from:'2026-04-01',to:'2026-06-30'});
  assert.deepEqual(ui.quarterDates('2026-Q3'),{from:'2026-07-01',to:'2026-09-30'});
  assert.deepEqual(ui.quarterDates('2026-Q4'),{from:'2026-10-01',to:'2026-12-31'});
  for (const value of [null,'','2026-Q0','2026-Q5','rolling-90d-to-2026-09-15']) assert.equal(ui.quarterDates(value),null);
});

test('daily summary counts inclusive calendar days without filling gaps or using outside dates', () => {
  const rows=[{date:'2024-02-28',availability_pct:100},{date:'2024-03-01',availability_pct:0},{date:'2024-03-02',availability_pct:10},{date:'2024-02-30',availability_pct:50}];
  const summary=ui.dailySummary(rows,'2024-02-28','2024-03-01');
  assert.equal(summary.calendarDays,3);
  assert.equal(summary.archivedDays,2);
  assert.deepEqual(summary.metrics.availability,{value:50,count:2,zeroDays:0,derivedDays:0,missingDays:1});
  assert.equal(ui.dailySummary(rows,'2024-03-01','2024-03-01').metrics.availability.value,0);
  for(const [from,to] of [['2024-02-30','2024-03-01'],['2024-03-01','2024-02-28'],['','2024-03-01']]) {
    const empty=ui.dailySummary(rows,from,to);
    assert.equal(empty.calendarDays,0);assert.equal(empty.archivedDays,0);
    assert.ok(Object.values(empty.metrics).every(item=>item.value===null && item.count===0));
  }
});

test('daily summary averages all metrics, retains genuine percentage zeros and excludes zero responses', () => {
  const rows=[
    {date:'2026-06-01',availability_pct:0,aisp_availability_pct:90,pisp_availability_pct:80,aisp_response_ms:0,pisp_response_ms:100,aisp_error_pct:0,pisp_error_pct:2,shared_error_pct:0},
    {date:'2026-06-02',availability_pct:100,aisp_availability_pct:100,pisp_availability_pct:100,aisp_response_ms:200,pisp_response_ms:300,aisp_error_pct:2,pisp_error_pct:0,shared_error_pct:4},
    {date:'2026-06-03',availability_pct:'',aisp_response_ms:null,pisp_response_ms:NaN,aisp_error_pct:-1,pisp_error_pct:101,shared_error_pct:Infinity},
  ];
  const {metrics}=ui.dailySummary(rows,'2026-06-01','2026-06-04');
  assert.deepEqual(Object.values(metrics).map(item=>item.value),[50,95,90,200,200,1,1,2]);
  assert.deepEqual(metrics.aispResponse,{value:200,count:1,zeroDays:1,derivedDays:0,missingDays:2});
  assert.equal(metrics.aispError.count,2);
  const zero=ui.dailySummary([{date:'2026-06-01',aisp_response_ms:0}],'2026-06-01','2026-06-02').metrics.aispResponse;
  assert.deepEqual(zero,{value:null,count:0,zeroDays:1,derivedDays:0,missingDays:1});
});

test('derived daily availability requires both valid services and preserves the published overall value', () => {
  const rows=[
    {date:'2026-06-01',aisp_availability_pct:100,pisp_availability_pct:90},
    {date:'2026-06-02',aisp_availability_pct:80},
    {date:'2026-06-03',availability_pct:98,aisp_availability_pct:50,pisp_availability_pct:50},
    {date:'2026-06-04',aisp_availability_pct:150,pisp_availability_pct:50},
  ];
  const summary=ui.dailySummary(rows,'2026-06-01','2026-06-04');
  assert.deepEqual(summary.metrics.availability,{value:96.5,count:2,zeroDays:0,derivedDays:1,missingDays:2});
  assert.equal(summary.metrics.aispAvailability.count,3);
  assert.equal(summary.metrics.pispAvailability.count,3);
});

test('daily summary deduplicates the latest supplied version without mutating the archive', () => {
  const rows=[{date:'2026-06-01',availability_pct:100},{date:'2026-06-01',availability_pct:80}];
  const before=JSON.stringify(rows);
  const summary=ui.dailySummary(rows,'2026-06-01','2026-06-01');
  assert.equal(summary.archivedDays,1);assert.equal(summary.metrics.availability.value,80);
  assert.equal(JSON.stringify(rows),before);
});

test('actual daily summary agrees with CREDITAS quarter and does not invent MONETA uptime or mBank service errors', () => {
  const fs=require('node:fs'), path=require('node:path');
  const daily=JSON.parse(fs.readFileSync(path.join(__dirname,'../data/daily-history.json'),'utf8'));
  const data=JSON.parse(fs.readFileSync(path.join(__dirname,'../dashboard/data.js'),'utf8').replace(/^window\.PSD2_DATA\s*=\s*/,'').trim().replace(/;$/,''));
  const quarter=bank=>ui.dailySummary(daily.filter(row=>row.bank_id===bank),'2026-04-01','2026-06-30');
  const creditas=quarter('creditas'), report=data.timeseries.find(row=>row.bank_id==='creditas' && row.period==='2026-Q2');
  assert.equal(creditas.calendarDays,91);assert.equal(creditas.archivedDays,91);
  for(const key of ['availability','aispResponse','pispResponse']) assert.ok(Math.abs(creditas.metrics[key].value-ui.metrics[key].value(report))<.0001,key);
  assert.equal(quarter('moneta').archivedDays,13);assert.equal(quarter('moneta').metrics.availability.value,null);
  const mbank=quarter('mbank');
  assert.equal(mbank.metrics.sharedError.count,91);assert.equal(mbank.metrics.aispError.value,null);assert.equal(mbank.metrics.pispError.value,null);
  const empty=ui.dailySummary(daily.filter(row=>row.bank_id==='ppf'),'2026-04-01','2026-06-30');
  assert.equal(empty.archivedDays,0);assert.ok(Object.values(empty.metrics).every(item=>item.value===null && item.missingDays===91));
});

test('archive date and bank handlers recalculate every summary card independently of the selected chart metric', () => {
  const fs=require('node:fs'), path=require('node:path'), vm=require('node:vm');
  class Element {
    constructor(tag='div') { this.tagName=tag;this.children=[];this.dataset={};this.listeners={};this.value='';this.classList={contains:()=>false,toggle(){}};this.parentElement={clientWidth:1080}; }
    append(...children) { children.forEach(child=>{child.parentElement=this;this.children.push(child);}); }
    add(child) { this.append(child);if(!this.value)this.value=child.value; }
    replaceChildren(...children) { this.children=[];this.append(...children); }
    setAttribute(key,value) { this[key]=String(value); }
    toggleAttribute(key,value) { this[key]=value; }
    querySelector() { return null; }
    closest(selector) { return selector==='[data-daily-metric]' && this.dataset.dailyMetric?this:null; }
    addEventListener(type,listener) { this.listeners[type]=listener; }
  }
  const elements=new Map(), element=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  const buttons=Object.values(ui.metrics).map(metric=>{const button=new Element('button');button.dataset.dailyMetric=metric.field;return button;});
  const document={body:new Element(),querySelector:selector=>element(selector.slice(1)),querySelectorAll:()=>buttons,createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag)};
  const history=[
    {bank_id:'creditas',bank:'Banka CREDITAS',date:'2026-06-01',availability_pct:100,aisp_response_ms:200,aisp_error_pct:0},
    {bank_id:'creditas',bank:'Banka CREDITAS',date:'2026-06-03',availability_pct:98,aisp_response_ms:400,aisp_error_pct:2},
    {bank_id:'moneta',bank:'MONETA',date:'2026-06-02',aisp_response_ms:100,aisp_error_pct:1},
    {bank_id:'mbank',bank:'mBank',date:'2026-06-01',availability_pct:99,country_code:'unverified'},
  ].map(row=>({...row,first_seen_on:'2026-09-18',last_seen_on:'2026-09-18',versions:1}));
  const window={PSD2_DATA:{},PSD2_DAILY_DATA:history,PSD2_UI:{...ui,initializeNavigation(){}},history:{replaceState(){}},addEventListener(){}};
  const location={search:'?bank=creditas&dayFrom=2026-06-01&dayTo=2026-06-03',href:'https://example.test/archive.html'};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../dashboard/archive.js'),'utf8'),{window,document,location,URL,URLSearchParams,Option:class extends Element{constructor(name,value){super('option');this.textContent=name;this.value=value;}}});
  const card=key=>element('dailySummaryCards').children.find(card=>card.dataset.summaryMetric===key);
  const value=key=>card(key).children[1].textContent;
  assert.equal(element('dailySummaryCards').children.length,8);
  assert.equal(value('availability'),'99 %');assert.equal(value('aispResponse'),'300 ms');assert.equal(value('aispError'),'1 %');
  assert.match(element('dailySummaryCoverage').textContent,/2 z 3 dnů/);
  element('archiveMetrics').listeners.click({target:buttons.find(button=>button.dataset.dailyMetric==='aisp_error_pct')});
  assert.equal(value('aispResponse'),'300 ms');
  element('archiveFrom').value='2026-06-03';element('archiveFrom').listeners.change();
  assert.equal(value('availability'),'98 %');assert.equal(value('aispResponse'),'400 ms');assert.match(card('availability').children[2].textContent,/1 z 1/);
  element('archiveFrom').value='2026-06-02';element('archiveTo').value='2026-06-02';element('archiveTo').listeners.change();
  assert.equal(value('availability'),'Údaj nedoložen');assert.equal(value('aispResponse'),'Údaj nedoložen');
  element('archiveBank').value='moneta';element('archiveBank').listeners.change();
  assert.equal(value('availability'),'Údaj nedoložen');assert.equal(value('aispResponse'),'100 ms');assert.equal(value('aispError'),'1 %');
  element('archiveBank').value='mbank';element('archiveBank').listeners.change();
  assert.match(element('dailySummaryMethod').textContent,/český rozsah nepotvrzen/);
  element('archiveFrom').value='2026-06-02';element('archiveTo').value='2026-06-02';element('archiveTo').listeners.change();
  assert.equal(value('availability'),'Údaj nedoložen');assert.match(element('dailySummaryMethod').textContent,/český rozsah nepotvrzen/);
});

test('bank chart event handlers show quarter dates and values, preserve resize and avoid stale selections', () => {
  // Minimal DOM fixture executes the real bank.js, not a copy of its handlers.
  const fs=require('node:fs'), path=require('node:path'), vm=require('node:vm');
  class Element {
    constructor(tag='div') { this.tagName=tag;this.children=[];this.dataset={};this.attributes={};this.listeners={};this.classList={toggle(){}};this.parentElement={clientWidth:1080}; }
    setAttribute(key,value) {
      this.attributes[key]=String(value);
      if(key==='class')this.className=value;
      if(key.startsWith('data-'))this.dataset[key.slice(5).replace(/-([a-z])/g,(_,letter)=>letter.toUpperCase())]=value;
    }
    append(...children) { children.forEach(child=>{child.parentElement=this;this.children.push(child);}); }
    add(child) { this.append(child); }
    replaceChildren(...children) { this.children=[];this.append(...children); }
    toggleAttribute(key,value) { if(key==='hidden')this.hidden=value; }
    remove() { this.parentElement.children=this.parentElement.children.filter(child=>child!==this); }
    matches(selector) {
      if(selector.startsWith('.'))return (this.className||'').split(' ').includes(selector.slice(1));
      const match=/^\[data-([\w-]+)\]$/.exec(selector);
      return Boolean(match && this.dataset[match[1].replace(/-([a-z])/g,(_,letter)=>letter.toUpperCase())]!==undefined);
    }
    closest(selector) { return this.matches(selector)?this:this.parentElement.closest?.(selector)||null; }
    querySelectorAll(selector) { return this.children.flatMap(child=>[...(child.matches(selector)?[child]:[]),...child.querySelectorAll(selector)]); }
    addEventListener(type,listener) { this.listeners[type]=listener; }
    focus() { this.focused=true; }
    getScreenCTM() { return {inverse:()=>({})}; }
    createSVGPoint() { return {x:0,y:0,matrixTransform(){return {x:this.x,y:this.y};}}; }
  }
  const elements=new Map(), element=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
  const document={getElementById:element,createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),querySelectorAll:selector=>selector==='#bankHistoryMetrics [data-metric]'?element('bankHistoryMetrics').children:[]};
  const bank={bank_id:'creditas',bank:'Banka CREDITAS',scope:'main',latest_period:'2024-Q4',availability_pct:98};
  const reports=[{period:'2024-Q1',availability_pct:100,aisp_response_ms:10},{period:'2024-Q3',availability_pct:99,aisp_response_ms:0},{period:'2024-Q4',availability_pct:98}].map(row=>({...bank,...row,report_url:'https://example.test/'+row.period}));
  const opened=[], resize={};
  const window={PSD2_DATA:{latest:[bank],timeseries:reports,checked_on:'2026-09-18',source_details:{}},PSD2_UI:{...ui,coverageContent(){},initializeNavigation(){},createCoverageDialog:()=> (_,row)=>opened.push(row.period),appendMetricButtons(container){Object.keys(ui.metrics).forEach(key=>{const button=new Element('button');button.setAttribute('data-metric',key);container.append(button);});}},history:{replaceState(){}},addEventListener:(type,listener)=>resize[type]=listener};
  const location={search:'?bank=creditas',href:'https://example.test/bank.html?bank=creditas'};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../dashboard/bank.js'),'utf8'),{window,document,location,URL,URLSearchParams,Option:class extends Element{}});
  const chart=element('bankChart'), details=element('bankHistoryPointDetails');
  const clickPeriod=period=>chart.listeners.click({target:chart.querySelectorAll('.bank-chart-point').find(dot=>dot.dataset.historyPeriod===period)});
  const key=key=>chart.listeners.keydown({key,target:chart,preventDefault(){}});
  const metric=metric=>element('bankHistoryMetrics').listeners.click({target:element('bankHistoryMetrics').children.find(button=>button.dataset.metric===metric)});
  assert.equal(details.hidden,true);
  clickPeriod('2024-Q4');
  assert.equal(details.hidden,false);
  assert.equal(element('bankHistoryPointPeriod').textContent,'4Q2024');
  assert.equal(element('bankHistoryPointRange').textContent,'1. 10. 2024 – 31. 12. 2024');
  assert.equal(element('bankHistoryPointValue').textContent,'98 %');
  element('bankHistoryPointReport').listeners.click();assert.deepEqual(opened,['2024-Q4']);
  resize.resize();assert.equal(details.hidden,false);assert.equal(element('bankHistoryPointPeriod').textContent,'4Q2024');
  assert.equal(chart.querySelectorAll('.bank-chart-selection').length,2);
  key('Home');assert.equal(element('bankHistoryPointPeriod').textContent,'1Q2024');
  metric('aispResponse');assert.equal(element('bankHistoryPointValue').textContent,'10 ms');
  key('ArrowRight');assert.equal(element('bankHistoryPointPeriod').textContent,'3Q2024');assert.equal(element('bankHistoryPointValue').textContent,'0 ms');
  key('Escape');assert.equal(details.hidden,true);
  metric('availability');clickPeriod('2024-Q4');metric('aispResponse');assert.equal(details.hidden,true);
  chart.listeners.click({target:chart,clientX:10,clientY:100});assert.equal(details.hidden,true);
  chart.listeners.click({target:chart,clientX:730,clientY:100});assert.equal(element('bankHistoryPointPeriod').textContent,'3Q2024');
  element('clearBankHistoryPoint').listeners.click();assert.equal(details.hidden,true);assert.equal(chart.querySelectorAll('.bank-chart-selection').length,0);
});
