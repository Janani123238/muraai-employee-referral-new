/* ------------------------------- Employee: Refer Candidate ------------------------------- */
function referCandidateView(){
  const pre = state.lastAnalyzedResume;
  const pendingJob = state.referPendingJob;
  state.referPendingJob = null;
  if(state.jobs.length===0){
    return `<div class="glass" style="padding:40px;text-align:center;">
      <div style="font-size:38px;margin-bottom:10px;"></div>
      <h3 style="margin:0 0 6px;">No open roles available yet</h3>
      <p style="color:var(--ink-soft);margin:0;">${isHrRole(state.role) ? 'Post a job first from Manage Jobs.' : 'Check back once HR posts an open role.'}</p>
    </div>`;
  }
  const escOpt = esc;
  const jobOpts = state.jobs.map(j=>{
    const sel = (pre?.bestJobId===j.id || pendingJob===j.id) ? 'selected' : '';
    return `<option value="${escOpt(j.id)}" ${sel}>${escOpt(j.title)}</option>`;
  }).join('');

  const defaultJob = state.jobs.find(j=> j.id===(pre?.bestJobId||pendingJob)) || state.jobs[0];
  const jobPick = defaultJob ? `<div class="ref-job-meta">${escOpt(defaultJob.dept||'')}${defaultJob.location?` · ${escOpt(defaultJob.location)}`:''}</div>` : '';

  const helper = (name, ph, required)=> escOpt(pre?.parsed?.[name]||'');

  return `
  <div class="refer-root fade-up">
    <div class="refer-hero">
      <div>
        <h1 class="display refer-hero-title">Refer a Candidate</h1>
        <p class="refer-hero-sub">Recommend a candidate for an open role.</p>
      </div>
      <span class="refer-pill">${icon('sparkles',13)} AI-assisted referral</span>
    </div>

    ${state.aiStatus && !state.aiStatus.available ? `
    <div class="ref-ai-banner ref-ai-banner-warn">
      ${icon('alertTriangle',15)} <span><strong>AI is running in fallback mode.</strong> Configure an AI provider (Ollama, OpenAI, Anthropic, Gemini) in Admin → AI Settings for more detailed analysis.</span>
    </div>` : ''}
    ${state.aiStatus && state.aiStatus.available ? `
    <div class="ref-ai-banner ref-ai-banner-ok">
      ${icon('zap',15)} <span>AI-powered: <strong>${escOpt(state.aiStatus.provider)}</strong> (${escOpt(state.aiStatus.model)})</span>
    </div>` : ''}

    <div id="referLayout" class="refer-layout">
      <div class="glass refer-card">
        <div id="duplicateWarning"></div>

        <form id="referForm" class="refer-form" novalidate>

          <section class="ref-section ref-sec-1">
            <div class="ref-sec-head"><div class="ref-sec-num">1</div><div class="ref-sec-title">Resume</div></div>
            <div class="ref-field ref-field-full">
              <input type="file" id="resumeFile" accept=".txt,.pdf,.doc,.docx,.png,.jpg,.jpeg,.webp" class="ref-file-input" hidden/>
              <div id="resumeDropzone" class="ref-dropzone" tabindex="0" role="button" aria-label="Upload candidate resume">
                <div class="ref-dropzone-icon">${icon('fileText',22)}</div>
                <div class="ref-dropzone-title">Upload Resume</div>
                <div class="ref-dropzone-sub">Drag &amp; drop or <span class="ref-muted-link">browse files</span></div>
                <div class="ref-dropzone-types">PDF / DOC / DOCX / TXT</div>
              </div>
              <div id="resumeFileCard" class="ref-file-card" hidden></div>
              <div class="ref-err" data-err-for="resume"></div>
            </div>
          </section>

          <section class="ref-section ref-sec-2">
            <div class="ref-sec-head"><div class="ref-sec-num">2</div><div class="ref-sec-title">Candidate Information</div></div>
            <div class="ref-fields">
              <div class="ref-field ref-field-full">
                <label class="field-label" for="candidateName">Candidate Name <span class="ref-req">*</span></label>
                <div class="ref-field-wrap">
                  <span class="ref-field-ic">${icon('user',15)}</span>
                  <input id="candidateName" class="input" name="candidateName" placeholder="e.g. Suresh Menon" value="${helper('name')}" autocomplete="name"/>
                </div>
                <div class="ref-err" data-err-for="candidateName"></div>
              </div>
              <div class="ref-field">
                <label class="field-label" for="email">Email Address</label>
                <div class="ref-field-wrap">
                  <span class="ref-field-ic">${icon('mail',15)}</span>
                  <input id="email" class="input" name="email" type="email" placeholder="candidate@email.com" value="${helper('email')}" autocomplete="email"/>
                </div>
                <div class="ref-err" data-err-for="email"></div>
              </div>
              <div class="ref-field">
                <label class="field-label" for="phone">Phone Number</label>
                <div class="ref-field-wrap">
                  <span class="ref-field-ic">${icon('phone',15)}</span>
                  <input id="phone" class="input" name="phone" placeholder="+91 90000 00000" value="${helper('phone')}" autocomplete="tel"/>
                </div>
                <div class="ref-err" data-err-for="phone"></div>
              </div>
            </div>
          </section>

          <section class="ref-section ref-sec-3">
            <div class="ref-sec-head"><div class="ref-sec-num">3</div><div class="ref-sec-title">Professional Information</div></div>
            <div class="ref-fields">
              <div class="ref-field">
                <label class="field-label" for="currentCompany">Current Company</label>
                <div class="ref-field-wrap"><span class="ref-field-ic">${icon('building',15)}</span>
                  <input id="currentCompany" class="input" name="currentCompany" placeholder="e.g. Infotech Solutions" value="${helper('currentCompany')}"/>
                </div>
              </div>
              <div class="ref-field">
                <label class="field-label" for="currentDesignation">Current Job Title</label>
                <div class="ref-field-wrap"><span class="ref-field-ic">${icon('briefcase',15)}</span>
                  <input id="currentDesignation" class="input" name="currentDesignation" placeholder="e.g. Senior Developer" value="${helper('currentDesignation')}"/>
                </div>
              </div>
              <div class="ref-field">
                <label class="field-label" for="totalExperience">Years of Experience</label>
                <div class="ref-field-wrap"><span class="ref-field-ic">${icon('clock',15)}</span>
                  <input id="totalExperience" class="input" name="totalExperience" placeholder="e.g. 5 years" value="${helper('totalExperience')}"/>
                </div>
              </div>
              <div class="ref-field">
                <label class="field-label" for="education">Highest Qualification</label>
                <div class="ref-field-wrap"><span class="ref-field-ic">${icon('award',15)}</span>
                  <input id="education" class="input" name="education" placeholder="e.g. B.Tech CSE, IIT" value="${helper('education')}"/>
                </div>
              </div>
            </div>
            <details class="ref-extra" open>
              <summary class="ref-extra-toggle">Additional professional details ${icon('chevronDown',14)}</summary>
              <div class="ref-extra-grid">
                <div class="ref-field">
                  <label class="field-label" for="relevantExperience">Relevant Experience</label>
                  <input id="relevantExperience" class="input" name="relevantExperience" placeholder="e.g. 3 years" value="${helper('relevantExperience')}"/>
                </div>
                <div class="ref-field">
                  <label class="field-label" for="skills">Skills (comma-separated)</label>
                  <input id="skills" class="input" name="skills" placeholder="e.g. Python, React, AWS, Docker" value="${escOpt((pre?.parsed?.skills||[]).join(', '))}"/>
                </div>
                <div class="ref-field">
                  <label class="field-label" for="certifications">Certifications</label>
                  <input id="certifications" class="input" name="certifications" placeholder="e.g. AWS Solutions Architect, PMP" value="${escOpt((pre?.parsed?.certifications||[]).join(', '))}"/>
                </div>
                <div class="ref-field">
                  <label class="field-label" for="projects">Projects</label>
                  <input id="projects" class="input" name="projects" placeholder="e.g. E-commerce platform, Chatbot" value="${escOpt((pre?.parsed?.projects||[]).join(', '))}"/>
                </div>
                <div class="ref-field">
                  <label class="field-label" for="linkedin">LinkedIn</label>
                  <input id="linkedin" class="input" name="linkedin" placeholder="linkedin.com/in/…" value="${helper('linkedin')}"/>
                </div>
                <div class="ref-field">
                  <label class="field-label" for="github">GitHub</label>
                  <input id="github" class="input" name="github" placeholder="github.com/…" value="${helper('github')}"/>
                </div>
                <div class="ref-field">
                  <label class="field-label" for="portfolio">Portfolio URL</label>
                  <input id="portfolio" class="input" name="portfolio" placeholder="e.g., yoursite.com" value=""/>
                </div>
                <div class="ref-field">
                  <label class="field-label" for="location">Preferred Location</label>
                  <input id="location" class="input" name="location" placeholder="e.g. Bengaluru / Remote" value=""/>
                </div>
                <div class="ref-field">
                  <label class="field-label" for="expectedSalary">Expected Salary</label>
                  <input id="expectedSalary" class="input" name="expectedSalary" placeholder="e.g. ₹22 LPA" value=""/>
                </div>
                <div class="ref-field">
                  <label class="field-label" for="noticePeriod">Notice Period</label>
                  <input id="noticePeriod" class="input" name="noticePeriod" placeholder="e.g. 30 days" value=""/>
                </div>
              </div>
            </details>
          </section>

          <section class="ref-section ref-sec-4">
            <div class="ref-sec-head"><div class="ref-sec-num">4</div><div class="ref-sec-title">Referral Information</div></div>
            <div class="ref-fields">
              <div class="ref-field ref-field-full ref-job">
                <label class="field-label" for="refJobSearch">Job Opening <span class="ref-req">*</span></label>
                <div class="ref-job-search" id="refJobSearchWrap">
                  <span class="ref-field-ic">${icon('search',15)}</span>
                  <input id="refJobSearch" class="input" type="text" placeholder="Search jobs" role="combobox" aria-expanded="false" aria-autocomplete="list" autocomplete="off"/>
                  <button type="button" class="ref-job-caret" aria-label="Toggle job list" tabindex="-1">${icon('chevronDown',16)}</button>
                  <div class="ref-job-list" id="refJobList" role="listbox" hidden></div>
                </div>
                <div class="ref-job-selected" id="refJobSelected" aria-live="polite">
                  <div class="ref-job-selected-card">
                    <div class="ref-job-title">${defaultJob? escOpt(defaultJob.title):'Select a job'}</div>
                    ${defaultJob? `<div class="ref-job-meta">${escOpt(defaultJob.dept||'')}${defaultJob.location?` · ${escOpt(defaultJob.location)}`:''}</div>`
                              : `<div class="ref-job-meta">No role selected yet</div>`}
                    ${defaultJob? `<div class="ref-job-tags">${ (defaultJob.skills||[]).slice(0,4).map(s=>`<span class="ref-job-tag">${escOpt(s)}</span>`).join('')}${defaultJob.exp?`<span class="ref-job-tag ref-job-tag-exp">${escOpt(defaultJob.exp)}</span>`:''}</div>`:''}
                  </div>
                </div>
                <select name="jobId" id="refJobSelect" class="ref-job-hidden" required aria-hidden="true">
                  <option value="">Select a job…</option>
                  ${jobOpts}
                </select>
                <div class="ref-err" data-err-for="jobId"></div>
              </div>
              <div class="ref-field">
                <label class="field-label" for="relationship">Referral Relationship</label>
                <select class="input" id="relationship" name="relationship">
                  <option>Ex-colleague</option><option>Friend</option><option>Former colleague</option><option>Former manager</option><option>Family</option><option>Acquaintance</option>
                </select>
              </div>
              <div class="ref-field ref-field-full">
                <label class="field-label" for="referralNote">Reason for Referral</label>
                <textarea id="referralNote" class="input ref-note" name="referralNote" placeholder="Why is this candidate a good fit for this role? (optional)"></textarea>
              </div>
            </div>
          </section>

          <section class="ref-section ref-sec-submit">
            <button type="submit" id="referSubmitBtn" class="btn btn-primary ref-submit">
              <span class="ref-submit-ic">${icon('sparkles',15)}</span><span class="ref-submit-txt">Submit Referral</span>
            </button>
          </section>
        </form>
      </div>

      <div class="refer-sidebar">
    </div>
  </div>`;
}
function skillBubbles(skills){
  return skills.map((s,i)=>`<span class="skill-bubble" style="background:${skillTagColor(i)};animation-delay:${i*0.15}s;">${s}</span>`).join('');
}
function fillFormFromParsed(parsed){
  const form = document.getElementById('referForm');
  if(!form) return;
  if(parsed.name) form.candidateName.value = parsed.name;
  if(parsed.phone) form.phone.value = parsed.phone;
  if(parsed.email) form.email.value = parsed.email;
  if(parsed.currentCompany) form.currentCompany.value = parsed.currentCompany;
  if(parsed.totalExperience) form.totalExperience.value = parsed.totalExperience;
  if(parsed.education) form.education.value = parsed.education;
  if(parsed.skills && parsed.skills.length) form.skills.value = parsed.skills.join(', ');
  if(parsed.certifications && parsed.certifications.length) form.certifications.value = parsed.certifications.join(', ');
  if(parsed.projects && parsed.projects.length) form.projects.value = parsed.projects.join(', ');
  if(parsed.linkedin) form.linkedin.value = parsed.linkedin;
  if(parsed.github) form.github.value = parsed.github;
}

