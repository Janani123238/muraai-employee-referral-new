/* ------------------------------- User Management (Admin) ------------------------------- */
function userManagementView(){
  return `
  <div class="fade-up">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;flex-wrap:wrap;gap:10px;">
      <h1 class="display" style="font-size:24px;margin:0;">User Management</h1>
      <button class="btn btn-primary" id="refreshUsersBtn">Refresh</button>
    </div>
    <div id="usersList"></div>
  </div>`;
}

/* ------------------------------- Referral Policy View (all roles editable by HR & Admin) ------------------------------- */
function policyMeta(){
  const at = state.policyUpdatedAt ? `${fmtRelative(state.policyUpdatedAt)} · ${fmtDate(state.policyUpdatedAt)}` : 'Not yet published';
  return { updatedAt: at, updatedBy: state.policyUpdatedBy || '—' };
}
function policyStats(){
  const sections = (state.policyContent||'').split(/(?=^\d+\.\s)/m).filter(b=>/^\d+\.\s/.test(b.trim())).length;
  const m = policyMeta();
  return [
    ['Publish status', `<span class="pol-status-dot"></span>Active`],
    ['Last updated', esc(m.updatedAt)],
    ['Updated by', esc(m.updatedBy)],
    ['Policy sections', String(sections)],
  ];
}
function policyMetaGridHtml(){
  return `<div class="pol-meta-grid">${policyStats().map(([l,v])=>`<div class="glass pol-meta"><div class="pol-meta-label">${l}</div><div class="pol-meta-val">${v}</div></div>`).join('')}</div>`;
}
function policyBodyHtml(text){
  let html=''; const list=[];
  const flush=()=>{ if(list.length){ html += `<ul class="pol-bullets">${list.map(l=>`<li><span class="pol-bullet"></span>${l}</li>`).join('')}</ul>`; list.length=0; } };
  for(const line of text.split('\n')){
    const t=line.trim();
    if(!t){ flush(); continue; }
    if(/^#{1,3}\s/.test(t)){
      flush();
      const lvl=t.match(/^#+/)[0].length;
      const title=esc(t.replace(/^#+\s*/,''));
      html += lvl===1 ? `<div class="pol-sub">${title}</div>` : `<div class="pol-micro">${title}</div>`;
    } else if(/^[-*•]\s+/.test(t)){
      list.push(esc(t.replace(/^[-*•]\s+/,'')));
    } else {
      flush();
      html += `<p class="pol-para">${esc(t)}</p>`;
    }
  }
  flush();
  return html;
}
function policyRender(content){
  const raw=(content||'').replace(/\r/g,'').trim();
  if(!raw) return `<div class="pol-empty"><div class="pol-empty-ic">${icon('fileText',20)}</div><div style="font-weight:600;font-size:14px;">No policy published yet</div><div style="font-size:12.5px;color:var(--text-secondary);margin-top:4px;">HR or an Admin can draft the referral policy here.</div></div>`;
  const blocks=raw.split(/(?=^\d+\.\s)/m).filter(Boolean);
  let out='';
  for(const b of blocks){
    const m=b.match(/^(\d+)\.\s*(.*?)(?:\n|$)/);
    if(m){
      const num=m[1];
      const title=esc(m[2]||'Section');
      const rest=b.slice(m[0].length);
      out += `<div class="pol-card fade-up"><div class="pol-card-head"><div class="pol-num">${num}</div><div class="pol-card-ttl">${title}</div></div><div class="pol-card-body">${policyBodyHtml(rest)}</div></div>`;
    } else {
      out += `<div class="pol-card fade-up"><div class="pol-card-body pol-card-body-standalone">${policyBodyHtml(b)}</div></div>`;
    }
  }
  return out;
}
function exportPolicyWord(){
  const content = state.policyContent || 'No referral policy has been set yet.';
  const blocks = content.split(/(?=^\d+\.\s)/m).filter(Boolean);
  let body = '';
  for(const b of blocks){
    const m = b.match(/^(\d+)\.\s*(.*?)(?:\n|$)/);
    if(m){
      body += `<p style='margin-top:16pt'><b><span style='font-size:14pt;color:#0F2A5C'>${esc(m[1])}. ${esc(m[2])}</span></b></p>`;
      const rest = b.slice(m[0].length);
      for(const line of rest.split('\n')){
        const t = line.trim();
        if(!t) continue;
        if(/^#{1,3}\s/.test(t)){
          body += `<p style='margin-top:10pt'><b><span style='font-size:11pt'>${esc(t.replace(/^#+\s*/,''))}</span></b></p>`;
        } else if(/^[-*•]\s+/.test(t)){
          body += `<p style='margin-left:20pt;margin-top:2pt'>&bull; ${esc(t.replace(/^[-*•]\s+/,''))}</p>`;
        } else {
          body += `<p style='margin-top:6pt'>${esc(t)}</p>`;
        }
      }
    } else {
      body += `<p style='margin-top:10pt'>${esc(b)}</p>`;
    }
  }
  const html = `<html xmlns:o='urn:schemas-microsoft-com:office:office'
    xmlns:w='urn:schemas-microsoft-com:office:word'
    xmlns='http://www.w3.org/TR/REC-html40'>
  <head><meta charset='utf-8'>
  <title>MuraAI Referral Policy</title>
  <style>
    body{font-family:Calibri,sans-serif;font-size:11pt;color:#0F172A;}
    p{margin:0;padding:0 0 2pt;}
  </style></head>
  <body>
    <h1 style='font-size:20pt;color:#0F2A5C;margin:0 0 6pt'>MuraAI Employee Referral Policy</h1>
    <p style='font-size:10pt;color:#64748B;margin:0 0 18pt'>Last updated: ${esc(policyMeta().updatedAt)}&ensp;|&ensp;Maintained by HR &amp; Admin</p>
    ${body}
  </body></html>`;
  const blob = new Blob([html], {type:'application/msword'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'Referral-Policy.doc';
  a.click();
  URL.revokeObjectURL(a.href);
  toast('Policy exported as Word document', 'success');
}
function policyView(){
  const canEdit = isHrRole(state.role);
  const meta = policyMeta();
  const secCount = Number(policyStats()[3][1]);
  return `
  <div class="fade-up pol-wrap">
    <div class="pol-head">
      <div>
        <div class="pol-kicker">HR · Employee Referrals</div>
        <h1 class="display" style="font-size:26px;margin:2px 0 4px;">Referral Policy</h1>
        <p style="color:var(--ink-soft);font-size:13px;margin:0;">Official guidelines, bonuses and rules for referring talent to MuraAI.</p>
      </div>
      <div class="pol-actions">
        <button class="btn btn-outline" id="exportPolicyBtn" title="Download the policy as a Word document">${icon('download',14)} Export Word</button>
        ${canEdit?`<button class="btn btn-primary" id="editPolicyBtn">${icon('pencil',14)} Edit Policy</button>`:''}
      </div>
    </div>

    <div class="pol-hero fade-up">
<div class="pol-hero-accent"></div>
      <div class="pol-hero-inner">
        <div class="pol-status"><span class="pol-status-dot"></span>Active and Published</div>
        <div class="pol-hero-title">MuraAI Employee Referral Program</div>
        <div class="pol-hero-sub">${secCount>0 ? `${secCount} policy sections · ${esc(meta.updatedAt)} · by ${esc(meta.updatedBy)}` : 'Draft policy — no sections yet'}</div>
      </div>
    </div>

    ${policyMetaGridHtml()}

    <div id="policyBody">${policyRender(state.policyContent)}</div>

    ${canEdit?`<div id="policyEditLayer" class="pol-edit-layer" hidden>
      <div class="pol-edit-sheet">
        <div class="pol-edit-head">
          <div class="pol-edit-title">${icon('pencil',15)} Edit referral policy</div>
          <div class="pol-edit-hint">Start a line with <b>1.</b> to add a policy section · <b># sub-heading</b> for sub-headings · <b>•</b> for bullet lists.</div>
        </div>
        <div class="pol-tools">
          <button class="btn btn-outline pol-tool" data-ins="# Sub-heading\n">${icon('hash',13)} Heading</button>
          <button class="btn btn-outline pol-tool" data-ins="- ">${icon('plus',13)} Bullet</button>
          <button class="btn btn-outline pol-tool" data-append="\n\n1. New policy section\nUse this area to describe the rule.">${icon('fileText',13)} Add section</button>
          <div class="pol-tools-spacer"></div>
          <span class="pol-wordcount" id="policyWordCount"></span>
        </div>
        <div class="pol-import" id="polImportBox" title="Import a policy document and auto-extract the text with OCR">
          <input type="file" id="polImportFile" accept=".pdf,.docx,.doc,.txt,.png,.jpg,.jpeg,.webp" hidden/>
          <div class="pol-import-ic" id="polImportIc">${icon('upload',18)}</div>
          <div class="pol-import-txt">
            <b>Import document</b>
            <span>Drop a <b>PDF, DOCX</b> or <b>image</b> here (or click to browse) — text is extracted automatically with OCR.</span>
          </div>
          <button class="btn btn-outline" id="polImportBtn">${icon('upload',14)} Browse</button>
        </div>
        <textarea class="input pol-editor" id="policyEditor" rows="16" spellcheck="false">${esc(state.policyContent)}</textarea>
        <div class="pol-edit-foot">
          <button class="btn btn-ghost pol-cancel" id="cancelPolicyBtn">Cancel</button>
          <button class="btn btn-primary" id="savePolicyBtn">${icon('check',14)} Save changes</button>
        </div>
      </div>
    </div>`:''}
  </div>`;
}
function bindPolicyView(){
  const canEdit = isHrRole(state.role);
  const editLayer = document.getElementById('policyEditLayer');
  const editBtn = document.getElementById('editPolicyBtn');

  const exportBtn = document.getElementById('exportPolicyBtn');
  if(exportBtn) exportBtn.addEventListener('click', exportPolicyWord);

  if(editBtn) editBtn.addEventListener('click', ()=>{
    editLayer.hidden = false;
    requestAnimationFrame(()=>editLayer.classList.add('pol-edit-show'));
    document.body.style.overflow = 'hidden';
    updatePolicyWordCount();
    const ed = document.getElementById('policyEditor');
    ed.focus(); ed.selectionStart = ed.selectionEnd = ed.value.length;
  });

  const updatePolicyWordCount = ()=>{
    const el = document.getElementById('policyWordCount');
    if(!el) return;
    const v = document.getElementById('policyEditor').value.trim();
    el.textContent = (v ? v.split(/\s+/).length : 0) + ' words';
  };

  document.querySelectorAll('.pol-tool').forEach(b=>{
    b.addEventListener('click', ()=>{
      const ed = document.getElementById('policyEditor');
      let at;
      if(b.dataset.insert!==undefined){
        at = ed.selectionStart;
        ed.value = ed.value.slice(0,at) + b.dataset.insert + ed.value.slice(at);
      } else {
        at = ed.value.length;
        const ins = (at && !/\n\n$/.test(ed.value)) ? (b.dataset.append || '') : (b.dataset.append||'').replace(/^\n\n/,'\n');
        ed.value = ed.value.slice(0,at) + ins + ed.value.slice(at);
      }
      updatePolicyWordCount();
      ed.focus(); ed.selectionStart = ed.selectionEnd = at + (b.dataset.insert||b.dataset.append||'').replace(/^\n\n/,'\n').length;
    });
  });

  const editor = document.getElementById('policyEditor');
  if(editor) editor.addEventListener('input', updatePolicyWordCount);

  const importBox = document.getElementById('polImportBox');
  const importInput = document.getElementById('polImportFile');
  const importBtn = document.getElementById('polImportBtn');
  const importIc = document.getElementById('polImportIc');
  const setImportBusy = (busy)=>{
    if(!importBox) return;
    importBox.classList.toggle('pol-import-busy', busy);
    if(importBtn){ importBtn.disabled = busy; importBtn.innerHTML = busy ? 'Extracting…' : `${icon('upload',14)} Browse`; }
    if(importIc) importIc.innerHTML = busy ? icon('loader',18) : icon('upload',18);
  };
  const doImport = async (file)=>{
    if(!file) return;
    const fd = new FormData();
    fd.append('file', file);
    setImportBusy(true);
    try{
      const r = await apiForm('/api/policy/import', fd);
      const text = (r.extractedText || '').trim();
      if(text.length < 20) throw new Error('Could not extract readable text from this file.');
      const ed = document.getElementById('policyEditor');
      ed.value = text;
      updatePolicyWordCount();
      toast('Text extracted from '+ (r.fileName || file.name) + ' (' + text.split(/\s+/).length + ' words)', 'success');
    }catch(e){
      toast('We couldn\u2019t import this document. Please try another file.', 'error');
    }
    setImportBusy(false);
    importInput.value = '';
  };
  if(importBtn) importBtn.addEventListener('click', ()=> importInput && importInput.click());
  if(importBox) importBox.addEventListener('click', (e)=>{ if(e.target.id!=='polImportBtn') importInput && importInput.click(); });
  if(importInput) importInput.addEventListener('change', ()=> doImport(importInput.files[0]));
  if(importBox){
    ['dragenter','dragover'].forEach(ev=> importBox.addEventListener(ev, (e)=>{ e.preventDefault(); e.stopPropagation(); importBox.classList.add('pol-import-over'); }));
    ['dragleave','drop'].forEach(ev=> importBox.addEventListener(ev, (e)=>{ e.preventDefault(); e.stopPropagation(); importBox.classList.remove('pol-import-over'); }));
    importBox.addEventListener('drop', (e)=>{ const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]; if(f) doImport(f); });
  }

  const cancelBtn = document.getElementById('cancelPolicyBtn');
  if(cancelBtn) cancelBtn.addEventListener('click', ()=>{
    document.getElementById('policyEditor').value = state.policyContent;
    editLayer.classList.remove('pol-edit-show');
    editLayer.setAttribute('hidden','');
    document.body.style.overflow = '';
  });

  const saveBtn = document.getElementById('savePolicyBtn');
  if(saveBtn) saveBtn.addEventListener('click', async ()=>{
    const content = document.getElementById('policyEditor').value.trim();
    if(content.length < 20){ toast('Policy must be at least 20 characters', 'amber'); return; }
    saveBtn.disabled = true; saveBtn.innerHTML = 'Saving…';
    try{
      const r = await api('/api/policy', {method:'PUT', body:{content}});
      state.policyContent = r.content || content;
      state.policyUpdatedAt = r.updatedAt;
      state.policyUpdatedBy = r.updatedBy;
      toast('Referral policy updated', 'success');
      const body = document.getElementById('policyBody');
      if(body) body.innerHTML = policyRender(state.policyContent);
      const grid = document.querySelector('.pol-meta-grid');
      if(grid) grid.outerHTML = policyMetaGridHtml();
      const heroSub = document.querySelector('.pol-hero-sub');
      if(heroSub){ const m=policyMeta(); const n=Number(policyStats()[3][1]); heroSub.textContent = n>0 ? `${n} policy sections · ${m.updatedAt} · by ${m.updatedBy}` : 'Draft policy — no sections yet'; }
    }catch(e){ toast('Could not save policy: '+e.message, 'error'); }
    saveBtn.disabled = false; saveBtn.innerHTML = `${icon('check',14)} Save changes`;
    if(cancelBtn) cancelBtn.click();
  });
}

/* ------------------------------- HR: Reports ------------------------------- */
function reportsView(){
  return `
  <div class="fade-up">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:10px;">
      <div><h1 class="display" style="font-size:24px;margin:0 0 4px;">Reports & Analytics</h1>
      <p style="color:var(--ink-soft);font-size:13px;margin:0;">Generate, export, and analyze referral data</p></div>
    </div>
    <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap;">
      <button class="btn btn-outline report-tab active" data-report="referral">Referral Report</button>
      <button class="btn btn-outline report-tab" data-report="interview">Interview Report</button>
      <button class="btn btn-outline report-tab" data-report="offer">Offer Report</button>
      <button class="btn btn-outline report-tab" data-report="joining">Joining Report</button>
      <button class="btn btn-outline report-tab" data-report="hiring">Hiring Analytics</button>
    </div>
    <div class="glass" style="padding:16px;margin-bottom:16px;">
      <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:end;">
        <div><label class="field-label">Start Date</label><input class="input" type="date" id="reportStartDate" style="width:160px;"/></div>
        <div><label class="field-label">End Date</label><input class="input" type="date" id="reportEndDate" style="width:160px;"/></div>
        <div><label class="field-label">Department</label><input class="input" id="reportDept" placeholder="All" style="width:140px;"/></div>
        <div><label class="field-label">Status</label>
          <select class="input" id="reportStatus" style="width:140px;"><option value="">All</option>${PIPELINE_STAGES.concat('Rejected').map(s=>`<option>${s}</option>`).join('')}</select>
        </div>
        <button class="btn btn-primary" id="generateReportBtn">Generate</button>
        <button class="btn btn-outline" id="exportExcelBtn" title="Download as Excel (.xlsx)">Export Excel (.xlsx)</button>
        <button class="btn btn-outline" id="exportPdfBtn" title="Download as PDF">Export PDF</button>
        <div style="position:relative;display:inline-block;">
          <button class="btn btn-outline" id="downloadJdBtn" title="Download Job Description" style="display:flex;align-items:center;gap:5px;">${icon('download',14)} Download JD</button>
          <div id="jdDropdown" class="glass-strong" style="display:none;position:absolute;right:0;top:calc(100% + 4px);min-width:320px;padding:10px;z-index:30;max-height:400px;overflow-y:auto;">
            <div style="font-size:12px;font-weight:700;color:var(--ink);padding:4px 6px 8px;">Select Job Position</div>
            <div id="jdJobList" style="margin-bottom:8px;"><div style="font-size:12px;color:var(--ink-soft);padding:6px;">Loading jobs…</div></div>
          </div>
        </div>
      </div>
    </div>
    <div id="reportOutput"></div>
  </div>`;
}
function bindReportsView(){
  let activeReport = 'referral';
  document.querySelectorAll('.report-tab').forEach(tab=>{
    tab.addEventListener('click', ()=>{
      document.querySelectorAll('.report-tab').forEach(t=>{t.classList.remove('active');t.style.background='';t.style.color='';});
      tab.classList.add('active');
      activeReport = tab.dataset.report;
    });
  });
  document.querySelector('.report-tab.active')?.click();

  document.getElementById('generateReportBtn')?.addEventListener('click', async ()=>{
    const output = document.getElementById('reportOutput');
    output.innerHTML = `<div class="glass" style="padding:20px;"><div class="shimmer" style="height:80px;border-radius:12px;"></div></div>`;
    const filters = {
      startDate: document.getElementById('reportStartDate').value || null,
      endDate: document.getElementById('reportEndDate').value || null,
      dept: document.getElementById('reportDept').value || null,
      status: document.getElementById('reportStatus').value || null,
    };
    try{
      const endpoint = activeReport==='hiring'?'/api/reports/hiring-analytics':'/api/reports/referral-report';
      const data = await api(endpoint, {method:'POST', body:filters});
      if(activeReport==='referral'||activeReport==='interview'||activeReport==='offer'||activeReport==='joining'){
        let filtered = data.results||[];
        if(activeReport==='interview') filtered=filtered.filter(r=>['Technical Round','Manager Round','HR Round'].includes(r.status));
        else if(activeReport==='offer') filtered=filtered.filter(r=>r.status==='Offer');
        else if(activeReport==='joining') filtered=filtered.filter(r=>r.status==='Joined');
        const summary = data.summary || {};
        output.innerHTML = `
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin-bottom:16px;">
          ${statCard('Total Referrals', filtered.length, 'referrals', GRADS[0])}
          ${statCard('Avg JD vs Resume Match', filtered.length? Math.round(filtered.reduce((s,r)=>s+(r.matchPercent||0),0)/filtered.length)+'%':'—', 'match', GRADS[1])}
        </div>
        <div class="glass" style="padding:6px;overflow-x:auto;">
          <table class="data-table">
            <thead><tr><th>Candidate</th><th>Job</th><th>Department</th><th>Referred By</th><th>JD vs Resume Match</th><th>Status</th><th>Date</th></tr></thead>
            <tbody>${filtered.map(r=>`<tr>
              <td><strong>${r.candidateName}</strong></td><td>${r.jobTitle}</td><td>${r.department}</td><td>${r.referredBy}</td>
              <td>${r.matchPercent||'—'}%</td>
              <td><span class="chip" style="background:${statusColor(r.status)}22;color:${statusColor(r.status)};">${r.status}</span></td>
              <td style="font-size:12px;color:var(--ink-soft);">${fmtRelative(r.submittedDate)}</td>
            </tr>`).join('')}</tbody>
          </table>
        </div>`;
      } else if(activeReport==='hiring'){
        output.innerHTML = `
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin-bottom:16px;">
          ${statCard('Total Referrals', data.totalReferrals||0, 'referrals', GRADS[0])}
          ${statCard('Joined', data.joined||0, 'joined', GRADS[2])}
          ${statCard('Conversion Rate', (data.conversionRate||0)+'%', 'conversion', GRADS[1])}
          ${statCard('Active Employees', data.activeEmployees||0, 'active', GRADS[5])}
        </div>
        <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;">
          <div class="glass" style="padding:16px;">
            <h4 style="margin:0 0 10px;font-size:13.5px;">By Department</h4>
            ${(Object.entries(data.byDepartment||{})).map(([k,v])=>`<div style="display:flex;justify-content:space-between;padding:6px 0;font-size:12.5px;border-bottom:1px solid rgba(226,232,240,0.08);"><span>${k}</span><span class="mono" style="font-weight:700;">${v}</span></div>`).join('')||'<div style="font-size:12.5px;color:var(--ink-soft);">No data.</div>'}
          </div>
          <div class="glass" style="padding:16px;">
            <h4 style="margin:0 0 10px;font-size:13.5px;">Top Referrers</h4>
            ${(Object.entries(data.topReferrers||{})).map(([k,v])=>`<div style="display:flex;justify-content:space-between;padding:6px 0;font-size:12.5px;border-bottom:1px solid rgba(226,232,240,0.08);"><span>${k}</span><span class="mono" style="font-weight:700;">${v}</span></div>`).join('')||'<div style="font-size:12.5px;color:var(--ink-soft);">No data.</div>'}
          </div>
        </div>`;
      }
    }catch(e){ output.innerHTML=''; toast('Could not generate report: '+e.message, 'error'); }
  });

  async function exportReport(format){
    const filters = {
      startDate: document.getElementById('reportStartDate').value || null,
      endDate: document.getElementById('reportEndDate').value || null,
      dept: document.getElementById('reportDept').value || null,
      status: document.getElementById('reportStatus').value || null,
    };
    try{
      const res = await fetch(API_BASE + '/api/reports/export', {
        method:'POST',
        headers:{'Content-Type':'application/json', Authorization:'Bearer '+(getToken()||'')},
        body: JSON.stringify({reportType: activeReport, format, filters}),
      });
      if(res.status === 401){
        clearToken(); state.user=null; state.role=null; render();
        throw new Error('Session expired. Please sign in again.');
      }
      if(!res.ok){
        let data=null; try{ data = await res.json(); }catch(e){}
        throw new Error((data && (data.detail || data.message)) || `We couldn\u2019t export the report (${res.status}).`);
      }
      const blob = await res.blob();
      const disposition = res.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?([^";]+)"?/);
      const filename = (match && match[1]) || `muraai-report.${format==='xlsx'?'xlsx':'pdf'}`;
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = filename;
      a.click();
      URL.revokeObjectURL(a.href);
      toast(`${format.toUpperCase()} downloaded`, 'success');
    }catch(e){ toast('We couldn\u2019t export the report. '+e.message, 'error'); }
  }
  document.getElementById('exportExcelBtn')?.addEventListener('click', ()=>exportReport('xlsx'));
  document.getElementById('exportPdfBtn')?.addEventListener('click', ()=>exportReport('pdf'));

  /* ---- Download JD dropdown ---- */
  const jdBtn = document.getElementById('downloadJdBtn');
  const jdDropdown = document.getElementById('jdDropdown');
  const jdJobList = document.getElementById('jdJobList');
  let jdJobsLoaded = false;

  if(jdBtn && jdDropdown){
    jdBtn.addEventListener('click', async (e)=>{
      e.stopPropagation();
      const isVisible = jdDropdown.style.display !== 'none';
      jdDropdown.style.display = isVisible ? 'none' : 'block';
      if(!isVisible && !jdJobsLoaded){
        jdJobList.innerHTML = '<div style="font-size:12px;color:var(--ink-soft);padding:6px;">Loading jobs…</div>';
        try{
          const jobs = await api('/api/reports/jobs');
          if(!jobs || jobs.length === 0){
            jdJobList.innerHTML = '<div style="font-size:12px;color:var(--ink-soft);padding:8px;">No job postings found.</div>';
          } else {
            jdJobList.innerHTML = jobs.map(j => `
              <div style="padding:8px 6px;border-bottom:1px solid rgba(226,232,240,0.1);cursor:pointer;border-radius:6px;transition:background 0.15s;" class="jd-job-item" data-job-id="${j.id}" data-job-title="${esc(j.title)}">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                  <div>
                    <div style="font-size:12.5px;font-weight:600;color:var(--ink);">${esc(j.title)}</div>
                    <div style="font-size:11px;color:var(--ink-soft);margin-top:1px;">${esc(j.dept || 'General')} &middot; ${esc(j.location || 'Remote')}</div>
                  </div>
                  <div style="display:flex;gap:4px;">
                    <button class="btn btn-ghost jd-dl-btn" data-job-id="${j.id}" data-job-title="${esc(j.title)}" data-format="pdf" style="font-size:11px;padding:3px 8px;color:var(--primary);">PDF</button>
                    <button class="btn btn-ghost jd-dl-btn" data-job-id="${j.id}" data-job-title="${esc(j.title)}" data-format="docx" style="font-size:11px;padding:3px 8px;color:var(--teal,#0F766E);">Word</button>
                  </div>
                </div>
              </div>
            `).join('');
            jdJobsLoaded = true;
            bindJdDownloadButtons();
          }
        }catch(e){
          jdJobList.innerHTML = '<div style="font-size:12px;color:var(--coral);padding:8px;">We couldn\u2019t load the jobs. ' + e.message + '</div>';
        }
      }
    });
    document.addEventListener('click', ()=>{
      if(jdDropdown) jdDropdown.style.display = 'none';
    });
    jdDropdown.addEventListener('click', (e)=> e.stopPropagation());
  }

  function bindJdDownloadButtons(){
    document.querySelectorAll('.jd-dl-btn').forEach(btn => {
      btn.addEventListener('click', async (e)=>{
        e.stopPropagation();
        const jobId = btn.dataset.jobId;
        const jobTitle = btn.dataset.jobTitle;
        const format = btn.dataset.format;
        if(!jobId) return;
        btn.disabled = true;
        const origText = btn.textContent;
        btn.textContent = '…';
        try{
          const res = await fetch(API_BASE + '/api/reports/jd-download/' + encodeURIComponent(jobId) + '?format=' + format, {
            method: 'GET',
            headers: { Authorization: 'Bearer ' + (getToken() || '') },
          });
          if(res.status === 401){
            clearToken(); state.user = null; state.role = null; render();
            throw new Error('Session expired. Please sign in again.');
          }
          if(!res.ok){
            let data = null;
            try { data = await res.json(); } catch(ex){}
            throw new Error((data && (data.detail || data.message)) || 'We couldn\u2019t download the document. Please try again.');
          }
          const blob = await res.blob();
          const disposition = res.headers.get('Content-Disposition') || '';
          const match = disposition.match(/filename="?([^";]+)"?/);
          const filename = (match && match[1]) || ('MuraAI_JD_' + (jobTitle || 'Job').replace(/\s+/g, '_') + (format === 'pdf' ? '.pdf' : '.docx'));
          const a = document.createElement('a');
          a.href = URL.createObjectURL(blob);
          a.download = filename;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(a.href);
          toast('JD downloaded as ' + format.toUpperCase(), 'success');
          if(jdDropdown) jdDropdown.style.display = 'none';
        }catch(e){
          toast('We couldn\u2019t download the document. '+e.message, 'error');
        }
        btn.disabled = false;
        btn.textContent = origText;
      });
    });
  }
}

/* ------------------------------- Admin: Config Settings ------------------------------- */
function adminSettingsView(){
  const s = state.settings;
  return `
  <div class="fade-up" style="max-width:680px;">
    <h1 class="display" style="font-size:24px;margin:0 0 6px;">Admin Settings</h1>
    <p style="color:var(--ink-soft);font-size:13px;margin:0 0 18px;">Configure AI provider, model, API keys, OCR, and email settings.</p>
    <div class="glass" style="padding:22px;margin-bottom:16px;">
      <h3 style="margin:0 0 14px;font-size:15px;">AI Provider Settings</h3>
      <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;">
        <div><label class="field-label">AI Provider</label>
          <select class="input" id="cfgAiProvider">
            <option value="ollama" ${s.aiProvider==='ollama'?'selected':''}>Ollama (Local)</option>
            <option value="openai" ${s.aiProvider==='openai'?'selected':''}>OpenAI</option>
            <option value="anthropic" ${s.aiProvider==='anthropic'?'selected':''}>Anthropic (Claude)</option>
            <option value="gemini" ${s.aiProvider==='gemini'?'selected':''}>Google Gemini</option>
          </select>
        </div>
        <div><label class="field-label">Model Name</label><input class="input" id="cfgAiModel" value="${s.aiModel||'llama3.2'}"/></div>
        <div style="grid-column:1/-1;"><label class="field-label">API Key (leave blank for local Ollama)</label><input class="input" id="cfgAiApiKey" type="password" value="${s.aiApiKey||''}" placeholder="sk-..."/></div>
        <div><label class="field-label">Temperature: <span class="mono" id="cfgTempVal">${s.aiTemperature||0.2}</span></label>
          <input class="input" id="cfgAiTemp" type="range" min="0" max="1" step="0.05" value="${s.aiTemperature||0.2}" style="padding:0;border:none;"/></div>
        <div><label class="field-label">Max Tokens</label><input class="input" id="cfgAiTokens" type="number" value="${s.aiMaxTokens||1000}"/></div>
      </div>
    </div>
    <div class="glass" style="padding:22px;margin-bottom:16px;">
      <h3 style="margin:0 0 14px;font-size:15px;">OCR Settings</h3>
      <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;">
        <div><label class="field-label">OCR Enabled</label>
          <label style="display:flex;align-items:center;gap:8px;margin-top:4px;">
            <input type="checkbox" id="cfgOcrEnabled" ${s.ocrEnabled?'checked':''}/> Enable OCR for scanned resumes
          </label>
        </div>
        <div><label class="field-label">OCR Language</label>
          <select class="input" id="cfgOcrLang">
            <option value="eng" ${s.ocrLanguage==='eng'?'selected':''}>English</option>
            <option value="hin" ${s.ocrLanguage==='hin'?'selected':''}>Hindi</option>
            <option value="eng+hin" ${s.ocrLanguage==='eng+hin'?'selected':''}>English + Hindi</option>
          </select>
        </div>
      </div>
    </div>
    <div class="glass" style="padding:22px;margin-bottom:16px;">
      <h3 style="margin:0 0 14px;font-size:15px;">Email Configuration (Microsoft Graph)</h3>
      <p style="font-size:12px;color:var(--ink-soft);margin:0 0 12px;">Emails are sent exclusively through Microsoft Graph using your Azure app credentials and the sending mailbox (<code>MAIL_FROM</code>) configured in the backend <code>.env</code>. SMTP is not used.</p>
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
        <button class="btn btn-outline" id="testSmtpBtn">Test Microsoft Graph Connection</button>
        <span id="smtpTestResult" style="font-size:12.5px;"></span>
      </div>
    </div>
    <div style="display:flex;gap:10px;">
      <button class="btn btn-primary" id="saveAdminConfigBtn">Save Configuration</button>
    </div>
  </div>`;
}
function bindAdminSettings(){
  const tempSlider = document.getElementById('cfgAiTemp');
  const tempVal = document.getElementById('cfgTempVal');
  if(tempSlider && tempVal) tempSlider.addEventListener('input', ()=>{ tempVal.textContent = tempSlider.value; });

  const testSmtpBtn = document.getElementById('testSmtpBtn');
  if(testSmtpBtn) testSmtpBtn.addEventListener('click', async ()=>{
    const resultEl = document.getElementById('smtpTestResult');
    if(!resultEl) return;
    testSmtpBtn.disabled = true;
    resultEl.innerHTML = `<span style="color:var(--ink-soft);">Testing Microsoft Graph connection…</span>`;
    try{
      const r = await api('/api/settings/test-smtp', {method:'POST'});
      if(r.ok){
        resultEl.innerHTML = `<span style="color:#059669;font-weight:600;">&#10004; ${r.message}</span>`;
      } else {
        resultEl.innerHTML = `<span style="color:var(--coral);">&#10008; ${r.message}</span>`;
      }
    }catch(e){
      resultEl.innerHTML = `<span style="color:var(--coral);">We couldn\u2019t reach Microsoft Graph. Please check configuration and retry.</span>`;
    }
    testSmtpBtn.disabled = false;
  });

  document.getElementById('saveAdminConfigBtn')?.addEventListener('click', async ()=>{
    const btn = document.getElementById('saveAdminConfigBtn');
    btn.disabled=true; btn.textContent='Saving…';
    const patch = {
      aiProvider: document.getElementById('cfgAiProvider').value,
      aiModel: document.getElementById('cfgAiModel').value,
      aiApiKey: document.getElementById('cfgAiApiKey').value,
      aiTemperature: parseFloat(document.getElementById('cfgAiTemp').value),
      aiMaxTokens: parseInt(document.getElementById('cfgAiTokens').value,10),
      ocrEnabled: document.getElementById('cfgOcrEnabled').checked,
      ocrLanguage: document.getElementById('cfgOcrLang').value,
    };
    try{
      const updated = await updateSettingsBackend(patch);
      state.settings = updated;
      toast('Configuration saved', 'success');
    }catch(e){ toast('We couldn\u2019t save the configuration. '+e.message, 'error'); }
    btn.disabled=false; btn.textContent='Save Configuration';
  });
}

/* ------------------------------- AI Email Communication Assistant (HR/Admin) ------------------------------- */
function emailTemplatesView(){
  return `<div class="fade-up"><div id="eaContent"></div></div>`;
}

async function bindEmailTemplatesView(){
  const root = document.getElementById('eaContent');
  if(!root) return;
  let candidates=[], employees=[], selectedCandidate=null;
  let currentEmail={subject:'',body:'',to:'',toName:''};
  let ccChips=[], bccChips=[], isGenerating=false;

  const quickActions=[
    {label:'Interview Invitation', prompt:'Send interview invitation to this candidate', icon:'M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2'},
    {label:'Shortlisted', prompt:'Tell the candidate they have been shortlisted and will proceed to the next round', icon:'M22 11.08V12a10 10 0 1 1-5.93-9.14'},
    {label:'Availability', prompt:'Ask the candidate for their availability for an interview', icon:'M12 8v4l3 3m6-3a9 9 0 1 1-18 0 9 9 0 0 1 18 0z'},
    {label:'Reminder', prompt:'Send a reminder for the upcoming interview', icon:'M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9'},
    {label:'Rejection', prompt:'Send a polite rejection email to the candidate', icon:'M18 6L6 18M6 6l12 12'},
    {label:'Selected', prompt:'Send selection notification - the candidate has been selected for the position', icon:'M9 12l2 2 4-4m6 2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z'},
    {label:'Documents', prompt:'Ask the candidate to submit required documents', icon:'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'},
    {label:'Thank You', prompt:'Send a thank-you email after the interview', icon:'M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z'},
  ];

  function esc(s){ const d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }

  function render(){
    root.innerHTML=`
    <div class="ec-header">
      <div class="ec-header-brand">
        <div class="ec-header-icon">${icon('sparkles',18)}</div>
        <div><h1 class="ec-header-title">Email Templates</h1><p class="ec-header-sub">Professional candidate communications powered by MuraAI</p></div>
      </div>
    </div>
    <div class="ec-layout">
      <div class="ec-sidebar">
        <div class="ec-candidate-section">
          <div class="ec-section-label">CANDIDATE</div>
          <div class="ec-search-box">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input class="ec-search" id="ecSearch" placeholder="Search candidates…" autocomplete="off"/>
          </div>
          <div class="ec-dd" id="ecDD" style="display:none"></div>
        </div>
        <div class="ec-candidate-card" id="ecCard" style="display:none"></div>
        <div class="ec-timeline-section" id="ecTimeline"></div>
      </div>
      <div class="ec-main">
        <div class="ec-quick-bar" id="ecQuickBar" style="display:none">
          <div class="ec-quick-label">QUICK ACTIONS</div>
          <div class="ec-quick-list">${quickActions.map(a=>`<button class="ec-quick" data-prompt="${esc(a.prompt)}"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="${a.icon}"/></svg>${a.label}</button>`).join('')}</div>
        </div>
        <div class="ec-empty" id="ecEmpty">
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="opacity:.3"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
          <div class="ec-empty-title">Email Templates</div>
          <div class="ec-empty-sub">Select a candidate, then choose an action or type your request below.</div>
        </div>
        <div class="ec-composer" id="ecComposer" style="display:none">
          <div class="ec-toolbar" id="ecToolbar" style="display:none">
            <button class="ec-tool" id="ecGenerateBtn"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3L12 3z"/></svg>Generate Referral Email</button>
            <button class="ec-tool" id="ecImproveBtn"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>Improve</button>
            <button class="ec-tool" id="ecProfessionalBtn"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3L12 3z"/></svg>More Professional</button>
            <button class="ec-tool" id="ecConciseBtn"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="9" x2="20" y2="9"/><line x1="4" y1="15" x2="14" y2="15"/></svg>Concise</button>
            <button class="ec-tool" id="ecRegenBtn"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>Regenerate</button>
            <button class="ec-tool ec-tool-usepost" id="ecUseBtn"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>Use Email</button>
            <button class="ec-tool" id="ecCopyBtn"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>Copy</button>
          </div>
          <div class="ec-fields">
            <div class="ec-field-row"><label class="ec-label">To</label><div class="ec-to-display" id="ecToDisplay"><span class="ec-to-chip"><span class="ec-to-avatar" id="ecToAvatar"></span><span id="ecToName"></span><span class="ec-to-email" id="ecToEmail"></span></span></div></div>
            <div class="ec-field-row ec-cc-row"><label class="ec-label">CC</label><div class="ec-cc-wrap" id="ecCCWrap"><span class="ec-cc-add" id="ecAddCC">+ Add CC</span></div><div class="ec-cc-dd" id="ecCCDD" style="display:none"></div></div>
            <div class="ec-field-row ec-cc-row"><label class="ec-label">BCC</label><div class="ec-cc-wrap" id="ecBCCWrap"><span class="ec-cc-add" id="ecAddBCC">+ Add BCC</span></div><div class="ec-cc-dd" id="ecBCCDD" style="display:none"></div></div>
            <div class="ec-field-row"><label class="ec-label">Subject</label><input class="ec-subject" id="ecSubject" placeholder="Email subject..."/></div>
          </div>
          <div class="ec-body-area"><textarea class="ec-body" id="ecBody" placeholder="Email body..."></textarea></div>
          <div class="ec-missing" id="ecMissing" style="display:none"></div>
          <div class="ec-actions"><button class="ec-send-btn" id="ecSendBtn"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>Send Email</button></div>
        </div>
        <div class="ec-input-bar" id="ecInputBar" style="display:none">
          <div class="ec-input-box">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="opacity:.4;flex-shrink:0"><path d="M12 3l1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3L12 3z"/></svg>
            <input class="ec-input" id="ecInput" placeholder="Describe the email to send" autocomplete="off"/>
            <button class="ec-input-send" id="ecInputSend" disabled><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg></button>
          </div>
        </div>
      </div>
    </div>
    <div class="ec-confirm-overlay" id="ecConfirmOverlay" style="display:none">
      <div class="ec-confirm-modal">
        <div class="ec-confirm-title">Ready to send?</div>
        <div class="ec-confirm-body" id="ecConfirmBody"></div>
        <div class="ec-confirm-actions">
          <button class="btn btn-ghost" id="ecConfirmCancel">Cancel</button>
          <button class="btn btn-primary" id="ecConfirmSend">Send Email</button>
        </div>
      </div>
    </div>`;
    bindEvents();
  }

  render();

  /* ---- Candidate search ---- */
  async function searchCandidates(q){
    try{ candidates=await api(`/api/ai/email-assistant/candidates?search=${encodeURIComponent(q)}`); renderCDD(); }catch(e){}
  }
  function renderCDD(){
    const dd=document.getElementById('ecDD'); if(!dd) return;
    if(!candidates.length){dd.innerHTML='<div class="ec-dd-empty">No candidates found</div>';dd.style.display='block';return;}
    dd.innerHTML=candidates.map(c=>`<div class="ec-dd-item" data-id="${c.referralId}"><div class="ec-dd-name">${esc(c.candidateName)}</div><div class="ec-dd-meta">${esc(c.email||'No email')} &middot; ${esc(c.status)}</div><div class="ec-dd-job">${esc(c.jobTitle||'No position')}</div></div>`).join('');
    dd.style.display='block';
  }
  function selectCandidate(id){
    const c=candidates.find(x=>x.referralId===id); if(!c)return;
    selectedCandidate=c;
    document.getElementById('ecDD').style.display='none';
    document.getElementById('ecSearch').value=c.candidateName;
    currentEmail={subject:'',body:'',to:c.email,toName:c.candidateName};
    ccChips=[]; bccChips=[];
    document.getElementById('ecMissing').style.display='none';
    renderCard(c);
    renderComposer();
    loadHistory(id);
    document.getElementById('ecQuickBar').style.display='block';
    document.getElementById('ecInputBar').style.display='block';
    const inp=document.getElementById('ecInput'); inp.disabled=false; inp.focus();
  }

  /* ---- Candidate card ---- */
  function renderCard(c){
    const el=document.getElementById('ecCard'); if(!el) return;
    const s=(c.status||'').toLowerCase().replace(/\s+/g,'-');
    const iv=c.interviews&&c.interviews.length?c.interviews[0]:null;
    el.style.display='block';
    el.innerHTML=`<div class="ec-card">
      <div class="ec-card-top"><div class="ec-card-avatar">${(c.candidateName||'?')[0].toUpperCase()}</div><div><div class="ec-card-name">${esc(c.candidateName)}</div><span class="ec-status ec-status-${s}">${esc(c.status)}</span></div></div>
      <div class="ec-card-grid">
        <div class="ec-card-f"><span class="ec-card-l">Email</span><span class="ec-card-v">${esc(c.email||'—')}</span></div>
        <div class="ec-card-f"><span class="ec-card-l">Position</span><span class="ec-card-v">${esc(c.jobTitle||'—')}</span></div>
        <div class="ec-card-f"><span class="ec-card-l">Department</span><span class="ec-card-v">${esc(c.jobDept||'—')}</span></div>
        <div class="ec-card-f"><span class="ec-card-l">JD vs Resume Match</span><span class="ec-card-v">${c.matchPercent?c.matchPercent+'%':'—'}</span></div>
        <div class="ec-card-f"><span class="ec-card-l">Experience</span><span class="ec-card-v">${esc(c.totalExperience||'—')}</span></div>
        <div class="ec-card-f"><span class="ec-card-l">Location</span><span class="ec-card-v">${esc(c.location||c.jobLocation||'—')}</span></div>
      </div>
      ${iv?`<div class="ec-card-interview"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>${esc(iv.round||'')} ${iv.date?'&middot; '+esc(iv.date):''} ${iv.time?'at '+esc(iv.time):''}</div>`:''}
    </div>`;
  }

  /* ---- Communication timeline ---- */
  async function loadHistory(refId){
    try{
      const data=await api(`/api/ai/email-assistant/history/${refId}`);
      renderTimeline(data.chatHistory||[],data.emailHistory||[]);
    }catch(e){}
  }
  function renderTimeline(chat,email){
    const el=document.getElementById('ecTimeline'); if(!el) return;
    const events=[];
    chat.filter(m=>m.role!=='system'&&m.content).forEach(m=>{
      events.push({date:m.createdAt?new Date(m.createdAt):null,label:(m.role==='hr'?'You asked: ':'')+(m.emailSubject||m.content),type:m.role==='hr'?'hr':'ai',sent:m.emailSent});
    });
    email.forEach(e=>{
      events.push({date:e.createdAt?new Date(e.createdAt):null,label:e.subject||'(no subject)',type:'sent',sent:e.status==='sent'});
    });
    events.sort((a,b)=>(b.date?b.date.getTime():0)-(a.date?a.date.getTime():0));
    if(!events.length){el.innerHTML='';el.style.display='none';return;}
    el.style.display='block';
    el.innerHTML=`<div class="ec-section-label">COMMUNICATION</div>
      <div class="ec-timeline">${events.slice(0,15).map(e=>{
        const dateStr=e.date?e.date.toLocaleDateString('en-GB',{day:'numeric',month:'short'}):'';
        const timeStr=e.date?e.date.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'}):'';
        const dotClass=e.type==='sent'?(e.sent?'ec-tl-sent':'ec-tl-failed'):e.type==='hr'?'ec-tl-hr':'ec-tl-ai';
        return `<div class="ec-tl-item"><div class="ec-tl-dot ${dotClass}"></div><div class="ec-tl-content"><div class="ec-tl-label" title="${esc(e.label)}">${esc(e.label)}</div><div class="ec-tl-time">${dateStr} ${timeStr}</div></div></div>`;
      }).join('')}</div>`;
  }

  /* ---- Email composer ---- */
  function renderComposer(){
    document.getElementById('ecEmpty').style.display='none';
    document.getElementById('ecComposer').style.display='flex';
    document.getElementById('ecToolbar').style.display=currentEmail.subject?'flex':'none';
    document.getElementById('ecToAvatar').textContent=(currentEmail.toName||'?')[0].toUpperCase();
    document.getElementById('ecToName').textContent=currentEmail.toName||'';
    document.getElementById('ecToEmail').innerHTML=currentEmail.to?'&lt;'+esc(currentEmail.to)+'&gt;':'';
    document.getElementById('ecSubject').value=currentEmail.subject||'';
    document.getElementById('ecBody').value=currentEmail.body||'';
    renderChips();
  }

  /* ---- CC/BCC chips ---- */
  function renderChips(){
    [{wrap:'ecCCWrap',add:'ecAddCC',chips:ccChips,type:'cc'},{wrap:'ecBCCWrap',add:'ecAddBCC',chips:bccChips,type:'bcc'}].forEach(cfg=>{
      const wrap=document.getElementById(cfg.wrap); if(!wrap) return;
      let html=cfg.chips.map((c,i)=>`<span class="ec-cc-chip"><span>${esc(c.name)}</span><button class="ec-cc-remove" data-idx="${i}" data-type="${cfg.type}" title="Remove">&times;</button></span>`).join('');
      html+=`<span class="ec-cc-add" id="${cfg.add}">+ Add ${cfg.type.toUpperCase()}</span>`;
      wrap.innerHTML=html;
      document.getElementById(cfg.add).onclick=(ev)=>{ev.stopPropagation();toggleEmpDD(cfg.type);};
      wrap.querySelectorAll('.ec-cc-remove').forEach(btn=>{
        btn.onclick=(ev)=>{
          ev.stopPropagation();
          const arr=btn.dataset.type==='cc'?ccChips:bccChips;
          arr.splice(parseInt(btn.dataset.idx),1); renderChips();
        };
      });
    });
  }
  function toggleEmpDD(type){
    const otherId=type==='cc'?'ecBCCDD':'ecCCDD';
    const other=document.getElementById(otherId); if(other)other.style.display='none';
    const dd=document.getElementById(type==='cc'?'ecCCDD':'ecBCCDD');
    if(dd.style.display==='block'){dd.style.display='none';return;}
    loadEmployees('',type); dd.style.display='block';
  }
  async function loadEmployees(q,type){
    try{ employees=await api(`/api/ai/email-assistant/employees?search=${encodeURIComponent(q)}`); renderEmpDD(type); }catch(e){}
  }
  function renderEmpDD(type){
    const dd=document.getElementById(type==='cc'?'ecCCDD':'ecBCCDD'); if(!dd) return;
    const existing=new Set((type==='cc'?ccChips:bccChips).map(e=>e.email));
    const list=employees.filter(e=>!existing.has(e.email));
    if(!list.length){dd.innerHTML='<div class="ec-dd-empty">No employees found</div>';return;}
    dd.innerHTML=list.map(e=>`<div class="ec-dd-item ec-dd-emp" data-email="${esc(e.email)}" data-name="${esc(e.name)}"><div class="ec-dd-name">${esc(e.name)}</div><div class="ec-dd-meta">${esc(e.email)}${e.dept?' &middot; '+esc(e.dept):''}</div></div>`).join('');
    dd.querySelectorAll('.ec-dd-emp').forEach(item=>{
      item.onclick=()=>{
        (type==='cc'?ccChips:bccChips).push({name:item.dataset.name,email:item.dataset.email});
        dd.style.display='none'; renderChips();
      };
    });
  }

  /* ---- Generate / revise email via AI ---- */
  async function generateEmail(prompt){
    if(!selectedCandidate||isGenerating||!prompt.trim()) return;
    isGenerating=true;
    const inp=document.getElementById('ecInput');
    const sendBtn=document.getElementById('ecInputSend');
    const mainBtn=document.getElementById('ecSendBtn');
    inp.disabled=true; sendBtn.disabled=true; mainBtn.disabled=true;

    // Show inline generating indicator in toolbar
    const toolbar=document.getElementById('ecToolbar');
    if(toolbar&&currentEmail.subject){
      toolbar.innerHTML='<span class="ec-generating"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3L12 3z"/></svg>MuraAI is drafting...</span>';
      toolbar.style.display='flex';
    } else {
      toast('Generating your email…','success');
    }

    try{
      const body={referralId:selectedCandidate.referralId, message:prompt};
      if(currentEmail.subject) body.currentSubject=currentEmail.subject;
      if(currentEmail.body) body.currentBody=currentEmail.body;
      const result=await api('/api/ai/email-assistant/chat',{method:'POST',body});
      if(result.emailPreview){
        currentEmail={subject:result.emailPreview.subject,body:result.emailPreview.body,to:result.emailPreview.to||currentEmail.to,toName:result.emailPreview.toName||currentEmail.toName};
        renderComposer();
      }
      const missEl=document.getElementById('ecMissing');
      if(result.missingInfo&&result.missingInfo.length){
        missEl.style.display='flex';
        missEl.textContent=result.missingInfo.join(' ');
      } else {
        missEl.style.display='none';
      }
      toast('Draft is ready — review and send','success');
    }catch(e){ toast('We couldn\u2019t generate the email. '+e.message,'error'); }
    isGenerating=false;
    inp.disabled=false; sendBtn.disabled=false; mainBtn.disabled=false;
  }

  /* ---- Send email ---- */
  function showConfirm(){
    const subj=document.getElementById('ecSubject').value.trim();
    const bodyTxt=document.getElementById('ecBody').value.trim();
    if(!subj){ toast('Please enter a subject','amber'); document.getElementById('ecSubject').focus(); return; }
    if(!bodyTxt){ toast('Please enter the email body','amber'); document.getElementById('ecBody').focus(); return; }
    if(!currentEmail.to){ toast('No recipient email for this candidate','amber'); return; }
    const body=document.getElementById('ecConfirmBody');
    body.innerHTML=`<div class="ec-confirm-row"><span class="ec-confirm-label">To:</span> ${esc(currentEmail.toName)} &lt;${esc(currentEmail.to)}&gt;</div>
      ${ccChips.length?`<div class="ec-confirm-row"><span class="ec-confirm-label">CC:</span> ${ccChips.map(c=>esc(c.name)).join(', ')}</div>`:''}
      ${bccChips.length?`<div class="ec-confirm-row"><span class="ec-confirm-label">BCC:</span> ${bccChips.map(c=>esc(c.name)).join(', ')}</div>`:''}
      <div class="ec-confirm-row"><span class="ec-confirm-label">Subject:</span> ${esc(subj)}</div>`;
    document.getElementById('ecConfirmOverlay').style.display='flex';
  }
  async function doSend(){
    document.getElementById('ecConfirmOverlay').style.display='none';
    const btn=document.getElementById('ecSendBtn');
    btn.disabled=true; btn.textContent='Sending…';
    try{
      const result=await api('/api/ai/email-assistant/send',{method:'POST',body:{
        referralId:selectedCandidate.referralId,
        to:currentEmail.to,
        cc:ccChips.map(c=>c.email).join(', '),
        bcc:bccChips.map(c=>c.email).join(', '),
        subject:document.getElementById('ecSubject').value,
        body:document.getElementById('ecBody').value,
      }});
      if(result.sent>0){ toast('Email sent successfully','success'); loadHistory(selectedCandidate.referralId); }
      else toast(result.message||'Email could not be sent','error');
    }catch(e){ toast('We couldn\u2019t send the email. '+e.message,'error'); }
    btn.disabled=false;
    btn.innerHTML='<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>Send Email';
  }

  /* ---- Events ---- */
  function bindEvents(){
    let searchTimer;
    document.getElementById('ecSearch').addEventListener('input',e=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>searchCandidates(e.target.value),300);});
    document.getElementById('ecSearch').addEventListener('focus',()=>{searchCandidates(document.getElementById('ecSearch').value);});
    document.addEventListener('click',e=>{
      if(!e.target.closest('.ec-candidate-section')){const dd=document.getElementById('ecDD');if(dd)dd.style.display='none';}
      if(!e.target.closest('.ec-cc-row')){const d1=document.getElementById('ecCCDD');const d2=document.getElementById('ecBCCDD');if(d1)d1.style.display='none';if(d2)d2.style.display='none';}
    });

    document.getElementById('ecDD').addEventListener('click',e=>{const item=e.target.closest('.ec-dd-item');if(item)selectCandidate(item.dataset.id);});

    document.getElementById('ecQuickBar').addEventListener('click',e=>{const btn=e.target.closest('.ec-quick');if(btn)generateEmail(btn.dataset.prompt);});

    const inp=document.getElementById('ecInput');
    const sendBtn=document.getElementById('ecInputSend');
    inp.addEventListener('input',()=>{sendBtn.disabled=!inp.value.trim()||isGenerating;});
    inp.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();if(inp.value.trim()){generateEmail(inp.value);inp.value='';sendBtn.disabled=true;}}});
    sendBtn.addEventListener('click',()=>{if(inp.value.trim()){generateEmail(inp.value);inp.value='';sendBtn.disabled=true;}});

    document.getElementById('ecSendBtn').addEventListener('click',showConfirm);
    document.getElementById('ecConfirmCancel').addEventListener('click',()=>{document.getElementById('ecConfirmOverlay').style.display='none';});
    document.getElementById('ecConfirmOverlay').addEventListener('click',e=>{if(e.target.id==='ecConfirmOverlay')e.target.style.display='none';});
    document.getElementById('ecConfirmSend').addEventListener('click',doSend);

    // AI editing commands
    const focusInput = (placeholder)=>{
      const inp=document.getElementById('ecInput');
      inp.placeholder=placeholder||(currentEmail.subject?'e.g. Make it shorter, more professional, or add the meeting link…':'Describe the email to send');
      inp.focus();
    };
    // Generate Email: start fresh from the user's typed request
    document.getElementById('ecGenerateBtn').addEventListener('click',()=>{
      focusInput('Describe the email to generate');
    });
    // Improve: refine the existing draft
    document.getElementById('ecImproveBtn').addEventListener('click',()=>{
      if(currentEmail.subject && currentEmail.body){
        generateEmail('Improve and polish this email: keep the meaning, fix grammar and phrasing.');
      } else { focusInput('Describe the improvement to make'); }
    });
    // Make More Professional: rewrite the current draft with a formal tone
    document.getElementById('ecProfessionalBtn').addEventListener('click',()=>{
      if(currentEmail.subject && currentEmail.body){
        generateEmail('Rewrite this email to be more professional and formal, while keeping all the facts and meaning.');
      } else { focusInput('Describe the email to generate'); }
    });
    // Make Concise: tighten the current draft
    document.getElementById('ecConciseBtn').addEventListener('click',()=>{
      if(currentEmail.subject && currentEmail.body){
        generateEmail('Make this email more concise: shorten it while keeping all key points and tone.');
      } else { focusInput('Describe the email to generate'); }
    });
    // Regenerate: fresh approach on the same topic
    document.getElementById('ecRegenBtn').addEventListener('click',()=>{
      if(selectedCandidate) generateEmail(currentEmail.subject?('Regenerate this email with a fresh approach: ' + currentEmail.subject):'Generate the email again');
    });
    // Use Email: populate the composer with the current AI draft (already shown)
    // and guide the user to review then send.
    document.getElementById('ecUseBtn').addEventListener('click',()=>{
      renderComposer();
      const subject=document.getElementById('ecSubject').value.trim();
      const body=document.getElementById('ecBody').value.trim();
      if(!subject && !body){ toast('There is no draft to use yet — generate one first','amber'); return; }
      document.getElementById('ecSubject').focus();
      toast('Email loaded into the composer — review, then press Send','success');
    });
    document.getElementById('ecCopyBtn').addEventListener('click',()=>{
      const text='Subject: '+document.getElementById('ecSubject').value+'\n\n'+document.getElementById('ecBody').value;
      navigator.clipboard.writeText(text); toast('Email copied to clipboard','success');
    });

    searchCandidates('');
  }
}

