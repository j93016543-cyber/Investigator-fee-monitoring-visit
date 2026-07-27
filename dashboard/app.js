/* TTK-CS-101 연구비·모니터링 트래커 — 렌더러 */
const DATA = JSON.parse(document.getElementById('store').textContent);
const $ = (s, r=document) => r.querySelector(s);
const el = (t, a={}, kids=[]) => {
  const n = document.createElement(t);
  for (const k in a){ if(k==='class') n.className=a[k]; else if(k==='html') n.innerHTML=a[k]; else n.setAttribute(k,a[k]); }
  (Array.isArray(kids)?kids:[kids]).forEach(c=>c!=null&&n.append(c.nodeType?c:document.createTextNode(c)));
  return n;
};
const usd = v => v==null?'—':(v<0?'-$':'$')+Math.abs(v).toLocaleString('en-US',{maximumFractionDigits:0});
const usd2 = v => v==null?'—':(v<0?'-$':'$')+Math.abs(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
const nfmt = v => v==null?'—':Number(v).toLocaleString('en-US');
const pct = v => v==null?'—':(v*100).toFixed(1)+'%';
const C = DATA.contract;

/* ---------- contract reference amounts for 음영 대조 ---------- */
const REFS = [];
(C.payment_schedule||[]).forEach(p=>REFS.push(Math.abs(p.amount)));
(C.wo_budget||[]).forEach(b=>{ if(b.total) REFS.push(Math.abs(b.total)); });
(C.investigator_rates||[]).forEach(r=>{ REFS.push(r.total); REFS.push(r.cost_per_unit); });
function matchContract(amount){
  if(amount==null) return null;
  const a=Math.abs(amount);
  return REFS.some(r=> Math.abs(a-r) <= Math.max(1, r*0.005)) ? 'good' : 'warn';
}

/* ---------- SVG charts ---------- */
const TT = $('#tt');
function showTT(html, ev){ TT.innerHTML=html; TT.style.opacity=1;
  const p=8, w=TT.offsetWidth, h=TT.offsetHeight;
  let x=ev.clientX+14, y=ev.clientY+14;
  if(x+w>innerWidth-p) x=ev.clientX-w-14; if(y+h>innerHeight-p) y=ev.clientY-h-14;
  TT.style.left=x+'px'; TT.style.top=y+'px'; }
function hideTT(){ TT.style.opacity=0; }
const SVGNS='http://www.w3.org/2000/svg';
const sv = (t,a={}) => { const n=document.createElementNS(SVGNS,t); for(const k in a) n.setAttribute(k,a[k]); return n; };

function barChart(host, {labels, series, yfmt=usd, height=260}){
  const W=Math.max(560, labels.length*Math.max(64, series.length*26+30)), H=height;
  const m={t:16,r:14,b:46,l:64};
  const iw=W-m.l-m.r, ih=H-m.t-m.b;
  const max=Math.max(1,...series.flatMap(s=>s.vals.map(v=>v||0)));
  const svg=sv('svg',{viewBox:`0 0 ${W} ${H}`,width:W,height:H,role:'img'});
  const g=sv('g',{transform:`translate(${m.l},${m.t})`}); svg.append(g);
  const gg=sv('g',{class:'grid'}); g.append(gg);
  const ticks=4;
  for(let i=0;i<=ticks;i++){ const y=ih-ih*i/ticks, val=max*i/ticks;
    gg.append(sv('line',{x1:0,y1:y,x2:iw,y2:y,'stroke-width':1,opacity:i?.5:1}));
    const tx=sv('text',{x:-10,y:y+4,'text-anchor':'end','font-size':11}); tx.textContent=yfmt(val); g.append(tx);
  }
  const bw=iw/labels.length, inner=Math.min(bw-14, series.length*30), sw=inner/series.length;
  labels.forEach((lab,i)=>{
    const x0=i*bw+(bw-inner)/2;
    series.forEach((s,si)=>{
      const v=s.vals[i]||0, bh=Math.max(0, ih*v/max), x=x0+si*sw, y=ih-bh;
      const r=sv('rect',{x:x+2,y,width:Math.max(0,sw-4),height:bh,rx:4,fill:s.color});
      r.style.cursor='pointer';
      r.addEventListener('mousemove',ev=>showTT(`<div class="tt-t">${lab}</div>${s.name}: <b>${yfmt(v)}</b>`,ev));
      r.addEventListener('mouseleave',hideTT);
      g.append(r);
    });
    const tx=sv('text',{x:i*bw+bw/2,y:ih+18,'text-anchor':'middle','font-size':11}); tx.textContent=lab; g.append(tx);
  });
  const wrap=el('div',{class:'svg-wrap'}); wrap.append(svg); host.append(wrap);
}

function lineChart(host, {labels, series, yfmt=nfmt, height=260}){
  const W=Math.max(560, labels.length*90), H=height, m={t:16,r:18,b:40,l:56};
  const iw=W-m.l-m.r, ih=H-m.t-m.b;
  const max=Math.max(1,...series.flatMap(s=>s.vals.map(v=>v||0)));
  const svg=sv('svg',{viewBox:`0 0 ${W} ${H}`,width:W,height:H});
  const g=sv('g',{transform:`translate(${m.l},${m.t})`}); svg.append(g);
  const gg=sv('g',{class:'grid'}); g.append(gg);
  for(let i=0;i<=4;i++){ const y=ih-ih*i/4;
    gg.append(sv('line',{x1:0,y1:y,x2:iw,y2:y,'stroke-width':1,opacity:i?.5:1}));
    const tx=sv('text',{x:-10,y:y+4,'text-anchor':'end','font-size':11}); tx.textContent=yfmt(max*i/4); g.append(tx);
  }
  const X=i=> labels.length<2?iw/2:iw*i/(labels.length-1);
  labels.forEach((lab,i)=>{ const tx=sv('text',{x:X(i),y:ih+18,'text-anchor':'middle','font-size':11}); tx.textContent=lab; g.append(tx); });
  series.forEach(s=>{
    const pts=s.vals.map((v,i)=>[X(i), ih-ih*(v||0)/max]);
    const d=pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' ');
    g.append(sv('path',{d,fill:'none',stroke:s.color,'stroke-width':2.4,'stroke-dasharray':s.dash||'','stroke-linejoin':'round'}));
    pts.forEach((p,i)=>{ const c=sv('circle',{cx:p[0],cy:p[1],r:s.dash?0:4.5,fill:s.color,stroke:'var(--surface)','stroke-width':1.5});
      if(!s.dash){ c.style.cursor='pointer';
        c.addEventListener('mousemove',ev=>showTT(`<div class="tt-t">${labels[i]}</div>${s.name}: <b>${yfmt(s.vals[i])}</b>`,ev));
        c.addEventListener('mouseleave',hideTT);} g.append(c); });
  });
  const wrap=el('div',{class:'svg-wrap'}); wrap.append(svg); host.append(wrap);
}
function legend(items){ return el('div',{class:'legend'}, items.map(it=>
  el('span',{},[el('span',{class:'dot',style:`background:${it.color}`}), it.name]))); }

