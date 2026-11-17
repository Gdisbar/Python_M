# LLD Pattern Selection: A Field Guide
### From "which pattern is this?" to "what is actually changing here?"

## Why this guide exists

Most LLD (Low-Level Design) courses teach patterns backwards: they hand you a scenario and tell you which pattern "solves" it. That's fine for recognizing patterns in hindsight, but it's the opposite of how design actually happens. In practice — and in a well-run interview — you:

1. Get a problem statement
2. Model the entities and responsibilities
3. Notice a specific part of the design is likely to change, or already has multiple variants
4. Only then reach for the pattern that names and isolates that specific kind of change
5. Get a new requirement mid-design, realize your current structure can't absorb it cleanly, and refactor toward a better-fitting pattern

Patterns are a **diagnostic vocabulary for volatility**, not a checklist of things your design needs to contain. This guide is built around that reframe.

## How this guide is organized

| Part | File | What it covers |
|---|---|---|
| 1 | `01-mental-model.md` | The framework: how to identify volatility in a problem *before* naming a pattern, and how to decide when a pattern is warranted at all |
| 2 | `02-pattern-catalog.md` | The ~10 patterns that show up most in real LLD work and interviews, each mapped to the specific volatility it isolates, with language-agnostic structure |
| 3 | `03-worked-examples.md` | Three classic LLD problems solved end-to-end using the framework — including the "got stuck, refactored to a better pattern" moment |
| 4 | `04-pitfalls-and-interview-playbook.md` | Common misuses, what interviewers actually evaluate, and a pre-interview checklist |

## How to use it

- Read Part 1 once, fully — it's the mental model everything else depends on.
- Keep Part 2 open as a reference while you practice problems.
- Work through Part 3 yourself before reading the walkthroughs — try to derive the same patterns independently first, then compare.
- Skim Part 4 the night before an interview.
