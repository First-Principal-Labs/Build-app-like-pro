"""Central subprocess interface for claude, git, and gh CLI commands."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
import threading
import time

logger = logging.getLogger(__name__)

# ANSI colors for terminal output
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


# --- Exceptions ---


class CLIError(Exception):
    def __init__(self, command: str, returncode: int, stderr: str):
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"Command failed ({returncode}): {command}\n{stderr}")


class MergeConflictError(CLIError):
    pass


# --- Core runner ---


def _run(
    cmd: list[str],
    cwd: str | None = None,
    input_text: str | None = None,
    timeout: int = 600,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run a subprocess. All CLI calls route through here."""
    logger.debug("Running: %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        input=input_text,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        stderr_lower = result.stderr.lower()
        stdout_lower = result.stdout.lower()
        if "conflict" in stdout_lower or "merge conflict" in stderr_lower:
            raise MergeConflictError(" ".join(cmd), result.returncode, result.stderr)
        raise CLIError(" ".join(cmd), result.returncode, result.stderr)
    logger.debug("Output: %s", result.stdout[:500])
    return result


def _display_stream_event(event: dict, label: str) -> None:
    """Print a human-readable line for each stream-json event."""
    etype = event.get("type", "")

    if etype == "system":
        subtype = event.get("subtype", "")
        if subtype == "init":
            session = event.get("session_id", "")[:8]
            print(
                f"  {_CYAN}[{label}]{_RESET} Session started ({session}...)",
                file=sys.stderr, flush=True,
            )

    elif etype == "assistant":
        msg = event.get("message", {})
        # Show text content and tool_use calls
        for block in msg.get("content", []):
            if block.get("type") == "text":
                text = block["text"]
                # Show first 200 chars of text
                preview = text[:200].replace("\n", " ")
                if len(text) > 200:
                    preview += "..."
                print(
                    f"  {_CYAN}[{label}]{_RESET} {_BOLD}Assistant:{_RESET} {preview}",
                    file=sys.stderr, flush=True,
                )
            elif block.get("type") == "tool_use":
                tool = block.get("name", "?")
                inp = block.get("input", {})
                # Show key details per tool type
                detail = ""
                if tool == "Read":
                    detail = inp.get("file_path", "")
                elif tool == "Write":
                    detail = inp.get("file_path", "")
                elif tool == "Edit":
                    detail = inp.get("file_path", "")
                elif tool == "Bash":
                    detail = inp.get("command", "")[:120]
                elif tool == "Glob":
                    detail = inp.get("pattern", "")
                elif tool == "Grep":
                    detail = inp.get("pattern", "")
                else:
                    detail = str(inp)[:100]
                print(
                    f"  {_CYAN}[{label}]{_RESET} {_GREEN}Tool: {tool}{_RESET} {_DIM}{detail}{_RESET}",
                    file=sys.stderr, flush=True,
                )

    elif etype == "tool":
        # Tool result — show abbreviated
        content = event.get("content", "")
        if isinstance(content, list):
            # Extract text from content blocks
            texts = [b.get("text", "") for b in content if b.get("type") == "text"]
            content = " ".join(texts)
        preview = str(content)[:150].replace("\n", " ")
        if len(str(content)) > 150:
            preview += "..."
        print(
            f"  {_CYAN}[{label}]{_RESET} {_DIM}Result: {preview}{_RESET}",
            file=sys.stderr, flush=True,
        )

    elif etype == "result":
        cost = event.get("cost_usd", 0)
        turns = event.get("num_turns", 0)
        duration = event.get("duration_ms", 0) / 1000
        print(
            f"  {_CYAN}[{label}]{_RESET} {_YELLOW}Done!{_RESET} "
            f"({turns} turns, {duration:.1f}s, ${cost:.4f})",
            file=sys.stderr, flush=True,
        )


def _run_claude(
    cmd: list[str],
    cwd: str | None = None,
    input_text: str | None = None,
    timeout: int = 600,
    label: str = "claude",
) -> subprocess.CompletedProcess:
    """
    Run Claude CLI with stream-json output.
    Every event is displayed live in the terminal.
    The final result text is captured and returned.
    """
    logger.info("  [%s] Starting...", label)
    start = time.time()

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
    )

    # Write prompt to stdin and close
    if input_text:
        proc.stdin.write(input_text)
    proc.stdin.close()

    # Read stdout line-by-line (each line is a JSON event)
    result_text = ""
    read_done = threading.Event()

    def _read_and_display():
        nonlocal result_text
        try:
            for line in proc.stdout:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    event = json.loads(stripped)
                    _display_stream_event(event, label)
                    # Capture the final result
                    if event.get("type") == "result":
                        result_text = event.get("result", "")
                except json.JSONDecodeError:
                    # Not JSON — print raw
                    print(
                        f"  {_CYAN}[{label}]{_RESET} {stripped}",
                        file=sys.stderr, flush=True,
                    )
        finally:
            read_done.set()

    reader = threading.Thread(target=_read_and_display, daemon=True)
    reader.start()

    # Wait for process with timeout
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise subprocess.TimeoutExpired(cmd, timeout) from None

    read_done.wait(timeout=10)
    elapsed = int(time.time() - start)

    logger.info("  [%s] Process exited in %ds (code %d)", label, elapsed, proc.returncode)

    if proc.returncode != 0:
        raise CLIError(" ".join(cmd), proc.returncode, "(see terminal output above)")

    return subprocess.CompletedProcess(
        args=cmd,
        returncode=proc.returncode,
        stdout=result_text,
        stderr="",
    )


