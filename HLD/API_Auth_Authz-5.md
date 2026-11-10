# API & Auth — Sections 10–15 

### 10. API Design Patterns & Protocols
### 11. RESTful API Design
### 12. GraphQL API Design

---

## 10. API Design Patterns & Protocols

### 10.1 Building the Intuition: Why an "API Style" Is a Decision At All

Recall §1.1's very first point: once two pieces of software are on
different machines, a function call is no longer free or implicit — it
becomes a message sent over a network, between two systems that are
deployed, versioned, and evolved **completely independently of each
other.** An API is the explicit contract that lets that communication
happen safely despite that independence — and every "API style" is really
just a different, complete answer to three questions any such contract
must settle:

```
1. How does the client tell the server WHAT it wants (address a resource,
   name an operation, specify a query)?
2. What FORMAT is the data exchanged in (text/JSON, binary/Protobuf)?
3. What's the SHAPE of the interaction itself (one request → one response,
   one request → a stream of responses, or a fully bidirectional channel)?
```
Keep these three questions in mind through the rest of this section —
every style below is a specific, opinionated answer to all three at once,
and the "right" answer for a given system is really "which combination of
answers fits how THIS client and THIS server actually need to interact."

### 10.2 Core API Styles — Each Derived From the Previous One's Blind Spot

#### 10.2.1 REST: model the world as resources

The most natural first answer to question 1 above: expose **resources**
(nouns — `/orders`, `/products`) and let standard HTTP verbs (GET, POST,
PUT, DELETE) express the operation. This maps beautifully onto CRUD, is
simple to reason about, and gets HTTP caching essentially for free
(`GET /products/42` is a stable, cacheable URL by construction).

```
Blind spot REST has, which motivates the next style:
  A mobile client rendering an order summary screen might need the order's
  basic fields, the customer's name, and the first 3 line items — but the
  `/orders/42` resource returns EVERY field and EVERY line item whether
  the screen needs them or not (OVER-fetching). Or the opposite: the
  screen needs data from three different resources (order + customer +
  product names) requiring three round trips because each is its own
  endpoint (UNDER-fetching, in the sense of needing multiple round trips
  to assemble one screen's worth of data).
```

#### 10.2.2 GraphQL: let the client specify the exact shape

GraphQL directly answers REST's blind spot: the client sends a single
query describing PRECISELY which fields it wants, across however many
underlying resources, and gets back exactly that shape in one round trip
(§7.6.3's CQRS query-side pattern and GraphQL's DataLoader batching, from
the earlier files, are both direct applications of this same idea).

```
Blind spot GraphQL introduces in fixing REST's:
  Because every query is typically sent as a POST with an arbitrary body
  (not a stable, cacheable GET URL), HTTP-level caching (CDNs, browser
  cache) mostly stops working out of the box — you need application-level
  caching schemes instead (persisted queries, normalized client-side
  caches like Apollo's). And because the SHAPE of every query can be
  arbitrary, the server must actively defend against maliciously deep or
  expensive queries (V1's GraphQL complexity-limiting) — a REST endpoint's
  cost is naturally bounded by what that ONE endpoint was built to do;
  a GraphQL query's cost is bounded only by what the schema ALLOWS a
  client to ask for.
```

#### 10.2.3 gRPC: optimize for service-to-service, not public/browser clients

gRPC answers all three foundational questions differently again: it
defines operations via a strict schema (Protocol Buffers), serializes
data in a compact binary format instead of human-readable JSON, and runs
over HTTP/2 — which natively supports multiplexing many concurrent
requests over a single connection and true bidirectional streaming.

```
Why this fits service-to-service calls (§8's internal east-west traffic)
particularly well: both ends of the call are code YOU control and deploy
together, so a strict, versioned schema (the .proto file) is a feature,
not friction — it catches contract mismatches at compile time rather than
as a runtime surprise. The binary format and HTTP/2 multiplexing directly
address raw performance, which matters most exactly where call volume
between services is highest (§7's internal messaging, §8's mesh sidecars).

Why it's usually a poor fit for public/browser-facing APIs: browsers
don't speak raw HTTP/2 gRPC natively (requires a gRPC-Web proxy layer),
and a binary payload is far harder for a third-party developer to
inspect/debug than a plain JSON response they can read directly in
devtools — the same properties that make gRPC efficient for
service-to-service make it actively worse for a public developer-facing
surface.
```

| Feature | REST | GraphQL | gRPC |
|---|---|---|---|
| Resource/operation addressing | URL + verb | Single flexible query | Strictly-typed RPC method |
| Data format | JSON/XML (readable) | JSON | Protobuf (binary, compact) |
| Over/under-fetching | Possible | Solved by design | N/A — each call is purpose-built |
| HTTP caching | Native (GET is cacheable) | Requires extra tooling | Not applicable (not cache-oriented) |
| Best fit | Public CRUD APIs, simple resources | Complex/nested data needs, mobile clients | Internal service-to-service, streaming, max performance |

