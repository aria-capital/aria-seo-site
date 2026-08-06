"""
inject_shared_css.py
====================
Injects <link rel="stylesheet" href="aria_style.css"> into all SEO site HTML files.
Also:
  1. Strips existing <style> blocks (replaced by shared stylesheet)
  2. Adds ARIA header + footer HTML if missing
  3. Detects and reports Git merge conflict markers (does NOT auto-resolve)
  4. Adds Inter font import if missing

Usage:
    python inject_shared_css.py             # dry run (preview only)
    python inject_shared_css.py --write     # write changes to files
    python inject_shared_css.py --write --strip-inline  # also remove inline <style> blocks

Run from: C:\\Users\\carlo\\Documents\\PythonScripts\\seo_site\\
Python 3.9 compatible.
"""

import os
import re
import sys
import argparse
from pathlib import Path

from safe_write import safe_write_html

# -- Config -------------------------------------------------------------------
SITE_DIR     = Path(__file__).parent
CSS_LINK     = '<link rel="stylesheet" href="aria_style.css">'
FONT_IMPORT  = '<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">'
CONFLICT_RE  = re.compile(r'^(<<<<<<<|=======|>>>>>>>)', re.MULTILINE)
STYLE_RE     = re.compile(r'<style[^>]*>.*?</style>', re.DOTALL | re.IGNORECASE)
LINK_RE      = re.compile(r'<link[^>]+aria_style\.css[^>]*>', re.IGNORECASE)

ARIA_HEADER_HTML = '''<header class="aria-header">
  <a href="/aria-seo-site/" class="aria-logo">
    <span class="aria-logo-mark">ARIA</span>
    <span class="aria-logo-sub">Capital Holdings</span>
  </a>
  <nav class="aria-nav">
    <a href="/aria-seo-site/">All Articles</a>
    <a href="https://nurse-finance.beehiiv.com" target="_blank" rel="noopener">Newsletter</a>
    <a href="https://icunotebook.gumroad.com" target="_blank" rel="noopener">Resources</a>
  </nav>
</header>'''

NEWSLETTER_CTA_HTML = '''<div class="newsletter-cta">
  <h3>The Midnight Brief</h3>
  <p>Weekly nurse finance insights. No fluff, no spam — just the money moves that matter for RNs.</p>
  <a href="https://nurse-finance.beehiiv.com" class="btn-subscribe" target="_blank" rel="noopener">
    Subscribe Free &rarr;
  </a>
</div>'''

# -- Helpers ------------------------------------------------------------------

def get_html_files(site_dir):
    """Return all .html files in site_dir (non-recursive top level)."""
    files = [f for f in site_dir.glob('*.html') if f.is_file()]
    return sorted(files)


def has_conflict_markers(content):
    return bool(CONFLICT_RE.search(content))


def already_has_css_link(content):
    return bool(LINK_RE.search(content))


def inject_css_link(content):
    """Insert CSS link + font import just before </head>."""
    if already_has_css_link(content):
        return content, False

    inject = f'{FONT_IMPORT}\n{CSS_LINK}\n'
    new_content = re.sub(
        r'(</head>)',
        f'{inject}\\1',
        content,
        count=1,
        flags=re.IGNORECASE
    )
    changed = new_content != content
    return new_content, changed


def strip_inline_styles(content):
    """Remove <style>...</style> blocks (replaced by shared CSS)."""
    new_content = STYLE_RE.sub('', content)
    changed = new_content != content
    return new_content, changed


def has_aria_header(content):
    return 'class="aria-header"' in content or 'class=\'aria-header\'' in content


def inject_aria_header(content):
    """Insert ARIA header after <body> opening tag if not present."""
    if has_aria_header(content):
        return content, False
    new_content = re.sub(
        r'(<body[^>]*>)',
        f'\\1\n{ARIA_HEADER_HTML}',
        content,
        count=1,
        flags=re.IGNORECASE
    )
    changed = new_content != content
    return new_content, changed


def has_newsletter_cta(content):
    return 'newsletter-cta' in content


