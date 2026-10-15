# Lane 222 — Netty fork reconciliation
Started: 2026-10-15 12:04 UTC. Stop new work by 13:09 UTC; hard stop 13:19 UTC.

## Plan
- [done] Read required context; clone both forks; establish published-artifact provenance and PR ancestry. Done means a source/metadata table backed by downloaded artifacts and git history.
- [in progress; release rebase refuted] Rebase only where needed; audit regression tests; demonstrate failures without the fixes and passing module tests with the fixes.
- [in progress; blocking findings recorded] Independently review tests and changes; address blocking findings; push branches and update both PR descriptions with evidence. No merge or publish.
- [pending] Record terminal verdict, exact remaining work, stop owned processes, and delete lane checkouts/cache.

## 2026-10-15 12:04 UTC — context
OBSERVED: Read lane brief and common.md fully. They prohibit nested delegation, touching the Handoff service, merging, publishing, and watching CI after pushing. The supervisor owns CI waiting. No repository edits or background processes yet.

## 2026-10-15 12:07 UTC — provenance first; substantive base mismatch
| Item | Observed source / metadata | Verdict |
|---|---|---|
| Published transport POM | parent io.netty:netty-parent:4.2.10.1-codexcoder21 | Coordinate matches PR title/current reactor |
| Published transport jar | META-INF/io.netty.versions.properties: longCommitHash=a66b8e41266dd9a8ae193cf3dea021b3b5547d7f, repoStatus=clean; build 2026-10-15 04:17:26 UTC | Published transport records exactly current release PR head |
| Published transport manifest | Implementation-Version and Bundle-Version=4.2.10.1-codexcoder21; Build-Jdk=21.0.12.1 | Consistent with release artifact |
| https://github.com/CodexCoder21Organization/netty/pull/2 | head a66b8e41266dd9a8ae193cf3dea021b3b5547d7f; base 4.2 at 006a2f1d92db733d10112de251600da7b6f8ec51; merge-base 4cc98736c3947bc93122e0b64e0bd8fc970c6437 (netty-4.2.10.Final); behind 541, ahead 4; draft, DIRTY | NOT a routine behind-base rebase: moving onto 4.2 would add 541 development commits to a published exact-tag release |
| https://github.com/CodexCoder21Organization/netty-2/pull/1 | head d7b4547b64859311b9317a966cb995385399b8c5; base and merge-base aa00c11e31381c85ec39f2c518321ff12635ae9c; behind 0, ahead 3; clean | No rebase needed; fetch/rebase origin/4.2 is a no-op (there is no main branch) |
| Shutdown source containment | release commit 13548ce836 ports confirmShutdown override and identical three regression scenarios; original commits are not ancestors | Fix contained semantically as a manual exact-tag backport, not by original commit identity |
| Publish record | supervisor-actions.log 05:12:31Z starts publish after lane146 13/13 gate; 05:15:58Z records 46/46 published, zero failures | Corroborates release branch and publication. out/netty-publish.log is absent from recursive evidence tree, so individual upload log cannot be verified |

OBSERVED: Both heads have two successful kotlin.build checks. Release PR targets development branch 4.2 although its README and prior authorized briefs explicitly require exact netty-4.2.10.Final source. No repository AGENTS.md or separate FORK notes found in tracked files. Read both READMEs, all three prior briefs, lane141/lane146 findings, handoff.md, common.md, Engineering Philosophy, Testing Architecture, and Code Review guidance (relevant sections: TDD, public API, deterministic reproduction, root cause, and red flags).

INFER: Rebase of release PR onto its current base is substantive and contradicts the exact-tag release decision. Per brief step 2 I will not perform it. Supervisor decision needed: preserve release by introducing a maintenance base branch at exact tag and retargeting the PR, or explicitly authorize a newer development-line release requiring new version/build/publication. Current published build == current release PR head for transport. Verifying buffer and other module metadata next. Keeping branch name is coherent as the existing draft-of-record, documented in description; changing it is unnecessary to source provenance.

## Lifecycle/ownership review table (before any source edits)
| Resource | Creation / owner / closure | Terminal behavior and caller tests |
|---|---|---|
| Registered NIO channel | caller creates socket/channel; event loop owns registration; shutdown preparation closes registrations | termination must mean channel closed, deregistered, closeFuture done; existing tests force task shutdown, callback re-entry, and new channel in shutdown hook |
| Event-loop IO handler | group creates handler; loop owns initialize/prepare/destroy | prepareToDestroy is idempotent; every shutdown confirmation precedes terminal destruction; no persisted restart state |
| Allocator event singleton | lazy JVM class initialization; JFR owns event registry | no recorder means allocator must not initialize event classes; fresh-child tests cover adaptive/pooled, heap/direct, resize/release; recording enabled after early use must receive events |
| Test child process/output reader | test creates/owns child and executor | finally forcibly closes child, shuts reader down, and waits with bounds; no shared recorder state across scenarios |

