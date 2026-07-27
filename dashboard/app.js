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
function money(v, cur, dp){ if(v==null) return '—';
  if(cur==='KRW') return (v<0?'-₩':'₩')+Math.abs(v).toLocaleString('en-US',{maximumFractionDigits:0});
  return (v<0?'-$':'$')+Math.abs(v).toLocaleString('en-US',{minimumFractionDigits:dp==null?2:dp,maximumFractionDigits:dp==null?2:dp}); }
const normName = s => String(s||'').toLowerCase().replace(/[\s,]/g,'');
const C = DATA.contract;

/* ---------- contract refs / helpers ---------- */
const VERS=(C.versions||[]).filter(v=>v.effective_date).slice().sort((a,b)=>a.effective_date.localeCompare(b.effective_date));
function contractAt(date){ if(!date) return C.effective_version; let out=VERS[0]; for(const v of VERS){ if(v.effective_date<=date) out=v; } return out?out.version:C.effective_version; }
function daysBetween(a,b){ if(!a||!b) return 1e9; return Math.abs((new Date(a)-new Date(b))/86400000); }
function siteName(s){ const o=(DATA.sites||{})[String(s)]; return o&&o.name?o.name:''; }
function ctaList(site){ const sc=(DATA.site_cta||{}).sites||{}; return (sc[String(site)]||{}).ctas||[]; }
function ctaAt(site, date){ const arr=ctaList(site).filter(c=>c.effective_date).slice().sort((a,b)=>a.effective_date.localeCompare(b.effective_date));
  if(!arr.length) return null; if(!date) return arr[arr.length-1]; let out=null; for(const c of arr){ if(c.effective_date<=date) out=c; } return out||arr[0]; }
function realDate(d){ return (d && !String(d).startsWith('2000-01-01'))? d : ''; }
function parseVisit(v){ if(!v) return {label:'', order:99999};
  if(/screen/i.test(v)) return {label:'Screening', order:0};
  const m=String(v).match(/C(\d+)\s*[_ ]?D([0-9]+(?:_[0-9A-Za-z]+)?)/i);
  if(m){ const cyc=+m[1], dn=parseInt(m[2],10)||0; return {label:`C${cyc}D${m[2]}`, order:cyc*1000+dn}; }
  return {label:String(v).replace(/^BF\s*V[\d_]+_P\d+S\d+_?/,'').trim()||String(v), order:98000}; }
function qkey(d){ if(!d) return null; const y=+d.slice(0,4), m=+d.slice(5,7); return `${y} ${Math.floor((m-1)/3)+1}Q`; }

/* ---------- SVG charts ---------- */
const TT = $('#tt');
function showTT(html, ev){ TT.innerHTML=html; TT.style.opacity=1;
  const p=8, w=TT.offsetWidth, h=TT.offsetHeight; let x=ev.clientX+14, y=ev.clientY+14;
  if(x+w>innerWidth-p) x=ev.clientX-w-14; if(y+h>innerHeight-p) y=ev.clientY-h-14; TT.style.left=x+'px'; TT.style.top=y+'px'; }
function hideTT(){ TT.style.opacity=0; }
const SVGNS='http://www.w3.org/2000/svg';
const sv = (t,a={}) => { const n=document.createElementNS(SVGNS,t); for(const k in a) n.setAttribute(k,a[k]); return n; };
function barChart(host, {labels, series, yfmt=usd, height=260}){
  const W=Math.max(560, labels.length*Math.max(64, series.length*26+30)), H=height, m={t:16,r:14,b:46,l:64}, iw=W-m.l-m.r, ih=H-m.t-m.b;
  const max=Math.max(1,...series.flatMap(s=>s.vals.map(v=>v||0)));
  const svg=sv('svg',{viewBox:`0 0 ${W} ${H}`,width:W,height:H,role:'img'}); const g=sv('g',{transform:`translate(${m.l},${m.t})`}); svg.append(g);
  const gg=sv('g',{class:'grid'}); g.append(gg);
  for(let i=0;i<=4;i++){ const y=ih-ih*i/4; gg.append(sv('line',{x1:0,y1:y,x2:iw,y2:y,'stroke-width':1,opacity:i?.5:1}));
    const tx=sv('text',{x:-10,y:y+4,'text-anchor':'end','font-size':11}); tx.textContent=yfmt(max*i/4); g.append(tx); }
  const bw=iw/labels.length, inner=Math.min(bw-14, series.length*30), sw=inner/series.length;
  labels.forEach((lab,i)=>{ const x0=i*bw+(bw-inner)/2;
    series.forEach((s,si)=>{ const v=s.vals[i]||0, bh=Math.max(0, ih*v/max), x=x0+si*sw, y=ih-bh;
      const r=sv('rect',{x:x+2,y,width:Math.max(0,sw-4),height:bh,rx:4,fill:s.color}); r.style.cursor='pointer';
      r.addEventListener('mousemove',ev=>showTT(`<div class="tt-t">${lab}</div>${s.name}: <b>${yfmt(v)}</b>`,ev)); r.addEventListener('mouseleave',hideTT); g.append(r); });
    const tx=sv('text',{x:i*bw+bw/2,y:ih+18,'text-anchor':'middle','font-size':11}); tx.textContent=lab; g.append(tx); });
  const wrap=el('div',{class:'svg-wrap'}); wrap.append(svg); host.append(wrap);
}
function lineChart(host, {labels, series, yfmt=nfmt, height=260}){
  const W=Math.max(560, labels.length*90), H=height, m={t:16,r:18,b:40,l:56}, iw=W-m.l-m.r, ih=H-m.t-m.b;
  const max=Math.max(1,...series.flatMap(s=>s.vals.map(v=>v||0)));
  const svg=sv('svg',{viewBox:`0 0 ${W} ${H}`,width:W,height:H}); const g=sv('g',{transform:`translate(${m.l},${m.t})`}); svg.append(g);
  const gg=sv('g',{class:'grid'}); g.append(gg);
  for(let i=0;i<=4;i++){ const y=ih-ih*i/4; gg.append(sv('line',{x1:0,y1:y,x2:iw,y2:y,'stroke-width':1,opacity:i?.5:1}));
    const tx=sv('text',{x:-10,y:y+4,'text-anchor':'end','font-size':11}); tx.textContent=yfmt(max*i/4); g.append(tx); }
  const X=i=> labels.length<2?iw/2:iw*i/(labels.length-1);
  labels.forEach((lab,i)=>{ const tx=sv('text',{x:X(i),y:ih+18,'text-anchor':'middle','font-size':11}); tx.textContent=lab; g.append(tx); });
  series.forEach(s=>{ const pts=s.vals.map((v,i)=>[X(i), ih-ih*(v||0)/max]);
    const dd=pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+' '+p[1].toFixed(1)).join(' ');
    g.append(sv('path',{d:dd,fill:'none',stroke:s.color,'stroke-width':2.4,'stroke-dasharray':s.dash||'','stroke-linejoin':'round'}));
    pts.forEach((p,i)=>{ const c=sv('circle',{cx:p[0],cy:p[1],r:s.dash?0:4.5,fill:s.color,stroke:'var(--surface)','stroke-width':1.5});
      if(!s.dash){ c.style.cursor='pointer'; c.addEventListener('mousemove',ev=>showTT(`<div class="tt-t">${labels[i]}</div>${s.name}: <b>${yfmt(s.vals[i])}</b>`,ev)); c.addEventListener('mouseleave',hideTT);} g.append(c); }); });
  const wrap=el('div',{class:'svg-wrap'}); wrap.append(svg); host.append(wrap);
}
function legend(items){ return el('div',{class:'legend'}, items.map(it=>el('span',{},[el('span',{class:'dot',style:`background:${it.color}`}), it.name]))); }

