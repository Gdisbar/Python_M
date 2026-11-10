# Ops & Architecture Practice — Sections 16–19 

### 16. Observability: Logging, Metrics, Tracing
### 17. Capacity Planning & Back-of-the-Envelope Math
### 18. Error Recovery & Graceful Degradation
---

## 16. Observability: Logging, Metrics, Tracing

### 16.1 Building the Intuition: Why This Is a Distributed-Systems-Specific Problem

In a monolith, "what happened during this request" could be answered by
reading one log file, or attaching one debugger to one process — there
was only ever one place to look. The moment a single user request fans
out across multiple services (§8), that single vantage point disappears:
the request's story is now scattered across N processes, on N different
machines, each with its own local log file that knows nothing about what
happened in any of the others. Observability tooling exists specifically
to reconstruct ONE coherent story out of what's now, by construction, N
separate and disconnected ones.

### 16.2 LLD: Distributed Tracing — How a Trace ID Actually Propagates

#### 16.2.1 The mechanism: W3C Trace Context

The entire trick behind distributed tracing is remarkably simple once you
see it: a single **trace ID** is generated once, at the very first entry
point of a request, and is then carried forward as an ordinary HTTP header
on EVERY subsequent call the original request causes — every service that
receives it simply passes it along to whatever it calls next.

```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
             │  │                                │                │
          version  trace-id (fixed for the         parent-span-id   flags
                    ENTIRE request, never           (the specific
                    changes across any hop)          span that made
                                                      THIS call)
```

**Class diagram:**

```
┌─────────────────────────────────┐
│ Span                                 │
├─────────────────────────────────┤
│ + trace_id: string                       │  # SAME across the entire request
│ + span_id: string                            │  # unique to THIS specific
│ + parent_span_id: string?                        │  operation/hop
│ + operation_name: string                             │
│ + start_time, end_time                                   │
│ + tags: Map<string,string>                                   │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ Propagator                           │
├─────────────────────────────────┤
│ + inject(span, outgoing_request)         │  # writes traceparent header
│ + extract(incoming_request) -> SpanContext?  │  # reads traceparent header,
│                                                 │  used to create a CHILD span
└─────────────────────────────────┘
```

**Sequence — a trace born at the edge, propagated through 3 hops:**

```
Client        Gateway            Order-Svc          Payment-Svc
  │  GET /checkout   │                    │                   │
  │──────────►│                                                  │
  │            │  NO traceparent header present → this is the         │
  │            │  ROOT span. Generate NEW trace_id="abc123",              │
  │            │  span_id="span-1" (no parent)                                │
  │            │  outgoing call to Order-Svc:                                     │
  │            │  Propagator.inject() adds header:                                   │
  │            │  traceparent: 00-abc123-span1-01                                        │
  │            │──────────────────────►│                                                    │
  │            │                          │  Propagator.extract() reads trace_id="abc123",  │
  │            │                          │  parent_span_id="span-1" → creates CHILD span       │
  │            │                          │  span_id="span-2", parent_span_id="span-1",            │
  │            │                          │  SAME trace_id="abc123"                                    │
  │            │                          │  outgoing call to Payment-Svc:                                 │
  │            │                          │  traceparent: 00-abc123-span2-01                                  │
  │            │                          │──────────────────────►│                                            │
  │            │                          │                          │  creates span_id="span-3",                  │
  │            │                          │                          │  parent="span-2", SAME trace_id                │
  │            │                          │◄──────────────────────│                                                     │
  │            │◄──────────────────────│                                                                                    │
  │◄──────────│                                                                                                                  │
  │                                                                                                                                │
  │  Every span, from every service, independently reports itself to a SHARED     │
  │  collector (Jaeger) tagged with the SAME trace_id — the collector's job is       │
  │  purely to GROUP all spans sharing a trace_id and reconstruct the parent-child       │
  │  tree from each span's parent_span_id, producing exactly the waterfall view          │
  │  shown back in the earlier §16 material.
```
**The one property that makes this work with zero central coordination**:
each service only ever needs to know the ID it RECEIVED and generate a new
child ID for its own work — no service needs to know anything about the
overall trace tree; the reconstruction happens entirely downstream, at the
collector, purely from the parent-pointers every span carries.

