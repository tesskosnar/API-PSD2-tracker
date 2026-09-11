# Audit zdrojů PSD2 statistik

Ověřeno 11. září 2026 proti oficiálním webům bank. Hodnocení rozlišuje dostupnost **publikovaného reportu** od dostupnosti samotného PSD2 API.

| Banka | Výsledek ověření | Nejdůležitější zjištění |
|---|---|---|
| Česká spořitelna | správně | Stránka je JavaScriptový portál; pod ní je veřejné JSON API s denními hodnotami AISP/PISP. Tracker načítá konfiguraci a veřejný klíč přímo z portálu, takže není závislý na natvrdo uloženém klíči. |
| ČSOB | správně, ale jen částečná metrika | Reportingová adresa při jednom ověření vrátila HTTP 500, při opakovaném načtení ale zpřístupnila XLSX 2026-Q2. Soubor obsahuje odezvu a chybovost, nikoli dostupnost. |
| Komerční banka | správně | Na stránce je aktuální PDF 2026-Q2 a archiv starších čtvrtletí. |
| Raiffeisenbank | správně jako rozcestník | Dokumenty se načítají dynamicky. V dodaném sešitu je poslední podklad 2025-Q3 a chybí 2026-Q2, rok 2023 i rychlost. |
| Air Bank | správně | Stránka obsahuje aktuální PDF 2026-Q2 a archiv. |
| MONETA Money Bank | správně, ale jen částečná metrika | Stránka publikuje posledních 90 dní AISP/PISP/CISP odezvy a chybovosti, nikoli uptime. |
| Fio banka | správně | Stránka obsahuje aktuální PDF 2026-Q2 a souvislý archiv od roku 2019. |
| mBank | problém obsahu | Česká adresa existuje, ale při ověření byly na reportovací stránce polské hodnoty; nelze je bez dalšího považovat za česká data. |
| UniCredit Bank | správně | Portál má CZ Dedicated Interface; publikuje měsíční uptime, odezvu a společnou chybovost. Tracker z měsíců skládá čtvrtletí. |
| Banka CREDITAS | správně | Oficiální seznam obsahuje 2026-Q2. Přehled může blokovat automatické klienty, ale PDF mají předvídatelnou adresu. |
| Trinity Bank | správně | Stránka rozlišuje API a internetové bankovnictví; aktuální API report je 2026-Q2. |
| Partners Banka | report nenalezen | Vývojářský portál funguje, ale sekce se statistikami dostupnosti nebyla nalezena. |
| Oberbank | původní poznámka byla nepřesná | Veřejná XS2A stránka funguje. Odkaz „Zveřejnění statistiky XS2A“ ale směřuje na interní hostname `redaktionsproduktion-oberbank-at:12080`, takže je pro veřejnost chybně nastaven. |
| J&T Banka | správně | Webová aplikace obsahuje aktuální PSD2 PDF 2026-Q2 v datech stránky. |
| PPF banka | správně, ale zastarale/neúplně | Nejnovější nalezený report je 2026-Q1 a PDF neobsahuje uptime, pouze odezvu a chybovost. |
| Národní rozvojová banka | kandidát chyběl v sešitu | Oficiální stránka potvrzuje PSD2 API, ale statistický report nebyl dohledán. Před zařazením do hlavního srovnání je vhodné potvrdit, zda vede relevantní online platební účty a má povinnost publikovat srovnávané rozhraní. |

## Opravené nebo sporné body

1. Oberbank nemá nedostupný webový server; problém je konkrétní neplatný odkaz na statistiky.
2. U ČSOB nelze z chyby reportovací stránky vyvozovat nedostupnost PSD2 API.
3. U MONETA, PPF a podle dostupného obsahu i několika dalších bank se „report existuje“ nerovná „je publikována dostupnost“.
4. Původní rozsah není úplný regulatorní registr. NRB byla doplněna jako kandidát; další pobočky zahraničních bank je nutné filtrovat podle toho, zda jsou ASPSP s relevantním rozhraním, ne pouze podle bankovní licence.

## Oficiální adresy

Přesné adresy jsou udržované v [`config/banks.json`](../config/banks.json). Regulatorní požadavek je v [čl. 32(4) Delegovaného nařízení (EU) 2018/389](https://eur-lex.europa.eu/legal-content/CS/TXT/?uri=CELEX:32018R0389); výklad k denní srovnatelnosti uvádí [EBA Q&A 2023_6687](https://www.eba.europa.eu/single-rule-book-qa/qna/view/publicId/2023_6687).
