/* ------------------------------- Employee: Dashboard ------------------------------- */
const INTERVIEW_STATUSES = ['Interview Scheduled','Interview Completed','Technical Round','Manager Round','HR Round'];
const OFFER_STATUSES = ['Offer','Offer Released'];
const HIRED_STATUSES = ['Selected','Offer','Offer Released','Joined'];

function employeeDashboard(){
  const mine = state.referrals.filter(r=>r.referredBy===state.user.employeeId);
  const total = mine.length;
  const interview = mine.filter(r=>INTERVIEW_STATUSES.includes(r.status)).length;
  const selected = mine.filter(r=>HIRED_STATUSES.includes(r.status)).length;
  const rejected = mine.filter(r=>r.status==='Rejected').length;

  return `
  <div class="fade-up">
    <div style="display:flex;justify-content:space-between;align-items:end;margin-bottom:20px;flex-wrap:wrap;gap:12px;">
      <div>
        <h1 class="display" style="font-size:26px;margin:0 0 4px;">Welcome back, ${state.user.name.split(' ')[0]}</h1>
        <div style="font-size:13.5px;color:var(--text-secondary);">${new Date().toLocaleDateString('en-IN',{weekday:'long',day:'numeric',month:'long'})}</div>
      </div>
      <button class="btn btn-primary" data-nav="refer">Refer a Candidate</button>
    </div>

    ${mine.length===0 ? `
    <div class="glass" style="padding:40px;text-align:center;margin-top:18px;">
      <div style="width:48px;height:48px;border-radius:12px;background:rgba(37,99,235,0.1);color:var(--primary);margin:0 auto 12px;display:flex;align-items:center;justify-content:center;">${icon('refer',22)}</div>
      <h3 style="margin:0 0 6px;font-size:15px;">No referrals yet</h3>
      <p style="color:var(--text-secondary);font-size:13px;margin:0 0 14px;">Refer your first candidate and track their progress here.</p>
      <button class="btn btn-primary" data-nav="refer">Refer Your First Candidate</button>
    </div>` : ''}
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;${mine.length===0?'margin-top:16px;':''}">
      ${statCard('Total Referrals', total, 'referrals', GRADS[0])}
      ${statCard('In Interviews', interview, 'interview', GRADS[1])}
      ${statCard('Selected / Offers', selected, 'selected', GRADS[2])}
      ${statCard('Rejected', rejected, 'rejected', GRADS[3])}
    </div>
  </div>`;
}

/* Ordered pipeline levels used to build a real cumulative hiring funnel from
   live referral statuses (legacy round names are mapped into the same ladder). */
const FUNNEL_LEVELS = [
  { label:'Applied',        match:['Applied','Submitted'] },
  { label:'Resume Screening', match:['Resume Screening','HR Review'] },
  { label:'Shortlisted',    match:['Shortlisted'] },
  { label:'Interviewing',   match:['Interview Scheduled','Technical Round','Manager Round','HR Round'] },
  { label:'Interview Done', match:['Interview Completed'] },
  { label:'Offer',          match:['Selected','Offer','Offer Released'] },
  { label:'Joined',         match:['Joined'] },
];
function funnelCounts(referrals){
  const levelOf = r => {
    let lvl = -1;
    FUNNEL_LEVELS.forEach((l,i)=>{ if(l.match.includes(r.status)) lvl = i; });
    return lvl;
  };
  const reached = referrals.filter(r=>r.status!=='Rejected').map(levelOf).filter(l=>l>=0);
  // cumulative: how many candidates have reached (or passed) each stage
  return FUNNEL_LEVELS.map((_,i)=>reached.filter(l=>l>=i).length);
}

