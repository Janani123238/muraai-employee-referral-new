/* ================================ Candidate Portal ================================ */
let _cpView = 'dashboard';
let _cpApplications = [];
let _cpProfile = {};
let _cpLastApplication = null;

function cpNav(view){ _cpView = view; render(); window.scrollTo({top:0,behavior:'smooth'}); }

function candidateShell(){
  return `
  <div class="cp-shell" style="display:flex;min-height:100vh;">
    <div class="sidebar-desktop" style="width:246px;padding:22px 16px;position:sticky;top:0;height:100vh;">
      <div style="display:flex;align-items:center;gap:10px;padding:6px 10px 26px;">
        <img src="/assets/logo.png" alt="" style="height:80px;width:auto;"/>
        <div style="font-size:10.5px;color:var(--text-muted);letter-spacing:0.06em;text-transform:uppercase;">Candidate Portal</div>
      </div>
      <div class="cp-nav-links" style="display:flex;flex-direction:column;gap:4px;">
        <div class="sidebar-link ${_cpView==='dashboard'?'active':''}" data-cp-nav="dashboard">My Dashboard</div>
        <div class="sidebar-link ${_cpView==='applications'?'active':''}" data-cp-nav="applications">My Applications</div>
        <div class="sidebar-link ${_cpView==='profile'?'active':''}" data-cp-nav="profile">My Profile</div>
        <div class="sidebar-link ${_cpView==='jobs'?'active':''}" data-cp-nav="jobs">Browse Jobs</div>
        <div class="sidebar-link" onclick="clearToken();state.user=null;state.role=null;render();" style="margin-top:8px;color:var(--info);cursor:pointer;">Back to Home</div>
      </div>
    </div>
    <div style="flex:1;min-width:0;">
      <div class="glass" style="margin:16px 18px 0;padding:12px 20px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:16px;z-index:20;">
        <div style="display:flex;align-items:center;gap:10px;">
          <div style="font-size:13px;color:var(--ink-soft);">Candidate Portal</div>
          <div class="chip" style="background:rgba(5,150,105,0.12);color:#059669;">Active</div>
        </div>
        <div style="display:flex;align-items:center;gap:14px;">
          <div style="position:relative;">
            <div style="display:flex;align-items:center;gap:8px;cursor:pointer;" id="cpUserMenuBtn">
              <div style="width:34px;height:34px;border-radius:50%;background:linear-gradient(135deg,#1E40AF,#38BDF8);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;">${initials(state.user.name)}</div>
              <div style="font-size:13px;font-weight:600;">${state.user.name.split(' ')[0]}</div>
            </div>
            <div id="cpUserMenuDropdown" class="glass-strong" style="display:none;position:absolute;right:0;top:44px;width:200px;padding:8px;z-index:300;">
              <div class="sidebar-link" data-cp-nav="profile">My Profile</div>
              <div style="height:1px;background:rgba(226,232,240,0.1);margin:4px 0;"></div>
              <div class="sidebar-link" onclick="clearToken();state.user=null;state.role=null;render();" style="color:var(--coral);">Sign Out</div>
            </div>
          </div>
        </div>
      </div>
      <div style="padding:22px 18px 100px;">
        ${cpViewBody()}
      </div>
    </div>
  </div>
  <div id="cpModal"></div>`;
}

function cpViewBody(){
  switch(_cpView){
    case 'dashboard': return cpDashboardView();
    case 'applications': return cpApplicationsView();
    case 'profile': return cpProfileView();
    case 'jobs': return cpBrowseJobsView();
    case 'confirmation': return cpConfirmationView();
    default: return cpDashboardView();
  }
}