/* ---------- reusable ---------- */
function card(tag, title, desc, bodyEl, flush){
  const head=el('div',{class:'head'},[ tag&&el('span',{class:'tag'},tag), el('h2',{},title), desc&&el('div',{class:'desc'},desc) ].filter(Boolean));
  return el('div',{class:'card'},[head, el('div',{class:'body'+(flush?' flush':'')},bodyEl)]);
}
function kpi(lab,val,meta,barPct){ return el('div',{class:'kpi'},[ el('div',{class:'lab'},lab), el('div',{class:'val tnum'},val),
  meta&&el('div',{class:'meta'},meta), barPct!=null&&el('div',{class:'bar'},el('i',{style:`width:${Math.min(100,barPct*100).toFixed(0)}%`})) ].filter(Boolean)); }
function tableFrom(cols, rows, opts={}){
  const thead=el('thead',{},el('tr',{},cols.map(c=>el('th',{class:c.num?'num':''},c.h))));
  const tbody=el('tbody',{}, rows.map(r=>{ const tr=el('tr',{class:r._cls||''});
    cols.forEach(c=>{ const cell=r[c.k]; const td=el('td',{class:(c.num?'num ':'')+(r._shade&&r._shade[c.k]?('shade-'+r._shade[c.k]):'')});
      if(cell&&cell.nodeType) td.append(cell); else td.textContent = cell==null?'':cell; tr.append(td); });
    return tr; }));
  return el('div',{class:'tbl-scroll'+(opts.tall?' tall':'')},el('table',{},[thead,tbody]));
}
function chip(cls,txt){ return el('span',{class:'chip '+cls},txt); }
function sum(arr,f){ return arr.reduce((s,x)=>s+(f(x)||0),0); }

/* =====================================================================
   연구비 TAB
===================================================================== */
function renderFee(){
  const p=$('#panel-fee'); p.innerHTML='';
  const env=C.payment_envelopes||{}, tm=C.tracker_meta||{};
  const st=(DATA.vendor_status||[]).find(v=>v.vendor==='IQVIA')||{};
  const fees=DATA.investigator_fees||[], invs=DATA.pass_through_invoices||[];
  const feeUSD=sum(fees.filter(x=>x.currency==='USD'),x=>x.amount);
  const feeKRW=sum(fees.filter(x=>x.currency==='KRW'),x=>x.amount);

  p.append(el('div',{class:'kpis'},[
    kpi('연구비 (Investigator Grants) 총액', usd(env.investigator_grants_total), 'WO v3 계약 · 대상자당 NA $43,174 / AP $37,442'),
    kpi('연구비 실지급 누계 (visit activity)', usd(feeUSD), `+ ₩${Math.round(feeKRW).toLocaleString()} · ${fees.length.toLocaleString()}건`),
    kpi('Invoiceable (Professional/Specialty)', usd(env.professional_specialty_max), 'WO v3 최대 (할인 후 Direct)'),
    kpi('IQVIA 지급 완료', usd(tm.paid_usd||st.paid), (st.pct_remaining!=null?`잔여 ${pct(st.pct_remaining)}`:''), tm.budget_usd?(tm.paid_usd/tm.budget_usd):null),
  ]));

  const q=(DATA.quarterly||[]).filter(x=>x.vendor==='IQVIA'&&(x.planned||x.actual)).sort((a,b)=>a.year-b.year||a.quarter-b.quarter);
  const cb=el('div',{},[legend([{name:'Planned',color:'var(--s1)'},{name:'Actual',color:'var(--s2)'}])]);
  barChart(cb, {labels:q.map(x=>`'${String(x.year).slice(2)} Q${x.quarter}`), series:[
    {name:'Planned',color:'var(--s1)',vals:q.map(x=>x.planned)},{name:'Actual',color:'var(--s2)',vals:q.map(x=>x.actual)}], yfmt:v=>'$'+(v/1e6).toFixed(v>=1e6?1:2)+'M'});
  p.append(card('TREND','분기별 지급 연구비 (IQVIA, USD)','계획 대비 실제 지급액 · 분기별',cb));

  renderA(p, fees, invs);
  renderB(p, fees, invs);
  renderC(p, fees, invs);
  renderWO(p);
}

