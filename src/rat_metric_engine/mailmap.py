"""Git ``.mailmap`` parsing (docs/06-author-merging.md §6.1).

Mailmap entries let a repository declare, as part of its own history, that
several commit emails belong to one canonical identity. We parse the standard
git mailmap formats ourselves (rather than relying on git's own ``%aN``/``%aE``
mailmap expansion) so the alias map is a plain, testable data structure that
can be applied once at ingestion time and inspected independently of git.

Supported line forms (see ``git help mailmap``):
    Canonical Name <canonical@email>
    Canonical Name <canonical@email> <commit@email>
    Canonical Name <canonical@email> Commit Name <commit@email>
    <canonical@email> <commit@email>
"""

from __future__ import annotations

import re
from pathlib import Path

EMAIL_RE = re.compile(r"<([^<>]*)>")

# {commit_email_lower: (canonical_name, canonical_email)}
MailmapAliases = dict[str, tuple[str, str]]


def parse_mailmap_text(text: str) -> MailmapAliases:
    """Parse ``.mailmap`` file contents into a commit-email alias map."""

    aliases: MailmapAliases = {}
    for raw_line in text.splitlines():
        entry = _parse_mailmap_line(raw_line)
        if entry is None:
            continue
        commit_email, canonical = entry
        aliases[commit_email] = canonical
    return aliases


def _parse_mailmap_line(raw_line: str) -> tuple[str, tuple[str, str]] | None:
    line = raw_line.split("#", 1)[0].strip()
    if not line:
        return None

    emails = list(EMAIL_RE.finditer(line))
    if not emails:
        return None

    canonical_email = emails[0].group(1).strip()
    canonical_name = line[: emails[0].start()].strip()
    if not canonical_email:
        return None

    if len(emails) == 1:
        # "Canonical Name <canonical@email>" — declares the display name for
        # commits already using this email; nothing to alias.
        return None

    commit_email = emails[-1].group(1).strip()
    if not commit_email:
        return None

    return commit_email.lower(), (canonical_name, canonical_email)


def load_mailmap(repo_path: str | Path) -> MailmapAliases:
    """Load and parse the ``.mailmap`` file at the root of a repository.

    Returns an empty alias map if the repository has no mailmap file.
    """

    mailmap_path = Path(repo_path) / ".mailmap"
    if not mailmap_path.exists():
        return {}
    return parse_mailmap_text(mailmap_path.read_text(encoding="utf-8", errors="replace"))


def resolve_mailmap_identity(name: str, email: str, aliases: MailmapAliases) -> tuple[str, str]:
    """Resolve a raw commit author identity through a mailmap alias map.

    Falls back to the original ``(name, email)`` when there is no alias for
    this email, or when the alias omits a canonical name.
    """

    canonical = aliases.get(email.lower())
    if canonical is None:
        return name, email
    canonical_name, canonical_email = canonical
    return canonical_name or name, canonical_email or email
