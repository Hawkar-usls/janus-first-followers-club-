const API=(window.JANUS_PORTAL_API||'').replace(/\/$/,'');
const tabs=[
  ['GROUP','Группа'],['GENESIS','Genesis'],['MARKET','Market'],['HELIOS','HELIOS'],
  ['HRAIN','HRaiN'],['INAIHR','iNaiHR'],['REWARDS','Rewards'],['INVENTORY','Inventory'],['PROFILE','Profile'],['ECOSYSTEM','Все JANUS']
];
const state={session:null,account:null,catalog:null,active:'GROUP',genesis:null,rewards:null};
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];

function endpoint(path){return API+path}
async function api(path,opts={}){
  const r=await fetch(endpoint(path),{credentials:'include',headers:{'Content-Type':'application/json',...(opts.headers||{})},...opts});
  if(!r.ok){let data=null;try{data=await r.json()}catch(_){ }throw Object.assign(new Error(data?.error||('HTTP '+r.status)),{status:r.status,data})}
  return r.status===204?null:r.json();
}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function buildTabs(){
  $('#tabs').innerHTML=tabs.map(([id,label])=>`<button type="button" data-tab="${id}">${label}</button>`).join('');
  $$('[data-tab]').forEach(b=>b.onclick=()=>show(b.dataset.tab));
}
function show(id){
  state.active=id;
  $$('.view').forEach(v=>v.classList.toggle('active',v.dataset.view===id));
  $$('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===id));
  if(['MARKET','HELIOS','HRAIN','INAIHR'].includes(id)){
    const frame=$(`[data-view="${id}"] iframe`);
    if(frame&&!frame.src)frame.src=frame.dataset.src;
  }
  if(id==='ECOSYSTEM')renderEcosystem();
  if(id==='REWARDS'){renderRewards();refreshRewards();}
  if(id==='INVENTORY')renderInventory();
  if(id==='PROFILE')renderProfile();
}
function lockPrivateTabs(){
  $$('[data-tab]').forEach(b=>{if(b.dataset.tab!=='GROUP')b.disabled=!state.account});
}
function renderAccount(){
  const a=state.account;
  const name=a?.display_name||'GUEST';
  const coin=Number(a?.balances?.JANUS_COIN?.available||0);
  const items=a?.inventory||[];
  $('#profileName').textContent=name.toUpperCase();
  $('#homeName').textContent=name;
  $('#homeBalance').textContent=coin.toLocaleString();
  $('#inventoryBalance').textContent=coin.toLocaleString();
  $('#homeStatus').textContent=a?'SIGNED IN':'LOGIN REQUIRED';
  $('#homeInventory').textContent=`${items.length} items`;
  $('#avatar').textContent=(name[0]||'J').toUpperCase();
  const prog=a?.progression||{};
  const xp=Number(prog.xp||0), level=Number(prog.level||1), streak=Number(prog.daily?.streak||0);
  $('#homeXp').textContent=xp.toLocaleString();
  $('#homeLevel').textContent=level;
  $('#homeStreak').textContent=streak;
  const levelFloor=Math.max(0,Math.pow(Math.max(0,level-1),2)*100);
  const levelCeil=Math.max(levelFloor+1,Math.pow(level,2)*100);
  const pct=Math.max(0,Math.min(100,((xp-levelFloor)/(levelCeil-levelFloor))*100));
  $('#homeXpBar').style.width=pct+'%';
  renderInventory(); renderProfile(); renderGenesisState(a?.genesis); renderRewards();
}
function renderInventory(){
  const host=$('#inventoryGrid'); if(!host)return;
  if(!state.account){host.innerHTML='<div class="system-msg">Login required.</div>';return}
  const items=state.account.inventory||[];
  host.innerHTML=items.length?items.map(x=>`<article class="item-card"><b>${esc(x.title||x.item_id)}</b><small>${esc(x.namespace||'PORTAL')} · qty ${Number(x.quantity||1)}</small><small>${esc(x.description||'')}</small></article>`).join(''):'<div class="system-msg">Inventory is empty.</div>';
}
function renderProfile(){
  const host=$('#profileCard');if(!host)return;
  if(!state.account){host.innerHTML='<div class="system-msg">Login required.</div>';return}
  const a=state.account;
  host.innerHTML=[
    ['Account',a.account_id],['Name',a.display_name],['JANUS Coin',a.balances?.JANUS_COIN?.available??0],
    ['Genesis world',a.genesis?.world_id||'not started'],['Genesis turn',a.genesis?.turn??0],
    ['HRaiN graph',a.hrain?.graph_id||'not created'],['iNaiHR graph',a.inaihr?.graph_id||'not created'],
    ['Level',a.progression?.level??1],['XP',a.progression?.xp??0],
    ['Daily streak',a.progression?.daily?.streak??0],
    ['Achievements',(a.progression?.achievements||[]).length],
    ['First free Market search',a.market?.first_free_search_consumed?'used':'available']
  ].map(([k,v])=>`<div class="profile-row"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('');
}
function rewardStatusFromAccount(){
  const p=state.account?.progression||{};
  return {
    xp:Number(p.xp||0),
    level:Number(p.level||1),
    daily:p.daily||{streak:0,last_claim_utc_date:null,total_claims:0},
    unlocked:p.achievements||[],
    recent_reward_receipts:p.recent_reward_receipts||[],
    achievements:[]
  };
}
function renderRewards(){
  const host=$('#achievementGrid'); if(!host)return;
  const r=state.rewards||rewardStatusFromAccount();
  const coin=Number(state.account?.balances?.JANUS_COIN?.available||0);
  $('#rewardsLevel').textContent=Number(r.level||1);
  $('#rewardsXp').textContent=Number(r.xp||0).toLocaleString();
  $('#rewardsCoin').textContent=coin.toLocaleString();
  $('#rewardsStreak').textContent=Number(r.daily?.streak||0);
  const unlocked=new Set((r.unlocked||[]).map(x=>typeof x==='string'?x:x.id));
  $('#rewardsAchievementCount').textContent=unlocked.size;
  const catalog=r.achievements||[];
  host.innerHTML=catalog.length?catalog.map(a=>{
    const yes=unlocked.has(a.id);
    const rw=a.reward||{};
    const reward=[rw.janus_coin?rw.janus_coin+' JC':'',rw.xp?rw.xp+' XP':'',rw.item||rw.badge||''].filter(Boolean).join(' · ');
    return `<article class="achievement-card ${yes?'unlocked':'locked'}"><div class="ach-state">${yes?'◆ UNLOCKED':'◇ LOCKED'}</div><h4>${esc(a.title||a.id)}</h4><p>${esc(a.description||'')}</p><small>${esc(reward)}</small></article>`;
  }).join(''):'<div class="system-msg">Achievement catalog loads from the account backend.</div>';
  const rows=r.recent_reward_receipts||[];
  $('#rewardHistory').innerHTML=rows.length?rows.map(x=>`<div class="reward-row"><b>${esc(x.kind||x.event_type||x.achievement_id||'REWARD')}</b><span>${esc(x.created_at||x.date||'')}</span><em>+${Number(x.janus_coin||x.reward?.janus_coin||0)} JC · +${Number(x.xp||x.reward?.xp||0)} XP</em></div>`).join(''):'<div class="system-msg" style="padding:14px">No reward receipts yet.</div>';
  const claimed=r.daily?.claimed_today===true;
  const msg=claimed?'Daily reward already claimed today.':state.account?'Daily reward available once per server UTC day.':'Login to claim.';
  $('#rewardsDailyState').textContent=msg;
  $('#dailyState').textContent=msg;
  $('#rewardsDailyClaim').disabled=!state.account||claimed;
  $('#dailyClaim').disabled=!state.account||claimed;
}
async function refreshRewards(){
  if(!state.account){state.rewards=null;renderRewards();return}
  try{
    const r=await api('/api/portal/rewards/status');
    state.rewards=r;
  }catch(_){
    state.rewards=rewardStatusFromAccount();
  }
  renderRewards();
}
async function claimDaily(){
  if(!state.account)return openLogin('Login required for daily rewards.');
  const key=crypto.randomUUID();
  for(const id of ['dailyClaim','rewardsDailyClaim']){const b=$('#'+id);if(b)b.disabled=true}
  try{
    const r=await api('/api/portal/rewards/daily/claim',{method:'POST',body:JSON.stringify({idempotency_key:key})});
    if(r?.reward){
      const bits=[r.reward.janus_coin?('+'+r.reward.janus_coin+' JANUS Coin'):'',r.reward.xp?('+'+r.reward.xp+' XP'):'',r.reward.item?('item '+r.reward.item):''].filter(Boolean);
      $('#dailyState').textContent='Claimed: '+bits.join(' · ');
    }
    await refreshAccount(); await refreshRewards();
  }catch(e){
    $('#dailyState').textContent='Daily reward: '+e.message;
    $('#rewardsDailyState').textContent='Daily reward: '+e.message;
    await refreshRewards();
  }
}

async function renderEcosystem(){
  const host=$('#ecosystemGrid'); if(!host)return;
  if(!state.catalog){try{state.catalog=await fetch('./ecosystem-catalog.json',{cache:'no-store'}).then(r=>r.json())}catch(_){state.catalog={featured:[]}}}
  host.innerHTML=(state.catalog.featured||[]).map(r=>`<article class="repo-card"><b>${esc(r.title)}</b><small>${esc(r.repo)}</small><small>${esc(r.mode)}</small><a href="${esc(r.url)}" target="_blank" rel="noopener">Source / public surface ↗</a></article>`).join('');
}
function renderGenesisState(g){
  const x=g||state.genesis||{};
  $('#genTurn').textContent=Number(x.turn||0);
  $('#genLocation').textContent=x.current_location||'—';
  $('#genWorld').textContent=x.world_id||'—';
}
function addChronicle(role,text){
  const host=$('#chronicleLog');
  const d=document.createElement('div');d.className='turn '+role;
  d.innerHTML=`<div class="${role}">${esc(text).replace(/\n/g,'<br>')}</div>`;
  host.append(d);host.scrollTop=host.scrollHeight;
}
async function checkGenesisHealth(){
  try{
    const h=await api('/api/portal/genesis/health');
    $('#genesisRuntime').textContent=h.authoritative_runtime_available?'AUTHORITATIVE ONLINE':'NARRATIVE / DEGRADED';
    $('#genesisRuntime').className='runtime '+(h.authoritative_runtime_available?'online':'offline');
  }catch(_){$('#genesisRuntime').textContent='RUNTIME OFFLINE';$('#genesisRuntime').className='runtime offline'}
}
async function startGenesis(){
  if(!state.account)return openLogin('Login required for persistent Genesis.');
  try{
    const r=await api('/api/portal/genesis/start',{method:'POST',body:JSON.stringify({idempotency_key:crypto.randomUUID()})});
    state.genesis=r.state||r; renderGenesisState(state.genesis);
    $('#chronicleLog').innerHTML=''; addChronicle('world',r.narration||'Janus Genesis is open. What do you do?');
    await refreshAccount();
  }catch(e){addChronicle('system-msg','Genesis unavailable: '+e.message)}
}
async function genesisTurn(text){
  if(!state.account)return openLogin('Login required.');
  const key=crypto.randomUUID();
  addChronicle('player','> '+text);
  try{
    const r=await api('/api/portal/genesis/turn',{method:'POST',body:JSON.stringify({text,idempotency_key:key})});
    addChronicle('world',r.narration||JSON.stringify(r));
    state.genesis=r.state||state.genesis; renderGenesisState(state.genesis); await refreshAccount();
  }catch(e){addChronicle('system-msg','Turn failed: '+e.message)}
}
async function saveGenesis(){
  try{const r=await api('/api/portal/genesis/capsule');const blob=new Blob([JSON.stringify(r,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='janus-genesis-capsule.json';a.click();URL.revokeObjectURL(a.href)}catch(e){addChronicle('system-msg','Capsule unavailable: '+e.message)}
}
function openLogin(msg){if(msg)$('#loginState').textContent=msg;$('#loginModal').classList.add('open')}
function closeLogin(){$('#loginModal').classList.remove('open')}
async function refreshAccount(){
  try{const r=await api('/api/portal/me');state.session=r.session||true;state.account=r.account||r;closeLogin()}catch(e){state.session=null;state.account=null;if(e.status!==401)$('#loginState').textContent='Portal backend unavailable: '+e.message}
  renderAccount();lockPrivateTabs();if(state.account)refreshRewards();
}
async function telegramLogin(){
  const tg=window.Telegram?.WebApp;
  if(tg?.initData){
    try{await api('/api/portal/auth/telegram',{method:'POST',body:JSON.stringify({init_data:tg.initData})});await refreshAccount();return}catch(e){$('#loginState').textContent='Telegram login failed: '+e.message;return}
  }
  location.href=endpoint('/api/portal/auth/telegram/start?return_to='+encodeURIComponent(location.href));
}
function githubLogin(){location.href=endpoint('/api/portal/auth/github/start?return_to='+encodeURIComponent(location.href))}
async function passkeyLogin(){
  $('#loginState').textContent='Passkey requires the Portal auth backend.';
  try{
    const options=await api('/api/portal/auth/passkey/options',{method:'POST',body:'{}'});
    if(!navigator.credentials?.get)throw new Error('WebAuthn unavailable');
    const assertion=await navigator.credentials.get({publicKey:options.publicKey});
    await api('/api/portal/auth/passkey/verify',{method:'POST',body:JSON.stringify({credential:assertion})});await refreshAccount();
  }catch(e){$('#loginState').textContent='Passkey login unavailable: '+e.message}
}
function bind(){
  $$('[data-go]').forEach(b=>b.onclick=()=>{if(!state.account&&b.dataset.go!=='GROUP')return openLogin();show(b.dataset.go)});
  $('#profileButton').onclick=()=>state.account?show('PROFILE'):openLogin();
  $('#telegramLogin').onclick=telegramLogin;$('#githubLogin').onclick=githubLogin;$('#passkeyLogin').onclick=passkeyLogin;
  $('#guestPreview').onclick=()=>{closeLogin();show('GROUP')};
  $('#startGenesis').onclick=startGenesis;$('#saveGenesis').onclick=saveGenesis;
  $('#dailyClaim').onclick=claimDaily;$('#rewardsDailyClaim').onclick=claimDaily;
  $('#genesisForm').onsubmit=e=>{e.preventDefault();const i=$('#genesisInput');const v=i.value.trim();if(v){i.value='';genesisTurn(v)}};
}
buildTabs();bind();show('GROUP');refreshAccount();checkGenesisHealth();renderEcosystem();
