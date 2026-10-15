The UrlProtocol test `testProtocolRootCloseCallerRacingEventLoopShutdown` left a channel open after event-loop termination, leading to the published `4.2.10.1-codexcoder21` correction pinned by https://github.com/CodexCoder21Organization/UrlProtocol/pull/704 and recorded in https://github.com/CodexCoder21Organization/netty/pull/2. Review then found that channels registered by termination callbacks could still remain open; the owner requested this `4.2.10.2-codexcoder21` release PR so the correction from https://github.com/CodexCoder21Organization/netty-2/pull/1 can be published and UrlProtocol re-pinned in a follow-up (related original failure: https://github.com/CodexCoder21Organization/UrlProtocol/pull/702).

This release starts at the exact published source [a66b8e41266dd9a8ae193cf3dea021b3b5547d7f](https://github.com/CodexCoder21Organization/netty/commit/a66b8e41266dd9a8ae193cf3dea021b3b5547d7f), cherry-picks the four correction/test commits through [7a9caa8cfd38683230db50ae83c58f22002044ba](https://github.com/CodexCoder21Organization/netty-2/commit/7a9caa8cfd38683230db50ae83c58f22002044ba), and changes the same 62 POMs plus README version location to `4.2.10.2-codexcoder21`. It targets `maint/4.2.10-codexcoder21`, the exact `netty-4.2.10.Final` maintenance line. The only cherry-pick conflict was context beside fields present only on development 4.2; the release adds only the new registration flag. No development scheduling changes were imported. The allocator correction and original shutdown tests remain unchanged.

After graceful shutdown commits to termination, the event loop stops accepting IO registrations before closing its final channel snapshot, then drains deferred deregistration. Immediate shutdown also rejects same-thread registrations. Live-loop callback registration remains supported.

Validation on release head [e5f302731d3c0ce684d323002f5fdce319381fdb](https://github.com/CodexCoder21Organization/netty/commit/e5f302731d3c0ce684d323002f5fdce319381fdb) (JDK 21, serial Maven, 2 GiB JVM heap):

| Gate | Tests | Failures | Errors | Existing skips | Exit |
|---|---:|---:|---:|---:|---:|
| Final invariant class with original published event-loop source | 5 | 3 expected | 0 | 0 | 1 expected |
| Corrected NIO classes (original suite plus five new invariant cases) | 21 | 0 | 0 | 0 | 0 |
| Full common suite | 1,430 | 0 | 0 | 7 | 0 |
| Full transport suite | 391 | 0 | 0 | 9 | 0 |

Complete 45-module publication reactor (`common,buffer,transport,handler,codec,all -am -DskipTests install`) and independent BOM install both exit 0. Staging/audit covers exactly the prior 46 artifact names: 136 POM/JAR payloads, 272 matching checksums, and all 44 main jars record this clean commit and version. Linux native epoll and QUIC classifier builds succeed. The final common/transport gate after the last maintenance rebase also exits 0 with 1,821 tests, zero failures/errors and 16 existing skips. Native module test suites and non-Linux classifier builds were not run.

The three baseline failures assert an open callback-created channel, a leftover registration, and successful admission after immediate shutdown. All five invariant cases run and pass on the corrected release. No existing test, assertion, iteration count, timeout or skip condition was changed. Existing skips are retained in the full Surefire reports. The first build encountered missing native compiler tools; full output/stacks are retained, and the final build uses lane-local native tools. Surefire's native-stream warning comes from the existing JVM GC startup flags, as shown in the retained dumpstream files.

Separate test and code reviews found no blocking source-port issue. Exact audit verifies that the source edit lines equal the reviewed development correction, the five-case test class is byte-identical, and all remaining changes relative to the published source are the 63 version substitutions.

Evidence:
- Published source provenance and original gap: https://github.com/CodexCoder21Organization/netty/blob/evidence/lane222-netty-reconcile/investigation/lane222/FINDINGS.md
- Prior deterministic reproduction, fix and development transport suite: https://github.com/CodexCoder21Organization/netty-2/tree/evidence/lane227-netty-callback/investigation/lane227
- This release's audit, reviews, logs, complete reports, version file inventory and findings: https://github.com/CodexCoder21Organization/netty/tree/evidence/lane230-netty-release/investigation/lane230

Publication procedure for the supervisor: https://github.com/CodexCoder21Organization/netty/blob/evidence/lane230-netty-release/investigation/lane230/PUBLISH-PROCEDURE.md . It gives the prior release's exact independent BOM install, `-pl common,buffer,transport,handler,codec,all -am -DskipTests install` build, one-POM-per-module assembly, checksums and parent/BOM/dependency order, then the exact per-directory publisher invocation. It also links the lane146 build/staging scripts that supplied those commands; lane222 records the 46-artifact publication provenance but contains no upload command.

**No artifact was published by this lane. Do not overwrite `4.2.10.1-codexcoder21`.** This PR is open for review; CI monitoring, merge and publication belong to the supervisor. The repository's existing kotlin.build checks report no build.kts and do not execute these Maven suites.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
