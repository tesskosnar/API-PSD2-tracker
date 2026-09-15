# Porovnání s původním Excelem

Porovnávaný soubor: `výkonnost API_2026_Q2.xlsx`, poslední změna 10. září 2026 v 15:42:37 CEST, velikost 3 056 969 B, SHA-256 `23f24b536bf3af9947ddcc4f1e95d886337f2177226ba6951da8c2b44ed53683`.

Původní Excel nebyl trackerem upraven. Není verzovaný v repozitáři a jeho datum změny je starší než první změny trackeru. Tracker z něj převzal seznam bank a použil jej jako výchozí kontrolní podklad; aktuální výstupy zapisuje jen do složek `data`, `dashboard` a `docs`.

## Rozsah bank

V listu `shrnutí` je 15 bank a stejných 15 bank je v hlavním rozsahu trackeru. Názvy byly pouze rozepsány: ČSAS → Česká spořitelna, KB → Komerční banka, UCB → UniCredit Bank, Creditas → Banka CREDITAS, JT → J&T Banka a PPF → PPF banka. Národní rozvojová banka je vedena jen jako oddělený kandidát a do počtu 15 ani do dashboardu nevstupuje.

## Změny v převedených datech

| Banka | Porovnání s Excelem | Důvod |
|---|---|---|
| Česká spořitelna | Dostupnost AISP 99,5523 % a PISP 99,2837 % je shodná. Odezvy a chybovosti z Excelu nejsou v aktuálním výstupu převzaty. | Veřejný endpoint `last-quarter`, který lze automaticky znovu ověřit, poskytuje pro tento přehled historii dostupnosti; další čísla z dodaného listu na tomto endpointu nejsou. |
| ČSOB | Odezvy 879,2395 / 612,5572 ms a chybovosti 5,9560 / 1,3187 % jsou po zaokrouhlení shodné. | XLSX ukládá chybovost jako podíl; stejně jako vzorce v původním souboru ji tracker násobí 100. Dostupnost banka v souboru neuvádí. |
| Komerční banka | Všechny čtyři výkonnostní hodnoty i dostupnost 97,1856 % jsou shodné po zaokrouhlení. | Bez věcné změny. |
| Raiffeisenbank | Ručních 100 % a chybovosti z Excelu nejsou publikovány jako potvrzený bod. | Poznámka souhrnu tvrdí 3Q 2025, ale datový list obsahuje 3Q 2024; veřejný report se nepodařilo doložit. |
| Air Bank | Dostupnost a odezvy jsou shodné. Chybovost je v trackeru 0,0066 / 0,0075 %, zatímco souhrn Excelu obsahuje 0,000066 / 0,000075. | Importované PDF hodnoty jsou v Excelu uložené jako podíl, ale souhrnný vzorec je nepřevedl na procentní body. Tracker zobrazuje procenta podle označení v reportu banky. |
| MONETA Money Bank | Hodnoty se změnily z 500,2444 / 150,8889 ms a 0,1767 / 0,0078 % na 498,7889 / 149,6556 ms a 0,1733 / 0,0089 %. | Nejde o stejné čtvrtletí. Excel končí 9. 9. 2026, aktuální veřejné klouzavé 90denní okno končí 14. 9. 2026. |
| Fio banka | Dostupnost 99,9809 %, odezvy i chybovosti jsou shodné po zaokrouhlení. | Bez věcné změny. |
| mBank | Bez čísel v Excelu i trackeru. | Český portál při kontrole zobrazoval polská data; ta se nepřebírají jako české hodnoty. |
| UniCredit Bank | Dostupnost 100 %, odezvy 345,29 / 248,6567 ms a společná chybovost 0,1567 % jsou shodné. | Bez věcné změny; z měsíců se skládá stejné čtvrtletí. |
| Banka CREDITAS | Dostupnost 99,9560 % a odezvy 1 819,5176 / 938,0659 ms jsou shodné. Hodnota 4,2198 % z Excelu není v trackeru vedena jako API chybovost. | Report ji označuje jako „poměr výpadků“, ne error response rate. Odlišné metriky se proto nemíchají. |
| Trinity Bank | Dostupnost 99,9951 % je shodná; ostatní hodnoty chybějí v obou zdrojích. | Bez věcné změny. |
| Partners Banka | Bez čísel v Excelu i trackeru. | Veřejný report nenalezen. |
| Oberbank | Bez čísel v Excelu i trackeru. | Veřejná stránka funguje, ale její odkaz na statistiku směřuje na interní hostname. |
| J&T Banka | Dostupnost 99,7801 %, odezvy 387,1698 / 1 482 ms a společná chybovost 0,0879 % jsou shodné. | Tracker pouze označuje, že chybovost je v reportu společná pro služby, nikoli samostatná pro AISP a PISP. |
| PPF banka | AISP odezva 1 833,6 ms a chybovost 100 % jsou shodné; období zůstá 1Q 2026. | Do průměru chybovosti se nezapočítávají dny bez jediného volání. |

Všechna čísla v CSV/JSON jsou zaokrouhlena na nejvýše čtyři desetinná místa. Tracker navíc doplňuje stav zdroje, přímý odkaz na report, období a popis metodiky; tyto sloupce v původním souhrnu nebyly.
