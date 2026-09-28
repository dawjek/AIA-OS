---
name: poznaj-mnie
description: Użyj, gdy użytkownik chce doprecyzować swój profil, cele, preferencje współpracy z AI lub wrócić do niedokończonej rozmowy o sobie.
---

# Poznaj użytkownika

Odczytaj bieżące `05 Wiedza/Kontekst/wlasciciel.md` i `priorytety.md`, jeśli istnieją, oraz stan przerwanej konfiguracji. Pytaj o jedną niejasną grupę tematów naraz: rodzaj pracy, cele, ograniczenia, sposób komunikacji, poziom samodzielności AI i granice zapisu. Użytkownik może pominąć pytanie. Nie wnioskuj z pustego pola, że coś go nie dotyczy.

Po odpowiedzi rozdziel w zapisie: **potwierdzone przez użytkownika**, **propozycja asystenta** i **do ustalenia**. Aktualizuj prywatny profil lub priorytety, zachowując nowsze ustalenia. Dopisuj źródło i datę tylko gdy pomagają rozstrzygnąć późniejszy konflikt. Nie przenoś pytań ani osobistych odpowiedzi do publicznych szablonów lub README. Jeśli rozmowa jest częścią pierwszego startu, zaktualizuj `.ai/onboarding.local.md`, aby dało się ją wznowić.

Przeczytaj zapis z powrotem i pokaż użytkownikowi krótki obraz: co już wiesz, co jest tylko pomysłem, co pozostaje otwarte. Po zmianie źródła pamięci wykonaj `pamiec.py --root . build` oraz `status`; `ready` potwierdza pakiet, nie trafność Twojego podsumowania. Jeśli użytkownik prosi tylko o rozmowę lub odczyt, nie zapisuj plików bez jego zlecenia.
