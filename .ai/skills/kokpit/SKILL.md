---
name: kokpit
description: Użyj, gdy użytkownik chce uruchomić, skonfigurować lub zrozumieć lokalny kokpit i mapę dokumentów AIA-OS.
---

# Kokpit i mapa

Brain jest lokalną aplikacją w `03 Nasza firma/Brain`. Przeczytaj jej README i stan konfiguracji. Przed personalizacją ustal, które obszary i źródła użytkownik chce widzieć. Do prywatnego `brain.config.json` przenieś strukturę z publicznego `brain.config.template.json`, wpisując `system_name`, tablicę `areas`, tablicę istniejących względnych ścieżek Markdown w `sources` oraz względne katalogi w `source_roots`. Nie dodawaj fikcyjnych projektów, klientów ani wykonanych zadań.

Sprawdź Node.js 22+. W folderze Braina uruchom `npm start`. Otwórz stronę główną z pełnoekranową mapą i osobny `/kokpit`. Porównaj oba widoki z plikami: profil, priorytety, projekty, decyzje oraz stan pamięci. Sprawdź obrót mapy, filtr obszaru i otwarcie rzeczywistego źródła. Dla nowej instalacji oba widoki powinny prowadzić do konfiguracji. Przy błędzie podaj konkretną przyczynę i brak potwierdzenia działania.

Kokpit czyta lokalne pliki; nie publikuj go ani prywatnych dokumentów bez osobnego zlecenia. Po zmianie źródła pamięci przebuduj pakiet, jeśli to źródło jest w jej konfiguracji. Zwróć użytkownikowi adres lokalny i informację, co zostało sprawdzone w widoku.