### 16.3 LLD: Metrics Collection — Pull vs Push, and Why Each Exists

#### 16.3.1 The intuition

```
PULL (Prometheus's model): the metrics BACKEND actively scrapes each
  service's /metrics endpoint on a fixed interval.
  ✅ Prometheus already needs a list of service addresses to scrape — this
     DOUBLES as a health/liveness signal for free: a scrape that fails
     repeatedly means the service is unreachable, no separate mechanism
     needed to notice that.
  ✅ The metrics backend controls its OWN load — it decides how often to
     scrape, rather than being at the mercy of however fast every service
     decides to push data at it.
  ❌ Doesn't work for something that doesn't exist long enough to be
     scraped on a schedule — a short-lived batch job that runs for 4
     seconds and exits has no window during which a periodic scrape could
     ever catch it.

PUSH (StatsD's model): each service actively SENDS its metrics to a
  collector.
  ✅ Naturally solves what pull can't: a batch job can push its final
     metrics right before exiting, regardless of any external schedule.
  ❌ The collector's load is now entirely at the mercy of however many
     services are pushing and how often — a burst of misbehaving
     services could overwhelm it with no natural back-pressure.
```
**The reconciliation used in practice**: Prometheus itself supports an
optional **Pushgateway** intermediary specifically for the short-lived-job
case — the batch job pushes ONCE to the Pushgateway before exiting, and
Prometheus then PULLS from the Pushgateway on its normal schedule, getting
the pull model's operational benefits everywhere else while still
covering the one case pure pull can't handle.

#### 16.3.2 Class Diagram and Exposition Format

```
┌─────────────────────────────────┐
│ MetricsRegistry                     │
├─────────────────────────────────┤
│ + counter(name) -> Counter               │  # only ever increases —
│ + gauge(name) -> Gauge                       │  total requests served
│ + histogram(name, buckets) -> Histogram          │  # current value — queue
│ + expose() -> string  (Prometheus text format)       │  depth right now
└─────────────────────────────────┘                       │  # distribution —
                                                            │  critical for latency:
                                                            │  an AVERAGE hides that
                                                            │  5% of users saw >5s
                                                            │  while 95% saw <200ms
```

```
# Prometheus text exposition format — what /metrics literally returns
http_requests_total{method="GET",status="200"} 15234
http_request_duration_seconds_bucket{le="0.1"} 12000
http_request_duration_seconds_bucket{le="0.5"} 14800
http_request_duration_seconds_bucket{le="+Inf"} 15234
```

### 16.4 Correlation — the Property That Makes Three Pillars Act as One System

None of the three pillars is useful in isolation once a real incident
requires cross-referencing them — the entire point is that a SINGLE
identifier ties them together:

```sql
-- Every structured log line MUST include the trace_id from §16.2,
-- not as an afterthought but as a mandatory field:
{"timestamp":"...", "trace_id":"abc123", "span_id":"span-2",
 "level":"ERROR", "message":"payment declined", "order_id":"789"}
```
```
┌─────────────────────────────────────────────────────────────────┐
│  A metric alert fires: p99 latency spike on the checkout endpoint.   │
│  → Query traces for trace_id values in that time window with high        │
│    latency → find one showing Payment-Svc as the long pole                    │
│  → Using that SAME trace_id, filter logs to exactly that request's                │
│    timeline across every service it touched → find the specific error                │
│    line explaining WHY Payment-Svc was slow                                              │
│                                                                                              │
│  Three different QUESTIONS (how much? where? why?), answered by three          │
│  different tools, joined by ONE shared identifier — this is the entire            │
│  value proposition of "observability" as a discipline distinct from just              │
│  having logs, metrics, and traces as separate, uncorrelated tools.                        │
└─────────────────────────────────────────────────────────────────┘
```

### 16.5 LLD: SLO Burn-Rate Alerting — Beyond a Naive Threshold

#### 16.5.1 Building the intuition: why a naive "alert if error rate > X%" is wrong in both directions

