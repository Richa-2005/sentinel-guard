"""Unit coverage for deterministic demo-only behavioral context."""

import unittest

import lightgbm as lgb
import pandas as pd
from xgboost import XGBClassifier

from app.config import settings
from app.core.config import SystemRiskConfig
from app.services.risk_service import apply_demo_scenario_context


class DemoScenarioContextTests(unittest.TestCase):
    def test_fraud_burst_uses_pre_hydrated_attack_context(self) -> None:
        context = apply_demo_scenario_context(
            "fraud_burst",
            card_velocity=0,
            device_card_ratio=0.0,
            device_card_limit=0.0,
            known_merchant=1.0,
        )
        self.assertEqual(context, (4, 2.0, 0.0, 0.0))

    def test_regular_evaluation_context_is_unchanged(self) -> None:
        context = apply_demo_scenario_context(
            None,
            card_velocity=2,
            device_card_ratio=1.0,
            device_card_limit=0.0,
            known_merchant=1.0,
        )
        self.assertEqual(context, (2, 1.0, 0.0, 1.0))

    def test_fraud_burst_context_crosses_the_deployed_model_boundary(self) -> None:
        card_velocity, device_ratio, device_limit, known_merchant = (
            apply_demo_scenario_context(
                "fraud_burst",
                card_velocity=0,
                device_card_ratio=0.0,
                device_card_limit=0.0,
                known_merchant=1.0,
            )
        )
        frame = pd.DataFrame([{
            "amount_paise": 12380,
            "card_vel_10m": card_velocity,
            "device_card_ratio_30m": device_ratio,
            "device_card_limit_crossed": device_limit,
            "is_known_merchant": known_merchant,
            "is_off_hours_window": 0.0,
        }])
        xgboost_model = XGBClassifier()
        xgboost_model.load_model(settings.DATA_DIR / "xgb_compliance_gate.json")
        lightgbm_model = lgb.Booster(
            model_file=str(settings.DATA_DIR / "lgb_compliance_gate.txt")
        )
        score = (
            float(xgboost_model.predict_proba(frame)[:, 1][0])
            + float(lightgbm_model.predict(frame)[0])
        ) / 2

        self.assertGreaterEqual(score, SystemRiskConfig.CALIBRATED_THRESHOLD)


if __name__ == "__main__":
    unittest.main()
