function manageJobsView(){
  return `
  <div class="fade-up">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;flex-wrap:wrap;gap:10px;">
      <div>
        <h1 class="display" style="font-size:24px;margin:0 0 4px;">Manage Jobs</h1>
        <div style="font-size:13px;color:var(--text-secondary);">${state.jobs.length} open position${state.jobs.length===1?'':'s'}</div>
      </div>
      <div style="display:flex;gap:10px;">
        <button class="btn btn-outline" id="openNewJobForm">Create Job</button>
        <button class="btn btn-primary" id="openJdGenerator">AI Job Description Generator</button>
      </div>
    </div>
    <div id="jdGeneratorPanel"></div>
    <div id="jobFormPanel"></div>
    ${state.jobs.length===0 ? `
    <div class="glass" style="padding:40px;text-align:center;">
      <div style="width:48px;height:48px;border-radius:12px;background:var(--primary-light);color:var(--primary);font-weight:700;font-size:22px;margin:0 auto 12px;display:flex;align-items:center;justify-content:center;">+</div>
      <h3 style="margin:0 0 6px;">No open roles yet</h3>
      <p style="color:var(--text-secondary);margin:0;">Post your first job to start collecting referrals.</p>
    </div>` : `
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;">
      ${state.jobs.map(j=>{
        const refCount = state.referrals.filter(r=>r.jobId===j.id).length;
        return `
      <div class="glass job-card" style="padding:20px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
          <div style="font-size:11px;font-weight:700;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.08em;">${j.dept}</div>
          <span class="chip" style="background:${j.status==='Open'?'rgba(5,150,105,0.12)':'rgba(100,116,139,0.12)'};color:${j.status==='Open'?'#047857':'var(--text-secondary)'};">${j.status}</span>
        </div>
        <h3 style="font-size:16px;font-weight:700;margin:0 0 6px;">${j.title}</h3>
        <div style="font-size:12.5px;color:var(--text-secondary);margin-bottom:14px;">${j.exp} · ${j.location} · Posted ${fmtRelative(j.posted)}</div>
        <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;padding:12px 0;border-top:1px solid var(--border);border-bottom:1px solid var(--border);margin-bottom:12px;">
          <div><div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:2px;">Salary</div><div style="font-size:13px;font-weight:600;color:var(--text-primary);overflow-wrap:anywhere;">${j.salary}</div></div>
          <div><div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:2px;">Bonus</div><div style="font-size:13px;font-weight:700;color:var(--teal);">₹${(j.bonus||0).toLocaleString('en-IN')}</div></div>
          <div><div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:2px;">Referrals</div><div style="font-size:13px;font-weight:600;color:var(--text-primary);">${refCount}</div></div>
        </div>
        <div style="margin-bottom:14px;">${j.skills.slice(0,4).map((s,k)=>`<span class="skill-bubble" style="background:${skillTagColor(k)};animation:none;">${s}</span>`).join('')}</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <button class="btn btn-outline" style="flex:1;" data-edit-job="${j.id}">${icon('pencil',13)} Edit</button>
          <button class="btn btn-danger-ghost" data-delete-job="${j.id}">${icon('trash',13)} Delete</button>
        </div>
      </div>`}).join('')}
    </div>`}
  </div>`;
}
function jobFormHTML(job){
  const isEdit = !!job;
  return `
  <div class="glass pop-in" style="padding:22px;margin-bottom:18px;">
    <h3 style="margin:0 0 14px;font-size:14.5px;">${isEdit?'Edit Job':'Create Job'}</h3>
    <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;">
      <div style="grid-column:1/-1;"><label class="field-label">Title *</label><input class="input" id="jobTitle" value="${job?.title||''}"/></div>
      <div><label class="field-label">Department</label><input class="input" id="jobDept" value="${job?.dept||'General'}"/></div>
      <div><label class="field-label">Experience</label><input class="input" id="jobExp" value="${job?.exp||'0-2 years'}"/></div>
      <div><label class="field-label">Location</label><input class="input" id="jobLocation" value="${job?.location||'Bengaluru'}"/></div>
      <div><label class="field-label">Salary Range</label><input class="input" id="jobSalary" value="${job?.salary||'TBD'}"/></div>
      <div><label class="field-label">Referral Bonus (₹)</label><input class="input" type="number" id="jobBonus" value="${job?.bonus||50000}"/></div>
      <div><label class="field-label">Status</label>
        <select class="input" id="jobStatus"><option ${job?.status==='Open'?'selected':''}>Open</option><option ${job?.status==='Closed'?'selected':''}>Closed</option></select>
      </div>
      <div style="grid-column:1/-1;"><label class="field-label">Skills (comma-separated)</label><input class="input" id="jobSkills" value="${(job?.skills||[]).join(', ')}"/></div>
      <div style="grid-column:1/-1;"><label class="field-label">Description</label><textarea class="input" id="jobDescription" rows="4">${job?.description||''}</textarea></div>
    </div>
    <div style="display:flex;gap:10px;margin-top:14px;">
      <button class="btn btn-primary" id="saveJobBtn">${isEdit?'Save Changes':'Create Job'}</button>
      <button class="btn btn-ghost" id="cancelJobForm">Cancel</button>
    </div>
  </div>`;
}
function readJobForm(){
  return {
    title: document.getElementById('jobTitle').value.trim(),
    dept: document.getElementById('jobDept').value.trim() || 'General',
    exp: document.getElementById('jobExp').value.trim() || '—',
    location: document.getElementById('jobLocation').value.trim() || 'Remote',
    salary: document.getElementById('jobSalary').value.trim() || 'TBD',
    bonus: parseInt(document.getElementById('jobBonus').value, 10) || 0,
    status: document.getElementById('jobStatus').value,
    skills: document.getElementById('jobSkills').value.split(',').map(s=>s.trim()).filter(Boolean),
    description: document.getElementById('jobDescription').value.trim(),
  };
}
function bindManageJobs(){
  const panel = document.getElementById('jobFormPanel');

  const newJobBtn = document.getElementById('openNewJobForm');
  if(newJobBtn) newJobBtn.addEventListener('click', ()=>{
    panel.innerHTML = jobFormHTML(null);
    document.getElementById('cancelJobForm').addEventListener('click', ()=> panel.innerHTML='');
    document.getElementById('saveJobBtn').addEventListener('click', async ()=>{
      const fields = readJobForm();
      if(!fields.title){ toast('Please enter a job title.', 'amber'); return; }
      const saveBtn = document.getElementById('saveJobBtn');
      saveBtn.disabled = true; saveBtn.textContent = 'Posting…';
      try{
        const job = await createJobBackend(fields);
        state.jobs.unshift(job);
        toast('Job created', 'success');
        nav('manageJobs');
      }catch(e){ toast('We couldn\u2019t create the job. '+e.message, 'error'); saveBtn.disabled=false; saveBtn.textContent='Create Job'; }
    });
  });

  document.querySelectorAll('[data-edit-job]').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      const job = jobById(btn.dataset.editJob);
      panel.innerHTML = jobFormHTML(job);
      panel.scrollIntoView({behavior:'smooth', block:'center'});
      document.getElementById('cancelJobForm').addEventListener('click', ()=> panel.innerHTML='');
      document.getElementById('saveJobBtn').addEventListener('click', async ()=>{
        const fields = readJobForm();
        if(!fields.title){ toast('Please enter a job title.', 'amber'); return; }
        const saveBtn = document.getElementById('saveJobBtn');
        saveBtn.disabled = true; saveBtn.textContent = 'Saving…';
        try{
          const updated = await api(`/api/jobs/${job.id}`, {method:'PUT', body:fields});
          const idx = state.jobs.findIndex(j=>j.id===job.id);
          if(idx>-1) state.jobs[idx] = updated;
          toast('Job updated', 'success');
          nav('manageJobs');
        }catch(e){ toast('We couldn\u2019t save the job. '+e.message, 'error'); saveBtn.disabled=false; saveBtn.textContent='Save Changes'; }
      });
    });
  });

  document.querySelectorAll('[data-delete-job]').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      const job = jobById(btn.dataset.deleteJob);
      if(!confirm(`Delete "${job.title}"? Existing referrals are retained for audit (soft delete).`)) return;
      try{
        await api(`/api/jobs/${job.id}`, {method:'DELETE'});
        state.jobs = state.jobs.filter(j=>j.id!==job.id);
        toast('Job deleted', 'success');
        render();
      }catch(e){ toast('We couldn\u2019t delete the job. '+e.message, 'error'); }
    });
  });

  const btn = document.getElementById('openJdGenerator');
  if(!btn) return;
  btn.addEventListener('click', ()=>{
    const jdPanel = document.getElementById('jdGeneratorPanel');
    jdPanel.innerHTML = `
    <div class="glass pop-in" style="padding:22px;margin-bottom:18px;">
      <h3 style="margin:0 0 10px;font-size:14.5px;">AI Job Description Generator</h3>
      <textarea class="input" id="jdBrief" rows="2" placeholder="e.g. Python Developer with 3-5 years of experience, Bengaluru, Django and AWS"></textarea>
      <div style="display:flex;gap:10px;margin-top:10px;">
        <button class="btn btn-cyan" id="generateJdBtn">Generate JD</button>
        <button class="btn btn-ghost" id="closeJdPanel">Cancel</button>
      </div>
      <div id="jdOutput" style="margin-top:14px;"></div>
    </div>`;
    document.getElementById('closeJdPanel').addEventListener('click', ()=> jdPanel.innerHTML='');
    document.getElementById('generateJdBtn').addEventListener('click', async ()=>{
      const brief = document.getElementById('jdBrief').value.trim();
      if(!brief){ toast('Please describe the role first.', 'amber'); return; }
      const gbtn = document.getElementById('generateJdBtn'); gbtn.disabled=true; gbtn.textContent='Generating…';
      try{
        const jd = await aiGenerateJD(brief);
        document.getElementById('jdOutput').innerHTML = `
          <div class="glass" style="padding:16px;font-size:12.5px;white-space:pre-wrap;line-height:1.65;max-height:320px;overflow-y:auto;">${jd}</div>
          <button class="btn btn-primary" id="publishJdBtn" style="margin-top:12px;">Create Job</button>`;
        document.getElementById('publishJdBtn').addEventListener('click', async ()=>{
          const publishBtn = document.getElementById('publishJdBtn');
          publishBtn.disabled = true; publishBtn.textContent = 'Publishing…';
          const titleGuess = brief.replace(/^need\s+a?n?\s*/i,'').split(',')[0];
          try{
            const job = await createJobBackend({
              title: titleGuess.slice(0,60), dept:'General', exp:'—', location:'Bengaluru', salary:'TBD', bonus:50000,
              skills: brief.split(/,| and /i).slice(1).map(s=>s.trim()).filter(Boolean).slice(0,6),
              status:'Open', description: jd,
            });
            state.jobs.unshift(job);
            toast('Job created', 'success');
            nav('manageJobs');
          }catch(e){ toast('We couldn\u2019t create the job. '+e.message, 'error'); publishBtn.disabled=false; publishBtn.textContent='Create Job'; }
        });
      }catch(e){ toast('We couldn\u2019t generate the job description. Please try again.', 'error'); }
      gbtn.disabled=false; gbtn.textContent='Generate JD';
    });
  });
}

