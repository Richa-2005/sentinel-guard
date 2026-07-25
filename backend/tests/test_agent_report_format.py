"""Unit coverage for generated compliance-report normalization."""

import unittest

from app.core.agent import normalize_generated_report


class GeneratedReportFormatTests(unittest.TestCase):
    def test_removes_conversational_preamble_and_normalizes_headings(self) -> None:
        report = """
Here is the mandatory compliance report in the required format:

NEXUS FINTECH COMPLIANCE INCIDENT REPORT [ALERT-GATEWAY-REJECTION]

A. EXECUTIVE RISK VERDICT
The transaction crossed the deployed decision boundary.

B. TECHNICAL SPECIFICATION PROFILE
- Transaction ID: tx-1

C. REGULATORY COMPLIANCE CROSS-REFERENCE
- Internal synthetic guidance requires review.

D. MITIGATION & ACTIONABLE DEFENCE ROADMAP
1. Retain the decision evidence.
"""

        normalized = normalize_generated_report(report)

        self.assertTrue(normalized.startswith("## A. Executive Risk Verdict"))
        self.assertNotIn("Here is the mandatory", normalized)
        self.assertNotIn("NEXUS FINTECH", normalized)
        self.assertIn("## B. Technical Specification Profile", normalized)
        self.assertIn("## D. Mitigation and Actionable Defense Roadmap", normalized)


if __name__ == "__main__":
    unittest.main()
