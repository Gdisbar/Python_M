
# Part 3: Worked Examples — Deriving Patterns End-to-End

*(Enhanced with production failure scenarios, recovery paths, concurrency, and architecture constraints)*

## Example A: Parking Lot System

**Requirements:** Multi-level parking lot, different spot sizes, different vehicle types, fee depends on vehicle type and duration, display showing free spots per level.

### Step 1 — Entities & Responsibilities
`ParkingLot`, `Level`, `Spot`, `Vehicle`, `Ticket`, `FeeCalculator`, `DisplayBoard`, `SpotAssignmentStrategy`, `VehicleFactory`.

### Step 2 — Volatility Scan
| Responsibility | Stable or varies? | Axis | Pattern |
|---|---|---|---|
| Assigning vehicle to spot | Varies | Algorithm | **Strategy** |
| Fee calculation | Varies | Algorithm | **Strategy** |
| Creating Vehicle from input | Varies | Object creation | **Factory** |
| Updating display on spot change | Multiple listeners | Fanout | **Observer** |
| Ticket construction | Fixed | — | Plain class |

### Step 3 — Patterns Chosen
- `SpotAssignmentStrategy` (nearest-first vs. size-optimal)
- `FeeStrategy` (per vehicle type)
- `VehicleFactory`
- `DisplayBoard` as `Observer` of spot-occupancy changes

### Step 4 — Production Architecture & Constraints

**Concurrency Model:** Multiple entry/exit lanes operate in parallel. Spot assignment must be **atomic** to prevent double-assignment.

```
class ParkingLot:
    field levels: List<Level>
    field assignmentStrategy: SpotAssignmentStrategy
    field spotLocks: Map<SpotId, ReentrantLock>   // or stripe locking
    
    method parkVehicle(vehicle: Vehicle) -> Ticket:
        // Atomic find-and-reserve
        candidate = assignmentStrategy.findSpot(levels, vehicle)
        if candidate == null: throw NoSpotAvailableError()
        
        lock = spotLocks.get(candidate.id)
        lock.lock()
        try:
            if candidate.isOccupied():              // double-check
                return parkVehicle(vehicle)          // retry with fresh strategy run
            candidate.occupy(vehicle)
            ticket = Ticket.create(vehicle, candidate)
            candidate.subject.notifyAll(SpotOccupiedEvent(candidate))
            return ticket
        finally:
            lock.unlock()
```

**Observability:** Tag metrics by `vehicle_type`, `spot_type`, `level`. Alert on `parkVehicle.latency` p99 and `no_spot_available` rate.

**Distributed Constraint:** If levels are in different microservices (e.g., airport parking with terminals as separate services), the `ParkingLot` becomes a **Facade** over level services, and `SpotAssignmentStrategy` might need to cache availability data with TTL.

### Step 5 — The "Stuck" Moment & Recovery

**New Requirement:** "Support EV charging spots, which have their own session tracking and a different pricing model — pay per kWh, not per hour."

**Problem:** `FeeStrategy` assumed all fees were duration-based:
```
interface FeeStrategy:
    method calculate(duration: Duration) -> Money   // too narrow!
```

**Fix:** Widen the interface to accept a `UsageContext`:
```
interface FeeStrategy:
    method calculate(context: UsageContext) -> Money

class DurationFeeStrategy implements FeeStrategy:
    method calculate(context):
        return ratePerHour * context.duration.toHours()

class EnergyFeeStrategy implements FeeStrategy:
    method calculate(context):
        return ratePerKwh * context.energyConsumedKwh
```

**Recovery Path in Production:** This is a breaking interface change. Migration strategy:
1. Deploy new interface alongside old (versioned strategies)
2. Update call sites to build `UsageContext` (duration + optional energy)
3. Gradually shift traffic to new strategies via feature flag
4. Deprecate old interface after 100% cutover

