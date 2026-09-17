/* =========================================================================
   MuraAI Refer — AI-powered Employee Referral Platform
   Single-page application (vanilla JS). Data persists via
   Persistence is via a real FastAPI + SQL database backend (see /backend).
   ========================================================================= */

/* ------------------------------ API client ------------------------------ */
const API_BASE = window.MURAAI_API_BASE || '';
const TOKEN_KEY = 'muraai_token';

function getToken(){ return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY); }
function setToken(t, remember=true){
  if(remember){ localStorage.setItem(TOKEN_KEY, t); sessionStorage.removeItem(TOKEN_KEY); }
  else { sessionStorage.setItem(TOKEN_KEY, t); localStorage.removeItem(TOKEN_KEY); }
}
function clearToken(){ localStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem(TOKEN_KEY); }

async function api(path, { method='GET', body=null, auth=true } = {}){
  const headers = {'Content-Type':'application/json'};
  if(auth){
    const t = getToken();
    if(t) headers['Authorization'] = 'Bearer '+t;
  }
  const res = await fetch(API_BASE + path, {
    method, headers, body: body ? JSON.stringify(body) : undefined,
  });
  if(res.status === 401){
    clearToken(); state.user=null; state.role=null; render();
    throw new Error('Session expired, please sign in again');
  }
  let data = null;
  try{ data = await res.json(); }catch(e){ /* no body */ }
  if(!res.ok){
    const msg = (data && (data.detail || data.message)) || `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return data;
}

async function apiUpload(path, file){
  const headers = {};
  const t = getToken();
  if(t) headers['Authorization'] = 'Bearer '+t;
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(API_BASE + path, { method:'POST', headers, body: form });
  if(res.status === 401){
    clearToken(); state.user=null; state.role=null; render();
    throw new Error('Session expired, please sign in again');
  }
  let data = null;
  try{ data = await res.json(); }catch(e){ /* no body */ }
  if(!res.ok){
    const msg = (data && (data.detail || data.message)) || `Upload failed (${res.status})`;
    throw new Error(msg);
  }
  return data;
}
async function uploadResumeFile(file){
  return apiUpload('/api/resumes/upload', file);
}

/* Fetch a resume file with the auth token and display it in a new tab.
   The `/api/resumes/file/{id}` endpoint requires a Bearer token, which a plain
   `href` + `target="_blank"` cannot send — so we fetch the bytes ourselves,
   create an object URL and open that. The tab is opened synchronously first so
   popup blockers don't suppress it after the async fetch completes. */
async function openResumeFile(url){
  if(!url) return;
  const win = window.open('', '_blank');
  try{
    const res = await fetch(API_BASE + url, {
      headers: { 'Authorization': 'Bearer ' + (getToken()||'') },
    });
    if(res.status === 401){
      clearToken(); state.user=null; state.role=null; render();
      throw new Error('Session expired, please sign in again');
    }
    if(!res.ok){
      let data=null; try{ data = await res.json(); }catch(e){}
      throw new Error((data && (data.detail || data.message)) || `Could not load resume (${res.status})`);
    }
    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);
    if(win){ win.location.href = objectUrl; }
    else { window.location.href = objectUrl; }
    setTimeout(()=> URL.revokeObjectURL(objectUrl), 60000);
  }catch(e){
    if(win) win.close();
    toast(e.message || 'Could not open resume', 'error');
  }
}

async function apiForm(path, formData){
  const headers = {};
  const t = getToken();
  if(t) headers['Authorization'] = 'Bearer '+t;
  const res = await fetch(API_BASE + path, { method:'POST', headers, body: formData });
  if(res.status === 401){
    clearToken(); state.user=null; state.role=null; render();
    throw new Error('Session expired, please sign in again');
  }
  let data = null;
  try{ data = await res.json(); }catch(e){ /* no body */ }
  if(!res.ok){
    const msg = (data && (data.detail || data.message)) || `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return data;
}

/* ---------------------------- Neural background --------------------------- */
(function neuralBackground(){
  const canvas = document.getElementById('neuralBg');
  const ctx = canvas.getContext('2d');
  let w,h,nodes=[];
  function resize(){ w=canvas.width=window.innerWidth; h=canvas.height=window.innerHeight; }
  window.addEventListener('resize', resize); resize();
  const N = Math.min(60, Math.floor((window.innerWidth*window.innerHeight)/28000));
  for(let i=0;i<N;i++){
    nodes.push({x:Math.random()*w,y:Math.random()*h,vx:(Math.random()-0.5)*0.25,vy:(Math.random()-0.5)*0.25});
  }
  const colors = ['37,99,235','8,145,178','124,58,237'];
  function tick(){
    ctx.clearRect(0,0,w,h);
    for(const n of nodes){
      n.x+=n.vx; n.y+=n.vy;
      if(n.x<0||n.x>w) n.vx*=-1;
      if(n.y<0||n.y>h) n.vy*=-1;
    }
    for(let i=0;i<nodes.length;i++){
      for(let j=i+1;j<nodes.length;j++){
        const a=nodes[i], b=nodes[j];
        const d = Math.hypot(a.x-b.x, a.y-b.y);
        if(d<140){
          ctx.strokeStyle = `rgba(${colors[i%3]},${0.12*(1-d/140)})`;
          ctx.lineWidth=1;
          ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
        }
      }
    }
    for(const n of nodes){
      ctx.fillStyle='rgba(37,99,235,0.25)';
      ctx.beginPath(); ctx.arc(n.x,n.y,2,0,Math.PI*2); ctx.fill();
    }
    requestAnimationFrame(tick);
  }
  tick();
})();

/* ------------------------------- Toasts ------------------------------- */
function toast(msg, type='primary'){
  const colors = {primary:'linear-gradient(135deg,#2563EB,#1D4ED8)', success:'linear-gradient(135deg,#059669,#047857)',
                   error:'linear-gradient(135deg,#DC2626,#B91C1C)', amber:'linear-gradient(135deg,#D97706,#B45309)'};
  const el = document.createElement('div');
  el.className='toast'; el.style.background = colors[type]||colors.primary;
  el.textContent = msg;
  document.getElementById('toastWrap').appendChild(el);
  setTimeout(()=>{ el.style.transition='opacity .4s'; el.style.opacity='0'; setTimeout(()=>el.remove(),400); }, 3400);
}

function uid(prefix){ return prefix+'_'+Math.random().toString(36).slice(2,9); }
function daysAgo(n){ const d=new Date(); d.setDate(d.getDate()-n); return d.toISOString(); }

const PIPELINE_STAGES = ['Applied', 'Resume Screening', 'Under Review', 'Shortlisted', 'Interview Scheduled', 'Interview Completed', 'Selected', 'Rejected', 'Offer Released', 'Joined'];

/* ------------------------------- App State ------------------------------- */
const state = {
  user:null, role:null,
  jobs:[], referrals:[], employees:[], settings:{resumeParsing:true,duplicateDetection:true,fraudDetection:true,chatAssistant:true},
  notifications:[], unreadCount:0, policyContent:'', policyUpdatedAt:null, policyUpdatedBy:'',
  view:'dashboard',
  lastAnalyzedResume:null,
  chat:{open:false, messages:[], listening:false, tts:false, lang:'en-US', sending:false},
  loginTab:'email', loginMode:null,
  aiStatus:null,
  referPendingJob:null, referPendingRef:'',
};

async function loadAllData(){
  const canSeeTeam = state.user && (isHrRole(state.user.role) || state.user.role==='manager');
  const [jobs, employees, referrals, settings, notifications, policy, ai] = await Promise.allSettled([
    api('/api/jobs'),
    api('/api/employees'),
    api(canSeeTeam ? '/api/referrals' : '/api/referrals/mine'),
    api('/api/settings'),
    api('/api/notifications'),
    api('/api/policy'),
    aiStatus(),
  ]);
  state.jobs = (jobs.status==='fulfilled' && Array.isArray(jobs.value)) ? jobs.value : [];
  state.employees = (employees.status==='fulfilled' && Array.isArray(employees.value)) ? employees.value : [];
  state.referrals = (referrals.status==='fulfilled' && Array.isArray(referrals.value)) ? referrals.value : [];
  state.settings = (settings.status==='fulfilled' && settings.value) ? settings.value : state.settings;
  state.notifications = (notifications.status==='fulfilled' && Array.isArray(notifications.value)) ? notifications.value : [];
  state.unreadCount = state.notifications.filter(n=>n&&!n.isRead).length;
  state.policyContent = (policy.status==='fulfilled' && policy.value) ? (policy.value.content || '') : '';
  state.policyUpdatedAt = (policy.status==='fulfilled' && policy.value) ? (policy.value.updatedAt || null) : null;
  state.policyUpdatedBy = (policy.status==='fulfilled' && policy.value) ? (policy.value.updatedBy || '') : '';
  state.aiStatus = (ai.status==='fulfilled' && ai.value) ? ai.value : {available:false, provider:'unknown', message:'Could not check AI status'};
}
async function persist(key){ /* no-op */ }

/* ------------------------------ AI helpers ------------------------------ */
async function aiStatus(){
  return api('/api/ai/status', {method:'GET'});
}
async function aiParseResume(resumeText){
  return api('/api/ai/parse-resume', {method:'POST', body:{resumeText}});
}
async function aiMatchJob(resumeText, job){
  return api('/api/ai/match-job', {method:'POST', body:{resumeText, jobId: job.id}});
}
async function aiMatchAllJobs(resumeText){
  return api('/api/ai/match-all-jobs', {method:'POST', body:{resumeText}});
}
async function aiSummary(resumeText){
  return api('/api/ai/summary', {method:'POST', body:{resumeText}});
}
async function aiFraudCheck(resumeText){
  return api('/api/ai/fraud-check', {method:'POST', body:{resumeText}});
}
async function aiInterviewPrediction(resumeText, job){
  return api('/api/ai/interview-prediction', {method:'POST', body:{resumeText, jobId: job.id}});
}
async function aiAutoTags(resumeText){
  const j = await api('/api/ai/auto-tags', {method:'POST', body:{resumeText}});
  return j ? j.tags : [];
}
async function aiCompareCandidates(idA, idB){
  const r = await api('/api/ai/compare-candidates', {method:'POST', body:{referralIds:[idA, idB]}});
  return r;
}
async function aiGenerateEmail(referral){
  const r = await api('/api/ai/generate-email', {method:'POST', body:{referralId: referral.id}});
  return r.email;
}
async function aiGenerateJD(brief){
  const r = await api('/api/ai/generate-jd', {method:'POST', body:{brief}});
  return r.jd;
}
async function aiChat(userMessage, history){
  const r = await api('/api/ai/chat', {method:'POST', body:{message:userMessage, history}});
  return r.reply;
}
/* Stream a chat answer token-by-token over SSE. onDelta(delta) fires with the
   full answer-so-far each time a chunk arrives; resolves with the final text.
   Pass an AbortSignal to allow cancelling. */
async function aiChatStream(userMessage, history, onDelta, signal){
  const headers = {'Content-Type':'application/json'};
  const t = getToken();
  if(t) headers['Authorization'] = 'Bearer '+t;
  const res = await fetch(API_BASE + '/api/ai/chat/stream', {
    method:'POST', headers, body: JSON.stringify({message:userMessage, history}),
    signal,
  });
  if(res.status === 401){
    clearToken(); state.user=null; state.role=null; render();
    throw new Error('Session expired, please sign in again');
  }
  if(!res.ok){
    let data = null;
    try{ data = await res.json(); }catch(e){}
    throw new Error((data && (data.detail || data.message)) || `Request failed (${res.status})`);
  }
  if(!res.body || !res.body.getReader){
    const data = await res.json();
    throw new Error('Streaming not supported');
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let full = '';
  while(true){
    const {done, value} = await reader.read();
    if(done) break;
    buffer += decoder.decode(value, {stream:true});
    const blocks = buffer.split('\n\n');
    buffer = blocks.pop();
    for(const block of blocks){
      const line = block.trim();
      if(!line.startsWith('data: ')) continue;
      let payload;
      try{ payload = JSON.parse(line.slice(6)); }catch(e){ continue; }
      if(payload.error) throw new Error(payload.message || payload.error);
      else if(payload.done){
        full = payload.reply || full;
        if(typeof onDelta === 'function') onDelta(full);
      }
      else if(payload.delta){
        full = payload.delta;
        if(typeof onDelta === 'function') onDelta(full);
      }
    }
  }
  return full;
}

/* ------------------------------ Mutations ------------------------------ */
async function submitReferralToBackend(fields){
  return api('/api/referrals', {method:'POST', body:fields});
}
async function updateReferralStatus(id, status){
  return api(`/api/referrals/${id}/status`, {method:'PATCH', body:{status}});
}
async function deleteReferral(id){
  return api(`/api/referrals/${id}`, {method:'DELETE'});
}
async function checkDuplicateReferral({email, phone, name}){
  const qs = new URLSearchParams({email:email||'', phone:phone||'', name:name||''});
  return api('/api/referrals/check-duplicate?'+qs.toString());
}
async function createJobBackend(job){
  return api('/api/jobs', {method:'POST', body:job});
}
async function updateSettingsBackend(patch){
  return api('/api/settings', {method:'PUT', body:patch});
}
