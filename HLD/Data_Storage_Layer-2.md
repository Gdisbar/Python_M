# Data & Storage Layer — Sections 1–4
### 3. Database Architectures & Scaling
### 4. Caching Strategies & Invalidation

---

## 3. Database Architectures & Scaling

### 3.1 Building the Intuition: Why Scale Beyond One Node At All, and In Which Direction

Start from the honest baseline: **a single, well-tuned database server is
capable of far more than most engineers assume** — modern hardware can push
tens of thousands of simple queries per second on one box. The first
instinct when a database is "slow" should never be "add more nodes" — it
should be "did we index correctly, is the query plan sane, is the box
under-provisioned." Scaling out is what you reach for only after that's
been exhausted, because scaling out trades simplicity for capacity, and
that trade isn't free.

```
┌─────────────────────────────────────────────────────────────────┐
│  VERTICAL SCALING (scale up)                                      │
│  One box. Add CPU, RAM, faster disks (NVMe SSD over spinning disk),  │
│  faster network.                                                       │
│  ✅ Zero architectural complexity — the application code doesn't        │
│     change at all.                                                        │
│  ❌ Hits a hard ceiling: the largest cloud instance available, and         │
│     cost grows non-linearly as you approach it (the biggest boxes are        │
│     disproportionately expensive per unit of compute).                          │
└─────────────────────────────────────────────────────────────────┘
```

