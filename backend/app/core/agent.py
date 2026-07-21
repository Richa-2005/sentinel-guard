"""
Using LLM to convert the SHAP output into a understandable audit 
trail
"""

import json
import requests
from typing import TypedDict, Dict, Any
from langgraph.graph import StateGraph, END,START

from app.config import settings
from app.core.knowledge import KnowledgeBaseManager

kb_manager = KnowledgeBaseManager()


def normalize_impact_map(impacts: Dict[str, Any]) -> Dict[str, float]:
    """Normalize legacy raw SHAP maps for pending jobs stored before this change."""
    numeric_impacts = {
        feature_name: float(value)
        for feature_name, value in impacts.items()
    }
    total_magnitude = sum(abs(value) for value in numeric_impacts.values())

    if total_magnitude <= 1e-12:
        return {feature_name: 0.0 for feature_name in numeric_impacts}

    return {
        feature_name: value / total_magnitude
        for feature_name, value in numeric_impacts.items()
    }


class ComplianceGraphState(TypedDict):
    raw_transaction: Dict[str, Any]
    hydrated_metrics: Dict[str, Any]
    shap_payload: Dict[str, Any]
    forensic_analysis_text: str
    regulatory_context_text: str
    final_audit_report_text: str
    ollama_base_url: str
    ollama_model: str
    ollama_timeout_seconds: float

def textForensics(state : ComplianceGraphState) -> ComplianceGraphState:
    """
    Receives the raw blocked data payload and converts mathematical SHAP importance 
    vectors into plain text statements identifying exactly why the tree rules 
    triggered the block.
    """

    shap_data = state.get("shap_payload", {})
    
    xgb_impacts = shap_data.get("xgb_normalized_impacts") or (
        normalize_impact_map(shap_data.get("xgb_feature_impacts", {}))
    )
    lgb_impacts = shap_data.get("lgb_normalized_impacts") or (
        normalize_impact_map(shap_data.get("lgb_feature_impacts", {}))
    )
    feature_names = list(dict.fromkeys([*xgb_impacts, *lgb_impacts]))
    
    findings = []

    findings.append(
        "MODEL-SPECIFIC RELATIVE SHAP EVIDENCE "
        "(normalized independently within each model):"
    )

    for feature_name in feature_names:
        x_w = float(xgb_impacts.get(feature_name, 0.0))
        l_w = float(lgb_impacts.get(feature_name, 0.0))

        if (
            abs(x_w) >= 0.01
            and abs(l_w) >= 0.01
            and (x_w > 0) != (l_w > 0)
        ):
            findings.append(
                f" ARCHITECTURAL DIVERGENCE ALERT on Feature '{feature_name}':\n"
                f"   -> XGBoost relative contribution: {x_w:+.2%}\n"
                f"   -> LightGBM relative contribution: {l_w:+.2%}\n"
                "   * Result: The models disagree on direction; raw SHAP "
                "magnitudes are not averaged."
            )
        else:
            findings.append(
                f" - Feature '{feature_name}': "
                f"[XGB relative share: {x_w:+.2%} | "
                f"LGB relative share: {l_w:+.2%}]"
            )

    forensic_summary = "\n".join(findings)
    state["forensic_analysis_text"] = forensic_summary
    
    return state
        
    
def crossRefRAG(state : ComplianceGraphState) -> ComplianceGraphState:
    """
    Invokes KnowledgeBaseManager class. It passes the transaction 
    attributes along with the metrics and injects only the hyper-relevant 
    regulatory rules fetched from disk.
    """

    raw_ts = state.get("raw_transaction",{})
    hyd_matrix = state.get("hydrated_metrics",{})

    extracted_regulatory_corpus = kb_manager.query_relevant_context(
        raw_ts,
        hyd_matrix
    )
    
    state["regulatory_context_text"] = extracted_regulatory_corpus
    return state

