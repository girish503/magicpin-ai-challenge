# Phase 1: Production Architecture Proposal

## Recommendation

Build a deterministic, stateful engagement pipeline in which the system chooses a permitted and worthwhile **message strategy** before a constrained composer phrases it. This is explicitly not:

```text
input -> LLM -> output
```

The key control is a typed, provenance-bearing `MessagePlan`. It contains only claims and actions selected from current supplied contexts. The LLM, if used, receives that plan and may improve recipient-appropriate wording; it does not decide facts, offers, consent, deduplication, or whether to send.

```text
Versioned Context Store
        |
Context Resolver + Conversation State
        |
Trigger Analyzer -> Eligibility / Consent / Expiry -> Suppression & Dedup
        |                                                  |
        +---------------------> Opportunity / Decision Ranker
                                      |
                              Message Strategy + MessagePlan
                                      |
                    constrained LLM Composer or deterministic renderer
                                      |
                               Output Validator / provenance check
                                      |
                       send action | deterministic safe fallback | abstain
                                      |
                         audit events, evaluation, observability
```

## System invariants

1. The latest accepted context version is the sole factual source. An update replaces its payload atomically.
2. Every proposed outbound has a resolvable active, unexpired trigger and its original suppression key.
3. A customer send requires trigger/customer/merchant ownership match, active consent for the trigger purpose, and no opt-out state.
4. Every factual clause in a message is backed by one or more provenance paths in the resolved contexts. If it is not backed, it is removed or the action is abandoned.
5. An LLM cannot introduce new factual claims, an offer, a price, an availability claim, a citation, or recipient data.
6. Deterministic validators and fallback renderers must keep the API inside the latency budget when an LLM is unavailable or rejected.
7. No outgoing body repeats verbatim in its conversation. A hard stop closes the conversation and applies durable suppression.

## Components

