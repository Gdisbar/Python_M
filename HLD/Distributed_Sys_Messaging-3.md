# Distributed Systems & Messaging — Sections 5–9 
### 5. Load Balancing & High Availability
### 6. Consensus & Distributed Coordination
### 7. Messaging & Event-Driven Architecture


> Same treatment as the Data & Storage Layer file: every topic builds from
> a single-node baseline up to the point where the problem it's solving
> genuinely appears, before presenting the formal mechanism, diagrams, and
> contracts.

---

## 5. Load Balancing & High Availability

### 5.1 Building the Intuition: This Is the Same Problem as §3.1, One Layer Up

Section 3.1 established that a single database server has a capacity
ceiling, and that once you exhaust vertical scaling you're forced to add
more machines. **Exactly the same argument applies to your application/web
tier, for exactly the same reason** — a single web server process can only
handle so many concurrent connections before CPU, memory, or open file
descriptors become the limiting factor. The fix looks identical at first:
add more servers.

```
Client → [ Server 1 ]
Client → [ Server 2 ]     ← but now: which server does each client talk to?
Client → [ Server 3 ]
```
The instant you have more than one server capable of answering the same
request, a new decision appears that had no analog with one server: *given
an incoming request, which of the N identical (or not-quite-identical)
servers should handle it?* That decision-making component is the load
balancer — it exists purely because you now have a choice to make that
didn't exist before, nothing more mystical than that.

### 5.2 Choosing Among the Pool — Deriving Each Algorithm From the Previous One's Blind Spot

The simplest possible answer is **random** — pick any server, uniformly.
This actually works reasonably well at scale (with enough requests, load
evens out statistically) but has no memory of what it just did, which
creates the opening for a slightly smarter default:

```
ROUND ROBIN — remembers which server was used last, cycles through in
  order (1,2,3,1,2,3...).
  Fixes: guarantees perfectly even DISTRIBUTION of request COUNT.
  Blind spot it doesn't fix: request count ≠ request cost. If Server 1
  happens to be mid-way through three long-running requests when its turn
  comes around again, round robin sends it a fourth anyway — it has no
  concept of a server's CURRENT load, only a rotation counter.

LEAST CONNECTIONS — tracks how many requests each server is CURRENTLY
  handling, routes to whichever has the fewest active connections.
  Fixes: naturally avoids piling onto a server that's mid-way through
  slow work, exactly round robin's blind spot.
  Blind spot it doesn't fix: connection COUNT still isn't the same as
  connection COST. A server with 2 active connections that are each
  CPU-heavy might be more loaded than one with 10 connections that are
  all cheap and about to finish.

LEAST RESPONSE TIME — actively measures how fast each server has been
  answering recently, routes to the fastest-responding one.
  Fixes: directly targets the thing you actually care about (how fast
  will THIS request be answered), not a proxy metric for it.
  Blind spot it doesn't fix: none of the above account for SESSION
  affinity — if a client's session data lives only on the server that
  handled their FIRST request (in-memory session store, no shared cache),
  routing their SECOND request somewhere else breaks the session entirely.

IP HASH — hash(client_ip) % server_count → same client always lands on
  the same server.
  Fixes: session affinity, by construction.
  Blind spot it introduces (not fixes): this is the EXACT SAME formula-
  based sharding problem from §3.3.1 (hash % num_shards) — adding or
  removing a server changes the modulus for almost every client, breaking
  affinity for nearly everyone at once, right when you're scaling (the
  worst possible time for this to happen).

CONSISTENT HASHING — fixes IP hash's rebalancing problem the same way it
  fixed sharding's in §3.3.1 — full mechanism below, since this is the one
  algorithm here that's a genuine standalone component worth the full LLD
  treatment.
```

#### 5.2.1 LLD: Consistent Hashing Ring

**The intuition, restated precisely for this context**: instead of
`hash(key) % N` (where changing N reshuffles almost everything), place
both servers AND keys on the same conceptual ring of hash values. A key
always routes to the next server clockwise from its own position. Adding
or removing a server only affects the keys between it and its
predecessor on the ring — everything else is untouched.

```
┌─────────────────────────────────┐
│ ConsistentHashRing                  │
├─────────────────────────────────┤
│ - ring: SortedMap<hash, server_id>      │  # sorted structure enables
│ - virtual_replicas_per_server: int          │  # O(log n) lookup via binary
├─────────────────────────────────┤              # search instead of scanning
│ + add_server(server_id)                            │
│     for i in range(virtual_replicas_per_server):        │
│         h = hash(f"{server_id}:{i}")                        │
│         ring[h] = server_id            # virtual nodes         │
│ + remove_server(server_id)                                        │
│     remove all virtual-node entries for this server_id                │
│ + get_server(key) -> server_id                                            │
│     h = hash(key)                                                            │
│     return ring's first entry with hash >= h (wrap to smallest              │
│            if none — the "ring" wraps around)                                   │
└─────────────────────────────────┘
```
**Why virtual replicas per physical server, specifically**: placing each
physical server just once on the ring means the ring's coverage is
determined by luck — one server could land next to another, taking a
disproportionate share of the keyspace. Placing each server at, say, 150
points on the ring averages this out — the LAW of large numbers, not
placement luck, is what gives even distribution.

**Sequence — adding a 4th server, and exactly what moves:**

```
Ring before (servers A, B, C placed at several points each):
  ... A ... B ... C ... A ... C ... B ... A ...
                              ↑
                    new key K hashes to right here → currently owned by C

Add Server D, whose virtual nodes happen to land in that same region:
  ... A ... B ... C ... D ... A ... C ... B ... A ...
                              ↑
                    key K NOW owned by D — but ONLY keys between C's
                    previous position and D's new position moved.
                    Every other key on the ring (owned by A, B, or the
                    rest of C's other virtual nodes) is COMPLETELY
                    UNAFFECTED by D joining.
```
This is the concrete, provable version of "only ~1/N keys move" — not a
rule of thumb, a direct consequence of the ring structure: a new server's
virtual nodes only ever displace the ring segment immediately preceding
each of them, nothing further away.

### 5.3 L4 vs L7 — What Information Is Actually Available at Each Layer

The trade-off here isn't arbitrary — it's a direct consequence of what
data each layer of the network stack has decoded by the time the load
balancer sees the request:

```
┌─────────────────────────────────────────────────────────────────┐
│  L4 (Transport layer): the LB sees IP + port only. It has NOT         │
│  decrypted TLS, has NOT parsed HTTP at all — it's routing based on         │
│  information available before any of that happens.                            │
│  ✅ Extremely fast — no decryption, no parsing overhead                          │
│  ❌ CANNOT route by URL path, header, or cookie, because it hasn't                  │
│     looked at any of that — the information simply isn't available yet               │
│     at this layer                                                                       │
│                                                                                              │
│  L7 (Application layer): the LB terminates TLS itself and fully parses        │
│  the HTTP request — URL, headers, cookies, body are all visible to it.          │
│  ✅ Can route /api/orders to one backend pool and /api/search to another,          │
│     can inspect a session cookie for affinity, can do content-based                    │
│     routing entirely impossible at L4                                                       │
│  ❌ Costs real CPU (decryption + parsing on every request) and adds a                       │
│     network hop's worth of latency versus a pure L4 pass-through                              │
└─────────────────────────────────────────────────────────────────┘

Use L4 for: raw TCP/UDP, databases, workloads where every microsecond of
  added latency matters and content-based routing isn't needed.
Use L7 for: HTTP APIs, microservices routing, canary/blue-green deploys —
  anything that needs to make a decision based on what's actually INSIDE
  the request, not just where it's addressed to.
```

### 5.4 Load Balancer Implementation Types — a Brief, Decision-Oriented Note

```
SOFTWARE (NGINX, HAProxy, Envoy): runs as a process on commodity hardware,
  fully configurable, scales by adding more instances behind a VIP —
  the default choice for nearly everything built today.
HARDWARE (F5 BIG-IP, Citrix ADC): dedicated appliances, extremely high
  raw throughput and built-in WAF/SSL acceleration — chosen when an
  organization has existing datacenter investment and compliance
  requirements that favor a physical appliance over software.
CLOUD-MANAGED (AWS ALB/NLB, Azure Load Balancer): the LB's own HA
  (§5.5 below) is handled entirely by the cloud provider — the most common
  choice specifically BECAUSE it eliminates the "who load-balances the
  load balancer" problem discussed next, by making it someone else's
  managed responsibility.
```

### 5.5 The Load Balancer Itself Becomes a SPOF — the Same Recursive Problem, One Layer Up

Here's the twist most explanations skip: **you introduced the load
balancer specifically to eliminate a single point of failure (one
overloaded server) — but the load balancer itself is now, by construction,
a single point of failure.** If it goes down, it doesn't matter that you
have five perfectly healthy backend servers behind it; nothing can reach
them. This is the exact same shape of problem as §3.2's primary-database
SPOF, just recursively appearing one layer higher in the stack — and the
fix is structurally the same idea: make the thing that used to be "the one
box" into a small, consensus-coordinated cluster of its own.

#### 5.5.1 LLD: A Health-Checking, Self-Healing Load Balancer

**Class diagram:**

```
┌─────────────────────────────────┐
│ LoadBalancer                        │
├─────────────────────────────────┤
│ - backend_pool: BackendPool             │
│ - routing_strategy: RoutingStrategy         │  # Strategy pattern — swap in
│ - health_checker: HealthChecker                 # RoundRobin, LeastConnections,
├─────────────────────────────────┤              # or ConsistentHashRing (§5.2.1)
│ + route(request) -> Response                        │  without changing this class
│     healthy = backend_pool.get_healthy_backends()      │
│     target = routing_strategy.select(healthy, request)    │
│     return forward(request, target)                          │
└─────────────────────────────────┘
            │                              │
            ▼                              ▼
┌─────────────────────┐        ┌─────────────────────────┐
│ BackendPool             │        │ HealthChecker               │
├─────────────────────┤        ├─────────────────────────┤
│ + backends: List<Backend>│        │ + check_interval_ms: int        │
│ + get_healthy_backends()   │        │ + run_loop()                        │
│ + mark_unhealthy(id)          │        │     for backend in pool.backends:       │
│ + mark_healthy(id)               │        │         ok = ping(backend, timeout=2s)    │
└─────────────────────────┘        │         if not ok: consecutive_failures++      │
                                    │         if consecutive_failures >= 3:              │
                                    │             pool.mark_unhealthy(backend.id)             │
                                    │         else if ok: pool.mark_healthy(backend.id)          │
                                    └─────────────────────────┘
```

**Sequence — a backend silently degrading and being removed from
rotation:**

```
HealthChecker         Backend-3            BackendPool         LoadBalancer
   │  ping (every 5s)     │                     │                    │
   │─────────────►│                              │                    │
   │◄─────────────│ 200 OK (healthy)                 │                    │
   │  ...time passes, Backend-3 starts failing (e.g. DB connection    │
   │  exhaustion on that instance)...                                     │
   │  ping                 │                     │                    │
   │─────────────►│                              │                    │
   │   X  (timeout, consecutive_failures=1)         │                    │
   │  ping (5s later)      │                     │                    │
   │─────────────►│                              │                    │
   │   X  (timeout, consecutive_failures=2)         │                    │
   │  ping (5s later)      │                     │                    │
   │─────────────►│                              │                    │
   │   X  (timeout, consecutive_failures=3 → THRESHOLD)                │
   │  mark_unhealthy("backend-3")                     │                    │
   │───────────────────────────────────►│                                    │
   │                                       │  Backend-3 removed from             │
   │                                       │  get_healthy_backends() results       │
   │                                       │                                          │
   │                                       │  new client request arrives                │
   │                                       │◄────────────────────────────────────────►│
   │                                       │  returns [Backend-1, Backend-2] only         │
   │                                       │  (Backend-3 silently excluded, client            │
   │                                       │  never sees a single failed request)               │
```
**Why 3 consecutive failures, not 1**: a single missed health check is far
more often a transient blip (a GC pause, a momentarily busy CPU) than a
genuine outage. Requiring several consecutive failures avoids flapping a
perfectly healthy backend in and out of rotation over noise — the same
"don't overreact to one data point" principle behind the circuit breaker's
own threshold tuning (§18).

#### 5.5.2 LLD: Making the Load Balancer Itself Redundant (Active-Passive via VRRP)

