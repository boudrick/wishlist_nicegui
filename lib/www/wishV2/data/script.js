/* ═══════════════════════════════════════════════════════════
   script.js  –  wishlist.php client logic
   PERSON and SLUG are injected by PHP as global const
═══════════════════════════════════════════════════════════ */

// ── Utilities ──────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function $id(id) { return document.getElementById(id); }

async function api(action, body) {
  const r = await fetch(`api.php?action=${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ slug: SLUG, ...body }),
  });
  return r.json();
}

// ── Toast ──────────────────────────────────────────────────────────────────────
function toast(msg, type = 'success') {
  const el = $id('toast');
  el.textContent = (type === 'success' ? '✓ ' : '✗ ') + msg;
  el.className = `toast show ${type}`;
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove('show'), 3000);
}

// ── Modals ─────────────────────────────────────────────────────────────────────
function openModal(id)  { $id(id).classList.add('open'); }
function closeModal(id) { $id(id).classList.remove('open'); }
function bgClose(e, id) { if (e.target === $id(id)) closeModal(id); }

// ── State ──────────────────────────────────────────────────────────────────────
let elements   = structuredClone(PERSON.elements ?? []);
let adminCode  = null;
let editingId  = null;   // null = adding new element
let showStatus = false;

// ── Stats ──────────────────────────────────────────────────────────────────────
function renderHero() {
  const gifts = elements.filter(e => e.type === 'cadeau');
  const total = gifts.length;
  const pris  = gifts.filter(g => g.multiple ? g.reserved_count > 0 : g.statut === 'pris').length;
  const libre = total - pris;

  $id('hero').innerHTML = `
    <div class="hero-av">
      <img src="${esc(PERSON.avatar ?? '')}" alt="${esc(PERSON.nom)}"
           onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
      <div class="av-emoji" style="display:none">${esc(PERSON.emoji ?? '🎁')}</div>
    </div>
    <h1>${esc((PERSON.emoji ?? '') + ' Liste de ' + PERSON.nom)}</h1>
    ${PERSON.description ? `<p class="hero-sub">${esc(PERSON.description)}</p>` : ''}
    <div class="hero-stats">
      <div class="hstat"><div class="hstat-n">${total}</div><div class="hstat-l">Cadeaux</div></div>
      <div class="hstat"><div class="hstat-n" style="color:#4CAF50">${libre}</div><div class="hstat-l">À offrir</div></div>
      <div class="hstat"><div class="hstat-n" style="color:#ff7043">${pris}</div><div class="hstat-l">Réservés</div></div>
    </div>`;
}

// ── Render gift list ───────────────────────────────────────────────────────────
function render(list) {
  list ??= elements;
  const isAdmin = !!adminCode;
  let html = '';

  list.forEach(el => {
    if (el.type === 'categorie') {
      html += `
      <div class="cat-hd" data-id="${el.id}">
        <h2>${esc(el.titre)}</h2>
        ${isAdmin ? `<div class="cat-btns">
          <button class="icon-btn edit" onclick="startEdit(${el.id})" title="Modifier"><i class="fas fa-pen"></i></button>
          <button class="icon-btn del"  onclick="delEl(${el.id})"    title="Supprimer"><i class="fas fa-trash"></i></button>
        </div>` : ''}
      </div>`;
      return;
    }

    const taken = el.multiple
      ? (!el.unlimited && el.reserved_count >= el.max_quantity)
      : el.statut === 'pris';

    const qtyBadge = el.multiple ? `
      <div class="qty-badge">
        <i class="fas fa-users"></i>
        ${el.reserved_count} / ${el.unlimited ? '∞' : el.max_quantity} réservé(s)
      </div>` : '';

    let who = '';
    if (el.multiple && el.participants?.length)
      who = `<div class="who-note"><strong>Participants :</strong> ${el.participants.map(esc).join(', ')}</div>`;
    else if (!el.multiple && el.statut === 'pris' && el.reserve_par)
      who = `<div class="who-note"><strong>Réservé par :</strong> ${esc(el.reserve_par)}</div>`;

    const links = (el.liens ?? [])
      .filter(l => l.url)
      .map(l => `<a class="gift-link" href="${esc(l.url)}" target="_blank" rel="noopener">
        <i class="fas fa-external-link-alt"></i>${esc(l.text || l.url)}
      </a>`).join('');

    const reserveBtn = (!taken || el.multiple)
      ? `<button class="btn-primary" onclick="openReserve(${el.id})"><i class="fas fa-hand-holding-heart"></i> Réserver</button>`
      : `<button class="btn-primary" disabled><i class="fas fa-check"></i> Déjà pris</button>`;

    const cancelBtn = (el.statut === 'pris' || el.reserved_count > 0)
      ? `<button class="btn-ghost sm" onclick="openCancel(${el.id})"><i class="fas fa-undo"></i> Annuler</button>`
      : '';

    html += `
    <div class="gift-card${taken ? ' taken' : ''}" data-id="${el.id}">
      <div class="gift-img">
        ${el.image
          ? `<img src="${esc(el.image)}" alt="${esc(el.titre)}" loading="lazy">`
          : `<div class="gift-img-ph">🎁</div>`}
        <div class="status-chip ${taken ? 'pris' : 'libre'}">${taken ? '✓ Réservé' : '🎁 Disponible'}</div>
      </div>
      <div class="gift-body">
        <div class="gift-title">${esc(el.titre)}</div>
        ${el.description ? `<div class="gift-desc">${esc(el.description)}</div>` : ''}
        ${qtyBadge}
        ${links ? `<div class="gift-links">${links}</div>` : ''}
        ${who}
        <div class="gift-foot">
          <div class="gift-actions">${reserveBtn}${cancelBtn}</div>
          ${isAdmin ? `<div class="gift-admin-btns">
            <button class="icon-btn drag" title="Déplacer"><i class="fas fa-grip-vertical"></i></button>
            <button class="icon-btn edit" onclick="startEdit(${el.id})" title="Modifier"><i class="fas fa-pen"></i></button>
            <button class="icon-btn del"  onclick="delEl(${el.id})"    title="Supprimer"><i class="fas fa-trash"></i></button>
          </div>` : ''}
        </div>
      </div>
    </div>`;
  });

  $id('giftList').innerHTML = html;
  $id('emptyState').style.display = html ? 'none' : 'block';
  renderHero();

  if (isAdmin) initMainSortable();
}

// ── Filter ─────────────────────────────────────────────────────────────────────
function filter() {
  const q = $id('search').value.toLowerCase();
  const s = $id('fStatus').value;

  const filtered = elements.filter(el => {
    if (el.type === 'categorie') return true;
    const matchQ = !q
      || el.titre.toLowerCase().includes(q)
      || (el.description ?? '').toLowerCase().includes(q);
    const matchS = !s || (s === 'libre'
      ? (el.statut === 'libre' && (!el.multiple || el.unlimited || el.reserved_count < el.max_quantity))
      : (el.statut === 'pris'  || (el.multiple && el.reserved_count > 0)));
    return matchQ && matchS;
  });
  render(filtered);
}

// ── Status reveal ──────────────────────────────────────────────────────────────
function toggleReveal() {
  showStatus = !showStatus;
  document.body.classList.toggle('show-status', showStatus);
  $id('revealLbl').textContent = showStatus ? 'Masquer les statuts' : 'Statuts masqués';
  $id('revealBtn').querySelector('i').className = showStatus ? 'fas fa-eye-slash' : 'fas fa-eye';
}

// ── Reserve ────────────────────────────────────────────────────────────────────
let _reserveId = null;

function openReserve(id) {
  _reserveId = id;
  $id('rTitle').textContent = elements.find(e => e.id == id)?.titre ?? '';
  $id('rName').value = '';
  $id('rErr').style.display = 'none';
  openModal('reserveModal');
  setTimeout(() => $id('rName').focus(), 80);
}

async function confirmReserve() {
  const name  = $id('rName').value.trim() || 'Anonyme';
  const errEl = $id('rErr');
  errEl.style.display = 'none';
  const r = await api('reserve', { id: _reserveId, name });
  if (r.ok) {
    closeModal('reserveModal');
    toast('Cadeau réservé ! Merci 🎉');
    await refresh();
  } else {
    errEl.textContent = r.err;
    errEl.style.display = 'block';
  }
}

// ── Cancel ─────────────────────────────────────────────────────────────────────
let _cancelId = null;

function openCancel(id) {
  _cancelId = id;
  $id('cTitle').textContent = elements.find(e => e.id == id)?.titre ?? '';
  $id('cName').value = '';
  $id('cErr').style.display = 'none';
  openModal('cancelModal');
  setTimeout(() => $id('cName').focus(), 80);
}

async function confirmCancel() {
  const name  = $id('cName').value.trim() || 'Anonyme';
  const errEl = $id('cErr');
  errEl.style.display = 'none';
  const r = await api('cancel', { id: _cancelId, name });
  if (r.ok) {
    closeModal('cancelModal');
    toast('Réservation annulée');
    await refresh();
  } else {
    errEl.textContent = r.err;
    errEl.style.display = 'block';
  }
}

// ── Refresh from server ────────────────────────────────────────────────────────
async function refresh() {
  // No dedicated read endpoint needed — PHP already served the data.
  // For real-time consistency after a write, we reload just the elements.
  // We call our own page to get fresh data without a full reload.
  try {
    const html = await fetch(`wishlist.php?slug=${SLUG}`).then(r => r.text());
    const match = html.match(/const PERSON = ({[\s\S]*?});\s*<\/script>/);
    if (match) {
      const fresh = JSON.parse(match[1]);
      elements = fresh.elements ?? [];
      render();
    }
  } catch {
    // Fallback: just re-render with the in-memory state
    render();
  }
}

// ── Admin: login ───────────────────────────────────────────────────────────────
function loginAdmin() {
  const code = $id('adminPwd').value;
  if (code === PERSON.admin_code) {
    adminCode = code;
    $id('adminLogin').style.display = 'none';
    $id('adminPanel').style.display = 'block';
    renderAdminItems();
    prefillProfile();
    render();
  } else {
    const e = $id('loginErr');
    e.textContent = 'Code incorrect';
    e.style.display = 'block';
  }
}

// ── Admin: tabs ────────────────────────────────────────────────────────────────
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.style.display = 'none');
    btn.classList.add('active');
    // tab data-tab="gifts" → tabGifts
    const name = btn.dataset.tab;
    $id('tab' + name[0].toUpperCase() + name.slice(1)).style.display = 'block';
  });
});

// ── Admin: form toggle helpers ─────────────────────────────────────────────────
function toggleType() {
  const t = $id('eType').value;
  $id('fGift').style.display = t === 'cadeau'    ? '' : 'none';
  $id('fCat').style.display  = t === 'categorie' ? '' : 'none';
}

function toggleQty() {
  $id('eQtyNum').style.display = $id('eQty').value === 'limited' ? '' : 'none';
}

function addLinkRow(url = '', text = '') {
  const row = document.createElement('div');
  row.className = 'link-row';
  row.innerHTML = `
    <input type="text" class="lu" placeholder="https://…" value="${esc(url)}">
    <input type="text" class="lt" placeholder="Texte / Prix" value="${esc(text)}">
    <button type="button" onclick="this.closest('.link-row').remove()">
      <i class="fas fa-trash"></i>
    </button>`;
  $id('linksWrap').appendChild(row);
}

// ── Admin: start editing an element ───────────────────────────────────────────
function startEdit(id) {
  editingId = id;
  const el = elements.find(e => e.id == id);
  if (!el) return;

  $id('formTitle').innerHTML = '<i class="fas fa-edit"></i> Modifier l\'élément';
  $id('saveLbl').textContent = 'Enregistrer';
  $id('eType').value = el.type;
  toggleType();

  if (el.type === 'categorie') {
    $id('eCatTitle').value = el.titre ?? '';
  } else {
    $id('eTitle').value = el.titre       ?? '';
    $id('eDesc').value  = el.description ?? '';
    $id('eImg').value   = el.image       ?? '';

    const qtyType = el.multiple ? (el.unlimited ? 'unlimited' : 'limited') : 'unique';
    $id('eQty').value    = qtyType;
    $id('eMaxQty').value = el.max_quantity ?? 1;
    toggleQty();

    $id('linksWrap').innerHTML = '';
    (el.liens ?? []).forEach(l => addLinkRow(l.url, l.text));
  }
}

function cancelEdit() {
  editingId = null;
  $id('formTitle').innerHTML = '<i class="fas fa-plus-circle"></i> Ajouter un élément';
  $id('saveLbl').textContent = 'Ajouter';
  $id('eType').value = 'cadeau';
  toggleType();
  ['eTitle','eDesc','eImg','eCatTitle'].forEach(id => $id(id).value = '');
  $id('eQty').value = 'unique';
  toggleQty();
  $id('linksWrap').innerHTML = '';
}

// ── Admin: save an element ─────────────────────────────────────────────────────
async function saveEl() {
  const type = $id('eType').value;
  let newEl;

  if (type === 'categorie') {
    const titre = $id('eCatTitle').value.trim();
    if (!titre) { toast('Titre requis', 'error'); return; }
    newEl = { type: 'categorie', id: editingId ?? Date.now(), titre };
  } else {
    const titre = $id('eTitle').value.trim();
    if (!titre) { toast('Titre requis', 'error'); return; }

    const qtyType  = $id('eQty').value;
    const multiple = qtyType !== 'unique';
    const unlimited= qtyType === 'unlimited';
    const maxQty   = parseInt($id('eMaxQty').value) || 1;

    const liens = [...document.querySelectorAll('#linksWrap .link-row')]
      .map(r => ({ url: r.querySelector('.lu').value.trim(), text: r.querySelector('.lt').value.trim() }))
      .filter(l => l.url);

    // Keep existing reservation data when editing
    const existing = editingId ? elements.find(e => e.id == editingId) : null;
    newEl = {
      ...(existing ?? {
        id: Date.now(), type: 'cadeau',
        statut: 'libre', reserve_par: '',
        date_creation: new Date().toISOString(),
        reserved_count: 0, participants: [],
      }),
      titre,
      description: $id('eDesc').value.trim(),
      image: $id('eImg').value.trim(),
      liens, multiple, unlimited, max_quantity: maxQty,
    };
  }

  if (editingId) {
    const idx = elements.findIndex(e => e.id == editingId);
    if (idx !== -1) elements[idx] = newEl;
  } else {
    elements.push(newEl);
  }

  const r = await api('save', { admin_code: adminCode, elements });
  if (r.ok) {
    toast(editingId ? 'Modifié ✓' : 'Ajouté ✓');
    cancelEdit();
    render();
    renderAdminItems();
  } else {
    toast(r.err, 'error');
  }
}

// ── Admin: delete an element ───────────────────────────────────────────────────
async function delEl(id) {
  if (!confirm('Supprimer cet élément ?')) return;
  elements = elements.filter(e => e.id != id);
  const r = await api('save', { admin_code: adminCode, elements });
  if (r.ok) { toast('Supprimé'); render(); renderAdminItems(); }
  else toast(r.err, 'error');
}

// ── Admin: render item list with drag-and-drop ─────────────────────────────────
let _adminSortable = null;

function renderAdminItems() {
  const container = $id('adminItems');
  $id('elCount').textContent = `(${elements.length})`;

  container.innerHTML = elements.map(el => `
    <div class="admin-item" data-id="${el.id}">
      <button class="icon-btn drag" title="Réordonner"><i class="fas fa-grip-vertical"></i></button>
      <div class="admin-item-label">
        ${el.type === 'categorie' ? '📂' : '🎁'}
        <span>${esc(el.titre)}</span>
      </div>
      <div class="admin-item-actions">
        <button class="icon-btn edit" onclick="startEdit(${el.id})" title="Modifier"><i class="fas fa-pen"></i></button>
        <button class="icon-btn del"  onclick="delEl(${el.id})"    title="Supprimer"><i class="fas fa-trash"></i></button>
      </div>
    </div>`).join('');

  if (_adminSortable) _adminSortable.destroy();
  _adminSortable = Sortable.create(container, {
    handle: '.drag', animation: 140,
    ghostClass: 'sortable-ghost', chosenClass: 'sortable-chosen',
    onEnd: async () => {
      const order = [...container.querySelectorAll('[data-id]')].map(e => Number(e.dataset.id));
      elements = order.map(id => elements.find(e => e.id === id)).filter(Boolean);
      await api('save', { admin_code: adminCode, elements });
      render();
    },
  });
}

// ── Sortable on the main gift list ────────────────────────────────────────────
function initMainSortable() {
  const list = $id('giftList');
  if (!list._sortable) {
    list._sortable = Sortable.create(list, {
      handle: '.icon-btn.drag', animation: 140,
      ghostClass: 'sortable-ghost', chosenClass: 'sortable-chosen',
      onEnd: async () => {
        const order = [...list.querySelectorAll('[data-id]')].map(e => Number(e.dataset.id));
        elements = order.map(id => elements.find(e => e.id === id)).filter(Boolean);
        await api('save', { admin_code: adminCode, elements });
        renderAdminItems();
      },
    });
  }
}

// ── Admin: profile ─────────────────────────────────────────────────────────────
function prefillProfile() {
  $id('pNom').value    = PERSON.nom         ?? '';
  $id('pEmoji').value  = PERSON.emoji       ?? '🎁';
  $id('pDesc').value   = PERSON.description ?? '';
  $id('pAvatar').value = PERSON.avatar      ?? '';
  $id('pColor').value  = PERSON.theme?.primary ?? '#a71d2a';
}

function setColor(id, hex) { $id(id).value = hex; }

function darken(hex, amount) {
  const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
  return '#' + [r,g,b].map(v => Math.max(0, Math.round(v*(1-amount))).toString(16).padStart(2,'0')).join('');
}

async function saveProfile() {
  const c = $id('pColor').value;
  const r = await api('save', {
    admin_code:  adminCode,
    nom:         $id('pNom').value.trim(),
    emoji:       $id('pEmoji').value.trim() || '🎁',
    description: $id('pDesc').value.trim(),
    avatar:      $id('pAvatar').value.trim(),
    theme: {
      primary:        c,
      secondary:      darken(c, .25),
      accent:         '#FFE135',
      gradient_start: c,
      gradient_end:   darken(c, .6),
    },
  });
  if (r.ok) toast('Profil enregistré ✓');
  else toast(r.err, 'error');
}

// ── Admin: backup ──────────────────────────────────────────────────────────────
function exportData() {
  const blob = new Blob(
    [JSON.stringify({ ...PERSON, elements }, null, 2)],
    { type: 'application/json' }
  );
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `wishlist-${SLUG}.json`;
  a.click();
}

function importData(e) {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const data = JSON.parse(reader.result);
      const imported = Array.isArray(data) ? data : (data.elements ?? []);
      if (!Array.isArray(imported)) { toast('Format invalide', 'error'); return; }
      elements = imported;
      const r = await api('save', { admin_code: adminCode, elements });
      if (r.ok) { toast('Import réussi ✓'); render(); renderAdminItems(); }
      else toast(r.err, 'error');
    } catch {
      toast('Fichier JSON invalide', 'error');
    }
  };
  reader.readAsText(file);
}

// ── Init ───────────────────────────────────────────────────────────────────────
render();