**Failure Scenario:** During migration, a bug causes `energyConsumedKwh` to be null for EV spots. `EnergyFeeStrategy` throws NPE, crashing the exit gate service.  
**Recovery:** 
1. Feature-flag off `EnergyFeeStrategy` (fallback to manual billing)
2. Fix null-handling in context builder
3. Add validation in `UsageContext.build()` that fails fast with a clear error message
4. Add integration test: "EV vehicle exit with missing kWh reading"

---

## Example B: Ride-Hailing / Cab Booking

**Requirements:** Riders request ride; system matches driver; ride lifecycle; notifications on status changes; fare depends on distance, time, demand.

### Step 1 — Entities
`Rider`, `Driver`, `Ride`, `MatchingService`, `FareCalculator`, `NotificationService`.

### Step 2 — Volatility Scan
| Responsibility | Varies? | Axis | Pattern |
|---|---|---|---|
| Driver matching | Varies | Algorithm | **Strategy** |
| Fare calculation | Varies | Algorithm | **Strategy** |
| Ride lifecycle | Varies by status | Internal state | **State** |
| Status change notifications | Multiple listeners | Fanout | **Observer** |

### Step 3 — Patterns Chosen
- `MatchingStrategy` (nearest vs. highest-rated vs. cheapest)
- `FareStrategy` (base vs. surge vs. promo)
- `RideState` (Requested/Accepted/OnTrip/Completed/Cancelled)
- `Ride` as Observer subject

### Step 4 — Production Architecture & Constraints

**Matching Constraint:** Sub-second matching requirement. A Strategy pattern alone isn't enough; you need a **geospatial index** (e.g., S2, H3, or PostGIS) as the first filter, then the Strategy ranks candidates within the radius.

```
class MatchingService:
    field geoIndex: GeoSpatialIndex<Driver>
    field strategy: MatchingStrategy
    field metrics: MetricsReporter
    
    method findDriver(rideRequest: RideRequest) -> Driver:
        // Latency budget: 50ms total
        nearby = geoIndex.query(
            center = rideRequest.pickup,
            radiusKm = 5,
            maxResults = 100
        )  // 10ms p99
        
        ranked = strategy.rank(nearby, rideRequest)  // 20ms p99
        metrics.histogram("matching.candidates", nearby.size())
        metrics.histogram("matching.latency", timer.elapsed())
        return ranked.first()
```

**State Machine Thread Safety:** Ride state is accessed by rider app, driver app, and background jobs. Use **optimistic locking** on the database row.

```
class Ride:
    field state: RideState
    field version: Long          // optimistic lock
    
    method transition(newState: RideState):
        // Database: UPDATE rides SET state=?, version=version+1 
        // WHERE id=? AND version=?
        updated = db.updateState(id, newState.getName(), version)
        if not updated:
            throw ConcurrentModificationError()
        this.state = newState
        notifyAll(new RideStateChangedEvent(id, newState.getName()))
```

**Observer at Scale:** In-process Observer doesn't survive service restarts or cross-service fanout. Production ride-hailing uses an **event bus** (Kafka/SNS). The `Ride` entity publishes events; `RiderNotificationService`, `DriverNotificationService`, and `AnalyticsService` consume from the bus.

### Step 5 — The "Stuck" Moment & Recovery

**New Requirement:** "Riders can schedule rides for later. Scheduled rides need to be queued and cancellable up until 10 minutes before pickup, with cancellation logged for support review."

**Problem:** Cancellation is no longer just a state transition; it's an action that can be **queued, delayed, and logged**. This pushes toward **Command** pattern.

```
class ScheduledRideCommand:
    field rideId: String
    field scheduledTime: Instant
    field commandType: CommandType  // CANCEL, START_MATCHING
    
    method execute():
        ride = rideRepository.find(rideId)
        if commandType == CANCEL:
            if ride.minutesUntilPickup() > 10:
                ride.transition(new CancelledState())
                auditLog.record(new CancellationEvent(rideId, "rider"))
            else:
                throw LateCancellationError()
```

