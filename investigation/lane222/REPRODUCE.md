# Published runtime review reproducer

Requires Python 3 and JDK 21. Download `reproduce_published_reentry.py` and `ShutdownReentryReviewTest.java` from this directory, place them beside one another, and run:

```bash
python3 reproduce_published_reentry.py
```

Expected result on the current published coordinate: process exit 1, one failed test, fourth accepted channel `open=true registered=true` after event-loop termination. The script downloads the four required binary modules, checks their source commit metadata, compiles only the public-API test, and runs it with a 128 MiB heap. Downloads and classes use a temporary directory that is closed afterward. No Maven checkout, Coursier cache, running service, private API, mock, test retry, or additional system load is involved.

Existing regression checks were also re-run through each fork's Maven wrapper. See FINDINGS.md and module-results.json for counts. Original scenario tests pass; this additional callback-created registration path fails.

Both PR heads remain unchanged. The rebase conflict was reproduced in an isolated worktree and aborted; release-rebase-reapply.log has the exact JFR add/add conflict. No merge, publish, or deployment was performed.
