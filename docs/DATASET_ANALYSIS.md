# Phase 1: Dataset Analysis

## Generation result

The supplied generator was run with:

```powershell
python dataset/generate_dataset.py --seed-dir dataset --out dataset/expanded
```

The expanded dataset contains exactly:

| Artifact | Count |
|---|---:|
| Categories | 5 |
| Merchants | 50 |
| Customers | 200 |
| Triggers | 100 |
| Canonical test pairs | 30 |

The generator is deterministic (`SEED = 20260426`). It copies the five category files unchanged, retains the 10 merchant / 15 customer / 25 trigger seeds, and derives the remaining records. The output layout is `dataset/expanded/{categories,merchants,customers,triggers}` plus `test_pairs.json`.

## The five category contexts

Every category provides the same top-level fields: `slug`, `display_name`, `voice`, `offer_catalog`, `peer_stats`, `digest`, `patient_content_library`, `seasonal_beats`, `trend_signals`, `regulatory_authorities`, and `professional_journals`.

| Category | Voice / register | Code mix | Offer / digest / content | Key directional constraint |
|---|---|---|---:|---|
| Dentists | `peer_clinical` / respectful collegial | Natural Hindi-English | 8 / 5 / 3 | Clinical peer tone; no cure, guarantee, miracle, unsupported approval, or “best” claims |
| Salons | `warm_practical` / approachable expert | Natural Hindi-English | 8 / 5 / 3 | Warm practical beauty expertise; avoid permanent, instant, miracle, and “best” claims |
| Restaurants | `warm_busy_practical` / fellow operator | Natural Hindi-English | 8 / 5 / 2 | Operator language such as covers, AOV, turnover; no packed-house or viral guarantees |
| Gyms | `energetic_disciplined` / coach to member | English primary with some Hindi | 8 / 5 / 3 | Coaching language, no guaranteed rapid weight-loss or miracle transformation claims |
| Pharmacies | `trustworthy_precise` / neighbourhood pharmacist | Natural Hindi-English | 8 / 5 / 3 | Precise, conservative medical-retail framing; no cure, safety, recommendation, or price superlatives without support |

Each category supplies 4–5 seasonal beats and trend signals, category-scoped peer metrics, source-cited digest items, and an eight-item offer catalog. The catalog is a category recommendation source; it is not proof that a specific merchant has that offer. For a factual customer/merchant message, use only a merchant offer with an appropriate active status.

### Important category data

- Dentist: clinical vocabulary includes `fluoride varnish`, `scaling`, `caries`, `OPG`, and `RCT`; digest includes research, compliance, CDE, trend, and tech. It has an explicit high-risk-adult fluoride study and DCI radiograph change.
- Salon: vocabulary includes `balayage`, `keratin`, `smoothening`, `olaplex`, and brand names; digest covers products, formaldehyde-free alternatives, bridal season, training, and GBP walk-in labeling.
- Restaurant: vocabulary includes `footfall`, `covers`, `AOV`, and `table turnover`; digest has IPL seasonality (weekend home-watch trade-off), GST packaging, verification, complaint analysis, and sugar-free dessert demand.
- Gym: vocabulary includes `membership churn`, `PT sessions`, `HIIT`, `BMR`, and `VO2max`; digest includes seasonal acquisition lull, PT demand, yoga/pilates competition, creatine guidance, and capacity studies.
- Pharmacy: vocabulary includes `OTC`, schedules H/X, molecule, MRP, expiry, and batch; digest includes generic metformin, H1 compliance, seasonal demand, chronic-Rx subscriptions, and an atorvastatin alert.

## Merchant context

### Canonical merchant shape

All 50 merchant records contain the following stable fields:

```text
merchant_id, category_slug,
identity.{name, city, locality, place_id, verified, languages, owner_first_name, established_year},
subscription.{status, plan},
performance.{window_days, views, calls, directions, ctr, leads, delta_7d.{views_pct,calls_pct}},
offers, conversation_history, customer_aggregate, signals, review_themes
```

Optional or category/seed-specific fields include `subscription.days_remaining`, `days_since_expiry`, and `renewed_at`; `performance.delta_7d.ctr_pct`; detailed offer status/start dates; full conversation turn fields; review themes; and category-specific customer aggregates such as active members, chronic-Rx count, retention, churn, or delivery share.

### Scope and distributions

- Exactly 10 merchants belong to each category.
- Merchant cities span Ahmedabad (6), Bangalore (6), Chandigarh (7), Chennai (5), Delhi (4), Hyderabad (2), Jaipur (4), Lucknow (5), Mumbai (6), and Pune (5).
- All merchants list `en` and `hi`; regional language codes appear for Mumbai (`mr`, 7), Bangalore (`kn`, 6), Chennai (`ta`, 5), and Hyderabad (`te`, 2).
- Subscription status: 36 active, 9 expired, and 5 trial.

Merchant context is the source of truth for whether an offer is active, what performance fact can be used, whether a profile is verified, which conversations have already happened, and which merchant-level signals are known. Empty generated `offers`, `conversation_history`, `signals`, and `review_themes` are meaningful: the composer may not backfill claims from a category template.

## Customer context

### Canonical customer shape

