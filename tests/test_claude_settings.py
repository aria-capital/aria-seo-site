"""
Tests for the committed .claude/settings.json.

This file is configuration, not code, which is exactly why it needs tests: every rule
below has already been broken once, silently, and none of them fail loudly on their own.

Two distinct concerns:

  * What must NOT be here, because the repo is PUBLIC. A committed
    permissions.defaultMode ships prompt-free Claude to anyone who clones. The owner's
    own "no prompts" wish is preserved — it lives in .claude/settings.local.json, which
    is untracked and outranks project scope in the merge order.

  * What MUST be here, because a future session may helpfully "clean up" settings it does
    not recognise. ultracode and effortLevel are a deliberate, repeated decision by the
    owner, and the absent `model` key is equally deliberate — pinning it can only weaken
    the main loop. An earlier revision pinned model:"fable" and had to be reverted.

Empirical note from the session that wrote this: Claude Code refuses bypass permission
modes under root ("--dangerously-skip-permissions cannot be used with root/sudo
privileges"). Cloud containers run as root, so the committed defaultMode was never doing
anything there. It only ever had an effect on a normal-user machine — where it is now
carried by the local file instead.
"""
import json
import os
import subprocess

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS = os.path.join(HERE, ".claude", "settings.json")


@pytest.fixture(scope="module")
def settings():
    with open(SETTINGS, encoding="utf-8") as fh:
        return json.load(fh)


# --- the file itself --------------------------------------------------------


def test_settings_file_exists():
    assert os.path.exists(SETTINGS), "session defaults are committed on purpose"


def test_settings_is_valid_json(settings):
    """A malformed settings file is ignored silently — no error, just no defaults."""
    assert isinstance(settings, dict)


# --- what must not leak to a public repo ------------------------------------


def test_permission_mode_is_not_committed(settings):
    """
    The leak this test exists to prevent. Anyone who clones a public repo carrying
    permissions.defaultMode gets approval prompts disabled in their own sessions, on
    their own machine, without ever choosing that.
    """
    assert "defaultMode" not in settings.get("permissions", {}), (
        "permissions.defaultMode must live in .claude/settings.local.json (untracked), "
        "not in the committed file — this repo is public"
    )


def test_dangerous_mode_prompt_suppression_is_not_committed(settings):
    assert "skipDangerousModePermissionPrompt" not in settings


def test_no_credentials_or_identifiers_in_settings():
    """
    A personal credential has already been committed to this repo once. Settings files
    are an easy place for an API key or account id to be pasted "just for now".
    """
    with open(SETTINGS, encoding="utf-8") as fh:
        raw = fh.read().lower()
    for needle in ("sk-", "api_key", "apikey", "token", "secret", "password", "pub-"):
        assert needle not in raw, f"possible credential material in settings.json: {needle!r}"


def test_local_settings_are_ignored_by_this_repo():
    """
    Must be ignored by the repo's OWN .gitignore, not by a machine-level one. The cloud
    container ignores this path globally; a Mac clone does not, so relying on the global
    rule would let the file be committed from the Mac and reintroduce the leak.
    """
    result = subprocess.run(
        ["git", "check-ignore", "-v", ".claude/settings.local.json"],
        cwd=HERE, capture_output=True, text=True,
    )
    assert result.returncode == 0, ".claude/settings.local.json is not gitignored"
    assert result.stdout.startswith(".gitignore:"), (
        "ignored only by a machine-level gitignore, not by this repo's — "
        f"got {result.stdout.strip()!r}"
    )


# --- what must stay, because a future session may 'tidy' it away ------------


def test_ultracode_is_enabled(settings):
    """Verified against CLI 2.1.220: project scope genuinely enables it."""
    assert settings.get("ultracode") is True


def test_effort_level_is_the_maximum_the_schema_allows(settings):
    """
    "max" is not a valid effortLevel — the enum is low|medium|high|xhigh, so xhigh IS the
    ceiling for the main session. ("max" exists only as a per-agent Workflow effort.)
    """
    assert settings.get("effortLevel") == "xhigh"


def test_model_is_not_pinned(settings):
    """
    Deliberately absent. The default selection resolves to the strongest model; pinning
    can only weaken it. A previous revision pinned "fable" here and was reverted.
    """
    assert "model" not in settings, (
        "do not pin a model — the default selection is the strongest available"
    )


def test_workflows_stay_enabled(settings):
    assert settings.get("enableWorkflows") is True
