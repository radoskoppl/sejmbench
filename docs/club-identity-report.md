# Club-identity overlap report (per term, terms 3-10)

Generated from `docs/club-identity-membership.json.gz` (30,626,109 vote rows, 62a17ece191e…; dates from `votings.jsonl`).
MP id is unique within a term, so membership sets are exact. `niez.`
(non-attached) is always its own canonical label — nothing is mapped
into it and it is never mapped into anything.

## Frozen classification rules

- **relay** — B continues A: `B.first <= A.last + 2` and jaccard ≥ 0.7.
- **alias** — same members concurrently: jaccard ≥ 0.99 with both spans ≥ 3 sittings.
- **split** — B splits from a persisting A: `|A∩B|/|B| ≥ 0.8`, `|B| < |A|`, overlapping spans.
- **absorbed** — informational majority continuation (`0.5 ≤ |A∩B|/|A| < 0.7`, time-adjacent).
- Pairwise rows with jaccard ≥ 0.5 are printed for audit; anything else is unrecorded.

The curated mapping lives in `docs/club-identity.json`; `verify` mode
recomputes every recorded relation from the snapshot.

## Term 3 — 19 labels

| label | MPs | divisions | sittings | first → last |
|---|---|---|---|---|
| `AWS` | 209 | 11801 | 1–119 | 1997-10-20 → 2001-09-18 |
| `MN` | 2 | 11 | 1–1 | 1997-10-20 → 1997-11-06 |
| `PSL` | 30 | 11801 | 1–119 | 1997-10-20 → 2001-09-18 |
| `ROP` | 8 | 5081 | 1–119 | 1997-10-20 → 2001-09-18 |
| `SLD` | 171 | 11801 | 1–119 | 1997-10-20 → 2001-09-18 |
| `UW` | 64 | 11801 | 1–119 | 1997-10-20 → 2001-09-18 |
| `niez.` | 58 | 11790 | 1–119 | 1997-10-20 → 2001-09-18 |
| `KPN-OP` | 7 | 1361 | 21–36 | 1998-06-18 → 1998-11-26 |
| `NK` | 7 | 2474 | 28–64 | 1998-09-16 → 1999-11-20 |
| `KPN-O` | 6 | 473 | 37–42 | 1998-12-03 → 1999-01-09 |
| `KPN-Ojcz` | 6 | 2796 | 43–81 | 1999-01-20 → 2000-06-30 |
| `PPS-RLP` | 3 | 2277 | 64–87 | 1999-11-17 → 2000-09-22 |
| `PP` | 7 | 8052 | 65–119 | 1999-12-01 → 2001-09-18 |
| `PRS` | 3 | 1230 | 69–81 | 2000-01-05 → 2000-06-30 |
| `ROP-PC` | 4 | 5500 | 73–112 | 2000-03-15 → 2001-07-06 |
| `KdP` | 8 | 2901 | 82–105 | 2000-07-12 → 2001-03-30 |
| `SKL` | 18 | 3700 | 105–119 | 2001-03-27 → 2001-09-18 |
| `Alternatyw` | 6 | 3642 | 106–119 | 2001-04-10 → 2001-09-18 |
| `PiS` | 18 | 1776 | 113–119 | 2001-07-18 → 2001-09-18 |

