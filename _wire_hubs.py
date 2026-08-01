# -*- coding: utf-8 -*-
"""One-time internal-linking pass: add a hub breadcrumb to topically matched
articles so the 10 hub pages stop being orphaned. Idempotent; caps per hub."""
import os, re

from safe_write import safe_write_html

HERE = os.path.dirname(os.path.abspath(__file__))
CAP = 40  # max new links added per hub this pass

HUBS = [
    # (hub_slug, label, priority-ordered predicate on slug)
    ("travel-nurse-tax-hub-2026", "Travel Nurse Tax Hub",
        lambda s: ("travel-nurse" in s and "tax" in s)),
    ("travel-nurse-hub-2026", "Travel Nursing Hub",
        lambda s: ("travel-nurse" in s or "travel-nursing" in s
                   or bool(re.search(r'(aya|amn|cross-country|clipboard|nomad-health|host-healthcare|medical-solutions|fusion-medical|triage-staffing|trusted-health|tnaa|vivian|travel-nurses-across-america).*(review|agency)', s)))),
    ("crna-career-hub-2026", "CRNA Career Hub",
        lambda s: ("crna" in s or "srna" in s or "nurse-anesth" in s)),
    ("nurse-money-hub-2026", "Nurse Money & Investing Hub",
        lambda s: bool(re.search(r'(roth|403b|457b|\bira\b|invest|index-fund|brokerage|\bfire\b|\bhsa\b|pension|dividend|\bbond|\betf\b|budget|net-worth|capital-gains|annuit|treasury|robo-advisor|expense-ratio|rebalanc|tax-loss|sinking-fund|emergency-fund|backdoor)', s))),
    ("nurse-side-hustle-hub-2026", "Nurse Side Hustle Hub",
        lambda s: bool(re.search(r'(side-hustle|legal-nurse|per-diem|coaching|consult|freelance|\bprn\b|nurse-gig|nurse-blog|nurse-tutor|curriculum-writing|chart-review|nurse-writer)', s))),
    ("federal-nurse-hub-2026", "Federal Nurse Hub",
        lambda s: bool(re.search(r'(federal-nurse|va-nurse|va-pay|government-nurse|public-health-service|bureau-of-prisons|indian-health|military-nurse|gs-\d|title-38)', s))),
    ("icu-devices-hub-2026", "ICU Devices Hub",
        lambda s: bool(re.search(r'(ecmo|iabp|impella|\blvad\b|crrt|ventilator|\bvent-|evd-|arterial-line|central-line|swan|\bcvp\b|wound-vac|\bhfnc\b|\bniv\b|cardioversion|defib|pacemaker|waveform|capnograph|dialysis-catheter)', s))),
    ("icu-pharmacology-hub-2026", "ICU Pharmacology Hub",
        lambda s: bool(re.search(r'(propofol|dexmedetomidine|precedex|ketamine|midazolam|versed|fentanyl|hydromorphone|norepinephrine|levophed|epinephrine|dopamine|dobutamine|milrinone|vasopressin|vasopressor|phenylephrine|nitroglycerin|nitroprusside|nicardipine|labetalol|esmolol|amiodarone|diltiazem|cardizem|insulin-drip|heparin-drip|bivalirudin|argatroban|vancomycin|valproate|adenosine|albumin|mannitol|sedation|analgesia)', s) and ("guide-icu" in s or "drip" in s or "icu-nurses" in s or "icu-sedation" in s))),
    ("icu-specialty-career-hub-2026", "ICU Specialty Career Hub",
        lambda s: bool(re.search(r'(nurse-career-guide|-career-guide-2026|charge-nurse|preceptor|new-grad|micu-nurse|cvicu-nurse|neuro-icu-nurse|burn-icu-nurse|sicu-nurse|picu-nurse|trauma-icu-nurse|ccrn|pccn|nurse-residency)', s))),
    ("icu-emergencies-hub-2026", "ICU Emergencies Hub",
        lambda s: s.endswith("icu-nurses-2026") or "nursing-guide-2026" in s),
]

HUB_SLUGS = {h[0] for h in HUBS}

def breadcrumb(slug, label):
    return ('<p class="hub-crumb" style="font-family:sans-serif;font-size:0.9em;'
            'background:#f0f4ff;border-left:4px solid #3b6cf8;padding:8px 14px;'
            'border-radius:0 6px 6px 0;margin:14px 0;">Part of the '
            '<a href="{0}.html"><strong>{1}</strong></a> &mdash; browse every related '
            'guide in one place.</p>').format(slug, label)

def main():
    files = [f for f in os.listdir(HERE) if f.endswith('.html')]
    added = {h[0]: 0 for h in HUBS}
    skipped_stub = 0
    changed = 0
    for f in sorted(files):
        slug = f[:-5]
        if slug == 'index' or slug in HUB_SLUGS:
            continue
        path = os.path.join(HERE, f)
        try:
            t = open(path, encoding='utf-8', errors='replace').read()
        except Exception:
            continue
        # skip redirect / noindex stubs
        if re.search(r'noindex', t, re.I) or 'http-equiv="refresh"' in t:
            skipped_stub += 1
            continue
        # pick first matching hub (priority order) that still has cap room
        target = None
        for hslug, label, pred in HUBS:
            try:
                if pred(slug):
                    target = (hslug, label)
                    break
            except Exception:
                continue
        if not target:
            continue
        hslug, label = target
        if added[hslug] >= CAP:
            continue
        # idempotent: already links to this hub?
        if hslug + '.html' in t:
            continue
        m = re.search(r'</h1>', t)
        if not m:
            continue
        crumb = breadcrumb(hslug, label)
        new = t[:m.end()] + '\n' + crumb + t[m.end():]
        safe_write_html(path, new, allow_preexisting=True)
        added[hslug] += 1
        changed += 1
    print("files changed:", changed, "| stubs skipped:", skipped_stub)
    for h in HUBS:
        print("  +{0:3d} -> {1}".format(added[h[0]], h[0]))

if __name__ == '__main__':
    main()
