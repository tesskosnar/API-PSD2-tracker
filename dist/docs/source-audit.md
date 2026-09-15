# Audit zdrojů PSD2 statistik

Původní seznam je ze sešitu dodaného k 9. září 2026. První audit proběhl 11. září; znovu ověřeno 14. září 2026 automatickým sběrem a u sporných adres kontrolou oficiálních webů bank. Hodnocení rozlišuje dostupnost **publikovaného reportu** od dostupnosti samotného PSD2 API.

| Banka | Výsledek ověření | Nejdůležitější zjištění |
|---|---|---|
| Česká spořitelna | správně | Stránka je JavaScriptový portál; pod ní je veřejné JSON API s denními hodnotami AISP/PISP. Tracker načítá konfiguraci a veřejný klíč přímo z portálu, takže není závislý na natvrdo uloženém klíči. |
| ČSOB | správně, ale jen částečná metrika | Reportingová adresa při jednom ověření vrátila HTTP 500, při opakovaném načtení ale zpřístupnila XLSX 2026-Q2. Soubor obsahuje odezvu a chybovost, nikoli dostupnost. Chybovost je v XLSX uložená jako podíl a na procenta se násobí 100. |
| Komerční banka | správně | Na stránce je aktuální PDF 2026-Q2 a archiv starších čtvrtletí. |
| Raiffeisenbank | rozcestník funguje, report nedoložen | Dokumenty se načítají dynamicky. Poznámka původního sešitu uvádí 2025-Q3, ale dodaný datový list, ze kterého pochází hodnota 100 %, pokrývá 2024-Q3. Bez ověřitelného veřejného reportu se ruční hodnota nezobrazuje ani jako poslední dostupnost. |
| Air Bank | správně | Stránka obsahuje aktuální PDF 2026-Q2 a archiv. |
| MONETA Money Bank | správně, ale jen částečná metrika | Stránka publikuje posledních 90 dní AISP/PISP/CISP odezvy a chybovosti, nikoli uptime. |
| Fio banka | správně | Stránka obsahuje aktuální PDF 2026-Q2 a souvislý archiv od roku 2019. |
| mBank | problém obsahu | Česká adresa existuje, ale při ověření byly na reportovací stránce polské hodnoty; nelze je bez dalšího považovat za česká data. |
| UniCredit Bank | správně | Portál má CZ Dedicated Interface; publikuje měsíční uptime, odezvu a společnou chybovost. Tracker z měsíců skládá čtvrtletí. |
| Banka CREDITAS | správně | Oficiální seznam obsahuje 2026-Q2. Přehled může blokovat automatické klienty, ale PDF mají předvídatelnou adresu. Sloupec „poměr výpadků“ není míra chybových API odpovědí; tracker jej proto nepřejmenovává na chybovost. |
| Trinity Bank | správně | Stránka rozlišuje API a internetové bankovnictví; aktuální API report je 2026-Q2. |
| Partners Banka | report nenalezen | Vývojářský portál funguje, ale sekce se statistikami dostupnosti nebyla nalezena. |
| Oberbank | původní poznámka byla nepřesná | Veřejná XS2A stránka funguje. Odkaz „Zveřejnění statistiky XS2A“ ale směřuje na interní hostname `redaktionsproduktion-oberbank-at:12080`, takže je pro veřejnost chybně nastaven. |
| J&T Banka | správně | Webová aplikace obsahuje aktuální PSD2 PDF 2026-Q2 v datech stránky. „Error response rate“ je společná pro služby, nikoli samostatně AISP a PISP; v PDF je zapsaná jako podíl. |
| PPF banka | správně, ale zastarale/neúplně | Nejnovější nalezený report je 2026-Q1 a PDF neobsahuje uptime, pouze odezvu a chybovost. Většina dnů má 0 volání a 0 % chyb; průměr chybovosti dává smysl jen pro dny se skutečnými voláními. |
| Národní rozvojová banka | kandidát chyběl v sešitu | Oficiální stránka potvrzuje PSD2 API, ale statistický report nebyl dohledán. Před zařazením do hlavního srovnání je vhodné potvrdit, zda vede relevantní online platební účty a má povinnost publikovat srovnávané rozhraní. |

## Co se změnilo proti minulé kontrole

Všech 15 původních bankovních stránek zůstává v trackeru na stejné adrese. U Komerční banky byl odstraněn pouze kotvicí fragment a u PPF banky nadbytečný dotazový řetězec; obě adresy vedou na stejnou stránku. Národní rozvojová banka je nadále jen oddělený kandidát mimo původní seznam.