| kinds | pair | jaccard | cont A→B | cont B→A |
|---|---|---|---|---|
| split:Alternatyw | `AWS` × `Alternatyw` | 0.03 | 0.03 | 1.00 |
| split:KPN-O | `AWS` × `KPN-O` | 0.03 | 0.03 | 1.00 |
| split:KPN-OP | `AWS` × `KPN-OP` | 0.03 | 0.03 | 1.00 |
| split:KPN-Ojcz | `AWS` × `KPN-Ojcz` | 0.03 | 0.03 | 1.00 |
| split:NK | `AWS` × `NK` | 0.03 | 0.03 | 1.00 |
| split:PP | `AWS` × `PP` | 0.03 | 0.03 | 1.00 |
| split:PiS | `AWS` × `PiS` | 0.08 | 0.08 | 0.94 |
| split:SKL | `AWS` × `SKL` | 0.09 | 0.09 | 1.00 |
| coabsorbed | `AWS` × `niez.` | 0.13 | 0.15 | 0.53 |
| relay | `Alternatyw` × `KPN-O` | 0.71 | 0.83 | 0.83 |
| absorbed | `Alternatyw` × `KPN-OP` | 0.62 | 0.83 | 0.71 |
| relay | `Alternatyw` × `KPN-Ojcz` | 0.71 | 0.83 | 0.83 |
| absorbed | `Alternatyw` × `KdP` | 0.56 | 0.83 | 0.62 |
| coabsorbed | `Alternatyw` × `niez.` | 0.05 | 0.50 | 0.05 |
| relay | `KPN-O` × `KPN-OP` | 0.86 | 1.00 | 0.86 |
| relay | `KPN-O` × `KPN-Ojcz` | 1.00 | 1.00 | 1.00 |
| relay | `KPN-O` × `KdP` | 0.75 | 1.00 | 0.75 |
| coabsorbed | `KPN-O` × `niez.` | 0.05 | 0.50 | 0.05 |
| relay | `KPN-OP` × `KPN-Ojcz` | 0.86 | 0.86 | 1.00 |
| absorbed | `KPN-OP` × `KdP` | 0.67 | 0.86 | 0.75 |
| relay | `KPN-Ojcz` × `KdP` | 0.75 | 1.00 | 0.75 |
| coabsorbed | `KPN-Ojcz` × `niez.` | 0.05 | 0.50 | 0.05 |
| absorbed | `KdP` × `PRS` | 0.38 | 0.38 | 1.00 |
| coabsorbed | `KdP` × `niez.` | 0.08 | 0.62 | 0.09 |
| split:MN | `MN` × `niez.` | 0.03 | 1.00 | 0.03 |
| relay | `NK` × `PP` | 1.00 | 1.00 | 1.00 |
| split:NK | `NK` × `niez.` | 0.12 | 1.00 | 0.12 |
| split:PP | `PP` × `niez.` | 0.12 | 1.00 | 0.12 |
| split:PPS-RLP | `PPS-RLP` × `SLD` | 0.02 | 1.00 | 0.02 |
| split:PPS-RLP | `PPS-RLP` × `niez.` | 0.05 | 1.00 | 0.05 |
| coabsorbed | `PRS` × `ROP` | 0.22 | 0.67 | 0.25 |
| split:PRS | `PRS` × `niez.` | 0.05 | 1.00 | 0.05 |
| absorbed | `PiS` × `ROP-PC` | 0.10 | 0.11 | 0.50 |
| split:ROP-PC | `ROP` × `ROP-PC` | 0.50 | 0.50 | 1.00 |
| split:ROP | `ROP` × `niez.` | 0.14 | 1.00 | 0.14 |
| split:ROP-PC | `ROP-PC` × `niez.` | 0.07 | 1.00 | 0.07 |

## Term 4 — 23 labels

| label | MPs | divisions | sittings | first → last |
|---|---|---|---|---|
| `LPR` | 47 | 13589 | 1–109 | 2001-10-19 → 2005-08-29 |
| `PO` | 70 | 13589 | 1–109 | 2001-10-19 → 2005-08-29 |
| `PSL` | 49 | 13189 | 1–109 | 2001-10-19 → 2005-08-29 |
| `PiS` | 53 | 13589 | 1–109 | 2001-10-19 → 2005-08-29 |
| `SLD` | 208 | 13589 | 1–109 | 2001-10-19 → 2005-08-29 |
| `Samoobrona` | 57 | 13589 | 1–109 | 2001-10-19 → 2005-08-29 |
| `UP` | 20 | 13587 | 1–109 | 2001-10-19 → 2005-08-29 |
| `niez.` | 117 | 13589 | 1–109 | 2001-10-19 → 2005-08-29 |
| `SKL` | 8 | 11104 | 5–94 | 2001-11-21 → 2004-12-22 |
| `PLD` | 16 | 8560 | 18–99 | 2002-04-04 → 2005-03-22 |
| `ROP` | 3 | 11260 | 28–109 | 2002-08-29 → 2005-08-29 |
| `KN` | 5 | 764 | 34–38 | 2002-11-12 → 2002-12-20 |
| `PBL` | 6 | 7561 | 38–95 | 2002-12-17 → 2005-01-07 |
| `RKN` | 5 | 9984 | 39–109 | 2003-01-08 → 2005-08-29 |
| `PP` | 3 | 9832 | 40–109 | 2003-01-23 → 2005-08-29 |
| `PRS` | 5 | 1679 | 57–67 | 2003-09-16 → 2004-01-29 |
| `FKP` | 17 | 1907 | 67–79 | 2004-01-20 → 2004-07-16 |
| `PSL-PBL` | 43 | 400 | 71–72 | 2004-03-17 → 2004-04-02 |
| `SDPL` | 36 | 4536 | 72–109 | 2004-03-30 → 2005-08-29 |
| `D_OJCZYSTY` | 10 | 3952 | 74–109 | 2004-04-29 → 2005-08-29 |
| `KL` | 5 | 2321 | 95–109 | 2005-01-05 → 2005-08-29 |
| `SG` | 11 | 1910 | 99–109 | 2005-03-09 → 2005-08-29 |
| `RP` | 3 | 816 | 106–108 | 2005-06-28 → 2005-07-29 |

