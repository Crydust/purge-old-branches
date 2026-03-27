# Implementation Plan

## Phase 1: Data & Environment (Module: csv_parser)
* [x] **Task 1.1:** Create a CSV parser that reads `ticket_id` and `status`.
* [x] **Task 1.2:** Implement a filter to return a set of ticket IDs where status is `Done`.
* [x] **Test:** Verify parser handles missing files, empty rows, and correctly identifies 'Done' tickets.

## Phase 2: Git Integration (Module: git_wrapper)
* [x] **Task 2.1:** Implement `get_merged_branches(target_branch)` to list branches already merged into a specific base.
* [x] **Task 2.2:** Implement `get_branch_commit_date(branch_name)` to retrieve the Unix timestamp or ISO date of the HEAD commit.
* [x] **Task 2.3:** Implement `delete_branches(branch_names, is_remote)` to handle both `git branch -d` and `git push origin --delete` with a configurable batch size. We want to be able to delete multiple branches with a single git command.
* [x] **Test:** Use a temporary git repo in tests to verify branch listing and deletion logic.

## Phase 3: Core Logic (Module: cleaner_logic)
* [x] **Task 3.1:** Create a utility to extract Ticket IDs from branch names (e.g., `FEATURE-123-description` -> `FEATURE-123`).
* [x] **Task 3.2:** Build the `PurgeManager` that iterates through branches and checks them against the "stale" criteria (Age > 90 days AND Status == Done).
* [x] **Test:** Mock Git and CSV outputs to verify the manager selects the correct branches for deletion.

## Phase 4: CLI & Configuration (Module: cli)
* [x] **Task 4.1:** Add `argparse` support for:
    * [x] `--target-branch` (default: `main`)
    * [x] `--prefix` (e.g., `BUG-,FEATURE-`)
    * [x] `--remote` (boolean flag for local vs remote)
    * [x] `--dry-run` (show what would be deleted without deleting)
    * [x] `--csv-path`
* [x] **Test:** Ensure CLI arguments are parsed correctly and passed to the logic module.

## Phase 5: Testing & Integration
* [x] **Task 5.1:** Add comprehensive test coverage for all modules.
* [x] **Task 5.2:** Create integration test across all modules.
* [x] **Task 5.3:** Set up console script entry point in pyproject.toml.
* [x] **Task 5.4:** All 47 tests passing.

## Phase 6: Multi-Repository Support
* [x] **Task 6.1:** `--repo` argument supports comma-separated values and is repeatable.
* [x] **Task 6.2:** One `PurgeManager` per repository, queried in parallel.
* [x] **Task 6.3:** Only branches eligible in ALL repositories are deleted (intersection).
* [x] **Task 6.4:** Update tests for multi-repo scenarios.
