"""Steps 4-6: Create repo, generate scaffolding, create staging branch."""

from __future__ import annotations

import logging
import os

from .cli_bridge import (
    claude_code_implement,
    gh_repo_clone,
    gh_repo_create,
    git,
    git_add_all,
    git_checkout,
    git_commit,
    git_push,
)
from .prompts import scaffolding_prompt
from .state import AgentState

logger = logging.getLogger(__name__)


def setup_repo(
    state: AgentState,
    state_path: str,
    use_existing: bool = False,
    existing_repo: str = "",
) -> None:
    """Create or connect to a GitHub repo, initialize local directory."""
    if state.repo_created:
        logger.info("Repo already created, skipping")
        return

    project_dir = state.project_dir
    os.makedirs(project_dir, exist_ok=True)

    if use_existing:
        state.repo_full_name = existing_repo
        state.repo_name = existing_repo.split("/")[-1]
        gh_repo_clone(existing_repo, project_dir)
    else:
        # Initialize local git repo
        if not os.path.exists(os.path.join(project_dir, ".git")):
            git(["init"], project_dir)
            git(["branch", "-M", "main"], project_dir)

            # Create initial README
            readme_path = os.path.join(project_dir, "README.md")
            with open(readme_path, "w") as f:
                f.write(f"# {state.repo_name}\n\n{state.project_idea}\n")

            # Ensure state dir is always gitignored
            gitignore_path = os.path.join(project_dir, ".gitignore")
            gitignore_lines = []
            if os.path.exists(gitignore_path):
                with open(gitignore_path) as f:
                    gitignore_lines = f.read().splitlines()
            if "state/" not in gitignore_lines:
                with open(gitignore_path, "a") as f:
                    f.write("\n# Agent state\nstate/\n")

            git_add_all(project_dir)
            git_commit("Initial commit", project_dir)

        # Create GitHub remote
        description = state.project_idea[:200]
        url = gh_repo_create(
            state.repo_name, project_dir, private=True, description=description
        )
        logger.info("GitHub repo created: %s", url)

        # Parse owner/repo from the URL (first line of output)
        # gh repo create --push can output multiple lines
        first_line = url.split("\n")[0].strip()
        import re as _re
        match = _re.search(r"github\.com/([^/\s]+/[^/\s]+)", first_line)
        if match:
            state.repo_full_name = match.group(1)
        else:
            state.repo_full_name = state.repo_name

    state.repo_created = True
    state.save(state_path)
    logger.info("Repo ready: %s", state.repo_full_name)


def generate_scaffolding(
    state: AgentState,
    plan_content: str,
    state_path: str,
) -> None:
    """Generate initial project scaffolding using Claude Code."""
    if state.scaffolding_done:
        logger.info("Scaffolding already done, skipping")
        return

    logger.info("Generating project scaffolding with Claude Code...")
    prompt = scaffolding_prompt(state.project_idea, state.tech_stack, plan_content)
    claude_code_implement(prompt, cwd=state.project_dir, timeout=600)

    # Commit and push scaffolding
    git_add_all(state.project_dir)
    try:
        git_commit("Add initial project scaffolding", state.project_dir)
        git_push(state.project_dir)
    except Exception as e:
        logger.warning("Commit/push scaffolding: %s", e)

    state.scaffolding_done = True
    state.save(state_path)
    logger.info("Scaffolding generated and pushed")


def create_staging_branch(state: AgentState, state_path: str) -> None:
    """Create staging branch from main."""
    if state.staging_branch_created:
        logger.info("Staging branch already exists, skipping")
        return

    cwd = state.project_dir

    # Ensure we're on main and up to date
    git_checkout("main", cwd)
    try:
        git(["pull", "origin", "main"], cwd)
    except Exception:
        pass  # May fail if remote has no additional commits

    # Create and push staging
    git_checkout("staging", cwd, create=True)
    git_push(cwd, "staging", set_upstream=True)

    state.staging_branch_created = True
    state.save(state_path)
    logger.info("Staging branch created and pushed")