function chartColors(){ return ['#2563EB','#0891B2','#DC2626','#059669','#D97706','#7C3AED']; }
// Builds the last N month labels/keys ending this month, e.g. ['Feb','Mar',...,'Jul']
function lastMonths(n){
  const out = [];
  const now = new Date();
  for(let i=n-1;i>=0;i--){
    const d = new Date(now.getFullYear(), now.getMonth()-i, 1);
    out.push({ key: `${d.getFullYear()}-${d.getMonth()}`, label: d.toLocaleDateString('en-US',{month:'short'}) });
  }
  return out;
}
function monthlyCounts(referrals, months, dateField, filterFn){
  const buckets = Object.fromEntries(months.map(m=>[m.key,0]));
  referrals.forEach(r=>{
    if(filterFn && !filterFn(r)) return;
    const d = new Date(r[dateField]);
    if(!d || isNaN(d.getTime())) return;
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    if(key in buckets) buckets[key]++;
  });
  return months.map(m=>buckets[m.key]);
}
function chartCard(title, canvasId){
  return `
  <div class="glass chart-card" style="padding:18px 20px 14px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
      <h3 style="margin:0;font-size:13.5px;font-weight:700;">${title}</h3>
      <span class="chart-legend-dot" style="display:none;"></span>
    </div>
    <div class="chart-wrap">
      <div class="chart-load"><span class="chart-spinner"></span></div>
      <canvas id="${canvasId}" height="190"></canvas>
    </div>
  </div>`;
}

/* Registry of live Chart instances. Without this every re-render (polling runs
   every 9s) piled new charts onto the same canvases and Chart.js threw
   "Canvas is already in use" — leaving blank/broken analytics after refresh. */
const _liveCharts = {};
function destroyChart(canvasId){
  if(_liveCharts[canvasId]){
    try{ _liveCharts[canvasId].destroy(); }catch(e){ /* already gone */ }
    delete _liveCharts[canvasId];
  }
}

