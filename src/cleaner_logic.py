"""Core logic for determining which branches should be purged."""

import re
from re import RegexFlag
from datetime import datetime, timezone
from typing import List, Set


class TicketIDExtractor:
    """Extract ticket IDs from branch names using configurable patterns."""

    def __init__(self, patterns: List[str], case_sensitive: bool = True):
        """
        Initialize the ticket ID extractor.

        Args:
            patterns: List of prefixes to match (e.g., ['FEATURE-', 'BUG-']).
            case_sensitive: Whether pattern matching is case-sensitive.
        """
        self.patterns = patterns
        self.case_sensitive = case_sensitive

    def extract_ticket_id(self, branch_name: str) -> str:
        """
        Extract ticket ID from a branch name.

        Strips 'origin/' prefix from remote branches before extraction.

        Args:
            branch_name: The branch name to extract from.

        Returns:
            The extracted ticket ID (prefix + identifier), or empty string if no match.
        """

        for pattern in self.patterns:

            # Strip 'origin/' prefix if present.
            # Extract the full ticket ID (all digits after the pattern).
            # We expect a dash or at least a word boundary after the last digit.
            # For example, from "FEATURE-123-description", extract "FEATURE-123"
            if match := re.fullmatch(
                    r"(?:origin/)?(" + re.escape(pattern) + r"\d{1,10})\b.*",
                    branch_name,
                    RegexFlag.NOFLAG if self.case_sensitive else RegexFlag.IGNORECASE):
                return match.group(1)

        return ""


class PurgeManager:
    """Orchestrate the decision-making process for branch deletion."""

    def __init__(
            self,
            git_wrapper,
            csv_parser,
            patterns: List[str],
            target_branch: str = "main",
            age_threshold_days: int = 90,
    ):
        """
        Initialize the purge manager.

        Args:
            git_wrapper: GitWrapper instance for git operations.
            csv_parser: CSVParser instance for reading ticket statuses.
            patterns: List of branch name prefixes to match (e.g., ['FEATURE-', 'BUG-']).
            target_branch: The branch to check merges against (default: 'main').
            age_threshold_days: Minimum age in days for branch to be considered stale.
        """
        self.git_wrapper = git_wrapper
        self.csv_parser = csv_parser
        self.extractor = TicketIDExtractor(patterns, case_sensitive=True)
        self.target_branch = target_branch
        self.age_threshold_days = age_threshold_days

    def get_branches_to_delete(self, is_remote: bool = False) -> List[str]:
        """
        Determine which branches should be deleted based on all four criteria.

        Criteria:
        1. Ticket Status: The ticket ID has status 'Done' in CSV.
        2. Age: The HEAD commit is older than age_threshold_days.
        3. Merged: The branch has been merged into the target branch.
        4. Naming Convention: The branch name matches one of the configured patterns.

        Args:
            is_remote: If True, check remote branches; if False, check local branches.

        Returns:
            A list of branch names eligible for deletion.
        """
        # Get all done tickets from CSV
        done_tickets: Set[str] = self.csv_parser.get_done_tickets()

        # Get all branches merged into the target branch
        merged_branches: List[str] = self.git_wrapper.get_merged_branches(
            self.target_branch, is_remote=is_remote
        )

        branches_to_delete: List[str] = []
        now = datetime.now(timezone.utc)

        for branch in merged_branches:
            # Criterion 4: Check if branch matches naming convention
            ticket_id = self.extractor.extract_ticket_id(branch)
            if not ticket_id:
                continue  # Doesn't match any pattern

            # Criterion 1: Check if ticket is "Done"
            if ticket_id not in done_tickets:
                continue  # Ticket is not done

            # Criterion 2: Check if branch is old enough
            try:
                branch_commit_date = self.git_wrapper.get_branch_commit_date(
                    branch, is_remote=is_remote
                )
            except RuntimeError:
                continue  # Skip if we can't get the commit date

            branch_age_days = (now - branch_commit_date).days
            if branch_age_days < self.age_threshold_days:
                continue  # Branch is too young

            # Criterion 3: Check if branch is merged (already verified above)
            # All criteria met, add to deletion list
            branches_to_delete.append(branch)

        return branches_to_delete
