"""Tests for the CLI module."""

import csv
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.cli import main, parse_arguments


class TestParseArguments:
    """Tests for argument parsing."""

    def test_required_csv_path(self):
        """Test that --csv-path is required."""
        with pytest.raises(SystemExit):
            parse_arguments([])

    def test_csv_path_provided(self):
        """Test parsing with required csv-path."""
        args = parse_arguments(["--csv-path", "/path/to/file.csv"])
        assert args.csv_path == "/path/to/file.csv"

    def test_default_values(self):
        """Test default argument values."""
        args = parse_arguments(["--csv-path", "file.csv"])
        assert args.csv_ticket_col == "ticket_id"
        assert args.csv_status_col == "status"
        assert args.target_branch == "main"
        assert args.prefix == "FEATURE-,BUG-"
        assert args.remote is False
        assert args.dry_run is False
        assert args.repo == "."

    def test_custom_csv_columns(self):
        """Test setting custom CSV column names."""
        args = parse_arguments(
            [
                "--csv-path",
                "file.csv",
                "--csv-ticket-col",
                "id",
                "--csv-status-col",
                "state",
            ]
        )
        assert args.csv_ticket_col == "id"
        assert args.csv_status_col == "state"

    def test_custom_target_branch(self):
        """Test setting custom target branch."""
        args = parse_arguments(
            ["--csv-path", "file.csv", "--target-branch", "RELEASE-1.0"]
        )
        assert args.target_branch == "RELEASE-1.0"

    def test_custom_prefixes(self):
        """Test setting custom branch prefixes."""
        args = parse_arguments(
            ["--csv-path", "file.csv", "--prefix", "JIRA-,TICKET-"]
        )
        assert args.prefix == "JIRA-,TICKET-"

    def test_remote_flag(self):
        """Test --remote flag."""
        args = parse_arguments(["--csv-path", "file.csv", "--remote"])
        assert args.remote is True

    def test_dry_run_flag(self):
        """Test --dry-run flag."""
        args = parse_arguments(["--csv-path", "file.csv", "--dry-run"])
        assert args.dry_run is True

    def test_custom_repo_path(self):
        """Test --repo argument."""
        args = parse_arguments(
            ["--csv-path", "file.csv", "--repo", "/path/to/repo"]
        )
        assert args.repo == "/path/to/repo"


