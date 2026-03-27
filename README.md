# Purge old branches

A tool to automate the cleanup of stale Git branches across multiple repositories based on Jira ticket status and branch age.

## Logic for Deletion
A branch is considered "stale" and eligible for deletion if **all** the following are true:
1. **Ticket Status:** The ticket ID extracted from the branch name has a status of `Done` in the provided CSV file.
2. **Age:** The `HEAD` commit of the branch is older than 90 days.
3. **Merged:** The branch has been merged into the "target" branch (e.g., `main` or `RELEASE-12345`).
4. **Naming Convention:** The branch name starts with a configurable prefix (e.g., `BUG-`, `FEATURE-`).
5. **Multi-Repository:** When multiple repositories are specified via `--repo`, a branch is only deleted if it is eligible in **every** repository.

## Architecture
The application is split into testable modules:
- `csv_parser`: Extracts ticket data.
- `git_wrapper`: Interfaces with Git to list branches, check merge status, and get commit dates.
- `cleaner_logic`: Orchestrates the decision-making process.
- `cli`: Handles user configuration (local vs remote, branch prefixes, target branch name).

## Development Flow
This project follows a test-driven approach. For every feature implemented, corresponding tests must be added to the `tests/` directory and pass before integration.

## Setup and Usage

- To run the application and see the usage message: `python -m purge_old_branches.cli --help`
- Or after installation: `purge-old-branches --help`
- To install for development: `pip install -e ".[dev]"`
- To run linting, type checking, and tests: 
```shell
python -m ruff check
python -m pyright
python -m pytest
python -m build
```
