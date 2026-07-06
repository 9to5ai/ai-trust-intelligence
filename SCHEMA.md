# SCHEMA — data.json v2

`schemaVersion: 2`. **Every v2 field is optional** — the site renders v1 data
(no ids, free-text severity) with graceful fallback, and renders v2 data richer.
The nightly job should always emit full v2 (see `RESEARCH_SPEC.md`).

## Top level

```jsonc
{
  "schemaVersion": 2,
  "lastUpdated": "2026-07-06 05:10 AEDT",
  "projectName": "AI Trust Intelligence",
  "projectDescription": "…",
  "executiveBrief": { … },          // unchanged shape + soWhat on items
  "trustDashboard": { … },          // unchanged
  "risks": [ Risk ],
  "controls": [ Control ],
  "vendors": [ Vendor ],
  "regulations": [ Regulation ],
  "standards": [ Standard ],
  "incidents": [ Incident ],
  "securityWatch": { "summary", "items": [WatchItem], "advisories": [WatchItem] },
  "assuranceWatch": { "summary", "items": [WatchItem] },
  "australiaFocus": { … },          // unchanged
  "globalWatch": { … },             // unchanged
  "sources": [ Source ],
  "researchNotes": [ { "date", "title", "content" } ],
  "changelog": [ { "date", "title", "details" } ],
  "history": [ HistoryEntry ]       // NEW — append one per run, cap 120
}
```

## Common entity fields (on risks, regulations, standards, vendors, incidents, controls)

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable kebab-case slug, never changes (`au-app1-adm-transparency`). The canonical-entity key. |
| `firstSeen` | `YYYY-MM-DD` | When the entity entered the corpus. |
| `lastUpdated` | `YYYY-MM-DD` | Last substantive change. |
| `status` | `new \| updated \| unchanged` | Reset each run; drives "what changed" UI. |
| `soWhat` | string | One public-safe practice-lens sentence. |
| `archived` | boolean | Soft delete; site hides archived by default. |
| `reviewBy` | `YYYY-MM-DD` | Staleness horizon per RESEARCH_SPEC cadence. |

## Regulation

```jsonc
{
  "id": "au-app1-adm-transparency",
  "jurisdiction": "Australia",
  "title": "APP 1 automated decision-making transparency obligation",
  "stage": "enacted",                    // consultation | proposed | enacted | in-force | enforced | deferred
  "status": "updated", "firstSeen": "…", "lastUpdated": "…",
  "date": "2026-12-10",                  // primary reference date (kept for v1 compat)
  "summary": "…",
  "obligations": ["…"], "affected": ["…"],
  "timeline": "…",                       // prose retained
  "deadlines": [                          // NEW — structured; drives Horizon calendar
    { "date": "2026-12-10", "label": "Disclosure obligation commences",
      "audience": "All APP entities using ADM affecting rights or interests",
      "jurisdiction": "Australia" }
  ],
  "events": [                             // NEW — the entity's life; newest first
    { "date": "2026-06-15", "what": "OAIC consultation closed", "sourceUrl": "https://…" }
  ],
  "enforcementRisk": "…", "australiaRelevance": "…",
  "sources": ["https://…"], "soWhat": "…"
}
```

`stage` supersedes the free-text `status` field (which is retained for v1
compat but should no longer be written).

## Risk

```jsonc
{
  "id": "synthetic-media-fraud",
  "name": "Synthetic-media fraud and impersonation",
  "description": "…",
  "category": "…",                        // v1 free text, retained
  "theme": "Security",                    // NEW enum: Security | Governance | Regulation & Privacy |
                                          //           Safety & Trust | Operational | Societal | Other
  "likelihoodLevel": "High",              // NEW enum: Low | Medium | High | Very High
  "impactLevel": "High",                  // NEW enum (same)
  "likelihood": "…", "impact": "…",       // v1 free text, retained
  "rationale": "…",                        // NEW — why these levels; carries old free-text nuance
  "direction": "increasing",              // NEW enum: increasing | stable | decreasing
  "trend": "…",                            // v1, retained
  "velocity": "…", "affectedStakeholders": "…",
  "controls": ["Control name", …],        // v1 name strings, retained
  "relatedControlIds": ["ai-use-case-inventory"],   // NEW
  "relatedIncidentIds": ["…"],            // NEW
  "examples": ["…"], "confidence": "High",
  "sources": ["…"], "soWhat": "…"
}
```

## Source

As v1 (title, author, institution, date, link, sourceType, geography, domain,
priority, confidence, summary, keyFacts, keyClaims, evidenceBase, methodology,
practicalImplications, whoAffected, auRelevance …) with:

- `evidenceGrade`: **single letter** `A | B | C | D` per the RESEARCH_SPEC
  rubric. Explanations go in `evidenceBase`, never appended to the grade.
- `id`, `firstSeen`, `status` as common fields.

## HistoryEntry (NEW)

```jsonc
{ "date": "2026-07-06", "riskPosture": "Moderately elevated",
  "counts": { "risks": 104, "regulations": 25, "incidents": 31, "sources": 187 },
  "newItems": 6, "updatedItems": 9 }
```

## Executive brief items

`topDevelopments[]`, `criticalAlerts[]` gain optional `soWhat` and
`relatedIds: ["au-app1-adm-transparency"]` so the brief can deep-link into the
registers.

## Invariants the job must keep

1. One real-world instrument/risk/vendor = one record (`events[]` grows, the
   arrays don't).
2. `deadlines[].date` is always `YYYY-MM-DD`; passed deadlines are pruned or
   annotated via `events[]`.
3. `history[]` grows by exactly one entry per run; cap 120 (drop oldest).
4. Never emit two records whose normalized titles match (case/punctuation-insensitive).
5. All v1 fields keep their meaning — the site must keep rendering old backups.
