# Nová kontrola veřejných PSD2 zdrojů všech 15 bank

Kontrola 16. září 2026 navazuje na verzi `a0061f1912cdfb37a3ab12dc3ccc1a7a89557789`. Znovu byly načteny primární stránky všech 15 bank, dostupné katalogy a doplňkové archivy. Dynamické portály byly ověřeny také v prohlížeči. U mBank byl prověřen skutečný katalog, FAQ a dokumentace; u Oberbank obsah produkčního PDF. „Nenalezen český souhrn“ neznamená „banka reporty nezveřejňuje“.

## Změny oproti minulé verzi

- **MONETA:** přibyl označený výpočet 2Q2026 z **13 archivovaných dnů z 91**, nikoli nově nalezený report banky nebo celé čtvrtletní měření. Probíhající 3Q2026 se nepředstírá jako uzavřený souhrn.
- **mBank:** český portál nabízí **28 různých veřejných PDF**: 27 v EN a jeden další (1Q2024) v PL variantě stejného českého portálu. Jejich existence je viditelná v matici a původní soubory jsou uchovány. Automatický sběr kontroluje oba skutečné veřejné katalogy. Stav je **český rozsah neověřen**, nikoli „bez reportu“.
- **Oberbank:** produkční report 2Q2026 existuje a je viditelný v matici. Samostatný český rozsah čísel není potvrzen; netvrdíme bez důkazu, že jde výhradně o rakouská nebo skupinová data.
- **Všech 194 dosavadních čtvrtletních JSON záznamů je beze změny v každém poli.** Nyní je 195 záznamů: 189 s čísly z bankovních reportů, 1 výpočet MONETY a 5 bez použitelného čtvrtletního číselného souhrnu.
- **17 319 denních záznamů zůstalo beze změny**, včetně verzí a původních nul. Neověřená mBank/Oberbank čísla nejsou převzata jako česká data. Původní Excel nebyl upraven; SHA-256 zůstává `23f24b536bf3af9947ddcc4f1e95d886337f2177226ba6951da8c2b44ed53683`.

## Opětovné ověření všech bank

Počty čtvrtletí označují záznamy v ověřeném českém datasetu, ne všechny dokumenty na webu nebo přítomnost všech metrik.

