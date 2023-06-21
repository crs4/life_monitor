# test-galaxy-wf-repo

A dummy workflow in a Git repository.  Taken from Simone Leo's
dummy test repository at <https://github.com/simleo/test_lm_gh_app>.

This repository has been modified so that it can be nested inside the
LifeMonitor repository by renaming .git to .dot-git.  The test fixture
simple_local_wf_repo takes care of restoring the .git directory for its use in
tests.

To modify the test fixture with git, use `git --git-dir .dot-git`.  Any git
operation without specifying the git directory will act on the main LifeMonitor
repository, allowing you to commit and push changes to the test fixture.