### 10.3 Application Protocols — Derived From "What If Request-Response Isn't Enough?"

The default assumption behind everything in §10.2 is still: client asks,
server answers, connection closes. That assumption breaks down the moment
the SERVER needs to push data the client didn't just ask for — and each
protocol below is a different, purpose-built answer to that gap.

```
HTTPS (the default): one request, one response, connection typically
  closes or is reused for the NEXT independent request-response pair.
  Fine for anything where the client is always the one initiating.

  Blind spot: a chat app, live notifications, or a streaming LLM response
  (exactly V2 §12's WebSocket use case) all need the SERVER to send data
  to an ALREADY-CONNECTED client, potentially long after the original
  request — plain request-response has no mechanism for this at all.

WEBSOCKETS: upgrades a single HTTP connection into a persistent,
  FULLY BIDIRECTIONAL channel — either side can send a message at any
  time, no new request needed.
  ✅ Solves the gap completely — true two-way, low-latency push
  ❌ The connection itself is now stateful infrastructure your servers
     must maintain (V2 §12's exact reason a shared Redis pub/sub layer
     was needed once you have more than one server instance — a
     WebSocket connection is pinned to whichever specific server accepted
     it, unlike a stateless HTTP request that any server behind an LB
     could equally handle)

SSE (Server-Sent Events): a simpler answer for the common case where only
  ONE direction of push is actually needed (server → client), built on
  plain HTTP with automatic reconnection handled by the browser natively.
  ✅ Much simpler than a full WebSocket for read-only streaming — this is
     specifically how most LLM chat UIs stream tokens: the client sends
     ONE request, and the server streams the response back token by
     token over that same still-open HTTP connection, closing it when done
  ❌ One-directional only — no channel for the client to push data back
     without starting a completely new request

MQTT: built for a genuinely different constraint than any of the above —
  devices with extremely limited power/bandwidth (IoT sensors) sending
  small, frequent messages. HTTP's per-request overhead (headers, TLS
  handshake cost relative to a tiny payload) is disproportionately
  expensive at that scale; MQTT's lightweight pub/sub protocol with
  configurable QoS levels (at-most-once/at-least-once/exactly-once —
  the SAME delivery-guarantee spectrum from §7.3, just named identically
  in this different protocol) is purpose-built for that specific
  power/bandwidth constraint, not a general HTTP alternative.
```

### 10.4 LLD: Protocol Translation at the Gateway

Real systems often need to expose ONE public style (typically REST, for
broad client compatibility) while running gRPC internally (for the
performance benefits in §10.2.3) — this reconciliation happens at exactly
the API Gateway component already built in §8.4, extended with a
translation responsibility.

**Extending §8.4's `ApiGateway` class diagram:**

```
┌─────────────────────────────────┐
│ ApiGateway (from §8.4)              │
├─────────────────────────────────┤
│ + handle(request) -> Response           │
│     ... existing middleware chain ...       │
│     route = match_route(request.path)          │
│     if route.backend_protocol == "grpc":            │
│         grpc_request = ProtocolTranslator.              │
│             rest_to_grpc(request, route.proto_schema)      │
│         grpc_response = grpc_client.call(grpc_request)         │
│         return ProtocolTranslator.grpc_to_rest(grpc_response)      │
│     else:                                                              │
│         return forward(request, route.backend_url)  # unchanged           │
└─────────────────────────────────┘
            │ uses (new)
            ▼
┌─────────────────────────────────┐
│ ProtocolTranslator                   │
├─────────────────────────────────┤
│ + rest_to_grpc(http_request, proto_schema) -> GrpcMessage │
│     # maps JSON fields to the .proto message fields by name  │
│ + grpc_to_rest(grpc_response) -> JsonResponse                    │
│     # the reverse mapping, back to a JSON body the public        │
│     # client can actually read                                       │
└─────────────────────────────────┘
```

**Sequence — a public REST client, served by an internal gRPC service,
neither side aware of the other's protocol:**

```
Public Client        Gateway              ProtocolTranslator      Internal gRPC Service
   │  POST /api/v1/orders                     │                          │
   │  {"customer_id": "42", "amount": 100}          │                          │
   │─────────────►│                                                        │                          │
   │               │  rest_to_grpc(request, OrderService.proto)                │                          │
   │               │──────────────────►│                                        │                          │
   │               │◄──────────────────│  CreateOrderRequest{customer_id:"42",     │                          │
   │               │                       amount:100}  (binary protobuf message)   │                          │
   │               │  grpc_client.call(CreateOrderRequest)                              │                          │
   │               │───────────────────────────────────────────────────────────────►│
   │               │◄───────────────────────────────────────────────────────────────│ CreateOrderResponse
   │               │  grpc_to_rest(response)                                                    │
   │               │──────────────────►│                                                              │
   │               │◄──────────────────│  {"order_id": "ord_789", "status": "created"}                    │
   │◄─────────────│  200 OK, JSON body                                                                        │
```
Neither the public client nor the internal gRPC service had to know
anything about the other's protocol — the gateway's translation layer is
the ONLY place that reconciliation logic lives, which is exactly the
same "centralize the cross-cutting concern once" reasoning that motivated
the gateway pattern in the first place (§8.4.1).

