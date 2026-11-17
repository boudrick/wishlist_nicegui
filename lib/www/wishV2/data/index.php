<?php
// PHP's only job: read data files and inject them as JSON
define('DATA_DIR', __DIR__ . '/data/');
$persons = [];
foreach (glob(DATA_DIR . '*.json') ?: [] as $f) {
    $d = json_decode(file_get_contents($f), true);
    if (!$d || ($d['slug'] ?? '') === 'exemple') continue;
    $total = $pris = 0;
    foreach ($d['elements'] ?? [] as $e) {
        if ($e['type'] !== 'cadeau') continue;
        $total++;
        if ($e['multiple'] ? $e['reserved_count'] > 0 : $e['statut'] === 'pris') $pris++;
    }
    $persons[] = [
        'slug' => $d['slug'], 'nom' => $d['nom'], 'emoji' => $d['emoji'] ?? '🎁',
        'description' => $d['description'] ?? '', 'avatar' => $d['avatar'] ?? '',
        'theme' => $d['theme'] ?? [], 'total' => $total, 'pris' => $pris,
    ];
}
?><!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>🎄 Listes de Cadeaux – Famille</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&family=Outfit:wght@300;400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="stylesheet" href="style.css">
</head>
<body class="page-home">

<div class="home-bg">
  <div class="orb o1"></div>
  <div class="orb o2"></div>
  <div class="orb o3"></div>
</div>

<main class="home-wrap">
  <header class="home-header">
    <span class="xmas-icon">🎄</span>
    <h1>Listes de Cadeaux</h1>
    <p>Choisissez une personne pour voir ses envies</p>
  </header>

  <div class="persons-grid" id="grid"></div>

  <div class="home-footer">
    <button class="btn-ghost" onclick="openModal('createModal')">
      <i class="fas fa-plus"></i> Créer ma liste
    </button>
  </div>
</main>

<!-- Modal : créer une liste -->
<div id="createModal" class="modal" onclick="bgClose(event,'createModal')">
  <div class="modal-box">
    <button class="x-btn" onclick="closeModal('createModal')"><i class="fas fa-times"></i></button>
    <h2>✨ Créer ma liste</h2>
    <div class="row-2">
      <div class="fg">
        <label>Prénom <span class="req">*</span></label>
        <input id="cNom" type="text" placeholder="Marie" maxlength="30" oninput="autoSlug()">
      </div>
      <div class="fg">
        <label>Emoji</label>
        <input id="cEmoji" type="text" placeholder="🎁" maxlength="4" value="🎁">
      </div>
    </div>
    <div class="fg">
      <label>Identifiant URL <span class="req">*</span></label>
      <input id="cSlug" type="text" placeholder="marie" maxlength="30" oninput="previewSlug()">
      <small>Lien : <code id="slugPreview">…</code></small>
    </div>
    <div class="fg">
      <label>Description</label>
      <textarea id="cDesc" rows="2" placeholder="Un petit mot d'intro…"></textarea>
    </div>
    <div class="fg">
      <label>Couleur du thème</label>
      <div class="color-row">
        <input id="cColor" type="color" value="#a71d2a">
        <div class="presets">
          <span class="dot" style="background:#a71d2a" onclick="setColor('cColor','#a71d2a')"></span>
          <span class="dot" style="background:#1a4fa0" onclick="setColor('cColor','#1a4fa0')"></span>
          <span class="dot" style="background:#1a6b3c" onclick="setColor('cColor','#1a6b3c')"></span>
          <span class="dot" style="background:#8b1a8b" onclick="setColor('cColor','#8b1a8b')"></span>
          <span class="dot" style="background:#c47a1a" onclick="setColor('cColor','#c47a1a')"></span>
          <span class="dot" style="background:#1a7a8b" onclick="setColor('cColor','#1a7a8b')"></span>
        </div>
      </div>
    </div>
    <div class="fg">
      <label>Code admin <span class="req">*</span></label>
      <input id="cCode" type="password" placeholder="Min. 4 caractères">
    </div>
    <div id="createErr" class="err-msg" style="display:none"></div>
    <button class="btn-primary full" onclick="createPerson()">
      <i class="fas fa-rocket"></i> Créer ma liste
    </button>
  </div>