/* ------------------------------- Audit Logs (Admin) ------------------------------- */
function auditLogsView(){
  return `
  <div class="fade-up">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;flex-wrap:wrap;gap:10px;">
      <div><h1 class="display" style="font-size:24px;margin:0 0 4px;">Audit Logs</h1>
      <p style="color:var(--ink-soft);font-size:13px;margin:0;">System activity and security audit trail</p></div>
    </div>
    <div id="auditLogsList"></div>
  </div>`;
}
async function bindAuditLogsView(){
  const container = document.getElementById('auditLogsList');
  if(!container) return;
  container.innerHTML = `<div class="glass" style="padding:20px;"><div class="shimmer" style="height:60px;border-radius:12px;"></div></div>`;
  try{
    const logs = await api('/api/admin/audit-logs');
    if(!logs || logs.length===0){
      container.innerHTML = `<div class="glass" style="padding:40px;text-align:center;color:var(--ink-soft);">No audit logs recorded yet.</div>`;
      return;
    }
    container.innerHTML = `
    <div class="glass" style="padding:6px;overflow-x:auto;">
      <table class="data-table">
        <thead><tr><th>User</th><th>Role</th><th>Action</th><th>Target</th><th>Details</th><th>Time</th></tr></thead>
        <tbody>
          ${logs.map(l=>`<tr>
            <td><strong>${l.userName||'—'}</strong></td>
            <td><span class="chip" style="background:rgba(37,99,235,0.12);color:var(--primary);">${l.userRole||'—'}</span></td>
            <td style="font-size:12px;">${l.action}</td>
            <td style="font-size:12px;">${l.target||'—'}</td>
            <td style="font-size:12px;max-width:200px;">${l.details||'—'}</td>
            <td style="font-size:11px;color:var(--ink-soft);">${fmtRelative(l.created_at)}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
  }catch(e){ container.innerHTML='<div class="glass" style="padding:20px;color:var(--coral);">We couldn\u2019t load the audit logs. '+e.message+'</div>'; }
}

