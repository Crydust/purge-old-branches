"""Git wrapper for interfacing with Git operations."""

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class BranchInfo:
    refname: str
    authordate: datetime
    committerdate: datetime


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
        try:
            self._run_git(["rev-parse", "--git-dir"])
        except subprocess.CalledProcessError:
            raise RuntimeError(f"'{self.repo_path}' is not a valid Git repository")

    def _run_git(self, args: List[str]) -> str:
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
    ) -> List[BranchInfo]:
        """
        Get a list of branches merged into the target branch.

        Args:
            target_branch: The target branch to check merges against.
            is_remote: If True, list remote branches; if False, list local branches.

        Returns:
            A list of branch names merged into the target branch.
        """

        try:
            args = ["branch", "--list", "--no-color",
                    '--format=%(refname), %(authordate:iso8601-strict), %(committerdate:iso8601-strict)']
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
            a, b, c = line.split(", ")
            if is_remote and a.startswith("refs/remotes/"):
                refname = a[len("refs/remotes/"):]
            elif not is_remote and a.startswith("refs/heads/"):
                refname = a[len("refs/heads/"):]
            else:
                print(f"Unexpected refname format: {a}, skipping")
                continue
            authordate = _datetime_at_utc(datetime.fromisoformat(b))
            committerdate = _datetime_at_utc(datetime.fromisoformat(c))
            if refname == target_branch or refname == f"origin/{target_branch}":
                continue
            branches.append(BranchInfo(refname, authordate, committerdate))

        return branches


def _datetime_at_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    else:
        return dt.replace(tzinfo=timezone.utc)


def delete_branch(self, branch_name: str, is_remote: bool = False) -> None:
    """
    Delete a branch.

    Args:
        branch_name: Name of the branch to delete.
        is_remote: If True, delete remote branch; if False, delete local branch.

    Raises:
        RuntimeError: If the deletion fails.
    """
    if is_remote:
        # Use git push origin --delete for remote branches
        try:
            self._run_git(["push", "origin", "--delete", branch_name])
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to delete remote branch '{branch_name}': {e.stderr}"
            )
    else:
        # Use git branch -d for local branches
        try:
            self._run_git(["branch", "-d", branch_name])
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to delete local branch '{branch_name}': {e.stderr}"
            )