## 2026-10-15 12:09 UTC — complete published module audit
OBSERVED: Downloaded all 46 POMs and the 44 corresponding binary jars listed by the prior release manifest. Every jar has META-INF/io.netty.versions.properties identifying a66b8e41266dd9a8ae193cf3dea021b3b5547d7f and repoStatus=clean. Parent/BOM are POM-only. No HTTP errors. Full per-file SHA256 and metadata saved in published-audit.json. This extends the provenance verdict from transport to every binary module in the published set (native platform classifiers not separately audited).

OBSERVED: All four green checks explicitly report `kotlin.build CI check passed (no build.kts found in repository).` These green checks execute no Maven compilation/tests. Existing PR full Maven suite results remain prior evidence until this lane's verification completes. No source/test changes yet. Initial evidence milestone pushed to https://github.com/CodexCoder21Organization/netty/tree/evidence/lane222-netty-reconcile/investigation/lane222 .

INFER: The public version and branch head provenance is established; no re-publish is needed merely to record/merge that exact source against a suitable maintenance base. Rebasing onto development 4.2 would no longer describe the published release and would require a separately versioned build/publication.

## 2026-10-15 12:11 UTC — review found adjacent shutdown re-entry gap
OBSERVED: Existing three regression scenarios PASS on netty-2 d7b4547b (3 tests, zero failures/errors/skips). Independent public-API review probe creates eight real NIO sockets/channels, registers the first, and has each closeFuture listener synchronously register the next. After group termination the probe FAILS (1 test, 1 failure): first two accepted channels closed/deregistered, third accepted channel closed but still registered. Full stack saved as netty2-reentry-full-stack.txt; full diagnostic pending to print every accepted channel before asserting. No production code changed. All raw sockets are closed by finally even on failure.

INFER (being verified): each prepareToDestroy snapshots registrations before calling close callbacks; those callbacks may register a new channel. Only a finite number of confirmShutdown passes run, so deeper callback chains outlive preparation; the last close can also enqueue a deregistration after the final drain. This is the neighboring lifecycle row the existing single-hook/single-callback cases do not cover. Not yet claiming a fix; retaining reproducible evidence first.

## 2026-10-15 12:13 UTC — review gap confirmed in development fork
OBSERVED: Diagnostic re-entry run fails again, printing all four accepted registrations after termination: `(open=false, registered=false)`, `(false,false)`, `(false,true)`, `(true,true)`. Thus the loop accepts a fourth channel during its final close callback and terminates with that channel open. Existing assertions were not weakened: the diagnostic version merely prints all states before running the same assertions. Compiling the same public-API scenario against downloaded published jars next to establish release impact independently. Source jars for all three changed production classes compare byte-for-byte equal to the release PR head.

INFER: Cannot approve either shutdown change as complete while this path remains. No speculative production fix made. The release-base mismatch is already a substantive stop condition under step 2; additional source changes also need a version/publication decision because published bytes must remain traceable. Continuing the original fail-first regression and module checks, and will update both descriptions with the blocking evidence.

## 2026-10-15 12:14 UTC — published build has the same re-entry failure
OBSERVED: The standalone JUnit public-API review test compiled against only downloaded published Netty jars and failed in 462 ms (1/1 failures). It printed the same four accepted channel states: third channel closed but still registered; fourth channel open and registered after termination. No source checkout classes are on that runtime classpath. This establishes that the already-published artifact has the same gap, not merely the development fork. The test now checks all open-channel invariants before close-future/deregistration invariants; none is removed or weakened. This avoids the earlier third-channel deregistration failure stopping before the fourth-channel physical-close assertion.

The mechanism under review is: NioIoHandler.prepareToDestroy() snapshots selector registrations, then invokes channel close callbacks that can synchronously register another channel; SingleThreadEventExecutor.doStartThread() performs only a final confirmShutdown() after moving to ST_SHUTDOWN and ignores its return, while registerForIo0() accepts registrations from the event-loop thread even at that state. The published override guarantees preparation is invoked, but cannot guarantee that its snapshot includes channels created by the final callbacks.

Full stack/output: published-reentry-review.log. Reproducer source: ShutdownReentryReviewTest.java. These are checkpointed below as evidence, not added as a failing test to either PR branch. No production fix guessed, no published coordinate overwritten.