```
Too NOISY for brief blips: a 2-minute error spike from a single pod
  restarting trips the alert, pages someone at 3am, and resolves itself
  before they even open their laptop — a wasted, trust-eroding page.

Too SLOW for a genuine slow burn: a sustained, smaller elevated error
  rate (say, 2% instead of the usual 0.1%) might never cross a fixed
  "alert if >10%" threshold at all, while quietly consuming the ENTIRE
  monthly error budget (§19.4) over several days, undetected until it's
  already gone.
```

#### 16.5.2 The Fix: Multi-Window Burn Rate

Instead of one threshold, use TWO alerts, each answering a genuinely
different question:

```
FAST BURN: "at the CURRENT error rate, would we exhaust the ENTIRE
  monthly error budget in just a few hours?" — checked over a SHORT
  window (5 minutes) so it fires almost immediately for a severe,
  acute problem, but is based on a rate high enough that a random brief
  blip won't trigger it.

SLOW BURN: "at a smaller but SUSTAINED elevated error rate, would we
  exhaust the budget over several days?" — checked over a LONGER window
  (6 hours, say), catching the slow, quiet problem the fast-burn alert
  is deliberately NOT tuned to catch.
```

```
burn_rate = (actual error rate over window) / (error rate the SLO permits)

Fast burn alert:  burn_rate over 5m  > 14.4   (would exhaust a 30-day
                                                budget in ~2 hours if
                                                sustained)
Slow burn alert:  burn_rate over 6h  > 1  (would exhaust the budget by
                                            the end of the SLO period if
                                            sustained at this steady rate)
```

**Sequence — both alerts evaluated continuously, firing independently at
different urgencies:**

```
Time T: Payment-Svc starts returning 30% errors (severe, acute problem)
  Fast-burn check (5m window): burn_rate = 30% / 0.1% ≈ 300 >> 14.4
  → PAGES IMMEDIATELY, severity=CRITICAL

Separately, on a different day:
Time T: a subtle bug causes a steady 0.5% error rate (5x normal, but far
  below any naive fixed threshold)
  Fast-burn check (5m window): burn_rate ≈ 5, below the 14.4 threshold
  → does NOT page immediately (correctly — this isn't an acute emergency)
  Slow-burn check (6h window): sustained burn_rate ≈ 5 > 1
  → PAGES with severity=WARNING, "budget will be exhausted in ~6 days
    at this rate" — caught well before the acute fast-burn alert ever
    would have fired, and without having paged anyone during a harmless
    momentary blip earlier in the system's life
```
This two-window design is precisely what lets an on-call rotation trust
its pages — acute problems page loudly and immediately, slow-burning
problems page with appropriate, lower urgency, and neither category
drowns out or masks the other.

### 16.6 Health Checks — Cross-Reference

The liveness-vs-readiness distinction, the CrashLoopBackOff failure mode
it prevents, and the FastAPI implementation are covered in full in the
standalone Sections 13–20 summary document (§16.3) and V2 §16 — not
repeated here. The one addition worth making at LLD depth: a readiness
check aggregating MULTIPLE dependencies should weight them by whether
they're actually required to serve traffic at all, not treat every
dependency identically:

```
┌─────────────────────────────────┐
│ ReadinessAggregator                  │
├─────────────────────────────────┤
│ + checks: List<(name, check_fn, required: bool)> │
│ + evaluate() -> ReadinessResult             │
│     results = [c.check_fn() for c in checks]      │
│     # a REQUIRED dependency failing → not ready       │
│     # an OPTIONAL dependency failing (e.g. a           │
│     # recommendations service that only enriches          │
│     # the response, §8.3's graceful degradation) →           │
│     # still ready, just report the degradation                │
│     required_ok = all(r.ok for r in results if r.required)        │
│     return ReadinessResult(ready=required_ok, details=results)        │
└─────────────────────────────────┘
```
This directly operationalizes §8's graceful-degradation principle at the
health-check level: a service shouldn't report itself as fully unready
just because a genuinely optional dependency is having a bad day.

---

## 17. Capacity Planning & Back-of-the-Envelope Math

### 17.1 Building the Intuition: Why This Gates Every Other Decision in This Guide

