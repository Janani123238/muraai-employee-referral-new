/* ------------------------------- Router / Render ------------------------------- */
function nav(view){ state.view=view; state.chat.open=false; render(); window.scrollTo({top:0,behavior:'smooth'}); }
function render(){
  const app = document.getElementById('app');
  if(!state.user){
    destroyHero3D();
    destroyShowcaseCard();
    app.innerHTML = renderLandingPage();
    initLandingScroll();
    initLandingAnchors();
    setTimeout(function(){ initHero3D(); initShowcaseCard(); }, 50);
    loadPublicJobs().then(()=>{ const grid=document.getElementById('lpJobGrid'); if(grid) grid.innerHTML=renderLandingJobCards(); });
    loadLandingStats();
    if(state.loginMode){
      setTimeout(()=>{
        if(state.loginMode==='forgot') showForgotModal();
        else if(state.loginMode==='reset') showResetModal();
        else showLoginModal();
      }, 100);
    }
    const lpParams = new URLSearchParams(window.location.search);
    const refJobId = lpParams.get('job');
    if(refJobId){
      state.referPendingJob = refJobId;
      state.referPendingRef = lpParams.get('ref') || '';
      setTimeout(()=>{ showReferralModal(refJobId); }, 400);
      history.replaceState({}, '', window.location.pathname);
    }
    return;
  }
  if(!state.role) state.role = state.user.role || 'employee';

  if(state.role === 'candidate'){
    app.innerHTML = candidateShell();
    bindCandidateShell();
    return;
  }

  app.innerHTML = shell();
  bindShell();
}

