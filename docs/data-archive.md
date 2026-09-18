# Trvalý datový archiv

Archiv se doplňuje při každé automatické týdenní kontrole. To, co již jednou uložíme, zůstává zachované i poté, co banka změní stránku, posune 90denní okno nebo odstraní původní report. Ukládají se pouze veřejné statistiky bank, nikoli klientské účty nebo přihlašovací údaje.

## Co uchováváme

- `data/archive/tracker.sqlite3`: trvalá databáze čtvrtletních hodnot, výsledků kontrol, jednotlivých denních hodnot, verzí a evidence zdrojových souborů.
- `data/archive/objects/`: původní stažené HTML/JSON/PDF/XLSX, komprimované a pojmenované podle kontrolního součtu SHA-256. Stejný obsah se ukládá pouze jednou.
- `data/archive/summary.json`: přehled velikosti a rozsahu archivu.
- `data/daily-history.csv` a `data/daily-history.json`: přenosný přehled uložených denních údajů; pro každý den je zde poslední zachycená verze. Starší verze jsou nadále v databázi a původních zdrojích.
- `data/timeseries.csv` a `data/timeseries.json`: ověřené čtvrtletní řady používané v hlavním dashboardu.

Databáze a zdrojové kopie se ukládají přímo do GitHub repozitáře společně s aktualizací. Nespoléháme na dočasný disk běhu GitHub Actions, jeho cache ani expirovatelné přílohy. Gitová historie zároveň dovoluje obnovit předchozí uložený stav. Bez výslovného pokynu se archiv nemaže ani nekrátí podle stáří.

## Pohyblivé přehledy a opravy

MONETA publikuje pohyblivé 90denní okno odezvy a chybovosti; Partners zveřejňuje 30denní PSD2 health-check, který není vydáván za čtvrtletní RTS report. Tracker ukládá každý publikovaný den samostatně. Týdenní kontroly se překrývají: novější dny se přidají, dny starší než aktuální okno zůstávají v databázi. Nuly se v původních denních datech zachovávají; v průměru odezvy se nadále vynechávají podle stávající metodiky.

Když banka tentýž den zpětně opraví, vznikne další číselná verze. Zaznamenáváme první uložení i poslední ověření a počet zachycených verzí. Nedostupný zdroj ani prázdný nový report nemůže vymazat již uložené denní hodnoty nebo přepsat ověřené čtvrtletní číslo prázdným údajem. Při poškození či ztrátě posledního exportu může další sběr použít databázový archiv jako podklad pro obnovu.