async function runAutofillAnalysis(text){
  const aiPipe = new ReferAutoFillPipeline();
  aiPipe.step('Resume uploaded');
  aiPipe.step('Analyzing resume content…');
  aiPipe.step('Extracting candidate information');

  let parsed;
  try {
    parsed = await aiParseResume(text);
  } catch(e){
    aiPipe.fail(e && e.message ? e.message : 'We could not parse the resume.');
    throw e;
  }

  if(!parsed){
    aiPipe.fail('We could not parse the resume.');
    const errMsg = 'We could not parse the resume.';
    throw new Error(errMsg);
  }

  const prevFileName = state.lastAnalyzedResume?.resumeFileName;
  const prevFileUrl = state.lastAnalyzedResume?.resumeFileUrl;
  state.lastAnalyzedResume = {
    resumeText:text, parsed, bestJobId:null, bestDetail:null,
    summary: '',
    resumeFileName: prevFileName, resumeFileUrl: prevFileUrl,
  };
  aiPipe.step('✓ Candidate details detected');
  aiPipe.finish();

  try{
    const dupCheck = await checkDuplicateReferral({email: parsed.email, phone: parsed.phone, name: parsed.name});
    const dupEl = document.getElementById('duplicateWarning');
    if(dupEl){
      if(dupCheck && dupCheck.duplicate){
        dupEl.innerHTML = `<div class="glass pop-in ref-dup" style="padding:14px 16px;margin-bottom:16px;border:1.5px solid rgba(220,38,38,0.4);display:flex;gap:12px;align-items:center;">
          <div style="color:var(--coral);display:flex;">${icon('alertTriangle',20)}</div>
          <div><div style="font-weight:700;font-size:13px;">Candidate already referred</div>
          <div style="font-size:12px;color:var(--ink-soft);">By ${dupCheck.referredByName||'another employee'} · ${fmtRelative(dupCheck.submittedDate)}</div></div>
        </div>`;
      } else { dupEl.innerHTML=''; }
    }
  }catch(e){ }

  const summaryCard = document.getElementById('aiSummaryCard');
  if(summaryCard && typeof aiSummaryCardHTML === 'function') summaryCard.innerHTML = aiSummaryCardHTML(state.lastAnalyzedResume);

  const form = document.getElementById('referForm');
  if(form){
    const set = (name, val) => {
      if(val === undefined || val === null) val = '';
      val = String(val);
      const el = form.elements[name];
      if(!el) return;
      const current = el.value || '';
      el.value = val;
      if(val && val !== current) ReferAutoFillPipeline.flash(el);
    };
    set('candidateName', parsed.name);
    set('email', parsed.email);
    set('phone', parsed.phone);
    set('currentCompany', parsed.currentCompany);
    set('currentDesignation', parsed.currentDesignation);
    set('totalExperience', parsed.totalExperience || (parsed.totalExperienceYears ? parsed.totalExperienceYears + ' years' : ''));
    set('relevantExperience', parsed.relevantExperience);
    set('education', parsed.education);
    set('skills', (parsed.skills||[]).join(', '));
    set('certifications', (parsed.certifications||[]).join(', '));
    set('projects', (parsed.projects||[]).join(', '));
    set('linkedin', parsed.linkedin);
    set('github', parsed.github);
    ReferAutoFillPipeline.markValid(form);
  }
  const dropzone = document.getElementById('resumeDropzone');
  if(dropzone && !state.lastAnalyzedResume.resumeFileName){
    dropzone.innerHTML = `<strong style="color:var(--ink);">Resume text</strong> attached via autofill`;
  }
  toast('Resume analyzed — form filled by AI', 'success');
}
/* ------------------------------ Refer Auto-Fill Pipeline ------------------------------
   Tiny helper for the AI processing feedback: an inline progress list that appears above
   the form while a resume is being analyzed, plus a spotlight flash on filled fields. */
