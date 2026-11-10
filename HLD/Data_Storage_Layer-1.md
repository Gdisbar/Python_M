# Data & Storage Layer — Sections 1–4
###   1. Distributed Systems Fundamentals
###   2. CAP Theorem & Database Selection 

---

## 1. Distributed Systems Fundamentals

### 1.1 Why Any of This Exists — Building the Intuition From One Machine

Start with the simplest possible system: **one process, one disk.**

```
Client ──► [ Single Process ] ──► [ Local Disk ]
```
Here, almost every hard problem in this document simply does not exist:

- **There is no "network partition"** — a function call either returns or
  the process has crashed. There's no in-between state.
- **There is no "which copy is correct"** — there is exactly one copy.
- **There is no "ordering ambiguity"** — instructions execute in the order
  the CPU issues them; there's a single, obvious timeline.
- **A retry is trivially safe** — if a function throws, nothing partially
  happened across two separate systems; you just call it again.

Everything in this guide — consensus, vector clocks, idempotency keys,
CRDTs — is scaffolding built to *simulate* those single-node guarantees
once you're forced to split state across more than one machine. So before
looking at any solution, look at exactly what breaks, and why, as soon as
you add a second machine:

```
Client ──► [ Process A ] ◄──sync──► [ Process B ]
                │                         │
              [ Disk A ]                [ Disk B ]
```

The moment you draw that second box, four new problems appear that simply
had no analog before:

1. **The link between A and B can be slow, or can fail, and A has no way
   to instantly know which one is happening.** If A sends an update to B
   and gets no response, did B receive it and the *acknowledgment* got
   lost? Or did the update itself never arrive? From A's point of view
   these are indistinguishable — and yet the correct recovery action is
   different (resending an already-applied update is dangerous if it's not
   idempotent; not resending a lost update loses data).

2. **A and B can now disagree about the current value**, if updates reach
   them in different orders, or one of them missed an update entirely.
   There is no longer one obvious "current state" — there might be two.

3. **"At the same time" stops being meaningful.** On one machine, one CPU
   core, instructions have a strict order. Across two machines with
   independent clocks, "which write happened first" is not just hard to
   observe — for events with no causal relationship, the question doesn't
   even have a single correct answer.

4. **A retry that was safe on one machine can now be dangerous.** If A's
   call to B *did* succeed but the acknowledgment was lost on the way
   back, and the client retries the same logical operation, B might now
   execute it twice.

Every concept in the rest of this section is a named, engineered answer to
one of these four problems. Keep that mapping in your head as you read:

| Problem introduced by adding a 2nd machine | Section that answers it |
|---|---|
| (1) Can't tell "slow" from "failed" | §1.1 fallacies below; timeouts, circuit breakers (later §8) |
| (2) Two machines can disagree on current state | §1.2 consistency models |
| (3) "At the same time" is ambiguous | §1.2.2 vector clocks specifically |
| (4) A retry can now cause a double-execution | §1.4 idempotency |

### 1.2 The Eight Fallacies — What Actually Breaks, One at a Time

These are commonly quoted as a memorized list. Instead, walk through *why*
each one is a fallacy by asking: "what would I naively assume if I'd only
ever built single-machine software?"

