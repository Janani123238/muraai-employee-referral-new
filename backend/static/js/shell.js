function isAdminExperience(role){
  return ['admin','system_admin','ceo','cto','vp','chro'].includes(role);
}
function navItemsFor(role){
  if(role==='employee') return [
    ['dashboard','dashboard','Dashboard'],['refer','refer','Refer a Candidate'],
    ['jobs','jobs','Open Positions'],['tracking','tracking','My Referrals'],['policy','policy','Referral Policy'],
    ['home','landing','Public Site'],
  ];
  if(role==='manager') return [
    ['dashboard','dashboard','Dashboard'],['refer','refer','Refer a Candidate'],
    ['jobs','jobs','Open Positions'],['tracking','tracking','My Referrals'],['teamInsights','teamInsights','Team Referral Insights'],
    ['leaderboard','leaderboard','Leaderboard'],['rewards','rewards','Rewards'],['policy','policy','Referral Policy'],
    ['home','landing','Public Site'],
  ];
  if(isAdminExperience(role)) return [
    ['dashboard','dashboard','Dashboard'],    ['manageJobs','manageJobs','Manage Jobs'],['allReferrals','allReferrals','All Referrals'],
    ['resumeAnalysis','resumeAnalysis','Resume Analysis'],['bulkImport','bulkImport','Bulk Import'],
    ['employees','employees','Employees'],
    ['interviews','interviews','Interviews'],['reports','reports','Reports & Analytics'],
    ['adminSettings','adminSettings','Admin Settings'],['aiSettings','aiSettings','AI Settings'],
    ['userManagement','userManagement','User Management'],['emailTemplates','emailTemplates','Email Templates'],['emailCenter','emailCenter','Email Center'],['auditLogs','auditLogs','Audit Logs'],['policy','policy','Referral Policy'],
    ['home','landing','Public Site'],
  ];
  return [
    ['dashboard','dashboard','Dashboard'],    ['manageJobs','manageJobs','Manage Jobs'],['allReferrals','allReferrals','All Referrals'],
    ['resumeAnalysis','resumeAnalysis','Resume Analysis'],['bulkImport','bulkImport','Bulk Import'],
    ['employees','employees','Employees'],
    ['interviews','interviews','Interviews'],['reports','reports','Reports & Analytics'],['emailTemplates','emailTemplates','Email Templates'],
    ['policy','policy','Referral Policy'],
    ['home','landing','Public Site'],
  ];
}
function shell(){
  const items = navItemsFor(state.role);
  const emp = currentUserEmployee();
  return `
  <div style="display:flex;min-height:100vh;">
    <aside class="app-sidebar">
      <div class="app-sidebar-brand">
        <img src="/assets/logo.png" alt="" style="height:80px;width:auto;"/>
      </div>
      <nav class="sidebar-nav">
        ${items.map(([ic,id,label])=>`
          <div class="sidebar-link ${state.view===id?'active':''}" data-nav="${id}" title="${label}">
            <span class="sidebar-link-icon">${icon(ic, 17)}</span>
            <span class="sidebar-link-label">${label}</span>
          </div>`).join('')}
      </nav>
      <div class="sidebar-footer">
        <div class="sidebar-assist">
          <div class="sidebar-assist-title">${icon('sparkles',13)} AI Assistant</div>
          <div class="sidebar-assist-sub">Ask about jobs, bonuses, or referral status</div>
          <button class="btn btn-primary" id="openChatSidebar">${icon('messageCircle',14)} Open Chat</button>
        </div>
      </div>
    </aside>
    <div style="flex:1;min-width:0;">
      <div class="app-topbar">
        <div style="display:flex;align-items:center;gap:10px;">
          <div style="font-size:13px;color:var(--text-secondary);font-weight:600;">${state.role==='employee'||state.role==='manager'?'Employee Portal':isAdminExperience(state.role)?'Admin Portal':'HR Portal'}</div>
          <div class="chip" style="background:rgba(5,150,105,0.12);color:#059669;"><span class="live-dot"></span>Live</div>
        </div>
        <div style="display:flex;align-items:center;gap:14px;">
          <div class="chip notif-chip" id="notifBtn">${icon('bell',15)} Notifications ${state.unreadCount>0?`<span class="notif-count">${state.unreadCount}</span>`:''}</div>
          <div style="position:relative;">
            <div style="display:flex;align-items:center;gap:8px;cursor:pointer;" id="userMenuBtn">
              <div class="avatar-sm" style="background:${emp?emp.color:'#60A5FA'};">${initials(state.user.name)}</div>
              <div style="font-size:13px;font-weight:600;">${state.user.name.split(' ')[0]}</div>
            </div>
            <div id="userMenuDropdown" class="glass-strong" style="display:none;position:absolute;right:0;top:44px;width:200px;padding:8px;z-index:30;">
              <div class="sidebar-link" data-nav="profile">${icon('profile',16)}<span class="sidebar-link-label">Profile</span></div>
              <div class="sidebar-link" data-nav="editProfile">${icon('editProfile',16)}<span class="sidebar-link-label">Edit Profile</span></div>
              <div style="height:1px;background:var(--border);margin:4px 0;"></div>
              <div class="sidebar-link" data-logout="1">${icon('logout',16)}<span class="sidebar-link-label">Sign Out</span></div>
            </div>
          </div>
        </div>
      </div>
      <div id="notifDropdown" class="glass-strong" style="display:none;position:fixed;top:70px;right:26px;width:340px;padding:10px;z-index:40;max-height:400px;overflow-y:auto;">
        <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 8px 10px;border-bottom:1px solid var(--border);">
          <div style="font-weight:700;font-size:13.5px;">Notifications</div>
          ${state.unreadCount>0?`<button class="btn btn-ghost" id="markAllReadBtn" style="font-size:11.5px;padding:4px 10px;">Mark All as Read</button>`:''}
        </div>
        ${state.notifications.length===0?`<div style="padding:20px;font-size:12.5px;color:var(--ink-soft);text-align:center;">No notifications yet.</div>`:
        state.notifications.slice(0,12).map(n=>`
          <div style="display:flex;gap:10px;padding:10px;border-radius:12px;${n.isRead?'':'background:rgba(37,99,235,0.08);'}cursor:pointer;" data-notif-id="${n.id}" data-notif-link="${n.link||''}">
            <div class="notif-icon notif-${n.type||'info'}">${icon(n.type==='success'?'success':n.type==='error'?'error':n.type==='warning'?'warning':'bell',15)}</div>
            <div style="flex:1;"><div style="font-size:12.5px;font-weight:${n.isRead?'400':'700'};">${n.title}</div><div style="font-size:11.5px;color:var(--ink-soft);margin-top:2px;">${n.message}</div><div style="font-size:10.5px;color:var(--ink-soft);margin-top:3px;">${fmtRelative(n.created_at)}</div></div>
          </div>
        `).join('')}
      </div>
      <div style="padding:22px 18px 100px;">
        ${viewBody()}
      </div>
    </div>
  </div>
  ${chatWidget()}
  `;
}
function notifItem(icon,title,sub){
  return `<div style="display:flex;gap:10px;padding:10px;border-radius:12px;" onmouseover="this.style.background='rgba(37,99,235,0.08)'" onmouseout="this.style.background='transparent'">
    <div class="notif-icon" style="background:var(--bg-card-hover);color:var(--navy);">${icon}</div>
    <div><div style="font-size:12.5px;font-weight:700;">${title}</div><div style="font-size:11.5px;color:var(--ink-soft);">${sub}</div></div>
  </div>`;
}
function recentActivityHTML(){
  const relevant = isHrRole(state.role) ? state.referrals : state.referrals.filter(r=>r.referredBy===state.user.employeeId);
  const recent = [...relevant].sort((a,b)=> new Date(b.submittedDate)-new Date(a.submittedDate)).slice(0,6);
  if(recent.length===0){
    return `<div style="padding:16px;font-size:12.5px;color:var(--ink-soft);text-align:center;">No activity yet.</div>`;
  }
  const icons = {Submitted:'refer','HR Review':'eye','Technical Round':'calendar','Manager Round':'calendar','HR Round':'calendar',Offer:'award',Joined:'joined',Rejected:'rejected'};
  return recent.map(r=>{
    const job = jobById(r.jobId);
    return notifItem(icon(icons[r.status]||'pin', 16), `${r.candidateName} — ${r.status}`, `${job?job.title:'—'} · ${fmtRelative(r.submittedDate)}`);
  }).join('');
}
function viewBody(){
  if(state.role==='employee' || state.role==='manager'){
    switch(state.view){
      case 'dashboard': return employeeDashboard();
      case 'refer': return referCandidateView();
      case 'jobs': return openPositionsView();
      case 'tracking': return myReferralsView();
      case 'teamInsights': return teamInsightsView();
      case 'leaderboard': return leaderboardView();
      case 'rewards': return rewardsView();
      case 'policy': return policyView();
      case 'profile': return profileView();
      case 'editProfile': return editProfileView();
      case 'landing': return renderLandingPage();
      default: return employeeDashboard();
    }
  } else {
    if(isAdminExperience(state.role)){
      switch(state.view){
        case 'dashboard': return hrDashboard();
        case 'manageJobs': return manageJobsView();
        case 'allReferrals': return allReferralsView();
        case 'resumeAnalysis': return resumeAnalysisView();
        case 'bulkImport': return bulkImportView();
        case 'employees': return employeesView();
        case 'interviews': return interviewsView();
        case 'reports': return reportsView();
        case 'aiSettings': return aiSettingsView();
        case 'adminSettings': return adminSettingsView();
        case 'userManagement': return userManagementView();
        case 'emailTemplates': return emailTemplatesView();
        case 'emailCenter': return emailCenterView();
        case 'auditLogs': return auditLogsView();
        case 'policy': return policyView();
        case 'profile': return profileView();
        case 'editProfile': return editProfileView();
        case 'landing': return renderLandingPage();
        default: return hrDashboard();
      }
    }
    switch(state.view){
      case 'dashboard': return hrDashboard();
      case 'manageJobs': return manageJobsView();
      case 'allReferrals': return allReferralsView();
      case 'resumeAnalysis': return resumeAnalysisView();
      case 'bulkImport': return bulkImportView();
      case 'employees': return employeesView();
      case 'interviews': return interviewsView();
      case 'reports': return reportsView();
      case 'emailTemplates': return emailTemplatesView();
      case 'emailCenter': return emailCenterView();
      case 'policy': return policyView();
      case 'profile': return profileView();
      case 'editProfile': return editProfileView();
      case 'landing': return renderLandingPage();
      default: return hrDashboard();
    }
  }
}
function teamInsightsView(){
  const team = state.referrals || [];
  const shortlisted = team.filter(r=>['Shortlisted','Interview Scheduled','Interview Completed','Selected','Offer','Offer Released','Joined'].includes(r.status)).length;
  const interviews = team.filter(r=>['Interview Scheduled','Interview Completed','Selected','Offer','Offer Released','Joined'].includes(r.status)).length;
  const hires = team.filter(r=>r.status==='Joined').length;
  const total = team.length;
  const rate = total ? Math.round(hires / total * 100) : 0;
  const byReferrer = {};
  team.forEach(r=>{ const name=(employeeById(r.referredBy)||{}).name || 'Team member'; byReferrer[name]=(byReferrer[name]||0)+1; });
  return `<div class="fade-up">
    <div style="margin-bottom:18px;"><h1 class="display" style="font-size:24px;margin:0 0 4px;">Team Referral Insights</h1><p style="color:var(--ink-soft);font-size:13px;margin:0;">Live referral performance for your department.</p></div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin-bottom:18px;">
      ${statCard('Team Referrals',total,'team',GRADS[0])}${statCard('Shortlisted',shortlisted,'shortlist',GRADS[1])}${statCard('Interviews',interviews,'interview',GRADS[2])}${statCard('Hiring Rate',rate+'%','conversion',GRADS[5])}
    </div>
    <div class="glass" style="padding:18px;"><h3 style="font-size:14px;margin:0 0 12px;">Referrals by employee</h3>
      ${Object.entries(byReferrer).sort((a,b)=>b[1]-a[1]).map(([name,count])=>`<div style="display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid rgba(226,232,240,.08);font-size:13px;"><span>${name}</span><strong class="mono">${count}</strong></div>`).join('') || '<div style="color:var(--ink-soft);font-size:13px;">No team referrals yet.</div>'}
    </div>
  </div>`;
}

