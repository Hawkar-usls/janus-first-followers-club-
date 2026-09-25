const API=(window.JANUS_PORTAL_API||'').replace(/\/$/,'');
const tabs=[
  ['GROUP','Группа'],['GENESIS','Genesis'],['MARKET','Market'],['HELIOS','HELIOS'],
  ['HRAIN','HRaiN'],['INAIHR','iNaiHR'],['INVENTORY','Inventory'],['PROFILE','Profile'],['ECOSYSTEM','Все JANUS']
];
const state={session:null,account:null,catalog:null,active:'GROUP',genesis:null};
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
  renderInventory(); renderProfile(); renderGenesisState(a?.genesis);
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
    ['First free Market search',a.market?.first_free_search_consumed?'used':'available']
  ].map(([k,v])=>`<div class="profile-row"><span>${esc(k)}</span><b>${esc(v)}</b></div>`).join('');
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
  renderAccount();lockPrivateTabs();
}
async function telegramLogin(){
  const tg=window.Telegram?.WebApp;
  if(tg?.initData){
    try{await api('/api/portal/auth/telegram',{method:'POST',body:JSON.stringify({init_data:tg.initData})});await refreshAccount();return}catch(e){$('#loginState').textContent='Telegram login failed: '+e.message;return}
  }
  location.href='https://t.me/Ini_Chron_bot?start=janus_portal_login';
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
  $('#genesisForm').onsubmit=e=>{e.preventDefault();const i=$('#genesisInput');const v=i.value.trim();if(v){i.value='';genesisTurn(v)}};
}
buildTabs();bind();show('GROUP');refreshAccount();checkGenesisHealth();renderEcosystem();