function drawCharts(){
  if(!window.Chart) return;
  const months = lastMonths(6);
  const monthLabels = months.map(m=>m.label);
  const gridColor = '#EEF2F7';
  const tooltip = {
    backgroundColor:'#0F172A', titleColor:'#F8FAFC', bodyColor:'#E2E8F0',
    padding:10, cornerRadius:8, boxPadding:6, titleFont:{size:12, weight:'700'}, bodyFont:{size:11.5}
  };

  const make = (canvasId, config)=>{
    const el = document.getElementById(canvasId);
    if(!el) return;
    destroyChart(canvasId);
    try{
      _liveCharts[canvasId] = new Chart(el, config);
      const box = el.closest('.chart-card');
      if(box){ const ld = box.querySelector('.chart-load'); if(ld) ld.remove(); }
    }catch(err){
      console.warn('Chart failed:', canvasId, err);
      const box = el.closest('.chart-card');
      if(box) box.innerHTML = '<div class="empty-note" style="padding:24px;text-align:center;color:var(--ink-soft);font-size:12.5px;">Chart unavailable.</div>';
    }
  };
  const emptyNote = (canvasId, note)=>{
    const el = document.getElementById(canvasId);
    if(!el) return;
    destroyChart(canvasId);
    const box = el.closest('.chart-card');
    if(box){
      box.querySelector('.chart-wrap').innerHTML =
        `<div style="min-height:170px;display:flex;align-items:center;justify-content:center;color:var(--ink-soft);font-size:12.5px;text-align:center;padding:12px;">${note}</div>`;
    }
  };

  const chartFunnel = document.getElementById('chartFunnel');
  if(chartFunnel){
    if(state.referrals.length===0){ emptyNote('chartFunnel','No referral data yet — the funnel fills as candidates enter the pipeline.'); }
    else{
      const counts = funnelCounts(state.referrals);
      const top = counts[0] || 1;
      make('chartFunnel', {
        type:'bar',
        data:{labels:FUNNEL_LEVELS.map(l=>l.label), datasets:[
          {label:'_spacer', data:counts.map(c=>(top-c)/2), backgroundColor:'transparent', barPercentage:1, categoryPercentage:0.8, hoverBackgroundColor:'transparent'},
          {label:'Candidates', data:counts, borderRadius:8, borderSkipped:false, barPercentage:1, categoryPercentage:0.8,
            backgroundColor: FUNNEL_LEVELS.map((_,i)=>`rgba(${['37,99,235','8,145,178','5,150,105','217,119,6','234,88,12','124,58,237','16,185,129'][i]},${(1 - i*0.11).toFixed(2)})`)}
        ]},
        options:{
          indexAxis:'y', responsive:true, maintainAspectRatio:false,
          plugins:{legend:{display:false}, tooltip:{...tooltip, callbacks:{
            label:(c)=>{ if(c.datasetIndex===0) return null; return ` ${c.raw} candidate${c.raw===1?'':'s'} · ${Math.round(c.raw/top*100)}% of applications`; }
          }}},
          scales:{ x:{stacked:true, beginAtZero:true, max:top, grid:{color:gridColor}, ticks:{precision:0, color:'#64748B', font:{size:10}}},
                   y:{stacked:true, grid:{display:false}, ticks:{color:'#334155', font:{size:11}, fontStyle:'bold'}} },
          animation:{duration:900, easing:'easeOutQuart'}
        }
      });
    }
  }

  const chartSource = document.getElementById('chartSource');
  if(chartSource){
    if(state.referrals.length===0){ emptyNote('chartSource','No referral data yet.'); }
    else{
      const rel = {};
      state.referrals.forEach(r=>{ const k = r.relationship || 'Unspecified'; rel[k] = (rel[k]||0)+1; });
      const labels = Object.keys(rel); const values = Object.values(rel);
      const total = values.reduce((a,b)=>a+b,0);
      const colors = ['#2563EB','#0891B2','#DC2626','#D97706','#059669','#7C3AED'];
      make('chartSource', {
        type:'doughnut',
        data:{labels, datasets:[{data:values, backgroundColor:labels.map((_,i)=>colors[i%colors.length]), borderColor:'#fff', borderWidth:2, hoverOffset:6}]},
        options:{
          responsive:true, maintainAspectRatio:false, cutout:'62%',
          plugins:{legend:{position:'bottom', labels:{boxWidth:10, boxHeight:10, usePointStyle:true, pointStyle:'circle', font:{size:11}, color:'#475569'}},
            tooltip:{...tooltip, callbacks:{label:(c)=>` ${c.label}: ${c.raw} (${Math.round(c.raw/total*100)}%)`}}},
          animation:{animateRotate:true, duration:900, easing:'easeOutQuart'}
        }
      });
    }
  }

  const chartJoining = document.getElementById('chartJoining');
  if(chartJoining){
    if(state.referrals.length===0){ emptyNote('chartJoining','No referral activity in the last 6 months.'); }
    else{
      const joined = state.referrals.filter(r=>r.status==='Joined');
      make('chartJoining', {
        type:'line',
        data:{labels:monthLabels, datasets:[
          {label:'Referrals received', data:monthlyCounts(state.referrals, months, 'submittedDate'),
            borderColor:'#2563EB', borderWidth:2.5, pointBackgroundColor:'#fff', pointBorderColor:'#2563EB', pointBorderWidth:2, pointRadius:4, pointHoverRadius:6,
            tension:0.45, fill:true,
            backgroundColor:(ctx)=>{ const {chart} = ctx; const {ctx:c, chartArea} = chart; if(!chartArea) return 'rgba(37,99,235,0.15)';
              const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
              g.addColorStop(0,'rgba(37,99,235,0.30)'); g.addColorStop(1,'rgba(37,99,235,0.02)'); return g; }},
          {label:'Joined', data:monthlyCounts(joined, months, 'submittedDate'),
            borderColor:'#10B981', borderWidth:2.5, pointBackgroundColor:'#fff', pointBorderColor:'#10B981', pointBorderWidth:2, pointRadius:4, pointHoverRadius:6,
            tension:0.45, fill:true,
            backgroundColor:(ctx)=>{ const {chart} = ctx; const {ctx:c, chartArea} = chart; if(!chartArea) return 'rgba(16,185,129,0.15)';
              const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
              g.addColorStop(0,'rgba(16,185,129,0.28)'); g.addColorStop(1,'rgba(16,185,129,0.02)'); return g; }}
        ]},
        options:{
          responsive:true, maintainAspectRatio:false,
          plugins:{legend:{position:'bottom', labels:{boxWidth:10, boxHeight:10, usePointStyle:true, pointStyle:'circle', font:{size:11}, color:'#475569'}}, tooltip:{...tooltip}},
          scales:{y:{beginAtZero:true, grid:{color:gridColor}, ticks:{precision:0, color:'#64748B', font:{size:10}}}, x:{grid:{display:false}, ticks:{color:'#64748B', font:{size:10}}}},
          animation:{duration:900, easing:'easeOutQuart'}
        }
      });
    }
  }

  const chartDeptHr = document.getElementById('chartDeptHr');
  if(chartDeptHr){
    if(state.referrals.length===0){ emptyNote('chartDeptHr','No department data yet.'); }
    else{
      const depts = {};
      state.referrals.forEach(r=>{
        const j = jobById(r.jobId);
        const d = (j && j.dept) || r.jobDept || 'Unknown';
        depts[d]=(depts[d]||0)+1;
      });
      const labels = Object.keys(depts); const values = Object.values(depts);
      const colors = chartColors();
      make('chartDeptHr', {
        type:'bar',
        data:{labels, datasets:[{label:'Referrals', data:values,
          backgroundColor: labels.map((_,i)=>colors[i%colors.length]), borderRadius:6, borderSkipped:false}]},
        options:{
          responsive:true, maintainAspectRatio:false,
          plugins:{legend:{display:false}, tooltip:{...tooltip}},
          scales:{y:{beginAtZero:true, grid:{color:gridColor}, ticks:{precision:0, color:'#64748B', font:{size:10}}}, x:{grid:{display:false}, ticks:{color:'#334155', font:{size:10}, maxRotation:0, autoSkip:true}}},
          animation:{duration:900, easing:'easeOutQuart'}
        }
      });
    }
  }
}

