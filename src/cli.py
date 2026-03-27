"""Command-line interface for the purge-old-branches tool."""

import argparse
import sys

from src.cleaner_logic import PurgeManager
from src.csv_parser import CSVParser
from src.git_wrapper import GitWrapper


def parse_arguments(args: list[str] | None = None) -> argparse.Namespace:
    """
    Parse command-line arguments.

    Args:
        args: List of arguments to parse. If None, sys.argv[1:] is used.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Purge old Git branches based on Jira ticket status and branch age."
    )

    parser.add_argument(
        "--csv-path",
        required=True,
        help="Path to the CSV file containing ticket statuses.",
    )

    parser.add_argument(
        "--csv-ticket-col",
        default="ticket_id",
        help="Name of the CSV column containing ticket IDs (default: ticket_id).",
    )

    parser.add_argument(
        "--csv-status-col",
        default="status",
        help="Name of the CSV column containing ticket status (default: status).",
    )

    parser.add_argument(
        "--target-branch",
        default="main",
        help="Target branch to check merges against (default: main).",
    )

    parser.add_argument(
        "--prefix",
        default="FEATURE-,BUG-",
        help="Comma-separated list of branch name prefixes to match (default: FEATURE-,BUG-).",
    )

    parser.add_argument(
        "--remote",
        action="store_true",
        help="Delete remote branches instead of local branches.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting.",
    )

    parser.add_argument(
        "--repo",
        default=".",
        help="Path to the Git repository (default: current directory).",
    )

    parser.add_argument(
        "--age-threshold-days",
        type=int,
        default=90,
        help="Minimum age in days for branch to be considered stale (default: 90).",
    )

    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    """
    Main entry point for the CLI.

    Args:
        args: List of arguments. If None, sys.argv[1:] is used.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    try:
        parsed_args = parse_arguments(args)

        # Initialize components
        git_wrapper = GitWrapper(parsed_args.repo)
        csv_parser = CSVParser(
            parsed_args.csv_path,
            ticket_id_col=parsed_args.csv_ticket_col,
            status_col=parsed_args.csv_status_col,
        )

        # Parse prefixes from comma-separated list
        prefixes = [p.strip() for p in parsed_args.prefix.split(",")]
        if not prefixes or "" in prefixes:
            print(
                "Error: --prefix must contain at least one prefix and the prefixes cannot be empty.",
                file=sys.stderr,
            )
            return 1

        if parsed_args.age_threshold_days < 1:
            print(
                "Error: --age-threshold-days must be a positive integer.",
                file=sys.stderr,
            )
            return 1

        # Create the purge manager
        purge_manager = PurgeManager(
            git_wrapper=git_wrapper,
            csv_parser=csv_parser,
            patterns=prefixes,
            target_branch=parsed_args.target_branch,
            age_threshold_days=parsed_args.age_threshold_days,
        )

        # Get branches to delete
        branches_to_delete = purge_manager.get_branches_to_delete(
            is_remote=parsed_args.remote
        )

        if not branches_to_delete:
            print("No branches to delete.")
            return 0

        # If dry-run, print what would be deleted
        if parsed_args.dry_run:
            print(f"[DRY-RUN] Would delete {len(branches_to_delete)} branch(es):")
            for branch in branches_to_delete:
                print(f"[DRY-RUN] {branch}")
            return 0

        # Delete branches
        git_wrapper.delete_branches(branches_to_delete, is_remote=parsed_args.remote)

        print(f"Successfully deleted {len(branches_to_delete)} branch(es).")
        return 0

    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
