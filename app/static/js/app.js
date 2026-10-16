const $ = id => document.getElementById(id);
const state = { user: null, devices: [], batches: [], images: [], batch: null, busy: false };
let toastTimer;
function toast(text) {
  $('toast').textContent = text; $('toast').hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 4500);
}
async function api(path, options = {}) {
  if ((options.method || 'GET') !== 'GET') { options.headers = { ...options.headers, 'X-CSRF-Token': document.querySelector('meta[name=csrf-token]').content }; }
  let response;
  try { response = await fetch(path, options); }
  catch { throw new Error('連線中斷，請稍後重試。'); }
  const data = await response.json().catch(() => ({ error: '伺服器回應異常，請稍後重試。' }));
  if (!response.ok) throw new Error(data.error || '操作失敗');
  return data;
}
const json = data => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
function closeMenu() { $('sidebar').classList.remove('open'); $('sidebarScrim').hidden = true; $('sidebarScrim').classList.remove('open'); }
$('menuBtn').onclick = () => { $('sidebar').classList.add('open'); $('sidebarScrim').hidden = false; $('sidebarScrim').classList.add('open'); };
$('sidebarScrim').onclick = closeMenu;
document.querySelectorAll('[data-close]').forEach(button => button.onclick = () => button.closest('dialog').close());
function requireUser() {
  if (state.user) return true;
  window.location.href = '/login.php'; return false;
}
async function refreshUser() {
  const data = await api('/api/auth/me'); state.user = data.user; state.devices = data.devices || []; $('adminLink').hidden = !data.user?.is_admin;
  $('accountName').textContent = data.user ? data.user.username : '登入／註冊';
  $('loginLink').hidden = !!data.user;
  $('keyStatus').textContent = data.user?.has_api_key ? '已設定金鑰，輸入新金鑰可更新。' : '尚未設定 Gemini API Key。';
  if (data.user) await loadHistory();
}
$('accountBtn').onclick = () => {
  if (!requireUser()) return;
  $('accountInfo').textContent = `${state.user.username} · UID ${state.user.uid}`;
  $('accountDialog').showModal(); closeMenu();
};
$('logoutBtn').onclick = async () => {
  if (state.busy) return toast('請等目前解題完成後再登出。');
  try { await api('/api/auth/logout', json({})); window.location.href = '/login.php'; }
  catch (error) { toast(error.message); }
};
$('settingsBtn').onclick = () => { if (requireUser()) { $('settingsDialog').showModal(); closeMenu(); loadConnections().catch(error => toast(error.message)); } };
$('settingsForm').onsubmit = async event => {
  event.preventDefault(); const button = $('saveConnection'); if (!$('modelVersion').value) return; button.disabled = true;
  const errorBox = $('settingsForm').querySelector('.form-error'); errorBox.textContent = '';
  try {
    await api('/api/connections', json({ name: $('connectionName').value.trim(), api_key: $('apiKey').value.trim(), model: $('modelVersion').value }));
    $('apiKey').value = ''; resetModelChoices(); await refreshUser(); $('settingsDialog').close(); toast('設定已儲存');
  } catch (error) { errorBox.textContent = error.message; }
  finally { button.disabled = !$('modelVersion').value; }
};
async function loadConnections() {
  const data = await api('/api/connections'); $('connectionHistory').replaceChildren();
  if (!data.connections.length) $('connectionHistory').textContent = '尚無命名設定；原有金鑰可直接沿用。';
  data.connections.forEach(c => {
    const row = document.createElement('div'); row.className = 'connection-row';
    const info = document.createElement('div'); const name = document.createElement('strong'); name.textContent = c.name;
    const meta = document.createElement('small'); meta.textContent = c.model + ' · ' + new Date(c.created_at + 'Z').toLocaleString(); info.append(name, meta);
    const button = document.createElement('button'); button.type = 'button'; button.className = 'outline-btn'; button.textContent = c.active ? '使用中' : '切換使用'; button.disabled = c.active;
    button.onclick = async () => { button.disabled = true; try { await api('/api/connections/' + c.id + '/activate', json({})); $('apiKey').value = ''; resetModelChoices(); await refreshUser(); await loadConnections(); toast('已切換模型設定'); } catch(error) { toast(error.message); button.disabled = false; } };
    row.append(info, button); $('connectionHistory').append(row);
  });
}
let modelLookupRevision = 0;
function resetModelChoices() {
  modelLookupRevision++;
  $('saveConnection').disabled = true; $('saveConnection').textContent = '請先讀取並選擇版本';
  $('modelVersion').replaceChildren(new Option('請重新讀取可用版本', ''));
}
$('modelVersion').onchange = () => { $('saveConnection').disabled = !$('modelVersion').value; $('saveConnection').textContent = $('modelVersion').value ? '儲存並使用' : '請先讀取並選擇版本'; };
$('apiKey').oninput = resetModelChoices;
$('loadModels').onclick = async () => {
  resetModelChoices(); const revision = modelLookupRevision;
  $('loadModels').disabled = true;
  const errorBox = $('settingsForm').querySelector('.form-error'); errorBox.textContent = '';
  try {
    const data = await api('/api/connections/models', json({api_key: $('apiKey').value.trim()}));
    if (revision !== modelLookupRevision) return;
    $('modelVersion').replaceChildren(new Option('請選擇模型版本', ''));
    data.models.forEach(m => $('modelVersion').append(new Option(m.name + ' · ' + m.id, m.id)));
    if (!data.models.length) errorBox.textContent = '這組金鑰沒有適合照片解題的模型版本。';
  } catch(error) { errorBox.textContent = error.message; }
  finally { $('loadModels').disabled = false; }
};
$('deviceBtn').onclick = () => {
  if (!requireUser()) return;
  $('devices').replaceChildren();
  for (const device of state.devices) { const p = document.createElement('p'); p.textContent = device.device_name; $('devices').append(p); }
  $('deviceToken').value = state.user.uid; $('tokenResult').hidden = false;
  $('deviceDialog').showModal(); closeMenu();
};
$('createDevice').onclick = async () => {
  $('createDevice').disabled = true;
  try {
    const data = await api('/api/device/token', json({ device_name: '拍題計算機' }));
    $('deviceToken').value = data.device.token; $('tokenResult').hidden = false; await refreshUser();
  } catch (error) { toast(error.message); }
  finally { $('createDevice').disabled = false; }
};
function updateControls() {
  $('sendBtn').disabled = state.busy || !state.images.length;
  $('pastePhotos').disabled = state.busy; $('attachBtn').disabled = state.busy; $('choosePhotos').disabled = state.busy;
  $('photoCount').textContent = state.images.length ? `${state.images.length} 張` : '';
}
function clearImages() { state.images.forEach(item => URL.revokeObjectURL(item.url)); state.images = []; renderPreviews(); }
function newChat() {
  if (state.busy) return toast('請先等待這次解題完成。');
  clearImages(); state.batch = null; $('chatTitle').textContent = '新對話';
  $('conversation').replaceChildren(emptyTemplate.cloneNode(true));
  $('conversation').querySelector('#emptyUpload').onclick = choose;
  markActive(); closeMenu();
}
const emptyTemplate = $('emptyChat').cloneNode(true);
$('newChat').onclick = newChat; $('newChatMobile').onclick = newChat;
function choose() { if (!state.busy) $('fileInput').click(); }
$('attachBtn').onclick = choose; $('choosePhotos').onclick = choose; $('emptyUpload').onclick = choose;
function addFiles(files) {
  if (state.busy) return;
  let invalid = false;
  for (const raw of files) {
    const file = PhotoInput.normalize(raw);
    if (!file) { invalid = true; continue; }
    const total = state.images.reduce((sum, item) => sum + item.file.size, 0);
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 8388608 || state.images.length >= 8 || total + file.size > 30 * 1024 * 1024) { invalid = true; continue; }
    state.images.push({ file, url: URL.createObjectURL(file) });
  }
  if (invalid) toast('最多 8 張圖片，每張 8 MB，總計不超過 30 MB。');
  renderPreviews();
}
$('fileInput').onchange = event => { addFiles([...event.target.files]); event.target.value = ''; };
function renderPreviews() {
  $('previews').replaceChildren();
  state.images.forEach((item, index) => {
    const card = document.createElement('div'); card.className = 'preview';
    const img = document.createElement('img'); img.src = item.url; img.alt = `待送出照片 ${index + 1}`;
    const badge = document.createElement('span'); badge.className = 'photo-index'; badge.textContent = index + 1;
    const button = document.createElement('button'); button.className = 'remove-photo'; button.textContent = '×'; button.disabled = state.busy;
    button.setAttribute('aria-label', `移除照片 ${index + 1}`);
    button.onclick = () => { URL.revokeObjectURL(item.url); state.images.splice(index, 1); renderPreviews(); };
    card.append(img, badge, button); $('previews').append(card);
  }); updateControls();
}
// Capture transfer events before child controls handle them.
document.addEventListener('paste', event => {
  if (document.querySelector('dialog[open]')) return;
  const files = PhotoInput.extract(event.clipboardData);
  if (files.length) { event.preventDefault(); addFiles(files); }
}, true);
let dragDepth = 0;
const fileDrag = event => [...(event.dataTransfer?.types || [])].includes('Files');
document.addEventListener('dragenter', event => {
  if (!fileDrag(event) || document.querySelector('dialog[open]')) return;
  event.preventDefault(); dragDepth++;
  if (!state.busy) $('dropZone').classList.add('dragging');
}, true);
document.addEventListener('dragover', event => {
  if (!fileDrag(event)) return;
  event.preventDefault(); event.dataTransfer.dropEffect = state.busy ? 'none' : 'copy';
}, true);
document.addEventListener('dragleave', event => {
  if (fileDrag(event)) dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) $('dropZone').classList.remove('dragging');
}, true);
document.addEventListener('drop', event => {
  event.preventDefault(); dragDepth = 0; $('dropZone').classList.remove('dragging');
  if (document.querySelector('dialog[open]')) return;
  const files = PhotoInput.extract(event.dataTransfer);
  if (files.length) addFiles(files);
  else toast('請拖入 JPG、PNG 或 WebP 圖片檔案；網頁連結請先另存成圖片。');
}, true);
window.addEventListener('blur', () => { dragDepth = 0; $('dropZone').classList.remove('dragging'); });
$('pastePhotos').onclick = async () => {
  if (state.busy) return;
  if (!navigator.clipboard?.read) return toast('請先複製圖片，再點一下聊天室並按 Ctrl+V。');
  try {
    const items = await navigator.clipboard.read();
    const files = [];
    for (const item of items) {
      const type = item.types.find(type => ['image/png', 'image/jpeg', 'image/webp'].includes(type));
      if (type) files.push(new File([await item.getType(type)], 'clipboard.' + (type === 'image/jpeg' ? 'jpg' : type.split('/')[1]), {type}));
    }
    if (!files.length) return toast('剪貼簿沒有圖片。請使用截圖或「複製圖片」，再貼上。');
    addFiles(files);
  } catch {
    toast('無法讀取剪貼簿。請允許剪貼簿權限，或點聊天室後按 Ctrl+V，也可按＋選擇檔案。');
  }
};
function scrollBottom() { $('conversation').scrollTop = $('conversation').scrollHeight; }
function photoMessage(photos, label = '題目照片') {
  const message = document.createElement('section'); message.className = 'message user';
  const meta = document.createElement('div'); meta.className = 'message-meta'; meta.textContent = '你';
  const images = document.createElement('div'); images.className = 'user-photos';
  photos.forEach((photo, index) => {
    const button = document.createElement('button'); button.setAttribute('aria-label', `查看照片 ${index + 1}`);
    const img = document.createElement('img'); img.src = photo.url; img.alt = `題目照片 ${index + 1}`;
    // Keep independent object URLs for chat images after clearing upload previews.
    if (photo.file) { img.src = URL.createObjectURL(photo.file); img.onload = () => URL.revokeObjectURL(img.src); }
    button.onclick = () => { $('fullImage').src = photo.file ? URL.createObjectURL(photo.file) : photo.url; $('imageDialog').showModal(); };
    button.append(img); images.append(button);
  });
  const caption = document.createElement('div'); caption.className = 'user-caption'; caption.textContent = `${label} · ${photos.length} 張`;
  message.append(meta, images, caption); $('conversation').append(message); return message;
}
$('imageDialog').addEventListener('close', () => { if ($('fullImage').src.startsWith('blob:')) URL.revokeObjectURL($('fullImage').src); $('fullImage').removeAttribute('src'); });
function createAssistant() {
  const section = document.createElement('section'); section.className = 'message assistant';
  const label = document.createElement('div'); label.className = 'assistant-label';
  const mark = document.createElement('span'); mark.className = 'assistant-mark'; mark.textContent = '解';
  label.append(mark, document.createTextNode('題目解答'));
  const sheet = document.createElement('div'); sheet.className = 'solution-sheet';
  section.append(label, sheet); $('conversation').append(section); return sheet;
}
function renderSolution(sheet, text, questions) {
  const body = document.createElement('div'); body.className = 'solution-body';
  if (window.marked && window.DOMPurify) {
    const formulas = [];
    const protectedText = text.replace(/\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|\$[^$\n]+\$/g, formula => { formulas.push(formula); return `FORMULAEXPR${formulas.length - 1}END`; });
    const html = marked.parse(protectedText).replace(/FORMULAEXPR(\d+)END/g, (_, index) => formulas[index].replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'));
    body.innerHTML = DOMPurify.sanitize(html, { FORBID_TAGS: ['img'] });
    body.querySelectorAll('p').forEach(p => { if (/^(答案|故選|最終答案)[：:]/.test(p.textContent.trim())) p.classList.add('answer-line'); });
  } else { body.textContent = text; }
  if (window.renderMathInElement) renderMathInElement(body, { delimiters: [{ left: '$$', right: '$$', display: true }, { left: '$', right: '$', display: false }, { left: '\\[', right: '\\]', display: true }, { left: '\\(', right: '\\)', display: false }], throwOnError: false, trust: false });
  if (Array.isArray(questions) && questions.length) {
    body.replaceChildren();
    let group = null, previousGroup = '';
    questions.forEach(q => {
      const prefix = q.number.match(/^([一二三四五六七八九十百]+)[、.．]/)?.[1] || '';
      const kind = q.question.match(/同義詞|反義詞/)?.[0] || '';
      const sectionTitle = q.section || (kind ? (prefix ? prefix + '、' : '') + kind : '');
      const groupKey = sectionTitle + ':' + q.photo_indices.join(',');
      if (!group || groupKey !== previousGroup) {
        group = document.createElement('section'); group.className = 'answer-group';
        if (sectionTitle) { const heading = document.createElement('h3'); heading.className = 'answer-group-title'; heading.textContent = sectionTitle; group.append(heading); }
        const source = document.createElement('small'); source.className = 'question-source'; source.textContent = '照片 ' + q.photo_indices.join('、'); group.append(source);
        body.append(group); previousGroup = groupKey;
      }

      const card = document.createElement('article'); card.className = 'question-card';
      const header = document.createElement('div'); header.className = 'question-header';
      const number = document.createElement('h4'); const subnumber = q.number.match(/(?:[、.．]\s*|第\s*)([0-9]+)(?:\s*題)?$/)?.[1] || q.number; number.textContent = '題目' + subnumber;
      const clarity = document.createElement('span'); clarity.className = 'clarity ' + (q.clarity === 'clear' ? 'clear' : 'unclear');
      clarity.textContent = q.clarity === 'clear' ? '辨識清楚' : '需補拍'; header.append(number, clarity);
      card.append(header);
      const field = (label, value, className) => {
        const row = document.createElement('div'); row.className = 'question-field ' + className;
        const title = document.createElement('span'); title.className = 'field-label'; title.textContent = label;
        const content = document.createElement('div'); content.className = 'field-content';
        // Reuse the sanitized Markdown/LaTeX renderer for each independent field.
        const holder = document.createElement('div'); renderSolution(holder, value || '無法辨識');
        content.append(...holder.querySelector('.solution-body').childNodes);
        if (label) row.append(title); row.append(content); card.append(row);
      };
      field('', q.question, 'question-prompt');
      if (q.clarity === 'clear') {
        field('解', q.solution, 'question-solution'); field('答案', q.answer, 'question-answer');
      } else {
        field('原因', q.unclear_reason, 'question-unclear'); field('補拍', q.recapture_hint, 'question-unclear');
        const retry = document.createElement('button'); retry.className = 'recapture-button'; retry.textContent = '上傳補拍照片'; retry.onclick = choose; card.append(retry);
      }
      group.append(card);
    });
  }
  const actions = document.createElement('div'); actions.className = 'answer-actions';
  const caption = document.createElement('span'); caption.textContent = '解答僅供參考，請對照題目驗算';
  const buttons = document.createElement('div');
  const copy = document.createElement('button'); copy.textContent = '複製'; copy.onclick = async () => { try { await navigator.clipboard.writeText(text); toast('已複製解答'); } catch { toast('請選取解答文字複製。'); } };
  const print = document.createElement('button'); print.textContent = '列印'; print.onclick = () => window.print();
  buttons.append(copy, print); actions.append(caption, buttons); sheet.replaceChildren(body, actions);
}
$('sendBtn').onclick = async () => {
  if (state.busy || !state.images.length || !requireUser()) return;
  if (!state.user.has_api_key) { $('settingsDialog').showModal(); return; }
  const selected = [...state.images];
  state.busy = true; renderPreviews();
  $('emptyChat')?.remove();
  const userMessage = photoMessage(selected, state.batch ? '補充照片' : '題目照片');
  const sheet = createAssistant(); const loading = document.createElement('div'); loading.className = 'loading'; loading.textContent = '正在辨識題目並整理解答…'; sheet.append(loading); scrollBottom();
  try {
    const form = new FormData(); if (state.batch) form.append('batch_id', state.batch);
    selected.forEach(item => form.append('images[]', item.file));
    const result = await api('/api/solve', { method: 'POST', body: form });
    state.batch = result.batch_id; renderSolution(sheet, result.reply, result.questions); clearImages();
    await loadHistory().catch(error => toast(error.message));
    const batch = state.batches.find(batch => batch.id === state.batch); $('chatTitle').textContent = batch?.prompt || '照片解題';
  } catch (error) {
    sheet.className = 'error-message'; sheet.textContent = `${error.message} 照片已保留，可重新送出。`;
    const retry = document.createElement('button'); retry.textContent = '重新送出'; retry.onclick = () => { if (state.busy) return; sheet.parentElement.remove(); userMessage.remove(); $('sendBtn').click(); };
    sheet.append(retry);
  } finally { state.busy = false; renderPreviews(); scrollBottom(); }
};
function markActive() { document.querySelectorAll('.history-item').forEach(button => button.classList.toggle('active', button.dataset.batch === state.batch)); }
async function loadHistory() {
  const data = await api('/api/history'); state.batches = data.batches || []; $('historyList').replaceChildren();
  if (!state.batches.length) { const p = document.createElement('p'); p.className = 'sidebar-empty'; p.textContent = '尚無對話紀錄'; $('historyList').append(p); }
  state.batches.forEach(batch => {
    const button = document.createElement('button'); button.className = 'history-item'; button.dataset.batch = batch.id;
    button.textContent = batch.prompt || `照片題目 · ${batch.photos.length} 張`; button.title = button.textContent;
    button.onclick = () => readBatch(batch); $('historyList').append(button);
  }); markActive();
}
function readBatch(batch) {
  if (state.busy) return toast('請先等待這次解題完成。');
  clearImages(); state.batch = batch.id; $('chatTitle').textContent = batch.prompt || '照片解題'; $('conversation').replaceChildren();
  if (batch.photos.length) photoMessage(batch.photos.map(photo => ({ url: '/api/uploads/' + encodeURIComponent(photo.filename) })));
  const replies = batch.messages.filter(message => message.role === 'model');
  replies.forEach(message => renderSolution(createAssistant(), message.content, message.questions));
  if (!replies.length) { const p = document.createElement('p'); p.className = 'error-message'; p.textContent = batch.status === 'solving' ? '這次解題仍在處理，稍後可重新打開。' : '此題尚未完成解答，請重新上傳照片。'; $('conversation').append(p); }
  markActive(); closeMenu(); scrollBottom();
}
refreshUser().catch(error => toast(error.message));
