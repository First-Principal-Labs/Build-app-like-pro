"""Steps 1-3: Get idea from user, generate plan, generate issues JSON."""

from __future__ import annotations

import json
import logging
import os

from .cli_bridge import claude_generate
from .prompts import issues_json_prompt, plan_prompt
from .state import AgentState, IssueState

logger = logging.getLogger(__name__)


def get_idea_from_user() -> tuple[str, str]:
    """Interactive prompt for project idea and tech stack."""
    print("\n" + "=" * 60)
    print("  Development Orchestration Agent")
    print("=" * 60)

    idea = input("\nDescribe your project idea:\n> ").strip()
    if not idea:
        raise ValueError("Project idea cannot be empty")

    tech_stack = input(
        "\nPreferred tech stack (or press Enter to let the agent decide):\n> "
    ).strip()
    if not tech_stack:
        tech_stack = "Choose the best tech stack for this project"

    return idea, tech_stack


def generate_plan(state: AgentState, state_path: str) -> str:
    """Generate plan.md using Claude. Returns the plan content."""
    if state.plan_generated:
        logger.info("Plan already generated, loading from disk")
        plan_path = os.path.join(state.project_dir, "plan.md")
        with open(plan_path) as f:
            return f.read()

    logger.info("Generating project plan with Claude...")
    prompt = plan_prompt(state.project_idea, state.tech_stack)
    plan_content = claude_generate(prompt)

    # Write plan.md to project directory
    os.makedirs(state.project_dir, exist_ok=True)
    plan_path = os.path.join(state.project_dir, "plan.md")
    with open(plan_path, "w") as f:
        f.write(plan_content)

    state.plan_generated = True
    state.save(state_path)
    logger.info("Plan generated and saved to plan.md")
    return plan_content


def generate_issues_json(
    state: AgentState, plan_content: str, state_path: str
) -> list[dict]:
    """Convert plan into structured issues JSON. Returns list of issue dicts."""
    if state.issues_json_generated:
        logger.info("Issues JSON already generated, loading from disk")
        issues_path = os.path.join(state.project_dir, "issues.json")
        with open(issues_path) as f:
            return json.load(f)

    logger.info("Generating issues JSON from plan...")
    prompt = issues_json_prompt(plan_content)
    raw_output = claude_generate(prompt, timeout=600)

    # Parse JSON — handle markdown fences if Claude adds them
    cleaned = raw_output.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        cleaned = "\n".join(lines)

    issues = json.loads(cleaned)

    # Validate required fields
    for i, issue in enumerate(issues):
        required = ["title", "description", "phase", "priority"]
        missing = [k for k in required if k not in issue]
        if missing:
            raise ValueError(f"Issue {i} missing fields: {missing}")

    # Sort by phase then respect dependency order
    issues = _topological_sort_issues(issues)

    # Persist to state
    state.issues = [
        IssueState(
            index=i,
            title=issue["title"],
            phase=issue["phase"],
            priority=issue["priority"],
        )
        for i, issue in enumerate(issues)
    ]

    # Write raw JSON to disk for reference
    issues_path = os.path.join(state.project_dir, "issues.json")
    with open(issues_path, "w") as f:
        json.dump(issues, f, indent=2)

    state.issues_json_generated = True
    state.save(state_path)
    logger.info("Generated %d issues across phases", len(issues))
    return issues


def _topological_sort_issues(issues: list[dict]) -> list[dict]:
    """Sort: by phase first, then respect dependency ordering within each phase."""
    phases: dict[int, list[dict]] = {}
    for iss in issues:
        phases.setdefault(iss["phase"], []).append(iss)

    sorted_issues: list[dict] = []
    for phase_num in sorted(phases.keys()):
        phase_issues = phases[phase_num]
        resolved: set[str] = set()
        remaining = list(phase_issues)
        max_iters = len(remaining) ** 2 + 1
        iteration = 0

        while remaining and iteration < max_iters:
            iteration += 1
            for iss in list(remaining):
                deps = iss.get("dependencies", [])
                if all(d in resolved for d in deps):
                    sorted_issues.append(iss)
                    resolved.add(iss["title"])
                    remaining.remove(iss)

        # Append anything left (cycle or unresolvable deps)
        sorted_issues.extend(remaining)

    return sorted_issues
