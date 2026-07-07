"""
Using LLM to convert the SHAP output into a understandable audit 
trail
"""

import json
import requests
from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END,START
import hashlib
from pathlib import Path

from core.knowledge import KnowledgeBaseManager  

kb_manager = KnowledgeBaseManager()

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
HASH_TRACKER_PATH = DATA_DIR / "last_ledger_hash.txt"

class ComplianceGraphState(TypedDict):
    raw_transaction: Dict[str, Any]
    hydrated_metrics: Dict[str, Any]
    shap_payload: Dict[str, Any]
    forensic_analysis_text: str
    regulatory_context_text: str
    final_audit_report_text: str
    previous_entry_hash: str

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
        response = requests.post(ollama_url, json=payload, timeout=60.0)
        if response.status_code == 200:
            response_json = response.json()
            compiled_report = response_json.get("response", "Error: Report generation string key missing.")
        else:
            compiled_report = f"LLM Generation Failed. Port returned status code: {response.status_code}"
    except Exception as e:
        compiled_report = f"LLM Generation Connection Timeout Error: {str(e)}"

    state["final_audit_report_text"] = compiled_report

    return state

def cryptLedger(state : ComplianceGraphState) -> ComplianceGraphState:
    """
    Before committing the log text string down to disk, this node automatically 
    calculates a cryptographic SHA-256 fingerprint hash value of the text, 
    linking it directly to the hash signature of the previous log entry to maintain 
    a tamper-evident audit history.
    """

    report_text = state.get("final_audit_report_text", "")
    
    # Fetch the preceding log entry's hash signature safely from disk cache
    if HASH_TRACKER_PATH.exists():
        previous_hash = HASH_TRACKER_PATH.read_text(encoding="utf-8").strip()
    else:
        # Genesis block default hash if this is the system's first rejection
        previous_hash = "0000000000000000000000000000000000000000000000000000000000000000"
        
    state["previous_entry_hash"] = previous_hash

    #Package the context chunk and calculate the unique cryptographic signature
    block_payload = f"PREV_HASH: {previous_hash}\nREPORT:\n{report_text}"
    
    current_hash = hashlib.sha256(block_payload.encode("utf-8")).hexdigest()

    # Inject the blockchain anchor straight into the report tail string
    signed_report = (
        f"{report_text}\n"
        f"[CRYPTOGRAPHIC LEDGER CHAIN CHECK]\n"
        f" - PREVIOUS_ENTRY_HASH : {previous_hash}\n"
        f" - CURRENT_RECORD_HASH : {current_hash}\n"
    )
    
    # Update state value containers
    state["final_audit_report_text"] = signed_report
    
    # Update the sidecar file on disk to act as the head pointer for the next block
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HASH_TRACKER_PATH.write_text(current_hash, encoding="utf-8")

    return state



graph = StateGraph(ComplianceGraphState)
graph.add_node("textForensics",textForensics)
graph.add_node("crossRefRAG",crossRefRAG)
graph.add_node("legalVerdict",legalVerdict)
graph.add_node("cryptLedger",cryptLedger)

graph.add_edge(START,"textForensics")
graph.add_edge("textForensics","crossRefRAG")
graph.add_edge("crossRefRAG","legalVerdict")
graph.add_edge("legalVerdict","cryptLedger")
graph.add_edge("cryptLedger",END)

CompilanceApp = graph.compile()


class ComplianceAgent:
    def __init__(self, ollama_url: str = "http://localhost:11434/api/generate"):
        self.ollama_url = ollama_url
        self.model_name = "llama3.1"

    def run_graph_audit(self, transaction_data: dict, hydrated_metrics: dict, shap_payload: dict) -> str:
        """
        Public entrypoint interface executing our compiled multi-node LangGraph DAG.
        Returns the finalized cryptographically chained compliance audit memo text.
        """
        # Initialize the state schema matching our TypedDict format requirement
        initial_state: ComplianceGraphState = {
            "raw_transaction": transaction_data,
            "hydrated_metrics": hydrated_metrics,
            "shap_payload": shap_payload,
            "forensic_analysis_text": "",
            "regulatory_context_text": "",
            "final_audit_report_text": "",
            "previous_entry_hash": ""
        }
        
        # Execute the compiled LangGraph App engine thread wrapper
        final_state = CompilanceApp.invoke(initial_state)
        
        # Extract the finalized cryptographically secured compliance log text
        return final_state.get("final_audit_report_text", "Error executing state DAG.")