# Phase 1: Specification Analysis

## Scope and authoritative inputs reviewed

This analysis covers the complete challenge brief, testing brief, engagement design and research notes, API-call examples, case studies, dataset generator, and local judge simulator. The challenge defines a stateful, proactive WhatsApp engagement service; it is not a one-shot generic chatbot.

## Exact functional requirements

### Core composition contract

The conceptual composition function is:

```python
compose(category, merchant, trigger, customer: dict | None) -> dict
```

It operates on four supplied context types:

| Context | Purpose | Required for |
|---|---|---|
| `CategoryContext` | Vertical-specific voice, offers, peer benchmarks, digest, content, seasons, trends | Every message |
| `MerchantContext` | Business identity, subscription, performance, offers, history, aggregates, signals | Every message |
| `TriggerContext` | The event and reason to communicate now | Every message |
| `CustomerContext` | A particular merchant customer's relationship, preferences, and consent | Customer-scoped messages only |

Every outbound message must have a trigger. Merchant-scoped messages send as `vera`; customer-scoped messages send as `merchant_on_behalf`. A customer context is optional only because merchant-facing messages do not use it, not because customer consent may be omitted.

### Required behavior

- Resolve the current category, merchant, trigger, and, when applicable, customer context from versioned context pushes.
- Decide whether a currently available trigger merits a proactive send; returning no action is valid and restraint is rewarded.
- Use a concrete, verifiable fact supplied in the resolved contexts whenever communicating a claim. Use source citations for research and compliance claims.
- Match the category's voice/taboos and the recipient's supported language or language preference.
- Use actual active merchant offers, not generic discounts or catalog items presented as already active.
- Explain why now by tying the message to the trigger's kind and payload.
- Use one primary, low-friction CTA. Action triggers normally use a binary CTA; pure-information messages may use no CTA. Booking flows may appropriately use a slot choice.
- Respect the WhatsApp 24-hour window: an initial outbound must be represented by a sensible approved-template structure with parameter values; messages in an active session may be free-form.
- Deduplicate with the trigger suppression key and avoid repeating a body in the same conversation.
- Handle replies: recognize auto-replies, explicit commitment, explicit opt-out/hostility, and off-topic requests. Stop or back off when indicated.

### Optional versus mandatory

| Mandatory | Optional / competitive advantage |
|---|---|
| Stateful HTTP API, five specified endpoints, correct response shapes, idempotent context updates, proactive tick handling, grounded composition, latency compliance, privacy controls | `conversation_handlers.py` in the file-submission framing; multi-turn capability is a tiebreaker in the brief but is exercised by the HTTP testing brief |
| `bot.py`, `submission.jsonl` with 30 lines, and <=1-page `README.md` in the artifact-submission framing | LLMs, retrieval, tool/function calling, prompt variants, a persistent DB (in-memory persistence during the test is sufficient) |
| Category/merchant language and consent controls; no fabrication; no external data scraping | URLs are described as allowed by the main brief, but prohibited by the API examples; treat URLs as disallowed pending clarification |

The testing brief has a later and more operationally detailed requirement for a public stateful service. A future implementation should satisfy both deliverable forms unless the challenge owner resolves the apparent submission-protocol split.

## HTTP API requirements

All endpoints are JSON, UTF-8, and HTTPS in deployment (HTTP is permitted for local testing). The required surface is five endpoints.

| Endpoint | Requirement | Success response |
|---|---|---|
| `POST /v1/context` | Accept a full context by `scope`, `context_id`, `version`, `payload`, `delivered_at`; idempotent by `(context_id, version)`; atomically replace lower versions with a higher one; retain through the test | `{"accepted": true, "ack_id": "...", "stored_at": "..."}` |
| `POST /v1/tick` | Given `now` and `available_triggers`, return zero to 20 new proactive actions | `{"actions": [Action, ...]}` |
| `POST /v1/reply` | Given a conversation reply, synchronously select `send`, `wait`, or `end` | Reply action schema below |
| `GET /v1/healthz` | Liveness plus counts by all four context scopes | `{"status":"ok","uptime_seconds":N,"contexts_loaded":{"category":N,"merchant":N,"customer":N,"trigger":N}}` |
| `GET /v1/metadata` | Team and version identification | `team_name`, `team_members`, `model`, `approach`, `contact_email`, `version`, `submitted_at` |

The privacy section additionally describes an optional `POST /v1/teardown`; if received, it must erase retained context after the test.

### `POST /v1/context` errors

- Duplicate or stale version: HTTP `409`, `{"accepted": false, "reason": "stale_version", "current_version": N}`.
- Malformed input: HTTP `400`, `{"accepted": false, "reason": "invalid_scope", "details": "..."}`.
- A re-post of the same version is a no-op. The testing brief describes it as idempotent; its concrete response example uses the `409` stale-version response, so implement that exact response.

### Context payload schemas

- `category`: `slug`, `offer_catalog`, `voice`, `peer_stats`, `digest`, `patient_content_library`, `seasonal_beats`, and `trend_signals`.
- `merchant`: `merchant_id`, `category_slug`, `identity`, `subscription`, `performance`, `offers`, `conversation_history`, `customer_aggregate`, and `signals`.
- `customer`: `customer_id`, `merchant_id`, `identity`, `relationship`, `state`, `preferences`, and `consent`.
- `trigger`: `id`, `scope`, `kind`, `source`, `merchant_id`, `customer_id`, `payload`, `urgency`, `suppression_key`, and `expires_at`.