function ReferAutoFillPipeline(){
  this.host = document.getElementById('referAutoPipe');
  if(!this.host){
    const card = document.getElementById('referForm');
    if(!card) return;
    this.host = document.createElement('div');
    this.host.id = 'referAutoPipe';
    this.host.className = 'ref-auto-pipe';
    this.host.setAttribute('role','status');
    this.host.setAttribute('aria-live','polite');
    this.host.style.display = 'none';
    card.parentNode.insertBefore(this.host, card);
  }
  this.items = [];
  this.el = document.createElement('div');
  this.el.className = 'ref-auto-pipe-box';
}
ReferAutoFillPipeline.flash = function(el){
  if(!el) return;
  el.classList.remove('ref-field-flash');
  void el.offsetWidth;
  el.classList.add('ref-field-flash');
  setTimeout(()=>{
    const w = el.closest('.ref-field');
    if(w){ w.classList.remove('ref-field-flash'); el.classList.remove('ref-field-flash'); }
  }, 900);
};
ReferAutoFillPipeline.markValid = function(form){
  if(!form) return;
  ['candidateName','email','phone','currentCompany','currentDesignation','totalExperience','education'].forEach(n=>{
    const el = form.elements[n];
    if(el && el.value){ el.closest('.ref-field')?.classList.add('ref-valid'); }
  });
};
ReferAutoFillPipeline.prototype.step = function(msg){
  if(!this.host) return;
  const item = document.createElement('div');
  item.className = 'ref-auto-step';
  item.innerHTML = `<span class="ref-auto-step-ic">${icon('loader',14)}</span><span>${esc(msg)}</span>`;
  this.host.style.display = 'block';
  this.host.appendChild(this.el);
  this.el.appendChild(item);
  this.items.push(item);
  setTimeout(()=> item.classList.add('ref-auto-step-in'), 30);
};
ReferAutoFillPipeline.prototype.fail = function(msg){
  this.finish(true, msg);
};
ReferAutoFillPipeline.prototype.finish = function(failed, msg){
  if(!this.host) return;
  const last = this.items[this.items.length-1];
  if(last){
    last.querySelector('.ref-auto-step-ic').innerHTML = failed ? icon('alertTriangle',14) : icon('check',14);
    last.classList.remove('ref-auto-step-in');
    last.classList.add('ref-auto-step-done','ref-auto-step-'+ (failed?'fail':'ok'));
    if(msg) last.querySelector('span:last-child').textContent = msg;
  }
  if(!failed){
    setTimeout(()=>{
      this.host.style.opacity = '0';
      setTimeout(()=>{ this.host.remove(); }, 400);
    }, 2400);
    this.host.style.transition = 'opacity .4s';
  }
};