/* A — 기관별 CTA & 지급 요약 (Site별) */
function renderA(p, fees, invs){
  const sites=[...new Set([...fees,...invs].map(x=>x.site).filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b)));
  const ctrl=el('div',{class:'controls'});
  const selSite=el('select',{}, sites.map(s=>el('option',{value:s},`Site ${s} — ${siteName(s)}`)));
  ctrl.append(el('span',{class:'small muted'},'Site:'),selSite);
  const holder=el('div',{});
  function draw(){ holder.innerHTML='';
    const s=selSite.value;
    const sf=fees.filter(x=>String(x.site)===s), si=invs.filter(x=>String(x.site)===s);
    const feeU=sum(sf.filter(x=>x.currency==='USD'),x=>x.amount), feeK=sum(sf.filter(x=>x.currency==='KRW'),x=>x.amount);
    const invU=sum(si.filter(x=>x.currency==='USD'),x=>x.amount), invK=sum(si.filter(x=>x.currency==='KRW'),x=>x.amount);
    const ctas=ctaList(s); const eff=ctaAt(s, null);
    let ctaTbl;
    if(ctas.length){
      const crows=ctas.slice().sort((a,b)=>String(a.effective_date).localeCompare(b.effective_date))
        .map(c=>({v:c.version, e:c.effective_date, n:(c.items||[]).length, _cls:(eff&&c.version===eff.version)?'eff':''}));
      ctaTbl=tableFrom([{k:'v',h:'CTA Version'},{k:'e',h:'Effective Date'},{k:'n',h:'항목 수',num:true}], crows);
    } else {
      ctaTbl=el('div',{class:'note pending',html:'<span>⚠️</span><div><b>이 site의 CTA 미입력:</b> <code>data/site_cta.json</code> 의 해당 site <code>ctas</code> 배열에 <code>{version, effective_date, items:[{item,amount}]}</code> 를 추가하면 A/B/C에 자동 반영됩니다.</div>'});
    }
    const qs={}; sf.forEach(x=>{ const k=qkey(x.payment_date); if(!k) return; (qs[k]=qs[k]||{fee:0,feeK:0,inv:0,dates:[]}); if(x.currency==='KRW') qs[k].feeK+=x.amount||0; else qs[k].fee+=x.amount||0; if(x.payment_date) qs[k].dates.push(x.payment_date); });
    si.forEach(x=>{ const k=qkey(x.payment_date); if(!k) return; (qs[k]=qs[k]||{fee:0,feeK:0,inv:0,dates:[]}); qs[k].inv=(qs[k].inv||0)+(x.currency==='KRW'?0:x.amount||0); });
    const qrows=Object.keys(qs).sort().map(k=>{ const o=qs[k]; const ds=o.dates.filter(Boolean).sort();
      return {q:k, pd: ds.length?(ds[0]+(ds[ds.length-1]!==ds[0]?' ~ '+ds[ds.length-1]:'')):'—',
        fee:(o.fee?('$'+Math.round(o.fee).toLocaleString()):'')+((o.fee&&o.feeK)?' / ':'')+(o.feeK?('₩'+Math.round(o.feeK).toLocaleString()):'')||'—',
        inv:o.inv?usd(o.inv):'—', _shade:{fee:'good'}}; });
    holder.append(el('div',{class:'kpis'},[
      kpi('Total Investigator fee (지급)', '$'+Math.round(feeU).toLocaleString(), feeK?`+ ₩${Math.round(feeK).toLocaleString()}`:''),
      kpi('Total Invoiceable (지급)', invU?('$'+Math.round(invU).toLocaleString()):('₩'+Math.round(invK).toLocaleString()), `${si.length}건`),
      kpi('현재 유효 CTA', eff?eff.version:'미입력', eff?('eff. '+eff.effective_date):'site_cta.json 입력'),
      kpi('대상자 / 방문', new Set(sf.map(x=>x.patient)).size+'명', new Set(sf.map(x=>x.patient+'|'+x.visit)).size+' 방문'),
    ]));
    holder.append(el('h3',{class:'subh'},'적용 CTA (기관 임상시험계약)')); holder.append(ctaTbl);
    holder.append(el('h3',{class:'subh'},'분기별 지급 (paid date 기준) — Investigator fee / Invoiceable'));
    holder.append(tableFrom([{k:'q',h:'분기'},{k:'pd',h:'Paid date'},{k:'fee',h:'Investigator fee',num:true},{k:'inv',h:'Invoiceable',num:true}], qrows));
  }
  selSite.onchange=draw; draw();
  p.append(card('A','기관별 계약(CTA) · 지급 요약', 'Site별 · Total Investigator fee · 분기별 · 적용 CTA', el('div',{},[ctrl,holder])));
}