| Component | Responsibility, inputs, and outputs | Why it exists / failure modes | LLM or deterministic |
|---|---|---|---|
| 1. Context Store | Persists `(scope, context_id) -> {version, payload, delivered_at}` and indexing by merchant/category/customer/trigger. Inputs: `/v1/context`. Outputs: atomic lookup and counts. | Makes pushes idempotent and update-safe. Failures: stale overwrite, partial update, lost state after restart, unknown scope. Reject malformed/stale data; snapshot reads. | Deterministic. |
| 2. Context Resolver | Resolves a trigger into current category, merchant, and optional linked customer; verifies IDs and category match. Inputs: trigger ID plus store snapshot. Outputs: `ResolvedContext` with version/provenance map or a typed unresolved reason. | Avoids composing from mixed versions or accidentally pairing a customer with another merchant. Failures: missing dependent context, bad reference, category mismatch. Return no action until resolvable. | Deterministic. |
| 3. Conversation State | Stores conversation ID, recipient, sent bodies, phase, trigger, last activity, auto-reply counts, intent, waits, opt-out/end status, and context versions used. Inputs: actions and `/v1/reply`. Outputs: permitted next transition. | Required for 24h behavior, anti-repetition, replay tests, action handoff, and graceful exit. Failures: state loss, cross-conversation leakage, re-opening closed conversation. | Deterministic state machine. |
| 4. Trigger Analyzer | Parses typed payload by `kind`, checks expiry/urgency/active availability, extracts safe factual candidates, and maps kind to required consent and strategy family. Inputs: `ResolvedContext`, simulated `now`. Outputs: `TriggerAssessment`. | Payloads vary and many generated ones are placeholders. Failures: treating `placeholder` as a real metric, unsupported kind, expired trigger, derived date errors. Mark inadequate payload as abstain or use only independently grounded fields. | Deterministic; optional offline LLM-assisted taxonomy authoring, never runtime authority. |
| 5. Intent Detector | Classifies an incoming reply into hard stop, auto-reply, explicit commitment, defer/wait, question, off-topic, or neutral. Inputs: normalized reply plus conversation state. Outputs: intent label, confidence, evidence. | Replay behavior depends on fast routing; explicit yes must not lead to requalification. Failures: false stop or missed stop, one-off canned text mistaken for a user. Stop rules must be high-recall and override all else. | Deterministic phrase/repetition rules first; a small deterministic-configured LLM may classify ambiguous remainder, with safe fallback to wait/clarify. |
| 6. Opportunity / Decision Ranker | Selects at most the highest-value eligible trigger per recipient/tick using urgency, evidence strength, relevance, fatigue, frequency, and expected compulsion. Inputs: assessments, state, suppressions. Outputs: ordered `Decision` or abstention with reason. | Prevents spam, action cap breaches, and sending sparse generated triggers. Failures: repeatedly favoring urgency, ignoring recent sends, too many concurrent actions. | Deterministic scoring and thresholds. |
| 7. Suppression / Deduplication | Enforces trigger suppression key, message cooldowns, conversation terminal status, opt-outs, and exact-body no-repeat. Inputs: candidate decision, state. Outputs: allow/block and auditable reason. | Required by contract, etiquette, and anti-repetition penalty. Failures: race condition at tick, suppressing an intended new trigger, treating wait as closed. Use atomic reservation keyed by recipient+suppression key. | Deterministic. |
| 8. Message Strategy | Maps a decision to a strategy: research citation, performance interpretation, compliance alert, recall/appointment slot, commitment execution, auto-reply backoff, graceful end, etc. Selects a CTA class, template requirement, salutation, tone rules, and claim slots. Inputs: decision and provenance candidates. Outputs: `MessagePlan`. | Implements “what before how”; prevents a free-form LLM from inventing the intervention. Failures: wrong strategy for scope, CTA mismatch, use of non-active offer. | Deterministic dispatch and data-driven rules. |
| 9. LLM Composer | Renders an approved `MessagePlan` into concise recipient language, returning structured fields (`body`, selected claim IDs, CTA). Inputs: plan, category voice constraints, permitted phrase/claim inventory. Outputs: candidate prose only. | Helps produce natural category-appropriate Hindi-English messaging without letting model choose facts. Failures: hallucination, verbosity, taboo words, nondeterminism, timeout. Use zero-temperature/seeded settings where available and tight schema; it is never the only renderer. | Optional LLM; deterministic renderer remains required. |
| 10. Output Validator | Checks JSON/action schema, send_as scope, IDs, CTA, template fields, no URL, no taboo term, language policy, factual provenance, offer status, citation match, consent, length/readability, and repetition. Inputs: candidate output + plan + state. Outputs: accepted output or a specific reject reason. | An LLM cannot self-certify safety or correctness. Failures: overly strict rejection/false negatives or unsafe fuzzy matching. Validate structured claim references, normalized numerals, and exact supplied citations; fall back rather than retry indefinitely. | Deterministic. An LLM critic can be advisory only, never an allow gate. |
| 11. Deterministic Fallback | Renders a short strategy-specific message from fact slots or returns no action/end/wait. Inputs: `MessagePlan` and validation failure/timeout. Outputs: valid response within budget. | Preserves availability and determinism when the model or network is unavailable. Failure: low copy quality; mitigate with curated category phrase templates. Never emit when fact/consent/strategy gates fail. | Deterministic. |
| 12. Evaluation / Observability | Emits structured audit events: context versions, resolver result, decision score, strategy, claim provenance, composer/fallback selection, validation result, latency, send/outcome, and score feedback. Inputs: all stages. Outputs: logs, metrics, replay records, offline evaluation corpus. | Enables explainable rationales, prompt/version audit, debugging, A/B comparisons, and safe iteration. Failures: logging sensitive raw data or missing correlation IDs. Redact/limit and destroy with test context. | Deterministic instrumentation; optional offline LLM grading is not runtime control. |

## The `MessagePlan` boundary

The plan should be a small typed object, not prose prompt context. Illustrative fields:

