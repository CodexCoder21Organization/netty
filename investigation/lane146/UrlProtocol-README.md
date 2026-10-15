# UrlProtocol

Low-level P2P protocol for opening raw RPC streams to `url://` services.

## Important: Most Users Should Use UrlResolver Instead

**In the vast majority of cases, you should use [`UrlResolver`](https://github.com/CodexCoder21Organization/UrlResolver) rather than UrlProtocol directly.** With UrlResolver, you only need to know the `url://` URL of the service you want to connect to:

```kotlin
val resolver = UrlResolver()
val service = resolver.openConnection("url://com.example.myservice/", MyService::class)
```

**You do not need to know peer IDs, multiaddresses, or any other low-level networking details.** The url:// protocol abstracts these away entirely. Peer IDs (like `12D3KooW...`) and multiaddresses (like `/ip4/.../tcp/.../p2p/...`) are internal implementation details that normal users never interact with.

**When should you use UrlProtocol directly?** Only in rare advanced scenarios:
- Building custom protocol extensions
- Implementing raw RPC stream communication
- Debugging low-level network issues
- Operating relay or bootstrap infrastructure

For normal application development, use UrlResolver and just provide the `url://` URL.

## Local RPC transport failures

`RpcStream.sendRequest` implementations return locally generated failures with a
`RpcTransportFailure` value in `response.error?.data`. Its `phase` distinguishes
`REQUEST_WRITE`, `CONNECTION_CLOSED`, `RESPONSE_TIMEOUT`, and `RESPONSE_READ`;
`cause` retains the underlying failure when one is available. A response read or
admission failure does not necessarily close the stream. Check this type to decide whether to replace a connection;
application error codes and messages do not identify transport failures.

The marker is local to the caller and is omitted when a response is serialized. A
response received from the service cannot acquire it through JSON. Existing error
codes and messages are unchanged. Caller-side request serialization failures propagate
their original exception before transport begins; they are not RPC transport results.

`UrlProtocol.sendServiceRpcRequest` follows the same rule. It replaces the cached stream
and sends the call once more only for a `REQUEST_WRITE` or `CONNECTION_CLOSED` transport
failure; a connection that closes after the request was written can therefore run the call
twice. It never retries a `RESPONSE_TIMEOUT` or `RESPONSE_READ` failure, or a service's own
error, whatever its message says. An exception that leaves the stream open, such as a failure
serializing the caller's parameters or an interruption, propagates unchanged and the stream
stays cached; an exception that closed the stream is retried on a replacement stream. A caller
whose thread is interrupted is not sent again; the failure is reported with the interruption
still set, and the stream is still replaced for later calls. If close has begun when a call without
caller interruption would replace its stream, the call fails with the close instead of reconnecting;
this also applies to the replacement attempt. Either way the call is sent at most twice. A replaced
stream stops receiving new calls, lets the calls already in flight on it finish, and is closed when the last of them is
done (or when the `UrlProtocol` is closed); if that close fails, an
`EvictedRpcStreamCloseWarningEffect` is tossed. When the call finally fails, the thrown
`UrlProtocolException` carries the transport failure's `cause`, as the bytecode request
methods do.

## Relay request failure logs

A relay writes one `[RelayRequestFailed]` line to standard error when a forwarded request
loses its response path. This is enabled without the debug property. The line names the caller's
`requestId`, this relay's `forwardRequestId`, caller/provider/relay peer ids, and both connection
and stream identities. `nextHopPeerId` names the authenticated peer on the provider-side connection;
on a multi-hop route this can be another relay rather than the final provider. `forwardRequestId` is the id the next hop receives; each relay restores its
caller's id on the response. These two ids let operators join records across relay hops.
`rpcRequestId` joins those transport ids to the caller's application RPC id when its adapter supplies
that id in the `resolverRpcRequestId` relay request header. It is `unknown` when that header is absent.
The relay preserves this diagnostic header across forwarded requests and chunks. The join remains
available when the provider never receives a request or completes normally before its reply is lost;
concurrent RPCs to one provider retain distinct caller ids. This field follows the same escaping and
length bound as the other fields and does not require reading or retaining the request body.

`closedSide` names `caller`, `provider`, or `relay`. `reason` records the event observed at this
relay: `remote-end-of-stream`, `idle-timeout`, `stalled-write-retirement`, `shutdown`, `local-close`,
or `error`; `cause` carries the observed exception when present. Remote EOF does not reveal the
remote process's own shutdown reason. Successful forwards add no failure line. A response queued
for transport remains eligible for a failure record until its write completes; queue admission
alone is not delivery. No request or response body is logged. Individual peer-supplied fields retain at most the first 1,024 input characters, then escape
backslashes, CR/LF and semicolons onto one line. Escaping can expand that retained prefix; when the
input is longer, the field also shows its original character count in a truncation suffix.

## Overview

UrlProtocol provides the low-level foundation for peer-to-peer service discovery and RPC communication over `url://` protocol URLs. It includes:

- **`UrlProtocol`** — Low-level API for opening raw RPC streams with direct protocol-level communication
- **P2P networking** — Built on libp2p with Ed25519 keys, gossip-based discovery, and universal relay architecture
- **Peer management** — PeerRegistry, gossip protocol, relay services
- **Service infrastructure** — Service registration, bytecode protocol for sandboxed execution

For detailed information about the network architecture, including routing, gossip propagation, and relay mechanisms, see [docs/NETWORK_ARCHITECTURE.md](docs/NETWORK_ARCHITECTURE.md).

Relay forwarding now maintains a link-state topology alongside the existing distance-vector table. Link-state advertisements list directly observed peer links and measured costs, are periodically re-originated before expiry, and are flooded through the existing gossip/relay substrate with sequence, timestamp, TTL, origin-count, and per-origin adjacency bounds (256 direct links by default). The fixed adjacency bound keeps both the retained LSA database and transient SPF graph linear in accepted origins rather than allowing dense peer-pair growth. Each relay computes its own SPF next-hop table from reciprocally confirmed edges only. Forwarding uses the link-state next hop when one is known, applies a hop limit to forwarded relay requests, and falls back to the distance-vector/relay behavior during convergence or when peers have not emitted usable LSAs. A re-flood pays one shared, bounded transport-admission interval for the whole fan-out rather than one interval per recipient, and it spends that interval on the thread that originated the advertisement: every recipient that recovers writability inside the interval is still delivered to, only a recipient still stalled when the interval expires is dropped, and an advertisement never waits on any other scheduler to run.
Local link-record updates take their list snapshot and allocate its version as one ordered transition.

Ordinary gossip fan-out is best-effort and enters a bounded serial outbox per registered peer. A
shared worker pool services one item from each peer lane per turn, so a backpressured peer neither
blocks the inline broadcast caller nor monopolizes the workers ahead of a healthy peer. The relay
bounds each lane to eight messages and 12 MiB of estimated retained data, with a 24 MiB aggregate
bound across all lanes; only the saturated peer's excess copies are shed. Authoritative service
withdrawals use the separate reliable path below.

### Inbound substream admission

A host bounds the inbound substreams it holds because the muxer creates a channel, pipeline,
negotiator and negotiation-timeout task before the admission visitor runs.
`InboundSubstreamAdmissionControl` counts live inbound substreams per connection and across the host.
At the per-connection soft cap (`MAX_INBOUND_SUBSTREAMS_PER_CONNECTION`, 256), it disables automatic
TCP reads while keeping one controlled read pending, so peer departure remains observable. The
per-connection hard limit includes 64 extra slots for already-arriving work. Exceeding that limit
resets only the excess child; the accepted root preserves every admitted stream in either direction.
The existing controlled-read pause bounds further arrivals. Per-connection overload records a
separate retirement obligation that closes the root only after both stream directions are idle.

This preservation rule also covers failures while installing a pause, scheduling a controlled read,
or issuing that read. Admission restores automatic reads, renews read demand so a partially received
frame can finish even after a failed resume, and restores matching read-state accounting before
reporting the exact failure through the transport exception path. Excess children continue to be
refused. An accepted root's read failure records retirement after both stream directions finish;
connections dialled by the host retain their retirement exemption.

At the aggregate cap (`MAX_INBOUND_SUBSTREAMS_GLOBAL`, 1024), an excess inbound substream is reset
before protocol negotiation. An accepted root holding live work in either stream direction survives,
including when the same arrival also exceeds its per-connection limit. Its reads are throttled through the
controlled read pump for that aggregate generation. The generation drains below three quarters of
the cap, clearing its refusal throttles; available slots can be admitted before then. A late refusal
cannot publish a throttle belonging to a drained generation.

An accepted root is idle only when it has no live streams in either direction. An idle root asking
while full is retired; a busy root spared after refusal is retired when its last stream closes,
even if the cap has since drained. Host-initiated streams keep their accepted root alive without
consuming inbound aggregate capacity. Registration in either direction and retirement are serialized,
so an older stream's close cannot retire a root carrying replacement work, and a terminal root
cannot register new work. A host-initiated open refused on a terminal root fails both its stream
and controller futures with `ConnectionClosedException`, before protocol negotiation.
Only one close operation is outstanding at a time; if that operation fails,
the root remains terminal and a later refused visit can hand off another close. Until physical
close completes, terminal roots retain controlled reads independently of aggregate-generation drain
and per-connection low-water resume.
`InboundSubstreamAdmissionRetirementFailureEffect` reports the exact cause and post-failure
retirement state to the effect scope that constructed the host. If that owner callback throws a
fatal `Error`, the exact error reaches the transport exception observer after the original close
cause. `shedIdleConnectionCount()` counts completed aggregate idle retirements exactly once;
deferred per-connection-only retirements do not contribute. Together with
the muxer's independent per-root child ceiling, this bounds retained resources from refused peers
without discarding their admitted work in either direction. Connections the host dialled are exempt
from these retirement paths.

`InboundSubstreamAdmissionCapEngagedEffect` reports aggregate engagement and refusals, with the live
count, configured cap and running refused total. Reports reach the effect scope that constructed
the controller and are rate-limited through its injected `Clock` to at most one per
`MIN_MILLIS_BETWEEN_INBOUND_ADMISSION_CAP_EFFECTS` (60 seconds). A backward clock adjustment starts
a new baseline without an immediate duplicate report; one interval in the new timeline permits
exactly one further report even under concurrent refusals. Per-connection-only refusals do not
emit an aggregate report or consume that reporting interval. Observer failures preserve reservation
cleanup. Existing two-parameter and no-argument constructors remain compatible with compiled callers;
the three-parameter overload accepts an explicit Clock.

The same counters are available on demand from `currentGlobalLive()`, `maxObservedGlobalLive()`,
`totalInboundSeen()`, `rejectedCount()` and `shedIdleConnectionCount()` via
`Libp2pHostFactory.inboundAdmissionControlFor(host)`. This diagnostic lookup weakly references both
the Host and its controller, so an owner effect handler may capture the Host without making the
factory retain that Host after it stops.

On a relay client's registered connection, peer scoring and relay-delivered gossip callbacks run
in a bounded serial lane for the authenticated relay peer. The connection reader decodes and
enqueues that callback work, then continues dispatching later protocol frames, so an application
callback cannot delay a later RPC frame on the same connection. The default lane retains 64
callbacks in addition to the callback currently running. `RelayConfig.receiveCallbackQueueCapacityPerPeer`
can set a bound from 1 through 4,096 before the `RelayService` is constructed. Ordinary callbacks
also share a 24 MiB estimated retained-data bound. When either ordinary-work bound is full, the
newest ordinary callback is dropped; `RelayService.relayWarningEffectsSnapshot()` exposes the
latest `RelayReceiveCallbackQueueOverflowWarningEffect` with the peer, message type, queue depth,
and retained bytes. Service announcements and withdrawals instead retain only the newest accepted
transition for each provider/service key according to the provider-authored timestamp; a withdrawal
wins an equal-timestamp tie, so an older or equal announcement cannot replace it. An accepted
transition remains retained, including its byte charge, while its callback is running. A reconnect
moves that same transition to the replacement lane unless a newer transition supersedes it.
If a newer transition supersedes an in-flight callback, the old payload remains charged until that
callback releases it even though only the newer transition remains eligible to apply.
Each accepted payload creates one charge, and that charge moves with the payload until its normal
terminal release after application, supersession, or close. At every queue mutation boundary the
charged bytes equal the sum of live entry sizes, and the ledger is exactly zero at quiescence;
closing a lane drops each entry through that lifecycle instead of clearing the ledger in bulk.
Same-key application is serialized across connection generations, and the catalog update and
watermark publication happen together after the application callback succeeds. The timestamp and
kind then remain recorded while the relay catalog retains a live entry or withdrawal tombstone for
that key. The watermark is removed by the same catalog lifecycle that forgets the key, so there is
no separate retention policy.
If those coalesced transitions fill the retained-data or key bound, their connection reader waits
for lane capacity, so a withdrawal is never dropped.
`RelayService.relayReceiveQueueSnapshot()` reports retained bytes, queued and active callbacks,
capacity-waiting service-state offers, active and retired peer lanes, and the configured per-peer
byte limit. Its `isQuiescent` value becomes true only after every retained payload, callback, and
capacity wait has finished.
Lanes belong to an exact connection generation. On disconnect or replacement, accepted coalesced
service-state entries transfer to the replacement lane with their recency intact, while ordinary
queued work is removed. Surviving entries keep their accepted arrival order across different keys.
A callback that already entered same-key application finishes before a newer replacement-generation
transition for that key can apply.
Callback failures,
including `Error` subclasses, appear as `RelayReceiveCallbackFailureWarningEffect`; its
`staleGeneration` field distinguishes retired-lane failures, which do not close a replacement
connection, from live-generation failures, which close the affected generation. An external
`RelayService.close()` waits for callback workers to finish after interruption. A callback worker
that calls `close()` waits for every other receive worker, then returns without waiting for its own
executor task, which finishes after the callback returns. A replacement worker waiting for that
callback's same-key application lock is interrupted during close, so it cannot block the join.
Remote registration-close observations use separate workers that `close()` interrupts but does not
join, so a public refresh callback can wait for a concurrent close without making each side wait for
the other.

Service withdrawals are authoritative relay traffic rather than best-effort gossip. A relay gives all backpressured observers one shared, bounded transient-backpressure interval when forwarding a withdrawal, and reports any delivery failure to its publication gate so the withdrawal remains eligible for retry instead of silently leaving stale routes behind. Withdrawals received from registered peers enter that gate before external fan-out, so one stalled observer cannot make fan-out failure escape another peer's message handler and close the healthy source registration stream. During explicit shutdown, the client keeps its relay listener alive until the relay acknowledges that it parsed and committed the unregister request. The relay attempts every service withdrawal in that committed generation even if an unrelated recipient rejects an earlier withdrawal.

Relay registration recovery is single-flight per client. If an immediate recovery pass and the
background reconnect loop overlap after a relay restart, they converge on one live registration
stream; an unchanged service snapshot is reused, while a changed snapshot is acknowledged over that
same stream. This prevents a competing recovery from displacing the listener that serves forwarded
requests. An accepted registration acknowledgement clears the preceding relay failure history
and restores the base recovery delay before its connected identity becomes visible. If that stream
closes while registration is still finishing, recovery uses that acknowledged relay at the base delay.

Each public registration replaces the recovery task and restores its base delay, including when the
registration is rejected. A reconnect that already started may still contribute to the same relay's
failure history until an accepted acknowledgement ends that history. Its older result cannot change
the new public registration's delay. Both rejected and thrown reconnect results follow this rule.

| Recovery state | Owner and terminal boundary | Observable behavior |
| --- | --- | --- |
| Registration intent | Public registration, candidate commit, or unregister replaces it; close is terminal. | An obsolete waiting worker cannot start or schedule a successor. |
| Same-relay failure history | An accepted acknowledgement ends the preceding failure generation. | Started failures remain counted across unacknowledged public registrations. |
| Recovery delay | The current public registration restores the base delay and owns later changes. | A rejected or thrown older result cannot double the replacement delay. |
| Alternative relay choice | The client commits its choice and failure reset together after the selector returns. | A selector that replaces or cancels the intent cannot restore the older choice. |
| Clock task | The client cancels its task on replacement, unregister, or close. | A failed current registration schedules one replacement task. |

Sequential requests to a relay-only target reuse an exclusively held relay request stream after its
complete response has been read. At most four clean request streams remain idle per relay; failures
and partly read responses close their stream, and closing the relay service drains the idle set.
Targets with a public direct address keep the direct/relay race and do not use this idle pool.

> **Note:** The high-level `UrlResolver` class has been moved to [`foundation.url:resolver`](https://github.com/CodexCoder21Organization/UrlResolver). Use UrlResolver for opening typed connections to services. UrlProtocol is for low-level stream-based communication.

## Building

```bash
./scripts/build.bash foundation.url.protocol.buildMaven
```

To build a fat JAR:

```bash
./scripts/build.bash foundation.url.protocol.buildFatJar
```

### Inbound RPC memory safety

Inbound JSON frames retain the protocol's independent 10,000,000-byte wire cap, and are
also admitted through a heap-scaled parse-memory budget before their body is allocated.
The budget conservatively charges seven bytes of transient parser footprint per wire byte;
an estimate that fills or exceeds the concurrency pool reserves it exclusively, serializing
large parses rather than rejecting a frame that is safe to parse alone. Frames beyond the
independent wire cap still fail with a descriptive `IOException` containing the actual frame,
estimate, cap, and concurrency-budget sizes. Admitted frames wait under backpressure and release
their reservation after parsing. A declared attachment size reserves future attachment capacity,
but bytes that have not arrived are not retained parse memory. While an attachment reservation is
open, another JSON frame may use its unused portion only after the attachment decoder pauses reads;
reads resume after the last JSON sublease is released. This lets independent JSON requests make
progress without allowing retained JSON and attachment bytes to exceed the shared cap.
A reader that already carries a deadline admits through `acquireParseBudgetByDeadline` instead, so
the wait for admission ends at that deadline rather than when the pool happens to drain. On expiry
the queued reservation is cancelled — it stops holding a queue position and stops reserving future
releases — and the call throws `ParseBudgetDeadlineExceededException` naming the frame size, the
worst-case parse estimate, the permits it asked for, and the total budget. Relay reads use this
form: `RelayStreamController.readMessage(timeout, unit)` applies its own deadline to admission just
as it does to byte reads, and reports a missed admission as `RelayParseBudgetDeadlineException`. A
missed admission consumes no body byte, and the reader keeps the frame's length prefix, so the next
read resumes the same frame rather than losing it. A clean remote close preserves complete frames
already buffered by either timed reader, including a frame whose prefix was retained after missed
admission. After the last complete frame, a read reports end-of-stream promptly. A local close
discards buffered frames. A reader failure makes every later timed read report that failure. A relay
controller also discards its buffered bytes on failure, while a `NettyStreamController`'s plain
`input` stream still drains bytes received before the failure and then reports end-of-stream.
Explicit local close also cancels a queued parse admission
without waiting for the read deadline, including after an earlier remote close.
Interruption during admission retains the prefix too, including when the interrupted call was
resuming an earlier admission miss. A remote close wakes a queued admission immediately when its
body is incomplete; a complete buffered body keeps its admission and is delivered by that same
call. Transport errors wake admission and remain visible to later timed reads.
Concurrent `readMessage` calls take turns owning complete frames, with each waiting caller using
its own deadline. In the original overloads, if a byte wait expires before consuming any body
bytes, the prefix remains resumable. If it abandons a partly consumed prefix or body, the stream becomes terminal instead
of interpreting the remaining bytes as a new frame.
The overload `acquireParseBudgetByDeadline(bytes, deadlineMs, clock)` uses the supplied Clock's
millisecond domain for the deadline. The caller owns that clock. Admission cancels its scheduled
wake on every exit, and a late wake cannot change permit ownership. An immediate grant reads time
once and submits no clock task; only a reservation that has to wait schedules a wake. Absolute
deadlines are compared before deriving a remaining interval, which saturates at `Long.MAX_VALUE`. The two-argument overload
continues to use wall-clock deadlines and a timed wait.
Both timed stream readers also accept a caller-owned Clock for their byte, frame-ownership and
admission waits. In the original overloads, a grant that wins an expiry race may finish an
already-buffered frame; the read deadline does not preempt JSON parsing, but interruption during
parsing withholds the parsed frame (see below).
Interruption of either timed reader follows one rule: once a call has consumed a frame's body
bytes, interrupting it ends the stream. A read interrupted after its final body copy or while
parsing returns null with the interrupted flag still set, never returns that frame, closes the
stream and releases the frame's parse reservation, so a later reader sees end-of-stream rather
than the frame that followed. Interruption also wins over a frame deadline reached at the same
final copy: the call returns null instead of reporting expiry. A complete length prefix is not a
consumed body: an interruption arriving with only the prefix read retains that prefix, as above.

For callers that poll within a longer operation, both readers also provide
`readMessage(idleTimeout, frameTimeout, unit, clock, operationDeadlineMs)`. The idle timeout
bounds ownership, first-byte waiting, and parse-memory admission while only a complete prefix
has been consumed; these states can resume after a poll expires. A partial prefix or any consumed
body byte instead uses the frame allowance, continuing past the idle boundary until completion
or frame expiry, which ends the stream and reports its progress.
A zero idle allowance polls already-buffered bytes without waiting; an expired absolute operation
deadline still prevents a frame from starting. The prefix allowance starts at its first byte;
the body allowance starts at its first byte, so waiting for admission does not shorten it.
An admitted read waiting for its first body byte has the same frame allowance measured from
admission: if the body has not arrived by that deadline, it ends the stream. Before that wait
begins, admission is checked separately: a grant returning after its poll deadline returns the
reservation, keeps the prefix, and reports an admission miss so the next read can resume.
An incomplete frame whose prefix allowance has already expired instead ends the stream with
its complete frame-expiry progress message, whether admission has not started, misses, or grants.
A complete buffered body retains the admission-resumption behavior described above.
A grant winning exactly at poll expiry may finish an already-buffered message while the operation
deadline remains live; JSON parsing and caller-supplied clock callbacks are not preempted.
An optional absolute operation deadline in the supplied clock's millisecond domain caps every
allowance. Admission-only expiry retains the prefix; a subsequent call starts a new poll capped
by that same operation deadline. These bounds do not promise an immutable message lifetime
across separate resumed calls. Expiry after partial prefix or body consumption reports the
declared length (or that it is not yet known), consumed bytes, frame allowance and operation
deadline. Existing overloads retain their grant-at-expiry and untouched-body resumption contracts.
The frame-budget overload checks its deadline again after the complete body copy. A body copied
across that deadline ends the stream with the same frame-expiry error before JSON parsing.

Candidate registration uses the remaining preparation allowance for its frame budget, with the
existing one-second idle poll capped by that operation's deadline. Its polls, frame allowance,
absolute deadline and cancellation timer all use `RelayService`'s application `clock`, matching
`prepareRelayCandidateRegistration`'s clock-measured total budget. That clock also continues to
govern reconnect checks and chunk lifetimes.

The registered listener uses a separate `listenerReadClock`, defaulting to `SystemClock`, for its
idle, frame and admission waits. An application clock jump does not expire its network read.
The constructor overload with required `listenerReadClock` lets embedders control that clock
independently; both clocks remain caller-owned, and the existing constructors keep their signatures.
The listener retains its 60-second allowance starting at the first prefix or body byte, independently
of its 60-second idle wait. A listener has no finite overall lifetime. Initial registration keeps its
10-second acknowledgement deadline; ping keeps its five-second read allowance. Ordinary relay
responses and each request/response chunk read keep the caller-supplied allowance (30 seconds by
default). These limits bound waiting; they do not preempt JSON parsing or caller Clock callbacks.
`Libp2pRpcProtocol.parseMemoryBudgetSnapshot()` reports current and peak reservations, acquisition
and contention counts, queued pool reservations, ordinary-pool available bytes, and deadline
expiry counts with the last expired frame's declared wire length (null before the first expiry).
Each admission miss increments the expiry count once. Registered listeners emit
`RelayParseBudgetDeadlineWarningEffect` for every missed poll and keep their registration active;
candidate preparation likewise keeps polling until its own operation deadline. A warning handler
that throws does not end the listener (the failure is printed by the effects runtime as an
unhandled notification rather than delivered to the same handler again), while a blocking handler
holds up that listener's reads until it returns. A listener interrupted during warning delivery,
or whose handler restores the interrupted flag before failing, keeps its interrupted flag and
exits; `RelayService.close()` completes while a handler blocks.
The parse-memory byte limit reported by the snapshot includes the ordinary parse
pool and the bounded companion-frame allowance described below; `MAX_CONCURRENT_PARSE_BYTES`
remains the ordinary pool's capacity.
Accounted releases verify that their reservation was removed before returning permits to that queue,
so diagnostics cannot temporarily include both an old holder and the waiters that replace it.

The sequential stream reader reserves attachment capacity as each validated length becomes known.
Only one sequential attachment frame grows at a time; independent JSON frames can use the remaining
pool. Ordinary queued reservations allow at most eight fitting later admissions before waiting for
the older reservation to fit. Continuations of already admitted frames have priority so retained
bodies can finish and release their bytes; new attachment frames still take the fair frame turn.
A stalled or expired frame cancels its queued growth and releases both its reservation and frame
turn when its lease closes, even if closing the input does not wake the blocked read. A reader that
later continues cannot grow that closed lease, and its cleanup cannot release the turn a second time.
Turn waits are fair and interruptible, with no numerical bound on total queue time. A holder still
waiting for its initial eight-byte reservation has no progress watchdog yet: only capacity becoming
available or interruption ends that wait. Once admitted, the existing stall and absolute-deadline
guards also cover queued growth and free the turn without waiting for the holder's read to return.
Interrupting an admission wait cancels it; `TcpRpcStream.close()` interrupts its reader.
Callers supplying an arbitrary `InputStream` must interrupt a reader waiting for admission when
cancelling it: that interface provides no close notification, and peer EOF is observed only by a
read. Closing that input alone does not bound either a turn wait or an initial capacity wait.
Frames above the independent attachment aggregate limit are rejected before body allocation with
the declared total, aggregate limit, and pool size. A valid frame above the concurrency pool size
reserves the pool exclusively, preserving large transfers.

Completed chunked relay requests use a separate process-wide fair materialization budget.
`RelayService.relayRequestMaterializationSnapshot()` reports that budget's capacity, retained bytes,
and completed requests waiting for their turn without exposing scheduler or mutation operations.

### Awaited RPC response flow control

After an RPC handler completes, temporary connection backpressure does not discard its response or
close the substream. Computed responses wait in connection-scoped outboxes through a transient
stall; if a root connection remains non-writable with buffered output for the documented ten-second
grace, the server first replaces every buffered computed response with its pre-reserved
`OUTBOX_FULL` frame, then closes the affected substreams and retires that root. The same terminal
frame is sent before a child close or a failed first-chunk admission discards a computed response,
so a waiting caller receives a definite delivery-failure result instead of bare end-of-stream.
When UrlProtocol closes a still-writable root with a completed
RPC response queued, it first replaces that response with a framed `RESPONSE_DELIVERY_ENDED` error
naming the same request. If the transport ends before any response frame completes and no frame can
still be written, the server emits one `RpcResponseDeliveryLossEffect` and one structured
`[RpcResponseDeliveryLoss]` stderr record containing the request ID, method, service, child stream,
root generation, close initiator, cause, and completed-frame byte count. The client does not replay
the request in either case. After that close completes, a later stream request excludes the retired
connection from peer connection selection and opens a fresh transport connection.
Transport adapters that initiate a protocol-owned RPC root close must use `closeProtocolRoot()`:

```kotlin
import foundation.url.protocol.closeProtocolRoot
import io.netty.channel.Channel

fun retireRpcConnection(root: Channel) = root.closeProtocolRoot()
```

The returned `ChannelFuture` reports the first protocol close's result, including the same failure
object when it fails. Repeated callers, completion callbacks, concurrent callers, and calls queued
during or after teardown share that result; only the first caller starts a physical close. This
also holds with no pending RPC responses, with the protocol's pipeline handler removed, and after
the root's event loop terminates, whether the first result is pending or complete. Outbound handlers may
forward the physical close with a different promise without starting another protocol close. The
optional promise argument must be a pending, non-void promise for that root channel. A supplied
promise becomes uncancellable once accepted and retains its own listener executor; callers that need callbacks after transport shutdown
must supply an independent executor. The default caller promise uses the root event loop.
The first caller claims the close before submitting work to the event loop; later callers do not
submit another task, and a claim is never re-claimed: every claimed close ends in exactly one
physical close attempt, or in one terminal result delivered to every caller, whatever the event
loop's state. If the root's live event loop rejects the submission because its task queue is full,
the close stays pending and is offered to the loop again at the
100 ms reconciliation interval described below until the loop accepts it; callers are
not failed by a busy loop. If the loop is shutting down, or accepts the task and then terminates
without running it, the loop's termination completes the close on a dedicated per-root daemon
thread: queued responses cannot receive a terminal frame and each gets one delivery-loss report,
and a root the transport already closed completes successfully without another close attempt.
Otherwise one close is attempted from that thread; if it fails, every caller receives an
`IOException` naming the root, with the attempt's failure as its cause.
An admitted response whose write is in flight when the close is claimed gets exactly one outcome,
decided by that write's own terminal result: a write that succeeds is not reported lost.
If response
preparation or a delivery-loss notification handler throws, cleanup and physical close still run,
and the physical close promise and all protocol callers receive the first preparation exception.
Any distinct later preparation failure is suppressed on that exception, except that a fatal JVM
error (`VirtualMachineError`, such as `OutOfMemoryError` or `StackOverflowError`, or
`LinkageError`) becomes the primary result, with the earlier exception suppressed on it. After the
close bookkeeping has run and every caller is settled, the fatal error is rethrown to the thread
that ran preparation (the `closeProtocolRoot()` caller when it called on the root's event loop); a
fatal error from submitting the close is rethrown to the `closeProtocolRoot()` caller after the
claim has been protected. Failures from response preparation and its pending-write barriers are
recorded before physical close starts. A failure that arrives after the result has been selected
is written to stderr as a `[ProtocolRootCloseLateFailure]` record and is never added to the
exception callers already received. Notifications from independent transport teardown can arrive
after the result has been selected; they are not guaranteed to change a successful close, and
cannot change an already-completed caller promise.
Delivery-loss notification handlers run on the root's event loop during close preparation, or on
the root's dedicated daemon thread when the close runs without that loop. A handler that blocks
stalls that root's close until it returns, and on the event loop also every other channel on that
loop; callers stay pending, not failed, while it blocks. A fatal JVM error rethrown from a task on
the event loop is logged by Netty rather than propagated; it remains the close's primary result.
Promise completion and notification callbacks run outside the response outbox monitor.
Callbacks on a supplied response-write promise observe its outbox accounting already released,
so a callback can admit another response using the completed write's capacity.
A pending response write stops holding up protocol close when its child or root closes, or either
channel's event loop terminates. The outbox releases that write's accounting and observes terminal
changes to the promise it supplied independently of the child executor, including when a live
event loop's task queue is full. This covers handlers that preserve that promise and Netty's
automatic executor handoff. A handler that replaces or aggregates promises must propagate the
terminal result to the supplied promise without relying on a listener task that can be rejected.
Arbitrary promise replacement is outside this completion guarantee: ordinary `PromiseNotifier`
forwarding and the multi-output `MessageToMessageEncoder`/`PromiseCombiner` path can lose their
cascade when the live executor rejects its notification. Their downstream promises can finish
while the original promise and protocol-close callers remain pending. A pipeline-head observer
cannot recover a result completed by a retaining handler before reaching the head; a buffer wrapper
cannot observe a separate promise's terminal state, and an encoder can replace the buffer entirely.
A handler that drops a message without completing the supplied promise also leaves the write
pending while its channels remain live.
Pipeline listeners registered on a handler's executor retain that executor; registrations from an
unrelated worker use the channel event loop. Outbox completion does not move downstream handlers'
listeners to the thread completing a write. Child/root death is
still observed when a close-future notification is rejected or lifecycle handlers are removed.
Automatic stalled-root retirement observes these same write lifetimes before initiating its root
close. An outbound handler that retained the write still owns its
buffer and physical write promise; it must release that buffer. Writes on live channels continue to
keep protocol close pending until they finish.
Child streams keep their separate stream-close contract.

`Libp2pHostFactory.createServerHost` and `createServerHostWithRelayHandler` accept a
`reconciliationClock`, for example
`Libp2pHostFactory.createServerHost(requestHandler = handler, reconciliationClock = clock)`.
The host installs this clock on each physical root before relay or direct protocols can create
its outbox, so protocol initialization order does not select the clock. The default is `SystemClock`.
For hosts assembled directly with the libp2p DSL, the existing
`UnifiedRpcProtocolBinding(handler, reconciliationClock = clock)` constructor supplies a default
only when the root has no clock installed; it cannot replace an existing root outbox's clock.
Pending response writes share one reconciliation timer per root, which checks every 100 ms while a write is pending. The clock callback
runs on the clock's thread (for the default `SystemClock`, one timer thread shared by the process)
and only inspects completion and channel lifetime; it never expires a write on a live channel.
When a write needs completing, it hands that work, including any physical close and caller
listeners that follow, to the root's event loop, or to the root's dedicated daemon thread once
that loop has stopped running tasks, so a blocking caller listener never stalls the clock thread.
Reconciliation failures are written to stderr as `[AwaitedResponseReconciliationFailure]` records.
A root registers one listener on its close future and one on its event loop's termination future,
not one per pending write, and removes the latter when the root closes; that removal is linear in
the number of roots sharing the event loop, once per root. Netty notifies loop termination on its
single process-wide `GlobalEventExecutor` thread; that listener only hands the reconciliation pass,
and everything it completes, to the root's daemon thread, so a blocking loss handler or caller
listener cannot stall termination notifications for other roots. A protocol close whose pending
write completes only after the loop stopped closes the root from that daemon thread as well, with
the same result as a close claimed after termination.

Raw third-party Netty closes can be intercepted only while the outbox handler is installed. An
idle root keeps the third party's existing close policy. Once a protocol close has started,
raw closes continue as independent transport operations. In
particular, `UrlProtocol.close()` delegates to `Libp2pNetworkProvider.close()` → libp2p
`HostImpl.stop()` → `NetworkImpl.close()` → `Connection.close()` →
`P2PChannelOverNetty.close()` → `Channel.close()`. These libp2p-owned shutdown calls do not use
`closeProtocolRoot()` and cannot promise the retained result after handler removal. Direct
`Connection.close()` calls have the same limitation.

Admission-control retirement is also a transport-level close, excluded from the routed protocol
close contract. After the last admitted stream closes, its path is
`InboundSubstreamAdmissionControl.visit()` → the stream's `closeFuture()` callback →
`releaseReservation()` → `retireConnection()` → `Connection.close()` →
`P2PChannelOverNetty.close()` → `Channel.close()`. Admission retains its own retirement and
close-failure policy. When that transport close physically retires a root, with or without the optional
interceptor still installed, it does not wait for or replace an already-retained protocol result: later
`closeProtocolRoot()` callers still receive the first protocol result, including the identical
failure object. The transport close's own result is outside that guarantee.

Root retirement initiated by the response outbox uses `closeProtocolRoot()`;
`NettyStreamController.close()` and relay-controller close operate on child streams, not the
shared root.
Before invoking a request handler, the server reserves the exact, request-scoped `OUTBOX_FULL`
frame; if that bounded reservation is unavailable, request admission pauses and the handler does
not execute until a completion signal can be guaranteed. Normal and small-priority responses use a
4 MiB per-connection pool, with the priority sublane capped at 1 MiB; the separate failure lane is
capped at 1.5 MiB per connection. Writable roots also share the documented 8 MiB normal/priority
and 3 MiB failure process-wide pools. When a root becomes non-writable, its queued entries release
those process-wide charges and remain subject to their per-connection bounds, so a stalled peer
cannot block healthy roots while its finite retirement grace runs. If the computed response cannot
enter its lane, the pre-reserved `OUTBOX_FULL` result is queued instead, stating that the handler
completed and the request was not replayed.

Drain scheduling round-robins across the three lanes and, within each lane, across writable mux
substreams. A continuously replenished small-response or failure lane therefore cannot starve a
large normal response, and one busy substream cannot monopolize its lane. Each event-loop
invocation drains at most 32 entries before rescheduling so response recovery yields to unrelated
connection work.

Diagnostic outbox and writability-wait callbacks run only after every ownership scope on their
calling thread has returned: the outbox monitor, per-stream framing locks, capacity/charge gates,
and writer-owned large-response turns and parked-write permits. One exception-isolated reporter
handles these callbacks. Thrown nonfatal observer or reporting failures do not interrupt the drain
or bypass buffer and capacity cleanup. The reporter renders messages and stack traces inside its
own boundary; if rendering throws nonfatally, it writes a fixed record naming the exception
classes. If that sink also throws nonfatally, the root channel's String attribute
`foundation.url.protocol.observerReportingFailure` retains the latest complete fixed record,
replacing the previous record without more rendering or sink calls; later notifications continue.
`VirtualMachineError`, `ThreadDeath`, and `LinkageError` propagate after ownership handoff or
release, without further diagnostic rendering or dispatch of the scope's remaining notifications.
A fatal `DRAINED` callback ends its current task while already queued siblings retain a separate
drain owner. If the event loop rejects that sibling submission because its task queue is full,
the rejected scheduling claim is released and an accepted event-loop continuation tries the
ordinary scheduling claim after the current task exits. If that continuation is also rejected,
protocol close releases the queued responses and sends `RESPONSE_DELIVERY_ENDED` where a terminal
frame can still be written; otherwise the caller observes connection closure and delivery loss
is reported. The original fatal object still propagates; debug logging records a rejected sibling
submission by its exception class and message. Neither recovery path invokes observers while
holding the outbox monitor, a framing lock, or a writer permit.
`ADMITTED:*` and `DRAINED:*` have **no guaranteed arrival order**, even for the same entry.
The submitting thread reports admission after scheduling the drain and leaving its ownership
scopes; the drain worker reports `DRAINED:*` after attaching the completion listener and handing
the buffer to the transport (or completing synchronous write-failure cleanup), outside its own
scopes. Consumers must count events rather than infer per-entry order from arrival.
Writability callbacks likewise report a wait after writer ownership returns. Tests that need to
observe or interrupt a live wait use implementation-owned final passive records with read/await
access; callers cannot supply the signaling method or attach a callback to the private signal.

The raw-TCP optimized bytecode path identity-accounts the arrays retained by completed response jobs
from job creation through delivery, refusal, or connection teardown. This includes a complete job
waiting for shared writer capacity. One array allocation is recorded once while any response job
refers to it, whether the provider keeps, replaces, or releases its own reference. Concurrent
responses sharing one implementation JAR therefore do not multiply its recorded size, while fresh
arrays remain fully recorded until their last response releases them. The public snapshot reports
both all retained response bytes and the subset admitted to writer queues and charged against the
allowances. One process-wide lock serializes both sets of attachment reference counts, allowance
totals, and reported peaks across every connection; the lock is never held during socket IO.

An upgraded 1.1 client advertises support for interleaved large-response frames in a private
top-level request field. Only the literal JSON Boolean `true` enables the capability; an absent
field, `false`, `null`, strings, and numbers use the legacy writer. For that client, a response
larger than 1 MiB is a compact start frame followed by complete attachment-chunk frames of at most
256 KiB. The server retains the fair
per-connection large-response turn for the sequence, but releases the substream write lock at every
complete frame boundary and schedules the small-response outbox before the next chunk. A computed
small reply can therefore complete while the unrelated large response is still transferring,
without placing any response bytes inside another frame's declared attachment body. The receiver
holds one bounded reassembly lease and leaves a 1 MiB compact-frame lane for continuation frames.
An admitted assembly's continuations do not consume the bypass allowance for new memory readers;
a queued whole-pool reader can wait for an assembly, but cannot prevent its remaining chunks from
being admitted. New assemblies still use the ordinary bounded fairness rule.

Ordinary JSON replies retain the existing 10,000,000-byte wire limit while another response is
being assembled. Across the process, one companion frame at a time may use additional capacity
for its combined JSON estimate and attachment bytes. The extra allowance is bounded by
`MAX_JSON_FRAME_BYTES * PARSE_AMPLIFICATION + MAX_ATTACHMENT_AGGREGATE_BYTES - 1 MiB`;
the existing ordinary parse pool and assembly limits do not change. Actual extra bytes are charged
before allocation and included in `parseMemoryBudgetSnapshot()`, and released on delivery or close.
The frame's JSON and all attachment destinations share one accounting boundary. This preserves
valid ordinary envelopes without letting their JSON and binary storage each reuse the same lease. Interleaving is selected only when the fully serialized
start, including its four-byte frame prefix and escaped response envelope, fits that 1 MiB lane and
both JSON bodies pass the receiver's structural checks. Larger JSON envelopes use the legacy
writer, avoiding a multi-megabyte start before the first schedulable attachment chunk. A terminal
`OUTBOX_FULL` response releases any partial
assembly before it completes the request. Direct-stream response admission never waits on the
reader that must consume an earlier response's chunks: it reserves the combined destination-byte sum and response JSON parse budget
before parsing or allocation, returns a terminal `INTERNAL_ERROR` with the required and available byte counts
when that reservation cannot fit, and consumes the rejected transfer's later chunks without
retaining their payload. Explicitly closing the direct stream, or reaching a request timeout,
releases every partial assembly and active companion-frame reservation before waiting for the
transport reader to finish. Interrupting one request caller instead removes only that request's
pending entry, releases only its partial assembly and leases, and retains bounded discard state
for its later chunks. The stream keeps serving other callers while that discard state fits. Each
stream retains at most 64 abandoned-response records and 1 MiB of their bookkeeping. If another
interrupted request cannot install its record within either bound, the stream closes explicitly
with the complete bound error as its terminal result. The interrupted caller keeps its selected
interruption or send failure and carries the cleanup error as a suppressed failure; pending and
later callers receive that same terminal bound error. Buffered frames read after this terminal
transition are ignored. `interleavedResponseStateSnapshot()` reports the active assembly count,
abandoned-response count, and retained bookkeeping bytes for operational accounting.
This request-local cleanup is serialized with start-frame admission, so a concurrent start is
either admitted and immediately abandoned or recorded for discard before admission. Start-frame
attachment lengths must be exact JSON integers within the per-attachment limit; fractional and
out-of-range values are rejected without numeric truncation.

Older 1.1 clients do not advertise this capability, so the server keeps the legacy atomic frame:
the full header-and-chunk sequence holds the substream write lock, the drain skips that substream's
in-flight marker, and deferred responses run after the frame ends. Framed request, push, effect and
controller writers take framing ownership before large-write ordering. Independently committed
interleaved chunks do not register a multipart-order marker, so a push holding the framing lock
cannot wait on a chunk that needs the same lock. This compatibility path keeps
the established 1.1 wire bytes and frame-integrity rule unchanged across mixed-version peers.

### Closed writes before admission

`StreamClosedBeforeWriteException` is an `IOException` proving that the stream closed before
any bytes from that particular write were admitted. The message and `streamDescription` identify
the stream. Netty controller outputs and in-memory stream outputs report this type at their
closed-before-admission boundary. A write that already admitted a prefix retains an ordinary
`IOException`; a successful earlier write is never covered by the later exception's guarantee.
Callers can safely replay a request only if the rejected operation contained the complete request
and no prior operation admitted part of it. A prior zero-byte probe does not reserve the stream.
In-memory RPC responses retain their detailed write failure message and this exception type;
their cause chain also retains the output exception and its write diagnostic.

### Transport failure attribution

A request that loses its response to a stream ending returns `Stream closed`, and a request whose
write fails returns `Failed to send request: …`. Those messages are unchanged, and they name no
connection — which makes a recurring loss impossible to attribute when several peers serve the same
service and relays carry some of those connections.

Each failed request therefore also emits `RpcTransportFailureEffect`, carrying the service
identifier, the destination `remotePeerId`, the `relayPeerId` that carried the connection (null for
a direct one), the failing request ID, and the underlying transport cause. `RpcStream.relayPeerId`
exposes the same relay hop for callers that want it directly; `Libp2pRpcStream` derives it from the
`/p2p-circuit/` segment of the multiaddress it was dialed at, which `Libp2pNetworkProvider.dial`
supplies.

The effect is emitted from the requesting thread, so a caller's `handler { … }` receives it — the
stream's reader is a daemon thread that cannot reach caller-installed handlers. It is also written
to standard error, so the report survives a caller that installed no handler. Exactly one effect is
emitted per failed request: a request that receives its response emits nothing, an orderly close
with nothing in flight emits nothing, and a request cancelled by a local `close()` is not attributed
to the peer — neither one whose response was still in flight nor one whose write was interrupted by
that close.

### Connection close records

Every host built by `Libp2pHostFactory` records why each of its root connections closed. When a
connection's channel closes, the host writes one line to standard error and tosses
`ConnectionClosedEffect` to the effect scope that built the host:

```
[ConnectionClosed] Connection connection@1b2c3d closed: initiator=REMOTE_END_OF_STREAM; direction=inbound; localAddress=/ip4/10.0.0.5/tcp/35000; remoteAddress=/ip4/10.0.0.9/tcp/51422; remotePeerId=12D3KooW...; closedBy=none; cause=none
```

`initiator` is one of `ConnectionCloseInitiator`:

- `LOCAL_CLOSE` — code in this process asked the channel to close. `closedBy` names the first
  calling method outside Netty and the libp2p channel wrapper only when the close was requested on
  the channel's own event loop. A close requested from any other thread (a worker thread, a
  `CompletableFuture` callback, most application code) is queued by Netty, so its record says
  `closedBy=unknown`.
- `LOCAL_EVENT_LOOP_SHUTDOWN` — this process shut down the event loop that owned the channel.
- `TRANSPORT_ERROR` — a read or write failed with an I/O error first, such as a connection reset
  by the peer; `cause` names it, and `closedBy` names a handler that closed in reaction, if any.
  `cause` only sees exceptions that reach the head of the root channel's pipeline (transport read
  failures, exceptions fired from the head, failed write promises); an exception raised inside
  another handler travels towards the tail and is not recorded.
- `REMOTE_END_OF_STREAM` — nothing local closed the channel and no I/O failure was seen, so the
  peer (or a hop between the two peers) ended the stream.
- `CLOSED_BEFORE_OBSERVATION` — the channel had already closed when the connection was handed to
  the recorder.

`direction` is `outbound` for a connection this host dialled. The identity `connection@<hex>`
matches the identity in the admission records below and in admission error messages, so both ends
of one close can be lined up: the closing side records `LOCAL_CLOSE` or `TRANSPORT_ERROR`, and the
other side records how the close reached it. Only root connections are recorded, once each; no
payload bytes, keys or per-message events are logged.

Inbound admission also records its own decisions to close or refuse, with the same delivery (a
stderr line plus an effect to the scope that constructed the `InboundSubstreamAdmissionControl`):

- `[InboundAdmissionRetirement]` / `InboundSubstreamAdmissionRetirementEffect`, written once for
  each close attempt of an accepted root, after that close has completed or failed: the retirement reasons (`aggregate-cap-refusal`,
  `per-connection-overflow`, `read-failure`), the `InboundAdmissionRetirementTrigger`, the remote
  peer and address, the live substream counts on the connection and across the host, and the
  read failure's cause when there is one.
- `[InboundAdmissionRefusal]` / `InboundSubstreamRefusedEffect`, written for the first refused
  (reset) inbound substream on each root only, with the refusal reason (`aggregate-cap`,
  `per-connection-cap`, `connection-retiring`, `connection-closed`) and the live counts. Later
  refusals on that root are counted by `rejectedCount()` but not written individually. It is
  written after the refused substream has been reset and after any close that refusal started.

Every record is produced only after the close or reset it describes, so a failure while building,
writing or delivering it cannot prevent or hold up that action. Such a failure is still reported:
for the admission records through the root channel's exception path, as admission's other cleanup
failures are, and for `[ConnectionClosed]` through the thread's uncaught-exception handler, since
the channel is already closed. A fatal JVM error from an admission record is rethrown once the
reset and close are done. Delivery to a handler holds the monitor of the effect scope that built
the host, as admission's other effects already do, and every host built in that scope shares it.
Handlers for these effects must return promptly: a close that has already happened stays
completed, but a blocked handler (or a blocked standard-error stream) stalls the thread delivering
the record, usually a Netty event loop, and every later record delivery in that scope waits behind
it.

## Usage

> **Note:** For high-level typed connections, use [`UrlResolver`](https://github.com/CodexCoder21Organization/UrlResolver) from `foundation.url:resolver`. The examples below show the low-level `UrlProtocol` API for raw stream communication.

### Peer registry add provenance

`PeerRegistry.addPeer(peer)` remains the direct application API and records `CALLER` origin. Code
that feeds a registry from another source can use the additive overload with
`PeerRegistryAddOrigin`. UrlProtocol marks its own service and peer catalogs as `CATALOG`, peer and
LAN exchange as `DISCOVERY`, relay paths as `RELAY`, and restored records as `PERSISTENCE`.

`getPeerOriginState(peerId)` returns the current retained lifetime's latest accepted origin and a
monotonic `hasCallerOrigin` bit. A later network refresh changes the latest origin but never clears
caller authorship. That bit is persisted; on restart the latest origin becomes `PERSISTENCE` while
the prior caller-authorship fact is retained. Removal clears the state for that lifetime.

Peer-file writes are coordinated with the exact retained lifetime. Removal waits for a write that
already started before deleting its file, while a write that starts after removal skips the stale
lifetime. This applies both to accepted additions and to `saveAll()` snapshots, so a completed
removal cannot reappear after restart.

### Low-Level API (UrlProtocol)

### Selecting a Network Provider

`UrlProtocol` uses `Libp2pNetworkProvider` by default, preserving the existing TCP, Noise,
multiplexer, relay, and peer-identity behavior. Applications that need to control the provider
instance can pass it explicitly:

```kotlin
import foundation.url.protocol.Libp2pNetworkProvider
import foundation.url.protocol.UrlProtocol

val network = Libp2pNetworkProvider(keySeed = "stable-node-identity")
val protocol = UrlProtocol(network = network)

// UrlProtocol owns the supplied provider and closes it when the protocol is closed.
protocol.close()
```

`UrlProtocol.close()` is terminal and idempotent: it rejects new stream opens and service sends. A dial
that finishes after close is closed without being returned to its caller. External callers
wait for transport cleanup and all active service send attempts, with the same cleanup failure
reported to ordinary closers. A send issued after terminal close is rejected before transport.
An already-running send may still finish and return its result. A service send fails with
`Cannot send service RPC request to '<url>' method '<method>': UrlProtocol is closed.` in exactly two
cases, decided from the protocol's closed state and the typed transport failure, never from message text:
it is rejected at an admission check because close had begun (no cause), including network startup
before dialing, or an attempt ends with a failure that would otherwise replace the stream (a `REQUEST_WRITE` or `CONNECTION_CLOSED`
`RpcTransportFailure`, or an exception that left the stream closed) and close has begun when the
protocol decides not to send again. In that second case the cause is the transport failure's cause or
the thrown exception. This rule covers both the initial and replacement attempts. Direct
`openStream()` admission still reports `Cannot open stream: UrlProtocol is closed.`. An exception that
leaves the stream open propagates unchanged, and a service error or another transport failure is
reported as it is. A caller's own interruption keeps the same exception or RPC error and interrupt
flag on either attempt; it is never converted to the close failure or retried.
A send that calls `close()` excludes itself from the drain, and a sending
caller joining an existing close waits only for cleanup so concurrent senders cannot wait on each other.
Nested close calls from the cleanup owner, an owned stream cleanup callback, or a relay receive callback
being joined return before cleanup finishes and do not observe its final failure. External closers still wait for that callback
and the remaining cleanup and sends. If a relay callback initiates close, teardown can interrupt
that same callback while it is still running. After that self-close detaches the relay service,
a repeated close cannot join the callback's remaining work.
Frame admission is terminal too: closing a stream releases queued senders with a stream-closed
failure before they enter the supplied writer. When a libp2p child stream ends because its transport
failed, those senders instead fail with `Stream closed: transport failed: <message>` whose cause is
that transport failure, the same failure timed readers report. The interrupt a close uses to
release a waiting sender is consumed before that sender's stream-closed failure is thrown, so the
sender's thread is not left interrupted. `RpcStream.output` on the TCP and libp2p streams is a
wrapper: each call is admitted as one frame write, like `sendRequest`, and closing it closes the
stream. Synchronizing on the returned output
object does not exclude `sendRequest` frames; write a whole frame in one call instead. A compatibility controller's output getter is
captured once before admission, and its getter, writes, and flushes can call protocol close.
Controller lookup uses identity without calling the controller's `hashCode` or `equals`.
Raw complete frames and segmented RPC frames share one writer at a time, so their bytes cannot
interleave. Waiting sends retain their attachment references without making complete frame copies.
An admitted writer still has to finish or unwind before an external protocol close finishes draining it.
Service stream acquisition and provider startup also release their state monitors before supplied
getters, dialing, listening, registration, or cleanup. Close releases callers waiting for acquisition
before it drains their active outer sends.
A stream handle obtained from `UrlProtocol` ends its ownership once, through either `close()` or
`releaseAfterForwarding()`. Concurrent callers join that cleanup, and completed handles are removed
from protocol ownership. A forwarding release preserves the response's separate transfer lifetime;
the receiving writer or response owner finishes or closes that response. Automatic protocol cleanup
joins an in-progress release without cancelling its response. An explicit `close()` on the released
handle still cancels the live response, with concurrent callers sharing that cancellation's result.
An explicit close after a failed release also attempts that one cancellation in case the response
remains live. The original release failure is thrown, with a distinct cancellation failure attached
as suppressed, so callers can identify why the release failed and whether cancellation also failed.
If the release callback calls `close()` on its own handle, that close returns to the callback and
the release caller completes the requested cancellation before returning. This applies when the
release succeeds or fails, and uses the same failure order.
Concurrent closers share this result. Releasing after close does not repeat cleanup.

Close runs every cleanup step, then throws the first cleanup failure with later failures attached
as suppressed exceptions exactly once. If an owned
stream's cleanup callback initiates protocol close and then fails, external protocol closers wait for
that callback and receive its failure too. A stream cleanup that completed before protocol close
continues to report its failure only to its own caller.

Alternative network implementations implement `NetworkProvider`, whose type-neutral API covers
identity derivation, listening, timed dialing of an `RpcStream`, inbound protocol handlers, and peer
connection lifecycle events. The interface deliberately exposes no `io.libp2p.*` types, but its
string values are provider-interpreted rather than universal: identities and addresses are opaque to
`UrlProtocol`; `Libp2pNetworkProvider` interprets them as base58 peer IDs and libp2p multiaddresses.
Some existing `UrlProtocol` routing filters remain explicitly libp2p-multiaddress-specific while the
addressing model is migrated incrementally. Relay service and LAN discovery require
`Libp2pNetworkProvider` and fail loudly when enabled with an incompatible provider.

#### Installing a direct libp2p RPC binding

Advanced callers that install `UnifiedRpcProtocolBinding` into their own libp2p `Host` must attach
the binding to the host lifecycle and use the returned host for startup and shutdown. This gives
PeerExchange requests one aggregate admission budget: each parsed request carries a conservative,
heap-scaled retained-byte charge across the existing 64 running and 64 pending count limits. A
request that cannot fit the byte or count budget is refused with a warning and its stream is
closed. The lifecycle wrapper also makes host shutdown wait for admitted request work:

```kotlin
val binding = UnifiedRpcProtocolBinding(requestHandler, gossipHandler)
val rawHost = buildHostWith(binding) // your libp2p Host builder
val host = binding.withHostLifecycle(rawHost)
host.start()
// ...
host.stop()
```

The underlying libp2p `Host` API does not expose a protocol-lifecycle callback, so stopping the
unwrapped `rawHost` cannot drain the binding's PeerExchange work.

#### In-memory network provider

`InMemoryNetworkFabric` runs any number of `UrlProtocol` nodes inside one JVM without opening real
sockets. Each `InMemoryNetworkProvider` derives a stable, non-cryptographic peer ID from its seed.
Addresses are opaque `memory://` strings understood by the fabric. Every stream direction has a
bounded byte buffer (4 KiB by default), so writes block under backpressure and fail at the
clock-driven write deadline instead of accumulating an unbounded payload. Dials blocked by a
non-dialable target or fabric partition likewise fail at their caller-supplied, clock-driven
deadline with the source peer, target peer, address, protocol, and timeout in the error.

Closed streams return their empty backing arrays to a fabric-local pool for later streams. The
pool retains at most 256 arrays, so the default fabric keeps at most 1 MiB of reusable pipe storage
while sequential request/response traffic avoids allocating two new 4 KiB arrays per stream.
`pipeBufferAllocationCount` reports how many backing arrays the fabric has actually allocated.

```kotlin
import community.kotlin.clocks.simple.ManualClock
import foundation.url.protocol.InMemoryNetworkFabric
import foundation.url.protocol.InMemoryNetworkProvider
import foundation.url.protocol.LanDiscoveryConfig
import foundation.url.protocol.Libp2pPeer
import foundation.url.protocol.RelayConfig
import foundation.url.protocol.UrlProtocol

val clock = ManualClock(1_000L)
val fabric = InMemoryNetworkFabric(clock = clock, bufferCapacityBytes = 4 * 1024)
val providerA = InMemoryNetworkProvider(fabric, keySeed = "node-a")
val providerB = InMemoryNetworkProvider(fabric, keySeed = "node-b")
val relay = RelayConfig(enableRelay = false)
val lan = LanDiscoveryConfig(enabled = false)
val nodeA = UrlProtocol(providerA, relay, lan, clock)
val nodeB = UrlProtocol(providerB, relay, lan, clock)

val addressA = nodeA.startNetwork()
val addressB = nodeB.startNetwork()
nodeA.addBootstrapPeer(Libp2pPeer.remote(addressB.peerId, addressB.listenAddresses))
nodeB.addBootstrapPeer(Libp2pPeer.remote(addressA.peerId, addressA.listenAddresses))

nodeA.announceService("example.service")
fabric.runUntilIdle()
check(nodeB.findPeersForService("example.service").single().peerId == addressA.peerId)

nodeB.close()
nodeA.close()
fabric.close()
```

Test harnesses can call `stallReader(nodeId)`, `slowReader(nodeId, bytesPerTick)`,
`resumeReader(nodeId)`, `kill(nodeId)`, `partition(nodeA, nodeB)`, `heal(nodeA, nodeB)`,
`setDialable(nodeId, false)`, `addAddressAlias(nodeId, address)`, and
`setAddressDialable(nodeId, address, false)` to reproduce slow consumers, abrupt loss, network
splits, whole-peer dial failure, and one stale address on a multi-address peer. Inbound handlers are
created through a configurable thread factory; hermetic failure-path tests can call
`configureInboundHandlerThreadFactory` before the first dial to make worker startup fail at an exact
launch. A failed worker start commits no connection, handler sequence, or success counter.
Successful inbound handlers are launched in deterministic FIFO order. The handler launch and stream
open become visible in one locked state change, while the virtual worker body begins asynchronously.
Inbound handlers cooperatively hand off the fabric turn when blocked, allowing a healthy reader to
drain frames larger than one bounded pipe while the writer remains backpressured. `runUntilIdle()` single-flights concurrent drains and waits for all
scheduled handlers and lifecycle callbacks; advance the injected `ManualClock` to release
slow-reader ticks and write deadlines. Closing either `RpcStream` endpoint (including its input or
output view) immediately makes both endpoint views unusable while preserving already-buffered bytes
for graceful input drain.

Impaired scenarios can use `drainReadyWork()` instead of polling. It runs all work that is ready at
the current injected-clock time and returns either `FabricDrainResult.Idle` or
`FabricDrainResult.WaitingForClock(nextDeadlineMillis)`, so the caller can advance a `ManualClock`
exactly to the next fabric-owned dial, write, or slow-reader deadline. `snapshot()` returns an
immutable `InMemoryNetworkSnapshot` built from maintained counters: node states, active and peak
streams, current buffered bytes, accepted bytes and opens by protocol/node/directed link, dial and
handler totals, the peak pending-handler count, and current pending callback/handler counts.
Snapshot reads do not run callbacks, inspect payloads, drain buffers, or advance time.

### Opening an RPC Stream
            path: String,
            params: Map<String, Any?>,
            metadata: Map<String, String>
        ): Any? {
            return when (path) {
                "status" -> mapOf("online" to true)
                "data" -> fetchData(params["id"] as? String)
                else -> null
            }
        }
    }
)

