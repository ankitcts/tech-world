# AdSense compliance checklist

Mark each item. Auto = the `audit.py` scanner can check it; Manual = a human/
agent must read the site to judge it.

## Required pages & legal (blockers)
- [ ] **Privacy Policy** page exists, linked site-wide, and discloses cookies,
      third-party ad vendors (Google), and opt-out. *(Auto: presence · Manual: content)*
- [ ] **About** page describing the site/author. *(Auto: presence)*
- [ ] **Contact** page or method. *(Auto: presence)*
- [ ] Terms/Disclaimer if applicable. *(Manual)*

## ads.txt & ad code
- [ ] `ads.txt` at the domain root, reachable at `https://domain/ads.txt`. *(Auto)*
- [ ] `ads.txt` contains `google.com, pub-XXXXXXXXXXXXXXXX, DIRECT, f08c47fec0942fa0`. *(Auto)*
- [ ] AdSense loader script from `pagead2.googlesyndication.com` present with a
      real `ca-pub-` client id. *(Auto)*
- [ ] Ad code is unmodified (no altering Google's snippet). *(Manual)*
- [ ] No ads on pages without publisher content (login, error, thank-you,
      404, empty results). *(Manual)*

## Consent & privacy (EEA/UK/CH)
- [ ] Google-certified **CMP** integrated (IAB TCF v2) and/or **Consent Mode v2**. *(Auto: signals)*
- [ ] Personalised ads are gated on consent for EEA/UK users. *(Manual)*
- [ ] CCPA/US state-privacy handling if targeting those users. *(Manual)*

## Content quality (the #1 rejection area — all Manual)
- [ ] Substantial, **original** content (not scraped, spun, or auto-generated).
- [ ] Enough real, indexable pages (not one thin page or placeholders).
- [ ] Clear value to users; not made-for-advertising.
- [ ] No "under construction" / lorem ipsum / template-only pages.
- [ ] Language/content matches a supported AdSense language.

## Prohibited / restricted content (all Manual)
- [ ] No adult/sexual, violent, hateful, harassing, or dangerous content.
- [ ] No IP infringement / pirated content.
- [ ] No sale of dangerous/regulated goods; restricted topics handled per policy.
- [ ] No deceptive/misleading content or fake news.

## Ad placement & layout
- [ ] Ads clearly distinguishable from content; not labelled to induce clicks. *(Manual)*
- [ ] No encouraging clicks ("click here", arrows pointing at ads). *(Manual)*
- [ ] Content-to-ad ratio reasonable; ads don't dominate the page. *(Manual)*
- [ ] No ads in pop-ups, emails, or non-content placements. *(Manual)*
- [ ] Layout meets Better Ads Standards (no intrusive interstitials/auto-play). *(Manual)*

## Crawlability & technical
- [ ] Googlebot can crawl: no site-wide `noindex`, robots.txt not blocking. *(Auto: signals)*
- [ ] `robots.txt` present and sane. *(Auto)*
- [ ] `sitemap.xml` present / submitted. *(Auto)*
- [ ] Mobile-friendly and reasonably fast (Core Web Vitals). *(Manual)*
- [ ] HTTPS enabled. *(Manual/deploy)*

## Traffic quality (Manual)
- [ ] Organic/legitimate traffic only; no bought traffic, bots, or paid-to-click.
- [ ] No self-clicking or asking others to click ads.
