# Purge old branches

We develop our software in multiple separate git repositories.
In all of them we create branches for bug fixes and new features.
These get names like `BUG-12345-foo` and `FEATURE-12345-bar`.
We want to delete old branches.
We have a main-ish branch we call `RELEASE-12345`.
There will be two versions of this program: one that deletes local branches and one that deletes remote branches.

The definition of an old branch is:
* The ticket status is `Done` (we read this from a csv file with the ticket number and the status)
* The `HEAD` commit of the branch is older than 90 days (in every repository)
* The branch is merged into `RELEASE-12345` (in every repository)
* The branch name matches the pattern `BUG-12345` or `FEATURE-12345`
