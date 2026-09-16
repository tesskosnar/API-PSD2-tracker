# Audit zdrojů PSD2 statistik

Původní seznam je ze sešitu dodaného k 9. září 2026. První audit proběhl 11. září; poslední sběr a kontrola historických reportů proběhly 16. září 2026. U sporných adres byly kontrolovány oficiální weby bank. Hodnocení rozlišuje dostupnost **publikovaného reportu** od dostupnosti samotného PSD2 API.

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

U ostatních bank se mezi sběry 13. a 14. září nezměnil odkaz na report ani poslední doložené čtvrtletí. Čtvrtletní dostupnost za 2026-Q2 lze stále doložit pro osm bank. Úplné pokrytí všech bank netvrdíme: prázdné místo znamená nedoloženou či metodicky neporovnatelnou hodnotu.

## Veřejné reporty dohledané zpětně

Kontrola 15. září 2026 prošla celé archivy na oficiálních stránkách, ne jen posledních osm čtvrtletí. Dataset nyní obsahuje 142 archivních PDF/XLSX a dvě aktuální období z veřejných online portálů, celkem 144 doložených bankovních období.

| Banka | Počet | Veřejný rozsah | Poznámka |
|---|---:|---|---|
| Air Bank | 30 | 2019-Q1–2026-Q2 | Souvislý archiv PDF. |
| Banka CREDITAS | 28 | 2019-Q3–2026-Q2 | Souvislý archiv PDF; 2023-Q2 má odlišně pojmenovaný soubor. |
| Fio banka | 28 | 2019-Q3–2026-Q2 | Souvislý archiv PDF. |
| ČSOB | 22 | 2021-Q1–2026-Q2 | Souvislý archiv XLSX, bez uptime. |
| J&T Banka | 14 | 2019-Q2–2026-Q2 | Veřejný archiv má mezi roky mezery; tracker je nedoplňuje odhadem. |
| PPF banka | 9 | 2024-Q1–2026-Q1 | Souvislý archiv PDF, bez uptime. |
| Komerční banka | 8 | 2024-Q3–2026-Q2 | Tolik dokumentů dnes uvádí oficiální stránka. |
| Trinity Bank | 3 | 2025-Q4–2026-Q2 | Tolik API reportů dnes uvádí oficiální stránka. |
| Česká spořitelna | 1 | 2026-Q2 | Veřejný portál poskytuje poslední čtvrtletí, ne archiv dokumentů. |
| UniCredit Bank | 1 | 2026-Q2 | Veřejný portál aktuálně vrací tři měsíce posledního čtvrtletí. |

Čtvrtletní report nebyl doložen pro Raiffeisenbank, mBank, Partners Banku a Oberbank. MONETA publikuje jen pohyblivé 90denní okno, proto se nevydává za čtvrtletní archiv. V dashboardu se nově zobrazí všech 15 bank; banka bez hodnoty pro vybranou metriku zůstane viditelná s prázdnými poli.

Podrobné porovnání hodnot s dodaným Excelem je v [`original-data-comparison.md`](original-data-comparison.md).

### Dodatečná kontrola zpracování 16. září