</div>

<script>
// ── Data injected by PHP ───────────────────────────────────────────────────
const PERSONS = <?= json_encode($persons, JSON_UNESCAPED_UNICODE) ?>;

// ── Helpers ────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function openModal(id)  { document.getElementById(id).classList.add('open'); }
function closeModal(id) { document.getElementById(id).classList.remove('open'); }
function bgClose(e, id) { if (e.target.id === id) closeModal(id); }
function setColor(id, hex) { document.getElementById(id).value = hex; }

// ── Render person cards ────────────────────────────────────────────────────
function renderPersons() {
  const grid = document.getElementById('grid');
  if (!PERSONS.length) {
    grid.innerHTML = '<p class="empty-note">Aucune liste pour l\'instant. Créez la première !</p>';
    return;
  }
  grid.innerHTML = PERSONS.map(p => {
    const th = p.theme || {};
    const g1 = th.gradient_start || th.primary || '#333';
    const g2 = th.gradient_end   || '#111';
    const ac = th.accent || '#FFE135';
    const pct = p.total ? Math.round(p.pris / p.total * 100) : 0;
    return `
    <a href="wishlist.php?slug=${esc(p.slug)}" class="person-card" style="background:linear-gradient(140deg,${g1},${g2});--ac:${ac}">
      <div class="pc-avatar">
        <img src="${esc(p.avatar)}" alt="${esc(p.nom)}" onerror="this.style.display='none'">
      </div>
      <div class="pc-emoji">${esc(p.emoji)}</div>
      <div class="pc-name">${esc(p.nom)}</div>
      <div class="pc-desc">${esc(p.description)}</div>
      <div class="pc-stats">
        <span>${p.total} cadeau${p.total>1?'x':''}</span>
        <span>${p.total - p.pris} disponible${(p.total-p.pris)>1?'s':''}</span>
      </div>
      <div class="pc-bar"><div style="width:${pct}%;background:${ac}"></div></div>
      <div class="pc-cta">Voir la liste <i class="fas fa-arrow-right"></i></div>
    </a>`;
  }).join('');
}

// ── Create person ──────────────────────────────────────────────────────────
function autoSlug() {
  const v = document.getElementById('cNom').value.toLowerCase()
    .normalize('NFD').replace(/[\u0300-\u036f]/g,'')
    .replace(/[^a-z0-9]/g,'-').replace(/-+/g,'-').replace(/^-|-$/g,'');
  document.getElementById('cSlug').value = v;
  previewSlug();
}
function previewSlug() {
  const s = document.getElementById('cSlug').value;
  document.getElementById('slugPreview').textContent = location.origin + location.pathname.replace('index.php','') + 'wishlist.php?slug=' + s;
}
async function createPerson() {
  const nom  = document.getElementById('cNom').value.trim();
  const slug = document.getElementById('cSlug').value.trim();
  const code = document.getElementById('cCode').value;
  const errEl = document.getElementById('createErr');
  errEl.style.display = 'none';
  if (!nom || !slug || !code) {
    errEl.textContent = 'Prénom, identifiant et code sont requis.';
    errEl.style.display = 'block';
    return;
  }
  const r = await fetch('api.php?action=create', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      nom, slug,
      emoji: document.getElementById('cEmoji').value || '🎁',
      description: document.getElementById('cDesc').value,
      color: document.getElementById('cColor').value,
      admin_code: code,
    })
  }).then(r => r.json());
  if (r.ok) {
    location.href = 'wishlist.php?slug=' + r.slug;
  } else {
    errEl.textContent = r.err;
    errEl.style.display = 'block';
  }
}

renderPersons();
</script>
</body>
</html>
