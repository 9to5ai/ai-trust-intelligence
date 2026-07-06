#!/usr/bin/env python3
"""Classify controls onto two reference taxonomies (see SCHEMA.md):

- nistFunction: NIST AI RMF 1.0 function — GOVERN | MAP | MEASURE | MANAGE
- iso42001Area: ISO/IEC 42001:2023 Annex A control-objective area (A.2–A.10)

Keyword rules + curated overrides; mappings are indicative analyst
classifications, not certified crosswalks. Idempotent; prints the full
assignment list for human review.
"""
import json, re, sys
from collections import Counter
from pathlib import Path

DATA = Path(__file__).parent / "data.json"

ISO_LABELS = {
    "A.2": "A.2 AI policies",
    "A.3": "A.3 Internal organization",
    "A.4": "A.4 Resources",
    "A.5": "A.5 Impact assessment",
    "A.6": "A.6 System life cycle",
    "A.7": "A.7 Data",
    "A.8": "A.8 Interested-party info",
    "A.9": "A.9 Responsible use",
    "A.10": "A.10 Third parties",
}

# Curated overrides by lowercase control name (wins over keyword rules)
OVERRIDES = {
    "prompt-injection-resistant agent design": ("MANAGE", "A.6"),
    "portability and exit readiness": ("GOVERN", "A.10"),
    "age-assurance and account-gating workflow": ("MANAGE", "A.9"),
    "adm disclosure and contestability workflow": ("GOVERN", "A.8"),
    "transparency, human review, and contestability controls": ("GOVERN", "A.8"),
    "ai-abuse telemetry and mitre mapping": ("MEASURE", "A.6"),
    "privacy minimisation and deletion workflow": ("MANAGE", "A.7"),
    "synthetic-image abuse intake and takedown workflow": ("MANAGE", "A.8"),
}

def classify(c):
    t = f"{c.get('name','')} {c.get('description','')[:160]}".lower()
    name = c.get('name', '').lower()

    # ── NIST function (rule order matters) ──
    if re.search(r"vendor|supplier|third[- ]party|procurement|contract", name):
        fn = "GOVERN"
    elif re.search(r"inventory|classification|tiering|impact assessment|use[- ]case|shadow ai|discovery|risk assessment|deployment assessment|mapping|\bmap\b", name):
        fn = "MAP"
    elif re.search(r"incident|shutdown|intervention|kill[- ]switch|patch|segment|gateway|sandbox|least[- ]privilege|access|quarantine|contingency|fallback|out-of-band|verification|containment|rollback|response|approval|takedown", name):
        fn = "MANAGE"
    elif re.search(r"red[- ]team|test|evaluat|monitor|regression|benchmark|audit|assurance gate|validation|scan|telemetry|logging|detection|simulation", name):
        fn = "MEASURE"
    elif re.search(r"policy|acceptable[- ]use|governance|accountab|board|training|awareness|disclosure|transparency|compliance|re-baseline|legal|liability|charter|framework", name):
        fn = "GOVERN"
    elif re.search(r"red[- ]team|test|evaluat|monitor|audit|review", t):
        fn = "MEASURE"
    elif re.search(r"guardrail|filter|control|restrict|limit|protect", t):
        fn = "MANAGE"
    else:
        fn = "GOVERN"

    # ── ISO 42001 Annex A area ──
    if re.search(r"vendor|supplier|third[- ]party|procurement|customer", name):
        area = "A.10"
    elif re.search(r"impact assessment|privacy.*assessment|deployment assessment", name):
        area = "A.5"
    elif re.search(r"data (governance|quality|lineage|provenance|retention)|training data|dataset", t):
        area = "A.7"
    elif re.search(r"disclosure|transparency|notice|report|statement|communication|contestab|appeal|complaint", name):
        area = "A.8"
    elif re.search(r"policy|acceptable[- ]use|charter", name):
        area = "A.2"
    elif re.search(r"role|accountab|board|governance committee|training|awareness|competence|organis|organiz", name):
        area = "A.3"
    elif re.search(r"human (oversight|intervention|approval|review)|acceptable use|responsible use|misuse|human-in-the-loop|safe shutdown|oversight", t):
        area = "A.9"
    elif re.search(r"inventory|register|tooling|resource", name):
        area = "A.4"
    else:
        area = "A.6"  # life-cycle: build/deploy/operate/monitor controls

    key = c.get("name", "").strip().lower()
    if key in OVERRIDES:
        fn, area = OVERRIDES[key]
    return fn, area

def main():
    d = json.loads(DATA.read_text())
    changed = 0
    for c in d.get("controls", []):
        fn, area = classify(c)
        if c.get("nistFunction") != fn or c.get("iso42001Area") != ISO_LABELS[area]:
            changed += 1
        c["nistFunction"] = fn
        c["iso42001Area"] = ISO_LABELS[area]
    if "--dry" not in sys.argv:
        DATA.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    cs = d["controls"]
    print(f"classified {len(cs)} controls ({changed} changed)\n")
    print("function distribution:", dict(Counter(c['nistFunction'] for c in cs)))
    print("area distribution:", dict(Counter(c['iso42001Area'] for c in cs)))
    print("\nfull assignment list:")
    for c in sorted(cs, key=lambda x: (x['nistFunction'], x['iso42001Area'])):
        print(f"  {c['nistFunction']:<8} {c['iso42001Area']:<26} {c['name'][:64]}")

if __name__ == "__main__":
    main()