// Later, to unregister:
registration.unregister()
```

### Low-Level API (UrlProtocol)

### Opening an RPC Stream

> **Note:** The examples below show explicit peer IDs and multiaddresses for educational purposes. In practice, you almost never need to specify these — just use the default constructor and provide the `url://` URL. The protocol handles peer discovery automatically.

```kotlin
import foundation.url.protocol.*

// Recommended: Use default bootstrap peers (no peer IDs or multiaddresses needed)
val protocol = UrlProtocol()
val stream = protocol.openStream("url://my.service/")

// Advanced: Create protocol with custom bootstrap peers (rarely needed)
val bootstrapPeers = listOf(
    Libp2pPeer.remote(
        peerId = "QmBootstrapPeerId",
        multiaddresses = listOf("/ip4/192.168.1.1/tcp/4001/p2p/QmBootstrapPeerId"),
        advertisedServices = listOf("my.service")
    )
)
val protocol = UrlProtocol(bootstrapPeers)

// Open a raw RPC stream
val stream = protocol.openStream("url://my.service/")

// Send RPC request
val request = Libp2pRpcProtocol.RpcRequest(
    id = Libp2pRpcProtocol.nextRequestId(),
    method = "myMethod",
    params = mapOf("key" to "value")
)
val response = stream.sendRequest(request)

// Handle response
if (response.error != null) {
    println("Error: ${response.error.code} - ${response.error.message}")
} else {
    println("Result: ${response.result}")
}

// Clean up
stream.close()
protocol.close()
```