### 10.5 LLD: API Versioning as an Operated System, Not Just a URL Prefix

#### 10.5.1 Building the intuition: why versioning needs to be OPERATED, not just decided once

Choosing `/api/v1/` vs a header vs a query param is the easy 5% of API
versioning. The hard 95% is everything that happens AFTER you ship v2:
knowing whether it's actually safe to retire v1 requires knowing, with
certainty, whether any client is still calling it — a question that "we
picked URI versioning" does nothing to answer on its own.

#### 10.5.2 Class Diagram and Schema — Tracking Real Usage, Not Guessing

```
┌─────────────────────────────────┐
│ VersionedRouter                     │
├─────────────────────────────────┤
│ + route(request) -> Response            │
│     version = extract_version(request)     │  # from URI, header, or
│     usage_tracker.record(version,               │  query param, per your
│         client_id, endpoint)                        │  chosen scheme (§10.5.4)
│     handler = registry.get_handler(version, endpoint)   │
│     if handler.deprecated:                                  │
│         response.headers["Sunset"] = handler.sunset_date        │
│     return handler.execute(request)                                  │
└─────────────────────────────────┘
```

```sql
CREATE TABLE api_version_usage (
    version         TEXT NOT NULL,
    endpoint        TEXT NOT NULL,
    client_id       TEXT NOT NULL,       -- from an API key or auth token,
                                            -- NOT just an IP — you need to
                                            -- know WHICH INTEGRATION is
                                            -- still on the old version to
                                            -- actually reach out to them
    last_called_at  TIMESTAMPTZ NOT NULL,
    call_count_24h  BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (version, endpoint, client_id)
);
-- This table is the ENTIRE difference between "we think nobody uses v1
-- anymore" (a guess) and "these exact 3 client_ids made 40 calls to v1
-- yesterday, here's who to contact before we sunset it" (a fact).
```

#### 10.5.3 Sequence — the Full Deprecation Lifecycle

```
Time T0: v2 ships. v1 marked deprecated=true, sunset_date = T0+180 days.
  Every v1 response now includes:  Sunset: Sat, 01 Aug 2026 00:00:00 GMT

Time T0+30 days: Ops queries api_version_usage — 12 client_ids still
  calling v1 daily. Outreach begins to those specific integrations
  (this is only possible because the table tracks client_id, not just
  aggregate call counts).

Time T0+150 days: usage table shows only 2 client_ids remain on v1,
  both non-responsive to outreach. Decision: proceed with sunset on
  schedule, or grant a case-by-case extension — either way, an INFORMED
  decision, not a guess made from silence.

Time T0+180 days (sunset_date reached): v1 requests now return 410 Gone
  instead of executing, with a response body pointing to the v2 migration
  guide — a deliberate, clear failure instead of a silent behavior change.
```

#### 10.5.4 API Contract

```yaml
paths:
  /api/{version}/orders/{id}:
    get:
      parameters:
        - name: version
          in: path
          schema: { type: string, enum: [v1, v2] }
      responses:
        '200':
          headers:
            Sunset:
              schema: { type: string }
              description: >
                Present ONLY on deprecated versions. RFC 8594 date after
                which this version will stop functioning. Absence of this
                header means the version is fully supported with no
                planned retirement date.
        '410':
          description: >
            This version has passed its Sunset date and is retired.
            Response body includes a `migration_guide_url` pointing to
            the current version's documentation.
```
This is the concrete artifact that turns "we version our API" from a
one-time URL-naming decision into an operated process with an actual,
evidence-based off-ramp — exactly the kind of operational discipline an
architect is expected to design in, not just the naming scheme itself.

### 10.6 Contract-First vs Code-First — a Brief, Decision-Relevant Note

```
CODE-FIRST: write the handler code, generate documentation/schema from it
  afterward (e.g. FastAPI auto-generating an OpenAPI spec from your route
  decorators and Pydantic models).
  ✅ Fast to iterate for a single team owning both client and server
  ❌ The contract can silently drift as code changes, discovered only
     when a consumer's integration breaks

CONTRACT-FIRST: write the OpenAPI/Protobuf schema FIRST, generate
  server stubs and client SDKs from it, implementation fills in the stubs.
  ✅ The contract is reviewed and agreed BEFORE any code exists — critical
     once multiple independent teams (or external partners) depend on the
     API, since a contract violation is caught at schema-review time,
     not after a consumer has already integrated against undocumented
     behavior
  ❌ Slower for a single small team that owns both ends and can just talk
     to each other directly when something needs to change
```
The deciding factor is almost always **how many independent teams consume
this API** — a single team's internal endpoint rarely justifies
contract-first's overhead; a platform API serving multiple external
partners almost always does.

