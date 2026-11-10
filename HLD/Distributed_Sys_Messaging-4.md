# Distributed Systems & Messaging — Sections 5–9 
### 8. Microservices Patterns
### 9. Distributed Transactions & Data Consistency

----

## 8. Microservices Patterns

### 8.1 Building the Intuition: Not Everything Can Be Made Async

Section 7 solved chained-failure risk by removing synchrony entirely
where possible — but some interactions genuinely can't be made
asynchronous: a checkout flow needs to know **right now** whether the
payment succeeded before it can show the user a confirmation page. Wherever
synchronous service-to-service calls remain necessary, §5.6's chained-
availability math still applies in full force — and the patterns in this
section exist specifically to contain the blast radius of a struggling
synchronous dependency, rather than eliminate the synchrony itself.

### 8.2 Circuit Breaker — Building Up From "Why Does One Slow Service Take Down Everything?"

#### 8.2.1 The cascading failure, step by step

```
┌─────────────────────────────────────────────────────────────────┐
│  Service B becomes SLOW (not down — every request eventually            │
│  succeeds, just after 25 seconds instead of 50ms).                          │
│                                                                                  │
│  Service A calls B synchronously, with a 30-second timeout. Every                  │
│  in-flight call to B now holds one of A's limited worker threads (or                  │
│  connection-pool slots) for nearly the full 30 seconds.                                  │
│                                                                                                │
│  If requests to B arrive faster than B can drain them, A's threads FILL UP              │
│  with calls all waiting on B — and once A's thread pool is exhausted, A CAN'T              │
│  serve ANY request anymore, including ones that have NOTHING to do with B.                     │
│                                                                                                      │
│  Now A itself looks "down" to ITS callers — the slowness has propagated                                │
│  upward through the call chain, even though every individual timeout was                                  │
│  technically "working correctly." This is the cascading failure §5.6's math                                   │
│  warned about, made concrete.                                                                                    │
└─────────────────────────────────────────────────────────────────┘
```
The fix can't be "just lower the timeout" — a shorter timeout still gets
exhausted by enough concurrent requests, just faster. The real fix has to
be behavioral: **after enough recent calls to B have failed or timed out,
stop calling B at all for a while**, freeing A's resources immediately
instead of letting them be consumed by calls that are statistically very
likely to fail anyway.

#### 8.2.2 Class Diagram

```
┌─────────────────────────────────┐
│ CircuitBreaker                       │
├─────────────────────────────────┤
│ - state: enum{CLOSED, OPEN, HALF_OPEN}   │
│ - failure_window: SlidingWindow<bool>       │  # tracks recent call
│ - failure_threshold: float = 0.5                │  # outcomes — NOT just a
│ - open_duration_seconds: int = 30                   │  raw consecutive-failure
│ - half_open_max_probes: int = 1                        │  counter, so one old
├─────────────────────────────────┤                       │  failure from an hour
│ + call(fn) -> Result                                       │  ago doesn't linger
│     if state == OPEN:                                          │  and skew the decision
│         if time_since_opened() < open_duration_seconds:            │
│             raise CircuitOpenError()   # fail FAST, don't even        │
│                                          # attempt the network call      │
│         else: state = HALF_OPEN                                             │
│     if state == HALF_OPEN and probes_in_flight >= half_open_max_probes: │
│         raise CircuitOpenError()   # only let a LIMITED number of          │
│                                       # test requests through, not a          │
│                                       # full flood the instant it opens          │
│     try:                                                                            │
│         result = fn()                                                                   │
│         failure_window.record(success=True)                                                │
│         if state == HALF_OPEN: state = CLOSED   # probe succeeded, trust restored   │
│         return result                                                                          │
│     except:                                                                                        │
│         failure_window.record(success=False)                                                          │
│         if state == HALF_OPEN: state = OPEN     # probe failed, not recovered yet          │
│         elif failure_window.failure_rate() > failure_threshold: state = OPEN                  │
│         raise                                                                                            │
└─────────────────────────────────┘
```

#### 8.2.3 Sequence — Full Lifecycle Through All Three States

