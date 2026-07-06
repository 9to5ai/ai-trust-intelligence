# RESEARCH_SPEC — the nightly monitor's contract

This file is the operating contract for the nightly research job that maintains
`data.json`. Wire it into the job's prompt verbatim. The companion `SCHEMA.md`
defines the exact JSON shapes; this file defines **what to gather, what to skip,
and the disciplines that keep the corpus trustworthy**.

The product this feeds is a public-safe intelligence terminal read by both the
practice and (eventually) clients. Every rule below exists because its absence
was observed to degrade the corpus: duplicate entities, vendor-PR skew,
uncited claims, free-text severity with no discriminating power, and hard
compliance deadlines buried in prose.

---

## 1. What to gather, in priority order

Work the tiers top-down each night. A short night should still cover Tier 1.

### Tier 1 — primary regulators & obligations (daily)
| Beat | Sources | What matters |
|---|---|---|
| Australia — prudential/markets | APRA, ASIC | AI/model-risk guidance, CPS 230/234 touchpoints, letters to industry, enforcement, REP follow-ups |
| Australia — privacy/ADM | OAIC | APP 1 ADM transparency (10 Dec 2026), Privacy Act reform tranches, guidance, determinations |
| Australia — online safety & gov | eSafety, DTA, DISR, ACSC | Codes/notices (incl. SMMA), AI-in-government policy, voluntary/mandatory guardrails, cyber advisories on AI |
| Australia — sectoral | TGA (health AI/SaMD), ACCC | Sector rules that create assurance work |
| EU | AI Office, EUR-Lex, EDPB | Implementing/delegated acts, GPAI Code of Practice, Digital Omnibus timing, guidance, first enforcement |
| US | NIST/CAISI, FTC, state legislatures (CO, CA, TX, IL, UT, NY) | Framework updates, enforcement, effective dates and amendments/delays |
| UK | DSIT/AISI, ICO | Evaluation guidance, AI regulation direction, ADM/privacy intersection |

### Tier 2 — standards, certification & security (2–3× week)
- **ISO/IEC JTC 1/SC 42 pipeline**: 42001 (AIMS), 42005 (impact assessment), 42006 (cert-body requirements), 23894, 24027/24028 — ballots, publications, revisions.
- **Accreditation market**: UKAS, ANAB, JAS-ANZ, IAF — who can certify 42001, scheme rules, first accreditations. This is the assurance market's plumbing; track it like a market feed.
- **Security frameworks**: OWASP GenAI/LLM Top 10 + Agentic Security Initiative, MITRE ATLAS new techniques/case studies, NIST AI security profiles.
- **Vulnerabilities**: CVEs and advisories in AI tooling and the agent stack (MCP, orchestrators, vector DBs, inference servers). Concrete CVE IDs, affected versions.

### Tier 3 — incidents, enforcement & litigation (2–3× week)
- **Incidents**: AI Incident Database, AVID, quality journalism. Log only with a named failure mode and a lesson; skip "AI said something weird" filler.
- **Enforcement & litigation tracker**: court decisions, regulator penalties, consent orders, class actions touching AI (privacy, IP, consumer, safety). These become case-study material — cite the filing or judgment, not a hot take.
- **Insurance/liability signals**: AI exclusions or affirmative cover, actuarial notes — early markers of how risk gets priced.

### Tier 4 — capability & assurance ecosystem (weekly)
- **Frontier-lab safety artifacts only**: system cards, model cards, RSP/Frontier-Safety-Framework changes, eval results, incident disclosures. A model launch is in scope only for its safety/assurance content; product marketing is not.
- **Evals & tooling releases**: inspect_ai, garak, PyRIT, promptfoo, Giskard — releases and new probe/eval classes, with what they let an assurer test.
- **Assurance market moves**: Big-4 AI assurance offerings, GRC platforms (Vanta, Drata, OneTrust, Holistic AI, Credo AI), methodology publications.
- **Content provenance**: C2PA adoption, watermarking mandates.

### Out of scope (do not gather)
Funding rounds without an assurance angle; benchmark horse-races; model-launch
hype; opinion pieces that cite no primary material; anything already fully
captured on an existing entity with no new fact.

---

## 2. Source quality rules (hard constraints)

1. **Evidence grade rubric** — grade the *source*, not the story. Single letter only.
   - **A** — primary text: the regulation, judgment, standard, regulator letter, official notice.
   - **B** — reputable secondary: quality journalism, law-firm analysis, academic work, established institutes.
   - **C** — interested party: vendor/lab blogs and announcements, analyst notes, Wikipedia (background only).
   - **D** — unverified: social posts, single-sourced claims. Rarely worth storing.
