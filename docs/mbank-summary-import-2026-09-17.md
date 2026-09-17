# mBank: zahrnutí souhrnných reportů — 17. 9. 2026

Změna provedená na výslovnou žádost zahrnout nalezené reporty do statistik a webového dashboardu. Původní dokumenty ani původní Excel nebyly upraveny.

## Výsledek

- 28 různých uchovaných oficiálních PDF; celkem 118 stran.
- 29 čtvrtletních souhrnů od 2Q2019 do 2Q2026; první dokument pokrývá 14. 6.–30. 9. 2019 a jeho denní řádky jsou rozděleny podle skutečných datumů.
- 2 574 denních řádků, souvisle od 14. 6. 2019 do 30. 6. 2026. Částečné první čtvrtletí obsahuje pouze 17 z 91 dnů, nikoli odhad celého čtvrtletí.
- Celý dataset: 224 bankovních čtvrtletních záznamů a 19 893 denních řádků.
- Číselné hodnoty čtvrtletních i denních řad ostatních bank jsou vůči předchozí verzi shodné; jejich nejnovější metriky a zdroje nebyly přepsány.

## Rozsah a zdroje

Zdrojový [katalog mBank](https://developer.api.mbank.cz/reports) má dohromady 28 PDF v EN/PL variantách; jazyk portálu není důkaz země metrik. [FAQ](https://developer.api.mbank.cz/faq) uvádí společné API pro Česko a Slovensko s rozdílným `bankID` v cestě. [Oficiální dokumentace](https://developer.api.mbank.cz/documentation/api-v3#operation/initiateAuthorization) rozlišuje `cz-retail`, `sk-retail` a `pl-retail` (a `pl-corpo`). České API rovněž používá doménu `.pl`, takže samotná doména není důkaz polského rozsahu.

Ve všech 118 stranách uchovaných PDF chybí `bankID` i identifikátory české, slovenské nebo polské země. Souhrnné statistiky jsou proto zahrnuty s `country_scope="unverified"`, `report_kind="summary"` a denní `country_code="unverified"`. Nejsou vydávány za ověřený samostatný český výřez ani označeny bez důkazu jako výhradně polské. V dashboardu jsou odlišené symbolem † a poznámkou „Souhrnný report · samostatný český rozsah nepotvrzen“; totéž vysvětlení je v metodice exportů a detailu banky.

## Metriky a agregace

Z tabulek se používá pouze uptime pro mBank API, odezva AIS, odezva PIS a společná API error rate. Hodnoty internetového/mobilního bankovnictví, CAF a jejich výpadky se do PSD2 metrik nepřevádějí.

- Dostupnost: nevážený aritmetický průměr zveřejněných denních uptime v příslušném čtvrtletí.
- Odezvy AIS/PIS: průměr publikovaných denních hodnot větších než 0 ms, bez doplňování prázdných dnů.
- Společná chybovost API: nevážený průměr denních procent, nikoli podíl všech chybných volání; objemy volání nejsou k takovému přepočtu doloženy.
- Samostatná dostupnost AISP/PISP a samostatná chybovost AISP/PISP zůstávají prázdné. Společná chybovost není do dvou služeb zkopírována.
- Čtvrtletní agregace je ukládána se čtyřmi desetinnými místy; denní čísla odpovídají publikovaným buňkám.

Za 2Q2026: dostupnost 99,9929 %, odezva AIS 392,6154 ms, odezva PIS 327,9451 ms, společná chybovost API 0,0604 %, 91/91 archivovaných dnů. [Původní PDF za 2Q2026](https://dpprodassetstorage.blob.core.windows.net/prod-asset-storage-container/1d57afe69deb4b25a25aac9487a31605.pdf).

## Kontrola a budoucí sběr

Parser zvládá obě publikovaná rozložení tabulek a kontroluje počet sloupců, platnost hodnot, duplicity a skutečné datumy vůči katalogovému období. V reportu 2Q2020 opravuje pouze textové rozdělení původního datumu `10.05 .2020` a desetinné buňky `100,0 0`, nikoli hodnoty zdroje. Pokrytí i denní hodnoty jsou kontrolovány proti nezávislé tabulkové extrakci a uchované kopii PDF.

Čtvrtletní souhrny i denní řádky zůstávají ve verzované databázi. Týdenní GitHub Actions získává nové reporty a použije stejné explicitní zahrnutí mBank; historické reporty lze znovu vytěžit z uchovaných PDF i po odstranění z webu banky. Dosavadní testy vylučování ostatních zahraničních/neověřených katalogů zůstávají zachovány. Zahrnutí mBank není automatickým rozšířením na Oberbank nebo jiné banky.