| kinds | pair | jaccard | cont A→B | cont B→A |
|---|---|---|---|---|
| split:D_OJCZYSTY | `D_OJCZYSTY` × `LPR` | 0.16 | 0.80 | 0.17 |
| split:PLD | `FKP` × `PLD` | 0.83 | 0.88 | 0.94 |
| absorbed | `FKP` × `SG` | 0.56 | 0.59 | 0.91 |
| coabsorbed | `FKP` × `Samoobrona` | 0.14 | 0.53 | 0.16 |
| split:FKP | `FKP` × `niez.` | 0.15 | 1.00 | 0.15 |
| split:KL | `KL` × `PO` | 0.07 | 1.00 | 0.07 |
| absorbed | `KL` × `SKL` | 0.62 | 1.00 | 0.62 |
| split:KN | `KN` × `LPR` | 0.11 | 1.00 | 0.11 |
| relay | `KN` × `RKN` | 1.00 | 1.00 | 1.00 |
| split:PP | `LPR` × `PP` | 0.06 | 0.06 | 1.00 |
| split:RKN | `LPR` × `RKN` | 0.11 | 0.11 | 1.00 |
| split:ROP | `LPR` × `ROP` | 0.06 | 0.06 | 1.00 |
| split:PBL | `PBL` × `PSL-PBL` | 0.14 | 1.00 | 0.14 |
| split:PBL | `PBL` × `Samoobrona` | 0.11 | 1.00 | 0.11 |
| split:PBL | `PBL` × `niez.` | 0.05 | 1.00 | 0.05 |
| split:SG | `PLD` × `SG` | 0.69 | 0.69 | 1.00 |
| coabsorbed | `PLD` × `Samoobrona` | 0.14 | 0.56 | 0.16 |
| split:PLD | `PLD` × `niez.` | 0.14 | 1.00 | 0.14 |
| split:SKL | `PO` × `SKL` | 0.11 | 0.11 | 1.00 |
| split:PP | `PP` × `niez.` | 0.03 | 1.00 | 0.03 |
| split:PRS | `PRS` × `Samoobrona` | 0.09 | 1.00 | 0.09 |
| split:PRS | `PRS` × `niez.` | 0.04 | 1.00 | 0.04 |
| split:PSL-PBL | `PSL` × `PSL-PBL` | 0.70 | 0.78 | 0.88 |
| coabsorbed | `ROP` × `niez.` | 0.02 | 0.67 | 0.02 |
| coabsorbed | `RP` × `Samoobrona` | 0.03 | 0.67 | 0.04 |
| split:RP | `RP` × `niez.` | 0.03 | 1.00 | 0.03 |
| split:SDPL | `SDPL` × `SLD` | 0.16 | 0.92 | 0.16 |
| split:SDPL | `SDPL` × `niez.` | 0.23 | 0.81 | 0.25 |
| split:SG | `SG` × `niez.` | 0.09 | 1.00 | 0.09 |
| split:UP | `UP` × `niez.` | 0.13 | 0.80 | 0.14 |

## Term 5 — 13 labels

| label | MPs | divisions | sittings | first → last |
|---|---|---|---|---|
| `LPR` | 36 | 3473 | 1–48 | 2005-10-19 → 2007-09-19 |
| `PO` | 138 | 3473 | 1–48 | 2005-10-19 → 2007-09-19 |
| `PSL` | 28 | 3473 | 1–48 | 2005-10-19 → 2007-09-19 |
| `PiS` | 170 | 3473 | 1–48 | 2005-10-19 → 2007-09-19 |
| `SLD` | 56 | 3473 | 1–48 | 2005-10-19 → 2007-09-19 |
| `Samoobrona` | 56 | 3473 | 1–48 | 2005-10-19 → 2007-09-19 |
| `niez.` | 34 | 3473 | 1–48 | 2005-10-19 → 2007-09-19 |
| `NKP` | 7 | 542 | 18–25 | 2006-05-23 → 2006-09-22 |
| `RLN` | 18 | 2185 | 26–48 | 2006-10-10 → 2007-09-19 |
| `RLCh` | 8 | 703 | 32–40 | 2007-01-10 → 2007-04-27 |
| `KPB` | 3 | 748 | 40–46 | 2007-04-24 → 2007-08-24 |
| `PR` | 6 | 578 | 40–45 | 2007-04-24 → 2007-07-10 |
| `Prawica` | 6 | 315 | 45–48 | 2007-07-04 → 2007-09-19 |