/* ======================== Candidate Dashboard ======================== */
function cpDashboardView(){
  const totalApps = _cpApplications.length;
  const inReview = _cpApplications.filter(a => ['Applied','Resume Screening','Shortlisted'].includes(a.status)).length;
  const interviews = _cpApplications.filter(a => ['Interview Scheduled','Interview Completed'].includes(a.status)).length;
  const selected = _cpApplications.filter(a => a.status === 'Selected').length;
  const recentApps = _cpApplications.slice(0, 5);

  return `
  <div class="glass" style="padding:24px;margin-bottom:18px;">
    <h2 style="margin:0 0 4px;font-size:20px;">Welcome back, ${state.user.name.split(' ')[0]}.</h2>
    <p style="color:var(--ink-soft);font-size:13px;margin:0;">Track your applications and manage your profile.</p>
  </div>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-bottom:18px;">
    <div class="glass" style="padding:20px;text-align:center;">
      <div style="font-size:28px;font-weight:700;color:var(--primary);">${totalApps}</div>
      <div style="font-size:12.5px;color:var(--ink-soft);margin-top:4px;">Total Applications</div>
    </div>
    <div class="glass" style="padding:20px;text-align:center;">
      <div style="font-size:28px;font-weight:700;color:#2563EB;">${interviews}</div>
      <div style="font-size:12.5px;color:var(--ink-soft);margin-top:4px;">Interviews</div>
    </div>
    <div class="glass" style="padding:20px;text-align:center;">
      <div style="font-size:28px;font-weight:700;color:#059669;">${selected}</div>
      <div style="font-size:12.5px;color:var(--ink-soft);margin-top:4px;">Selected</div>
    </div>
  </div>
  <div class="glass" style="padding:18px;">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">
      <h3 style="margin:0;font-size:15px;">Recent Applications</h3>
      <button class="btn btn-ghost" style="font-size:12px;" data-cp-nav="applications">View All →</button>
    </div>
    ${recentApps.length === 0 ? '<div style="text-align:center;padding:30px;color:var(--ink-soft);">No applications yet. <a href="#" onclick="cpNav(\'jobs\');event.preventDefault();" style="color:var(--primary);font-weight:600;">Browse jobs</a> to get started.</div>' :
    `<div class="glass" style="padding:6px;overflow-x:auto;">
      <table class="data-table">
        <thead><tr><th>Job Title</th><th>Status</th><th>Applied On</th><th>Actions</th></tr></thead>
        <tbody>
          ${recentApps.map(a => {
            const statusColor = a.status === 'Selected' ? '#059669' : a.status === 'Rejected' ? '#DC2626' : a.status === 'Withdrawn' ? '#6B7280' : a.status === 'Interview Scheduled' ? '#2563EB' : '#D97706';
            return `<tr>
              <td><strong>${a.jobTitle || 'N/A'}</strong></td>
              <td><span class="chip" style="background:${statusColor}15;color:${statusColor};font-weight:600;">${a.status}</span></td>
              <td style="font-size:12px;color:var(--ink-soft);">${a.submittedDate ? new Date(a.submittedDate).toLocaleDateString() : '—'}</td>
              <td><button class="btn btn-ghost" style="font-size:11px;padding:3px 8px;" data-cp-withdraw="${a.id}">Withdraw</button></td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>
    </div>`}
  </div>`;
}

/* ======================== My Applications ======================== */
function cpApplicationsView(){
  return `
  <div class="glass" style="padding:24px;margin-bottom:18px;">
    <h2 style="margin:0 0 4px;font-size:20px;">My Applications</h2>
    <p style="color:var(--ink-soft);font-size:13px;margin:0;">Track the status of all your job applications.</p>
  </div>
  <div class="glass" style="padding:18px;">
    ${_cpApplications.length === 0 ? '<div style="text-align:center;padding:40px;color:var(--ink-soft);">You have not applied to any jobs yet. <a href="#" onclick="cpNav(\'jobs\');event.preventDefault();" style="color:var(--primary);font-weight:600;">Browse open positions</a>.</div>' :
    `<div class="glass" style="padding:18px;">
      <table class="data-table">
        <thead><tr><th>Application ID</th><th>Job Title</th><th>Status</th><th>Applied On</th><th>Actions</th></tr></thead>
        <tbody>
          ${_cpApplications.map(a => {
            const statusColor = a.status === 'Selected' ? '#059669' : a.status === 'Rejected' ? '#DC2626' : a.status === 'Withdrawn' ? '#6B7280' : a.status === 'Interview Scheduled' ? '#2563EB' : '#D97706';
            const canWithdraw = !['Selected','Rejected','Withdrawn','Joined','Offer Released'].includes(a.status);
            return `<tr>
              <td class="mono" style="font-size:11px;">${a.id ? a.id.slice(0,12)+'...' : '—'}</td>
              <td><strong>${a.jobTitle || 'N/A'}</strong></td>
              <td><span class="chip" style="background:${statusColor}15;color:${statusColor};font-weight:600;">${a.status}</span></td>
              <td style="font-size:12px;color:var(--ink-soft);">${a.submittedDate ? new Date(a.submittedDate).toLocaleDateString() : '—'}</td>
              <td>${canWithdraw ? `<button class="btn btn-ghost" style="font-size:11px;padding:3px 8px;color:var(--coral);" data-cp-withdraw="${a.id}">Withdraw</button>` : '<span style="font-size:11px;color:var(--ink-soft);">—</span>'}</td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>
    </div>`}
  </div>`;
}

/* ======================== Profile ======================== */
function cpProfileView(){
  const p = _cpProfile;
  return `
  <div class="glass" style="padding:24px;margin-bottom:18px;">
    <h2 style="margin:0 0 4px;font-size:20px;">My Profile</h2>
    <p style="color:var(--ink-soft);font-size:13px;margin:0;">View and update your profile information.</p>
  </div>
  <div class="glass" style="padding:24px;">
    <form id="cpProfileForm" onsubmit="handleCpProfileUpdate(event)">
      <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;">
        <div class="lp-form-group"><label class="lp-label">Full Name</label><input class="lp-input" id="cpProfName" value="${p.name || state.user.name || ''}"/></div>
        <div class="lp-form-group"><label class="lp-label">Email Address</label><input class="lp-input" value="${p.email || state.user.email || ''}" disabled style="opacity:0.6;"/></div>
        <div class="lp-form-group"><label class="lp-label">Phone Number</label><input class="lp-input" id="cpProfPhone" value="${p.phone || ''}" placeholder="+91 98765 43210"/></div>
        <div class="lp-form-group"><label class="lp-label">Location</label><input class="lp-input" id="cpProfLocation" value="${p.location || ''}" placeholder="City, Country"/></div>
        <div class="lp-form-group"><label class="lp-label">Experience (years)</label><input class="lp-input" id="cpProfExp" value="${p.experience || ''}" placeholder="e.g. 5"/></div>
        <div class="lp-form-group"><label class="lp-label">Education</label><input class="lp-input" id="cpProfEdu" value="${p.education || ''}" placeholder="e.g. B.Tech Computer Science"/></div>
        <div class="lp-form-group" style="grid-column:1/-1;"><label class="lp-label">Skills (comma-separated)</label><input class="lp-input" id="cpProfSkills" value="${p.skills || ''}" placeholder="e.g. Python, React, AWS"/></div>
      </div>
      <div class="lp-form-actions" style="margin-top:20px;">
        <button type="submit" class="lp-btn lp-btn-primary" id="cpProfSaveBtn">Save Changes</button>
      </div>
      <div id="cpProfResult"></div>
    </form>
  </div>`;
}

async function handleCpProfileUpdate(e){
  e.preventDefault();
  const btn = document.getElementById('cpProfSaveBtn');
  const resultEl = document.getElementById('cpProfResult');
  btn.disabled = true; btn.textContent = 'Saving…';
  try{
    const body = {
      name: document.getElementById('cpProfName').value.trim(),
      phone: document.getElementById('cpProfPhone').value.trim(),
      location: document.getElementById('cpProfLocation').value.trim(),
      experience: document.getElementById('cpProfExp').value.trim(),
      education: document.getElementById('cpProfEdu').value.trim(),
      skills: document.getElementById('cpProfSkills').value.trim(),
    };
    await api('/api/candidates/profile', {method:'PATCH', body});
    state.user.name = body.name;
    _cpProfile = {..._cpProfile, ...body};
    toast('Profile updated successfully.', 'success');
    resultEl.innerHTML = '';
  }catch(err){
    resultEl.innerHTML = `<div style="color:var(--coral);font-size:12.5px;margin-top:8px;">${err.message || 'We couldn\u2019t update the profile. Please try again.'}</div>`;
  }
  btn.disabled = false; btn.textContent = 'Save Changes';
}

/* ======================== Browse Jobs ======================== */
function cpBrowseJobsView(){
  return `
  <div class="glass" style="padding:24px;margin-bottom:18px;">
    <h2 style="margin:0 0 4px;font-size:20px;">Browse Open Positions</h2>
    <p style="color:var(--ink-soft);font-size:13px;margin:0;">Find and apply to jobs that match your skills.</p>
  </div>
  <div id="cpJobGrid"><div class="shimmer" style="height:200px;border-radius:12px;"></div></div>`;
}

async function loadCpJobs(){
  try {
    const jobs = await api('/api/jobs/public');
    const grid = document.getElementById('cpJobGrid');
    if(!grid) return;
    const openJobs = (Array.isArray(jobs) ? jobs : []).filter(j => j.status === 'Open');
    if(!openJobs.length){ grid.innerHTML = '<div class="glass" style="padding:30px;text-align:center;color:var(--ink-soft);">No open positions available right now.</div>'; return; }
    grid.innerHTML = `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px;">
      ${openJobs.map(j => {
        return `<div class="glass" style="padding:18px;">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
            <div style="width:42px;height:42px;border-radius:12px;background:#10B981;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700;color:#fff;">${(j.title||'J')[0]}</div>
            <div><div style="font-weight:700;font-size:15px;">${j.title}</div><div style="font-size:12.5px;color:var(--ink-soft);">${j.dept || 'General'} · ${j.location || 'Remote'}</div></div>
          </div>
          <div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:12px;font-size:12px;color:var(--ink-soft);">
            <span>${j.exp || 'Any'} years</span>
            <span>${j.type || 'Full-time'}</span>
            <span>₹${(j.bonus||0).toLocaleString('en-IN')} bonus</span>
          </div>
          <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px;">
            ${(j.skills||[]).slice(0,5).map(s=>`<span class="lp-skill-tag">${s}</span>`).join('')}
          </div>
          <div style="display:flex;gap:8px;">
            <button class="lp-btn lp-btn-sm lp-btn-outline" onclick="showJobDetail('${j.id}')">View Details</button>
            <button class="lp-btn lp-btn-sm lp-btn-primary" onclick="showApplyModal('${j.id}')">Apply</button>
          </div>
        </div>`;
      }).join('')}
    </div>`;
  } catch(e){
    const grid = document.getElementById('cpJobGrid');
    if(grid) grid.innerHTML = '<div class="glass" style="padding:30px;text-align:center;color:var(--coral);">We couldn\u2019t load the jobs. Please try again.</div>';
  }
}

/* ======================== Confirmation View ======================== */
function cpConfirmationView(){
  const a = _cpLastApplication;
  if(!a) return '<div class="glass" style="padding:40px;text-align:center;">No application data. <a href="#" onclick="cpNav(\'applications\');event.preventDefault();" style="color:var(--primary);">View applications</a></div>';

  return `
  <div class="glass" style="padding:40px;text-align:center;max-width:560px;margin:0 auto;">
    <div style="width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,#059669,#10B981);display:flex;align-items:center;justify-content:center;margin:0 auto 20px;font-size:32px;">✓</div>
    <h2 style="margin:0 0 6px;font-size:22px;">Application submitted</h2>
    <p style="color:var(--ink-soft);font-size:14px;margin:0 0 24px;">Your application has been received. We'll keep you updated on the status.</p>

    <div class="glass" style="padding:20px;text-align:left;margin-bottom:24px;">
      <div style="display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;">
        <div><div style="font-size:11px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:0.5px;">Application ID</div><div class="mono" style="font-size:13px;font-weight:600;margin-top:2px;word-break:break-all;">${a.id || '—'}</div></div>
        <div><div style="font-size:11px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:0.5px;">Job ID</div><div class="mono" style="font-size:13px;font-weight:600;margin-top:2px;word-break:break-all;">${a.jobId || '—'}</div></div>
        <div><div style="font-size:11px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:0.5px;">Job Title</div><div style="font-size:13px;font-weight:600;margin-top:2px;">${a.jobTitle || '—'}</div></div>
        <div><div style="font-size:11px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:0.5px;">Candidate Email</div><div style="font-size:13px;font-weight:600;margin-top:2px;">${state.user?.email || '—'}</div></div>
        <div><div style="font-size:11px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:0.5px;">Status</div><div style="margin-top:2px;"><span class="chip" style="background:rgba(217,119,6,0.12);color:#D97706;font-weight:600;">Applied</span></div></div>
        <div><div style="font-size:11px;color:var(--ink-soft);text-transform:uppercase;letter-spacing:0.5px;">Applied On</div><div style="font-size:13px;font-weight:600;margin-top:2px;">${new Date().toLocaleDateString()}</div></div>
      </div>
    </div>

    <div style="display:flex;gap:10px;justify-content:center;">
      <button class="lp-btn lp-btn-primary" onclick="cpNav('applications')">Track My Application</button>
      <button class="lp-btn lp-btn-outline" onclick="cpNav('jobs')">Browse More Jobs</button>
    </div>
  </div>`;
}

/* ======================== Withdraw Confirmation ======================== */
function showCpWithdrawConfirm(appId){
  const modal = document.getElementById('cpModal');
  modal.innerHTML = `
  <div class="lp-modal-overlay" onclick="if(event.target===this)this.remove()" style="position:fixed;inset:0;z-index:100;">
    <div class="lp-modal lp-modal-sm pop-in" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);">
      <div class="lp-modal-header" style="background:linear-gradient(135deg,#DC2626,#B91C1C);">
        <div>
          <h2 class="lp-modal-title">Withdraw Application</h2>
          <div class="lp-modal-sub">This action cannot be undone</div>
        </div>
        <button class="lp-modal-close" onclick="this.closest('.lp-modal-overlay').remove()">&times;</button>
      </div>
      <div class="lp-modal-body" style="text-align:center;">
        <p style="color:var(--ink-soft);font-size:13.5px;margin-bottom:18px;">Are you sure you want to withdraw this application? You will not be able to re-apply to the same position for 6 months.</p>
        <div style="display:flex;gap:10px;justify-content:center;">
          <button class="lp-btn lp-btn-outline" onclick="this.closest('.lp-modal-overlay').remove()">Cancel</button>
          <button class="lp-btn" style="background:linear-gradient(135deg,#DC2626,#B91C1C);color:#fff;" id="cpConfirmWithdrawBtn" data-app-id="${appId}">Withdraw Application</button>
        </div>
      </div>
    </div>
  </div>`;

  document.getElementById('cpConfirmWithdrawBtn')?.addEventListener('click', async function(){
    const btn = this;
    btn.disabled = true; btn.textContent = 'Withdrawing…';
    try{
      await api(`/api/candidates/withdraw/${btn.dataset.appId}`, {method:'POST'});
      toast('Application withdrawn', 'success');
      document.querySelector('#cpModal .lp-modal-overlay')?.remove();
      _cpApplications = _cpApplications.filter(a => a.id !== btn.dataset.appId);
      render();
    }catch(err){
      toast(err.message || 'Withdraw failed', 'error');
      btn.disabled = false; btn.textContent = 'Withdraw Application';
    }
  });
}

/* ======================== Bind Candidate Shell ======================== */
function bindCandidateShell(){
  document.querySelectorAll('[data-cp-nav]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      cpNav(el.dataset.cpNav);
    });
  });

  const menuBtn = document.getElementById('cpUserMenuBtn');
  const dropdown = document.getElementById('cpUserMenuDropdown');
  if(menuBtn && dropdown){
    menuBtn.addEventListener('click', () => {
      dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
    });
    document.addEventListener('click', (e) => {
      if(!menuBtn.contains(e.target) && !dropdown.contains(e.target)){
        dropdown.style.display = 'none';
      }
    });
  }

  document.querySelectorAll('[data-cp-withdraw]').forEach(btn => {
    btn.addEventListener('click', () => {
      showCpWithdrawConfirm(btn.dataset.cpWithdraw);
    });
  });

  if(_cpView === 'jobs') loadCpJobs();
}

/* ======================== Init Candidate Data ======================== */
let _cpLoadError = false;
async function loadCandidateData(){
  _cpLoadError = false;
  try{
    const apps = await api('/api/candidates/applications');
    _cpApplications = Array.isArray(apps) ? apps : [];
  }catch(e){ _cpApplications = []; _cpLoadError = true; }

  try{
    const profile = await api('/api/candidates/me');
    _cpProfile = profile || {};
  }catch(e){ _cpProfile = {}; _cpLoadError = true; }
}
