# Pamięć lokalna

Pamięć korzysta z plików tego folderu. Nie odczytuje wszystkich rozmów ani nie zapisuje ich automatycznie. Ważny wynik najpierw opracuj w dokumencie projektu lub w stanie rozmowy, a potem sprawdź, czy można do niego wrócić w nowej sesji.

## Pierwsza konfiguracja

Publiczna paczka zawiera `.ai/memory.template.json` i `.ai/memory-projects.template.json`. Nie zawiera danych użytkownika. Onboarding tworzy lokalne `.ai/memory.json` i `.ai/memory-projects.json` na podstawie szablonów. Oba pliki, utworzone dokumenty osobiste, pakiet startowy i ustawienia hooków są ignorowane przez Git.

W `memory.json` pole `sources` wskazuje pliki do pakietu. Każdy wpis ma `path` względem głównego folderu i `required`. `search_roots` wskazuje katalogi przeszukiwane przez `search`. Po zapisaniu własnego profilu, priorytetów, mapy pracy i stanu rozmowy ustaw `configured` na `true`. Jeśli któryś wymagany plik nie istnieje, `build` zgłosi `unavailable` i nie opublikuje pakietu.

Ścieżki `output`, `manifest` i `checkpoint_path` pozostają stałe: wskazują prywatny pakiet, manifest i stan rozmowy w miejscach ignorowanych przez Git. Walidator odrzuca zmianę tych pól na publiczny dokument oraz dowiązanie lub alias celu zapisu. Dokument stanu projektu musi leżeć wewnątrz prywatnego projektu w `01 Zarząd/Karty projektów`, `02 Klienci` albo `03 Nasza firma/Projekty własne`.

Wymagany jest Python 3.10 lub nowszy. Skrypty używają tylko jego biblioteki standardowej. Na macOS i Linuksie zwykle uruchamia się je przez `python3`, a na Windows przez `py -3` albo wskazany interpreter Pythona. Nie jest wymagany WSL. Natywnego uruchomienia na Windows nie potwierdzono w teście tego wydania.

## Sprawdzenie i wyszukiwanie

Z głównego folderu wywołaj:

```text
python3 "90 Zaplecze techniczne/narzedzia/pamiec.py" --root . status
python3 "90 Zaplecze techniczne/narzedzia/pamiec.py" --root . build
python3 "90 Zaplecze techniczne/narzedzia/pamiec.py" --root . search "fraza"
```

Na Windows zastąp `python3` przez `py -3`. `--root .` oznacza bieżący folder i działa również wtedy, gdy jego nazwa zawiera spacje lub polskie znaki. Wynik każdej komendy jest obiektem JSON.

`empty` oznacza, że onboarding nie został zakończony albo wskazane źródła są puste. `stale` oznacza, że pakiet nie powstał lub nie odpowiada już bieżącym plikom. `unavailable` podaje kod przyczyny, na przykład `missing_source` albo `limit_exceeded`. `ready` potwierdza zgodność pakietu z lokalnymi źródłami w chwili kontroli. Gdy limit został przekroczony, skrypt nie skraca źródeł; dobierz mniejszy zestaw lub zmień limit świadomie. `ready` nie dowodzi, że aplikacja AI odebrała lub wykorzystała treść.

`search` zwraca ścieżkę i numer linii w dozwolonym źródle. Nie przeszukuje poświadczeń, plików sesji ani katalogu technicznego pamięci. Wynik może mieć `truncated_results: true` po 50 trafieniach; to limit listy wyników, nie treści pakietu.

## Zapis stanu rozmowy

`status` zwraca `checkpoint_revision`: SHA-256 całego `checkpoint_path` lub `null`, gdy dokument jeszcze nie istnieje. Agent przygotowuje JSON z polami:

```json
{
  "event_id": "pierwsza-decyzja-001",
  "expected_revision": "SHA-256 z aktualnego status",
  "summary": "Wybrano pierwszy temat atlasu.",
  "done": ["Zebrano wymagania."],
  "next": ["Przygotować szkic spisu treści."],
  "sources": ["05 Wiedza/Kontekst/priorytety.md"]
}
```

