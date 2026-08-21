# Phase 1: Judge Analysis

## What is evaluated

The official harness evaluates a stateful proactive bot across an initial test window, adaptive context injections, and (for the top 10) replay conversations. The main brief defines five 0–10 dimensions, for a base 50-point message score:

| Dimension | What the judge rewards |
|---|---|
| Specificity | A verifiable number, price, date, source, headline, peer statistic, or exact local fact supplied in context |
| Category fit | Correct category voice, vocabulary, offer format, regulated-category restraint, and taboo avoidance |
| Merchant fit | Correct merchant / owner identity, local and performance context, active offers, history, and language |
| Trigger relevance | A clear causal explanation of why the message is being sent now, using the actual trigger payload |
| Engagement compulsion | A realistic reason to reply: curiosity, loss aversion, social proof, reciprocity, effort externalization, or one clear low-friction CTA |

The local simulator calls the fourth dimension `decision_quality`, but its rubric describes trigger relevance and parses a judge response's `trigger_relevance` field as fallback. Treat it as the same evaluation concern.

## How the supplied simulator scores

`judge_simulator.py` is a local, simplified evaluator rather than the full hosted protocol.

1. It loads the five category files and **seed** merchant/customer/trigger JSON files, not `dataset/expanded` or `test_pairs.json`.
2. Its LLM scoring prompt exposes category slug/tone/taboos; merchant name, owner, locality, languages, a small performance subset, signals, and active offers; trigger kind/payload/urgency; and only customer identity. The hosted judge can see the full pushed contexts and should be considered the real requirement.
3. The scorer delegates the 0–10 decisions to a configurable LLM at temperature 0.2. If LLM output fails, its fallback awards specificity based on digit count and gives 5 to each other dimension; do not optimize for this fallback.
4. The local score system lists fabrication (-2) and merchant-facing internal jargon (-1), although its `ScoreResult.penalties` are not actually populated by the Python code. The official briefs and examples remain the operational floor.

## What causes weak scores

- Generic “increase sales” or flat-discount language where a concrete service/price or other verified fact is present.
- A message whose only connection to the trigger is a generic recommendation.
- Claiming an offer, price, citation, availability, customer preference, peer figure, competitor, date, or outcome not in the current context.
- A clinical, regulated category rendered as hype; a salon, restaurant, gym, or pharmacy message using the wrong register; taboo terms.
- Ignoring a merchant's languages or a customer's language preference and relationship state.
- Multiple competing calls to action, a buried CTA, or a lengthy greeting/preamble.
- Stale composition after a versioned category, merchant, customer, or trigger update.
- A rationale that describes a decision not actually visible in the message.
- Repeated bodies, too many nudges, and messaging after a stop/hostile response.

## What supports 9–10 scores

1. A specific source-grounded anchor appropriate to the exact trigger: research/compliance citation, date, price, affected batch, known performance movement, validated slot, or peer comparison.
2. Correct category semantics, not merely a category name. For example, pharmacy communication is accurate and non-alarmist; dental language is collegial and clinical; restaurant language is operator-to-operator.
3. A true merchant or customer detail that changes the recommendation: owner name, locality, active offer, known cohort, preference, or relevant past interaction.
4. A visible “why now” sentence tied to the supplied event.
5. One minimal-friction next step, usually a binary ask. Booking flows may offer the verified available slots.
6. A concise rationale that names the grounded fact, intended outcome, and relevant guardrail.
7. Sound judgment, including a valuable recommendation not to act when the supplied data supports that conclusion. Judgment must be context-derived, not imagined.

The case-study cross-case guidance further says source citations are essential for research/compliance claims, identifies domain vocabulary as evidence of CategoryContext use, and wants facts traceable to provided inputs.

## Operational failures and penalties

| Failure | Result stated by challenge documents |
|---|---|
| 3 health check failures in succession | Disqualification for that test slot / remaining ticks skipped; -10 operational |
| Tick or reply exceeds 30 s | Skip / mark silent and -1 each |
| Malformed action or empty `send` body | Action score 0 and -2 each |
| Same body repeated in one conversation | -2 per repeat |
| URL in a message | API examples call it a hard failure and -3 per URL |
| Fabricated fact | Simulator rubric: -2; main rubric: severe score harm |
| Merchant-visible internal jargon | Simulator rubric: -1 |
| Case-study near duplicate | Similarity/plagiarism penalty |

The service also fails functionally if it does not acknowledge all 255 base context pushes, does not replace higher context versions, returns an invalid new `conversation_id`, ignores a relevant customer context, or returns more than 20 tick actions.

## Replay scenarios

The hosted top-ten replay test is five turns per scenario:

- **Auto-reply hell:** the same canned reply arrives four times. Detect the pattern, give at most one useful owner-facing bridge, then wait/end rather than continuing to sell.
- **Intent transition:** after qualification, “let’s do it” means switch immediately to a concrete execution/confirmation step. Do not ask another qualification question.
- **Hostile/off-topic:** end or give one short apology on a stop/hostile reply; politely decline out-of-scope requests such as GST filing and return to the mission only if the recipient remains engaged.

The supplied simulator's auto-reply routine uses a different conversation ID on each turn, so it cannot verify per-conversation repetition faithfully; the hosted requirement explicitly can. Future code must track both conversation-local repeat count and robust canned-auto-reply signals.

## How to use the case studies

Use them as a score-shape reference:

- Map trigger type to an appropriate value proposition and CTA shape.
- Learn the combination of grounded specificity, category voice, recipient fit, and concise action.
- Treat every example fact as illustration-only unless it is present in the current resolved context.
- Use them to construct test assertions such as “all research messages cite the selected source” or “all customer sends pass consent scope.”

Do **not** copy their text, sentence structure, or pricing/offer details. The official judge compares submissions against these cases and applies a similarity check. Several studies even call out hypothetical facts that must be verified in `MerchantContext`; that is an instruction to validate, not a license to reuse the claim.

## Judge and documentation discrepancies worth preserving

- The local simulator's provider calls use temperature 0.2 although the candidate bot must be deterministic; simulator configuration is not candidate guidance.
- The simulator's short scenario pushes only five seed merchants and no customers; passing it is not proof of full protocol compliance.
- Its `full_evaluation` also omits customer context pushes even when a trigger refers to a customer, so it is insufficient for customer-scope validation.
- URL policy, endpoint latency values, and artifact submission vs HTTP-service submission conflict across documents. Implement conservatively and seek clarification before assuming the permissive version.