def legalVerdict(state : ComplianceGraphState) -> ComplianceGraphState:
    """
    Combines the forensic features and the fetched regulatory context, prompting 
    local LLM node to output an official, structured legal compliance audit report.
    """
    raw_tx = state.get("raw_transaction", {})
    forensics = state.get("forensic_analysis_text", "")
    reg_context = state.get("regulatory_context_text", "")
    ollama_base_url = state["ollama_base_url"]
    ollama_model = state["ollama_model"]
    ollama_timeout_seconds = state["ollama_timeout_seconds"]

    llm_prompt = f"""
    [COMPLIANCE ROLE SYSTEM MANDATE: TIER-1 RISK EXECUTIVE AUDIT GENERATOR]
    
    You are an automated risk core auditing agent processing a high-alert network breach block.
    Analyze the transaction telemetry details and build an official, authoritative compliance report.
    
    --- 
    1. INBOUND TRANSACTION METRICS:
    {json.dumps(raw_tx, indent=2)}
    
    ---
    2. FORENSIC TREE CONSENSUS ANALYSIS:
    {forensics}
    
    ---
    3. RELEVANT REGULATORY RULES CORE REF:
    {reg_context}

    The supplied reference corpus contains synthetic demonstration material.
    Treat it as an internal portfolio fixture, not official legal guidance.
    
    ---
    MANDATORY REPORT FORMAT DIRECTIVE:
    Your output MUST follow this strict structural layout down to the characters:
   
    NEXUS FINTECH COMPLIANCE INCIDENT REPORT [ALERT-GATEWAY-REJECTION]
   
    A. EXECUTIVE RISK VERDICT: [State clear reason for block matching forensic weights]
    B. TECHNICAL SPECIFICATION PROFILE: [Detail active transaction features and amounts]
    C. REGULATORY COMPLIANCE CROSS-REFERENCE: [Reference matching sections from the supplied synthetic corpus]
    D. MITIGATION & ACTIONABLE DEFENSE ROADMAP: [Provide operational steps for account tracking]

    """
    
    payload = { 
        "model": ollama_model,
        "prompt": llm_prompt,
        "stream": False
    }

    try:
        response = requests.post(
            ollama_base_url,
            json=payload,
            timeout=ollama_timeout_seconds,
        )
        response.raise_for_status()

        compiled_report = response.json().get("response")
        if not compiled_report:
            raise RuntimeError("LLM returned an empty compliance memo")

    except requests.RequestException as error:
        raise RuntimeError(
            f"Compliance memo generation failed: {error}"
        ) from error
    
    state["final_audit_report_text"] = compiled_report

    return state


graph = StateGraph(ComplianceGraphState)
graph.add_node("textForensics",textForensics)
graph.add_node("crossRefRAG",crossRefRAG)
graph.add_node("legalVerdict",legalVerdict)

graph.add_edge(START,"textForensics")
graph.add_edge("textForensics","crossRefRAG")
graph.add_edge("crossRefRAG","legalVerdict")
graph.add_edge("legalVerdict",END)

CompilanceApp = graph.compile()


class ComplianceAgent:
    def __init__(
        self,
        ollama_base_url: str | None = None,
        model_name: str | None = None,
        timeout_seconds: float | None = None,
    ):
        self.ollama_base_url = ollama_base_url or settings.OLLAMA_BASE_URL
        self.model_name = model_name or settings.OLLAMA_MODEL
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.OLLAMA_TIMEOUT_SECONDS
        )

    def run_graph_audit(self, transaction_data: dict, hydrated_metrics: dict, shap_payload: dict) -> str:
        """
        Public entrypoint interface executing our compiled multi-node LangGraph DAG.
        Returns the generated compliance audit memo.
        """
        # Initialize the state schema matching our TypedDict format requirement
        initial_state: ComplianceGraphState = {
            "raw_transaction": transaction_data,
            "hydrated_metrics": hydrated_metrics,
            "shap_payload": shap_payload,
            "forensic_analysis_text": "",
            "regulatory_context_text": "",
            "final_audit_report_text": "",
            "ollama_base_url": self.ollama_base_url,
            "ollama_model": self.model_name,
            "ollama_timeout_seconds": self.timeout_seconds,
        }
        
        # Execute the compiled LangGraph App engine thread wrapper
        final_state = CompilanceApp.invoke(initial_state)
        
        # Extract the completed compliance memo
        return final_state.get("final_audit_report_text", "Error executing state DAG.")