/* ---------- reusable ---------- */
function card(tag, title, desc, bodyEl, flush){
  const head=el('div',{class:'head'},[ tag&&el('span',{class:'tag'},tag), el('h2',{},title), desc&&el('div',{class:'desc'},desc) ].filter(Boolean));
  const body=el('div',{class:'body'+(flush?' flush':'')},bodyEl);
  return el('div',{class:'card'},[head,body]);
}
function kpi(lab,val,meta,barPct){
  return el('div',{class:'kpi'},[ el('div',{class:'lab'},lab), el('div',{class:'val tnum'},val),
    meta&&el('div',{class:'meta'},meta),
    barPct!=null&&el('div',{class:'bar'},el('i',{style:`width:${Math.min(100,barPct*100).toFixed(0)}%`})) ].filter(Boolean));
}
function tableFrom(cols, rows){
  const thead=el('thead',{},el('tr',{},cols.map(c=>el('th',{class:c.num?'num':''},c.h))));
  const tbody=el('tbody',{}, rows.map(r=>{
    const tr=el('tr',{class:r._cls||''});
    cols.forEach(c=>{ const cell=r[c.k]; const td=el('td',{class:(c.num?'num ':'')+(r._shade&&r._shade[c.k]?('shade-'+r._shade[c.k]):'')});
      if(cell&&cell.nodeType) td.append(cell); else td.textContent = cell==null?'':cell; tr.append(td); });
    return tr;
  }));
  return el('div',{class:'tbl-scroll'},el('table',{},[thead,tbody]));
}