| Banka | Znovu kontrolovaný primární zdroj a výsledek | České čtvrtletní záznamy před → nyní |
|---|---|---:|
| Air Bank | [Český archiv](https://www.airbank.cz/aplikace-tretich-stran/) stále nabízí 30 reportů 2019-Q1–2026-Q2. Další období nebylo nalezeno. | 30 → 30 |
| Banka CREDITAS | [Statistiky](https://www.creditas.cz/povinne-uverejnovane-informace#statisticke-udaje-o-dostupnosti) opět vracejí 403. Ověřené uložené kopie 28 období jsou zachovány, neoznačujeme je jako nově stažené. | 28 → 28 |
| Česká spořitelna | [Český health-check portál](https://developers.erstegroup.com/api-health-check/bank.csas/last-quarter) a veřejná JSON data potvrzují 2Q2026. Starší veřejný čtvrtletní archiv nebyl doložen. | 1 → 1 |
| ČSOB | [Reporting](https://www.csob.cz/csob/otevrene-bankovnictvi-csob/pro-vyvojare/seznam-api/reporting) obsahuje 22 XLSX 2021-Q1–2026-Q2. Výkonnostní reporty existují; chybí v nich doložená uptime metrika, nikoli reporty. | 22 → 22 |
| Fio banka | [Statistiky](https://developers.fio.cz/stats.html) stále obsahují 28 PSD2 PDF 2019-Q3–2026-Q2. | 28 → 28 |
| J&T Banka | [Česká informační povinnost](https://www.jtbank.cz/informacni-povinnost) má 14 českých reportů v nesouvislé řadě 2019-Q2–2026-Q2. Mezery nejsou doplněny slovenskými dokumenty. | 14 → 14 |
| Komerční banka | [České statistiky API](https://www.kb.cz/cs/dostupnost-sluzeb-internetoveho-a-otevreneho-bankovnictvi-api) potvrzují 8 reportů 2024-Q3–2026-Q2. Vyhledání starších českých reportů nepřineslo další doložený dokument. | 8 → 8 |
| mBank | [Český portál reportů](https://developer.api.mbank.cz/reports) nabízí 28 PDF napříč EN/PL variantou, nově je doložen také [1Q2024](https://dpprodassetstorage.blob.core.windows.net/prod-asset-storage-container/69317d8b41524036a6f48d7a65c20b0e.pdf). Samostatný český řez čísel není vymezen. V matici jsou dokumenty viditelné s vysvětlením omezení. | 0 → 0; navíc 28 zdrojových dokladů |
| MONETA Money Bank | [Otevřené bankovnictví](https://www.moneta.cz/otevrene-bankovnictvi) zveřejňuje 90 dnů odezvy/chybovosti 18. 6.–15. 9. 2026. Dřívější uchované kopie neobsahují starší dny. Přibyl částečný výpočet 2Q2026. | 0 → 1 výpočet; 0 publikovaných čtvrtletních reportů |
| Oberbank | [Česká XS2A stránka](https://www.oberbank.cz/xs2a-interface) a [opravený veřejný PDF](https://www.oberbank.cz/documents/20195/21703/obkglobal_xs2a_statistik.pdf/ed74f6e3-961a-a810-31ed-0df88ef05b56) potvrzují produkční statistiku 1. 4.–30. 6. 2026. Český řez není vymezen. | 0 → 0; navíc 1 zdrojový doklad |
| Partners Banka | Ověřen [stavový web](https://jakbezi.partnersbanka.cz/), [PSD2 dokumentace](https://psd2.partnersbanka.cz/), [dokumenty](https://www.partnersbanka.cz/dokumenty-ke-stazeni) a [archiv](https://www.partnersbanka.cz/archiv). Veřejný čtvrtletní statistický report nebyl dohledán. Uchovává se oddělený 30denní health-check. | 0 → 0 |
| PPF banka | [Aktuální katalog](https://www.ppfbanka.cz/cs/dokumenty/1868-pristupy-tretich-stran) a [archiv](https://www.ppfbanka.cz/cs/dokumenty/1868-pristupy-tretich-stran?category_id=1868&archive=archive) mají 13 období 2023-Q1–2026-Q1. Novější 2Q2026 nebylo doloženo. Uptime chybí; čtyři reporty 2025 nemají aktivní volání pro čtvrtletní souhrn. | 13 → 13 |
| Raiffeisenbank | [Dynamický katalog](https://www.rb.cz/informacni-servis/dokumenty-ke-stazeni) byl znovu prohledán užšími dotazy. Stále 21 dokumentů: 20 použitelných a sporný 3Q2025 bez převzatých čísel. Nejnovější použitelný souhrn je 1Q2025. | 21 → 21 |
| Trinity Bank | Znovu prošlo všech **14 stránek** [českého archivu](https://www.trinitybank.cz/otevrene-bankovnictvi/), potvrzeno 28 API reportů 2019-Q3–2026-Q2, nikoli reporty internetového bankovnictví. | 28 → 28 |
| UniCredit Bank | [Oficiální portál](https://developer.unicredit.eu/report?view=kpi) byl znovu načten a ověřeny podklady `CZ-B → Dedicated Interface` za duben–červen 2026. Jiné země českou historii nedoplňují. | 1 → 1 |

## mBank: existence reportů versus rozsah čísel

[Česká PSD2 stránka](https://www.mbank.cz/informace-k-produktum/info/jine/psd2.html) odkazuje na vývojářský portál. [Úvodní dokumentace](https://developer.api.mbank.cz/how-to) výslovně popisuje přístup ke klientům Polska, České republiky a Slovenska. [Oficiální FAQ](https://developer.api.mbank.cz/faq) potvrzuje společné API pro českou a slovenskou mBank, odlišené `bankID` v URL. Jazyk PDF nebo varšavská patička tedy nejsou důvodem pro tvrzení, že reporty nesouvisí s ČR.

Anglická varianta českého a slovenského portálu odkazuje na stejných 27 PDF. Polská jazyková varianta přímo na českém hostu doplňuje 1Q2024, celkem je nyní doloženo 28 dokumentů. Všech 28 PDF bylo pročteno. Katalog ani PDF nevymezují samostatnou českou řadu statistik. Společné API samo o sobě nedokazuje rozsah agregace jednotlivého reportu. **Není potvrzeno nepublikování české mBank ani výhradně polský rozsah; neověřen je samostatný český řez čísel.** Dokumenty uchováváme a ukazujeme, ale do potvrzení rozsahu je neimportujeme jako česká měření.

Automatický sběr používá veřejný endpoint `https://developer.api.mbank.cz/reportpage?locale=en` s hlavičkou `mode: INDIVIDUAL_EN` a jeho PL variantu `?locale=pl` / `INDIVIDUAL_PL`. Obě vracejí reporty na českém hostu. Tyto režimy nejsou důkazem země statistik. Nepoužívá se vymyšlený režim `INDIVIDUAL_CS` ani přihlašovací údaje.

Jeden počáteční dokument zahrnuje **14. 6.–30. 9. 2019**. V evidenci má své skutečné období, není přeznačen na samostatný souhrn 2Q2019 nebo 3Q2019. Dvě políčka matice jen odkazují na stejný společný dokument.

## MONETA: automatický výpočet z trvalého archivu

Po každém týdenním sběru se z posledních zachycených verzí českých denních údajů přepočítají uzavřená čtvrtletí. Dny odstraněné ze živého okna zůstávají v databázi i ve výpočtu. Oprava banky vytvoří novou verzi a souhrn se přepočítá. Výpočet nikdy nepřepíše případný publikovaný report banky.

Za 2Q2026 je zachyceno jen **18.–30. 6.: 13/91 dnů**. Průměr AISP odezvy je 544,8462 ms, PISP 150,5385 ms. Průměr publikovaných denních procent chybovosti AISP je 0,1308 % a PISP 0,0077 %. Odezva vynechává publikované 0 ms; původní denní nuly zůstávají. Chybovost zachovává skutečné nuly, chybějící dny nikoli.

Bez počtů volání **nelze vypočítat provozem váženou čtvrtletní chybovost**. Jde výslovně o nevážený průměr denních procent za zachycené dny, ne o poměr všech chyb ke všem voláním. Uptime se z těchto metrik neodvozuje. Úplnost bude doložena až zachycením všech příslušných dnů/metrik; starší chybějící dny se nedopočítávají odhadem.

JSON/CSV označuje výpočty `report_kind=archive-derived` a uvádí počet/rozsah dnů. CSV má pět doplněných metadatových sloupců, dosavadních šestnáct sloupců se obsahově nezměnilo. Databázové verze výpočtů mají samostatný typ `quarterly-derived`, nikoli `quarterly-report`.

## Legenda a zobrazení

Matice se při otevření posune k nejnovějším čtvrtletím vpravo. Jména bank zůstávají ukotvená; uživatel se může sám posunout do historie od roku 2019.

- **Kompletní report:** použitelné údaje a denní archiv celého čtvrtletí u metrik skutečně uvedených v souhrnu. Neznamená přítomnost všech metrik ani potvrzení regulatorního souladu.
- **Částečně vyplněn:** použitelné údaje s neúplným či nedoloženým denním pokrytím některé souhrnné metriky.
- **Report bez použitelných metrik:** dokument existuje, ale pro ověřené CZ srovnání nemáme použitelný číselný souhrn. Detail uvádí důvod.
- **Bez reportu:** pro dané období nebyl ve zde prověřených zdrojích doložen dokument; není to důkaz, že žádný nemůže existovat jinde.

**Σ a přerušovaný okraj** navíc označují výpočet trackeru, nikoli report banky. Kliknutí zobrazí skutečné pokrytí a zdroj; MONETA má také odkaz na denní podklady výpočtu. Podle používané dostupnostní metriky nelze usuzovat na počet bank zveřejňujících reporty.

## Ověření

Proběhlo porovnání 194 předchozích čtvrtletních záznamů pole po poli, shoda celého denního exportu a kontrola původního Excelu. Ověřena integrita databáze i všech **306** zdrojových objektů. Testy pokrývají uzavřená/otevřená čtvrtletí, přestupný rok, duplicity, opravy, zachování odstraněných dnů, chybějící údaje versus nuly, nevytváření uptime a neověřený český rozsah. Prohlížeč ověřil 15 bank, legendu, nejnovější sloupec a ukotvení jmen na počítači i mobilu.

Z neúplné veřejné dohledávky nevyvozujeme nepublikování nebo porušení regulatorní povinnosti. Bankám nebyly bez zadání posílány dotazy; samostatný český rozsah mBank/Oberbank může vyžadovat jejich potvrzení.