/* B — 11-컬럼 원장 */
function renderB(p, fees, invs){
  const rows=[];
  fees.forEach(x=>{ const pv=parseVisit(x.visit); const c=ctaAt(x.site, x.payment_date||realDate(x.visit_date));
    rows.push({t:'Investigator fee', country:x.country, site:x.site, subj:x.patient, visit:pv.label, vdate:realDate(x.visit_date),
      desc:x.visit, amount:x.amount, cur:x.currency, cta:c, pdate:x.payment_date, order:pv.order}); });
  invs.forEach(x=>{ const c=ctaAt(x.site, x.payment_date);
    rows.push({t:'Invoice', country:x.country, site:x.site, subj:'', visit:'', vdate:'',
      desc:x.description, amount:x.amount, cur:x.currency, cta:c, pdate:x.payment_date, order:1e9}); });
  const sites=[...new Set(rows.map(r=>r.site).filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b)));
  const ctrl=el('div',{class:'controls'});
  const selSite=el('select',{},[el('option',{value:''},'모든 Site'),...sites.map(s=>el('option',{value:s},'Site '+s))]);
  const selType=el('select',{},[el('option',{value:''},'전체'),el('option',{value:'Investigator fee'},'Investigator fee'),el('option',{value:'Invoice'},'Invoice')]);
  const qq=el('input',{type:'search',placeholder:'검색 (대상자/설명/visit)'});
  const cnt=el('span',{class:'small muted'});
  ctrl.append(el('span',{class:'small muted'},'필터:'),selSite,selType,qq,el('span',{class:'spacer'}),cnt);
  const holder=el('div',{});
  const cols=[{k:'country',h:'Country'},{k:'sname',h:'site name'},{k:'site',h:'site #'},{k:'t',h:'Invoice/Investigator fee'},
    {k:'subj',h:'subject #'},{k:'visit',h:'Visit #'},{k:'vdate',h:'Visit date'},{k:'desc',h:'description'},
    {k:'amt',h:'Amount',num:true},{k:'cv',h:'effective CTA version'},{k:'ce',h:'CTA effective date'}];
  function draw(){ holder.innerHTML='';
    const fs=selSite.value, ft=selType.value, fq=qq.value.trim().toLowerCase();
    let rs=rows.filter(r=>(!fs||String(r.site)===fs)&&(!ft||r.t===ft)&&(!fq||[r.subj,r.desc,r.visit].some(v=>String(v||'').toLowerCase().includes(fq))));
    cnt.textContent=`${rs.length.toLocaleString()}건`;
    const rr=rs.slice(0,600).map(r=>{ const neg=r.amount<0;
      return {country:r.country, sname:siteName(r.site), site:r.site, t:chip(r.t==='Invoice'?'mute':'acc',r.t),
        subj:r.subj, visit:r.visit, vdate:r.vdate, desc:r.desc, amt:money(r.amount,r.cur),
        cv:r.cta?r.cta.version:'—', ce:r.cta?r.cta.effective_date:'—',
        _shade:{amt: neg?'warn':(r.pdate?'good':null), cv: r.cta?null:'warn'}}; });
    holder.append(tableFrom(cols,rr,{tall:true}));
    if(rs.length>600) holder.append(el('div',{class:'small muted',style:'padding:8px 12px'},`상위 600건 표시 (총 ${rs.length.toLocaleString()}). Site/검색으로 좁히세요.`));
  }
  selSite.onchange=draw; selType.onchange=draw; qq.oninput=draw; draw();
  const body=el('div',{},[
    el('div',{class:'note',html:'<span>ℹ️</span><div><b>연구비 원장</b> (템플릿 11컬럼). <b>effective CTA</b>는 방문/지급일 시점의 site CTA(<code>site_cta.json</code>). 음영: <span class="chip good">지급완료</span>/<span class="chip warn">조정·취소(음수)</span>, CTA 미입력 시 노랑.</div>'}),
    ctrl, holder ]);
  p.append(card('B','지급 원장 (Country · site · subject · visit · Amount · CTA)','연구비 + invoiceable 라인 상세', body, false));
}

