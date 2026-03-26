"""CSV parser for reading ticket statuses from a CSV file."""

import csv
from pathlib import Path
from typing import Set


class CSVParser:
    """Parse CSV files with configurable header names to extract ticket statuses."""

    def __init__(
            self,
            csv_path: str,
            ticket_id_col: str = "ticket_id",
            status_col: str = "status",
    ):
        """
        Initialize the CSV parser.

        Args:
            csv_path: Path to the CSV file.
            ticket_id_col: Name of the column containing ticket IDs.
            status_col: Name of the column containing ticket status.
        """
        self.csv_path = Path(csv_path)
        self.ticket_id_col = ticket_id_col
        self.status_col = status_col

    def get_done_tickets(self) -> Set[str]:
        """
        Read the CSV file and return a set of ticket IDs with 'Done' status.

        Returns:
            A set of ticket IDs where status is 'Done'.

        Raises:
            ValueError: If headers are missing or malformed.
            FileNotFoundError: If the CSV file does not exist.
        """

        if not self.csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.csv_path}")

        done_tickets: Set[str] = set()

        with open(self.csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            if reader.fieldnames is None:
                raise ValueError("CSV file has no headers")

            # Check that required columns exist
            if self.ticket_id_col not in reader.fieldnames:
                raise ValueError(
                    f"Column '{self.ticket_id_col}' not found in CSV. "
                    f"Available columns: {', '.join(reader.fieldnames)}"
                )
            if self.status_col not in reader.fieldnames:
                raise ValueError(
                    f"Column '{self.status_col}' not found in CSV. "
                    f"Available columns: {', '.join(reader.fieldnames)}"
                )

            for row in reader:
                if row is None:
                    continue

                ticket_id = row.get(self.ticket_id_col, "").strip()
                status = row.get(self.status_col, "").strip()

                # Only add non-empty ticket IDs with 'Done' status
                if ticket_id and status == "Done":
                    done_tickets.add(ticket_id)

        return done_tickets
