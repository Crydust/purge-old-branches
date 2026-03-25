"""Git wrapper for interfacing with Git operations."""

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


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
    ) -> List[str]:
        """
        Get a list of branches merged into the target branch.

        Args:
            target_branch: The target branch to check merges against.
            is_remote: If True, list remote branches; if False, list local branches.

        Returns:
            A list of branch names merged into the target branch.
        """
        if is_remote:
            # For remote branches, use origin/target_branch
            merge_base_branch = f"origin/{target_branch}"
        else:
            merge_base_branch = target_branch

        try:
            output = self._run_git(["branch", "--merged", merge_base_branch])
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to get merged branches for '{merge_base_branch}': {e.stderr}"
            )

        # Parse branch names, removing leading asterisk and whitespace
        branches = [line.strip().lstrip("*") for line in output.split("\n") if line.strip()]

        # Filter out the target branch itself
        branches = [b for b in branches if b != target_branch and b != merge_base_branch]

        return branches

    def get_branch_commit_date(self, branch_name: str, is_remote: bool = False) -> datetime:
        """
        Get the commit date of the HEAD commit of a branch in GMT/UTC.

        Args:
            branch_name: Name of the branch (without 'origin/' prefix for remote branches).
            is_remote: If True, treat as a remote branch.

        Returns:
            A datetime object in UTC representing the commit date.

        Raises:
            RuntimeError: If the branch doesn't exist or the command fails.
        """
        if is_remote:
            full_branch_name = f"origin/{branch_name}"
        else:
            full_branch_name = branch_name

        try:
            # Get the committer date in ISO format (most recent date if multiple)
            output = self._run_git(
                ["log", "-1", "--format=%cI", full_branch_name]
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to get commit date for branch '{full_branch_name}': {e.stderr}"
            )

        if not output:
            raise RuntimeError(f"Branch '{full_branch_name}' has no commits")

        # Parse ISO 8601 format timestamp
        commit_date = datetime.fromisoformat(output)

        # Convert to UTC if it has timezone info
        if commit_date.tzinfo is not None:
            commit_date = commit_date.astimezone(timezone.utc)
        else:
            commit_date = commit_date.replace(tzinfo=timezone.utc)

        return commit_date

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

