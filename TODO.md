# Implementation Plan

## Phase 1: Data & Environment (Module: csv_parser)
* [ ] **Task 1.1:** Create a CSV parser that reads `ticket_id` and `status`.
* [ ] **Task 1.2:** Implement a filter to return a set of ticket IDs where status is `Done`.
* [ ] **Test:** Verify parser handles missing files, empty rows, and correctly identifies 'Done' tickets.

## Phase 2: Git Integration (Module: git_wrapper)
* [ ] **Task 2.1:** Implement `get_merged_branches(target_branch)` to list branches already merged into a specific base.
* [ ] **Task 2.2:** Implement `get_branch_commit_date(branch_name)` to retrieve the Unix timestamp or ISO date of the HEAD commit.
* [ ] **Task 2.3:** Implement `delete_branch(branch_name, is_remote)` to handle both `git branch -d` and `git push origin --delete`.
* [ ] **Test:** Use a temporary git repo in tests to verify branch listing and deletion logic.

## Phase 3: Core Logic (Module: cleaner_logic)
* [ ] **Task 3.1:** Create a utility to extract Ticket IDs from branch names (e.g., `FEATURE-123-description` -> `FEATURE-123`).
* [ ] **Task 3.2:** Build the `PurgeManager` that iterates through branches and checks them against the "stale" criteria (Age > 90 days AND Status == Done).
* [ ] **Test:** Mock Git and CSV outputs to verify the manager selects the correct branches for deletion.

## Phase 4: CLI & Configuration (Module: cli)
* [ ] **Task 4.1:** Add `argparse` support for:
    * `--target-branch` (default: `main`)
    * `--prefix` (e.g., `BUG-,FEATURE-`)
    * `--remote` (boolean flag for local vs remote)
    * `--dry-run` (show what would be deleted without deleting)
    * `--csv-path`
* [ ] **Test:** Ensure CLI arguments are parsed correctly and passed to the logic module.

## Phase 5: Polishing
* [ ] **Task 5.1:** Add logging for skipped branches (explaining why: "Not merged", "Too young", "Ticket not Done").
* [ ] **Task 5.2:** Final integration test across all modules.