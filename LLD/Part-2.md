
# Part 2: The Core Pattern Catalog — Mapped to Volatility

*(Enhanced: Strategy, Factory, Observer, State get full production treatment. Others get operational awareness.)*

## Quick reference

| # | Pattern | Isolates | Trigger phrase | Production watch-out |
|---|---|---|---|---|
| 1 | Strategy | Which algorithm runs | "different ways to calculate / rank / validate" | Selection logic itself becomes a bottleneck; ensure strategies are stateless or thread-safe |
| 2 | Factory Method / Abstract Factory | Which concrete class is created | "support new types of X later" | Thread-safe registration; avoid reflection in hot paths |
| 3 | Builder | How a complex object is assembled | "many optional fields / step-by-step setup" | Invalid intermediate states must fail fast with clear errors |
| 4 | Adapter | Interface mismatch | "integrate with existing / third-party / legacy" | Wrap with circuit breaker; log translation failures |
| 5 | Facade | Number of subsystems exposed | "one simple operation over several subsystems" | p99 latency = sum of p99s; add timeout and partial-failure handling |
| 6 | Decorator | Which responsibilities are combined | "combinations of optional add-ons" | Stack depth and order matter; avoid infinite recursion |
| 7 | Observer | Fanout of reactions to an event | "notify all interested parties when X" | Backpressure, dead observers, async vs sync semantics |
| 8 | State | Behavior tied to internal status | "behaves differently depending on current status" | Distributed state needs persistence; invalid transitions need guardrails |
| 9 | Command | An action as a first-class object | "undo/redo, queue, schedule, log" | Idempotency, exactly-once, command serialization |
| 10 | Singleton | Whether >1 instance is allowed | "exactly one shared X managing a resource" | Distributed singletons need consensus; testability suffers |

---

### 1. Strategy — behavior/algorithm changes *(Production Deep-Dive)*

**Volatility it names:** the *algorithm* used to do one step, while the surrounding process stays the same.

**Shows up in:** pricing engines, ride-matching, sorting/ranking, discount rules, fraud-scoring, route-finding, feature-flag-driven behavior.

**Industry example:** Checkout service supporting flat pricing, surge pricing, and loyalty-tier pricing without the checkout flow changing.

**Structure:**
```
interface PricingStrategy:
    method calculatePrice(context: PricingContext) -> Money

class FlatPricingStrategy implements PricingStrategy: ...
class SurgePricingStrategy implements PricingStrategy: ...
class LoyaltyPricingStrategy implements PricingStrategy: ...

class CheckoutService:
    field strategyRegistry: Map<String, PricingStrategy>  // thread-safe
    field metrics: MetricsReporter
    
    method setStrategy(name: String):
        if not strategyRegistry.contains(name):
            throw StrategyNotFoundError
        this.activeStrategy = strategyRegistry.get(name)
    
    method checkout(cart: Cart):
        startTimer()
        price = activeStrategy.calculatePrice(cart)
        recordLatency("pricing.strategy." + activeStrategy.name, timer)
        return price
```

**Production Concerns:**

*Thread Safety:* Strategies should be **stateless** or **immutable**. If a strategy needs configuration, inject it at construction time, not during `calculatePrice()`. The registry lookup must be thread-safe (concurrent hash map, copy-on-write, or read-only after startup).

*Observability:* Tag metrics by strategy name. Log strategy selection decisions with context. If a strategy starts returning unexpected values, you need to know *which* strategy was active for that request.

*Recovery — Code Breakdown Scenario:*  
**Scenario:** A new `SurgePricingStrategy` is deployed. It caches surge multipliers in an unbounded `HashMap` keyed by city ID. Over a week, memory usage grows until the service OOMs.  
**Root cause:** Strategy carried hidden state (cache) that wasn't bounded or instrumented.  
**Recovery:** 
1. Roll back to previous version (feature flag off)
2. Fix: replace with bounded `Cache<String, Float>` (LRU, max 10K entries) with hit-rate metrics
3. Add alert on heap usage per strategy instance
4. Document: strategies must not hold unbounded caches unless explicitly designed as stateful services

