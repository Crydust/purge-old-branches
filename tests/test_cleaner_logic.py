"""Tests for the cleaner logic module."""

import csv
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.cleaner_logic import PurgeManager, TicketIDExtractor
from src.csv_parser import CSVParser
from src.git_wrapper import GitWrapper


class TestTicketIDExtractor:
    """Tests for the TicketIDExtractor class."""

    def test_extract_single_pattern(self):
        """Test extracting ticket ID with a single pattern."""
        extractor = TicketIDExtractor(["FEATURE-"])
        ticket_id = extractor.extract_ticket_id("FEATURE-123-my-feature")
        assert ticket_id == "FEATURE-123"

    def test_extract_multiple_patterns(self):
        """Test extracting ticket ID with multiple patterns."""
        extractor = TicketIDExtractor(["FEATURE-", "BUG-"])
        assert extractor.extract_ticket_id("FEATURE-456-description") == "FEATURE-456"
        assert extractor.extract_ticket_id("BUG-789-fix") == "BUG-789"

    def test_no_match_returns_empty(self):
        """Test that no match returns empty string."""
        extractor = TicketIDExtractor(["FEATURE-"])
        ticket_id = extractor.extract_ticket_id("dev/my-branch")
        assert ticket_id == ""

    def test_case_sensitive_matching(self):
        """Test case-sensitive pattern matching."""
        extractor = TicketIDExtractor(["FEATURE-"], case_sensitive=True)
        # Lowercase 'feature' should not match uppercase 'FEATURE-'
        ticket_id = extractor.extract_ticket_id("feature-123-desc")
        assert ticket_id == ""

    def test_strips_origin_prefix(self):
        """Test that 'origin/' prefix is stripped from remote branches."""
        extractor = TicketIDExtractor(["FEATURE-"])
        ticket_id = extractor.extract_ticket_id("origin/FEATURE-123-description")
        assert ticket_id == "FEATURE-123"

    def test_complex_ticket_id(self):
        """Test extracting ticket IDs with alphanumeric identifiers."""
        extractor = TicketIDExtractor(["JIRA-", "TICKET-"])
        assert extractor.extract_ticket_id("JIRA-ABC123-desc") == "JIRA-ABC123"
        assert extractor.extract_ticket_id("TICKET-99XYZ-fix") == "TICKET-99XYZ"

    def test_pattern_priority_order(self):
        """Test that patterns are checked in order."""
        extractor = TicketIDExtractor(["FEATURE-", "BUG-"])
        # When a branch could match multiple patterns, first match wins
        # But in this case, each branch only matches one
        assert extractor.extract_ticket_id("BUG-123-desc") == "BUG-123"


