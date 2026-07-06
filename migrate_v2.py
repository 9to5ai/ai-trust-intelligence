#!/usr/bin/env python3
"""One-time migration of data.json to schema v2 (see SCHEMA.md).

- Backs up data.json to data.backup-YYYYMMDD.json first.
- Merges duplicate regulation records into canonical entities with events[].
- Dedupes sources (normalized title+institution, keeps richest) and risks.
- Normalizes risk severity/trend into enums; adds theme + rationale.
- Adds stable ids, structured deadlines, stage; seeds history[].
- Idempotent: running on already-migrated data makes no further changes.
"""
import json, re, shutil, sys, unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data.json"
TODAY = "2026-07-06"  # data as-of date; deadlines strictly after this are "upcoming"

# ── helpers ──────────────────────────────────────────────────────────────
def slugify(s, prefix=""):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)[:60].strip("-")
    return (prefix + s) if s else prefix + "item"

def norm_title(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()

def richness(rec):
    n = 0
    for v in rec.values():
        if isinstance(v, str): n += len(v)
        elif isinstance(v, list): n += sum(len(str(x)) for x in v)
    return n

def norm_level(v):
    s = str(v or "").lower()
    if not s: return None
    if any(k in s for k in ("very high", "critical", "almost certain", "confirmed", "established", "severe")): return "Very High"
    if "high" in s or "likely" in s: return "High"
    if "medium" in s or "moderate" in s or "possible" in s: return "Medium"
    if "low" in s or "rare" in s or "unlikely" in s: return "Low"
    return "Medium"

def norm_direction(v):
    s = str(v or "").lower()
    if s.startswith("increas") or "rising" in s or "growing" in s: return "increasing"
    if s.startswith("decreas") or "easing" in s or "declining" in s: return "decreasing"
    if "stable" in s or "steady" in s: return "stable"
    return None

def theme_of(cat):
    s = str(cat or "").lower()
    if re.search(r"secur|cyber|threat|supply|vulnerab|attack", s): return "Security"
    if re.search(r"regul|compliance|legal|privacy|copyright|liabilit", s): return "Regulation & Privacy"
    if re.search(r"govern|oversight|accountab|assurance|audit|transparen", s): return "Governance"
    if re.search(r"safety|trust|ethic|misinform|deepfake|harm|bias|fairness", s): return "Safety & Trust"
    if re.search(r"societ|social|labour|labor|employ|environment|workforce", s): return "Societal"
    if re.search(r"operat|reliab|perform|technical|concentrat|model", s): return "Operational"
    return "Other"

def stage_of(status_text):
    s = str(status_text or "").lower()
    if "defer" in s or "postpon" in s: return "deferred"
    if "enforce" in s: return "enforced"
    if "in force" in s or "in effect" in s or "effective" in s or "applied" in s or "active" in s or "commenc" in s: return "in-force"
    if "enact" in s or "passed" in s or "issued" in s or "final" in s or "published" in s: return "enacted"
    if "consult" in s: return "consultation"
    if "proposed" in s or "draft" in s or "bill" in s or "pending" in s: return "proposed"
    return "enacted"

MONTHS = {m.lower(): i for i, m in enumerate(
    ["January","February","March","April","May","June","July","August","September","October","November","December"], 1)}

def extract_dates(text):
    """Yield (iso_date, context) for explicit day-level dates in text."""
    out = []
    for m in re.finditer(r"(\d{4})-(\d{2})-(\d{2})", text):
        out.append((m.group(0), text[max(0, m.start()-70):m.end()+70]))
    for m in re.finditer(r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})", text, re.I):
        iso = f"{m.group(3)}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
        out.append((iso, text[max(0, m.start()-70):m.end()+70]))
    for m in re.finditer(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})", text, re.I):
        iso = f"{m.group(3)}-{MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
        out.append((iso, text[max(0, m.start()-70):m.end()+70]))
    return out