```
Caller              CircuitBreaker              Service B (degrading)
  │  call() #1-10, all succeed normally               │
  │───────────►│───────────────────────────────►│
  │◄───────────│◄───────────────────────────────│  (state stays CLOSED)
  │  ...Service B starts failing...                         │
  │  call() #11-20, 12 of them fail/timeout                    │
  │───────────►│───────────────────────────────►│
  │             │  failure_rate() now > 50% threshold      │
  │             │  state → OPEN                                 │
  │  call() #21                                                     │
  │───────────►│  state==OPEN, within open_duration → FAIL FAST,        │
  │◄───────────│  NEVER even attempts the network call to B                  │
  │  (30 seconds pass — B has time to recover, e.g. its own          │
  │   downstream dependency comes back, GC pressure subsides,             │
  │   an autoscaler adds capacity)                                            │
  │  call() #22                                                                  │
  │───────────►│  open_duration elapsed → state → HALF_OPEN,                        │
  │             │  allow exactly 1 probe through                                        │
  │             │───────────────────────────────►│
  │             │◄───────────────────────────────│  SUCCESS
  │◄───────────│  probe succeeded → state → CLOSED, full traffic resumes  │
```
**Why the recovery check is "a percentage over a sliding window," not "N
consecutive failures"**: a single consecutive-failure counter can be
skewed by one old failure from long ago still counting toward the
threshold, or reset by one lucky success in the middle of a genuine
outage. A sliding window of recent outcomes (e.g. last 20 calls, or last
10 seconds) reflects the CURRENT health of the dependency, which is the
only thing that should drive the open/closed decision.

### 8.3 Bulkhead — Building Up From "the Circuit Breaker Alone Isn't Enough"

#### 8.3.1 The problem circuit breakers don't solve

Suppose Service A calls THREE downstream services — X, Y, Z — all through
one shared thread pool. A circuit breaker on the call to X will correctly
stop calling X once X starts failing... but **until that threshold is
crossed**, every slow call to X is still occupying a thread from the SAME
shared pool that calls to Y and Z also need. If X is merely slow (not yet
failing enough to trip the breaker), it can still starve Y and Z of
threads purely by occupying the shared pool — Y and Z might be perfectly
healthy and still can't get served.

```
┌─────────────────────────────────────────────────────────────────┐
│  WITHOUT BULKHEAD                    WITH BULKHEAD                     │
│  Shared pool: 50 threads                Pool-X: 20 threads (dedicated)     │
│  X is slow → 45 threads stuck            Pool-Y: 20 threads (dedicated)       │
│  waiting on X → only 5 threads              Pool-Z: 10 threads (dedicated)         │
│  left for Y and Z combined                                                            │
│  ❌ Y and Z requests queue up or fail       X's slowness can consume ALL 20 of           │
│     purely due to resource starvation,       Pool-X's threads, but Pool-Y and              │
│     even though Y and Z themselves            Pool-Z are PHYSICALLY SEPARATE               │
│     never had a single problem                threads — they cannot be touched                │
│                                                by whatever is happening to X                      │
└─────────────────────────────────────────────────────────────────┘
```

#### 8.3.2 Class Diagram

```
┌─────────────────────────────────┐
│ BulkheadRegistry                    │
├─────────────────────────────────┤
│ - pools: Map<dependency_name, Bulkhead>  │
│ + get_or_create(dependency_name, max_concurrent) -> Bulkhead│
└─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│ Bulkhead                             │
├─────────────────────────────────┤
│ - semaphore: Semaphore(max_concurrent)   │  # a semaphore, not a full OS
│ - queue_capacity: int                       │  # thread pool, is often the
├─────────────────────────────────┤              # lighter-weight, sufficient
│ + execute(fn) -> Result                            │  implementation — it just
│     if not semaphore.try_acquire():                    │  caps CONCURRENT calls to
│         raise BulkheadFullError()                          │  this one dependency,
│     try: return fn()                                           │  independent of any other
│     finally: semaphore.release()                                   │  dependency's pool
└─────────────────────────────────┘
```
**The combined pattern in practice**: a circuit breaker and a bulkhead are
usually wrapped around the SAME call, addressing two different failure
dimensions — the bulkhead caps how many concurrent calls to X can ever be
in flight (protecting other dependencies from resource starvation), while
the circuit breaker decides whether to keep attempting calls to X at all
once its failure rate crosses a threshold (protecting A's own resources
from being wasted on a dependency very likely to fail).

### 8.4 API Gateway — Building Up From "Every Client Talking to Every Service Directly"

#### 8.4.1 What breaks without one

```
┌─────────────────────────────────────────────────────────────────┐
│  Without a gateway: the mobile app, web app, and third-party partners │
│  must each know the network address of EVERY microservice, and each        │
│  must independently implement TLS termination, authentication, and             │
│  rate limiting — meaning these cross-cutting concerns get reimplemented           │
│  N times (once per client) instead of once, and every service must be                │
│  reachable directly from the public internet, expanding the attack surface.          │
└─────────────────────────────────────────────────────────────────┘
```
The fix centralizes exactly the concerns that don't belong to any single
business service: TLS termination, authentication, rate limiting, and
routing — behind one entry point every client talks to instead.