**Recovery — Code Breakdown Scenario:**  
**Scenario:** A scheduled ride is queued in a job scheduler. The scheduler has a bug and executes the `CANCEL` command 3 times due to retry logic. The first cancellation succeeds; the second and third fail because the ride is already cancelled, but they still write to the audit log, creating duplicate support tickets.  
**Root cause:** Command execution was not idempotent; audit logging happened regardless of transition success.  
**Recovery:**
1. Add idempotency key to `ScheduledRideCommand` (e.g., `commandId = hash(rideId + CANCEL + scheduledTime)`)
2. Check `processedCommands` set before executing
3. Only log to audit if the state transition actually occurred (not just if the command ran)
4. Add alert on duplicate command execution rate

---

## Example C: Notification / Alerting System

**Requirements:** Send notifications across email, SMS, push; multiple subsystems trigger notifications; notification has many optional fields; retry on failure.

### Step 1 — Entities
`Notification`, `Channel` (Email/SMS/Push), `Subscriber`, `NotificationService`.

### Step 2 — Volatility Scan
| Responsibility | Varies? | Axis | Pattern |
|---|---|---|---|
| How notification is sent per channel | Varies | Algorithm | **Strategy** |
| Which Channel object to use | Varies | Object creation | **Factory** |
| Assembling Notification | Varies | Construction | **Builder** |
| Telling all subscribers about one event | Varies | Fanout | **Observer** |
| Exposing simple notify() over complexity | Fixed complexity | Subsystem count | **Facade** |

### Step 3 — Patterns Chosen
- `ChannelStrategy` per delivery mechanism
- `ChannelFactory` to pick the right one
- `NotificationBuilder` for assembly
- `Observer`-style event bus for subscriber fanout
- `NotificationFacade.notify(event)` tying it together

### Step 4 — Production Architecture & Constraints

**Retry & Decorator:** New requirement: "some notifications must be retried with backoff on failure, and failed sends after N retries logged for manual review — attachable to any channel without duplicating logic."

This is Strategy **+ Decorator**:

```
interface ChannelStrategy:
    method send(notification: Notification) -> SendResult

class RetryDecorator implements ChannelStrategy:
    field wrapped: ChannelStrategy
    field maxRetries: Int = 3
    field backoff: BackoffPolicy
    
    method send(notification):
        lastError = null
        for attempt in 1..maxRetries:
            try:
                result = wrapped.send(notification)
                if result.success:
                    metrics.increment("send.success", tag("channel", wrapped.name()))
                    return result
            except Exception as e:
                lastError = e
                metrics.increment("send.retry", tag("attempt", attempt))
                if attempt < maxRetries:
                    sleep(backoff.delay(attempt))
        
        metrics.increment("send.dead_letter")
        deadLetterQueue.enqueue(notification, lastError)
        return SendResult.permanentFailure()
```

**Thread Safety:** The `NotificationFacade` handles concurrent requests. Each channel strategy should be stateless. The retry decorator's sleep/backoff must not block the caller's thread if the facade is async.

**Observability:** Every stage emits metrics:
- `notification.received` (at facade entry)
- `notification.built` (after builder)
- `notification.channel.selected` (after factory)
- `notification.send.latency` (per channel, per attempt)
- `notification.dead_letter` (after max retries)

### Step 5 — The "Stuck" Moment & Recovery

**Problem:** Duplicating retry logic inside every strategy would violate the point of isolating the sending algorithm. The Decorator solves this.

**Recovery — Code Breakdown Scenario:**  
**Scenario:** The `RetryDecorator` uses `Thread.sleep()` between retries. Under high load, all threads in the notification service pool are blocked sleeping, and the service stops accepting new requests.  
**Root cause:** Blocking retry in an async service exhausts the thread pool.  
**Recovery:**
1. Replace `Thread.sleep()` with async scheduling (e.g., `scheduler.schedule(() -> retry, delay, TimeUnit.SECONDS)`)
2. Use a separate **retry thread pool** with bounded queue; if retry queue fills, drop and dead-letter immediately
3. Add alert on thread pool utilization > 80%
4. Document: decorators that add latency must be async-aware

---
