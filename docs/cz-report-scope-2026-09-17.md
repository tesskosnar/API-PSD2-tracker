# Český rozsah přehledu reportů — oprava 17. 9. 2026

V matici publikovaných reportů se dříve zobrazovaly také katalogové dokumenty mBank a Oberbank se stavem `unverified`. Ačkoliv jejich číselné hodnoty nikdy nebyly importovány do české časové řady, jejich existence mohla působit jako doložený report pro české PSD2 rozhraní.

Po upřesnění zadání jsou z české matice vyloučeny dokumenty jiných zemí i katalogové dokumenty bez explicitně ověřeného českého rozsahu. Česká doména ani jazyk dokumentu nejsou důkazem země metrik. Kategorie „report bez použitelných metrik“ je určena pouze reportům v českém rozsahu, ne reportům jiného nebo neověřeného trhu.

Původní Excel, číselná historie, denní hodnoty ani archiv stažených dokumentů nejsou změněny nebo mazány. mBank nadále nemá žádný ověřený český číselný záznam.

Po následném výslovném souhlasu s odděleným zobrazením jsou její 28 dohledané dokumenty vráceny do samostatného katalogu v detailu mBank a na její list v novém Excelu. Nejsou započteny do české matice ani českých číselných časových řad. Země je uvedena pouze tehdy, když je rozsah doložen. Katalog mBank má dosud rozsah `unverified`, proto je správné označení „Země neověřena · CZ nepotvrzeno“, nikoli domyšlené označení všech dokumentů jako polských. Jde o metadata a odkazy na původní PDF, ne o nově importované české hodnoty.

## Následné rozhodnutí: zahrnout souhrnné statistiky

Výše je zaznamenána původní oprava a následné vrácení katalogu. Po další výslovné žádosti „tak je zahrn do statistiky i na webu“ byly 17. 9. 2026 importovány také číselné hodnoty mBank: 29 čtvrtletních souhrnů z 28 dokumentů a 2 574 denních řádků. Dashboard je nyní zahrnuje do statistik a matice, ale odlišuje symbolem † a označením „Souhrnný report · CZ rozsah nepotvrzen“. Podmínka `isCzReport` nadále tyto reporty odmítá jako ověřený český report; zahrnutí je explicitní výjimka pouze pro souhrnné mBank záznamy. Země zůstává `unverified`, ne `CZ` ani domyšlené `PL`.

Oficiální dokumentace rozlišuje `cz-retail`, `sk-retail` a `pl-retail`. V uchovaných PDF tyto identifikátory ani `bankID` nebyly nalezeny; společná technická cesta API v českém/slovenském FAQ nedokládá zeměpisný rozsah reportovaných statistik. [Nový import a jeho metodika](mbank-summary-import-2026-09-17.md) popisuje změnu a kontroly. Ostatní banky a původní Excel se nezměnily.