#### 8.4.2 Class Diagram

```
┌─────────────────────────────────┐
│ ApiGateway                          │
├─────────────────────────────────┤
│ - routes: List<Route>                   │
│ - middleware_chain: List<Middleware>        │  # ordered: TLS terminate →
├─────────────────────────────────┤              # authenticate → rate limit →
│ + handle(request) -> Response                     # route
│     for mw in middleware_chain:                        │
│         request = mw.process(request)  # may short-       │
│                                            # circuit with an   │
│                                            # error response      │
│     route = match_route(request.path)                              │
│     return forward(request, route.backend_url)                        │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│ Route                                │
├─────────────────────────────────┤
│ + path_pattern: string                   │  # e.g. "/api/v1/orders/**"
│ + backend_service: string                    │  # e.g. "order-service.internal:8000"
│ + required_scopes: List<string>                  │
└─────────────────────────────────┘
```

**Sequence — a request passing through the full middleware chain:**

```
Client        Gateway          AuthMiddleware    RateLimitMiddleware   Order-Service
  │ GET /api/v1/orders/42          │                     │                    │
  │─────────►│                                                │                    │
  │           │  verify JWT (§13's mechanism, unchanged)              │                    │
  │           │────────────────►│                                        │                    │
  │           │◄────────────────│  valid, roles=[customer]                   │                    │
  │           │  check rate limit for this user/IP (§2's token          │                    │
  │           │  bucket, unchanged mechanism, just enforced HERE            │                    │
  │           │  instead of in each individual service)                        │                    │
  │           │───────────────────────────────►│                                    │                    │
  │           │◄───────────────────────────────│  under limit, proceed                │                    │
  │           │  match_route("/api/v1/orders/42") → order-service              │                    │
  │           │───────────────────────────────────────────────────────────►│
  │◄─────────│◄───────────────────────────────────────────────────────────│  200 OK
```
Notice that Order-Service itself never had to implement JWT verification
or rate limiting at all — those concerns were fully absorbed by the
gateway, which is precisely the point.

#### 8.4.3 API Contract — Admin Route Registration

```yaml
paths:
  /admin/routes:
    post:
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                path_pattern: { type: string, example: "/api/v1/orders/**" }
                backend_service: { type: string, example: "order-service.internal:8000" }
                required_scopes: { type: array, items: { type: string } }
                rate_limit_per_minute: { type: integer }
```
**The BFF (Backend-For-Frontend) variant**: rather than one universal
gateway config for every client, some organizations run a SEPARATE gateway
instance per client type (mobile-BFF, web-BFF) — each shaped around that
specific client's needs (a mobile BFF might aggregate three backend calls
into one response to save round trips on a cellular connection; a web BFF
might not need to). This is the same gateway pattern, just deliberately
NOT shared across all client types when their needs genuinely diverge.

### 8.5 Service Mesh — Building Up From "the Gateway Only Covers Half the Traffic"

#### 8.5.1 North-south vs east-west, and why the gateway doesn't help internally

The API Gateway (§8.4) sits at the boundary between external clients and
your services — this is usually called **north-south traffic**. But
services also call EACH OTHER internally (order-service calls
inventory-service calls payment-service) — **east-west traffic** — and
the gateway, sitting only at the perimeter, has no visibility into or
control over any of it. Without something addressing this, every service
must reimplement mTLS, retries, and circuit breaking (§8.2) itself, in
whatever language it happens to be written in — the exact same
"reimplemented N times" problem the gateway solved externally, just
recurring internally.