/* C — 대상자 × 방문 매트릭스 */
function renderC(p, fees, invs){
  const idx={};
  fees.forEach(x=>{ if(!x.site||!x.patient) return; const pv=parseVisit(x.visit);
    const S=idx[x.site]=idx[x.site]||{}, P=S[x.patient]=S[x.patient]||{}, V=P[pv.label]=P[pv.label]||{u:0,k:0,dates:[],vdate:'',order:pv.order};
    if(x.currency==='KRW') V.k+=x.amount||0; else V.u+=x.amount||0;
    if(x.payment_date) V.dates.push(x.payment_date); if(!V.vdate) V.vdate=realDate(x.visit_date); });
  const sites=Object.keys(idx).sort((a,b)=>String(a).localeCompare(String(b)));
  const ctrl=el('div',{class:'controls'});
  const selSite=el('select',{}, sites.map(s=>el('option',{value:s},`Site ${s} — ${siteName(s)}`)));
  const selSubj=el('select',{});
  ctrl.append(el('span',{class:'small muted'},'Site:'),selSite,el('span',{class:'small muted'},'대상자:'),selSubj);
  const holder=el('div',{});
  function fillSubj(){ const P=idx[selSite.value]||{}; selSubj.innerHTML='';
    selSubj.append(el('option',{value:'*'},'전체 대상자')); Object.keys(P).sort().forEach(pt=>selSubj.append(el('option',{value:pt},pt))); }
  function subjBlock(site, pt){
    const P=(idx[site]||{})[pt]||{};
    const vis=Object.keys(P).map(l=>({l,...P[l]})).sort((a,b)=>a.order-b.order);
    const eff=ctaAt(site, null);
    const head=el('tr',{},[el('th',{},'Visit #'),...vis.map(v=>el('th',{class:'num'},v.l))]);
    function row(label, cellFn){ return el('tr',{}, [el('td',{style:'font-weight:650;color:var(--ink-2)'},label), ...vis.map(v=>cellFn(v))]); }
    const tb=el('tbody',{},[
      row('Visit date', v=>el('td',{class:'num'},v.vdate||'—')),
      row('effective CTA', v=>{ const c=ctaAt(site, (v.dates[0]||v.vdate)); return el('td',{class:'num'+(c?'':' shade-warn')}, c?c.version:'—'); }),
      row('CTA effective date', v=>{ const c=ctaAt(site,(v.dates[0]||v.vdate)); return el('td',{class:'num'}, c?c.effective_date:'—'); }),
      row('Investigator fee', v=>{ const str=(v.u?('$'+Math.round(v.u).toLocaleString()):'')+((v.u&&v.k)?' / ':'')+(v.k?('₩'+Math.round(v.k).toLocaleString()):''); const paid=v.dates.length>0;
        return el('td',{class:'num'+(paid?' shade-good':'')}, str||'—'); }),
      row('Invoiceable item', v=>el('td',{class:'num muted'},'—')),
      row('Paid date', v=>{ const ds=v.dates.filter(Boolean).sort(); return el('td',{class:'num'+(ds.length?' shade-good':'')}, ds[ds.length-1]||'—'); }),
    ]);
    const tbl=el('div',{class:'tbl-scroll'},el('table',{},[el('thead',{},head),tb]));
    return el('div',{style:'margin-bottom:18px'},[
      el('div',{class:'flex',style:'margin:4px 0 8px'},[el('span',{class:'chip acc'},pt),
        el('span',{class:'small muted'},`방문 ${vis.length} · Region ${(fees.find(f=>f.patient===pt)||{}).country||''}`),
        eff&&el('span',{class:'small muted'},`유효 CTA: ${eff.version}`)].filter(Boolean)),
      tbl ]);
  }
  function draw(){ holder.innerHTML='';
    const site=selSite.value, pt=selSubj.value;
    holder.append(el('div',{class:'note',html:'<span>ℹ️</span><div>열=Visit, 행=지표. <b>지급일(Paid date)·연구비 셀 음영</b> <span class="chip good">지급</span>. Invoiceable은 site 단위라 방문별 매핑 없음(B 원장 참조). effective CTA는 <code>site_cta.json</code> 입력 시 채워집니다.</div>'}));
    const P=idx[site]||{}; const pts= pt==='*'? Object.keys(P).sort() : [pt];
    pts.slice(0,15).forEach(x=>holder.append(subjBlock(site,x)));
    if(pt==='*'&&Object.keys(P).length>15) holder.append(el('div',{class:'small muted'},`상위 15명 표시 (총 ${Object.keys(P).length}명). 대상자를 선택하세요.`));
  }
  selSite.onchange=()=>{fillSubj();draw();}; selSubj.onchange=draw; fillSubj(); draw();
  p.append(card('C','기관 · 대상자 · 방문 매트릭스', 'Visit별 연구비·지급일·적용 CTA (지급일 음영)', el('div',{},[ctrl,holder]), false));
}

/* IQVIA WO 계약 참고 */
function renderWO(p){
  const vrows=(C.versions||[]).map(v=>({version:v.version,type:v.type,eff:v.effective_date,term:v.term,
    total: v.grand_total?usd(v.grand_total):'—', note:v.note, _cls: v.is_effective?'eff':''}));
  const brows=(C.wo_budget||[]).map(b=>({item:b.item,unit:b.unit||'',qty:b.qty!=null?nfmt(b.qty):'',
    uc:b.unit_cost!=null?usd2(b.unit_cost):'', tot:b.total!=null?usd(b.total):'',
    _cls:(b.kind==='section'?'sec':b.kind==='sub'?'sub':b.kind==='subtotal'?'subtotal':b.kind==='total'?'total':'')}));
  const aWrap=el('div',{},[
    el('h3',{class:'subh'},'IQVIA 계약(WO/CO) 버전 이력 — CRO 마스터 계약 (음영=현재 유효)'),
    tableFrom([{k:'version',h:'버전'},{k:'type',h:'유형'},{k:'eff',h:'Effective'},{k:'term',h:'기간'},{k:'total',h:'총액',num:true},{k:'note',h:'비고'}],vrows),
    el('h3',{class:'subh'},'WO v3 항목별 단가 (Attachment 2) — 연구비 단가: Investigator Payments NA/AP'),
    tableFrom([{k:'item',h:'항목'},{k:'unit',h:'Unit'},{k:'qty',h:'수량',num:true},{k:'uc',h:'단가(USD)',num:true},{k:'tot',h:'총액(USD)',num:true}],brows,{tall:true}),
  ]);
  p.append(card('참고','IQVIA WO 계약 (CRO 마스터 · 연구비 단가)', `${C.vendor} · 계약번호 ${C.contract_number}`, aWrap));
}