Once vertical scaling is genuinely exhausted (not "we haven't tried
tuning yet," but "we're on the largest reasonable instance and still
constrained"), you face a fork that most explanations gloss over as one
undifferentiated "horizontal scaling" bucket — but it's actually two
completely different problems with two completely different solutions,
and conflating them is the single most common scaling-architecture
mistake:

```
Is the bottleneck READS, or WRITES?

READS bottlenecked (e.g. 100,000 product-page views/sec, but only a
handful of admin writes/sec):
  → The data itself doesn't need to be split. You just need more COPIES
    of it so more machines can each answer read queries independently.
  → This is REPLICATION (§3.2).

WRITES bottlenecked (e.g. an ingestion pipeline doing 50,000 writes/sec —
more than one machine's disk I/O can physically absorb):
  → More copies don't help — every copy still has to process every write
    eventually. You need to split the DATA ITSELF so different machines
    each own a different slice and only process writes for their slice.
  → This is SHARDING (§3.3).
```
Why does replication only help reads and never writes? Because a
replica's entire value proposition is "I have an independent, consistent-
enough copy you can read from without bothering the primary" — but every
write must still, eventually, reach every replica that needs to reflect
it. Adding replicas doesn't reduce the total amount of write work in the
system; it multiplies it (now N machines must each apply the write instead
of one). This is the single fact that explains why "just add more
replicas" is a common but wrong answer to a write-throughput problem, and
why sharding — a completely different, more invasive mechanism — exists at
all.

### 3.2 Replication — From "One Copy" to an Automated Failover Component

#### 3.2.1 The intuition: what a copy actually buys you, and what it costs

A replica is valuable specifically because it can serve reads without
talking to the primary. The moment you have one, though, you're forced into
exactly the same choice we derived in §2.1/§2.3: does the primary wait for
the replica to confirm before telling the client "write succeeded" (safer,
slower), or does it not wait (faster, riskier)?

```
┌─────────────────────────────────────────────────────────────────┐
│  SYNCHRONOUS: Primary waits for the replica's ACK before telling      │
│  the client the write succeeded.                                         │
│  ✅ Zero data loss on primary failure — the replica definitely has          │
│     everything the client was told succeeded.                                 │
│  ❌ Write latency = worst of (local disk write, network round trip to           │
│     replica, replica's disk write). If the replica is slow or far away,           │
│     EVERY write pays that cost.                                                      │
│                                                                                          │
│  ASYNCHRONOUS: Primary acknowledges the client immediately, replicates    │
│  in the background.                                                          │
│  ✅ Write latency = only the primary's own local disk write.                    │
│  ❌ If the primary dies before the replica catches up, those last few             │
│     writes are GONE — the client was told "success" for data that no                │
│     longer exists anywhere.                                                             │
│                                                                                              │
│  SEMI-SYNCHRONOUS (the production-default middle ground): Primary waits      │
│  for AT LEAST ONE replica to ACK (not all of them), then responds.               │
│  ✅ Bounds the data-loss window to "at most what wasn't yet sent to ANY            │
│     replica" — much tighter than full-async, without paying the full                  │
│     latency cost of waiting for every replica.                                             │
└─────────────────────────────────────────────────────────────────┘
```
This is literally the same C-vs-A trade-off from §2.1, just relocated from
"during a network partition" to "on every single write, all the time" —
which is exactly the PACELC insight from §1.4: even with no partition
happening right now, you're still trading latency for durability
guarantees on every write.

#### 3.2.2 The failure scenario replication exists to survive, and why it's dangerous

```
┌─────────────────────────────────────────────────────────────────┐
│  Primary dies. A replica must be PROMOTED to take over. This sounds        │
│  simple and is actually one of the most failure-prone moments in a            │
│  database's operational life, for one specific reason:                            │
│                                                                                        │
│  If TWO replicas both believe the primary is dead (e.g. each can reach            │
│  clients but not each other — a partition, not an actual primary death)               │
│  and each independently promotes itself, you now have TWO primaries                     │
│  both accepting writes — this is exactly the split-brain scenario                          │
│  described in §6 (Consensus), and it's why real failover systems don't                        │
│  let any single replica unilaterally decide "the primary is dead, I'll                          │
│  promote myself" — they require a QUORUM of observers to agree first.                              │
└─────────────────────────────────────────────────────────────────┘
```
The full mechanics of *how* a quorum agrees on this without also
split-brain-ing on the decision itself is the subject of §6 (Raft/Paxos) —
what matters here is recognizing that "replica promotion" is not a
standalone problem; it's an application of consensus, which is why
production Postgres failover tools (Patroni) delegate the "who is allowed
to be primary right now" decision to an external consensus store
(etcd/Consul), rather than reimplementing leader election themselves.

#### 3.2.3 LLD: Automated Failover Controller (Patroni-style)

**Class diagram:**

```
┌─────────────────────────────────┐        ┌──────────────────────────────┐
│ FailoverController                  │───uses──►│ ConsensusStore (interface)     │
├─────────────────────────────────┤        ├──────────────────────────────┤
│ - node_id: string                    │        │ + try_acquire_lock(key, ttl)    │
│ - role: enum{PRIMARY,REPLICA,        │        │ + renew_lock(key, ttl)            │
│             OBSERVER}                   │        │ + read_lock_holder(key)              │
│ - health_check_interval_ms: int          │        └──────────────────────────────┘
├─────────────────────────────────┤                          ▲
│ + run_health_loop()                       │           implements
│ + attempt_promotion()                        │                 │
│ + demote_self()                                 │      ┌─────────────────┐
│ + is_primary_reachable() -> bool                   │      │ EtcdConsensusStore│
└─────────────────────────────────┘                    │ (backed by Raft — │
                                                        │  see §6)             │
                                                        └─────────────────┘
```

**Sequence — the promotion decision, requiring quorum before acting:**

```
Replica A         Replica B          etcd (Raft-backed consensus store)
   │  health check: primary unreachable for > threshold                 │
   │  attempt_promotion()             │                                   │
   │──────────────────────────────────►│  try_acquire_lock("primary-lock",   │
   │                                     │    ttl=10s)                          │
   │                                     │  (this is a QUORUM write — etcd       │
   │                                     │   itself won't accept it unless a       │
   │                                     │   majority of ITS OWN nodes agree,         │
   │                                     │   which is exactly what prevents two          │
   │                                     │   replicas from both getting the lock)          │
   │◄────────────────────────────────────│  LOCK GRANTED to Replica A                        │
   │  Replica A promotes itself to PRIMARY                                                      │
   │                                                                                                │
                                     Replica B also independently suspects the primary is down       │
                                     │  attempt_promotion()                                             │
                                     │──────────────────────────────────►│  try_acquire_lock(...)          │
                                     │◄────────────────────────────────────│  LOCK DENIED (A already holds it) │
                                     │  Replica B stays a REPLICA, does NOT promote — split-brain avoided   │
```
Notice precisely what makes this safe: the decision "who gets to be
primary" was never made by a single replica examining its own view of the
world (which is exactly what causes split-brain) — it was delegated to a
system (etcd) whose own internal write is itself quorum-gated. This is why
you should never build ad hoc "if I can't reach the primary, promote
myself" logic directly into an application — it is silently unsafe the
instant a partition (rather than a real primary crash) is the actual
cause.

**Database schema — the cluster state a controller like Patroni tracks:**

```sql
CREATE TABLE cluster_members (
    node_id         TEXT PRIMARY KEY,
    role            TEXT NOT NULL CHECK (role IN ('PRIMARY','REPLICA','OBSERVER')),
    host            TEXT NOT NULL,
    port            INTEGER NOT NULL,
    last_heartbeat  TIMESTAMPTZ NOT NULL,
    replication_lag_bytes BIGINT,          -- how far behind the primary this replica is
    is_sync_replica BOOLEAN NOT NULL DEFAULT false  -- semi-sync: which replica(s)
                                                       -- the primary waits on before ack
);

-- The promotion lock itself typically lives in etcd/Consul, NOT this table —
-- this table is READ by monitoring/ops tooling, but the actual "who is
-- primary right now" source of truth is the consensus store's lock, because
-- this table could itself become stale/partitioned along with a dead node.
```

**API contract — health and admin endpoints a controller exposes:**

```yaml
paths:
  /cluster/status:
    get:
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  primary_node: { type: string }
                  replicas:
                    type: array
                    items:
                      type: object
                      properties:
                        node_id: { type: string }
                        lag_bytes: { type: integer }
                        is_sync: { type: boolean }
  /cluster/failover:
    post:
      description: >
        MANUAL failover trigger — forces a re-election even if the current
        primary is healthy. Requires operator confirmation; always routes
        through the same consensus-store lock as automatic failover, never
        a direct "make this node primary" bypass.
      responses:
        '202': { description: "Failover initiated, watch /cluster/status for completion" }
        '409': { description: "A failover is already in progress" }
```

### 3.3 Sharding — From "Split the Data" to a Directory-Based Router

#### 3.3.1 The intuition: what forces you to pick a sharding strategy at all

Once you've accepted (§3.1) that write throughput requires actually
splitting the data across machines, the only remaining question is: **given
a piece of data, which machine owns it?** Every sharding strategy is just a
different answer to that one lookup function, `owner(key) -> shard`, and
each answer has a different weakness that shows up under a specific kind of
load:

```
STRATEGY 1 — RANGE: owner(key) = whichever shard's declared range contains
  key (e.g. user_id 1-1000 → Shard 1).
  Intuition for why this seems obviously reasonable: it's simple, and
  range QUERIES ("give me users 500-600") stay cheap because they map to
  one shard.
  The problem this creates: if user_ids are assigned sequentially, EVERY
  new user goes to the same (last) shard — all new-user write traffic
  concentrates on one machine, defeating the entire point of sharding.

STRATEGY 2 — HASH: owner(key) = hash(key) % num_shards.
  This directly fixes Strategy 1's hotspot problem — hashing scatters
  keys uniformly regardless of their sequential creation order.
  The problem THIS creates: range queries now have to ask EVERY shard
  ("give me users 500-600" could be scattered across all N machines),
  and — the more operationally painful issue — adding a shard changes
  `% num_shards` for almost every key, forcing a near-total data
  reshuffle (consistent hashing, covered fully in the Distributed
  Systems file §5/§14, exists specifically to fix THIS problem, by making
  only ~1/N of the keys move when a node is added instead of nearly all
  of them).

STRATEGY 3 — DIRECTORY-BASED: owner(key) = whatever a separate lookup
  service says it is, right now, looked up explicitly rather than computed.
  This fixes BOTH previous problems — you can rebalance by just updating
  the lookup table, no formula-driven mass reshuffle — at the cost of
  introducing a new component (the directory) that must itself be fast
  and highly available, since now EVERY query needs it.

STRATEGY 4 — GEOGRAPHY-BASED: owner(key) = the shard for the user's
  region (compliance/latency driven, not a load-balancing mechanism at all
  — a US user's data simply must not live on a shard physically located
  in the EU, independent of load).
```
Directory-based is the one that's a genuine standalone component (a real
service you'd build and operate), so it gets the full LLD treatment below.

#### 3.3.2 LLD: Directory-Based Shard Router

**Class diagram:**

```
┌─────────────────────────────────┐
│ ShardRouter                        │
├─────────────────────────────────┤
│ - directory: ShardDirectory         │
│ - directory_cache: LRUCache            │  # caching the directory lookup
│                                            │  is essential — see edge cases
├─────────────────────────────────┤
│ + get_shard_for(key) -> ShardConnection    │
│ + route_query(key, query) -> QueryResult      │
└─────────────────────────────────┘
            │ uses
            ▼
┌─────────────────────────────────┐
│ ShardDirectory                     │
├─────────────────────────────────┤
│ + lookup(key) -> shard_id             │
│ + reassign_range(key_range, new_shard) │  # the operation that makes
│                                            │  rebalancing possible without
│                                            │  a mass data reshuffle
└─────────────────────────────────┘
            │ backed by
            ▼
┌─────────────────────────────────┐
│ shard_assignments (table, itself       │
│ REPLICATED for availability — the        │
│ directory becoming unavailable would       │
│ take down EVERY shard lookup, so this        │
│ table is the highest-value thing to           │
│ protect in the whole architecture)               │
└─────────────────────────────────┘
```

**Database schema:**

```sql
CREATE TABLE shard_assignments (
    range_start     BIGINT NOT NULL,
    range_end       BIGINT NOT NULL,
    shard_id        TEXT NOT NULL,
    version         INTEGER NOT NULL DEFAULT 1,   -- incremented on every
                                                     -- reassignment, used to
                                                     -- detect stale cached
                                                     -- lookups on the router
    PRIMARY KEY (range_start, range_end)
);

CREATE TABLE shards (
    shard_id    TEXT PRIMARY KEY,
    host        TEXT NOT NULL,
    port        INTEGER NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('ACTIVE','DRAINING','MIGRATING'))
);
```

**Sequence — routing a normal request:**

```
Client        ShardRouter       DirectoryCache    ShardDirectory     Shard-7
  │  GET /users/12345              │                    │                  │
  │──────────────►│                                     │                  │
  │                │  cache.get(hash_range(12345))            │                  │
  │                │─────────────►│                                │                  │
  │                │◄─────────────│  MISS                             │                  │
  │                │  directory.lookup(12345)                             │                  │
  │                │─────────────────────────────────►│                    │                  │
  │                │◄─────────────────────────────────│  shard_id="shard-7"    │                  │
  │                │  cache.put(range, "shard-7", ttl=60s)                     │                  │
  │                │  execute query on shard-7                                    │                  │
  │                │────────────────────────────────────────────────────────►│                  │
  │◄───────────────│◄────────────────────────────────────────────────────────│ result             │
```

**Sequence — live resharding without downtime (the operation this whole
strategy exists to make possible):**

```
Operator       ShardDirectory     Shard-7 (old)    Shard-12 (new)     Router (many instances)
  │ reassign_range(shard-7 hot range, → shard-12)  │                    │                          │
  │──────────────►│                                    │                    │                          │
  │                │  1. Start DUAL-WRITE: new writes to      │                    │                          │
  │                │     this range go to BOTH shard-7             │                    │                          │
  │                │     and shard-12 (background job)                │                    │                          │
  │                │  2. Backfill existing data: copy               │                    │                          │
  │                │     shard-7's range → shard-12                    │                    │                          │
  │                │  3. Verify: row counts / checksums match             │                    │                          │
  │                │  4. Flip shard_assignments.shard_id,                    │                    │                          │
  │                │     bump `version`                                        │                    │                          │
  │                │  5. Stop dual-write, shard-7's copy of                       │                    │                          │
  │                │     the range becomes dead data (cleaned up                     │                    │                          │
  │                │     later)                                                          │                    │                          │
  │                │                                                                          │                          │
  │                │  Every router instance's CACHED lookup for this range is now STALE           │
  │                │  for up to `ttl` seconds — this is why version numbers matter: a router          │
  │                │  that gets a stale-shard response can check `version` and refresh its              │
  │                │  cache immediately rather than waiting for TTL expiry                                │
```

**API contract:**

```yaml
paths:
  /admin/shards/reassign:
    post:
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                range_start: { type: integer }
                range_end: { type: integer }
                target_shard: { type: string }
      responses:
        '202':
          description: >
            Reassignment initiated. Progresses through DUAL_WRITE →
            BACKFILLING → VERIFIED → CUTOVER phases; poll
            /admin/shards/reassign/{id}/status for progress. The affected
            key range remains fully available for reads and writes
            throughout — this is a zero-downtime operation by design.
```

**Edge cases:**

| Edge case | Behavior | Why |
|---|---|---|
| Router's cached shard assignment is stale mid-migration | Query routed to the OLD shard still succeeds (dual-write period) or gets a version-mismatch signal forcing a cache refresh | The dual-write window (§3.3.2 sequence) exists specifically so a stale router never causes a hard failure, only a brief extra hop |
| Directory itself becomes unavailable | ALL shard lookups fail — this is why the directory must be replicated (§3.2) and cached aggressively at the router | The directory being a SPOF is the acknowledged cost of directory-based sharding (V1 called this out); mitigating it is non-negotiable, not optional hardening |
| Backfill during migration falls behind due to high write volume | Cutover step (4) is deliberately blocked until verification (step 3) passes | Cutting over before the backfill is verified complete would silently lose or misplace writes that landed only on the old shard after the backfill snapshot was taken |
| Hot range needs splitting, not just moving (single range is itself overloaded) | `reassign_range` generalizes to a SPLIT: one range → two smaller ranges, potentially on two different shards | The directory model handles this naturally — it's just two rows in `shard_assignments` instead of one, no different mechanism needed |

### 3.4 Database Performance Optimization — From "Why Is This Slow" to Concrete Fixes

#### 3.4.1 Connection Pooling — the intuition first

A Postgres connection is not a lightweight object — each one spawns a
dedicated OS process with its own memory overhead (typically several MB).
An application server that opens a new DB connection per incoming HTTP
request is, at any real scale, asking Postgres to spawn and tear down
hundreds of full processes per second — this is expensive on its own,
before a single query even runs, and it's the actual root cause the first
time someone sees "too many connections" errors under load that seemingly
has nothing to do with query complexity.

```
┌─────────────────────────────────────────────────────────────────┐
│  WITHOUT POOLING                     WITH POOLING (PgBouncer)        │
│  2,500 app requests                    2,500 app requests                │
│       ↓ (each opens its OWN               ↓ (each borrows a connection      │
│         connection)                          from a small pre-existing pool) │
│  2,500 Postgres processes                 500 actual Postgres connections      │
│  ❌ Postgres falls over                     ✅ Postgres sees a stable, small,     │
│     from process/memory overhead              known connection count               │
└─────────────────────────────────────────────────────────────────┘
```

**PgBouncer config (transaction-mode pooling — the production default):**

```ini
# pgbouncer.ini
[databases]
orders_db = host=postgres-primary port=5432 dbname=orders

[pgbouncer]
listen_port = 6432
pool_mode = transaction   # connection is returned to the pool as soon as
                           # the CURRENT TRANSACTION ends, not when the
                           # client disconnects — this is what lets 500
                           # backend connections serve 2,500 concurrent
                           # clients: most connections spend most of their
                           # time idle between transactions
max_client_conn = 3000
default_pool_size = 500
reserve_pool_size = 50     # extra connections held back for burst spikes,
                             # released only when default_pool_size is
                             # fully exhausted
```
**The trade-off transaction-mode pooling forces you to accept**: session-
level features that depend on state persisting BETWEEN transactions on the
same physical connection (e.g. `SET search_path`, session-level temp
tables, advisory locks held across transactions) silently break, because
the next transaction from the "same" client might physically land on a
different backend connection. This is the single most common PgBouncer
production surprise — always check whether your ORM or driver relies on
session state before adopting transaction-mode pooling.

#### 3.4.2 Indexing — the intuition first, then a real EXPLAIN ANALYZE walkthrough

Without an index, finding a row means a **sequential scan** — reading
every row in the table and checking if it matches, O(n). A B-Tree index
is a sorted structure that lets the database jump directly toward the
answer, O(log n) — the same principle from §2.6.1's B-Tree explanation,
just applied to equality/range lookups instead of full-text search.

```sql
-- Without an index on customer_id:
EXPLAIN ANALYZE SELECT * FROM orders WHERE customer_id = 42;
--  Seq Scan on orders  (cost=0.00..18334.00 rows=50 width=120)
--                      (actual time=0.02..145.30 rows=48 loops=1)
--    Filter: (customer_id = 42)
--    Rows Removed by Filter: 999952        <-- scanned ~1M rows to find 48

CREATE INDEX idx_orders_customer_id ON orders(customer_id);

EXPLAIN ANALYZE SELECT * FROM orders WHERE customer_id = 42;
--  Index Scan using idx_orders_customer_id on orders
--                      (cost=0.43..8.45 rows=50 width=120)
--                      (actual time=0.015..0.045 rows=48 loops=1)
--    Index Cond: (customer_id = 42)         <-- ~3000x faster, jumped
--                                               straight to the matching rows
```

**Covering indexes — the next optimization once basic indexing is in
place**: even with the index above, Postgres still has to fetch the full
row from the table's heap to get columns not in the index (a "heap
fetch"). A **covering index** includes every column the query needs
directly in the index itself, letting Postgres answer entirely from the
index without touching the heap at all:

```sql
-- Query only ever needs customer_id (to filter) and total_amount (to sum):
CREATE INDEX idx_orders_covering ON orders(customer_id) INCLUDE (total_amount);

EXPLAIN ANALYZE SELECT total_amount FROM orders WHERE customer_id = 42;
--  Index Only Scan using idx_orders_covering on orders
--    (no heap fetch at all — "Heap Fetches: 0" in the actual output)
```

**The cost this doesn't show for free**: every index added speeds up
reads but slows down writes (every `INSERT`/`UPDATE` must also update every
index on that table) and consumes additional disk space. "Just add an
index" is not free optimization — it's a read/write trade-off exactly like
every other pattern in this document, and the same discipline (§19.4 NFRs:
what's the actual read:write ratio for this table) applies to deciding
which columns deserve one.

#### 3.4.3 Query Optimization Checklist (Applied, Not Just Listed)

```
1. Run EXPLAIN ANALYZE before optimizing anything — guessing which query
   is slow, rather than measuring, is the most common wasted-effort trap.
2. Avoid SELECT * — fetching unused columns costs both I/O and network
   bandwidth for no benefit; it also silently defeats covering indexes
   (§3.4.2), since "every column" can never be fully covered.
3. Watch for N+1 query patterns from an ORM — the exact same problem as
   the GraphQL N+1 issue (V1 §12), just manifesting as one query per row
   in a loop instead of one resolver call per field.
4. Keep OLTP (transactional) and OLAP (analytical) workloads on physically
   separate databases — a single heavy analytics query can evict an
   entire working set from the buffer cache that transactional queries
   depend on, turning every subsequent transactional query into a
   cache-miss disk read until the cache rewarms (§4 covers this from the
   caching side in detail).
```

---


## 4. Caching Strategies & Invalidation

### 4.1 Building the Intuition: Why Cache Exists, and Why It's Actually Just Replication in Disguise

Every access to data has a cost that scales with *distance* — not
geographic distance, but distance through the memory/storage hierarchy:

```
L1/L2 CPU cache      ~1 ns
RAM                   ~100 ns        (~100x slower than L1)
SSD random read        ~100 μs        (~1,000x slower than RAM)
Same-datacenter network round trip ~0.5 ms
Cross-region network round trip     ~50-150 ms
```
A cache is nothing more than **a copy of data placed deliberately closer**
in this hierarchy than its authoritative source. Reading from Redis (RAM)
instead of Postgres (disk + a network hop) isn't a fundamentally different
operation — it's the exact same "read a value" operation, just performed
against a copy positioned to answer faster.

And here is the insight worth sitting with, because it reframes everything
that follows: **a cache is a replica** — the exact same concept from §3.2
(replication) — except deliberately allowed to be more stale, in exchange
for being faster and cheaper to place anywhere you want (in the browser, on
a CDN edge node, in application memory). Cache invalidation is hard for
precisely the same underlying reason replication consistency is hard
(§2.1, §3.2): you now have two copies of the truth, and every strategy in
this section is really just another point on the same consistency-vs-
latency spectrum from §1.3/§1.4, applied to a copy you've explicitly chosen
to make less durable and less authoritative than the source.

### 4.2 Where a Cache Lives — Each Layer Solves a Different Distance Problem

```
┌─────────────────────────────────────────────────────────────────┐
│  CLIENT-SIDE (browser cache, mobile local storage)                   │
│  Distance solved: the network round trip between user and YOUR          │
│  servers entirely — the fastest possible cache is one that never           │
│  leaves the user's device at all.                                             │
│  ✅ Zero network cost on a hit    ❌ Cannot be invalidated by the server        │
│     directly — you can only set a TTL/ETag and wait, or change the               │
│     resource's URL/version to force a fresh fetch (cache-busting)                   │
│                                                                                          │
│  SERVER-SIDE (Redis/Memcached, in application-tier memory)                                │
│  Distance solved: the trip from your application server to your primary                     │
│  database (§3.4.2's disk-seek cost).                                                            │
│  ✅ Centrally invalidatable — the server controls it directly                                       │
│  ❌ Still pays a network hop from app server to cache server (unless the                              │
│     cache is literally in-process memory, which then can't be shared                                    │
│     across multiple app instances — see the WebSocket fan-out problem                                        │
│     in V2 §12 for the exact same "in-memory doesn't work behind a                                                │
│     load balancer" issue)                                                                                          │
│                                                                                                                        │
│  CDN (edge cache, geographically distributed)                                                                          │
│  Distance solved: the physical, speed-of-light distance between a                                                        │
│  user in Singapore and your origin server in Virginia — no amount of                                                        │
│  server-side optimization fixes 150ms of unavoidable geography.                                                                │
│  ✅ Serves from a node physically near the user    ❌ Purge propagation                                                            │
│     across hundreds of edge locations is itself a distributed-consistency                                                            │
│     problem (§4.6)                                                                                                                        │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 The One Question Every Caching Strategy Answers

Once a cache exists at any layer, exactly one design question determines
its entire behavior: **relative to a write reaching the source of truth,
when does the cache find out about it?** There are only three honest
answers — notice this is structurally the same "enumerate the honest
answers" move as §1.3's consistency-model derivation and §2.1's CAP
derivation, because it's the same underlying problem wearing a different
name.

```
ANSWER 1 — "The cache finds out lazily, on the NEXT read, if at all"
  → CACHE-ASIDE (lazy loading). The application checks the cache; on a
    miss, reads the DB and populates the cache; on a WRITE, it simply
    DELETES the cache entry rather than trying to update it (deleting is
    simpler and safer than trying to keep the cached value in sync with
    exactly what was written).
  ✅ Cache only ever holds data that was actually requested; resilient to
     total cache failure (app just falls through to the DB, see §4.4.3)
  ❌ The first read after every invalidation is guaranteed to be a miss

ANSWER 2 — "The cache finds out AT THE MOMENT of the write, synchronously"
  → WRITE-THROUGH. The write path itself updates the cache and the DB
    together before telling the client it succeeded.
  ✅ Cache is never stale relative to a completed write
  ❌ Write latency now includes the cache update; if the DB write fails
     after the cache was already updated, the cache is now wrong

ANSWER 3 — "The cache is updated immediately, the DB catches up LATER"
  → WRITE-BACK (write-behind). The write lands in the cache and returns
    success immediately; a background process flushes to the DB.
  ✅ Fastest possible write path
  ❌ If the cache dies before the flush happens, that data is gone
     entirely — this is the exact same risk profile as asynchronous
     replication in §3.2.1, just relocated to the cache layer
```

### 4.4 LLD: Cache-Aside With Distributed Lock and Stampede Protection

Cache-aside is the dominant real-world pattern (answer 1 above), so it's
the one that earns the full component treatment.

#### 4.4.1 The failure this component exists to prevent

A cache entry expiring is normal and constant. The problem appears when a
**popular** key expires: the very next instant, every concurrent request
for that key sees a miss simultaneously, and — without protection — every
one of them independently queries the database at once.

```
┌─────────────────────────────────────────────────────────────────┐
│  Popular key "product:12345" expires at T=0.                        │
│  1,000 concurrent requests arrive at T=0.001s, ALL see a cache miss,   │
│  ALL independently query Postgres for the same row at the same instant.  │
│  Postgres — which was handling this load fine when 999 of those 1,000       │
│  requests were being served entirely from cache — suddenly takes 1,000        │
│  simultaneous identical queries. This is a CACHE STAMPEDE (also called            │
│  "thundering herd"), and it's a self-inflicted DB overload caused ENTIRELY           │
│  by the cache doing its job of expiring, not by any real increase in                    │
│  underlying demand.                                                                          │
└─────────────────────────────────────────────────────────────────┘
```

#### 4.4.2 Class Diagram

```
┌─────────────────────────────────┐
│ CacheAsideService                   │
├─────────────────────────────────┤
│ - cache: CacheStore                    │
│ - lock_provider: DistributedLock          │
│ - db: DataSource                             │
├─────────────────────────────────┤
│ + get(key) -> value                             │
│     value = cache.get(key)                          │
│     if value exists: return value                      │
│     lock = lock_provider.try_acquire(f"lock:{key}")        │
│     if lock acquired:                                          │
│         try:                                                       │
│             value = db.query(key)                                      │
│             cache.set(key, value, ttl=BASE_TTL + jitter())                  │
│         finally: lock_provider.release(lock)                                    │
│     else:                                                                             │
│         wait briefly, re-check cache (another request is already                        │
│         rebuilding it) — see sequence below                                                  │
│ + invalidate(key) -> void                                                                          │
│     cache.delete(key)   # on write path                                                                 │
└─────────────────────────────────┘
```

#### 4.4.3 Sequence — Stampede Protection in Action

```
Req 1 (winner)     Req 2..1000 (waiters)     Cache          DB
  │  get("product:12345")                       │               │
  │──────────────►│                                                │               │
  │                │  MISS                                              │               │
  │                │  try_acquire("lock:product:12345") → GRANTED           │               │
  │                │                                                            │               │
                    Req 2..1000 arrive nearly simultaneously, ALSO miss cache        │
  │                │                                    │  try_acquire(...) → DENIED    │               │
  │                │                                    │  (lock already held by Req 1)     │               │
  │                │                                    │  → WAIT + poll cache briefly           │               │
  │  query DB directly (only Req 1 does this)              │                                            │               │
  │───────────────────────────────────────────────────────────────────────────────────►│
  │◄───────────────────────────────────────────────────────────────────────────────────│ row
  │  cache.set("product:12345", row, ttl=300s + random_jitter(0-30s))
  │───────►│
  │  release lock                                             │
  │                                                    │  poll finds cache now populated → return it,
  │                                                    │  NEVER touched the DB
  │                                                                                    │
  RESULT: Postgres received exactly ONE query instead of 1,000 for this expiry event.
```
**Why the TTL includes random jitter, specifically**: if every popular key
were cached with an identical 300-second TTL, and many of them happened to
be populated around the same time (e.g. after a deploy that flushed the
whole cache), they'd all expire simultaneously later, recreating the exact
stampede this component exists to prevent — just delayed by 300 seconds
instead of eliminated. Jitter staggers expiry times so the herd never
reforms.

#### 4.4.4 Interaction With Cache Failure (Tying Into §18)

```
┌─────────────────────────────────────────────────────────────────┐
│  If the CACHE STORE ITSELF is down (not just a key miss, but Redis    │
│  entirely unreachable):                                                  │
│                                                                              │
│  1. A circuit breaker (§18/V2§3) around cache calls trips OPEN after         │
│     N consecutive connection failures — the app STOPS attempting cache          │
│     calls entirely rather than paying a timeout on every single request            │
│  2. Every request falls through directly to the database                             │
│  3. Database load is monitored — if it spikes dangerously, this is the                   │
│     signal to shed load (rate limit more aggressively, degrade features)                    │
│     rather than let the DB itself fall over from the sudden full-traffic                       │
│     exposure it wasn't sized for                                                                   │
│  4. Once the cache recovers, DON'T instantly resume full traffic against it —                        │
│     the half-open circuit breaker state (§18) lets a small fraction of                                  │
│     traffic hit the cache first, confirming it's stable, before fully                                      │
│     reopening — this is "gradual cache warming," and it's the same state                                     │
│     machine as any other circuit breaker, just applied to your own cache                                        │
│     instead of a downstream service                                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.5 LLD: Building an LRU Cache From First Principles

Before reaching for Redis, it's worth building the eviction logic itself
by hand once — this is also one of the most common LLD interview
questions, and the reasoning behind the data structure choice is the
actual point, not the code.

#### 4.5.1 The intuition: why eviction is needed, and why a naive approach fails

Any in-memory cache has finite space. Once full, adding a new entry
requires removing an old one — the question is *which one*. **Least
Recently Used (LRU)** answers: evict whatever hasn't been accessed in the
longest time, on the theory that data accessed recently is likely to be
accessed again soon (temporal locality — the same principle that makes CPU
caches effective in the first place).

The naive implementation — a single hash map, scan all entries for the
oldest access timestamp on every eviction — works but costs O(n) per
eviction, defeating the entire purpose of a cache meant to be fast. The
insight that fixes this: you need O(1) access by key (a hash map gives you
that) AND O(1) knowledge of "what's least recently used" (a hash map alone
does NOT give you that) — so you need a second structure purpose-built for
that second question, kept in sync with the first.

#### 4.5.2 Class Diagram — HashMap + Doubly Linked List

```
┌─────────────────────────────────┐
│ LRUCache                            │
├─────────────────────────────────┤
│ - capacity: int                        │
│ - map: HashMap<key, Node>                  │  # gives O(1) lookup by key
│ - head: Node (dummy, most-recently-used end) │
│ - tail: Node (dummy, least-recently-used end)  │  # the linked list gives
├─────────────────────────────────┤              │  O(1) "move to front" and
│ + get(key) -> value                                │  O(1) "evict from back"
│     node = map[key]                                    │
│     if node is None: return MISS                          │
│     move_to_front(node)   # this access just became          │
│                              the most recent                    │
│     return node.value                                              │
│ + put(key, value) -> void                                             │
│     if key in map: update node.value; move_to_front(node); return         │
│     if len(map) >= capacity:                                                  │
│         lru_node = tail.prev                                                     │
│         remove(lru_node); del map[lru_node.key]    # evict least-recent           │
│     new_node = Node(key, value)                                                       │
│     add_to_front(new_node); map[key] = new_node                                          │
└─────────────────────────────────┘
            │ contains
            ▼
┌─────────────────────────────────┐
│ Node                                 │
├─────────────────────────────────┤
│ + key, value                            │
│ + prev: Node, next: Node                    │  # doubly-linked so a node can
└─────────────────────────────────┘              # remove ITSELF in O(1) without
                                                  # scanning the list to find its
                                                  # neighbors
```
**Complexity, and why it's the whole point**: both `get` and `put` are
O(1) — not "fast" in some vague sense, but genuinely constant-time
regardless of cache size, because a hash map lookup is O(1) and moving a
node in a doubly-linked list (given a direct pointer to it, which the hash
map provides) is O(1). This is why the hash-map-alone approach was
insufficient: it gave you O(1) lookup but forced an O(n) scan to find the
eviction candidate — the linked list is what removes that O(n) cost.

#### 4.5.3 LRU vs LFU — When the "Recency" Assumption Is Wrong

```
LRU assumption: "recently accessed" ≈ "likely to be accessed again."
  Breaks down for: a cache serving a mix of a few very hot keys and a
  long tail of one-off requests — a single burst of one-off requests can
  evict genuinely hot keys purely because they weren't JUST accessed,
  even though they're accessed far more often overall.

LFU (Least Frequently Used) fixes this by tracking access COUNT, not
  recency, so a truly hot key survives a temporary burst of unrelated
  traffic.
  Its own new problem: a key that was extremely popular last week but is
  now irrelevant can still have a high historical count, and LFU alone
  won't evict it — production systems typically use LFU with a decay
  factor (old counts gradually lose weight) to get the benefit of both.
```

### 4.6 CDN — Pull vs Push, and the Purge Propagation Problem

#### 4.6.1 Pull-based (the common default)

```
┌─────────────────────────────────────────────────────────────────┐
│ First request for /images/product-123.jpg from a Singapore user:   │
│                                                                        │
│ User → nearest CDN edge (Singapore) → MISS → edge fetches from            │
│ origin server (Virginia) → edge CACHES the response → serves user            │
│                                                                                    │
│ EVERY SUBSEQUENT request from ANY user near that Singapore edge is served          │
│ directly from the edge — origin is never contacted again until TTL expiry            │
└─────────────────────────────────────────────────────────────────┘
```

#### 4.6.2 Push-based (for content you know in advance will be hot)

```
┌─────────────────────────────────────────────────────────────────┐
│ Origin PROACTIVELY uploads content to every edge location BEFORE any   │
│ user requests it — used for content you can predict will be immediately   │
│ hot everywhere at once (e.g. a major platform's homepage assets right         │
│ after a deploy) where waiting for the first pull-triggered miss at EACH          │
│ edge would mean thousands of users hitting a cold cache simultaneously              │
└─────────────────────────────────────────────────────────────────┘
```

#### 4.6.3 The Purge Problem — Why Invalidating a CDN Is Genuinely Hard

```
┌─────────────────────────────────────────────────────────────────┐
│  You update /images/product-123.jpg on the origin. This same file is    │
│  now cached on hundreds of geographically distributed edge nodes.          │
│  "Invalidate this" is not a single operation — it's a purge request           │
│  that must PROPAGATE to every one of those edges, and until it does,             │
│  different users in different regions see different versions of the                │
│  same resource — this is literally the eventual-consistency problem                    │
│  from §1.3/§1.3.5 (the CRDT section), just manifesting as "which edge                     │
│  node have you hit" instead of "which database replica."                                       │
│                                                                                                       │
│  Practical mitigation, used instead of relying on purges at all:                                        │
│  version the URL itself (/images/product-123.v7.jpg) — a new version is                                   │
│  a NEW cache key entirely, so there's nothing to invalidate or                                                │
│  propagate; old cached copies simply age out via TTL, never served                                               │
│  again because nothing references that URL anymore.                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.7 Buffer Cache Eviction — Why OLTP and OLAP Must Never Share a Cache

```
┌─────────────────────────────────────────────────────────────────┐
│  A database's buffer cache (the in-memory working set of "hot" pages)  │
│  is itself governed by an eviction policy (typically LRU-like). A          │
│  heavy analytics query that scans millions of rows for a report touches       │
│  a huge number of PAGES exactly once each — and by LRU's own logic, "just         │
│  accessed" pages are treated as hot and kept, EVICTING the small working             │
│  set of pages that transactional queries actually depend on repeatedly.                  │
│                                                                                                │
│  The fix is not a smarter eviction policy — it's architectural: physically                       │
│  separate OLTP and OLAP onto different database instances (§2.5's OLAP row                          │
│  explains why columnar storage suits the analytics side far better anyway),                            │
│  so a report query can never evict the transactional working set it has                                  │
│  nothing to do with.                                                                                          │
└─────────────────────────────────────────────────────────────────┘
```