/* ================================ Landing Page ================================ */
let _landingJobs = [];
let _landingFilter = { keyword: '', location: '', dept: '', exp: '', type: '' };

async function loadPublicJobs(){
  try {
    const res = await fetch('/api/jobs/public');
    if(res.ok) _landingJobs = await res.json();
  } catch(e){ _landingJobs = []; }
  const grid = document.getElementById('lpJobGrid');
  if(grid) grid.innerHTML = renderLandingJobCards();
}

async function loadLandingStats(){
  try {
    const res = await fetch('/api/reports/landing-stats');
    if(!res.ok) return;
    const s = await res.json();
    document.querySelectorAll('[data-lp-stat]').forEach(el=>{
      const val = s[el.dataset.lpStat];
      if(val === undefined) return;
      const prefix = el.dataset.prefix || '';
      el.setAttribute('data-count', val);
      el.textContent = prefix + Number(val).toLocaleString('en-IN');
    });
  } catch(e){ /* keep zeros on failure */ }
}

/* ================================ Main Render ================================ */
function renderLandingPage(){
  return `
  <div class="landing-page">
    ${lpHeader()}
    ${lpHero()}
    ${lpSearchSection()}
    ${lpFeaturedJobs()}
    ${lpHowItWorks()}
    ${lpWhyRefer()}
    ${lpFaq()}
    ${lpNewsletter()}
    ${lpFooter()}
  </div>
  <div id="landingModals"></div>`;
}

/* ================================ Navigation ================================ */
function lpHeader(){
  const loggedIn = !!getToken();
  return `
  <header class="lp-header" id="lpHeader">
    <div class="lp-header-inner">
      <a href="#" class="lp-logo" onclick="event.preventDefault();window.scrollTo({top:0,behavior:'smooth'})">
        <img src="/assets/logo.png" alt="" style="height:76px;width:auto;margin-top:8px;"/>
      </a>
      <nav class="lp-nav" id="lpNav">
        <a href="#hero" class="lp-nav-link active" data-section="hero">Home</a>
        <a href="#jobs" class="lp-nav-link" data-section="jobs">Jobs</a>
        <a href="#howItWorks" class="lp-nav-link" data-section="howItWorks">How It Works</a>
        <a href="#whyRefer" class="lp-nav-link" data-section="whyRefer">Why Refer</a>
        <a href="#faq" class="lp-nav-link" data-section="faq">FAQ</a>
      </nav>
      <div class="lp-header-actions">
        ${loggedIn
          ? `<button class="lp-btn lp-btn-primary lp-btn-nav" id="lpDashBtn" onclick="lpRouteToPortal()">Dashboard</button>`
          : `<button class="lp-btn lp-btn-primary lp-btn-nav" onclick="showLoginModal()">Sign In</button>`
        }
        <button class="lp-hamburger" id="lpHamburger" onclick="toggleLpMenu()">
          <span></span><span></span><span></span>
        </button>
      </div>
    </div>
    <div class="lp-header-glow"></div>
  </header>`;
}

function toggleLpMenu(){
  const nav = document.getElementById('lpNav');
  if(nav) nav.classList.toggle('open');
  const ham = document.getElementById('lpHamburger');
  if(ham) ham.classList.toggle('active');
}

/* Role-aware routing for authenticated visitors: a valid session on the public
   landing page always lands in the portal that matches the user's role
   (Admin → Admin Dashboard, HR → HR Dashboard, Employee → Employee Portal). */
async function lpRouteToPortal(){
  if(!getToken()){ showLoginModal(); return; }
  try{
    if(!state.user){
      const user = await api('/api/auth/me');
      state.user = user; state.role = user.role;
    }
    window.location.reload(); // init() routes to the role-correct dashboard
  }catch(e){
    clearToken();
    render();
  }
}
function lpReferAction(){
  if(getToken()){ lpRouteToPortal(); return; }
  showLoginModal();
}

/* ================================ Hero ================================ */
function lpHero(){
  return `
  <section class="lp-hero enterprise-hero" id="hero">
    <video class="enterprise-hero-video" autoplay muted loop playsinline><source src="https://videos.pexels.com/video-files/3188992/3188992-hd_1920_1080_25fps.mp4" type="video/mp4"></video>
    <div class="enterprise-hero-video-overlay"></div>
    <div class="lp-hero-3d-wrap"><canvas id="hero3dCanvas"></canvas></div>
    <div class="lp-hero-bg"></div>
    <div class="lp-hero-geometric">
      <div class="orb orb-1"></div>
      <div class="orb orb-2"></div>
      <div class="orb orb-3"></div>
      <div class="grid-lines"></div>
    </div>
    <div class="lp-hero-content">
      <div class="lp-hero-badge"><span class="badge-dot"></span> Enterprise employee referral platform</div>
      <h1 class="lp-hero-title">Refer <span class="accent-word">Great Talent</span>.<br>Build Strong Teams.</h1>
      <p class="lp-hero-sub">Employee referral platform with resume intelligence, smart referrals, and real-time hiring analytics.</p>
      <div class="lp-hero-actions">
        <a href="#jobs" class="lp-btn lp-btn-primary lp-btn-lg">Explore Jobs</a>
        <button class="lp-btn lp-btn-hero-outline lp-btn-lg" onclick="lpReferAction()">Refer a Candidate</button>
      </div>
      <div class="lp-hero-stats">
        <div class="lp-stat">
          <span class="lp-stat-num" data-count="0" data-lp-stat="openJobs">0</span>
          <div class="lp-stat-label">Open Jobs</div>
        </div>
        <div class="lp-stat">
          <span class="lp-stat-num" data-count="0" data-lp-stat="totalReferrals">0</span>
          <div class="lp-stat-label">Total Referrals</div>
        </div>
        <div class="lp-stat">
          <span class="lp-stat-num" data-count="0" data-lp-stat="successfulHires">0</span>
          <div class="lp-stat-label">Successful Hires</div>
        </div>
        <div class="lp-stat">
          <span class="lp-stat-num" data-count="0" data-prefix="₹" data-lp-stat="referralRewardsPaid">0</span>
          <div class="lp-stat-label">Referral Rewards Paid</div>
        </div>
      </div>
    </div>
    <div class="enterprise-hero-visual" aria-label="Live recruitment intelligence dashboard">
      <div class="enterprise-visual-glow"></div>
      <div class="enterprise-dashboard">
        <div class="enterprise-dashboard-top"><span class="enterprise-product-mark"><i></i> Talent intelligence</span><span class="enterprise-live"><b></b> Live</span></div>
        <div class="enterprise-dashboard-main">
          <div class="enterprise-candidate-card"><div class="enterprise-avatar">AM</div><div><strong>Ananya Menon</strong><small>Senior Data Engineer</small></div><span class="enterprise-score">94%</span></div>
          <div class="enterprise-match-panel"><div class="enterprise-match-head"><span>JD Match Score</span><strong>94</strong></div><div class="enterprise-match-ring"><span>Strong fit</span></div><div class="enterprise-skill-list"><i>Python</i><i>Azure</i><i>SQL</i><i>+4</i></div></div>
          <div class="enterprise-chart"><div class="enterprise-chart-head"><span>Hiring analytics</span><small>Last 30 days</small></div><div class="enterprise-bars"><i style="height:35%"></i><i style="height:58%"></i><i style="height:46%"></i><i style="height:76%"></i><i style="height:62%"></i><i style="height:92%"></i><i style="height:72%"></i></div></div>
        </div>
        <div class="enterprise-workflow"><span class="active">Referral</span><i></i><span class="active">AI Screening</span><i></i><span>Interview</span><i></i><span>Hire</span></div>
      </div>
      <div class="enterprise-float enterprise-float-one"><span class="enterprise-mini-avatar teal">RK</span><div><strong>Resume screened</strong><small>Skills mapped to role</small></div><b>✓</b></div>
      <div class="enterprise-float enterprise-float-two"><span class="enterprise-mini-avatar blue">SV</span><div><strong>Interview ready</strong><small>92% role alignment</small></div></div>
    </div>
  </section>`;
}