| kinds | pair | jaccard | cont A→B | cont B→A |
|---|---|---|---|---|
| split:KPB | `KPB` × `RLN` | 0.17 | 1.00 | 0.17 |
| split:KPB | `KPB` × `Samoobrona` | 0.05 | 1.00 | 0.05 |
| split:KPB | `KPB` × `niez.` | 0.09 | 1.00 | 0.09 |
| split:NKP | `LPR` × `NKP` | 0.19 | 0.19 | 1.00 |
| absorbed | `NKP` × `RLN` | 0.25 | 0.71 | 0.28 |
| split:NKP | `NKP` × `niez.` | 0.21 | 1.00 | 0.21 |
| split:PR | `PR` × `PiS` | 0.04 | 1.00 | 0.04 |
| alias | `PR` × `Prawica` | 1.00 | 1.00 | 1.00 |
| split:PR | `PR` × `niez.` | 0.14 | 0.83 | 0.15 |
| split:Prawica | `PiS` × `Prawica` | 0.04 | 0.04 | 1.00 |
| split:Prawica | `Prawica` × `niez.` | 0.14 | 0.83 | 0.15 |
| split:RLCh | `RLCh` × `RLN` | 0.44 | 1.00 | 0.44 |
| split:RLCh | `RLCh` × `niez.` | 0.24 | 1.00 | 0.24 |
| coabsorbed | `RLN` × `Samoobrona` | 0.16 | 0.56 | 0.18 |
| split:RLN | `RLN` × `niez.` | 0.49 | 0.94 | 0.50 |

## Term 6 — 14 labels

| label | MPs | divisions | sittings | first → last |
|---|---|---|---|---|
| `LiD` | 53 | 442 | 1–13 | 2007-11-05 → 2008-04-11 |
| `PO` | 240 | 8437 | 1–100 | 2007-11-05 → 2011-09-16 |
| `PSL` | 37 | 8437 | 1–100 | 2007-11-05 → 2011-09-16 |
| `PiS` | 186 | 8437 | 1–100 | 2007-11-05 → 2011-09-16 |
| `niez.` | 32 | 8437 | 1–100 | 2007-11-05 → 2011-09-16 |
| `DKP` | 3 | 3064 | 13–45 | 2008-04-10 → 2009-07-02 |
| `Lewica` | 49 | 5161 | 14–74 | 2008-04-25 → 2010-09-24 |
| `SDPL-NL` | 8 | 3343 | 14–48 | 2008-04-25 → 2009-08-28 |
| `Polska_XXI` | 6 | 2563 | 26–51 | 2008-10-21 → 2009-10-09 |
| `DKP_SD` | 3 | 4038 | 46–94 | 2009-07-16 → 2011-06-10 |
| `SDPL` | 4 | 4652 | 49–100 | 2009-09-09 → 2011-09-16 |
| `Polska_Plus` | 9 | 1648 | 52–74 | 2009-10-23 → 2010-09-24 |
| `SLD` | 48 | 2834 | 75–100 | 2010-10-08 → 2011-09-16 |
| `PJN` | 19 | 2673 | 78–100 | 2010-11-24 → 2011-09-16 |