[Denní archiv v dashboardu](https://tesskosnar.github.io/API-PSD2-tracker/archive.html) obsahuje graf, výběr banky, metriky a dat od–do, jednotlivé uložené dny a stažení CSV. Čtvrtletní reporty a jejich časový vývoj zůstávají odděleně v hlavním dashboardu. SQLite databáze a úplné zdrojové kopie se do GitHub Pages nekopírují; jsou v repozitáři. Viditelnost repozitáře určuje přístup k nim. Dashboard a denní CSV na GitHub Pages jsou veřejné.

## Začátek archivu a limity

### Souhrn libovolného vybraného období

Detail banky i samostatný denní archiv po změně banky nebo dat od–do přepočítávají všechny metriky pro zvolené dny, nezávisle na metrice grafu. Jde o výpočet trackeru z posledních uložených denních verzí, nikoli dodatečně publikovaný report banky. Datumové meze jsou včetně prvního a posledního dne; každý den se započítá nejvýše jednou. Souhrn ukazuje počet archivovaných dnů proti kalendářním dnům výběru a u každé metriky vlastní počet dnů ve výpočtu.

Dostupnost a chybovost jsou nevážené průměry publikovaných denních procent, včetně skutečných nul. Odezvy jsou průměry denních hodnot větších než 0 ms; počet vynechaných nul je zobrazen. Prázdné nebo chybějící údaje se nedoplňují, a průměr chybovosti bez počtů volání není celkový podíl chybných volání. Samostatné metriky AISP a PISP i společná chybovost zůstávají rozlišené. Pokud banka nepublikuje souhrnnou dostupnost, lze ji orientačně odvodit jako denní průměr AISP/PISP pouze ve dnech s oběma údaji; tyto dny jsou viditelně označené. Z jediného dostupného typu služby se souhrnná dostupnost neodvozuje. mBank zachovává poznámku o neověřeném samostatném českém rozsahu, Partners označení doplňkového health-checku. Výpočet nemění zdrojové hodnoty ani čtvrtletní historii.

### Čtvrtletní výpočty MONETY

Každý týdenní sběr nově přepočítává uzavřená čtvrtletí MONETY z posledních verzí zachycených českých dnů. Výpočet má `report_kind=archive-derived` a vlastní databázový typ `quarterly-derived`; není vydáván za report banky a nikdy jej nenahradí. Denní odezva se průměruje nad 0 ms, chybovost je nevážený průměr publikovaných denních procent včetně skutečných nul. Bez počtů volání ji nelze vydávat za podíl všech chybných volání. Dostupnost ze zdroje odvodit nelze.

První souhrn 2Q2026 pokrývá pouze **13/91 dnů (18.–30. 6. 2026)** a je viditelně částečný. Chybějící dny se nedoplňují. Budoucí souhrny budou používat i dny, které již zmizely z 90denního okna; po opravě denního údaje se přepočítají. [Nová kontrola všech 15 zdrojů](source-recheck-2026-09-16.md) rozlišuje česká čísla, vypočtené souhrny a existující reporty mBank/Oberbank s neověřeným českým rozsahem.

### Vývoj uchovávané historie

Po další kontrole je uchováno **194 původních čtvrtletních záznamů, 1 označený výpočet MONETY a 17 319 denních záznamů za 13 bank**. Zdrojových objektů je 306, včetně 28 mBank PDF. Reporty s neověřeným českým rozsahem se uchovávají jako doklady, nikoli importují jako české denní statistiky. Následující počty popisují předchozí etapy založení archivu.

Trvalý archiv byl založen **16. září 2026**. Bylo do něj převedeno všech 144 již ověřených bankovních období. Uchovaly se rovněž všechny dostupné kopie 142 PDF/XLSX z předchozího sběru. První denní sběr MONETY zachytil 90 dnů do 15. září 2026. Datum bankovního údaje není datum jeho uložení: starší report importovaný dnes je poctivě označen jako uložený dnes.

Po rozšířeném auditu téhož dne archiv obsahuje **173 čtvrtletních záznamů a 15 507 bankovních dnů za 12 bank**. Denní tabulka vedle MONETY a Partners zahrnuje i vytěžené české PDF/XLSX a online zdroje Air Bank, CREDITAS, České spořitelny, ČSOB, Fio, J&T, KB, PPF, Trinity a UniCredit. U UniCredit jsou odděleně zachované také české měsíční podklady. V denním CSV má společná chybovost vlastní sloupec; u všech denních záznamů je země `CZ`. Počet a rozsah dnů po čtvrtletích uvádí [kontrola denního pokrytí](daily-source-coverage.csv); ne všechny reporty mají vyplněný každý den.

Data odstraněná ještě před prvním zachycením zpětně obnovit neumíme. Delší přerušení sběru než publikační okno může způsobit mezeru; tracker chybějící dny nedoplňuje odhadem. Týdenní interval poskytuje vůči 30/90denním oknům rezervu, není ale zárukou nepřetržitého běhu GitHubu ani dostupnosti bankovních zdrojů. Velká denní historie se načítá pouze na stránce denního archivu; hlavní dashboard zůstává malý a rychlý.

## Kontrola integrity

Každý automatický běh před uložením ověřuje integritu SQLite, vazby mezi záznamy, existenci zdrojových kopií a jejich SHA-256. Chybějící nebo změněná kopie způsobí selhání kontroly, nikoli tiché přijetí poškozeného archivu. Kontrolu lze spustit i místně:

```bash
python -m psd2_tracker.archive --data-dir data
```