# ── curated regulation clusters (by normalized-title match) ─────────────
# canonical id -> (canonical title, jurisdiction, member title fragments)
CLUSTERS = {
    "eu-ai-act": ("EU Artificial Intelligence Act (Regulation 2024/1689)", "European Union", [
        "eu artificial intelligence act regulation 2024 1689",
        "eu ai act high risk system provisions enforcement",
        "eu ai act implementation framework",
        "artificial intelligence act",
        "ai act implementation timeline and transparency code of practice",
    ]),
    "eu-digital-omnibus-ai": ("EU Digital Omnibus on AI (AI Act simplification)", "European Union", [
        "eu ai act digital omnibus on ai",
        "digital omnibus on ai ai act simplification measures",
    ]),
    "au-app1-adm-transparency": ("APP 1 automated decision-making transparency obligation", "Australia", [
        "app 1 automated decision making transparency obligation",
        "oaic consultation on transparency in automated decision making",
        "consultation on guidance for transparency in automated decision making",
        "oaic app 1 automated decision making transparency guidance",
        "guidance on transparency in automated decision making",
        "transparency in automated decision making",
        "automated decision making transparency obligation app 1 7 1 9",
        "app 1 automated decision transparency obligation",
    ]),
    "au-apra-ai-supervision": ("APRA supervisory expectations on AI risk management and governance", "Australia", [
        "apra letter to industry on artificial intelligence ai",
        "apra ai supervisory expectations",
        "apra letter on ai related risk management and governance",
        "apra letter to industry on artificial intelligence",
    ]),
    "au-apra-governance-review": ("APRA governance review (CPS 510 consultation)", "Australia", [
        "apra governance review consultation paper updated draft cps 510 governance",
        "apra governance review consultation",
    ]),
    "au-asic-cyber-uplift": ("ASIC 26-092MR — urgent cyber uplift as AI accelerates cyber threats", "Australia", [
        "asic 26 092mr urgent cyber uplift as ai accelerates cyber threats",
        "asic open letter on cyber uplift as ai accelerates cyber threats",
        "asic open letter on ai accelerated cyber threats",
    ]),
    "au-gov-ai-policy": ("Policy for the responsible use of AI in government (DTA)", "Australia", [
        "policy for the responsible use of ai in government updated",
        "dta responsible use of ai in government policy transparency statement",
        "ai transparency statement dta implementation of the policy for responsible use",
        "policy for the responsible use of ai in government",
        "apra ai transparency statement",
    ]),
    "au-smma": ("Social Media Minimum Age restrictions", "Australia", [
        "social media minimum age restrictions",
        "social media minimum age compliance notice",
    ]),
    "au-esafety-ai-companions": ("eSafety expectations for AI companions (transparency & child safety)", "Australia", [
        "esafety ai companion and transparency guidance",
        "esafety ai companion transparency notices and child safety expectations",
        "online safety guidance for ai companions and age assurance",
    ]),
}

# Curated deadlines & practice lens for canonical entities (accuracy > automation)
CURATED = {
    "au-app1-adm-transparency": {
        "stage": "enacted",
        "deadlines": [
            {"date": "2026-09-01", "label": "OAIC guidance expected (September 2026, approx.)",
             "audience": "Privacy and compliance teams", "jurisdiction": "Australia"},
            {"date": "2026-12-10", "label": "APP 1 ADM disclosure obligation commences",
             "audience": "All APP entities using ADM affecting rights or interests", "jurisdiction": "Australia"},
        ],
        "soWhat": "Ask for the ADM inventory and a draft privacy-policy disclosure now — guidance lands around September and the obligation is fixed for 10 December 2026.",
    },
    "eu-ai-act": {
        "stage": "in-force",
        "deadlines": [
            {"date": "2026-08-02", "label": "High-risk system obligations apply (subject to Digital Omnibus deferral, pending formal adoption)",
             "audience": "Providers and deployers of high-risk AI in the EU", "jurisdiction": "European Union"},
        ],
        "soWhat": "Classify your EU-touching AI systems against Annex III now; the August 2026 date only moves if the Omnibus is formally adopted.",
    },
    "eu-gpai-code-of-practice": {
        "stage": "in-force",
        "deadlines": [
            {"date": "2026-08-02", "label": "Commission enforcement of GPAI obligations begins",
             "audience": "GPAI model providers", "jurisdiction": "European Union"},
        ],
        "soWhat": "GPAI providers should map Code-of-Practice commitments to evidence they can produce before enforcement starts in August 2026.",
    },
    "eu-digital-omnibus-ai": {
        "stage": "proposed",
        "deadlines": [
            {"date": "2027-12-02", "label": "Deferred high-risk date (certain system types) — takes effect only if Omnibus adopted",
             "audience": "High-risk AI providers/deployers", "jurisdiction": "European Union"},
            {"date": "2028-08-02", "label": "Deferred high-risk date (remaining system types) — takes effect only if Omnibus adopted",
             "audience": "High-risk AI providers/deployers", "jurisdiction": "European Union"},
        ],
        "soWhat": "Treat the deferral as conditional: plan to the original timetable until formal adoption, then re-baseline.",
    },
    "au-smma": {
        "stage": "in-force",
        "deadlines": [
            {"date": "2026-12-10", "label": "Social Media Minimum Age compliance expected",
             "audience": "Age-restricted social media platforms", "jurisdiction": "Australia"},
        ],
        "soWhat": "Platforms need age-assurance evidence and enforcement-response runbooks before 10 December 2026.",
    },
    "au-gov-ai-policy": {
        "stage": "in-force",
        "deadlines": [
            {"date": "2026-12-31", "label": "All remaining policy requirements effective (December 2026)",
             "audience": "Australian Government agencies", "jurisdiction": "Australia"},
        ],
        "soWhat": "Agencies should close the gap between their published AI transparency statement and actual inventory, testing, and accountability practices.",
    },
    "au-apra-ai-supervision": {
        "stage": "in-force",
        "soWhat": "APRA-regulated entities should evidence board-visible AI inventories, supplier controls, testing, and contingency plans — the gap APRA names is execution, not awareness.",
    },
    "au-asic-cyber-uplift": {
        "stage": "in-force",
        "soWhat": "Re-test phishing, credential, supply-chain, and incident-response controls against AI-accelerated attack paths and table the results at board level.",
    },
    "au-esafety-ai-companions": {
        "stage": "in-force",
        "soWhat": "Consumer AI products need age assurance, abuse reporting, moderation, and incident handling as core controls, not roadmap items.",
    },
    "au-apra-governance-review": {
        "stage": "consultation",
        "soWhat": "Track CPS 510 changes for board-challenge and accountability expectations that will pull AI oversight up to director level.",
    },
}

