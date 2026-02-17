#!/usr/bin/env python3
"""
Development Orchestration Agent

Usage:
    python -m dev_agent                              # Fresh start
    python -m dev_agent --resume --project-dir /path # Resume from saved state
    python -m dev_agent --repo owner/repo            # Use existing GitHub repo
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from .config import AgentConfig
from .issue_processor import process_all_issues
from .planner import generate_issues_json, generate_plan, get_idea_from_user
from .repo_manager import create_staging_branch, generate_scaffolding, setup_repo
from .state import AgentState


def main() -> None:
    parser = argparse.ArgumentParser(description="Development Orchestration Agent")
    parser.add_argument(
        "--resume", action="store_true", help="Resume from saved state"
    )
    parser.add_argument(
        "--repo", type=str, default="", help="Existing repo (owner/name)"
    )
    parser.add_argument(
        "--project-dir", type=str, default="", help="Local project directory"
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO", help="Logging level"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    config = AgentConfig(log_level=args.log_level)

    # --- Determine state path and load or create state ---

    state: AgentState | None = None
    state_path: str = ""

    if args.resume:
        project_dir = args.project_dir or os.getcwd()
        state_path = os.path.join(project_dir, config.state_filename)
        if os.path.exists(state_path):
            state = AgentState.load(state_path)
            logger.info("Resumed state from %s", state_path)
        else:
            logger.error("No state file found at %s", state_path)
            sys.exit(1)

    if state is None:
        # Fresh start — gather user input
        idea, tech_stack = get_idea_from_user()

        repo_name = input("\nRepository name (e.g., my-cool-app):\n> ").strip()
        if not repo_name:
            # Generate a default name from the first word of the idea
            repo_name = idea.split()[0].lower() + "-app"

        if args.project_dir:
            project_dir = args.project_dir
        else:
            # Default: create under the projects/ directory
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            projects_dir = os.path.join(base, "projects")
            os.makedirs(projects_dir, exist_ok=True)
            project_dir = os.path.join(projects_dir, repo_name)

        state = AgentState(
            project_idea=idea,
            tech_stack=tech_stack,
            repo_name=repo_name,
            project_dir=project_dir,
        )
        state_path = os.path.join(project_dir, config.state_filename)
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        state.save(state_path)
        logger.info("Project directory: %s", project_dir)

    # --- Execute pipeline ---

    try:
        # Step 1-2: Generate plan
        logger.info("\n=== Step: Generate Plan ===")
        plan_content = generate_plan(state, state_path)

        # Step 3: Generate issues JSON
        logger.info("\n=== Step: Generate Issues ===")
        issues_data = generate_issues_json(state, plan_content, state_path)
        logger.info("Total issues: %d", len(issues_data))

        # Step 4: Create/connect repo
        logger.info("\n=== Step: Setup Repository ===")
        use_existing = bool(args.repo)
        setup_repo(
            state,
            state_path,
            use_existing=use_existing,
            existing_repo=args.repo,
        )

        # Step 5: Generate scaffolding
        logger.info("\n=== Step: Generate Scaffolding ===")
        generate_scaffolding(state, plan_content, state_path)

        # Step 6: Create staging branch
        logger.info("\n=== Step: Create Staging Branch ===")
        create_staging_branch(state, state_path)

        # Steps 7-8: Process all issues
        logger.info("\n=== Step: Process Issues ===")
        process_all_issues(
            state,
            issues_data,
            plan_content,
            state_path,
            max_retries=config.max_retries,
        )

        # Done!
        print("\n" + "=" * 60)
        print("  ALL PHASES COMPLETE")
        print(f"  Repository: https://github.com/{state.repo_full_name}")
        print("=" * 60)

    except KeyboardInterrupt:
        logger.info("\n\nInterrupted. Run with --resume to continue.")
        state.save(state_path)
        sys.exit(130)

    except Exception as e:
        logger.error("Fatal error: %s", e, exc_info=True)
        logger.info("State saved. Run with --resume --project-dir %s", state.project_dir)
        state.save(state_path)
        sys.exit(1)


if __name__ == "__main__":
    main()