```text
recipient: merchant | customer
send_as: vera | merchant_on_behalf
trigger_id, suppression_key, strategy, template_requirement
language_mode, category_voice, taboos
claim_slots: [{claim_id, rendered_value, source_path, allowed_paraphrases}]
offer_id: optional active merchant offer only
cta_class, allowed_cta_text
rationale_facts: [source paths]
```

For example, a research strategy can select the trigger's `top_item_id`, the matching category digest title, source, trial count, patient segment, and an eligible merchant signal. The LLM sees those fields, not the full unrestricted dataset. The validator checks that the rendered output references only selected claim IDs and exact approved source text/numeric values. A customer appointment plan similarly admits only verified slot records, consent-appropriate purpose, merchant identity, and the customer's known language/preference.

## Runtime flows

### Context push

1. Validate the envelope, scope, ID, payload shape, and version.
2. Reject malformed or stale updates; atomically store a valid higher version.
3. Update lookup indexes and emit an audit event. Do not compose during this endpoint.

### Tick / proactive send

1. Snapshot store at tick start and resolve each `available_trigger`.
2. Analyze expiry, scope, consent, payload evidence, fatigue, and suppression.
3. Rank only eligible decisions; apply per-recipient and 20-action caps.
4. Build one `MessagePlan` per selected decision, reserve suppression atomically, compose/render, then validate.
5. If the candidate fails or is slow, use a valid deterministic fallback; otherwise release reservation and abstain.
6. Create a unique conversation ID, persist state, and return the valid action(s).

### Reply / conversation continuation

1. Load conversation state; unknown/ended IDs should safely end or wait rather than guess facts.
2. Detect stop/hostility first, then repeated auto-reply, then explicit commitment, then deferral/off-topic/neutral.
3. Transition the state machine. Commitment selects an execution/confirmation strategy; it never goes back to qualification. Auto-reply follows a capped send/wait/end policy. Hard stops end and create broad suppression.
4. Render/validate a `send`, `wait`, or `end` response with an accurate concise rationale.

## LLM placement trade-offs

| Question | Recommendation | Trade-off |
|---|---|---|
| Trigger classification | Do deterministic mapping from supplied `kind`, `scope`, and schema. Use no runtime LLM for known kinds. | An LLM can help recognize future untyped text offline, but it creates latency and inconsistent eligibility decisions. |
| Decision making | Deterministic ranker with explicit policies for consent, expiry, suppression, data sufficiency, fatigue, and strategy selection. | An LLM may create novel campaign ideas, but it cannot be allowed to override privacy, factual grounding, or deterministic schedule behavior. |
| Message generation | Use an optional constrained LLM after plan construction; accept only schema/provenance-valid output. Keep a deterministic renderer. | LLM improves naturalness, code-mix, and variation but risks invention and timeout. Templates alone are safe but can become formulaic; strategy-specific phrasing libraries mitigate this. |
| Validation | Deterministic validator is authoritative. An optional LLM critic may flag style issues for a retry, never authorize sending. | LLM validation cannot reliably establish data provenance and adds latency/non-determinism. Structured claim references make deterministic validation feasible. |

## Latency and deployment posture

- Keep context writes and health checks entirely local/in-memory or local durable storage.
- Precompute indexes and category policy on context update, not tick.
- Avoid per-trigger external calls. The challenge prohibits non-LLM external calls with payloads.
- Budget composition below the stricter 10-second tick/reply target. Use a short LLM timeout and immediate fallback; never consume the documented 30-second hard limit.
- Serialize only the selected plan to an LLM; do not send all contexts or conversation history.
- Run deterministic validation in-process, collect timer metrics by stage, and cap actions before composition.

## Proposed delivery sequence (not implementation in this phase)

1. Define schemas, store/version semantics, and test fixtures from the expanded data.
2. Implement resolver, suppression, consent policy, state transitions, decision ranker, and deterministic message plans/renderers.
3. Add HTTP endpoints and contract tests only after this phase is explicitly authorized.
4. Add constrained LLM composition behind the validator and fallback.
5. Test context version injection, all customer-consent paths, auto-reply repetition, commitment transition, hostility, no-URL validation, no-repeat behavior, and latency degradation.
