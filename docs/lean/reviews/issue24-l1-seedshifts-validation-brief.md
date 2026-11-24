# #24 L1 — seed shifts: podsumowanie prac do walidacji

> **Dla agenta-walidatora:** ten plik jest snapshotem stanu do walidacji.
> Wersja kanoniczna powinna trafić jako komentarz do issue #24.

## Cel etapu
Łańcuch `EligibleFlip ⇒ exact k ⇒ seed shifts ⇒ nActive`, zakończony pierwszym formalnym dowodem *efektu* kontrfaktycznej transformacji (nie tylko zachowania struktury danych).

## Commity podlegające walidacji
| Commit | Zakres |
|---|---|
| `4d86298` | EligibleFlip fixed (nil only on [], srcKind restored) |
| `7d84e00` | namespace Sejmbench restored |
| `eb5f5f6` | namespace na working module (7d84e00 + 434e03f proofs) |
| `010c315` | restore `flipFrom_length` (regresja z 4d86298) |
| `f9a37ff` | **nowy moduł `Sejmbench/SeedCount.lean`: seed shifts (N+1..N+4)** |

## Struktura dowodowa (Sejmbench/SeedCount.lean)

**N+1 — ogólne counting lematy** (`countOn P K d`: filtered count, P = stały predykat klubu):
- `countOn_cons` — krok kons z fixowanym predykatem
- `countOn_congr` — pointowo równe predykaty liczą się równo
- `countOn_flipAt_src` / `countOn_flipAt_dst` — nagłówek `sel` znika ze źródła / pojawia się w celu
- `countOn_cons_not` — nagłówek niespełniający (P, K) nie wpływa na liczbę
- **`countOn_src_flipFrom`** — Source' + k = Source, `k = selFrom S off d.length`, indukcja po `EligibleFlip`, gałąź `sel` używa `hs/hp/hsrc/hrest`
- **`countOn_dst_flipFrom`** — Target' = Target + k, pod `hdisjoint : ∀ k, srcKind k = true → dstKind k = false` i `hdst : dstKind lose = true`
- **`countOn_mid_flipFrom`** — Mid' = Mid (trzeci rodzaj głosu nietknięty)

**N+2 — most do seed totals**:
- `seedYes/seedNo/seedAbstain d = countOn (isTrack d) · d` — definicyjnie (`rfl`)
- `countOn_isTrack_flipFrom` — przez `countOn_congr` + `isTrack_flipFrom`: predykat `isTrack d` pozostaje STAŁY w trakcie transformacji
- rozłączność rodzajów: `isNoKind_of_isYesKind`, `isYesKind_of_isNoKind`, `isYesKind_of_isAbstainKind`, `isNoKind_of_isAbstainKind` (case analysis po 5 konstruktorach `VoteKind`)

**N+3/N+4 — cztery twierdzenia seed + ABSTAIN + nActive**:
- YES→NO: `seedYes_dec_of_eligible` (seedYes d' + k = seedYes d), `seedNo_inc_of_eligible` (seedNo d' = seedNo d + k), `seedAbstain_flip_no_of_eligible`, `nActive_flip_no_of_eligible` (kompozycja przez istniejący `nActive_of_seed_shifts`)
- NO→YES: `seedNo_dec_of_eligible`, `seedYes_inc_of_eligible`, `seedAbstain_flip_yes_of_eligible`, `nActive_flip_yes_of_eligible` (symetryczna kompozycja algebraiczna)

## Stan weryfikacji
- `lake build`: 12/12, zero błędów i warningów (Lean 4.36.0, core only, zero Mathlib)
- `#print axioms` (zweryfikowane lokalnie, 2026-11-24):
  - counting laws: `[propext, Quot.sound]`
  - seed/nActive twierdzenia: `[propext, Classical.choice, Quot.sound]`
  - **brak `sorryAx`** — sprawdzono na countOn, seedYes_eq_countOn, countOn_isTrack_flipFrom oraz wszystkich dziesięciu powyższych
- CI: push `f9a37ff` uruchomił workflow; oczekiwane green (lean-spec + test)

## Kryteria milestone (z ustaleń review) — status
| Kryterium | Status |
|---|---|
| Ogólny `countOn` | ✅ |
| Source count −k dokładnie | ✅ `countOn_src_flipFrom` |
| Target count +k dokładnie | ✅ `countOn_dst_flipFrom` |
| Fixed-track predicate bridge | ✅ `countOn_isTrack_flipFrom` |
| seedYes/seedNo YES→NO | ✅ |
| seedYes/seedNo NO→YES | ✅ |
| `#print axioms` bez sorryAx | ✅ (lokalnie; CI do potwierdzenia) |
| Pełny `lake build` + zielone CI | build ✅ lokalnie; CI do potwierdzenia na `f9a37ff` |

## Otwarte (poza tym etapem, wg ustaleń review)
1. **P0 — winner change**: kompozycja `EligibleFlip ⇒ k ⇒ seed shifts ⇒ winner change` z istniejącymi `winner_no_of_shift`/`winner_yes_of_shift`. Uwaga: `nActive_of_seed_shifts` i `seedYes_dec_of_eligible` opisują YES→NO; do kompozycji z winner lematami dobrać kierunek.
2. **P1 — most `flipped_record_indices ↔ S`** (mask ↔ Python) — osobne kryterium, nie blocker.
3. **L3** — struktura par i metryki (`CounterfactualV2`).

## Pułapki do weryfikacji (z tej sesji)
- `countOn_cons_not` wymaga postaci `¬((P r.club && K r.kind) = true)` (nie `= false`) — kształt dla `if_neg`.
- W gałęzi `sel` `countOn_mid_flipFrom` nie ma `h1` w scope — `selFrom_cons` musi iść we właściwej kolejności (pomocniczy `e0 : flipFrom (r::rest) S lose off = flipAt lose r :: …`).
- `simp [isNoKind] at h` na sprzecznym `h : isYesKind .no = true` robi `h : True` (zostawia cel); bezpieczna forma: `absurd h (by simp [isYesKind])` w postaci equation-lemmat.
- Rodzinne agenty edytują `FlipRecord.lean` — przed edycją pliku przeczytać świeżo; w `eb5f5f6` istniał niedokończony `filterLen_flipFrom` (usunięty przy wprowadzeniu `countOn`).