/* ------------------------------ Resume dropzone states ------------------------------ */
function setResumeUI(stateKind, payload){
  const dropzone = document.getElementById('resumeDropzone');
  const fileCard = document.getElementById('resumeFileCard');
  const errEl = document.querySelector('.ref-field [data-err-for="resume"]');
  if(!dropzone) return;
  if(stateKind === 'empty'){
    dropzone.hidden = false;
    if(fileCard) fileCard.hidden = true;
    return;
  }
  if(stateKind === 'loading'){
    dropzone.hidden = false;
    dropzone.classList.add('ref-dropzone-busy');
    dropzone.querySelector('.ref-dropzone-icon').innerHTML = icon('loader',22);
    dropzone.querySelector('.ref-dropzone-title').textContent = 'Uploading resume…';
    dropzone.querySelector('.ref-dropzone-sub').textContent = payload && payload.name ? payload.name : '';
    dropzone.querySelector('.ref-dropzone-types').textContent = 'Processing may take a moment…';
    return;
  }
  if(stateKind === 'error'){
    dropzone.hidden = false;
    fileCard && (fileCard.hidden = true);
    dropzone.classList.remove('ref-dropzone-busy');
    dropzone.querySelector('.ref-dropzone-icon').innerHTML = icon('fileText',22);
    dropzone.querySelector('.ref-dropzone-title').textContent = 'Upload Resume';
    dropzone.querySelector('.ref-dropzone-sub').innerHTML = 'Drag &amp; drop or <span class="ref-muted-link">browse files</span>';
    dropzone.querySelector('.ref-dropzone-types').textContent = 'PDF / DOC / DOCX / TXT';
    if(errEl) errEl.textContent = payload && payload.message ? payload.message : 'We could not process that file. Please try again.';
    return;
  }
  /* uploaded */
  dropzone.hidden = true;
  if(!fileCard) return;
  fileCard.hidden = false;
  const name = payload && payload.fileName;
  const size = payload && payload.sizeText;
  fileCard.innerHTML = `
    <div class="ref-file-main">
      <div class="ref-file-ic">${icon('fileText',20)}</div>
      <div class="ref-file-info">
        <div class="ref-file-name">${esc(name||'Resume')}</div>
        <div class="ref-file-meta">${esc(size||'')}</div>
      </div>
      <div class="ref-file-state"><span class="ref-file-state-dot"></span>${icon('check',13)} Resume uploaded</div>
    </div>
    <div class="ref-file-actions">
      <button type="button" class="btn btn-outline ref-small-btn" data-ref-preview>${icon('eye',14)} Preview</button>
      <button type="button" class="btn btn-outline ref-small-btn" data-ref-replace>${icon('refresh',14)} Replace</button>
      <button type="button" class="btn btn-danger-ghost ref-small-btn" data-ref-remove>${icon('trash',14)} Remove</button>
    </div>`;
  const setDropzoneEmpty = ()=>{ setResumeUI('empty'); };
  const prev = fileCard.querySelector('[data-ref-preview]');
  const repl = fileCard.querySelector('[data-ref-replace]');
  const rem = fileCard.querySelector('[data-ref-remove]');
  if(prev && payload.previewUrl){ prev.addEventListener('click', ()=>{ openResumeFile(payload.previewUrl); }); }
  if(repl){ repl.addEventListener('click', ()=>{ const fi = document.getElementById('resumeFile'); if(fi){ fi.value=''; fi.click(); } }); }
  if(rem){ rem.addEventListener('click', ()=>{
      state.lastAnalyzedResume = null;
      const fi = document.getElementById('resumeFile'); if(fi) fi.value='';
      setDropzoneEmpty();
      if(errEl) errEl.textContent='';
    }); }
}

