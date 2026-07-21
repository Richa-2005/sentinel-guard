# Sentinel Guard Fraud Ensemble — Model Card

## Intended use

This model is a portfolio and educational fraud-risk classifier for evaluating
synthetic payment transactions. It demonstrates chronological feature
engineering, imbalanced classification, ensemble inference, explainability,
and threshold calibration. It is not approved for real financial decisions.

## Versioned inference artifacts

- `xgb_compliance_gate.json` — XGBoost classifier
- `lgb_compliance_gate.txt` — LightGBM classifier
- `model_config.json` — calibrated threshold and ordered feature schema
- `artifacts.sha256` — integrity checksums for models and knowledge assets

The text knowledge-base assets are synthetic demonstration fixtures. They are
versioned for reproducible application behavior and are not official RBI, Visa,
or legal documents.

The ensemble score is the equal-weight average of the two model probabilities.
The saved decision threshold is `0.9574951827526093`.

## Features

The inference order is fixed and recorded in `model_config.json`:

1. `amount_paise`
2. `card_vel_10m`
3. `device_card_ratio_30m`
4. `device_card_limit_crossed`
5. `is_known_merchant`
6. `is_off_hours_window`

## Training and evaluation data

The training pipeline uses a generated 50,000-row transaction ledger with a
0.2% fraud rate. Data is sorted chronologically and split 80/20, leaving 10,000
rows in the frozen test partition. The test partition contains 14 positive
examples. The generated `transactions.csv` is intentionally not versioned; the
generator and training pipeline remain in the repository.

## Frozen test results

Results below were recalculated from the committed model artifacts without
retraining:

| Metric | Result |
| --- | ---: |
| Average precision (PR-AUC summary) | 0.7936 |
| Precision | 0.6000 |
| Recall | 0.8571 |
| F2 score | 0.7895 |
| True negatives | 9,978 |
| False positives | 8 |
| False negatives | 2 |
| True positives | 12 |

## Explainability

Raw SHAP values are retained separately for XGBoost and LightGBM. Because raw
values from different tree implementations can use incompatible scales, they
are not averaged. The API also supplies signed relative contributions normalized
independently within each model for UI comparison.

## Limitations

- Metrics come from synthetic data and do not establish real-world accuracy.
- The small number of positive test examples makes fraud-class metrics
  sensitive to individual predictions.
- The feature set does not represent the full context available to a production
  payment network.
- Drift, fairness, calibration, and adversarial robustness require further
  evaluation before any real deployment.
- Generated compliance memos are operational aids, not legal advice.

## Integrity verification

From the `backend` directory, verify all committed runtime artifacts with:

```bash
shasum -a 256 -c data/artifacts.sha256
```