*Architecture Constraints:*
| Constraint | Choice |
|---|---|
| Latency < 5ms | Pre-register all strategies in a `Map<String, Strategy>`; no reflection or classpath scanning in hot path |
| Hot-reload required | Use copy-on-write registry; new strategy instances replace old atomically |
| Memory-constrained (edge device) | Strategy selection via enum + switch, not polymorphism; avoids vtable and object overhead |

**Misuse warning:** If there is — and will only ever be — one algorithm, Strategy is pure indirection. Don't introduce it until a second variant exists or is guaranteed.

---

### 2. Factory Method / Abstract Factory — object creation changes *(Production Deep-Dive)*

**Volatility it names:** *which concrete class* to instantiate, decided by some input, kept out of client code.

**Shows up in:** vehicle/spot creation in parking systems, notification-channel creation, payment-method creation, database driver selection.

**Industry example:** Notification service creating `EmailNotification`, `SMSNotification`, or `PushNotification` based on user preference, without the calling code branching on type.

**Structure:**
```
interface NotificationChannel:
    method send(notification: Notification)

class EmailChannel implements NotificationChannel: ...
class SMSChannel implements NotificationChannel: ...
class PushChannel implements NotificationChannel: ...

class ChannelFactory:
    field registry: Map<String, NotificationChannel>  // immutable after init
    field metrics: MetricsReporter
    
    method create(channelType: String) -> NotificationChannel:
        channel = registry.get(channelType)
        if channel == null:
            metrics.increment("factory.unknown_type", tag("type", channelType))
            throw UnsupportedChannelError(channelType)
        metrics.increment("factory.create", tag("type", channelType))
        return channel
    
    // Alternative: if channels need per-request state
    method createStateful(channelType: String) -> NotificationChannel:
        // Thread-safe object pool or prototype clone
        ...
```

**Production Concerns:**

*Thread Safety:* If the factory creates new instances per request, ensure the constructor chain is lightweight. Heavy initialization (DB connections, thread pools) should happen at factory-registration time, not per `create()` call. Use object pools for expensive-to-create objects.

*Distributed Context:* In microservices, the Factory often becomes a **service registry** or **sidecar proxy**. The "creation" might be resolving a service endpoint, not a local object.

*Recovery — Code Breakdown Scenario:*  
**Scenario:** A `PaymentFactory` creates `StripePaymentProcessor` instances. A deployment misconfiguration causes the Stripe API key to be missing. The factory still creates instances, but every `charge()` call fails with authentication errors. The checkout service retries aggressively, hitting Stripe's rate limit and affecting all payment methods.  
**Root cause:** Factory created invalid objects; validation happened too late (at use time, not creation time).  
**Recovery:**
1. Add **fail-fast validation** in factory: `create()` verifies API key presence and throws `InvalidConfigurationError` at startup
2. Add **health check** that attempts a test transaction on factory initialization
3. Wrap processor in Adapter with circuit breaker; factory returns the wrapped instance
4. Separate factory per payment provider so one misconfiguration doesn't affect others

*Architecture Constraints:*
| Constraint | Choice |
|---|---|
| Startup time critical | Eager initialization + background warming; factory returns pre-built instances |
| Thousands of types | Registry as concurrent hash map; avoid O(n) scanning |
| Object creation is expensive | Object pool (e.g., Apache Commons Pool); factory borrows/returns instead of new/delete |

**Misuse warning:** If there's only ever one concrete type, a plain constructor is fine.

---

### 3. Builder — construction process changes *(Enhanced)*

**Volatility it names:** the *steps or optional parts* used to assemble one complex object.

**Production additions:**
- **Validation layer:** The `build()` method should run invariant checks and throw a clear `ValidationException` listing *all* missing/invalid fields, not just the first one.
- **Immutability:** The returned object should be immutable. No setters after `build()`.
- **Observability:** Log `build()` failures with the fields that were attempted; this catches integration bugs early.

```
class NotificationBuilder:
    field title: String?
    field body: String?
    field priority: Priority = Priority.NORMAL
    
    method withTitle(t: String): self.title = t; return self
    method withBody(b: String): self.body = b; return self
    method withPriority(p: Priority): self.priority = p; return self
    
    method build() -> Notification:
        errors = []
        if title == null: errors.add("title required")
        if body == null: errors.add("body required")
        if not errors.isEmpty(): throw ValidationException(errors)
        return Notification(title, body, priority)  // immutable
```