function formatBytes(b){
  if(!b && b!==0) return '';
  if(b < 1024) return b + ' B';
  if(b < 1024*1024) return (b/1024).toFixed(1) + ' KB';
  return (b/(1024*1024)).toFixed(1) + ' MB';
}

/* ------------------------------ Job dropdown search ------------------------------ */
function setUpJobCombo(selectEl, searchInput, listEl, selectedEl){
  const jobs = state.jobs;
  const renderList = (filter)=>{
    const q = (filter||'').toLowerCase().trim();
    const matches = jobs.filter(j=>{
      if(!q) return true;
      return (j.title||'').toLowerCase().includes(q)
        || (j.dept||'').toLowerCase().includes(q)
        || (j.location||'').toLowerCase().includes(q)
        || (j.skills||[]).some(s=>String(s).toLowerCase().includes(q));
    });
    listEl.innerHTML = matches.length ? '' : '<div class="ref-job-empty">No matching roles</div>';
    matches.slice(0,12).forEach(j=>{
      const opt = document.createElement('div');
      opt.className = 'ref-job-opt' + (selectEl.value===j.id ? ' ref-job-opt-on' : '');
      opt.setAttribute('role','option');
      opt.innerHTML = `
        <div class="ref-job-opt-main">
          <div class="ref-job-title">${esc(j.title||'')}</div>
          <div class="ref-job-meta">${esc(j.dept||'')}${j.location?` · ${esc(j.location)}`:''}</div>
        </div>
        ${(j.skills||[]).slice(0,3).length?`<div class="ref-job-meta ref-job-opt-tags">${(j.skills||[]).slice(0,3).map(s=>`<span class="ref-job-tag">${esc(s)}</span>`).join('')}</div>`:''}`;
      opt.addEventListener('mousedown', (e2)=>{
        e2.preventDefault();
        pickJob(j);
      });
      listEl.appendChild(opt);
    });
  };
  const pickJob = (j)=>{
    selectEl.value = j.id;
    searchInput.value = j.title;
    renderSelected(j);
    listEl.hidden = true;
    searchInput.setAttribute('aria-expanded','false');
    searchInput.classList.remove('ref-open');
  };
  const renderSelected = (j)=>{
    if(!selectedEl || !j) return;
    selectedEl.innerHTML = `
      <div class="ref-job-selected-card">
        <div class="ref-job-title">${esc(j.title||'')}</div>
        <div class="ref-job-meta">${esc(j.dept||'')}${j.location?` · ${esc(j.location)}`:''}</div>
        ${(j.skills||[]).slice(0,4).length?`<div class="ref-job-tags">${(j.skills||[]).slice(0,4).map(s=>`<span class="ref-job-tag">${esc(s)}</span>`).join('')}${j.exp?`<span class="ref-job-tag ref-job-tag-exp">${esc(j.exp)}</span>`:''}</div>`:''}
      </div>`;
  };
  const open = ()=>{
    listEl.hidden = false;
    searchInput.setAttribute('aria-expanded','true');
    searchInput.classList.add('ref-open');
    renderList(searchInput.value);
    listEl.style.maxHeight = '280px';
  };
  const close = ()=>{
    if(!searchInput.value && selectEl.value){
      const cur = jobs.find(j=>j.id===selectEl.value);
      if(cur) searchInput.value = cur.title;
    }
    listEl.hidden = true;
    searchInput.setAttribute('aria-expanded','false');
    searchInput.classList.remove('ref-open');
  };
  searchInput.addEventListener('focus', open);
  searchInput.addEventListener('input', ()=>{ renderList(searchInput.value); listEl.hidden=false; searchInput.classList.add('ref-open'); });
  searchInput.addEventListener('click', (e2)=>{ e2.stopPropagation(); open(); });
  searchInput.addEventListener('keydown', (e2)=>{
    if(e2.key==='Escape') close();
    if(e2.key==='Enter'){ e2.preventDefault(); const first = listEl.querySelector('.ref-job-opt'); if(first) first.dispatchEvent(new MouseEvent('mousedown',{bubbles:true})); }
  });
  document.addEventListener('click', (e2)=>{
    const wrap = searchInput.closest('.ref-job-search');
    if(wrap && !wrap.contains(e2.target)) close();
  });
  searchInput.closest('.ref-job-search')?.querySelector('.ref-job-caret')?.addEventListener('click', (e2)=>{
    e2.stopPropagation();
    listEl.hidden ? open() : close();
  });
  if(selectEl.value){
    const cur = jobs.find(j=>j.id===selectEl.value) || jobs[0];
    if(cur){ searchInput.value = cur.title; renderSelected(cur); }
  }
}

