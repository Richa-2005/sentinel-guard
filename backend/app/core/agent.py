"""
Using LLM to convert the SHAP output into a understandable audit 
trail
"""

import json
import requests

try:
    from .explainer import TransactionExplainer
    from .trainer import FraudModelTrainer
except ImportError:
    from explainer import TransactionExplainer
    from trainer import FraudModelTrainer


class ComplianceAgent:
    def __init__(self, ollama_url: str = "http://localhost:11434/api/generate"):
        self.ollama_url = ollama_url
        self.model_name = "llama3.1"

    def compile_audit_prompt(self, transaction_data: dict, shap_payload: dict) -> str:
        """
        Structures a pristine system context wrapper grounding the model in data.
        """
        
        prompt = f"""
        You are an Expert FinTech Risk Compliance Auditor at an international payment gateway.
        Your task is to translate raw statistical machine learning model logs into a professional, human-readable compliance audit trail.

        GROUND-TRUTH TRANSACTION DATA:
        {json.dumps(transaction_data, indent=2)}

        SHAP MATHEMATICAL FEATURE IMPACT ANALYTICS LOG:
        {json.dumps(shap_payload, indent=2)}

        INSTRUCTIONS:
        1. Write a 3-sentence diagnostic summary detailing exactly why the transaction was blocked or flagged.
        2. Specifically interpret what the highest positive SHAP impact means in terms of user behavior.
        3. Keep your tone objective, professional, and compliant. Do not hallucinate or assume values outside the data provided above.
        """
        return prompt
    
    def generate_audit_trail(self, prompt: str) -> str:
        payload = { 
            "model" : self.model_name,
            "prompt" : prompt,
            "stream" : False
        }

        response = requests.post(self.ollama_url, json=payload)
        
        if response.status_code == 200:
            # Extract the response map and isolate the generated string output
            response_json = response.json()
            audit_trail_text = response_json.get("response", "⚠️ Error: Text token key not found.")
            return audit_trail_text
        else:
            raise requests.exceptions.HTTPError(f"Local server returned status code: {response.status_code}")

if __name__ == '__main__':
    explainer = TransactionExplainer("data/xgb_compliance_gate.json", "data/lgb_compliance_gate.txt")
    trainer = FraudModelTrainer("data/transactions.csv")
    _ = trainer.prepare_datasets()

    sample_row = trainer.X_test[trainer.y_test == 1].head(1)
    
    if not sample_row.empty:
        
        raw_tx_dict = sample_row.to_dict(orient="records")[0]
        shap_json_str = explainer.generate_explanation(sample_row)
        shap_payload = json.loads(shap_json_str)

        agent = ComplianceAgent()
        full_prompt = agent.compile_audit_prompt(raw_tx_dict, shap_payload)
        
        audit_report = agent.generate_audit_trail(full_prompt)
        
        print("\n Sentinel Guard: LLM Generated Compliance Audit Trail")
        print(audit_report)