```
┌─────────────────────────────────────────────────────────────────┐
│  Two LB instances share ONE virtual IP (VIP) that clients actually     │
│  connect to. VRRP (Virtual Router Redundancy Protocol, implemented        │
│  via keepalived) elects a MASTER that owns the VIP; the other stands          │
│  by, ready to claim it.                                                          │
└─────────────────────────────────────────────────────────────────┘
```

**Sequence — the failover:**

```
LB-Primary (MASTER, owns VIP)      LB-Standby (BACKUP)
   │  broadcasts VRRP advertisement every 1s ("I'm alive, I own the VIP")│
   │───────────────────────────────►│                                    │
   │  (LB-Primary crashes / network fails)                                  │
   │   X                              │  advertisement missing for 3           │
   │                                  │  intervals (master_down_interval)         │
   │                                  │  → LB-Standby PROMOTES ITSELF                │
   │                                  │  → claims the VIP via a gratuitous ARP           │
   │                                  │    announcement ("this IP is now MY               │
   │                                  │    MAC address") so the network's                    │
   │                                  │    switches/routers immediately redirect                │
   │                                  │    traffic to LB-Standby, with NO DNS                       │
   │                                  │    change and NO client reconfiguration                        │
   │                                  │    required — the IP address itself just                          │
   │                                  │    moved to a different physical machine                              │
```
**Why this is a good pattern to know cold**: it's the same "who's allowed
to be in charge right now" problem as §3.2's database failover, but
solved with a simpler, purpose-built protocol (VRRP) rather than a general
consensus store — because a load balancer's failover decision only ever
involves two peers watching a heartbeat, not an arbitrary-sized cluster
needing majority agreement. Recognizing when the simpler VRRP-style
mechanism suffices versus when you actually need Raft/etcd-backed
consensus (§6) is itself an architectural judgment call worth being able
to articulate explicitly.

#### 5.5.3 API Contract — LB Admin/Observability Surface

```yaml
paths:
  /lb/backends:
    get:
      responses:
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  backends:
                    type: array
                    items:
                      type: object
                      properties:
                        id: { type: string }
                        status: { type: string, enum: [HEALTHY, UNHEALTHY, DRAINING] }
                        active_connections: { type: integer }
  /lb/backends/{id}/drain:
    post:
      description: >
        Gracefully removes a backend from new-request rotation WITHOUT
        killing its existing in-flight connections — used before a planned
        deploy/restart, distinct from mark_unhealthy (which is for
        detected failures). Existing connections are allowed to finish
        naturally; the backend receives zero NEW requests from the moment
        this is called.
      responses:
        '202': { description: "Draining initiated" }
```

### 5.6 Availability Math — Turning "High Availability" Into a Number You Can Defend

```
┌─────────────────────────────────────────────────────────────────┐
│  Two 9s (99%)     ≈ 3.65 days downtime/year                          │
│  Three 9s (99.9%)  ≈ 8.76 hours/year                                     │
│  Four 9s (99.99%)   ≈ 52.6 minutes/year                                       │
│  Five 9s (99.999%)   ≈ 5.26 minutes/year                                            │
│                                                                                          │
│  CHAINED DEPENDENCIES MULTIPLY, not add:                                                    │
│  If your request path is Client → LB → Service A → Service B → DB, and                        │
│  each hop is independently 99.9% available:                                                       │
│    0.999 × 0.999 × 0.999 × 0.999 ≈ 0.996 → effectively 99.6%, NOT 99.9%              │
│  Every additional hop in a synchronous call chain taxes the END-TO-END                            │
│  availability, even if every individual hop looks fine in isolation on its                            │
│  own dashboard — this is why a design review should count hops, not just                                │
│  check each service's individual SLO in isolation.                                                          │
└─────────────────────────────────────────────────────────────────┘
```
**The concrete architectural consequence**: going from three 9s to four 9s
is not a linear engineering effort — it typically requires moving from
active-passive (one region serving, one on standby) to active-active
(multiple regions serving simultaneously, load balanced globally via DNS
or Anycast), because a passive standby still has a non-zero failover
detection-and-promotion time (the VRRP `master_down_interval` above, or
the etcd lock TTL in §3.2) that an active-active setup with global load
balancing doesn't pay at all — traffic simply continues being served by
whichever regions remain healthy, with no promotion step in the critical
path.

---

## 6. Consensus & Distributed Coordination

### 6.1 Building the Intuition: Generalizing the Split-Brain Problem From §3.2

Section 3.2.2 showed one specific instance of a problem: two database
replicas, both suspecting the primary is dead, both trying to promote
themselves. Strip away the "database" framing and what's left is a
completely general problem that appears anywhere more than one node might
need to make an exclusive decision: **any time multiple nodes must agree
on a single value — who's the leader, what order two writes happened in,
whether a transaction committed — a node that decides unilaterally, based
only on its own local view of the world, can be wrong in exactly the way
§1.1's first fallacy warned about: it cannot distinguish "my peer is dead"
from "my peer is merely unreachable to me right now."**

```
┌─────────────────────────────────────────────────────────────────┐
│  Naive approach: "whichever node notices the leader is unreachable   │
│  first gets to become the new leader."                                  │
│                                                                              │
│  Before partition: Node A (leader), Node B, Node C                            │
│  Partition splits the network: [Node A] | [Node B, Node C]                       │
│                                                                                      │
│  Node A still thinks it's the leader (it hasn't crashed — it just can't            │
│  reach B or C). Node B, unable to reach A, decides A is dead and promotes             │
│  ITSELF. Now there are TWO nodes both believing they are the sole leader,                 │
│  both potentially accepting writes — this is split-brain, and it happened                    │
│  even though every individual node behaved "reasonably" given only its own                       │
│  local information.                                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

The fix has to remove the word "unilaterally" from that sentence: no node
should be allowed to make this decision alone. It must instead require
confirmation from **enough other nodes that it's mathematically impossible
for two separate groups to both think they've gotten that confirmation at
the same time.** That number has a name, and the reasoning behind it is
worth deriving explicitly rather than just citing:

```
For N total nodes, define a MAJORITY as any group of at least
floor(N/2) + 1 nodes.

Claim: during any partition, AT MOST ONE side of the split can contain a
majority.