/* =====================================================================
   연구비 TAB
===================================================================== */
function renderFee(){
  const p=$('#panel-fee'); p.innerHTML='';
  const env=C.payment_envelopes||{}, tm=C.tracker_meta||{};
  const st=(DATA.vendor_status||[]).find(v=>v.vendor==='IQVIA')||{};

  // KPIs
  p.append(el('div',{class:'kpis'},[
    kpi('연구비 (Investigator Grants) 총액', usd(env.investigator_grants_total), 'WO v3 · 대상자당 NA $43,174 / AP $37,442'),
    kpi('Invoiceable (Professional/Specialty)', usd(env.professional_specialty_max), 'WO v3 최대 (할인 후 Direct)'),
    kpi('IQVIA 계약 총액', usd(tm.budget_usd||st.contracted), 'CO1 기준 전체 예산'),
    kpi('지급 완료', usd(tm.paid_usd||st.paid), (st.pct_remaining!=null?`잔여 ${pct(st.pct_remaining)}`:''), tm.budget_usd?(tm.paid_usd/tm.budget_usd):null),
  ]));

  // 분기별 trend
  const q=(DATA.quarterly||[]).filter(x=>x.vendor==='IQVIA'&&(x.planned||x.actual)).sort((a,b)=>a.year-b.year||a.quarter-b.quarter);
  const labels=q.map(x=>`'${String(x.year).slice(2)} Q${x.quarter}`);
  const chartBody=el('div',{},[
    legend([{name:'Planned',color:'var(--s1)'},{name:'Actual',color:'var(--s2)'}]),
    el('div',{}),
  ]);
  barChart(chartBody, {labels, series:[
    {name:'Planned',color:'var(--s1)',vals:q.map(x=>x.planned)},
    {name:'Actual',color:'var(--s2)',vals:q.map(x=>x.actual)},
  ], yfmt:v=>'$'+(v/1e6).toFixed(v>=1e6?1:2)+'M'});
  p.append(card('TREND','분기별 지급 연구비 (IQVIA, USD)','계획 대비 실제 지급액 · 분기별',chartBody));

  // A — 계약서 & 항목별 단가
  const vcols=[{k:'version',h:'버전'},{k:'type',h:'유형'},{k:'eff',h:'Effective Date'},{k:'term',h:'기간'},{k:'total',h:'총액',num:true},{k:'note',h:'비고'}];
  const vrows=(C.versions||[]).map(v=>({version:v.version,type:v.type,eff:v.effective_date,term:v.term,
    total: v.grand_total?usd(v.grand_total):'—', note:v.note, _cls: v.is_effective?'eff':''}));
  const aBudget=el('div',{});
  aBudget.append(el('h3',{class:'subh'},'WO v3 항목별 단가 (Attachment 2) — Budgeting Unit · 단가 · 총액'));
  const bcols=[{k:'item',h:'항목'},{k:'unit',h:'Unit'},{k:'qty',h:'수량',num:true},{k:'uc',h:'단가(USD)',num:true},{k:'tot',h:'총액(USD)',num:true}];
  const brows=(C.wo_budget||[]).map(b=>({item:b.item,unit:b.unit||'',qty:b.qty!=null?nfmt(b.qty):'',
    uc:b.unit_cost!=null?usd2(b.unit_cost):'', tot:b.total!=null?usd(b.total):'',
    _cls:(b.kind==='section'?'sec':b.kind==='sub'?'sub':b.kind==='subtotal'?'subtotal':b.kind==='total'?'total':'')}));
  aBudget.append(tableFrom(bcols,brows));
  const aWrap=el('div',{},[
    el('h3',{class:'subh'},'계약 버전 이력 (음영 = 현재 유효 계약)'),
    tableFrom(vcols,vrows), aBudget ]);
  p.append(card('A','기관별 계약서 · 항목별 비용', `${C.vendor} · 계약번호 ${C.contract_number}`, aWrap));

  // B — 지급/invoice 기록
  const pays=(DATA.payments||[]).slice().sort((a,b)=>String(a.invoiced_date||'').localeCompare(String(b.invoiced_date||'')));
  const bcols2=[{k:'type',h:'구분'},{k:'desc',h:'Milestone / Description'},{k:'inv',h:'Invoice #'},{k:'date',h:'Invoiced'},
    {k:'amt',h:'금액(USD)',num:true},{k:'appr',h:'지출결의#(내부기안)'},{k:'paid',h:'지급'},{k:'chk',h:'계약대조'}];
  const brows2=pays.map(py=>{
    const m=matchContract(py.invoiced_usd);
    const chip = m==='good'?el('span',{class:'chip good'},'계약 일치'): m==='warn'?el('span',{class:'chip warn'},'확인 필요'):el('span',{class:'chip mute'},'—');
    const paidChip = (py.paid_yn==='Y'||py.paid_date)?el('span',{class:'chip good'},'지급완료'):el('span',{class:'chip mute'},'대기');
    return {type: el('span',{class:'chip '+(py.cost_type==='Direct'?'acc':'mute')},py.cost_type),
      desc: py.milestone||'PTC invoice', inv: py.invoice_no||'', date: py.invoiced_date||'',
      amt: usd2(py.invoiced_usd), appr: py.approval_no||'', paid: paidChip, chk: chip,
      _shade:{amt: m||null} };
  });
  const bBody=el('div',{},[
    el('div',{class:'note',html:'<span>ℹ️</span><div><b>음영 규칙:</b> 각 지급건의 금액이 A(유효 계약서 WO v3)의 Payment Schedule·항목 단가와 일치하면 <span class="chip good">계약 일치</span>(초록), 계약서에서 찾지 못하면 <span class="chip warn">확인 필요</span>(노랑)로 표시됩니다.</div>'}),
    tableFrom(bcols2,brows2) ]);
  p.append(card('B','지급 · Invoice 기록 (계약 대조 음영)', 'IQVIA Direct + Pass-through 지급 내역', bBody, false));

  // C — 대상자·방문 tracker
  const sv0=DATA.subject_visits||[];
  const sites=[...new Set(sv0.map(x=>x.site_no).filter(Boolean))].sort();
  const ctrl=el('div',{class:'controls'});
  const selSite=el('select',{},[el('option',{value:''},'모든 Site'),...sites.map(s=>el('option',{value:s},'Site '+s))]);
  const q2=el('input',{type:'search',placeholder:'대상자 검색 (예: 537-1002)'});
  const countEl=el('span',{class:'small muted'});
  ctrl.append(el('span',{class:'small muted'},'필터:'),selSite,q2,el('span',{class:'spacer'}),countEl);
  const holder=el('div',{});
  function draw(){
    holder.innerHTML='';
    const fs=selSite.value, fq=q2.value.trim().toLowerCase();
    const rows=sv0.filter(x=>(!fs||x.site_no===fs)&&(!fq||String(x.subject).toLowerCase().includes(fq)));
    countEl.textContent=`${rows.length.toLocaleString()} 방문 · 대상자 ${new Set(rows.map(r=>r.subject)).size}명`;
    const cols=[{k:'site_no',h:'Site#'},{k:'site',h:'기관명'},{k:'subject',h:'대상자'},{k:'instance',h:'Visit'},{k:'visit_date',h:'방문일'},{k:'done',h:'완료'}];
    const rr=rows.slice(0,400).map(x=>({site_no:x.site_no,site:x.site,subject:x.subject,instance:x.instance||x.visit_folder,
      visit_date:x.visit_date||'', done: x.visit_done==='Yes'?el('span',{class:'chip good'},'Y'):el('span',{class:'chip mute'},x.visit_done||'—')}));
    holder.append(tableFrom(cols,rr));
    if(rows.length>400) holder.append(el('div',{class:'small muted',style:'padding:8px 12px'},`상위 400건 표시 (총 ${rows.length}건). Site/대상자로 필터하세요.`));
  }
  selSite.onchange=draw; q2.oninput=draw; draw();
  const cBody=el('div',{},[
    el('div',{class:'note pending',html:'<span>⚠️</span><div><b>방문별 지급액(연구비+invoice)은 데이터 대기 중:</b> 방문별 <b>금액</b>은 <code>visit activity.xlsx</code>·<code>Invoice.xlsx</code>가 필요합니다. 현재는 EDC 기반 <b>대상자·방문·방문일</b>을 표시하며, 파일을 주시면 방문별 지급액과 지급일별 음영을 추가합니다.</div>'}),
    ctrl, holder ]);
  p.append(card('C','기관별 · 대상자별 · 방문별 Tracker', 'EDC subject visit 기준', cBody));
}