---

## 11. RESTful API Design

### 11.1 Building the Intuition: the Richardson Maturity Model — What "True REST" Actually Means

Most APIs called "REST" today are really at one specific point on a
spectrum Roy Fielding's original dissertation described — and understanding
WHY each level exists (what problem moving up a level solves) is more
useful than just knowing the label "Level 2."

```
LEVEL 0 — "RPC over HTTP": one single endpoint, HTTP is just a transport
  tunnel. e.g. POST /api with {"action": "getOrder", "id": 42} in the body.
  Problem this has: NONE of HTTP's own semantics are used at all — no
  verbs, no status codes, no URL structure — every client and every piece
  of infrastructure (caches, proxies, monitoring) sees identical, opaque
  POST requests and can infer nothing about what's actually happening.

LEVEL 1 — Resources: give each thing you can act on its own URL
  (/orders/42) instead of one undifferentiated endpoint.
  Fixes: infrastructure (logs, monitoring, caches) can now at least
  distinguish WHICH resource a request concerns just from the URL.
  Doesn't fix yet: still might use POST for everything regardless of the
  actual operation, so the ACTION being performed is still opaque.

LEVEL 2 — HTTP Verbs + Status Codes: use GET/POST/PUT/DELETE to express
  the actual operation, and real status codes (404, 409, etc.) to express
  the actual outcome. THIS is what "RESTful API" means in the overwhelming
  majority of real systems today.
  Fixes: a GET is now guaranteed safe/cacheable by HTTP's own semantics
  (§10.2.1), a 404 means "not found" to EVERY piece of HTTP-aware
  infrastructure without needing custom client logic to interpret it.
  Doesn't fix yet: the client still has to hardcode knowledge of every
  URL structure and what transitions are possible from a given state —
  the API describes DATA, but not what you're allowed to DO next.

LEVEL 3 — HATEOAS (Hypermedia as the Engine of Application State): each
  response includes LINKS to the valid next actions, so a client
  discovers what it can do next by reading the response, not by having
  URL structures hardcoded in advance.
  Fixes: an order in "pending" state can literally only offer a "cancel"
  link; once "shipped," that link is simply absent from the response and
  a "track" link appears instead — the client's UI can be driven by
  what the server says is currently valid, rather than the client needing
  its own separate copy of the order's state machine rules.
```
Most production APIs deliberately stop at Level 2 — that's a legitimate,
common choice, not a failure to reach "true REST." Level 3 genuinely
solves a real problem (client/server state-machine knowledge duplication),
but at a real engineering cost (every response needs computed links, and
most client SDKs/tooling aren't built expecting to navigate this way) —
know this trade-off explicitly rather than treating Level 2 as merely
"REST done partway."

### 11.2 Resource Modeling — What Happens When an Action Doesn't Fit CRUD

CRUD verbs map naturally to "create an order," "read an order," "update an
order's shipping address," "delete an order." But what about "cancel this
order" — is that a DELETE (it's not; the order still exists, just in a
different state), a PUT (replacing the whole resource for what's really
one field changing), or something else?

```
OPTION A — Sub-resource-as-verb:
  POST /orders/42/cancel
  ✅ Explicit, discoverable, easy to add audit logging/authorization
     specific to THIS action (§14's authorization models can attach a
     distinct permission to "cancel" separately from generic "update")
  ❌ Not "pure" REST in the strictest sense (a URL segment is acting like
     a verb, not a noun) — but this is a pragmatic, extremely common and
     accepted pattern in real APIs, including large public ones (Stripe,
     GitHub both use this shape for non-CRUD actions)

OPTION B — PATCH with a status field change:
  PATCH /orders/42  { "status": "cancelled" }
  ✅ Stays within pure resource semantics — you're updating a field on
     an existing resource, nothing more
  ❌ The server must now validate that the STATE TRANSITION itself is
     legal (can you go from "shipped" directly to "cancelled"? probably
     not) — this validation logic is exactly the same state-machine logic
     the sub-resource-as-verb approach makes visible in the URL/route
     structure itself, just hidden inside a generic PATCH handler instead
```
The practical recommendation: use Option A whenever the action has
distinct authorization rules, side effects, or audit requirements from a
plain field update (which "cancel" almost always does) — reserve plain
PATCH for genuinely simple field edits.

### 11.3 Pagination — Why Offset Degrades, Precisely, and Cursor's Full Mechanics

#### 11.3.1 The intuition: connecting back to how an index actually works

Section 3.4.2 showed a B-Tree index lets the database jump directly to a
matching row. `OFFSET 100000 LIMIT 20` cannot use that shortcut for the
"jump" part — the database must still walk through and DISCARD the first
100,000 matching rows before it can return the next 20, because "the
100,000th row in this order" isn't something a B-Tree can locate directly;
it has no choice but to count through them.

