
# Part 1: The Mental Model — Deriving Patterns Instead of Recalling Them

*(Enhanced for production system design reference)*

## 1. The problem with "scenario → pattern" learning

Most tutorials teach patterns as answers to fixed scenarios. That works only if the problem happens to match the memorized scenario word-for-word. In production — and in well-run interviews — you:

1. Get a problem statement
2. Model the entities and responsibilities
3. Notice a specific part of the design is likely to change, or already has multiple variants
4. **Check architecture constraints** (latency budget, consistency model, throughput target, fault-domain isolation)
5. Only then reach for the pattern that names and isolates that specific kind of change **under those constraints**
6. Build the simplest version that satisfies it
7. **Instrument it** (metrics, tracing, structured logging) *before* it breaks in production
8. New requirement arrives → current structure strains at one specific point → refactor toward a better-fitting pattern

Patterns come out at step 5 and step 8 — never at step 1.

## 2. The core insight: patterns name axes of *change*, not types of *problem*

Every classic pattern answers: *"What is the one thing here that's going to vary, and how do I wall it off so the rest of the system doesn't have to know or care?"*

In **production distributed systems**, this question extends across process boundaries. The "rest of the system" might be a different service, a different replica, or a different team's codebase.

| Pattern | Axis of change it isolates | Production extension |
|---|---|---|
| Strategy | The algorithm/behavior used to do something | Can be hot-reloaded via feature flags; selection logic itself becomes a volatility point |
| Factory Method / Abstract Factory | Which concrete object gets created | Becomes a service registry or DI container; thread-safe instantiation is non-negotiable |
| Builder | The steps/parts used to assemble one object | Validation rules often embed here; invalid intermediate states must be observable |
| Adapter | The interface of something you don't control | Critical at service boundaries; circuit-breaker logic often lives in the adapter layer |
| Facade | The number of subsystems a caller has to know about | Often becomes an API Gateway or BFF; latency budgets must account for fan-out |
| Decorator | Which combination of responsibilities an object has | Stack depth affects stack memory and latency; order of wrapping matters for correctness |
| Observer | How many things need to react when one thing happens | At scale, becomes a message bus; backpressure and dead-letter handling are mandatory |
| State | Which behavior applies given internal status | Distributed state machines need persistence and reconciliation; atomic transitions are hard |
| Command | What an action is bound to, and when it executes | Becomes a job queue; idempotency keys and exactly-once semantics are the real challenge |
| Singleton | Whether more than one instance is allowed to exist | In distributed systems, "exactly one" requires distributed locks or consensus; prefer scoped instances |

## 3. The decision framework

For every responsibility/entity, run these questions.

**Q1 — Is this fixed for the life of the system, or will it plausibly have more than one variant?**
If fixed → plain code, no pattern.

**Q2 — If it varies, what *kind* of thing is varying?**

| What's varying | Look toward |
|---|---|
| The *algorithm* used | Strategy |
| *Which class* gets instantiated | Factory Method / Abstract Factory |
| *How* an object gets built | Builder |
| The *shape of an external interface* | Adapter |
| The *number of subsystems* a client would otherwise call directly | Facade |
| *Which optional responsibilities* an object has, in combination | Decorator |
| *How many listeners* need to react to one event | Observer |
| The object's *own internal state* driving different behavior | State |
| *What action* to run — later, repeatedly, or undoably | Command |
| Whether the system must guarantee *exactly one* instance of something | Singleton |

**Q3 — Does the requirement text explicitly say "should support adding new X without changing existing code"?**
Direct pointer to Open-Closed Principle. Almost always Strategy, Factory, or Decorator.

**Q4 — Am I introducing this pattern because I've already seen 2+ concrete variants, or because it "feels professional"?**
If the latter, don't.

**Q5 — What are the architecture constraints?**
| Constraint | Implication for pattern selection |
|---|---|
| **Latency < 10ms p99** | Avoid reflective Factory lookups; pre-register strategies in a map; avoid deep Decorator stacks |
| **Strong consistency required** | State pattern needs distributed transactions or Saga; Observer needs synchronous delivery |
| **Eventual consistency acceptable** | Observer can be async/message-bus; State transitions can be queued |
| **High throughput (>10K rps)** | Immutable strategies; lock-free Observer subscription lists; object pooling instead of per-request Factory allocation |
| **Multi-region deployment** | Singleton becomes a distributed problem; prefer per-region scoped instances |
| **Strict audit/compliance** | Command pattern with append-only logs; every state transition must be persisted |

**Q6 — How will I observe this in production?**
Every pattern introduces indirection. Indirection makes debugging harder. Before applying a pattern, ask:
- Can I trace a request through the strategy selection?
- Can I measure factory creation latency?
- Can I detect an observer that never unsubscribes (memory leak)?
- Can I log state transitions with context for replay?

## 4. Patterns compose — and this is where "stuck, then better" comes from

Common production progression:

1. You add **Strategy** to isolate a varying algorithm.
2. Requirements grow: 5 strategies, caller has to know which concrete class to instantiate based on some input. Instantiation logic is itself a volatility — introduce **Factory**.
3. Later, an object needs several behaviors *stacked* rather than swapped exclusively — pushed from Strategy toward **Decorator**.
4. At scale, the Decorator stack becomes a latency bottleneck — you refactor to a **Pipeline** (composite strategy) with explicit metrics per stage.

This is the normal way volatility reveals itself. The difference in production is that each refactor must preserve observability and often migrate state without downtime.

## 5. Relationship to SOLID + Operational Concerns

Patterns are concrete techniques for satisfying **Open-Closed Principle** along one axis, while **Single Responsibility Principle** tells you *where* to draw the boundary.

In production, two more principles dominate:
- **Observability Principle**: Every axis of variation should be measurable independently. If you can't tell which Strategy is running or which State an entity is in, you can't operate the system.
- **Failure Isolation Principle**: A misbehaving Strategy, Observer, or State handler must not crash the host process. Patterns should be wrapped with bulkheads, circuit breakers, or timeouts.

## 6. The YAGNI guardrail

Apply a pattern only when:
- You already have 2+ concrete variants in the requirements, **or**
- The requirements explicitly demand extensibility, **or**
- You're mid-design and a follow-up requirement strains your current structure at one specific point, **or**
- **You need the operational boundary for safety** (e.g., wrapping a third-party SDK in an Adapter so you can circuit-break it)

Otherwise, write the plain version.

---