**Misuse warning:** If the object has 2–3 required fields and no optional ones, a constructor is simpler.

---

### 4. Adapter — interface/boundary changes *(Enhanced)*

**Volatility it names:** the *shape of an interface* you don't control.

**Production additions:**
- **Circuit breaker integration:** The adapter is the perfect place to wrap external calls with timeouts, retries, and circuit breakers.
- **Metrics:** Track adapter latency, error rate, and translation failures separately from core business logic.
- **Idempotency:** If adapting a payment gateway, the adapter should generate and attach idempotency keys.

```
interface PaymentProcessor:
    method charge(amount: Money, idempotencyKey: String) -> Receipt

class StripeAdapter implements PaymentProcessor:
    field stripeClient: StripeClient
    field circuitBreaker: CircuitBreaker
    field metrics: MetricsReporter
    
    method charge(amount, idempotencyKey):
        if not circuitBreaker.allowRequest():
            throw ServiceUnavailableError()
        
        try:
            result = stripeClient.charges.create(
                amount = amount.cents,
                currency = amount.currency,
                idempotency_key = idempotencyKey
            )
            circuitBreaker.recordSuccess()
            metrics.increment("adapter.stripe.success")
            return Receipt(result.id, result.status)
        except Exception as e:
            circuitBreaker.recordFailure()
            metrics.increment("adapter.stripe.failure", tag("error", e.type))
            throw PaymentGatewayError(e)
```

**Misuse warning:** Don't add an adapter "just in case."

---

### 5. Facade — subsystem complexity changes *(Enhanced)*

**Volatility it names:** the *number of subsystems and their internal call order*.

**Production additions:**
- **Latency budget:** A facade over 3 subsystems has a p99 latency roughly equal to the sum of p99s (if sync) or the max p99 (if async). Document and enforce the budget.
- **Partial failure:** If one subsystem fails, should the facade fail entirely? Or return degraded results? Define the strategy explicitly.
- **Tracing:** Inject a trace ID at the facade boundary so you can follow the request through all subsystems.

```
class OrderFacade:
    field inventory: InventoryService
    field payment: PaymentService
    field notification: NotificationService
    field tracer: Tracer
    
    method placeOrder(order: Order):
        span = tracer.startSpan("placeOrder")
        try:
            inventory.reserve(order.items)        // may throw
            payment.charge(order.total)           // may throw
            notification.sendConfirmation(order)  // best-effort
            span.setStatus(OK)
            return OrderResult.success()
        except InventoryException as e:
            span.setStatus(ERROR, "inventory")
            return OrderResult.failed(e)
        except PaymentException as e:
            inventory.release(order.items)        // compensating action
            span.setStatus(ERROR, "payment")
            return OrderResult.failed(e)
        finally:
            span.end()
```

**Misuse warning:** A facade over one subsystem is just an extra layer.

---

### 6. Decorator — combined-responsibility changes *(Enhanced)*

**Volatility it names:** *which optional responsibilities* an object has, in combination.

**Production additions:**
- **Stack depth limits:** Deep decorator chains can cause stack overflow or obscure latency. Instrument depth.
- **Order sensitivity:** `CompressionDecorator(EncryptionDecorator(stream))` is not the same as `EncryptionDecorator(CompressionDecorator(stream))`. Document required ordering.
- **Resource leaks:** Each decorator may hold resources (buffers, connections). Ensure `close()` propagates through the entire stack.

```
interface DataStream:
    method read() -> ByteArray
    method close()

class CompressionDecorator implements DataStream:
    field wrapped: DataStream
    method read():
        data = wrapped.read()
        return decompress(data)
    method close():
        wrapped.close()  // propagate cleanup
```

**Misuse warning:** If only 2–3 fixed combinations exist, subclasses are simpler.

---

### 7. Observer — fanout changes *(Production Deep-Dive)*

**Volatility it names:** *how many* (and which) other parts need to react when one thing happens, without the subject knowing who they are.

**Shows up in:** notification systems, stock-price tickers, event-driven pub/sub, audit logging, cache invalidation.

**Industry example:** When a ride's status changes to "driver arrived," the rider app, driver app, and analytics logger all need to be told.