```
EXPLAIN ANALYZE SELECT * FROM posts ORDER BY created_at DESC OFFSET 100000 LIMIT 20;
--  Limit (actual time=145.223..145.240 rows=20)
--    -> Sort (actual time=140.100..144.900 rows=100020)  <- had to sort/walk
--         ALL 100,020 rows just to throw away the first 100,000 of them
```

**Cursor (keyset) pagination fixes this by turning "give me the Nth page"
into "give me everything AFTER this specific known point"** — which a
B-Tree CAN jump directly to, because it's expressed as a value comparison
(`WHERE (created_at, id) < (last_seen_created_at, last_seen_id)`), not a
row count to skip.

```sql
-- The composite comparison (created_at, id) rather than created_at alone
-- is essential: created_at values can TIE (two posts in the same
-- millisecond) — without id as a tiebreaker, a tie could cause a post to
-- be skipped entirely or returned twice across page boundaries.
SELECT * FROM posts
WHERE (created_at, id) < ($last_created_at, $last_id)
ORDER BY created_at DESC, id DESC
LIMIT 20;
-- This directly uses a (created_at, id) composite INDEX to jump straight
-- to the right starting point — no counting/discarding, regardless of
-- how deep into the result set this page is.
```

#### 11.3.2 Sequence — Why Cursor Pagination Stays Stable Under Concurrent Inserts, and Offset Doesn't

```
OFFSET-based, with a concurrent insert between page loads:
  Client loads page 1 (rows 1-20, sorted by created_at DESC)
  A NEW post is inserted (becomes the new "row 1" in DESC order)
  Client requests page 2 (OFFSET 20 LIMIT 20)
  ❌ Every row shifted down by one because of the new insert — the item
     that WAS at position 20 (last item on page 1) is now at position 21,
     and gets shown AGAIN at the top of page 2 — a visible duplicate,
     purely from OFFSET's positional (not value-based) definition of
     "page 2."

CURSOR-based, same concurrent insert:
  Client loads page 1, remembers cursor = (last_item.created_at, last_item.id)
  A NEW post is inserted
  Client requests page 2 using that SAME remembered cursor value
  ✅ The query is "everything with created_at < X" — a VALUE comparison,
     completely unaffected by what got inserted above that value. The new
     post doesn't shift anything, because nothing about the cursor's
     definition depends on ROW POSITION at all.
```

### 11.4 Idempotency by HTTP Method — Cross-Reference, Not Repetition

```
GET, PUT, DELETE — idempotent BY DEFINITION (calling twice has the same
  end-state effect as calling once): GET never mutates state at all;
  PUT REPLACES a resource with a given representation (doing that twice
  results in the identical final state); DELETE removes a resource
  (deleting an already-deleted resource is still "gone," same end state).
POST — NOT idempotent by default, because it typically means "create a
  NEW thing" — calling it twice naturally creates two things. This is
  exactly why §1.5's full Idempotency-Key component exists specifically
  for POST endpoints, not the other verbs.
PATCH — depends entirely on the semantics of what's being patched: setting
  a field to an absolute value (`{"status": "cancelled"}`) is idempotent;
  an operation expressed as a DELTA (`{"increment_quantity_by": 1}`) is
  NOT idempotent — calling it twice doubles the effect. Always check
  which shape a given PATCH endpoint actually uses before assuming safety.
```

### 11.5 HATEOAS in Practice — a Full Worked Example

#### 11.5.1 Class Diagram

```
┌─────────────────────────────────┐
│ HypermediaResource<T>               │
├─────────────────────────────────┤
│ + data: T                               │
│ + links: Map<rel_name, Link>                │
└─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────┐
│ OrderLinkBuilder                    │
├─────────────────────────────────┤
│ + build_links(order) -> Map<string, Link>│
│     links = { "self": Link(f"/orders/{order.id}") }
│     if order.status == "pending":           │
│         links["cancel"] = Link(f"/orders/{order.id}/cancel", method="POST")
│         links["pay"] = Link(f"/orders/{order.id}/pay", method="POST")
│     elif order.status == "paid":                │
│         links["ship"] = Link(f"/orders/{order.id}/ship", method="POST")
│     elif order.status == "shipped":                 │
│         links["track"] = Link(order.tracking_url, method="GET")
│     # NOTE: "cancel" is structurally ABSENT once status is "shipped" —
│     # this is HATEOAS's entire value: the state machine's rules are
│     # expressed by which links EXIST, not documented separately
│     return links                                        │
└─────────────────────────────────┘
```

#### 11.5.2 Sequence — a Client Navigating Purely Via Links