#### Opening a Stream to One Exact Peer

Code that already resolved a concrete provider can bypass service discovery and dial only that
peer's advertised addresses:

```kotlin
val stream = protocol.openStreamToPeer(
    peerId = provider.peerId,
    addresses = provider.multiaddresses,
    serviceIdentifier = "my.service",
    resourcePath = "status",
    connectionTimeoutMs = 5_000
)
```

The addresses are raced within one overall connection budget. A stale first address therefore does
not receive its own full timeout before another supplied address is attempted, and a failed call
names the requested peer, address list, method path, and budget. Reconnect code should call the same
API again with its explicit budget; this method never falls back to service discovery.

### Direct Stream I/O

Streams opened with the default settings use an automatic response reader. Send requests with
`sendRequest` so that reader can match each reply to its request:

```kotlin
val stream = protocol.openStream("url://my.service/")

// Create the request
val request = Libp2pRpcProtocol.RpcRequest(
    id = Libp2pRpcProtocol.nextRequestId(),
    method = "lowLevelMethod",
    params = emptyMap()
)
// Send the request and receive its reply through the automatic reader
val response = stream.sendRequest(request)

stream.close()
```

For caller-owned direct reads, see ["Choosing who reads replies"](https://github.com/CodexCoder21Organization/UrlProtocol/blob/c5edef610b9b75dde8733d9864dbab816516544a/README.md#choosing-who-reads-replies) in the reader ownership update.

Applications that share a memory budget between UrlProtocol and other components can pass an
`RpcStreamRetainedResourceScope` when they construct a `Libp2pRpcStream`. The scope returns one
`AutoCloseable` reservation for each retained interleaved response and compact frame. UrlProtocol
closes those reservations during normal completion or stream shutdown, after it has attempted to
release its own process-wide reservation. A reservation close failure is reported through the
stream's normal cleanup path without skipping the remaining reservations.

Applications that need separate accounting domains for independent stream groups can construct an
`RpcStreamMemoryBudgets` and pass it to each group's `Libp2pRpcStream` instances. Omitting that
parameter preserves the default process-wide shared frame and interleaved-response budget.

#### Request and Response Metadata

Both `RpcRequest` and `RpcResponse` carry an optional, additive `metadata: Map<String, String>` — a flat, generic string map for piggybacking out-of-band information alongside the method parameters or result without changing their shape:

```kotlin
// A server stamps extra information onto its response without touching the result.
val response = Libp2pRpcProtocol.RpcResponse
    .success(request.id, mapOf("value" to 42))
    .copy(metadata = mapOf("clock-timestamp" to "nodeA@42"))

// The client reads it back after deserialization.
val stamp = Libp2pRpcProtocol.RpcResponse.fromJson(responseJson).metadata["clock-timestamp"]
```

The channel is fully backward compatible:

- **Omitted when empty (`RpcResponse` only).** `RpcResponse.toJson()` writes the `"metadata"` field only when the map is non-empty, so the wire form of a response with no metadata is byte-identical to the pre-metadata format. (`RpcRequest.toJson()` differs: it always emits a `"metadata"` object, even an empty `{}`.)
- **Absence tolerated.** `fromJson()` / `fromJsonRaw()` decode a missing `"metadata"` field to an empty map, so a new reader parses an old writer's response, and an old reader simply ignores the unknown field on a new writer's response — no protocol-version negotiation is required.
- **Preserved across relays.** A relay carries the response as an opaque payload inside its `RELAY_RESPONSE` envelope, so metadata survives multi-hop relay forwarding intact.

`UrlResolver` uses this response channel to transport HierarchicalClock information — a serving clock stamps `clock-timestamp` and ships coverage receipts as `clock-receipts` — but the field itself imposes no schema on the keys or values.

### Remote AiCliPty Quota Reporting

`RemoteAiCliPty` mirrors the AI CLI PTY quota API without depending on the upstream
`aiCliPtyApi` module. Call `quotaStatus()` to fetch a `RemoteAiCliQuotaStatus`
containing supported state, fetched timestamp, raw text or error details, and any
reported quota metrics. Metrics use `RemoteAiCliQuotaMetric` with a stable id,
display name, quota window, optional model, unit, total/used/remaining quantities,
and optional reset information.

Providers expose the same call through `AiCliPtyAdapter.quotaStatus()`. Adapters
that do not implement quota reporting remain source-compatible and return
`supported = false` with a descriptive error message. The remote client tolerates
older or newer wire payloads: missing or JSON-null fields decode to null/defaults,
unknown quota window names decode to `RemoteAiCliQuotaWindow.UNKNOWN`, and closed
or failing remote connections return an unsupported status instead of throwing.

### Peer Management

```kotlin
val protocol = UrlProtocol()

// Add peers manually (optional - default bootstrap peers are added automatically)
protocol.addBootstrapPeer(peer)

// Find peers for a specific service (peer discovery happens automatically)
val peers = protocol.findPeersForService("my.service")

// Get peer count
println("Known peers: ${protocol.peerCount}")
```

Peer reputation is computed from bounded observation records rather than elapsed-time
windows. Each peer retains at most 64 checks, 64 direct/relay reach observations,
64 authenticated interaction severities, and 64 deduplicated recommendations.
Idle time does not change a score.

```kotlin
val observations = PeerObservationLog()
observations.observePeer("12D3KooW...")
observations.recordSuccess("12D3KooW...")
observations.recordDirectReachability("12D3KooW...")
observations.recordAuthenticatedInteraction(
    "12D3KooW...",
    PeerInteractionSeverity.CLEAN
)

val scores = observations.scoreAllComponents()
val peerScore = scores.getValue("12D3KooW...")
println("bootstrap=${peerScore.bootstrapScore}, ostracism=${peerScore.ostracismScore}")
```

`bootstrapScore` favors witnessed tenure and direct reachability.
`ostracismScore` favors reliability and recommendation quality. Both multiply by
the recoverable spam factor. Failed checks are omitted entirely while this node
cannot confirm its own connectivity, and there are no score or calendar thresholds
that permanently remove a peer.

Health checks use `5 minutes × 2^min(consecutiveFailures, 10)` with a random
`0.8..1.2` jitter applied before the six-hour cap. Tests can inject a
deterministic `jitterFactor` when constructing `PeerPruner`.

#### Learned addresses, dial failures, and quarantine

Multiaddresses that arrive from PeerExchange, `PeerAnnouncement`, or
`ServiceAnnouncement` are third-party assertions, and every address the registry
retains later becomes an outbound dial target. `PeerRegistry.addPeer` therefore
drops addresses that can never identify a reachable TCP peer — a `tcp` port that
is not a number or cannot exist, IPv4 `0.0.0.0/8`, `169.254.0.0/16`, `224.0.0.0/4`,
`240.0.0.0/4`, IPv6 `::` and `ff00::/8`, and multiaddresses the transport cannot
parse. Relay addresses containing more than one actual `/p2p-circuit/` protocol component are
also rejected with a `PeerMultiaddressRejectedWarningEffect` that names the address. Protocol
values and opaque paths containing the text `p2p-circuit` do not count as circuit components.
The same check runs before relay-owned gossip fan-out and cached-announcement replay. A peer whose
every advertised address is rejected is not retained at all.
Loopback and private ranges are accepted: co-located mesh processes and peers on
a shared private network legitimately use them.

Callers report dial outcomes so a departed host stops being dialed:

```kotlin
val registry = PeerRegistry.inMemory()

try {
    // ... dial the peer ...
    registry.recordDialSuccess(peerId)
} catch (failure: Exception) {
    // Evicts and quarantines the peer once PeerRegistry.MAX_CONSECUTIVE_DIAL_FAILURES
    // consecutive failures accumulate with no intervening success.
    val evicted = registry.recordDialFailure(peerId)
}

println("quarantined peers: ${registry.quarantinedPeerCount}")
```

The registry retains at most `PeerRegistry.MAX_QUARANTINED_PEERS` quarantine entries. If peer
identity churn exceeds that bound within the 15-minute window, it discards the oldest quarantine
entries first while continuing to quarantine the most recent failures.

An evicted peer is refused re-entry for `PeerRegistry.DIAL_FAILURE_QUARANTINE_MS`
however often the rest of the mesh re-advertises it, and `isQuarantined` reports
whether that window is still open. Without the quarantine, the next gossip message
restores the peer within seconds and the eviction removes no dials at all. A
recovered host rejoins on its own when the window lapses.

#### Outbound dial bound

Every outbound dial holds a socket until it connects or the kernel abandons the
unanswered SYN, so dialing is bounded process-wide at
`Libp2pNetworkProvider.MAX_CONCURRENT_OUTBOUND_DIALS` across all provider
instances. A dial that cannot be admitted within its own timeout budget fails with
`OutboundDialAdmissionException`, which best-effort callers such as gossip fan-out
handle like any other dial failure. `Libp2pNetworkProvider.pendingOutboundDialCount()`
reports how many dials currently hold a permit; a value pinned at the bound means
dials are being issued faster than they complete.

> **Note:** Peer discovery happens automatically in the background. When you call
> `openStream()` or `findPeersForService()`, the protocol will automatically join the
> network and wait for peer discovery to complete if it hasn't already.

### LAN Peer Discovery

`UrlProtocol` enables zero-config LAN discovery by default. Each node announces its peer
ID and listen multiaddresses on qualifying local interfaces, then connects to discovered
peers through the normal identity-pinned libp2p dial path. Service lists are not included
in LAN beacons; existing peer exchange and gossip carry service information after the
first connection.

```kotlin
// Default: LAN discovery enabled.
val protocol = UrlProtocol()

// Opt out, or confine discovery to selected interfaces/CIDR ranges.
val localOnly = UrlProtocol(
    lanDiscoveryConfig = LanDiscoveryConfig(
        enabled = true,
        mdnsEnabled = true,
        interfaceAllowlist = setOf("lo"),
        addressCidrsAllowlist = setOf("127.0.0.0/8")
    )
)

val noLanDiscovery = UrlProtocol(
    lanDiscoveryConfig = LanDiscoveryConfig(enabled = false)
)
```

`LanDiscoveryConfig` also exposes the service tag, announce/query interval, multicast UDP
port, multicast group, interface/address allowlists and denylists, and dial-abuse guards
for beacon-triggered connections. Set `mdnsEnabled = false` to keep the project-local UDP
beacon path while disabling mDNS binding; this is useful for hermetic tests that use
per-test UDP ports and must avoid cross-talk with host mDNS on port 5353. Discovery
startup is best-effort: if multicast or mDNS cannot start on a host/interface, `UrlProtocol`
continues without LAN discovery.

### Hierarchical Name Verification

Service gossip is treated as a reachability hint. `UrlProtocol` can also verify
service ownership through signed hierarchical name descriptors before routing to
an announcing peer. Existing namespaces remain free-to-claim by default for
backward compatibility; verified zones opt in by providing a signed TLD
descriptor and child delegation descriptors.

Rollout is intentionally an islands-of-trust model. If a resolver has not yet
seen a valid root-signed descriptor for a TLD, that TLD is treated as
free-to-claim so legacy services continue to work. Once a resolver sees a valid
`VERIFIED` TLD descriptor, it pins that TLD in memory and, when `UrlProtocol` is
created with a peer persistence directory, persists the pin in that same
directory. A pinned verified TLD cannot later downgrade to absent or
`FREE_TO_CLAIM`; it can only be replaced by a root-signed descriptor with a
strictly higher signed version. Operators that need to close the
pre-propagation window for reserved names should ship those descriptors through
`SignedDelegationResolver(hardCodedPinnedTldDescriptors = ...)` so the TLD is
verified before gossip arrives.

Names are authorized in their canonical spelling only. A canonical identifier is
a dot-separated series of segments that are non-empty, at most 63 characters, and
lowercase, with no whitespace and no empty segment. An identifier that names a
known TLD but is spelled non-canonically — `secure..service`, `SECURE.service`,
or `secure .service` — is rejected rather than normalized into `secure.service`,
and is rejected rather than being treated as naming some other, unknown TLD that
would be free to claim. Identifiers under a TLD that has no descriptor stay
free-to-claim whatever their spelling, so legacy names are unaffected.

```kotlin
import foundation.url.protocol.*

val rootKey = HierarchicalNameKeys.keyPair("local-root")
val tldKey = HierarchicalNameKeys.keyPair("local-secure-zone")
val providerPeerId = UrlProtocol.peerIdFromSeed("provider")

val resolver = SignedDelegationResolver(
    rootPublicKey = rootKey.publicKeyBase64,
    tldDescriptors = listOf(
        SignedTldDescriptor.create(
            tld = "secure",
            mode = NameDelegationMode.VERIFIED,
            childAuthorityPublicKeys = listOf(tldKey.publicKeyBase64),
            signer = rootKey
        )
    ),
    delegationDescriptors = listOf(
        SignedNameDelegationDescriptor.create(
            parentName = "secure",
            childSegment = "service",
            mode = NameDelegationMode.VERIFIED,
            authorizedPeerIds = listOf(providerPeerId),
            signer = tldKey
        )
    )
)

val protocol = UrlProtocol(
    nameResolutionConfig = NameResolutionConfig(
        rootPublicKey = rootKey.publicKeyBase64,
        resolver = resolver
    )
)
```

TLD resolver descriptors can be distributed through gossip with
`GossipProtocol.TldResolverAnnouncement`. A node verifies each TLD descriptor
against its configured root public key before storing it; descriptors that fail
verification are dropped and are not returned by `onTldResolverQuery()` for
re-propagation.

### Peer Persistence

```kotlin
// Create with persistence directory
val protocol = UrlProtocol(peersDirectory = "/path/to/peers")

// Peers are automatically loaded on construction
// and saved when calling savePeers()
protocol.savePeers()
```

Persistence version 2 keeps each peer header, bounded score observations,
direct-reachability timestamp, and registry discovery timestamp in that peer's
`<peer-id>.json` file. Updates are written to a temporary file in the same
directory and atomically renamed over the previous record.

On the first startup over version 1 data, `PeerRegistry` folds
`observation-log.json`, `direct-reachability.json`, and `first-seen-at.json`
into the matching per-peer files, removes the old shared files, and then writes
`migration-v2-complete`. Failed cleanup is retried on the next startup, so the
migration is idempotent. A malformed peer record is
reported through `PeerRegistry.getPersistenceFailures()` as a
`PeerPersistenceException` and emitted as a `PeerPersistenceWarningEffect`
without preventing valid sibling records from loading. Write failures throw
`PeerPersistenceException` to the caller.

### Peer Registry Capacity

`PeerRegistry` retains at most 1,000 peers. When an insertion exceeds that
limit, it removes the final peer from the same score-and-address-diversity
ordering used for bootstrap selection. Tied-positive-score IPv4 populations
use incrementally maintained indexes for both repeated and distinct addresses,
so capacity churn does not repeatedly walk the whole registry. When a closed
batch has a population shape that needs the general ranking fallback, the
registry computes that ordering once and removes its lowest-ranked tail rather
than rebuilding the ordering once per excess peer. A newly created successful
observation uses one event timestamp for discovery and success, preventing
clock-sampling latency from manufacturing false score differences.

`getEvictionWorkDiagnostics()` returns cumulative candidate counts for fallback
eviction ranking, the temporary repeated-IPv4 fallback index, and peer-list
snapshot publication. `getFullSnapshotStagingMapCandidateCopies()` reports
temporary full-snapshot membership-map copies. These counters can be sampled
before and after a workload to check work without using elapsed time. Capacity
publication reuses the prior snapshot and its known unpublished additions rather
than building a temporary map of the full registry. Serial capacity replacement
also advances a snapshot with immutable list membership past the removed oldest peer and appends
the replacement into never-before-visible storage, so prior snapshots stay stable
without copying the retained registry for each replacement.
Peer objects in these lists keep their existing ownership: nested collections are not deep-copied.
Repeated `getAllPeers()` calls reuse the most recently published membership
snapshot until the registry changes.
A closed batch applies all pending removals, refreshes and additions in at most one
copy of the live membership, independent of the number of refreshed peers.
If a peer property throws during publication, the accepted membership changes and removal
callbacks still finish before the error reaches the caller; retained lists keep their prior membership.
Peer-exchange admission conservatively charges requested-ID hash entries for treeified
buckets as well as ordinary buckets, including JVMs with compressed object references disabled.

Each retained peer also has one stable `PeerLifetime` token, available through
`PeerRegistry.getPeerLifetime(peerId)`. Registry refreshes keep that token; any removal—including
direct removal, pruning, dial-failure eviction, or capacity eviction—ends it, and a later re-add gets
a higher generation. `PeerLifetime.runIfActive { ... }` is ordered against removal, while
`onRemoval { ... }` callbacks registered before removal begins run synchronously once before the
same peer ID can publish its next lifetime. A callback registered after removal begins runs
immediately on its registering thread and is not joined to the in-progress handoff; it may overlap
the captured callbacks or finish after a later lifetime is published. Together these operations
let consumers record and clean peer-scoped state without a remove/re-add check-then-write race for
callbacks registered while the lifetime is active. Removal callbacks run after the registry has
released its peer, capacity, publication, and dial-outcome locks. If captured callbacks throw,
every captured callback is still invoked and the failures are reported together. If persisted
cleanup or another operation for an earlier peer in the same removal batch throws a fatal error,
later peers' captured callbacks and persisted cleanup still finish before their handoffs release
re-adds. The original fatal failure remains primary, with callback, persistence-cleanup, and handoff
failures from the rest of the batch suppressed.

`PeerRegistry.removePeer(peerId, expectedLifetime)` removes the peer only when the supplied token
is still that peer ID's current lifetime. The comparison and removal are atomic with other
same-peer registry mutations. It returns `true` after removal and the usual synchronous callback,
persistence, and membership-publication work complete; it returns `false` without changing state
when the peer is absent or has a different current lifetime. The existing unconditional
`removePeer(peerId)` operation is unchanged.

An active action must finish before it removes its own peer or adds a previously absent peer to the
registry; either same-thread operation throws `IllegalStateException` before changing registry
state because a new peer could evict the active peer at capacity. Calling `removePeer` for the
action's own peer is rejected before waiting on registry locks. Removal callbacks may make
bounded calls to the same registry, including operations on unrelated peers. If callback-context
work tries to add any peer whose prior removal callbacks are still unfinished, the add is rejected
immediately with `IllegalStateException` instead of waiting on a handoff the callback may be
responsible for finishing. A callback must not wait for work submitted to a pre-existing thread
pool that tries such a re-add, because pre-existing worker threads do not inherit the callback
context and ordinary non-callback callers intentionally wait for the ordered handoff.

A running action can read its peer, refresh an already published peer, remove a different retained
peer, or call `saveAll()` while another thread waits to remove the action's peer. While waiting for
an active action, the registry holds no peer stripe, capacity lock, publication gate, persistence
lock, or dial-outcome stripe. Removal waits first, then checks the exact lifetime again and commits
membership removal under the registry locks. Reads never return a token whose removal has already
published, or a retained peer without its current lifetime.

An action cannot refresh a peer that is retained but not yet in `getAllPeers()`: that peer's add is
still waiting for publication and may need this very action to finish an eviction. This operation
throws `IllegalStateException`, naming the peer and its retained-but-unpublished state, before
changing it. A refresh of an already published peer remains allowed and publishes in place before
returning, preserving snapshot position and the capacity bound. It does not wait for unrelated
pending additions. Each capacity publication captures its completed pending generations and exact
eviction victims, releases the publication gate before waiting for those lifetimes, and publishes
only the captured generations. A selected victim stays active if another removal already freed the
needed capacity. Later additions retain their own ordered publication obligation.

Concurrent `saveAll()` calls first check their lifetime before taking its persistence lock and
recheck active state without another lifetime wait while holding that lock. Removal joins previously
admitted writes after releasing its registry locks, then dispatches callbacks and deletes the peer
file. A late write cannot recreate a removed lifetime after restart.

A dial success from inside the exact active action that a threshold removal is waiting for returns
immediately. Its observation belongs to that pre-removal generation: it cannot cancel the decided
removal or quarantine, and removal clears the observation. An ordinary concurrent success waits for
the threshold membership removal without holding registry locks, then records the post-removal
outcome. The lifetime present after removal and the quarantine identity are captured at completion and
checked again when applying the success. A delayed outcome cannot clear a later generation's
quarantine or write its observations. Dial-removal
completion is signalled before callback dispatch, preserving bounded registry calls from callbacks.

### Local TCP Mode (localhost.tcp)

For container environments or local testing, you can bypass libp2p entirely by using the `localhost.tcp:PORT` domain pattern:

```kotlin
import foundation.url.protocol.*

// Client: Connect to a local TCP service
val protocol = UrlProtocol()
val stream = protocol.openStream("url://localhost.tcp:8080/")

val request = Libp2pRpcProtocol.RpcRequest(
    id = Libp2pRpcProtocol.nextRequestId(),
    method = "hello",
    params = emptyMap()
)
val response = stream.sendRequest(request)
println("Result: ${response.result}")

stream.close()
protocol.close()
```

```kotlin
// Server: Bind to a local TCP port
val protocol = UrlProtocol()

val binding = protocol.bind("url://localhost.tcp:8080/") { request, effectHandler ->
    when (request.method) {
        "hello" -> Libp2pRpcProtocol.RpcResponse.success(request.id, "Hello World")
        else -> Libp2pRpcProtocol.RpcResponse.error(
            request.id,
            Libp2pRpcProtocol.ERROR_UNKNOWN_METHOD,
            "Unknown method: ${request.method}"
        )
    }
}

// Server is now listening on port 8080
// When done:
binding.stop()
```

When a TCP connection ends, its `CloseAwareServiceClientConnection.closeCause` is published before
the transport interrupts request handlers owned by that connection. A blocked handler can therefore
record the connection close as the reason its work ended, while an unrelated caller-owned interrupt
remains distinguishable. `CloseAwareServiceClientConnection` is an optional capability, so code
must check the connection with `as?` before reading it. Close listeners run after handler
cancellation and are still notified exactly once; a slow listener cannot delay cancellation or
admission release, and a listener failure is reported without skipping later listeners.

Code that constructs `TcpServer` directly can pass port `0` to let the operating system choose an
ephemeral port without a probe-and-rebind gap. After `server.start()`, `server.localPort` reports
the actual bound port for clients to connect to.

Requests on a local TCP connection execute independently. Each handler runs on its own reusable
daemon platform thread from an elastic pool, so blocking on an external dependency — including
blocking while inside a `synchronized` section — does not occupy a shared virtual-thread scheduler
slot or prevent an unrelated handler from starting. Code that constructs `TcpServer` directly can
pass port `0`, call `start()`, and then read `localPort` to use the operating system's assigned port.
Advanced direct users can pass a `TcpServerSocketFactory` together with a
`TcpServerReaderThreadFactory` when they need a custom bound-server-socket or reader-thread creation
policy; the ordinary constructors keep the default `ServerSocket` and daemon reader threads.
If the socket factory calls `stop()` before returning, `start()` closes the returned socket without
publishing it or starting an accept thread.
The pool admits up to
`TcpServer.DEFAULT_CONCURRENT_HANDLER_LIMIT` handlers by default (256, leaving ample headroom above
the 65-or-more concurrent blocking handlers supported by the earlier contract); callers can set a
different `concurrentHandlerLimit` constructor value. Requests beyond the configured ceiling are not
queued: a request beyond it receives a `CONCURRENT_HANDLER_LIMIT` RPC error explaining
the port, configured limit, request ID, and method, and the server emits a
`TcpServerConcurrentHandlerLimitEffect` for consumers that want to record the refusal. Idle request
threads are reaped after 60 seconds, and stopping the binding interrupts outstanding request work.
Ending one client connection removes its queued requests before interrupting its running handlers,
because that client can no longer receive their results. Stopping the server applies that ordering
across all connections. A handler that does not respond to interruption continues to hold its slot
until its complete invocation exits, including work moved to another coroutine dispatcher. Connection
cancellation keeps the request worker servicing its own coroutine continuations until that work and
its cleanup finish. Only then is its slot returned. Blocking cleanup from separate requests therefore
continues independently on their respective request workers, including after returning from another
dispatcher. Plain blocking waits on a request worker are still interrupted when its connection ends,
and the worker's interrupt flag is cleared before reuse. The handler ceiling remains an exact bound.
`TcpServer.activeHandlerCount` is a read-only operational metric reporting occupied admission slots, including queued handlers and unfinished cancellation cleanup.

The ceiling counts handlers that are running, which is what the refusal reports when it says a
request "was not started". A handler's slot is freed once it returns and before its response is even
handed to the connection's writer thread, so a caller holding a response is guaranteed the slot that
served it is already free. A caller that keeps at most `concurrentHandlerLimit` requests outstanding
is therefore never refused for capacity, including when it issues its next request immediately on
receiving the previous response.

### Bounded response delivery

A handler never writes its response to a socket. It computes the response, frees its slot, hands the
frame to its connection's single writer thread and terminates, so a peer that pipelines requests
without reading its responses cannot make handlers accumulate. (Effect propagation is the exception:
`propagateRequestEffect` and `propagateNotificationEffect` write to the socket directly on the
handler's own thread, so a handler that emits an effect to a peer that has stopped reading blocks
there while still holding its slot. It occupies capacity, not extra threads.) The bounds are exact:

- **Platform threads:** one accept thread, one reader thread and one writer thread per connection,
  and at most `concurrentHandlerLimit` request-handler threads for the whole server. The handler pool
  enforces that ceiling as its `maximumPoolSize`; its queue exists only to absorb the moment between
  a handler finishing and its worker becoming available again, and never holds more than
  `concurrentHandlerLimit` entries because a queued task still holds its admission permit.
- **Undelivered response bytes:** 4 MiB per connection and 16 MiB across all connections in the
  process, plus a separate 1.5 MiB per-connection / 3 MiB process-wide allowance reserved for the
  errors below so a saturated connection can still answer. A response offered while its connection
  has nothing undelivered is admitted under a higher 32 MiB process-wide ceiling instead of being
  refused, because it is not a pileup: that covers both a peer that is simply keeping up and a single
  response legitimately larger than the whole per-connection allowance, such as a multi-megabyte
  bytecode JAR. Streaming bytecode responses are queued as their JSON header plus their existing
  attachment arrays and emitted segment by segment, so they are never aggregate-copied into a single
  frame.
- **Reading:** a connection's reader stops consuming that connection's requests while its own
  undelivered responses exceed 1 MiB — including a response that is waiting for the shared allowance
  below. The peer's receive window fills and its writes block, so a peer that stops reading throttles
  itself and no other connection.
- **Waiting for the shared allowance:** a response whose own connection holds nothing undelivered is
  not refused the moment the shared process-wide allowance is spoken for. An empty outbox is the
  server's own evidence that this peer consumed everything computed for it, so the response occupies
  the allowance only for as long as its write takes; several such peers routinely ask for more than
  the ceiling at one instant and for less than it a moment later. The offer waits up to five seconds
  for the connections ahead of it to return what they are delivering, and is refused only if they do
  not — which is what a peer that has stopped reading looks like, since its bytes stay charged until
  its connection is torn down. Every refusal a connection earns against its *own* allowance, and
  every refusal reply, is still returned immediately, so a stalled peer never makes a handler thread
  wait.

When a computed response does not fit those allowances the caller receives a `RESPONSE_OUTBOX_FULL`
RPC error stating that the handler ran to completion, that the response was discarded, and that the
request was not retried — deliberately not the `CONCURRENT_HANDLER_LIMIT` refusal, which says the
request "was not started". The error names which allowance was exceeded and the bytes observed when
it was: only the per-connection case means this caller stopped reading, and the process-wide cases
routinely refuse a caller that is reading perfectly because other connections consumed the shared
allowance. The server also emits a `TcpServerResponseOutboxFullEffect`, whose `refusal` carries the
same allowance and observed byte counts.
`TcpServer.responseOutboxSnapshot()` reports the bytes currently and peak retained, the allowances,
the read-pause mark, and how many responses have been answered this way.
Advanced delivery diagnostics can pass a `TcpServerResponseOutboxObserver` to the matching
`TcpServer` constructor overload. Its queued callback runs only after the response is writer-visible
and its positive byte accounting is complete; its released callback runs after delivery or teardown
has returned every charge. Callbacks run without the connection outbox monitor, so they may overlap
and a fast writer may report release before the queued callback starts. Consumers should use them for
aggregate lifecycle diagnostics rather than pairing concurrent responses by callback arrival order.

### Environment-Based Binding

Containers can use the `URL_BIND_DOMAIN` environment variable to control their binding:

```kotlin
// When URL_BIND_DOMAIN is set to "localhost.tcp:8080", binds to TCP port 8080
// When URL_BIND_DOMAIN is not set, uses the default domain "my.service"
val binding = protocol.bindWithEnvOverride("url://my.service/") { request, _ ->
    // Handle request...
    Libp2pRpcProtocol.RpcResponse.success(request.id, "Hello")
}
```

This allows the same code to:
- Run standalone with full P2P networking (default domain)
- Run in a container with local TCP binding (when `URL_BIND_DOMAIN=localhost.tcp:8080`)

### P2P Relay for NAT Traversal

For peers behind NAT (home routers, firewalls), the protocol supports connecting via a public P2P relay:

```kotlin
import foundation.url.protocol.*

// Create protocol with relay support
val protocol = UrlProtocol()

// Connect to a NAT-ed peer via relay
// The relay peer ID is: 12D3KooWQE54k2VQzbLqDZLmfoEZ8AyAxz2GoxCE2muSpWF5UNDN
// The relay address is: /ip4/198.199.106.165/tcp/4001/p2p/...
val stream = protocol.openStream("url://w3wallet.daemon.12D3KooWTargetPeerId/")

// Send request - automatically routed through relay if direct connection fails
val request = Libp2pRpcProtocol.RpcRequest(
    id = Libp2pRpcProtocol.nextRequestId(),
    method = "list_profiles",
    params = emptyMap()
)
val response = stream.sendRequest(request)
```

**Relay Protocol: `/urlresolver-relay/1.0.0`**

The relay protocol uses the following message types:
- `RELAY_REGISTER` - NAT-ed peer registers with the relay
- `RELAY_REQUEST` - Client sends request to target peer via relay
- `RELAY_RESPONSE` - Response from target peer via relay

NAT-ed services (like W3WalletDaemon) automatically register with the public relay on startup, allowing clients to reach them without requiring port forwarding.

Large `sendViaRelay` requests on a relay request stream are split into 128 KiB chunks. The sender
opens with up to two request chunks in flight, widens the window by one after each successful
acknowledgement up to the existing byte-derived cap, and consumes replies in stream order. Upload
time therefore does not include one full application-level round trip per chunk while the existing
bounded transport writes remain in use.

Relay operators can sample `RelayService.currentIncomingChunkAssemblyCount()` to monitor how many
incomplete incoming chunked requests are being assembled. Their raw chunks remain in temporary
file-backed storage rather than accumulating on the JVM heap, and `RelayConfig.chunkAssemblyTtlMs`
bounds their idle lifetime. Expiry and relay shutdown remove that temporary storage. The process
reserves one 128 KiB slot per declared chunk against a shared 1,610,612,736-byte temporary-storage
limit, so one maximum-size 12,288-chunk declaration fits and further declarations are refused until
storage is released. A deletion failure keeps its storage charged and is retried by the next
reservation, so the ledger never reports space that the filesystem still retains. If closing the
Okio `FileHandle` itself fails, Okio has already marked that handle closed and cannot safely retry
the close. The relay therefore keeps the path and its process-wide storage charge for the rest of
the process instead of deleting a file that may still be open. The initial failure and each later
cleanup attempt are exposed by `RelayService.relayWarningEffectsSnapshot()` as the latest
`RelayRequestTemporaryStorageCleanupWarningEffect`; the effect states the path, operation, attempt,
failure, and whether an earlier close already failed.

Embedders can provide `relayRequestFileSystem` and `relayRequestTemporaryDirectory` to
`RelayService`; production defaults to Okio's system filesystem and system temporary directory.
The existing five-parameter `RelayService` constructor and its Kotlin defaults remain available,
while the storage-injection overload requires both storage arguments. Per-transfer filesystem work
is serialized without holding the service-wide assembly-state lock, so a delayed file operation for
one transfer does not stop an unrelated transfer. `RelayService.close()` first stops new transfer
admission, then waits for an in-flight per-transfer filesystem operation to leave its gate before it
closes and removes that transfer. A transfer released after close observes the closed response and
does not reach the request handler. `RelayService.isClosed` becomes true at that initial permanent
close transition, before `close()` waits for in-flight work or releases resources. A completed
request is materialized for the existing handler contract only after every chunk arrives.
Materialization is admitted in FIFO order against a process-wide heap
budget of one half of the JVM maximum heap, with a 512 MiB ceiling; requests whose raw bytes plus
three times their Base64 size exceed that budget are refused. A chunk's Base64 text is refused
before decoding when it exceeds the exact 174,764-character ceiling for one 128 KiB chunk, while
the decoded-size check remains in place for payloads whose encoded length is within that ceiling.
`chunkSeq` and `totalChunks` must be JSON integer values within the signed `Int` range; omitted
fields retain the legacy defaults of zero and one. The separate
`outgoingChunkedResponseIdleTtlMs` setting bounds large responses awaiting chunk fetches and
refreshes only when a previously unserved chunk is delivered.
These lifetime values are preserved by `RelayConfig.copy()` and included in its equality and hash
code while remaining outside the legacy seven-argument constructor used by existing consumers.

Both directions of a chunked transfer between a requester and a relay are pipelined within a bounded
window rather than exchanged one chunk at a time. (The one-hop path a relay uses to push to a peer
already registered with it, `sendDirectlyToRegisteredPeer`, still exchanges one chunk at a time.)
`sendViaRelay` keeps several request-chunk frames in flight and issues one more for each interim
acknowledgement it reads, so an N-chunk transfer costs roughly `ceil(N / window)` relay round-trips
instead of N sequential ones. Sending a chunk and then blocking on its acknowledgement
multiplied every scheduling delay by the chunk count, which is what made a multi-megabyte upload over
a relay slow to a crawl on a busy machine while the same upload finished quickly on an idle one.

The request window is bounded in bytes rather than in frames, because a request chunk is a ~175 KB
frame while a response-chunk fetch is a few hundred bytes. In-flight request-chunk bytes stay at or
below the transport's 1 MiB write low-water mark, so a transfer never pushes its own channel into the
unwritable range where its next frame would fail admission outright. The window opens at two frames
and widens by one per acknowledgement, so senders that start together do not put a combined
opening burst on a relay's ingress; each paces itself to the capacity the path has demonstrated. Each
direction has its own connection-wide budget sized by its own byte footprint, so their sum respects
both the write watermark and the connection's parked-write permits. A transfer waits for a permit only
when it holds none of its own, so a transfer with frames in flight always keeps reading the
acknowledgements that release them.

A sender with several request chunks in flight identifies each reply by its own content rather than
by the order it arrives in, because nothing in the protocol guarantees that reply *i* answers chunk
*i*. Chunk assembly happens at the target, so a relay forwards every chunk onward and answers from an
asynchronous completion rather than from its per-stream critical section; multi-hop routes and older
relay versions widen that gap further. No reordering has been observed in practice, so this is
robustness against an ordering that was never promised rather than a fix for a seen interleaving.
Interim
acknowledgements carry `chunkAck` and an empty payload and are interchangeable; the target's response
is the one reply that is not an acknowledgement, and a transfer that produces a second such reply, or
none at all, is reported as a protocol error. Every reply is read before the call returns, so a
reused request connection never carries replies belonging to a finished transfer.

A successful `RelayRegisterAck` also means the relay has already recorded the registering peer's
direct contact in its `PeerObservationLog` and replaced that peer's registry membership and service
catalog with RELAY origin. Both changes complete before the acknowledgement is sent, so a client
that has been told its registration succeeded is immediately visible through the relay's peer
registry and is never treated as an unverified peer by peer-exchange sharing or any other observation
gate. Later messages, callbacks, withdrawals, and notifications remain ordered by the relay's
per-identity publication generations.

#### Refreshing an Existing Relay Registration

A client that starts advertising additional services after its relay connection is established can
replace the registration's service list without opening another connection. The asynchronous form
completes only after the relay has applied and acknowledged the replacement; the blocking form is a
compatibility wrapper around the same acknowledged operation:

```kotlin
val applied = relayService.refreshRelayRegistrationAsync(
    listOf("my.service", "my.second.service")
).get()

val appliedBlocking = relayService.refreshRelayRegistration(
    listOf("my.service", "my.second.service")
)
```

Both forms return `false` when there is no live relay registration or when the relay rejects the
replacement. The requested list becomes the desired relay catalog before connection inspection or
I/O; a successful ACK marks that exact revision committed, while any later reconnect sends the
newest desired revision even when the preceding refresh ACK was lost. If the registration stream
closes while a replacement is awaiting its ACK, that operation finishes from the close event; it
does not remain pending until the missing-ACK time budget expires.

A listener startup or read failure closes that listener's registration transport and clears its
selected relay and candidate state before pending refresh callbacks run. Those refreshes receive
the original listener failure, with any transport-close failure attached as cleanup detail. A fatal
`Error` still leaves the listener worker after cleanup; an older listener's failure preserves a
replacement registration.

#### Relay-cache admission and direct withdrawal recording

Use `RelayService.cacheServiceAnnouncement(serviceIdentifier, message)` for announcements learned
through direct gossip as well as relay connections. For the same retained service/provider, a
strictly older announcement cannot replace the newer cached JSON or message ID. This applies to
registered and unregistered providers; registered providers also retain their inventory timestamp
check. Equal announcement timestamps may refresh the payload, but a withdrawal wins an equal
timestamp. Provider timestamps are compared only within the same service/provider lifecycle.
The existing cache, inventory, and withdrawal expiry and capacity limits still bound retention.
Admission takes a detached snapshot before reading ordering fields. The cache owns immutable
ordering metadata and serialized replay JSON; changing the original input or any value returned
by `getCachedServiceAnnouncements()` (including nested JSON) cannot change admission or replay.
This costs one JSON copy per admission and one per returned announcement on each snapshot. That
cost is acceptable at these ownership boundaries: retention is bounded, and the copies let callers
use mutable JSON without sharing the cache's ordering state.

A consumer handling a direct withdrawal should record it before notifying its handlers:

```kotlin
relayService.recordServiceWithdrawal(
    withdrawal.serviceIdentifier,
    withdrawal.providerPeerId,
    withdrawal.timestamp
)
```

`recordServiceWithdrawal` monotonically records that timestamp and removes a matching old-or-equal
cache entry before returning. Later old-or-equal announcements are rejected while the withdrawal
is retained; a strictly newer announcement survives that withdrawal. The method invokes no
application handler on its calling thread, including for expired disconnected-provider cleanup,
whose publication runs on a separate worker. Announcement and withdrawal handlers, including
inventory-eviction handlers, run after every caller has released the relay's provider, registration,
inventory and cache locks. Together these guarantees allow direct withdrawal recording while the
consumer holds its own service publication stripe. Per-stream delivery and same-key receive
callbacks remain serialized.

`cacheServiceAnnouncement` may synchronously invoke an inventory-eviction withdrawal handler.
Call it after releasing application locks that the handler may acquire. Its atomic timestamp
comparison preserves cache order if an older write was delayed across a newer announcement or a
recorded withdrawal. `removeCachedServiceAnnouncement` remains a callback-free removal-only
operation: it records no withdrawal timestamp and cannot by itself reject a delayed cache copy.

Explicit `unregisterFromRelay()` captures the acknowledged registration on its relay stream.
A relay that supports generation-specific unregister keeps a later registration acknowledged on
that same stream, including when an older unregister write arrives afterward. Refresh ACKs may
arrive out of order without changing which registration a later unregister captures. This behavior
requires both the client and relay to contain the generation-specific unregister implementation;
older relays retain the original sender-only removal behavior. If the captured response path ends
while unregister awaits its ACK, that wait ends from stream departure. A live admission failure,
a negative ACK, and caller interruption remain visible to the caller.

#### Observing Disconnected-Peer Cleanup

A relay emits `RelayDisconnectedPeerCleanupEffect` after it has finished removing a disconnected
peer's stream-owned registration and cached announcement state. Each announcement accepted
through a relay stream is tagged with that stream's generation, so cleanup removes entries written
by the closing stream even when a newer stream from the same peer is already the current
registration; the newer stream's registration and generation-owned entries are kept. Direct cache
writes that did not come through a relay stream are not attributed to a stream close. The effect
carries the peer ID and `cachedAnnouncementRemoved`, which is `true` when cleanup removed at least
one cached service announcement owned by the closing stream. This lets operators and embedding
services observe registration reaping that was previously silent.

Install the specific handler before starting the relay so the service can carry that effect scope
to its asynchronous disconnect-cleanup workers:

```kotlin
import foundation.url.protocol.RelayDisconnectedPeerCleanupEffect
import kotlinx.algebraiceffects.Effective

Effective {
    handler { effect: RelayDisconnectedPeerCleanupEffect ->
        println(
            "Relay cleaned up ${effect.peerId}; " +
                "cached announcement removed: ${effect.cachedAnnouncementRemoved}"
        )
    }

    relayService.start()
}
```

`RelayService` does not handle or suppress this effect. A caller can handle the dedicated type at
the application boundary according to its own logging, metrics, or lifecycle policy.

#### Preparing Relay Candidates Before Selection

A caller that needs to compare several relays can prepare their registrations concurrently without
publishing any of them as the selected relay:

```kotlin
val first = relayService.prepareRelayCandidateRegistration(
    relayPeerId = firstRelayPeerId,
    budgetMs = 10_000,
    services = listOf("my.service"),
    handler = ::handleRelayedRequest
)
val second = relayService.prepareRelayCandidateRegistration(
    relayPeerId = secondRelayPeerId,
    budgetMs = 10_000,
    services = listOf("my.service"),
    handler = ::handleRelayedRequest
)

val acknowledgedFirst = first.acknowledgement.get()
val acknowledgedSecond = second.acknowledgement.get()
val firstWon = relayService.commitRelayCandidateRegistration(acknowledgedFirst)
val loser = if (firstWon) acknowledgedSecond else acknowledgedFirst
relayService.cancelRelayCandidateRegistration(loser).get()
```

`prepareRelayCandidateRegistration` returns immediately and performs the bounded dial,
registration, and acknowledgement wait on a per-service worker pool. Preparation registers only
the candidate connection's liveness; its service catalog is not sent until commit, so an
acknowledged loser cannot advertise a route without a listener. An acknowledged handle does not
change `currentRelayPeerId`. `commitRelayCandidateRegistration` atomically installs exactly one
acknowledged handle, starts its listener, and publishes that winner's service catalog over the
selected stream. It returns `true` only after the relay acknowledges that catalog; a late, losing,
or rejected commit returns `false` and releases the failed handle for cleanup.
`cancelRelayCandidateRegistration` changes the losing handle to `CANCELED` immediately and returns
a future for its asynchronous stream cleanup. After acknowledgement, an uncommitted handle remains
live for one additional preparation-budget interval and then changes to `FAILED`, closes its stream
asynchronously, and releases its admission slot. A handle that is neither committed nor needed
should still be canceled promptly rather than retained until that bound. After
`unregisterFromRelay`, the same `RelayService` can run another candidate selection lifecycle.

The original blocking `registerWithRelay` API is unchanged. Use it when the relay is already
selected and candidate comparison is not needed.

### Server-Initiated Push to a Connected Client

A registered service normally only *replies* to requests. When a service needs to send **unsolicited** frames back to one specific connected client over its persistent RPC connection — for example live-projection deltas, or any long-lived subscription — it implements `ConnectionAwareServiceHandler` instead of `ServiceHandler`. The four-argument `handleRequest` additionally receives a `ServiceClientConnection`: a **durable, connection-scoped** channel to that exact client. Capture it during one request (e.g. a subscribe) and use it later:

```kotlin
import foundation.url.protocol.*
import org.json.JSONObject

class MySubscriptionService : ConnectionAwareServiceHandler {
    override suspend fun handleRequest(
        path: String,
        params: Map<String, Any?>,
        metadata: Map<String, String>,
        connection: ServiceClientConnection
    ): Any? {
        if (path == "subscribe") {
            // Reap the subscription the moment this client's connection dies —
            // no polling heartbeat needed (fires once, on graceful close OR abrupt reset).
            connection.onClose { subscriptions.remove(connection.connectionId) }
            subscriptions[connection.connectionId] = connection
            return mapOf("subscribed" to true)
        }
        return null
    }
}

// Later, when new data is available, push an unsolicited frame to that client.
// The frame's "type" must be one the client registered an inbound handler for.
try {
    connection.push(JSONObject().put("type", "my_delta").put("value", 42))
} catch (e: ServicePushException) {
    // The push FAILS LOUDLY (never silently drops) when the connection is closed,
    // reset, or unwritable — so a connection-scoped lease can reap on failure.
    subscriptions.remove(connection.connectionId)
}
```

Key properties:

- **Backward compatible.** Existing three-argument `ServiceHandler`s are unchanged and never receive a connection; server-initiated frames only ever flow after a `ConnectionAwareServiceHandler` explicitly calls `push`.
- **Authenticated peer identity when available.** `ServiceClientConnection.remotePeerId` is the authenticated libp2p remote peer id for libp2p-backed connections, taken from the secure stream identity rather than request metadata. It is stable across reconnects from the same client keypair. It is `null` for `localhost.tcp` and detached/in-process calls, which have no cryptographic peer identity; code that falls back to `connectionId` in those cases should treat that fallback as reconnect-unstable.
- **Validated type.** The pushed frame must carry a non-empty custom `type` that is not one of the transport's reserved types (`response`, `error`, `ping`, `pong`, the `stream_*`/`effect_*`/`observable_*` families — see `Libp2pRpcProtocol.RESERVED_MESSAGE_TYPES`). A missing/empty or reserved type is a caller programming error and throws `IllegalArgumentException` before anything is written, so a push can never spoof an in-flight RPC response or control frame at the client.
- **Loud failure, always bounded.** `push` throws `ServicePushException` when the connection is closed/reset/unwritable, rather than silently dropping the frame. The deadline is per transport but a push never blocks forever: on a **libp2p** connection the frame goes over the same backpressure-gated path as an awaited RPC response and is reported dropped if the connection stays unwritable through the delivery window; on a **`localhost.tcp`** connection the blocking socket write (which has no OS send timeout) is bounded by a watchdog that closes the socket after the same delivery window, so a client that stops reading cannot park the write forever.
- **Direct connections only.** Server-initiated push requires a direct connection (or a transport-level circuit-relay connection) to the client. A service reached through the *app-level* relay sees the relay-bound connection, not the true client's: the relay forwards a request and correlates exactly one response, with no unsolicited-frame path back to the original source, so pushes on such a connection will not reach the true client.
- **Connection-scoped lifecycle.** `onClose` fires exactly once when the connection dies (graceful close or abrupt disconnect); a listener registered after the connection is already dead fires immediately. Request cancellation never waits for these callbacks. Registered listeners run on a dedicated dispatcher rather than the transport's I/O or teardown thread, so a slow listener cannot stall other connections or transport cleanup; listeners should still be fast, and should be registered once per subscription (each call adds a listener). TCP connections also implement the optional `CloseAwareServiceClientConnection`, whose final `closeCause` is published before their request handlers are interrupted. `connectionId` is unique per live connection, so a sender captured before a client reconnects fails loudly on the old connection and can never write onto the new one.
- **Admission order.** Real TCP and libp2p service connections implement the optional `AdmissionOrderedServiceClientConnection`. Its positive `admissionOrder` is assigned when the RPC transport is admitted, before asynchronous request work, and remains unchanged after close. All built-in transports in the same protocol classloader share this order; it does not compare processes or restarts. Inbound `NetworkProvider` streams expose `AdmissionOrderedRpcStream` before their callback is queued, so a server adapter carries that value into its service connection. A custom transport can use `nextServiceConnectionAdmissionOrder()` once at admission. Missing capability means unknown order: consumers must not infer age from first handler execution or let an unknown-order connection replace a different existing owner based on that observation. Existing interfaces, constructors, and wire frames remain compatible. All handles for one admitted connection preserve that same positive ordinal, which identifies its lifetime as well as its order. The legacy transport constructor remains binary compatible and reports zero for unknown order.
- **Optional transport retirement.** Real TCP and libp2p service connections also implement `DisconnectableServiceClientConnection`. A connection-aware proxy can check for this subtype and call `disconnect()` when its downstream connection dies. The outside client then observes normal transport loss and can reconnect instead of remaining attached to a connection that cannot deliver more updates. This is an optional local API with no new frame type: existing `ServiceClientConnection` implementations and old peers continue unchanged.

For a persistent `localhost.tcp` backend connection, opt into non-response frames on `TcpRpcStream`:

```kotlin
val stream = TcpRpcStream.connect("127.0.0.1", 8080, "my.service")
stream.setInboundFrameHandler { frame ->
    when (frame.getString("type")) {
        "my_delta" -> applyDelta(frame)
    }
}
```

Response frames still use the existing request-id correlation path and never reach this handler. Other valid JSON frames are delivered unchanged, in wire-read order, on one per-stream worker rather than the socket reader. Callback completion is not ordered against later correlated responses: after an unsolicited frame enters the bounded handoff, the reader may complete a later response while that callback is still running. A non-fatal callback failure is reported and isolated to that frame so the worker can deliver later frames; malformed length-delimited JSON bodies are discarded after their bytes have been consumed so later compact frames retain alignment. The one-frame handoff is deliberately bounded: if the handler stops consuming, the reader stops draining the socket and the existing TCP write limits apply backpressure to the sender. Local close, remote EOF, and reader errors all close the socket and stop the dispatch worker, but a frame that was already read off the wire is still delivered: the worker drains the frames accepted before the close before its lane ends, so a peer that pushes frames and immediately disconnects cannot have those frames discarded while the response written behind them is still correlated (a handler can therefore run briefly after `close()` returns). A stream with no handler retains the prior response-only behavior and creates no dispatch worker, so existing clients and wire bytes are unchanged.

`ConnectionAwareServiceHandler` is what [`foundation.url:resolver`](https://github.com/CodexCoder21Organization/UrlResolver) builds its negotiated live-projection server-push on top of. Resolver's persistent reader continues to dispatch its own libp2p frames by `type`; `TcpRpcStream.setInboundFrameHandler` provides the corresponding opt-in path for persistent localhost TCP clients such as connection-aware proxies.

### Bytecode Fetching

UrlProtocol provides the `BytecodeProtocol` for requesting implementation bytecode from remote peers. This is used by [`foundation.url:resolver`](https://github.com/CodexCoder21Organization/UrlResolver) to support sandboxed execution.

When a service provider serves its **own** implementation bytecode (the optimized `supportsSandboxedExecution()` path), the response is streamed to the transport with bounded additional memory rather than materialized as a base64 `String` plus an inner JSON `String` plus a re-encoded `byte[]` (which previously held the payload ~5× in heap and could OOM a `-Xmx128m` service JVM under concurrent load). The serve path returns a `StreamingBytecodeResponse` carrier that the stream-write sites recognize. Attachment-capable transports send a small JSON envelope followed by the raw JAR bytes without first copying the complete frame into an aggregate byte array.

On raw TCP and an attachment-capable `/aicli-rpc/1.1.0` stream, that carrier is sent as a small JSON envelope plus a raw binary JAR attachment. This also bounds receiver-side parse memory: the multi-megabyte JAR never enters `org.json`. A negotiated libp2p 1.0 stream retains the legacy streamed base64 envelope for wire compatibility.

The same negotiated behavior applies to ordinary RPC results: every `ByteArray` nested in a response is extracted into a binary attachment on `/aicli-rpc/1.1.0`, keeping the JSON envelope bounded. A 1.0 peer continues to receive the legacy inline Base64 representation. This includes a result kept as raw org.json, such as one a forwarder relays from `sendRequestRaw`: its inline Base64 byte-array markers (`{"__type":"bytes","__value":…}`) are sent as binary attachments to a 1.1 peer, so a forwarded byte array can use the chunked large-response path instead of one oversized JSON frame. A message carries at most 1000 attachments, so a raw value with more markers than the message has room left for keeps its inline Base64 form. The caller decodes the same `ByteArray` either way.

"Nested" here means reachable through any combination of `Map`, `Collection` (`List`, `Set`, …) and object-array values, on both the request-parameter and response-result legs. Encoding traverses those container types rather than handing them to `org.json`'s generic wrapping, which would render a contained `ByteArray` inline as an array of numbers — so a `List<ByteArray>` arrives as a `List<ByteArray>`, not as a `List<List<Int>>`, and its bytes stay out of the JSON envelope.

These container values must be acyclic: a `Map`, `Collection`, or object array that points to itself or an ancestor container is rejected with an `IllegalArgumentException`, because JSON has no representation for cycles.

Explicitly-null values are preserved as present keys holding a JSON null, so a service can distinguish "the caller passed null" from "the caller omitted this argument". This holds for top-level request parameters, for entries of a nested `Map`, for elements of a nested `Collection`, and for the response result.

Inbound v1.1 attachments are admitted under the same shared memory discipline as JSON parsing. Both the `InputStream` reader (`Libp2pRpcProtocol.readMessageFrameFromStream`) and the Netty `/aicli-rpc/1.1.0` decoder enforce, before allocating any attachment body: (1) the declared attachment count must equal the number of binary references in the JSON envelope (mismatch → `RPC binary attachment count does not match the JSON envelope: …`), and those references' `__index` values must form an exact **bijection** with `0..count-1` — validated with a strict integer parse that rejects coerced numeric strings, fractions, and Int-overflow (so a duplicate/sparse/non-integer index cannot leave an attachment unreferenced or double-referenced); (2) the declared per-frame aggregate must not exceed `Libp2pRpcProtocol.MAX_ATTACHMENT_AGGREGATE_BYTES` (heap-scaled `maxMemory/4`, clamped to `[32 MiB, 100 MB]`), checked at each length header so an invalid declaration is declined promptly without buffering; and (3) the `InputStream` reader grows its reservation to the validated running attachment total, capped at the whole pool. A fair frame turn lets only one sequential attachment frame grow at a time, so frames cannot each retain an earlier body while waiting for the other to release capacity. Independent JSON frames can use the remaining pool. The Netty decoder takes an exact-size lease for a one-attachment frame after its validated length header (capped at the whole pool) and retains its whole-pool lease policy for multi-attachment frames. Non-attachment frames are untouched. A legitimate tens-of-MB implementation JAR therefore still transfers on a small-heap consumer. The Netty decoder probes admission without blocking its event loop. When a reservation is unavailable, it pauses the child stream and registers callback continuations with the process-wide `SizeAwareReservationScheduler`; there is no blocking admission worker pool. The scheduler grants the oldest fitting request, allows at most eight later fitting requests to pass an older non-fitting request, and then reserves releases for that older request. On the send side, an attachment frame larger than `ATTACHMENT_SINGLE_BUFFER_FRAME_LIMIT_BYTES` (1 MiB) is written as bounded, backpressured header + attachment chunks rather than one aggregate `ByteBuf`, so a large legitimate response is admissible under the muxer's connection-wide write budget and never duplicates the whole payload in heap.

Connection turns remain FIFO, while process memory reservations use that bounded size-aware scheduling rule so a non-fitting large request cannot block every fitting small request and repeated small requests cannot postpone it without limit. A reader that holds a whole-pool lease also cannot retain it indefinitely: a **minimum-progress stall watchdog** (`Libp2pRpcProtocol.ATTACHMENT_STALL_TIMEOUT_MS`, reset by every inbound byte so a slow-but-progressing large transfer is not stopped) releases the lease and closes the stream after a real no-progress stall on both decode paths.

Awaited writes assigned to the compact handoff lane are copied once into exact-size lane-owned storage before queueing; the caller buffer is released immediately. The compact lane retains at most 64 KiB per entry because it owns copies, never caller buffers, and its 64-entry limit therefore retains at most 4 MiB per physical connection. The `ByteBuf` shape walk is only a routing aid: known large backing graphs, composite retained storage, and opaque multi-segment buffers keep the ordinary non-compact route without copying. It is not a claim that every caller backing allocation can be discovered through Netty's public wrapper graph.

A service **bound** directly with `bind("url://…/") { … }` gets the same streaming serve by using the bytecode-aware overload:

```kotlin
val binding = protocol.bind(
    "url://localhost.tcp:8080/",
    { request, effectHandler -> /* handle non-bytecode RPC methods */ },
    implementationJar = myImplJarBytes,
    implementationClassName = "com.example.MyServiceImpl"
)
```

With this overload the framework answers `__bytecode_request` for the bound service itself with a `StreamingBytecodeResponse` (streamed by the bound server's write path, peak heap ≈ `implementationJar.size`); the handler is never invoked for that method. This is the `localhost.tcp` / url-bind analogue of the `supportsSandboxedExecution()` streaming serve, and it replaces hand-rolling `__bytecode_request` in the bound handler — which would Base64-materialize the whole JAR per (re)connect and OOM a small-heap provider under a reconnect storm. When such a bound provider is reached through a proxy (e.g. ContainerNursery's UrlFacade), the proxy forwards the already-final streamed response unchanged rather than re-demanding the legacy `{jar, className}` backend keys.

A proxy that passes results directly to another RPC writer should use `RpcStream.sendRequestForForwarding`. For `__bytecode_request`, the TCP implementation returns after the validated response header and known attachment length arrive, allowing the outer writer to emit its response header while the attachment body is still arriving. Code that needs to inspect the raw JSON result should continue to use `sendRequestRaw`, whose result behavior is unchanged.

#### Conditional Requests (ETag-Style Revalidation)

A client that already holds a copy of a service's bytecode can make the request *conditional* — the `url://` analogue of HTTP `If-None-Match`/`304 Not Modified`:

1. The client digests its cached JAR with `BytecodeProtocol.computeDigest(jarBytes)` (canonical form: `"sha256:" + lowercase hex`) and sends it via `BytecodeProtocol.createRequest(serviceIdentifier, interfaceClassName, cachedDigest)`.
2. The server compares it against `ServiceHandler.getImplementationJarDigest()` (default: `computeDigest` over `getImplementationJar()`; override with a precomputed value to avoid rehashing per request). On a match, it replies with a few-hundred-byte `createNotModifiedResponse(digest)` frame instead of the multi-megabyte JAR.
3. The client parses with `BytecodeProtocol.parseConditionalResponse(json)`, which returns a `BytecodeFetchResult` — either `NotModified` (keep using the cached copy) or `Downloaded` (the bytecode changed; here is the new payload).

Both directions are backward compatible: old clients send no digest and always receive the full payload, and old servers ignore the `cachedDigest` field and reply in full, which a conditional client handles as `Downloaded`. The proxied/forwarding serve path (services without local JAR bytes) always serves in full, since answering conditionally would require materializing the backend's JAR bytes to hash them.

When the caller already knows the exact provider, `requestBytecodeFromPeer` and
`requestBytecodeConditionallyFromPeer` use the same provider-aware exact-peer dial path. Both accept
separate connection and request budgets, and the conditional form returns `NotModified` only after
validating that the peer echoed the submitted canonical digest. The request budget is enforced by
the caller-supplied `Clock` all the way through the real libp2p response wait; it is not shortened
to the low-level stream's historical 30-second default and does not expire while an injected
`ManualClock` is frozen.

### TCP request outcomes

`TcpRpcStream.sendRequestRawWithOutcome(request)` returns `TcpRpcRequestOutcome` with the
ordinary raw `RpcResponse` available as `response`:

- `Response` means a decoded peer reply, including application errors.
- `LocalDeadlineExpired` means this stream's own 30-second response wait expired and closed its
  connection (`TIMEOUT`, `Request timed out after 30 seconds`).
- `RequestSendFailed` means an I/O error occurred while writing this request (`INTERNAL_ERROR`,
  `Failed to send request: <original I/O error message>`). Its mandatory `origin` is captured when
  that write fails; a later `close()` cannot change it.
- `StreamClosed` means a locally generated `INTERNAL_ERROR`, `Stream closed` result: the stream
  ended before selecting a reply. It carries the same mandatory, failure-time `origin` as
  `RequestSendFailed`, so reads and writes use one cause taxonomy.
- `TcpRpcTransportFailureOrigin.CLEAN_EOF` guarantees that the reader observed an orderly peer EOF
  before a response. It does not claim that the peer reset the connection or that this stream
  closed it locally.
- `TcpRpcTransportFailureOrigin.PEER_RESET` guarantees that the failed read or write observed native
  reset evidence (including a write-side broken pipe). Its derived `peerResetObserved` value is true
  and `closedLocally` is false, even if `close()` is called after that failure.
- `TcpRpcTransportFailureOrigin.LOCAL_CLOSE` guarantees that `TcpRpcStream.close()` or
  `releaseAfterForwarding()` caused the operation to end. It does not track a caller directly
  closing the socket passed to the constructor. Its derived `closedLocally` value is true and
  `peerResetObserved` is false. Queued frame sends retain the origin that ended admission, even
  before the reader processes the closure; a later local close does not replace an earlier peer origin.
- `TcpRpcTransportFailureOrigin.IO_FAILURE` means the failed operation had no clean-EOF, native-reset,
  or tracked local-close evidence. Direct caller closure of the constructor socket and framing I/O
  failures use this value. Neither derived flag is true.
- `Socket closed` text alone never establishes a peer reset. Callers describing a peer reset should
  require `peerResetObserved && !closedLocally`; both values come from the immutable `origin`, not
  from the stream's later state.
- `ResponseUnavailable` retains the defensive `INTERNAL_ERROR`, `Response was null` result if a
  response wait completes without a selected response.

A backend's error stays `Response` even when its text exactly matches any of those transport
messages and the backend immediately closes the connection. Callers should classify origin by
the outcome type, never by message text, elapsed time, or the stream's later open state.

The existing `sendRequest`, `sendRequestRaw`, asynchronous, and forwarding APIs retain their
response shape and deadlines. The new method does not add retries or change wire messages.

### Forwarding a bytecode response

`RpcStream.sendRequestForForwarding(request)` lets a proxy pass an accepted bytecode response
through before its backend body has finished arriving. `TcpRpcStream` returns a
`ForwardedStreamingBytecodeResponse` after validating the header and admitting its retained
resources. Ordinary `sendRequestRaw` continues to return a fully read raw result. Implementations
without incremental forwarding support use that ordinary raw path.

Pass the returned result to the outer RPC writer unchanged, preserving the response metadata.
Use `releaseAfterForwarding()` when the request handle is no longer needed but its accepted
response still belongs to the outer writer:

```kotlin
import foundation.url.protocol.Libp2pRpcProtocol
import foundation.url.protocol.TcpRpcStream

fun forwardBytecode(request: Libp2pRpcProtocol.RpcRequest): Libp2pRpcProtocol.RpcResponse {
    val backend = TcpRpcStream.connect("127.0.0.1", 8080, "bytecode-provider")
    return try {
        backend.sendRequestForForwarding(request)
    } finally {
        backend.releaseAfterForwarding()
    }
}
```

`close()` cancels the connection and its active body even after `releaseAfterForwarding()`.
This applies to direct transport streams and handles returned by `UrlProtocol` alike.
Closing the returned response
also cancels an incomplete body. A response permits one body reader and one outer writer; once
its exact body length has been consumed, an unreleased backend connection can carry another
request. Transfers are not resumed after a process restart.

Streaming forwarding admits at most 32 transfers process-wide and bounds their estimated retained headers,
metadata and scratch buffers to one sixteenth of the maximum heap, with an 8 MiB minimum and
256 MiB maximum. Streaming admission never waits. When either limit is full, compatible responses
fall back to the ordinary buffered reader and its existing memory budget, returning the same bytes
after the body has arrived. The unread declared body does not consume the streaming reservation. Existing transport queues keep their own limits;
`forwardedTransferMemorySnapshot()` reports forwarding reservations and active transfers.
A demanded body read keeps the existing 10-second no-progress bound, while every held transfer
has the existing size-based absolute lifetime (a 60-second minimum and 4 KiB/second floor).
An output-capacity pause does not count as a backend read stall.

TCP and attachment-capable libp2p writers pull bounded body chunks. A capable libp2p peer can
receive small replies between complete forwarded chunks, including while the backend is paused.
Older libp2p peers receive incremental base64 within their JSON limits. If response preparation
fails, including when a valid attachment exceeds those legacy limits, the requester receives a
framed error after the backend is released. If that error cannot be sent, the affected stream closes.
A truncated body or a failed output write closes the affected stream; an early header does not
promise body completion, and error frames are never inserted into a partly written body.

### Sandbox Package

The `foundation.url.protocol.sandbox` package contains protocol-level types for bytecode exchange:

| Class | Description |
|-------|-------------|
| `BytecodeProtocol` | Creates and parses bytecode request/response messages, including conditional (digest-validated) requests |
| `BytecodeRequest` | Represents a request for implementation bytecode, optionally carrying a `cachedDigest` |
| `BytecodeResponse` | Contains implementation JAR bytes and class name |
| `BytecodeFetchResult` | Outcome of a conditional request: `NotModified` or `Downloaded` |
| `BytecodeProvider` | Interface for services that provide implementation bytecode |
| `JsonSerialization` | Serializes/deserializes objects crossing service boundaries |
| `SandboxException` | Thrown when sandbox operations fail |

> **Note:** `SandboxedConnection`, `SandboxedProxyGenerator`, `TypeMarshaling`, and the high-level `UrlResolver` class have been moved to [`foundation.url:resolver`](https://github.com/CodexCoder21Organization/UrlResolver), which provides typed connections and SJVM-based sandboxed execution on top of UrlProtocol.

## Default Bootstrap Peers

> **Note:** You do not need to know or configure bootstrap peers for normal usage. The default bootstrap peers are used automatically when you create a `UrlProtocol()` or `UrlResolver()` instance. This section is for reference only.

The url:// network includes two hardcoded bootstrap peers running on wasmserver.com (`198.199.106.165`):

| Peer | Seed Constant | Port | Service |
|------|--------------|------|---------|
| ContainerNursery | `WASMSERVER_BOOTSTRAP_SEED` | 35000 | Primary relay node |
| HardwareControlFabric Daemon | `HARDWARE_FABRIC_BOOTSTRAP_SEED` | 44605 | `hardware.control.fabric.daemon` |

These are used automatically by `UrlProtocol.withDefaultBootstrapPeers()` and `DEFAULT_BOOTSTRAP_PEERS`. Custom peers can be added via `addBootstrapPeer()` but this is rarely necessary.

```kotlin
// Use default bootstrap peers (recommended)
val protocol = UrlProtocol.withDefaultBootstrapPeers()

// Or create the HCF daemon bootstrap peer explicitly
val hcfPeer = UrlProtocol.createHardwareFabricBootstrapPeer()
```

## Network Architecture

### Peer Discovery via Gossip Protocol

UrlProtocol uses a gossip-based peer discovery mechanism. When peers join the network or register services, announcements propagate through the network:

1. **Service Announcements**: When a service is registered, the node broadcasts a `ServiceAnnouncement` message to all connected peers
2. **TTL-based Propagation**: Each message has a TTL (default: 7 hops). Receiving peers decrement the TTL and re-broadcast until TTL reaches 0
3. **Deduplication**: The `GossipMessageTracker` suppresses a message while its ID remains in the retained window. Its five-minute time TTL is paired with a hard 10,000-entry bound; a live-entry storm evicts oldest IDs first rather than growing until time expiry. At more than 10,000 unique IDs per five minutes (about 33.3 IDs/second), capacity can evict an ID before its time TTL, and a delayed copy of that ID is then processed again. The message's hop TTL (default: 7), not the tracker's time TTL, is the final bound on one re-forwarding lineage; repeated external re-injection after eviction can start additional bounded lineages.
4. **Peer Exchange**: Nodes periodically exchange their known peer lists, enabling organic network growth. Each `PeerInfo` may include a `serviceLifecycleTimestamps` map containing provider-authored lifecycle timestamps for its advertised services. Peer announcements and relay peer lists carry the same optional map so the ordering information survives each discovery path. A missing map or a missing service entry means that lifecycle value is unknown, as it is for catalogs written by older peers. The map is an additive JSON field, so older readers continue to consume the peer ID, addresses, and service list. `PeerInfo` exposes an immutable snapshot of the map, and its copy, equality, hash, and destructuring operations include that snapshot. A PeerExchange response is a durable acknowledgement: request-side received peers are applied before the response is written, while response-side follow-up processing remains fire-and-forget. A request may set `requestedResponsePeerIds` to receive only the submitted peer records it needs to confirm, plus the responder's own record when its Noise-authenticated peer ID is explicitly requested. Other third-party records remain excluded; omitting the field preserves the full-view response used for discovery.

```
Node A registers service → broadcasts to Node B, C
                          ↓
                    Node B re-broadcasts to Node D, E (TTL-1)
                          ↓
                    Node D re-broadcasts to Node F (TTL-2)
                          ...continues until TTL=0
```

#### Late-Joining Peers: Best-Effort Replay and Eventual Consistency

Relays replay a bounded, recent set of service announcements when a peer registers. This is a
best-effort acceleration for late joiners, not a durable history: each relay retains at most 1,000
distinct service-announcement payloads, refreshes move an entry to the newest position, and the
oldest entry is evicted when the bound is exceeded. A late joiner therefore discovers services
inside the retained window immediately, while services beyond that window become visible through
normal gossip, an explicit query/peer exchange, or a later provider re-announcement.

The recovery contract is eventual consistency through periodic re-announcement. A global service
registered with the default `ServiceRegistrationConfig` re-announces every five minutes, so an
announcement omitted from a relay's bounded replay window is repaired on a later cycle. Setting
`ServiceRegistrationConfig.reannounceIntervalMs` to `0` disables that recovery path; an operator
that does so must arrange explicit calls to `ServiceRegistration.reannounce()` or accept that a
peer joining after the original announcement was evicted may not discover the service until some
other query or fresh announcement occurs.

When a registered client sends gossip into a relay, `RelayService` retains sole ownership of the
registered-client fan-out decision and transport. Relay-aware gossip handlers receive the sender
and ingress-relay identities plus that ownership flag, allowing their registry rebroadcast path to
exclude both peers without duplicating the hub-to-leaf distribution. Ownership does not promise
delivery when relay validation rejects the message.

Compatibility is directional. A new `RelayService` still invokes the legacy callback for a handler
compiled before `RelayIngressGossipHandler`; the relay also keeps its own fan-out so that mixed
deployments may duplicate a message but cannot lose registered-client delivery. A handler compiled
against `RelayIngressGossipHandler` requires a protocol version containing that interface at runtime,
so consumers must upgrade the protocol dependency before (or together with) the relay-aware handler.

### Universal Relay Architecture

**Every node in the UrlProtocol network participates as a relay by default.** There is no dedicated relay infrastructure - instead, any node with a publicly routable IP address automatically serves as a relay for NAT-ed peers.

#### How It Works

1. **Public IP Discovery**: When a node starts, it learns its public IP address through peer observations (the Identify protocol reports what address peers see). After the first peer connection, `queryObservedAddress()` queries the Identify protocol to learn our observed public address. Nodes can also set their public IP explicitly via the `PUBLIC_IP` environment variable.

2. **Automatic Relay Capability**: Nodes with public IPs automatically accept relay registrations from other peers. The `RelayService` enables this functionality when `isPubliclyRoutable()` returns true.

3. **NAT-ed Peer Registration**: Peers behind NAT register with one or more publicly-reachable peers.

#### Public IP Detection

The `PublicAddressDiscovery` utility handles public IP detection with this priority:

1. **Explicit Configuration**: `PUBLIC_IP` environment variable (highest priority)
2. **Peer Observation**: IP addresses reported by connected peers via the Identify protocol (`/ipfs/id/1.0.0`)

`getMostObservedIp()` is always non-blocking — it returns the best known IP from explicit configuration or peer observations. On initial startup before any peers are contacted, the public IP may be unknown; wildcard listen addresses are filtered out and relay addresses are used instead. Once the public IP is discovered via peer observation (Identify protocol), subsequent address lookups include it and an updated PeerAnnouncement is broadcast.

```kotlin
// Explicitly set via environment variable
// PUBLIC_IP=198.199.106.165 java -jar UrlProtocol.jar

// Or let Identify discover it automatically after connecting to peers
// queryObservedAddress() is called automatically after successful connections
```


## Error Handling

The following exceptions may be thrown:

- `IllegalArgumentException` — Invalid URL format (wrong scheme, missing service identifier)
- `UrlResolutionException` — Service cannot be resolved (no peer found advertising the service)
- `UrlProtocolException` — Low-level protocol errors (connection failures, stream errors)
- `RelayRequestNotDispatchedException` — A relay request failed before any target handler received
  it. A caller may re-resolve or reconnect and resend after this specific exception.
- `RelayException` — A relay failure whose delivery state is unknown. Timeouts, target failures,
  and lost replies use this base type; callers must not automatically replay non-idempotent work.
- `SandboxException` — Sandbox creation or execution failures. The exception defines two
  read-only, nullable fields for describing the application exception behind a remote failure:
  `remoteExceptionClassName` (its fully qualified class name) and `remoteExceptionMessage` (its
  message, null when it had none). The sandbox implementation (UrlResolver) fills them in only
  for a failure the remote service itself reported (see "Remote application failures on the wire"
  below); they are null otherwise, including for every exception built with the two-argument
  constructor. Existing `message` and `cause` text is unchanged and remains available for
  diagnostics.

```kotlin
import foundation.url.protocol.UrlResolver
import foundation.url.protocol.UrlResolutionException

val resolver = UrlResolver(bootstrapPeers)

try {
    val service = resolver.openConnection("url://unknown.service/", SomeType::class)
} catch (e: IllegalArgumentException) {
    println("Invalid URL: ${e.message}")
} catch (e: UrlResolutionException) {
    println("Service not resolved: ${e.message}")
}
```

### Remote application failures on the wire

When a service's own request handler throws (the exception reaches `ServiceRoutingHandler`, or a
raw `RpcRequestHandler` served by `Libp2pHostFactory.createServerHost` or `TcpServer` throws), the error response
keeps its existing `code` and `message` text and additionally carries the exception's fully
qualified class name and message in the optional `RpcError.data` field. Older clients ignore the
field; responses from older servers omit it.

```kotlin
import foundation.url.protocol.RemoteApplicationFailure
import foundation.url.protocol.remoteApplicationFailure

val response = stream.sendRequest(request)
val failure: RemoteApplicationFailure? = response.error?.remoteApplicationFailure
// e.g. RemoteApplicationFailure(className = "java.lang.IllegalStateException", message = "wrong state")
```

`remoteApplicationFailure` is null for transport, timeout, closed-stream, routing, and legacy
errors, and for cancellations and interruptions. An exception implementing `ServiceInfrastructureFailure` (a failure of
the service-hosting machinery, such as an expired handler session or a malformed resume) keeps its
error code and text but is never reported as an application failure; use
`ServiceInfrastructureException` (an `IllegalStateException`) or
`ServiceInfrastructureArgumentException` (an `IllegalArgumentException`, which keeps
`INVALID_PARAMS`). Servers build these errors with `applicationFailureRpcError`;
other error formats that embed the same shape (for example relay responses) use
`applicationFailureData` and `remoteApplicationFailureFromData`. The structured message copy is
capped at `MAX_REMOTE_FAILURE_MESSAGE_CHARS` characters; the full text stays in the error message.
`ServicePushException` (a server push the client connection could not take) is a
`ServiceInfrastructureFailure` too.

#### Proxy handlers

A handler that forwards each call to another service (a proxy, gateway, or facade) must report
details only for the leaf service's own exception, so it has two obligations:

1. **Forward the backend's failure unchanged.** Throw an exception implementing
   `ReportsRemoteApplicationFailure` whose `remoteApplicationFailure` is the backend error's
   `remoteApplicationFailure` (null when the backend reported none), for example the ready-made
   `ForwardedApplicationFailureException`. Its own class and message then only shape the error text;
   the reported details are the leaf's.
2. **Mark the proxy's own failures as hosting failures.** Failures of the proxy itself (a backend it
   cannot reach, a route or bridge mismatch, a closed backend connection) must implement
   `ServiceInfrastructureFailure`, or the proxy's exception class would be reported as the
   application's.

```kotlin
import foundation.url.protocol.ForwardedApplicationFailureException
import foundation.url.protocol.remoteApplicationFailure

// Inside the proxy's ServiceHandler.handleRequest:

val response = backend.sendRequest(request)
val backendError = response.error ?: return response.result
throw ForwardedApplicationFailureException(
    "Backend call failed: ${backendError.message}",
    backendError.remoteApplicationFailure
)
```

Throw the forwarding exception directly from the handler: only the exception that leaves the handler
is inspected, so a wrapper around it (for example an `ExecutionException` from `Future.get()`) is
reported as the proxy's own failure. Proxies can be chained; each hop forwards the leaf's details
unchanged.

## Network Health

Monitor the health of the URL protocol network at: https://url-network-health.wasmserver.com/