/* =====================================================================
   모니터링 TAB
===================================================================== */
function monitoringSummary(){
  const mv=DATA.monitoring_visits||{}; const rows=mv.rows||[]; const cats={}; const order=[];
  rows.forEach(r=>{ let gl=(r.group||'').trim();
    if(!gl||gl.startsWith('Interim MV Sub-Total')||gl==='Total') return;
    const name=gl.replace(/\s*\d+\s*$/,'').trim();
    if(!cats[name]){ cats[name]={name,contracted:0,latest:0,balance:0}; order.push(name); }
    cats[name].contracted += r.contracted||0;
    const last=(r.actuals||[])[(r.actuals||[]).length-1]; cats[name].latest += (last&&last.total)||0; cats[name].balance += r.balance||0; });
  return {cats:order.map(n=>cats[n])};
}
function renderMon(){
  const p=$('#panel-mon'); p.innerHTML='';
  const mv=DATA.monitoring_visits||{}; const rows=mv.rows||[]; const snaps=mv.snapshots||[];
  const totalRow=rows.find(r=>(r.group||'').startsWith('Total'))||{};
  const imvSub=rows.find(r=>(r.group||'').startsWith('Interim MV Sub-Total'))||{};
  const {cats}=monitoringSummary();
  const uc=C.monitoring_unit_costs||{};
  const cvis=DATA.cra_visits||[]; const cexp=DATA.cra_expenses||[];
  const completedCRA=cvis.filter(v=>(v.status||'').includes('Completed')).length;

  p.append(el('div',{class:'kpis'},[
    kpi('계약 모니터링 Visit 총', nfmt(totalRow.contracted||596), 'WO v3 (SIV 11 · IMV 553 · COV 19)'),
    kpi('CRA 수행 Visit (실적)', nfmt(cvis.length), `완료 ${completedCRA} · CRA Site Visit Report`),
    kpi('IMV 잔여', nfmt(imvSub.balance!=null?imvSub.balance:''), '계약 대비 남은 IMV'),
    kpi('CRA 경비 누계', usd(sum(cexp,x=>x.net_amount!=null?x.net_amount:x.amount)), `${cexp.length}건 · ER`),
  ]));

  if(snaps.length){ const body=el('div',{},[legend([{name:'IMV 누적 실적',color:'var(--s3)'},{name:`계약 (${imvSub.contracted||473})`,color:'var(--ink-3)'}])]);
    lineChart(body,{labels:snaps, series:[
      {name:'IMV 누적 실적',color:'var(--s3)',vals:(imvSub.actuals||[]).map(a=>a.total||0)},
      {name:'계약',color:'var(--ink-3)',dash:'5 4',vals:snaps.map(()=>imvSub.contracted||473)}], yfmt:nfmt});
    p.append(card('TREND','Interim Monitoring Visit 누적 실적 vs 계약','스냅샷별 누적 IMV 수행 횟수',body)); }
  const catBody=el('div',{},[legend([{name:'계약',color:'var(--s1)'},{name:'실적(최신)',color:'var(--s3)'}])]);
  barChart(catBody,{labels:cats.map(c=>c.name), series:[
    {name:'계약',color:'var(--s1)',vals:cats.map(c=>c.contracted)},{name:'실적(최신)',color:'var(--s3)',vals:cats.map(c=>c.latest)}], yfmt:nfmt, height:240});
  p.append(card('TREND','카테고리별 계약 vs 실적','Site Selection · SIV · IMV · Co-IMV · COV',catBody));

  const fcols=[{k:'group',h:'카테고리'},{k:'act',h:'Activity'},{k:'con',h:'계약',num:true},
    ...snaps.map((s,i)=>({k:'s'+i,h:s,num:true})),{k:'bal',h:'잔여',num:true}];
  const frows=rows.map(r=>{ const o={group:(r.activity?'':r.group)||'', act:r.activity||r.group||'', con:r.contracted!=null?nfmt(r.contracted):'',
      bal:r.balance!=null?nfmt(r.balance):'', _shade:{}};
    (r.actuals||[]).forEach((a,i)=>o['s'+i]=a.total!=null?nfmt(a.total):'');
    const isAgg=(r.group||'').startsWith('Interim MV Sub-Total')||(r.group||'').startsWith('Total'); o._cls=isAgg?'subtotal':'';
    if(r.balance!=null) o._shade.bal = r.balance<0?'crit':(r.balance===0?'warn':'good'); return o; });
  p.append(card('계약','계약 대비 Visit 잔여 (Visit Balance)','스냅샷별 누적 실적 · 잔여 음영', el('div',{},[
    el('div',{class:'note',html:'<span>ℹ️</span><div><b>음영:</b> 잔여 <span class="chip crit">음수</span>=계약 초과, <span class="chip warn">0</span>=소진, <span class="chip good">양수</span>=잔여.</div>'}),
    tableFrom(fcols,frows,{tall:true}) ]), false));

  const drows=[['Site Initiation Visit (SIV)',uc.SIV],['Site Qualification Visit (SQV)',uc.SQV],['SQV by Phone',uc.SQV_phone],
    ['IMV — One-Day',uc.IMV_1day],['IMV — Two-Day',uc.IMV_2day],['Remote IMV — One-Day',uc.IMV_remote_1day],
    ['Remote IMV — Two-Day',uc.IMV_remote_2day],['Close-Out Visit (COV)',uc.COV],
    ['Monitoring Travel (per visit)',uc.Monitoring_Travel_per_visit],['Regulatory/IRB/EC fees (per site)',uc.Regulatory_IRB_EC_per_site]].map(([k,v])=>({k,v:usd2(v)}));
  const psRows=(C.payment_schedule||[]).map(x=>({m:x.month,ms:x.milestone,p:x.pct+'%',a:usd(x.amount),_cls:x.milestone==='Total'?'total':''}));
  const dWrap=el('div',{},[el('div',{class:'grid2'},[
      el('div',{},[el('h3',{class:'subh'},'모니터링 Visit 단가 (WO v3)'),tableFrom([{k:'k',h:'항목'},{k:'v',h:'단가(USD)',num:true}],drows)]),
      el('div',{},[el('h3',{class:'subh'},'지급 스케줄 (Attachment 4)'),tableFrom([{k:'m',h:'예정월'},{k:'ms',h:'Milestone'},{k:'p',h:'%',num:true},{k:'a',h:'Net(USD)',num:true}],psRows,{tall:true})]) ])]);
  p.append(card('D','IQVIA(CRO) 모니터링 계약 · 항목별 비용', `유효: ${C.effective_version} (eff. ${C.effective_date})`, dWrap));

  renderE(p, cexp, cvis);
  renderF(p, cvis);
}

