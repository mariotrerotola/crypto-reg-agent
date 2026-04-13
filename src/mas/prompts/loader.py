"""Versioned prompt loader with content hashing for audit trails."""

from __future__ import annotations

import hashlib
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str, version: str = "v1") -> str:
    """Load a prompt file by name and version.

    Args:
        name: Prompt filename without extension (e.g. ``asset_flags``).
        version: Version directory name (e.g. ``v1``).

    Returns:
        The prompt text content.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
    """
    path = PROMPTS_DIR / version / f"{name}.md"
    if not path.exists():
        msg = f"Prompt not found: {path}"
        raise FileNotFoundError(msg)
    return path.read_text()


def prompt_hash(name: str, version: str = "v1") -> str:
    """Return a short SHA-256 hash of a prompt file's content."""
    content = load_prompt(name, version)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def prompt_version_tag(version: str = "v1") -> str:
    """Build a composite version tag for audit logging.

    Format: ``v1|asset_flags:a3b2c1d4|compliance:e5f6g7h8``

    This tag uniquely identifies the exact prompt content used in a run,
    enabling tamper detection if prompt files are modified after the fact.
    """
    version_dir = PROMPTS_DIR / version
    if not version_dir.exists():
        return version

    hashes: list[str] = []
    for f in sorted(version_dir.glob("*.md")):
        h = hashlib.sha256(f.read_text().encode()).hexdigest()[:8]
        hashes.append(f"{f.stem}:{h}")

    return f"{version}|{'|'.join(hashes)}"
