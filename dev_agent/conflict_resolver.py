"""Merge conflict detection and Claude-based resolution."""

from __future__ import annotations

import logging
import os

from .cli_bridge import claude_generate, git_conflicted_files

logger = logging.getLogger(__name__)


def resolve_conflicts(cwd: str, feature_description: str) -> None:
    """Detect conflicted files, resolve each with Claude, write back."""
    conflicted = git_conflicted_files(cwd)
    if not conflicted:
        logger.info("No conflicted files found")
        return

    logger.info("Resolving conflicts in %d file(s): %s", len(conflicted), conflicted)

    for file_path in conflicted:
        abs_path = os.path.join(cwd, file_path)
        with open(abs_path, "r") as f:
            content = f.read()

        # Verify it actually has conflict markers
        if "<<<<<<" not in content:
            logger.warning(
                "  %s marked as conflicted but has no markers, skipping", file_path
            )
            continue

        resolved = _resolve_single_file(content, file_path, feature_description)

        with open(abs_path, "w") as f:
            f.write(resolved)

        logger.info("  Resolved: %s", file_path)


def _resolve_single_file(
    content: str, file_path: str, feature_description: str
) -> str:
    """Send a conflicted file to Claude for resolution, with one retry."""
    from .prompts import resolve_conflict_prompt

    resolved = claude_generate(
        resolve_conflict_prompt(content, file_path, feature_description),
        timeout=120,
    )
    resolved = _strip_code_fences(resolved)

    # Verify markers are removed
    if "<<<<<<" in resolved or "=======" in resolved or ">>>>>>" in resolved:
        logger.warning("  First resolution still has markers, retrying for %s", file_path)
        resolved = claude_generate(
            f"The following text still contains merge conflict markers. "
            f"Remove ALL lines containing <<<<<<, ======, >>>>>> and produce "
            f"the clean merged file:\n\n{resolved}",
            timeout=60,
        )
        resolved = _strip_code_fences(resolved)

    return resolved


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences if Claude wraps the output."""
    lines = text.strip().split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)
