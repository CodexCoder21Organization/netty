The UrlProtocol test `testProtocolRootCloseCallerRacingEventLoopShutdown` left a root channel open after event-loop termination and blocked https://github.com/CodexCoder21Organization/UrlProtocol/pull/702. The owner requested a custom Netty build carrying the shutdown correction and the allocator-recorder guard; https://github.com/CodexCoder21Organization/UrlProtocol/pull/704 now pins the published `4.2.10.1-codexcoder21` build.

The release is based on exact `netty-4.2.10.Final` plus four commits. The earlier `4.2.10.Final-codexcoder21-1` version lost dependency mediation to upstream Final in the runner's Coursier API; the published string wins that comparison. The existing head branch keeps its earlier name as the draft-of-record. The reactor POMs, README and PR title use the published coordinate.

The changes comprise the shutdown backport from https://github.com/CodexCoder21Organization/netty-2/pull/1; ten adaptive/pooled allocator checks that avoid initializing event classes until a recorder exists; their public-API regression tests; compile-only FlightRecorder stubs; eight README lines; and 62 POM version substitutions. No unrelated production logic change was found. Earlier build/version/13-invocation consumer evidence remains at https://github.com/CodexCoder21Organization/netty/tree/evidence/lane146-version-selection/investigation/lane146 and exact-tag backport evidence at https://github.com/CodexCoder21Organization/netty/tree/evidence/lane141-custom-netty/investigation/lane141 .

**Review (lane 222): changes required.** The original three shutdown cases pass, but a new public-API review scenario registers a finite chain of channels from close listeners during shutdown. After termination four registrations have succeeded; the third channel still reports registered and the fourth is open and registered. This fails on the development PR and on the downloaded published runtime (4/4 fresh JVMs, including the standalone script check). `prepareToDestroy()` snapshots registrations before callbacks create the next channel; the final executor confirmation is not a drain loop, and same-thread registration still succeeds at `ST_SHUTDOWN`. The existing fix therefore closes the originally demonstrated path without closing this adjacent terminal-registration path. The self-contained test, full output, separate test/code review, and provenance audit are on the evidence branch.

A second blocker is the PR base. Its current `4.2` target is 541 development commits beyond the exact release tag, and GitHub reports conflicts. Rebasing onto it would change the release source set. An isolated rebase stopped on an add/add conflict in JfrEventsTest: the development base already has a ~357-line JFR suite where the release tag has none. The conflict was recorded and the rebase aborted. Lane 222 was authorized only to resolve mechanical conflicts, so it left both PR heads unchanged. The supervisor must choose a maintenance base at the exact tag or authorize a different release line/version; this draft is not ready to merge against its current base.

| Item | Source / result |
| --- | --- |
| Published coordinate | `io.netty:*:4.2.10.1-codexcoder21`, 46 artifacts (44 binary modules plus parent/BOM) |
| Published jar metadata | All 44 module jars name `a66b8e41266dd9a8ae193cf3dea021b3b5547d7f`, `repoStatus=clean`; every POM coordinate matches |
| Source jar comparison | All three changed production classes are byte-identical to release head |
| Release PR | https://github.com/CodexCoder21Organization/netty/pull/2, head `a66b8e41266dd9a8ae193cf3dea021b3b5547d7f` |
| Release base / merge-base | `4.2` at `006a2f1d92db733d10112de251600da7b6f8ec51` / exact tag commit `4cc98736c3947bc93122e0b64e0bd8fc970c6437`; 541 behind, 4 ahead |
| Shutdown PR | https://github.com/CodexCoder21Organization/netty-2/pull/1, head `d7b4547b64859311b9317a966cb995385399b8c5`; base and merge-base `aa00c11e31381c85ec39f2c518321ff12635ae9c`; 0 behind, 3 ahead |
| Shutdown fix in published source | Manual semantic/test backport in `13548ce836`, not original commit ancestry |
| Publication record | Supervisor log at 05:15:58Z records 46/46 successful uploads; detailed upload log absent from archived evidence |

Evidence: https://github.com/CodexCoder21Organization/netty/tree/evidence/lane222-netty-reconcile/investigation/lane222. Native classifier jars were not separately audited.

Lane 222 fail-first verification: the unchanged release shutdown tests fail 3/3 with only the production loop restored to the upstream tag and pass 3/3 with the backport. Both inactive-recorder tests fail without the allocator guards; all four JFR scenarios pass with them. Both late-enabled recording cases also pass on the baseline. No existing test assertion, bound, iteration count, or timeout was changed.

- release buffer: tests=13456, failures=0, errors=0, skipped=1315; command exit=0.
- release transport: tests=386, failures=0, errors=0, skipped=9; command exit=0.
- development transport: tests=422, failures=0, errors=0, skipped=9; command exit=0.

Both green `kotlin.build` checks explicitly say `no build.kts found in repository`; they ran no Maven compilation/tests. They are not evidence for the Maven suites above.

Provenance verdict: the published binary module set equals the current PR head. Merging that exact source against an appropriate base would not require re-publication solely for provenance, but would retain the demonstrated callback-registration gap. Correcting that gap requires a new version/build/publication decision. Lane 222 merged, published and deployed nothing.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
