/* ------------------------------- Bind view-specific handlers after render ------------------------------- */
function bindViewSpecific(){
  drawCharts();
  if(state.view==='dashboard' && (isHrRole(state.role) || isAdminExperience(state.role))) bindPendingReviews();
  if(state.view==='refer') bindReferView();
  if(state.view==='jobs') bindOpenPositions();
  if(state.view==='tracking') bindTrackingView();
  if(state.view==='manageJobs') bindManageJobs();
  if(state.view==='allReferrals') bindAllReferrals();
  if(state.view==='reports') bindReportsView();
  if(state.view==='employees') bindEmployeesView();
  if(state.view==='policy') bindPolicyView();
  if(state.view==='adminSettings') bindAdminSettings();
  if(state.view==='aiSettings') bindAiSettings();
  if(state.view==='userManagement') bindUserManagement();
  if(state.view==='resumeAnalysis') bindResumeAnalysis();
  if(state.view==='bulkImport') bindBulkImport();
  if(state.view==='interviews') bindInterviewsView();
  if(state.view==='profile') bindProfileView();
  if(state.view==='editProfile') bindEditProfileView();
  if(state.view==='emailTemplates') bindEmailTemplatesView();
  if(state.view==='auditLogs') bindAuditLogsView();
  if(state.view==='emailCenter') bindEmailCenterView();
}

function bindProfileView(){
  document.querySelectorAll('[data-nav="editProfile"]').forEach(el=>el.addEventListener('click',()=>nav('editProfile')));
}

function bindEditProfileView(){
  const btn = document.getElementById('saveProfileBtn');
  if(btn) btn.addEventListener('click', async ()=>{
    btn.disabled=true; btn.textContent='Saving\u2026';
    const name = document.getElementById('editProfileName').value.trim();
    const dept = document.getElementById('editProfileDept').value.trim();
    const designation = document.getElementById('editProfileDesig').value.trim();
    const phone = document.getElementById('editProfilePhone').value.trim();
    const location = document.getElementById('editProfileLocation').value.trim();
    if(!name){ toast('Please enter your name.','amber'); btn.disabled=false; btn.textContent='Save Changes'; return; }
    try{
      await api('/api/employees/me/profile',{method:'PATCH',body:{name,dept,designation,phone,location}});
      state.user.name = name;
      const idx = state.employees.findIndex(e=>e.id===state.user.employeeId);
      if(idx>-1){ state.employees[idx].name=name; state.employees[idx].dept=dept; state.employees[idx].designation=designation; state.employees[idx].phone=phone; state.employees[idx].location=location; }
      toast('Profile updated','success');
      nav('profile');
    }catch(e){ toast('We couldn\u2019t update the profile: '+e.message,'error'); btn.disabled=false; btn.textContent='Save Changes'; }
  });
}

