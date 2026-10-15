The UrlProtocol test `testProtocolRootCloseCallerRacingEventLoopShutdown` failed in CI with `Iteration 40: the root is closed` although close promises had completed and the event loop had terminated: https://github.com/CodexCoder21Organization/UrlProtocol/actions/runs/38663196732/job/116189023105 . That failure blocked https://github.com/CodexCoder21Organization/UrlProtocol/pull/702, so the fix belongs in Netty's event-loop shutdown path; https://github.com/CodexCoder21Organization/UrlProtocol/pull/704 now pins the exact-tag release backport.

`SingleThreadIoEventLoop.run()` previously checked shutdown before its task phase. Shutdown starting from a task or close listener could therefore reach terminal confirmation without calling `prepareToDestroy()`, leaving registered channels open. This change moves preparation into an override of `confirmShutdown()`, covering the normal run loop and the superclass's final drains. The IoHandler contract permits repeated preparation.

Three tests use real NIO channels and public APIs: shutdown started by a task; shutdown started by another channel's close listener; and a channel registered by a shutdown hook. Each checks physical closure, closeFuture completion and deregistration after loop termination. Lane 222 reverified 3/3 failures with the production class restored to the PR base and 3/3 passes with the fix. No existing test assertion, bound, iteration count, or timeout was changed. The original recorded transport suite was 422 tests, zero failures/errors and 9 existing skips; lane222 module counts below supersede that only where explicitly stated.

**Review (lane 222): changes required.** The original three shutdown cases pass, but a new public-API review scenario registers a finite chain of channels from close listeners during shutdown. After termination four registrations have succeeded; the third channel still reports registered and the fourth is open and registered. This fails on the development PR and on the downloaded published runtime (4/4 fresh JVMs, including the standalone script check). `prepareToDestroy()` snapshots registrations before callbacks create the next channel; the final executor confirmation is not a drain loop, and same-thread registration still succeeds at `ST_SHUTDOWN`. The existing fix therefore closes the originally demonstrated path without closing this adjacent terminal-registration path. The self-contained test, full output, separate test/code review, and provenance audit are on the evidence branch.

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

This PR is already based on current `4.2`; fetch/rebase was a no-op. Its diff contains only shutdown ordering and the three regression scenarios, with no unrelated change. The exact-tag release port contains the same override/test semantics, adapted to retain that tag's task scheduling.

- release buffer: tests=13456, failures=0, errors=0, skipped=1315; command exit=0.
- release transport: tests=386, failures=0, errors=0, skipped=9; command exit=0.
- development transport: tests=422, failures=0, errors=0, skipped=9; command exit=0.

Both green `kotlin.build` checks explicitly say `no build.kts found in repository`; they ran no Maven compilation/tests. The PR is mechanically mergeable, but lane222's correctness review remains blocking until callback-created registration and final deregistration are covered and corrected. No merge or publication was performed.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
