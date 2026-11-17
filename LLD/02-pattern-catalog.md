# Part 2: The Core Pattern Catalog — Mapped to Volatility

For each pattern below: the volatility it names, where it shows up in real LLD interviews, an industry example, language-agnostic structure, minimal pseudocode, and a misuse warning.

## Quick reference

| # | Pattern | Isolates | Trigger phrase in requirements |
|---|---|---|---|
| 1 | Strategy | Which algorithm runs | "different ways to calculate / rank / validate / match X" |
| 2 | Factory Method / Abstract Factory | Which concrete class is created | "system should support new types of X later" |
| 3 | Builder | How a complex object is assembled | "object has many optional fields / step-by-step setup" |
| 4 | Adapter | Interface mismatch | "integrate with an existing / third-party / legacy system" |
| 5 | Facade | Number of subsystems exposed | "expose one simple operation over several subsystems" |
| 6 | Decorator | Which responsibilities are combined | "combinations of optional add-ons / toppings / features" |
| 7 | Observer | Fanout of reactions to an event | "notify all interested parties when X happens" |
| 8 | State | Behavior tied to internal status | "behaves differently depending on current status, with defined transitions" |
| 9 | Command | An action as a first-class object | "undo/redo, queue, schedule, or log actions" |
| 10 | Singleton | Whether >1 instance is allowed | "exactly one shared X managing a resource" |

---

### 1. Strategy — behavior/algorithm changes

**Volatility it names:** the *algorithm* used to do one step, while the surrounding process stays the same.

**Shows up in:** pricing engines, ride-matching, sorting/ranking, discount rules, fraud-scoring, route-finding.

**Industry example:** a checkout service supporting flat pricing, surge pricing, and loyalty-tier pricing without the checkout flow itself changing.

**Structure:**
```
interface Strategy:
    method execute(input) -> Result

class ConcreteStrategyA implements Strategy: ...
class ConcreteStrategyB implements Strategy: ...

class Context:
    field strategy: Strategy
    method setStrategy(s): strategy = s
    method run(input): return strategy.execute(input)
```

**Misuse warning:** if there is — and will only ever be — one algorithm, Strategy is pure indirection. Don't introduce it until a second variant exists or is guaranteed by the spec.

---

### 2. Factory Method / Abstract Factory — object creation changes

**Volatility it names:** *which concrete class* to instantiate, decided by some input, kept out of client code.

**Shows up in:** vehicle/spot creation in parking systems, notification-channel creation, shape creation in editors, payment-method creation.

**Industry example:** a notification service that creates an `EmailNotification`, `SMSNotification`, or `PushNotification` object based on a user's channel preference, without the calling code branching on type.

**Structure:**
```
interface Product:
    method action()

class ConcreteProductA implements Product: ...
class ConcreteProductB implements Product: ...

class Creator:
    method create(type) -> Product:
        switch type:
            case A: return new ConcreteProductA()
            case B: return new ConcreteProductB()
```
*Abstract Factory* is the same idea one level up: a factory that creates a *family* of related objects — e.g. a `UIFactory` that produces a matching Button + Checkbox + Scrollbar for one theme.

**Misuse warning:** if there's only ever one concrete type, a plain constructor is fine. Factories earn their keep once "new types will be added later" is a real requirement, or the object graph being built is genuinely complex.

---

### 3. Builder — construction process changes

**Volatility it names:** the *steps or optional parts* used to assemble one complex object, especially when most fields are optional or order matters.

**Shows up in:** constructing notification objects (title, body, deep-link, priority, attachments — mostly optional), building configuration/request objects, assembling a `Pizza` or `Meal` from many optional components.

**Industry example:** an HTTP-request builder or notification builder where you chain `.withTitle().withBody().withPriority().build()` instead of a constructor with twelve optional parameters.

**Structure:**
```
class Product:
    fields: partA, partB, partC, ...

class Builder:
    field product: Product
    method setPartA(x): product.partA = x; return self
    method setPartB(x): product.partB = x; return self
    method build() -> Product: return product
```

**Misuse warning:** if the object has 2–3 required fields and no optional ones, a constructor is simpler and clearer. Builder pays off once you'd otherwise need multiple overloaded constructors or a long parameter list with several optional values.

---

### 4. Adapter — interface/boundary changes

**Volatility it names:** the *shape of an interface* you don't control (a legacy system, a third-party API, a different vendor) that must be made to look like the interface your system expects.

**Shows up in:** integrating a legacy payment gateway with a different method signature, wrapping a third-party maps SDK behind your own `RouteProvider` interface, plugging in a new external service without touching callers.

**Industry example:** your system expects a `PaymentProcessor.charge(amount)` interface; a newly-integrated vendor's SDK exposes `LegacyGateway.doTransaction(cents, currencyCode)`. An adapter wraps the vendor call to match your interface.

**Structure:**
```
interface Target:
    method request()

class Adaptee:
    method specificRequest()

class Adapter implements Target:
    field adaptee: Adaptee
    method request():
        adaptee.specificRequest()   // translate call/shape here
```

**Misuse warning:** don't add an adapter "just in case" a second vendor shows up — add it when you're actually bridging two interfaces that already disagree.

---

### 5. Facade — subsystem complexity changes

**Volatility it names:** the *number of subsystems and their internal call order* that a caller would otherwise need to know about directly.

