"""Integration tests for the full purge-old-branches workflow."""

import csv
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from purge_old_branches.cli import main


@pytest.fixture
def temp_git_repo_with_branches(tmp_path: Path):
    """Create a temporary git repo with multiple branches."""
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

    # Create initial commit on main
    (repo_path / "README.md").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
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
def temp_csv_with_tickets(tmp_path: Path):
    """Create a temporary CSV file with ticket statuses."""
    csv_path = tmp_path / "tickets.csv"

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ticket_id", "status"])
        writer.writeheader()
        writer.writerow({"ticket_id": "FEATURE-123", "status": "Done"})
        writer.writerow({"ticket_id": "FEATURE-124", "status": "In Progress"})
        writer.writerow({"ticket_id": "BUG-001", "status": "Done"})

    yield csv_path


def test_integration_full_workflow(temp_git_repo_with_branches, temp_csv_with_tickets):
    """Test the full workflow: create branches, mark done, delete old merged branches."""
    repo_path = temp_git_repo_with_branches
    csv_path = temp_csv_with_tickets

    # Create and merge an old branch (FEATURE-123)
    subprocess.run(
        ["git", "checkout", "-b", "FEATURE-123-description"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    (repo_path / "feature.txt").write_text("feature content")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)

    old_date = datetime(2020, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    env = {
        "GIT_AUTHOR_DATE": old_date.isoformat(),
        "GIT_COMMITTER_DATE": old_date.isoformat(),
    }
    subprocess.run(
        ["git", "commit", "-m", "feature"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        env=os.environ | env,
    )

    # Merge back to main
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "merge", "FEATURE-123-description"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Create a young branch that should NOT be deleted (FEATURE-124)
    subprocess.run(
        ["git", "checkout", "-b", "FEATURE-124-young"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    (repo_path / "young.txt").write_text("young content")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "young branch"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "merge", "FEATURE-124-young"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Create an old unmerged branch (should not be deleted)
    subprocess.run(
        ["git", "checkout", "-b", "BUG-001-unmerged"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    (repo_path / "bug.txt").write_text("bug fix")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "bug fix"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        env=os.environ | env,
    )

    # Verify initial state - all branches exist
    result = subprocess.run(
        ["git", "branch"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "FEATURE-123-description" in result.stdout
    assert "FEATURE-124-young" in result.stdout
    assert "BUG-001-unmerged" in result.stdout

    # Run purge with dry-run first
    result = main(
        [
            "--repo",
            str(repo_path),
            "--csv-path",
            str(csv_path),
            "--prefix",
            "FEATURE-,BUG-",
            "--target-branch",
            "main",
            "--dry-run",
        ]
    )
    assert result == 0

    # Run purge without dry-run
    result = main(
        [
            "--repo",
            str(repo_path),
            "--csv-path",
            str(csv_path),
            "--prefix",
            "FEATURE-,BUG-",
            "--target-branch",
            "main",
        ]
    )
    assert result == 0

    # Verify FEATURE-123 was deleted
    result = subprocess.run(
        ["git", "branch"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "FEATURE-123-description" not in result.stdout

    # Verify FEATURE-124 still exists (too young)
    assert "FEATURE-124-young" in result.stdout

    # Verify BUG-001 still exists (not merged)
    assert "BUG-001-unmerged" in result.stdout
