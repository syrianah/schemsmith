# Plan projektu: AI-owy warsztat schematów Minecraft

Nazwa: **schemsmith**. Dokument źródłowy (po polsku); obowiązujący plan to `docs/plans/`.

## Cel

Open-source'owe narzędzie, dzięki któremu AI (Claude, inne modele przez MCP) potrafi **projektować, sprawdzać i poprawiać** schematy Minecrafta: budynki, farmy i układy redstone. Schematy są gotowe do postawienia w grze przez Litematicę.

Czym różni się od tego, co już jest na GitHubie:

| Istniejące projekty | Czego im brakuje, a co my robimy |
|---|---|
| Generatory budowli z opisu (minecraft-builder-claude-mcp-server, VibeSchem, schematic-architect) | Nie rozumieją redstone. Stawiają bloki „na oko”, bez sprawdzenia, czy maszyna zadziała. |
| Edytory/inspektory `.litematic` dla AI (litematic-agent) | Brak lintera i symulacji redstone. Autor wprost pisze, że QC, opóźnienia i kolejność aktualizacji trzeba sprawdzać w grze. Repo nie ma licencji. |
| Biblioteki I/O (litemapy, nbtlib) | Nie są dla AI. litemapy ma licencję GPL-3.0, nbtlib nie jest rozwijane od 2022. |
| Symulatory (MCHPRS, Rust, MIT) | To cały serwer, a nie biblioteka. Nie czyta schematów jako narzędzie dla AI. |

**Nasza przewaga:** pętla *zaprojektuj → zlintuj → zasymuluj → zweryfikuj w prawdziwej grze → popraw*. AI dostaje twardą informację zwrotną, a nie tylko „plik się zapisał”.

## Lekcje z timera gry (prawdziwe błędy, które narzędzie ma łapać)

Pliki w `fixtures/`, do wrzucenia do repo jako testy regresji:

| Plik | Błąd | Reguła, która ma go złapać |
|---|---|---|
| `timer_v1_qc_dropper.litematic` | Pochodnia blokująca hopper (12,2,1) przez quasi-connectivity zasila też dropper (12,1,1) pod nim. Dropper odpala na końcu impulsu do zablokowanego hoppera, więc muzyka gra co drugą grę. | `qc-unintended-power` |
| `timer_v2_locked_repeater.litematic` | Bramka przycisku zrobiona jako zablokowany repeater (10,1,9). Blokada zamraża stan, więc jeśli przycisk jest wciśnięty w chwili końca gry, bramka zostaje otwarta. | `locked-repeater-may-freeze-on` |
| `timer_v3_fixed.litematic` | Wersja poprawiona. Nie powinna dawać żadnego z powyższych ostrzeżeń. | (test negatywny) |

Inne problemy, które wyszły przy okazji:
- Wygenerowany plik miał `MinecraftDataVersion` 2975 (1.18.2), choć używał bloków z 1.21+ (copper bulb). Litemapy wpisuje domyślną wersję. **Wersję trzeba ustawiać świadomie.**
- Kable redstone miały niespójne kształty (np. kropka bez połączeń obok innego kabla). Verifier w Litematice zgłaszał to jako „Wrong state”. **Trzeba przeliczać kształty kabli przy zapisie.**
- Schemat nie zawierał zawartości kontenerów (188 przedmiotów w hopperze, płyta w dropperze). Użytkownik musiał to robić ręcznie. **Potrzebne jest API do kontenerów i block entities.**

## Architektura