/* ------------------------------- HR / Admin: Dashboard ------------------------------- */
function hrDashboard(){
  const isAdmin = isAdminExperience(state.role);
  const total = state.referrals.length;
  const openRoles = state.jobs.length;
  const interviews = state.referrals.filter(r=>INTERVIEW_STATUSES.includes(r.status)).length;
  const offers = state.referrals.filter(r=>OFFER_STATUSES.includes(r.status)).length;
  const joined = state.referrals.filter(r=>r.status==='Joined').length;
  return `
  <div class="fade-up">
    <div style="display:flex;justify-content:space-between;align-items:end;margin-bottom:20px;flex-wrap:wrap;gap:12px;">
      <div><h1 class="display" style="font-size:26px;margin:0 0 4px;">${isAdmin?'Admin Dashboard':'HR Dashboard'}</h1><div style="font-size:13.5px;color:var(--ink-soft);">Org-wide referral performance, live.</div></div>
      <button class="btn btn-primary" data-nav="manageJobs">Post a Job</button>
    </div>
    ${total===0 ? `
    <div class="glass" style="padding:40px;text-align:center;margin-bottom:22px;">
      <div style="width:48px;height:48px;border-radius:12px;background:rgba(37,99,235,0.1);color:var(--primary);margin:0 auto 12px;display:flex;align-items:center;justify-content:center;">${icon('allReferrals',22)}</div>
      <h3 style="margin:0 0 6px;font-size:15px;">No candidates in the pipeline yet</h3>
      <p style="color:var(--text-secondary);font-size:13px;margin:0;">Once employees start referring candidates, live analytics will appear here.</p>
    </div>` : ''}
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:16px;margin-bottom:22px;">
      ${statCard('Total Referrals', total, 'referrals', GRADS[0])}
      ${statCard('Open Positions', openRoles, 'jobs', GRADS[1])}
      ${statCard('In Interviews', interviews, 'interview', GRADS[2])}
      ${statCard('Offers Extended', offers, 'offers', GRADS[3])}
      ${statCard('Joined', joined, 'joined', GRADS[4])}
    </div>
    <div id="pendingReviewsSection"></div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:16px;">
      ${chartCard('Hiring Pipeline Funnel', 'chartFunnel')}
      ${chartCard('Referral Source', 'chartSource')}
      ${chartCard('Monthly Joining Trend', 'chartJoining')}
      ${chartCard('Department-wise Referrals', 'chartDeptHr')}
    </div>
  </div>`;
}