| kinds | pair | jaccard | cont A→B | cont B→A |
|---|---|---|---|---|
| relay | `DKP` × `DKP_SD` | 1.00 | 1.00 | 1.00 |
| split:DKP | `DKP` × `LiD` | 0.06 | 1.00 | 0.06 |
| coabsorbed | `DKP` × `niez.` | 0.06 | 0.67 | 0.06 |
| absorbed | `DKP_SD` × `LiD` | 0.06 | 1.00 | 0.06 |
| coabsorbed | `DKP_SD` × `niez.` | 0.06 | 0.67 | 0.06 |
| relay | `Lewica` × `LiD` | 0.79 | 0.92 | 0.85 |
| relay | `Lewica` × `SLD` | 0.80 | 0.88 | 0.90 |
| absorbed | `LiD` × `SDPL` | 0.06 | 0.06 | 0.75 |
| absorbed | `LiD` × `SDPL-NL` | 0.15 | 0.15 | 1.00 |
| relay | `LiD` × `SLD` | 0.71 | 0.79 | 0.88 |
| split:PJN | `PJN` × `PiS` | 0.10 | 0.95 | 0.10 |
| split:Polska_Plus | `PiS` × `Polska_Plus` | 0.05 | 0.05 | 1.00 |
| split:Polska_XXI | `PiS` × `Polska_XXI` | 0.03 | 0.03 | 1.00 |
| absorbed | `Polska_Plus` × `Polska_XXI` | 0.67 | 0.67 | 1.00 |
| split:Polska_Plus | `Polska_Plus` × `niez.` | 0.24 | 0.89 | 0.25 |
| split:Polska_XXI | `Polska_XXI` × `niez.` | 0.15 | 0.83 | 0.16 |
| absorbed | `SDPL` × `SDPL-NL` | 0.33 | 0.75 | 0.38 |
| absorbed | `SDPL-NL` × `SLD` | 0.10 | 0.62 | 0.10 |
| coabsorbed | `SDPL-NL` × `niez.` | 0.14 | 0.62 | 0.16 |

## Term 7 — 13 labels

| label | MPs | divisions | sittings | first → last |
|---|---|---|---|---|
| `PO` | 235 | 6298 | 1–102 | 2011-11-08 → 2015-10-09 |
| `PSL` | 43 | 6298 | 1–102 | 2011-11-08 → 2015-10-09 |
| `PiS` | 163 | 6298 | 1–102 | 2011-11-08 → 2015-10-09 |
| `RP` | 44 | 3832 | 1–102 | 2011-11-08 → 2015-10-09 |
| `SLD` | 39 | 6298 | 1–102 | 2011-11-08 → 2015-10-09 |
| `SP` | 21 | 3639 | 1–71 | 2011-11-08 → 2014-07-11 |
| `niez.` | 78 | 6298 | 1–102 | 2011-11-08 → 2015-10-09 |
| `ID` | 4 | 619 | 45–56 | 2013-07-11 → 2013-12-12 |
| `TR` | 36 | 2451 | 51–87 | 2013-10-09 → 2015-02-20 |
| `KPSP` | 16 | 1164 | 72–88 | 2014-07-22 → 2015-03-05 |
| `BiG` | 11 | 779 | 77–86 | 2014-10-08 → 2015-02-06 |
| `ZP` | 16 | 1430 | 89–102 | 2015-03-20 → 2015-10-09 |
| `BC` | 4 | 755 | 96–102 | 2015-07-09 → 2015-10-09 |

| kinds | pair | jaccard | cont A→B | cont B→A |
|---|---|---|---|---|
| absorbed | `BC` × `TR` | 0.08 | 0.75 | 0.08 |
| coabsorbed | `BiG` × `PSL` | 0.12 | 0.55 | 0.14 |
| split:BiG | `BiG` × `RP` | 0.25 | 1.00 | 0.25 |
| split:BiG | `BiG` × `TR` | 0.31 | 1.00 | 0.31 |
| split:BiG | `BiG` × `niez.` | 0.14 | 1.00 | 0.14 |
| split:ID | `ID` × `PSL` | 0.09 | 1.00 | 0.09 |
| split:ID | `ID` × `RP` | 0.09 | 1.00 | 0.09 |
| absorbed | `KPSP` × `SP` | 0.54 | 0.81 | 0.62 |
| relay | `KPSP` × `ZP` | 0.88 | 0.94 | 0.94 |
| split:KPSP | `KPSP` × `niez.` | 0.21 | 1.00 | 0.21 |
| split:TR | `RP` × `TR` | 0.82 | 0.82 | 1.00 |
| split:RP | `RP` × `niez.` | 0.44 | 0.84 | 0.47 |
| absorbed | `SP` × `ZP` | 0.48 | 0.57 | 0.75 |
| split:SP | `SP` × `niez.` | 0.27 | 1.00 | 0.27 |
| split:TR | `TR` × `niez.` | 0.39 | 0.89 | 0.41 |
| split:ZP | `ZP` × `niez.` | 0.19 | 0.94 | 0.19 |

## Term 8 — 19 labels

