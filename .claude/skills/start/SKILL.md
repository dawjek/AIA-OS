---
name: start
description: Użyj przy pierwszym otwarciu AIA-OS, prośbie o konfigurację folderu albo wznowieniu przerwanego onboardingu.
---

# Pierwsza konfiguracja AIA-OS

Prowadź krótką rozmowę i zapisuj odpowiedzi na bieżąco. Użytkownik może nie mieć firmy ani klientów. Instrukcja [START.md](../../../START.md) wyjaśnia mapę folderów, a publiczne `*.template.md` są wzorami. Dane użytkownika trafiają do osobnych, ignorowanych przez Git plików bez `.template`.

## Rozpoznaj stan

Sprawdź `.ai/onboarding.local.md`, prywatne pliki w `05 Wiedza/Kontekst/`, `.ai/memory.json` i faktyczny stan pamięci. Jeśli praca była przerwana, odczytaj także pliki zmienione po zapisanym postępie. Wznów od brakującej odpowiedzi; konflikt między dawną odpowiedzią a nowszym źródłem wyjaśnij przed zapisem. Nie nadpisuj istniejącej wiedzy szablonem.

## Rozmowa i zapis

Zapytaj kolejno, małymi porcjami, jak się zwracać do użytkownika, czym się zajmuje, jakie 1–3 cele są teraz ważne, jakie projekty i narzędzia już ma oraz jakiej samodzielności oczekuje od AI. Zapytaj, czego AI nie ma zapisywać lub robić samodzielnie. Nie proś o hasła i tokeny. Po każdej odpowiedzi zapisz postęp w `.ai/onboarding.local.md`: potwierdzone fakty, pytania otwarte, pliki zaktualizowane i następny krok. Jeśli użytkownik przerwie, podaj jedno zdanie, jak wznowić.

Na podstawie odpowiedzi utwórz z szablonów `wlasciciel.md`, `priorytety.md`, `mapa-pracy.md`, `stan-rozmowy.md`, `01 Zarząd/PORTFOLIO.md` i `01 Zarząd/Decyzje/DZIENNIK.md`. `firma.md` twórz tylko wtedy, gdy opis działalności jest potrzebny. Utwórz prywatne indeksy wiki oraz pusty lokalny `01 Zarząd/Autodiagnoza pracy AI/REJESTR.md`; `polaczenia.md` twórz tylko dla narzędzi, które użytkownik wskazał. W plikach kanonicznych nie zostawiaj fikcyjnych przykładów ani odpowiedzi udających fakty. Publicznych README nie personalizuj. Gdy istnieje realny projekt, użyj [podlacz-projekt](../podlacz-projekt/SKILL.md); folder klientów pozostaje pusty bez takiej potrzeby.

## Uruchom i sprawdź

Sprawdź dostępność Python 3.10+ oraz Node.js 22+. Skopiuj `.ai/memory.template.json` do prywatnego `.ai/memory.json` i `.ai/memory-projects.template.json` do prywatnego `.ai/memory-projects.json`. Dopasuj źródła pamięci do istniejących plików, ustaw `configured: true` dopiero po zapisaniu wymaganych źródeł. Uruchom `pamiec.py --root . build` i `status`, a następnie instalator hooka dla używanego narzędzia według [procedury pamięci](<../../../90 Zaplecze techniczne/procedury/pamiec.md>). Zachowaj inne ustawienia narzędzia. Gdy runtime jest niedostępny, zapisz konkretną blokadę; nie ogłaszaj gotowej pamięci.

Skopiuj `03 Nasza firma/Brain/brain.config.template.json` do prywatnego `brain.config.json`. Wpisz nazwę systemu, rzeczywiste obszary i istniejące ścieżki źródeł. Uruchom Brain według jego README i pokaż użytkownikowi profil, priorytety oraz mapę. Pusty ekran albo sama odpowiedź HTTP nie dowodzą poprawnej konfiguracji.

Ustal z użytkownikiem pierwsze małe zadanie. Zapisz faktyczny wynik, uzgodnioną decyzję i następny krok we właściwym źródle; dziennik decyzji stosuje nagłówek z datą `YYYY-MM-DD`. Zakończony etap utrwal według [instrukcji pamięci](../../../.ai/instructions/memory.md), potem przebuduj pakiet i sprawdź `status`. Poproś o próbę w **nowej sesji AI**: „Jaki jest mój aktualny cel i następny krok? Podaj źródło”. Zapisz wynik próby w `.ai/onboarding.local.md`. Dopóki jej nie sprawdzono, raportuj „gotowe do testu nowej sesji”, nie pełne zakończenie onboardingu.