**Structure:**
```
interface RideEventObserver:
    method onRideEvent(event: RideEvent)

class RideSubject:
    field observers: List<RideEventObserver>           // thread-safe
    field eventQueue: BlockingQueue<RideEvent>         // for async dispatch
    field executor: ExecutorService                    // bounded thread pool
    
    method subscribe(o: RideEventObserver):
        // Copy-on-write or synchronized list
        observers.add(o)
    
    method notifyAll(event: RideEvent):
        // Synchronous path: immediate but blocks subject
        for o in observers:
            try:
                o.onRideEvent(event)
            except Exception as e:
                log.error("Observer failed", e)        // don't let one observer break others
    
    method notifyAllAsync(event: RideEvent):
        // Asynchronous path: subject returns immediately
        eventQueue.offer(event)
    
    // Background dispatcher thread
    method dispatchLoop():
        while running:
            event = eventQueue.take()
            for o in observers:
                executor.submit(() -> {
                    try:
                        o.onRideEvent(event)
                    except Exception as e:
                        log.error("Async observer failed", e)
                })
```

**Production Concerns:**

*Thread Safety:* The observer list must be thread-safe. **CopyOnWriteArrayList** is excellent for read-heavy, write-rare scenarios (typical in production). If subscriptions happen frequently, use a `ReadWriteLock`.

*Backpressure:* If observers are slower than events, an unbounded queue will OOM. Use a **bounded queue** with `offer()` and a **rejection strategy** (drop, sample, or block).

*Dead Observers (Memory Leaks):* The #1 production bug with Observer. If an observer is a UI component or a short-lived request handler that doesn't unsubscribe, the subject holds a reference forever.  
**Fix:** Use **weak references** for observer storage, or require explicit unsubscribe in `finally` blocks, or use a time-to-live subscription model.

*Recovery — Code Breakdown Scenario:*  
**Scenario:** A new `AnalyticsObserver` is added to the `OrderSubject`. It synchronously POSTs to an analytics service. The analytics service has a 2-second latency spike. Because the observer is sync, the entire order placement API slows down to 2+ seconds, causing cascading timeouts.  
**Root cause:** Observer doing blocking I/O on the publisher's thread.  
**Recovery:**
1. Immediately switch to async dispatch (separate thread pool)
2. Add timeout (max 100ms) to analytics call; if it fails, drop the event (analytics is best-effort)
3. Add metrics: `observer.latency`, `observer.dropped_events`
4. Document rule: observers must not block the publisher; if they need to block, they must implement their own queue and ack mechanism

*Architecture Constraints:*
| Constraint | Choice |
|---|---|
| Strong ordering required | Single dispatcher thread; async but serialized |
| High throughput, ordering relaxed | Parallel executor per observer; risk of out-of-order delivery to one observer |
| At-least-once delivery | Persist events to log/queue before dispatch; observer acks receipt |
| Cross-service fanout | Replace in-process Observer with message bus (Kafka, SNS, RabbitMQ) |

**Misuse warning:** If there is exactly one fixed listener, a direct method call is simpler.

---

### 8. State — internal-state-driven behavior changes *(Production Deep-Dive)*

**Volatility it names:** *which behavior applies*, driven by the object's own current status, with well-defined transitions.

**Shows up in:** order/ride lifecycle, document workflow, approval processes, payment state machines, infrastructure provisioning.

**Industry example:** A ride object behaves differently when `cancel()` is called depending on whether it's `Requested`, `Accepted`, or `OnTrip`.

**Structure:**
```
interface RideState:
    method cancel(context: Ride) -> TransitionResult
    method complete(context: Ride) -> TransitionResult
    method getName() -> String

class RequestedState implements RideState:
    method cancel(context):
        context.setState(new CancelledState())
        context.recordTransition("REQUESTED", "CANCELLED")
        return TransitionResult.success()
    method complete(context):
        return TransitionResult.invalid("Cannot complete from REQUESTED")

class OnTripState implements RideState:
    method cancel(context):
        return TransitionResult.invalid("Cannot cancel while ON_TRIP")
    method complete(context):
        context.setState(new CompletedState())
        context.recordTransition("ON_TRIP", "COMPLETED")
        return TransitionResult.success()

class Ride:
    field state: RideState
    field transitionLog: List<StateTransition>   // append-only audit log
    field lock: ReentrantLock                    // for thread safety
    
    method cancel():
        lock.lock()
        try:
            result = state.cancel(this)
            if result.success:
                publishEvent(new RideCancelledEvent(this.id, state.getName()))
            return result
        finally:
            lock.unlock()
    
    method setState(newState: RideState):
        this.state = newState
```

