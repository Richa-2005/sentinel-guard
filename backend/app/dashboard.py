import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Sentinel Guard: Risk Telemetry Core",
    page_icon="🛡️",
    layout="wide"
)

# Custom CSS Injection to elevate the user interface
st.markdown("""
    <style>
        .main { background-color: #0e1117; }
        .metric-card {
            background-color: #161e2e;
            border-left: 5px solid #6366f1;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
            margin-bottom: 20px;
        }
        .metric-card-alert {
            background-color: #2a1414;
            border-left: 5px solid #ef4444;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
            margin-bottom: 20px;
        }
        .terminal-box {
            background-color: #05070a;
            font-family: 'Courier New', Courier, monospace;
            color: #38bdf8;
            padding: 15px;
            border-radius: 6px;
            border: 1px solid #334155;
            height: 380px;
            overflow-y: scroll;
            white-space: pre-wrap;
        }
        .text-alert { color: #ef4444; font-weight: bold; }
        .text-clear { color: #22c55e; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

BACKEND_API_URL = "http://127.0.0.1:8000/api/v1/evaluate"

# Premium Application Title banner
st.markdown("## 🛡️ SENTINEL GUARD | <span style='color:#6366f1'>RISK COMPLIANCE & TELEMETRY CORE</span>", unsafe_allow_html=True)
st.markdown("---")

# Create a responsive split screen layout
col1, col2 = st.columns([1, 2])

with col1:
    st.markdown("### 💳 Live Ingestion Emulator")
    
    card_id = st.text_input("Card Signature ID", value="card_token_999")
    device_id = st.text_input("Device Hardware Token", value="dev_mac_001")
    
    # Toggle common testing presets to give recruiters immediate shortcuts
    preset_mode = st.radio("Select Ingestion Profile Preset", ["Standard Safe Swipe", "High-Volume Threat Vector"])
    
    if preset_mode == "High-Volume Threat Vector":
        amount_input = 27370
    else:
        amount_input = 1250
        
    amount_paise = st.number_input("Transaction Magnitude (Paise Subunits)", min_value=1, value=amount_input)
    submit_trigger = st.button("Transmit Infiltration Packet", use_container_width=True)

    if submit_trigger: 
        if (not card_id) or (not device_id) or (not amount_paise):
            st.error("Please fill all the fields.")
        else:
            payload = {
                "card_id": card_id, 
                "device_id": device_id, 
                "amount_paise": amount_paise
            }

            response = requests.post(BACKEND_API_URL, json=payload)

            if response.status_code == 200:
                data = response.json()
                is_blocked = data.get("is_blocked", False)
                risk_score = data.get("ensemble_risk_score", 0.0)
                hydrated = data.get("hydrated_metrics", {})
                status_msg = data.get("status", "Evaluated")
                
                # Render visual metric alerts based on security results
                if is_blocked:
                    st.markdown(f"""
                        <div class="metric-card-alert">
                            <span class="text-alert">🚨 SYSTEM BLOCK TRIGGERED</span><br>
                            <small style="color: #94a3b8;">Status: {status_msg}</small>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                        <div class="metric-card">
                            <span class="text-clear">✅ TRANSACTION CLEARED</span><br>
                            <small style="color: #94a3b8;">Status: Automated Passing Gate Approved</small>
                        </div>
                    """, unsafe_allow_html=True)

with col2:
    st.markdown("### 📊 Operational Analytics & Compliance Telemetry")
    
    # 1. Initialize clean enterprise tab divisions
    tab_live, tab_vault = st.tabs(["⚡ Live Traffic Monitor", "🗄️ Historical Audit Vault"])
    
    with tab_live:
        if submit_trigger and response.status_code == 200:
            # Wrap core metrics inside our styled HTML card
            st.markdown(f"""
                <div class="metric-card">
                    <h4 style="margin:0 0 10px 0; color:#94a3b8; font-size:14px;">DECISION LOG ENGINE METRICS</h4>
                    <table style="width:100%; color:white; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 4px 0;"><b>Ensemble Threat Probability:</b></td>
                            <td style="text-align:right;"><span class="{ 'text-alert' if is_blocked else 'text-clear' }">{risk_score:.4f}</span></td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0;"><b>Rolling Card Velocity (10m):</b></td>
                            <td style="text-align:right; color:#38bdf8;">{int(hydrated.get("card_vel_10m", 0))} swipes</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0;"><b>Device/Card Authorization Ratio:</b></td>
                            <td style="text-align:right; color:#38bdf8;">{hydrated.get("device_card_ratio_30m", 0.0):.4f}</td>
                        </tr>
                    </table>
                </div>
            """, unsafe_allow_html=True)
            
            if is_blocked:
                st.markdown("#### 📑 Isolated Incident Audit Trail")
                st.caption(f"Showing localized Llama 3 compliance log for active signature: {card_id}")
                
                # Extract ONLY the latest entry matching this specific transaction run
                try:
                    with open("data/compliance_audit.log", "r", encoding="utf-8") as f:
                        log_contents = f.read()
                    
                    entries = log_contents.strip().split("=== AUDIT ENTRY")
                    # Filter out entries to locate the absolute newest record for this card asset
                    matching_entry = None
                    for entry in reversed(entries):
                        if f"Card ID: {card_id}" in entry:
                            matching_entry = entry
                            break
                    
                    if matching_entry:
                        st.markdown(f"""
                            <div class="terminal-box">
=== AUDIT ENTRY{matching_entry}
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.info("🔄 Async Worker Thread is executing token calculations... Re-click in 2 seconds.")
                except FileNotFoundError:
                    st.info("🔄 Log pool initialization pending. Boot your background worker thread structures.")
        else:
            st.markdown("""
                <div class="terminal-box" style="color: #64748b; display: flex; align-items: center; justify-content: center; text-align: center; height: 200px;">
                    [Gateway Standby Mode: Awaiting Inbound Network Payload Request]
                </div>
            """, unsafe_allow_html=True)

    with tab_vault:
        st.markdown("#### 🔍 Corporate Compliance Search Directory")
        st.caption("Query the absolute chronological ledger history of malicious card token IDs recorded on disk.")
        
        search_target = st.text_input("Enter Target Card ID Hash to Audit", placeholder="e.g., card_token_999")
        search_trigger = st.button("Query Persistence Storage Engine", use_container_width=True)
        
        if search_trigger and search_target:
            try:
                with open("data/compliance_audit.log", "r", encoding="utf-8") as f:
                    log_contents = f.read()
                
                entries = log_contents.strip().split("=== AUDIT ENTRY")
                # Collect all historical offenses associated with this string identifier
                historical_matches = [entry for entry in entries if f"Card ID: {search_target}" in entry]
                
                if historical_matches:
                    st.success(f"Located {len(historical_matches)} historical risk alerts for token target.")
                    for match in historical_matches:
                        st.markdown(f"""
                            <div class="terminal-box" style="margin-bottom: 15px; height: 180px;">
=== AUDIT ENTRY{match}
                            </div>
                        """, unsafe_allow_html=True)
                else:
                    st.error("No flagged compliance entries matched the parsed query token signature.")
            except FileNotFoundError:
                st.info("Storage layer ledger has not recorded any malicious entities yet.")