#### 8.5.2 The Sidecar Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│  Instead of each service's OWN code implementing mTLS/retries/           │
│  circuit-breaking, a SIDECAR PROXY (Envoy) runs alongside every            │
│  service instance and transparently intercepts ALL its inbound and            │
│  outbound network traffic — the application code doesn't change AT ALL,          │
│  it just makes normal HTTP calls to "localhost," unaware a proxy is                 │
│  actually handling the real network hop.                                                │
│                                                                                              │
│      Service A          Service B                                                              │
│      ┌────────┐         ┌────────┐                                                                │
│      │  App   │         │  App   │  (application code — completely unaware                          │
│      ├────────┤  mTLS   ├────────┤   of the mesh, just calls localhost)                                │
│      │ Sidecar│◄───────►│ Sidecar│  (Envoy — handles mTLS, retries, circuit                              │
│      │ (Envoy)│         │ (Envoy)│   breaking, and emits tracing spans for                                  │
│      └────────┘         └────────┘   EVERY hop, transparently)                                                │
│           ▲                   ▲                                                                                    │
│           └── Control Plane ──┘  (Istio/Linkerd — pushes routing rules,                                              │
│                                    certificates, and policy to every                                                    │
│                                    sidecar; sidecars are the DATA PLANE                                                    │
│                                    that actually handles traffic)                                                              │
└─────────────────────────────────────────────────────────────────┘
```

**Sequence — Service A calling Service B, with the sidecar handling
everything transparently:**

```
Service A App    A's Sidecar        B's Sidecar        Service B App
   │  HTTP GET to "localhost:9000/api"    │                    │
   │─────────────►│                             │                    │
   │               │  looks up routing rule (pushed by control     │
   │               │  plane): "this path → service-b, use mTLS"       │
   │               │  initiates mTLS handshake with B's sidecar            │
   │               │────────────────────────────►│                            │
   │               │◄────────────────────────────│  mTLS established,             │
   │               │                                 CERTIFICATE VERIFIED               │
   │               │  forwards the actual request over the encrypted tunnel   │
   │               │────────────────────────────►│                                 │
   │               │                                 │  forwards to Service B's app       │
   │               │                                 │  over plain localhost (B's app         │
   │               │                                 │  never even sees TLS directly)              │
   │               │                                 │───────────────────────────────►│
   │◄─────────────│◄────────────────────────────│◄───────────────────────────────│
```

#### 8.5.3 Config Example — Circuit Breaking Enforced at the Mesh Layer

```yaml
# Envoy cluster config — the EXACT §8.2 circuit breaker logic, now
# enforced transparently for every service without any application code
clusters:
  - name: payment-service
    circuit_breakers:
      thresholds:
        - priority: DEFAULT
          max_connections: 100
          max_pending_requests: 50
          max_retries: 3
    outlier_detection:
      consecutive_5xx: 5
      base_ejection_time: 30s
```

**The trade-off to state explicitly, because it's real**: a mesh gives
every service consistent mTLS, retries, and circuit breaking "for free" —
but it's genuine operational complexity (a control plane to run, certs to
rotate, another moving part in every request path) and adds a small but
real latency cost per hop. Below roughly 10-15 services, a good API
gateway plus disciplined use of a shared client library (a Resilience4j/
Polly wrapper every team imports) usually delivers most of the benefit
without the mesh's operational weight — the mesh earns its cost specifically
once the number of services and languages involved makes "just use a
shared library everywhere" impractical to enforce.

### 8.6 Strangler Fig — Building Up From Why "Big Bang" Rewrites Fail

#### 8.6.1 The intuition: the moving-target problem

The obvious way to replace a monolith is to build the new system
completely, then cut over in one release. The problem: **the old
monolith doesn't stop changing while the rewrite is in progress.** Product
requirements keep shipping to the old system throughout the (often
multi-year) rewrite; by the time the new system is "done," it's actually
behind, missing everything the monolith gained in the meantime — this is
the well-documented failure mode behind nearly every famous "rewrite that
never shipped."

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1:  [ Router ] → ALL traffic → [ Monolith ]                     │
│            (router exists from day one, even though it does nothing        │
│            yet except pass everything through — this is deliberate,          │
│            so adding new-service routes later is a config change, not             │
│            a new architectural component introduced under pressure)                  │
│                                                                                          │
│  Phase 2:  [ Router ] → /checkout → [ New Checkout Service ]                              │
│                       → everything else → [ Monolith ]  (unchanged, still            │
│                                             receiving normal ongoing feature work)         │
│                                                                                                │
│  Phase 3:  more routes peeled off incrementally, monolith shrinks feature                        │
│            by feature, EACH migrated piece independently validated in                                │
│            production before the next one starts                                                        │
│                                                                                                                │
│  Phase 4:  [ Router ] → mostly [ New Services ], monolith fully retired                                          │
└─────────────────────────────────────────────────────────────────┘
```
This directly avoids the moving-target problem: at every phase, the
system in production is a WORKING mix of old and new, never a big-bang
switch where months of untested integration risk gets discovered all at
once on cutover day.

#### 8.6.2 The Hard Part That's Easy to Underestimate: Data Ownership During Migration