function bindShell(){
  document.querySelectorAll('[data-nav]').forEach(el=> el.addEventListener('click', ()=>{
    nav(el.dataset.nav);
  }) );
  if(state.view==='landing'){
    initLandingScroll();
    initLandingAnchors();
    setTimeout(function(){ initHero3D(); initShowcaseCard(); }, 50);
    loadPublicJobs().then(()=>{ const grid=document.getElementById('lpJobGrid'); if(grid) grid.innerHTML=renderLandingJobCards(); });
    loadLandingStats();
  }
  const userMenuBtn = document.getElementById('userMenuBtn');
  const dropdown = document.getElementById('userMenuDropdown');
  if(userMenuBtn) userMenuBtn.addEventListener('click', (e)=>{ e.stopPropagation(); dropdown.style.display = dropdown.style.display==='none'?'block':'none'; });
  document.addEventListener('click', ()=>{ if(dropdown) dropdown.style.display='none'; const nd=document.getElementById('notifDropdown'); if(nd) nd.style.display='none'; }, {once:true});
  const logout = document.querySelector('[data-logout]');
  if(logout) logout.addEventListener('click', ()=>{
    clearToken(); if(pollTimer){clearInterval(pollTimer); pollTimer=null;}
    state.user=null; state.role=null; state.jobs=[]; state.referrals=[]; state.employees=[];
    // End the Microsoft session too (redirects to Entra logout, then back home).
    window.location.href = '/api/auth/microsoft/logout';
  });
  const notifBtn = document.getElementById('notifBtn');
  if(notifBtn) notifBtn.addEventListener('click', (e)=>{ e.stopPropagation(); const nd=document.getElementById('notifDropdown'); nd.style.display = nd.style.display==='none'?'block':'none'; });
  document.querySelectorAll('[data-notif-id]').forEach(el=>{
    el.addEventListener('click', async ()=>{
      const id = el.dataset.notifId;
      const link = el.dataset.notifLink;
      if(!el.style.background) {
        try{ await api('/api/notifications/mark-read', {method:'POST', body:{ids:[id]}}); }catch(e){}
        state.notifications = state.notifications.map(n=>n.id===id?{...n,isRead:true}:n);
        state.unreadCount = state.notifications.filter(n=>!n.isRead).length;
      }
      if(link){ nav(link.replace('/','')); }
      render();
    });
  });
  const markAllBtn = document.getElementById('markAllReadBtn');
  if(markAllBtn) markAllBtn.addEventListener('click', async ()=>{
    const unreadIds = state.notifications.filter(n=>!n.isRead).map(n=>n.id);
    if(unreadIds.length){
      try{ await api('/api/notifications/mark-read', {method:'POST', body:{ids:unreadIds}}); }catch(e){}
      state.notifications = state.notifications.map(n=>({...n,isRead:true}));
      state.unreadCount = 0;
      render();
    }
  });
  const openChatSidebar = document.getElementById('openChatSidebar');
  if(openChatSidebar) openChatSidebar.addEventListener('click', ()=>{ state.chat.open=true; render(); });
  attachTilt(document.getElementById('app'));
  bindViewSpecific();
  bindChatWidget();
}

function statCard(label, value, ic, grad){
  return `<div class="glass fade-up" style="padding:16px 18px;display:flex;align-items:center;gap:13px;">
    <div style="flex-shrink:0;width:38px;height:38px;border-radius:9px;background:var(--bg-card-hover);color:var(--navy);display:flex;align-items:center;justify-content:center;">${icon(ic)}</div>
    <div style="min-width:0;">
      <div class="mono" style="font-size:20px;font-weight:700;color:var(--text-primary);line-height:1.15;">${value}</div>
      <div style="font-size:11.5px;color:var(--text-secondary);margin-top:3px;line-height:1.3;">${label}</div>
    </div>
  </div>`;
}
const GRADS = ['linear-gradient(135deg,#2563EB,#60A5FA)','linear-gradient(135deg,#0891B2,#1D4ED8)','linear-gradient(135deg,#059669,#059669)',
  'linear-gradient(135deg,#DC2626,#E11D48)','linear-gradient(135deg,#D97706,#D97706)','linear-gradient(135deg,#60A5FA,#0891B2)',
  'linear-gradient(135deg,#1D4ED8,#2563EB)','linear-gradient(135deg,#0891B2,#059669)'];