```text
customer_id, merchant_id,
identity.{name, phone_redacted, language_pref, age_band, [senior_citizen]},
relationship.{first_visit, last_visit, visits_total, services_received, lifetime_value,
              [chronic_conditions], [favourite_dish]},
state,
preferences.{channel, reminder_opt_in, [preferred_slots], [preferred_stylist],
             [training_focus], [health_focus], [wedding_date], [delivery_address], ...},
consent.{opted_in_at, scope}
```

`state` covers `new`, `active`, `lapsed_soft`, `lapsed_hard`, and `churned`. The 200 records distribute as active 98, lapsed_soft 48, new 19, lapsed_hard 19, and churned 16.

### Language, consent, and relationship information

- Customer language preferences: `en` 78, `hi` 52, `hi-en mix` 61, `english` 5, plus Tamil-, Telugu-, and Kannada-English mix variants.
- `preferences.reminder_opt_in` is true for 168 and false for 32 customers.
- Consent is timestamped and purpose-scoped. `promotional_offers` appears on 190 records; smaller numbers use recall, appointment, refill, winback, treatment-followup, delivery, bridal, program, seasonal-health, stylist, or lunch/match updates scopes.
- A customer message must not infer that an opt-in to `promotional_offers` also permits recall, clinical, refill, or appointment outreach. Future policy must map each trigger kind to required consent scopes before any customer send.

Customer identity contains redacted phone values only. Relationship and preference data is still sensitive within the challenge boundary and must not be sent to non-LLM external APIs or retained after test teardown.

## Trigger context

Every trigger has the stable shape:

```text
id, scope, kind, source, merchant_id, customer_id,
payload, urgency, suppression_key, expires_at
```

The payload is intentionally kind-specific. It can contain a digest ID, time/date/slot, performance delta, event details, category relevance, manufacturer/batch data, competitor data, intent topic, or a generic generated placeholder. The trigger is the reason-to-send source; it must not be rewritten into made-up facts.

### Scope and source split

| Trigger property | Count |
|---|---:|
| Merchant scope | 70 |
| Customer scope | 30 |
| Internal source | 77 |
| External source | 23 |

For customer scope, `customer_id` references a customer belonging to the same `merchant_id`. The future resolver must verify this relationship, not trust a body value in isolation.

### Trigger kinds and counts

| Kind family | Exact kind counts |
|---|---|
| Merchant performance/engagement | `perf_dip` 6, `perf_spike` 6, `milestone_reached` 6, `dormant_with_vera` 6, `curious_ask_due` 6, `renewal_due` 6, `review_theme_emerged` 6, `active_planning_intent` 2 |
| Merchant external/contextual | `research_digest` 6, `competitor_opened` 6, `festival_upcoming` 6, plus one each `category_seasonal`, `cde_opportunity`, `gbp_unverified`, `ipl_match_today`, `regulation_change`, `seasonal_perf_dip`, `supply_alert`, `winback_eligible` |
| Customer lifecycle | `appointment_tomorrow` 5, `chronic_refill_due` 6, `customer_lapsed_hard` 1, `customer_lapsed_soft` 5, `recall_due` 6, `trial_followup` 6, `wedding_package_followup` 1 |

The generator adds five records for each listed additional kind, but its `payload` for generated records is only `{"placeholder": true, "metric_or_topic": kind}`. Those records provide a valid event shape but not enough evidence for an asserted metric, offer, date, slot, or recommendation. The decision layer should either use only facts demonstrably available in resolved contexts or return no action.

### Suppression keys

Every trigger provides a suppression key. Its intended semantics are trigger-level deduplication, not a display field. Store it with recipient and status, suppress a successfully initiated action, and separately preserve durable opt-out/hostile suppression. Do not substitute a newly invented key in the outbound action.

## Canonical test pairs

`test_pairs.json` has the shape:

```json
{
  "pairs": [
    {
      "test_id": "T01",
      "trigger_id": "trg_...",
      "merchant_id": "m_...",
      "customer_id": null
    }
  ]
}
```

It contains 30 pairs. The generator groups all triggers by `kind`, iterates kinds in lexical order, takes the first two triggers per kind, then stops at 30. Although a random instance is passed to `write_test_pairs`, it is not used. This means the test-pair selection is stable, but it reaches only the first 15 lexical trigger kinds: the file does not represent all 26 kinds.

The selected pairs contain 21 merchant-scoped and 9 customer-scoped scenarios. The first selection includes active planning, appointment, category seasonal, CDE, refill, competitor, curiosity, lapse, dormancy, festival, GBP verification, IPL, milestone, performance dip/spike, recall, and regulation. It does not include the later lexical kinds such as `research_digest`, `review_theme_emerged`, `seasonal_perf_dip`, `supply_alert`, `trial_followup`, wedding follow-up, or winback. The live judge may inject new scenarios, so a future design must cover the complete trigger set rather than overfit to the 30 pairs.

## Data-quality and implementation implications

1. Use null/empty/missing fields as absence, not permission to infer values.
2. Merchant offers and customer consent are the decisive truth sources for outbound claims and eligibility.
3. Category digests and peer stats are rich groundable material, but only use the item explicitly selected by the trigger or a deterministic relevance rule with cited provenance.
4. The five categories have distinctive language rules and taboos; a uniform marketing template will violate the dataset.
5. Generated records deliberately cover broad structural cases but often have sparse details. A high-quality system must be comfortable abstaining.
