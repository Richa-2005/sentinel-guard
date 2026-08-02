# Model Card: Sentinel Guard Fraud Ensemble

Sentinel Guard uses a two-model fraud-risk ensemble to score synthetic payment
transactions, explain the decision with per-model SHAP evidence, and route
blocked transactions into human review and audit reporting.

> This model is built for portfolio demonstration and educational review. It is
> not approved for real payment authorization, customer risk scoring,
> regulatory filing, or legal decision-making.

## Snapshot

| Item | Value |
| --- | --- |
| Task | Binary fraud-risk classification |
| Model family | XGBoost + LightGBM soft-voting ensemble |
| Ensemble weighting | 50% XGBoost probability + 50% LightGBM probability |
| Feature count | 6 |
| Decision threshold | `0.9574951827526093` |
| Threshold objective | Maximize F2 on the frozen test split |
| Training rows | 50,000 synthetic transactions |
| Synthetic fraud rate | 0.2% |
| Frozen test rows | 10,000 chronological holdout rows |
| Frozen test positives | 14 |
| Report generation layer | LangGraph + Groq, downstream from scoring |

## Intended Use

The ensemble is intended to demonstrate:

- chronological fraud-feature engineering
- cost-sensitive learning on an imbalanced synthetic dataset
- calibrated thresholding for high-recall intervention
- per-model explainability with SHAP
- operational handoff from automated block to human review
- post-decision monitoring through prediction and review metrics

The model is suitable only for controlled demonstrations using synthetic data.

## Not Intended For

The model must not be used for:

- real payment authorization or decline decisions
- customer, merchant, or device risk scoring in production
- regulatory submissions or legal conclusions
- fraud claims without independent human investigation
- benchmarking real-world fraud performance

## Inference Contract

The backend loads these committed runtime artifacts from `backend/data/`:

| Artifact | Purpose |
| --- | --- |
| `xgb_compliance_gate.json` | Frozen XGBoost classifier |
| `lgb_compliance_gate.txt` | Frozen LightGBM classifier |
| `model_config.json` | Calibrated threshold and feature order |
| `artifacts.sha256` | Integrity checksums for model and knowledge assets |

At runtime, the backend:

1. Hydrates stateful transaction features from the SQLite ledger.
2. Scores the ordered feature vector with both tree models.
3. Averages both fraud probabilities into one ensemble score.
4. Blocks the transaction when the ensemble score meets or exceeds the saved
   threshold.
5. Stores the raw score, hydrated metrics, and SHAP payload.
6. Creates a review case and audit job for blocked transactions.

## Feature Schema

The inference order is fixed in `model_config.json`.

| Feature | Meaning |
| --- | --- |
| `amount_paise` | Transaction amount in paise |
| `card_vel_10m` | Number of recent transactions for the card in the previous 10 minutes |
| `device_card_ratio_30m` | Distinct-card activity observed for the device over the previous 30 minutes |
| `device_card_limit_crossed` | Binary indicator that the device exceeded the distinct-card limit |
| `is_known_merchant` | Whether this card has previously transacted with the merchant |
| `is_off_hours_window` | Whether the transaction occurred during the configured off-hours window |

These features intentionally model a narrow card-testing and velocity-risk
scenario. They do not represent the full context available to a real payment
network.

## Training Data

The training pipeline uses a reproducible synthetic transaction ledger generated
by `app/core/generator.py`.

| Property | Value |
| --- | --- |
| Total rows | 50,000 |
| Fraud ratio | 0.2% |
| Random seed | `42` |
| Split strategy | Chronological 80/20 split |
| Frozen test size | 10,000 rows |

The synthetic generator creates normal card behavior, merchant history, device
reuse, purchase-time distributions, and adversarial card-testing bursts. The
generated `transactions.csv` is intentionally not committed.

## Training Procedure

The training code lives in `app/core/trainer.py` and
`app/core/ensemble.py`.

- Features are computed through a chronological pipeline to avoid lookahead
  leakage.
- XGBoost and LightGBM are tuned with forward-chaining time-series validation.
- PR-AUC is used during tuning because the positive class is highly sparse.
- `scale_pos_weight` is computed from the synthetic class imbalance.
- The final ensemble threshold is selected by sweeping test-set probabilities
  and maximizing F2, which weights recall more heavily than precision.

## Frozen Test Results

Results below were recalculated from the committed model artifacts without
retraining.

| Metric | Result |
| --- | ---: |
| Average precision / PR-AUC summary | 0.7936 |
| Precision | 0.6000 |
| Recall | 0.8571 |
| F2 score | 0.7895 |
| True negatives | 9,978 |
| False positives | 8 |
| False negatives | 2 |
| True positives | 12 |

### Interpretation

The frozen test partition contains only 14 positive examples, so each positive
case has a large effect on recall and F-score. At the calibrated threshold, the
ensemble catches 12 of those 14 synthetic fraud examples and misses 2. It also
blocks 8 normal synthetic transactions, which would require human review in the
application workflow.

These numbers should be read as evidence that the demonstration pipeline is
coherent, not as evidence of real-world fraud accuracy.

## Explainability

The backend uses SHAP TreeExplainer for both models.

Raw SHAP values are retained separately for XGBoost and LightGBM because values
from different tree implementations may not share the same scale. The API also
returns signed relative contribution maps normalized independently within each
model. The UI uses those normalized maps to show which features supported or
reduced the block decision.

The application does not average SHAP values across models.

## Compliance Memo Generation

Compliance memoranda are downstream operational artifacts, not classifier
outputs.

For blocked transactions, Sentinel Guard creates a durable audit job. The
LangGraph pipeline then:

1. Converts model-specific SHAP evidence into plain-language forensic findings.
2. Retrieves relevant synthetic internal guidance from local knowledge files.
3. Calls Groq with `llama-3.1-8b-instant` to draft a structured memorandum.
4. Normalizes the memo format.
5. Appends the report to the SHA-256 audit chain.

The knowledge-base files are synthetic demonstration fixtures. They are not
official RBI, Visa, network, or legal documents.

## Runtime Monitoring

The admin monitoring surface derives operational metrics from predictions and
human outcomes:

- total predictions, blocked count, and blocked rate
- average, minimum, and maximum risk score
- risk-score distribution buckets
- Population Stability Index across adjacent time windows
- review case coverage for blocked transactions
- administrator decision completion rate
- false-positive and confirmed-fraud rates from final decisions
- average and P95 review-resolution latency

These metrics help detect behavior changes after deployment, but they do not
replace formal model validation.

## Limitations

- The dataset is synthetic and only approximates a narrow fraud pattern.
- The test set has very few positive examples, making fraud metrics unstable.
- The feature space omits many signals used in real payment fraud systems.
- There is no fairness, demographic, merchant-segment, or geography analysis.
- The threshold is optimized on synthetic holdout data, not real operations.
- SHAP explanations describe model behavior, not causal proof of fraud.
- Groq-generated memoranda can contain language errors and require human review.
- SQLite-backed job dispatch is designed for a single backend worker.

## Integrity Verification

From the `backend` directory, verify committed runtime artifacts with:

```bash
shasum -a 256 -c data/artifacts.sha256
```

Expected result:

```text
data/xgb_compliance_gate.json: OK
data/lgb_compliance_gate.txt: OK
data/model_config.json: OK
data/mcc_codes.csv: OK
data/corporate_policy.txt: OK
data/network_tos.txt: OK
data/rbi_circular.txt: OK
```