```
Client                              Server
  │  GET /orders/42                    │
  │──────────────►│                      │
  │◄──────────────│  { "id":42, "status":"pending",
  │                    "_links": {
  │                      "self": "/orders/42",
  │                      "cancel": {"href":"/orders/42/cancel","method":"POST"},
  │                      "pay": {"href":"/orders/42/pay","method":"POST"} } }
  │
  │  Client's UI renders a "Pay Now" button ONLY because the "pay" link
  │  was present — it did NOT need to separately know "orders in pending
  │  status can be paid" as a hardcoded business rule of its own.
  │
  │  POST /orders/42/pay   (URL taken directly from the previous response,
  │  never constructed/guessed by the client itself)
  │──────────────►│
  │◄──────────────│  { "id":42, "status":"paid",
  │                    "_links": {
  │                      "self": "/orders/42",
  │                      "ship": {"href":"/orders/42/ship","method":"POST"} } }
  │                      # "cancel" and "pay" are BOTH now gone — the
  │                      # client's UI updates its available actions purely
  │                      # by re-rendering from whatever links are present
  │                      # in THIS response, no separate lookup needed
```

### 11.6 Structured Error Responses — RFC 7807 Problem Details

#### 11.6.1 Building the intuition: why a plain error string breaks down

`{"error": "Order cannot be cancelled"}` is fine for a human reading logs,
but useless for a CLIENT trying to programmatically decide what to do
next — is this retryable? Is it a permissions issue? A validation issue?
A structured, machine-parseable error format lets client code branch on
the error TYPE, not on parsing a human sentence.

```json
{
  "type": "https://api.example.com/errors/invalid-state-transition",
  "title": "Order cannot be cancelled",
  "status": 409,
  "detail": "Order 42 is in 'shipped' status; only 'pending' orders can be cancelled.",
  "instance": "/orders/42/cancel",
  "current_status": "shipped",
  "allowed_transitions": ["track"]
}
```
**Why the `type` field is a URL, specifically**: it's a stable,
dereferenceable identifier a client can `switch` on programmatically
(`if error.type == ".../invalid-state-transition"`) AND a human can visit
in a browser for full documentation on that exact error class — one field
serving both a machine and a human audience is the entire design intent
behind RFC 7807.

---

## 12. GraphQL API Design

### 12.1 Building the Intuition: the Resolver Execution Model Is Why N+1 Happens

Section 10.2.2 established GraphQL's motivation (let the client specify
exact shape). To understand its most infamous problem, you need to see
HOW a GraphQL server actually executes a query — it's not magic, it's a
straightforward tree walk, and that mechanical fact is the entire, precise
reason the N+1 problem exists.

```
Query:  { users { name posts { title } } }

This is executed as a TREE, top-down, ONE RESOLVER FUNCTION PER FIELD:

  resolve_users()             → called ONCE, returns [user1, user2, ..., userN]
  resolve_posts(user1)            → called for user1 SPECIFICALLY
  resolve_posts(user2)            → called for user2 SPECIFICALLY
  ...
  resolve_posts(userN)            → called for userN SPECIFICALLY

If resolve_posts(user) is implemented as "query the posts table WHERE
author_id = user.id" — the OBVIOUS, natural way to write it — you get
exactly 1 query for users PLUS N separate queries for posts, one per
user. This isn't a bug introduced by a careless developer; it's the
DIRECT, mechanical consequence of a per-field resolver execution model —
each resolver function has no built-in awareness that N siblings are
about to ask for the same KIND of data.
```

### 12.2 LLD: DataLoader — Batching Within an Execution Tick

**The fix, precisely**: instead of each `resolve_posts(user)` call hitting
the database the INSTANT it's invoked, defer it — collect every
`resolve_posts` call that happens within the current tick of execution
(GraphQL resolves all sibling fields of the SAME level essentially
together before moving on), THEN make one single batched database call for
every collected user_id at once, and distribute each result back to the
resolver that originally asked for it.

**Class diagram:**

```
┌─────────────────────────────────┐
│ DataLoader<K, V>                     │
├─────────────────────────────────┤
│ - batch_fn: (keys: List<K>) -> List<V>  │
│ - pending_keys: List<K> = []                │  # collected DURING the
│ - cache: Map<K, Promise<V>>                     │  current tick, not yet
├─────────────────────────────────┤              │  sent to the DB
│ + load(key) -> Promise<V>                          │
│     if key in cache: return cache[key]                 │
│     promise = create_pending_promise()                     │
│     cache[key] = promise                                       │
│     pending_keys.append(key)                                       │
│     schedule_batch_dispatch_on_next_tick()   # NOT immediately —       │
│                                                 # deferred until the       │
│                                                 # current synchronous        │
│                                                 # execution block ends          │
│     return promise                                                                 │
│ + dispatch_batch()   # runs once, after collection window closes             │
│     results = batch_fn(pending_keys)                                              │
│     for key, result in zip(pending_keys, results):                                    │
│         cache[key].resolve(result)                                                        │
│     pending_keys = []                                                                         │
└─────────────────────────────────┘
```

**Sequence — N calls collapsing into exactly 1 database round trip:**

