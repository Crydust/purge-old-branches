"""Tests for the CLI module."""

import csv
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from purge_old_branches.cli import main, parse_arguments


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
        assert args.repo is None

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
        assert args.repo == ["/path/to/repo"]


class TestMainFunction:
    """Tests for the main CLI function."""

    @pytest.fixture
    def temp_csv_file(self, tmp_path: Path):
        """Create a temporary CSV file."""
        csv_path = tmp_path / "tickets.csv"

        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["ticket_id", "status"])
            writer.writeheader()
            writer.writerow({"ticket_id": "FEATURE-123", "status": "Done"})

        yield csv_path

    def test_missing_csv_file(self):
        """Test that missing CSV file causes error."""
        result = main(["--csv-path", "/nonexistent/file.csv"])
        assert result == 1

    @patch("purge_old_branches.cli.GitWrapper")
    @patch("purge_old_branches.cli.CSVParser")
    @patch("purge_old_branches.cli.PurgeManager")
    def test_no_branches_to_delete(
        self, mock_purge_manager_class, mock_csv_parser_class, mock_git_class, tmp_path: Path
    ):
        """Test when no branches need to be deleted."""
        mock_git_instance = MagicMock()
        mock_git_class.return_value = mock_git_instance

        mock_csv_instance = MagicMock()
        mock_csv_parser_class.return_value = mock_csv_instance

        mock_purge_instance = MagicMock()
        mock_purge_instance.get_branches_to_delete.return_value = []
        mock_purge_manager_class.return_value = mock_purge_instance

        csv_path = tmp_path / "tickets.csv"

        # Create a fake CSV file
        with open(csv_path, "w") as f:
            f.write("ticket_id,status\n")

        result = main(["--csv-path", str(csv_path)])
        assert result == 0


    @patch("purge_old_branches.cli.GitWrapper")
    @patch("purge_old_branches.cli.CSVParser")
    @patch("purge_old_branches.cli.PurgeManager")
    def test_dry_run_mode(
        self, mock_purge_manager_class, mock_csv_parser_class, mock_git_class, tmp_path: Path
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

        csv_path = tmp_path / "tickets.csv"

        with open(csv_path, "w") as f:
            f.write("ticket_id,status\n")

        result = main(["--csv-path", str(csv_path), "--dry-run"])
        assert result == 0
        # Verify delete_branches was NOT called
        mock_git_instance.delete_branches.assert_not_called()


    @patch("purge_old_branches.cli.GitWrapper")
    @patch("purge_old_branches.cli.CSVParser")
    @patch("purge_old_branches.cli.PurgeManager")
    def test_successful_deletion(
        self, mock_purge_manager_class, mock_csv_parser_class, mock_git_class, tmp_path: Path
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
        mock_purge_instance.git_wrapper = mock_git_instance
        mock_purge_manager_class.return_value = mock_purge_instance

        csv_path = tmp_path / "tickets.csv"

        with open(csv_path, "w") as f:
            f.write("ticket_id,status\n")

        result = main(["--csv-path", str(csv_path)])
        assert result == 0
        # Verify delete_branches was called for each branch
        assert mock_git_instance.delete_branches.call_count == 1

    @patch("purge_old_branches.cli.GitWrapper")
    @patch("purge_old_branches.cli.CSVParser")
    @patch("purge_old_branches.cli.PurgeManager")
    def test_deletion_error_handling(
        self, mock_purge_manager_class, mock_csv_parser_class, mock_git_class, tmp_path: Path
    ):
        """Test that deletion errors cause failure."""
        mock_git_instance = MagicMock()
        mock_git_instance.delete_branches.side_effect = RuntimeError("Permission denied")
        mock_git_class.return_value = mock_git_instance

        mock_csv_instance = MagicMock()
        mock_csv_parser_class.return_value = mock_csv_instance

        mock_purge_instance = MagicMock()
        mock_purge_instance.get_branches_to_delete.return_value = ["FEATURE-123-desc"]
        mock_purge_instance.git_wrapper = mock_git_instance
        mock_purge_manager_class.return_value = mock_purge_instance

        csv_path = tmp_path / "tickets.csv"

        with open(csv_path, "w") as f:
            f.write("ticket_id,status\n")

        result = main(["--csv-path", str(csv_path)])
        assert result == 1

    @patch("purge_old_branches.cli.GitWrapper")
    @patch("purge_old_branches.cli.CSVParser")
    @patch("purge_old_branches.cli.PurgeManager")
    def test_custom_prefixes_passed_to_manager(
        self, mock_purge_manager_class, mock_csv_parser_class, mock_git_class, tmp_path: Path
    ):
        """Test that custom prefixes are parsed and passed to PurgeManager."""
        mock_git_instance = MagicMock()
        mock_git_class.return_value = mock_git_instance

        mock_csv_instance = MagicMock()
        mock_csv_parser_class.return_value = mock_csv_instance

        mock_purge_instance = MagicMock()
        mock_purge_instance.get_branches_to_delete.return_value = []
        mock_purge_manager_class.return_value = mock_purge_instance

        csv_path = tmp_path / "tickets.csv"

        with open(csv_path, "w") as f:
            f.write("ticket_id,status\n")

        result = main(
            ["--csv-path", str(csv_path), "--prefix", "JIRA-,TICKET-,EPIC-"]
        )
        assert result == 0

        # Verify PurgeManager was created with correct patterns
        call_kwargs = mock_purge_manager_class.call_args[1]
        assert call_kwargs["patterns"] == ["JIRA-", "TICKET-", "EPIC-"]

    @patch("purge_old_branches.cli.GitWrapper")
    @patch("purge_old_branches.cli.CSVParser")
    @patch("purge_old_branches.cli.PurgeManager")
    def test_age_threshold_days_passed_to_manager(
        self, mock_purge_manager_class, mock_csv_parser_class, mock_git_class, tmp_path: Path
    ):
        """Test that --age-threshold-days is forwarded to PurgeManager."""
        mock_git_class.return_value = MagicMock()
        mock_csv_parser_class.return_value = MagicMock()

        mock_purge_instance = MagicMock()
        mock_purge_instance.get_branches_to_delete.return_value = []
        mock_purge_manager_class.return_value = mock_purge_instance

        csv_path = tmp_path / "tickets.csv"
        csv_path.write_text("ticket_id,status\n")

        result = main(["--csv-path", str(csv_path), "--age-threshold-days", "180"])
        assert result == 0

        call_kwargs = mock_purge_manager_class.call_args[1]
        assert call_kwargs["age_threshold_days"] == 180

    @patch("purge_old_branches.cli.GitWrapper")
    def test_empty_prefix_rejected(self, mock_git_class, tmp_path: Path):
        """Test that a trailing comma in --prefix causes an error."""
        mock_git_class.return_value = MagicMock()

        csv_path = tmp_path / "tickets.csv"
        csv_path.write_text("ticket_id,status\n")

        result = main(["--csv-path", str(csv_path), "--prefix", "FEATURE-,"])
        assert result == 1

    @patch("purge_old_branches.cli.GitWrapper")
    @patch("purge_old_branches.cli.CSVParser")
    @patch("purge_old_branches.cli.PurgeManager")
    def test_multi_repo_only_deletes_intersection(
        self, mock_purge_manager_class, mock_csv_parser_class, mock_git_class, tmp_path: Path
    ):
        """Test that with two repos, only branches eligible in both are deleted."""
        mock_csv_parser_class.return_value = MagicMock()

        # Two separate GitWrapper mocks, one per repo
        git_mock_a = MagicMock()
        git_mock_b = MagicMock()
        mock_git_class.side_effect = [git_mock_a, git_mock_b]

        # Two PurgeManager mocks, one per repo
        manager_a = MagicMock()
        manager_a.get_branches_to_delete.return_value = [
            "FEATURE-100-shared",
            "FEATURE-200-only-in-a",
        ]
        manager_a.git_wrapper = git_mock_a

        manager_b = MagicMock()
        manager_b.get_branches_to_delete.return_value = [
            "FEATURE-100-shared",
            "FEATURE-300-only-in-b",
        ]
        manager_b.git_wrapper = git_mock_b

        mock_purge_manager_class.side_effect = [manager_a, manager_b]

        csv_path = tmp_path / "tickets.csv"
        csv_path.write_text("ticket_id,status\n")

        result = main([
            "--csv-path", str(csv_path),
            "--repo", "/repo/a",
            "--repo", "/repo/b",
        ])
        assert result == 0

        # Only the shared branch should be deleted in both repos
        git_mock_a.delete_branches.assert_called_once()
        git_mock_b.delete_branches.assert_called_once()
        deleted_a = git_mock_a.delete_branches.call_args[0][0]
        deleted_b = git_mock_b.delete_branches.call_args[0][0]
        assert deleted_a == ["FEATURE-100-shared"]
        assert deleted_b == ["FEATURE-100-shared"]