class TestMainFunction:
    """Tests for the main CLI function."""

    @pytest.fixture
    def temp_csv_file(self):
        """Create a temporary CSV file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            csv_path = f.name

        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["ticket_id", "status"])
            writer.writeheader()
            writer.writerow({"ticket_id": "FEATURE-123", "status": "Done"})

        yield Path(csv_path)
        Path(csv_path).unlink()

    def test_missing_csv_file(self):
        """Test that missing CSV file causes error."""
        result = main(["--csv-path", "/nonexistent/file.csv"])
        assert result == 1

    @patch("src.cli.GitWrapper")
    @patch("src.cli.CSVParser")
    @patch("src.cli.PurgeManager")
    def test_no_branches_to_delete(
        self, mock_purge_manager_class, mock_csv_parser_class, mock_git_class
    ):
        """Test when no branches need to be deleted."""
        mock_git_instance = MagicMock()
        mock_git_class.return_value = mock_git_instance

        mock_csv_instance = MagicMock()
        mock_csv_parser_class.return_value = mock_csv_instance

        mock_purge_instance = MagicMock()
        mock_purge_instance.get_branches_to_delete.return_value = []
        mock_purge_manager_class.return_value = mock_purge_instance

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name
        Path(csv_path).unlink()

        # Create a fake CSV file
        with open(csv_path, "w") as f:
            f.write("ticket_id,status\n")

        try:
            result = main(["--csv-path", csv_path])
            assert result == 0
        finally:
            Path(csv_path).unlink()

    @patch("src.cli.GitWrapper")
    @patch("src.cli.CSVParser")
    @patch("src.cli.PurgeManager")
    def test_dry_run_mode(
        self, mock_purge_manager_class, mock_csv_parser_class, mock_git_class
    ):
        """Test dry-run mode doesn't delete branches."""
        mock_git_instance = MagicMock()
        mock_git_class.return_value = mock_git_instance

        mock_csv_instance = MagicMock()
        mock_csv_parser_class.return_value = mock_csv_instance

        mock_purge_instance = MagicMock()
        mock_purge_instance.get_branches_to_delete.return_value = [
            "FEATURE-123-desc"
        ]
        mock_purge_manager_class.return_value = mock_purge_instance

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name
        Path(csv_path).unlink()

        with open(csv_path, "w") as f:
            f.write("ticket_id,status\n")

        try:
            result = main(["--csv-path", csv_path, "--dry-run"])
            assert result == 0
            # Verify delete_branch was NOT called
            mock_git_instance.delete_branch.assert_not_called()
        finally:
            Path(csv_path).unlink()

    @patch("src.cli.GitWrapper")
    @patch("src.cli.CSVParser")
    @patch("src.cli.PurgeManager")
    def test_successful_deletion(
        self, mock_purge_manager_class, mock_csv_parser_class, mock_git_class
    ):
        """Test successful deletion of branches."""
        mock_git_instance = MagicMock()
        mock_git_class.return_value = mock_git_instance

        mock_csv_instance = MagicMock()
        mock_csv_parser_class.return_value = mock_csv_instance

        mock_purge_instance = MagicMock()
        mock_purge_instance.get_branches_to_delete.return_value = [
            "FEATURE-123-desc",
            "BUG-001-fix",
        ]
        mock_purge_manager_class.return_value = mock_purge_instance

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name
        Path(csv_path).unlink()

        with open(csv_path, "w") as f:
            f.write("ticket_id,status\n")

        try:
            result = main(["--csv-path", csv_path])
            assert result == 0
            # Verify delete_branch was called for each branch
            assert mock_git_instance.delete_branch.call_count == 2
        finally:
            Path(csv_path).unlink()

    @patch("src.cli.GitWrapper")
    @patch("src.cli.CSVParser")
    @patch("src.cli.PurgeManager")
    def test_deletion_error_handling(
        self, mock_purge_manager_class, mock_csv_parser_class, mock_git_class
    ):
        """Test that deletion errors cause failure."""
        mock_git_instance = MagicMock()
        mock_git_instance.delete_branch.side_effect = RuntimeError("Permission denied")
        mock_git_class.return_value = mock_git_instance

        mock_csv_instance = MagicMock()
        mock_csv_parser_class.return_value = mock_csv_instance

        mock_purge_instance = MagicMock()
        mock_purge_instance.get_branches_to_delete.return_value = ["FEATURE-123-desc"]
        mock_purge_manager_class.return_value = mock_purge_instance

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name
        Path(csv_path).unlink()

        with open(csv_path, "w") as f:
            f.write("ticket_id,status\n")

        try:
            result = main(["--csv-path", csv_path])
            assert result == 1
        finally:
            Path(csv_path).unlink()

    @patch("src.cli.GitWrapper")
    @patch("src.cli.CSVParser")
    @patch("src.cli.PurgeManager")
    def test_custom_prefixes_passed_to_manager(
        self, mock_purge_manager_class, mock_csv_parser_class, mock_git_class
    ):
        """Test that custom prefixes are parsed and passed to PurgeManager."""
        mock_git_instance = MagicMock()
        mock_git_class.return_value = mock_git_instance

        mock_csv_instance = MagicMock()
        mock_csv_parser_class.return_value = mock_csv_instance

        mock_purge_instance = MagicMock()
        mock_purge_instance.get_branches_to_delete.return_value = []
        mock_purge_manager_class.return_value = mock_purge_instance

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name
        Path(csv_path).unlink()

        with open(csv_path, "w") as f:
            f.write("ticket_id,status\n")

        try:
            result = main(
                ["--csv-path", csv_path, "--prefix", "JIRA-,TICKET-,EPIC-"]
            )
            assert result == 0

            # Verify PurgeManager was created with correct patterns
            call_kwargs = mock_purge_manager_class.call_args[1]
            assert call_kwargs["patterns"] == ["JIRA-", "TICKET-", "EPIC-"]
        finally:
            Path(csv_path).unlink()