Every pattern built in Files 1–3 — whether to shard (§3.3), whether
caching is worth its complexity (§4), whether you need a CDN (§4.6),
whether a single load balancer or an active-active multi-region setup is
warranted (§5.6) — is a decision that depends entirely on the ACTUAL
SCALE you're building for. Sharding a database handling 50 requests/second
is over-engineering that adds real operational cost for no benefit;
NOT sharding a database that genuinely needs to handle 500,000 writes/sec
is under-engineering that will fall over in production. **The skill this
section teaches isn't precision — it's getting the ORDER OF MAGNITUDE
right quickly enough to make an early architecture decision, refined later
with real measurements once the system exists.** This is also literally
one line item of §19.4's Non-Functional Requirements checklist — capacity
estimation is where that NFR gets a number attached to it.

### 17.2 The Latency Numbers — Why These Specific Ratios, Not Just Facts to Memorize

```
L1/L2 CPU cache      ~1 ns
RAM                   ~100 ns        (~100x slower than L1)
SSD random read        ~100 μs        (~1,000x slower than RAM)
Same-datacenter network round trip ~0.5 ms
Cross-region network round trip     ~50-150 ms
```
The reason these specific numbers matter isn't trivia — they're the exact
ratios that make §4's entire caching argument concrete rather than
hand-wavy. "Caching helps" is a vague claim; **"reading from Redis (RAM)
instead of Postgres (disk) is roughly 1,000x faster per access, so if your
working set fits in memory, caching turns a disk-bound system into a
memory-bound one" is a claim you can actually defend with a number.**
Without these ratios memorized, you can't quickly distinguish "this
optimization will matter enormously" from "this optimization is
negligible" without actually benchmarking first — and knowing which is
which BEFORE reaching for a profiler is exactly the fast, approximate
judgment this section is building.

### 17.3 A Structured Estimation Framework — a Repeatable Pipeline, Not One Memorized Example

Rather than memorizing a single worked example, build the same five-stage
pipeline every time — each stage's output is a direct input to the next:

```
┌─────────────────────────────────┐
│ CapacityEstimationPipeline           │
├─────────────────────────────────┤
│ 1. TRAFFIC                               │
│    avg_qps = daily_requests / 86,400          │  # 86,400 = seconds/day,
│    peak_qps = avg_qps × peak_multiplier           │  round to 100,000 for
│      (typically 2-10x avg, domain-dependent)          │  fast mental math
│                                                            │
│ 2. STORAGE                                                    │
│    daily_storage = daily_new_records × avg_record_size            │
│    total_storage(N years) = daily_storage × 365 × N                   │
│                                                                            │
│ 3. BANDWIDTH                                                                   │
│    bandwidth = peak_qps × avg_payload_size                                        │
│      (check this against your NIC/network tier's actual capacity —                    │
│      this is where a design realizes it needs a CDN, §4.6, BEFORE                          │
│      ever hitting the problem in production)                                                  │
│                                                                                                    │
│ 4. MEMORY (cache working set)                                                                        │
│    working_set = (fraction of data that's "hot," e.g. last 24h of                                        │
│      activity) × avg_record_size                                                                             │
│      (compare against a single Redis node's practical RAM ceiling —                                              │
│      this is where a design realizes it needs a partitioned/clustered                                                │
│      cache instead of one node, tying directly to §3.3's sharding                                                        │
│      reasoning, just applied to the cache layer instead of the DB)                                                           │
│                                                                                                                                    │
│ 5. SERVERS NEEDED                                                                                                                       │
│    servers = peak_qps / requests_per_server_per_second                                                                                       │
│      (compare against §5's load balancing algorithms — this number is                                                                            │
│      literally what determines whether you need 3 backend instances or                                                                              │
│      300, which in turn is what determines whether a simple round-robin                                                                                 │
│      LB suffices or you're deep into consistent-hashing territory, §5.2.1)                                                                                   │
└─────────────────────────────────┘
```

### 17.4 Full Worked Example: a Chat/Messaging Application at Scale

Working through ALL five stages for one concrete system, to show the
methodology transferring cleanly to a domain heavier on storage and
bandwidth than the URL-shortener example:

```
ASSUMPTIONS: 10 million daily active users, average 40 messages sent per
user per day, average message size 200 bytes (text) + occasional media.

STAGE 1 — TRAFFIC:
  daily_messages = 10,000,000 users × 40 = 400,000,000 messages/day
  avg_qps = 400,000,000 / 86,400 ≈ 4,630 messages/sec
  peak_qps (assume 5x average for a chat app's typical daytime peak)
    ≈ 23,150 messages/sec

STAGE 2 — STORAGE:
  daily_storage = 400,000,000 × 200 bytes ≈ 80 GB/day (text only)
  Over 3 years' retention: 80 GB × 365 × 3 ≈ 87.6 TB
  → This is comfortably within a SHARDED (§3.3) but not exotic storage
    tier — directory-based or hash-based sharding across a reasonable
    number of nodes, not a novel storage architecture.

STAGE 3 — BANDWIDTH:
  peak_bandwidth = 23,150 msg/sec × 200 bytes ≈ 4.6 MB/sec for TEXT alone
  — genuinely trivial, a single network interface handles this easily.
  BUT: if even 5% of messages include a media attachment averaging 500KB:
  media_bandwidth = (23,150 × 0.05) × 500,000 bytes ≈ 578 MB/sec
  → THIS is the number that forces a CDN (§4.6) into the design — media
    delivery, not text messaging itself, is where bandwidth planning
    actually bites, and this calculation is what surfaces that BEFORE
    the system is built, not after a media feature ships and the origin
    server's bandwidth bill or throughput becomes a production incident.

STAGE 4 — MEMORY (cache working set):
  Most users only actively view their OWN recent conversations — assume
  the "hot" working set is roughly the last 24 hours of messages for
  currently-active users: with ~1M concurrently active users at any
  moment, each with ~20 recent messages cached at 200 bytes each:
  working_set ≈ 1,000,000 × 20 × 200 bytes = 4 GB
  → Comfortably fits on a SINGLE well-provisioned Redis node — no need
    for a partitioned cache cluster at this specific scale, a concrete,
    numbers-backed answer rather than a guess.

STAGE 5 — SERVERS NEEDED:
  Assume each application server instance handles 2,000 req/sec
  (a reasonable assumption for a lightweight message-routing service):
  servers = 23,150 / 2,000 ≈ 12 instances at peak
  → This number is what tells you a simple round-robin or least-
    connections load balancer (§5.2) is entirely sufficient — you are
    nowhere near the scale where consistent hashing's rebalancing
    benefits (§5.2.1) would matter over a simpler algorithm.
```

### 17.5 Capacity Numbers as the Trigger for Specific Architecture Decisions

This is the capstone table tying the whole guide's patterns to the actual
numbers that justify reaching for each one — the answer to "how do I know
WHEN to apply §3.3's sharding, or §5.2.1's consistent hashing, or §4.6's
CDN" is always a number from this section, not intuition alone:

| Calculated result | Threshold crossed | Pattern this justifies |
|---|---|---|
| Write QPS exceeds a single primary's sustainable write throughput (measured, not assumed — often tens of thousands/sec on solid hardware) | Vertical scaling exhausted | Sharding (§3.3) |
| Read QPS far exceeds writes, single primary struggling with read load alone | Read-heavy bottleneck | Read replicas (§3.2) |
| Cache working set exceeds one node's practical RAM ceiling | Single-node cache limit | Partitioned/clustered cache (§3.3's logic, applied to cache) |
| Bandwidth for media/large payloads approaches network tier limits | Bandwidth ceiling | CDN (§4.6) |
| Backend instance count grows into the dozens+ | LB algorithm choice starts to matter | Move from round-robin toward least-connections or consistent hashing (§5.2) |
| Number of services × languages makes "shared client library" enforcement impractical | Organizational scaling limit, not a traffic number at all | Service mesh (§8.5) — the one row in this table driven by team topology, not raw capacity |
| Availability requirement moves from 3 nines to 4 nines | A DEFINED SLO target (§16.5), not a traffic number | Active-active multi-region (§5.6) |

The pattern worth internalizing: **almost every architectural escalation
in this entire guide is justified by a number crossing a threshold, not by
an aesthetic preference for a "more sophisticated" pattern.** An architect
who can produce the number that justifies a design choice is making a
fundamentally different kind of argument than one who can only say "this
is best practice" — and this section is the toolkit for producing that
number quickly.

---

## 18. Error Recovery & Graceful Degradation

### 18.1 Building the Intuition: a Real Call Composes Multiple Patterns Built in Isolation

