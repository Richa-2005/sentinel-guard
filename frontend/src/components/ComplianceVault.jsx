import { useEffect, useMemo, useState } from 'react';
import { Check, Clipboard, Expand, FileText, Link2, RefreshCw, Search, ShieldCheck, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { verifyAuditChain } from '../api/client';
import { useApp } from '../context/AppContext';
import { useAuth } from '../context/AuthContext';
import { Badge, EmptyState, PageGuide } from './ui/Primitives';

const improve=(text='')=>{
  const lines=text.replaceAll('```markdown','').replaceAll('```','').split('\n');
  const firstSection=lines.findIndex(line=>/^\s*(?:#{1,3}\s*)?A\.\s*EXECUTIVE RISK VERDICT/i.test(line));
  const relevant=(firstSection>=0?lines.slice(firstSection):lines).filter(line=>
    !/^\s*(?:here is|below is|the following is) (?:the )?(?:mandatory )?(?:compliance )?report/i.test(line)
    && !/^\s*NEXUS FINTECH COMPLIANCE INCIDENT REPORT/i.test(line)
  );
  return relevant.map(line=>{
    const clean=line.trim();
    if(/^\|/.test(clean)){
      const cells=clean.split('|').map(cell=>cell.trim()).filter(Boolean);
      if(!cells.length||cells.every(cell=>/^:?-{3,}:?$/.test(cell))||/^feature$/i.test(cells[0]))return '';
      if(cells.length>=2)return `- **${cells[0].replaceAll('_',' ')}:** ${cells.slice(1).join(' · ')}`;
    }
    if(/^\s*#{1,6}\s/.test(line))return line;
    if(/^[A-D]\.\s*(EXECUTIVE RISK VERDICT|TECHNICAL SPECIFICATION PROFILE|REGULATORY COMPLIANCE CROSS-REFERENCE|COMPLIANCE CROSS-REFERENCE|MITIGATION (?:&|AND) ACTIONABLE DEFEN[CS]E ROADMAP)\s*:?\s*$/i.test(clean))return `## ${clean.replace(/:$/,'')}`;
    if(/^(Transaction details|Anomalies detected|Model evidence|Recommended actions):?$/i.test(clean))return `### ${clean.replace(/:$/,'')}`;
    return line;
  }).join('\n').trim();
};
const utc=(v)=>v?new Date(v).toLocaleString('en-GB',{timeZone:'UTC',hour12:false})+' UTC':'Historical record';

function CopyButton({text,label='Copy report'}){const[copied,setCopied]=useState(false);const copy=async()=>{try{await navigator.clipboard.writeText(text||'')}catch{const area=document.createElement('textarea');area.value=text||'';area.style.position='fixed';area.style.opacity='0';document.body.appendChild(area);area.select();document.execCommand('copy');area.remove()}setCopied(true);setTimeout(()=>setCopied(false),1500)};return <button className="button button--secondary" onClick={copy} disabled={!text}>{copied?<Check size={14}/>:<Clipboard size={14}/>} {copied?'Copied':label}</button>}
function Hash({label,value}){return <div className="ledger-hash"><span>{label}</span><code>{value||'Not recorded'}</code><CopyButton text={value} label="Copy"/></div>}
function Report({record}){return <article className="report-paper"><header><div><span>Sentinel Guard · Compliance memorandum</span><h1>Model decision review</h1></div><b>Record #{record.id}</b></header><div className="report-meta"><div><span>Target card</span><strong>{record.card_id}</strong></div><div><span>Recorded</span><strong>{utc(record.timestamp)}</strong></div><div><span>Chain state</span><strong>Append-only</strong></div></div><div className="report-prose"><ReactMarkdown>{improve(record.report_text)}</ReactMarkdown></div></article>}

export default function ComplianceVault(){
  const{audits,auditStatuses,loading,refreshAudits,auditSearch,setAuditSearch,selectedAuditId,setSelectedAuditId}=useApp();
  const{user}=useAuth();const admin=user?.role==='admin';
  const[reader,setReader]=useState(false);const[verification,setVerification]=useState(null);const[checking,setChecking]=useState(false);const[syncing,setSyncing]=useState(false);const[syncMessage,setSyncMessage]=useState('');
  const filtered=useMemo(()=>audits.filter(a=>`${a.card_id} ${a.transaction_id} ${a.report_text}`.toLowerCase().includes(auditSearch.toLowerCase())),[audits,auditSearch]);
  const selected=audits.find(a=>a.id===selectedAuditId)||filtered[0]||null;
  useEffect(()=>{if(selected&&selected.id!==selectedAuditId)setSelectedAuditId(selected.id)},[selected?.id]);
  useEffect(()=>{const close=e=>e.key==='Escape'&&setReader(false);addEventListener('keydown',close);return()=>removeEventListener('keydown',close)},[]);
  const continuity=selected?.previous_hash&&audits.find(a=>a.current_hash===selected.previous_hash);
  const verify=async()=>{setChecking(true);try{setVerification(await verifyAuditChain())}finally{setChecking(false)}};
  const sync=async()=>{setSyncing(true);setSyncMessage('');try{await refreshAudits();setSyncMessage('Ledger refreshed')}catch(error){setSyncMessage(error.message)}finally{setSyncing(false)}};
  const pending=Object.values(auditStatuses).filter(s=>['processing','delayed'].includes(s.status)).length;
  return <div className="ops-page">
    <PageGuide title="Read the complete incident memorandum and follow its preserved record.">The document explains the automated intervention. The continuity view shows how records link together; human recommendations and final verdicts remain in Review Control.</PageGuide>
    <section className="ops-statusline"><div><ShieldCheck size={15}/><strong>Append-only audit ledger</strong></div><span>{audits.length} records</span><span>{pending} processing</span>{verification&&<span>{verification.records_checked} links checked</span>}{admin&&<button className="verify-chain-action" onClick={verify} disabled={checking}>{checking?'Verifying chain…':'Verify ledger chain'}</button>}<button onClick={sync} disabled={syncing}><RefreshCw size={13} className={syncing?'spin':''}/>{syncing?'Refreshing…':'Refresh ledger'}</button></section>
    {syncMessage&&<div className="sync-feedback" role="status">{syncMessage}</div>}
    {verification&&<div className={`verification-line ${verification.is_valid?'is-valid':'is-invalid'}`}><strong>{verification.is_valid?'Chain continuity verified':'Continuity issue detected'}</strong><span>{verification.issue_count} issues · head {verification.head_hash?.slice(0,14)}… · checked {utc(verification.checked_at)}</span></div>}
    <section className="vault-workspace">
      <aside className="vault-records"><div className="queue-tools"><label className="ops-search"><Search size={14}/><input value={auditSearch} onChange={e=>{setAuditSearch(e.target.value);setSelectedAuditId(null)}} placeholder="Search card or report"/></label></div><div className="audit-index">{loading?<p>Loading ledger…</p>:filtered.length?filtered.map(a=><button key={a.id} className={selected?.id===a.id?'is-selected':''} onClick={()=>setSelectedAuditId(a.id)}><FileText size={15}/><span><strong>{a.card_id||'Unknown card'}</strong><small>{utc(a.timestamp)}</small></span><Badge tone={a.is_error?'warning':'neutral'}>{a.is_error?'issue':'recorded'}</Badge></button>):<EmptyState title="No records" message="Completed generated reports will appear in this index."/>}</div></aside>
      <main className="vault-reading">{selected&&!selected.is_error?<><div className="reader-toolbar"><div><span className="eyebrow">Generated report</span><strong>Readable document view</strong></div><CopyButton text={selected.report_text}/><button className="button button--primary" onClick={()=>setReader(true)}><Expand size={14}/>Focus reader</button></div><Report record={selected}/></>:selected?<div className="report-error"><h2>Report generation did not complete</h2><p>{selected.report_text}</p></div>:<EmptyState title="Select an audit record" message="The complete generated memorandum opens here."/>}</main>
      <aside className="vault-continuity"><div><span className="eyebrow">Ledger continuity</span><h3>{selected?(/^0{64}$/.test(selected.previous_hash)?'Genesis record':continuity?'Predecessor matched':'Predecessor outside view'):'No record selected'}</h3></div>{selected&&<><div className="chain-state"><Link2 size={17}/><span><strong>{continuity?'Hash reference resolved':'Recorded chain reference'}</strong><small>{continuity?`Points to record #${continuity.id}`:'Compare against the full verification result.'}</small></span></div><Hash label="Previous hash" value={selected.previous_hash}/><div className="hash-link"><i/><Link2 size={13}/><i/></div><Hash label="Current hash" value={selected.current_hash}/></>}</aside>
    </section>
    {reader&&selected&&<div className="report-reader-layer" role="dialog" aria-modal="true" aria-label="Compliance report reader"><div className="report-reader-shell"><header><div><span>Focused report reader</span><strong>{selected.card_id} · Record #{selected.id}</strong></div><CopyButton text={selected.report_text}/><button className="icon-button" onClick={()=>setReader(false)} aria-label="Close report"><X/></button></header><div className="report-reader-scroll"><Report record={selected}/></div></div></div>}
  </div>;
}