/* ================================ 3D Showcase Card ================================ */
function lpShowcaseCard(){
  return `
  <section class="lp-showcase-section">
    <div class="lp-container">
      <div class="sc-scene" id="scScene">
        <div class="sc-glow"></div>
        <div class="sc-card" id="scCard">
          <div class="sc-card-inner">

            <div class="sc-content">
              <div class="sc-badge"><span class="sc-badge-dot"></span>AI-Powered Referrals</div>
              <h2 class="sc-title">Refer Smarter.<br>Hire <span class="sc-gradient-word">Faster</span>.</h2>
              <p class="sc-desc">Our AI engine analyzes resumes, scores match quality, and surfaces the best candidates — turning your network into your strongest hiring pipeline.</p>
              <div class="sc-stats-row">
                <div class="sc-stat"><span class="sc-stat-num">2</span><span class="sc-stat-unit">min</span><span class="sc-stat-label">Avg Referral</span></div>
                <div class="sc-stat-divider"></div>
                <div class="sc-stat"><span class="sc-stat-num">40</span><span class="sc-stat-unit">%</span><span class="sc-stat-label">Faster Hiring</span></div>
                <div class="sc-stat-divider"></div>
                <div class="sc-stat"><span class="sc-stat-num">94</span><span class="sc-stat-unit">%</span><span class="sc-stat-label">Match Accuracy</span></div>
              </div>
              <div class="sc-actions">
                <button class="lp-btn lp-btn-primary lp-btn-lg sc-btn-glow" onclick="lpReferAction()">Start Referring</button>
                <a href="#howItWorks" class="lp-btn lp-btn-outline lp-btn-lg sc-btn-light">See How It Works</a>
              </div>
            </div>

            <div class="sc-visual">
              <div class="sc-video-halo"></div>
              <div class="sc-dashboard sc-video-frame">
                <div class="sc-dash-header">
                  <div class="sc-dash-dot sc-dash-dot-r"></div>
                  <div class="sc-dash-dot sc-dash-dot-y"></div>
                  <div class="sc-dash-dot sc-dash-dot-g"></div>
                  <span class="sc-dash-title">MuraAI Intelligence</span>
                  <span class="sc-video-live"><i></i> LIVE</span>
                </div>
                <div class="sc-video-grid"></div>
                <div class="sc-video-orbit sc-video-orbit-a"></div>
                <div class="sc-video-orbit sc-video-orbit-b"></div>
                <div class="sc-video-core"><span>AI</span></div>
                <div class="sc-video-scan"></div>
                <div class="sc-dash-body">
                  <div class="sc-video-caption"><span>Candidate intelligence stream</span><strong>Analyzing in real time</strong></div>
                  <div class="sc-dash-row">
                    <div class="sc-dash-stat">
                      <div class="sc-dash-stat-icon" style="background:linear-gradient(135deg,#1E40AF,#3B82F6);"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg></div>
                      <div><div class="sc-dash-stat-val">24</div><div class="sc-dash-stat-name">Referred</div></div>
                    </div>
                    <div class="sc-dash-stat">
                      <div class="sc-dash-stat-icon" style="background:linear-gradient(135deg,#059669,#10B981);"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg></div>
                      <div><div class="sc-dash-stat-val">8</div><div class="sc-dash-stat-name">Hired</div></div>
                    </div>
                    <div class="sc-dash-stat">
                      <div class="sc-dash-stat-icon" style="background:linear-gradient(135deg,#D97706,#F59E0B);"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg></div>
                      <div><div class="sc-dash-stat-val">₹3.2L</div><div class="sc-dash-stat-name">Earned</div></div>
                    </div>
                  </div>
                  <div class="sc-dash-bar-group">
                    <div class="sc-dash-bar-label"><span>Engineering</span><span>78%</span></div>
                    <div class="sc-dash-bar"><div class="sc-dash-bar-fill" style="width:78%;background:linear-gradient(90deg,#1E40AF,#3B82F6);"></div></div>
                    <div class="sc-dash-bar-label"><span>Product</span><span>62%</span></div>
                    <div class="sc-dash-bar"><div class="sc-dash-bar-fill" style="width:62%;background:linear-gradient(90deg,#059669,#10B981);"></div></div>
                    <div class="sc-dash-bar-label"><span>Design</span><span>45%</span></div>
                    <div class="sc-dash-bar"><div class="sc-dash-bar-fill" style="width:45%;background:linear-gradient(90deg,#D97706,#FBBF24);"></div></div>
                  </div>
                </div>
              </div>

              <div class="sc-float-card sc-float-1">
                <div class="sc-float-avatar" style="background:linear-gradient(135deg,#1E40AF,#60A5FA);">AK</div>
                <div class="sc-float-info"><div class="sc-float-name">Anil Kumar</div><div class="sc-float-meta">Senior Engineer • <span class="sc-float-match">96% Match</span></div></div>
              </div>
              <div class="sc-float-card sc-float-2">
                <div class="sc-float-avatar" style="background:linear-gradient(135deg,#7C3AED,#A78BFA);">PS</div>
                <div class="sc-float-info"><div class="sc-float-name">Priya Sharma</div><div class="sc-float-meta">Product Manager • <span class="sc-float-match">91% Match</span></div></div>
              </div>
              <div class="sc-float-card sc-float-3">
                <div class="sc-float-icon-wrap"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg></div>
                <div><div class="sc-float-notif-title">Referral hired</div><div class="sc-float-notif-meta">Rahul M. joined Engineering • ₹50K bonus</div></div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </div>
  </section>`;
}

function initShowcaseCard(){
  const scene = document.getElementById('scScene');
  const card = document.getElementById('scCard');
  if(!scene || !card) return;

  let raf = null;
  let targetX = 0, targetY = 0;
  let currentX = 0, currentY = 0;

  scene.addEventListener('mousemove', e=>{
    const rect = scene.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    targetX = y * -14;
    targetY = x * 14;
    const glow = scene.querySelector('.sc-glow');
    if(glow){
      glow.style.opacity = '1';
      glow.style.background = `radial-gradient(600px circle at ${e.clientX - rect.left}px ${e.clientY - rect.top}px, rgba(30,64,175,0.15), transparent 60%)`;
    }
    const card = document.getElementById('scCard');
    if(card){
      card.style.setProperty('--gx', ((e.clientX - rect.left) / rect.width * 100) + '%');
      card.style.setProperty('--gy', ((e.clientY - rect.top) / rect.height * 100) + '%');
    }
  });

  scene.addEventListener('mouseleave', ()=>{
    targetX = 0; targetY = 0;
    const glow = scene.querySelector('.sc-glow');
    if(glow) glow.style.opacity = '0';
  });

  function animate(){
    currentX += (targetX - currentX) * 0.08;
    currentY += (targetY - currentY) * 0.08;
    card.style.transform = `perspective(1000px) rotateX(${currentX}deg) rotateY(${currentY}deg) scale3d(1.01,1.01,1.01)`;
    raf = requestAnimationFrame(animate);
  }
  animate();

  scene._scCleanup = ()=>{ cancelAnimationFrame(raf); };
}

function destroyShowcaseCard(){
  const scene = document.getElementById('scScene');
  if(scene && scene._scCleanup) scene._scCleanup();
}

/* ================================ Search Bar ================================ */
function lpSearchSection(){
  return `
  <section class="lp-search-section" id="searchBar">
    <div class="lp-container">
      <div class="lp-search-bar">
        <div class="lp-search-field lp-search-field-grow">
          <svg class="lp-search-icon-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          <input type="text" placeholder="Job title, keyword, or skill" id="lpKeyword" oninput="filterLandingJobs()"/>
        </div>
        <div class="lp-search-divider"></div>
        <div class="lp-search-field">
          <svg class="lp-search-icon-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
          <select id="lpLocationFilter" onchange="filterLandingJobs()" class="lp-search-select">
            <option value="">All Locations</option>
            <option>Bangalore</option><option>Mumbai</option><option>Delhi NCR</option>
            <option>Hyderabad</option><option>Pune</option><option>Chennai</option><option>Remote</option>
          </select>
        </div>
        <div class="lp-search-divider"></div>
        <div class="lp-search-field">
          <select id="lpDept" onchange="filterLandingJobs()" class="lp-search-select">
            <option value="">All Departments</option>
            <option>Engineering</option><option>Product</option><option>Design</option>
            <option>Data Science</option><option>Marketing</option><option>Sales</option>
            <option>Human Resources</option><option>Finance</option><option>Operations</option>
          </select>
        </div>
        <button class="lp-btn lp-btn-primary lp-search-btn" onclick="filterLandingJobs()">Search Jobs</button>
      </div>
    </div>
  </section>`;
}

/* ================================ Featured Jobs ================================ */
function lpFeaturedJobs(){
  return `
  <section class="lp-section" id="jobs">
    <div class="lp-container">
      <div class="lp-section-header">
        <span class="lp-section-badge">Open Positions</span>
        <h2 class="lp-section-title">Featured Job Openings</h2>
        <p class="lp-section-sub">Explore opportunities across teams and find the right role for you or your referral.</p>
      </div>
      <div class="lp-filters-bar" id="lpFiltersBar">
        <button class="lp-filter-chip lp-filter-chip-active" data-filter="all" onclick="setLandingFilter('all')">All</button>
        <button class="lp-filter-chip" data-filter="Engineering" onclick="setLandingFilter('Engineering')">Engineering</button>
        <button class="lp-filter-chip" data-filter="Product" onclick="setLandingFilter('Product')">Product</button>
        <button class="lp-filter-chip" data-filter="Design" onclick="setLandingFilter('Design')">Design</button>
        <button class="lp-filter-chip" data-filter="Data Science" onclick="setLandingFilter('Data Science')">Data Science</button>
        <button class="lp-filter-chip" data-filter="Marketing" onclick="setLandingFilter('Marketing')">Marketing</button>
        <button class="lp-filter-chip" data-filter="Sales" onclick="setLandingFilter('Sales')">Sales</button>
      </div>
      <div class="lp-job-grid" id="lpJobGrid">${renderSkeletons()}</div>
    </div>
  </section>`;
}

function renderSkeletons(){
  return Array(6).fill('').map(()=>`
    <div class="lp-skeleton-card">
      <div class="lp-skeleton lp-sk-header"></div>
      <div class="lp-skeleton lp-sk-line" style="width:60%"></div>
      <div class="lp-skeleton lp-sk-line" style="width:80%"></div>
      <div class="lp-skeleton lp-sk-line" style="width:40%"></div>
      <div class="lp-skeleton lp-sk-footer"></div>
    </div>
  `).join('');
}

