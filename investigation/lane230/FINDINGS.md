# Lane 230 — Netty 4.2.10.2 release PR
Started 2026-10-15 13:01 UTC. Stop new work 14:06 UTC; hard stop 14:16 UTC.

## Plan
- [in progress] Read context, docs and fork notes; verify source/base heads and exact published-source version file inventory.
- [pending] Create release branch from a66b8e41; cherry-pick only lane227 correction/tests; set 4.2.10.2 at exactly prior release version locations; push first source checkpoint.
- [pending] Build published modules and run common/transport suites plus invariant tests; record counts/exit codes and independent test/code reviews.
- [pending] Fetch/rebase maintenance base, verify exact final head, open non-draft PR by REST with provenance and publish procedure; push evidence, stop owned processes, remove checkout/cache.

## 2026-10-15 13:02 UTC — initial context
OBSERVED: Read brief, common.md, prior lane222/227 findings and github-repos/status-report instructions. No nested delegation, Handoff writes, CI waiting, merge, publication or deployment is authorized. Brief explicitly requires exact maintenance base rather than development main; will rebase onto maint/4.2.10-codexcoder21 before builds. Lane227 records final source 7a9caa8c with five new public NIO invariant cases and 427-test development transport suite. This lane must verify release-line results itself.

## 2026-10-15 13:04 UTC — source/base and invariant review
OBSERVED: Fresh clone read both development and release README.md; no tracked AGENTS.md or FORK notes. Maintenance head is exact tag 4cc98736c3947bc93122e0b64e0bd8fc970c6437. Release start is a66b8e41266dd9a8ae193cf3dea021b3b5547d7f; netty2 head 7a9caa8cfd38683230db50ae83c58f22002044ba. Last four commits after d7b4547b are df533854c5 (new tests), 6c5f69997e (source), c062219ba3 (exact failure messages), 7a9caa8cfd (boundary cases). Prior version commit changes exactly README.md and 62 POM files.
Mechanism being ported: final selector snapshot closure invokes callbacks that register new channels after the snapshot; terminal same-thread registration remains admitted. The correction closes registration admission once graceful termination is confirmed, then closes final IO and drains deferred deregistration tasks. Reproducer: public real-NIO close/unregister callback chains and immediate shutdown in NioShutdownReentryTest.

| Resource | Creates / owns / closes | Terminal/caller contract | Reentry / close / restart tests |
|---|---|---|---|
| Registered channel/socket | caller creates; loop owns accepted registration; shutdown closes | termination leaves channel closed, closeFuture completed and deregistered | close-listener and unregister callback chains; immediate shutdown; no persisted restart |
| IO registration admission | event-loop thread owns flag | final confirmation rejects new registrations; live registrations still work | full failed-registration message; live-loop preservation; post-termination boundary |
| Deferred cleanup task | loop queues/owns/drains | drain deregistration before publishing termination | callback chains assert deregistered after termination |
| Test socket/group | test creates and closes in finally | no sockets or loop threads survive test | five ported tests use public API and real local sockets |

Docs read: common.md, full handoff snapshot, lane222/227 findings, remote lane222 FINDINGS.md, Engineering Philosophy (root cause/reproduce/upstream/refutation), Testing Architecture (TDD, comprehensive tests, public API, hermetic real dependencies, bug workflow, never calibrate), Code Review red flags. Prior allocator source/tests stay unchanged; this is a release port, not a new downstream workaround.
Plan: source/context DONE; cherry-pick/version IN PROGRESS. No substantive conflict encountered yet.

## 2026-10-15 13:05 UTC — source checkpoint
OBSERVED: Four cherry-picks complete. Sole conflict was field-declaration context: release lacks development-only ioRatio/activeIoTimeNanos fields; added only ioRegistrationClosed after maxTaskProcessingQuantumNs. No execution hunk conflict. Five-case test file is byte-identical to upstream fix head. Version file inventory exactly equals a66b8e41's 63 files (62 POMs plus README), one literal substitution per file. Branch source checkpoint pushed at 6cda658045; subsequent local indentation-only correction restores four spaces on ported field comment and will be included in final push. Core six-root build is running serially, with private Maven cache, 2 GiB JVM heap and 1200-second command deadline.
OBSERVED: Lane222 findings establish provenance but contain no exact publication command; lane146 evidence build_release.py and assemble_artifacts.py give reactor/BOM build and per-module staging. Reading that earlier publication record to supply a precise procedure as required by this brief. No artifacts uploaded.
