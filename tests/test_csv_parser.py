"""Tests for the CSV parser module."""

import csv
import tempfile
from pathlib import Path

import pytest

from src.csv_parser import CSVParser


@pytest.fixture
def temp_csv_file():
    """Create a temporary CSV file for testing."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline=""
    ) as f:
        csv_path = f.name
    yield Path(csv_path)
    Path(csv_path).unlink()


def test_csv_parser_reads_done_tickets(temp_csv_file):
    """Test that parser correctly identifies 'Done' tickets."""
    with open(temp_csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ticket_id", "status"])
        writer.writeheader()
        writer.writerow({"ticket_id": "JIRA-123", "status": "Done"})
        writer.writerow({"ticket_id": "JIRA-124", "status": "In Progress"})
        writer.writerow({"ticket_id": "JIRA-125", "status": "Done"})

    parser = CSVParser(str(temp_csv_file))
    done_tickets = parser.get_done_tickets()

    assert done_tickets == {"JIRA-123", "JIRA-125"}


def test_csv_parser_with_custom_headers(temp_csv_file):
    """Test that parser works with custom header names."""
    with open(temp_csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "state"])
        writer.writeheader()
        writer.writerow({"id": "BUG-001", "state": "Done"})
        writer.writerow({"id": "BUG-002", "state": "Open"})

    parser = CSVParser(str(temp_csv_file), ticket_id_col="id", status_col="state")
    done_tickets = parser.get_done_tickets()

    assert done_tickets == {"BUG-001"}


def test_csv_parser_handles_empty_rows(temp_csv_file):
    """Test that parser handles empty rows gracefully."""
    with open(temp_csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ticket_id", "status"])
        writer.writeheader()
        writer.writerow({"ticket_id": "JIRA-123", "status": "Done"})
        writer.writerow({"ticket_id": "", "status": "Done"})
        writer.writerow({"ticket_id": "JIRA-125", "status": ""})

    parser = CSVParser(str(temp_csv_file))
    done_tickets = parser.get_done_tickets()

    assert done_tickets == {"JIRA-123"}


def test_csv_parser_missing_file():
    """Test that parser fails fast when CSV file is missing."""
    with pytest.raises(FileNotFoundError):
        CSVParser("/nonexistent/path/file.csv")


def test_csv_parser_missing_column(temp_csv_file):
    """Test that parser fails when required column is missing."""
    with open(temp_csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ticket_id"])
        writer.writeheader()
        writer.writerow({"ticket_id": "JIRA-123"})

    parser = CSVParser(str(temp_csv_file))
    with pytest.raises(ValueError, match="Column 'status' not found"):
        parser.get_done_tickets()


def test_csv_parser_empty_file(temp_csv_file):
    """Test that parser handles empty CSV file."""
    temp_csv_file.touch()

    parser = CSVParser(str(temp_csv_file))
    with pytest.raises(ValueError, match="CSV file has no headers"):
        parser.get_done_tickets()


def test_csv_parser_whitespace_handling(temp_csv_file):
    """Test that parser handles whitespace in ticket IDs and statuses."""
    with open(temp_csv_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ticket_id", "status"])
        writer.writeheader()
        writer.writerow({"ticket_id": "  JIRA-123  ", "status": "  Done  "})
        writer.writerow({"ticket_id": "JIRA-124", "status": "Done "})

    parser = CSVParser(str(temp_csv_file))
    done_tickets = parser.get_done_tickets()

    assert done_tickets == {"JIRA-123", "JIRA-124"}

