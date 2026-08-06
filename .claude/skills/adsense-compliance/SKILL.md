---
name: adsense-compliance
description: >-
  Use this skill to keep any web project compliant with Google AdSense program
  policies and to diagnose why an AdSense application/site was rejected or a
  project is "failing" AdSense review. Trigger on "AdSense", "ad approval",
  "site rejected", "not compliant", "ads.txt", "privacy policy for ads",
  "consent / CMP / GDPR for ads", "why did AdSense reject", "low value content",
  or before shipping any project that shows Google ads. Runs a repo audit and
  maps findings to the exact policy areas Google checks.
---

# Google AdSense Compliance

Keep projects continuously compliant with Google AdSense policies, and diagnose
rejections. This skill is a practical engineering aid — it does **not** replace
reading Google's official policies, and it is not legal advice. Authoritative
sources:
- AdSense Program policies: https://support.google.com/adsense/answer/48182
- Ad placement policies: https://support.google.com/adsense/answer/1346295
- Site behaviour & "Better Ads": https://www.betterads.org/standards/
- Google Publisher Policies: https://support.google.com/publisherpolicies

## How to use

1. **Audit the project** with the bundled scanner (heuristic, fast):
   ```bash
   python .claude/skills/adsense-compliance/scripts/audit.py <project-dir>
   ```
   It reports PASS/WARN/FAIL for each machine-checkable requirement and prints
   what to fix. Treat WARN/FAIL as leads, then verify manually.
2. **Walk the full checklist** in `references/checklist.md` — many policy items
   (content quality, navigation, originality) can't be auto-detected and must be
   judged by a human/agent reading the site.
3. **Fix, then re-audit.** Re-run until the machine-checkable items pass and the
   manual checklist is satisfied.

## The requirements the auditor checks

- **`ads.txt`** present at the site root and containing a valid
  `google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0` line. A missing
  or malformed `ads.txt` is one of the most common causes of "earnings at risk"
  and reduced monetisation.
- **Privacy policy** page that discloses the use of cookies, third-party
  vendors (Google), and how users can opt out. AdSense *requires* a privacy
  policy.
- **Consent management (EEA/UK/CH):** a Google-certified CMP wired to the IAB
  TCF and/or Google Consent Mode v2. Serving personalised ads to EEA users
  without valid consent violates policy.
- **Valid AdSense tag:** the `adsbygoogle` script from
  `pagead2.googlesyndication.com` with a real `ca-pub-` client id; ad code not
  modified; not placed on pages without publisher content.
- **Sufficient original content & navigation:** enough real pages, a way to
  navigate, and no "under construction"/placeholder/thin pages behind the ads.

## The most common rejection reasons (map findings to these)

1. **"Low value content" / "Site does not comply" / "Under construction"** —
   thin, templated, scraped, or auto-generated content; too few real pages; no
   original value. The #1 rejection. Fix with substantial, original, useful
   content and real navigation.
2. **Missing required pages** — no Privacy Policy, About, or Contact page.
3. **`ads.txt` missing/misconfigured** — publisher id wrong or file unreachable.
4. **No/!broken consent** for EEA users (no certified CMP / Consent Mode v2).
5. **Prohibited or restricted content** — adult, violent, hateful, dangerous,
   IP-infringing, or otherwise against Google Publisher Policies.
6. **Ad placement violations** — ads that encourage accidental clicks, ads on
   screens without content, deceptive layout, more ads than content, ads on
   error/thank-you/login pages.
7. **Invalid traffic** — bought traffic, bots, or click manipulation.
8. **Navigation/UX** — site hard to navigate, broken links, not mobile-friendly,
   slow (poor Core Web Vitals), pop-ups violating Better Ads Standards.
9. **Insufficient traffic/domain issues** — brand-new domain, no indexing, or
   `noindex`/robots blocking Googlebot.

## Diagnosing a rejected/failing project

1. Get the **exact message** Google showed (e.g. "Low value content",
   "Site does not comply with Google policies"). It points at the category.
2. Run the auditor and open `references/checklist.md`; note every FAIL/WARN and
   every manual item that is not clearly satisfied.
3. Read a sample of the site's actual pages for content quality, originality,
   and required legal pages — the auditor cannot judge these.
4. Produce a prioritised fix list: hard blockers (missing ads.txt, privacy
   policy, thin content, prohibited content) first, then placement/UX/consent.
5. Fix, redeploy, ensure Googlebot can crawl (no `noindex`, valid robots.txt,
   submitted sitemap), then re-request review.

## Keeping projects compliant going forward

- Add the auditor to CI so `ads.txt`, privacy policy, and consent presence are
  checked on every build.
- Re-audit before any release that adds ad units or new page types.
- Never place ads on pages without genuine publisher content.
