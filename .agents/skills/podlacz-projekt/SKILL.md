---
name: podlacz-projekt
description: Użyj, gdy użytkownik chce dodać istniejący lub nowy projekt do mapy AIA-OS i wracać do jego stanu w kolejnych sesjach.
---

# Podłącz projekt

Ustal nazwę, cel projektu, właściciela decyzji, właściwy folder i dokument stanu. Projekt dla klienta może trafić do `02 Klienci/`; własny do `03 Nasza firma/Projekty własne/`. Jeśli użytkownik nie pracuje z klientami, nie twórz katalogu klienta. Przy istniejącym repo lub folderze najpierw przeczytaj jego instrukcje i wybierz odsyłacz do źródła, nie kopiuj całego projektu do startera.

Utwórz prywatną kartę według `04 Warsztat/Szablony/projekt.md`. W portfolio zapisz nazwę, ścieżkę do stanu, bieżący status i następny krok, bez deklarowania wykonania na podstawie samego planu. W `05 Wiedza/Kontekst/mapa-pracy.md` dodaj krótką trasę. Jeśli stan ma być obsługiwany przez `pamiec-projekt.py`, zarejestruj go w prywatnym `.ai/memory-projects.json`: `schema_version: 1`, `max_state_bytes` oraz wpis w `projects` z unikalnym `id`, `name`, `root`, `state_path`. `root` i `state_path` są ścieżkami względnymi w starterze; `state_path` musi wskazywać istniejący dokument w katalogu projektu. Zachowaj inne wpisy. Nie edytuj publicznego szablonu JSON.

Uruchom `pamiec-projekt.py --root . list` i `show ID`; sprawdź, czy karta prowadzi do właściwego źródła. W przypadku projektu poza folderem AIA-OS zachowaj bezpieczny odsyłacz w karcie, lecz nie rejestruj go w pamięci projektu, jeśli narzędzie wymaga ścieżki wewnątrz root. Po zmianie mapy pamięci przebuduj pakiet globalny. Zwróć ścieżkę projektu i jeden następny krok.