async function bindResumeAnalysis(){
  const btn = document.getElementById('loadAnalysisBtn');
  if(!btn) return;
  btn.addEventListener('click', async ()=>{
    const jobId = document.getElementById('analysisJobSelect').value;
    const results = document.getElementById('analysisResults');
    let candidates = state.referrals;
    if(jobId) candidates = candidates.filter(r=>r.jobId===jobId);
    if(candidates.length===0){ results.innerHTML='<div class="glass" style="padding:30px;text-align:center;color:var(--ink-soft);">No candidates found for the selected criteria.</div>'; return; }
    results.innerHTML=`<div class="glass" style="padding:20px;"><div class="shimmer" style="height:60px;border-radius:12px;"></div><div style="font-size:12px;color:var(--ink-soft);margin-top:8px;text-align:center;">AI is analyzing ${candidates.length} candidate(s)…</div></div>`;
    btn.disabled=true;
    try{
      results.innerHTML=`
      <div class="glass" style="padding:6px;overflow-x:auto;">
        <table class="data-table ra-table">
          <thead><tr><th>Candidate</th><th>Job</th><th>JD vs Resume Match</th><th>Strengths</th><th>AI Candidate Summary</th></tr></thead>
          <tbody>
            ${candidates.map(r=>{
              const job = jobById(r.jobId);
              return `<tr>
                <td><strong>${r.candidateName}</strong></td>
                <td>${job?job.title:'—'}</td>
                <td class="mono" style="font-weight:700;color:var(--primary);">${r.matchPercent||'—'}%</td>
                <td style="font-size:11px;max-width:180px;">${(r.strengths||[]).join(', ')||'—'}</td>
                <td style="font-size:11px;max-width:220px;">${r.aiSummary||'—'}</td>
              </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>`;
    }catch(e){ toast('We could not analyze the candidates. '+e.message,'error'); results.innerHTML=''; }
    btn.disabled=false;
  });
}

/* ===========================================================================
   SMART INTERVIEW SCHEDULER & CALENDAR
   =========================================================================== */
async function bindInterviewsView(){
  const container = document.getElementById('interviewTabContent');
  if(!container) return;

  let activeTab = 'list';
  let allReferrals = [];
  let allInterviews = [];
  let allJobs = [];
  let allEmployees = [];
  let calView = 'month';
  let calDate = new Date();

  const ROUNDS = ['HR Screening','Technical Round 1','Technical Round 2','Manager Round','Director Round','HR Final Discussion'];
  const TYPES = ['Microsoft Teams','In-person','Phone'];
  const STATUS_COLORS = {Scheduled:'#2563EB',Completed:'#059669',Cancelled:'#DC2626',Rescheduled:'#D97706',Pending:'#8B5CF6'};

  async function loadData(){
    [allReferrals, allInterviews, allJobs, allEmployees] = await Promise.all([
      api('/api/referrals').catch(()=>[]),
      api('/api/interviews').catch(()=>[]),
      api('/api/jobs').catch(()=>[]),
      api('/api/employees').catch(()=>[]),
    ]);
  }

  function getJobTitle(id){ return (allJobs.find(j=>j.id===id)||{}).title || '\u2014'; }

  function fmtTime(t){
    if(!t) return '';
    const [h,m]=t.split(':').map(Number);
    const ampm=h>=12?'PM':'AM';
    const h12=h>12?h-12:h===12?12:h;
    return `${h12}:${String(m).padStart(2,'0')} ${ampm}`;
  }

  function timeDiff(a,b){
    if(!a||!b) return '';
    const [ah,am]=a.split(':').map(Number),[bh,bm]=b.split(':').map(Number);
    const diff=(bh*60+bm)-(ah*60+am);
    if(diff<=0) return '';
    return diff>=60?`${Math.floor(diff/60)}h ${diff%60?diff%60+'m':''}`:`${diff}m`;
  }

  function switchTab(tab){
    activeTab = tab;
    document.querySelectorAll('.iv-tab').forEach(b=>b.classList.remove('active'));
    document.querySelector(`.iv-tab[data-ivtab="${tab}"]`)?.classList.add('active');
    renderTab();
  }

  document.querySelectorAll('.iv-tab').forEach(b=>{
    b.addEventListener('click', ()=>switchTab(b.dataset.ivtab));
  });

  async function renderTab(){
    if(activeTab==='list') await renderCandidateList();
    else if(activeTab==='calendar') await renderSmartCalendar();
    else if(activeTab==='timeline') await renderTimelineView();
  }

  await loadData();
  switchTab('list');

  /* ===================== CANDIDATE LIST ===================== */
  async function renderCandidateList(){
    container.innerHTML = '<div class="glass" style="padding:20px;"><div class="shimmer" style="height:60px;border-radius:12px;"></div></div>';
    try{
      let search='', statusFilter='';
      const statuses=['Applied','Resume Screening','Shortlisted','Under Review','Auto-Reject Recommended','Interview Scheduled','Interview Completed','Selected','Rejected','Offer Released','Joined'];
      const filterOptions=['Rejected','Screening','Shortlisted','Interview Scheduled','Selected'];

      function statusMatches(r,f){
        if(!f) return true;
        if(f==='Rejected') return r.status==='Rejected';
        if(f==='Screening') return r.status==='Resume Screening';
        return r.status===f;
      }

      function drawTable(list){
        const filtered=list.filter(r=>{
          if(search&&!(r.candidateName||'').toLowerCase().includes(search.toLowerCase())) return false;
          if(!statusMatches(r,statusFilter)) return false;
          return true;
        });

        let html=`
        <div class="glass rm-toolbar-card">
          <div class="rm-toolbar">
            <div class="rm-field iv-field-search">
              <label class="field-label" for="ivSearch">Search Candidates</label>
              <input class="input" id="ivSearch" placeholder="Type a name, email or skill\u2026" value="${search}"/>
            </div>
            <div class="rm-field iv-status-field">
              <label class="field-label" for="ivStatusFilter">Status</label>
              <select class="input" id="ivStatusFilter"><option value="">All</option>${filterOptions.concat(statuses.filter(s=>!filterOptions.includes(s))).map(s=>`<option ${statusFilter===s?'selected':''}>${s}</option>`).join('')}</select>
            </div>
            <div class="iv-count-wrap">
              <div class="rm-count-chip"><strong class="mono">${filtered.length}</strong>&nbsp;/ ${list.length} shown</div>
            </div>
          </div>
        </div>
        <div class="glass" style="padding:6px;overflow-x:auto;">
          <table class="data-table iv-table">
            <thead><tr><th>Candidate</th><th>Applied Job</th><th>Referred By</th><th>Resume</th><th>Match</th><th>Status</th><th>Actions</th></tr></thead>
            <tbody>
              ${filtered.map(r=>{
                const job=jobById(r.jobId);
                const emp=employeeById(r.referredBy);
                const isRejected=r.status==='Rejected';
                return `<tr style="${isRejected?'opacity:0.85;':''}">
                  <td><strong>${r.candidateName}</strong><div style="font-size:11px;color:var(--ink-soft);">${r.email||''}</div>
                    ${r.status==='Auto-Reject Recommended'?`<div style="font-size:10.5px;color:#B45309;margin-top:2px;display:flex;align-items:center;gap:4px;">${icon('zap',11)} Auto-reject recommended \u00b7 HR review required \u00b7 Original match ${r.originalMatch||'\u2014'}%</div>`:''}
                  </td>
                  <td style="font-size:12.5px;">${job?job.title:'\u2014'}</td>
                  <td style="font-size:12.5px;">${emp?emp.name:'\u2014'}</td>
                  <td>${r.resumeFileUrl?`<a href="javascript:void(0)" onclick="openResumeFile('${r.resumeFileUrl}')" style="color:var(--primary);font-size:12px;">View</a>`:'<span style="color:var(--ink-soft);font-size:12px;">None</span>'}</td>
                  <td class="mono" style="font-weight:700;color:${isRejected?'var(--coral)':'var(--primary)'};">${r.matchPercent||'\u2014'}%</td>
                  <td><select class="input iv-status-select" data-ref-id="${r.id}" style="padding:4px 8px;font-size:11px;min-width:130px;${isRejected?'color:#DC2626;':''}">
                    ${statuses.map(s=>`<option ${r.status===s?'selected':''}>${s}</option>`).join('')}
                  </select></td>
                  <td><div style="display:flex;gap:4px;flex-wrap:wrap;">
                    <button class="btn btn-ghost iv-btn-sm" data-schedule-iv='${JSON.stringify({id:r.id,name:r.candidateName,jobId:r.jobId})}'>Schedule</button>
                    ${isRejected?`<button class="btn btn-ghost iv-btn-sm iv-btn-green" data-iv-reopen="${r.id}">Reopen</button>`:''}
                    ${isRejected?`<button class="btn btn-ghost iv-btn-sm iv-btn-amber" data-iv-reanalyze="${r.id}">Re-evaluate</button>`:''}
                    <button class="btn btn-ghost iv-btn-sm" style="color:var(--primary);" data-iv-override="${r.id}">Override</button>
                    <button class="btn btn-ghost iv-btn-sm" data-view-timeline='${r.id}'>Timeline</button>
                  </div></td>
                </tr>`;
              }).join('')}
            </tbody>
          </table>
        </div>
        <div style="margin-top:10px;font-size:12px;color:var(--ink-soft);">Showing ${filtered.length} of ${list.length} candidates \u00b7 auto-rejected candidates are visible here for HR review</div>`;

        const wasFocused=document.activeElement&&document.activeElement.id==='ivSearch';
        container.innerHTML=html;
        if(wasFocused){const si=document.getElementById('ivSearch');if(si){si.focus();si.setSelectionRange(si.value.length,si.value.length);}}

        document.getElementById('ivSearch')?.addEventListener('input',(e)=>{search=e.target.value;drawTable(list);});
        document.getElementById('ivStatusFilter')?.addEventListener('change',(e)=>{statusFilter=e.target.value;drawTable(list);});

        document.querySelectorAll('.iv-status-select').forEach(sel=>{
          sel.addEventListener('change',async()=>{
            try{const updated=await api(`/api/referrals/${sel.dataset.refId}/status`,{method:'PATCH',body:{status:sel.value}});toast('Status updated to '+sel.value,'success');const r=list.find(x=>x.id===sel.dataset.refId);if(r)Object.assign(r,updated);drawTable(list);}
            catch(e){toast('We couldn\u2019t update the status. '+e.message,'error');renderCandidateList();}
          });
        });

        document.querySelectorAll('[data-schedule-iv]').forEach(btn=>{
          btn.addEventListener('click',()=>openSmartScheduler(JSON.parse(btn.dataset.scheduleIv)));
        });
        document.querySelectorAll('[data-iv-reopen]').forEach(btn=>{
          btn.addEventListener('click',async()=>{
            if(!confirm('Reopen this candidate to Resume Screening?')) return;
            try{await api(`/api/referrals/${btn.dataset.ivReopen}/status`,{method:'PATCH',body:{status:'Resume Screening'}});toast('Candidate reopened','success');renderCandidateList();}
            catch(e){toast('We couldn\u2019t reopen the candidate. '+e.message,'error');}
          });
        });
        document.querySelectorAll('[data-iv-reanalyze]').forEach(btn=>{
          btn.addEventListener('click',async()=>{
            btn.disabled=true;btn.textContent='Re-evaluating\u2026';
            try{const res=await api(`/api/referrals/${btn.dataset.ivReanalyze}/reanalyze`,{method:'POST'});toast(`Re-evaluated \u2014 match ${res.referral.matchPercent}%`,'success');renderCandidateList();}
            catch(e){toast('We couldn\u2019t re-evaluate. '+e.message,'error');btn.disabled=false;btn.textContent='Re-evaluate';}
          });
        });
        document.querySelectorAll('[data-iv-override]').forEach(btn=>{
          btn.addEventListener('click',()=>{const r=list.find(x=>x.id===btn.dataset.ivOverride);if(r)openOverrideModal(r,()=>renderCandidateList());});
        });
        document.querySelectorAll('[data-view-timeline]').forEach(btn=>{
          btn.addEventListener('click',async()=>{activeTab='timeline';document.querySelectorAll('.iv-tab').forEach(b=>b.classList.remove('active'));document.querySelector('.iv-tab[data-ivtab="timeline"]')?.classList.add('active');await renderCandidateTimeline(btn.dataset.viewTimeline);});
        });
      }
      drawTable(allReferrals);
    }catch(e){ container.innerHTML=`<div class="glass" style="padding:20px;color:var(--coral);">Could not load the candidate list. ${e.message}</div>`; }
  }

  /* ===================== SMART SCHEDULER MODAL ===================== */
  async function openSmartScheduler(cand, existingIv){
    const modal = document.getElementById('scheduleModal');
    if(!modal) return;
    const job = jobById(cand.jobId);
    const tz = 'Asia/Kolkata (IST)';
    const editMode = !!existingIv;

    function summaryHTML(){
      const round=document.getElementById('schRound')?.value||'';
      const type=document.getElementById('schType')?.value||'';
      const date=document.getElementById('schDate')?.value||'';
      const start=document.getElementById('schStart')?.value||'';
      const end=document.getElementById('schEnd')?.value||'';
      const interviewer=document.getElementById('schInterviewer')?.value||'';
      const dur=timeDiff(start,end);
      const dateFmt=date?new Date(date+'T00:00:00').toLocaleDateString('en-US',{weekday:'short',month:'short',day:'numeric',year:'numeric'}):'\u2014';
      return `<div class="sch-summary-grid">
        <div class="sch-summary-item"><span class="sch-summary-label">Candidate</span><span class="sch-summary-value">${cand.name}</span></div>
        <div class="sch-summary-item"><span class="sch-summary-label">Position</span><span class="sch-summary-value">${job?job.title:'\u2014'}</span></div>
        <div class="sch-summary-item"><span class="sch-summary-label">Round</span><span class="sch-summary-value">${round||'\u2014'}</span></div>
        <div class="sch-summary-item"><span class="sch-summary-label">Mode</span><span class="sch-summary-value">${type||'\u2014'}</span></div>
        <div class="sch-summary-item"><span class="sch-summary-label">Date</span><span class="sch-summary-value">${dateFmt}</span></div>
        <div class="sch-summary-item"><span class="sch-summary-label">Time</span><span class="sch-summary-value">${fmtTime(start)||'\u2014'}${end?' \u2013 '+fmtTime(end):''}</span></div>
        <div class="sch-summary-item"><span class="sch-summary-label">Duration</span><span class="sch-summary-value">${dur||'\u2014'}</span></div>
        <div class="sch-summary-item"><span class="sch-summary-label">Interviewer</span><span class="sch-summary-value">${interviewer||'\u2014'}</span></div>
        <div class="sch-summary-item sch-summary-full"><span class="sch-summary-label">Timezone</span><span class="sch-summary-value sch-tz">${tz}</span></div>
      </div>`;
    }

    const ivData = editMode ? existingIv : {};

    modal.innerHTML = `
    <div class="modal-overlay" id="scheduleOverlay">
      <div class="glass-strong pop-in sch-modal">
        <div class="sch-modal-header">
          <div class="sch-modal-header-left">
            <div class="sch-modal-icon">${icon(editMode?'fileText':'calendar',20)}</div>
            <div>
              <h3 class="sch-modal-title">${editMode?'Edit':'Schedule'} Interview</h3>
              <p class="sch-modal-sub">${cand.name}${job?' \u00b7 '+job.title:''}</p>
            </div>
          </div>
          <button class="btn btn-ghost sch-close-btn" id="schCloseBtn">${icon('x',18)}</button>
        </div>

        <div class="sch-body">
          <div class="sch-two-col">
            <div class="sch-col-left">
              <div class="sch-section">
                <div class="sch-section-title">Interview Details</div>
                <div class="sch-field">
                  <label class="field-label">Interview Round *</label>
                  <select class="input" id="schRound">${ROUNDS.map(r=>`<option ${ivData.roundName===r?'selected':''}>${r}</option>`).join('')}</select>
                </div>
                <div class="sch-field">
                  <label class="field-label">Meeting Mode *</label>
                  <select class="input" id="schType">${TYPES.map(t=>`<option ${ivData.interviewType===t||(t==='Microsoft Teams'&&ivData.interviewType==='Online')?'selected':''}>${t}</option>`).join('')}</select>
                </div>
              </div>

              <div class="sch-section">
                <div class="sch-section-title">Schedule</div>
                <div class="sch-field">
                  <label class="field-label">Interview Date *</label>
                  <input class="input" id="schDate" type="date" value="${ivData.interviewDate||''}"/>
                </div>
                <div class="sch-field">
                  <label class="field-label">Duration *</label>
                  <select class="input" id="schDurationSelect">
                    <option value="30">30 minutes</option>
                    <option value="45">45 minutes</option>
                    <option value="60">60 minutes</option>
                  </select>
                </div>
                <div class="sch-time-row">
                  <div class="sch-field">
                    <label class="field-label">Start Time *</label>
                    <input class="input" id="schStart" type="time" value="${ivData.startTime||''}"/>
                  </div>
                  <span class="sch-time-sep">\u2013</span>
                  <div class="sch-field">
                    <label class="field-label">End Time</label>
                    <input class="input" id="schEnd" type="time" value="${ivData.endTime||''}"/>
                  </div>
                  <div class="sch-dur-badge" id="schDuration">\u2014</div>
                </div>
                <div class="sch-field">
                  <label class="field-label">Interviewer(s) *</label>
                  <input class="input" id="schInterviewer" placeholder="Comma-separated names or emails" value="${ivData.interviewer||''}"/>
                </div>
              </div>

              <div class="sch-section">
                <div class="sch-section-title">Meeting Details</div>
                <div class="sch-field">
                  <label class="field-label">Location / Meeting Link</label>
                  <input class="input" id="schMeetingLink" placeholder="https://teams.microsoft.com/... or Room name" value="${ivData.meetingLink||''}"/>
                </div>
                <div class="sch-field">
                  <label class="field-label">Notes / Instructions</label>
                  <textarea class="input" id="schNotes" rows="2" placeholder="Optional context for the interviewer...">${ivData.notes||''}</textarea>
                </div>
              </div>
            </div>

            <div class="sch-col-right">
              <div class="sch-availability" id="schAvailability"></div>
              <div class="sch-section">
                <div class="sch-section-title">Live Summary</div>
                <div class="sch-summary-card" id="schSummary">${summaryHTML()}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="sch-footer">
          <button class="btn btn-primary" id="saveSchBtn">${editMode?'Update Interview':'Save Interview'}</button>
          <button class="btn btn-outline" id="sendInviteBtn">${icon('mail',14)} Send Invitation</button>
          <button class="btn btn-outline" id="teamsBtn">${icon('video',14)} ${editMode?'Update Teams':'Schedule with Teams'}</button>
          <button class="btn btn-ghost" id="schCancelBtn">Cancel</button>
        </div>
        <div id="schResult"></div>
      </div>
    </div>`;

    /* -- helpers -- */
    function updateSummary(){
      const el=document.getElementById('schSummary');
      if(el) el.innerHTML=summaryHTML();
      const dur=document.getElementById('schDuration');
      if(dur){
        const s=document.getElementById('schStart')?.value;
        const e=document.getElementById('schEnd')?.value;
        dur.textContent=timeDiff(s,e)||'\u2014';
      }
    }

    // Set initial end time from duration if not edit mode
    if(!editMode && !ivData.startTime){
      // No default start time set
    } else if(!editMode && ivData.startTime) {
      const dur=parseInt(document.getElementById('schDurationSelect')?.value||'30',10);
      const [h,m]=ivData.startTime.split(':').map(Number);
      const endMin=h*60+m+dur;
      if(!ivData.endTime) document.getElementById('schEnd').value=`${String(Math.floor(endMin/60)).padStart(2,'0')}:${String(endMin%60).padStart(2,'0')}`;
    }

    ['schRound','schType','schDate','schStart','schEnd','schInterviewer','schNotes','schMeetingLink','schDurationSelect'].forEach(id=>{
      document.getElementById(id)?.addEventListener('input',updateSummary);
      document.getElementById(id)?.addEventListener('change',updateSummary);
    });

    /* -- availability -- */
    let availabilityTimer=null;
    let lastAvailData=null;
    function debounceAvailability(){clearTimeout(availabilityTimer);availabilityTimer=setTimeout(()=>checkAvailability(false),500);}

    document.getElementById('schInterviewer')?.addEventListener('input',debounceAvailability);
    document.getElementById('schDate')?.addEventListener('change',debounceAvailability);
    document.getElementById('schDurationSelect')?.addEventListener('change',()=>{
      // Auto-set end time when duration changes and start is set
      const s=document.getElementById('schStart')?.value;
      if(s){
        const dur=parseInt(document.getElementById('schDurationSelect')?.value||'30',10);
        const [h,m]=s.split(':').map(Number);
        const endMin=h*60+m+dur;
        document.getElementById('schEnd').value=`${String(Math.floor(endMin/60)).padStart(2,'0')}:${String(endMin%60).padStart(2,'0')}`;
        updateSummary();
      }
      debounceAvailability();
    });
    // Also update end time when start time changes
    document.getElementById('schStart')?.addEventListener('change',()=>{
      const s=document.getElementById('schStart')?.value;
      if(s){
        const dur=parseInt(document.getElementById('schDurationSelect')?.value||'30',10);
        const [h,m]=s.split(':').map(Number);
        const endMin=h*60+m+dur;
        document.getElementById('schEnd').value=`${String(Math.floor(endMin/60)).padStart(2,'0')}:${String(endMin%60).padStart(2,'0')}`;
        updateSummary();
      }
    });

    async function checkAvailability(forceRefresh=false){
      const interviewer=document.getElementById('schInterviewer')?.value||'';
      const date=document.getElementById('schDate')?.value||'';
      const dur=parseInt(document.getElementById('schDurationSelect')?.value||'30',10);
      const el=document.getElementById('schAvailability');
      if(!interviewer||!date||!el) return;
      el.innerHTML='<div class="sch-avail-loading"><div class="chart-spinner"></div><span>'+(forceRefresh?'Refreshing calendar\u2026':'Checking availability\u2026')+'</span></div>';
      try{
        const data=await api(`/api/interviews/availability?interviewer=${encodeURIComponent(interviewer)}&date=${date}&duration=${dur}&fetch_calendar=true`);
        lastAvailData=data;

        const calSrc=data.calendarSource||'none';
        const calErr=data.calendarError||'';

        let h='<div class="sch-avail-body">';

        // Calendar error banner — shown prominently when Graph fails
        if(calSrc==='error' && calErr){
          h+=`<div class="sch-cal-error-banner">`;
          h+=icon('alertTriangle',16);
          h+=`<div><strong>Calendar Unavailable</strong><br><span class="sch-cal-error-detail">${calErr}</span></div>`;
          h+=`</div>`;
        }

        // Calendar sync status header
        const calBadge=calSrc==='graph'?'<span class="sch-cal-badge sch-cal-ok">'+icon('check',11)+' Outlook synced</span>':
                         calSrc==='error'?'<span class="sch-cal-badge sch-cal-warn">'+icon('alertTriangle',11)+' Sync failed</span>':'';
        h+=`<div class="sch-avail-header">`;
        h+=`<span class="sch-avail-title">${icon('clock',13)} <strong>Available Slots</strong> (${dur} min \u00b7 IST)</span>`;
        h+=`<div class="sch-avail-header-right">${calBadge}<button class="sch-refresh-btn" id="schRefreshCal" title="Refresh Outlook calendar">${icon('refresh',13)} Refresh</button></div>`;
        h+=`</div>`;

        // Individual time slot grid
        if(data.slots?.length){
          h+=`<div class="sch-slot-grid">`;
          data.slots.forEach(s=>{
            const cls=s.available?'sch-slot sch-slot-available':'sch-slot sch-slot-busy';
            const conflictName=s.conflict?.candidateName||'';
            const title=s.available?`Select ${fmtTime(s.start)} \u2013 ${fmtTime(s.end)}`:`Busy: ${conflictName} (${s.conflict?.roundName||''})`;
            const iconStr=s.available?icon('check',12):icon('x',12);
            h+=`<button class="${cls}" data-slot-start="${s.start}" data-slot-end="${s.end}" title="${title}" ${s.available?'':'disabled'}>`;
            h+=`<span class="sch-slot-time">${fmtTime(s.start)}</span>`;
            h+=`<span class="sch-slot-icon">${iconStr}</span>`;
            h+=`</button>`;
          });
          h+=`</div>`;
        }else if(calSrc!=='error' && !data.busy?.length){
          h+=`<div class="sch-avail-free">`+icon('check',16)+` No conflicts \u2014 all day available</div>`;
        }

        // Calendar events detail section — show ALL calendar events for transparency
        if(data.busy?.length){
          // Separate graph events from internal DB events
          const graphBusy=data.busy.filter(b=>b.source==='graph');
          const internalBusy=data.busy.filter(b=>b.source==='internal');

          if(graphBusy.length){
            h+=`<div class="sch-avail-section-title sch-conflict-header">${icon('calendar',13)} <strong>Outlook Calendar Events</strong> (${graphBusy.length})</div>`;
            graphBusy.forEach(b=>{
              h+=`<div class="sch-avail-conflict sch-conflict-graph">`;
              h+=`<span class="sch-conflict-dot sch-dot-graph"></span>`;
              h+=`<span class="sch-conflict-event"><strong>${b.candidateName}</strong> <span class="sch-conflict-sub">${b.roundName}</span></span>`;
              h+=`<span class="sch-conflict-time">${fmtTime(b.startTime)}\u2013${fmtTime(b.endTime)}</span>`;
              h+=`</div>`;
            });
          }
          if(internalBusy.length){
            h+=`<div class="sch-avail-section-title sch-conflict-header">${icon('users',13)} <strong>Scheduled Interviews</strong> (${internalBusy.length})</div>`;
            internalBusy.forEach(b=>{
              h+=`<div class="sch-avail-conflict">`;
              h+=`<span class="sch-conflict-dot"></span>`;
              h+=`<span class="sch-conflict-event"><strong>${b.candidateName}</strong> <span class="sch-conflict-sub">${b.roundName}</span></span>`;
              h+=`<span class="sch-conflict-time">${fmtTime(b.startTime)}\u2013${fmtTime(b.endTime)}</span>`;
              h+=`</div>`;
            });
          }
        }

        h+=`</div>`;
        el.innerHTML=h;

        // Bind slot click handlers
        el.querySelectorAll('.sch-slot-available').forEach(btn=>{
          btn.addEventListener('click',()=>{
            document.getElementById('schStart').value=btn.dataset.slotStart;
            document.getElementById('schEnd').value=btn.dataset.slotEnd;
            updateSummary();
            // Highlight selected slot
            el.querySelectorAll('.sch-slot').forEach(s=>s.classList.remove('sch-slot-selected'));
            btn.classList.add('sch-slot-selected');
          });
        });

        // Bind refresh button
        document.getElementById('schRefreshCal')?.addEventListener('click',()=>checkAvailability(true));
      }catch(e){el.innerHTML='<div class="sch-avail-error">'+icon('alertTriangle',14)+' Could not check availability: '+e.message+'</div>';}
    }

    /* -- save -- */
    let createdId=existingIv?.id||null;

    function getFormBody(){
      return {
        referralId:cand.id,jobId:cand.jobId,candidateName:cand.name,
        roundName:document.getElementById('schRound').value,
        interviewType:document.getElementById('schType').value,
        interviewDate:document.getElementById('schDate').value,
        startTime:document.getElementById('schStart').value,
        endTime:document.getElementById('schEnd').value,
        interviewer:document.getElementById('schInterviewer').value,
        meetingLink:document.getElementById('schMeetingLink').value,
        location:'',notes:document.getElementById('schNotes').value,
      };
    }

    document.getElementById('saveSchBtn')?.addEventListener('click',async()=>{
      const btn=document.getElementById('saveSchBtn');
      btn.disabled=true;btn.textContent='Saving\u2026';
      try{
        let iv;
        if(editMode){iv=await api(`/api/interviews/${existingIv.id}`,{method:'PUT',body:getFormBody()});}
        else{iv=await api('/api/interviews',{method:'POST',body:getFormBody()});}
        createdId=iv.id;
        toast(editMode?'Interview updated':'Interview scheduled','success');
        document.getElementById('scheduleOverlay').remove();
        await loadData();
        if(!editMode){await api(`/api/referrals/${cand.id}/status`,{method:'PATCH',body:{status:'Interview Scheduled'}});await loadData();}
        renderTab();
      }catch(e){toast('We couldn\u2019t save the interview. '+e.message,'error');btn.disabled=false;btn.textContent=editMode?'Update Interview':'Save Interview';}
    });

    document.getElementById('sendInviteBtn')?.addEventListener('click',async()=>{
      const btn=document.getElementById('sendInviteBtn');
      btn.disabled=true;btn.textContent='Sending\u2026';
      try{
        let id=createdId;
        if(!id){const iv=await api('/api/interviews',{method:'POST',body:getFormBody()});id=iv.id;createdId=id;}
        await api(`/api/interviews/${id}/send-invitation`,{method:'POST'});
        toast('Invitation sent','success');
      }catch(e){toast('We couldn\u2019t send the invitation. '+e.message,'error');}
      btn.disabled=false;btn.innerHTML=`${icon('mail',14)} Send Invitation`;
    });

    document.getElementById('teamsBtn')?.addEventListener('click',async()=>{
      const btn=document.getElementById('teamsBtn');
      const resultEl=document.getElementById('schResult');
      btn.disabled=true;btn.textContent='Scheduling Teams interview\u2026';
      try{
        let id=createdId;
        if(!id){const iv=await api('/api/interviews',{method:'POST',body:getFormBody()});id=iv.id;createdId=id;}
        if(!id) throw new Error('Save the interview first.');
        const iv=await api(`/api/interviews/${id}/schedule-teams`,{method:'POST',body:{timezone:'Asia/Kolkata'}});
        if(iv&&iv.teamsJoinUrl){
          document.getElementById('schMeetingLink').value=iv.teamsJoinUrl;
          resultEl.innerHTML=`<div class="sch-success-card"><div class="sch-success-header">${icon('check',18)} Interview Scheduled Successfully</div><div class="sch-success-body"><div><strong>When:</strong> ${iv.interviewDate} ${fmtTime(iv.startTime)}</div><div><strong>Interviewer:</strong> ${iv.interviewer||'-'}</div>${iv.organizer?`<div><strong>Organizer:</strong> ${iv.organizer}</div>`:''}<div><strong>Teams:</strong> <a href="${iv.teamsJoinUrl}" target="_blank" style="color:var(--primary);word-break:break-all;">${iv.teamsJoinUrl}</a></div><div><strong>Calendar:</strong> ${iv.calendarEventId?'Created':'Pending'}</div></div></div>`;
          toast('Teams interview scheduled','success');
        }else{
          resultEl.innerHTML=`<div style="color:var(--coral);font-size:12.5px;">${(iv&&iv.detail)||'The interview could not be scheduled. Please try again.'}</div>`;
          toast('Scheduling failed','error');
        }
      }catch(e){resultEl.innerHTML=`<div style="color:var(--coral);font-size:12.5px;">${e.message}</div>`;toast('We couldn\u2019t schedule the Teams interview. '+e.message,'error');}
      btn.disabled=false;btn.innerHTML=`${icon('video',14)} Schedule with Teams`;
    });

    document.getElementById('schCloseBtn')?.addEventListener('click',()=>document.getElementById('scheduleOverlay')?.remove());
    document.getElementById('schCancelBtn')?.addEventListener('click',()=>document.getElementById('scheduleOverlay')?.remove());
    document.getElementById('scheduleOverlay')?.addEventListener('click',(e)=>{if(e.target.id==='scheduleOverlay')e.target.remove();});

    setTimeout(checkAvailability,400);
  }

  /* ===================== SMART CALENDAR ===================== */
  async function renderSmartCalendar(view){
    if(view) calView=view;
    container.innerHTML='<div class="glass" style="padding:20px;"><div class="shimmer" style="height:60px;border-radius:12px;"></div></div>';

    try{
      let interviews=[];
      const now=new Date();

      if(calView==='month'){
        const y=calDate.getFullYear(),m=calDate.getMonth()+1;
        interviews=await api(`/api/interviews/calendar?year=${y}&month=${m}`);
      }else if(calView==='week'){
        const sow=new Date(calDate);sow.setDate(calDate.getDate()-calDate.getDay());
        const eow=new Date(sow);eow.setDate(sow.getDate()+6);
        interviews=await api(`/api/interviews/calendar?start=${sow.toISOString().slice(0,10)}&end=${eow.toISOString().slice(0,10)}`);
      }else if(calView==='day'){
        const ds=calDate.toISOString().slice(0,10);
        interviews=await api(`/api/interviews/calendar?start=${ds}&end=${ds}`);
      }else{
        interviews=await api('/api/interviews');
      }

      const viewTabs=['month','week','day','agenda'].map(v=>`<button class="cal-view-btn ${calView===v?'active':''}" data-cal-view="${v}">${v.charAt(0).toUpperCase()+v.slice(1)}</button>`).join('');

      const navTitle=calView==='month'?calDate.toLocaleString('en-US',{month:'long',year:'numeric'}):
                     calView==='week'?`Week of ${calDate.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})}`:
                     calView==='day'?calDate.toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric',year:'numeric'}):
                     'All Interviews';

      let bodyHTML='';
      if(calView==='month') bodyHTML=renderMonthView(interviews);
      else if(calView==='week') bodyHTML=renderWeekView(interviews);
      else if(calView==='day') bodyHTML=renderDayView(interviews);
      else bodyHTML=renderAgendaView(interviews);

      const legend=Object.entries(STATUS_COLORS).map(([s,c])=>`<span class="cal-legend-item"><span class="cal-legend-dot" style="background:${c};"></span>${s}</span>`).join('');

      container.innerHTML=`
      <div class="cal-toolbar">
        <div class="cal-nav">
          <button class="cal-nav-btn" id="calPrev">${icon('chevronLeft',16)}</button>
          <button class="cal-nav-btn cal-today-btn" id="calToday">Today</button>
          <button class="cal-nav-btn" id="calNext">${icon('chevronRight',16)}</button>
          <h3 class="cal-title">${navTitle}</h3>
        </div>
        <div class="cal-view-tabs">${viewTabs}</div>
      </div>
      <div class="cal-legend">${legend}</div>
      <div class="cal-body glass">${bodyHTML}</div>`;

      document.querySelectorAll('[data-cal-view]').forEach(b=>b.addEventListener('click',()=>renderSmartCalendar(b.dataset.calView)));
      document.getElementById('calPrev')?.addEventListener('click',()=>{navigateCal(-1);renderSmartCalendar();});
      document.getElementById('calNext')?.addEventListener('click',()=>{navigateCal(1);renderSmartCalendar();});
      document.getElementById('calToday')?.addEventListener('click',()=>{calDate=new Date();renderSmartCalendar();});

      document.querySelectorAll('[data-cal-iv-id]').forEach(el=>{
        el.addEventListener('click',()=>{const iv=interviews.find(x=>x.id===el.dataset.calIvId);if(iv)openInterviewDetails(iv);});
      });
    }catch(e){container.innerHTML=`<div class="glass" style="padding:20px;color:var(--coral);">Calendar failed: ${e.message}</div>`;}
  }

  function navigateCal(dir){
    if(calView==='month') calDate.setMonth(calDate.getMonth()+dir);
    else if(calView==='week') calDate.setDate(calDate.getDate()+dir*7);
    else if(calView==='day') calDate.setDate(calDate.getDate()+dir);
  }

  function renderMonthView(interviews){
    const y=calDate.getFullYear(),m=calDate.getMonth()+1;
    const daysInMonth=new Date(y,m,0).getDate();
    const firstDay=new Date(y,m-1,1).getDay();
    const now=new Date();
    let html='<div class="cal-month-grid">';
    ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].forEach(d=>{html+=`<div class="cal-grid-header">${d}</div>`;});
    for(let i=0;i<firstDay;i++) html+='<div class="cal-day-cell cal-day-empty"></div>';
    for(let d=1;d<=daysInMonth;d++){
      const ds=`${y}-${String(m).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
      const dayIvs=interviews.filter(iv=>iv.interviewDate===ds);
      const isToday=d===now.getDate()&&m===now.getMonth()+1&&y===now.getFullYear();
      html+=`<div class="cal-day-cell ${isToday?'cal-today':''}">
        <div class="cal-day-num ${isToday?'cal-today-num':''}">${d}</div>
        <div class="cal-day-events">
          ${dayIvs.slice(0,3).map(iv=>{
            const c=STATUS_COLORS[iv.status]||'#2563EB';
            return `<div class="cal-event-chip" data-cal-iv-id="${iv.id}">
              <div class="cal-event-indicator" style="background:${c};"></div>
              <div class="cal-event-text"><span class="cal-event-name">${iv.candidateName}</span><span class="cal-event-round">${iv.roundName}</span></div>
              <span class="cal-event-time">${fmtTime(iv.startTime)}</span>
            </div>`;
          }).join('')}
          ${dayIvs.length>3?`<div class="cal-more">+${dayIvs.length-3} more</div>`:''}
        </div>
      </div>`;
    }
    html+='</div>';
    return html;
  }

  function renderWeekView(interviews){
    const sow=new Date(calDate);sow.setDate(calDate.getDate()-calDate.getDay());
    const now=new Date();
    let html='<div class="cal-week">';
    for(let d=0;d<7;d++){
      const day=new Date(sow);day.setDate(sow.getDate()+d);
      const ds=day.toISOString().slice(0,10);
      const dayIvs=interviews.filter(iv=>iv.interviewDate===ds);
      const isToday=ds===now.toISOString().slice(0,10);
      html+=`<div class="cal-week-day ${isToday?'cal-week-today':''}">
        <div class="cal-week-header"><span class="cal-week-dayname">${day.toLocaleDateString('en-US',{weekday:'short'})}</span><span class="cal-week-daynum ${isToday?'cal-week-daynum-today':''}">${day.getDate()}</span></div>
        <div class="cal-week-events">`;
      dayIvs.forEach(iv=>{
        const c=STATUS_COLORS[iv.status]||'#2563EB';
        html+=`<div class="cal-week-event" data-cal-iv-id="${iv.id}" style="border-left:3px solid ${c};">
          <div class="cal-week-event-name">${iv.candidateName}</div>
          <div class="cal-week-event-detail">${fmtTime(iv.startTime)}${iv.endTime?' \u2013 '+fmtTime(iv.endTime):''} \u00b7 ${iv.roundName}</div>
        </div>`;
      });
      if(!dayIvs.length) html+='<div class="cal-week-empty">No interviews</div>';
      html+='</div></div>';
    }
    html+='</div>';
    return html;
  }

  function renderDayView(interviews){
    const ds=calDate.toISOString().slice(0,10);
    const dayIvs=interviews.filter(iv=>iv.interviewDate===ds);
    if(!dayIvs.length) return '<div class="cal-empty-state">No interviews scheduled for this day.</div>';
    const sorted=[...dayIvs].sort((a,b)=>(a.startTime||'').localeCompare(b.startTime||''));
    let html='<div class="cal-day-list">';
    sorted.forEach(iv=>{
      const c=STATUS_COLORS[iv.status]||'#2563EB';
      html+=`<div class="cal-day-card" data-cal-iv-id="${iv.id}" style="border-left:4px solid ${c};">
        <div class="cal-day-card-left">
          <div class="cal-day-card-time">${fmtTime(iv.startTime)}${iv.endTime?' \u2013 '+fmtTime(iv.endTime):''}</div>
          <div class="cal-day-card-dur">${timeDiff(iv.startTime,iv.endTime)||''}</div>
        </div>
        <div class="cal-day-card-body">
          <div class="cal-day-card-name">${iv.candidateName}</div>
          <div class="cal-day-card-meta">${getJobTitle(iv.jobId)} \u00b7 ${iv.roundName} \u00b7 ${iv.interviewer||'Unassigned'}</div>
        </div>
        <span class="cal-day-card-badge" style="background:${c}15;color:${c};">${iv.status}</span>
      </div>`;
    });
    html+='</div>';
    return html;
  }

  function renderAgendaView(interviews){
    if(!interviews.length) return '<div class="cal-empty-state">No interviews found.</div>';
    const sorted=[...interviews].sort((a,b)=>(a.interviewDate||'').localeCompare(b.interviewDate||'')||(a.startTime||'').localeCompare(b.startTime||''));
    let html='<div class="cal-agenda">';
    let lastDate='';
    sorted.forEach(iv=>{
      if(iv.interviewDate!==lastDate){
        lastDate=iv.interviewDate;
        const d=lastDate?new Date(lastDate+'T00:00:00').toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric',year:'numeric'}):'No Date';
        html+=`<div class="cal-agenda-date">${d}</div>`;
      }
      const c=STATUS_COLORS[iv.status]||'#2563EB';
      html+=`<div class="cal-agenda-item" data-cal-iv-id="${iv.id}">
        <div class="cal-agenda-time">${fmtTime(iv.startTime)}${iv.endTime?' \u2013 '+fmtTime(iv.endTime):''}</div>
        <div class="cal-agenda-info">
          <div class="cal-agenda-name">${iv.candidateName}</div>
          <div class="cal-agenda-meta">${getJobTitle(iv.jobId)} \u00b7 ${iv.roundName} \u00b7 ${iv.interviewer||'Unassigned'}</div>
        </div>
        <span class="cal-agenda-badge" style="background:${c}15;color:${c};">${iv.status}</span>
      </div>`;
    });
    html+='</div>';
    return html;
  }

  /* ===================== INTERVIEW DETAILS MODAL ===================== */
  async function openInterviewDetails(iv){
    const modal=document.getElementById('interviewDetailModal');
    if(!modal) return;
    const c=STATUS_COLORS[iv.status]||'#2563EB';
    const dur=timeDiff(iv.startTime,iv.endTime);
    const job=getJobTitle(iv.jobId);
    const dateFmt=iv.interviewDate?new Date(iv.interviewDate+'T00:00:00').toLocaleDateString('en-US',{weekday:'long',month:'long',day:'numeric',year:'numeric'}):'\u2014';
    const meetingType=iv.interviewType||'Online';
    const meetingBadge=meetingType==='Microsoft Teams'||meetingType==='Online'?icon('video',13):meetingType==='Phone'?icon('phone',13):icon('mapPin',13);

    modal.innerHTML=`
    <div class="modal-overlay" id="ivDetailOverlay">
      <div class="glass-strong pop-in iv-detail-modal">
        <div class="iv-detail-header" style="border-top:4px solid ${c};">
          <div class="iv-detail-header-top">
            <div class="iv-detail-candidate">
              <div class="iv-detail-avatar" style="background:${c}18;color:${c};">${(iv.candidateName||'C')[0].toUpperCase()}</div>
              <div>
                <h2 class="iv-detail-name">${iv.candidateName}</h2>
                <p class="iv-detail-job">${job}</p>
              </div>
            </div>
            <button class="btn btn-ghost sch-close-btn" id="ivDetailClose">${icon('x',18)}</button>
          </div>
          <div class="iv-detail-badges">
            <span class="iv-detail-badge" style="background:${c}18;color:${c};">${iv.status}</span>
            <span class="iv-detail-badge">${meetingBadge} ${meetingType}</span>
            ${dur?`<span class="iv-detail-badge">${icon('clock',12)} ${dur}</span>`:''}
          </div>
        </div>
        <div class="iv-detail-body">
          <div class="iv-detail-grid">
            <div class="iv-detail-field"><span class="iv-detail-label">Round</span><span class="iv-detail-val">${iv.roundName||'\u2014'}</span></div>
            <div class="iv-detail-field"><span class="iv-detail-label">Date</span><span class="iv-detail-val">${dateFmt}</span></div>
            <div class="iv-detail-field"><span class="iv-detail-label">Time</span><span class="iv-detail-val">${fmtTime(iv.startTime)||'\u2014'}${iv.endTime?' \u2013 '+fmtTime(iv.endTime):''}</span></div>
            <div class="iv-detail-field"><span class="iv-detail-label">Interviewer(s)</span><span class="iv-detail-val">${iv.interviewer||'Unassigned'}</span></div>
            <div class="iv-detail-field"><span class="iv-detail-label">Meeting</span><span class="iv-detail-val">${iv.meetingLink?`<a href="${iv.meetingLink}" target="_blank" style="color:var(--primary);word-break:break-all;">Join Link</a>`:'\u2014'}</span></div>
            <div class="iv-detail-field iv-detail-field-full"><span class="iv-detail-label">Notes</span><span class="iv-detail-val">${iv.notes||'\u2014'}</span></div>
          </div>
        </div>
        <div class="iv-detail-footer">
          ${iv.meetingLink?`<a href="${iv.meetingLink}" target="_blank" class="btn btn-primary">${icon('video',14)} Join Meeting</a>`:''}
          <button class="btn btn-outline" data-iv-edit="${iv.id}">${icon('edit',14)} Edit</button>
          <button class="btn btn-outline iv-btn-amber" data-iv-reschedule="${iv.id}">${icon('calendar',14)} Reschedule</button>
          <button class="btn btn-outline iv-btn-coral" data-iv-cancel="${iv.id}">${icon('x',14)} Cancel</button>
          <button class="btn btn-ghost" id="ivDetailCloseBtn">Close</button>
        </div>
      </div>
    </div>`;

    document.getElementById('ivDetailClose')?.addEventListener('click',()=>modal.innerHTML='');
    document.getElementById('ivDetailCloseBtn')?.addEventListener('click',()=>modal.innerHTML='');
    document.getElementById('ivDetailOverlay')?.addEventListener('click',(e)=>{if(e.target.id==='ivDetailOverlay')modal.innerHTML='';});

    document.querySelectorAll('[data-iv-edit]').forEach(btn=>{
      btn.addEventListener('click',()=>{modal.innerHTML='';openSmartScheduler({id:iv.referralId,name:iv.candidateName,jobId:iv.jobId},iv);});
    });
    document.querySelectorAll('[data-iv-reschedule]').forEach(btn=>{
      btn.addEventListener('click',async()=>{
        if(!confirm('Mark this interview as Rescheduled?')) return;
        try{await api(`/api/interviews/${iv.id}`,{method:'PUT',body:{status:'Rescheduled'}});toast('Interview rescheduled','success');modal.innerHTML='';await loadData();renderTab();}
        catch(e){toast('We couldn\u2019t reschedule the interview. '+e.message,'error');}
      });
    });
    document.querySelectorAll('[data-iv-cancel]').forEach(btn=>{
      btn.addEventListener('click',async()=>{
        if(!confirm('Cancel this interview?')) return;
        try{await api(`/api/interviews/${iv.id}`,{method:'PUT',body:{status:'Cancelled'}});toast('Interview cancelled','success');modal.innerHTML='';await loadData();renderTab();}
        catch(e){toast('We couldn\u2019t cancel the interview. '+e.message,'error');}
      });
    });
  }

  /* ===================== TIMELINE ===================== */
  async function renderTimelineView(){
    try{
      container.innerHTML=`
      <div class="glass" style="padding:14px;margin-bottom:14px;">
        <label class="field-label">Select Candidate</label>
        <select class="input" id="timelineSelect" style="max-width:400px;">
          <option value="">Choose a candidate...</option>
          ${allReferrals.map(r=>`<option value="${r.id}">${r.candidateName} \u2014 ${r.status}</option>`).join('')}
        </select>
      </div>
      <div id="timelineResult"></div>`;
      document.getElementById('timelineSelect')?.addEventListener('change',async(e)=>{if(e.target.value)await renderCandidateTimeline(e.target.value);});
    }catch(e){container.innerHTML=`<div class="glass" style="padding:20px;color:var(--coral);">${e.message}</div>`;}
  }

  async function renderCandidateTimeline(refId){
    const result=document.getElementById('timelineResult')||container;
    if(!result) return;
    result.innerHTML='<div class="glass" style="padding:20px;"><div class="shimmer" style="height:40px;border-radius:12px;"></div></div>';
    try{
      const data=await api(`/api/activity/timeline/${refId}`);
      if(!data.timeline||!data.timeline.length){result.innerHTML='<div class="glass" style="padding:30px;text-align:center;color:var(--ink-soft);">No timeline events found.</div>';return;}
      result.innerHTML=`
      <div class="glass" style="padding:18px;">
        <div style="margin-bottom:14px;"><h3 style="margin:0 0 4px;font-size:15px;">${data.candidateName} \u2014 Hiring Timeline</h3>
        <span class="chip" style="background:rgba(37,99,235,0.12);color:var(--primary);">Current: ${data.currentStatus}</span></div>
        <div class="tl-track">
          ${data.timeline.map(t=>{
            const color=t.type==='interview'?'#2563EB':t.type==='activity'?'#1D4ED8':'#059669';
            return `<div class="tl-item">
              <div class="tl-dot" style="background:${color};box-shadow:0 0 0 3px ${color}22;"></div>
              <div class="tl-content">
                <div class="tl-title">${icon('fileText',14)} ${t.title}</div>
                <div class="tl-desc">${t.description}</div>
                <div class="tl-meta">${t.performedBy?'By '+t.performedBy+' \u00b7 ':''}${t.date?new Date(t.date).toLocaleString():''}</div>
              </div>
            </div>`;
          }).join('')}
        </div>
      </div>`;
    }catch(e){result.innerHTML=`<div class="glass" style="padding:20px;color:var(--coral);">${e.message}</div>`;}
  }
}

