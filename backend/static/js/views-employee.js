/* ------------------------------- Employee: Open Positions ------------------------------- */
function openPositionsView(){
  if(state.jobs.length===0){
    return `<div class="fade-up">
      <h1 class="display" style="font-size:24px;margin:0 0 4px;">Open Positions</h1>
      <div class="glass" style="padding:40px;text-align:center;margin-top:18px;">
        <h3 style="margin:0 0 6px;">No open positions right now</h3>
        <p style="color:var(--text-secondary);margin:0;">New roles are posted regularly — check back soon.</p>
      </div>
    </div>`;
  }
  return `
  <div class="fade-up">
    <h1 class="display" style="font-size:24px;margin:0 0 4px;">Open Positions</h1>
    <p style="color:var(--ink-soft);font-size:13.5px;margin:0 0 20px;">${state.jobs.length} roles hiring now across MuraAI.</p>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;">
      ${state.jobs.map(j=>{
        const refCount = state.referrals.filter(r=>r.jobId===j.id).length;
        return `
      <div class="glass fade-up" style="padding:20px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
          <div style="font-size:11px;font-weight:700;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.08em;">${j.dept}</div>
        </div>
        <h3 style="font-size:16px;font-weight:700;margin:0 0 6px;">${j.title}</h3>
        <div style="font-size:12.5px;color:var(--text-secondary);margin-bottom:14px;">${j.exp} · ${j.location} · ${j.type||'Full-time'}</div>
        <div style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;padding:12px 0;border-top:1px solid var(--border);border-bottom:1px solid var(--border);margin-bottom:12px;">
          <div><div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:2px;">Salary</div><div style="font-size:13px;font-weight:600;color:var(--text-primary);">${j.salary}</div></div>
          <div><div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:2px;">Bonus</div><div style="font-size:13px;font-weight:700;color:var(--teal);">₹${(j.bonus||0).toLocaleString('en-IN')}</div></div>
          <div><div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:2px;">Referrals</div><div style="font-size:13px;font-weight:600;color:var(--text-primary);">${refCount}</div></div>
        </div>
        <div style="margin-bottom:14px;">${j.skills.slice(0,4).map((s,k)=>`<span class="skill-bubble" style="background:${skillTagColor(k)};animation:none;">${s}</span>`).join('')}</div>
        <button class="btn btn-primary" style="width:100%;" data-apply-job="${j.id}">Refer a Candidate</button>
      </div>`}).join('')}
    </div>
  </div>`;
}
function bindOpenPositions(){
  document.querySelectorAll('[data-apply-job]').forEach(el=>{
    el.addEventListener('click', ()=>{
      if(!state.lastAnalyzedResume) state.lastAnalyzedResume = {resumeText:'', parsed:{}, bestJobId:el.dataset.applyJob};
      else state.lastAnalyzedResume.bestJobId = el.dataset.applyJob;
      nav('refer');
    });
  });
}

