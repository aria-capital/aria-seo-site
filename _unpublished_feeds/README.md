# Unpublished feeds — kept, not served

Two RSS feeds for "The Midnight Brief" (`feed` and `newsletter-feed.xml`; 13 and 17 items, not
copies of each other). Between them they advertised 34 URLs under `/newsletter/`, a directory
that has never existed, and both were served live at HTTP 200.

They live under an underscore directory so Jekyll leaves them out of the GitHub Pages build.
That is the mechanism on purpose: an `exclude:` entry of `feed` in `_config.yml` would ALSO
have dropped `feeding-intolerance-gastric-residuals-icu-nurses-2026.html` (Jekyll 3.10 matches
exclude entries by string prefix) — caught in review on 2026-09-02 before it shipped.

**Do not delete these files.** They are the only copy of that writing; the day the newsletter
pages are published, move them back.
