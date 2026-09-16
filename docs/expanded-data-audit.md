# Rozšířený audit českých PSD2 dat · 16. září 2026

## Výsledek a změny oproti předchozímu datasetu

Rozsah zůstává přesně **15 bank z původního Excelu**, pouze české PSD2 rozhraní. Nové dohledávání zvýšilo počet bankovních čtvrtletí ze **144 na 173**: **25 dalších reportů Trinity Bank** a **4 reporty PPF banky**. Trvalý denní archiv nově obsahuje **15 507 bankovních dnů za 12 bank**, od 1. ledna 2019 do 15. září 2026. Počet dnů je součet záznamů všech bank, ne počet unikátních kalendářních dnů.

Všech **144 původních čtvrtletních záznamů bylo porovnáno po jednotlivých číselných polích: žádná hodnota dostupnosti, odezvy ani chybovosti se při tomto rozšíření nezměnila**. Ani původní sešit nebyl změněn. Jeho SHA-256 zůstává `23f24b536bf3af9947ddcc4f1e95d886337f2177226ba6951da8c2b44ed53683`.

Nové čtvrtletní záznamy jsou uvedeny jednotlivě v [seznamu přírůstků](expanded-data-changes.csv). Starší opravy před tímto rozšířením jsou nadále oddělené v [porovnání s původním Excelem](original-data-comparison.md) a [historických opravách](historical-data-corrections.csv).

Poslední stav má dvě další změny:

- **Partners Banka:** místo chybějícího údaje je dostupný průměr **99,986 %** z 30 zveřejněných denních PSD2 health-check hodnot, 17. 8.–15. 9. 2026. Jde o nový doplňkový zdroj, **ne o čtvrtletní RTS report**; není zařazen do čtvrtletní tabulky a ve stavu je označen jako částečná data. Odezva ani chybovost nebyly domyšleny.
- **Oberbank:** opraven veřejný proklik na skutečný produkční PDF report. Čísla zůstávají prázdná, protože report neodděluje ČR od dalších trhů Oberbank AG.

## Ověření všech 15 bank