| label | MPs | divisions | sittings | first → last |
|---|---|---|---|---|
| `Kukiz15` | 43 | 8157 | 1–86 | 2015-11-12 → 2019-10-16 |
| `N` | 32 | 7538 | 1–82 | 2015-11-12 → 2019-06-13 |
| `PO` | 147 | 6472 | 1–73 | 2015-11-12 → 2018-12-06 |
| `PSL` | 17 | 4951 | 1–58 | 2015-11-12 → 2018-02-08 |
| `PiS` | 278 | 8157 | 1–86 | 2015-11-12 → 2019-10-16 |
| `niez.` | 49 | 8157 | 1–86 | 2015-11-12 → 2019-10-16 |
| `WiS` | 6 | 6900 | 19–86 | 2016-05-19 → 2019-10-16 |
| `ED` | 4 | 521 | 26–32 | 2016-09-21 → 2016-12-15 |
| `UED` | 4 | 2538 | 32–58 | 2016-12-13 → 2018-02-08 |
| `Republikanie` | 3 | 949 | 37–47 | 2017-03-09 → 2017-09-15 |
| `PSL-UED` | 20 | 2831 | 59–83 | 2018-02-28 → 2019-07-04 |
| `L-S` | 3 | 844 | 65–71 | 2018-06-27 → 2018-11-09 |
| `TERAZ!` | 3 | 1747 | 72–86 | 2018-11-21 → 2019-10-16 |
| `W-S` | 3 | 881 | 72–78 | 2018-11-21 → 2019-03-15 |
| `PO-KO` | 160 | 1685 | 73–86 | 2018-12-05 → 2019-10-16 |
| `Konfederacja` | 7 | 853 | 79–86 | 2019-04-03 → 2019-10-16 |
| `PSL-KP` | 22 | 375 | 84–86 | 2019-07-17 → 2019-10-16 |
| `PP` | 3 | 175 | 85–86 | 2019-07-31 → 2019-10-16 |
| `UPR` | 4 | 175 | 85–86 | 2019-07-31 → 2019-10-16 |

| kinds | pair | jaccard | cont A→B | cont B→A |
|---|---|---|---|---|
| split:ED | `ED` × `PO` | 0.03 | 1.00 | 0.03 |
| absorbed | `ED` × `PSL-KP` | 0.13 | 0.75 | 0.14 |
| absorbed | `ED` × `PSL-UED` | 0.20 | 1.00 | 0.20 |
| alias | `ED` × `UED` | 1.00 | 1.00 | 1.00 |
| split:Konfederacja | `Konfederacja` × `Kukiz15` | 0.14 | 0.86 | 0.14 |
| absorbed | `Konfederacja` × `W-S` | 0.43 | 0.43 | 1.00 |
| split:Konfederacja | `Konfederacja` × `niez.` | 0.14 | 1.00 | 0.14 |
| split:PP | `Kukiz15` × `PP` | 0.07 | 0.07 | 1.00 |
| coabsorbed | `Kukiz15` × `Republikanie` | 0.05 | 0.05 | 0.67 |
| split:UPR | `Kukiz15` × `UPR` | 0.09 | 0.09 | 1.00 |
| split:W-S | `Kukiz15` × `W-S` | 0.07 | 0.07 | 1.00 |
| split:WiS | `Kukiz15` × `WiS` | 0.14 | 0.14 | 1.00 |
| split:L-S | `L-S` × `N` | 0.09 | 1.00 | 0.09 |
| relay | `L-S` × `TERAZ!` | 1.00 | 1.00 | 1.00 |
| split:L-S | `L-S` × `niez.` | 0.06 | 1.00 | 0.06 |
| split:TERAZ! | `N` × `TERAZ!` | 0.09 | 0.09 | 1.00 |
| coabsorbed | `N` × `niez.` | 0.35 | 0.66 | 0.43 |
| split:PO | `PO` × `PO-KO` | 0.83 | 0.95 | 0.87 |
| split:UED | `PO` × `UED` | 0.03 | 0.03 | 1.00 |
| coabsorbed | `PP` × `niez.` | 0.04 | 0.67 | 0.04 |
| absorbed | `PSL` × `PSL-KP` | 0.62 | 0.88 | 0.68 |
| absorbed | `PSL` × `PSL-UED` | 0.68 | 0.88 | 0.75 |
| relay | `PSL-KP` × `PSL-UED` | 0.83 | 0.86 | 0.95 |
| absorbed | `PSL-KP` × `UED` | 0.13 | 0.14 | 0.75 |
| absorbed | `PSL-UED` × `UED` | 0.20 | 0.20 | 1.00 |
| coabsorbed | `PiS` × `Republikanie` | 0.01 | 0.01 | 0.67 |
| coabsorbed | `PiS` × `WiS` | 0.01 | 0.01 | 0.50 |
| split:Republikanie | `Republikanie` × `niez.` | 0.06 | 1.00 | 0.06 |
| split:TERAZ! | `TERAZ!` × `niez.` | 0.06 | 1.00 | 0.06 |
| split:W-S | `W-S` × `niez.` | 0.06 | 1.00 | 0.06 |
| coabsorbed | `WiS` × `niez.` | 0.08 | 0.67 | 0.08 |