/* ------------------------------ Form setup / submit ------------------------------ */
let __referBusy = false;
function setUpReferForm(form){
  /* job dropdown */
  const jobSelect = document.getElementById('refJobSelect');
  const jobSearch = document.getElementById('refJobSearch');
  const jobList = document.getElementById('refJobList');
  const jobSelected = document.getElementById('refJobSelected');
  if(jobSelect && jobSearch && jobList){ setUpJobCombo(jobSelect, jobSearch, jobList, jobSelected); }

  /* focus / validation micro-interactions */
  const errEls = {
    candidateName: document.querySelector('[data-err-for="candidateName"]'),
    email: document.querySelector('[data-err-for="email"]'),
    phone: document.querySelector('[data-err-for="phone"]'),
    jobId: document.querySelector('[data-err-for="jobId"]'),
    resume: document.querySelector('[data-err-for="resume"]'),
  };
  const fieldWraps = Array.prototype.slice.call(form.querySelectorAll('.ref-field-wrap'));
  fieldWraps.forEach(w=>{
    const inp = w.querySelector('input, select');
    if(!inp) return;
    inp.addEventListener('focus', ()=>{ w.classList.add('ref-focus'); });
    inp.addEventListener('blur', ()=>{ w.classList.remove('ref-focus'); });
  });
  form.querySelectorAll('.ref-field input, .ref-field select, .ref-field textarea').forEach(inp=>{
    inp.addEventListener('blur', ()=>{ validateField(form, inp, errEls); });
  });

  /* resume dropzone */
  const dropzone = document.getElementById('resumeDropzone');
  const fileInput = document.getElementById('resumeFile');
  if(dropzone){
    dropzone.addEventListener('click', ()=> fileInput.click());
    dropzone.addEventListener('keydown', (e)=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); fileInput.click(); } });
    ['dragover','dragenter'].forEach(ev=> dropzone.addEventListener(ev,(e)=>{ e.preventDefault(); dropzone.classList.add('ref-dropzone-drag'); }));
    ['dragleave','drop'].forEach(ev=> dropzone.addEventListener(ev,(e)=>{ e.preventDefault(); dropzone.classList.remove('ref-dropzone-drag'); }));
    dropzone.addEventListener('drop', (e)=>{
      const f = e.dataTransfer.files[0];
      if(f) handleResumeFile(f, errEls);
    });
  }
  if(fileInput) fileInput.addEventListener('change', async ()=>{
    const f = fileInput.files[0];
    if(f) await handleResumeFile(f, errEls);
  });

  /* submit */
  form.addEventListener('submit', (e)=> handleReferSubmit(form, e, errEls));
}