```
┌─────────────────────────────────────────────────────────────────┐
│  The monolith's database still holds the authoritative "orders" table.   │
│  The new Checkout Service needs to read AND write order data too — but      │
│  which system actually owns it during the transition?                          │
│                                                                                     │
│  Option A: New service calls back into the monolith's API for anything            │
│  it doesn't own yet — simplest to reason about, but couples the new                    │
│  service's latency/availability to the monolith it's supposed to be                        │
│  replacing (exactly the chained-dependency problem from §5.6, now                             │
│  introduced ON PURPOSE as a deliberate, TEMPORARY transitional cost).                              │
│                                                                                                        │
│  Option B: Dual-write to both the monolith's DB and the new service's DB               │
│  during the transition, with a CDC pipeline (the exact same mechanism                       │
│  from §2.6.5's Elasticsearch reindex-from-source-of-truth discipline)                            │
│  keeping them in sync until the new service is confidently the sole owner.                          │
│  More engineering effort up front, but decouples the new service's                                     │
│  availability from the monolith sooner.                                                                    │
└─────────────────────────────────────────────────────────────────┘
```
Choosing between these options for each migrated slice — not just "we're
doing the strangler fig pattern" in the abstract — is the actual
architectural decision a senior engineer is expected to make explicit in
a migration's design doc (§19.2's trade-off document is exactly the right
artifact for this).

---


## 9. Distributed Transactions & Data Consistency

### 9.1 Building the Intuition: What a Monolith Gave You For Free

In a monolith, a checkout flow touching orders, inventory, and payments is
typically one single ACID database transaction: `BEGIN; INSERT order;
UPDATE inventory; INSERT payment; COMMIT;`. If ANY step fails, the database
itself guarantees the whole thing rolls back atomically — you never see a
half-finished checkout. This was never something you had to design; it was
a free property of everything living in one database with one transaction
manager.

The moment you split Order, Inventory, and Payment into separate services —
each deliberately given its OWN database, specifically so each can scale,
deploy, and evolve its schema independently (§3's entire premise) — **you
have knowingly given up that single-transaction guarantee as the direct
cost of that independence.** The question this section answers: given
you've made that trade on purpose, how do you get *some* form of "all
three succeed, or none meaningfully do" back, across three separate
databases with no shared transaction manager?

### 9.2 Two-Phase Commit — the Obvious Fix, and Exactly Why It's Dangerous

#### 9.2.1 Building it up: what would "just coordinate them" look like?

The direct instinct: introduce a coordinator. Before anyone commits
anything, ask every participant "are you SURE you can commit this?" — have
them lock their resources and confirm — and only once everyone has said
yes does the coordinator tell everyone to actually commit.

```
PHASE 1 (PREPARE): coordinator asks every participant "can you commit?"
  Each participant locks the relevant rows/resources and replies YES or NO,
  WITHOUT yet actually committing.
PHASE 2 (COMMIT/ABORT): if ALL replied YES, coordinator tells everyone to
  COMMIT. If ANY replied NO, coordinator tells everyone to ABORT.
```
This genuinely does give you atomicity across multiple databases — as
long as everyone communicates successfully.

#### 9.2.2 Building the failure intuition: the exact moment this becomes dangerous

Ask the one question that always breaks a two-phase protocol: **what
happens if the coordinator crashes AFTER phase 1 (everyone said YES,
locked their resources) but BEFORE sending the phase 2 decision?**

```
┌─────────────────────────────────────────────────────────────────┐
│  Participant A: voted YES, is now holding a lock on its row(s),      │
│  WAITING to be told commit or abort.                                    │
│  Coordinator: CRASHED. Will not send a decision until it restarts          │
│  (which might be minutes, might be much longer).                              │
│                                                                                    │
│  Participant A CANNOT unilaterally decide what to do:                                │
│    - It can't commit on its own — what if another participant voted NO           │
│      and the coordinator was about to tell everyone to abort?                        │
│    - It can't abort on its own either — what if every OTHER participant                 │
│      also voted YES and the coordinator WAS about to say commit?                          │
│  Participant A is stuck holding its lock — BLOCKING any other transaction                    │
│  that needs those same rows — until the coordinator comes back and tells                        │
│  it what happened. This is why 2PC is called a BLOCKING protocol, and                              │
│  it's precisely the same "unilateral decision is unsafe" problem from                                  │
│  §6.1's split-brain reasoning, just manifesting as indefinite unavailability                              │
│  instead of a wrong decision.                                                                                │
└─────────────────────────────────────────────────────────────────┘
```

**Class diagram and sequence — the exact failure:**

```
┌─────────────────────────┐        ┌──────────────────────┐
│ TwoPhaseCoordinator          │        │ Participant                │
├─────────────────────────┤        ├──────────────────────┤
│ + prepare_all() -> List<Vote>   │        │ + prepare() -> Vote           │
│ + commit_all() / abort_all()       │        │ + commit() / abort()              │
└─────────────────────────┘        │ + state: enum{ACTIVE, PREPARED,│
                                    │   COMMITTED, ABORTED}              │
                                    └──────────────────────┘
```

```
Coordinator          Participant-A (Orders)     Participant-B (Payments)
   │  PREPARE            │                            │
   │────────────────────►│                                │
   │────────────────────────────────────────────────────►│
   │◄────────────────────│  VOTE: YES (locked)                │
   │◄────────────────────────────────────────────────────│  VOTE: YES (locked)
   │  (coordinator now knows it SHOULD tell both to COMMIT) │
   │   X  (coordinator crashes right here — before sending      │
   │       the COMMIT message to either participant)                │
   │                     │  Participant-A: state=PREPARED,          │
   │                     │  holding its lock, waiting...                │
   │                                                    │  Participant-B: state=PREPARED,
   │                                                    │  ALSO holding its lock, waiting...
   │                     │  BOTH participants are now BLOCKED — neither can safely
   │                     │  proceed OR safely release its lock — until the
   │                     │  coordinator restarts and tells them the decision it
   │                     │  never got to send
```
This is why 2PC, despite giving genuine atomicity, is rarely used across
service boundaries in modern microservice architectures — the availability
cost of this blocking failure mode is usually judged worse than the
consistency it buys, which motivates §9.3's fundamentally different trade.

### 9.3 Saga Pattern — Trading Atomicity for Availability, Explicitly

#### 9.3.1 The intuition: why you can't just "roll back," and what to do instead

Saga's starting insight is blunt: **give up the "everyone locks and waits"
approach entirely.** Each step commits as its OWN independent local ACID
transaction, immediately, with no cross-service locking at all. If a LATER
step fails, you don't roll back the earlier ones (you can't — they're
already committed, and the outside world may have already acted on them:
a payment processor may have already moved real money, an email may have
already been sent). Instead, you run a **compensating transaction** — a
new operation that semantically undoes the effect of the earlier step,
rather than a database-level rollback of it.