Do testu zapisu użyj `pamiec.py --root . checkpoint --input - --check-only`, przekazując JSON na standardowe wejście procesu. Ta kontrola nie tworzy plików. Jeśli wynik ma `status: ok`, wykonaj to samo polecenie bez `--check-only`. Stara rewizja daje `conflict`; wtedy odczytaj aktualny dokument i połącz zmiany przed przygotowaniem nowego zdarzenia. Powtórzenie tego samego `event_id` z tą samą treścią jest idempotentne. Inna treść pod tym samym ID jest konfliktem. Poprzednia wersja dokumentu trafia do `.ai/synchronizacja/pamiec/retencja/`.

Checkpoint zastępuje wyłącznie oznaczony blok w dokumencie. Inne akapity pozostają na miejscu. Źródła podane w `sources` muszą być istniejącymi plikami z tego systemu. Kod odrzuca typowe wzorce kluczy i haseł, ale przed zapisem nadal sprawdź, czy tekst nadaje się do lokalnej pamięci.

## Osobne projekty

Lokalne `.ai/memory-projects.json` zaczyna od `projects: []`. Po utworzeniu projektu dodaj wpis z `id`, `name`, `root` i `state_path`. Dokument `state_path` musi istnieć wewnątrz folderu `root`. Przykład:

```json
{
  "id": "atlas",
  "name": "Atlas roślin",
  "root": "03 Nasza firma/Projekty własne/Atlas",
  "state_path": "03 Nasza firma/Projekty własne/Atlas/README.md"
}
```

Narzędzie `pamiec-projekt.py --root . list` zwraca zarejestrowane projekty. `show atlas` zwraca aktualny stan i rewizję dokumentu. `checkpoint atlas --input - --check-only` sprawdza zapis, a to samo polecenie bez `--check-only` go wykonuje. Payload ma takie same pola jak globalny checkpoint oraz `"project": "atlas"`; `expected_revision` pochodzi z `show atlas`. Zapis jednego projektu nie przepisuje stanu pozostałych.

## Hook nowej sesji

`instaluj-pamiec.py --root . --runtime codex install` lub `--runtime claude install` dodaje lokalny handler `SessionStart`. `--runtime both` obejmuje oba narzędzia. `status` pokazuje, czy wpis jest skonfigurowany, a `uninstall` usuwa wyłącznie handler pamięci. Instalator zachowuje pozostałe wpisy i nie zmienia uprawnień, logowania ani zaufania do hooków.

Codex wymaga osobnego sprawdzenia i zaufania do nowego hooka w `/hooks`. Sam wpis w `.codex/hooks.json` nie potwierdza uruchomienia. Handler Claude działa również przy rozgałęzieniu sesji (`fork`). W świeżej sesji zadaj pytanie o konkretną, wcześniej zapisaną decyzję i sprawdź odpowiedź wraz ze wskazanym źródłem. Dopiero taki odczyt potwierdza powrót do ustalenia w wybranym narzędziu. Hook przygotowuje kontekst przy starcie sesji i zwraca czytelne `empty` lub `unavailable`, gdy nie może potwierdzić aktualnego pakietu.

Jeśli po awarii został plik `.ai/synchronizacja/pamiec/memory.lock`, najpierw upewnij się, że żaden proces zapisu pamięci nie działa. Potem zachowaj kopię tego pliku w retencji i usuń blokadę ręcznie; skrypt sam nie przełamuje pozostawionej blokady.

## Lokalna kolejka korekt AI

Po istotnej pomyłce można dodać wpis przez `autodiagnoza.py --root . enqueue --input -`. JSON zawiera `event_id`, `observation`, `evidence` i `correction`. `list` zwraca oczekujące wpisy oraz ich rewizje. Po sprawdzeniu poprawki wywołaj `record --input -` z `event_id`, `expected_revision` z listy oraz `outcome`. Skrypt zapisze wynik do prywatnego `01 Zarząd/Autodiagnoza pracy AI/REJESTR.md`, odczyta wpis ponownie i zachowa poprzednią wersję rejestru w lokalnej retencji. Ponowienie tego samego zdarzenia nie dubluje wpisu. Ten obieg potwierdza wyłącznie lokalny plik; nie korzysta z usługi chmurowej.