function renderLandingJobCards(){
  let jobs = _landingJobs.filter(j => j.status === 'Open');
  if(_landingFilter.keyword) jobs = jobs.filter(j => (j.title||'').toLowerCase().includes(_landingFilter.keyword) || (j.skills||[]).some(s=>s.toLowerCase().includes(_landingFilter.keyword)));
  if(_landingFilter.location) jobs = jobs.filter(j => (j.location||'').toLowerCase().includes(_landingFilter.location));
  if(_landingFilter.dept) jobs = jobs.filter(j => (j.dept||'').toLowerCase().includes(_landingFilter.dept));
  if(_landingFilter.type) jobs = jobs.filter(j => (j.type||'').toLowerCase().includes(_landingFilter.type));
  if(_landingFilter.exp) jobs = jobs.filter(j => matchExpRange(j.exp, _landingFilter.exp));

  if(!jobs.length) return `<div class="lp-empty">No jobs match your search. Try adjusting your filters.</div>`;

  return jobs.map(j => {
    const posted = j.posted ? new Date(j.posted) : null;
    const daysAgo = posted ? Math.floor((Date.now() - posted.getTime()) / 86400000) : null;
    const closingSoon = daysAgo !== null && daysAgo > 20;
    return `
    <div class="lp-job-card">
      <div class="lp-job-card-top">
        <div class="lp-job-icon">${(j.title||'J')[0]}</div>
        <div class="lp-job-card-info">
          <div class="lp-job-title">${j.title}</div>
          <div class="lp-job-dept">${j.dept || 'General'}</div>
        </div>
        ${closingSoon ? '<span class="lp-badge lp-badge-urgent">Closing Soon</span>' : '<span class="lp-badge lp-badge-open">Open</span>'}
      </div>
      <div class="lp-job-meta">
        <span class="lp-job-meta-item">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
          ${j.location || 'Remote'}
        </span>
        <span class="lp-job-meta-item">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>
          ${j.type || 'Full-time'}
        </span>
        <span class="lp-job-meta-item">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10H12V2z"/><path d="M20.66 7A10 10 0 0 0 14 2v6h6.66z"/></svg>
          ${j.exp || 'Any'} years
        </span>
        <span class="lp-job-meta-item">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          ${daysAgo !== null ? (daysAgo === 0 ? 'Posted today' : `${daysAgo} days ago`) : 'Just posted'}
        </span>
      </div>
      <div class="lp-job-skills">${(j.skills||[]).slice(0,4).map(s=>`<span class="lp-skill-tag">${s}</span>`).join('')}</div>
      <div class="lp-job-bonus">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
        <span>Referral Bonus</span>
        <strong>₹${(j.bonus||0).toLocaleString('en-IN')}</strong>
      </div>
      <div class="lp-job-footer">
        <div class="lp-job-actions">
          <button class="lp-btn lp-btn-sm lp-btn-outline" onclick="showJobDetail('${j.id}')">View Details</button>
          <button class="lp-btn lp-btn-sm lp-btn-primary" onclick="showReferralModal('${j.id}')">Refer</button>
        </div>
      </div>
    </div>`;
  }).join('');
}

function hashStr(s){ let h=0; for(let i=0;i<s.length;i++){ h=((h<<5)-h)+s.charCodeAt(i); h|=0; } return h; }

function matchExpRange(jobExp, filterExp){
  if(!filterExp) return true;
  const num = parseInt(jobExp) || 0;
  if(filterExp === '10+') return num >= 10;
  const [min, max] = filterExp.split('-').map(Number);
  return num >= min && num <= max;
}

function setLandingFilter(dept){
  _landingFilter.dept = dept === 'all' ? '' : dept;
  document.querySelectorAll('.lp-filter-chip').forEach(c => {
    c.classList.toggle('lp-filter-chip-active', c.dataset.filter === dept);
  });
  const grid = document.getElementById('lpJobGrid');
  if(grid) grid.innerHTML = renderLandingJobCards();
}

function filterLandingJobs(){
  _landingFilter.keyword = (document.getElementById('lpKeyword')?.value || '').toLowerCase();
  _landingFilter.location = (document.getElementById('lpLocationFilter')?.value || '').toLowerCase();
  _landingFilter.dept = (document.getElementById('lpDept')?.value || '').toLowerCase();
  const grid = document.getElementById('lpJobGrid');
  if(grid) grid.innerHTML = renderLandingJobCards();
}

/* ================================ How It Works ================================ */
function lpHowItWorks(){
  const steps = [
    {
      num: '01',
      icon: `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
      title: 'Employee Refers',
      desc: 'Share your unique referral link with talented candidates in your network. One click is all it takes to start the process.'
    },
    {
      num: '02',
      icon: `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`,
      title: 'Candidate Applies',
      desc: 'The candidate fills out a streamlined application with their resume, experience, and portfolio details.'
    },
    {
      num: '03',
      icon: `<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2a10 10 0 1 0 10 10H12V2z"/><path d="M20.66 7A10 10 0 0 0 14 2v6h6.66z" fill="currentColor" opacity="0.2"/><polyline points="12 8 12 12 14 14"/></svg>`,
      title: 'AI Matches',
      desc: 'Our AI engine analyzes the resume against job requirements, scores the match, and surfaces the best-fit candidates.'
    }
  ];
  return `
  <section class="lp-section lp-section-alt" id="howItWorks">
    <div class="lp-container">
      <div class="lp-section-header">
        <span class="lp-section-badge">How It Works</span>
        <h2 class="lp-section-title">Three Simple Steps</h2>
        <p class="lp-section-sub">A streamlined process that makes referring candidates quick and clear.</p>
      </div>
      <div class="lp-steps-grid">
        ${steps.map((s,i) => `
          <div class="lp-step-card">
            <div class="lp-step-num">${s.num}</div>
            <div class="lp-step-icon">${s.icon}</div>
            <h3 class="lp-step-title">${s.title}</h3>
            <p class="lp-step-desc">${s.desc}</p>
            ${i < steps.length - 1 ? '<div class="lp-step-connector"></div>' : ''}
          </div>
        `).join('')}
      </div>
    </div>
  </section>`;
}