# --- Claude Code calls ---


def claude_generate(prompt: str, cwd: str | None = None, timeout: int = 600) -> str:
    """Call claude -p with sonnet for fast text generation. Full output visible."""
    result = _run_claude(
        [
            "claude", "-p",
            "--dangerously-skip-permissions",
            "--model", "sonnet",
            "--verbose",
            "--output-format", "stream-json",
            "--no-session-persistence",
        ],
        cwd=cwd,
        input_text=prompt,
        timeout=timeout,
        label="claude-generate",
    )
    return result.stdout.strip()


def claude_code_implement(prompt: str, cwd: str, timeout: int = 1800) -> str:
    """Call claude -p with full tool access. Full output visible."""
    result = _run_claude(
        [
            "claude", "-p",
            "--dangerously-skip-permissions",
            "--verbose",
            "--output-format", "stream-json",
            "--no-session-persistence",
        ],
        cwd=cwd,
        input_text=prompt,
        timeout=timeout,
        label="claude-code",
    )
    return result.stdout.strip()


# --- Git calls ---


def git(args: list[str], cwd: str, check: bool = True) -> str:
    result = _run(["git"] + args, cwd=cwd, check=check)
    return result.stdout.strip()


def git_checkout(branch: str, cwd: str, create: bool = False) -> str:
    args = ["checkout"]
    if create:
        args.append("-b")
    args.append(branch)
    return git(args, cwd)


def git_add_all(cwd: str) -> str:
    return git(["add", "-A"], cwd)


def git_commit(message: str, cwd: str) -> str:
    return git(["commit", "-m", message], cwd)


def git_push(cwd: str, branch: str | None = None, set_upstream: bool = False) -> str:
    args = ["push"]
    if set_upstream:
        args.extend(["-u", "origin"])
        if branch:
            args.append(branch)
    elif branch:
        args.extend(["origin", branch])
    return git(args, cwd)


def git_merge(branch: str, cwd: str, no_ff: bool = False) -> str:
    args = ["merge"]
    if no_ff:
        args.append("--no-ff")
    args.append(branch)
    result = _run(["git"] + args, cwd=cwd, check=True)
    return result.stdout.strip()


def git_has_changes(cwd: str) -> bool:
    result = _run(["git", "status", "--porcelain"], cwd=cwd, check=False)
    return bool(result.stdout.strip())


def git_conflicted_files(cwd: str) -> list[str]:
    result = _run(
        ["git", "diff", "--name-only", "--diff-filter=U"], cwd=cwd, check=False
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def git_current_branch(cwd: str) -> str:
    return git(["rev-parse", "--abbrev-ref", "HEAD"], cwd)


# --- GitHub (gh) calls ---


def gh_repo_create(
    name: str,
    cwd: str,
    private: bool = True,
    description: str = "",
) -> str:
    """Create a GitHub repo from the local directory. Returns the repo URL."""
    cmd = ["gh", "repo", "create", name]
    cmd.append("--private" if private else "--public")
    if description:
        cmd.extend(["--description", description])
    cmd.extend(["--source", cwd, "--push"])
    result = _run(cmd, cwd=cwd)
    return result.stdout.strip()


def gh_repo_clone(repo: str, target_dir: str) -> str:
    result = _run(["gh", "repo", "clone", repo, target_dir])
    return result.stdout.strip()


def gh_issue_create(title: str, body: str, labels: list[str], cwd: str) -> int:
    """Create a GitHub issue. Returns the issue number."""
    cmd = ["gh", "issue", "create", "--title", title, "--body", body]
    for label in labels:
        cmd.extend(["--label", label])
    result = _run(cmd, cwd=cwd)
    url = result.stdout.strip()
    match = re.search(r"/issues/(\d+)", url)
    if match:
        return int(match.group(1))
    raise CLIError("gh issue create", 0, f"Could not parse issue number from: {url}")


def gh_pr_create(
    title: str, body: str, base: str, head: str, cwd: str
) -> int:
    """Create a PR. Returns the PR number."""
    cmd = [
        "gh", "pr", "create",
        "--title", title,
        "--body", body,
        "--base", base,
        "--head", head,
    ]
    result = _run(cmd, cwd=cwd)
    url = result.stdout.strip()
    match = re.search(r"/pull/(\d+)", url)
    if match:
        return int(match.group(1))
    raise CLIError("gh pr create", 0, f"Could not parse PR number from: {url}")


def gh_pr_merge(
    pr_number: int, cwd: str, squash: bool = True, delete_branch: bool = True
) -> str:
    cmd = ["gh", "pr", "merge", str(pr_number), "--admin"]
    if squash:
        cmd.append("--squash")
    else:
        cmd.append("--merge")
    if delete_branch:
        cmd.append("--delete-branch")
    result = _run(cmd, cwd=cwd)
    return result.stdout.strip()


def gh_pr_diff(pr_number: int, cwd: str) -> str:
    result = _run(["gh", "pr", "diff", str(pr_number)], cwd=cwd)
    return result.stdout


def gh_issue_close(
    issue_number: int, cwd: str, comment: str = ""
) -> str:
    cmd = ["gh", "issue", "close", str(issue_number), "--reason", "completed"]
    if comment:
        cmd.extend(["--comment", comment])
    result = _run(cmd, cwd=cwd)
    return result.stdout.strip()
