---
name: sprawdz-system
description: Użyj, gdy użytkownik chce sprawdzić, czy AIA-OS odnajduje właściwe źródła, pamięta ustalenia i uruchamia lokalny kokpit.
---

# Sprawdź system

Sprawdź rzeczywisty stan, nie tylko obecność plików. Odczytaj profil, priorytety, portfolio i jeden wskazany projekt. Uruchom `pamiec.py --root . status`; jeśli zwróci `stale`, po upoważnionym zapisie źródeł wykonaj `build` i ponownie sprawdź. `empty` jest prawidłowym stanem przed onboardingiem, `unavailable` wymaga wskazania powodu. Sprawdź status hooka dla używanego narzędzia według lokalnej procedury.

Uruchom Brain z jego README i porównaj widok z plikami: nazwa, obszary, dokumenty i decyzje muszą pochodzić z rzeczywistych źródeł. Jeśli użytkownik prosi o pełną kontrolę ciągłości, w nowej sesji AI odczytaj ostatnią decyzję i następny krok oraz wskaż plik źródłowy. Test uruchomiony w tej samej rozmowie nie potwierdza przeniesienia kontekstu między sesjami.

Zwróć krótką tabelę: **element, wynik, dowód, działanie**. Odróżnij błąd, brak konfiguracji i brak potwierdzenia. Napraw lokalne, odwracalne usterki objęte prośbą i sprawdź dotknięty element ponownie. Nie modyfikuj publicznych szablonów danymi użytkownika.