```
GraphQL Executor      DataLoader              Database
   │  resolve_posts(user1) → loader.load(1)         │
   │──────────────►│  key=1 added to pending_keys, returns    │
   │◄──────────────│  a PENDING promise (not yet resolved)       │
   │  resolve_posts(user2) → loader.load(2)                │
   │──────────────►│  key=2 added to pending_keys, returns          │
   │◄──────────────│  a PENDING promise                                │
   │  ...same for every user in this level of the query...          │
   │  resolve_posts(userN) → loader.load(N)                                │
   │──────────────►│  key=N added, returns a PENDING promise                  │
   │                                                                            │
   │  (current execution tick ends — every sibling resolver at this               │
   │   level has now been CALLED, even though none of their promises                 │
   │   have resolved yet)                                                                │
   │                │  dispatch_batch() fires                                                │
   │                │  batch_fn([1,2,...,N])                                                     │
   │                │─────────────────────────────────────────►│                                    │
   │                │◄─────────────────────────────────────────│  ONE query:                            │
   │                │                                              SELECT * FROM posts                       │
   │                │                                              WHERE author_id IN (1,2,...,N)               │
   │                │  resolves EACH pending promise with its matching slice of results │
   │◄──────────────│  (all N promises resolve, executor continues with the results)         │
```
The developer never had to manually batch anything — they wrote
`resolve_posts(user) { return loader.load(user.id) }` exactly as naturally
as the naive N+1 version, and the DataLoader's deferred-dispatch mechanism
is what silently turns N calls into 1.

### 12.3 LLD: Query Complexity & Depth Limiting

#### 12.3.1 The intuition: why this is uniquely GraphQL's problem

A REST endpoint's worst-case cost is bounded by what that ONE specific
route was built to do — `GET /orders/42` can never accidentally become
an expensive operation regardless of what a client sends, because the
client can't change its shape at all. A GraphQL query's cost is bounded
only by what the SCHEMA allows — and a schema with `user { friends {
friends { friends { friends { name } } } } }` lets a client construct an
exponentially expensive query just by nesting deeper, entirely within
what the schema technically permits.

#### 12.3.2 Class Diagram — Cost Scored Before Execution Even Begins

```
┌─────────────────────────────────┐
│ ComplexityAnalyzer                   │
├─────────────────────────────────┤
│ - max_depth: int = 10                    │
│ - max_cost: int = 1000                       │
│ - field_costs: Map<field_name, int>              │  # e.g. "friends": 10,
├─────────────────────────────────┤                  # "name": 1 — fields
│ + analyze(query_ast) -> AnalysisResult                  # that trigger a DB
│     depth = compute_max_depth(query_ast)                    # call cost more
│     if depth > max_depth: reject("too deep")                   # than scalar fields
│     cost = compute_total_cost(query_ast, field_costs)               │
│     # cost of a field with children MULTIPLIES by expected              │
│     # result count — "friends" returning up to 50 results,                  │
│     # each ALSO expanding "friends" again, compounds cost                       │
│     # multiplicatively with depth, not additively                                  │
│     if cost > max_cost: reject("too expensive")                                        │
│     return AnalysisResult(depth, cost, allowed=True)                                       │
└─────────────────────────────────┘
```

#### 12.3.3 Sequence — Rejected at Validation Time, Never Even Starts Resolving

```
Client                    GraphQL Server (Validation Phase)      Database
  │  { user(id:1) { friends { friends { friends { friends { name }}}}}}
  │──────────────►│                                                        │
  │                │  ComplexityAnalyzer.analyze(query_ast)                     │
  │                │  depth = 4 nested "friends" > max_depth (say, 3)                │
  │                │  → REJECTED                                                       │
  │◄──────────────│  400 Bad Request: "Query exceeds maximum depth of 3"                │
  │                │  (query NEVER reaches a resolver — zero database calls made,  │
  │                │   because rejection happens at the VALIDATION phase, before        │
  │                │   execution begins at all — this is the crucial detail: the           │
  │                │   defense must run BEFORE resolvers start firing, not as a               │
  │                │   timeout partway through an already-expensive execution)               │
```

### 12.4 LLD: Persisted Queries — Bandwidth AND a Security Boundary

#### 12.4.1 The intuition

A mobile app's GraphQL queries are typically fixed at build time — the
app always sends the SAME handful of query strings, never an arbitrary
new one a user typed. Sending the full query text (which can be
substantial) on every single request is wasted bandwidth for data that
never actually changes between requests. **Persisted queries** let the
client send just a short hash instead — and, as a direct side effect,
let the server be configured to execute ONLY pre-registered queries,
closing off arbitrary query injection as an attack surface entirely
(directly addressing §12.3's threat at the root, rather than just
limiting its cost).

#### 12.4.2 Schema and Sequence

```sql
CREATE TABLE persisted_queries (
    query_hash    TEXT PRIMARY KEY,     -- SHA-256 of the full query text
    query_text    TEXT NOT NULL,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

```
Client (first time)         Server                    persisted_queries table
  │  POST { "query": "{ user(id:1){name} }",     │                              │
  │          "extensions": {"persistedQuery":         │                              │
  │            {"sha256Hash": "abc123..."}}}                │                              │
  │──────────────►│                                                    │                              │
  │                │  hash not found in table → this is a REGISTRATION    │
  │                │  attempt: verify the provided hash actually matches      │
  │                │  sha256(query_text) → INSERT into persisted_queries         │
  │                │───────────────────────────────────────────────────────►│
  │◄──────────────│  execute normally, return result                                    │

