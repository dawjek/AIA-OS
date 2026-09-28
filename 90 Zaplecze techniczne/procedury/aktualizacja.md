# Aktualizacja i odzyskanie danych

Publiczna paczka zawiera kod, instrukcje i szablony. Prywatne pliki użytkownika, takie jak `wlasciciel.md`, `PORTFOLIO.md`, `polaczenia.md`, `.ai/memory.json` i `brain.config.json`, powstają lokalnie i nie są częścią nowego ZIP. Git też ich domyślnie nie śledzi. Ta ochrona nie zastępuje kopii zapasowej.

Przed aktualizacją skopiuj cały swój folder AIA-OS w inne prywatne miejsce, razem z plikami ukrytymi i ignorowanymi przez Git. Pobierz nową wersję do osobnego folderu. Porównaj publiczne instrukcje, szablony i format konfiguracji z własną instalacją, a następnie przenieś potrzebne nowe pliki publiczne. Nie zastępuj własnego folderu przez rozpakowanie nowej paczki w jego miejsce. Jeśli zmienił się format prywatnej konfiguracji, przygotuj jej nową wersję z kopii i sprawdź dane przed podmianą.

Po zmianie uruchom `pamiec.py --root . status`. Jeżeli pakiet jest `stale`, wykonaj `build` i sprawdź status ponownie. Uruchom Brain oraz sprawdź jeden własny projekt i ostatnią decyzję w źródłach. W świeżej sesji AI zapytaj o konkretny następny krok i poproś o wskazanie pliku. Dopiero ta próba potwierdza ciągłość po aktualizacji.

Jeśli aktualizacja się nie uda, zatrzymaj bieżącą pracę na uszkodzonej kopii i odtwórz folder z własnej kopii zapasowej. Przed kolejną próbą zachowaj osobno nowe decyzje lub wyniki powstałe po wykonaniu kopii, żeby ich nie utracić. Przywrócona konfiguracja wymaga ponownego sprawdzenia pamięci i kokpitu.