async function bindUserManagement(){
  const container = document.getElementById('usersList');
  if(!container) return;
  container.innerHTML=`<div class="glass" style="padding:20px;"><div class="shimmer" style="height:60px;border-radius:12px;"></div></div>`;
  try{
    const users = await api('/api/admin/users');
    container.innerHTML=`
    <div class="glass" style="padding:6px;overflow-x:auto;">
      <table class="data-table">
        <thead><tr><th>User</th><th>Email</th><th>Role</th><th>Status</th><th>Joined</th><th>Action</th></tr></thead>
        <tbody>
          ${users.map(u=>`<tr>
            <td><strong>${u.name}</strong></td>
            <td>${u.email}</td>
            <td><select class="input" style="padding:6px 10px;font-size:12px;" data-user-role="${u.id}">
              ${['employee','manager','hr','hr_manager','chro','vp','cto','ceo','system_admin','admin'].map(r=>`<option value="${r}" ${u.role===r?'selected':''}>${roleLabel(r)}</option>`).join('')}
            </select></td>
            <td>${u.isActive?'<span class="chip" style="background:rgba(5,150,105,0.15);color:#059669;">Active</span>':'<span class="chip" style="background:rgba(220,38,38,0.15);color:var(--coral);">Inactive</span>'}</td>
            <td style="font-size:12px;color:var(--ink-soft);">${fmtRelative(u.created_at)}</td>
            <td></td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>`;
    document.querySelectorAll('[data-user-role]').forEach(sel=>{
      sel.addEventListener('change', async ()=>{
        try{
          await api(`/api/admin/users/${sel.dataset.userRole}/role?role=${sel.value}`,{method:'PATCH'});
          toast('Role updated','success');
        }catch(e){ toast('We couldn\u2019t update the role. '+e.message,'error'); render(); }
      });
    });
    document.getElementById('refreshUsersBtn')?.addEventListener('click',()=>bindUserManagement());
  }catch(e){ container.innerHTML='<div class="glass" style="padding:20px;color:var(--coral);">Could not load users: '+e.message+'</div>'; }
}

/* ------------------------------- Polling (real-time sync against the backend) ------------------------------- */
let pollTimer=null;
function startPolling(){
  if(pollTimer) return;
  pollTimer = setInterval(async ()=>{
    if(!state.user || !state.role) return;
    try{
      const canSeeTeam = isHrRole(state.role) || state.role==='manager';
      const [referrals, notifications] = await Promise.allSettled([
        api(canSeeTeam ? '/api/referrals' : '/api/referrals/mine'),
        api('/api/notifications'),
      ]);
      if(referrals.status==='fulfilled' && Array.isArray(referrals.value) && JSON.stringify(referrals.value)!==JSON.stringify(state.referrals)){
        state.referrals = referrals.value;
        if(['dashboard','tracking','allReferrals','reports','leaderboard','rewards'].includes(state.view)) render();
      }
      if(notifications.status==='fulfilled' && Array.isArray(notifications.value)){
        const newCount = notifications.value.filter(n=>n&&!n.isRead).length;
        if(newCount !== state.unreadCount){
          state.notifications = notifications.value;
          state.unreadCount = newCount;
          render();
        }
      }
    }catch(e){ /* stay quiet on transient poll failures */ }
  }, 9000);
}

/* ------------------------------- Init ------------------------------- */
(async function init(){
  const params = new URLSearchParams(window.location.search);
  const resetToken = params.get('reset_token');
  if(resetToken){
    state.resetToken = resetToken;
    state.loginMode = 'reset';
    history.replaceState({}, '', window.location.pathname);
    render();
    return;
  }

  const ssoToken = params.get('sso_token');
  if(ssoToken){
    setToken(ssoToken);
    history.replaceState({}, '', window.location.pathname);
  }
  const ssoError = params.get('sso_error');
  if(ssoError){
    history.replaceState({}, '', window.location.pathname);
    render();
    setTimeout(()=> toast('Sign In failed: '+decodeURIComponent(ssoError), 'error'), 200);
    return;
  }

  const token = getToken();
  if(!token){ render(); return; }
  try{
    const user = await api('/api/auth/me');
    state.user = user; state.role = user.role;
    if(state.role === 'candidate'){
      await loadCandidateData();
      render();
    } else {
      await loadAllData();
      state._loaded = true;
      render();
      startPolling();
    }
  }catch(e){
    clearToken();
    render();
  }
})();