`scope` for a push is one of `category`, `merchant`, `customer`, or `trigger`; a trigger's own `scope` is `merchant` or `customer`.

### Tick action schema

Every action in `actions` needs:

```json
{
  "conversation_id": "unique new id",
  "merchant_id": "...",
  "customer_id": null,
  "send_as": "vera | merchant_on_behalf",
  "trigger_id": "...",
  "template_name": "...",
  "template_params": ["..."],
  "body": "...",
  "cta": "...",
  "suppression_key": "...",
  "rationale": "..."
}
```

`conversation_id` must be new for a tick action; a continuation uses `/v1/reply`, not another tick action with the same ID. `customer_id` is required and non-null for customer scope. Examples use `binary_yes_no`, `binary_confirm_cancel`, `open_ended`, `none`, and `multi_choice_slot` CTA labels; preserve those descriptive values rather than inventing unstructured variants.

### Reply action schema

Exactly one action shape is valid:

```json
{"action":"send", "body":"...", "cta":"...", "rationale":"..."}
{"action":"wait", "wait_seconds":1800, "rationale":"..."}
{"action":"end", "rationale":"..."}
```

`send` requires a non-empty body. Rationales are visible to the judge and must accurately reflect the actual decision and message.

## Determinism and statefulness

- The original `compose` requirement is deterministic for identical inputs. LLM use therefore requires deterministic configuration (the brief explicitly cites temperature 0); deterministic planning and fallback are still required because provider determinism alone is insufficient.
- Context state persists through the entire test; memory is acceptable only if the process does not restart.
- Higher context versions must replace the old full payload atomically. A category update, for example, must affect subsequent composition immediately and must not be merged into a stale payload by assumption.
- Conversation state must record sent bodies, suppression/opt-out state, recipient, trigger, phase, auto-reply observations, and recent commitments so replies do not repeat, requalify an explicit yes, or resume an ended conversation.
- Triggers should only be considered while active, unsuppressed, unexpired, and fully resolvable. The judge can inject unknown merchants, new customers, updated performance, new digest entries, and new triggers at any time.

## Latency, capacity, and availability requirements

| Requirement | Value |
|---|---:|
| Hard per-call timeout stated in testing brief | 30 seconds |
| Judge request rate | <=10 requests/s |
| Context payload cap | 500 KB |
| Tick action cap | 20 actions/tick |
| Test duration | 60 simulated minutes; approximately 30–45 real minutes |
| Healthz failure disqualification threshold | 3 consecutive failures |

There are conflicting detailed budgets. The API-call examples summarize `healthz`/`metadata` at 2 s, `/context` at 5 s, and `/tick`/`reply` at 10 s. The provided simulator actually uses 5 s, 10 s, 15 s, and 15 s respectively; the testing brief also repeatedly describes 30 s. Engineering should target the strictest documented targets (2/5/10 seconds) and regard 30 seconds only as the absolute failure boundary.

## Evaluation, weak scores, and penalties

The official score is five 0–10 dimensions (maximum 50): specificity, category fit, merchant fit, trigger relevance, and engagement compulsion. The simulator calls the fourth field `decision_quality`, falling back to `trigger_relevance` when parsing an LLM answer; it is judging the same “why this action now?” concept.

Phase 3 adaptive-context performance can add up to +5 per dimension. Top-ten replay evaluation can add up to +30. Operational penalties can total -20. The precise aggregation of those additions is not fully specified.

| Penalty / failure | Stated effect |
|---|---:|
| Three consecutive failing health probes | Offline; remaining ticks skipped; -10 operational |
| Tick or reply timeout | -1 each; the turn/tick is skipped or treated as silent |
| Malformed action JSON or empty `send` body | Action scores 0 and -2 each |
| Exact repeated body within a conversation | -2 per repeat |
| URL in a body (API examples) | Hard fail for action and -3 per URL |
| Fabricated context data (local simulator rubric) | -2 |
| Internal jargon exposed to merchant (local simulator rubric) | -1 |
| Case-study near duplicate | Similarity/plagiarism penalty |

High scores require grounded numerical/date/source anchors, correct vertical language, recipient-specific facts and language, an explicit trigger reason, and a compelling low-friction next step. Generic discounts, hollow “increase sales” copy, a long preamble, multiple CTAs, incorrect language, medical/promotional taboos, stale context, or unsupported facts suppress scores sharply.

## Constraints and privacy restrictions

- The supplied dataset is synthetic and must not be augmented by scraping real magicpin or Google data. Do not impersonate magicpin or conduct real outreach.
- Do not transmit merchant/customer payloads outside the test environment to non-LLM external APIs. Commercial LLM APIs are explicitly allowed for composition.
- Do not retain context after test completion; clear it on teardown when provided.
- The bot must ground every claim in supplied context. It may not invent offers, prices, research, citations, dates, names, availability, customer details, or competitor facts.
- Customer sends require merchant/customer matching and consent scope appropriate to the trigger. `STOP`, hostile language, or a not-interested reply ends future outreach.
- Prefer no URLs pending clarification: the main brief permits value-adding URLs, while the API examples declare every URL a Meta-rejected hard failure.

## Submission requirements

The main brief requests `bot.py` with `compose`, a 30-line `submission.jsonl`, and a one-page `README.md`; `conversation_handlers.py` is optional. The testing brief requires a publicly reachable bot at `https://<host>/v1/*` and a submitted public URL. The API examples and judge simulator are built around the HTTP protocol. This mismatch is logged as an unresolved question rather than resolved by assumption.
