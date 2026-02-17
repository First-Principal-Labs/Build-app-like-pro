"""Steps 7-8: Main issue processing loop and phase merges."""

from __future__ import annotations

import logging
import os
import re

from .cli_bridge import (
    MergeConflictError,
    claude_code_implement,
    claude_generate,
    gh_issue_close,
    gh_issue_create,
    gh_pr_create,
    gh_pr_diff,
    gh_pr_merge,
    git,
    git_add_all,
    git_checkout,
    git_commit,
    git_diff_branch,
    git_has_changes,
    git_merge,
    git_push,
)
from .conflict_resolver import resolve_conflicts
from .prompts import (
    format_issue_body,
    generate_phase_pr_body_prompt,
    generate_pr_body_prompt,
    implement_issue_prompt,
    review_pr_prompt,
)
from .state import AgentState, IssueState, StepStatus

logger = logging.getLogger(__name__)


def slugify(title: str) -> str:
    """Convert issue title to a branch-name-safe slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    return slug[:50]


def get_existing_files_summary(project_dir: str) -> str:
    """Walk the project dir and return a file listing for context."""
    skip_dirs = {
        ".git", "node_modules", "__pycache__", "venv", ".venv",
        "dist", "build", ".next", "state",
    }
    files: list[str] = []
    for root, dirs, filenames in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
        for fname in filenames:
            rel_path = os.path.relpath(os.path.join(root, fname), project_dir)
            files.append(rel_path)
    return "\n".join(f"- {f}" for f in sorted(files))


def process_all_issues(
    state: AgentState,
    issues_data: list[dict],
    plan_content: str,
    state_path: str,
    max_retries: int = 2,
) -> None:
    """Main loop: process every issue in order, grouped by phase."""
    phases_in_order = sorted(set(iss["phase"] for iss in issues_data))
    cwd = state.project_dir

    for phase_num in phases_in_order:
        logger.info("\n" + "=" * 60)
        logger.info("  Phase %d", phase_num)
        logger.info("=" * 60)

        phase_issues = [
            (i, iss)
            for i, iss in enumerate(issues_data)
            if iss["phase"] == phase_num
        ]

        for idx, issue_data in phase_issues:
            issue_state = state.issues[idx]

            if issue_state.sub_step == "issue_closed":
                logger.info("Skipping completed issue: %s", issue_data["title"])
                continue

            logger.info(
                "\nProcessing issue %d/%d: %s",
                idx + 1, len(issues_data), issue_data["title"],
            )
            issue_state.status = StepStatus.IN_PROGRESS
            state.save(state_path)

            _process_single_issue(
                state, issue_state, issue_data, plan_content,
                state_path, cwd, max_retries,
            )

            issue_state.status = StepStatus.COMPLETED
            state.save(state_path)

        # Phase complete — merge staging into main
        if phase_num not in state.phases_merged:
            _merge_phase_to_main(state, phase_num, state_path, cwd, issues_data)


def _process_single_issue(
    state: AgentState,
    issue_state: IssueState,
    issue_data: dict,
    plan_content: str,
    state_path: str,
    cwd: str,
    max_retries: int,
) -> None:
    """Process one issue through all sub-steps. Resumes from last completed sub_step."""

    # Step 1: Create GitHub issue (no labels — they may not exist on the repo)
    if not issue_state.past_step("issue_created"):
        body = format_issue_body(issue_data)
        issue_number = gh_issue_create(
            title=issue_data["title"], body=body, labels=[], cwd=cwd,
        )
        issue_state.github_issue_number = issue_number
        issue_state.sub_step = "issue_created"
        state.save(state_path)
        logger.info("  Created GitHub issue #%d", issue_number)

    # Step 2: Create feature branch from staging
    if not issue_state.past_step("branch_created"):
        slug = slugify(issue_data["title"])
        branch_name = f"feature/issue-{issue_state.github_issue_number}-{slug}"
        issue_state.branch_name = branch_name

        git_checkout("staging", cwd)
        try:
            git(["pull", "origin", "staging"], cwd)
        except Exception:
            pass  # Remote may not be ahead

        git_checkout(branch_name, cwd, create=True)

        issue_state.sub_step = "branch_created"
        state.save(state_path)
        logger.info("  Created branch: %s", branch_name)

    # Step 3: Generate code with Claude Code
    if not issue_state.past_step("code_generated"):
        git_checkout(issue_state.branch_name, cwd)
        files_summary = get_existing_files_summary(cwd)
        prompt = implement_issue_prompt(
            issue_title=issue_data["title"],
            issue_body=format_issue_body(issue_data),
            plan_context=plan_content,
            existing_files_summary=files_summary,
        )

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                claude_code_implement(prompt, cwd=cwd, timeout=600)
                break
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(
                        "  Code generation attempt %d failed: %s, retrying...",
                        attempt + 1, e,
                    )
                else:
                    raise last_error

        issue_state.sub_step = "code_generated"
        state.save(state_path)
        logger.info("  Code generated")

    # Step 4: Commit and push
    if not issue_state.past_step("committed"):
        git_checkout(issue_state.branch_name, cwd)
        if git_has_changes(cwd):
            git_add_all(cwd)
            git_commit(
                f"Implement: {issue_data['title']}\n\n"
                f"Closes #{issue_state.github_issue_number}",
                cwd,
            )
        else:
            logger.warning("  No changes detected after code generation")

        git_push(cwd, issue_state.branch_name, set_upstream=True)

        issue_state.sub_step = "committed"
        state.save(state_path)
        logger.info("  Changes committed and pushed")

    # Step 5: Create PR with Claude-generated description
    if not issue_state.past_step("pr_created"):
        diff_text = git_diff_branch("staging", issue_state.branch_name, cwd)

        # Truncate large diffs to fit prompt limits
        if len(diff_text) > 15000:
            diff_text = diff_text[:15000] + "\n... [truncated]"

        issue_body = format_issue_body(issue_data)
        pr_body_prompt = generate_pr_body_prompt(
            issue_title=issue_data["title"],
            issue_body=issue_body,
            diff_text=diff_text,
        )
        pr_body = claude_generate(pr_body_prompt, cwd=cwd, timeout=120)

        # Prepend the issue reference
        pr_body = f"Implements #{issue_state.github_issue_number}\n\n{pr_body}"

        pr_number = gh_pr_create(
            title=issue_data["title"],
            body=pr_body,
            base="staging",
            head=issue_state.branch_name,
            cwd=cwd,
        )
        issue_state.pr_number = pr_number
        issue_state.sub_step = "pr_created"
        state.save(state_path)
        logger.info("  Created PR #%d", pr_number)

    # Step 6: Auto-review the PR
    if not issue_state.past_step("pr_reviewed"):
        diff_text = gh_pr_diff(issue_state.pr_number, cwd)

        # Truncate large diffs to fit prompt limits
        if len(diff_text) > 15000:
            diff_text = diff_text[:15000] + "\n... [truncated]"

        review = claude_generate(
            review_pr_prompt(diff_text, issue_data["title"]),
            timeout=120,
        )
        logger.info("  Review: %s", review)

        if review.strip().upper().startswith("CONCERNS"):
            logger.warning("  PR review flagged concerns — proceeding anyway")

        issue_state.sub_step = "pr_reviewed"
        state.save(state_path)

    # Step 7: Merge PR
    if not issue_state.past_step("pr_merged"):
        try:
            gh_pr_merge(
                issue_state.pr_number, cwd,
                squash=True, delete_branch=True,
            )
        except Exception as e:
            logger.warning("  gh pr merge failed: %s — attempting manual merge", e)
            _manual_merge_to_staging(state, issue_state, issue_data, cwd, state_path)

        # Update local staging to match remote
        git_checkout("staging", cwd)
        try:
            git(["pull", "origin", "staging"], cwd)
        except Exception:
            pass

        issue_state.sub_step = "pr_merged"
        state.save(state_path)
        logger.info("  PR merged into staging")

    # Step 8: Close issue
    if not issue_state.past_step("issue_closed"):
        gh_issue_close(
            issue_state.github_issue_number,
            cwd,
            comment=f"Implemented and merged via PR #{issue_state.pr_number}",
        )
        issue_state.sub_step = "issue_closed"
        state.save(state_path)
        logger.info("  Issue #%d closed", issue_state.github_issue_number)


def _manual_merge_to_staging(
    state: AgentState,
    issue_state: IssueState,
    issue_data: dict,
    cwd: str,
    state_path: str,
) -> None:
    """Fallback: merge feature branch into staging locally, handling conflicts."""
    git_checkout("staging", cwd)
    try:
        git(["pull", "origin", "staging"], cwd)
    except Exception:
        pass

    try:
        git_merge(issue_state.branch_name, cwd)
    except MergeConflictError:
        logger.warning("  Merge conflicts detected, resolving with Claude...")
        resolve_conflicts(cwd=cwd, feature_description=issue_data["title"])
        git_add_all(cwd)
        git_commit(
            f"Merge {issue_state.branch_name} into staging (conflicts resolved)\n\n"
            f"Closes #{issue_state.github_issue_number}",
            cwd,
        )

    git_push(cwd, "staging")


def _merge_phase_to_main(
    state: AgentState,
    phase_num: int,
    state_path: str,
    cwd: str,
    issues_data: list[dict] | None = None,
) -> None:
    """After all issues in a phase complete, merge staging -> main via PR."""
    logger.info("\n  Merging Phase %d: staging -> main", phase_num)

    # Generate a proper PR body using Claude
    diff_text = git_diff_branch("main", "staging", cwd)
    if len(diff_text) > 15000:
        diff_text = diff_text[:15000] + "\n... [truncated]"

    phase_issues = []
    if issues_data:
        phase_issues = [iss for iss in issues_data if iss["phase"] == phase_num]

    pr_body_prompt = generate_phase_pr_body_prompt(
        phase_num=phase_num,
        phase_issues=phase_issues,
        diff_text=diff_text,
    )
    pr_body = claude_generate(pr_body_prompt, cwd=cwd, timeout=120)

    # Create PR from staging to main
    pr_number = gh_pr_create(
        title=f"Phase {phase_num} complete — merge to main",
        body=pr_body,
        base="main",
        head="staging",
        cwd=cwd,
    )
    logger.info("  Created phase merge PR #%d", pr_number)

    gh_pr_merge(pr_number, cwd, squash=False, delete_branch=False)
    logger.info("  Phase %d PR merged", phase_num)

    # Sync local branches
    git_checkout("main", cwd)
    try:
        git(["pull", "origin", "main"], cwd)
    except Exception:
        pass

    git_checkout("staging", cwd)
    try:
        git(["pull", "origin", "staging"], cwd)
    except Exception:
        pass

    # Ensure staging is in sync with main for the next phase
    try:
        git_merge("main", cwd)
    except MergeConflictError:
        resolve_conflicts(cwd=cwd, feature_description=f"Phase {phase_num} sync")
        git_add_all(cwd)
        git_commit("Sync staging with main after phase merge", cwd)

    try:
        git_push(cwd, "staging")
    except Exception:
        pass

    state.phases_merged.append(phase_num)
    state.save(state_path)
    logger.info("  Phase %d merged to main successfully", phase_num)