/* ------------------------------- Email Center (Admin) ------------------------------- */
function emailCenterView(){
  return `
  <div class="fade-up">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;flex-wrap:wrap;gap:10px;">
      <div><h1 class="display" style="font-size:24px;margin:0 0 4px;">Email Center</h1>
      <p style="color:var(--ink-soft);font-size:13px;margin:0;">Compose, send, and track candidate communications</p></div>
      <button class="btn btn-primary" id="ecComposeBtn">Compose Email</button>
    </div>
    <div style="display:flex;gap:6px;margin-bottom:16px;flex-wrap:wrap;">
      <button class="btn btn-outline report-tab active" data-ectab="history">Sent History</button>
      <button class="btn btn-outline report-tab" data-ectab="compose">Compose</button>
    </div>
    <div id="ecContent"></div>
    <div id="ecModal"></div>
  </div>`;
}

async function bindEmailCenterView(){
  const content = document.getElementById('ecContent');
  if(!content) return;

  const loadHistory = async ()=>{
    content.innerHTML = `<div class="glass" style="padding:20px;"><div class="shimmer" style="height:60px;border-radius:12px;"></div></div>`;
    try{
      const emails = await api('/api/emails/history');
      if(!emails || emails.length===0){
        content.innerHTML = `<div class="glass" style="padding:40px;text-align:center;color:var(--ink-soft);">No emails have been sent yet.</div>`;
        return;
      }
      const statusColor = {sent:'#059669', delivered:'#059669', scheduled:'#D97706', failed:'#DC2626'};
      content.innerHTML = `
      <div class="glass" style="padding:6px;overflow-x:auto;">
        <table class="data-table">
          <thead><tr><th>To</th><th>Subject</th><th>Type</th><th>Status</th><th>Category</th><th>Sent</th><th></th></tr></thead>
          <tbody>
            ${emails.map(e=>{
              const sc = statusColor[(e.status||'').toLowerCase()] || '#2563EB';
              return `<tr>
                <td><strong>${e.toEmail||'—'}</strong>${e.cc?`<div style="font-size:11px;color:var(--ink-soft);">cc: ${e.cc}</div>`:''}</td>
                <td style="font-size:12.5px;max-width:260px;">${e.subject||'—'}</td>
                <td><span class="chip" style="background:rgba(37,99,235,0.12);color:var(--primary);">${e.emailType||'general'}</span></td>
                <td><span class="chip" style="background:${sc}18;color:${sc};">${e.status||'—'}</span></td>
                <td style="font-size:12px;">${e.category||'—'}</td>
                <td style="font-size:11.5px;color:var(--ink-soft);">${e.createdAt?new Date(e.createdAt).toLocaleString():'—'}</td>
                <td>${e.body?`<button class="btn btn-ghost" style="font-size:11px;padding:3px 8px;" data-ec-view='${e.id}'>View</button>`:''}</td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>
      <div style="margin-top:10px;font-size:12px;color:var(--ink-soft);">${emails.length} email record(s)</div>`;
      content.querySelectorAll('[data-ec-view]').forEach(btn=>{
        btn.addEventListener('click', ()=>{
          const e = emails.find(x=>x.id===btn.dataset.ecView);
          if(!e) return;
          document.getElementById('ecModal').innerHTML = `
          <div class="modal-overlay" id="ecOverlay">
            <div class="glass-strong pop-in" style="max-width:600px;width:100%;padding:24px;max-height:85vh;overflow-y:auto;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
                <h3 style="margin:0;font-size:15px;">${e.subject||'Email'}</h3>
                <button class="btn btn-ghost" onclick="document.getElementById('ecOverlay').remove()" style="padding:6px;">${icon('x',16)}</button>
              </div>
              <div style="font-size:12px;color:var(--ink-soft);margin-bottom:12px;">To: <strong>${e.toEmail}</strong>${e.cc?' · cc: '+e.cc:''} · ${e.emailType||'general'} · ${e.createdAt?new Date(e.createdAt).toLocaleString():''}</div>
              <div class="glass" style="padding:16px;font-size:13px;line-height:1.6;white-space:pre-wrap;">${e.body||'(empty body)'}</div>
            </div>
          </div>`;
        });
      });
    }catch(e){ content.innerHTML = `<div class="glass" style="padding:20px;color:var(--coral);">Could not load email history: ${e.message}</div>`; }
  };

  const loadCompose = ()=>{
    const candidates = state.referrals.filter(r=>r.email);
    content.innerHTML = `
    <div class="glass" style="padding:20px;max-width:760px;">
      <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;">
        <div><label class="field-label">Recipient</label>
          <select class="input" id="ecToSelect"><option value="">Custom…</option>${candidates.map(r=>`<option value="${r.email}">${r.candidateName} &lt;${r.email}&gt;</option>`).join('')}</select>
        </div>
        <div><label class="field-label">Or Custom Email</label><input class="input" id="ecToCustom" placeholder="hr@muraai.com"/></div>
        <div style="grid-column:1/-1;"><label class="field-label">Subject</label><input class="input" id="ecSubject" placeholder="Subject line"/></div>
        <div style="grid-column:1/-1;"><label class="field-label">Message</label><textarea class="input" id="ecBody" rows="8" placeholder="Write your message…"></textarea></div>
      </div>
      <div style="display:flex;gap:10px;margin-top:14px;">
        <button class="btn btn-outline" id="ecAiBtn">AI Compose</button>
        <button class="btn btn-primary" id="ecSendBtn">Send Email</button>
      </div>
      <div id="ecAiArea"></div>
    </div>`;

    document.getElementById('ecAiBtn').addEventListener('click', async ()=>{
      const aiArea = document.getElementById('ecAiArea');
      const prompt = document.getElementById('ecBody').value.trim();
      const candName = candidates.find(c=>c.email===document.getElementById('ecToSelect').value)?.candidateName || 'the candidate';
      aiArea.innerHTML = `<div style="margin-top:12px;font-size:12px;color:var(--ink-soft);">AI is composing…</div>`;
      try{
        const r = await api('/api/ai/compose-email', {method:'POST', body:{context:'general', candidateName:candName, jobTitle:'the position', companyName:'MuraAI', prompt:prompt}});
        document.getElementById('ecSubject').value = r.subject || '';
        document.getElementById('ecBody').value = r.body || '';
        aiArea.innerHTML = `<div style="margin-top:12px;font-size:12px;color:#059669;">AI draft ready — review and send.</div>`;
      }catch(e){
        aiArea.innerHTML = `<div style="margin-top:12px;font-size:12px;color:var(--coral);">We couldn\u2019t compose the email. ${e.message}</div>`;
      }
    });

    document.getElementById('ecSendBtn').addEventListener('click', async ()=>{
      const to = document.getElementById('ecToSelect').value || document.getElementById('ecToCustom').value.trim();
      const subject = document.getElementById('ecSubject').value.trim();
      const body = document.getElementById('ecBody').value.trim();
      if(!to){ toast('Enter a recipient email', 'amber'); return; }
      if(!subject || !body){ toast('Subject and message are required', 'amber'); return; }
      try{
        const r = await api('/api/ai/send-email', {method:'POST', body:{to:[to], subject, body, emailType:'general'}});
        toast(r.message || 'Email sent', 'success');
        document.getElementById('ecToSelect').value='';
        document.getElementById('ecToCustom').value='';
        document.getElementById('ecSubject').value='';
        document.getElementById('ecBody').value='';
      }catch(e){ toast('Send failed: '+e.message, 'error'); }
    });
  };

  const switchTab = (tab)=>{
    document.querySelectorAll('[data-ectab]').forEach(b=>{
      b.classList.toggle('active', b.dataset.ectab===tab);
    });
    if(tab==='history') loadHistory();
    else loadCompose();
  };

  document.querySelectorAll('[data-ectab]').forEach(b=> b.addEventListener('click', ()=>switchTab(b.dataset.ectab)));
  document.getElementById('ecComposeBtn').addEventListener('click', ()=>switchTab('compose'));
  switchTab('history');
}
