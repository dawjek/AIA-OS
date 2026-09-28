# AIA-OS

Polski starter do prowadzenia własnej pracy z pomocą AI. Otwierasz folder w Codexie lub Claude Code, opowiadasz o swojej pracy i celach, a asystent zapisuje kontekst, porządkuje projekty i uruchamia lokalny kokpit. Możesz korzystać z niego także wtedy, gdy nie masz firmy ani klientów.

To **wersja testowa do samodzielnego wypróbowania**. Pełny pierwszy przebieg sprawdzono w Codexie na Macu; nie przeprowadzono jeszcze odbioru przez niezależnego użytkownika ani pełnej próby onboardingu w Claude Code.

## Pierwsze uruchomienie

1. Pobierz ZIP i rozpakuj go albo sklonuj repozytorium. Otwórz **główny folder AIA-OS** w Codexie lub Claude Code. Samo wklejenie linku do czatu nie da asystentowi dostępu do plików na Twoim komputerze.
2. Wklej do asystenta: **„Przeczytaj START.md w tym folderze i przeprowadź mnie przez pierwszą konfigurację. Zapisuj postęp, żebym mógł wrócić do rozmowy później.”**
3. Odpowiedz na krótkie pytania. Asystent utworzy Twoje prywatne pliki, skonfiguruje pamięć i pokaże kokpit. Możesz przerwać w dowolnym momencie; przy powrocie poproś: „Wznów konfigurację AIA-OS”.
4. Na koniec rozpocznij nową sesję AI i zapytaj o zapisany cel oraz następny krok. To sprawdza, czy kontekst rzeczywiście wraca.

Jeżeli narzędzie wykryło lokalne skille, możesz wywołać `start` przez `$start` w Codexie lub `/start` w Claude Code. Polecenie zwykłym językiem z kroku 2 działa także wtedy, gdy skill nie pojawił się jeszcze w interfejsie.

## Co jest w paczce

Sześć folderów porządkuje zarządzanie pracą, klientów, własną działalność, warsztat, wiedzę i zaplecze techniczne. Są w nich neutralne instrukcje i szablony. Nie ma przykładowych klientów ani gotowych faktów o Tobie. Sześć własnych polskich skilli prowadzi przez start, poznanie użytkownika, podłączenie projektu, kontrolę systemu, jedno usprawnienie i kokpit.

Brain działa lokalnie w przeglądarce: ma pełnoekranową, obracaną mapę dokumentów i osobny kokpit stanu pracy. Pamięć składa mały pakiet z wybranych plików i pomaga wrócić do ustaleń. Żadne z tych narzędzi nie zastępuje zapisu decyzji i stanu pracy przez asystenta.

## Wymagania

Do czytania instrukcji wystarczy Codex lub Claude Code z dostępem do tego folderu. Do działania pamięci potrzebny jest **Python 3.10 lub nowszy**, a do kokpitu **Node.js 22 lub nowszy**. Nie trzeba zakładać zewnętrznej bazy ani dodawać klucza API dla tych dwóch funkcji. Kod przygotowano także do uruchomienia z natywnym Pythonem i Node.js na Windows; pełna zgodność wymaga jeszcze próby na komputerze z Windows.

Brain uruchomisz po konfiguracji, otwierając terminal w `03 Nasza firma/Brain` i wpisując `npm start`. Mapa jest pod adresem [http://127.0.0.1:4173/](http://127.0.0.1:4173/), a osobny kokpit pod [http://127.0.0.1:4173/kokpit](http://127.0.0.1:4173/kokpit). Aplikacja nie wymaga instalowania pakietów przez `npm install`.

Jeśli asystent zgłosi, że jego środowisko blokuje zapis ustawień pamięci lub uruchomienie kokpitu, otwórz zwykły terminal na swoim komputerze w **głównym folderze AIA-OS**. Zainstaluj lokalny start pamięci dla używanego narzędzia:

```text
python3 "90 Zaplecze techniczne/narzedzia/instaluj-pamiec.py" --root . --runtime codex install
```

Zamień `codex` na `claude`, jeśli używasz Claude Code; na Windows zamień `python3` na `py -3`. Potem uruchom kokpit zgodnie z akapitem wyżej. Instalacja wpisu nie potwierdza jeszcze, że narzędzie AI go wykonało; sprawdź to pytaniem w nowej sesji z kroku 4.

## Twoje dane

Pliki z dopiskiem `.template` są publicznym wzorem. Onboarding tworzy z nich osobne pliki bez tego dopisku, na przykład `wlasciciel.md` z `wlasciciel.template.md`. Własny profil, cele, projekty, decyzje, rejestr połączeń i konfiguracje powstałe po starcie są ignorowane przez Git. Publicznych `README.md` i szablonów nie wypełniaj danymi osobistymi. Przed udostępnieniem kopii folderu zawsze sprawdź jej zawartość, także pliki ignorowane przez Git.

Pierwszą trasę po folderze i stan konfiguracji opisuje [START.md](START.md). Gdy coś przerwiesz, wróć do tego samego folderu: asystent powinien odczytać zapisany postęp i aktualne pliki, zanim zada następne pytanie.

Przed zmianą wersji zachowaj kopię całego folderu, także plików ignorowanych przez Git. Krótką procedurę aktualizacji i odzyskania danych znajdziesz w [zapleczu technicznym](<90 Zaplecze techniczne/procedury/aktualizacja.md>).

Własny kod i instrukcje AIA-OS są udostępnione na [licencji MIT](LICENSE).