const ECAT_ORDER=['식비','교통비','숙박비','Per Diem','IRB/승인비','기타'];
function renderE(p, cexp, cvis){
  const cIdx={}; cvis.forEach(v=>{ const k=normName(v.cra); (cIdx[k]=cIdx[k]||[]).push(v.visit_start); });
  function fMatch(x){ const arr=cIdx[normName(x.cra)]; if(!arr) return 'warn';
    const d=x.visit_date||x.trans_date; return arr.some(vs=>daysBetween(vs,d)<=10)?'good':'warn'; }
  const catSum={}; ECAT_ORDER.forEach(c=>catSum[c]=0);
  cexp.forEach(x=>{ const g=x.group||'기타'; catSum[g]=(catSum[g]||0)+(x.net_amount!=null?x.net_amount:x.amount||0); });
  const chips=el('div',{class:'flex',style:'margin-bottom:12px'}, ECAT_ORDER.map(c=>
    el('span',{class:'kpi',style:'padding:9px 12px;flex-direction:row;gap:8px;align-items:baseline'},[
      el('span',{class:'lab',style:'text-transform:none'},c), el('span',{class:'val',style:'font-size:15px'},usd2(catSum[c]||0))])));
  const cras=[...new Set(cexp.map(x=>x.cra).filter(Boolean))].sort();
  const sites=[...new Set(cexp.map(x=>x.site).filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b)));
  const ctrl=el('div',{class:'controls'});
  const selCra=el('select',{},[el('option',{value:''},'모든 CRA'),...cras.map(s=>el('option',{value:s},s))]);
  const selSite=el('select',{},[el('option',{value:''},'모든 Site'),...sites.map(s=>el('option',{value:s},'Site '+s))]);
  const selCat=el('select',{},[el('option',{value:''},'모든 카테고리'),...ECAT_ORDER.map(s=>el('option',{value:s},s))]);
  const cnt=el('span',{class:'small muted'});
  ctrl.append(el('span',{class:'small muted'},'필터:'),selCra,selSite,selCat,el('span',{class:'spacer'}),cnt);
  const holder=el('div',{});
  const cols=[{k:'cra',h:'CRA'},{k:'site',h:'Site#'},{k:'cat',h:'카테고리'},{k:'reason',h:'Reason'},{k:'desc',h:'Description'},
    {k:'tdate',h:'Trans Date'},{k:'vdate',h:'Visit Date'},{k:'amt',h:'금액(USD)',num:true},{k:'fm',h:'F 일치'}];
  function draw(){ holder.innerHTML='';
    const rs=cexp.filter(x=>(!selCra.value||x.cra===selCra.value)&&(!selSite.value||String(x.site)===selSite.value)&&(!selCat.value||x.group===selCat.value));
    cnt.textContent=`${rs.length}건 · 합계 ${usd2(sum(rs,x=>x.net_amount!=null?x.net_amount:x.amount))}`;
    const rr=rs.map(x=>{ const fm=fMatch(x); const amt=x.net_amount!=null?x.net_amount:x.amount;
      const trav=x.group==='교통비'&&amt>(C.monitoring_unit_costs||{}).Monitoring_Travel_per_visit;
      return {cra:x.cra, site:x.site, cat:chip('acc',x.group), reason:x.reason, desc:x.description,
        tdate:x.trans_date||'', vdate:x.visit_date||'', amt:usd2(amt),
        fm: fm==='good'?chip('good','일치'):chip('warn','미확인'), _shade:{amt: trav?'warn':null, fm: fm}}; });
    holder.append(tableFrom(cols,rr,{tall:true}));
  }
  selCra.onchange=draw; selSite.onchange=draw; selCat.onchange=draw; draw();
  const body=el('div',{},[ chips,
    el('div',{class:'note',html:'<span>ℹ️</span><div><b>F 일치:</b> 해당 CRA·일자가 F(CRA Site Visit Report)의 방문(±10일)과 매칭되면 <span class="chip good">일치</span>, 아니면 <span class="chip warn">미확인</span>. <b>금액 음영:</b> 교통비가 계약 Monitoring Travel 단가(<b>$585/visit</b>)를 초과하면 노랑.</div>'}),
    ctrl, holder ]);
  p.append(card('E','CRA 경비 (식비·교통·IRB·숙박·Per Diem)','CRA별·site별 경비 · 계약/ F 대조', body, false));
}

