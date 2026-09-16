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

MONETA aktuálně publikuje pohyblivé 90denní okno. Tracker nyní ukládá každý publikovaný den odezvy a chybovosti samostatně, nejen průměr posledních 90 dnů. Týdenní kontroly se překrývají: novější dny se přidají, dny starší než aktuální okno zůstávají v databázi. Nuly se v původních denních datech zachovávají; v průměru odezvy se nadále vynechávají podle stávající metodiky.

Když banka tentýž den zpětně opraví, vznikne další číselná verze. Zaznamenáváme první uložení i poslední ověření a počet zachycených verzí. Nedostupný zdroj ani prázdný nový report nemůže vymazat již uložené denní hodnoty nebo přepsat ověřené čtvrtletní číslo prázdným údajem. Při poškození či ztrátě posledního exportu může další sběr použít databázový archiv jako podklad pro obnovu.

[Denní archiv v dashboardu](https://tesskosnar.github.io/API-PSD2-tracker/archive.html) obsahuje graf, výběr banky, metriky a dat od–do, jednotlivé uložené dny a stažení CSV. Čtvrtletní reporty a jejich časový vývoj zůstávají odděleně v hlavním dashboardu. SQLite databáze a úplné zdrojové kopie se do GitHub Pages nekopírují; jsou v repozitáři. Viditelnost repozitáře určuje přístup k nim. Dashboard a denní CSV na GitHub Pages jsou veřejné.

## Začátek archivu a limity

Trvalý archiv byl založen **16. září 2026**. Bylo do něj převedeno všech 144 již ověřených bankovních období. Uchovaly se rovněž všechny dostupné kopie 142 PDF/XLSX z předchozího sběru. První denní sběr MONETY zachytil 90 dnů do 15. září 2026. Datum bankovního údaje není datum jeho uložení: starší report importovaný dnes je poctivě označen jako uložený dnes.

U ostatních online portálů se ukládá celý dostupný zdroj a čtvrtletní hodnoty; u UniCredit také ověřené české měsíční podklady. Denní tabulka zatím zahrnuje MONETU. Data odstraněná ještě před prvním zachycením zpětně obnovit neumíme. Delší přerušení sběru než publikační okno může způsobit mezeru; tracker chybějící dny nedoplňuje odhadem. Týdenní interval poskytuje vůči 90dennímu oknu velkou rezervu, není ale zárukou nepřetržitého běhu GitHubu ani dostupnosti bankovních zdrojů.

## Kontrola integrity

Každý automatický běh před uložením ověřuje integritu SQLite, vazby mezi záznamy, existenci zdrojových kopií a jejich SHA-256. Chybějící nebo změněná kopie způsobí selhání kontroly, nikoli tiché přijetí poškozeného archivu. Kontrolu lze spustit i místně:

```bash
python -m psd2_tracker.archive --data-dir data
```