```
schemsmith/
├─ core/          model struktury: regiony, paleta, stany bloków, block entities, encje
├─ nbt/           własny koder/dekoder NBT (gzip, big-endian), bez zależności
├─ formats/       .litematic (v6/v7), Sponge .schem (v2/v3), vanilla .nbt; legacy .schematic tylko do odczytu
├─ registry/      dane bloków per wersja MC (stany, właściwości, kategorie), generowane z data generatora Mojanga
├─ geometry/      obrót, lustro, przesunięcie z poprawnym przeliczeniem stanów (facing, axis, rotation, shape)
├─ redstone/
│  ├─ graph/      graf zasilania: kto zasila kogo, mocno/słabo, QC, aktualizacje
│  ├─ lint/       reguły (patrz niżej), każda z ID, poziomem, opisem i propozycją poprawki
│  └─ sim/        symulator tickowy (etap późniejszy)
├─ build/         API do budowania: prymitywy, auto-kształt kabli/płotów/schodów, biblioteka modułów
├─ library/       parametryczne moduły: zegary, przerzutniki, drzwi z tłoków, sortery, farmy
├─ render/        podgląd: przekroje ASCII per warstwa, izometryczny PNG
├─ guide/         lista materiałów, instrukcja warstwa po warstwie, wersja „survival-friendly”
├─ mcp/           serwer MCP (stdio), narzędzia z ograniczonym rozmiarem odpowiedzi
├─ cli/           ta sama funkcjonalność z terminala
└─ harness/       weryfikacja w prawdziwej grze: headless serwer Fabric + GameTest
```

### Kluczowe decyzje

- **Język: Python ≥ 3.11**, zarządzanie przez `uv`, MCP przez oficjalne `mcp` Python SDK (MIT). Python to język, w którym AI najczęściej pisze skrypty, a ekosystem MC-schematów też jest głównie w Pythonie.
- **Licencja projektu: Apache-2.0** (albo MIT). Dlatego **nie zależymy od litemapy (GPL-3.0)**. Własny NBT i własny `.litematic` to kilkaset linii kodu. Litemapy może być co najwyżej opcjonalną zależnością deweloperską, tylko do testów krzyżowych.
- **Rejestr bloków generujemy z serwera Mojanga dla konkretnej wersji:** `java -DbundlerMainClass=net.minecraft.data.Main -jar server.jar --reports` → `generated/reports/blocks.json`. PrismarineJS/minecraft-data kończy się na 26.1, a nam potrzebne jest np. 26.3. **Nie commitujemy jara Mojanga.** Skrypt pobiera go z oficjalnego manifestu wersji.
- **Prawdą jest gra, nie nasz symulator.** Symulator służy do szybkiej informacji zwrotnej. Ostateczna weryfikacja to prawdziwy serwer w CI (harness).
- **Bezpieczne zapisy:** nigdy nie nadpisujemy pliku wejściowego bez flagi. Każdy zapis jest ponownie czytany i walidowany. Nieznane tagi NBT zostają zachowane (round-trip).
- **Odpowiedzi dla AI mają ograniczony rozmiar:** paginacja, wycinki, podsumowania. Nigdy nie wyrzucamy całego schematu do kontekstu modelu.

## Reguły lintera (pierwsza partia)

| ID | Co wykrywa |
|---|---|
| `qc-unintended-power` | Dropper/dispenser/tłok zasilony przez QC (blok nad nim) przez źródło, które ma sterować czymś innym |
| `locked-repeater-may-freeze-on` | Repeater używany jako bramka przez blokadę. Może zamarznąć włączony. Sugestia: komparator w trybie odejmowania. |
| `diode-wrong-direction` | Repeater/komparator, którego wejście nie jest połączone z żadnym źródłem, a wyjście z żadnym odbiornikiem. Prawdopodobnie odwrócony. |
| `comparator-mode-suspicious` | Komparator z bocznym wejściem w trybie `compare` tam, gdzie wygląda na bramkę (i odwrotnie) |
| `wire-shape-inconsistent` | Zapisany kształt kabla różni się od tego, co gra przeliczy. Auto-fix: przeliczenie. |
| `torch-burnout-risk` | Pochodnia w pętli, która może przełączać się więcej niż 8 razy w 60 gt |
| `hopper-unlocked-unexpectedly` / `hopper-always-locked` | Hopper w obwodzie, który nigdy się nie odblokuje albo nigdy nie zablokuje |
| `observer-faces-nothing` | Observer patrzący na blok, który nigdy się nie zmienia |
| `invalid-block-state` | Stan bloku nieistniejący w docelowej wersji MC |
| `data-version-mismatch` | `MinecraftDataVersion` niezgodny z użytymi blokami |
| `container-empty-but-required` | Hopper-clock lub dropper bez przedmiotów, a moduł ich wymaga |