## 2026-10-15 12:16 UTC — fail-first shutdown and repeated published counterexample
OBSERVED: Reverted only netty-2 SingleThreadIoEventLoop.java to origin/4.2 while retaining the three PR tests: 3 tests, 3 failures, 0 errors/skips, each at the channel-open assertion. Original source restored afterward and working tree clean. The same three tests passed earlier with the fix. Published re-entry scenario repeated in two additional fresh JVMs for reproducibility: failures 3/3 overall; each prints identical four accepted registrations and the fourth open. These were diagnostic repeats of a known, deterministic condition, not retries to seek green. All 46 POMs also parse to the custom version with zero mismatches.

## 2026-10-15 12:18 UTC — release selected tests verified
OBSERVED: At exact release head a66b8e41, selected suites pass: JfrEventsTest 4/4, NIO shutdown scenarios 3/3; zero errors/skips. With only the three production files restored to upstream tag, allocator cases fail 2/4 (both inactive cases); both late-enabled recording cases still pass. Maven correctly skips downstream transport after buffer fails, so that invocation is not counted as shutdown baseline evidence. A separate transport-only negative check follows. All production sources restored after the negative command; no test assertion/budget was changed. Full stacks preserved from Surefire reports.

## 2026-10-15 12:20 UTC — descriptions updated; original release shutdown fail-first complete
OBSERVED: Release transport-only baseline check: 3 tests, 3 failures, zero errors/skips with the original tag loop under unchanged PR tests; restored source afterward. Full buffer/transport module suites now running serially at exact a66b8e41 (bounded outer command, 2 GiB heap). Both PR descriptions were rewritten via REST PATCH with why-first provenance, links to UrlProtocol 702/704, the requested `Review (lane 222)` paragraph/table, and explicit blocking findings. PR heads are unchanged. Both descriptions retain the required footer and say full module counts are pending; they will be amended after completion.

OBSERVED: Separate test and code review is durable at https://github.com/CodexCoder21Organization/netty/blob/evidence/lane222-netty-reconcile/investigation/lane222/review.md . Complete diff inventory: netty-2 changes only loop shutdown ordering and three NIO tests; release changes three production classes, three test files, one compile-only JFR stub file, README public release contract, and 62 POM version substitutions. No unrelated logic edit found. SCM tags remain the upstream base tag. The old release branch name is documented in the description; no rename performed.

## 2026-10-15 12:24 UTC — 20-minute status checkpoint
Request: reconcile the live Netty artifacts with both fork PRs, review and validate them, and leave them ready for supervisor merge without merging or publishing.

OBSERVED: Provenance DONE (46 POMs/44 binary module jars; exact release head; three changed source files equal published sources). Original fail-first checks DONE on both fork lines. Separate test/code review DONE; descriptions updated by REST. Complete release buffer suite: 13,456 tests discovered, 0 failures/errors, 1,315 existing conditional skips; release transport suite still running. Development override is byte-identical to the release override. No nested delegation or background watcher started; only one heavy Maven invocation in this lane. Isolated rebase probe is retrieving missing partial-clone objects, and will be aborted at first substantive conflict.

BLOCKING FINDINGS: (1) Exact-tag release PR targets development 4.2, 541 commits beyond release base; cannot convert the published release to that line as mechanical reconciliation. (2) Finite close-listener registration chain leaves a publicly accepted channel open/registered after termination; reproduced on development fork and published release, published failure rate 3/3. Both current PR heads are retained unchanged. Needs supervisor scope/version/base decision, not a CI re-run.

Remaining lane work: collect final module counts/skips and exact conflict evidence, finish the development transport module verification, checkpoint all findings/PR bodies, and clean up owned processes/checkouts/cache.

## 2026-10-15 12:25 UTC — full release modules pass
OBSERVED: Complete release module command exited 0 in 4m44s: buffer 13,456 tests / 0 failures / 0 errors / 1,315 pre-existing conditional skips; transport 386 / 0 / 0 / 9 existing skips. Allocator/new shutdown regression cases all execute (no skips). Surefire reports and skip summaries retained; no test condition changed. Development transport dependency install and full module run now execute serially, with explicit command deadlines and whole child-group cleanup. This success does not invalidate the independently failing callback-chain reproducer, which is outside the existing PR suites and remains blocking.

