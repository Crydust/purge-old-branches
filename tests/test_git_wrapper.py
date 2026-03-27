"""Tests for the Git wrapper module."""

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from purge_old_branches.git_wrapper import BranchInfo, GitWrapper


@pytest.fixture
def temp_git_repo(tmp_path: Path):
    """Create a temporary Git repository for testing."""
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Create initial commit on main branch
    (repo_path / "README.md").write_text("test")
    subprocess.run(
        ["git", "add", "."], cwd=repo_path, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "branch", "-M", "main"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    yield repo_path


@pytest.fixture
def git_wrapper(temp_git_repo: Path):
    """Create a GitWrapper instance pointing to temp repo."""
    return GitWrapper(str(temp_git_repo))


def test_git_wrapper_rejects_non_git_repo(tmp_path: Path):
    """Test that GitWrapper fails fast on non-Git directories."""
    with pytest.raises(RuntimeError, match="not a valid Git repository"):
        GitWrapper(str(tmp_path))


def test_get_merged_branches_local(git_wrapper: GitWrapper, temp_git_repo: Path):
    """Test retrieving local branches merged into main."""
    # Create and merge a feature branch
    subprocess.run(
        ["git", "checkout", "-b", "feature-1"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
    )
    (temp_git_repo / "feature.txt").write_text("content")
    subprocess.run(
        ["git", "add", "."], cwd=temp_git_repo, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-m", "feature"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
    )

    # Switch back to main and merge
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "merge", "feature-1"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
    )

    merged: list[BranchInfo] = git_wrapper.get_merged_branches("main")
    matches = [b for b in merged if b.refname == "feature-1"]
    assert len(matches) == 1
    first_merged: BranchInfo = matches[0]

    # Should be a datetime in UTC
    committer_date = first_merged.committer_date
    assert isinstance(committer_date, datetime)
    assert committer_date.tzinfo is not None
    assert committer_date.tzinfo == timezone.utc

    author_date = first_merged.author_date
    assert isinstance(author_date, datetime)
    assert author_date.tzinfo is not None
    assert author_date.tzinfo == timezone.utc

    # Should be recent (within last hour)
    now = datetime.now(timezone.utc)
    assert (now - committer_date).total_seconds() < 3600
    assert (now - author_date).total_seconds() < 3600


def test_get_merged_branches_excludes_target(git_wrapper: GitWrapper):
    """Test that the target branch is excluded from merged branches."""
    merged = git_wrapper.get_merged_branches("main")
    refnames = [b.refname for b in merged]
    assert "main" not in refnames


def test_get_merged_branches_old_branch(git_wrapper: GitWrapper, temp_git_repo: Path):
    """Test retrieving commit date from an old commit."""
    old_date = datetime(2020, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Create a commit with a specific date
    subprocess.run(
        ["git", "checkout", "-b", "old-branch"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
    )
    (temp_git_repo / "old.txt").write_text("old content")
    subprocess.run(
        ["git", "add", "."], cwd=temp_git_repo, check=True, capture_output=True
    )

    # Set the commit date to 2020-01-01
    env = {
        "GIT_AUTHOR_DATE": old_date.isoformat(),
        "GIT_COMMITTER_DATE": old_date.isoformat(),
    }
    subprocess.run(
        ["git", "commit", "-m", "old commit"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
        env=os.environ | env,
    )

    # Switch back to main and merge
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "merge", "old-branch"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
    )

    merged: list[BranchInfo] = git_wrapper.get_merged_branches("main")
    matches = [b for b in merged if b.refname == "old-branch"]
    assert len(matches) == 1
    first_merged: BranchInfo = matches[0]

    # Should be in 2020
    committer_date = first_merged.committer_date
    assert committer_date.year == 2020
    assert committer_date.month == 1
    assert committer_date.day == 1

    author_date = first_merged.author_date
    assert author_date.year == 2020
    assert author_date.month == 1
    assert author_date.day == 1


def test_delete_local_branch(git_wrapper: GitWrapper, temp_git_repo: Path):
    """Test deleting a local branch."""
    # Create a branch to delete
    subprocess.run(
        ["git", "checkout", "-b", "to-delete"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
    )

    # Verify branch exists
    branches = subprocess.run(
        ["git", "branch"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert "to-delete" in branches

    # Delete the branch
    git_wrapper.delete_branches(["to-delete"], is_remote=False)

    # Verify it's deleted
    branches = subprocess.run(
        ["git", "branch"],
        cwd=temp_git_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    assert "to-delete" not in branches


def test_delete_local_branch_nonexistent(git_wrapper: GitWrapper):
    """Test that deleting nonexistent branch raises error."""
    with pytest.raises(RuntimeError, match="Failed to delete local branch"):
        git_wrapper.delete_branches(["nonexistent"], is_remote=False)


def test_delete_branches_batches_local(git_wrapper: GitWrapper, monkeypatch):
    """Test that local branch deletion is split into batch-sized git calls."""
    calls: list[list[str]] = []

    def fake_run_git(args: list[str]) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(git_wrapper, "_run_git", fake_run_git)

    git_wrapper.delete_branches(
        ["feature-1", "feature-2", "feature-3"], is_remote=False, batch_size=2
    )

    assert calls == [
        ["branch", "--delete", "feature-1", "feature-2"],
        ["branch", "--delete", "feature-3"],
    ]


def test_delete_branches_remote(git_wrapper: GitWrapper, monkeypatch):
    """Test that remote branch deletion uses 'git push origin --delete' in batches."""
    calls: list[list[str]] = []

    def fake_run_git(args: list[str]) -> str:
        calls.append(args)
        return ""

    monkeypatch.setattr(git_wrapper, "_run_git", fake_run_git)

    git_wrapper.delete_branches(
        ["origin/feature-1", "origin/feature-2", "origin/feature-3"],
        is_remote=True,
        batch_size=2,
    )

    assert calls == [
        ["push", "origin", "--delete", "feature-1", "feature-2"],
        ["push", "origin", "--delete", "feature-3"],
    ]


def _run(args: list[str], cwd: Path, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True, **kwargs)


@pytest.fixture
def remote_and_clone(tmp_path: Path):
    """Create a bare 'server' repo and a clone with pushed feature branches."""
    bare = tmp_path / "server.git"
    bare.mkdir()
    _run(["git", "init", "--bare"], cwd=bare)

    clone = tmp_path / "clone"
    _run(["git", "clone", str(bare), str(clone)], cwd=tmp_path)
    _run(["git", "config", "user.email", "test@example.com"], cwd=clone)
    _run(["git", "config", "user.name", "Test User"], cwd=clone)

    # Initial commit on main
    (clone / "README.md").write_text("init")
    _run(["git", "add", "."], cwd=clone)
    _run(["git", "commit", "-m", "initial"], cwd=clone)
    _run(["git", "branch", "-M", "main"], cwd=clone)
    _run(["git", "push", "-u", "origin", "main"], cwd=clone)

    # Create two feature branches, merge them into main, and push everything
    for branch in ["feature-1", "feature-2"]:
        _run(["git", "checkout", "-b", branch], cwd=clone)
        (clone / f"{branch}.txt").write_text(branch)
        _run(["git", "add", "."], cwd=clone)
        _run(["git", "commit", "-m", branch], cwd=clone)
        _run(["git", "push", "-u", "origin", branch], cwd=clone)
        _run(["git", "checkout", "main"], cwd=clone)
        _run(["git", "merge", branch], cwd=clone)

    _run(["git", "push"], cwd=clone)

    yield bare, clone


def test_delete_remote_branches_real(remote_and_clone):
    """Test deleting remote branches against a real bare repo."""
    bare, clone = remote_and_clone

    # Confirm both branches exist on the remote
    remote_refs = _run(["git", "branch", "-r"], cwd=clone).stdout
    assert "origin/feature-1" in remote_refs
    assert "origin/feature-2" in remote_refs

    wrapper = GitWrapper(str(clone))

    # Delete only feature-1 remotely (using origin/ prefix as get_merged_branches returns)
    wrapper.delete_branches(["origin/feature-1"], is_remote=True)

    # Fetch to update remote tracking refs
    _run(["git", "fetch", "--prune"], cwd=clone)
    remote_refs = _run(["git", "branch", "-r"], cwd=clone).stdout

    assert "origin/feature-1" not in remote_refs
    assert "origin/feature-2" in remote_refs



