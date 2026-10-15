The owner asked to make the kompile runner select the organization's custom Netty build so the shutdown work in https://github.com/CodexCoder21Organization/UrlProtocol/pull/702 can pass its consumer gate. The previous release string lost dependency mediation to upstream `4.2.10.Final`, so the consumer loaded upstream transport and buffer even with custom direct pins.

This branch now uses `4.2.10.1-codexcoder21`, still based on the exact `netty-4.2.10.Final` tag with the same two fixes. All 62 POMs and the README are changed only by version substitution from the previous release head. The branch name retains its earlier release string because it is the existing draft PR head.

The selection mechanism is version ordering in the runner's exact `coursierapi.Fetch` interface, `2.1.31-freshcache1`. Its public comparator ranks the previous `4.2.10.Final-codexcoder21-1` below upstream Final, and the two-root Fetch assertion fails with upstream transport/common/buffer/resolver selected. The same assertion passes for `4.2.10.1-codexcoder21`; the runner comparator, native cs, and Maven ComparableVersion all agree that it is higher than upstream Final. The consumer's jvm-libp2p dependency directly brings the upstream requests. Full dependency trees and exact API selections are recorded separately in the evidence; no custom bytes are stored at upstream coordinates and no transitive dependency is excluded.

The unchanged source backports are:
- https://github.com/CodexCoder21Organization/netty-2/pull/1: run registration closure from `confirmShutdown()` before terminal shutdown confirmation, retaining the exact tag's task scheduling.
- https://github.com/CodexCoder21Organization/netty/pull/1: check that a Java Flight Recorder exists before evaluating adaptive/pooled allocator event singleton state, preserving later enabled recording.

Lane141 proved the unchanged source fixes fail first and pass afterward: shutdown 3/3 failed before and 3/3 passed after; allocator 2 inactive cases failed before and all 4 cases passed after. Its previous-version full suites passed (common 1,430 tests, transport 386, zero failures/errors; 7 and 9 existing conditional/disabled cases respectively). This lane runs no full suite, as explicitly required, and changes no test assertions, timeouts, bounds or iteration counts.

REBUILD_AND_ARTIFACT_RESULTS

CONSUMER_GATE_RESULTS

UrlProtocol pin branch: https://github.com/CodexCoder21Organization/UrlProtocol/tree/fix/lane137-root-close-pin . It has exactly 53 version substitutions in 34 files. Verification uses the same four-file discovery scope as lane141 to avoid the independently verified unrelated workspace clock-pin discovery conflict; every requested file is byte-identical to that branch, and all production files remain present. No consumer source workaround or discovery change is committed.

Evidence, version probes, full trees, review, build logs, origins, and every consumer result:
https://github.com/CodexCoder21Organization/netty/tree/evidence/lane146-version-selection/investigation/lane146

Earlier fail-first source/backport/full-suite evidence:
https://github.com/CodexCoder21Organization/netty/tree/evidence/lane141-custom-netty/investigation/lane141

No publication, merge, enqueue, deploy, or Handoff write was performed.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
