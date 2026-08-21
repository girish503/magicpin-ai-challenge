# Engineering Rules

These rules apply to every subsequent change in this repository.

1. Do not modify official challenge artifacts: `challenge-brief.md`, `challenge-testing-brief.md`, `engagement-design.md`, `engagement-research.md`, `examples/`, `judge_simulator.py`, or the source files under `dataset/`. Generated output may be refreshed only by running the supplied generator.
2. Never fabricate context. Merchant facts, offers, prices, research findings, citations, dates, slots, customer facts, and competitor facts must be grounded in the supplied current context.
3. Never copy, closely paraphrase, or template-match case-study wording. Learn the scoring pattern, then produce independently worded, context-specific messages.
4. Preserve determinism: identical state and request inputs must yield the same response. Do not use random decisions or uncontrolled LLM sampling.
5. Decide **what** to communicate with deterministic, typed business logic before using an LLM to decide **how** to phrase it.
6. Do not replace deterministic business rules (scope resolution, consent, expiry, suppression, deduplication, response schema validation, or safety gates) with an LLM.
7. Respect each category's voice, allowed vocabulary, and taboos. Respect merchant language and customer language preference.
8. Customer-facing sends require matching merchant/customer ownership, an eligible customer-scoped trigger, and explicit consent for the communication purpose. Opt-out, hostile, and stop signals override all engagement goals.
9. Keep endpoint latency below the challenge limit; design to the stricter per-endpoint budgets documented in `docs/SPEC_ANALYSIS.md` and retain a deterministic fallback.
10. Do not add unnecessary dependencies or external services. Do not transmit challenge context to non-LLM external APIs.
11. Record architectural decisions and assumptions in `docs/DECISION_LOG.md` before making material design changes.
12. Test relevant behavior and validation before declaring work complete. Report actual commands and outcomes; never claim a test passed when it was not run.
13. Treat context pushes as versioned source-of-truth updates. Apply valid higher versions atomically and do not compose from stale or partially resolved context.
14. Do not proceed from analysis to FastAPI or bot implementation until the task explicitly authorizes that phase.
15. Treat `payload.placeholder = true` as insufficient evidence. A trigger kind alone never authorizes a factual claim; emit no action unless independently supplied context supports the exact planned fact.