## Term 9 — 17 labels

| label | MPs | divisions | sittings | first → last |
|---|---|---|---|---|
| `KO` | 140 | 9389 | 1–81 | 2019-11-12 → 2023-08-30 |
| `Konfederacja` | 13 | 9389 | 1–81 | 2019-11-12 → 2023-08-30 |
| `Lewica` | 49 | 9382 | 1–81 | 2019-11-12 → 2023-08-30 |
| `PSL` | 30 | 7 | 1–1 | 2019-11-12 → 2019-11-22 |
| `PSL-Kukiz15` | 30 | 2565 | 1–21 | 2019-11-12 → 2020-11-28 |
| `PiS` | 247 | 9389 | 1–81 | 2019-11-12 → 2023-08-30 |
| `SLD` | 49 | 7 | 1–1 | 2019-11-12 → 2019-11-22 |
| `niez.` | 27 | 9389 | 1–81 | 2019-11-12 → 2023-08-30 |
| `KP` | 34 | 6817 | 21–81 | 2020-11-18 → 2023-08-30 |
| `Kukiz15` | 5 | 6318 | 26–81 | 2021-02-24 → 2023-08-30 |
| `Polska2050` | 8 | 6318 | 26–81 | 2021-02-24 → 2023-08-30 |
| `PS` | 4 | 5961 | 29–81 | 2021-05-04 → 2023-08-30 |
| `WP` | 3 | 7 | 34–34 | 2021-07-07 → 2021-07-08 |
| `Porozumienie` | 6 | 5010 | 36–79 | 2021-08-11 → 2023-07-13 |
| `PPS` | 3 | 2893 | 44–71 | 2021-12-14 → 2023-01-26 |
| `LD` | 3 | 1543 | 72–81 | 2023-02-07 → 2023-08-30 |
| `Wolnościowcy` | 3 | 1263 | 73–80 | 2023-03-07 → 2023-07-28 |

| kinds | pair | jaccard | cont A→B | cont B→A |
|---|---|---|---|---|
| split:Polska2050 | `KO` × `Polska2050` | 0.05 | 0.05 | 0.88 |
| split:Kukiz15 | `KP` × `Kukiz15` | 0.15 | 0.15 | 1.00 |
| coabsorbed | `KP` × `PS` | 0.06 | 0.06 | 0.50 |
| relay | `KP` × `PSL` | 0.88 | 0.88 | 1.00 |
| split:PSL-Kukiz15 | `KP` × `PSL-Kukiz15` | 0.88 | 0.88 | 1.00 |
| coabsorbed | `KP` × `Porozumienie` | 0.08 | 0.09 | 0.50 |
| split:Wolnościowcy | `Konfederacja` × `Wolnościowcy` | 0.23 | 0.23 | 1.00 |
| absorbed | `Kukiz15` × `PSL` | 0.17 | 1.00 | 0.17 |
| absorbed | `Kukiz15` × `PSL-Kukiz15` | 0.17 | 1.00 | 0.17 |
| split:Kukiz15 | `Kukiz15` × `niez.` | 0.19 | 1.00 | 0.19 |
| split:LD | `LD` × `Lewica` | 0.06 | 1.00 | 0.06 |
| relay | `LD` × `PPS` | 1.00 | 1.00 | 1.00 |
| absorbed | `LD` × `SLD` | 0.06 | 1.00 | 0.06 |
| split:PPS | `Lewica` × `PPS` | 0.06 | 0.06 | 1.00 |
| absorbed | `PPS` × `SLD` | 0.06 | 1.00 | 0.06 |
| absorbed | `PS` × `PSL` | 0.06 | 0.50 | 0.07 |
| absorbed | `PS` × `PSL-Kukiz15` | 0.06 | 0.50 | 0.07 |
| coabsorbed | `PS` × `PiS` | 0.01 | 0.50 | 0.01 |
| split:Porozumienie | `PiS` × `Porozumienie` | 0.02 | 0.02 | 1.00 |
| split:WP | `PiS` × `WP` | 0.01 | 0.01 | 1.00 |
| coabsorbed | `Polska2050` × `niez.` | 0.17 | 0.62 | 0.19 |
| coabsorbed | `Porozumienie` × `niez.` | 0.10 | 0.50 | 0.11 |
| coabsorbed | `WP` × `niez.` | 0.07 | 0.67 | 0.07 |
| coabsorbed | `Wolnościowcy` × `niez.` | 0.07 | 0.67 | 0.07 |

