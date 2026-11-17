# Part 3: Worked Examples — Deriving Patterns End-to-End

Each example follows the same process from Part 1: model responsibilities → scan for volatility → pick patterns → hit a "stuck" moment as requirements grow → refactor.

## Example A: Parking Lot System

**Requirements (typical interview phrasing):** A multi-level parking lot with different spot sizes (compact, large, handicapped), different vehicle types (car, bike, truck), a fee that depends on vehicle type and duration, and a display showing free spots per level.

**Step 1 — Entities & responsibilities:** `ParkingLot`, `Level`, `Spot`, `Vehicle`, `Ticket`, `FeeCalculator`, `DisplayBoard`.

**Step 2 — Volatility scan:**

| Responsibility | Stable or varies? | Axis |
|---|---|---|
| Assigning a vehicle to a spot | Varies (nearest-first vs. size-optimal) | Algorithm → **Strategy** |
| Fee calculation | Varies by vehicle type/duration | Algorithm → **Strategy** |
| Creating a `Vehicle` object from an input type string | Varies as new vehicle types are added | Object creation → **Factory** |
| Updating the display when a spot frees up | Multiple boards/levels may need to know | Fanout → **Observer** |
| Ticket construction (entry time, spot, vehicle, rate) | Fixed set of fields, no optional complexity | No pattern needed — plain class |

**Step 3 — Patterns chosen:** `SpotAssignmentStrategy` (nearest vs. size-optimal), `FeeStrategy` (per vehicle type), `VehicleFactory`, `DisplayBoard` as an `Observer` of spot-occupancy changes.

**Step 4 — The "stuck" moment:** The interviewer adds: "now support EV charging spots, which have their own session tracking and a different pricing model entirely — pay per kWh, not per hour." Your existing `FeeStrategy` interface assumed all fees were duration-based; kWh-based billing doesn't fit that method signature cleanly. This is the sign that `FeeStrategy` was scoped one level too narrow. The fix: widen the strategy interface to accept a `UsageContext` (which can carry either duration or energy-consumed) rather than special-casing EV inside a duration-shaped interface. This is the "move to a better one" moment — not a sign the first version was wrong, just incomplete against a requirement you didn't have yet.

**Step 5 — Final shape:** `VehicleFactory` creates typed vehicles → `ParkingLot.parkVehicle()` uses `SpotAssignmentStrategy` to pick a spot → on park/unpark, spot changes are pushed to `DisplayBoard` observers → on exit, `Ticket` is closed using the vehicle-type-appropriate `FeeStrategy`.

---

## Example B: Ride-Hailing / Cab Booking

**Requirements:** Riders request a ride; the system matches a driver; the ride goes through a lifecycle; riders and drivers get notified of status changes; fare depends on distance, time, and demand.

**Step 1 — Entities:** `Rider`, `Driver`, `Ride`, `MatchingService`, `FareCalculator`, `NotificationService`.

**Step 2 — Volatility scan:**

| Responsibility | Varies? | Axis |
|---|---|---|
| Choosing which driver to match | Nearest vs. highest-rated vs. cheapest | Algorithm → **Strategy** |
| Fare calculation | Base vs. surge vs. promo | Algorithm → **Strategy** |
| Ride lifecycle behavior (what `cancel()`/`complete()` legally do) | Depends heavily on current status | Internal state → **State** |
| Telling rider app, driver app, and analytics about status changes | Multiple independent listeners | Fanout → **Observer** |

**Step 3 — Patterns chosen:** `MatchingStrategy`, `FareStrategy`, `RideState` (Requested/Accepted/OnTrip/Completed/Cancelled, each implementing its own legal transitions), `Ride` as an `Observer` subject notifying rider/driver/analytics listeners.

**Step 4 — The "stuck" moment:** Requirement grows: "riders can now schedule a ride for later, and scheduled rides need to be queued and be cancellable up until 10 minutes before pickup, with the cancellation itself logged for support review." Cancelling isn't just a state transition anymore — it needs to be represented as an action that can be queued, delayed, and logged. This pushes you from "state transition method" toward wrapping the cancel action itself as a **Command** object (`CancelRideCommand`) that can be scheduled and whose execution is logged, while `RideState` still governs *whether* cancellation is currently legal.

**Step 5 — Final shape:** `MatchingStrategy` picks a driver → `Ride` transitions through `RideState` implementations → status changes fan out via `Observer` to rider/driver/analytics → cancellation (especially for scheduled rides) is represented as a `Command` for queuing/logging, gated by the current `RideState`.

---

## Example C: Notification / Alerting System

**Requirements:** Send notifications across email, SMS, and push; multiple subsystems (billing, security, marketing) can trigger notifications; a notification has many optional fields (title, body, deep-link, priority, attachment, expiry).

**Step 1 — Entities:** `Notification`, `Channel` (Email/SMS/Push), `Subscriber`, `NotificationService`.

**Step 2 — Volatility scan:**

| Responsibility | Varies? | Axis |
|---|---|---|
| How a notification is actually sent per channel | Email vs. SMS vs. Push | Algorithm → **Strategy** |
| Which `Channel` object to use based on user preference | New channels added over time | Object creation → **Factory** |
| Assembling a `Notification` with many optional fields | Mostly-optional fields, varies per event type | Construction → **Builder** |
| Telling all interested subscribers about one event | One event, many listeners | Fanout → **Observer** |
| Exposing one `notify(event)` call over channel selection + sending + logging | Caller shouldn't coordinate all of that | Complexity → **Facade** |

**Step 3 — Patterns chosen:** `ChannelStrategy` per delivery mechanism, `ChannelFactory` to pick the right one, `NotificationBuilder` for assembly, an `Observer`-style event bus for subscriber fanout, and a `NotificationFacade.notify(event)` tying it all together for callers.

**Step 4 — The "stuck" moment:** New requirement: "some notifications must be retried with backoff on failure, and failed sends after N retries should be logged for manual review — and this retry/logging behavior should be attachable to any channel without duplicating it in every `ChannelStrategy` implementation." Duplicating retry logic inside every strategy would violate the whole point of isolating the sending algorithm. The fix: wrap a `ChannelStrategy` with a `RetryDecorator` that adds retry/backoff/logging around any underlying channel implementation — a shift from Strategy alone toward Strategy **+ Decorator** stacked together.

**Step 5 — Final shape:** `NotificationFacade.notify(event)` → builds the notification via `NotificationBuilder` → picks a channel via `ChannelFactory` → wraps it in a `RetryDecorator` → sends → publishes to `Observer` subscribers for cross-cutting concerns like analytics.

---

Notice the repeated shape across all three examples: you never start with "I'll use Observer here." You start with "multiple things need to know when X happens," and Observer is just the name for the structure that was already necessary.

---
**Next:** Part 4 — `04-pitfalls-and-interview-playbook.md`