```
This distinction is the entire idea:
  ROLLBACK undoes an operation that never actually completed/committed.
  COMPENSATION undoes the REAL-WORLD EFFECT of an operation that DID
    complete — "refund the payment" is a compensation for "charge the
    payment," not a rollback of it, because the charge genuinely happened.
```
The cost of this trade is real and must be stated explicitly in any design
review: **there is now a window of time where the system is in a visibly
inconsistent intermediate state** (e.g., "order: pending payment
confirmation") — this must be designed for, not hidden, exactly like every
other eventual-consistency trade-off in this guide (§1.3's staleness
transparency principle applies here too).

#### 9.3.2 LLD: Orchestration — a Central Saga Coordinator

**Class diagram:**

```
┌─────────────────────────────────┐
│ SagaOrchestrator                    │
├─────────────────────────────────┤
│ - steps: List<SagaStep>                 │
├─────────────────────────────────┤
│ + execute(saga_id, context)                 │
│     completed = []                              │
│     for step in steps:                             │
│         try:                                           │
│             step.action(context)                          │
│             persist_progress(saga_id, step, DONE)             │
│             completed.append(step)                                │
│         except:                                                       │
│             for done_step in reversed(completed):                        │
│                 done_step.compensation(context)                              │
│                 persist_progress(saga_id, done_step, COMPENSATED)                │
│             raise SagaFailedError()                                                  │
└─────────────────────────────────┘
            │ composed of
            ▼
┌─────────────────────────────────┐
│ SagaStep                             │
├─────────────────────────────────┤
│ + action(context) -> void                │
│ + compensation(context) -> void  # MUST be idempotent (§1.5) — a          │
│                                     # crashed-and-retried compensation       │
│                                     # can't be allowed to double-refund         │
└─────────────────────────────────┘
```

**Database schema — durable saga state (critical: without this, an
orchestrator crash mid-saga loses track of what needs compensating):**

```sql
CREATE TABLE saga_instances (
    saga_id       UUID PRIMARY KEY,
    saga_type     TEXT NOT NULL,        -- e.g. "checkout"
    status        TEXT NOT NULL CHECK (status IN
                    ('IN_PROGRESS','COMPLETED','COMPENSATING','FAILED')),
    context       JSONB NOT NULL,        -- order_id, amount, etc.
    current_step  INTEGER NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE saga_step_log (
    saga_id       UUID NOT NULL REFERENCES saga_instances(saga_id),
    step_index    INTEGER NOT NULL,
    step_name     TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN
                    ('PENDING','DONE','COMPENSATED','COMPENSATION_FAILED')),
    completed_at  TIMESTAMPTZ,
    PRIMARY KEY (saga_id, step_index)
    -- this log is EXACTLY what lets a crashed orchestrator, upon restart,
    -- know precisely which steps succeeded and therefore which
    -- compensations still need to run — without it, a mid-saga crash
    -- would lose track of state completely
);
```

**Sequence — a failure midway through, with compensations run in reverse:**

```
Orchestrator      OrderService    PaymentService    InventoryService
   │  action: create order              │                │                    │
   │────────────────►│                                       │                    │
   │◄────────────────│  DONE — persisted to saga_step_log           │                    │
   │  action: charge payment                 │                                        │
   │─────────────────────────────────►│                                                │
   │◄─────────────────────────────────│  DONE — persisted                                  │
   │  action: reserve inventory                                     │                        │
   │───────────────────────────────────────────────────────────►│                        │
   │◄───────────────────────────────────────────────────────────│  FAILS (item out of stock)│
   │                                                                                          │
   │  Failure detected — begin COMPENSATION in REVERSE order (undo the                         │
   │  most recently completed step FIRST, since later steps may causally               │
   │  depend on earlier ones having happened):                                                │
   │  compensation: refund payment            │                                                    │
   │─────────────────────────────────►│                                                                │
   │◄─────────────────────────────────│  refunded, persisted as COMPENSATED                                │
   │  compensation: cancel order            │                                                                    │
   │────────────────►│                                                                                        │
   │◄────────────────│  cancelled, persisted as COMPENSATED                                                        │
   │  saga_instances.status = FAILED (fully compensated)                                                                │
```
**Why reverse order specifically**: later steps were built assuming
earlier steps' effects existed (inventory reservation logic might assume
a valid order already exists) — undoing in the same forward order could
attempt to, e.g., cancel an order while a compensation for a later step
still implicitly depends on it existing. Reverse order mirrors exactly how
you'd manually unwind a stack of dependent operations.