Circuit breakers (§8.2), bulkheads (§8.3), and cache stampede protection
(§4.4) were each built as standalone patterns, addressing one specific
failure mode. But a single real outbound call in production needs several
of these applied SIMULTANEOUSLY, and the question this section answers
first — genuinely new synthesis, not covered by any single earlier
section — is: **in what ORDER do you layer them around one call, and
why does the order actually matter?**

```
The four resilience concerns, and what each one bounds:
  TIMEOUT      bounds ONE attempt's duration
  RETRY        decides whether to make ANOTHER attempt after a failure
  CIRCUIT BREAKER  decides whether to attempt AT ALL, based on recent
                    aggregate outcomes (§8.2)
  BULKHEAD     bounds how many concurrent EXECUTIONS (including retries)
                are allowed against this dependency at once (§8.3)
```

**The correct nesting, reasoned through, not just asserted** — outermost
to innermost: `Bulkhead(CircuitBreaker(Retry(Timeout(call))))`

```
┌─────────────────────────────────────────────────────────────────┐
│  WHY TIMEOUT IS INNERMOST: it must bound a SINGLE attempt. If it        │
│  wrapped the retry loop instead, a slow dependency could consume the        │
│  ENTIRE timeout budget on attempt #1, leaving zero time for the retries          │
│  that were supposed to happen.                                                       │
│                                                                                          │
│  WHY RETRY WRAPS TIMEOUT (not the reverse): retry logic needs to see              │
│  the OUTCOME of one bounded attempt (succeeded, or timed out) before                     │
│  deciding whether a NEXT attempt is warranted — it operates one level                        │
│  up from the raw call.                                                                          │
│                                                                                                      │
│  WHY CIRCUIT BREAKER WRAPS RETRY (not the reverse): if the circuit is                                │
│  OPEN, you want to fail IMMEDIATELY, without even entering the retry                                    │
│  loop at all — if retry wrapped the circuit breaker instead, every                                          │
│  single retry attempt would separately re-check an open circuit and                                            │
│  immediately fail, wastefully looping through retry/backoff logic for                                              │
│  a call you already know won't be attempted.                                                                          │
│                                                                                                                            │
│  WHY BULKHEAD IS OUTERMOST: the bulkhead must cap TOTAL concurrent                                                        │
│  executions of this ENTIRE policy stack — including all retries a given             │
│  call might trigger. If it wrapped anything INSIDE retry, a single                     │
│  logical call's retries could each separately consume a bulkhead slot,                    │
│  defeating the bulkhead's whole purpose of capping how much of a shared                       │
│  resource (§8.3) one dependency can consume.                                                     │
└─────────────────────────────────────────────────────────────────┘
```

### 18.2 LLD: Retry with Jitter — the Full Algorithm, and Why Naive Jitter Isn't Enough

#### 18.2.1 Building the intuition beyond the basic formula

Earlier material introduced `delay = min(cap, base × 2^retry) ×
random(0.5, 1.5)` as "exponential backoff with jitter." This is better
than no jitter at all, but it's not the whole story — there are several
genuinely different jitter STRATEGIES, and the difference between them
matters under real concurrent load.

```
NO JITTER: delay = min(cap, base × 2^retry)
  Every client retries at EXACTLY the same moment after a shared outage —
  recreates the retry storm (§18.1's original motivating problem)
  completely, just delayed by the backoff interval instead of eliminated.

"EQUAL" JITTER: delay = (base × 2^retry)/2 + random(0, (base × 2^retry)/2)
  Half the backoff is fixed, half is randomized — guarantees SOME spread,
  but the fixed half still means every client's delay has a shared floor,
  so a partial synchronization pressure remains.

FULL JITTER (the AWS-recommended default): delay = random(0, base × 2^retry)
  The ENTIRE delay is randomized across the full computed range — no
  fixed floor at all, maximizing the spread of retry attempts across
  time, minimizing the odds of a renewed synchronized thundering herd.

DECORRELATED JITTER: delay = min(cap, random(base, previous_delay × 3))
  Each retry's delay is randomized based on the PREVIOUS delay rather
  than purely on the retry count — empirically spreads retries out even
  further than full jitter under sustained, repeated failure conditions,
  at the cost of being slightly less intuitive to reason about upfront.
```