function renderF(p, cvis){
  const piv={};
  cvis.forEach(v=>{ const k=(v.cra||'?')+'|'+(v.site||'?'); (piv[k]=piv[k]||{cra:v.cra,site:v.site,account:v.account,n:0,dos:0,types:{}});
    const o=piv[k]; o.n++; o.dos+=v.dos||0; o.types[v.visit_type]=(o.types[v.visit_type]||0)+1; });
  const pivRows=Object.values(piv).sort((a,b)=>String(a.cra).localeCompare(String(b.cra))||String(a.site).localeCompare(String(b.site)));
  const cras=[...new Set(cvis.map(v=>v.cra).filter(Boolean))].sort();
  const sites=[...new Set(cvis.map(v=>v.site).filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b)));
  const ctrl=el('div',{class:'controls'});
  const selCra=el('select',{},[el('option',{value:''},'모든 CRA'),...cras.map(s=>el('option',{value:s},s))]);
  const selSite=el('select',{},[el('option',{value:''},'모든 Site'),...sites.map(s=>el('option',{value:s},'Site '+s))]);
  const mode=el('select',{},[el('option',{value:'pivot'},'CRA×Site 요약'),el('option',{value:'detail'},'상세 방문')]);
  const cnt=el('span',{class:'small muted'});
  ctrl.append(el('span',{class:'small muted'},'보기:'),mode,el('span',{class:'small muted'},'필터:'),selCra,selSite,el('span',{class:'spacer'}),cnt);
  const holder=el('div',{});
  function draw(){ holder.innerHTML='';
    const fc=selCra.value, fs=selSite.value;
    if(mode.value==='pivot'){
      const rs=pivRows.filter(o=>(!fc||o.cra===fc)&&(!fs||String(o.site)===fs));
      cnt.textContent=`${rs.length} CRA×Site · 방문 ${sum(rs,o=>o.n)}건 · DOS ${sum(rs,o=>o.dos)}일`;
      const cols=[{k:'cra',h:'CRA'},{k:'site',h:'Site#'},{k:'account',h:'기관(Account)'},{k:'n',h:'방문수',num:true},{k:'dos',h:'DOS 합',num:true},{k:'types',h:'Visit Types'}];
      holder.append(tableFrom(cols, rs.map(o=>({cra:o.cra,site:o.site,account:o.account,n:o.n,dos:o.dos,
        types:Object.entries(o.types).map(([t,c])=>`${t}×${c}`).join(', ')})),{tall:true}));
    } else {
      const rs=cvis.filter(v=>(!fc||v.cra===fc)&&(!fs||String(v.site)===fs)).sort((a,b)=>String(b.visit_start||'').localeCompare(String(a.visit_start||'')));
      cnt.textContent=`${rs.length} 방문 · DOS ${sum(rs,v=>v.dos)}일`;
      const cols=[{k:'cra',h:'CRA'},{k:'site',h:'Site#'},{k:'account',h:'기관'},{k:'pi',h:'PI'},{k:'vt',h:'Visit Type'},
        {k:'status',h:'Status'},{k:'vs',h:'Visit Start'},{k:'ve',h:'Visit End'},{k:'dos',h:'DOS',num:true},{k:'rep',h:'Report'}];
      holder.append(tableFrom(cols, rs.slice(0,500).map(v=>({cra:v.cra,site:v.site,account:v.account,pi:v.pi,vt:v.visit_type,
        status:(v.status||'').includes('Completed')?chip('good',v.status):chip('mute',v.status||'—'),
        vs:v.visit_start||'',ve:v.visit_end||'',dos:v.dos,rep:v.report_status||''})),{tall:true}));
      if(rs.length>500) holder.append(el('div',{class:'small muted',style:'padding:8px 12px'},`상위 500건 표시 (총 ${rs.length}).`));
    }
  }
  mode.onchange=draw; selCra.onchange=draw; selSite.onchange=draw; draw();
  const body=el('div',{},[
    el('div',{class:'note',html:'<span>ℹ️</span><div><b>F = CRA Site Visit Report.</b> CRA(Monitor)·site·Visit Type·방문일(Visit Start)·<b>DOS(Days On Site)</b>·모니터링 횟수를 CRA별·site별로 집계합니다. 보기를 <b>상세 방문</b>으로 바꾸면 개별 방문 이력을 볼 수 있습니다.</div>'}),
    ctrl, holder ]);
  p.append(card('F','모니터링 Visit Tracker (CRA Site Visit Report)','CRA별·Site별 방문·DOS·횟수', body, false));
}

/* ---------- shell ---------- */
function setTab(which){ const fee=which==='fee';
  $('#tab-fee').setAttribute('aria-selected',fee); $('#tab-mon').setAttribute('aria-selected',!fee);
  $('#panel-fee').classList.toggle('hide',!fee); $('#panel-mon').classList.toggle('hide',fee); }
$('#tab-fee').onclick=()=>setTab('fee'); $('#tab-mon').onclick=()=>setTab('mon');
$('#themeBtn').onclick=()=>{ const r=document.documentElement;
  const cur=r.getAttribute('data-theme')||(matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light');
  r.setAttribute('data-theme', cur==='dark'?'light':'dark'); };
$('#sub').textContent=`Protocol ${C.protocol||'TTK-CS-101'} · CRO ${C.vendor} · 계약번호 ${C.contract_number}`;
$('#effBadge').textContent=`유효 계약: ${C.effective_version} (eff. ${C.effective_date})`;
$('#foot').innerHTML=`데이터 소스: ${(DATA.sources||[]).map(s=>`<code>${s}</code>`).join(' · ')}<br>`+
  `누적 처리: <code>ingest.py</code> · 새 IQVIA 파일을 <code>data/source/</code>에 추가 후 재실행하면 자동 누적됩니다.`;
renderFee(); renderMon();