**API contract:**

```yaml
paths:
  /sagas/{saga_id}/status:
    get:
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  status: { type: string, enum: [IN_PROGRESS, COMPLETED, COMPENSATING, FAILED] }
                  current_step: { type: integer }
                  steps:
                    type: array
                    items:
                      type: object
                      properties:
                        name: { type: string }
                        status: { type: string }
```

#### 9.3.3 LLD: Choreography — No Central Coordinator, Event-Driven

Choreography achieves the same outcome without a central orchestrator —
each service reacts to events from the previous step and publishes its own
event when done, using exactly the Kafka pub/sub mechanism from §7.

```
Order Service          Payment Service         Inventory Service
   │  publishes OrderCreated                       │                    │
   │──────────────────────────►│                    │                    │
   │                            │  consumes it, charges payment,             │
   │                            │  publishes PaymentCharged (or               │
   │                            │  PaymentFailed)                                │
   │                            │───────────────────────────►│                     │
   │                            │                                │  consumes PaymentCharged,    │
   │                            │                                │  reserves inventory,            │
   │                            │                                │  publishes InventoryReserved       │
   │                            │                                │  (or InventoryOutOfStock)             │
   │                                                             │                                          │
   │  ─── failure case: Inventory publishes InventoryOutOfStock ───                                            │
   │◄────────────────────────────────────────────────────────────│                                          │
   │  Order Service is SUBSCRIBED to this failure event too — it reacts     │
   │  by cancelling the order (its own compensation), AND Payment Service       │
   │  is ALSO independently subscribed to InventoryOutOfStock, reacting            │
   │  by refunding the charge — NO central coordinator told either of them             │
   │  to do this; each service's own subscription list encodes its own                    │
   │  compensating reaction.
```
**The trade-off versus orchestration, stated plainly**: choreography has
no single point of coordination failure (there's no orchestrator process
to crash and lose track of saga state) — but tracing "what actually
happened during this checkout" now means reconstructing a timeline by
grepping event logs across three separate services, rather than reading
one `saga_instances` row. This is a genuine debuggability cost that grows
with the number of steps involved, and is exactly why orchestration is
often preferred once a saga has more than a handful of steps, despite
reintroducing a coordinating component.

### 9.4 The Outbox Pattern — Solving the Dual-Write Problem That Sagas Depend On

#### 9.4.1 Building the intuition: the exact gap choreography (and CQRS, §7.6) silently assumes away

Look closely at what Choreography (§9.3.3) requires of Payment Service:
when it finishes charging a payment, it must (1) commit that fact to its
own local database AND (2) publish a `PaymentCharged` event to Kafka. These
are two SEPARATE systems, with no shared transaction. **What happens if the
process crashes after step 1 commits but before step 2 publishes?**