**Shows up in:** an `OrderService.placeOrder()` that internally coordinates inventory check, payment, notification, and shipping subsystems behind one call.

**Industry example:** placing an order in an e-commerce system touches inventory, pricing, payment, and notifications — the client just calls `orderFacade.placeOrder(cart)`.

**Structure:**
```
class SubsystemA: method opA()
class SubsystemB: method opB()
class SubsystemC: method opC()

class Facade:
    method simpleOperation():
        subsystemA.opA()
        subsystemB.opB()
        subsystemC.opC()
```

**Misuse warning:** a facade over one subsystem is just an extra layer. It earns its place once a client would otherwise need to coordinate 3+ subsystems correctly, in order, every time.

---

### 6. Decorator — combined-responsibility changes

**Volatility it names:** *which optional responsibilities* an object has, especially when they can combine in any number/order.

**Shows up in:** coffee/pizza customization (toppings), stacking discounts (seasonal + loyalty + coupon), wrapping a data stream with compression + encryption in any combination.

**Industry example:** a `Coffee` object wrapped with `MilkDecorator`, then `SugarDecorator`, each adding cost/description without a combinatorial explosion of subclasses (`CoffeeWithMilkAndSugar`, etc.).

**Structure:**
```
interface Component:
    method cost() -> number
    method description() -> string

class ConcreteComponent implements Component: ...

class Decorator implements Component:
    field wrapped: Component
    method cost(): return wrapped.cost() + extraCost
    method description(): return wrapped.description() + ", extra"
```

**Misuse warning:** if there are only 2–3 fixed combinations total, a handful of subclasses is simpler than a decorator chain. Decorator earns its keep once combinations would otherwise multiply subclasses.

---

### 7. Observer — fanout changes

**Volatility it names:** *how many* (and which) other parts of the system need to react when one thing happens, without the subject knowing who they are in advance.

**Shows up in:** notification systems (order status change → notify rider app, driver app, analytics), stock-price tickers, event-driven pub/sub inside a single service.

**Industry example:** when a ride's status changes to "driver arrived," the rider's app, the driver's app, and an analytics logger all need to be told — the ride object shouldn't need a hardcoded list of exactly those three.

**Structure:**
```
interface Observer:
    method update(event)

class Subject:
    field observers: list<Observer>
    method subscribe(o): observers.add(o)
    method notifyAll(event):
        for o in observers: o.update(event)
```

**Misuse warning:** if there is exactly one fixed listener that will never change, a direct method call is simpler than an observer list.

---

### 8. State — internal-state-driven behavior changes

**Volatility it names:** *which behavior applies*, driven by the object's own current status, with well-defined transitions between statuses.

**Shows up in:** an order or ride's lifecycle (`Requested → Accepted → OnTrip → Completed`/`Cancelled`), a document's state (`Draft → InReview → Published`), a traffic-light or elevator's mode.

**Industry example:** a ride object behaves differently when `cancel()` is called depending on whether it's `Requested` (free), `Accepted` (small fee), or `OnTrip` (not allowed) — each state encapsulates its own legal transitions instead of one giant if/else on a status field.

**Structure:**
```
interface RideState:
    method cancel(context)
    method complete(context)

class RequestedState implements RideState: ...
class OnTripState implements RideState: ...

class Ride:
    field state: RideState
    method cancel(): state.cancel(self)
    method setState(s): state = s
```

**Misuse warning:** if there are only 2 states and one trivial transition, a boolean flag is fine. State earns its place once you have 3+ statuses each with different legal actions/transitions.

---

### 9. Command — action-as-object changes

**Volatility it names:** *what action runs, and when* — decoupling the thing that triggers an action from the thing that executes it, enabling queuing, logging, undo/redo, or scheduling.

**Shows up in:** undo/redo in a text editor, task queues/schedulers, remote-control-style APIs, transaction logs.

**Industry example:** a smart-home system where a `PressButtonCommand` object can be queued, logged, executed later, or reversed, instead of the button directly calling a device method.

**Structure:**
```
interface Command:
    method execute()
    method undo()

class ConcreteCommand implements Command:
    field receiver
    method execute(): receiver.action()
    method undo(): receiver.reverseAction()

class Invoker:
    field history: list<Command>
    method run(cmd): cmd.execute(); history.push(cmd)
    method undoLast(): history.pop().undo()
```

**Misuse warning:** if you never need to queue, log, delay, or undo the action, a direct method call is simpler.

---

### 10. Singleton — shared-instance constraint

**Volatility it names, inverted:** this is the one pattern about *constraining* rather than isolating variation — it guarantees exactly one instance manages access to something (a config store, a connection pool, a logger).

**Shows up in:** configuration managers, logging, connection pools, caches — anywhere uncoordinated multiple instances would cause bugs (double-counting, conflicting writes).

**Industry example:** a single `ConnectionPoolManager` instance shared across a service so connections are actually pooled rather than duplicated.

**Structure:**
```
class Singleton:
    static field instance: Singleton = null
    private constructor()
    static method getInstance():
        if instance == null: instance = new Singleton()
        return instance
```

**Misuse warning:** this is the most over-applied pattern in interviews. It introduces global state, hurts testability, and is often reached for out of habit rather than necessity. Use it only when the requirement is genuinely "exactly one, system-wide" — not just "a class I only happen to instantiate once."

---
**Next:** Part 3 — `03-worked-examples.md`, applying this catalog to full problems end-to-end.