/* ================================ Why Refer Through Us ================================ */
function lpWhyRefer(){
  const features = [
    { icon: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2a10 10 0 1 0 10 10H12V2z"/><path d="M20.66 7A10 10 0 0 0 14 2v6h6.66z"/></svg>`, title: 'AI Resume Matching', desc: 'Intelligent matching that analyzes skills, experience, and cultural fit to connect the right candidates with the right roles.' },
    { icon: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`, title: 'Quick Referral Process', desc: 'Submit a referral in under 2 minutes. Our simplified workflow eliminates unnecessary friction and paperwork.' },
    { icon: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>`, title: 'Real-Time Tracking', desc: 'Track every referral from submission to onboarding with live status updates and transparent pipeline visibility.' },
    { icon: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>`, title: 'Rewards Up to ₹1 Lakh', desc: 'Earn competitive referral bonuses for every successful hire. The more you refer, the more you earn.' },
    { icon: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`, title: 'Transparent Process', desc: 'Complete visibility into where your referral stands at every stage. No more guessing or follow-up emails.' },
    { icon: `<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/></svg>`, title: 'Career Growth', desc: 'Help your network grow while advancing your own career. Build your reputation as a top referrer in the organization.' }
  ];
  return `
  <section class="lp-section" id="whyRefer">
    <div class="lp-container">
      <div class="lp-section-header">
        <span class="lp-section-badge">Why Choose Us</span>
        <h2 class="lp-section-title">Why Refer Through MuraAI</h2>
        <p class="lp-section-sub">We make employee referrals smarter, faster, and more rewarding.</p>
      </div>
      <div class="lp-features-grid">
        ${features.map(f => `
          <div class="lp-feature-card">
            <div class="lp-feature-icon">${f.icon}</div>
            <h3 class="lp-feature-title">${f.title}</h3>
            <p class="lp-feature-desc">${f.desc}</p>
          </div>
        `).join('')}
      </div>
    </div>
  </section>`;
}

/* ================================ FAQ ================================ */
function lpFaq(){
  const faqs = [
    { q: 'How do I refer a candidate?', a: 'Simply log in to the portal, browse open positions, and click "Refer" on any job posting. You can paste the candidate\'s resume directly or share your unique referral link. The entire process takes under 2 minutes.' },
    { q: 'What is the referral bonus amount?', a: 'Referral bonuses range from ₹25,000 to ₹1,00,000 depending on the role level. Junior roles offer ₹25,000-₹50,000, mid-level roles offer ₹50,000-₹75,000, and senior/leadership roles offer up to ₹1,00,000. The bonus is paid after the candidate completes 90 days.' },
    { q: 'How long does the hiring process take?', a: 'On average, referred candidates move through the pipeline 40% faster than external applicants. The typical timeline is 2-3 weeks from referral submission to offer, depending on the role and interview scheduling.' },
    { q: 'Can I refer multiple candidates?', a: 'Yes, there is no limit on the number of referrals you can submit. In fact, top referrers earn additional recognition and exclusive rewards through our leaderboard program. Many employees refer 5-10 candidates per quarter.' },
    { q: 'What happens if my referral is rejected?', a: 'If your referral is not selected, you will receive a notification with the general reason. You can refer the same person again for a different role after 6 months. The AI matching system will also suggest other roles that may be a better fit.' },
    { q: 'How does the AI matching work?', a: 'Our AI engine analyzes the candidate\'s resume against the job description, evaluating skills match, experience relevance, education alignment, and cultural fit indicators. It generates a detailed match score with strengths, gaps, and a recommendation — all in seconds.' },
    { q: 'When is the referral bonus paid?', a: 'The referral bonus is credited to your account within 30 days of the referred candidate completing their 90-day probation period. You can track the bonus status in the Rewards section of your dashboard.' },
    { q: 'Can I refer someone who previously applied?', a: 'If the candidate has not applied in the last 6 months, you can submit a referral for them. The system will check for duplicates and notify you if the candidate is already in our pipeline. Re-referrals for different positions are welcome.' }
  ];
  return `
  <section class="lp-section" id="faq">
    <div class="lp-container">
      <div class="lp-section-header">
        <span class="lp-section-badge">FAQ</span>
        <h2 class="lp-section-title">Frequently Asked Questions</h2>
        <p class="lp-section-sub">Everything you need to know about our referral program.</p>
      </div>
      <div class="lp-faq-list">
        ${faqs.map((f, i) => `
          <div class="lp-faq-item" data-faq="${i}">
            <div class="lp-faq-q" onclick="toggleFaq(${i})">
              <span>${f.q}</span>
              <svg class="lp-faq-chevron" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
            </div>
            <div class="lp-faq-a"><p>${f.a}</p></div>
          </div>
        `).join('')}
      </div>
    </div>
  </section>`;
}

function toggleFaq(i){
  const item = document.querySelector(`[data-faq="${i}"]`);
  if(item) item.classList.toggle('open');
}

/* ================================ Newsletter ================================ */
function lpNewsletter(){
  return `
  <section class="lp-newsletter-section">
    <div class="lp-container">
      <div class="lp-newsletter-card">
        <div class="nl-shimmer"></div>
        <div class="lp-newsletter-content">
          <h2 class="lp-newsletter-title">Stay Updated</h2>
          <p class="lp-newsletter-desc">Get notified about new job openings, referral rewards, and platform updates.</p>
        </div>
        <div class="lp-newsletter-form">
          <input type="email" class="lp-input lp-newsletter-input" placeholder="Enter your email address" id="lpNewsletterEmail"/>
          <button class="lp-btn lp-btn-primary lp-newsletter-btn" onclick="handleNewsletterSubscribe()">Subscribe</button>
        </div>
      </div>
    </div>
  </section>`;
}

function handleNewsletterSubscribe(){
  const email = document.getElementById('lpNewsletterEmail')?.value;
  if(!email || !email.includes('@')) return toast('Please enter a valid email address', 'error');
  toast('Subscribed. We will notify you of new openings.', 'success');
  const input = document.getElementById('lpNewsletterEmail');
  if(input) input.value = '';
}

/* ================================ Footer ================================ */
function lpFooter(){
  return `
  <footer class="lp-footer">
    <div class="lp-container">
      <div class="lp-footer-grid">
        <div class="lp-footer-col lp-footer-about">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:20px;">
            <div style="width:36px;height:36px;border-radius:8px;background:linear-gradient(135deg,#38BDF8,#0EA5E9);display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:800;color:#fff;font-family:'Space Grotesk',sans-serif;flex-shrink:0;">M</div>
            <span style="font-size:20px;font-weight:800;color:#fff;font-family:'Space Grotesk',sans-serif;letter-spacing:-0.3px;">MuraAI <span style="font-weight:500;color:#BAE6FD;">Refer</span></span>
          </div>
          <p class="lp-footer-desc">AI-powered employee referral platform that connects great talent with great companies.</p>
          <div class="lp-social-links">
            <a href="#" class="lp-social-icon" title="LinkedIn">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect x="2" y="9" width="4" height="12"/><circle cx="4" cy="4" r="2"/></svg>
            </a>
            <a href="#" class="lp-social-icon" title="Twitter">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M23 3a10.9 10.9 0 0 1-3.14 1.53 4.48 4.48 0 0 0-7.86 3v1A10.66 10.66 0 0 1 3 4s-4 9 5 13a11.64 11.64 0 0 1-7 2c9 5 20 0 20-11.5a4.5 4.5 0 0 0-.08-.83A7.72 7.72 0 0 0 23 3z"/></svg>
            </a>
            <a href="#" class="lp-social-icon" title="Facebook">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/></svg>
            </a>
            <a href="#" class="lp-social-icon" title="Instagram">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"/></svg>
            </a>
          </div>
        </div>
        <div class="lp-footer-col">
          <h4 class="lp-footer-heading">Quick Links</h4>
          <a href="#jobs" class="lp-footer-link">Search Jobs</a>
          <a href="#howItWorks" class="lp-footer-link">How It Works</a>
          <a href="#whyRefer" class="lp-footer-link">Why Refer</a>
          <a href="#faq" class="lp-footer-link">FAQ</a>
        </div>
        <div class="lp-footer-col">
          <h4 class="lp-footer-heading">Careers</h4>
          <a href="#jobs" class="lp-footer-link" onclick="setLandingFilter('Engineering')">Engineering</a>
          <a href="#jobs" class="lp-footer-link" onclick="setLandingFilter('Product')">Product</a>
          <a href="#jobs" class="lp-footer-link" onclick="setLandingFilter('Design')">Design</a>
          <a href="#jobs" class="lp-footer-link" onclick="setLandingFilter('Marketing')">Marketing</a>
          <a href="#jobs" class="lp-footer-link">View All Roles</a>
        </div>
        <div class="lp-footer-col">
          <h4 class="lp-footer-heading">Contact</h4>
          <p class="lp-footer-contact">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-2px;margin-right:6px;"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
            MuraAI Technologies Pvt. Ltd.<br/>HSR Layout, Bengaluru, India 560102
          </p>
          <p class="lp-footer-contact">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-2px;margin-right:6px;"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
            careers@muraai.com
          </p>
          <p class="lp-footer-contact">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-2px;margin-right:6px;"><path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/></svg>
            +91 80 4567 8900
          </p>
        </div>
      </div>
      <div class="lp-footer-bottom">
        <span>&copy; 2026 MuraAI Technologies. All Rights Reserved.</span>
      </div>
    </div>
  </footer>`;
}

/* ================================ Job Detail Modal ================================ */
function showJobDetail(jobId){
  const j = _landingJobs.find(x=>x.id===jobId);
  if(!j){ toast('Job details could not be loaded. Please refresh the page.', 'amber'); return; }
  const skills = (j.skills||[]);
  const posted = j.posted ? new Date(j.posted).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'}) : '';
  const modal = document.getElementById('landingModals');
  modal.innerHTML = `
  <div class="lp-modal-overlay" onclick="if(event.target===this)this.remove()">
    <div class="lp-modal jd-modal pop-in">
      <div class="jd-hero">
        <div class="jd-hero-glow"></div>
        <div class="jd-hero-top">
          <div class="jd-status-badge"><span class="jd-badge-pulse"></span>${j.status || 'Open'}</div>
          <button class="jd-close-btn" onclick="this.closest('.lp-modal-overlay').remove()">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
        <h2 class="jd-hero-title">${j.title}</h2>
        <div class="jd-hero-tags">
          <span class="jd-hero-tag"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>${j.dept}</span>
          <span class="jd-hero-tag"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>${j.location}</span>
          <span class="jd-hero-tag"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>${j.type || 'Full-time'}</span>
          ${j.exp ? `<span class="jd-hero-tag"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>${j.exp} years</span>` : ''}
        </div>
      </div>
      <div class="jd-body">
        <div class="jd-stats-row">
          <div class="jd-stat-card">
            <div class="jd-stat-icon jd-stat-blue"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg></div>
            <div class="jd-stat-info"><span class="jd-stat-label">Referral Bonus</span><span class="jd-stat-val jd-val-green">\u20B9${(j.bonus||0).toLocaleString('en-IN')}</span></div>
          </div>
          <div class="jd-stat-card">
            <div class="jd-stat-icon jd-stat-indigo"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg></div>
            <div class="jd-stat-info"><span class="jd-stat-label">Openings</span><span class="jd-stat-val">${j.openings || 1}</span></div>
          </div>
          <div class="jd-stat-card">
            <div class="jd-stat-icon jd-stat-teal"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg></div>
            <div class="jd-stat-info"><span class="jd-stat-label">Posted${posted ? ' \u00B7 '+posted : ''}</span><span class="jd-stat-val">ID: #${j.id}</span></div>
          </div>
        </div>
        ${skills.length ? `
        <div class="jd-section">
          <div class="jd-section-header">
            <div class="jd-section-icon jd-sec-blue"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg></div>
            <h3>Required Skills</h3>
          </div>
          <div class="jd-skills-grid">${skills.map(s=>`<span class="jd-skill">${s}</span>`).join('')}</div>
        </div>` : ''}
        ${j.description ? `
        <div class="jd-section">
          <div class="jd-section-header">
            <div class="jd-section-icon jd-sec-indigo"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></div>
            <h3>Job Description</h3>
          </div>
          <div class="jd-desc-content">${j.description}</div>
        </div>` : ''}
        <div class="jd-footer-actions">
          <button class="jd-btn jd-btn-ghost" onclick="this.closest('.lp-modal-overlay').remove()">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
            Back to Jobs
          </button>
          <button class="jd-btn jd-btn-primary" onclick="this.closest('.lp-modal-overlay').remove();showReferralModal('${j.id}')">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg>
            Refer a Candidate
          </button>
        </div>
      </div>
    </div>
  </div>`;
}

/* ================================ Apply Modal ================================ */
function showApplyModal(jobId){
  const j = _landingJobs.find(x=>x.id===jobId);
  if(!j) return;
  const loggedIn = !!getToken();
  const modal = document.getElementById('landingModals');

  if(!loggedIn){
    modal.innerHTML = `
    <div class="lp-modal-overlay" onclick="if(event.target===this)this.remove()">
      <div class="lp-modal lp-modal-sm pop-in">
        <div class="lp-modal-header">
          <div>
            <h2 class="lp-modal-title">Candidate Sign In</h2>
            <div class="lp-modal-sub">Sign in with your candidate account to apply</div>
          </div>
          <button class="lp-modal-close" onclick="this.closest('.lp-modal-overlay').remove()">&times;</button>
        </div>
        <div class="lp-modal-body">
          <div class="lp-auth-tabs">
            <button class="lp-auth-tab lp-auth-tab-active" onclick="showApplyModal('${jobId}')" id="lpApplyLoginTab">Sign In</button>
            <button class="lp-auth-tab" onclick="showApplyRegisterForJob('${jobId}')">Register</button>
          </div>
          <form id="lpApplyLoginForm" onsubmit="handleLpApplyLogin(event,'${jobId}')">
            <div class="lp-form-group"><label class="lp-label">Email</label><input class="lp-input" name="email" type="email" required placeholder="your@email.com" id="lpApplyLoginEmail"/></div>
            <div class="lp-form-group"><label class="lp-label">Password</label><input class="lp-input" name="password" type="password" required placeholder="Enter your password" id="lpApplyLoginPass"/></div>
            <div class="lp-form-actions"><button type="submit" class="lp-btn lp-btn-primary" style="width:100%;justify-content:center;" id="lpApplyLoginBtn">Sign In</button></div>
            <div id="lpApplyLoginError" class="lp-form-error"></div>
          </form>
        </div>
      </div>
    </div>`;
    return;
  }

  modal.innerHTML = `
  <div class="lp-modal-overlay" onclick="if(event.target===this)this.remove()">
    <div class="lp-modal pop-in">
      <div class="lp-modal-header">
        <div>
          <h2 class="lp-modal-title">Apply for ${j.title}</h2>
          <div class="lp-modal-sub">${j.dept} &middot; ${j.location}</div>
        </div>
        <button class="lp-modal-close" onclick="this.closest('.lp-modal-overlay').remove()">&times;</button>
      </div>
      <div class="lp-modal-body">
        <form id="lpCandidateApplyForm" onsubmit="handleCandidateApply(event,'${jobId}')">
          <div class="lp-form-group">
            <label class="lp-label">Resume Text</label>
            <textarea class="lp-input lp-textarea" name="resumeText" rows="6" placeholder="Paste your resume content here..." id="lpApplyResumeText"></textarea>
          </div>
          <div class="lp-form-group">
            <label class="lp-label">Upload Resume</label>
            <input type="file" class="lp-input lp-file-input" accept=".pdf,.doc,.docx,.txt" id="lpApplyResumeFile"/>
          </div>
          <div class="lp-form-row">
            <div class="lp-form-group"><label class="lp-label">LinkedIn Profile</label><input class="lp-input" name="linkedin" placeholder="linkedin.com/in/yourprofile"/></div>
            <div class="lp-form-group"><label class="lp-label">GitHub Profile</label><input class="lp-input" name="github" placeholder="github.com/yourprofile"/></div>
          </div>
          <div class="lp-form-group"><label class="lp-label">Portfolio URL</label><input class="lp-input" name="portfolio" placeholder="https://yourportfolio.com"/></div>
          <div class="lp-form-row">
            <div class="lp-form-group"><label class="lp-label">Phone Number *</label><input class="lp-input" name="phone" required placeholder="+91 98765 43210"/></div>
            <div class="lp-form-group"><label class="lp-label">Location</label><input class="lp-input" name="location" placeholder="City, Country"/></div>
          </div>
          <div class="lp-form-row">
            <div class="lp-form-group"><label class="lp-label">Years of Experience</label><input class="lp-input" name="experience" type="number" min="0" placeholder="e.g. 5"/></div>
            <div class="lp-form-group"><label class="lp-label">Education</label><input class="lp-input" name="education" placeholder="e.g. B.Tech Computer Science"/></div>
          </div>
          <div class="lp-form-group"><label class="lp-label">Skills (comma-separated)</label><input class="lp-input" name="skills" placeholder="e.g. Python, React, AWS, SQL"/></div>
          <div class="lp-form-actions">
            <button type="button" class="lp-btn lp-btn-outline" onclick="this.closest('.lp-modal-overlay').remove()">Cancel</button>
            <button type="submit" class="lp-btn lp-btn-primary" id="lpApplySubmitBtn">Submit Application</button>
          </div>
        </form>
        <div id="lpApplyResult"></div>
      </div>
    </div>
  </div>`;
}

function showApplyRegisterForJob(jobId){
  const modal = document.getElementById('landingModals');
  modal.innerHTML = `
  <div class="lp-modal-overlay" onclick="if(event.target===this)this.remove()">
    <div class="lp-modal lp-modal-sm pop-in">
      <div class="lp-modal-header">
        <div>
          <h2 class="lp-modal-title">Create Candidate Account</h2>
          <div class="lp-modal-sub">Join MuraAI Refer to apply</div>
        </div>
        <button class="lp-modal-close" onclick="this.closest('.lp-modal-overlay').remove()">&times;</button>
      </div>
      <div class="lp-modal-body">
        <div class="lp-auth-tabs">
          <button class="lp-auth-tab" onclick="showApplyModal('${jobId}')">Sign In</button>
          <button class="lp-auth-tab lp-auth-tab-active">Register</button>
        </div>
        <form id="lpApplyRegForm" onsubmit="handleLpApplyRegister(event,'${jobId}')">
          <div class="lp-form-group"><label class="lp-label">Full Name</label><input class="lp-input" name="name" required placeholder="Your full name" id="lpApplyRegName"/></div>
          <div class="lp-form-group"><label class="lp-label">Email</label><input class="lp-input" name="email" type="email" required placeholder="your@email.com" id="lpApplyRegEmail"/></div>
          <div class="lp-form-group"><label class="lp-label">Password</label><input class="lp-input" name="password" type="password" required placeholder="Minimum 8 characters" id="lpApplyRegPass"/></div>
          <div class="lp-form-actions"><button type="submit" class="lp-btn lp-btn-primary" style="width:100%;justify-content:center;" id="lpApplyRegBtn">Create Account</button></div>
          <div id="lpApplyRegError" class="lp-form-error"></div>
        </form>
      </div>
    </div>
  </div>`;
}

async function handleLpApplyLogin(e, jobId){
  e.preventDefault();
  const btn = document.getElementById('lpApplyLoginBtn');
  const errEl = document.getElementById('lpApplyLoginError');
  btn.disabled = true; btn.textContent = 'Signing in...'; errEl.textContent = '';
  try{
    const email = document.getElementById('lpApplyLoginEmail').value.trim();
    const password = document.getElementById('lpApplyLoginPass').value;
    const data = await api('/api/candidates/login', {method:'POST', body:{email, password}, auth:false});
    setToken(data.access_token);
    state.user = data.user; state.role = 'candidate';
    showApplyModal(jobId);
  }catch(err){
    errEl.textContent = err.message || 'Sign In failed';
    btn.disabled = false; btn.textContent = 'Sign In';
  }
}

async function handleLpApplyRegister(e, jobId){
  e.preventDefault();
  const btn = document.getElementById('lpApplyRegBtn');
  const errEl = document.getElementById('lpApplyRegError');
  btn.disabled = true; btn.textContent = 'Creating account…'; errEl.textContent = '';
  try{
    const name = document.getElementById('lpApplyRegName').value.trim();
    const email = document.getElementById('lpApplyRegEmail').value.trim();
    const password = document.getElementById('lpApplyRegPass').value;
    const data = await api('/api/candidates/register', {method:'POST', body:{name, email, password, phone:''}, auth:false});
    setToken(data.access_token);
    state.user = data.user; state.role = 'candidate';
    showApplyModal(jobId);
  }catch(err){
    errEl.textContent = err.message || 'Unable to create account. Please try again.';
    btn.disabled = false; btn.textContent = 'Create Account';
  }
}

async function handleCandidateApply(e, jobId){
  e.preventDefault();
  const btn = document.getElementById('lpApplySubmitBtn');
  const resultEl = document.getElementById('lpApplyResult');
  btn.disabled = true; btn.textContent = 'Submitting…';
  const fd = new FormData(e.target);
  const job = _landingJobs.find(x=>x.id===jobId);

  const applyBody = {
    jobId,
    candidateName: state.user?.name || 'Candidate',
    email: state.user?.email || '',
    phone: fd.get('phone') || '',
    location: fd.get('location') || '',
    experience: fd.get('experience') || '',
    education: fd.get('education') || '',
    skills: (fd.get('skills') || '').split(',').map(s=>s.trim()).filter(Boolean),
    resumeText: fd.get('resumeText') || '',
    linkedin: fd.get('linkedin') || '',
    github: fd.get('github') || '',
    portfolio: fd.get('portfolio') || '',
    referredBy: 'self',
  };

  try{
    const appResult = await api('/api/candidates/apply', { method:'POST', body: applyBody });

    const appJob = _landingJobs.find(x=>x.id===jobId);
    const confirmId = appResult.id || '—';
    resultEl.innerHTML = `
    <div style="text-align:center;padding:16px 0;">
      <div style="width:56px;height:56px;border-radius:50%;background:linear-gradient(135deg,#059669,#10B981);display:flex;align-items:center;justify-content:center;margin:0 auto 14px;font-size:24px;color:#fff;">✓</div>
      <h3 style="margin:0 0 6px;font-size:17px;color:#059669;">Application submitted</h3>
      <p style="color:var(--ink-soft);font-size:13px;margin:0 0 16px;">Your application has been recorded and will be reviewed.</p>
      <div class="glass" style="padding:14px;text-align:left;max-width:420px;margin:0 auto 16px;">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:12.5px;">
          <div><span style="color:var(--ink-soft);">Application ID:</span><div class="mono" style="font-weight:700;margin-top:2px;">${confirmId}</div></div>
          <div><span style="color:var(--ink-soft);">Job ID:</span><div class="mono" style="font-weight:700;margin-top:2px;">${jobId}</div></div>
          <div><span style="color:var(--ink-soft);">Job Title:</span><div style="font-weight:700;margin-top:2px;">${appJob?.title || '—'}</div></div>
          <div><span style="color:var(--ink-soft);">Email:</span><div style="font-weight:700;margin-top:2px;">${state.user?.email || '—'}</div></div>
        </div>
      </div>
      <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap;">
        <button class="lp-btn lp-btn-primary lp-btn-sm" onclick="document.querySelector('.lp-modal-overlay')?.remove();_cpLastApplication={id:'${confirmId}',jobId:'${jobId}',jobTitle:'${(appJob?.title||'').replace(/'/g,"\\'")}'};_cpView='confirmation';render();">Track Application</button>
        <button class="lp-btn lp-btn-outline lp-btn-sm" onclick="document.querySelector('.lp-modal-overlay')?.remove();_cpView='dashboard';loadCandidateData().then(()=>render());">Go to Dashboard</button>
      </div>
    </div>`;

    }catch(err){
      resultEl.innerHTML = `<div class="lp-error-box">${err.message || 'We couldn\u2019t submit the application. Please try again.'}</div>`;
      btn.disabled = false; btn.textContent = 'Submit Application';
    }
}

/* ================================ Referral Modal ================================ */
function showReferralModal(jobId){
  const j = _landingJobs.find(x=>x.id===jobId);
  if(!j) return;
  const loggedIn = !!getToken();
  const modal = document.getElementById('landingModals');

  if(!loggedIn){
    modal.innerHTML = `
    <div class="lp-modal-overlay" onclick="if(event.target===this)this.remove()">
      <div class="lp-modal lp-modal-sm pop-in">
        <div class="lp-modal-header">
          <div>
            <h2 class="lp-modal-title">Sign In Required</h2>
            <div class="lp-modal-sub">Sign in as an employee to refer candidates</div>
          </div>
          <button class="lp-modal-close" onclick="this.closest('.lp-modal-overlay').remove()">&times;</button>
        </div>
        <div class="lp-modal-body" style="text-align:center;padding:32px 28px;">
          <p style="color:var(--text-secondary);font-size:14px;margin-bottom:20px;">You need an employee account to generate referral links and track your referrals.</p>
          <button class="lp-btn lp-btn-primary lp-btn-lg" onclick="this.closest('.lp-modal-overlay').remove();showLoginModal()">Sign In</button>
          <p style="font-size:12px;color:var(--text-muted);margin-top:14px;">Access is managed by your organization. Contact HR if you need an account.</p>
        </div>
      </div>
    </div>`;
    return;
  }

  const referralLink = `${window.location.origin}/refer?job=${jobId}&ref=${state.user?.employeeId || state.user?.id || 'unknown'}`;
  modal.innerHTML = `
  <div class="lp-modal-overlay" onclick="if(event.target===this)this.remove()">
    <div class="lp-modal lp-modal-sm pop-in ref-modal">
      <div class="ref-topbar">
        <button class="ref-close-btn" onclick="this.closest('.lp-modal-overlay').remove()">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
      <div class="ref-hero-light">
        <div class="ref-hero-icon"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg></div>
        <h2 class="ref-hero-title">Refer a Candidate</h2>
        <div class="ref-hero-tags">
          <span class="ref-hero-tag">${j.title}</span>
          <span class="ref-hero-tag">${j.dept}</span>
          <span class="ref-hero-tag">${j.location}</span>
        </div>
      </div>
      <div class="ref-body">
        <div class="ref-link-card">
          <div class="ref-link-label">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
            Your Referral Link
          </div>
          <div class="ref-link-row">
            <input class="ref-link-input" value="${referralLink}" readonly id="lpReferralLinkInput"/>
            <button class="ref-link-copy" onclick="copyReferralLink()">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              Copy
            </button>
          </div>
          <button class="ref-share-email" onclick="shareReferralEmail('${j.title}','${referralLink}')">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
            Share via Email
          </button>
        </div>
        <div class="ref-divider"><span>or submit manually</span></div>
        <div class="ref-form-section">
          <div class="ref-form-header">
            <div class="ref-form-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg></div>
            <span>Candidate Details</span>
          </div>
          <form id="lpReferralForm" onsubmit="submitLpReferral(event,'${jobId}')">
            <div class="ref-form-group">
              <label class="ref-label">Candidate Name <span class="ref-required">*</span></label>
              <div class="ref-input-wrap"><input class="ref-input" name="candidateName" required placeholder="e.g. John Smith"/></div>
            </div>
            <div class="ref-form-row">
              <div class="ref-form-group">
                <label class="ref-label">Email Address <span class="ref-required">*</span></label>
                <div class="ref-input-wrap"><input class="ref-input" name="email" type="email" required placeholder="john@example.com"/></div>
              </div>
              <div class="ref-form-group">
                <label class="ref-label">Phone Number</label>
                <div class="ref-input-wrap"><input class="ref-input" name="phone" placeholder="+91 98765 43210"/></div>
              </div>
            </div>
            <div class="ref-form-group">
              <label class="ref-label">LinkedIn Profile</label>
              <div class="ref-input-wrap"><input class="ref-input" name="linkedin" placeholder="linkedin.com/in/candidate"/></div>
            </div>
            <div class="ref-form-group">
              <label class="ref-label">Resume or Summary</label>
              <div class="ref-input-wrap"><textarea class="ref-input ref-textarea" name="resumeText" rows="3" placeholder="Paste resume content or highlight key skills and experience."></textarea></div>
            </div>
            <div class="ref-form-group">
              <label class="ref-label">Why is this candidate a good fit?</label>
              <div class="ref-input-wrap"><textarea class="ref-input ref-textarea" name="notes" rows="2" placeholder="Your recommendation…"></textarea></div>
            </div>
            <div class="ref-form-actions">
              <button type="button" class="ref-btn ref-btn-ghost" onclick="this.closest('.lp-modal-overlay').remove()">Cancel</button>
              <button type="submit" class="ref-btn ref-btn-primary" id="lpSubmitRefBtn">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                Submit Referral
              </button>
            </div>
          </form>
          <div id="lpReferralResult"></div>
        </div>
      </div>
    </div>
  </div>`;
}

function copyReferralLink(){
  const input = document.getElementById('lpReferralLinkInput');
  if(input){
    input.select();
    navigator.clipboard.writeText(input.value).then(()=> toast('Referral link copied', 'success')).catch(()=> toast('We couldn\u2019t copy the link. Please try again.', 'error'));
  }
}

function shareReferralEmail(jobTitle, link){
  const subject = encodeURIComponent(`Refer a candidate for ${jobTitle} at MuraAI`);
  const body = encodeURIComponent(`Hi,\n\nI thought you might be interested in this role at MuraAI:\n\n${jobTitle}\n\nApply through my referral link: ${link}\n\nBest regards`);
  window.open(`mailto:?subject=${subject}&body=${body}`, '_blank');
}

async function submitLpReferral(e, jobId){
  e.preventDefault();
  const form = e.target;
  const btn = document.getElementById('lpSubmitRefBtn');
  const resultEl = document.getElementById('lpReferralResult');
  btn.disabled = true; btn.textContent = 'Submitting…';
  const fd = new FormData(form);
  try{
    await api('/api/referrals', { method:'POST', body:{
      candidateName: fd.get('candidateName'), email: fd.get('email'), phone: fd.get('phone'),
      linkedin: fd.get('linkedin'), resumeText: fd.get('resumeText') || 'No resume provided',
      notes: fd.get('notes'), jobId: jobId,
    }});
    resultEl.innerHTML = `<div class="ref-success-box">
      <div class="ref-success-icon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg></div>
      <div class="ref-success-title">Referral submitted</div>
      <div class="ref-success-text">Our HR team will review it shortly.</div>
    </div>`;
    form.style.display = 'none';
  }catch(err){
    resultEl.innerHTML = `<div class="ref-error-box">${err.message || 'We couldn\u2019t submit the referral. Please try again.'}</div>`;
    btn.disabled = false; btn.textContent = 'Submit Referral';
  }
}

/* ================================ Login Modal ================================ */

function showLoginModal(){
  const modal = document.getElementById('landingModals');
  modal.innerHTML = `
  <div class="lp-modal-overlay enterprise-login-overlay" onclick="if(event.target===this)this.remove()">
    <div class="enterprise-login-card pop-in" role="dialog" aria-modal="true" aria-labelledby="enterpriseLoginTitle">
      <button class="enterprise-login-close" aria-label="Close sign in" onclick="this.closest('.lp-modal-overlay').remove()">&times;</button>
      <div class="enterprise-login-content">
        <div class="enterprise-login-eyebrow"><span></span> MURAAI REFER</div>
        <h2 id="enterpriseLoginTitle">Welcome to your<br><em>talent network.</em></h2>
        <button class="enterprise-microsoft-button" onclick="ssoLogin()">
          <span class="enterprise-ms-mark"><i></i><i></i><i></i><i></i></span>
          <span>Continue with Microsoft</span>
          <b>→</b>
        </button>
        <div class="enterprise-login-divider"><span>OR</span></div>
        <form class="enterprise-email-login" id="lpLoginForm" onsubmit="handleLpLogin(event)">
          <label class="enterprise-field-label" for="lpLoginEmail">Email Address</label>
          <div class="enterprise-input-wrap">
            <input id="lpLoginEmail" type="email" required autocomplete="email" placeholder="name@company.com">
          </div>
          <div class="enterprise-password-label"><label for="lpLoginPass">Password</label></div>
          <div class="enterprise-input-wrap enterprise-password-wrap">
            <input id="lpLoginPass" type="password" required autocomplete="current-password" placeholder="Enter your password">
            <button type="button" class="enterprise-password-toggle" id="lpTogglePass" aria-label="Show password" onclick="toggleLpPassword()">
              <svg class="eye-open" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/><circle cx="12" cy="12" r="3"/></svg>
              <svg class="eye-closed" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="display:none"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><path d="M1 1l22 22"/></svg>
            </button>
          </div>
          <div class="enterprise-forgot-row"><a href="#" class="enterprise-forgot-link" onclick="showForgotModal();event.preventDefault()">Forgot password?</a></div>
          <button type="submit" class="enterprise-email-button" id="lpLoginBtn">Sign In</button>
          <div id="lpLoginError" class="lp-form-error"></div>
        </form>
        <div class="enterprise-login-help">Need access? <span>Contact your HR administrator.</span></div>
      </div>
      <div class="enterprise-login-illustration" aria-hidden="true">
        <div class="enterprise-illustration-orbit orbit-a"></div><div class="enterprise-illustration-orbit orbit-b"></div>
        <div class="enterprise-illustration-core">MuraAI</div>
        <div class="enterprise-illustration-card card-a"><span>92%</span><small>Role match</small></div>
        <div class="enterprise-illustration-card card-b"><span>18</span><small>Open roles</small></div>
        <div class="enterprise-illustration-line"></div>
        <div class="enterprise-illustration-caption"><b>Hiring intelligence</b><span>Connected. Secure. Real time.</span></div>
      </div>
    </div>
  </div>`;
}

function showLpEmployeeRegister(){
  const modal = document.getElementById('landingModals');
  modal.innerHTML = `
  <div class="lp-modal-overlay" onclick="if(event.target===this)this.remove()">
    <div class="lp-modal lp-modal-sm pop-in">
      <div class="lp-modal-header">
        <div>
          <h2 class="lp-modal-title">Create Employee Account</h2>
          <div class="lp-modal-sub">Join MuraAI Refer as an employee</div>
        </div>
        <button class="lp-modal-close" onclick="this.closest('.lp-modal-overlay').remove()">&times;</button>
      </div>
      <div class="lp-modal-body">
        <form id="lpEmpRegForm" onsubmit="handleLpEmployeeRegister(event)">
          <div class="lp-form-group"><label class="lp-label">Full Name</label><input class="lp-input" name="name" required placeholder="Your full name" id="lpEmpRegName"/></div>
          <div class="lp-form-group"><label class="lp-label">Work Email</label><input class="lp-input" name="email" type="email" required placeholder="you@company.com" id="lpEmpRegEmail"/></div>
          <div class="lp-form-group"><label class="lp-label">Password</label><input class="lp-input" name="password" type="password" required placeholder="Minimum 8 characters" id="lpEmpRegPass"/></div>
          <div class="lp-form-actions" style="flex-direction:column;gap:10px;">
            <button type="submit" class="lp-btn lp-btn-primary" style="width:100%;justify-content:center;" id="lpEmpRegBtn">Create Account</button>
          </div>
          <div id="lpEmpRegError" class="lp-form-error"></div>
          <div style="text-align:center;margin-top:14px;font-size:13px;">
            <a href="#" onclick="showLoginModal();event.preventDefault()" style="color:var(--primary);font-weight:600;">Already have an account? Sign In</a>
          </div>
        </form>
      </div>
    </div>
  </div>`;
}

async function handleLpEmployeeRegister(e){
  e.preventDefault();
  const btn = document.getElementById('lpEmpRegBtn');
  const errEl = document.getElementById('lpEmpRegError');
  btn.disabled = true; btn.textContent = 'Creating account…'; errEl.textContent = '';
  try{
    const name = document.getElementById('lpEmpRegName').value.trim();
    const email = document.getElementById('lpEmpRegEmail').value.trim();
    const password = document.getElementById('lpEmpRegPass').value;
    const data = await api('/api/auth/register', {method:'POST', body:{name, email, password, role:'employee', dept:'General'}, auth:false});
    setToken(data.access_token);
    state.user = data.user;
    state.role = data.user.role;
    document.querySelector('.lp-modal-overlay')?.remove();
    toast('Account created. Welcome to MuraAI Refer.', 'success');
    await loadAllData();
    render();
    startPolling();
  }catch(err){
    errEl.textContent = err.message || 'Unable to create account. Please try again.';
    btn.disabled = false; btn.textContent = 'Create Account';
  }
}

async function handleLpLogin(e){
  e.preventDefault();
  const btn = document.getElementById('lpLoginBtn');
  const errEl = document.getElementById('lpLoginError');
  btn.disabled = true; btn.textContent = 'Signing in…'; errEl.textContent = '';
  try{
    const email = document.getElementById('lpLoginEmail').value.trim();
    const password = document.getElementById('lpLoginPass').value;
    const data = await api('/api/auth/login', {method:'POST', body:{email, password}, auth:false});
    setToken(data.access_token);
    state.user = data.user;
    state.role = data.user.role;
    document.querySelector('.lp-modal-overlay')?.remove();
    toast('Signed in successfully.', 'success');
    await loadAllData();
    render();
    startPolling();
    if(state.referPendingJob && state.role !== 'candidate'){ nav('refer'); }
  }catch(err){
    errEl.textContent = err.message || 'Sign In failed';
    btn.disabled = false; btn.textContent = 'Sign In';
  }
}

function ssoLogin(){
  window.location.href = '/api/auth/microsoft/login';
}

function toggleLpPassword(){
  const input = document.getElementById('lpLoginPass');
  const toggle = document.getElementById('lpTogglePass');
  const show = input.type === 'password';
  input.type = show ? 'text' : 'password';
  toggle.classList.toggle('active', show);
  toggle.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
}

function showForgotModal(){
  const modal = document.getElementById('landingModals');
  modal.innerHTML = `
  <div class="lp-modal-overlay" onclick="if(event.target===this)this.remove()">
    <div class="lp-modal lp-modal-sm pop-in">
      <div class="lp-modal-header">
        <div>
          <h2 class="lp-modal-title">Reset Password</h2>
          <div class="lp-modal-sub">We'll email you a link to get back in</div>
        </div>
        <button class="lp-modal-close" onclick="this.closest('.lp-modal-overlay').remove()">&times;</button>
      </div>
      <div class="lp-modal-body">
        <form id="lpForgotForm" onsubmit="handleLpForgot(event)">
          <div class="lp-form-group"><label class="lp-label">Work Email</label><input class="lp-input" name="email" type="email" required placeholder="you@company.com" id="lpForgotEmail"/></div>
          <div class="lp-form-actions" style="flex-direction:column;gap:10px;">
            <button type="submit" class="lp-btn lp-btn-primary" style="width:100%;justify-content:center;" id="lpForgotBtn">Send reset link</button>
          </div>
          <div id="lpForgotError" class="lp-form-error"></div>
          <div id="lpForgotSuccess" style="color:#059669;font-size:12.5px;margin-top:10px;text-align:center;"></div>
          <div style="text-align:center;margin-top:14px;font-size:13px;">
            <a href="#" onclick="showLoginModal();event.preventDefault()" style="color:var(--primary);font-weight:600;">Back to Sign In</a>
          </div>
        </form>
      </div>
    </div>
  </div>`;
}

async function handleLpForgot(e){
  e.preventDefault();
  const btn = document.getElementById('lpForgotBtn');
  const errEl = document.getElementById('lpForgotError');
  const okEl = document.getElementById('lpForgotSuccess');
  btn.disabled = true; btn.textContent = 'Sending…'; errEl.textContent = ''; okEl.textContent = '';
  try{
    const email = document.getElementById('lpForgotEmail').value.trim();
    const res = await api('/api/auth/forgot-password', {method:'POST', body:{email}, auth:false});
    okEl.textContent = res.message || 'If an account exists for that email, a reset link has been sent.';
  }catch(err){
    errEl.textContent = err.message || 'We couldn\u2019t send the reset link. Please try again.';
  }finally{
    btn.disabled = false; btn.textContent = 'Send reset link';
  }
}

function showResetModal(){
  const modal = document.getElementById('landingModals');
  modal.innerHTML = `
  <div class="lp-modal-overlay" onclick="if(event.target===this)this.remove()">
    <div class="lp-modal lp-modal-sm pop-in">
      <div class="lp-modal-header">
        <div>
          <h2 class="lp-modal-title">Choose a New Password</h2>
          <div class="lp-modal-sub">Enter and confirm your new password</div>
        </div>
        <button class="lp-modal-close" onclick="this.closest('.lp-modal-overlay').remove()">&times;</button>
      </div>
      <div class="lp-modal-body">
        <form id="lpResetForm" onsubmit="handleLpReset(event)">
          <div class="lp-form-group"><label class="lp-label">New Password</label><input class="lp-input" name="newPass" type="password" required placeholder="Minimum 8 characters" id="lpResetPass"/></div>
          <div class="lp-form-group"><label class="lp-label">Confirm New Password</label><input class="lp-input" name="confirmPass" type="password" required placeholder="Re-enter your new password" id="lpResetPassConfirm"/></div>
          <div class="lp-form-actions" style="flex-direction:column;gap:10px;">
            <button type="submit" class="lp-btn lp-btn-primary" style="width:100%;justify-content:center;" id="lpResetBtn">Update password</button>
          </div>
          <div id="lpResetError" class="lp-form-error"></div>
          <div style="text-align:center;margin-top:14px;font-size:13px;">
            <a href="#" onclick="showLoginModal();event.preventDefault()" style="color:var(--primary);font-weight:600;">Back to Sign In</a>
          </div>
        </form>
      </div>
    </div>
  </div>`;
}

async function handleLpReset(e){
  e.preventDefault();
  const btn = document.getElementById('lpResetBtn');
  const errEl = document.getElementById('lpResetError');
  const newPass = document.getElementById('lpResetPass').value;
  const confirmPass = document.getElementById('lpResetPassConfirm').value;
  if(newPass !== confirmPass){ errEl.textContent = 'Passwords do not match.'; return; }
  if(!state.resetToken){ errEl.textContent = 'The reset link is missing its token. Please request a new one.'; return; }
  btn.disabled = true; btn.textContent = 'Updating…'; errEl.textContent = '';
  try{
    await api('/api/auth/reset-password', {method:'POST', body:{token: state.resetToken, newPassword: newPass}, auth:false});
    toast('Password updated — sign in with your new password', 'success');
    state.resetToken = null; state.loginMode = 'login';
    showLoginModal();
  }catch(err){
    errEl.textContent = err.message || 'We couldn\u2019t update the password. Please try again.';
  }finally{
    btn.disabled = false; btn.textContent = 'Update password';
  }
}

function showRegisterModal(){
  const modal = document.getElementById('landingModals');
  modal.innerHTML = `
  <div class="lp-modal-overlay" onclick="if(event.target===this)this.remove()">
    <div class="lp-modal lp-modal-sm pop-in">
      <div class="lp-modal-header">
        <div>
          <h2 class="lp-modal-title">Create Account</h2>
          <div class="lp-modal-sub">Join MuraAI Refer as an employee</div>
        </div>
        <button class="lp-modal-close" onclick="this.closest('.lp-modal-overlay').remove()">&times;</button>
      </div>
      <div class="lp-modal-body">
        <form id="lpRegForm" onsubmit="handleLpRegister(event)">
          <div class="lp-form-group"><label class="lp-label">Full Name</label><input class="lp-input" name="name" required placeholder="Your full name" id="lpRegName"/></div>
          <div class="lp-form-group"><label class="lp-label">Work Email</label><input class="lp-input" name="email" type="email" required placeholder="you@company.com" id="lpRegEmail"/></div>
          <div class="lp-form-group"><label class="lp-label">Password</label><input class="lp-input" name="password" type="password" required placeholder="Minimum 8 characters" id="lpRegPass"/></div>
          <div class="lp-form-actions" style="flex-direction:column;gap:10px;">
            <button type="submit" class="lp-btn lp-btn-primary" style="width:100%;justify-content:center;" id="lpRegBtn">Create Account</button>
          </div>
          <div id="lpRegError" class="lp-form-error"></div>
          <div style="text-align:center;margin-top:14px;font-size:13px;">
            <a href="#" onclick="showLoginModal();event.preventDefault()" style="color:var(--primary);font-weight:600;">Already have an account? Sign In</a>
          </div>
        </form>
      </div>
    </div>
  </div>`;
}

async function handleLpRegister(e){
  e.preventDefault();
  const btn = document.getElementById('lpRegBtn');
  const errEl = document.getElementById('lpRegError');
  btn.disabled = true; btn.textContent = 'Creating account…'; errEl.textContent = '';
  try{
    const name = document.getElementById('lpRegName').value.trim();
    const email = document.getElementById('lpRegEmail').value.trim();
    const password = document.getElementById('lpRegPass').value;
    const data = await api('/api/auth/register', {method:'POST', body:{name, email, password, role:'employee', dept:'General'}, auth:false});
    setToken(data.access_token);
    state.user = data.user;
    state.role = data.user.role;
    document.querySelector('.lp-modal-overlay')?.remove();
    toast('Account created. Welcome to MuraAI Refer.', 'success');
    await loadAllData();
    render();
    startPolling();
  }catch(err){
    errEl.textContent = err.message || 'Unable to create account. Please try again.';
    btn.disabled = false; btn.textContent = 'Create Account';
  }
}

/* ================================ Scroll Effects ================================ */
function initLandingScroll(){
  let ticking = false;
  window.addEventListener('scroll', ()=>{
    if(!ticking){
      requestAnimationFrame(()=>{
        const header = document.getElementById('lpHeader');
        if(header) header.classList.toggle('scrolled', window.scrollY > 50);

        document.querySelectorAll('.lp-nav-link').forEach(link=>{
          const section = link.dataset.section;
          if(!section) return;
          const el = document.getElementById(section);
          if(!el) return;
          const rect = el.getBoundingClientRect();
          link.classList.toggle('active', rect.top <= 200 && rect.bottom >= 200);
        });

        animateCounters();

        ticking = false;
      });
      ticking = true;
    }
  });

  /* Scroll-reveal with IntersectionObserver */
  const revealObserver = new IntersectionObserver((entries)=>{
    entries.forEach(entry=>{
      if(entry.isIntersecting){
        entry.target.classList.add('lp-visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.08, rootMargin: '0px 0px -40px 0px' });

  setTimeout(()=>{
    document.querySelectorAll('.lp-section-header, .lp-step-card, .lp-feature-card, .lp-faq-item, .lp-job-card, .lp-newsletter-card, .lp-filter-chip').forEach((el, i)=>{
      el.classList.add('lp-reveal');
      el.style.transitionDelay = `${Math.min(i % 6 * 80, 400)}ms`;
      revealObserver.observe(el);
    });
    document.querySelectorAll('.lp-feature-card, .lp-step-card').forEach(card=>{
      card.addEventListener('mousemove', e=>{
        const rect = card.getBoundingClientRect();
        card.style.setProperty('--mx', ((e.clientX - rect.left) / rect.width * 100) + '%');
        card.style.setProperty('--my', ((e.clientY - rect.top) / rect.height * 100) + '%');
      });
    });
  }, 100);
}

function animateCounters(){
  document.querySelectorAll('.lp-stat-num[data-count]').forEach(el=>{
    if(el.dataset.animated) return;
    const rect = el.getBoundingClientRect();
    if(rect.top > window.innerHeight || rect.bottom < 0) return;
    el.dataset.animated = '1';
    const target = parseInt(el.dataset.count);
    const prefix = el.dataset.prefix || '';
    const suffix = el.dataset.suffix || '';
    const duration = 2000;
    const startTime = performance.now();
    function step(now){
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.floor(eased * target);
      el.textContent = prefix + current.toLocaleString('en-IN') + suffix;
      if(progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });
}

/* ================================ Smooth Scroll ================================ */
function initLandingAnchors(){
  document.addEventListener('click', e=>{
    const a = e.target.closest('a[href^="#"]');
    if(!a) return;
    const id = a.getAttribute('href').replace('#','');
    const el = document.getElementById(id);
    if(el){
      e.preventDefault();
      el.scrollIntoView({behavior:'smooth', block:'start'});
      const nav = document.getElementById('lpNav');
      if(nav) nav.classList.remove('open');
      const ham = document.getElementById('lpHamburger');
      if(ham) ham.classList.remove('active');
    }
  });
}