| Zdroj | Původní sešit / audit 11. 9. | Kontrola 14. 9. | Dopad na tracker |
|---|---|---|---|
| [Raiffeisenbank](https://www.rb.cz/informacni-servis/dokumenty-ke-stazeni) | Sešit uváděl jako poslední 2025-Q3; první audit tuto poznámku převzal. | Podklad pro ručně vložených 100 % ve skutečnosti obsahuje 2024-Q3; ověřitelný veřejný report nedoložen. | Ruční hodnota byla odstraněna z aktuálního stavu i časové řady, aby nepůsobila jako publikovaná statistika banky. |
| [Oberbank](https://www.oberbank.cz/xs2a-interface) | Sešit označoval server za nedostupný; 11. 9. jsme zjistili, že funguje stránka, ale ne odkaz na statistiku. | Stránka je stále dostupná, odkaz „Ke statistice“ stále míří na interní hostname. | Bez číselné hodnoty; nejde o důkaz výpadku PSD2 API. |
| [ČSOB](https://www.csob.cz/csob/otevrene-bankovnictvi-csob/pro-vyvojare/seznam-api/reporting) | Stránka byla občas nestabilní; soubor XLSX obsahoval výkon, nikoli uptime. | Stránka znovu občas vrací HTTP 500, přímý oficiální [XLSX za 2026-Q2](https://www.csob.cz/documents/10710/21871290/psd2-q2-2026.xlsx) se načetl. Původní sešit počítal míru chyb jako `průměr × 100`, tracker ji dosud zobrazoval bez převodu. | Stav „částečná data“ beze změny; chybovost opravena z podílu na procenta. |
| [PPF banka](https://www.ppfbanka.cz/cs/dokumenty/1868-pristupy-tretich-stran) | Nejnovější report 2026-Q1, bez hodnoty uptime. Původní sešit uváděl pro AISP 100 %. | Ve veřejném seznamu je nadále nejnovější 2026-Q1; 2026-Q2 chybí. [PDF](https://www.ppfbanka.cz/cs/document/download/8437) obsahuje pět březnových dnů s AISP voláními, každý se 100 % chyb; ostatní dny mají 0 volání. | Stav „zastaralé“ beze změny; průměr AISP chyb jen z aktivních dnů je 100 %, ne 5,56 %. PISP chybovost bez provozu zůstává prázdná. |
| [mBank](https://developer.api.mbank.cz/reports) | Česká adresa v sešitu ukazovala na reporty s polskými hodnotami. | Nepodařilo se doložit český čtvrtletní report. | Polské hodnoty se nepřebírají. |
| [MONETA Money Bank](https://www.moneta.cz/otevrene-bankovnictvi) | Pouze klouzavých 90 dní odezvy a chybovosti, bez uptime. | Zdroj i metodika stejné; okno se posunulo z 12. na 13. září. | Aktualizovaly se jen klouzavé hodnoty, nevznikl nový čtvrtletní bod. |
| [Air Bank](https://www.airbank.cz/aplikace-tretich-stran/) | Původní sešit měl chybovost zapsanou jako desetinný podíl (např. 0,000066). | [PDF 2026-Q2](https://www.airbank.cz/file-download/statistiky-dostupnosti-2q-2026) přímo značí denní chybovost znakem `%`. | Tracker správně uchovává procentní hodnoty; číselný rozdíl vůči sešitu je rozdíl jednotek, nikoli nová data. |
| [J&T Banka](https://www.jtbank.cz/informacni-povinnost) | Původní sešit násobil denní „Error response rate“ stem. | [PDF 2026-Q2](https://assets-eu-01.kc-usercontent.com/23883f12-8a12-01af-3f05-426faedce691/69bbf441-3b3b-4519-998b-10ec11b07591/Q2-2026_psd2_unavailability.pdf) uvádí míru chyb společně pro všechny služby bez znaku `%`. | Tracker opravuje převod podílu na procenta a v tabulce hodnotu označuje jako společnou; graf AISP ji nemíchá se samostatnými AISP mírami. |
| [Banka CREDITAS](https://www.creditas.cz/files/statisticke-udaje-o-dostupnosti-a-vykonu-rozhrani-2q-2026.pdf) | Původní sešit sloupec „poměr výpadků“ uváděl v souhrnu jako chybovost. | PDF jej označuje jako poměr výpadků, ne jako podíl chybných API odpovědí. | Chybovost zůstává v trackeru prázdná; odlišné metriky se nemíchají. |

U ostatních bank se mezi sběry 13. a 14. září nezměnil odkaz na report ani poslední doložené čtvrtletí. Čtvrtletní dostupnost za 2026-Q2 lze stále doložit pro osm bank (u CREDITAS se automatické čtení někdy zablokuje, poslední ověřený report se zachová s varováním). Po odstranění čtyř období PPF s nulovým provozem a bez měřitelné odezvy či chybovosti obsahuje historická řada 55 bankovních čtvrtletí s použitelným údajem a odkazem na zdroj. Úplné pokrytí všech bank netvrdíme: prázdné místo znamená nedoloženou či metodicky neporovnatelnou hodnotu.

## Opravené nebo sporné body

1. Oberbank nemá nedostupný webový server; problém je konkrétní neplatný odkaz na statistiky.
2. U ČSOB nelze z chyby reportovací stránky vyvozovat nedostupnost PSD2 API.
3. U MONETA, PPF a podle dostupného obsahu i několika dalších bank se „report existuje“ nerovná „je publikována dostupnost“.
4. Původní rozsah není úplný regulatorní registr. NRB byla doplněna jako kandidát; další pobočky zahraničních bank je nutné filtrovat podle toho, zda jsou ASPSP s relevantním rozhraním, ne pouze podle bankovní licence.

## Oficiální adresy

Přesné adresy jsou udržované v [`config/banks.json`](../config/banks.json). Regulatorní požadavek je v [čl. 32(4) Delegovaného nařízení (EU) 2018/389](https://eur-lex.europa.eu/legal-content/CS/TXT/?uri=CELEX:32018R0389); výklad k denní srovnatelnosti uvádí [EBA Q&A 2023_6687](https://www.eba.europa.eu/single-rule-book-qa/qna/view/publicId/2023_6687).