async function handleResumeFile(f, errEls){
  if(!f) return;
  setResumeUI('loading', { name: f.name });
  if(f.name.toLowerCase().endsWith('.txt')) {
    const reader = new FileReader();
    reader.onerror = ()=>{ setResumeUI('error', {message:'We could not read the file. Please try again.'}); toast('We could not read the file. Please try again.','error'); };
    reader.onload = ()=>{
      const text = reader.result;
      state.lastAnalyzedResume = { ...(state.lastAnalyzedResume||{parsed:{}}), resumeText:text, resumeFileName:f.name, resumeFileUrl:'' };
      setResumeUI('uploaded', { fileName:f.name, sizeText:formatBytes(f.size) });
      if(errEls && errEls.resume) errEls.resume.textContent='';
      toast('Resume file loaded', 'success');
      runAutofillAnalysis(text).catch(e=> toast(e.message||'AI analysis incomplete','amber'));
    };
    reader.readAsText(f);
    return;
  }
  try {
    const result = await uploadResumeFile(f);
    state.lastAnalyzedResume = { ...(state.lastAnalyzedResume||{parsed:{}}), resumeText: result.extractedText, resumeFileName: result.fileName, resumeFileUrl: result.fileUrl };
    setResumeUI('uploaded', { fileName: result.fileName, sizeText: formatBytes(f.size), previewUrl: result.fileUrl });
    if(errEls && errEls.resume) errEls.resume.textContent='';
    toast('Resume uploaded and text extracted', 'success');
    runAutofillAnalysis(result.extractedText).catch(e=> toast(e.message||'AI analysis incomplete','amber'));
  } catch(e) {
    setResumeUI('error', { message: e.message||'We could not process that file. Please try again.' });
    toast(e.message || 'We could not process that file. Please try again.', 'error');
  }
}

function validateField(form, inp, errEls){
  if(__referBusy) return;
  const name = inp.name;
  const wrap = inp.closest('.ref-field');
  const errEl = errEls && errEls[name];
  const val = inp.value ? String(inp.value).trim() : '';
  const showErr = (msg)=>{
    if(wrap){ wrap.classList.add('ref-invalid'); wrap.classList.remove('ref-valid'); }
    if(errEl) errEl.textContent = msg;
  };
  const ok = ()=>{
    if(wrap){ wrap.classList.remove('ref-invalid'); if(val) wrap.classList.add('ref-valid'); else wrap.classList.remove('ref-valid'); }
    if(errEl) errEl.textContent='';
  };
  if(name==='candidateName'){
    if(!val){ showErr('Please enter the candidate\'s full name.'); return; }
    ok(); return;
  }
  if(name==='email'){
    if(val && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)){ showErr('Please enter a valid email address.'); return; }
    ok(); return;
  }
  if(name==='phone'){
    if(val && val.replace(/[^+\d]/g,'').length < 8){ showErr('Please enter a valid phone number.'); return; }
    ok(); return;
  }
  if(name==='jobId'){
    if(!val){ showErr('Please select a job opening.'); return; }
    ok(); return;
  }
  ok();
}

function validateReferForm(form, errEls){
  const requiredNames = ['candidateName','jobId'];
  let firstBad = null;
  requiredNames.forEach(n=>{
    const el = form.elements[n];
    if(!el || !String(el.value||'').trim()){
      validateField(form, el, errEls);
      if(!firstBad) firstBad = el;
    } else validateField(form, el, errEls);
  });
  return firstBad;
}