#### 18.2.2 Class Diagram

```
┌─────────────────────────────────┐
│ RetryPolicy                          │
├─────────────────────────────────┤
│ - max_attempts: int                      │
│ - base_delay_ms: int                         │
│ - cap_ms: int                                    │
│ - jitter_strategy: enum{FULL, EQUAL, DECORRELATED}│
├─────────────────────────────────┤
│ + execute(fn) -> Result                                │
│     for attempt in range(max_attempts):                    │
│         try: return fn()                                       │
│         except RetryableError:                                     │
│             if attempt == max_attempts - 1: raise                      │
│             delay = compute_delay(attempt, jitter_strategy)                 │
│             sleep(delay)                                                       │
└─────────────────────────────────┘
```

### 18.3 LLD: the Composed Resilience Policy in Action

**Sequence — a single logical call, showing all four layers engaging, and
where a request can be short-circuited at each layer:**

```
Caller       Bulkhead      CircuitBreaker      RetryPolicy      Timeout       Downstream
  │  call()         │                                                                    │
  │──────────►│  slot available?                                                                │
  │            │  YES → acquire                                                                     │
  │            │──────────►│  state == CLOSED → proceed                                                 │
  │            │            │──────────►│  attempt 1                                                        │
  │            │            │            │──────────►│  (2s timeout wraps this ONE attempt)                     │
  │            │            │            │            │──────────►│                                              │
  │            │            │            │            │   X  (times out at 2s — downstream is slow)                  │
  │            │            │            │◄──────────│  TimeoutError                                                    │
  │            │            │            │  attempt 1 failed → compute FULL JITTER delay (§18.2.1),                        │
  │            │            │            │  sleep, then attempt 2                                                            │
  │            │            │            │──────────►│                                                                          │
  │            │            │            │            │──────────►│                                                                │
  │            │            │            │            │◄──────────│  SUCCESS this time                                                │
  │            │            │◄──────────│  success → record success in circuit breaker's sliding window   │
  │            │◄──────────│                                                                                                            │
  │◄──────────│  release bulkhead slot                                                                                                        │
```
**A DIFFERENT execution, where the circuit is already open — showing the
fail-fast short-circuit that avoids ever entering retry or timeout at
all:**

```
Caller       Bulkhead      CircuitBreaker
  │  call()         │
  │──────────►│  slot available → acquire
  │            │──────────►│  state == OPEN (recent failure rate crossed
  │            │            │  threshold) → FAIL IMMEDIATELY, no retry loop
  │            │            │  entered, no timeout clock started at all
  │            │◄──────────│  CircuitOpenError
  │◄──────────│  release bulkhead slot (held only briefly)
  │  caller receives the error almost instantly — NOT after waiting
  │  through a full retry-and-timeout sequence against a dependency
  │  already known to be failing
```

### 18.4 LLD: Graceful Degradation as a Designed Feature, Generalized

Section 2.6's search fallback chain (ES → Postgres → Redis trending →
exact match) was one CONCRETE instance of a general pattern worth
formalizing once: any feature can define its own **degradation ladder**,
with each rung explicitly labeled so the response is never silently
worse without the caller knowing.

```
┌─────────────────────────────────┐
│ DegradableFeature<T>                 │
├─────────────────────────────────┤
│ - rungs: List<(level: int, provider: () -> T)>│
│ + serve() -> DegradableResponse<T>              │
│     for level, provider in rungs:                   │
│         try:                                            │
│             return DegradableResponse(                       │
│                 data=provider(), degraded_level=level)           │
│         except: continue   # fall to the NEXT rung                  │
│     return DegradableResponse(data=None, degraded_level=MAX)            │
└─────────────────────────────────┘
```
**Applied to "recommendations" instead of search**: rung 0 = full
personalized ML-ranked recommendations; rung 1 = simple "trending in your
category" (cheap, cached, no personalization); rung 2 = a static
editorial list. A homepage that can't get rung 0 degrades to rung 1 or 2
rather than showing an error or an empty section — exactly the "hide
'related items' rather than fail the whole page" principle from §8.2,
now expressed as a reusable, generic component instead of a one-off if/else.

### 18.5 LLD: Verifying Resilience Actually Works — Chaos Engineering

