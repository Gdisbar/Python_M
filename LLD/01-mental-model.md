# Part 1: The Mental Model — Deriving Patterns Instead of Recalling Them

## 1. The problem with "scenario → pattern" learning

Most tutorials teach patterns as answers to fixed scenarios: "need to notify multiple objects? Use Observer." That works only if the interview problem happens to match the memorized scenario word-for-word. It almost never does — interviewers deliberately rephrase requirements, combine two problems, or change one constraint specifically to see if you're pattern-matching keywords instead of reasoning about the design.

The real sequence, every time, is:

**Problem statement → model responsibilities → find what varies → name the axis of variation → the pattern that isolates that axis becomes obvious → build the simplest version that satisfies it → new requirement arrives → current structure strains at one specific point → refactor toward a better-fitting pattern**

Patterns come out at step 5 and step 8 — never at step 1.

## 2. The core insight: patterns name axes of *change*, not types of *problem*

Every classic pattern is really answering one question: "What is the one thing here that's going to vary, and how do I wall it off so the rest of the system doesn't have to know or care?"

| Pattern | Axis of change it isolates |
|---|---|
| Strategy | The algorithm/behavior used to do something |
| Factory Method / Abstract Factory | Which concrete object gets created |
| Builder | The steps/parts used to assemble one object |
| Adapter | The interface of something you don't control |
| Facade | The number of subsystems a caller has to know about |
| Decorator | Which combination of responsibilities an object has |
| Observer | How many things need to react when one thing happens |
| State | Which behavior applies given internal status |
| Command | What an action is bound to, and when it executes |
| Singleton | Whether more than one instance is allowed to exist |

Once you see it this way, you stop asking "which pattern fits this problem" and start asking "what, specifically, is going to vary here — and along which of these axes."

## 3. The decision framework

For every responsibility/entity you identify while modeling a problem, run it through these questions.

**Q1 — Is this fixed for the life of the system, or will it plausibly have more than one variant (now, or per the stated requirements)?**
If fixed → plain code, no pattern. Don't design for hypothetical futures the interviewer never mentioned (see the YAGNI note below).

**Q2 — If it varies, what *kind* of thing is varying?**

| What's varying | Look toward |
|---|---|
| The *algorithm* used (pricing, sorting, matching, validation) | Strategy |
| *Which class* gets instantiated | Factory Method / Abstract Factory |
| *How* an object gets built (many optional fields, multi-step assembly) | Builder |
| The *shape of an external interface* you must conform to | Adapter |
| The *number of subsystems* a client would otherwise call directly | Facade |
| *Which optional responsibilities* an object has, in combination | Decorator |
| *How many listeners* need to react to one event | Observer |
| The object's *own internal state* driving different behavior | State |
| *What action* to run — later, repeatedly, or undoably | Command |
| Whether the system must guarantee *exactly one* instance of something | Singleton |

**Q3 — Does the requirement text explicitly say "should support adding new X without changing existing code"?**
That sentence is a direct pointer to the Open-Closed Principle, and almost always to Strategy, Factory, or Decorator — depending on whether "X" is a behavior, an object type, or a responsibility.

**Q4 — Am I introducing this pattern because I've already seen 2+ concrete variants (or the requirements guarantee more are coming), or because it "feels professional" to have one?**
If it's the latter, don't. An unnecessary pattern is worse than none — it adds indirection someone (an interviewer, or a future teammate) has to unwind for zero benefit.

## 4. Patterns compose — and this is where "stuck, then better" comes from

You rarely land on the final structure in one pass. A common progression:

1. You add **Strategy** to isolate a varying algorithm.
2. Requirements grow: now there are 5 strategies, and the caller has to know which concrete class to instantiate based on some input (a type string, a user tier, a region). That instantiation logic is itself a volatility — so you introduce a **Factory** whose entire job is picking the right Strategy.
3. Later, an object needs several of these behaviors *stacked* rather than swapped exclusively — that's the moment you're being pushed from Strategy toward **Decorator**.

This is exactly the "stuck on some point → move to a better one" loop. It isn't a sign you designed it wrong the first time — it's the normal way volatility reveals itself, one requirement at a time. Part 3 walks through this happening in real problems.

## 5. Relationship to SOLID

Patterns aren't a separate topic from SOLID — most of them are concrete techniques for satisfying the **Open-Closed Principle** (open for extension, closed for modification) along one specific axis, while the **Single Responsibility Principle** is what tells you *where* to draw the boundary in the first place. If you can't say which SOLID principle a pattern is serving in your design, you probably don't need it yet.

## 6. The YAGNI guardrail

Apply a pattern only when one of these is true:

- You already have 2+ concrete variants in the requirements, **or**
- The requirements explicitly demand extensibility ("support new payment methods later," "pluggable ranking algorithm"), **or**
- You're mid-design and just got a follow-up requirement that strains your current structure at one specific point

Otherwise, write the plain version. A `Checkout` class with one hardcoded pricing method is *correct* code, not a missed pattern, if nothing in the problem says pricing will vary.

---
**Next:** Part 2 — `02-pattern-catalog.md`, the ~10 patterns mapped to volatility with language-agnostic structure.
