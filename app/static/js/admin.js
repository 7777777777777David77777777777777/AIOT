const $ = id => document.getElementById(id);
let memberPage = 1, memberPages = 1, selected = null;
const node = (tag, text, cls) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; };
const time = value => new Date(value + 'Z').toLocaleString();
async function api(path, post = false) {
  const response = await fetch(path, post ? {method:'POST', headers:{'X-CSRF-Token':document.querySelector('meta[name=csrf-token]').content}} : {});
  const result = await response.json(); if (!response.ok) throw new Error(result.error || '讀取失敗'); return result;
}
function report(error) { $('adminError').textContent = error.message; }
async function loadMembers() {
  const data = await api('/api/admin/members?page=' + memberPage + '&q=' + encodeURIComponent($('search').value));
  memberPages = data.pages; $('memberCount').textContent = '共 ' + data.total + ' 位會員'; $('memberList').replaceChildren();
  data.members.forEach(user => {
    const button = node('button', undefined, 'member' + (selected === user.id ? ' active' : ''));
    button.append(node('strong', user.username), node('small', user.batch_count + ' 筆紀錄 · ' + (user.active_model || '預設模型')));
    button.onclick = () => showMember(user.id).catch(report); $('memberList').append(button);
  });
  $('membersPage').textContent = data.page + ' / ' + data.pages;
  $('previousMembers').disabled = memberPage <= 1; $('nextMembers').disabled = memberPage >= memberPages;
}
async function showMember(id, page = 1) {
  const data = await api('/api/admin/members/' + id + '?page=' + page); selected = id; $('adminError').textContent = '';
  const target = $('memberDetail'); target.replaceChildren();
  const profile = node('div', undefined, 'profile'); const info = node('div');
  info.append(node('h2', data.user.username + (data.user.is_admin ? ' · 管理員' : '')), node('p', '裝置碼 ' + data.user.uid + ' · 註冊 ' + time(data.user.created_at), 'muted'));
  const reveal = node('button', '顯示完整 API Key'); reveal.onclick = () => revealKeys(id).catch(report); profile.append(info,reveal); target.append(profile);
  target.append(node('h3','模型設定與歷史'));
  if (!data.connections.length) target.append(node('p',data.user.has_api_key ? '使用原有金鑰與預設模型' : '尚未設定金鑰','muted'));
  data.connections.forEach(c => { const row = node('div',undefined,'model-row'); row.append(node('strong',c.name + ' '),node('span',c.active?'使用中':'歷史設定','badge'),node('p',c.model),node('small',time(c.created_at))); target.append(row); });
  target.append(node('h3','解題紀錄 · ' + data.total + ' 筆'));
  data.batches.forEach(batch => {
    const record = node('details',undefined,'record'); record.append(node('summary',batch.prompt || '照片解題'),node('p',time(batch.created_at) + ' · ' + batch.status,'muted'));
    const photos = node('div',undefined,'photos');
    batch.photos.forEach(p => { const a = node('a'); a.href='/api/uploads/' + encodeURIComponent(p.filename); a.target='_blank'; a.rel='noopener'; const img = node('img'); img.src=a.href; img.alt='題目照片'; img.onerror=()=>{ const missing=node('span','照片已不存在','muted'); a.replaceChildren(missing); }; a.append(img); photos.append(a); }); record.append(photos);
    batch.messages.filter(m=>m.role==='model').forEach(m=>{record.append(node('pre',m.content,'answer')); if(m.questions){const raw=node('details'); raw.append(node('summary','查看解答 JSON'),node('pre',JSON.stringify(m.questions,null,2),'json'));record.append(raw);}});
    if (!batch.messages.some(m=>m.role==='model')) record.append(node('p','尚無解答','muted')); target.append(record);
  });
  const nav = node('nav'); const prev=node('button','上一頁'), next=node('button','下一頁'); prev.disabled=page<=1;next.disabled=page>=data.pages;
  prev.onclick=()=>showMember(id,page-1).catch(report);next.onclick=()=>showMember(id,page+1).catch(report);nav.append(prev,node('span',page+' / '+data.pages),next);target.append(nav);
  document.querySelectorAll('.member').forEach(b=>b.classList.toggle('active',b.querySelector('strong').textContent===data.user.username));
}
async function revealKeys(id) {
  $('keyList').replaceChildren();
  const data = await api('/api/admin/members/' + id + '/keys',true);
  const entries = [{name:'目前使用的金鑰',api_key:data.current_key},...data.connections];
  entries.forEach(c=>{const label=node('label',c.name + (c.model?' · '+c.model:''));const input=node('input');input.readOnly=true;input.value=c.api_key||'尚未設定';label.append(input);$('keyList').append(label);});
  $('keysDialog').showModal();
}
$('closeKeys').onclick=()=>$('keysDialog').close();
$('keysDialog').addEventListener('close',()=>$('keyList').replaceChildren());
$('searchForm').onsubmit=e=>{e.preventDefault();memberPage=1;loadMembers().catch(report);};
$('previousMembers').onclick=()=>{memberPage--;loadMembers().catch(report);};
$('nextMembers').onclick=()=>{memberPage++;loadMembers().catch(report);};
loadMembers().catch(report);