/* =====================================================================
   모니터링 TAB
===================================================================== */
function monitoringSummary(){
  const mv=DATA.monitoring_visits||{}; const rows=mv.rows||[]; const snaps=mv.snapshots||[];
  const cats={}; const order=[];
  rows.forEach(r=>{
    let gl=(r.group||'').trim();
    if(!gl||gl.startsWith('Interim MV Sub-Total')||gl==='Total') return;
    const name=gl.replace(/\s*\d+\s*$/,'').trim();
    if(!cats[name]){ cats[name]={name,contracted:0,latest:0,balance:0}; order.push(name); }
    cats[name].contracted += r.contracted||0;
    const last=(r.actuals||[])[ (r.actuals||[]).length-1 ];
    cats[name].latest += (last&&last.total)||0;
    cats[name].balance += r.balance||0;
  });
  return {cats:order.map(n=>cats[n]), snaps};
}
function renderMon(){
  const p=$('#panel-mon'); p.innerHTML='';
  const mv=DATA.monitoring_visits||{}; const rows=mv.rows||[]; const snaps=mv.snapshots||[];
  const totalRow=rows.find(r=>(r.group||'').startsWith('Total')) || {};
  const imvSub=rows.find(r=>(r.group||'').startsWith('Interim MV Sub-Total')) || {};
  const {cats}=monitoringSummary();
  const contractedTotal = totalRow.contracted || 596;
  const latestActualTotal = cats.reduce((s,c)=>s+c.latest,0);
  const uc=C.monitoring_unit_costs||{};

  p.append(el('div',{class:'kpis'},[
    kpi('계약 모니터링 Visit 총', nfmt(contractedTotal), 'WO v3 (SIV 11 · IMV 553 · COV 19 등)'),
    kpi('실적 (최신 스냅샷)', nfmt(latestActualTotal), snaps.length?('as of '+snaps[snaps.length-1]):''),
    kpi('IMV 계약', nfmt(imvSub.contracted||473), 'Interim MV 합계'),
    kpi('IMV 잔여', nfmt(imvSub.balance!=null?imvSub.balance:''), '계약 대비 남은 IMV'),
  ]));

  // trend: IMV 누적 실적 vs 계약
  if(snaps.length){
    const body=el('div',{},[ legend([{name:'IMV 누적 실적',color:'var(--s3)'},{name:`계약 (${imvSub.contracted||473})`,color:'var(--ink-3)'}]) ]);
    lineChart(body,{labels:snaps, series:[
      {name:'IMV 누적 실적',color:'var(--s3)',vals:(imvSub.actuals||[]).map(a=>a.total||0)},
      {name:'계약',color:'var(--ink-3)',dash:'5 4',vals:snaps.map(()=>imvSub.contracted||473)},
    ], yfmt:nfmt});
    p.append(card('TREND','Interim Monitoring Visit 누적 실적 vs 계약','스냅샷별 누적 IMV 수행 횟수',body));
  }
  // 계약 대비 카테고리 bar
  const catBody=el('div',{},[ legend([{name:'계약',color:'var(--s1)'},{name:'실적(최신)',color:'var(--s3)'}]) ]);
  barChart(catBody,{labels:cats.map(c=>c.name), series:[
    {name:'계약',color:'var(--s1)',vals:cats.map(c=>c.contracted)},
    {name:'실적(최신)',color:'var(--s3)',vals:cats.map(c=>c.latest)},
  ], yfmt:nfmt, height:240});
  p.append(card('TREND','카테고리별 계약 vs 실적','Site Selection · SIV · IMV · Co-IMV · COV',catBody));

  // D — 계약(모니터링)
  const dcols=[{k:'k',h:'모니터링 항목'},{k:'v',h:'단가(USD)',num:true}];
  const drows=[
    ['Site Initiation Visit (SIV)',uc.SIV],['Site Qualification Visit (SQV)',uc.SQV],['SQV by Phone',uc.SQV_phone],
    ['IMV — One-Day',uc.IMV_1day],['IMV — Two-Day',uc.IMV_2day],['Remote IMV — One-Day',uc.IMV_remote_1day],
    ['Remote IMV — Two-Day',uc.IMV_remote_2day],['Close-Out Visit (COV)',uc.COV],
    ['Monitoring Travel (per visit)',uc.Monitoring_Travel_per_visit],['Regulatory/IRB/EC fees (per site)',uc.Regulatory_IRB_EC_per_site],
  ].map(([k,v])=>({k,v:usd2(v)}));
  const psCols=[{k:'m',h:'예정월'},{k:'ms',h:'Milestone'},{k:'p',h:'%',num:true},{k:'a',h:'Net Amount(USD)',num:true}];
  const psRows=(C.payment_schedule||[]).map(x=>({m:x.month,ms:x.milestone,p:x.pct+'%',a:usd(x.amount),
    _cls: x.milestone==='Total'?'total':''}));
  const dWrap=el('div',{},[
    el('div',{class:'grid2'},[
      el('div',{},[el('h3',{class:'subh'},'모니터링 Visit 단가 (WO v3)'),tableFrom(dcols,drows)]),
      el('div',{},[el('h3',{class:'subh'},'지급 스케줄 (Attachment 4)'),tableFrom(psCols,psRows)]),
    ]),
  ]);
  p.append(card('D','IQVIA(CRO) 모니터링 계약 · 항목별 비용', `유효: ${C.effective_version} (eff. ${C.effective_date})`, dWrap));

  // E — CRA 경비 (데이터 대기)
  const ecaps=[
    ['교통비/여비 (Monitoring Travel)', usd2(uc.Monitoring_Travel_per_visit)+' / visit'],
    ['IRB/EC fees (Regulatory)', usd2(uc.Regulatory_IRB_EC_per_site)+' / site'],
    ['식비 (Meal)', '계약서 내 세부 rate 미확인'],
    ['숙박비 (Lodging)', '계약서 내 세부 rate 미확인'],
    ['Per Diem', '계약서 내 세부 rate 미확인'],
  ];
  const eBody=el('div',{},[
    el('div',{class:'note pending',html:'<span>⚠️</span><div><b>CRA 경비 상세(ER)는 데이터 대기 중:</b> CRA 이름·모니터링일·카테고리(식비/교통비/IRB/숙박비/Per Diem)·금액은 <code>CRA 모니터링 ER.xlsx</code>가 필요합니다. 파일을 주시면 아래 계약 단가와 대조해 금액 초과 여부를 음영으로, 그리고 F(방문일)와의 일치를 자동 검증합니다.</div>'}),
    el('h3',{class:'subh'},'검증 기준 (계약 단가) — 파일 수령 시 자동 대조'),
    tableFrom([{k:'k',h:'카테고리'},{k:'v',h:'계약 단가/상한'}], ecaps.map(([k,v])=>({k,v}))),
  ]);
  p.append(card('E','CRA 경비 (식비·교통·IRB·숙박·Per Diem)','CRA별 · 모니터링일별 경비 대조', eBody));

  // F — 모니터링 visit tracker (계약 대비, 음영)
  const fcols=[{k:'group',h:'카테고리'},{k:'act',h:'Activity'},{k:'con',h:'계약',num:true},
    ...snaps.map((s,i)=>({k:'s'+i,h:s,num:true})),{k:'bal',h:'잔여',num:true}];
  const frows=rows.map(r=>{
    const o={group:(r.activity?'':r.group)||'', act:r.activity||r.group||'', con:r.contracted!=null?nfmt(r.contracted):'',
      bal:r.balance!=null?nfmt(r.balance):'', _shade:{}};
    (r.actuals||[]).forEach((a,i)=>o['s'+i]=a.total!=null?nfmt(a.total):'');
    const isAgg=(r.group||'').startsWith('Interim MV Sub-Total')||(r.group||'').startsWith('Total');
    o._cls=isAgg?'subtotal':'';
    if(r.balance!=null){ o._shade.bal = r.balance<0?'crit':(r.balance===0?'warn':'good'); }
    return o;
  });
  const fBody=el('div',{},[
    el('div',{class:'note',html:'<span>ℹ️</span><div><b>음영:</b> 잔여 <span class="chip crit">음수</span> = 계약 초과, <span class="chip warn">0</span> = 소진, <span class="chip good">양수</span> = 잔여 있음. KR/US 분리 수치는 원본 파일에 포함.</div>'}),
    tableFrom(fcols,frows),
    el('div',{class:'note pending',style:'margin-top:12px',html:'<span>⚠️</span><div><b>CRA별·Site별 DOS 상세는 데이터 대기 중:</b> CRA 이름·site·방문일·DOS·모니터링 횟수 상세는 <code>CRA Site Visit Report.xlsx</code>가 필요합니다. 현재는 계약 대비 visit 잔여(집계)를 표시합니다.</div>'}),
  ]);
  p.append(card('F','모니터링 Visit Tracker (계약 대비 잔여)','SIV / IMV / COV · 스냅샷별 누적 실적', fBody, false));
}

