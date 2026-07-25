import { useMemo, useState } from 'react';

const WIDTH=860, HEIGHT=280, PAD={left:48,right:22,top:24,bottom:38};
const time=(value)=>new Date(value||0).toLocaleTimeString('en-GB',{timeZone:'UTC',hour:'2-digit',minute:'2-digit',hour12:false});
const money=(value=0)=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR'}).format(value/100);

function curve(points) {
  if (!points.length) return '';
  if (points.length===1) return `M ${points[0].x} ${points[0].y}`;
  let path=`M ${points[0].x} ${points[0].y}`;
  for(let index=1;index<points.length-1;index+=1){const current=points[index],next=points[index+1];path+=` Q ${current.x} ${current.y} ${(current.x+next.x)/2} ${(current.y+next.y)/2}`;}
  const last=points[points.length-1];return `${path} T ${last.x} ${last.y}`;
}

export function RiskTraceChart({transactions=[],threshold=.95}) {
  const [active,setActive]=useState(null);
  const values=useMemo(()=>transactions.slice(0,42).reverse(),[transactions]);
  const points=values.map((item,index)=>({item,x:PAD.left+(index/Math.max(1,values.length-1))*(WIDTH-PAD.left-PAD.right),y:PAD.top+(1-Number(item.ensemble_risk_score||0))*(HEIGHT-PAD.top-PAD.bottom)}));
  const line=curve(points);const base=HEIGHT-PAD.bottom;
  const area=points.length?`${line} L ${points[points.length-1].x} ${base} L ${points[0].x} ${base} Z`:'';
  return <div className="interactive-chart"><svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Recent ensemble risk scores over time">
    <defs><linearGradient id="riskArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#b995ff" stopOpacity=".32"/><stop offset="1" stopColor="#b995ff" stopOpacity="0"/></linearGradient></defs>
    {[0,.25,.5,.75,1].map(value=>{const y=PAD.top+(1-value)*(HEIGHT-PAD.top-PAD.bottom);return <g key={value}><line className="chart-gridline" x1={PAD.left} x2={WIDTH-PAD.right} y1={y} y2={y}/><text x={8} y={y+4}>{Math.round(value*100)}%</text></g>})}
    <line className="chart-threshold" x1={PAD.left} x2={WIDTH-PAD.right} y1={PAD.top+(1-threshold)*(HEIGHT-PAD.top-PAD.bottom)} y2={PAD.top+(1-threshold)*(HEIGHT-PAD.top-PAD.bottom)}/><text className="threshold-label" x={WIDTH-PAD.right-94} y={Math.max(16,PAD.top+(1-threshold)*(HEIGHT-PAD.top-PAD.bottom)-7)}>decision boundary</text>
    <path className="chart-area" d={area}/><path className="chart-line" d={line}/>
    {points.map((point,index)=><circle key={point.item.transaction_id||index} tabIndex="0" className={`chart-point ${point.item.is_blocked?'is-blocked':''} ${active===index?'is-active':''}`} cx={point.x} cy={point.y} r={active===index?6:3.5} onMouseEnter={()=>setActive(index)} onMouseLeave={()=>setActive(null)} onFocus={()=>setActive(index)} onBlur={()=>setActive(null)}/>) }
    {points.length>1&&<><text x={PAD.left} y={HEIGHT-10}>{time(values[0]?.timestamp)}</text><text textAnchor="end" x={WIDTH-PAD.right} y={HEIGHT-10}>{time(values[values.length-1]?.timestamp)}</text></>}
  </svg>{active!=null&&points[active]&&<div className="chart-tooltip" style={{left:`${points[active].x/WIDTH*100}%`,top:`${points[active].y/HEIGHT*100}%`}}><strong>{points[active].item.is_blocked?'Blocked decision':'Allowed decision'}</strong><span className="mono">{points[active].item.transaction_id}</span><span>{(Number(points[active].item.ensemble_risk_score)*100).toFixed(3)}% risk · {money(points[active].item.amount_paise)}</span><small>{time(points[active].item.timestamp)} UTC</small></div>}</div>;
}

export function DistributionChart({buckets=[],threshold=.95}) {
  const [active,setActive]=useState(null);const max=Math.max(1,...buckets.map(bucket=>bucket.count));
  return <div className="distribution-chart"><div className="distribution-bars">{buckets.map((bucket,index)=><button key={`${bucket.lower_bound}-${bucket.upper_bound}`} onMouseEnter={()=>setActive(index)} onMouseLeave={()=>setActive(null)} onFocus={()=>setActive(index)} onBlur={()=>setActive(null)}><span className="distribution-value">{bucket.count}</span><i><b style={{height:`${Math.max(3,bucket.count/max*100)}%`}}/></i><small>{Math.round(bucket.lower_bound*100)}–{Math.round(bucket.upper_bound*100)}%</small>{active===index&&<output><strong>{bucket.count} predictions</strong><span>{bucket.rate==null?'No observations':`${(bucket.rate*100).toFixed(1)}% of this window`}</span><small>Risk range {bucket.lower_bound.toFixed(2)}–{bucket.upper_bound.toFixed(2)}</small></output>}</button>)}</div><div className="distribution-threshold"><i style={{left:`${Math.min(100,threshold*100)}%`}}/><span>Deployed decision boundary: {(threshold*100).toFixed(2)}%</span></div></div>;
}

export function StabilityGauge({psi,level='insufficient_data',currentSample=0,minimumSample=30}) {
  const value=psi==null?0:Math.min(.4,psi);const angle=-90+(value/.4)*180;return <div className="stability-gauge"><svg viewBox="0 0 260 145" role="img" aria-label={`Population stability ${level.replaceAll('_',' ')}`}><path className="gauge-track" d="M 35 125 A 95 95 0 0 1 225 125"/><path className="gauge-stable" d="M 35 125 A 95 95 0 0 1 96 36"/><path className="gauge-moderate" d="M 96 36 A 95 95 0 0 1 169 36"/><path className="gauge-critical" d="M 169 36 A 95 95 0 0 1 225 125"/>{psi!=null&&<g transform={`rotate(${angle} 130 125)`}><line className="gauge-needle" x1="130" y1="125" x2="130" y2="47"/><circle cx="130" cy="125" r="7"/></g>}<text className="gauge-number" x="130" y="112" textAnchor="middle">{psi==null?`${currentSample}/${minimumSample}`:psi.toFixed(3)}</text></svg><div><span>Stable &lt; 0.10</span><span>Moderate 0.10–0.25</span><span>Significant &gt; 0.25</span></div></div>;
}