class TestPurgeManager:
    """Tests for the PurgeManager class."""

    @pytest.fixture
    def mock_git_wrapper(self):
        """Create a mock GitWrapper."""
        return MagicMock(spec=GitWrapper)

    @pytest.fixture
    def temp_csv_file(self):
        """Create a temporary CSV file with test data."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            csv_path = f.name

        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["ticket_id", "status"])
            writer.writeheader()
            writer.writerow({"ticket_id": "FEATURE-123", "status": "Done"})
            writer.writerow({"ticket_id": "FEATURE-124", "status": "In Progress"})
            writer.writerow({"ticket_id": "BUG-001", "status": "Done"})

        yield Path(csv_path)
        Path(csv_path).unlink()

    @pytest.fixture
    def csv_parser(self, temp_csv_file):
        """Create a CSVParser instance."""
        return CSVParser(str(temp_csv_file))

    def test_all_criteria_met(self, mock_git_wrapper, csv_parser):
        """Test that a branch is marked for deletion when all criteria are met."""
        old_date = datetime.now(timezone.utc) - timedelta(days=100)
        mock_git_wrapper.get_merged_branches.return_value = ["FEATURE-123-desc"]
        mock_git_wrapper.get_branch_commit_date.return_value = old_date

        manager = PurgeManager(
            mock_git_wrapper,
            csv_parser,
            patterns=["FEATURE-", "BUG-"],
            target_branch="main",
            age_threshold_days=90,
        )

        branches_to_delete = manager.get_branches_to_delete()
        assert "FEATURE-123-desc" in branches_to_delete

    def test_branch_too_young(self, mock_git_wrapper, csv_parser):
        """Test that young branches are not deleted."""
        recent_date = datetime.now(timezone.utc) - timedelta(days=30)
        mock_git_wrapper.get_merged_branches.return_value = ["FEATURE-123-desc"]
        mock_git_wrapper.get_branch_commit_date.return_value = recent_date

        manager = PurgeManager(
            mock_git_wrapper,
            csv_parser,
            patterns=["FEATURE-", "BUG-"],
            age_threshold_days=90,
        )

        branches_to_delete = manager.get_branches_to_delete()
        assert "FEATURE-123-desc" not in branches_to_delete

    def test_ticket_not_done(self, mock_git_wrapper, csv_parser):
        """Test that branches with 'In Progress' tickets are not deleted."""
        old_date = datetime.now(timezone.utc) - timedelta(days=100)
        mock_git_wrapper.get_merged_branches.return_value = ["FEATURE-124-desc"]
        mock_git_wrapper.get_branch_commit_date.return_value = old_date

        manager = PurgeManager(
            mock_git_wrapper,
            csv_parser,
            patterns=["FEATURE-", "BUG-"],
            age_threshold_days=90,
        )

        branches_to_delete = manager.get_branches_to_delete()
        assert "FEATURE-124-desc" not in branches_to_delete

    def test_branch_not_matching_pattern(self, mock_git_wrapper, csv_parser):
        """Test that branches not matching patterns are ignored."""
        old_date = datetime.now(timezone.utc) - timedelta(days=100)
        mock_git_wrapper.get_merged_branches.return_value = ["dev/my-branch"]
        mock_git_wrapper.get_branch_commit_date.return_value = old_date

        manager = PurgeManager(
            mock_git_wrapper,
            csv_parser,
            patterns=["FEATURE-", "BUG-"],
            age_threshold_days=90,
        )

        branches_to_delete = manager.get_branches_to_delete()
        assert len(branches_to_delete) == 0

    def test_multiple_branches_mixed_criteria(self, mock_git_wrapper, csv_parser):
        """Test with multiple branches having different criteria outcomes."""
        old_date = datetime.now(timezone.utc) - timedelta(days=100)
        young_date = datetime.now(timezone.utc) - timedelta(days=30)

        mock_git_wrapper.get_merged_branches.return_value = [
            "FEATURE-123-desc",  # Old, Done -> DELETE
            "FEATURE-124-desc",  # Old, In Progress -> KEEP
            "BUG-001-fix",  # Old, Done -> DELETE
            "dev/something",  # Old, but wrong pattern -> KEEP
        ]

        def get_commit_date_side_effect(branch, is_remote=False):
            if branch == "FEATURE-124-desc":
                return young_date
            return old_date

        mock_git_wrapper.get_branch_commit_date.side_effect = (
            get_commit_date_side_effect
        )

        manager = PurgeManager(
            mock_git_wrapper,
            csv_parser,
            patterns=["FEATURE-", "BUG-"],
            age_threshold_days=90,
        )

        branches_to_delete = manager.get_branches_to_delete()
        assert set(branches_to_delete) == {"FEATURE-123-desc", "BUG-001-fix"}

    def test_get_branch_commit_date_error_handling(self, mock_git_wrapper, csv_parser):
        """Test that branches with date retrieval errors are skipped."""
        mock_git_wrapper.get_merged_branches.return_value = ["FEATURE-123-desc"]
        mock_git_wrapper.get_branch_commit_date.side_effect = RuntimeError("No commits")

        manager = PurgeManager(
            mock_git_wrapper,
            csv_parser,
            patterns=["FEATURE-", "BUG-"],
            age_threshold_days=90,
        )

        branches_to_delete = manager.get_branches_to_delete()
        assert "FEATURE-123-desc" not in branches_to_delete

    def test_remote_branches(self, mock_git_wrapper, csv_parser):
        """Test with remote branches."""
        old_date = datetime.now(timezone.utc) - timedelta(days=100)
        mock_git_wrapper.get_merged_branches.return_value = ["FEATURE-123-desc"]
        mock_git_wrapper.get_branch_commit_date.return_value = old_date

        manager = PurgeManager(
            mock_git_wrapper,
            csv_parser,
            patterns=["FEATURE-", "BUG-"],
            age_threshold_days=90,
        )

        branches_to_delete = manager.get_branches_to_delete(is_remote=True)

        # Verify that is_remote was passed to the git wrapper methods
        mock_git_wrapper.get_merged_branches.assert_called_with("main", is_remote=True)
        mock_git_wrapper.get_branch_commit_date.assert_called_with(
            "FEATURE-123-desc", is_remote=True
        )
        assert "FEATURE-123-desc" in branches_to_delete

