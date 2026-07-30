"""
push_seo_full.py
Git add, commit, and push all seo_site changes to GitHub Pages.
Python 3.9 compatible.

Usage:
  python push_seo_full.py              # commits with auto-generated message
  python push_seo_full.py "My message" # custom commit message
"""
import subprocess
import sys
import os
import logging
from datetime import datetime

# ── CONFIG ───────────────────────────────────────────────────────────────────
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(REPO_DIR, "push_seo_full.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def run(cmd, cwd=None):
    """Run a shell command; return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd,
        cwd=cwd or REPO_DIR,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def count_articles():
    """Count article HTML files in seo_site/."""
    skip = {
        "index.html", "all-articles.html", "about.html", "contact.html",
        "privacy_policy.html", "privacy-policy.html", "affiliate-disclosure.html",
        "dmca-policy.html", "terms-of-service.html",
    }
    count = 0
    for f in os.listdir(REPO_DIR):
        if f.endswith(".html") and f not in skip and not f.startswith("_"):
            count += 1
    return count


def main():
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    n_articles = count_articles()

    # Custom commit message from CLI arg, or auto-generate
    if len(sys.argv) > 1:
        commit_msg = " ".join(sys.argv[1:])
    else:
        commit_msg = (
            f"Add {n_articles} articles, update index + sitemap [{timestamp}]"
        )

    log.info("=" * 60)
    log.info("SEO SITE PUSH STARTING")
    log.info("Repo dir: %s", REPO_DIR)
    log.info("Commit:   %s", commit_msg)

    # 1. git add -A
    code, out, err = run(["git", "add", "-A"])
    if code != 0:
        log.error("git add failed (code %d): %s", code, err or out)
        sys.exit(1)
    log.info("git add -A ... OK")

    # 2. Check if there's anything to commit
    code, out, err = run(["git", "status", "--porcelain"])
    if code != 0:
        log.error("git status failed: %s", err)
        sys.exit(1)
    if not out:
        log.info("Nothing to commit — working tree clean. Skipping commit/push.")
        print("\nNothing to commit. Site is already up to date.")
        return

    changed_files = out.count("\n") + 1
    log.info("%d file(s) staged for commit.", changed_files)

    # 3. git commit
    code, out, err = run(["git", "commit", "-m", commit_msg])
    if code != 0:
        log.error("git commit failed (code %d): %s", code, err or out)
        sys.exit(1)
    log.info("git commit ... OK")
    log.info(out)

    # 4. git push origin main
    code, out, err = run(["git", "push", "origin", "main"])
    if code != 0:
        log.error("git push failed (code %d):\n%s\n%s", code, out, err)
        sys.exit(1)
    log.info("git push origin main ... OK")
    log.info(out or err)

    log.info("PUSH COMPLETE. GitHub Pages will rebuild in ~60 seconds.")
    log.info("Check: https://aria-capital.github.io/aria-seo-site/")
    print("\n" + "=" * 60)
    print(f"  DONE — {changed_files} files pushed.")
    print(f"  Site URL: https://aria-capital.github.io/aria-seo-site/")
    print(f"  Log:      {LOG_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
