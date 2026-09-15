# API PSD2 tracker

Automatický přehled zveřejňované dostupnosti a výkonu PSD2 rozhraní českých bank. Tracker sleduje **to, co banky samy publikují** podle čl. 32 odst. 4 regulatorních technických standardů PSD2. Neměří živé produkční API vlastním voláním, protože to by bez TPP certifikátu a korektního testovacího scénáře dávalo zavádějící výsledky.

Kontrola běží každé úterý pomocí GitHub Actions a také ručně přes `Actions → Aktualizace PSD2 trackeru → Run workflow`. Banky publikují povinné statistiky čtvrtletně, ale ne ve stejný den; týdenní kontrola zachytí nový report rychle a přitom jejich weby nezatěžuje.

## Vývoj v čase

![Čtvrtletní vývoj dostupnosti PSD2 API podle zveřejněných reportů bank](docs/trend.svg)

Graf se při týdenní aktualizaci obnovuje automaticky. Zobrazuje jen banky s doloženými reporty; chybějící čtvrtletí nepřemosťuje. Podrobnější interaktivní přehled, přepínání metrik, pokrytí zdroji a odkazy na jednotlivé reporty je připravený pro GitHub Pages na adrese `https://tesskosnar.github.io/API-PSD2-tracker/`.

GitHub Pages je nutné jednou povolit v `Settings → Pages → Source: GitHub Actions`. Publikace se potom obnoví po každém úspěšném běhu týdenního trackeru a lze ji spustit také ručně v `Actions → Publikace dashboardu na GitHub Pages`.

> **Soukromí:** GitHub Pages je veřejně dostupný web i tehdy, když zdrojový repozitář zůstane soukromý. Zapnutí Pages proto znamená zveřejnění dashboardu a dat, která zobrazuje.

<!-- TRACKER:START -->
Očekávané poslední zveřejněné období: **2026-Q2** (po 45denní lhůtě na publikaci).

Souhrn hlavního seznamu: **7 s aktuální dostupností**, **2 s částečnými daty**, **1 zastaralé**, **4 bez nalezeného reportu**, **1 blokováno**.