| Banka | Čtvrtletí před → nyní | Denní záznamy | Výsledek rozšířeného dohledávání |
|---|---:|---:|---|
| Air Bank | 30 → 30 | 2 737 | [Oficiální archiv](https://www.airbank.cz/aplikace-tretich-stran/) od 2019-Q1 do 2026-Q2; nově vytěženy denní hodnoty. Report 2019-Q1 má v extrakci jen 89 dnů. Přesně opakovaný řádek 1. 1. 2024 je v denní databázi uložen jednou, čtvrtletní souhrn nebyl změněn. |
| Banka CREDITAS | 28 → 28 | 2 371 | [Oficiální statistiky](https://www.creditas.cz/povinne-uverejnovane-informace#statisticke-udaje-o-dostupnosti) od 2019-Q3 do 2026-Q2. Seznam při novém automatickém načtení vracel 403; ověřené PDF kopie jsou zachované. Denní extrakce zachovává prázdné sloupce a rozlišuje chybovost od poměru výpadků. |
| Česká spořitelna | 1 → 1 | 91 | [Český portál](https://developers.erstegroup.com/api-health-check/bank.csas/last-quarter) publikuje poslední uzavřené čtvrtletí a pohyblivé kratší intervaly. Nově archivovány jednotlivé dny 2026-Q2, odděleně AISP/PISP. Datumy veřejného JSON byly převedeny z UTC na český kalendářní den. Další čtvrtletní archiv nebyl doložen. |
| ČSOB | 22 → 22 | 2 005 | [Reporting](https://www.csob.cz/csob/otevrene-bankovnictvi-csob/pro-vyvojare/seznam-api/reporting) obsahuje souvislou řadu 2021-Q1–2026-Q2. Denní XLSX odezva a chybovost nově uloženy; chybovost z podílu × 100. Uptime není publikován. Starší české reporty nebyly novým hledáním doloženy. |
| Fio banka | 28 → 28 | 2 481 | [Archiv](https://developers.fio.cz/stats.html) 2019-Q3–2026-Q2. Nově denní PSD2 provoz, odezva a chybovost; první report začíná 15. 9. 2019. |
| J&T Banka | 14 → 14 | 1 247 | [Česká informační povinnost](https://www.jtbank.cz/informacni-povinnost) obsahuje nesouvislou historii od 2019-Q2. Nově denní hodnoty včetně společné chybovosti, podíl × 100. [Slovenský archiv](https://www.jtbanka.sk/povinne-informacie/psd2/) nebyl použit k zaplnění českých mezer. |
| Komerční banka | 8 → 8 | 730 | [Český archiv](https://www.kb.cz/cs/dostupnost-sluzeb-internetoveho-a-otevreneho-bankovnictvi-api) 2024-Q3–2026-Q2. Nově denní PSD2 provoz, odezva a chybovost. Starší české statistiky se nepodařilo doložit; živé stavové stránky nejsou historický čtvrtletní report. |
| mBank | 0 → 0 | 0 | [Reportovací stránka](https://developer.api.mbank.cz/reports) je dynamická. Veřejné `reportpage?locale=en` obsahuje 27 odkazů; kontrolované PDF za 2019, 2023, 2024 a 2026 mají polsko-anglický obsah a nevymezují české rozhraní. Česká verze `reportpage?locale=cs`, s režimem `INDIVIDUAL_CS` používaným portálem, vrací prázdný seznam. Tato data nejsou doloženými českými statistikami a nebyla importována. |
| MONETA Money Bank | 0 → 0 | 90 | [Oficiální 90denní přehled](https://www.moneta.cz/otevrene-bankovnictvi) 18. 6.–15. 9. 2026, odezva a chybovost. Dny již zachycené před rozšířením jsou uchované; nyní mají i explicitní českou provenienci. Žádný uptime ani čtvrtletní report nebyl domyšlen. |
| Oberbank | 0 → 0 | 0 | [Česká XS2A stránka](https://www.oberbank.cz/xs2a-interface) stále odkazuje na interní hostname. Stejná cesta na veřejné české doméně vrací [produkční report 2026-Q2](https://www.oberbank.cz/documents/20195/21703/obkglobal_xs2a_statistik.pdf/ed74f6e3-961a-a810-31ed-0df88ef05b56). Ten uvádí Oberbank AG a odezvu jednotlivých služeb napříč trhy, bez českého řezu. Odkaz opraven, čísla v českém datasetu záměrně nepřevzata. |
| Partners Banka | 0 → 0 | 30 | Nový oficiální zdroj [Jak běží Partners banka](https://jakbezi.partnersbanka.cz/) obsahuje samostatný denní graf PSD2 „API 30 d.“; nepřebíráme graf aplikace ani celkové dostupnosti banky. Původní [vývojářská dokumentace](https://psd2.partnersbanka.cz/) zůstává jako doplňková adresa. Denní health-check je oddělen od RTS čtvrtletí. |
| PPF banka | 9 → 13 | 1 155 | K [aktuálnímu seznamu](https://www.ppfbanka.cz/cs/dokumenty/1868-pristupy-tretich-stran) doplněn [oficiální archiv](https://www.ppfbanka.cz/cs/dokumenty/1868-pristupy-tretich-stran?category_id=1868&archive=archive): čtyři reporty 2023-Q1–Q4. Archiv navíc odkazuje na samostatný leden 2023, který patří do stejného 1Q, nikoli do dalšího čtvrtletí. Nejnovější report zůstává 2026-Q1. Uptime chybí, nulové dny zůstávají v denní historii. |
| Raiffeisenbank | 0 → 0 | 0 | Znovu prověřen [rozcestník](https://www.rb.cz/informacni-servis/dokumenty-ke-stazeni) i český [vývojářský portál](https://developers.rb.cz/store/). Veřejný český statistický report nebyl doložen. Rakouské a maďarské reporty skupiny nebyly importovány. Původní ruční hodnota z Excelu se bez ověřeného reportu nevrací do srovnání. |
| Trinity Bank | 3 → 28 | 2 479 | [Český archiv](https://www.trinitybank.cz/otevrene-bankovnictvi/) je stránkovaný. Po průchodu všemi odkazovanými stránkami nalezena řada 2019-Q3–2026-Q2. Importovány pouze API reporty, nikoli IB. Starší formát uvádí procenta bez znaku `%`; parser byl doplněn a ověřen oproti skutečnému PDF. První report obsahuje pouze 14.–30. 9. 2019. |
| UniCredit Bank | 1 → 1 | 91 | [Oficiální portál](https://developer.unicredit.eu/report?view=kpi): výhradně `CZ-B → Dedicated Interface`. Nově uloženo 91 denních záznamů 2026-Q2, s dostupností, odezvou a společnou chybovostí. Měsíční údaje a jejich původní čtvrtletní průměr se nezměnily. BusinessNet, Online/Smart Banking, UC eBanking ani `SK-B`/`IT` nejsou přimíchány. |

## Co zůstává neúplné

Dataset není úplným regulatorním registrem všech bank a poboček v ČR. Zahrnuje zadaných 15 bank; NRB zůstává jen samostatným kandidátem. Nové vyhledávání nedoložilo české statistiky mBank, Raiffeisenbank a oddělený český řez Oberbank. Čtvrtletní report Partners také není doložen — doplněný health-check jej nenahrazuje.

Některé zveřejněné reporty obsahují méně dnů, prázdné číselné buňky nebo dny bez volání. V [denním pokrytí zdrojů](daily-source-coverage.csv) je proto u každého čtvrtletí uveden počet kalendářních dnů, skutečně uložených dnů, rozsah a počet dnů s dostupností či odezvou. **Chybějící den ani prázdná buňka není nula ani automaticky výpadek.** Souhrn z publikovaných dnů nemusí znamenat úplně změřené čtvrtletí. U PPF a CREDITAS mohou být uložené dny řidší než počet řádků v PDF, protože řádky se všemi prázdnými metrikami se neukládají jako měření.

Denní čísla jsou dodatečná podrobnost, nikoli přepis čtvrtletního datasetu. Denní archiv zachovává publikované nuly; čtvrtletní odezvy nadále vynechávají nulové dny bez volání. Společná chybovost má v denním exportu vlastní sloupec `shared_error_pct`. Země je u všech denních řádků explicitně `CZ`; obsah zahraničních rozhraní se nepoužívá k vyplňování českých mezer.

## Automatické uchovávání

Týdenní sběr nově umí pokračovat přes stránkovaný archiv Trinity a samostatný archiv PPF. Z aktuálních reportů ukládá i jednotlivé dny; MONETA a Partners doplňují pohyblivé 90/30denní intervaly. SQLite uchovává původní verze i opravy a zdrojové dokumenty jsou uložené podle kontrolního součtu. Už zachycené hodnoty se neztratí, když banka staré údaje později stáhne. [Popis trvalého archivu](data-archive.md).

Před zveřejněním je provedena kontrola čísel proti původním 144 záznamům, integrity databáze a zdrojových kopií, testy parserů i prohlížečové kontroly řazení, časových posuvníků a mobilního rozložení.
