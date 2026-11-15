# Layer 11 — English lower divisions and UEFA competitions Priority B identity review

**Queue entries:** `observed_competition_029`, `observed_competition_030`, `observed_competition_031`, `observed_competition_033`, `observed_competition_034`, `observed_competition_035`, `observed_competition_036`, `observed_competition_037`  
**Priority:** B — source-scoped provider identities  
**Disposition:** Official competition scope supported; provider mappings held

## Provider observations

| Queue entry | Competition | Provider | Competition ID | Season ID | Raw observations |
|---|---|---|---:|---|---:|
| `observed_competition_029` | League One | Bzzoiro | `86` | `86::1655` | 50 |
| `observed_competition_030` | League Two | Bzzoiro | `87` | `87::1674` | 48 |
| `observed_competition_031` | National League | Bzzoiro | `91` | `91::1903` | 50 |
| `observed_competition_033` | Conference League | OpenLigaDB | `6015` | `6015::2026` | 324 |
| `observed_competition_034` | Europa League | OpenLigaDB | `6000` | `6000::2026` | 432 |
| `observed_competition_035` | Nations League A | OpenLigaDB | `5978` | `5978::2026` | 144 |
| `observed_competition_036` | UEFA Champions League | OpenLigaDB | `4946`, `5997` | `4946::2026`, `5997::2026` | 528 total |
| `observed_competition_037` | UEFA Nations League | Bzzoiro | `64` | `64::1430` | 122 |

## English league candidates

The Bzzoiro records for League One, League Two and National League are plausible counterparts to the previously reviewed LiveScoreFootball records `observed_competition_023`, `observed_competition_024` and `observed_competition_025`. Official competition identity and tier match, but exact fixture crosswalks and provider season-ID equivalence have not been approved.

- **League One:** men's third tier, 24 clubs.
- **League Two:** men's fourth tier, 24 clubs.
- **National League:** men's fifth tier, 24 clubs (12 fixtures in a standard round).

Keep the Bzzoiro and LiveScoreFootball records separate pending exact fixture evidence.

## UEFA club competitions

1. **UEFA Champions League:** 36 clubs in the 2026/27 league phase; each plays eight opponents. Official UEFA regulations: https://documents.uefa.com/r/Regulations-of-the-UEFA-Champions-League-2026/27/Article-17-Match-system-league-phase-Online
2. **UEFA Europa League:** 36 clubs; each plays eight opponents. Official UEFA regulations: https://documents.uefa.com/r/Regulations-of-the-UEFA-Europa-League-2026/27/Article-17-Match-system-league-phase-Online
3. **UEFA Conference League:** 36 clubs; each plays six opponents. Official UEFA regulations: https://documents.uefa.com/r/Regulations-of-the-UEFA-Conference-League-2026/27/Article-17-Match-system-league-phase-Online

OpenLigaDB's Champions League record contains two distinct competition IDs, `4946` and `5997`. The reason for the split is not established. Do not merge the IDs or assume they are interchangeable.

## UEFA national-team competitions

- **Nations League A:** a men's national-team tier with 16 national teams divided into four groups of four. Official UEFA regulations: https://documents.uefa.com/r/Regulations-of-the-UEFA-Nations-League-2026/27/Article-13-Group-formation-league-phase-Online
- **UEFA Nations League:** the broad men's national-team competition spans Leagues A–D and 54 UEFA associations. Bzzoiro's broad competition record is not equivalent to OpenLigaDB's narrower League A record.

These are international national-team competitions, not club leagues. Keep them separate from club competitions and from one another.

## Decision and safeguards

All records remain source-scoped.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.
- Do not merge the two Champions League source IDs.
- Do not merge the broad UEFA Nations League with the narrower Nations League A.
- Do not merge Bzzoiro and LiveScoreFootball English league records until exact fixture evidence supports a reviewed crosswalk.

Next evidence needed: exact provider season metadata, precise semantics for both OpenLigaDB Champions League IDs, and exact fixture matching for the English league candidate pairs.