**If you've only written single-process code, you naturally assume:**
a function call either completes or throws — nothing in between (you'd
assume **the network is reliable**); a function call returns instantly
relative to your program's other work (you'd assume **latency is zero**);
you can pass as much data as you want between two function calls without
thinking about it (you'd assume **bandwidth is infinite**); nobody else can
tamper with memory inside your own process (you'd assume **the network is
secure**); the object you have a reference to is the same object you'll
have a reference to next time (you'd assume **topology doesn't change**);
you're the only one editing this codebase's shared assumptions (you'd
assume **there is one administrator**); passing a struct by reference is
free (you'd assume **transport cost is zero**); every core in your machine
runs at the same speed (you'd assume **the network is homogeneous**).

Every one of those instincts is *correct for a single process* and
*actively wrong* the instant a call crosses a machine boundary — which is
exactly why they're called fallacies: they're not stupid assumptions in
isolation, they're the completely reasonable defaults you'd carry over from
everything you learned writing non-distributed code.

| Fallacy | Concrete failure mode in production | Architectural mitigation |
|---|---|---|
| Network is reliable | TCP retransmit storms, half-open connections, silent packet loss | Timeouts + retries with jitter, idempotency keys (§1.4), circuit breakers |
| Latency is zero | p99 dominated by the slowest hop in a fan-out call | Parallel fan-out (gather, don't sequentially await), co-locate chatty services in the same AZ |
| Bandwidth is infinite | Egress cost/throttling on large payloads (image/video APIs) | Pagination, field selection (GraphQL), compression, CDN offload |
| Network is secure | Lateral movement after a single host compromise | mTLS between services (zero trust, not perimeter trust) |
| Topology doesn't change | Hardcoded IPs/hostnames break on autoscale/node replacement | Service discovery (Consul/Eureka/K8s DNS), never hardcode instance addresses |
| One administrator | Cross-team config drift, silent breaking changes to a shared API | Contract-first API design + consumer-driven contract tests (Pact) |
| Transport cost is zero | Serialization overhead dominates latency on hot paths | Protobuf/Avro over JSON on internal RPC; benchmark serialization, not just I/O |
| Network is homogeneous | A batch job assumes uniform node specs and OOMs on a smaller node | Explicit resource requests/limits per workload, never assumed |

### 1.3 Consistency Models — Building Up From "Just Read the Value"

#### Step 1: the single-node baseline you're trying to preserve

On one machine, "read the current value of `x`" has an unambiguous answer:
whatever the last completed write set it to. There's a total order of
operations because there's one CPU executing them one at a time (or, with
threads, a lock enforcing the same effect). This property — *every read
sees the most recent write, and everyone agrees on what "most recent"
means* — is what we call **linearizability**. It's not a fancy distributed
systems invention; it's the thing you already had for free on one machine,
and it's what you *lose* the moment you add replicas.

#### Step 2: what happens when you add a second copy of the data

The instant you have two copies (for availability, or to serve reads
closer to users), you must answer a question that didn't exist before:
*when Node A writes a new value, exactly when does Node B know about it,
and what should Node B answer if it's asked before it's caught up?*

There are exactly three honest answers to that question, and each one *is*
a named consistency model — they are not arbitrary categories invented by
academics, they are the three logically possible answers to "what does the
stale replica do when asked":

```
Q: A just wrote x=5. Node B hasn't heard yet. Client reads x from B. What
   does B say?

Answer 1: "I will not answer until I've confirmed I'm caught up with the
           latest write (or I'll forward you to whoever IS caught up)."
           → This is LINEARIZABLE consistency. Correct, but the read now
             pays a network round-trip cost it didn't need to pay before.

Answer 2: "I'll tell you my current value (x=old), UNLESS you can show me
           you already observed A's write yourself — in which case I owe
           you at least that version."
           → This is CAUSAL consistency. Cheaper than (1), but only
             ordering along a chain of causally-related events is
             guaranteed — two writes with no causal link can be seen in
             different orders by different readers, and that's allowed.

Answer 3: "I'll tell you my current value (x=old) with no further
           questions asked. I promise that IF writes eventually stop
           arriving, all replicas will eventually agree — but right now,
           no guarantee."
           → This is EVENTUAL consistency. Cheapest, most available,
             weakest guarantee.
```

This is the entire spectrum. There is no fourth option, because there is no
fourth honest answer to "what does the stale node do." Once you see it this
way, the question "which consistency model should I use" stops being
"which buzzword sounds right" and becomes "how much staleness can THIS
specific read tolerate, and am I willing to pay a round trip to avoid it."

#### Step 3: the mechanism behind Answer 1 — Linearizable Consistency

The naive way to implement Answer 1 ("don't answer until you're caught
up") would be for a follower to always redirect every read to whoever is
definitely current. That works but throws away the whole benefit of having
replicas (you're back to a single bottleneck). Real systems instead use
Raft (or Paxos) to keep a **replicated log** — every node applies the same
sequence of writes in the same order — plus one of two tricks so that a
follower can answer locally without a round trip on every single read:

```
Client A                 Leader (N1)         Follower (N2)      Follower (N3)
   │  WRITE x=5              │                    │                   │
   │─────────────────────────►│                    │                   │
   │                          │  AppendEntries(x=5) │                   │
   │                          │───────────────────►│                   │
   │                          │───────────────────────────────────────►│
   │                          │◄───────────────────│ ack               │
   │                          │◄───────────────────────────────────────│ ack
   │                          │  (quorum: 2 of 3 acked → COMMIT)        │
   │  ◄───────────────────────│  200 OK                                 │
   │                          │                                          │
Client B                      │                                          │
   │  READ x  (routed to N2, must be LINEARIZABLE)                        │
   │──────────────────────────────────────────────►│                       │
   │                          N2 checks: "am I current with the committed  │
   │                          index the leader last told me about?"        │
   │                          (ReadIndex protocol), OR: N1 grants N2 a        │
   │                          time-bound LEASE during which N1 promises no      │
   │                          other node could have become leader, letting        │
   │                          N2 answer locally without asking N1 every time         │
   │◄───────────────────────────────────────────────│  x=5 (never x=stale)   │
```
**Why a naive follower read is NOT automatically linearizable**: a follower
that just serves whatever's in its local copy might be one or more log
entries behind the leader — it hasn't been told the write happened yet.
ReadIndex and leader-leases are both mechanisms for the follower to
*prove to itself* it's not stale before answering, without paying the cost
of asking the leader on every single read.

#### Step 4: the mechanism behind Answer 2 — Causal Consistency via Vector Clocks

Causal consistency needs a way to answer one specific question cheaply:
*"did the writer of THIS update already know about THAT other update?"*
A wall-clock timestamp can't answer this reliably (clocks drift and skew
across machines). The tool built specifically to answer "did event X know
about event Y" is a **vector clock** — one logical counter per node:

```
VectorClock = { node_id: logical_counter, ... }

Example evolution across 3 nodes (N1, N2, N3):
  N1 writes "A"  → VC = {N1:1, N2:0, N3:0}
  N2 writes "B" (has seen A) → VC = {N1:1, N2:1, N3:0}   # causally after A
  N3 writes "C" (has NOT seen A or B) → VC = {N1:0, N2:0, N3:1}  # concurrent

Comparison rule:
  VC1 happens-before VC2  IFF  every component of VC1 <= the corresponding
  component of VC2, AND at least one component is strictly less.
  If neither VC1<=VC2 nor VC2<=VC1 → CONCURRENT (a real conflict — the
  system must merge or ask the application to resolve it).
```

```
Client                Node A (VC:{A:1})       Node B (VC:{B:1})
  │  write "B" is a reply to "A" (client attaches VC:{A:1} it read) │
  │────────────────────────────────►│                                │
  │        Node A merges: VC becomes {A:1, B:1} — B's write is        │
  │        recorded as CAUSALLY AFTER A's write                          │
  │                                  │  replicate to Node B                │
  │                                  │───────────────────────────────────►│
  │                                  │        Node B independently accepts │
  │                                  │        write "C" concurrently:        │
  │                                  │        VC:{C:1} — NOT derived from A    │
  │                                  │                                        │
  │  read → sees both "B" (VC:{A:1,B:1}) and "C" (VC:{C:1}) → these are        │
  │  CONCURRENT (neither VC dominates) → application-level conflict resolution │
  │  required (e.g. "last writer wins" by timestamp, or present both to the      │
  │  user like Amazon's shopping cart historically did)                            │
```
Notice what the vector clock buys you exactly, and no more: it correctly
identifies "B knew about A" (so B must be shown after A), but it makes NO
claim at all about "A vs C" — and that's not a limitation to work around,
that's the entire point. A and C are genuinely, physically unordered
events; a vector clock refuses to invent a fake ordering for them, unlike
a wall-clock timestamp which would silently assign one that could be wrong.

#### Step 5: the mechanism behind Answer 3 — Eventual Consistency via CRDTs

Answer 3 promised "eventually all replicas agree, no guarantee before
that" — but it left one thing unsaid: agree *how*, if two replicas
received different updates in different orders? A **CRDT** (Conflict-Free
Replicated Data Type) is a data structure engineered so the merge rule is
mathematically guaranteed to produce the same result regardless of what
order updates arrive in — you don't detect a conflict and resolve it
(that's the vector-clock/causal approach); you use a data structure where
conflicts are structurally impossible.

```
┌───────────────────────────────────────────────┐
│ GCounter  (grow-only counter CRDT)               │
├───────────────────────────────────────────────┤
│ - counts: Map<node_id, int>   # one slot per     │
│           node — this is the whole trick:          │
│           each node only ever increments ITS OWN     │
│           slot, so there's never a write conflict     │
│           to resolve in the first place                 │
├───────────────────────────────────────────────┤
│ + increment(node_id):                                 │
│     counts[node_id] += 1                                 │
│ + value() -> int:                                            │
│     return sum(counts.values())                                │
│ + merge(other: GCounter) -> GCounter:                             │
│     # element-wise MAX per node — commutative,                     │
│     # associative, idempotent. Apply in ANY order,                   │
│     # any number of times, same final result.                          │
│     for node_id in counts.keys() ∪ other.counts.keys():                  │
│         result[node_id] = max(counts[node_id], other.counts[node_id])      │
│     return result                                                            │
└───────────────────────────────────────────────┘
```
**Why this is a genuinely different tool, not just "eventual consistency
with extra steps"**: a like-counter or view-counter built this way needs
zero coordination between regions, ever — no consensus round trip, no
conflict-resolution logic in the application, no vector clock bookkeeping.
The cost is that CRDTs only exist for operations with a commutative merge
rule (counters, sets, sequences) — you cannot build "a bank balance that
must never go negative" as a CRDT, because "reject this withdrawal" is not
a commutative operation with respect to a concurrent withdrawal on another
node. Knowing which category your data falls into (mergeable vs. requires
a real decision) is the actual skill here, not memorizing that "CRDTs
exist."

### 1.4 PACELC — From "Which Do I Pick" to a Decision You Can Defend

CAP only tells you what happens *during a partition* — and partitions are
rare. PACELC completes the picture by adding: *even when there's no
partition at all, you're still trading consistency for latency*, because a
linearizable read (Step 3 above) pays a round trip that an eventual read
doesn't. This gives a decision tree you can actually apply per-field,
rather than per-system:

```
                    ┌─────────────────────────┐
                    │ Is this field ever read   │
                    │ immediately after a write   │
                    │ by the SAME causal chain     │
                    │ (e.g. "did my payment go       │
                    │ through") ?                       │
                    └───────────┬─────────────────┘
                    yes │                    │ no
                        ▼                    ▼
            ┌───────────────────┐   ┌─────────────────────┐
            │ Strong/linearizable │   │ Is ordering between    │
            │ read required.       │   │ DIFFERENT users' writes │
            │ Pay the consensus       │   │ meaningful (e.g. a        │
            │ round-trip latency        │   │ comment thread)?             │
            └───────────────────┘   └──────────┬──────────────┘
                                       yes │            │ no
                                           ▼            ▼
                                 ┌─────────────┐  ┌──────────────┐
                                 │ Causal          │  │ Eventual        │
                                 │ consistency        │  │ consistency        │
                                 │ (vector clocks)       │  │ (CRDT or LWW)         │
                                 └─────────────┘  └──────────────┘
```

The most useful architectural move here is to stop treating "consistency
level" as a property of the whole database and expose it as a property of
each *request*, so different callers of the same field can each pay for
exactly the guarantee they need:

```yaml
# openapi fragment
paths:
  /accounts/{id}/balance:
    get:
      parameters:
        - name: consistency
          in: query
          schema:
            type: string
            enum: [eventual, strong]
            default: eventual
          description: >
            'eventual' reads from the nearest replica, may be stale by
            replication lag (typically <100ms). 'strong' routes the read
            through the leader/quorum path — higher latency, guaranteed
            latest committed value. Callers displaying a balance for
            informational purposes should use 'eventual'; callers about to
            authorize a withdrawal MUST use 'strong'.
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  balance: { type: number }
                  as_of_replica_lag_ms:
                    type: integer
                    description: >
                      Only present when consistency=eventual — tells the
                      caller how stale this value might be, so a UI can
                      show "as of 40ms ago" rather than presenting a
                      potentially-stale number as ground truth silently.
```
This single contract is the concrete answer to "what did learning PACELC
actually change about how I build systems": instead of one global decision
made once at the database layer, every caller states which of the two
honest trade-offs (from Step 2 above) it needs, and pays exactly that cost.

### 1.5 Idempotency — Building Up From the Retry Problem, Then the Full Component

#### Step 1: why a retry that was safe on one machine becomes dangerous

Recall problem (4) from §1.1: on a single machine, if a function throws,
you know nothing else observed a partial effect, so calling it again is
safe. Across a network this guarantee disappears completely, and the
failure is specifically this: **the client cannot distinguish "my request
never arrived" from "my request arrived, succeeded, but the response was
lost on the way back."** Both look identical to the client: a timeout.

```
Client                              Server
  │  POST /payments {amount:100}        │
  │─────────────────────────────────────►│
  │                                       │  charges the card successfully
  │        X   (response lost/timeout)     │
  │  ... client sees no response, and has NO WAY to know if the charge
  │      happened or not ...
  │  client's ONLY reasonable options: give up (bad — might have failed
  │  and now the user is never charged), or retry (bad — might have
  │  succeeded and now the user is charged twice)
```
Neither "give up" nor "blindly retry" is acceptable. The fix has to change
what a retry actually *means* to the server: instead of "do this action
again," it must become "tell me what happened last time I asked you to do
this specific action" — which requires the server to remember, per
logical action, whether it already ran and what it returned. That's the
entire concept; everything below is the engineering of that memory.

#### Step 2: the component that provides that memory

```
┌─────────────────────────────────────────────────┐
│ IdempotencyRecord (Entity)                         │
├─────────────────────────────────────────────────┤
│ + idempotency_key: string        (PK)                │
│ + request_fingerprint: string     (SHA-256 of body)     │
│ + status: enum { IN_PROGRESS, COMPLETED }                 │
│ + response_status_code: int?      (null while in-progress) │
│ + response_body: jsonb?           (null while in-progress)   │
│ + owner_instance_id: string       (which process holds it)     │
│ + created_at: timestamptz                                       │
│ + expires_at: timestamptz         (TTL — 24h typical)              │
├─────────────────────────────────────────────────┤
│ + try_acquire(key, fingerprint) -> AcquireResult                     │
│ + complete(key, status_code, body) -> void                             │
│ + get(key) -> IdempotencyRecord?                                          │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────┐      ┌──────────────────────────────┐
│ IdempotencyMiddleware              │─────►│ IdempotencyStore (interface)    │
├─────────────────────────────────┤      ├──────────────────────────────┤
│ + handle(request, next) -> Response │      │ + try_acquire(...) -> AcquireResult│
└─────────────────────────────────┘      │ + complete(...) -> void          │
                                            │ + get(key) -> Record?              │
        implements ▲                        └──────────────────────────────┘
                    │                                     ▲
        ┌───────────┴───────────┐             implements   │
        │ RedisIdempotencyStore    │◄───────────────────────┘
        │ (production default —      │        ┌──────────────────────────────┐
        │  fast, TTL-native)             │        │ PostgresIdempotencyStore        │
        └───────────────────────┘        │ (fallback when durability across  │
                                          │  a Redis flush/restart matters      │
                                          │  more than raw latency)                │
                                          └──────────────────────────────┘

AcquireResult = ACQUIRED | ALREADY_IN_PROGRESS | ALREADY_COMPLETED(response) |
                CONFLICT_DIFFERENT_PAYLOAD
```
Notice why the record needs BOTH a `status` (IN_PROGRESS vs COMPLETED) and
a `request_fingerprint`, not just a key → response mapping: the status is
what solves the "client retries while the first attempt is still running"
race (Sequence c below); the fingerprint is what catches "client reused a
key for a genuinely different action" (Sequence d below) — a bug, not a
retry, that a plain key→response cache would silently mask.

#### Step 3: the schema (Postgres variant)

```sql
CREATE TABLE idempotency_records (
    idempotency_key      TEXT PRIMARY KEY,
    request_fingerprint   TEXT NOT NULL,
    status                 TEXT NOT NULL CHECK (status IN ('IN_PROGRESS','COMPLETED')),
    response_status_code    INTEGER,
    response_body            JSONB,
    owner_instance_id          TEXT NOT NULL,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at                   TIMESTAMPTZ NOT NULL
);

-- Enables the background reaper to cheaply find expired rows without a
-- full table scan; without this index, cleanup degrades as the table grows.
CREATE INDEX idx_idempotency_expires_at ON idempotency_records (expires_at);

-- Acquire, implemented as a single atomic statement rather than a
-- read-then-write (which would reintroduce exactly the race we're
-- trying to eliminate):
--   INSERT INTO idempotency_records (idempotency_key, request_fingerprint,
--       status, owner_instance_id, expires_at)
--   VALUES ($1, $2, 'IN_PROGRESS', $3, now() + interval '24 hours')
--   ON CONFLICT (idempotency_key) DO NOTHING
--   RETURNING *;
--   -- zero rows returned => someone else already holds this key; SELECT
--   -- the existing row to decide ALREADY_IN_PROGRESS vs ALREADY_COMPLETED
```
The Redis version (V2 §1) is preferred for latency; reach for this
Postgres version specifically when the dedup guarantee must survive a
Redis restart/flush — i.e. when losing dedup state risks a real
double-charge, not just a harmless duplicate side effect.

#### Step 4: every real failure mode as a sequence diagram

**(a) Happy path — first request:**
```
Client          Middleware           Store            Handler
  │  POST /payments               │                    │
  │  Idempotency-Key: K1            │                    │
  │──────────────────►│                                    │
  │                    │  try_acquire(K1, hash(body))         │
  │                    │───────────►│                            │
  │                    │◄───────────│ ACQUIRED                     │
  │                    │  invoke handler                             │
  │                    │─────────────────────────────────►│           │
  │                    │◄─────────────────────────────────│ 200, body   │
  │                    │  complete(K1, 200, body)                        │
  │                    │───────────►│                                     │
  │◄───────────────────│ 200, body                                          │
```

**(b) The exact scenario from Step 1 — retry after client timeout, server
actually succeeded:**
```
Client          Middleware           Store            Handler
  │  POST /payments (attempt 1)   │                    │
  │──────────────────►│                                    │
  │                    │  try_acquire(K1) → ACQUIRED            │
  │                    │─────────────────────────────────►│         │
  │   X  (client times out waiting, does NOT see response)              │
  │                    │◄─────────────────────────────────│ 200        │
  │                    │  complete(K1, 200, body)  [server-side done]   │
  │  POST /payments (attempt 2, SAME key K1, client retry)                │
  │──────────────────►│                                                    │
  │                    │  try_acquire(K1) → ALREADY_COMPLETED(200,body)      │
  │◄───────────────────│ 200, body   [replayed, handler NEVER re-invoked]     │
```
This is the whole point of the component: the client's ambiguity from Step
1 is resolved not by guessing, but by the server answering the *actual*
question — "what happened last time" — instead of blindly redoing work.

**(c) Concurrent retry arriving WHILE the first is still processing:**
```
Client A         Middleware          Store
  │ POST (K1) attempt 1           │
  │──────────────►│                  │
  │                │ try_acquire(K1) → ACQUIRED, invoking handler...
Client A (retry, same K1, fired concurrently by an aggressive client lib)
  │ POST (K1) attempt 2           │
  │──────────────►│                  │
  │                │ try_acquire(K1) → ALREADY_IN_PROGRESS
  │◄───────────────│ 409 Conflict — "retry after a short delay"
```
409 here is a deliberate choice: it tells the client "the first attempt is
still in flight," which calls for a different client reaction (wait, then
re-check) than replaying a completed response would.

**(d) Key reused with a DIFFERENT payload — a client bug, not a retry:**
```
Client          Middleware           Store
  │ POST (K1, body={amount:100})  │
  │──────────────►│  try_acquire(K1, hash_A) → ACQUIRED, completes 200
  │ POST (K1, body={amount:500})  │   <-- same key, DIFFERENT amount!
  │──────────────►│  try_acquire(K1, hash_B)
  │                │  found existing record: fingerprint hash_A != hash_B
  │◄───────────────│ 422 Unprocessable — "Idempotency-Key reused with a
  │                    different request body"
```

**(e) Store unavailable — the failure mode that must be an explicit,
per-endpoint decision, not a library default:**
```
Client          Middleware           Store (DOWN)
  │ POST /payments (K1)            │
  │──────────────►│  try_acquire(K1) → connection error / timeout
  │                │
  │   FAIL CLOSED (reject, 503) — correct for /payments, /orders:
  │     a duplicate charge is worse than a temporary outage
  │   FAIL OPEN (proceed without dedup) — acceptable for low-stakes
  │     idempotent-by-nature actions (e.g. "mark notification read")
```

#### Step 5: the API contract every client integrates against

```yaml
paths:
  /payments:
    post:
      parameters:
        - name: Idempotency-Key
          in: header
          required: true          # required=true for payment-class endpoints
          schema: { type: string, format: uuid }
      responses:
        '200':
          description: Payment processed (or replayed from a prior identical request)
        '409':
          description: >
            A request with this Idempotency-Key is currently being
            processed by another in-flight request. Retry after a short
            delay — do NOT immediately resubmit.
        '422':
          description: >
            This Idempotency-Key was already used with a DIFFERENT request
            body. This indicates a client-side bug (key reused across
            distinct logical operations) — generate a new key per distinct
            user action.
        '503':
          description: >
            The idempotency store is unavailable and this endpoint fails
            closed for safety. Retry with the SAME Idempotency-Key once
            available — retrying with a new key risks a duplicate charge.
```

#### Step 6: edge cases a design review will actually push on

| Edge case | Behavior | Why |
|---|---|---|
| Key never expires from client's perspective, but server TTL passes | New execution happens, no dedup | TTL must exceed the client's realistic retry window (24h is generous; tune to your client's actual backoff ceiling) |
| Two different USERS accidentally send the same key value | Second user gets the first user's response | Keys must be generated with enough entropy (UUID v4) that collision across users is cryptographically negligible — never let clients pick human-readable keys |
| Handler itself is non-deterministic (e.g. calls `random()` for a discount code) | Replayed response returns the ORIGINAL result, not a fresh one | This is correct and required — idempotency's entire purpose is "same input → same output," even if the underlying operation isn't naturally deterministic |
| Partial failure: handler succeeded but `complete()` write to the store failed | Record stuck in IN_PROGRESS forever (or until TTL) | Add a secondary reconciliation job: if IN_PROGRESS and owner_instance_id's process is confirmed dead (health-check), forcibly re-open the key for retry — this is the "stuck lock" recovery path |

---


## 2. CAP Theorem & Database Selection

### 2.1 Building the Intuition: What a Partition Actually Breaks

Start again from the smallest possible step up from a single node: **two
nodes, replicating, with a perfectly healthy link between them.**

```
Node A ◄──always-healthy link──► Node B
```
As long as that link never fails, you can actually have everything: every
write to A gets forwarded to B before A acknowledges the client, so both
nodes are always consistent, and both are available for reads, because
neither one ever needs to refuse a request. There is no trade-off yet —
CAP hasn't "kicked in," because nothing has partitioned. This is worth
sitting with for a second, because it's the source of a lot of confusion:
**CAP is not a tax you pay for having more than one node. It's a
consequence that only appears the instant the link between nodes actually
breaks.**

Now break the link:

```
Node A  ✕──(network partition)──✕  Node B
   │                                    │
Client 1 writes x=5 to A          Client 2 writes x=9 to B
```

Both clients are talking to a node that is, from its own point of view,
working perfectly. Node A has no way to know if Node B is dead, slow, or
just unreachable — and vice versa. Now ask the concrete question: **when
Client 3 comes along and reads `x` from Node A, what should Node A say?**

There are only two honest options, and this is the entire theorem:

```
OPTION 1 — Node A refuses to answer (or refuses to accept Client 1's
           write in the first place) until it can confirm with Node B
           that they agree.
           → The system is now UNAVAILABLE during the partition — a node
             that is technically healthy is refusing to serve a request.
           → This is choosing CONSISTENCY over Availability.

OPTION 2 — Node A answers immediately with whatever it locally has,
           without waiting to hear from B.
           → The system stays AVAILABLE, but Node A and Node B may now
             have processed genuinely conflicting writes (x=5 vs x=9)
             with no way to know until the partition heals.
           → This is choosing AVAILABILITY over Consistency.
```
There is no third option, because there is no third honest thing a healthy
node can do when it can't reach its peer: it either waits (unavailable) or
it doesn't (potentially inconsistent). This is why CAP is usually stated as
"pick 2 of 3" but is more precisely "during a partition, pick one of two,
because Partition tolerance was never actually optional in a system with
more than one machine."

### 2.2 The Proof Sketch — Why You Cannot Have All Three at Once

Formalizing the walkthrough above: assume, for contradiction, a system
claims to offer Consistency, Availability, AND Partition tolerance
simultaneously.

```
┌─────────────────────────────────────────────────────────────────┐
│  Setup: two nodes N1, N2, replicating value v. Network between      │
│  them is partitioned (P holds — this is a real, unavoidable event).   │
│                                                                     │
│  Step 1: Client writes v=1 to N1.                                     │
│          Because the system is AVAILABLE, N1 must accept this write     │
│          and respond success — it cannot block waiting for N2, since     │
│          N2 is unreachable during the partition.                           │
│                                                                             │
│  Step 2: A different client reads v from N2.                                │
│          Because the system is AVAILABLE, N2 must also respond — it          │
│          cannot block waiting for N1 either.                                   │
│                                                                                 │
│  Step 3: But N2 has NOT received N1's write (the network is partitioned).        │
│          So N2 can only answer with its old value, v=0.                            │
│                                                                                     │
│  CONTRADICTION: the system was assumed to be CONSISTENT, meaning every                │
│  read must reflect the most recent write. But N2 just returned v=0 when                 │
│  v=1 was already committed on N1. □                                                       │
└─────────────────────────────────────────────────────────────────┘
```
The contradiction isn't a bug in some specific database — it's forced by
the setup itself. The only ways out are to give up Availability (N2
refuses to answer until it can confirm with N1) or give up Consistency
(N2 answers with stale data and the system labels the result "eventually"
correct instead of "immediately" correct). This is why CAP, once you've
walked through the proof instead of memorizing the triangle diagram, stops
feeling like an arbitrary rule and starts feeling like an unavoidable
consequence of what "two independent machines" actually means.

### 2.3 CP vs AP — The Real-World Choice, and What Each Costs You

Because partition tolerance isn't optional (networks partition — this is
observed behavior, not a design choice), the practical decision is always
CP vs AP, made *per subsystem*, not once for your whole architecture:

| Failure scenario | CP behavior | AP behavior | Recovery |
|---|---|---|---|
| Network partition | Minority side refuses writes/reads (`503`) until healed | Both sides keep serving, may diverge | CP: nothing to reconcile. AP: conflict resolution (LWW, CRDTs, vector clocks — §1.3) needed on heal |
| Write conflict (two sides both accepted writes) | Cannot happen — a write is only accepted by the side with quorum | Can happen — both sides accepted, values diverge | Version vectors, or CRDTs designed to merge cleanly (§1.3.5) |
| Node failure (not a full partition, just one node down) | Remaining quorum continues; system stays both C and A as long as a majority is up | Continues serving from whichever replicas remain reachable | CP: automatic once quorum is re-established. AP: gossip/anti-entropy repair |

| System | Choice | Why |
|---|---|---|
| ZooKeeper, etcd | **CP** | Used specifically for configuration/leader-election data where two nodes disagreeing about "who's the leader" is worse than a brief unavailability |
| Cassandra, DynamoDB | **AP** (tunable — see §1.4's per-request consistency contract) | Built for always-on, globally distributed workloads (shopping carts, session data) where brief staleness is invisible to the user but downtime isn't |
| Traditional single-primary Postgres/MySQL | Effectively **CP** at the primary, **AP-ish** on read replicas if you allow stale reads | Most teams don't realize they've made this choice implicitly until a replica lags and a user sees old data right after their own write |

### 2.4 From CAP to a Concrete Choice: the Database Selection Framework

The "5 questions" from your original notes are really shorthand for one
underlying test: **for THIS specific piece of data, what does staleness
cost you, and what does unavailability cost you — and which is cheaper?**
Turn that into a framework you'd actually put in an ADR (§19.3):

```
                ┌───────────────────────────┐
                │ Can a stale read cause real   │
                │ harm (double-spend, overselling │
                │ inventory, security decision)?     │
                └─────────────┬─────────────────┘
                    yes │              │ no
                        ▼              ▼
              ┌─────────────┐   ┌─────────────────────┐
              │ Need ACID/CP    │   │ Is write throughput at   │
              │ (Postgres,        │   │ a scale a single primary   │
              │  MySQL, or a        │   │ genuinely cannot handle       │
              │  CP-configured        │   │ (not "might someday" —          │
              │  distributed DB)        │   │ measured, current)?               │
              └─────────────┘   └──────────┬──────────────────┘
                                   yes │            │ no
                                       ▼            ▼
                             ┌─────────────┐  ┌──────────────────┐
                             │ AP, horizontally│  │ Single-primary SQL,   │
                             │ scalable            │  │ read replicas for       │
                             │ (Cassandra,           │  │ read scaling — simplest    │
                             │  DynamoDB)              │  │ correct answer, don't        │
                             └─────────────┘  │ shard until forced         │
                                              └──────────────────┘
```

**Worked example — scoring three candidates for an "Orders" service**,
the kind of table that actually belongs in a trade-off document (§19.2):

| Criterion (weighted) | Postgres | MongoDB | DynamoDB |
|---|---|---|---|
| Multi-row ACID transactions (weight: high — order+line-items+inventory must move together) | ✅ Native | ⚠️ Possible, added complexity | ❌ Not a natural fit |
| Ad hoc relational reporting (weight: medium) | ✅ Excellent (JOINs) | ⚠️ Requires aggregation pipeline | ❌ Poor |
| Team's existing operational expertise (weight: medium) | ✅ High | ⚠️ Low | ⚠️ Low |
| Horizontal write scaling past ~5k/sec (weight: low today, flagged for revisit) | ❌ Needs manual sharding | ✅ Native sharding | ✅ Native |
| **Verdict** | **Chosen** — wins on the two highest-weighted criteria | Rejected | Rejected |

This table, not a one-line justification, is what makes the decision
defensible later — see §19.3 for how this becomes the "Alternatives
Considered" section of the resulting ADR.

### 2.5 Database Types — Why Each One Fits Its Niche (Mechanism, Not Just Label)

The "best for" column in a database comparison table is usually presented
as received wisdom. It's actually a direct consequence of the underlying
data structure each engine is built around:

| Type | Examples | Underlying structure | Why that structure fits the niche |
|---|---|---|---|
| Document | MongoDB | Self-describing JSON/BSON blobs, no fixed schema enforced at write time | Flexible schema is a direct property of NOT having a rigid page layout tied to a fixed column list — adding a field is just adding a key to a document, not an `ALTER TABLE` |
| Wide-Column | Cassandra, CosmosDB | Column families physically stored together, sorted by a partition+clustering key | Time-series/IoT queries ("give me all readings for sensor X between t1 and t2") become a contiguous on-disk range scan because the clustering key IS time |
| Key-Value | Redis, DynamoDB | Hash table — O(1) average lookup by key | Sessions/cache have exactly one access pattern ("get this exact key") — a hash table is the theoretically optimal structure for that pattern, nothing else is needed |
| Graph | Neo4j | Adjacency list — each node stores direct pointers to its neighbors | "Friends of friends of friends" is O(1) per hop via pointer-following; the equivalent in SQL is a self-JOIN per hop, which grows combinatorially expensive with depth |
| Search Engine | Elasticsearch | Inverted index — term → list of document IDs containing it | Full-text/partial-match search becomes an index lookup on the TERM, not a scan of every document — see §2.6 for exactly why this beats a B-Tree |
| OLAP | BigQuery, ClickHouse | Columnar storage — each column's values stored contiguously, not each row | `AVG(price)` only needs to read the `price` column's bytes off disk, not every other column in every row — a 100-column table's aggregate query on 1 column is ~100x less I/O than a row store |
| Row Store | PostgreSQL | Rows stored contiguously (heap), B-Tree indexes for lookups | Transactional workloads read/write whole records ("get this order, all its fields") — row-contiguous storage means one disk read gets you the whole record |
| Vector | Pinecone, pgvector | Approximate nearest-neighbor index (HNSW graphs) over high-dimensional embeddings | Semantic similarity search needs "closest points in 768-dimensional space," which brute-force is O(n) per query — HNSW makes it approximately O(log n) by pre-building a navigable small-world graph |

### 2.6 Full Component Design: Full-Text Search With Graceful Fallback

This is the one genuinely engineerable component in this section, so it
gets the full treatment — starting from why a relational index can't do
the job at all.

#### 2.6.1 Building the intuition: why a B-Tree can't do this

A B-Tree index is sorted by the indexed value's prefix — that's precisely
what makes `WHERE name = 'Smith'` or `WHERE name > 'M'` fast: the tree can
jump straight to the right branch using the first few characters. Now ask
it to satisfy `WHERE name LIKE '%mit%'` — a wildcard with no fixed prefix.
There is no branch to jump to, because the match could start anywhere in
the string. The B-Tree's entire speed advantage evaporates, and the
database falls back to comparing every single row — a full table scan.

An **inverted index** solves this by flipping the data structure inside
out: instead of indexing *documents* to look up *terms*, it indexes
*terms* to look up *documents* directly.

```
Documents:                          Inverted Index:
  doc1: "the quick brown fox"          "brown" → [doc1]
  doc2: "the lazy brown dog"           "dog"   → [doc2]
                                        "fox"   → [doc1]
                                        "quick" → [doc1]
                                        "the"   → [doc1, doc2]
```
Now `WHERE content CONTAINS 'brown'` is a direct hash/tree lookup on the
term "brown" — O(1)-ish, not a scan — because the data structure was built
around exactly the access pattern the query needs, the same principle as
every row in the §2.5 table above.

#### 2.6.2 Class Diagram — Fallback as a Chain of Responsibility

```
┌─────────────────────────────┐
│ SearchOrchestrator              │
├─────────────────────────────┤
│ - strategies: List<SearchStrategy>│
│ - circuit_breakers: Map<strategy_name, CircuitBreaker>│
├─────────────────────────────┤
│ + search(query) -> SearchResult    │
│     for strategy in strategies:       │
│         if circuit_breakers[strategy].is_open(): continue
│         try: return strategy.execute(query) with degraded_level=strategy.level
│         except: circuit_breakers[strategy].record_failure(); continue
│     return SearchResult.empty(degraded_level=FULLY_DEGRADED)
└─────────────────────────────┘
            │ uses (ordered chain)
            ▼
┌─────────────────────────────┐
│ «interface» SearchStrategy      │
├─────────────────────────────┤
│ + execute(query) -> SearchResult   │
│ + level: int   (0=best, higher=more degraded)│
└─────────────────────────────┘
       ▲            ▲             ▲              ▲
       │            │             │              │
┌─────────────┐┌────────────┐┌─────────────┐┌──────────────┐
│Elasticsearch  ││PostgresScoped││RedisTrending ││ExactMatch      │
│Strategy         ││SearchStrategy ││Strategy        ││Strategy          │
│level=0            ││level=1          ││level=2            ││level=3 (last resort)│
│(inverted index,      ││(ILIKE on            ││(cached "trending"    ││(exact string          │
│ full relevance         ││ indexed columns,      ││ items — not query      ││  match on primary       │
│ ranking, typo             ││ scoped to recent       ││ specific, but            ││  key column only,         │
│ tolerance)                  ││ data only for             ││ always available)          ││  cheapest possible          │
│                               ││ acceptable latency)         ││                               ││  query the DB can run)        │
└─────────────────────────────┘└────────────────┘└─────────────┘└──────────────┘
```

#### 2.6.3 Sequence Diagram — Cascading Fallback Under Failure

```
Client        Orchestrator      ES Strategy      PG Strategy      Redis Strategy
  │  search("wireles headphnes")│                    │                   │
  │─────────────►│                                     │                   │
  │              │  circuit_breaker[ES].is_open()? NO      │                   │
  │              │  execute(query)                            │                   │
  │              │──────────────►│                               │                   │
  │              │   X  (timeout after 2s — ES cluster overloaded)  │                   │
  │              │◄──────────────│ TimeoutError                       │                   │
  │              │  circuit_breaker[ES].record_failure()                  │                   │
  │              │  (5th consecutive failure → breaker OPENS)                │                   │
  │              │  try next strategy: PG scoped search                          │                   │
  │              │─────────────────────────────►│                                    │                   │
  │              │◄─────────────────────────────│ results (exact-ish match             │                   │
  │              │                                 only — no typo tolerance,               │                   │
  │              │                                 "wireles" won't match "wireless")        │                   │
  │◄─────────────│ SearchResult(items=[...],                                                    │                   │
  │                degraded_level=1, message=                                                     │                   │
  │                "Showing basic results — typo-tolerant search temporarily unavailable")            │                   │
```
The critical design decision visible here: **the degraded response is
explicitly labeled**, not silently returned as if it were a normal result.
A frontend that ignores `degraded_level` will show the user a confusingly
poor result set with no explanation; one that reads it can show "Showing
basic results" — turning an invisible quality regression into an
acknowledged, bounded one.

#### 2.6.4 API Contract

```yaml
paths:
  /search:
    get:
      parameters:
        - name: q
          in: query
          required: true
          schema: { type: string }
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  items: { type: array, items: { type: object } }
                  degraded_level:
                    type: integer
                    description: >
                      0 = full relevance-ranked search (Elasticsearch).
                      1 = scoped/basic DB search, no typo tolerance.
                      2 = cached trending results only, NOT query-specific.
                      3 = exact-match only, last resort.
                      Clients SHOULD surface a visible notice to the user
                      when degraded_level > 0 rather than presenting
                      degraded results as if they were normal.
                  strategy_used:
                    type: string
                    description: "Which SearchStrategy actually served this response — for debugging/observability, not for end users."
```

#### 2.6.5 Index Schema and the "Derived Data" Discipline

```json
// Elasticsearch mapping — products index
{
  "mappings": {
    "properties": {
      "product_id":  { "type": "keyword" },
      "name":        { "type": "text", "analyzer": "standard" },
      "description": { "type": "text", "analyzer": "standard" },
      "price":       { "type": "double" },
      "updated_at":  { "type": "date" }
    }
  }
}
```
```
┌─────────────────────────────────────────────────────────────────┐
│  DISCIPLINE: Elasticsearch's index is a DERIVED, eventually          │
│  consistent copy of PostgreSQL's `products` table — never the           │
│  source of truth. This has two concrete engineering consequences:          │
│                                                                              │
│  1. Reindex-with-alias-swap for zero-downtime mapping changes:                │
│     products_v2 (new mapping) built in the background from Postgres →           │
│     alias "products" atomically repointed from products_v1 to products_v2 →       │
│     old index dropped. Search traffic never sees a missing index.                    │
│                                                                                          │
│  2. Rebuild path must always exist: a CDC pipeline (Debezium reading the                  │
│     Postgres WAL) or a nightly reindex job must be able to fully                             │
│     reconstruct the ES index from Postgres alone — if ES is ever lost                          │
│     entirely, that's an inconvenience (slow fallback search until rebuilt),                      │
│     not data loss, ONLY if this discipline was followed.                                            │
└─────────────────────────────────────────────────────────────────┘
```

#### 2.6.6 Edge Cases

| Edge case | Behavior | Why |
|---|---|---|
| ES index lags behind Postgres (CDC delay) | Search shows a product that was just deleted, or misses one just added | Bound and surface the lag: expose `indexed_as_of` timestamp; for inventory-critical views, re-verify availability against Postgres directly before checkout, never trust search-index freshness for a purchase decision |
| Mapping change requires different tokenization (e.g. adding multi-language support) | Requires a full reindex, not an in-place field edit | ES mappings are largely immutable once set for a field — this is why the alias-swap pattern in §2.6.5 exists as a standing operational procedure, not a one-off migration |
| All fallback strategies exhausted (ES down, PG overloaded, Redis empty) | Return `degraded_level=3` exact-match-only, or an explicit empty state, never a 500 | A search box that errors outright is worse UX than one that returns "no matches" truthfully at the cheapest possible strategy |
| Circuit breaker on ES flaps open/closed under partial degradation | Half-open test requests probe recovery without fully committing traffic back | Standard breaker state machine (§18) — don't let a single successful test request immediately re-open the floodgates; require a short sustained success window |

---

