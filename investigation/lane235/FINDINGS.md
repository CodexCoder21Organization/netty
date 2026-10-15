# Lane 235 — Netty 4.2.10.2 publication
Started 2026-10-15 13:52 UTC; stop at 14:57 UTC (65 minutes); hard wall 15:07 UTC.

## Plan
- [in progress] Read brief/common/docs/prior evidence, verify merged maintenance source and exact previous payload set.
- [pending] Build independent BOM plus exact 45-module reactor serially with bounded memory; audit/stage payloads.
- [pending] Publish each of 46 coordinates with CLI 0.0.6, retaining output and direct exit code.
- [pending] Probe every POM/JAR/classifier, verify downloaded transport provenance, record UrlProtocol pin lines, push evidence and clean checkout/staging/cache.

## 2026-10-15 13:54 UTC — initial context
OBSERVED: Read brief, common.md, handoff snapshot, lane222/230 findings and GitHub/Maven publisher/status skills. Explicit lane brief authorizes Maven publication and --force; no additional approval required. No merging, deployment, nested delegation, CI waits or Handoff writes. Maintenance base overrides generic main rebase because this release must remain on exact-tag source. Prior lane230 built all 45 reactor modules plus BOM, with 44 binary modules, parent and BOM POM-only. Prior suites at release source: common 1430/0 failures/0 errors/7 existing skips and transport 391/0/0/9; this lane is authorized to use -DskipTests.

## 2026-10-15 13:56 UTC — source and prerequisites verified
OBSERVED: Fresh netty checkout head 6e9dcc994cc29c022ac547ab113c9e603d7a9c29 equals merged release PR https://github.com/CodexCoder21Organization/netty/pull/3 merge SHA. Diff from tested release e5f302731d is empty; checkout clean, no tracked AGENTS.md. Read README and prior PUBLISH-PROCEDURE.md, assembly/audit scripts, prior module manifest and requested Philosophy/Testing/Code Review sections. Native prerequisites installed only into lane-private toolchain (Debian packages, Rust 1.99.0, Go 1.27.2); C compile/link/run passes. Independent BOM install exits 0. Prepublication probes: every one of 46 .2 POMs returns HTTP 404, so none is occupied. Full exact reactor started after maintenance fetch/rebase, 2 GiB heap, native serial compilation, 2700-second hard deadline.
INFER: Since the merge tree exactly equals tested release source, using -DskipTests here follows the brief; no new source/test edits are needed. Main UrlProtocol still pins upstream Final; the requested .1 follow-up must target pending pin branch first. Checking exact pin locations there.
Plan item 1 DONE; item 2 IN PROGRESS.

## 2026-10-15 14:01 UTC — native prerequisite and module progress
OBSERVED: Reactor has built native Unix common and handler and reached HTTP (20/45); no build failure. C and C++ private compile/link/run probes pass. Old 4.2.10.1 manifest and lane230 .2 manifest have identical 46 module names, per-module payload counts, and total 136 payloads / 272 checksums. Native classifiers in that set are linux-x86_64 for netty-transport-native-unix-common, netty-transport-native-epoll and netty-codec-native-quic; no native kqueue classifier was part of that publication. Source tree remains clean at merged maintenance SHA. Evidence checkpoint branch: https://github.com/CodexCoder21Organization/netty/tree/evidence/lane235-netty-publish/investigation/lane235 .
OBSERVED: Fresh UrlProtocol pin-branch clone at 2f15e153168e2419d93c950c6910c57116b89a7b, README read; no AGENTS.md. Exact .1 inventory is 5 build.kts lines (59–63), 48 test imports in 33 files, README line 24; full file:line inventory retained in urlprotocol-pin-lines.txt. Default main still has upstream Final pins because https://github.com/CodexCoder21Organization/UrlProtocol/pull/704 is not merged. No consumer edit is authorized by this publication-only brief.