async function bindPendingReviews(){
  const el = document.getElementById('pendingReviewsSection');
  if(!el) return;
  try {
    const data = await api('/api/referrals/pending-reviews');
    if(!data.total) return;
    const badge = (count, color, label) => count ? `<span class="pr-badge" style="background:${color}15;color:${color};">${label}: <strong>${count}</strong></span>` : '';
    el.innerHTML = `
    <div class="glass pr-section" style="padding:18px 20px;margin-bottom:22px;">
      <div class="pr-header">
        <div class="pr-header-left">
          <div class="pr-icon">${icon('clock',18)}</div>
          <div>
            <h3 style="margin:0;font-size:15px;font-weight:700;">Pending Referral Reviews</h3>
            <p style="margin:2px 0 0;font-size:12px;color:var(--ink-soft);">Referrals approaching their 7-day review deadline</p>
          </div>
        </div>
        <div class="pr-badges">
          ${badge(data.overdue.length,'#DC2626','Overdue')}
          ${badge(data.dueToday.length,'#DC2626','Due Today')}
          ${badge(data.dueTomorrow.length,'#D97706','Due Tomorrow')}
          ${badge(data.dueThisWeek.length,'#059669','Due This Week')}
        </div>
      </div>
      <div class="pr-list">
        ${[...data.overdue,...data.dueToday,...data.dueTomorrow,...data.dueThisWeek].slice(0,10).map(r => {
          const days = r.daysLeft;
          let statusColor, statusLabel;
          if(days < 0){ statusColor='#DC2626'; statusLabel='Overdue'; }
          else if(days < 1){ statusColor='#DC2626'; statusLabel='Due Today'; }
          else if(days < 2){ statusColor='#D97706'; statusLabel='Due Tomorrow'; }
          else if(days < 4){ statusColor='#D97706'; statusLabel=`Review Soon`; }
          else { statusColor='#059669'; statusLabel='On Track'; }
          const job = jobById(r.jobId);
          const emp = employeeById(r.referredBy);
          const deadline = r.reviewDeadline ? new Date(r.reviewDeadline).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}) : '—';
          return `<div class="pr-item" data-pr-ref="${r.id}" style="border-left:3px solid ${statusColor};">
            <div class="pr-item-main">
              <div class="pr-item-name">${r.candidateName}</div>
              <div class="pr-item-meta">${job?job.title:'—'} · Referred by ${emp?emp.name:'—'}</div>
            </div>
            <div class="pr-item-deadline">
              <span style="font-size:11px;color:var(--ink-soft);">Due: ${deadline}</span>
            </div>
            <span class="pr-item-status" style="background:${statusColor}15;color:${statusColor};">${statusLabel}</span>
          </div>`;
        }).join('')}
      </div>
    </div>`;

    document.querySelectorAll('[data-pr-ref]').forEach(item => {
      item.addEventListener('click', () => {
        nav('allReferrals');
      });
    });
  } catch(e) { /* silent */ }
}