Proof: suppose both side X and side Y each independently contained a
majority. Then |X| + |Y| > N (each is more than half). But X and Y are
different nodes on different sides of a partition, so they don't overlap
— meaning the total node count would have to be MORE than N, which
contradicts there only being N nodes total. Contradiction — so this
cannot happen. At most one side can ever have a majority at the same time.
```
This single proof is the entire reason "majority vote" — not "first to
notice," not "any 2 out of however many happen to be reachable" — is the
mechanism every consensus algorithm (Raft, Paxos) and every quorum-based
system (Cassandra, Dynamo) builds on. It's not a convention; it's the
minimum threshold that makes split-brain mathematically impossible.

### 6.2 Raft — Solving Two Sub-Problems: Who Leads, and In What Order

Raft exists to answer exactly two questions using the majority principle
from §6.1: **(1) at any given moment, who is the one node allowed to make
decisions (the leader)?** and **(2) once there's a leader, how do all nodes
agree on the exact order that writes happened in (the replicated log)?**
These are handled by two distinct sub-protocols.

#### 6.2.1 Leader Election — Building It Up From "Just Vote"

The obvious idea: when a node hasn't heard from a leader in a while, it
asks everyone else to vote for it, and if it gets a majority, it becomes
leader. The immediate problem with the obvious idea: **if every follower
uses the exact same timeout duration**, they'll all notice the leader is
missing at almost exactly the same moment, all become candidates
simultaneously, and split the vote — nobody gets a majority, and (with
fixed timeouts) this could repeat forever.

```
┌─────────────────────────────────────────────────────────────────┐
│  THE FIX: each node picks a RANDOMIZED election timeout (e.g.           │
│  somewhere between 150-300ms) instead of a fixed one.                       │
│                                                                                  │
│  Why randomization specifically breaks the tie: with random timeouts,             │
│  it becomes very likely that ONE node's timer expires meaningfully                    │
│  before the others', so it becomes a candidate and requests votes BEFORE                 │
│  any other node's timer has even expired — by the time the others would                     │
│  have become candidates themselves, they instead receive a vote request                        │
│  and (having not voted yet this term) simply vote for the first candidate.                         │
│  Only in the unlucky case of a near-simultaneous tie does a split vote                                │
│  happen at all — and even then, each node picks a NEW random timeout for                                 │
│  the next round, so a repeated tie becomes exponentially less likely each                                    │
│  retry, not a permanent deadlock.                                                                                │
└─────────────────────────────────────────────────────────────────┘
```

**Class diagram — a Raft node's complete state:**

```
┌─────────────────────────────────┐
│ RaftNode                            │
├─────────────────────────────────┤
│ PERSISTENT STATE (written to disk       │  # must survive a crash+restart —
│ before responding to any RPC —             │  this is THE critical safety
│ this durability requirement is NOT           │  property; skipping it allows
│ optional, see the safety note below):           │  a node to vote twice in the
│   - current_term: int                              │  same term after a restart,
│   - voted_for: node_id? (this term)                    │  which can elect two leaders
│   - log: List<LogEntry{term, command}>                     │  for the same term
│                                                                 │
│ VOLATILE STATE (fine to lose on restart,                          │
│ safely rebuilt from persistent state + peers):                       │
│   - commit_index: int                                                    │
│   - last_applied: int                                                        │
│   - role: enum{FOLLOWER, CANDIDATE, LEADER}                                       │
│   - (LEADER only) next_index[peer], match_index[peer]                                │
│                                                                                            │
│ + on_election_timeout()                                                                        │
│ + handle_request_vote(req) -> RequestVoteResponse                                                    │
│ + handle_append_entries(req) -> AppendEntriesResponse                                                    │
└─────────────────────────────────┘
```

**Sequence — election with a near-tie split vote, resolved by retry:**

```
Node A (timeout≈152ms)   Node B (timeout≈149ms)   Node C
   │                          │  timer fires FIRST (149ms < 152ms)   │
   │                          │  term:1→2, votes for self, sends        │
   │                          │  RequestVote(term=2) to A and C              │
   │◄─────────────────────────│                                              │
   │  A's timer ALSO about to fire (152ms, very close) — A becomes             │
   │  a candidate for term 2 independently, in the same tiny window                │
   │  A votes for itself, term 2, sends RequestVote(term=2) to B and C                 │
   │──────────────────────────►│                                                        │
   │                          │◄─────────────────────────────────────►│
   │      B receives A's RequestVote(term=2): B already voted for            │
   │      ITSELF this term → B rejects A's request (already voted)             │
   │      A receives B's RequestVote(term=2): same situation, A rejects            │
   │  Node C receives BOTH requests, votes for WHICHEVER ARRIVED FIRST                  │
   │  (say, B's) → B gets C's vote. B now has 2 of 3 votes (itself + C)                    │
   │  = MAJORITY → B becomes leader for term 2.                                                │
   │  A never reaches majority (only itself) → A's election TIMES OUT,                            │
   │  A reverts to follower, picks a NEW random timeout for next time                                │
```
Notice this resolved in a single retry cycle, not indefinitely — the
randomized timeout is what makes an exact repeated tie increasingly
unlikely each time it's retried.

#### 6.2.2 Log Replication — Agreeing on Order, With a Lagging Follower

Once a leader is elected, every write is appended to the leader's log and
must be replicated to a majority before it's considered "committed" —
directly applying the §6.1 majority guarantee to writes themselves, not
just to leader elections.

```
┌─────────────────────────────────┐
│ LogEntry                            │
├─────────────────────────────────┤
│ + term: int      (which leader's term created this entry — used to        │
│                    detect and discard entries from a leader that turned       │
│                    out to be stale/wrong)                                        │
│ + index: int      (position in the log)                                             │
│ + command: bytes  (the actual operation, e.g. "SET x=5")                                │
└─────────────────────────────────┘
```

**Sequence — a follower that's fallen behind, being brought back into
consistency (the `nextIndex` back-off mechanism):**

```
Leader                                Follower-C (fell behind after a
                                        temporary network drop, missing
                                        the last 3 entries)
  │  AppendEntries(prevLogIndex=10, prevLogTerm=4, entries=[11])            │
  │─────────────────────────────────────►│                                       │
  │                                        │  Follower checks: "do I have an        │
  │                                        │  entry at index 10 with term 4?"          │
  │                                        │  NO (Follower-C is missing entries          │
  │                                        │  8-10 entirely) → REJECT                       │
  │◄─────────────────────────────────────│  AppendEntriesResponse(success=false)             │
  │  Leader decrements next_index[Follower-C] by 1, retries with an              │
  │  EARLIER prevLogIndex                                                             │
  │  AppendEntries(prevLogIndex=9, prevLogTerm=4, entries=[10,11])                       │
  │─────────────────────────────────────►│                                                    │
  │                                        │  still missing index 9 too → REJECT again            │
  │◄─────────────────────────────────────│                                                            │
  │  ... this repeats, decrementing next_index each time, until ...                                │
  │  AppendEntries(prevLogIndex=7, prevLogTerm=4, entries=[8,9,10,11])                                 │
  │─────────────────────────────────────►│                                                                │
  │                                        │  Follower DOES have entry 7 matching        │
  │                                        │  → accepts, appends 8,9,10,11 to catch up        │
  │◄─────────────────────────────────────│  AppendEntriesResponse(success=true)                    │
  │  Leader updates next_index[Follower-C] = 12 going forward — back to normal    │
```
**Why the leader has to walk backward one index at a time (in the naive
version) rather than just resending everything**: the leader doesn't
initially know exactly how far behind a follower is — this back-off search
finds the exact point of agreement between leader and follower logs, which
is what guarantees the follower ends up with a log that's a true, gap-free
prefix match with the leader's, never a corrupted or divergent history.
(Production Raft implementations optimize this with extra response fields
that let the leader jump back further in one round trip rather than
one-at-a-time — the mechanism above is the baseline correctness argument,
not the fastest possible version.)

#### 6.2.3 RPC Contract

```protobuf
// The two RPCs Raft is built entirely out of — everything above is
// implemented purely in terms of these two message exchanges.
message RequestVoteRequest {
  int32 term = 1;
  string candidate_id = 2;
  int32 last_log_index = 3;
  int32 last_log_term = 4;
}
message RequestVoteResponse {
  int32 term = 1;
  bool vote_granted = 2;
}

message AppendEntriesRequest {
  int32 term = 1;
  string leader_id = 2;
  int32 prev_log_index = 3;
  int32 prev_log_term = 4;
  repeated LogEntry entries = 5;   // empty = this is just a heartbeat
  int32 leader_commit = 6;
}
message AppendEntriesResponse {
  int32 term = 1;
  bool success = 2;
}
```
Heartbeats are literally `AppendEntriesRequest` with an empty `entries`
list, sent periodically by the leader — this is also what resets every
follower's election timeout (§6.2.1), which is why a genuinely dead leader
(heartbeats stop) and a genuinely alive one (heartbeats continue) are the
only two states a follower needs to distinguish; there's no separate
"leader health check" mechanism, the replication protocol itself doubles
as the liveness signal.

### 6.3 Quorum Reads/Writes — Tuning the Same Trade-off Per-Request

Raft gives you strong consistency but pays a full round trip through the
leader on every single operation. Section 1.4 already showed that not
every read needs that guarantee — Dynamo-style systems (Cassandra,
DynamoDB) generalize the exact majority argument from §6.1 into a tunable
knob, rather than a fixed all-or-nothing protocol.

```
N = replication factor (how many copies of the data exist)
W = write quorum (how many copies must ack a write before it succeeds)
R = read quorum (how many copies must respond before a read succeeds)

THE RULE, derived from the SAME pigeonhole argument as §6.1:
  If W + R > N, then any write-quorum set and any read-quorum set are
  GUARANTEED to overlap by at least one node (same proof shape as §6.1:
  if they never overlapped, W+R could be at most N, contradiction).
  That overlapping node necessarily has the latest write — so the read
  is guaranteed to see it. This is why W+R>N gives strong consistency
  WITHOUT needing a single elected leader at all.

  If W + R ≤ N, no such overlap is guaranteed — a read might land
  entirely on replicas that haven't seen the latest write yet. Cheaper
  and more available, but consciously eventually-consistent.
```

| Config (N=3) | W+R | Guarantee | Cost |
|---|---|---|---|
| W=3, R=1 | 4 | Strong (any single reader overlaps the full write set) | Slow writes (must reach ALL 3), fast reads |
| W=1, R=3 | 4 | Strong | Fast writes, slow reads (must reach ALL 3) |
| W=2, R=2 | 4 | Strong | Balanced — the common production default |
| W=1, R=1 | 2 | Eventual only | Fastest possible both ways — fine for view counters, not for inventory |

This is precisely the mechanism behind the tunable-consistency API
contract already built in §1.4 — that `consistency=strong` parameter is
implemented, under the hood, as exactly this W+R>N quorum choice (or a
Raft-routed read), not a different mechanism entirely.

### 6.4 Leader Election in Practice — You Rarely Build Raft Yourself

The point of walking through Raft's internals above isn't that you'll
implement it — it's that you'll correctly recognize when a design needs
it, and use an existing implementation (etcd, ZooKeeper) rather than
building an ad hoc "whoever notices first" mechanism like the one §6.1
showed is unsafe. The concrete pattern: **delegate the leader-election
decision to a system that already has Raft built in, using a
lease/TTL primitive.**

#### 6.4.1 LLD: Application-Level Leader Election via an etcd Lease

**Class diagram:**

```
┌─────────────────────────────────┐
│ LeaderElectionClient                │
├─────────────────────────────────┤
│ - etcd_client: EtcdClient               │
│ - lease_ttl_seconds: int = 10               │
│ - election_key: string = "/election/cron-job"│
├─────────────────────────────────┤
│ + campaign() -> bool                            │  # attempts to become leader
│     lease = etcd_client.grant_lease(ttl=10)         │
│     acquired = etcd_client.put_if_absent(               │
│         election_key, self.node_id, lease=lease)          │
│     if acquired: start_keepalive_loop(lease)                  │
│     return acquired                                              │
│ + keepalive_loop(lease)                                             │
│     every ttl/3 seconds: etcd_client.renew_lease(lease)                 │
│     # renewing at 1/3 of the TTL gives 2 missed renewals of margin           │
│     # before the lease actually expires — tolerates a couple of                │
│     # transient network blips without losing leadership unnecessarily            │
│ + resign()                                                                            │
│     etcd_client.revoke_lease(lease)  # explicit, graceful step-down                     │
└─────────────────────────────────┘
```

**Sequence — leadership handoff when the current leader crashes:**

```
Instance-A (LEADER)       etcd (Raft-backed)        Instance-B (standby)
   │  put_if_absent(key, "A", lease=10s) → SUCCESS       │                    │
   │  renew every ~3s                    │                    │
   │──────────────►│                                          │                    │
   │  (Instance-A crashes — process dies, no graceful resign)     │                    │
   │   X            │                                                │                    │
   │                │  no renewal received for 10s → LEASE EXPIRES        │                    │
   │                │  key "/election/cron-job" is AUTOMATICALLY DELETED      │                    │
   │                │  (this is the etcd server's own doing, tied directly       │                    │
   │                │  to the lease TTL — no separate "detect death" logic          │                    │
   │                │  needed anywhere)                                                  │                    │
   │                │                                          │  Instance-B was polling/     │
   │                │                                          │  watching this key, sees        │
   │                │                                          │  it's now gone                    │
   │                │◄─────────────────────────────────────────│  put_if_absent(key,"B",lease)         │
   │                │  SUCCESS (key absent, so this succeeds)         │                              │
   │                │─────────────────────────────────────────►│  Instance-B is now LEADER                  │
```
**Why this is safe against the exact split-brain scenario from §6.1**:
the `put_if_absent` operation on etcd is itself a write that must go
through etcd's own internal Raft consensus — meaning it's impossible for
two instances to both successfully `put_if_absent` the same key at the
same time, for the same reason it's impossible for two Raft nodes to both
win a majority vote in the same term. The application never has to
reimplement any of §6.1–§6.2's reasoning itself; it inherits the guarantee
by using a primitive that's already built on top of it.

#### 6.4.2 API Contract (etcd's actual lease/lock API surface)

```
gRPC / HTTP gateway (etcd v3 API):
  Lease.Grant(ttl_seconds) -> lease_id
  Lease.KeepAlive(lease_id)   -- streaming RPC, client sends periodic
                                  renewals, server streams back confirmation
  KV.Put(key, value, lease=lease_id, prev_kv=true) with a "create revision
     == 0" condition (etcd's transaction API) -- this IS the
     put_if_absent primitive above, expressed as an atomic
     compare-and-swap transaction
  Watch(key) -- lets Instance-B react the INSTANT the key is deleted,
                rather than polling on an interval
```
This is the concrete answer to "how does Kubernetes do leader election for
controllers" and "how does Patroni (§3.2) decide who's the Postgres
primary" — both are direct applications of exactly this lease pattern on
top of etcd, not a separate bespoke mechanism each.

---

## 7. Messaging & Event-Driven Architecture

### 7.1 Building the Intuition: Why Decouple in Time At All

Section 5.6 showed that a synchronous call chain (A → B → C → D) has its
availability multiplied down by every hop — if any one service in the
chain is down or slow, every request through the whole chain suffers. Look
at exactly *why* that's true: a synchronous call makes the CALLER's
success depend on the CALLEE being up **at this exact instant**. There is
no flexibility in time at all — if B is down right now, A's request fails
right now, even if B would have been fine ten seconds later.

```
Service A ──(sync HTTP call)──► Service B
  A is BLOCKED until B responds. If B is slow, A is slow. If B is down,
  A's request fails — even though A's own logic was perfectly capable of
  succeeding.
```

The fix is the same conceptual move as trading strong consistency for
eventual consistency in §1.3: instead of requiring the two parties to
interact **at the same instant**, introduce a durable intermediary that
holds the message until the second party is ready. This exchanges
"immediate execution" for "decoupled availability" — precisely the same
kind of trade discussed throughout this guide, just applied to *when work
happens* rather than *when data is readable*.

```
Service A ──► [ Durable Queue/Topic ] ◄── Service B (reads whenever ready)
  A's success now depends ONLY on the broker being up — a much simpler,
  more available dependency than "Service B, right now, at full capacity."
  If B is down for five minutes, the message just waits. Nothing is lost,
  nothing times out, A never even knows B had a problem.
```

### 7.2 Queue vs Pub/Sub — Derived From "How Many Consumers Need This?"

Once you accept a durable intermediary is the fix, exactly one question
determines its shape: **when this message is processed, should it be
processed by exactly one consumer, or does every interested consumer need
its own independent copy?**

```
"Only ONE consumer should do this work" (e.g. "charge this order" —
  charging it twice would be a bug, not a feature):
  → QUEUE (point-to-point). One message, ONE consumer takes it and it's
    gone from the queue. Naturally load-balances work across multiple
    consumer instances competing for the same queue.

"EVERY interested system needs to know this happened" (e.g. "an order was
  placed" — the notification service, the analytics pipeline, and the
  fraud-detection service ALL need to react independently, and none of
  them should "steal" the event from the others):
  → PUB/SUB (topic/fan-out). Every subscribed consumer GROUP gets its own
    full, independent copy of every message.
```
This single distinction is also exactly why Kafka is described as "a
distributed log" rather than "a queue" — as the class diagram in §7.4
will show, a Kafka topic naturally supports BOTH behaviors simultaneously
depending on how consumers are grouped, which is why it's become the
default choice when a system isn't sure in advance which shape it'll need.

### 7.3 Delivery Guarantees — the Same Ambiguity as §1.5's Idempotency Problem

Recall the exact retry ambiguity from §1.5: a caller can't always tell if
an operation succeeded or the acknowledgment was merely lost. Message
delivery has the identical ambiguity, just relocated to "did the consumer
finish processing before it crashed, or after":

```
AT-MOST-ONCE: consumer ACKs the message BEFORE processing it.
  If the consumer crashes mid-processing, the message is gone forever —
  it was already marked "delivered" from the broker's point of view.
  Acceptable only for data where losing an occasional message is truly
  harmless (a metrics ping, not an order).

AT-LEAST-ONCE: consumer ACKs the message ONLY AFTER processing completes.
  If the consumer crashes AFTER processing but BEFORE the ack reaches the
  broker, the broker — having never received the ack — will redeliver the
  same message. This means the SAME message can be processed twice.
  This is the default and correct choice for anything that matters,
  PROVIDED the consumer's processing logic is idempotent (§1.5) — this is
  the exact same fix, just applied at the message-consumer boundary
  instead of the HTTP-retry boundary.

EXACTLY-ONCE: would mean neither of the above ambiguities exist at all.
  Genuinely achievable only WITHIN a single system that can make delivery
  and processing part of one atomic transaction (Kafka's transactional
  API does this within a single Kafka cluster). The instant a message
  causes a side effect in a SEPARATE system (calling an external payment
  API, writing to a different database), true exactly-once is not
  achievable — you're back to at-least-once + idempotency (§1.5) as the
  practical, honest answer, dressed up as "effectively-once."
```

### 7.4 LLD: Kafka's Internal Model — Partitions, Offsets, Consumer Groups

#### 7.4.1 Why a topic is split into partitions at all

A single append-only log, on one machine, can only be written and read so
fast — the exact same single-node ceiling from §3.1. Kafka's answer is the
same one from §3.3: split the data (here, the STREAM of messages) across
multiple machines, each owning a slice. The "slice" in Kafka's case is
called a **partition** — and deciding which partition a given message goes
to uses the exact same `hash(key) % num_partitions` mechanism from §3.3.1's
hash-sharding, with the exact same trade-off (same key always lands on the
same partition, preserving order for that key, at the cost of a
near-total reshuffle if the partition count ever changes — which is why
partition counts are chosen deliberately up front and rarely changed
casually).

```
┌─────────────────────────────────┐
│ Topic: "order-events"               │
├─────────────────────────────────┤
│  Partition 0: [msg0, msg1, msg2, msg3, ...]   ← append-only log, each      │
│  Partition 1: [msg0, msg1, msg2, ...]            message has a sequential     │
│  Partition 2: [msg0, msg1, msg2, msg3, msg4,...] OFFSET within its partition    │
└─────────────────────────────────┘
```

#### 7.4.2 Class Diagram — Producer, Partition, Consumer Group

```
┌─────────────────────────────────┐
│ Producer                            │
├─────────────────────────────────┤
│ + send(topic, key, value, acks)         │
│     partition = hash(key) % num_partitions  │  # same key → same partition,
│     append to that partition's log             │  ordering preserved per-key
│     wait for `acks` setting to be satisfied        │  (§7.4.4 below)
└─────────────────────────────────┘

┌─────────────────────────────────┐        ┌──────────────────────────────┐
│ ConsumerGroup ("notification-svc")  │───owns──►│ PartitionAssignment              │
├─────────────────────────────────┤        ├──────────────────────────────┤
│ - consumers: List<Consumer>              │        │ partition 0 → Consumer-1            │
│ - assignment: PartitionAssignment           │        │ partition 1 → Consumer-2            │
├─────────────────────────────────┤        │ partition 2 → Consumer-2            │  # a partition
│ + rebalance()   (§7.4.5)                    │        │ (rule: EACH partition is owned  │  # is owned by
└─────────────────────────────────┘        │ by EXACTLY ONE consumer WITHIN │  # exactly one
                                            │ a given group at a time)          │  # consumer, but
                                            └──────────────────────────────┘  # a consumer can
                                                                                  own many
```
**The rule that follows directly from this structure**: you cannot usefully
have MORE active consumer instances in a group than partitions — any
extra consumer simply gets zero partitions assigned and sits idle. This is
why partition count is effectively your topic's maximum parallelism
ceiling, decided at topic-creation time.

**And the rule that gives you BOTH queue and pub/sub behavior from one
structure**: two different consumer GROUPS reading the same topic each get
their OWN full copy of every message (pub/sub, fan-out) — but multiple
consumer INSTANCES within the SAME group split the partitions between
them, each message processed by only one of them (queue-like, load
distributed). This is precisely the "supports both" property flagged in
§7.2.

#### 7.4.3 Sequence — Consumer Group Rebalance When an Instance Joins

```
Consumer-1 (owns P0,P1,P2)       Group Coordinator        Consumer-2 (new)
   │                                  │                          │
   │                                  │◄─────────────────────────│ JoinGroup request
   │  Coordinator detects a new member joined this group           │
   │◄─────────────────────────────────│  "rebalance starting, stop     │
   │                                  │   processing and rejoin"          │
   │  Consumer-1 commits its current offsets, releases all partitions   │
   │─────────────────────────────────►│                                      │
   │                                  │  Coordinator reassigns:                 │
   │                                  │    P0,P1 → Consumer-1                       │
   │                                  │    P2    → Consumer-2                          │
   │◄─────────────────────────────────│─────────────────────────────────────────►│
   │  both consumers resume from their LAST COMMITTED OFFSET per partition — this   │
   │  is exactly why manual offset commits (§7.4.4) matter: a message read but NOT     │
   │  yet committed before a rebalance WILL be redelivered to whichever consumer          │
   │  ends up owning that partition next (at-least-once, §7.3, again)                       │
```

#### 7.4.4 Producer Acknowledgment Levels — the Same W-Quorum Idea From §6.3

```
acks=0: producer doesn't wait for any confirmation at all. Fastest,
  but a message can be silently lost if the partition leader crashes
  before even receiving it durably.
acks=1: producer waits for the PARTITION LEADER to write the message to
  its own log. Faster than the option below, but if the leader crashes
  before replicating to its followers, the message can still be lost.
acks=all (or acks=-1): producer waits for the message to be written to
  every replica in the partition's ISR (in-sync replica set) — this is
  literally the W=N case from §6.3's quorum framework, applied to Kafka's
  own internal partition replication, giving the strongest durability
  guarantee at the highest latency cost.
```

### 7.5 Kafka vs RabbitMQ vs SQS — the Decision, Reasoned From Structure

| Feature | Kafka | RabbitMQ | SQS/SNS |
|---|---|---|---|
| Underlying model | Partitioned, replayable log (§7.4.1) | Traditional broker, message deleted once consumed | Fully managed queue/topic |
| Replay a past message? | Yes — offsets are just a position in the log, can rewind | No — once consumed and acked, it's gone | No |
| Ordering | Per-partition only (by design, §7.4.1) | Per-queue | FIFO queue type only |
| Best fit | Event streaming, event sourcing (§7.6), audit/log aggregation — anywhere REPLAYABILITY matters | Complex routing topologies, RPC-style request/reply patterns | Simple decoupling with near-zero operational overhead |
| Operational cost | High (self-managed) or MSK/Confluent Cloud | Moderate | Very low — fully managed |

The one property that most decisively picks Kafka over the alternatives:
**replayability**. If you ever need to reprocess history (a new service
joins that needs to build its state from every past event, or a bug in a
consumer requires reprocessing last week's events), Kafka's log-based
model supports this natively by just resetting a consumer group's offset
backward — RabbitMQ and SQS have already discarded the message the moment
it was successfully consumed, so this simply isn't possible after the
fact.

### 7.6 Event Sourcing & CQRS — LLD

#### 7.6.1 Building the intuition: what's wrong with just storing current state

A normal table stores only the CURRENT value — `accounts.balance = 90`.
This is simple, but it has thrown away the history: you cannot answer
"what was the balance last Tuesday" or "show me every event that led to
this balance" without a separate audit log bolted on afterward. **Event
sourcing inverts this**: instead of storing current state, store the
sequence of events that produced it, and treat "current state" as a
*derived* value you compute by replaying that sequence — never stored as
the primary source of truth at all.

```
Instead of:  accounts.balance = 90

Store:       AccountCreated
             Deposited($100)
             Withdrew($30)
             Deposited($20)

Current balance = replay all events = 100 - 30 + 20 = 90
```

#### 7.6.2 Class Diagram and Schema — the Event Store

```
┌─────────────────────────────────┐
│ EventStore                          │
├─────────────────────────────────┤
│ + append(aggregate_id, expected_version, events) -> void  │
│     # expected_version is OPTIMISTIC CONCURRENCY CONTROL —      │
│     # see the conflict sequence below for exactly why this        │
│     # parameter is not optional                                       │
│ + read_stream(aggregate_id, from_version=0) -> List<Event>         │
│ + read_snapshot(aggregate_id) -> Snapshot?                             │
└─────────────────────────────────┘
```

```sql
CREATE TABLE events (
    aggregate_id    TEXT NOT NULL,
    version         INTEGER NOT NULL,     -- sequential per aggregate,
                                            -- starting at 1
    event_type      TEXT NOT NULL,
    payload         JSONB NOT NULL,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (aggregate_id, version)   -- this composite PK is what
                                            -- makes optimistic concurrency
                                            -- control a simple INSERT
                                            -- conflict, not custom logic
);

CREATE TABLE snapshots (
    aggregate_id     TEXT PRIMARY KEY,
    version_as_of    INTEGER NOT NULL,
    state            JSONB NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Why snapshots exist: an aggregate with 100,000 events would need all
-- 100,000 replayed to compute current state on every read. A snapshot
-- lets you start from "state as of version 90,000" and replay only the
-- last few thousand — the exact same idea as a database checkpoint.
```

**Sequence — appending an event with a concurrency conflict (two
concurrent commands on the same aggregate):**

```
Command Handler A         EventStore              Command Handler B
   │  read_stream("acct-1") → current version = 5        │
   │◄──────────────────────│                                 │
   │  (both A and B loaded the SAME version 5 state, and       │
   │   both are about to append their own next event)               │
   │  append("acct-1", expected_version=5, [WithdrewEvent])          │
   │──────────────────────►│                                             │
   │◄──────────────────────│  SUCCESS — inserted as version 6                  │
   │                                                                │
                            │◄────────────────────────────────────│ append("acct-1",
                            │                                          expected_version=5, [...])
                            │  INSERT fails — PRIMARY KEY (acct-1, 6) already
                            │  exists from Handler A's write. The composite
                            │  key on (aggregate_id, version) makes this an
                            │  ordinary DB constraint violation, not custom
                            │  application-level locking logic.
                            │──────────────────────────────────────►│ CONFLICT — Handler B
                            │                                          must re-read the
                            │                                          now-current version 6
                            │                                          and retry its logic
                            │                                          against the up-to-date state
```
This is the exact same "detect, don't prevent" philosophy as MVCC in
traditional databases — rather than locking the aggregate for the duration
of the command (which would hurt throughput), the conflict is detected
cheaply at write time via the version number, and the loser simply retries
with fresh state.

#### 7.6.3 CQRS — Splitting the Write Model From the Read Model

Event sourcing naturally produces a write-optimized model (an append-only
event log) that's terrible for reading ("show me all accounts with
balance > $10,000" would require replaying every account's entire event
history). **CQRS** solves this by explicitly maintaining a SEPARATE,
denormalized read model, kept up to date asynchronously as events occur.

```
┌─────────────────────────────────┐
│ Projector ("AccountSummaryProjector")│
├─────────────────────────────────┤
│ + handle(event) -> void                 │
│     if event.type == "Deposited":          │
│         read_db.execute(                       │
│           "UPDATE account_summaries SET             │
│            balance = balance + $1 WHERE id=$2",         │
│           event.amount, event.aggregate_id)                │
│     # this projector is itself just another Kafka           │
│     # CONSUMER (§7.4) — event sourcing and CQRS compose         │
│     # naturally with everything already built in this section     │
└─────────────────────────────────┘
```

```
Command side (writes)              Read side (queries)
  Normalized event log                 Denormalized `account_summaries`
  (Postgres, §7.6.2 schema)              table (fast to query, optimized
  ──────event stream────────────────►    per use case — could even be
        (via Kafka, §7.4)                 Elasticsearch for search, per §2.6)
```

**API contract — commands and queries explicitly separated, not just two
endpoints on the same resource:**

```yaml
paths:
  /accounts/{id}/commands/withdraw:      # COMMAND — writes an event,
    post:                                 # returns only acceptance,
      responses:                          # NOT the resulting state
        '202':
          description: >
            Withdrawal event accepted and appended. The read model will
            reflect this change shortly (eventually consistent, §1.3) —
            poll the query endpoint below if you need to observe it.
        '409':
          description: Optimistic concurrency conflict (§7.6.2) — retry.

  /accounts/{id}/summary:                # QUERY — reads from the fast,
    get:                                  # denormalized projection,
      responses:                          # never replays events directly
        '200':
          content:
            application/json:
              schema:
                type: object
                properties:
                  balance: { type: number }
                  projection_lag_ms:
                    type: integer
                    description: >
                      How far behind the write side this read model
                      currently is — the same staleness-transparency
                      principle as §1.4's as_of_replica_lag_ms field.
```
The command/query split here is not a stylistic API choice — it's the
direct architectural consequence of accepting that the write model
(event log) and read model (projection) are now two physically different
data stores, kept consistent only eventually, and the API contract's job
is to make that lag visible rather than hide it.

---