# GPAI CoP gets split out of the EU cluster into its own instrument
GPAI_FRAGMENT = "eu ai act general purpose ai code of practice"


def migrate(d):
    report = []
    if d.get("schemaVersion") == 2:
        print("Already schemaVersion 2 — nothing to do.")
        return d, report

    # ── sources: dedupe + grade normalization ────────────────────────────
    seen, deduped = {}, []
    for s in d.get("sources", []):
        key = (norm_title(s.get("title") or s.get("name")), (s.get("institution") or s.get("author") or "").lower())
        if key in seen:
            if richness(s) > richness(seen[key]):
                deduped[deduped.index(seen[key])] = s
                seen[key] = s
            continue
        seen[key] = s
        deduped.append(s)
    n_src_removed = len(d.get("sources", [])) - len(deduped)
    for s in deduped:
        g = str(s.get("evidenceGrade") or "").strip()
        if g and g[0].upper() in "ABCD":
            if len(g) > 1 and s.get("evidenceBase") is None:
                s["evidenceBase"] = g
            s["evidenceGrade"] = g[0].upper()
        s.setdefault("id", slugify(s.get("title") or s.get("name") or "", "src-"))
        s.setdefault("status", "unchanged")
    d["sources"] = deduped
    report.append(f"sources: removed {n_src_removed} duplicates, normalized grades ({len(deduped)} remain)")

    # ── regulations: cluster merge ────────────────────────────────────────
    regs = d.get("regulations", [])
    frag_to_id = {}
    for cid, (_, _, frags) in CLUSTERS.items():
        for f in frags:
            frag_to_id[f] = cid
    frag_to_id[GPAI_FRAGMENT] = "eu-gpai-code-of-practice"

    grouped, order = {}, []
    for r in regs:
        nt = norm_title(r.get("title") or r.get("name"))
        cid = frag_to_id.get(nt)
        if cid is None:
            cid = slugify(r.get("title") or r.get("name") or "", "reg-")
        if cid not in grouped:
            grouped[cid] = []
            order.append(cid)
        grouped[cid].append(r)

    merged_regs = []
    n_merged = 0
    for cid in order:
        members = grouped[cid]
        base = max(members, key=richness)
        rec = dict(base)
        rec["id"] = cid
        if cid in CLUSTERS:
            rec["title"] = CLUSTERS[cid][0]
            rec["jurisdiction"] = CLUSTERS[cid][1]
        # events from every member (incl. base) that has a date
        events, urls = [], set()
        for m in members:
            src = m.get("sources") or []
            url = next((u for u in src if isinstance(u, str) and u.startswith("http")), None)
            if m.get("date"):
                what = m.get("title") if m is not base else f"Tracked: {m.get('status') or 'update'}"
                events.append({"date": str(m["date"]), "what": str(what)[:140], **({"sourceUrl": url} if url else {})})
            for u in src:
                if isinstance(u, str): urls.add(u)
                elif isinstance(u, dict) and (u.get("url") or u.get("link")): urls.add(u.get("url") or u.get("link"))
        if len(members) > 1:
            rec["events"] = sorted(events, key=lambda e: e["dates" if False else "date"], reverse=True)
            rec["sources"] = sorted(urls)
            n_merged += len(members) - 1
            dates = [str(m.get("date")) for m in members if m.get("date")]
            if dates: rec["firstSeen"] = min(dates)[:10]
        rec["stage"] = CURATED.get(cid, {}).get("stage") or stage_of(rec.get("status"))
        # deadlines: curated first, else regex over timeline+summary
        if "deadlines" in CURATED.get(cid, {}):
            rec["deadlines"] = CURATED[cid]["deadlines"]
        else:
            found, seen_dates = [], set()
            for m in members:
                text = f"{m.get('timeline','')} {m.get('summary','')}"
                for iso, ctx in extract_dates(text):
                    if iso > TODAY and iso not in seen_dates:
                        seen_dates.add(iso)
                        label = re.sub(r"\s+", " ", ctx).strip()
                        found.append({"date": iso, "label": label[:120],
                                      "jurisdiction": rec.get("jurisdiction") or ""})
            if found:
                rec["deadlines"] = sorted(found, key=lambda x: x["date"])[:3]
        if CURATED.get(cid, {}).get("soWhat"):
            rec["soWhat"] = CURATED[cid]["soWhat"]
        rec.setdefault("status2", None)
        rec.pop("status2")
        rec["lastUpdated"] = max([str(m.get("date") or TODAY)[:10] for m in members] + [TODAY[:10] if False else "0"])
        if rec["lastUpdated"] == "0": rec["lastUpdated"] = TODAY
        rec["statusFlag"] = "unchanged"
        merged_regs.append(rec)
    d["regulations"] = merged_regs
    report.append(f"regulations: {len(regs)} -> {len(merged_regs)} ({n_merged} records merged into canonical entities)")

    # ── risks: dedupe + enums ─────────────────────────────────────────────
    risks = d.get("risks", [])
    seen_r, out_r, n_risk_merged = {}, [], 0
    for r in risks:
        key = norm_title(r.get("name") or r.get("title"))
        if key in seen_r:
            tgt = seen_r[key]
            for f in ("examples", "sources", "controls"):
                a, b = tgt.get(f) or [], r.get(f) or []
                tgt[f] = list(dict.fromkeys([*a, *b]))
            n_risk_merged += 1
            continue
        seen_r[key] = r
        out_r.append(r)
    used_ids = set()
    for r in out_r:
        rid = slugify(r.get("name") or "", "")
        while rid in used_ids: rid += "-2"
        used_ids.add(rid)
        r["id"] = rid
        r["likelihoodLevel"] = norm_level(r.get("likelihood"))
        r["impactLevel"] = norm_level(r.get("impact"))
        r["direction"] = norm_direction(r.get("trend")) or "stable"
        r["theme"] = theme_of(r.get("category"))
        bits = []
        for f in ("likelihood", "impact", "trend"):
            v = str(r.get(f) or "")
            if len(v) > 24: bits.append(f"{f}: {v}")
        if bits: r["rationale"] = "; ".join(bits)
        r["status"] = "unchanged"
    d["risks"] = out_r
    report.append(f"risks: merged {n_risk_merged} duplicate(s), normalized severity enums ({len(out_r)} remain)")

    # ── controls: ids + risk cross-links ─────────────────────────────────
    ctrl_ids = {}
    for c in d.get("controls", []):
        cid = slugify(c.get("name") or "", "")
        c["id"] = cid
        ctrl_ids[norm_title(c.get("name"))] = cid
    n_links = 0
    for r in d["risks"]:
        links = []
        for cname in (r.get("controls") or []):
            nid = ctrl_ids.get(norm_title(cname if isinstance(cname, str) else cname.get("name", "")))
            if nid: links.append(nid)
        if links:
            r["relatedControlIds"] = links
            n_links += len(links)
    report.append(f"controls: {len(d.get('controls', []))} ids assigned; {n_links} risk->control links resolved")

    # ── incidents/vendors/standards: ids ─────────────────────────────────
    for key, prefix in (("incidents", "inc-"), ("vendors", "v-"), ("standards", "std-")):
        for x in d.get(key, []):
            x.setdefault("id", slugify(x.get("name") or x.get("title") or "", prefix))
            x.setdefault("status", "unchanged")

    # ── history seed (honest: today only) ─────────────────────────────────
    d["history"] = [{
        "date": TODAY,
        "riskPosture": (d.get("trustDashboard") or {}).get("riskPosture"),
        "counts": {"risks": len(d["risks"]), "regulations": len(d["regulations"]),
                   "incidents": len(d.get("incidents", [])), "sources": len(d["sources"])},
        "newItems": 0, "updatedItems": 0,
    }]
    d["schemaVersion"] = 2
    report.append("history: seeded with today's snapshot; schemaVersion=2")
    return d, report


def main():
    d = json.loads(DATA.read_text())
    if d.get("schemaVersion") == 2 and "--force" not in sys.argv:
        print("data.json is already schemaVersion 2 — nothing to do.")
        return
    backup = HERE / f"data.backup-{date.today():%Y%m%d}.json"
    if not backup.exists():
        shutil.copy(DATA, backup)
        print(f"Backup written: {backup.name}")
    d, report = migrate(d)
    DATA.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    print("Migration report:")
    for line in report:
        print(" -", line)

if __name__ == "__main__":
    main()
