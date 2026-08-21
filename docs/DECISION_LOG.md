# Phase 1: Decision Log

| ID | Decision / observation | Rationale and consequence | Status |
|---|---|---|---|
| D-001 | Keep all official challenge files unchanged. | The task and repository rules explicitly prohibit edits to briefs, examples, generator, simulator, seeds, and category source data. Analysis lives in `docs/`; generated data is produced only by the supplied command. | Adopted |
| D-002 | Run the generator into `dataset/expanded`. | This is the generator's advertised output location and enables inspection without altering seed inputs. | Adopted |
| D-003 | Treat the task as a stateful proactive service design, not a `compose`-only script. | The testing brief, API examples, and simulator exercise five endpoints, incremental updates, ticks, and conversation replies. | Adopted |
| D-004 | Use the most conservative compatible operational constraints. | The documents conflict on latency and URLs. Target 2/5/10-second endpoint budgets and prohibit URLs until clarified; both choices avoid the stricter documented failure path. | Adopted pending clarification |
| D-005 | Use a deterministic “what before how” boundary. | Consent, context resolution, trigger eligibility, suppression, rank, strategy, factual provenance, and schema validation are business/safety controls. The LLM may phrase only a pre-approved plan. | Adopted |
| D-006 | Include a deterministic renderer and abstention path. | Generated triggers can have only placeholder payloads, and LLM/network failures must not cause a late or fabricated message. | Adopted |
| D-007 | Treat merchant `offers` as factual source of truth; category catalog is recommendation material only. | The catalog is vertical-level, while factual price/offer availability varies per merchant. | Adopted |
| D-008 | Gate customer messages by explicit scope-level consent, customer/merchant ownership, and opt-out state. | Reminder opt-in and consent scope vary; a broad promotional scope does not establish permission for clinical recall/refill or appointment communication. | Adopted |
| D-009 | Do not overfit to `test_pairs.json` or the local simulator. | Pairs cover only the first 15 lexical trigger kinds. The simulator loads seeds only and has incomplete customer/replay fidelity; the hosted judge injects new context. | Adopted |
| D-010 | Preserve provenance and policy reasons in state/audit events. | The judge reads rationales and evaluates adaptive updates. Claim paths, versions, chosen strategy, validation result, and fallback reason support replay and defensible composition. | Adopted |
| D-011 | Implement Phase 2 as a standard-library deterministic domain package with no endpoint, network, LLM, or body-generation code. | The approved scope is the internal engine only. Dataclasses and enums give typed, dependency-free, deterministic decision inputs and outputs. | Adopted |
| D-012 | Make placeholder evidence a hard no-action gate before opportunity ranking. | The generator's synthetic `payload.placeholder=true` records identify a trigger kind but do not supply the facts needed to make a claim. A kind must never be converted into an asserted metric, date, offer, or recommendation. | Adopted |
| D-013 | Use exact, fail-closed consent-scope mappings for customer trigger kinds. | The source materials do not define a universal semantic mapping. Only explicitly named matching scopes are accepted; unknown customer kinds and generic promotional consent do not authorize a send. | Adopted pending clarification |

## Open questions requiring challenge-owner resolution

1. **Submission shape:** Is the expected deliverable a module plus `submission.jsonl`, a deployed five-endpoint service, or both? The main brief and testing brief specify different primary integration modes.
2. **URLs:** The main brief permits URLs when valuable; API examples call any body URL a hard failure (-3). Which rule governs the hosted judge?
3. **Timeouts:** Which values are enforced: the 30-second hard timeout, the API-examples 2/5/10-second budget, or simulator client timeouts of 5/10/15/15 seconds? Design assumes the strictest values, but official confirmation is needed.
4. **Template requirement:** What exact field or behavior proves a first outbound uses an approved WhatsApp template? The action schema has `template_name` and `template_params`, but no session-window context field or approved template registry is supplied.
5. **Consent mapping:** Which trigger kinds map to which consent scopes, and does `preferences.reminder_opt_in` supplement or override explicit `consent.scope`? The dataset exposes both but provides no normative mapping.
6. **Consent/registration ambiguity:** The testing brief calls `/v1/teardown` optional but privacy rules say state must be erased on receipt. What response shape, status, and deadline are expected?
7. **Scoring aggregation:** How are base scores, the stated “+5 per dimension” adaptive bonus, and the top-ten replay bonus combined or normalized?
8. **Sparse generated triggers:** Should a bot abstain for placeholder payloads, or is there an intended category-level fallback message family? The safe interpretation is abstention unless another supplied field grounds the claim.
9. **Case-study data:** Some examples explicitly rely on facts that may not be in a merchant's supplied context. Confirm that examples are pedagogical only and never expected to be reproduced.