#### 18.5.1 Building the intuition: untested resilience code is a hypothesis, not a guarantee

Every pattern in §18.1–§18.4 is code that ONLY runs during a failure —
which means, by construction, it's the LEAST-exercised code path in the
entire system. A circuit breaker that's never actually seen its
dependency fail in production is a hypothesis about what will happen, not
a verified guarantee — the only way to know it genuinely opens at the
right threshold and recovers correctly is to deliberately CAUSE the
failure, in a controlled way, and observe.

#### 18.5.2 Class Diagram — Fault Injection Middleware

```
┌─────────────────────────────────┐
│ FaultInjectionMiddleware             │
├─────────────────────────────────┤
│ - active_experiments: List<Experiment>  │
├─────────────────────────────────┤
│ + handle(request) -> Response               │
│     exp = find_matching_experiment(request)     │
│     if exp and exp.enabled:                         │
│         if random() < exp.injection_rate:               │
│             if exp.fault_type == "latency":                 │
│                 sleep(exp.latency_ms)                            │
│             elif exp.fault_type == "error":                          │
│                 raise InjectedFailure()                                  │
│     return call_next(request)                                                │
└─────────────────────────────────┘
```

```sql
CREATE TABLE chaos_experiments (
    experiment_id    TEXT PRIMARY KEY,
    target_route      TEXT NOT NULL,
    fault_type        TEXT NOT NULL CHECK (fault_type IN ('latency','error')),
    injection_rate     FLOAT NOT NULL,       -- e.g. 0.05 = 5% of matching requests
    latency_ms          INTEGER,
    enabled              BOOLEAN NOT NULL DEFAULT false,
    kill_switch_triggered BOOLEAN NOT NULL DEFAULT false,  -- see 18.5.3
    max_blast_radius_pct  FLOAT NOT NULL     -- e.g. never affect more than
                                                -- 5% of TOTAL production
                                                -- traffic, regardless of
                                                -- injection_rate on the
                                                -- targeted route alone
);
```

#### 18.5.3 Sequence — a Controlled Experiment Validating the Circuit Breaker

```
Operator                FaultInjectionMiddleware       CircuitBreaker      Monitoring
  │  enable experiment: inject 500ms latency into           │                    │
  │  10% of calls to Payment-Svc, blast_radius capped at 5%      │                    │
  │────────────────────►│                                             │                    │
  │                       │  (production traffic flows normally,          │                    │
  │                       │   10% of Payment-Svc calls now                    │                    │
  │                       │   experience injected 500ms delay)                    │                    │
  │                       │                                                           │                    │
  │                       │  the ALREADY-BUILT circuit breaker (§8.2)                     │                    │
  │                       │  observes the elevated failure/timeout rate                       │                    │
  │                       │  from these injected delays and TRIPS OPEN                             │                    │
  │                       │  exactly as designed                                                        │                    │
  │                                                                                                         │  dashboards show:
  │                                                                                                         │  circuit opened,
  │                                                                                                         │  fallback engaged,
  │                                                                                                         │  overall checkout
  │                                                                                                         │  success rate stayed
  │                                                                                                         │  above the SLO (§16.5)
  │  RESULT: the experiment PROVED the circuit breaker behaves correctly            │                    │
  │  under real, controlled failure — not just in a unit test — with a                 │                    │
  │  known, capped blast radius (5% of traffic) and an automatic kill switch:              │                    │
  │  if overall error rate breaches a safety threshold DURING the experiment,               │                    │
  │  the experiment auto-disables itself immediately, regardless of the                       │                    │
  │  operator's original schedule                                                                 │                    │
```
**The steady-state hypothesis discipline this follows**: define what
"normal" looks like BEFORE the experiment (checkout success rate, p99
latency), inject the fault, and confirm the system's OVERALL behavior
stays within acceptable bounds despite the injected failure — the goal
isn't "break something," it's "prove the system tolerates this specific,
already-anticipated failure mode as designed," with the blast radius and
kill switch ensuring a genuinely wrong assumption can't turn a controlled
experiment into a real incident.

---

## 19. Architect Deliverables: RFCs, Trade-off Docs & ADRs

*(To be detailed in a subsequent pass.)*