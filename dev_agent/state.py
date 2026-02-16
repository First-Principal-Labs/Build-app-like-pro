from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Optional


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# Ordered sub-steps for each issue's lifecycle
SUB_STEPS = [
    "not_started",
    "issue_created",
    "branch_created",
    "code_generated",
    "committed",
    "pr_created",
    "pr_reviewed",
    "pr_merged",
    "issue_closed",
]


@dataclass
class IssueState:
    index: int
    title: str
    phase: int
    priority: str
    github_issue_number: Optional[int] = None
    branch_name: Optional[str] = None
    pr_number: Optional[int] = None
    status: str = StepStatus.PENDING
    sub_step: str = "not_started"

    def past_step(self, step_name: str) -> bool:
        """Return True if this issue has already completed the given sub-step."""
        current_idx = SUB_STEPS.index(self.sub_step)
        target_idx = SUB_STEPS.index(step_name)
        return current_idx >= target_idx


@dataclass
class AgentState:
    # Project identity
    project_idea: str = ""
    tech_stack: str = ""
    repo_name: str = ""
    repo_full_name: str = ""  # owner/repo
    project_dir: str = ""  # Local path to the project

    # Pipeline step-completion flags
    plan_generated: bool = False
    issues_json_generated: bool = False
    repo_created: bool = False
    scaffolding_done: bool = False
    staging_branch_created: bool = False

    # Issues list
    issues: list[IssueState] = field(default_factory=list)

    # Phase tracking
    phases_merged: list[int] = field(default_factory=list)

    # --- Persistence ---

    def save(self, path: str) -> None:
        """Atomic write: write to temp file then rename."""
        dir_name = os.path.dirname(path)
        os.makedirs(dir_name, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(asdict(self), f, indent=2)
            os.replace(tmp_path, path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    @classmethod
    def load(cls, path: str) -> AgentState:
        with open(path) as f:
            data = json.load(f)
        state = cls()
        for key, value in data.items():
            if key == "issues":
                state.issues = [IssueState(**iss) for iss in value]
            else:
                setattr(state, key, value)
        return state