def inject_newsletter_cta(content):
    """Insert newsletter CTA before </body>."""
    if has_newsletter_cta(content):
        return content, False
    new_content = re.sub(
        r'(</body>)',
        f'{NEWSLETTER_CTA_HTML}\n\\1',
        content,
        count=1,
        flags=re.IGNORECASE
    )
    changed = new_content != content
    return new_content, changed


# -- Main ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Inject shared CSS into ARIA SEO site HTML files.')
    parser.add_argument('--write',        action='store_true', help='Write changes (default: dry run)')
    parser.add_argument('--strip-inline', action='store_true', help='Remove inline <style> blocks')
    parser.add_argument('--add-header',   action='store_true', help='Inject ARIA header bar')
    parser.add_argument('--add-cta',      action='store_true', help='Inject newsletter CTA above </body>')
    parser.add_argument('--conflict-only',action='store_true', help='Only report conflict markers, no changes')
    args = parser.parse_args()

    dry_run = not args.write
    if dry_run:
        print('[DRY RUN] No files will be written. Pass --write to apply changes.\n')

    files = get_html_files(SITE_DIR)
    print(f'Found {len(files)} HTML files in {SITE_DIR}\n')

    stats = {
        'conflicts':     [],
        'css_injected':  0,
        'style_stripped':0,
        'header_added':  0,
        'cta_added':     0,
        'already_done':  0,
        'skipped':       0,
    }

    for fpath in files:
        try:
            content = fpath.read_text(encoding='utf-8', errors='replace')
        except Exception as e:
            print(f'  ERROR reading {fpath.name}: {e}')
            stats['skipped'] += 1
            continue

        if args.conflict_only:
            if has_conflict_markers(content):
                stats['conflicts'].append(fpath.name)
            continue

        if has_conflict_markers(content):
            stats['conflicts'].append(fpath.name)
            print(f'  [CONFLICT] {fpath.name} — SKIPPED (resolve conflicts first)')
            stats['skipped'] += 1
            continue

        changed = False
        original = content

        # 1. Inject CSS link
        content, c = inject_css_link(content)
        if c:
            stats['css_injected'] += 1
            changed = True
        else:
            stats['already_done'] += 1

        # 2. Strip inline styles
        if args.strip_inline:
            content, c = strip_inline_styles(content)
            if c:
                stats['style_stripped'] += 1
                changed = True

        # 3. Add ARIA header
        if args.add_header:
            content, c = inject_aria_header(content)
            if c:
                stats['header_added'] += 1
                changed = True

        # 4. Add newsletter CTA
        if args.add_cta:
            content, c = inject_newsletter_cta(content)
            if c:
                stats['cta_added'] += 1
                changed = True

        if changed:
            if dry_run:
                print(f'  [WOULD CHANGE] {fpath.name}')
            else:
                safe_write_html(str(fpath), content, allow_preexisting=True)
                print(f'  [UPDATED] {fpath.name}')

    # Summary
    print(f'\n{"="*55}')
    print(f'SUMMARY {"(DRY RUN)" if dry_run else "(WRITTEN)"}')
    print(f'{"="*55}')
    print(f'  Files scanned:         {len(files)}')
    print(f'  CSS link injected:     {stats["css_injected"]}')
    print(f'  Already had CSS link:  {stats["already_done"]}')
    if args.strip_inline:
        print(f'  Inline styles removed: {stats["style_stripped"]}')
    if args.add_header:
        print(f'  Header added:          {stats["header_added"]}')
    if args.add_cta:
        print(f'  Newsletter CTA added:  {stats["cta_added"]}')
    print(f'  Skipped (conflicts):   {stats["skipped"]}')
    print(f'  Merge conflicts found: {len(stats["conflicts"])}')

    if stats['conflicts']:
        print(f'\n[CONFLICT FILES — resolve manually]:')
        for fn in stats['conflicts'][:20]:
            print(f'  {fn}')
        if len(stats['conflicts']) > 20:
            print(f'  ... and {len(stats["conflicts"]) - 20} more')

    if dry_run and stats['css_injected'] > 0:
        print(f'\nTo apply: python inject_shared_css.py --write')
        print(f'Full run: python inject_shared_css.py --write --strip-inline --add-header --add-cta')


if __name__ == '__main__':
    main()
