# Dev Agent - Development Orchestration Agent

An autonomous Python agent that takes a project idea, generates a development plan, creates GitHub issues, and implements every feature end-to-end using Claude Code CLI — complete with branching, pull requests, code reviews, and phase-based merges.

## How It Works

```
User Input (idea + tech stack)
        │
        ▼
  Generate plan.md (Claude)
        │
        ▼
  Generate issues.json (Claude)
        │
        ▼
  Create GitHub repo + scaffolding
        │
        ▼
  Create staging branch
        │
        ▼
  ┌─── For each issue (grouped by phase) ──┐
  │  1. Create GitHub issue                 │
  │  2. Create feature branch from staging  │
  │  3. Implement with Claude Code          │
  │  4. Commit and push                     │
  │  5. Create PR → staging                 │
  │  6. Auto-review PR                      │
  │  7. Merge PR (squash)                   │
  │  8. Close issue                         │
  └─────────────────────────────────────────┘
        │
        ▼ (after each phase)
  Merge staging → main via PR
```

## Prerequisites

- **Python 3.10+**
- **Claude Code CLI** — installed and authenticated
  ```bash
  npm install -g @anthropic-ai/claude-code
  ```
- **GitHub CLI (`gh`)** — installed and authenticated
  ```bash
  brew install gh
  gh auth login
  ```
- **Git** — configured with name and email
  ```bash
  git config --global user.name "Your Name"
  git config --global user.email "you@example.com"
  ```

## Installation

No extra dependencies required — the agent uses only Python standard library modules.

```bash
git clone <this-repo-url>
cd Build-app-like-pro
```

## Usage

### Fresh Start

```bash
python -m dev_agent
```

You'll be prompted for:
1. **Project idea** — describe what you want to build
2. **Tech stack** — specify preferred technologies (or let the agent decide)
3. **Repository name** — name for the GitHub repo

### Resume After Interruption

The agent saves progress after every sub-step. If it gets interrupted (Ctrl+C, crash, timeout), resume from exactly where it left off:

```bash
python -m dev_agent --resume --project-dir /path/to/project
```

### Use an Existing Repository

```bash
python -m dev_agent --repo owner/repo-name
```

### CLI Options

| Flag | Description |
|------|-------------|
| `--resume` | Resume from saved state |
| `--repo OWNER/NAME` | Use an existing GitHub repository |
| `--project-dir PATH` | Set local project directory |
| `--log-level LEVEL` | Set logging level (DEBUG, INFO, WARNING, ERROR) |

## Project Structure

```
dev_agent/
  __init__.py            # Package marker
  __main__.py            # CLI entry point and pipeline orchestration
  config.py              # AgentConfig dataclass (timeouts, retries, settings)
  state.py               # AgentState + IssueState with atomic JSON persistence
  cli_bridge.py          # Subprocess interface for claude, git, and gh CLIs
  planner.py             # Plan generation and issues JSON creation
  repo_manager.py        # Repo creation, scaffolding, staging branch
  issue_processor.py     # Main issue processing loop and phase merges
  conflict_resolver.py   # Merge conflict detection and Claude-based resolution
  prompts.py             # All prompt templates
```

## Branching Strategy

```
main ← staging ← feature/issue-{N}-{slug}
```

- **main** — stable, receives phase merges only
- **staging** — integration branch, all feature PRs target here
- **feature branches** — one per issue, created from staging, squash-merged back

## State & Resumability

The agent persists its state to `state/agent_state.json` inside the project directory. Each issue tracks its progress through 9 sub-steps:

`not_started` → `issue_created` → `branch_created` → `code_generated` → `committed` → `pr_created` → `pr_reviewed` → `pr_merged` → `issue_closed`

On resume, completed sub-steps are skipped automatically.

## Conflict Resolution

When merge conflicts occur:
1. The agent first tries `gh pr merge` (GitHub-side merge)
2. If that fails, it falls back to local `git merge`
3. Conflicted files are sent to Claude for resolution
4. Resolved files are committed and pushed

## Example

```bash
$ python -m dev_agent

============================================================
  Development Orchestration Agent
============================================================

Describe your project idea:
> A todo CLI app in Python with add, list, complete, and delete commands

Preferred tech stack (or press Enter to let the agent decide):
> Python, Click, SQLite

Repository name (e.g., my-cool-app):
> todo-cli

# Agent takes over from here:
# - Generates plan.md
# - Creates 12 GitHub issues across 3 phases
# - Creates repo, scaffolding, staging branch
# - Implements each issue with Claude Code
# - Creates PRs, reviews, merges
# - Merges each phase to main
```
