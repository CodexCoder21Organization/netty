# Native source generation failure reported as a missing custom artifact

Attempt: serial Netty 4.2.10.Final-codexcoder21-1 reactor install using the requested six roots with -am. This selects 45 modules, including native epoll and QUIC through test dependencies even with -DskipTests.

Observed: the image has no compiler/build tools. After preparing a lane-local toolchain from Debian packages, HawtJNI's generate goal ran `./autogen.sh`, which reported `Can't exec "aclocal": No such file or directory` and `rc: 2`. Its later build goal then attempted to fetch `io.netty:netty-transport-native-epoll:zip:native-src:4.2.10.Final-codexcoder21-1` from Central and failed because that custom version has never been published. The final error names missing custom source rather than the failed local source-generation command. Full log: custom-reactor-install-complete.log, lines around 4614–4639 and 4693 onward.

Workaround: add the Debian alternatives aliases aclocal -> aclocal-1.16 and automake -> automake-1.16; relocate embedded autotools script paths to the lane-private installation. A real autoreconf/configure check then succeeded. Resume the reactor at native epoll. Build jobs remain serial. No repository code or tests changed for this environment repair.

Suggested durable fix: provide the full native toolchain in build images, and make HawtJNI fail immediately when autogen fails, preserving that error instead of trying a custom-version source download.

The report-challenge skill was read, but its CLI automatically enqueues and merges a PlanRepository PR. This lane explicitly forbids enqueue/merge, so this report is retained in the evidence branch for the supervisor instead.
