# Consumer selection blocker

Observed on the exact UrlProtocol pin commit ee207bbea86351df923bb9dcdb7c21650aefdc1d:

- The deterministic root-close test executed once and failed with an open, registered root after event-loop termination. No behavioral retry was run. The ten racing runs and two connection cases were not run after the failed gate.
- A separate diagnostic reports transport and buffer loaded from upstream `4.2.10.Final` jars. Its intentionally thrown diagnostic message makes the origins visible in `runtime-binding-origin.log`; it does not exercise or retry shutdown.
- The staged custom transport jar contains protected `confirmShutdown()` (javap); the equivalent three NIO regressions failed 3/3 before the port, passed 3/3 after, and the entire transport suite passed.

Small independent selection experiment: `CoursierVersionProbe.java` requests only transport at both `4.2.10.Final-codexcoder21-1` and `4.2.10.Final`, through public `coursierapi.Fetch` methods. Run it on the classpath obtained by fetching `kompile.cli:kompile-cli:0.0.100` from kotlin.directory. The API origin is `io.get-coursier:interface:2.1.31-freshcache1`; it returns upstream Final transport/common/buffer/resolver. Full output is `java-version-mediation-probe-full-cp.log`. The standalone `/home/u/bin/cs resolve` with the same two coordinates returns the custom versions (`version-mediation-probe.txt`). This isolates a difference in dependency selection before any Netty shutdown operation.

The consumer's libp2p POM brings upstream Netty; its custom direct pins coexist with those requests. The runtime origin diagnostic confirms that the intended fork is not the transport executing the test. Source backport equivalence is not refuted. The fallback to 4.2.20 was only authorized if exact-tag shutdown equivalence could not be obtained, so no fallback was made.

Required next step: establish exact fork selection in the Java API/build resolver, checking class origins before executing the prescribed gate. Potential exact-version constraints need proof against the same API, not an assumption based on native cs results. Do not replace upstream-coordinate cache bytes with the custom jars: that would hide whether the real published pins work. No resolver/library source fix or version-constraint change was guessed in this lane.

The earlier name and file filter setup attempts ran no test functions: the scanner rejects an unrelated deliberate clocks-simple 0.0.11 runtime test against another test's 0.0.16 pin. Untouched main emitted the same error. The verification worktree therefore exposed exactly the four requested files (all byte-identical to the pin branch) and retained all production files. Temporary repository annotations were restored; the final actual invocation used no source edits and artifacts copied into the lane-private Coursier cache. All setup logs and full stacks are retained in separately named directories.