/* ------------------------------- Employee: My Referrals / Tracking ------------------------------- */
function pipelineHTML(status){
  const idx = status==='Rejected' ? -1 : PIPELINE_STAGES.indexOf(status);
  return `<div style="overflow-x:auto;padding-bottom:4px;"><div style="display:flex;margin:14px 0 4px;min-width:520px;">
    ${PIPELINE_STAGES.map((s,i)=>{
      let cls = 'pipeline-dot'; let lineCls='pipeline-line';
      if(status==='Rejected' && i===0){ cls+=' rejected'; }
      else if(i < idx) { cls+=' done'; lineCls+=' done'; }
      else if(i===idx){ cls+=' current'; if(i>0) {} }
      if(i<idx) lineCls+=' done';
      return `<div class="pipeline-step">${i>0?`<div class="${lineCls}"></div>`:''}<div class="${cls}">${i<idx||status==='Joined'&&i<=idx?'✓':i+1}</div>
        <div style="font-size:10.5px;text-align:center;margin-top:6px;color:var(--ink-soft);max-width:72px;">${s}</div></div>`;
    }).join('')}
  </div></div>`;
}
function myReferralsView(){
  const mine = state.referrals.filter(r=>r.referredBy===state.user.employeeId);
  if(mine.length===0) return `<div class="glass" style="padding:40px;text-align:center;"><h3 style="margin:0 0 6px;">No referrals yet</h3><p style="color:var(--text-secondary);margin:0 0 14px;">Refer your first candidate to see it tracked here.</p><button class="btn btn-primary" data-nav="refer">Refer a Candidate</button></div>`;
  return `
  <div class="fade-up">
    <h1 class="display" style="font-size:24px;margin:0 0 18px;">My Referrals</h1>
    <div style="display:flex;flex-direction:column;gap:16px;">
      ${mine.map(r=>{
        const job = jobById(r.jobId);
        return `<div class="glass" style="padding:22px;">
          <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:10px;">
            <div style="display:flex;gap:12px;align-items:center;">
              <div style="width:42px;height:42px;border-radius:50%;background:var(--navy);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;">${initials(r.candidateName)}</div>
              <div>
                <div style="font-weight:700;font-size:15px;">${r.candidateName}</div>
                <div style="font-size:12px;color:var(--ink-soft);">${job?job.title:'—'} · Submitted ${fmtRelative(r.submittedDate)}</div>
              </div>
            </div>
            <div class="chip" style="background:${statusColor(r.status)}22;color:${statusColor(r.status)};">${r.status}</div>
          </div>
          ${pipelineHTML(r.status)}
          <div style="display:flex;gap:14px;margin-top:14px;flex-wrap:wrap;align-items:center;">
            <div style="flex:1;min-width:220px;font-size:12.5px;color:var(--ink-soft);">${r.aiSummary||'AI candidate summary not available.'}</div>
            <button class="btn btn-outline" data-view-referral="${r.id}">View Details</button>
          </div>
        </div>`;
      }).join('')}
    </div>
  </div>`;
}
function referralDetailModal(r){
  const job = jobById(r.jobId);
  return `
  <div class="modal-overlay" id="refModalOverlay">
    <div class="glass-strong pop-in" style="max-width:560px;width:100%;padding:28px;max-height:85vh;overflow-y:auto;">
      <div style="display:flex;justify-content:space-between;align-items:start;">
        <div>
          <h2 class="display" style="margin:0 0 2px;font-size:19px;">${r.candidateName}</h2>
          <div style="font-size:12.5px;color:var(--ink-soft);">${job?job.title:'—'} · Applying via ${employeeById(r.referredBy)?.name||'referral'}</div>
        </div>
        <button class="btn btn-ghost" id="closeRefModal" style="padding:4px 8px;">${icon('x',16)}</button>
      </div>
      <div class="chip" style="background:${statusColor(r.status)}22;color:${statusColor(r.status)};margin:12px 0;">${r.status}</div>
      ${pipelineHTML(r.status)}
      <div style="margin:18px 0;">
        <div style="flex:1;">
          <div style="font-size:13px;font-weight:700;margin-bottom:4px;">AI Candidate Summary</div>
          <div style="font-size:12.5px;color:var(--ink-soft);">${r.aiSummary||'—'}</div>
        </div>
      </div>
      ${r.resumeFileUrl ? `<div style="margin-bottom:6px;font-size:13px;font-weight:700;">Resume</div><div style="margin-bottom:14px;"><button type="button" class="btn btn-outline" style="font-size:12px;padding:6px 12px;" onclick="openResumeFile('${r.resumeFileUrl}')">${icon('eye',14)} View Resume</button></div>` : ''}
      <div style="margin-bottom:6px;font-size:13px;font-weight:700;">Skills</div>
      <div style="margin-bottom:14px;">${skillBubbles(r.tags&&r.tags.length?r.tags:['—'])}</div>
      <div style="display:flex;gap:10px;">
        <button class="btn btn-outline" id="genEmailBtn" style="flex:1;">Generate Referral Email</button>
        ${r.status==='Applied'||r.status==='Submitted' ? `<button class="btn btn-ghost" id="withdrawRefBtn" style="color:var(--coral);border:1px solid rgba(220,38,38,0.3);flex:1;">Withdraw Referral</button>` : ''}
      </div>
      <div id="genEmailResult" style="margin-top:12px;"></div>
      <button class="btn btn-primary" id="sendMailBtn" style="display:none;margin-top:12px;width:100%;">${icon('mail',14)}&nbsp; Send Email</button>
    </div>
  </div>`;
}
/* Compose & send the generated referral mail */
function parseReferralEmail(email){
  const text = (email||'').trim();
  let subject='', body=text;
  const m = text.match(/^\s*Subject\s*:\s*(.+)$/m);
  if(m){ subject = m[1].trim(); body = text.slice(text.indexOf(m[0]) + m[0].length).replace(/^\s*\n+\s*/,''); }
  return { subject, body };
}
function openReferralMailComposer(r, generatedMail){
  const { subject, body } = parseReferralEmail(generatedMail);
  const hasResume = !!(r.resumeFileUrl);
  const overlay = document.createElement('div');
  overlay.innerHTML = `
  <div class="modal-overlay" id="mailComposeOverlay">
    <div class="glass-strong pop-in" style="max-width:640px;width:100%;padding:26px;max-height:88vh;overflow-y:auto;">
      <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:14px;">
        <div>
          <h2 class="display" style="margin:0 0 2px;font-size:19px;">Send Referral Email</h2>
          <div style="font-size:12.5px;color:var(--ink-soft);">${esc(r.candidateName)} · ${esc(r.email||'')}</div>
        </div>
        <button class="btn btn-ghost" id="mailComposeCancel" style="padding:4px 8px;">${icon('x',16)}</button>
      </div>
      <div style="display:flex;flex-direction:column;gap:10px;">
        <div>
          <div style="font-size:12.5px;font-weight:700;margin-bottom:4px;">From <span style="color:var(--coral);font-weight:400;">*</span></div>
          <input id="mailFrom" class="input" style="width:100%;" value="${esc(state.user?.email||'')}" readonly placeholder="Loading company mailbox…">
        </div>
        <div>
          <div style="font-size:12.5px;font-weight:700;margin-bottom:4px;">To <span style="color:var(--coral);font-weight:400;">*</span></div>
          <input id="mailTo" class="input" style="width:100%;" placeholder="recipient@company.com (comma-separated for multiple)">
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <div>
            <div style="font-size:12.5px;font-weight:700;margin-bottom:4px;">CC</div>
            <input id="mailCc" class="input" style="width:100%;min-width:0;box-sizing:border-box;" placeholder="cc@company.com">
          </div>
          <div>
            <div style="font-size:12.5px;font-weight:700;margin-bottom:4px;">BCC</div>
            <input id="mailBcc" class="input" style="width:100%;min-width:0;box-sizing:border-box;" placeholder="bcc@company.com">
          </div>
        </div>
        <div>
          <div style="font-size:12.5px;font-weight:700;margin-bottom:4px;">Subject <span style="color:var(--coral);font-weight:400;">*</span></div>
          <input id="mailSubject" class="input" style="width:100%;" value="${esc(subject)}">
        </div>
        <div>
          <div style="font-size:12.5px;font-weight:700;margin-bottom:4px;">Body</div>
          <textarea id="mailBody" class="input" style="width:100%;min-height:160px;resize:vertical;white-space:pre-wrap;">${esc(body)}</textarea>
        </div>
        ${hasResume?`<label style="display:flex;align-items:center;gap:8px;font-size:12.5px;cursor:pointer;padding:8px 10px;background:var(--bg);border:1px solid var(--border);border-radius:10px;">
          <input type="checkbox" id="mailAttachResume" checked style="accent-color:var(--primary);"> ${icon('paperclip',13)} Attach resume ${esc(r.resumeFileName||'')}</label>`:''}
        <div id="mailComposeNote" style="display:none;font-size:12px;color:var(--coral);"></div>
        <div style="display:flex;gap:10px;margin-top:6px;">
          <button class="btn btn-primary" id="mailSendBtn" style="flex:1;">${icon('send',14)}&nbsp; Send Email</button>
          <button class="btn btn-outline" id="mailComposeCancelBtn" style="flex:1;">Cancel</button>
        </div>
      </div>
    </div>
  </div>`;
  document.body.appendChild(overlay);
  const fromInput = document.getElementById('mailFrom');
  const toInput = document.getElementById('mailTo');
  const ccInput = document.getElementById('mailCc');
  const bccInput = document.getElementById('mailBcc');
  const subjectInput = document.getElementById('mailSubject');
  const bodyInput = document.getElementById('mailBody');
  const attachCheck = document.getElementById('mailAttachResume');
  const note = document.getElementById('mailComposeNote');
  const sendBtn = document.getElementById('mailSendBtn');
  const close = ()=> overlay.remove();
  document.getElementById('mailComposeOverlay').addEventListener('click', (e)=>{ if(e.target.id==='mailComposeOverlay') close(); });
  document.getElementById('mailComposeCancel').addEventListener('click', close);
  document.getElementById('mailComposeCancelBtn').addEventListener('click', close);
  api('/api/emails/sender').then(res=>{
    if(res.from){
      fromInput.value = res.from;
      note.style.display='none';
      sendBtn.disabled = false;
    }else{
      fromInput.value = '';
      note.style.display='';
      note.textContent = res.message || 'No sending mailbox is configured.';
      sendBtn.disabled = true;
    }
  }).catch(()=>{
    fromInput.value = '';
    note.style.display='';
    note.textContent = 'We couldn\u2019t load the sending mailbox.';
    sendBtn.disabled = true;
  });
  const parseEmails = (v)=> String(v||'').split(',').map(s=>s.trim()).filter(Boolean);
  const validEmail = (s)=>/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(s);
  sendBtn.addEventListener('click', async ()=>{
    const to = parseEmails(toInput.value);
    const cc = parseEmails(ccInput.value);
    const bcc = parseEmails(bccInput.value);
    const subject = subjectInput.value.trim();
    if(!fromInput.value.trim()){ toast('No sending mailbox is configured. Set GRAPH_SENDER_EMAIL in the backend .env.', 'error'); return; }
    if(!to.length){ toast('Please enter at least one recipient in the To field.', 'error'); return; }
    if(!to.every(validEmail) || !cc.every(validEmail) || !bcc.every(validEmail)){ toast('Please enter valid email addresses.', 'error'); return; }
    if(!subject){ toast('Subject is required.', 'error'); return; }
    if(sendBtn.dataset.busy==='1') return; // prevent duplicate submissions while in flight
    sendBtn.dataset.busy='1'; sendBtn.disabled = true; sendBtn.innerHTML = 'Sending…';
    try{
      const res = await api(`/api/referrals/${r.id}/send-email`, {method:'POST', body:{
        to, cc, bcc, subject, body: bodyInput.value, attachResume: hasResume? (attachCheck ? attachCheck.checked : true) : false,
      }});
      if(res.sent > 0){
        toast('Referral email sent successfully.', 'success');
        close();
      }else{
        toast(res.message || 'Failed to send referral email. Please try again.', 'error');
      }
    }catch(e){
      toast(e.message || 'Failed to send referral email. Please try again.', 'error');
    }finally{
      delete sendBtn.dataset.busy; sendBtn.disabled = false; sendBtn.innerHTML = `${icon('send',14)}&nbsp; Send Email`;
    }
  });
}
function bindTrackingView(){
  document.querySelectorAll('[data-view-referral]').forEach(el=>{
    el.addEventListener('click', ()=>{
      const r = state.referrals.find(x=>x.id===el.dataset.viewReferral);
      const wrap = document.createElement('div'); wrap.innerHTML = referralDetailModal(r);
      document.body.appendChild(wrap);
      document.getElementById('closeRefModal').addEventListener('click', ()=> wrap.remove());
      document.getElementById('refModalOverlay').addEventListener('click', (e)=>{ if(e.target.id==='refModalOverlay') wrap.remove(); });
      const genBtn = document.getElementById('genEmailBtn');
      let generatedMail = '';
      genBtn.addEventListener('click', async ()=>{
        if(genBtn.dataset.busy==='1') return; // prevent double-generation while in flight
        genBtn.dataset.busy='1'; genBtn.disabled = true; genBtn.textContent = 'Generating…';
        try{
          const email = await aiGenerateEmail(r);
          generatedMail = email;
          document.getElementById('genEmailResult').innerHTML = `<div class="glass" style="padding:14px;font-size:12.5px;white-space:pre-wrap;line-height:1.6;">${email}</div>`;
          document.getElementById('sendMailBtn').style.display = '';
        }catch(e){ toast('Could not generate email', 'error'); }
        delete genBtn.dataset.busy; genBtn.disabled = false; genBtn.textContent = 'Generate Referral Email';
      });
      const sendMailBtn = document.getElementById('sendMailBtn');
      sendMailBtn.addEventListener('click', ()=>{
        if(!generatedMail){ toast('Generate the referral email first', 'error'); return; }
        openReferralMailComposer(r, generatedMail);
      });
      const withdrawBtn = document.getElementById('withdrawRefBtn');
      if(withdrawBtn){
        withdrawBtn.addEventListener('click', async ()=>{
          if(!confirm('Withdraw this referral? This cannot be undone.')) return;
          withdrawBtn.disabled = true; withdrawBtn.textContent = 'Withdrawing…';
          try{
            await deleteReferral(r.id);
            state.referrals = state.referrals.filter(x=>x.id!==r.id);
            wrap.remove();
            toast('Referral withdrawn', 'success');
            render();
          }catch(e){ toast(e.message||'Could not withdraw referral', 'error'); withdrawBtn.disabled=false; withdrawBtn.textContent='Withdraw Referral'; }
        });
      }
    });
  });
}

