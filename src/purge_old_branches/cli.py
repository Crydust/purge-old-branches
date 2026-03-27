"""Command-line interface for the purge-old-branches tool."""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor

from purge_old_branches.cleaner_logic import PurgeManager
from purge_old_branches.csv_parser import CSVParser
from purge_old_branches.git_wrapper import GitWrapper


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
        action="append",
        help="Path to a Git repository. Repeatable and supports comma-separated values (default: current directory).",
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

        # Flatten --repo values (each may be comma-separated) and default to "."
        raw_repos = parsed_args.repo or ["."]
        repo_paths = [
            p.strip()
            for arg in raw_repos
            for p in arg.split(",")
            if p.strip()
        ]

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

        # Create one PurgeManager per repository
        managers = [
            PurgeManager(
                git_wrapper=GitWrapper(repo),
                csv_parser=csv_parser,
                patterns=prefixes,
                target_branch=parsed_args.target_branch,
                age_threshold_days=parsed_args.age_threshold_days,
            )
            for repo in repo_paths
        ]

        # Query each repository in parallel (git operations are slow)
        def get_eligible(m: PurgeManager) -> set[str]:
            return set(m.get_branches_to_delete(is_remote=parsed_args.remote))

        with ThreadPoolExecutor(max_workers=len(managers)) as executor:
            branch_sets = list(executor.map(get_eligible, managers))

        branches_to_delete = sorted(set.intersection(*branch_sets))

        if not branches_to_delete:
            print("No branches to delete.")
            return 0

        # If dry-run, print what would be deleted
        if parsed_args.dry_run:
            print(f"[DRY-RUN] Would delete {len(branches_to_delete)} branch(es):")
            for branch in branches_to_delete:
                print(f"[DRY-RUN] {branch}")
            return 0

        # Delete the common branches from every repository in parallel
        def delete_from(m: PurgeManager) -> None:
            m.git_wrapper.delete_branches(branches_to_delete, is_remote=parsed_args.remote)

        with ThreadPoolExecutor(max_workers=len(managers)) as executor:
            list(executor.map(delete_from, managers))

        print(f"Successfully deleted {len(branches_to_delete)} branch(es).")
        return 0

    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