function submitButtonState(btn, kind){
  if(!btn) return;
  const ic = btn.querySelector('.ref-submit-ic');
  const txt = btn.querySelector('.ref-submit-txt');
  const set = (iconName, label, cls)=>{
    btn.disabled = cls==='loading' || cls==='success';
    btn.classList.remove('ref-submit-loading','ref-submit-success');
    if(cls) btn.classList.add('ref-submit-'+cls);
    if(ic) ic.innerHTML = icon(iconName, 15);
    if(txt) txt.textContent = label;
  };
  if(kind==='loading') set('loader','Submitting Referral…','loading');
  else if(kind==='success') set('check','Referral Submitted','success');
  else set('sparkles','Submit Referral','');
}

async function handleReferSubmit(form, e, errEls){
  e.preventDefault();
  if(__referBusy) return;
  const submitBtn = document.getElementById('referSubmitBtn');
  const fd = new FormData(form);
  const resumeText = (state.lastAnalyzedResume && state.lastAnalyzedResume.resumeText) || 'No resume text provided.';
  const resumeFileUrl = (state.lastAnalyzedResume && state.lastAnalyzedResume.resumeFileUrl) || '';
  const resumeFileName = (state.lastAnalyzedResume && state.lastAnalyzedResume.resumeFileName) || '';

  const firstBad = validateReferForm(form, errEls);
  if(firstBad){
    firstBad.scrollIntoView({block:'center', behavior:'smooth'});
    toast('Please review the highlighted fields','amber');
    return;
  }

  __referBusy = true;
  submitButtonState(submitBtn, 'loading');

  const parseList = (v) => v ? v.split(',').map(s=>s.trim()).filter(Boolean) : [];
  const fields = {
    candidateName: fd.get('candidateName'), phone: fd.get('phone'), email: fd.get('email'),
    resumeText, linkedin: fd.get('linkedin'), github: fd.get('github'), portfolio: fd.get('portfolio'),
    location: fd.get('location'), expectedSalary: fd.get('expectedSalary'), noticePeriod: fd.get('noticePeriod'),
    currentCompany: fd.get('currentCompany'), currentDesignation: fd.get('currentDesignation'),
    totalExperience: fd.get('totalExperience'), relevantExperience: fd.get('relevantExperience'),
    skills: parseList(fd.get('skills')), education: fd.get('education'),
    certifications: parseList(fd.get('certifications')), projects: parseList(fd.get('projects')),
    relationship: fd.get('relationship'), jobId: fd.get('jobId'),
    resumeFileUrl, resumeFileName,
  };
  try {
    const referral = await submitReferralToBackend(fields);
    state.referrals.unshift(referral);
    toast('Referral for ' + referral.candidateName + ' submitted successfully', 'success');
    submitButtonState(submitBtn, 'success');
    showReferSuccess(referral);
    state.lastAnalyzedResume = null;
    if(window.ReferralTreeAnimation){
      try{ await ReferralTreeAnimation.onSubmitted(); }catch(ee){}
    }
    await new Promise(r=>setTimeout(r, 1900));
    nav('tracking');
  } catch(err) {
    __referBusy = false;
    toast('We couldn\'t submit the referral. ' + err.message, 'error');
    submitButtonState(submitBtn, 'idle');
  }
}

function showReferSuccess(referral){
  const layout = document.getElementById('referLayout');
  if(!layout) return;
  let overlay = document.getElementById('refSuccessOverlay');
  if(!overlay){
    overlay = document.createElement('div');
    overlay.id = 'refSuccessOverlay';
    overlay.className = 'ref-success-overlay';
    layout.appendChild(overlay);
  }
  overlay.innerHTML = `
    <div class="ref-success-check">${icon('check',26)}</div>
    <div class="ref-success-title">Referral Submitted</div>
    <div class="ref-success-sub">${esc(referral ? referral.candidateName : '')} — your referral has been submitted for review.</div>
    <div class="ref-success-conn">
      <span class="ref-conn-node">Employee</span>
      <span class="ref-conn-line">${icon('chevronDown',14)}</span>
      <span class="ref-conn-node">Candidate</span>
      <span class="ref-conn-line">${icon('chevronDown',14)}</span>
      <span class="ref-conn-node ref-conn-opp">${icon('briefcase',13)} Job Opportunity</span>
    </div>`;
  overlay.classList.add('ref-success-show');
  requestAnimationFrame(()=> overlay.classList.add('ref-success-in'));
}

function bindReferView() {
  const referSidebar = document.querySelector('.refer-sidebar');
  if(referSidebar && window.ReferralTreeAnimation) ReferralTreeAnimation.mount(referSidebar);

  /* ---------- Section stagger on load ---------- */
  const sections = Array.prototype.slice.call(document.querySelectorAll('.ref-section'));
  sections.forEach((s,i)=>{ s.style.transitionDelay = (0.05*i)+'s'; s.classList.add('ref-section-show'); });

  /* ---------- Form micro-interactions, dropdown, resume, submit ---------- */
  const form = document.getElementById('referForm');
  if(form) setUpReferForm(form);
}