```
┌─────────────────────────────────────────────────────────────────┐
│  Payment Service commits "payment charged" to its local Postgres         │
│  database. SUCCESS. Before it can also publish PaymentCharged to             │
│  Kafka, the process crashes (deploy, OOM kill, hardware failure —                │
│  doesn't matter which).                                                              │
│                                                                                          │
│  Result: the payment genuinely happened (it's durably committed in the                     │
│  database) — but NO EVENT was ever published. Inventory Service, waiting                       │
│  on PaymentCharged to proceed, never hears about it. The saga is now                               │
│  silently STUCK FOREVER, with no error, no timeout, no compensation                                    │
│  triggered — just an order that never progresses, and nobody watching                                    │
│  would even know why.                                                                                        │
└─────────────────────────────────────────────────────────────────┘
```
This is the exact same category of problem as §1.5's idempotency
motivation (two things need to happen together, but the infrastructure
doesn't make them atomic) — just relocated to "commit a row" + "publish an
event" instead of "process a request" + "acknowledge it."

#### 9.4.2 The fix: reuse the ONE atomic guarantee you still have

The insight: you still have a real ACID transaction available — **within
a single service's own database.** So instead of writing to the DB and
separately publishing to Kafka, write the business row AND a record of
"this event needs to be published" to the SAME database, in the SAME local
transaction. A separate process then reads that outbox table and publishes
to Kafka asynchronously, retrying until it succeeds — but the FACT that
publishing is needed is never lost, because it's as durable as the
business row itself.

**Class diagram:**

```
┌─────────────────────────────────┐
│ PaymentService                      │
├─────────────────────────────────┤
│ + charge_payment(order_id, amount)      │
│     BEGIN TRANSACTION                       │
│       INSERT INTO payments (...)                │
│       INSERT INTO outbox_events                     │  # SAME transaction —
│         (event_type="PaymentCharged", payload)          │  either BOTH rows exist
│     COMMIT                                                  │  after commit, or NEITHER
└─────────────────────────────────┘                              │  does. No dual-write gap.
            │
            ▼
┌─────────────────────────────────┐
│ OutboxRelay (separate process)      │
├─────────────────────────────────┤
│ + poll_and_publish()                    │
│     unpublished = SELECT * FROM outbox_events    │
│                    WHERE published=false            │
│     for event in unpublished:                           │
│         kafka.publish(event)                                │
│         UPDATE outbox_events SET published=true                │
└─────────────────────────────────┘
```

**Sequence — the crash scenario from §9.4.1, now survived correctly:**

```
PaymentService      Postgres            OutboxRelay          Kafka
  │  BEGIN               │                     │                  │
  │  INSERT payments          │                     │                  │
  │  INSERT outbox_events         │                     │                  │
  │  COMMIT                          │                     │                  │
  │──────────────────►│                                        │                  │
  │◄──────────────────│  SUCCESS — BOTH rows durably committed         │                  │
  │   X  (process crashes RIGHT HERE, before ever                       │                  │
  │       talking to Kafka directly)                                          │                  │
  │                       │  (nothing lost — the outbox_events row              │                  │
  │                       │   survived the crash because it was part               │                  │
  │                       │   of the same committed transaction)                        │                  │
  │                       │◄────────────────────│  poll_and_publish()                        │                  │
  │                       │  SELECT unpublished  │                                                │                  │
  │                       │─────────────────────►│  finds the row from BEFORE the crash                │                  │
  │                       │                          │  publish(PaymentCharged)                                │                  │
  │                       │                          │─────────────────────────────────────►│
  │                       │                          │◄─────────────────────────────────────│ ack
  │                       │◄────────────────────│  UPDATE published=true                            │                  │
                                                                                              RESULT: the event WAS
                                                                                              eventually published,
                                                                                              despite the crash —
                                                                                              because it was never
                                                                                              only-in-memory to begin
                                                                                              with.
```

**Polling vs CDC — the same trade-off as choosing a monitoring interval
anywhere else:**

```
POLLING (simple background job, checks the outbox table every N ms):
  ✅ Trivial to implement, no extra infrastructure
  ❌ Adds polling load to the database, and events are delayed by up to
     the poll interval

CDC (Change Data Capture — e.g. Debezium reading Postgres's write-ahead
log directly):
  ✅ Near-zero latency (reacts to the WAL almost immediately), no polling
     load on the database at all
  ❌ Genuine infrastructure to run and operate (Debezium + Kafka Connect)
```
**Why this pattern generalizes far beyond sagas**: this exact mechanism is
also what §7.6.3's CQRS projector needs underneath it (the write model
must reliably notify the read-model projector of every event) and what any
"update the database and also notify something else" operation needs
anywhere in this guide — the outbox pattern is the general-purpose
solution to the dual-write problem, sagas are simply the case where it
becomes unavoidable to reason about explicitly.

---

