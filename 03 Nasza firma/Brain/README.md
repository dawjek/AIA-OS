# Brain

Brain ma dwa widoki czytające pliki z tego folderu OS: pełnoekranową mapę przestrzenną dokumentów oraz osobny kokpit. Po pierwszej konfiguracji pokazuje projekty, decyzje, źródła i wynik sprawdzenia pamięci. Na czystym starcie prowadzi do konfiguracji.

## Uruchomienie

Potrzebny jest Node.js 22 lub nowszy. Z głównego folderu OS przejdź do `03 Nasza firma/Brain` i uruchom `npm start`. Otwórz adres wypisany w terminalu, domyślnie `http://127.0.0.1:4173/`. Mapa jest na stronie głównej, a kokpit pod `/kokpit`. Serwer nasłuchuje tylko na tym komputerze. Zatrzymasz go przez `Ctrl+C` w terminalu.

Nie trzeba instalować pakietów. Aplikacja korzysta tylko z modułów Node.js i plików `public/`.

## Co widać

- **Mapa** zajmuje cały ekran. Przeciąganie obraca układ przestrzenny, kółko lub gest dwóch palców zmienia przybliżenie, a wybór punktu otwiera zapisany dokument. Obszary można filtrować. „Odtwórz mapę” animuje połączenia, nie historię pracy. „Kino” ukrywa panele, zostawiając samą mapę i przyciski powrotu. Przy ograniczonym ruchu animacja jest wyłączona.
- **Kokpit** pod `/kokpit` pokazuje liczbę dokumentów, powiązań, projektów i obszarów, a także decyzje, następne kroki i stan pamięci.
- **Źródła** można przeszukać po tytule i treści w obu widokach. Wynik prowadzi do dokumentu w tym folderze.
- **Następny krok** pochodzi z pól `Następny krok:` w stanach projektów. Jeśli ich nie ma, kokpit pokazuje czynności potrzebne do konfiguracji albo zapisania źródeł.

Stan `Pakiet gotowy` pochodzi z `pamiec.py status`. Oznacza sprawdzenie plików pamięci, a nie potwierdzenie, że nowa rozmowa AI już z nich skorzystała. Gdy skrypt lub interpreter są niedostępne, kokpit pokazuje `Brak odczytu`.

## Własne źródła

Kokpit działa bez pliku `brain.config.json`. Po onboardingu agent może utworzyć go na podstawie `brain.config.template.json`:

```json
{
  "system_name": "Nazwa mojego systemu",
  "configured": true,
  "areas": ["Praca", "Nauka"],
  "sources": ["05 Wiedza/Kontekst/wlasciciel.md"],
  "source_roots": ["05 Wiedza/Wiki"]
}
```

`sources` wskazuje konkretne pliki Markdown, a `source_roots` katalogi do przeszukania. Ścieżki są względne wobec głównego folderu OS i używają ukośników `/`. Brain dodaje też dokumenty wejściowe, źródła z `.ai/memory.json`, stany projektów z `.ai/memory-projects.json` i dokumenty wskazane odsyłaczami. Pokazuje tylko pliki Markdown w obszarach `01`–`05` oraz `START.md`; pomija szablony `.template.md` i dowiązania symboliczne. Prywatny `brain.config.json` nie powinien trafiać do publicznej paczki.

## Kontrola

`npm test` sprawdza puste wejście, powiązania, projekty, oba widoki, obrót układu, filtrowanie, wyszukiwanie i ograniczenie odczytu API. Adresy HTTP obsługiwane przez serwer są zamkniętą listą; nie ma trasy do odczytu dowolnej ścieżki z URL.
