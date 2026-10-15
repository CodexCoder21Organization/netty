The owner asked to “produce the custom Netty build `4.2.10.Final-codexcoder21-1` carrying the organization's two Netty fixes” so the blocked consumer changes can proceed. This release supplies the shutdown closure needed by https://github.com/CodexCoder21Organization/UrlProtocol/pull/702 and allocator event deferral needed by https://github.com/CodexCoder21Organization/UrlProtocol/pull/692.

This branch starts at `netty-4.2.10.Final` (4cc98736c3947bc93122e0b64e0bd8fc970c6437). The exact-tag shutdown fix is semantically equivalent to the later 4.2 fix, so the fallback to 4.2.20 was unnecessary. The custom version is set in all 62 reactor/independent-BOM POMs.

Manual backports:
- https://github.com/CodexCoder21Organization/netty-2/pull/1: move `prepareToDestroy()` from the pre-task shutdown check into `confirmShutdown()`, before its superclass call. Keep the tag's `maxTaskProcessingQuantumNs` scheduling unchanged. Copy the three NIO regression tests unchanged.
- https://github.com/CodexCoder21Organization/netty/pull/1: add the recorder-exists short circuit at all five adaptive and five pooled event sites, leaving capability and per-operation enabled checks intact. Port the three compile-only FlightRecorder stub methods. The tag has no JfrEventsTest, so create an equivalent four-case class using the source cold-child harness and source timeout/JDK conditions; do not import the later unrelated JFR suite.

Fail-first and fixed verification, JDK 21:
- Shutdown regressions: baseline 3 tests / 3 failures / 0 errors / 0 skips; fixed 3 / 0 / 0 / 0. Full NioEventLoopTest: 16 / 0 / 0 / 0.
- Allocator cold-child cases: baseline 4 tests / 2 failures / 0 errors / 0 skips (both inactive cases fail; both late-recording controls pass); fixed 4 / 0 / 0 / 0.
- Full common suite: 1,430 tests / 0 failures / 0 errors / 7 existing skips.
- Full transport suite: 386 tests / 0 failures / 0 errors / 9 existing skips. Existing disabled/conditional cases and Surefire native-stream warnings are preserved in the evidence. No test bound, iteration count or assertion was changed.
- Built the requested six-root Maven dependency closure serially (45 modules), including native epoll/QUIC, then installed the independent BOM. Nothing was published.

Artifact directories: `/tmp/claude-1000/-code/e2107bbc-8389-42b8-8447-42cf956a6745/scratchpad/publish/netty-codexcoder21-1/`. There are 46 one-POM directories, 136 POM/JAR files, and 272 verified SHA1/SHA256 checksums. MANIFEST.txt gives the parent/BOM-first publish order, ending with netty-all. CUSTOM-DEPENDENCIES.json records references from the built POMs, including unchanged independent tcnative/JNI/build-tool versions. A lane-private file-repository resolve of netty-all yielded 35 Netty runtime jars, all at this custom version.

UrlProtocol pin branch: https://github.com/CodexCoder21Organization/UrlProtocol/tree/fix/lane137-root-close-pin at ee207bbea86351df923bb9dcdb7c21650aefdc1d. Its 53 Netty coordinates in 34 files are updated, plus the reproducer's stale expected-failure comment. No UrlProtocol PR was created. Verification uses a detached worktree at that exact commit, with the four requested test files visible to avoid a workspace-wide unrelated clock-pin discovery error also observed on untouched main. All four test files match the branch byte-for-byte; all production files remain present. Locally built artifacts are installed into a lane-private Coursier cache; nothing is published and no source workaround is committed.

Consumer gate: **BLOCKED — do not publish this release yet.** The deterministic root-close function executed once and failed with the registered root still open after termination. No retry was performed; the ten racing-shutdown runs and the two connection tests have not run. A separate origin diagnostic proves transport and buffer were actually loaded from upstream `4.2.10.Final` jars, despite custom pins and custom netty-all resources.

The selection problem is independently reproducible with only two Coursier API dependencies: request transport at both `4.2.10.Final-codexcoder21-1` and `4.2.10.Final` on the tool's exact classpath; its Java API selects upstream Final, while the standalone cs CLI selects the custom version. The consumer's libp2p dependency brings the upstream version, so the pin edits do not establish the intended runtime. The custom transport jar has the expected override (javap), and its three fail-first tests plus the full transport suite pass. This does not justify the 4.2.20 fallback, whose permission was specifically conditional on failure to make the shutdown backport equivalent.

This draft preserves the finished Netty backport and artifact preparation for review. Remaining work is to correct consumer resolver selection without altering test bounds or hiding the failing run, then run the prescribed consumer gate. STATUS.txt and MANIFEST.txt in the artifact root explicitly hold publication.

Evidence, full failure stacks, manual hunk ledger, suite counts, and artifact manifest:
https://github.com/CodexCoder21Organization/netty/tree/evidence/lane141-custom-netty/investigation/lane141

No publication, merge, enqueue, deploy, or Handoff write was performed.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