## Term 10 — 17 labels

| label | MPs | divisions | sittings | first → last |
|---|---|---|---|---|
| `KO` | 175 | 5451 | 1–69 | 2023-11-13 → 2026-11-19 |
| `Konfederacja` | 21 | 5451 | 1–69 | 2023-11-13 → 2026-11-19 |
| `Kukiz15` | 4 | 902 | 1–20 | 2023-11-13 → 2024-10-18 |
| `Lewica` | 29 | 5443 | 1–69 | 2023-11-13 → 2026-11-19 |
| `Nowa_Lewica` | 26 | 8 | 1–1 | 2023-11-13 → 2023-12-21 |
| `PSL` | 32 | 8 | 1–1 | 2023-11-13 → 2023-12-21 |
| `PSL-TD` | 33 | 5443 | 1–69 | 2023-11-13 → 2026-11-19 |
| `PiS` | 207 | 5451 | 1–69 | 2023-11-13 → 2026-11-19 |
| `Polska2050` | 34 | 2847 | 1–69 | 2023-11-13 → 2026-11-19 |
| `Polska2050-TD` | 34 | 2604 | 1–42 | 2023-11-13 → 2025-10-09 |
| `niez.` | 16 | 5206 | 7–69 | 2024-03-06 → 2026-11-19 |
| `Republikanie` | 4 | 2401 | 20–50 | 2024-10-16 → 2026-01-23 |
| `Razem` | 5 | 4508 | 21–69 | 2024-11-06 → 2026-11-19 |
| `Konfederacja_KP` | 3 | 3498 | 36–69 | 2025-06-03 → 2026-11-19 |
| `Demokracja` | 5 | 2140 | 50–69 | 2026-01-21 → 2026-11-19 |
| `Centrum` | 15 | 1958 | 52–69 | 2026-02-25 → 2026-11-19 |
| `RozwojPlus` | 41 | 955 | 63–69 | 2026-07-29 → 2026-11-19 |

| kinds | pair | jaccard | cont A→B | cont B→A |
|---|---|---|---|---|
| split:Centrum | `Centrum` × `Polska2050` | 0.44 | 1.00 | 0.44 |
| absorbed | `Centrum` × `Polska2050-TD` | 0.44 | 1.00 | 0.44 |
| relay | `Demokracja` × `Kukiz15` | 0.80 | 0.80 | 1.00 |
| split:Demokracja | `Demokracja` × `PiS` | 0.02 | 0.80 | 0.02 |
| split:Republikanie | `Demokracja` × `Republikanie` | 0.80 | 0.80 | 1.00 |
| coabsorbed | `Demokracja` × `niez.` | 0.17 | 0.60 | 0.19 |
| coabsorbed | `Konfederacja` × `Konfederacja_KP` | 0.09 | 0.10 | 0.67 |
| coabsorbed | `Konfederacja_KP` × `niez.` | 0.12 | 0.67 | 0.12 |
| split:Kukiz15 | `Kukiz15` × `PiS` | 0.02 | 1.00 | 0.02 |
| alias | `Kukiz15` × `Republikanie` | 1.00 | 1.00 | 1.00 |
| coabsorbed | `Kukiz15` × `niez.` | 0.11 | 0.50 | 0.12 |
| split:Nowa_Lewica | `Lewica` × `Nowa_Lewica` | 0.90 | 0.90 | 1.00 |
| split:Razem | `Lewica` × `Razem` | 0.17 | 0.17 | 1.00 |
| absorbed | `Nowa_Lewica` × `Razem` | 0.15 | 0.15 | 0.80 |
| split:PSL | `PSL` × `PSL-TD` | 0.97 | 1.00 | 0.97 |
| split:Republikanie | `PiS` × `Republikanie` | 0.02 | 0.02 | 1.00 |
| split:RozwojPlus | `PiS` × `RozwojPlus` | 0.20 | 0.20 | 1.00 |
| alias | `Polska2050` × `Polska2050-TD` | 1.00 | 1.00 | 1.00 |
| coabsorbed | `Republikanie` × `niez.` | 0.11 | 0.50 | 0.12 |

