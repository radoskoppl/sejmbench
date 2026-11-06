# Basal wskazuje zwycięską stronę w 97.96% głosowań imiennych Sejmu

*Wyniki pełnego eksperymentu SejmBench (9B), 6 listopada 2026.*

Modele językowe coraz częściej mają opisywać rzeczywistość polityczną — ale rzadko ktoś sprawdza, jak dobrze potrafią ją **rozstrzygnąć**. SejmBench pyta wprost: znając listę głosów imiennych, czy model wskaże, która strona wygrała? Pełny wynik: **97.96%** trafień na 66 104 głosowaniach. Poprzeczka: 61.1%.

## Co mierzymy

SejmBench to benchmark na głosowaniach imiennych Sejmu, zbudowany wyłącznie na źródłach urzędowych — API Sejmu (dane mirror 66 427 głosowań z kadencji 3–10, lata 1997–2026). Ground truth jest wyliczany przez kod, nie przez człowieka ani żaden model: zwycięzca, jednomyślność, polaryzacja per klub, z zamrożonymi definicjami (CODEBOOK v0.3). Warstwa 0.1, którą tu oceniamy, to najprostsze pytanie możliwego benchmarku: **która strona wygrała** — ZA czy PRZECIW.

Do oceny kwalifikuje się 66 104 głosowań (241 odrzucono przez niespójne liczniki — dane zweryfikowane i opisane w rejestrze populacji).

## Kontrakt zamrożony przed runem

Całe badanie opiera się na zasadzie: definicje przed wynikami. Przed pierwszą próbą zamrozone zostały: populacja (hash `0b814f62…`), prompt (hash `e165643d…`, lista rekordów `klub | głos`), tożsamość modelu (rewizja wag `3c1e540f…`, bf16, silnik 2.5.2, GPU DGX Spark), polityka retry (jedna próba, błędy transportowe do trzech razy ten sam request, nigdy losowanie treści) oraz wersje scorera. Wynik różni się od tablicy wyników tym, że da się go **uruchomić offline i dostać identyczne liczby** — scorecard budujemy z surowych odpowiedzi bez udziału modelu.

## Wynik

| model | trafność zwycięzcy | 95% CI | n |
|---|---|---|---|
| typuj zawsze dominującą stronę | 61.1% | — | 66 104 |
| losowanie | 49.8% | — | 66 104 |
| **Basal (basal-omni-1.0-ultra, lokalnie)** | **97.96%** | **[97.85, 98.07]** | 66 104 |

Trafność per kadencja: 95.2% (kad. III), 98.5 (IV), 97.6 (V), 99.0 (VI), 99.3 (VII), 99.7 (VIII), 99.1 (IX), 94.9 (X). Dwa najniższe miejsca to nie przypadek: kadencja III to najstarsze dane (w tym głosowania z wartością głosu `NO_VOTE`), a kadencja X jest najbardziej spolaryzowana i najbardziej „kwestyjna" — tu model ma najwięcej realnej pracy.

Sam wynik nie mówi wiele bez poprzeczki: naiwny strateg „typuj dominującą stronę" zbiera 61.1%. Cała teza SejmBench jest taka, że **sam procent jest nic wart, dopóki nie ma baseline'u, przedziału ufności i sposobności powtórzenia**.

## Uczciwe zastrzeżenia

**Remisy.** W korpusie jest 37 głosowań remisowych (wg konwencji benchmarku: remis = zwycięstwo wcześniejszego seedu, czyli ZA). Basal trafił w 40.5% z nich — i nie wybrał opcji „remis" ani razu w 66 104 odpowiedziach. To najsłabszy segment wyniku, widoczny tylko dlatego, że raportujemy go osobno.

**Warstwa 0.2.** Model decyzyjny typu Basal nie emituje numerycznych estymacji per klub, więc warstwa spójności klubowej (yes_share, polaryzacja) ma pokrycie 0% i nie jest karana — zamiast tego oznaczamy ją jako *unsupported by typed API*. Wolimy zero pokrycia niż MAE wygenerowane na siłę.

**Kontaminacja.** Model może pamiętać historyczne głosowania z pretrainingu. Deklarujemy brak kontroli nad cutoff (`unknown`); właściwym zabezpieczeniem będzie split czasowy, którego mechanika jest już opisana w CODEBOOK §9. Dla kadencji sprzed kilkunastu lat ryzyko pamięci jest realne — uczciwy wynik cross-model przyjdzie razem z tym zabezpieczeniem.

## Dlaczego to nie jest koniec, tylko punkt wyjścia

Jeden model na własnym benchmarku to dowód koncepcji, nie tablica wyników. Ten sam zamrożony zbiór i kontrakt czeka na drugi model — wtedy dopiero pojawi się pierwsza prawdziwa porównywalność. Poza tym przed nami: walidacja warstwy 1 (typy głosowań ze słownika urzędowych formuł API) i backtest predykcyjny „historia ≤ T, przewidź podział T+1".

Wszystkie artefakty: repo `github.com/radoskoppl/sejmbench` (scorecard, surowe odpowiedzi, skrypt wykresu, CODEBOOK, rejestr populacji) oraz zbiór danych `huggingface.co/datasets/patrykorwat/sejm-votings` (30.5 mln rekordów głosów, pięć konfiguracji).

*Metoda: 66 104 pojedynczych zapytań, 0 błędów, 45.7 h, tokeny wejściowe max 5 949 (bez cięcia kontekstu), odpowiedzi: ZA 25 046 / PRZECIW 41 058.*