**Production Concerns:**

*Thread Safety:* State transitions must be **atomic**. Use a lock or compare-and-swap. The transition check (`can I move from A to B?`) and the state update must happen atomically.

*Persistence:* In production, the state machine often spans requests or even restarts. The state must be **persisted** (database row, event log) before the method returns, or you risk inconsistency on crash.

*Distributed State:* If the ride entity is loaded by multiple services, they might each have a stale copy of the state. Use **optimistic locking** (version number on the row) or **event sourcing** (rebuild state from event log).

*Recovery — Code Breakdown Scenario:*  
**Scenario:** A payment goes through `INITIATED → PROCESSING → COMPLETED`. Between `PROCESSING` and `COMPLETED`, the service crashes. On restart, the payment is stuck in `PROCESSING`. A reconciliation job sees it and tries to retry, but the external gateway already processed it. The system double-charges the customer.  
**Root cause:** State transition was not idempotent; no record of the external call's idempotency key was tied to the state.  
**Recovery:**
1. Before calling the gateway, persist `PROCESSING` state + idempotency key + timestamp
2. On recovery, query the gateway with the idempotency key to determine if it succeeded
3. Only then transition to `COMPLETED` or `FAILED`
4. Add reconciliation job that handles `PROCESSING` older than N minutes as a special case
5. State machine becomes: `INITIATED → PROCESSING(persist key) → [query gateway] → COMPLETED/FAILED`

*Architecture Constraints:*
| Constraint | Choice |
|---|---|
| Strict consistency | Database row with optimistic locking; state transitions in transaction |
| High availability | Event sourcing: state is a projection of an append-only log; multiple replicas can rebuild |
| Audit required | Every transition persisted to immutable log; state object only appends |
| Cross-service workflow | Saga pattern: each state handler emits a command to the next service; compensating transactions for rollback |

**Misuse warning:** If only 2 states and one trivial transition, a boolean flag is fine.

---

### 9. Command — action-as-object changes *(Enhanced)*

**Volatility it names:** *what action runs, and when* — enabling queuing, logging, undo/redo, scheduling.

**Production additions:**
- **Idempotency:** Commands must carry an idempotency key. Executing the same command twice must be safe.
- **Serialization:** Commands often cross network boundaries. Design them as serializable DTOs from the start.
- **Exactly-once semantics:** At-least-once delivery + idempotent handlers, or distributed transactions.

```
interface Command:
    method execute()
    method getIdempotencyKey() -> String

class ProcessPaymentCommand implements Command:
    field orderId: String
    field idempotencyKey: String
    field timestamp: Instant
    
    method execute():
        if idempotencyStore.contains(idempotencyKey):
            return  // already processed
        paymentService.charge(orderId)
        idempotencyStore.put(idempotencyKey, timestamp)
```

**Misuse warning:** If you never need to queue, log, delay, or undo, a direct method call is simpler.

---

### 10. Singleton — shared-instance constraint *(Enhanced)*

**Volatility it names, inverted:** guarantees exactly one instance manages access to something.

**Production additions:**
- **Distributed singletons:** In a multi-node deployment, a process-level singleton is insufficient. You need a distributed lock (Redis Redlock, Zookeeper, database advisory lock) or a consensus protocol.
- **Testability:** Singletons make unit testing hard. Prefer **dependency injection** with a single instance scoped to the application context.
- **Lifecycle management:** Singletons often hold resources (threads, connections). They need explicit `shutdown()` hooks.

```
// Prefer this in production:
class ConnectionPoolManager:
    // No static getInstance()
    // Created once by DI framework, injected where needed
    
    field pool: ConnectionPool
    field metrics: MetricsReporter
    
    method getConnection():
        conn = pool.borrow()
        metrics.increment("pool.active")
        return conn
    
    method shutdown():
        pool.close()
```

**Misuse warning:** The most over-applied pattern. Use only when "exactly one, system-wide" is a genuine requirement. In distributed systems, prefer per-region scoped instances.

---
