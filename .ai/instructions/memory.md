# Pamięć i ciągłość pracy

Źródłem prawdy są prywatne pliki użytkownika. Pakiet startowy jest ich małym, generowanym wyciągiem; nie zastępuje źródeł. Przy pytaniu o stan projektu odczytaj jego kartę i dokument stanu. Przy pytaniu o wcześniejsze ustalenia sprawdź dziennik decyzji lub `stan-rozmowy.md`. Gdy plik nie istnieje, nie zgaduj.

Podczas onboardingu utwórz własne pliki z publicznych `*.template.md`. Skopiuj `.ai/memory.template.json` do ignorowanego `.ai/memory.json`, dopasuj listę źródeł do faktycznie istniejących plików i ustaw `configured: true` dopiero po zapisaniu profilu, priorytetów, mapy pracy i stanu rozmowy. Pliki konfiguracyjne i wygenerowany pakiet są prywatne. Nie modyfikuj publicznego szablonu, by przechować dane użytkownika.

Skrypty pamięci znajdują się w `90 Zaplecze techniczne/narzedzia/`. Uruchamiaj je z parametrem `--root` wskazującym główny folder (zwykle `.`). Na macOS i Linux użyj `python3`, na Windows `py -3` lub działającego `python`. Przykład z folderu głównego:

```text
python3 "90 Zaplecze techniczne/narzedzia/pamiec.py" --root . status
python3 "90 Zaplecze techniczne/narzedzia/pamiec.py" --root . build
python3 "90 Zaplecze techniczne/narzedzia/pamiec.py" --root . search "temat"
```

`empty` oznacza brak zakończonego onboardingu lub treści; `stale` wymaga przebudowania pakietu; `unavailable` wskazuje błąd źródła lub konfiguracji; `ready` potwierdza pakiet, lecz nie użycie go przez model. Po zmianie źródła wykonaj `build`, a następnie `status`. Gdy hook nie jest zainstalowany lub niedostępny, odczytaj źródła bezpośrednio i zgłoś brak automatycznego przekazania kontekstu.

Po ważnym zakończonym etapie użyj `pamiec.py --root . status`, pobierz `checkpoint_revision` i wywołaj `checkpoint --input -` z JSON zawierającym `event_id`, `expected_revision`, `summary` oraz listy `done`, `next`, `sources`. `event_id` ma być unikalne dla wydarzenia; przy ponowieniu tego samego zapisu zachowaj to samo ID. `expected_revision` zapobiega nadpisaniu nowszego stanu. Przy konflikcie odczytaj aktualny dokument, połącz ustalenia i dopiero ponów. Skrypt `pamiec-projekt.py --root . list|show ID|checkpoint ID --input -` służy projektom wpisanym w prywatnym `.ai/memory-projects.json`.

W trybie tylko do odczytu nie zapisuj źródeł, pakietu, checkpointu ani rejestrów. Nowa sesja powinna potrafić przywołać zapisany cel i kolejny krok z właściwego źródła; samo `ready` nie zalicza tej próby.
