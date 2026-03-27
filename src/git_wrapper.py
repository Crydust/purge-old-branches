"""Git wrapper for interfacing with Git operations."""

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class BranchInfo:
    refname: str
    author_date: datetime
    committer_date: datetime

def _datetime_at_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    else:
        return dt.replace(tzinfo=timezone.utc)


class GitWrapper:
    """Wrapper around Git commands to manage branches and queries."""

    def __init__(self, repo_path: str = "."):
        """
        Initialize the Git wrapper.

        Args:
            repo_path: Path to the Git repository. Defaults to current directory.

        Raises:
            RuntimeError: If the path is not a valid Git repository.
        """
        self.repo_path = Path(repo_path)
        self._verify_git_repo()

    def _verify_git_repo(self) -> None:
        """Verify that the repo path is a valid Git repository."""
        # This breaks for worktrees and bare repos (where .git is a file, not a directory).
        # we could enhance this by checking for "git rev-parse --is-inside-work-tree" instead.
        # For simplicity we'll just check for .git directory.
        if not (self.repo_path / ".git").is_dir():
            raise RuntimeError(f"Path '{self.repo_path}' is not a valid Git repository")

    def _run_git(self, args: list[str]) -> str:
        """
        Run a git command and return stdout.

        Args:
            args: List of git command arguments (without 'git' prefix).

        Returns:
            The stdout output of the git command.

        Raises:
            subprocess.CalledProcessError: If the git command fails.
        """
        result = subprocess.run(
            ["git", "-C", str(self.repo_path)] + args,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def get_merged_branches(
        self, target_branch: str, is_remote: bool = False
    ) -> list[BranchInfo]:
        """
        Get a list of branches merged into the target branch.

        Args:
            target_branch: The target branch to check merges against.
            is_remote: If True, list remote branches; if False, list local branches.

        Returns:
            A list of BranchInfo objects representing branches merged into the target branch.
        """

        try:
            args = [
                "branch",
                "--list",
                "--no-color",
                "--format=%(refname) ?sep? %(authordate:iso8601-strict) ?sep? %(committerdate:iso8601-strict)",
            ]
            if is_remote:
                args.extend(["--remotes", "--merged", f"origin/{target_branch}"])
            else:
                args.extend(["--merged", target_branch])
            output = self._run_git(args)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to get merged branches for '{target_branch}': {e.stderr}"
            )

        branches = []
        for line in output.splitlines():
            a, b, c = line.split(" ?sep? ", maxsplit=2)
            if is_remote and a.startswith("refs/remotes/"):
                refname = a[len("refs/remotes/") :]
            elif not is_remote and a.startswith("refs/heads/"):
                refname = a[len("refs/heads/") :]
            else:
                print(f"Unexpected refname format: {a}, skipping")
                continue
            authordate = _datetime_at_utc(datetime.fromisoformat(b))
            committerdate = _datetime_at_utc(datetime.fromisoformat(c))
            if refname == target_branch or refname == f"origin/{target_branch}":
                continue
            branches.append(BranchInfo(refname, authordate, committerdate))

        return branches

    def delete_branches(
        self, branch_names: list[str], is_remote: bool = False, batch_size: int = 10
    ) -> None:
        """
        Delete multiple branches.

        Args:
            branch_names: List of branch names to delete.
            is_remote: If True, delete remote branch; if False, delete local branch.

        Raises:
            RuntimeError: If the deletion fails.
        """
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")

        for i in range(0, len(branch_names), batch_size):
            batch = branch_names[i : i + batch_size]
            if is_remote:
                # Use git push origin --delete for remote branches
                try:
                    self._run_git(["push", "origin", "--delete"] + batch)
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(
                        f"Failed to delete remote branches '{batch}': {e.stderr}"
                    )
            else:
                # Use git branch --delete for local branches
                try:
                    self._run_git(["branch", "--delete"] + batch)
                except subprocess.CalledProcessError as e:
                    raise RuntimeError(
                        f"Failed to delete local branches '{batch}': {e.stderr}"
                    )
