# Manual backport resolution ledger

Base: `netty-4.2.10.Final`, commit 4cc98736c3947bc93122e0b64e0bd8fc970c6437.
Source shutdown: https://github.com/CodexCoder21Organization/netty-2/pull/1 at d7b4547b64859311b9317a966cb995385399b8c5.
Source allocator: https://github.com/CodexCoder21Organization/netty/pull/1 at 8094800230100d820c3215b51485b9f2e3db30b0.

## Shutdown hunks

1. Source deletes the pre-task `isShuttingDown()/prepareToDestroy()` block from a loop whose task quantum is computed using ioRatio. The tag has the identical block but calls `runAllTasks(maxTaskProcessingQuantumNs)` directly. Delete only the identical block; keep the tag's task quantum unchanged.
2. Source overrides `confirmShutdown()` to return false outside shutdown, otherwise prepare registrations and delegate to the superclass. Insert the override unchanged after `run()`. The tag has the same protected superclass method and the same repeated-call IoHandler contract. Thus every loop/executor final confirmation closes registrations first, including shutdown requested in a task, close callback or shutdown hook. No scheduling code from the later branch is imported.
3. Source adds three public NIO scenarios and a ChannelFuture import. Apply the test-only diff unchanged on the tag. Existing timeout/iteration/assertion values stay unchanged.

## Allocator hunks

1. AdaptivePoolingAllocator: source imports FlightRecorder and short-circuits on `FlightRecorder.isInitialized()` between the existing PlatformDependent capability check and the event-enabled check at allocation/free chunk, allocation/reallocation/free buffer. The tag has all five identical event conditions at earlier line numbers. Apply the same additional guard independently at those five sites.
2. PooledByteBufAllocator: same import/guard at its five corresponding event sites, which also exist on the tag. Preserve each existing event body and enabled check.
3. Compile-only FlightRecorder stub: source adds isInitialized(), getFlightRecorder() and getEventTypes(). The tag already has EventType.getName() and consumer RecordingStream/RecordedEvent stubs, so only the same three methods and java.util.List import are needed.
4. JfrEventsTest: the tag has no such file. Create a minimal class with the source's four new cold-child methods and its exact @Timeout(10), Java 17 condition and @Isolated annotation. Do not copy the later branch's unrelated JFR suite. Copy AllocatorJfrColdStartHarness from the source head unchanged, including child timeouts, heap, release assertions and late-name-enabled event assertion.

## Review before implementation

Tests drive real public registration/shutdown and ByteBuf allocation APIs, with owned Java sockets closed even on baseline failure. Cold allocator processes isolate event registration, and output reader/process cleanup is bounded. Task shutdown, callback shutdown and hook-created registrations exercise the terminal registration ownership invariant. Both allocators are checked before a recorder exists and after a recorder is enabled by name. The platform capability short circuit remains first; recorder existence is read afresh on every operation, so late recording remains possible. No reflection or new mocks are introduced.