/* ---------- shell ---------- */
function setTab(which){
  const fee=which==='fee';
  $('#tab-fee').setAttribute('aria-selected',fee); $('#tab-mon').setAttribute('aria-selected',!fee);
  $('#panel-fee').classList.toggle('hide',!fee); $('#panel-mon').classList.toggle('hide',fee);
}
$('#tab-fee').onclick=()=>setTab('fee'); $('#tab-mon').onclick=()=>setTab('mon');
$('#themeBtn').onclick=()=>{ const r=document.documentElement;
  const cur=r.getAttribute('data-theme')|| (matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');
  r.setAttribute('data-theme', cur==='dark'?'light':'dark'); };

$('#sub').textContent=`Protocol ${C.protocol||'TTK-CS-101'} · CRO ${C.vendor} · 계약번호 ${C.contract_number}`;
$('#effBadge').textContent=`유효 계약: ${C.effective_version} (eff. ${C.effective_date})`;
$('#foot').innerHTML=`데이터 소스: ${(DATA.sources||[]).map(s=>`<code>${s}</code>`).join(' · ')}<br>`+
  `누적 처리: <code>ingest.py</code>로 생성 · 새 IQVIA 파일을 <code>data/source/</code>에 추가 후 재실행하면 자동 누적됩니다.`;
renderFee(); renderMon();