Všech 142 nalezených archivních PDF/XLSX bylo znovu načteno. U Air Bank, ČSOB a CREDITAS byly opraveny odlišné historické formáty tabulek. Přesný rozdíl proti předchozí verzi trackeru je v [`historical-data-corrections.csv`](historical-data-corrections.csv); důvody popisuje [porovnání dat](original-data-comparison.md#opravy-nově-rozšířené-historie-trackeru). Původní Excel se nezměnil.

Některé reporty CREDITAS obsahují prázdné dny i ve sloupci uptime. Takové čtvrtletí je označeno jako částečné a metodika uvádí počet doložených denních hodnot; prázdné dny se nedoplňují hodnotou 100 %. Například [2023-Q3](https://www.creditas.cz/files/statisticke-udaje-o-dostupnosti-a-vykonu-rozhrani-3q-2023.pdf) obsahuje uptime jen pro 76 z 92 dnů.

Čtvrtletní srovnání zobrazuje ve výchozím stavu posledních osm čtvrtletí. Volby 1 rok, 2 roky, celá historie a přesné čtvrtletí od–do mění pouze zobrazení, nikoli uložená data. Banky s reportem ve zvoleném období jsou nejdříve abecedně, banky bez reportu potom také abecedně. Přehled publikovaných reportů nadále ukazuje celý archiv a všechny banky čistě abecedně.

### UniCredit: kontrola českého prokliku 16. září

[Oficiální KPI portál](https://developer.unicredit.eu/report?view=kpi) se otevírá s výchozí zemí Itálie. Ověřovaný parametr `legalEntity=CZ-B` výchozí volbu nezměnil; tracker proto nevydává obecnou adresu za přímý český report. Odkaz v dashboardu nově otevírá český detail trackeru s měsíčními podklady a odkazem na oficiální portál. Tam je nutné zvolit **Legal Entity → UniCredit Bank Czech Republic** a **Product → Dedicated Interface**.

Ve zdrojových datech byla ověřena výhradně česká větev `CZ-B` (také větev `CZ` má shodné hodnoty), nikoli `SK-B` ani `IT`. Duben/květen/červen 2026 uvádějí uptime 100/100/100 %, AISP 329,75/367,37/338,75 ms, PISP 220,24/299,84/225,89 ms a společnou chybovost 0,07/0,20/0,20 %. Čtvrtletní průměry odpovídají stávajícím datům trackeru: 100 %, AISP 345,29 ms, PISP 248,6567 ms a společná chybovost 0,1567 %. Žádná z těchto číselných hodnot se touto úpravou nezměnila.

Automatické zpracování bylo přizpůsobeno i aktuálnímu formátu `JSON.parse(...)`. Měsíční české podklady se při dalších kontrolách ukládají spolu s dashboardem a historické detaily zůstávají zachované i po posunu posledního čtvrtletí.

## Trvalý archiv založený 16. září

Všech 144 již ověřených bankovních období bylo převedeno do trvalé databáze. Uloženy jsou i kopie všech 142 dostupných PDF/XLSX z předchozího sběru a původní obsah online zdrojů při nové kontrole. MONETA nově uchovává jednotlivých 90 dnů od 18. června do 15. září, nejen poslední pohyblivý průměr. Nové dny se při týdenních kontrolách doplňují, staré se neodstraňují a opravy mají vlastní verze. [Popis archivace](data-archive.md) uvádí uložení, obnovu, kontrolu integrity i limity.

Při této úpravě se nezměnila žádná stávající číselná hodnota posledního stavu ani čtvrtletních řad. U CREDITAS za 2026-Q2 se pouze upřesnil stav zdroje na `ok-direct-pdf`, protože sběr použil přímý oficiální PDF odkaz. Nové denní hodnoty MONETY jsou dodatečná podrobnost, nikoli změna jejích původních čtvrtletních dat; MONETA nadále není vykazována jako banka s čtvrtletním reportem.

## Opravené nebo sporné body

1. Oberbank nemá nedostupný webový server; problém je konkrétní neplatný odkaz na statistiky.
2. U ČSOB nelze z chyby reportovací stránky vyvozovat nedostupnost PSD2 API.
3. U MONETA, PPF a podle dostupného obsahu i několika dalších bank se „report existuje“ nerovná „je publikována dostupnost“.
4. Původní rozsah není úplný regulatorní registr. NRB byla doplněna jako kandidát; další pobočky zahraničních bank je nutné filtrovat podle toho, zda jsou ASPSP s relevantním rozhraním, ne pouze podle bankovní licence.

## Oficiální adresy

Přesné adresy jsou udržované v [`config/banks.json`](../config/banks.json). Regulatorní požadavek je v [čl. 32(4) Delegovaného nařízení (EU) 2018/389](https://eur-lex.europa.eu/legal-content/CS/TXT/?uri=CELEX:32018R0389); výklad k denní srovnatelnosti uvádí [EBA Q&A 2023_6687](https://www.eba.europa.eu/single-rule-book-qa/qna/view/publicId/2023_6687).