2. **Quotas per nightly run** (on *newly added* sources):
   - ≤ 20% grade C vendor/lab material. If the night's news is vendor-dominated, say so in the changelog rather than padding.
   - ≥ 30% Australia-relevant across the run (the practice's home market).
   - Wikipedia is never graded above C and never the sole source for a claim.
3. **Every executive-brief item cites at least one grade-A or grade-B source.**
4. **Institution diversity**: no single institution may contribute more than 15% of the total source base. When a lab's own posts dominate, seek the primary document they reference instead.

---

## 3. Canonical-entity discipline (the anti-sprawl rule)

**Before adding any regulation, risk, standard, vendor, or incident: search
existing `id`s and titles for the same real-world thing.** The corpus tracks
*entities that evolve*, not a news wire.

- If the entity exists → append an entry to its `events[]`
  (`{date, what, sourceUrl}`), update `lastUpdated`, `stage`, `deadlines`,
  `soWhat`, and set `status: "updated"`. **Never create a sibling record.**
- If genuinely new → create it with a stable kebab-case `id`
  (e.g. `au-app1-adm-transparency`, `eu-ai-act`), `firstSeen` = today,
  `status: "new"`.
- One instrument = one record. A consultation, its guidance, and its
  commencement are **events on one obligation**, not three regulations.
  (Observed failure: APP 1 ADM appeared as ~8 records; the EU AI Act as ~6.)
- Risks are consolidated the same way: "synthetic-media fraud" is one risk that
  accumulates examples, not a new risk per incident.

## 4. Delta discipline (answer "what changed today?")

- Nightly, reset every entity's `status` to `unchanged`, then mark only the
  touched ones `new` / `updated`.
- Maintain `firstSeen` and `lastUpdated` (ISO dates) on every entity.
- Append one `history[]` entry per run:
  `{date, riskPosture, counts: {risks, regulations, incidents, sources}, newItems, updatedItems}` — cap at 120 entries.
- The changelog entry must name the entities touched (ids), not just themes.

## 5. Deadline discipline (the compliance calendar)

Any date with a compliance consequence must be captured as structured data on
its regulation — never only in prose:

```json
"deadlines": [
  { "date": "2026-12-10", "label": "APP 1 ADM disclosure obligation commences",
    "audience": "All APP entities using ADM affecting rights", "jurisdiction": "Australia" }
]
```

Include consultation closes, commencement dates, enforcement start dates,
transition endings. Remove or annotate deadlines that pass or get deferred
(deferral = an `events[]` entry + updated deadline, same entity).

## 6. Scoring discipline (make severity mean something)

- `likelihoodLevel` and `impactLevel` are enums: `Low | Medium | High | Very High`.
  Free-text nuance goes in `rationale`.
- **Calibration rule**: not everything is High/High-and-rising. Each run,
  re-check: if >50% of risks sit in one matrix cell, or >80% share one trend,
  re-score against relative anchors before writing. Reserve `Very High` impact
  for plausible existential/regulatory-shutdown/major-harm outcomes.
- `direction`: `increasing | stable | decreasing` — justified by an event from
  this cycle, otherwise leave as-is.

## 6b. Control taxonomy discipline

Every control carries `nistFunction` (NIST AI RMF: GOVERN/MAP/MEASURE/MANAGE)
and `iso42001Area` (ISO/IEC 42001 Annex A area — see SCHEMA.md for the exact
labels). Classify new controls on creation; when unsure, match against the
rules in `classify_controls.py`. Controls are entities too: near-duplicate
controls ("AI use-case inventory and risk tiering" vs "AI system inventory and
risk tiering") get merged under the canonical-entity rule, not accumulated.

**Reference control libraries to mine when adding controls** (cite the source
on the control): ISO/IEC 42001 Annex A / B; NIST AI RMF Playbook actions;
CSA AI Controls Matrix (AICM); OWASP LLM Top 10 + Agentic Top 10 mitigations;
MITRE ATLAS mitigations; NIST SP 800-53 AI overlays as they land. Prefer
adapting a recognized control to inventing one.

## 7. The practice lens (`soWhat`)

Every brief item, regulation, and risk carries `soWhat`: **one sentence, public-safe**, phrased as what a competent organisation should do — an evidence artifact to
produce, a control to test, a question a board should ask. No client names, no
internal pricing/pipeline language. Example: *"Boards should ask for the ADM
inventory and the December disclosure draft now — the OAIC guidance lands
September."*

## 8. Staleness & pruning (the register must shrink too)

Mirror the Assurance Brain review cadence: regulations re-verified every 30
days; tools/vendors/market every 60; frameworks, standards and case-studies
every 90. On each run: items past review get re-checked (update `lastUpdated`)
or `archived: true` with a one-line reason. Superseded risks are merged, not
left to rot. Target steady state: a register a practitioner can read end-to-end.

## 9. Self-audit (write it into the changelog)

End each run with three honest lines in the changelog entry:
1. Source mix this run (grades, % vendor, % AU).
2. Entities merged/archived (anti-sprawl work done).
3. Known gaps — what the run looked for and could not confirm.

---

## Appendix — recommended watchlist additions (for `wiki/sources/watchlist.md`, applied via /scan workflow, not by this job)

- MITRE ATLAS (currently `last_checked: never`) — biweekly.
- Courts/enforcement: AustLII + major AI litigation trackers — biweekly.
- Insurance: ICA/underwriter AI liability notes — monthly.
- ACSC advisories (AI-relevant) — biweekly; TGA SaMD/AI guidance — monthly.
- C2PA / content-provenance adoption — monthly.
- JAS-ANZ (AU/NZ accreditation of 42001 cert bodies) — monthly.
