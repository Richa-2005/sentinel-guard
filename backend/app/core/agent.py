"""
Using LLM to convert the SHAP output into a understandable audit 
trail
"""

import json
import requests
from typing import TypedDict, Dict, Any
from langgraph.graph import StateGraph, END,START

from app.core.knowledge import KnowledgeBaseManager

kb_manager = KnowledgeBaseManager()

class ComplianceGraphState(TypedDict):
    raw_transaction: Dict[str, Any]
    hydrated_metrics: Dict[str, Any]
    shap_payload: Dict[str, Any]
    forensic_analysis_text: str
    regulatory_context_text: str
    final_audit_report_text: str

def textForensics(state : ComplianceGraphState) -> ComplianceGraphState:
    """
    Receives the raw blocked data payload and converts mathematical SHAP importance 
    vectors into plain text statements identifying exactly why the tree rules 
    triggered the block.
    """

    shap_data = state.get("shap_payload", {})
    
    xgb_impacts = shap_data.get("xgb_feature_impacts", {})
    lgb_impacts = shap_data.get("lgb_feature_impacts", {})
    ensemble_impacts = shap_data.get("ensemble_feature_impacts", {})
    
    findings = []

    findings.append("PRIMARY ENSEMBLE SYSTEM IMPACTS:")
    for feature_name, val_weight in ensemble_impacts.items():
        weight_float = float(val_weight)
        if weight_float > 0.01:
            findings.append(f" - Blended Feature [{feature_name}]: POSITIVE risk push of +{round(weight_float, 4)}.")
        elif weight_float < -0.01:
            findings.append(f" - Blended Feature [{feature_name}]: NEGATIVE safety anchor of {round(weight_float, 4)}.")

  
    findings.append("\nTREE ARCHITECTURE CONSENSUS DEEP DIVE")
    for feature_name in ensemble_impacts.keys():
        x_w = float(xgb_impacts.get(feature_name, 0.0))
        l_w = float(lgb_impacts.get(feature_name, 0.0))
        
        # Check if one tree model completely contradicts the other model's structural split direction
        if (x_w > 0.05 and l_w < -0.05) or (x_w < -0.05 and l_w > 0.05):
            findings.append(
                f" ARCHITECTURAL DIVERGENCE ALERT on Feature '{feature_name}':\n"
                f"   -> XGBoost processed a split impact weight of: {round(x_w, 4)}\n"
                f"   -> LightGBM processed a split impact weight of: {round(l_w, 4)}\n"
                f"   * Result: The ensemble gate stabilized this divergence via mathematical averaging."
            )
        else:
            findings.append(
                f" - Feature '{feature_name}' Node Consensus: [XGB Weight: {round(x_w, 4)} | LGB Weight: {round(l_w, 4)}]"
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
    
    ---
    MANDATORY REPORT FORMAT DIRECTIVE:
    Your output MUST follow this strict structural layout down to the characters:
   
    NEXUS FINTECH COMPLIANCE INCIDENT REPORT [ALERT-GATEWAY-REJECTION]
   
    A. EXECUTIVE RISK VERDICT: [State clear reason for block matching forensic weights]
    B. TECHNICAL SPECIFICATION PROFILE: [Detail active transaction features and amounts]
    C. REGULATORY COMPLIANCE CROSS-REFERENCE: [Quote exact matching clauses or sections from the texts]
    D. MITIGATION & ACTIONABLE DEFENSE ROADMAP: [Provide operational steps for account tracking]

    """
    
    ollama_url = "http://localhost:11434/api/generate"
    payload = { 
        "model": "llama3.1",
        "prompt": llm_prompt,
        "stream": False
    }

    try:
        response = requests.post(
            ollama_url,
            json=payload,
            timeout=60.0,
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
    def __init__(self, ollama_url: str = "http://localhost:11434/api/generate"):
        self.ollama_url = ollama_url
        self.model_name = "llama3.1"

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
        }
        
        # Execute the compiled LangGraph App engine thread wrapper
        final_state = CompilanceApp.invoke(initial_state)
        
        # Extract the completed compliance memo
        return final_state.get("final_audit_report_text", "Error executing state DAG.")
