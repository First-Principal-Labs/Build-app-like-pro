"""All prompt templates used by the orchestration agent."""


def plan_prompt(idea: str, tech_stack: str) -> str:
    return f"""You are a senior software architect. Create a detailed project plan in Markdown for the following project.

## Project Idea
{idea}

## Tech Stack
{tech_stack}

## Required Output Format
Output ONLY the plan in this exact Markdown structure:

# Project Plan: [Project Name]

## Overview
[2-3 sentence summary]

## Tech Stack
[List all technologies]

## Phases
For each phase:
### Phase N: [Phase Name]
**Goal:** [What this phase accomplishes]

#### Features:
For each feature:
- **Feature Name**: [Description]
  - Function/component signatures and responsibilities
  - Files to create or modify

#### Dependencies:
- [What must be completed before this phase]

## File Structure
[Expected directory tree at project completion]

Rules:
- Order phases by dependency (Phase 1 has no deps)
- Each phase should be independently testable
- Keep phases small (2-5 features each)
- Be specific about function names, file paths, and data structures
"""


def issues_json_prompt(plan_content: str) -> str:
    return f"""You are converting a project plan into a JSON array of GitHub issues.

## The Plan
{plan_content}

## Required Output
Return ONLY a valid JSON array. No markdown fences, no explanation, just the JSON.

Each element must have exactly these fields:
{{
    "title": "Short descriptive title",
    "description": "Detailed description of what to implement",
    "problem_statement": "Why this is needed",
    "proposed_solution": "How to implement it",
    "technical_details": "Specific functions, files, data structures",
    "acceptance_criteria": ["Criterion 1", "Criterion 2"],
    "expected_outcome": "What success looks like",
    "optional_enhancements": ["Enhancement 1"],
    "related_files": ["path/to/file.ext"],
    "phase": 1,
    "priority": "high",
    "dependencies": [],
    "labels": ["phase-1", "feature"]
}}

Rules:
- Order issues so dependencies come first within each phase
- The "dependencies" field contains titles of other issues this depends on
- Every issue must have a phase number matching the plan
- Make titles concise but unique
- Include setup/infrastructure issues in Phase 1
- priority is one of: "high", "medium", "low"
"""


def scaffolding_prompt(idea: str, tech_stack: str, plan_content: str) -> str:
    return f"""You are setting up the initial project scaffolding.

## Project
{idea}

## Tech Stack
{tech_stack}

## Plan Overview
{plan_content}

## Instructions
1. Create all necessary directories
2. Create configuration files (package.json, requirements.txt, tsconfig.json, etc. as appropriate)
3. Create entry point files with minimal boilerplate
4. Create a .gitignore appropriate for the tech stack
5. Do NOT implement any features yet — only scaffolding
6. Make sure the project can at least start/compile with no errors after scaffolding

Create all files now.
"""


def implement_issue_prompt(
    issue_title: str,
    issue_body: str,
    plan_context: str,
    existing_files_summary: str,
) -> str:
    return f"""You are implementing a specific feature for an existing project.

## Issue to Implement
**Title:** {issue_title}

**Details:**
{issue_body}

## Project Plan Context
{plan_context}

## Existing Project Files
{existing_files_summary}

## Instructions
1. Read the existing code to understand the current state
2. Implement ONLY what this issue describes — nothing more
3. Follow existing code conventions and patterns
4. Write clean, production-ready code
5. Add tests if appropriate for this feature
6. Do not modify files unrelated to this issue
7. Make sure the project still compiles/runs after your changes

Implement the feature now.
"""


def format_issue_body(issue_data: dict) -> str:
    """Format an issue dict into the GitHub issue markdown template."""
    criteria = "\n".join(
        f"- [ ] {c}" for c in issue_data.get("acceptance_criteria", [])
    )
    enhancements = "\n".join(
        f"- {e}" for e in issue_data.get("optional_enhancements", [])
    )
    related = "\n".join(
        f"- `{f}`" for f in issue_data.get("related_files", [])
    )

    return f"""## Description

{issue_data.get('description', '')}

## Problem Statement

{issue_data.get('problem_statement', '')}

## Proposed Solution

{issue_data.get('proposed_solution', '')}

## Technical Details

{issue_data.get('technical_details', '')}

## Acceptance Criteria

{criteria}

## Expected Outcome

{issue_data.get('expected_outcome', '')}

## Optional Enhancements (Future Scope)

{enhancements}

## Related Files

{related}

## Notes / References

Phase: {issue_data.get('phase', 'N/A')} | Priority: {issue_data.get('priority', 'N/A')}
Dependencies: {', '.join(issue_data.get('dependencies', [])) or 'None'}
"""


def review_pr_prompt(diff_text: str, issue_title: str) -> str:
    return f"""You are reviewing a pull request for the issue: "{issue_title}"

Here is the diff:

```diff
{diff_text}
```

Evaluate:
1. Does the diff implement what the issue asked for?
2. Are there any obvious bugs, security issues, or missing error handling?
3. Does it look like a reasonable implementation?

Respond with either:
APPROVED - [brief reason]
or
CONCERNS - [list specific concerns]

Keep your response to 2-3 sentences maximum.
"""


def resolve_conflict_prompt(
    conflicted_file_contents: str,
    file_path: str,
    feature_description: str,
) -> str:
    return f"""You are resolving a merge conflict in: {file_path}

The file contains merge conflict markers (<<<<<<, ======, >>>>>>).

## Context
This conflict arose while merging a feature branch into staging.
Feature being implemented: {feature_description}

## File with conflicts:
```
{conflicted_file_contents}
```

## Instructions
1. Resolve the conflict by keeping both changes where possible
2. Prefer the feature branch changes when there is a true conflict
3. Remove ALL conflict markers (<<<<<<, ======, >>>>>>)
4. Output ONLY the resolved file contents — no explanations, no markdown fences

Output the resolved file now:
"""
