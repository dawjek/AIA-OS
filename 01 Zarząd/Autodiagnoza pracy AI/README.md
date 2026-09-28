# Korekty pracy AI

Zapisuj tu istotną pomyłkę lub uwagę, która zmieni sposób pracy: co się stało, jaki był dowód, co poprawiono i czy poprawka zadziałała. Zwykłe udane kroki nie potrzebują osobnego wpisu. Onboarding tworzy pusty prywatny rejestr z [wzoru](REJESTR.template.md).

Z głównego folderu uruchom `python3 "90 Zaplecze techniczne/narzedzia/autodiagnoza.py" --root . enqueue --input -`; na Windows użyj `py -3`. Wejściowy JSON ma pola `event_id`, `observation`, `evidence` i `correction`. Komenda `list` pokazuje wpisy oczekujące oraz ich rewizje. Po sprawdzeniu skutku `record --input -` zapisuje wpis do prywatnego `REJESTR.md`; JSON zawiera `event_id`, `expected_revision` z listy i `outcome`. Skrypt potwierdza odczyt rejestru i zachowuje poprzednią wersję. Cały obieg działa lokalnie, bez usługi chmurowej.