Client (every subsequent call)      Server
  │  POST { "extensions": {"persistedQuery":       │
  │          {"sha256Hash": "abc123..."}} }   <-- NO query text sent at all,
  │──────────────►│                                  just the hash — massive
  │                │  hash FOUND → look up query_text from table,          bandwidth saving
  │                │  execute that stored query
  │◄──────────────│  result
```
**The security hardening this enables**: once a production deployment has
registered its full set of legitimate query hashes, the server can be
configured to REJECT any request that isn't a recognized hash — meaning
even if an attacker could somehow reach the GraphQL endpoint directly,
they cannot submit an arbitrary new query at all, sidestepping the entire
complexity-limiting problem from §12.3 for that deployment.

### 12.5 Field-Level Authorization — GraphQL's Partial-Success Response Shape

#### 12.5.1 The intuition: why REST's endpoint-level auth doesn't map directly

REST typically gates an entire ENDPOINT (`/admin/users` requires an admin
role, checked once). GraphQL has exactly ONE endpoint serving every
possible query shape — so authorization frequently needs to apply PER
FIELD within a single response: an `Employee` type's `name` and `title`
fields might be visible to anyone, while its `salary` field should only
resolve for HR roles, even within the exact same query.

#### 12.5.2 Sequence — a Partial Response, Not an All-or-Nothing Failure

```
Client (role: regular employee)         Server
  │  { employee(id:5) { name title salary } }
  │──────────────►│
  │                │  resolve_name() → OK, no restriction
  │                │  resolve_title() → OK, no restriction
  │                │  resolve_salary() → auth check: current_user.role
  │                │     does NOT include "hr" → REJECT this field only
  │◄──────────────│  {
  │                    "data": { "employee": { "name": "Alex",
  │                                             "title": "Engineer",
  │                                             "salary": null } },
  │                    "errors": [{ "message": "Not authorized to view salary",
  │                                  "path": ["employee", "salary"] }]
  │                  }
```
This is a genuinely different failure MODEL than REST's single status
code per response: `name` and `title` resolved successfully and are
present in `data`, while `salary` failed and is reported separately in
`errors` with a `path` pinpointing exactly which field — the response is
neither a full success nor a full failure, and client code must be
written to expect and handle this partial shape explicitly (a REST client
checking `if response.status == 200` has no direct analog here; a
GraphQL client must inspect `errors` even on an HTTP 200 response).

### 12.6 Federation — When One Schema Doesn't Scale Organizationally

#### 12.6.1 The intuition

The same argument that motivated splitting a monolith into microservices
(§8) applies to a single, monolithic GraphQL schema owned by one team: as
an organization grows, a Users team, an Orders team, and a Products team
each want to own and evolve their own piece of the schema independently,
without needing a single central team to merge every change. **Federation**
lets each team publish its own **subgraph**, and a **gateway** composes
them into one unified schema the client queries as if it were a single
API.

#### 12.6.2 Sequence — a Federated Query Spanning Two Subgraphs

```
Client                    Gateway              Users Subgraph      Orders Subgraph
  │ { user(id:1) { name orders { total } } }        │                     │
  │──────────►│                                                   │                     │
  │            │  Gateway's composed schema knows "user.orders"       │                     │
  │            │  is resolved by the Orders subgraph, using the          │                     │
  │            │  user's ID as a federation KEY                              │                     │
  │            │  query Users subgraph for { user(id:1){ name id } }              │                     │
  │            │──────────────►│                                                        │                     │
  │            │◄──────────────│  { name: "Alex", id: 1 }                                    │                     │
  │            │  query Orders subgraph: "given entity User{id:1}, resolve       │                     │
  │            │  its `orders` field" (the @key directive on User in the             │                     │
  │            │  Orders subgraph is what makes this entity resolution                     │                     │
  │            │  possible — Orders subgraph doesn't own User, but knows                        │                     │
  │            │  how to attach data to one given its key)                                          │                     │
  │            │───────────────────────────────────────────────────────────►│
  │            │◄───────────────────────────────────────────────────────────│ orders:[{total:100}]
  │            │  STITCHES both results into one response, matching the           │                     │
  │            │  client's originally requested shape                                    │                     │
  │◄──────────│  { "user": { "name":"Alex", "orders":[{"total":100}] } }                │                     │
```
**The trade-off, stated plainly**: teams gain full ownership of their
subgraph's schema and resolvers — but the gateway's composition step adds
a real latency cost (multiple subgraph calls per federated query,
stitched together) and requires schema governance (two teams' subgraphs
must not define conflicting types) that a single monolithic schema never
had to worry about.

---