/* ------------------------------- Employee: Leaderboard ------------------------------- */
function leaderboardView(){
  const ranked = state.employees.map(e=>{
    const refs = state.referrals.filter(r=>r.referredBy===e.id);
    const selected = refs.filter(r=>r.status==='Joined').length;
    return {...e, count:refs.length, selected, rate: refs.length? Math.round(selected/refs.length*100):0};
  }).sort((a,b)=>b.count-a.count);
  return `
  <div class="fade-up" style="max-width:720px;">
    <h1 class="display" style="font-size:24px;margin:0 0 18px;">Referral Leaderboard</h1>
    <div style="display:flex;flex-direction:column;gap:12px;">
      ${ranked.map((e,i)=>`
      <div class="glass" style="padding:16px 20px;display:flex;align-items:center;gap:14px;${e.id===state.user.employeeId?'border:1.5px solid rgba(37,99,235,0.5);':''}">
        <div class="mono" style="font-size:15px;font-weight:700;width:34px;text-align:center;color:${i===0?'#D97706':i===1?'#64748B':i===2?'#B45309':'var(--text-secondary)'};">${i+1}</div>
        <div style="width:40px;height:40px;border-radius:50%;background:${e.color};color:#fff;display:flex;align-items:center;justify-content:center;font-weight:700;">${initials(e.name)}</div>
        <div style="flex:1;">
          <div style="font-weight:700;font-size:14.5px;">${e.name} ${e.id===state.user.employeeId?'<span style="color:var(--primary);font-size:11.5px;">(You)</span>':''}</div>
          <div style="font-size:12px;color:var(--ink-soft);">${e.dept} · ${e.selected} selected · ${e.rate}% success rate</div>
        </div>
        <div class="mono" style="font-size:20px;font-weight:700;color:var(--primary);">${e.count}</div>
      </div>`).join('')}
    </div>
  </div>`;
}