| Banka | Stav | Poslední období | Dostupnost | Odezva AISP / PISP | Zdroj |
|---|---|---:|---:|---:|---|
| Česká spořitelna | OK | 2026-Q2 | AISP 99.5523 % / PISP 99.2837 % | — / — | [stránka](https://developers.erstegroup.com/api-health-check/bank.csas/last-quarter) |
| ČSOB | Částečná data | 2026-Q2 | — | 879.2395 ms / 612.5572 ms | [stránka](https://www.csob.cz/csob/otevrene-bankovnictvi-csob/pro-vyvojare/seznam-api/reporting) · [report](https://www.csob.cz/documents/10710/21871290/psd2-q2-2026.xlsx) |
| Komerční banka | OK | 2026-Q2 | 97.1856 % | 378.5604 ms / 408.4945 ms | [stránka](https://www.kb.cz/cs/dostupnost-sluzeb-internetoveho-a-otevreneho-bankovnictvi-api) · [report](https://www.kb.cz/getmedia/956647de-9725-4cf0-9975-52c1e3462491/kb-psd2-2026-q2-cz.pdf) |
| Raiffeisenbank | Nenalezen report | — | — | — / — | [stránka](https://www.rb.cz/informacni-servis/dokumenty-ke-stazeni) |
| Air Bank | OK | 2026-Q2 | 98.9736 % | 62.8242 ms / 72.7143 ms | [stránka](https://www.airbank.cz/aplikace-tretich-stran/) · [report](https://www.airbank.cz/file-download/statistiky-dostupnosti-2q-2026) |
| MONETA Money Bank | Částečná data | rolling-90d-to-2026-09-14 | — | 498.7889 ms / 149.6556 ms | [stránka](https://www.moneta.cz/otevrene-bankovnictvi) |
| Fio banka | OK | 2026-Q2 | 99.9809 % | 22.7143 ms / 16 ms | [stránka](https://developers.fio.cz/stats.html) · [report](https://developers.fio.cz/stats/PSD2_2026Q2.pdf) |
| mBank | Nenalezen report | — | — | — / — | [stránka](https://developer.api.mbank.cz/reports) |
| UniCredit Bank | OK | 2026-Q2 | 100 % | 345.29 ms / 248.6567 ms | [stránka](https://developer.unicredit.eu/report?view=kpi) |
| Banka CREDITAS | Zdroj blokuje automatizaci | 2026-Q2 | 99.956 % | 1819.5176 ms / 936.4353 ms | [stránka](https://www.creditas.cz/povinne-uverejnovane-informace#statisticke-udaje-o-dostupnosti) · [report](https://www.creditas.cz/files/statisticke-udaje-o-dostupnosti-a-vykonu-rozhrani-2q-2026.pdf) |
| Trinity Bank | OK | 2026-Q2 | 99.9951 % | — / — | [stránka](https://www.trinitybank.cz/otevrene-bankovnictvi/) · [report](https://www.trinitybank.cz/download/3036) |
| Partners Banka | Nenalezen report | — | — | — / — | [stránka](https://psd2.partnersbanka.cz/) |
| Oberbank | Nenalezen report | — | — | — / — | [stránka](https://www.oberbank.cz/xs2a-interface) |
| J&T Banka | OK | 2026-Q2 | 99.7801 % | 387.1698 ms / 1482 ms | [stránka](https://www.jtbank.cz/informacni-povinnost) · [report](https://assets-eu-01.kc-usercontent.com:443/23883f12-8a12-01af-3f05-426faedce691/69bbf441-3b3b-4519-998b-10ec11b07591/Q2-2026_psd2_unavailability.pdf) |
| PPF banka | Zastaralé | 2026-Q1 | — | 1833.6 ms / — | [stránka](https://www.ppfbanka.cz/cs/dokumenty/1868-pristupy-tretich-stran) · [report](https://www.ppfbanka.cz/cs/document/download/8437) |

### Kandidáti na rozšíření rozsahu

| Instituce | Stav | Proč je zde | Zdroj |
|---|---|---|---|
| Národní rozvojová banka | Nenalezen report | Doplněný kandidát mimo původní sešit: oficiální PSD2 API stránka existuje, statistiky nebyly nalezeny. | [stránka](https://www.nrb.cz/webklient/api-rozhrani-informace-pro-treti-strany/) |
<!-- TRACKER:END -->

## Co znamená stav

- **OK**: pro očekávané čtvrtletí byla automaticky načtena hodnota dostupnosti.
- **Částečná data**: banka zveřejnila report nebo výkonnostní metriky, ale chybí uptime nebo zatím není podporován její formát.
- **Zastaralé**: poslední nalezený report je starší než očekávané čtvrtletí.
- **Nenalezen report**: oficiální PSD2 stránka existuje, ale tracker na ní nenašel statistiky.
- **Zdroj blokuje automatizaci**: stránka vrátila chybu, blokaci nebo se změnil její formát. To samo o sobě **neznamená výpadek bankovního API**.

Hodnoty nejsou mezi bankami vždy metodicky totožné. Některá banka publikuje jednu dostupnost vyhrazeného rozhraní, jiná odděleně AISP a PISP a další pouze odezvu a chybovost. Sloupec `metric_method` v datech proto vždy uvádí způsob výpočtu.
Pokud banka zveřejňuje AISP a PISP dostupnost odděleně, křivka v přehledovém grafu používá jejich prostý průměr jen pro vizualizaci; obě původní hodnoty zůstávají v datech. Nulové denní odezvy se do průměru nezapočítávají, protože typicky znamenají den bez volání, nikoli okamžitou odpověď API.

## Výstupy

- `data/latest.csv` a `data/latest.json` — poslední stav všech bank.
- `data/history.csv` — nový záznam se přidá pouze při věcné změně hodnot nebo stavu.
- `data/timeseries.csv` a `data/timeseries.json` — doložené reporty za posledních osm čtvrtletí.
- `docs/trend.svg` — automaticky obnovovaný graf pro hlavní stránku GitHubu.
- `dashboard/index.html` — interaktivní přehled publikovaný přes GitHub Pages.
- `docs/source-audit.md` — audit adres z původního sešitu a nalezené mezery v rozsahu.
- `config/banks.json` — zdroje, parser a poznámky pro jednotlivé banky.

## Místní spuštění

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
psd2-tracker
python -m unittest discover -s tests -v
```

## Regulatorní základ

[Článek 32(4) Delegovaného nařízení Komise (EU) 2018/389](https://eur-lex.europa.eu/legal-content/CS/TXT/?uri=CELEX:32018R0389) požaduje, aby poskytovatelé platebních účtů zveřejňovali čtvrtletní statistiky dostupnosti a výkonu vyhrazeného rozhraní a rozhraní používaného jejich uživateli. [EBA Q&A 2023_6687](https://www.eba.europa.eu/single-rule-book-qa/qna/view/publicId/2023_6687) dále vysvětluje srovnatelnost těchto statistik.

## Omezení rozsahu

Hlavní seznam vychází z dodaného sešitu a není prohlašován za úplný registr všech ASPSP v Česku. Kandidáty doplněné při auditu tracker ukazuje odděleně. Pro úplnou regulatorní inventuru je třeba pravidelně porovnat rozsah s [otevřenými daty seznamu regulovaných subjektů ČNB](https://www.cnb.cz/cs/dohled-financni-trh/seznamy/Otevrena-data/).