let refFilter = { q:'', status:'' };
let refSearchPendingFocus = false;
function refMatchesFilter(r){
  if(refFilter.q){
    const job = jobById(r.jobId);
    const hay = ((r.candidateName||'')+' '+(r.email||'')+' '+((r.skills||[]).join(' '))+' '+(job?job.title:'')+' '+((r.tags||[]).join(' '))).toLowerCase();
    if(!hay.includes(refFilter.q.toLowerCase())) return false;
  }
  const f = refFilter.status;
  if(!f) return true;
  if(f==='Rejected') return r.status==='Rejected';
  if(f==='Under Review') return r.status==='Under Review';
  if(f==='Resume Screening') return r.status==='Resume Screening';
  if(f==='Shortlisted') return r.status==='Shortlisted';
  if(f==='Interview Scheduled') return r.status==='Interview Scheduled';
  if(f==='Interview Completed') return r.status==='Interview Completed';
  if(f==='Selected') return r.status==='Selected';
  if(f==='Offer Released') return r.status==='Offer Released';
  if(f==='Joined') return r.status==='Joined';
  if(f==='Applied') return r.status==='Applied';
  return r.status===f;
}

function allReferralsView(){
  const statusOptions = ['Applied','Resume Screening','Shortlisted','Under Review','Auto-Reject Recommended','Rejected','Interview Scheduled','Interview Completed','Selected','Offer Released','Joined'];
  const filtered = state.referrals.filter(refMatchesFilter);
  return `
  <div class="fade-up">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:10px;">
      <div>
        <h1 class="display" style="font-size:24px;margin:0;">All Referrals</h1>
        <div style="font-size:12.5px;color:var(--ink-soft);margin-top:2px;">${state.referrals.length} candidates</div>
      </div>
      <div style="display:flex;gap:8px;">
        <button class="btn btn-primary" data-nav="bulkImport" style="display:inline-flex;align-items:center;gap:6px;">${icon('upload',14)} Bulk Import</button>
        <button class="btn btn-outline" id="compareModeBtn">Select 2 to Compare</button>
      </div>
    </div>
    <div class="glass rm-toolbar-card">
      <div class="rm-toolbar">
        <div class="rm-field rm-field-search">
          <label class="field-label" for="refSearchInput">Smart Search Candidates</label>
          <input class="input" id="refSearchInput" placeholder="Type a name, email, or skill" value="${esc(refFilter.q)}"/>
        </div>
        <div class="rm-field rm-field-status">
          <label class="field-label" for="refStatusFilter">Status Filter</label>
          <select class="input" id="refStatusFilter"><option value="">All Statuses</option>${statusOptions.map(s=>`<option ${refFilter.status===s?'selected':''}>${s}</option>`).join('')}</select>
        </div>
        <div class="rm-count-wrap">
          <div class="rm-count-chip"><strong class="mono">${filtered.length}</strong>&nbsp;/ ${state.referrals.length} shown</div>
        </div>
      </div>
    </div>
    <div class="glass" style="padding:6px;overflow-x:auto;">
      <table class="data-table ref-table">
        <thead><tr><th style="width:40px;"><input type="checkbox" id="compareSelectAll" style="display:none;"/></th><th>Candidate</th><th>Job</th><th>Referred By</th><th>Status</th><th>Submitted</th><th></th></tr></thead>
        <tbody>
          ${filtered.map(r=>{
            const job = jobById(r.jobId); const emp = employeeById(r.referredBy);
            const isRejected = r.status==='Rejected';
            return `<tr style="${isRejected?'opacity:0.85;':''}">
              <td><input type="checkbox" class="compare-check" data-id="${r.id}" style="display:none;"/></td>
              <td><strong>${r.candidateName}</strong></td>
              <td>${job?job.title:'—'}</td>
              <td>${emp?emp.name:'—'}</td>
              <td><select class="input" style="padding:6px 10px;font-size:12px;max-width:150px;width:100%;${isRejected?'color:#DC2626':''}" data-status-select="${r.id}">
                ${statusOptions.map(s=>`<option ${r.status===s?'selected':''}>${s}</option>`).join('')}
              </select></td>
              <td style="font-size:12px;color:var(--ink-soft);">${fmtRelative(r.submittedDate)}</td>
              <td class="ref-actions"><div style="display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end;">
                <button class="btn btn-ghost" style="font-size:11px;padding:4px 8px;" data-hr-view="${r.id}">Details</button>
                ${isHrRole(state.role)?`<button class="btn btn-ghost" style="font-size:11px;padding:4px 8px;color:var(--rose);" data-delete-ref="${r.id}">Delete</button>`:''}
              </div></td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>
      ${filtered.length===0?`<div style="padding:30px;text-align:center;color:var(--ink-soft);font-size:13px;">No candidates match this filter.</div>`:''}
    </div>
    <div id="compareResultPanel"></div>
  </div>`;
}
function hrReferralModal(r){
  const job = jobById(r.jobId); const emp = employeeById(r.referredBy);
  return `
  <div class="modal-overlay" id="hrModalOverlay">
    <div class="glass-strong pop-in" style="max-width:640px;width:100%;padding:28px;max-height:88vh;overflow-y:auto;">
      <div style="display:flex;justify-content:space-between;gap:10px;">
        <div style="flex:1;min-width:0;"><h2 class="display" style="margin:0 0 2px;font-size:19px;word-break:break-word;">${esc(r.candidateName)}</h2>
        <div style="font-size:12.5px;color:var(--ink-soft);">${job?job.title:'—'} · Referred by ${emp?emp.name:'—'} (${r.relationship||'—'})</div></div>
        <button class="btn btn-ghost" id="closeHrModal" style="padding:6px;flex-shrink:0;">${icon('x',16)}</button>
      </div>

      <div style="display:grid;grid-template-columns:auto 1fr;gap:18px;align-items:center;margin:16px 0;padding:16px;border-radius:12px;background:rgba(37,99,235,0.06);">
        <div style="text-align:center;flex-shrink:0;">
          <div class="mono" style="font-size:28px;font-weight:700;color:var(--primary);">${r.matchPercent||0}%</div>
          <div style="font-size:11px;color:var(--ink-soft);margin-top:2px;">JD vs Resume Match</div>
        </div>
        <div style="font-size:12.5px;color:var(--ink-soft);">${r.aiSummary||'—'}</div>
      </div>

      ${r.status==='Auto-Reject Recommended'?`
      <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin-bottom:14px;padding:12px 14px;border-radius:12px;background:rgba(217,119,6,0.12);border:1px solid rgba(217,119,6,0.35);">
        <div style="flex:1;min-width:200px;">
          <div style="font-size:13px;font-weight:700;color:#B45309;display:flex;align-items:center;gap:6px;">${icon('zap',14)} Auto-Reject Recommended — HR Review Required</div>
          <div style="font-size:12px;color:#78350F;margin-top:2px;">Match ${r.matchPercent||0}% is below the 40% threshold. No rejection email has been sent — review and decide.</div>
          ${r.rejectionReason?`<div style="font-size:11.5px;color:#78350F;margin-top:4px;opacity:0.85;">${esc(r.rejectionReason)}</div>`:''}
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;">
          <button class="btn" style="font-size:11.5px;padding:5px 10px;background:#DC2626;color:#fff;" data-confirm-reject="${r.id}">${icon('check',12)} Confirm Rejection</button>
          <button class="btn btn-outline" style="font-size:11.5px;padding:5px 10px;color:#047857;" data-move-review="${r.id}">${icon('eye',12)} Move to Under Review</button>
        </div>
      </div>`:''}

      ${r.matchBreakdown&&r.matchBreakdown.criteria&&r.matchBreakdown.criteria.length?`
      <div style="margin-bottom:6px;font-size:13px;font-weight:700;display:flex;align-items:center;gap:6px;">${icon('grid',13)} Match Breakdown</div>
      <div style="margin-bottom:14px;display:flex;flex-direction:column;gap:8px;padding:12px;border-radius:10px;background:rgba(37,99,235,0.04);">
        ${r.matchBreakdown.criteria.map(c=>`
          <div>
            <div style="display:flex;justify-content:space-between;font-size:11.5px;margin-bottom:2px;">
              <span style="color:var(--ink-soft);">${c.label||esc(c.key||'')}</span>
              <span class="mono" style="font-weight:700;color:${c.score>=80?'#059669':c.score>=50?'#B45309':'#DC2626'};">${c.score}% <span style="color:var(--ink-soft);font-weight:400;font-size:10.5px;">weight ${Math.round(c.weight*100)}%</span></span>
            </div>
            <div style="height:6px;background:rgba(37,99,235,0.1);border-radius:99px;overflow:hidden;"><div style="height:100%;width:${c.score}%;border-radius:99px;background:${c.score>=80?'#059669':c.score>=50?'#B45309':'#DC2626'};"></div></div>
            ${c.evidence?`<div style="font-size:11px;color:var(--ink-soft);margin-top:3px;opacity:0.9;">${esc(c.evidence)}</div>`:''}
          </div>`).join('')}
      </div>`:''}

      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;">
        <button class="btn btn-outline" style="font-size:12px;padding:6px 12px;" id="reanalyzeBtn" data-reanalyze="${r.id}">${icon('refresh',12)} Re-evaluate Resume</button>
        <button class="btn btn-outline" style="font-size:12px;padding:6px 12px;color:var(--primary);" id="overrideBtn" data-override="${r.id}">${icon('sliders',12)} Move to Stage</button>
        ${isHrRole(state.role)?`<button class="btn btn-ghost" style="font-size:12px;padding:6px 12px;color:var(--rose);" id="delRefBtn" data-delete-ref="${r.id}">Delete</button>`:''}
      </div>

      ${r.strengths&&r.strengths.length?`<div style="margin-bottom:6px;font-size:13px;font-weight:700;">Strengths</div><div style="font-size:12.5px;color:var(--ink-soft);margin-bottom:14px;">${r.strengths.join(' · ')}</div>`:''}
      ${r.skills&&r.skills.length?`<div style="margin-bottom:6px;font-size:13px;font-weight:700;">Skills</div><div style="margin-bottom:14px;">${skillBubbles(r.skills)}</div>`:''}
      ${r.education?`<div style="margin-bottom:6px;font-size:13px;font-weight:700;">Education</div><div style="font-size:12.5px;color:var(--ink-soft);margin-bottom:14px;">${r.education}</div>`:''}
      ${r.certifications&&r.certifications.length?`<div style="margin-bottom:6px;font-size:13px;font-weight:700;">Certifications</div><div style="font-size:12.5px;color:var(--ink-soft);margin-bottom:14px;">${r.certifications.join(' · ')}</div>`:''}
      ${r.projects&&r.projects.length?`<div style="margin-bottom:6px;font-size:13px;font-weight:700;">Projects</div><div style="font-size:12.5px;color:var(--ink-soft);margin-bottom:14px;">${r.projects.join(' · ')}</div>`:''}
      <div style="margin-bottom:6px;font-size:13px;font-weight:700;">Contact</div>
      <div style="font-size:12.5px;color:var(--ink-soft);">${r.email||'—'} · ${r.phone||'—'} · ${r.currentCompany||'—'} · ${r.currentDesignation||'—'}</div>
      <div style="font-size:12.5px;color:var(--ink-soft);margin-top:4px;">Experience: ${r.totalExperience||'—'} total, ${r.relevantExperience||'—'} relevant · ${r.resumeFileUrl?`<a href="javascript:void(0)" onclick="openResumeFile('${r.resumeFileUrl}')" style="color:var(--primary);">Resume</a>`:'No file'}</div>
    </div>
  </div>`;
}
function bindAllReferrals(){
  const searchInput = document.getElementById('refSearchInput');
  if(searchInput){
    searchInput.addEventListener('input', (e)=>{ refFilter.q = e.target.value; refSearchPendingFocus = true; render(); });
    if(refSearchPendingFocus){ searchInput.focus(); searchInput.setSelectionRange(searchInput.value.length, searchInput.value.length); refSearchPendingFocus = false; }
  }
  const statusFilter = document.getElementById('refStatusFilter');
  if(statusFilter){
    statusFilter.addEventListener('change', (e)=>{ refFilter.status = e.target.value; render(); });
  }
  document.querySelectorAll('[data-status-select]').forEach(sel=>{
    sel.addEventListener('change', async ()=>{
      const r = state.referrals.find(x=>x.id===sel.dataset.statusSelect);
      const prevStatus = r.status;
      try{
        const updated = await updateReferralStatus(r.id, sel.value);
        r.status = updated.status;
        toast(`${r.candidateName} moved to ${sel.value}`, 'success');
      }catch(e){
        sel.value = prevStatus;
        toast('We couldn\u2019t update the status. '+e.message, 'error');
      }
      render();
    });
  });
  document.querySelectorAll('[data-hr-view]').forEach(el=>{
    el.addEventListener('click', async ()=>{
      const r = state.referrals.find(x=>x.id===el.dataset.hrView);
      const wrap = document.createElement('div'); wrap.innerHTML = hrReferralModal(r);
      document.body.appendChild(wrap);
      document.getElementById('closeHrModal').addEventListener('click', ()=>wrap.remove());
      const overlay = document.getElementById('hrModalOverlay');
      overlay.addEventListener('click', async (e)=>{
        if(e.target.id==='hrModalOverlay'){ wrap.remove(); return; }
        const confirmBtn = e.target.closest('[data-confirm-reject]');
        if(confirmBtn){
          const rr = state.referrals.find(x=>x.id===confirmBtn.dataset.confirmReject);
          if(!rr || !confirm(`Confirm rejection for "${rr.candidateName}"? The rejection email will be sent to ${rr.email||'the candidate'} and this cannot be undone.`)) return;
          confirmBtn.disabled = true; confirmBtn.textContent = 'Rejecting…';
          try{
            const res = await api(`/api/referrals/${rr.id}/confirm-rejection`, {method:'POST'});
            toast(res.message || 'Candidate rejected', res.email_status==='sent'?'success':'warning');
            wrap.remove();
            await refreshReferrals();
            render();
          }catch(err){
            toast('We couldn\u2019t confirm the rejection. '+err.message, 'error');
            confirmBtn.disabled = false; confirmBtn.innerHTML = `${icon('check',12)} Confirm Rejection`;
          }
          return;
        }
        const moveBtn = e.target.closest('[data-move-review]');
        if(moveBtn){
          const rr = state.referrals.find(x=>x.id===moveBtn.dataset.moveReview);
          if(!rr) return;
          moveBtn.disabled = true; moveBtn.textContent = 'Moving…';
          try{
            await api(`/api/referrals/${rr.id}/move-to-review`, {method:'POST'});
            toast(`${rr.candidateName} moved to Under Review`, 'success');
            wrap.remove();
            await refreshReferrals();
            render();
          }catch(err){
            toast('We couldn\u2019t move the candidate. '+err.message, 'error');
            moveBtn.disabled = false; moveBtn.innerHTML = `${icon('eye',12)} Move to Under Review`;
          }
          return;
        }
        const raBtn = e.target.closest('[data-reanalyze]');
        if(raBtn){
          const rr = state.referrals.find(x=>x.id===raBtn.dataset.reanalyze);
          if(!rr) return;
          const raEl = document.getElementById('reanalyzeBtn');
          if(raEl){ raEl.disabled=true; raEl.textContent='Re-evaluating…'; }
          try{
            const res = await api(`/api/referrals/${rr.id}/reanalyze`, {method:'POST'});
            const idx = state.referrals.findIndex(x=>x.id===rr.id);
            if(idx>-1) state.referrals[idx] = res.referral;
            toast(`Re-evaluated — JD vs Resume Match ${res.referral.matchPercent||res.referral.jd_vs_resume_match||'—'}%`, 'primary');
            render();
          }catch(err){ toast('We couldn\u2019t re-evaluate the resume. '+err.message, 'error'); }
          if(raEl){ raEl.disabled=false; raEl.innerHTML=`<span style="display:inline-flex;align-items:center;gap:6px;">${icon('refresh',13)} Re-evaluate Resume</span>`; }
          return;
        }
        const ovBtn = e.target.closest('[data-override]');
        if(ovBtn){
          const rr = state.referrals.find(x=>x.id===ovBtn.dataset.override);
          if(rr) openOverrideModal(rr, ()=>{ wrap.remove(); render(); });
          return;
        }
        const delBtn = e.target.closest('[data-delete-ref]');
        if(delBtn){
          const rr = state.referrals.find(x=>x.id===delBtn.dataset.deleteRef);
          if(!rr || !confirm(`Delete the referral for "${rr.candidateName}"? The record is soft-deleted and kept for audit.`)) return;
          try{
            await api(`/api/referrals/${rr.id}`, {method:'DELETE'});
            toast(`Referral for ${rr.candidateName} deleted`, 'success');
            wrap.remove();
            await refreshReferrals();
            render();
          }catch(err){ toast('We couldn\u2019t delete the referral. '+err.message, 'error'); }
          return;
        }
      });
    });
  });
  document.querySelectorAll('.ref-table [data-delete-ref]').forEach(el=>{
    el.addEventListener('click', async ()=>{
      const r = state.referrals.find(x=>x.id===el.dataset.deleteRef);
      if(!r) return;
      if(!confirm(`Delete the referral for "${r.candidateName}"? The record is soft-deleted and kept for audit.`)) return;
      try{
        await api(`/api/referrals/${r.id}`, {method:'DELETE'});
        toast(`Referral for ${r.candidateName} deleted`, 'success');
        document.getElementById('hrModalOverlay')?.remove();
        await refreshReferrals();
        render();
      }catch(e){ toast('We couldn\u2019t delete the referral. '+e.message, 'error'); }
    });
  });

  document.querySelectorAll('.ref-table [data-reanalyze]').forEach(el=>{
    el.addEventListener('click', async ()=>{
      const r = state.referrals.find(x=>x.id===el.dataset.reanalyze);
      if(!r) return;
      const btn = document.getElementById('reanalyzeBtn');
      if(btn){ btn.disabled=true; btn.textContent='Re-evaluating…'; }
      try{
        const res = await api(`/api/referrals/${r.id}/reanalyze`, {method:'POST'});
        const idx = state.referrals.findIndex(x=>x.id===r.id);
        if(idx>-1) state.referrals[idx] = res.referral;
        toast(`Re-evaluated — JD vs Resume Match ${res.referral.matchPercent||res.referral.jd_vs_resume_match||'—'}%`, 'primary');
        render();
      }catch(e){ toast('We couldn\u2019t re-evaluate the resume. '+e.message, 'error'); }
      if(btn){ btn.disabled=false; btn.innerHTML=`<span style="display:inline-flex;align-items:center;gap:6px;">${icon('refresh',13)} Re-evaluate Resume</span>`; }
    });
  });

  document.querySelectorAll('.ref-table [data-override]').forEach(el=>{
    el.addEventListener('click', ()=>{
      const r = state.referrals.find(x=>x.id===el.dataset.override);
      if(r) openOverrideModal(r, ()=>{ document.getElementById('hrModalOverlay')?.remove(); render(); });
    });
  });

  document.querySelectorAll('.ref-table [data-confirm-reject]').forEach(el=>{
    el.addEventListener('click', async ()=>{
      const r = state.referrals.find(x=>x.id===el.dataset.confirmReject);
      if(!r) return;
      if(!confirm(`Confirm rejection for "${r.candidateName}"? The rejection email will be sent to ${r.email||'the candidate'} and this cannot be undone.`)) return;
      const btn = el; btn.disabled = true; btn.textContent = 'Rejecting…';
      try{
        const res = await api(`/api/referrals/${r.id}/confirm-rejection`, {method:'POST'});
        toast(res.message || 'Candidate rejected', res.email_status==='sent'?'success':'warning');
        document.getElementById('hrModalOverlay')?.remove();
        await refreshReferrals();
        render();
      }catch(e){
        toast('We couldn\u2019t confirm the rejection. '+e.message, 'error');
        btn.disabled = false; btn.innerHTML = `${icon('check',12)} Confirm Rejection`;
      }
    });
  });
  document.querySelectorAll('.ref-table [data-move-review]').forEach(el=>{
    el.addEventListener('click', async ()=>{
      const r = state.referrals.find(x=>x.id===el.dataset.moveReview);
      if(!r) return;
      const btn = el; btn.disabled = true; btn.textContent = 'Moving…';
      try{
        const res = await api(`/api/referrals/${r.id}/move-to-review`, {method:'POST'});
        toast(`${r.candidateName} moved to Under Review`, 'success');
        document.getElementById('hrModalOverlay')?.remove();
        await refreshReferrals();
        render();
      }catch(e){
        toast('We couldn\u2019t move the candidate. '+e.message, 'error');
        btn.disabled = false; btn.innerHTML = `${icon('eye',12)} Move to Under Review`;
      }
    });
  });
}

function openOverrideModal(r, onDone){
  const overlay = document.createElement('div');
  overlay.innerHTML = `
  <div class="modal-overlay" id="overrideOverlay">
    <div class="glass-strong pop-in" style="max-width:480px;width:100%;padding:26px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
        <h2 class="display" style="margin:0;font-size:18px;">Override AI Decision</h2>
        <button class="btn btn-ghost" onclick="document.getElementById('overrideOverlay').remove()" style="padding:6px;">${icon('x',16)}</button>
      </div>
      <div style="font-size:12.5px;color:var(--ink-soft);margin-bottom:16px;">${r.candidateName} · current status <strong>${r.status}</strong> · JD match <strong class="mono">${r.matchPercent||'—'}%</strong></div>
      <div style="margin-bottom:14px;">
        <label class="field-label">Move candidate to</label>
        <select class="input" id="overrideTarget">
          <option value="Resume Screening">Resume Screening</option>
          <option value="Under Review">Under Review</option>
          <option value="Shortlisted">Shortlisted</option>
          <option value="Interview Scheduled">Interview Scheduled</option>
          <option value="Interview Completed">Interview Completed</option>
          <option value="Offer Released">Offer Released</option>
          <option value="Selected">Selected</option>
          <option value="Rejected">Rejected</option>
        </select>
      </div>
      <div style="margin-bottom:16px;">
        <label class="field-label">Reason for override (logged for audit)</label>
        <textarea class="input" id="overrideReason" rows="3" placeholder="e.g. Candidate has a strong portfolio despite the keyword gap — override to Shortlisted"></textarea>
      </div>
      <div style="display:flex;gap:10px;">
        <button class="btn btn-primary" id="overrideConfirmBtn" style="flex:1;">Confirm Override</button>
        <button class="btn btn-ghost" onclick="document.getElementById('overrideOverlay').remove()">Cancel</button>
      </div>
      <div id="overrideResult" style="margin-top:12px;"></div>
    </div>
  </div>`;
  document.body.appendChild(overlay);
  document.getElementById('overrideOverlay').addEventListener('click', (e)=>{ if(e.target.id==='overrideOverlay') overlay.remove(); });
  document.getElementById('overrideConfirmBtn').addEventListener('click', async ()=>{
    const btn = document.getElementById('overrideConfirmBtn');
    btn.disabled = true; btn.textContent = 'Overriding…';
    try{
      const updated = await api(`/api/referrals/${r.id}/override`, {method:'POST', body:{
        targetStatus: document.getElementById('overrideTarget').value,
        reason: document.getElementById('overrideReason').value.trim(),
      }});
      const idx = state.referrals.findIndex(x=>x.id===r.id);
      if(idx>-1) state.referrals[idx] = updated;
      document.getElementById('overrideResult').innerHTML = `<div style="padding:10px 12px;border-radius:10px;background:rgba(5,150,105,0.12);font-size:12.5px;color:#059669;">Override recorded — ${r.candidateName} moved to <strong>${updated.status}</strong>.</div>`;
      toast('Decision overridden', 'success');
      setTimeout(()=>{ overlay.remove(); onDone && onDone(); }, 900);
    }catch(e){
      document.getElementById('overrideResult').innerHTML = `<div style="padding:10px 12px;border-radius:10px;background:rgba(220,38,38,0.1);font-size:12.5px;color:var(--coral);">${e.message}</div>`;
      btn.disabled = false; btn.textContent = 'Confirm Override';
    }
  });
}

async function runCompare(idA, idB){
  const a = state.referrals.find(r=>r.id===idA), b = state.referrals.find(r=>r.id===idB);
  const panel = document.getElementById('compareResultPanel');
  panel.innerHTML = `<div class="glass" style="padding:20px;margin-top:16px;"><div class="shimmer" style="height:60px;border-radius:12px;"></div></div>`;
  try{
    const result = await aiCompareCandidates(idA, idB);
    panel.innerHTML = `
    <div class="glass pop-in" style="padding:22px;margin-top:16px;">
      <h3 style="margin:0 0 14px;font-size:15px;">AI Comparison: ${a.candidateName} vs ${b.candidateName}</h3>
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;padding:12px 16px;border-radius:12px;background:rgba(5,150,105,0.1);margin-bottom:14px;">
        <span style="font-weight:700;font-size:13.5px;">Recommended Candidate</span>
        <span style="font-weight:700;color:#059669;overflow-wrap:anywhere;text-align:right;">${result.strongerCandidate==='A'?a.candidateName:b.candidateName}</span>
      </div>
      <p style="font-size:13px;color:var(--ink-soft);margin-bottom:14px;">${result.verdict}</p>
      <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;">
        <div><div style="font-weight:700;font-size:12.5px;margin-bottom:6px;">${a.candidateName}</div><ul style="font-size:12px;color:var(--ink-soft);padding-left:16px;">${(result.candidateAStrengths||[]).map(s=>`<li>${s}</li>`).join('')}</ul></div>
        <div><div style="font-weight:700;font-size:12.5px;margin-bottom:6px;">${b.candidateName}</div><ul style="font-size:12px;color:var(--ink-soft);padding-left:16px;">${(result.candidateBStrengths||[]).map(s=>`<li>${s}</li>`).join('')}</ul></div>
      </div>
    </div>`;
  }catch(e){ panel.innerHTML=''; toast('We couldn\u2019t compare these candidates. Please try again.', 'error'); }
}

function employeesView(){
  return `
  <div class="fade-up">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:10px;">
      <div>
        <h1 class="display" style="font-size:24px;margin:0 0 3px;">Employees</h1>
        <div style="font-size:12.5px;color:var(--ink-soft);">${state.employees.length} employee${state.employees.length===1?'':'s'} · referral activity at a glance</div>
      </div>
      ${isHrRole(state.role) ? `<button class="btn btn-primary" id="openAddEmployee">Add Employee</button>` : ''}
    </div>
    <div id="addEmployeePanel"></div>
    ${state.employees.length===0 ? `
    <div class="glass" style="padding:40px;text-align:center;">
      <h3 style="margin:0 0 6px;">No employees yet</h3>
      <p style="color:var(--ink-soft);margin:0;">${isHrRole(state.role) ? 'Add your first employee to start collecting referrals.' : 'HR hasn\'t added any employees yet.'}</p>
    </div>` : `
    <div class="glass" style="padding:6px;overflow-x:auto;">
      <table class="data-table emp-table">
        <thead><tr><th>Employee</th><th>Department</th><th>Designation</th><th>Account</th><th>Referrals</th><th>Selected</th><th>Status</th>${isHrRole(state.role)?'<th></th>':''}</tr></thead>
        <tbody>
          ${state.employees.map(e=>{
            const refs = state.referrals.filter(r=>r.referredBy===e.id);
            const selected = refs.filter(r=>r.status==='Joined').length;
            return `<tr style="${e.isActive===false?'opacity:0.5;':''}">
              <td><div style="display:flex;align-items:center;gap:10px;"><div style="width:32px;height:32px;border-radius:50%;background:${e.color};color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;flex-shrink:0;">${initials(e.name)}</div><span style="min-width:0;overflow-wrap:anywhere;font-weight:600;">${e.name}</span></div></td>
              <td>${e.dept}</td>
              <td>${e.designation||'—'}</td>
              <td>${e.hasLogin ? `<span class="chip" style="background:${isHrRole(e.role)?'rgba(37,99,235,0.12)':'rgba(8,145,178,0.12)'};color:${isHrRole(e.role)?'var(--primary)':'var(--cyan)'};">${roleLabel(e.role)}</span>` : '<span style="color:var(--ink-soft);font-size:12px;">No account</span>'}</td>
              <td class="mono" style="font-weight:700;">${refs.length}</td><td class="mono">${selected}</td>
              <td>${e.isActive===false ? '<span class="chip" style="background:rgba(220,38,38,0.15);color:var(--coral);">Inactive</span>' : '<span class="chip" style="background:rgba(5,150,105,0.15);color:#059669;">Active</span>'}</td>
              ${isHrRole(state.role)?`<td><button class="btn btn-ghost" data-toggle-employee="${e.id}" data-active="${e.isActive!==false}">${e.isActive===false?'Reactivate':'Deactivate'}</button></td>` : ''}
            </tr>`;
          }).join('')}
        </tbody>
      </table>
    </div>`}
  </div>`;
}
function addEmployeeFormHTML(){
  return `
  <div class="glass pop-in" style="padding:22px;margin-bottom:18px;">
    <h3 style="margin:0 0 14px;font-size:14.5px;">Add Employee</h3>
    <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;">
      <div><label class="field-label">Full Name *</label><input class="input" id="newEmpName"/></div>
      <div><label class="field-label">Work Email *</label><input class="input" id="newEmpEmail"/></div>
      <div><label class="field-label">Department</label><input class="input" id="newEmpDept" value="General"/></div>
      <div><label class="field-label">Designation</label><input class="input" id="newEmpDesignation" placeholder="e.g. Senior Engineer"/></div>
      <div><label class="field-label">Account type</label>
        <select class="input" id="newEmpRole"><option value="employee">Employee</option><option value="hr">HR / Admin</option></select>
      </div>
    </div>
    <label style="display:flex;align-items:center;gap:8px;margin-top:12px;font-size:12.5px;color:var(--ink-soft);">
      <input type="checkbox" id="newEmpCreateLogin" checked/> Create a login for this employee (a temporary password will be generated)
    </label>
    <div style="display:flex;gap:10px;margin-top:14px;">
      <button class="btn btn-primary" id="saveEmployeeBtn">Add Employee</button>
      <button class="btn btn-ghost" id="cancelAddEmployee">Cancel</button>
    </div>
    <div id="addEmployeeResult" style="margin-top:14px;"></div>
  </div>`;
}
function bindEmployeesView(){
  const openBtn = document.getElementById('openAddEmployee');
  if(openBtn) openBtn.addEventListener('click', ()=>{
    document.getElementById('addEmployeePanel').innerHTML = addEmployeeFormHTML();
    document.getElementById('cancelAddEmployee').addEventListener('click', ()=> document.getElementById('addEmployeePanel').innerHTML='');
    document.getElementById('saveEmployeeBtn').addEventListener('click', async ()=>{
      const name = document.getElementById('newEmpName').value.trim();
      const email = document.getElementById('newEmpEmail').value.trim();
      const dept = document.getElementById('newEmpDept').value.trim() || 'General';
      const designation = document.getElementById('newEmpDesignation')?.value?.trim() || '';
      const role = document.getElementById('newEmpRole').value;
      const createLogin = document.getElementById('newEmpCreateLogin').checked;
      if(!name || !email){ toast('Please enter both a name and an email address.', 'amber'); return; }
      const saveBtn = document.getElementById('saveEmployeeBtn');
      saveBtn.disabled = true; saveBtn.textContent = 'Adding…';
      try{
        const result = await api('/api/employees', {method:'POST', body:{name, email, dept, designation, role, createLogin}});
        state.employees.push(result.employee);
        const resultEl = document.getElementById('addEmployeeResult');
        if(result.temporaryPassword){
          resultEl.innerHTML = `<div class="glass" style="padding:14px;font-size:12.5px;">
            <strong>${name}</strong> was added. Share these one-time login details securely:<br/>
            Email: <span class="mono">${email}</span><br/>
            Temporary password: <span class="mono" style="color:var(--primary);font-weight:700;">${result.temporaryPassword}</span>
          </div>`;
        } else {
          resultEl.innerHTML = `<div class="glass" style="padding:14px;font-size:12.5px;">${name} was added (no login account created).</div>`;
        }
        toast('Employee added', 'success');
        render();
      }catch(e){
        toast('We couldn\u2019t add the employee. '+e.message, 'error');
        saveBtn.disabled = false; saveBtn.textContent = 'Add Employee';
      }
    });
  });
  document.querySelectorAll('[data-toggle-employee]').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      const id = btn.dataset.toggleEmployee;
      const currentlyActive = btn.dataset.active === 'true';
      try{
        const updated = await api(`/api/employees/${id}`, {method:'PUT', body:{isActive: !currentlyActive}});
        const idx = state.employees.findIndex(e=>e.id===id);
        if(idx>-1) state.employees[idx] = updated;
        toast(currentlyActive ? 'Employee deactivated' : 'Employee reactivated', 'success');
        render();
      }catch(e){ toast('We couldn\u2019t update the employee. '+e.message, 'error'); }
    });
  });
}

function analyticsView(){
  const ranked = state.employees.map(e=>({...e,count:state.referrals.filter(r=>r.referredBy===e.id).length})).sort((a,b)=>b.count-a.count).slice(0,5);
  const rejected = state.referrals.filter(r=>r.status==='Rejected');
  const pendingReject = state.referrals.filter(r=>r.status==='Auto-Reject Recommended');
  return `
  <div class="fade-up">
    <h1 class="display" style="font-size:24px;margin:0 0 18px;">Reports</h1>
    <div style="display:grid;grid-template-columns:2fr 1fr;gap:16px;">
      <div class="glass" style="padding:20px;"><h3 style="margin:0 0 12px;font-size:14.5px;">Hiring Funnel</h3><canvas id="chartFunnel" height="170"></canvas></div>
      <div class="glass" style="padding:20px;">
        <h3 style="margin:0 0 12px;font-size:14.5px;">Top Referrers</h3>
        ${ranked.map((e,i)=>`<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid rgba(226,232,240,0.08);">
          <div style="width:28px;height:28px;border-radius:50%;background:${e.color};color:#fff;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;">${initials(e.name)}</div>
          <div style="flex:1;font-size:12.5px;">${e.name}</div><div class="mono" style="font-weight:700;color:var(--primary);">${e.count}</div>
        </div>`).join('')}
      </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;margin-top:16px;">
      <div class="glass" style="padding:20px;">
        <h3 style="margin:0 0 12px;font-size:14.5px;">Auto-Reject Recommended — HR Review Required</h3>
        ${pendingReject.length===0?'<div style="font-size:12.5px;color:var(--ink-soft);">No pending auto-reject recommendations awaiting review.</div>':pendingReject.map(r=>`
        <div style="font-size:12.5px;padding:8px 0;border-bottom:1px solid rgba(226,232,240,0.08);"><strong>${r.candidateName}</strong> — ${jobById(r.jobId)?.title||'—'} <span class="mono" style="color:#B45309;font-size:11px;">${r.matchPercent||0}%</span><br/><span style="color:var(--ink-soft);">${r.email||''}</span></div>`).join('')}
      </div>
      <div class="glass" style="padding:20px;">
        <h3 style="margin:0 0 12px;font-size:14.5px;">Rejected Candidates</h3>
        ${rejected.length===0?'<div style="font-size:12.5px;color:var(--ink-soft);">No rejections recorded.</div>':rejected.map(r=>`
        <div style="font-size:12.5px;padding:8px 0;border-bottom:1px solid rgba(226,232,240,0.08);"><strong>${r.candidateName}</strong> — ${jobById(r.jobId)?.title||'—'}<br/><span style="color:var(--ink-soft);">${r.email||''}</span></div>`).join('')}
      </div>
    </div>
  </div>`;
}

function aiSettingsView(){
  const s = state.settings;
  const toggles = [
    ['resumeParsing','AI Resume Parsing','Extract skills, experience & education automatically'],
    ['duplicateDetection','Duplicate Detection','Flag candidates already referred by someone else'],
    ['fraudDetection','Fraud Detection','Detect exaggerated or AI-generated resumes'],
    ['chatAssistant','AI Chat Assistant','Let employees ask the AI assistant questions'],
  ];
  return `
  <div class="fade-up" style="max-width:640px;">
    <h1 class="display" style="font-size:24px;margin:0 0 6px;">AI Settings</h1>
    <p style="color:var(--ink-soft);font-size:13px;margin:0 0 18px;">Model: <span class="mono" style="color:var(--primary);">${state.settings.aiProvider||'ollama'}/${state.settings.aiModel||'llama3.2'}</span></p>
    <div class="glass" style="padding:8px;">
      ${toggles.map(([key,label,desc])=>`
      <div style="display:flex;justify-content:space-between;align-items:center;padding:16px 18px;border-bottom:1px solid rgba(226,232,240,0.08);">
        <div><div style="font-weight:700;font-size:13.5px;">${label}</div><div style="font-size:12px;color:var(--ink-soft);">${desc}</div></div>
        <label style="position:relative;display:inline-block;width:44px;height:24px;">
          <input type="checkbox" data-setting="${key}" ${s[key]?'checked':''} style="opacity:0;width:0;height:0;">
          <span class="toggle-slider" data-slider-for="${key}" style="position:absolute;inset:0;background:${s[key]?'linear-gradient(135deg,#2563EB,#1D4ED8)':'#CBD5E1'};border-radius:24px;transition:.2s;cursor:pointer;"></span>
          <span style="position:absolute;top:3px;left:${s[key]?'23px':'3px'};width:18px;height:18px;background:#fff;border-radius:50%;transition:.2s;pointer-events:none;" data-knob-for="${key}"></span>
        </label>
      </div>`).join('')}
    </div>
  </div>`;
}
function bindAiSettings(){
  document.querySelectorAll('[data-setting]').forEach(inp=>{
    inp.addEventListener('change', async ()=>{
      const key = inp.dataset.setting;
      const prev = state.settings[key];
      state.settings[key] = inp.checked;
      const slider = document.querySelector(`[data-slider-for="${key}"]`);
      const knob = document.querySelector(`[data-knob-for="${key}"]`);
      slider.style.background = inp.checked ? 'linear-gradient(135deg,#2563EB,#1D4ED8)' : '#CBD5E1';
      knob.style.left = inp.checked ? '23px' : '3px';
      try{
        const updated = await updateSettingsBackend({[key]: inp.checked});
        state.settings = updated;
        toast(inp.checked ? 'Feature enabled' : 'Feature disabled', 'success');
      }catch(e){
        state.settings[key] = prev; inp.checked = prev;
        slider.style.background = prev ? 'linear-gradient(135deg,#2563EB,#1D4ED8)' : '#CBD5E1';
        knob.style.left = prev ? '23px' : '3px';
        toast('We couldn\u2019t update the setting. '+e.message, 'error');
      }
    });
  });
}


/* ------------------------------- Bulk Resume Import (HR) ------------------------------- */
let bulkFiles = [];
function bulkImportView(){
  return `
  <div class="fade-up">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;flex-wrap:wrap;gap:10px;">
      <div>
        <h1 class="display" style="font-size:24px;margin:0 0 4px;">Bulk Resume Import</h1>
        <p style="color:var(--ink-soft);font-size:13px;margin:0;">Upload multiple resumes — OCR, JD matching, AI scoring, duplicate / gap / fake-experience detection and candidate passports run automatically.</p>
      </div>
    </div>
    <div class="glass" style="padding:18px;margin-bottom:16px;">
      <div class="search-row">
        <div style="flex:1;min-width:220px;">
          <label class="field-label">Target Job (for JD matching)</label>
          <select class="input" id="bulkJobSelect">
            <option value="">— No job selected (best-effort matching only) —</option>
            ${state.jobs.filter(j=>j.status==='Open').map(j=>`<option value="${j.id}">${j.title} (${j.dept})</option>`).join('')}
          </select>
        </div>
      </div>
      <div id="bulkDropzone" class="bulk-dropzone" style="margin-top:14px;">
        <div style="color:var(--primary);margin-bottom:8px;display:flex;justify-content:center;">${icon('fileText',30)}</div>
        <div style="font-weight:700;font-size:14px;">Drag & drop resume files here</div>
        <div style="font-size:12px;color:var(--ink-soft);margin:6px 0 12px;">or click to browse · PDF, DOC, DOCX, TXT, PNG, JPG (max 10 MB each)</div>
        <button class="btn btn-outline" id="bulkBrowseBtn" type="button">Choose Files</button>
        <input type="file" id="bulkFileInput" multiple accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg,.webp" style="display:none;"/>
      </div>
      <div id="bulkFileList" style="margin-top:12px;"></div>
      <div style="display:flex;align-items:center;gap:12px;margin-top:14px;">
        <button class="btn btn-primary" id="bulkImportBtn" disabled style="display:inline-flex;align-items:center;gap:6px;">${icon('upload',14)} Import Resumes</button>
        <span id="bulkFileCount" style="font-size:12.5px;color:var(--ink-soft);">No files selected</span>
        <button class="btn btn-ghost" id="bulkClearBtn" style="display:none;">Clear</button>
      </div>
    </div>
    <div id="bulkProgress" style="display:none;margin-bottom:16px;">
      <div class="glass" style="padding:18px;">
        <div style="font-size:12.5px;color:var(--ink-soft);margin-bottom:8px;" id="bulkProgressMsg">Processing resumes…</div>
        <div style="height:8px;border-radius:4px;background:#E2E8F0;overflow:hidden;"><div id="bulkProgressBar" style="width:0%;height:100%;background:linear-gradient(120deg,var(--primary),var(--indigo));transition:width .4s;"></div></div>
      </div>
    </div>
    <div id="bulkResults"></div>
  </div>`;
}

function renderBulkFileList(){
  const listEl = document.getElementById('bulkFileList');
  const countEl = document.getElementById('bulkFileCount');
  const btn = document.getElementById('bulkImportBtn');
  const clearBtn = document.getElementById('bulkClearBtn');
  if(!listEl) return;
  if(bulkFiles.length===0){
    listEl.innerHTML = '';
    countEl.textContent = 'No files selected';
    btn.disabled = true;
    clearBtn.style.display = 'none';
    return;
  }
  listEl.innerHTML = `<div style="display:flex;flex-wrap:wrap;gap:8px;">${bulkFiles.map((f,i)=>`
    <div class="glass" style="padding:8px 12px;display:flex;align-items:center;gap:8px;font-size:12px;">
      <span>${icon('fileText',14)}</span><span style="overflow-wrap:anywhere;word-break:break-all;min-width:0;">${f.name}</span>
      <span style="color:var(--ink-soft);font-size:11px;">${(f.size/1024).toFixed(0)} KB</span>
      <button class="btn btn-ghost" style="padding:2px 4px;color:var(--coral);" data-bulk-remove="${i}">${icon('x',14)}</button>
    </div>`).join('')}</div>`;
  countEl.textContent = `${bulkFiles.length} file(s) selected`;
  btn.disabled = false;
  clearBtn.style.display = '';
}

function bindBulkImport(){
  const dropzone = document.getElementById('bulkDropzone');
  const fileInput = document.getElementById('bulkFileInput');

  function addFiles(list){
    for(const f of list){
      if(bulkFiles.length>=50){ toast('You can upload up to 50 files at once.', 'amber'); break; }
      if(bulkFiles.some(x=>x.name===f.name && x.size===f.size)) continue;
      bulkFiles.push(f);
    }
    renderBulkFileList();
  }

  dropzone.addEventListener('click', (e)=>{ if(e.target.id!=='bulkBrowseBtn') fileInput.click(); });
  document.getElementById('bulkBrowseBtn').addEventListener('click', (e)=>{ e.stopPropagation(); fileInput.click(); });
  fileInput.addEventListener('change', ()=> addFiles([...fileInput.files]));
  ['dragover','dragenter'].forEach(ev=> dropzone.addEventListener(ev, (e)=>{ e.preventDefault(); dropzone.classList.add('dragging'); }));
  ['dragleave','drop'].forEach(ev=> dropzone.addEventListener(ev, (e)=>{ e.preventDefault(); dropzone.classList.remove('dragging'); }));
  dropzone.addEventListener('drop', (e)=> addFiles([...e.dataTransfer.files]));

  document.getElementById('bulkFileList').addEventListener('click', (e)=>{
    const rm = e.target.closest('[data-bulk-remove]');
    if(rm){ bulkFiles.splice(parseInt(rm.dataset.bulkRemove,10),1); renderBulkFileList(); }
  });
  document.getElementById('bulkClearBtn').addEventListener('click', ()=>{ bulkFiles = []; renderBulkFileList(); document.getElementById('bulkResults').innerHTML=''; });

  document.getElementById('bulkImportBtn').addEventListener('click', async ()=>{
    if(bulkFiles.length===0) return;
    const btn = document.getElementById('bulkImportBtn');
    const resultsEl = document.getElementById('bulkResults');
    const progress = document.getElementById('bulkProgress');
    const bar = document.getElementById('bulkProgressBar');
    const msg = document.getElementById('bulkProgressMsg');
    btn.disabled = true;
    progress.style.display = 'block';
    resultsEl.innerHTML = '';
    const jobId = document.getElementById('bulkJobSelect').value;
    try{
      const form = new FormData();
      if(jobId) form.append('job_id', jobId);
      bulkFiles.forEach(f=> form.append('files', f));
      bar.style.width = '25%'; msg.textContent = 'Uploading and processing '+bulkFiles.length+' resume'+(bulkFiles.length===1?'':'s')+'…';
      const res = await apiForm('/api/resumes/bulk-import', form);
      bar.style.width = '100%';
      msg.textContent = 'Done — '+res.summary.success+' processed.';
      setTimeout(()=>{ progress.style.display='none'; }, 1200);

      const s = res.summary;
      resultsEl.innerHTML = `
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:16px;">
        ${[
          ['Total Uploaded', s.total, '#2563EB'],
          ['Processed', s.success, '#059669'],
          ['Duplicates', s.duplicates, '#D97706'],
          ['Failed', s.failed, '#DC2626'],
        ].map(([label,val,color])=>`
          <div class="glass" style="padding:12px 16px;">
            <div class="mono" style="font-size:20px;font-weight:700;color:${color};">${val}</div>
            <div style="font-size:11.5px;color:var(--ink-soft);">${label}</div>
          </div>`).join('')}
      </div>
      <div class="glass" style="padding:6px;overflow-x:auto;">
        <table class="data-table">
          <thead><tr><th>File</th><th>Candidate</th><th>JD vs Resume Match</th><th>Duplicate</th><th>Status</th><th>Error</th></tr></thead>
          <tbody>
            ${res.results.map(r=>{
              const match = r.jd_vs_resume_match!==undefined&&r.jd_vs_resume_match!==null?r.jd_vs_resume_match:(r.matchPercent!==undefined&&r.matchPercent!==null?r.matchPercent:null);
              return `<tr>
                <td style="font-size:12px;overflow-wrap:anywhere;word-break:break-all;">${r.fileName}</td>
                <td style="font-size:12.5px;"><strong>${r.candidateName||'—'}</strong></td>
                <td class="mono" style="font-weight:700;color:var(--primary);">${match!==null?match+'%':'—'}</td>
                <td>${r.duplicate?`<span style="color:#D97706;font-size:12px;display:inline-flex;align-items:center;gap:4px;">${icon('warning',12)} ${r.duplicateOf||''}</span>`:'<span style="color:var(--ink-soft);font-size:12px;">No</span>'}</td>
                <td style="font-size:12px;">${r.success?`<span style="color:#059669;display:inline-flex;align-items:center;gap:4px;">${icon('check',12)} Success</span>`:r.duplicate?`<span style="color:#D97706;display:inline-flex;align-items:center;gap:4px;">${icon('minus',12)} Skipped</span>`:`<span style="color:#DC2626;display:inline-flex;align-items:center;gap:4px;">${icon('x',12)} Failed</span>`}</td>
                <td style="font-size:11.5px;color:var(--coral);max-width:200px;">${r.error||''}</td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>
      <div style="margin-top:12px;display:flex;gap:10px;flex-wrap:wrap;">
        <button class="btn btn-primary" data-nav="allReferrals">Go to Referral Management</button>
        <button class="btn btn-outline" id="bulkResetBtn">Clear & Import More</button>
      </div>`;
      document.getElementById('bulkResetBtn')?.addEventListener('click', ()=>{
        bulkFiles = []; renderBulkFileList(); resultsEl.innerHTML=''; progress.style.display='none';
        btn.disabled = true; btn.innerHTML = icon('upload',14) + ' Import Resumes';
      });
      await refreshReferrals();
    }catch(e){
      progress.style.display = 'none';
      resultsEl.innerHTML = `<div class="glass" style="padding:20px;color:var(--coral);font-size:13px;">We couldn\u2019t import the resumes. ${e.message}</div>`;
    }
    btn.disabled = false; btn.innerHTML = icon('upload',14) + ' Import Resumes';
  });
}

async function refreshReferrals(){
  try{
    const isHr = isHrRole(state.role);
    state.referrals = await api(isHr ? '/api/referrals' : '/api/referrals/mine');
  }catch(e){ /* keep stale copy on failure */ }
}