/* ------------------------------- Employee: Rewards ------------------------------- */
function rewardsView(){
  const mine = state.referrals.filter(r=>r.referredBy===state.user.employeeId);
  const paid = mine.filter(r=>r.status==='Joined').reduce((s,r)=>s+(jobById(r.jobId)?.bonus||0),0);
  const pending = mine.filter(r=>r.status==='Offer').reduce((s,r)=>s+(jobById(r.jobId)?.bonus||0),0);
  const paidCount = mine.filter(r=>r.status==='Joined').length;
  const pendingCount = mine.filter(r=>r.status==='Offer').length;
  return `
  <div class="fade-up" style="max-width:760px;">
    <h1 class="display" style="font-size:24px;margin:0 0 6px;">Rewards</h1>
    <p style="color:var(--text-secondary);font-size:13px;margin:0 0 22px;">Track referral bonuses paid and pending payout for your referrals.</p>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;">
      <div class="glass" style="padding:22px;border-left:4px solid #059669;">
        <div style="font-size:12px;font-weight:700;color:#059669;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;">Paid Bonus</div>
        <div class="mono" style="font-size:26px;font-weight:700;">₹${paid.toLocaleString('en-IN')}</div>
        <div style="font-size:12px;color:var(--text-secondary);margin-top:4px;">${paidCount} hire${paidCount===1?'':'s'} with bonus paid</div>
      </div>
      <div class="glass" style="padding:22px;border-left:4px solid #D97706;">
        <div style="font-size:12px;font-weight:700;color:#D97706;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;">Pending Bonus</div>
        <div class="mono" style="font-size:26px;font-weight:700;">₹${pending.toLocaleString('en-IN')}</div>
        <div style="font-size:12px;color:var(--text-secondary);margin-top:4px;">${pendingCount} offer${pendingCount===1?'':'s'} awaiting payout</div>
      </div>
    </div>
  </div>`;
}
