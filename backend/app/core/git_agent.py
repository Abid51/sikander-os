"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS GIT AGENT — Real Git Operations
  commit, push, pull, diff, log, branch, status — all via subprocess
  No fake stubs — actual git commands with output capture
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GitResult:
    command: str
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float
    success: bool
    repo_path: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GitStatus:
    branch: str
    ahead: int
    behind: int
    staged: List[str]
    modified: List[str]
    untracked: List[str]
    clean: bool
    last_commit: str
    last_commit_msg: str
    repo_path: str

    def to_dict(self) -> dict:
        return asdict(self)


# ─────────────────────────────────────────────────────────────────────────────
#  GIT AGENT
# ─────────────────────────────────────────────────────────────────────────────

class IgrisGitAgent:
    """
    Real Git agent for Igris — executes actual git commands.

    Usage:
    ─────
    agent = IgrisGitAgent("/path/to/repo")
    status = await agent.status()
    result = await agent.commit("feat: added awesome feature")
    result = await agent.push()
    diff = await agent.diff()
    log = await agent.log(limit=10)
    """

    def __init__(self, repo_path: Optional[str] = None) -> None:
        self._repo_path = os.path.abspath(repo_path or os.getcwd())
        self._history: List[GitResult] = []
        logger.info(f"[GIT] Agent initialized for: {self._repo_path}")

    def set_repo(self, path: str) -> None:
        """Change the working repository."""
        self._repo_path = os.path.abspath(path)
        logger.info(f"[GIT] Switched to repo: {self._repo_path}")

    def _is_git_repo(self) -> bool:
        """Check if path is a git repository."""
        return os.path.isdir(os.path.join(self._repo_path, ".git"))

    async def _run(self, *args: str, cwd: Optional[str] = None) -> GitResult:
        """Run a git command asynchronously."""
        cmd = ["git"] + list(args)
        work_dir = cwd or self._repo_path
        t_start = time.time()

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            result = GitResult(
                command=" ".join(cmd),
                stdout=stdout.decode("utf-8", errors="replace").strip(),
                stderr=stderr.decode("utf-8", errors="replace").strip(),
                exit_code=proc.returncode,
                duration_ms=(time.time() - t_start) * 1000,
                success=(proc.returncode == 0),
                repo_path=work_dir,
            )
        except asyncio.TimeoutError:
            result = GitResult(
                command=" ".join(cmd), stdout="", stderr="Command timed out (60s)",
                exit_code=-1, duration_ms=(time.time() - t_start) * 1000,
                success=False, repo_path=work_dir,
            )
        except Exception as e:
            result = GitResult(
                command=" ".join(cmd), stdout="", stderr=str(e),
                exit_code=-1, duration_ms=(time.time() - t_start) * 1000,
                success=False, repo_path=work_dir,
            )

        self._history.append(result)
        if not result.success:
            logger.warning(f"[GIT] Command failed: {result.command}\n{result.stderr}")
        return result

    # ── Core Operations ───────────────────────────────────────────────────────

    async def status(self) -> GitStatus:
        """Get full repository status."""
        # Branch
        branch_r = await self._run("rev-parse", "--abbrev-ref", "HEAD")
        branch = branch_r.stdout if branch_r.success else "unknown"

        # Ahead/behind
        ahead, behind = 0, 0
        try:
            ab_r = await self._run("rev-list", "--left-right", "--count", f"origin/{branch}...HEAD")
            if ab_r.success and "\t" in ab_r.stdout:
                b, a = ab_r.stdout.split("\t")
                behind, ahead = int(b), int(a)
        except Exception:
            pass

        # Status porcelain
        stat_r = await self._run("status", "--porcelain=v1")
        staged, modified, untracked = [], [], []
        for line in stat_r.stdout.splitlines():
            if len(line) < 3:
                continue
            x, y = line[0], line[1]
            filename = line[3:].strip()
            if x in ("A", "M", "D", "R"):
                staged.append(filename)
            if y == "M":
                modified.append(filename)
            if x == "?" and y == "?":
                untracked.append(filename)

        # Last commit
        last_r = await self._run("log", "--oneline", "-1")
        last_commit, last_msg = "", ""
        if last_r.success and last_r.stdout:
            parts = last_r.stdout.split(" ", 1)
            last_commit = parts[0]
            last_msg = parts[1] if len(parts) > 1 else ""

        return GitStatus(
            branch=branch,
            ahead=ahead,
            behind=behind,
            staged=staged,
            modified=modified,
            untracked=untracked,
            clean=not staged and not modified and not untracked,
            last_commit=last_commit,
            last_commit_msg=last_msg,
            repo_path=self._repo_path,
        )

    async def diff(self, staged: bool = False, filename: Optional[str] = None) -> GitResult:
        """Get diff of changes."""
        args = ["diff"]
        if staged:
            args.append("--cached")
        if filename:
            args.append(filename)
        return await self._run(*args)

    async def log(self, limit: int = 10, oneline: bool = True) -> GitResult:
        """Get commit history."""
        args = ["log", f"-{limit}"]
        if oneline:
            args.append("--oneline")
        else:
            args += ["--format=%h %an %ar: %s"]
        return await self._run(*args)

    async def add(self, *files: str) -> GitResult:
        """Stage files for commit."""
        if not files:
            return await self._run("add", "-A")
        return await self._run("add", *files)

    async def commit(self, message: str, add_all: bool = True) -> GitResult:
        """Create a commit."""
        if add_all:
            add_r = await self._run("add", "-A")
            if not add_r.success:
                return add_r
        return await self._run("commit", "-m", message)

    async def push(self, remote: str = "origin", branch: Optional[str] = None) -> GitResult:
        """Push commits to remote."""
        if branch:
            return await self._run("push", remote, branch)
        return await self._run("push", remote)

    async def pull(self, remote: str = "origin", branch: Optional[str] = None) -> GitResult:
        """Pull latest changes."""
        if branch:
            return await self._run("pull", remote, branch)
        return await self._run("pull")

    async def create_branch(self, name: str, checkout: bool = True) -> GitResult:
        """Create a new branch."""
        if checkout:
            return await self._run("checkout", "-b", name)
        return await self._run("branch", name)

    async def checkout(self, branch_or_commit: str) -> GitResult:
        """Checkout a branch or commit."""
        return await self._run("checkout", branch_or_commit)

    async def stash(self, message: Optional[str] = None) -> GitResult:
        """Stash uncommitted changes."""
        args = ["stash", "push"]
        if message:
            args += ["-m", message]
        return await self._run(*args)

    async def stash_pop(self) -> GitResult:
        """Pop the last stash."""
        return await self._run("stash", "pop")

    async def clone(self, url: str, dest: Optional[str] = None) -> GitResult:
        """Clone a repository."""
        args = ["clone", url]
        if dest:
            args.append(dest)
        return await self._run(*args, cwd=os.path.dirname(self._repo_path))

    async def tag(self, tag_name: str, message: Optional[str] = None) -> GitResult:
        """Create a tag."""
        if message:
            return await self._run("tag", "-a", tag_name, "-m", message)
        return await self._run("tag", tag_name)

    async def merge(self, branch: str) -> GitResult:
        """Merge a branch into current."""
        return await self._run("merge", branch)

    async def revert(self, commit_hash: str = "HEAD") -> GitResult:
        """Revert a commit."""
        return await self._run("revert", "--no-edit", commit_hash)

    async def reset(self, mode: str = "--soft", ref: str = "HEAD~1") -> GitResult:
        """Reset to a previous state. Use with caution."""
        return await self._run("reset", mode, ref)

    async def init(self, path: Optional[str] = None) -> GitResult:
        """Initialize a new git repository."""
        target = path or self._repo_path
        return await self._run("init", cwd=target)

    async def list_branches(self) -> Dict[str, Any]:
        """List all branches (local and remote)."""
        local_r = await self._run("branch")
        remote_r = await self._run("branch", "-r")
        return {
            "local": [b.strip().lstrip("* ") for b in local_r.stdout.splitlines() if b.strip()],
            "remote": [b.strip() for b in remote_r.stdout.splitlines() if b.strip()],
        }

    async def get_remotes(self) -> GitResult:
        """List configured remotes."""
        return await self._run("remote", "-v")

    async def add_remote(self, name: str, url: str) -> GitResult:
        """Add a remote."""
        return await self._run("remote", "add", name, url)

    async def generate_commit_message(self, diff_text: str) -> str:
        """Use LLM to generate a commit message from diff."""
        try:
            from app.core.llm_manager import universal_llm
            msg = await universal_llm.generate_response(
                system_prompt=(
                    "Generate a concise, conventional commit message (max 72 chars) "
                    "from the following diff. Format: <type>(<scope>): <description>\n"
                    "Types: feat, fix, docs, style, refactor, test, chore\n"
                    "Return ONLY the commit message, nothing else."
                ),
                user_prompt=f"Diff:\n{diff_text[:3000]}",
                max_tokens=100,
            )
            return msg.strip()
        except Exception:
            return "chore: update files"

    async def smart_commit(self, message: Optional[str] = None) -> GitResult:
        """
        AI-powered commit: stages all changes, generates commit message if not provided, commits.
        """
        # Stage all
        await self.add()

        # Get diff for AI message
        if not message:
            diff_r = await self._run("diff", "--cached", "--stat")
            message = await self.generate_commit_message(diff_r.stdout)

        return await self.commit(message, add_all=False)

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get command history."""
        return [r.to_dict() for r in self._history[-limit:]]

    def get_status_summary(self) -> Dict[str, Any]:
        return {
            "repo_path": self._repo_path,
            "is_git_repo": self._is_git_repo(),
            "commands_run": len(self._history),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[IgrisGitAgent] = None


def get_git_agent(repo_path: Optional[str] = None) -> IgrisGitAgent:
    global _instance
    if _instance is None:
        _instance = IgrisGitAgent(repo_path)
    elif repo_path:
        _instance.set_repo(repo_path)
    return _instance