## 2026-10-15 12:26 UTC — substantive rebase conflict captured and aborted
OBSERVED: Isolated worktree rebase with --reapply-cherry-picks (to avoid scanning the 541-commit partial-clone history for equivalent patches) stopped on the first release commit 7967591813: add/add conflict in buffer/src/test/java/io/netty/buffer/JfrEventsTest.java. Development base has an existing ~357-line JFR suite; release adds its own 34-line/four-scenario suite on the exact tag where no JfrEventsTest existed. Conflict is test-semantic integration, not a whitespace/version-only resolution. Full conflict is in release-rebase-reapply.log. Aborted immediately without resolving, and verified isolated worktree head returned to a66b8e41266dd9a8ae193cf3dea021b3b5547d7f. Original release PR branch remains untouched. A previous default rebase was stopped during object retrieval and aborted; no changed source was adopted.

INFER: This independently confirms the brief's substantive-conflict stop condition. A development-line rebase cannot be presented as preserving the exact published release. The source set should first be assigned an intentional maintenance base or a new development release/version.

## 2026-10-15 12:31 UTC — final validation and item-by-item disposition
OBSERVED: Development transport dependency install exited 0, then its full module test command exited 0. Final module counts:

| Source | Tests discovered | Failures | Errors | Existing skipped cases |
|---|---:|---:|---:|---:|
| release a66b8e41 — buffer | 13,456 | 0 | 0 | 1,315 |
| release a66b8e41 — transport | 386 | 0 | 0 | 9 |
| development d7b4547b — transport | 422 | 0 | 0 | 9 |

All seven newly added original regression cases ran; no new skip or test relaxation was introduced. Exact skipped class counts are in module-skip-classes.json. Most buffer skips are existing JDK/unsafe preconditions; the changed JfrEventsTest has zero skips. Development CoalescingBufferQueueTest deliberately consumes queued data under the queue and emits four expected `readableBytes is 292 but the queue is empty` log messages; its 16 cases pass. Full module logs retain those messages and all stacks rather than filtering them out.

The final standalone reproduction script was executed and returned the expected exit 1 with the same fourth-channel open/registered assertion. Together with the earlier three published fresh-JVM invocations, the published defect is now observed 4/4. It checks downloaded source commit metadata before compiling/running, uses no checkout classes, and cleans its temporary downloads automatically.

Existing-test edit inventory: ZERO permanent changes to either PR's tests. During investigation a new review-only test was created, then diagnostic output was moved before assertions and open-state assertions were grouped before future/registration assertions so the fourth accepted channel is tested directly; every original invariant assertion remains. The test was removed from the source tree after copying it to the evidence branch. Temporary production reversions for fail-first checks were restored. Both source branches and the rebase probe are clean and still at their original heads.

### Brief disposition
1. DONE: both forks cloned fresh/read, ancestry and behind counts recorded, all published modules audited, metadata/source-jar/publish-record provenance table written first and pushed.
2. DONE for test verification and netty-2 base synchronization (no rebase needed). The proposed routine rebase of the release is REFUTED as safe mechanical reconciliation: exact-tag release vs 541 development commits and actual JFR suite add/add conflict. Aborted at the first substantive conflict as explicitly required by the brief.
3. DONE: separate test and code reviews, complete diff inventory, provenance and why-first REST description updates. The claim that both PRs can be marked merge-ready as-is is REFUTED by the finite public-API callback chain (development and published source) and substantive release-base conflict. Blocking source correction was NOT performed after the required stop at substantive integration; it needs an intentional base/version/release decision. Heads unchanged, so no force-push was needed. Existing green checks execute no Maven build; this lane's module runs provide the actual validation.
4. Cleanup in progress; final process/disk verification will be appended locally after the last evidence push.

### Exact next steps for the supervisor
- Choose an exact-tag maintenance base at 4cc98736c3947bc93122e0b64e0bd8fc970c6437 and retarget the release PR, or explicitly choose a different source line/version. Do not present a development-line rebase as the already-published source.
- Correct final callback-created registration/deregistration using the self-contained reproducer in this evidence branch, preserving all three existing shutdown cases and keeping shutdown bounded even if callbacks keep creating channels. Verify both fork lines, then rerun module/consumer checks.
- Any corrected release requires a new coordinate/build/publication; do not overwrite 4.2.10.1-codexcoder21. An unchanged-head merge against an appropriate maintenance base would need no re-publication solely for provenance, but would retain the demonstrated defect.
- Supervisor owns all CI waiting, merge decisions, publishing and deployment. This lane performed none of them.

Artifacts: https://github.com/CodexCoder21Organization/netty/tree/evidence/lane222-netty-reconcile/investigation/lane222 ; https://github.com/CodexCoder21Organization/netty/pull/2 ; https://github.com/CodexCoder21Organization/netty-2/pull/1 . Findings remain at /tmp/claude-1000/-code/bc9e914b-1f43-4800-9ffc-3e16c08ce74e/scratchpad/out/r222-findings.md .
