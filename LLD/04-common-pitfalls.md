# Part 4: Pitfalls & Interview Playbook

## Common mistakes

- **Pattern-first thinking.** Deciding "I'll use Observer" before identifying what actually needs to react to what. Always derive the volatility first.
- **Over-engineering for a hypothetical future.** Adding a Factory for a type that will never have a second variant because "it's more extensible." Extensibility you didn't need is just complexity you did.
- **Singleton by default.** Reaching for Singleton anytime a class happens to be instantiated once in your current design, rather than when the requirement genuinely demands exactly one instance system-wide. This is the single most over-applied pattern in interviews.
- **Vocabulary-dropping.** Naming a pattern without being able to say, in one sentence, what specifically is varying that the pattern isolates. Interviewers notice this immediately.
- **Ignoring YAGNI.** Building a generic plugin architecture for a requirement that only ever mentions two vehicle types. Match the design's flexibility to what's actually stated or clearly implied, not to what's theoretically possible.
- **Solving the wrong axis.** E.g., using Strategy for what's actually a state-transition problem (behavior depending on an object's own lifecycle status, not on an interchangeable algorithm) — this usually shows up as an awkward strategy interface with parameters that don't quite fit every "variant."

## What interviewers are actually scoring

Contrary to what a pattern-heavy design might suggest, interviewers are rarely scoring "did you use N patterns." They're scoring:

- **Correctness** against the literal stated requirements
- **Extensibility** — can a new variant (vehicle type, payment method, notification channel) be added without modifying existing, tested classes? (Open-Closed Principle in action)
- **Clean responsibility boundaries** — does each class have one reason to change? (Single Responsibility Principle)
- **Reasonable coupling** — do unrelated parts of the system know about each other only through narrow interfaces?
- **Your reasoning, spoken aloud** — can you justify *why* a structure is shaped the way it is, and what you'd change if a new requirement showed up?

Pattern names are a shorthand for communicating a structure quickly — they're not the deliverable.

## How to narrate pattern choices out loud

Instead of: *"I'll use the Strategy pattern here."*

Say: *"The way fare gets calculated is going to vary — normal, surge, promo — but the checkout flow around it stays the same, so I'm pulling that calculation behind one interface so new fare types don't touch the checkout code."*

You've just described Strategy without needing the interviewer to independently verify you understand it — the name only comes up if it comes up naturally. This ordering — **what varies → why it needs isolating → what that gives you** — is worth more than the name of the pattern itself.

## Pre-interview review checklist

- [ ] For every pattern in my design, can I state the specific thing that varies, in one sentence, without saying the pattern's name?
- [ ] Is there any pattern in my design justified only by "it might be needed later" rather than a stated or implied requirement?
- [ ] Is there any Singleton that's really just "a class I happen to only instantiate once" rather than "must be exactly one, system-wide"?
- [ ] If the interviewer adds one new variant right now (new type, new channel, new rule), which existing classes would I have to modify? (Ideally: none, or very few — and none of them the "stable" core classes.)
- [ ] Have I described *why* out loud, not just named the pattern?

---

## Closing note

Going back to the original framing: patterns aren't the point — change is. A design that correctly identifies where change will happen and isolates it there is a good design whether or not it happens to match a textbook pattern by name. The name is just how you communicate that structure quickly to someone else who already knows the vocabulary.
