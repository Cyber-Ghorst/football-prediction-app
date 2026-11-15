# Layer 11 — Parva Liga 2026/27 Priority B identity review

**Queue entry:** `observed_competition_013`  
**Provider:** Bzzoiro  
**Provider competition ID:** `22`  
**Provider season ID:** `22::1326`  
**Provider season label:** `Parva Liga 26/27`  
**Raw provider observations in the intake snapshot:** 5  
**Disposition:** Official competition identity and season context supported; provider scope and season-ID semantics unverified

## Official Bulgarian Football Union evidence

1. The BFU's official 2026/27 regulations identify the First Professional League as Bulgaria's men's first tier with **14 professional clubs**. Article 2 specifies the two-phase competition: a home-and-away first phase, followed by three groups (places 1–4, 5–8, and 9–14): https://bfunion.bg/uploads/2026-06-24/naredba-za-parvenstavata-26-27.pdf
2. The BFU's official news index records publication of the efbet Liga 2026/2027 calendar on 11 June 2026: https://www.bfunion.bg/Новини?page=1
3. The BFU maintains an official national competition calendar portal, including efbet Liga: https://bfunion.bg/календар

## Provider evidence

The intake queue contains one source-scoped Bzzoiro record:

| Field | Value |
|---|---|
| Competition name | Parva Liga |
| Country | Bulgaria |
| Provider competition ID | `22` |
| Provider season ID | `22::1326` |
| Provider season label | Parva Liga 26/27 |
| Raw observations | 5 |

No independent provider record is currently attached to this exact country-scoped identity in the Priority B queue. The sample is too small to establish roster completeness or exact fixture corroboration.

## Assessment

- Competition identity: **externally supported** as Bulgaria's men's first-tier professional league.
- Season context: **2026/27 externally supported** by the BFU regulations and official calendar announcement.
- Official team count: **14**.
- Official competition format: **two phases**, with the 14 clubs split after the first phase into groups 1–4, 5–8, and 9–14.
- Provider sample: **5 observations**, one provider only.
- Full provider roster and season-ID equivalence: **not established**.
- Cross-provider fixture corroboration: **not available**.

## Decision and safeguards

Retain the Bzzoiro record as source-scoped. External evidence supports the competition identity, but does not prove that provider competition ID `22` and season ID `22::1326` are a complete and correct 2026/27 representation.

- Canonical competition/season/team mappings: **not approved**.
- Provider links and fixture ingestion: **unchanged and disabled**.
- Prediction eligibility: **unchanged and disabled**.

Next evidence needed: a broader provider roster and fixture sample, provider-specific season metadata, and independent provider observations. Do not infer missing clubs from a five-observation sample.