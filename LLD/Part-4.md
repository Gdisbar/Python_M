
# Part 4: Pitfalls & Interview Playbook

*(Enhanced with production failure modes, operational anti-patterns, and architecture decision templates)*

## Common Mistakes

- **Pattern-first thinking.** Deciding "I'll use Observer" before identifying what reacts to what.
- **Over-engineering for a hypothetical future.** Adding a Factory for a type that will never have a second variant.
- **Singleton by default.** Reaching for Singleton anytime a class happens to be instantiated once. In production, this creates global state and hurts testability. In distributed systems, it creates a consensus problem you didn't need.
- **Vocabulary-dropping.** Naming a pattern without saying, in one sentence, what specifically is varying.
- **Ignoring YAGNI.** Building a generic plugin architecture for two vehicle types.
- **Solving the wrong axis.** Using Strategy for a state-transition problem.
- **Missing observability.** Applying a pattern but not adding metrics, tracing, or logging at the variation point. When it breaks at 3 AM, you can't tell which strategy was active or which state the entity was in.

## Production-Specific Pitfalls

| Pattern | Production Pitfall | Detection | Prevention |
|---|---|---|---|
| **Strategy** | Strategy registry lookup is O(n) or uses reflection | p99 latency spikes on every request | Pre-register in `Map<String, Strategy>` at startup |
| **Factory** | Factory creates objects with unbounded threads/connections | Connection pool exhaustion, thread count alerts | Factory returns pooled objects; validate at creation time |
| **Observer** | Dead observers cause memory leaks | Heap growth, GC pressure | Weak references or mandatory unsubscribe; metrics on observer count |
| **State** | Invalid state transition after crash recovery | Data inconsistency, support tickets | Persist state + version; optimistic locking; reconciliation jobs |
| **Decorator** | Stack overflow from circular wrapping | Crash on specific request types | Document valid wrapping orders; validate at build time |
| **Command** | Duplicate execution without idempotency | Double charges, duplicate records | Idempotency keys; deduplication store |
| **Singleton** | Distributed singleton without consensus | Split-brain, double allocation | Per-region scope; distributed locks if truly global |

## What Interviewers Are Actually Scoring

- **Correctness** against literal stated requirements
- **Extensibility** — can a new variant be added without modifying existing, tested classes?
- **Clean responsibility boundaries** — does each class have one reason to change?
- **Reasonable coupling** — do unrelated parts know about each other only through narrow interfaces?
- **Operational awareness** — does the candidate mention thread safety, failure modes, or observability unprompted?
- **Reasoning, spoken aloud** — can you justify *why* a structure is shaped the way it is?

## Architecture Decision Record (ADR) Template

For every pattern in your design, be able to fill this out:

> **Context:** [What is varying and why?]  
> **Decision:** [Which pattern, and where is the boundary?]  
> **Constraints:** [Latency, consistency, throughput, deployment model]  
> **Consequences:** [What does this make easy? What does it make hard?]  
> **Observability:** [How will I know if this is working or failing?]  
> **Recovery:** [What happens if the pattern's abstraction leaks or fails?]

## How to Narrate Pattern Choices Out Loud

Instead of: *"I'll use the Strategy pattern here."*

Say: *"The way fare gets calculated is going to vary — normal, surge, promo — but the checkout flow stays the same. Under our latency constraint of 10ms p99, I'll pre-register strategies in a concurrent map at startup so selection is O(1). I'll also tag metrics by strategy name so we can detect if surge pricing starts misbehaving in production."*

## Pre-Interview / Pre-Production Review Checklist

- [ ] For every pattern, can I state the specific thing that varies, in one sentence, without saying the pattern's name?
- [ ] Is there any pattern justified only by "it might be needed later"?
- [ ] Is there any Singleton that's really just "a class I happen to only instantiate once"?
- [ ] If the interviewer adds one new variant right now, which existing classes would I have to modify? (Ideally: none.)
- [ ] **Production:** If this service restarts mid-transition, can it recover correctly?
- [ ] **Production:** Can I trace a request through every pattern boundary?
- [ ] **Production:** Are there any unbounded queues, caches, or observer lists?
- [ ] Have I described *why* out loud, not just named the pattern?

---

## Closing Note

Patterns aren't the point — change is. In production, **change happens under failure, at scale, while someone is on call**. A good design identifies where change will happen, isolates it, instruments it, and provides a recovery path when the isolation leaks. The pattern name is just how you communicate that structure quickly to someone else who already knows the vocabulary — and to the engineer who has to debug it at 3 AM six months from now.