Każda reguła: ID, poziom (error/warning/info), lokalizacja, wyjaśnienie, sugerowana poprawka. Gdzie się da, poprawka ma postać planu edycji do zastosowania jednym wywołaniem.

## Narzędzia MCP (docelowo)

| Narzędzie | Co robi |
|---|---|
| `schematic_summary` | Wymiary, regiony, wersja, liczba bloków, top materiały |
| `schematic_slice` | Przekrój ASCII jednej warstwy z legendą |
| `schematic_inspect` | Blok + 6 sąsiadów + block entity |
| `schematic_query` | Wyszukiwanie bloków (wzorzec, kategoria), stronicowane |
| `schematic_edit` | Plan edycji (set/fill/replace/properties/container), najpierw podgląd, potem apply |
| `schematic_create` | Nowy pusty schemat dla wersji MC |
| `build_place_module` | Wstawia moduł z biblioteki z parametrami, obrotem i pozycją |
| `redstone_lint` | Lista problemów z poprawkami |
| `redstone_trace` | Skąd przychodzi i dokąd idzie sygnał z danego bloku |
| `redstone_simulate` | N ticków od zadanego wejścia (np. „naciśnij przycisk (9,2,3)”), oś czasu stanów |
| `render_preview` | Izometryczny PNG (opcjonalnie wybrane warstwy) |
| `materials_list` | Lista materiałów w stackach i shulkerach |
| `build_guide` | Instrukcja krok po kroku warstwa po warstwie |
| `verify_in_game` | (harness) uruchamia test na prawdziwym serwerze i zwraca wynik |

Wszystko dostępne też w CLI (`schemsmith lint plik.litematic` itd.).

## Etapy

Każdy etap kończy się działającym, przetestowanym kodem w `main`.

### M0: szkielet repo
Struktura pakietu, `uv`, ruff, mypy (strict w `core`/`nbt`), pytest, GitHub Actions (lint, typy i testy na Linux/Windows/macOS), licencja, README, CONTRIBUTING, CODE_OF_CONDUCT, szablony issue/PR.
**Gotowe, gdy:** CI jest zielone na pustym pakiecie, a `schemsmith --version` działa.

### M1: NBT i formaty
Własny koder/dekoder NBT, odczyt i zapis `.litematic` (v6 i v7, ciasne pakowanie bitów, ujemne rozmiary regionów, wiele regionów), Sponge `.schem` v2/v3, vanilla `.nbt`. Model `Structure`. Konwersje między formatami.
**Gotowe, gdy:** round-trip zachowuje wszystkie dane (także nieznane tagi), pliki z `fixtures/` czytają się poprawnie, wyniki zgadzają się z litemapy w teście krzyżowym (opcjonalnym, tylko dev), a property-based testy (hypothesis) pakowania bitów przechodzą.

### M2: rejestr bloków i walidacja
Skrypt generujący rejestr dla wybranej wersji z data generatora. Kategorie bloków (redstone, kontener, pełny/przewodzący, przezroczysty) potrzebne linterowi. Walidacja stanów.
**Gotowe, gdy:** `invalid-block-state` i `data-version-mismatch` działają, a rejestr dla co najmniej dwóch wersji (np. 1.21.11 i 26.3) jest wygenerowany w CI.

### M3: graf redstone i linter
Model zasilania: źródła, przewodniki (mocne/słabe zasilanie), diody, QC, blokady hopperów, przeliczanie kształtów kabli. Reguły z tabeli powyżej.
**Gotowe, gdy:** `fixtures/timer_v1` daje `qc-unintended-power` na (12,1,1), `timer_v2` daje `locked-repeater-may-freeze-on` na (10,1,9), `timer_v3` jest czysty. Do tego minimum 30 małych testów jednostkowych układów.

### M4: MCP i CLI
Serwer MCP (stdio) i CLI z narzędziami z M1–M3, limity rozmiaru odpowiedzi, stronicowanie, bezpieczny zapis (`--root`, brak nadpisywania).
**Gotowe, gdy:** Claude Code/Desktop z tym MCP jest w stanie sam znaleźć oba błędy timera i zaproponować poprawki. Opisany scenariusz demo w README.

### M5: harness w prawdziwej grze
Headless serwer Fabric w CI (pobierany oficjalnie, EULA akceptuje opiekun repo świadomie w konfiguracji CI). Mod/GameTest: wstawia strukturę, wykonuje akcje (przycisk, dźwignia, przedmioty), odlicza ticki i zbiera stany bloków. Porównanie z oczekiwaniami.
**Gotowe, gdy:** w CI test „timer v3: po START i 3000 gt dzwon zadzwonił raz, B pusty, A ma 188” przechodzi, a dla v1 i v2 nie przechodzi.

### M6: symulator tickowy
Szybki symulator w Pythonie dla podzbioru mechaniki: kable, pochodnie, repeatery, komparatory, przyciski, dźwignie, hoppery, droppery, tłoki (bez BUD-ów na start), copper bulb, observer. Wyniki porównywane z harnessem (M5) jako wyrocznią.
**Gotowe, gdy:** wyniki zgadzają się z harnessem dla całej biblioteki testowej. Rozbieżności są udokumentowane jako znane ograniczenia.

### M7: budowanie przez AI
API wysokiego poziomu: prymitywy (fill, ściany, dach, schody z poprawnym `facing`/`half`), auto-kształty (kable, płoty, szyby, schody), obrót i lustro z przeliczaniem stanów. Biblioteka modułów parametrycznych:
- **redstone:** hopper clock, T flip-flop, pulse extender, monostabilny, licznik, drzwi z tłoków 2×2, wyświetlacz 7-segmentowy, bramka AND/OR/XOR,
- **farmy:** trzcina, kelp, dynia/arbuz, mączka kostna, krowy/kurczaki,
- **budynki:** domek, wieża, dach dwuspadowy, schody, okna, oświetlenie (anty-spawn).

**Gotowe, gdy:** każdy moduł ma test w harnessie albo symulatorze i podgląd PNG w dokumentacji.

### M8: podglądy i przewodniki
Izometryczny render PNG (bez tekstur Mojanga w repo; tekstury czytane z lokalnego jara klienta albo kolory bloków), przekroje warstw, lista materiałów, przewodnik „buduj warstwa po warstwie” (Markdown/HTML).

### M9: wydanie 1.0
Paczka na PyPI, `uvx schemsmith-mcp`, dokumentacja (mkdocs), instrukcja dodania do Claude Code/Desktop, galeria przykładów, changelog, wersjonowanie semver.

## Jakość i zasady

- Każda poprawka błędu dostaje test regresji (najlepiej mały `.litematic` w `fixtures/`).
- Bez zależności sieciowych w testach jednostkowych. Pobieranie jara Mojanga tylko w osobnym jobie CI.
- Nie commitujemy plików Mojanga (jary, tekstury). Wygenerowane rejestry bloków tylko jako dane pochodne, ze skryptem do odtworzenia.
- Dokumentacja i kod po angielsku (open source). Dyskusje mogą być po polsku.
- Etykiety issue: `good first issue`, `lint-rule`, `module`, `format`, `harness`.

## Ryzyka

| Ryzyko | Co z tym robimy |
|---|---|
| Mechanika redstone zmienia się między wersjami (np. nowe bloki w 26.x) | Rejestr per wersja, harness na konkretnej wersji, testy oznaczone wersją |
| Symulator rozjeżdża się z grą | Harness jako wyrocznia, znane rozbieżności w dokumentacji |
| Licencje | Własny NBT/format, brak kodu GPL w paczce, brak plików Mojanga w repo |
| Zbyt duże odpowiedzi MCP dla modelu | Twarde limity, stronicowanie, podsumowania |
