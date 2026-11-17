<?php
// PHP's only job: validate slug and inject person data as JSON
define('DATA_DIR', __DIR__ . '/data/');
$slug = preg_replace('/[^a-z0-9\-]/', '', strtolower($_GET['slug'] ?? ''));
if (!$slug) { header('Location: index.php'); exit; }
$file = DATA_DIR . $slug . '.json';
if (!file_exists($file)) { header('Location: index.php'); exit; }
$person = json_decode(file_get_contents($file), true);
if (!$person) { header('Location: index.php'); exit; }

$th      = $person['theme'] ?? [];
$primary = $th['primary']        ?? '#a71d2a';
$accent  = $th['accent']         ?? '#FFE135';
$gradS   = $th['gradient_start'] ?? $primary;
$gradE   = $th['gradient_end']   ?? '#080205';
?><!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>🎁 Liste de <?= htmlspecialchars($person['nom']) ?></title>
  <meta name="description" content="<?= htmlspecialchars($person['description'] ?? '') ?>">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&family=Outfit:wght@300;400;500;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <link rel="stylesheet" href="style.css">
  <!-- Only CSS variables come from PHP -->
  <style>
    :root {
      --primary: <?= $primary ?>;
      --accent:  <?= $accent  ?>;
      --gradS:   <?= $gradS   ?>;
      --gradE:   <?= $gradE   ?>;
    }
  </style>
</head>
<body class="page-wishlist">

<!-- Background -->
<div class="wl-bg"></div>

<!-- Navigation -->
<a href="index.php" class="back-link"><i class="fas fa-arrow-left"></i> Retour</a>
<button class="fab" id="adminFab" onclick="openModal('adminModal')" title="Administration">
  <i class="fas fa-user-cog"></i>
</button>

<!-- Main content — entirely built by JS -->
<div class="wl-wrap">
  <header class="wl-hero" id="hero"></header>
  <div class="wl-controls">
    <input id="search" class="ctrl-input" type="text" placeholder="🔍 Rechercher un cadeau…" oninput="filter()">
    <select id="fStatus" class="ctrl-select" onchange="filter()">
      <option value="">Tout afficher</option>
      <option value="libre">À offrir 🎁</option>
      <option value="pris">Déjà réservé ✓</option>
    </select>
    <button id="revealBtn" class="btn-ghost sm" onclick="toggleReveal()">
      <i class="fas fa-eye"></i> <span id="revealLbl">Statuts masqués</span>
    </button>
  </div>
  <div id="giftList"></div>
  <p id="emptyState" class="empty-note" style="display:none">Aucun cadeau trouvé.</p>
</div>

<!-- Modal : réserver -->
<div id="reserveModal" class="modal" onclick="bgClose(event,'reserveModal')">
  <div class="modal-box sm">
    <button class="x-btn" onclick="closeModal('reserveModal')"><i class="fas fa-times"></i></button>
    <h2><i class="fas fa-gift"></i> Réserver ce cadeau</h2>
    <p id="rTitle" class="modal-sub"></p>
    <div class="fg">
      <label>Votre prénom (facultatif)</label>
      <input id="rName" type="text" placeholder="Anonyme" maxlength="40"
             onkeydown="if(event.key==='Enter') confirmReserve()">
    </div>
    <div id="rErr" class="err-msg" style="display:none"></div>
    <div class="btn-row">
      <button class="btn-primary" onclick="confirmReserve()"><i class="fas fa-check"></i> Confirmer</button>
      <button class="btn-ghost" onclick="closeModal('reserveModal')">Annuler</button>
    </div>
  </div>
</div>

<!-- Modal : annuler réservation -->
<div id="cancelModal" class="modal" onclick="bgClose(event,'cancelModal')">
  <div class="modal-box sm">
    <button class="x-btn" onclick="closeModal('cancelModal')"><i class="fas fa-times"></i></button>
    <h2><i class="fas fa-undo"></i> Annuler une réservation</h2>
    <p id="cTitle" class="modal-sub"></p>
    <div class="fg">
      <label>Votre prénom (utilisé lors de la réservation)</label>
      <input id="cName" type="text" placeholder="Anonyme" maxlength="40"
             onkeydown="if(event.key==='Enter') confirmCancel()">
    </div>
    <div id="cErr" class="err-msg" style="display:none"></div>
    <div class="btn-row">
      <button class="btn-danger" onclick="confirmCancel()"><i class="fas fa-trash"></i> Annuler la réservation</button>
      <button class="btn-ghost" onclick="closeModal('cancelModal')">Fermer</button>
    </div>
  </div>
</div>

<!-- Modal : admin -->
<div id="adminModal" class="modal" onclick="bgClose(event,'adminModal')">
  <div class="modal-box wide">
    <button class="x-btn" onclick="closeModal('adminModal')"><i class="fas fa-times"></i></button>

    <!-- Écran de connexion -->
    <div id="adminLogin">
      <h2><i class="fas fa-lock"></i> Administration</h2>
      <div class="fg">
        <label>Code d'accès</label>
        <input id="adminPwd" type="password" placeholder="••••"
               onkeydown="if(event.key==='Enter') loginAdmin()">
      </div>
      <div id="loginErr" class="err-msg" style="display:none"></div>
      <button class="btn-primary" onclick="loginAdmin()">
        <i class="fas fa-sign-in-alt"></i> Se connecter
      </button>
    </div>

    <!-- Panel admin (affiché après login) -->
    <div id="adminPanel" style="display:none">
      <div class="tabs">
        <button class="tab active" data-tab="gifts"><i class="fas fa-gift"></i> Cadeaux</button>
        <button class="tab" data-tab="profile"><i class="fas fa-user"></i> Profil</button>
        <button class="tab" data-tab="backup"><i class="fas fa-database"></i> Backup</button>
      </div>

      <!-- Onglet Cadeaux -->
      <div id="tabGifts" class="tab-pane">
        <div class="admin-cols">

          <!-- Formulaire ajout / édition -->
          <div class="admin-form">
            <h3 id="formTitle"><i class="fas fa-plus-circle"></i> Ajouter un élément</h3>
            <div class="fg">
              <label>Type</label>
              <select id="eType" onchange="toggleType()">
                <option value="cadeau">🎁 Cadeau</option>
                <option value="categorie">📂 Catégorie</option>
              </select>
            </div>
            <div id="fCat" style="display:none">
              <div class="fg"><label>Titre de la catégorie</label>
                <input id="eCatTitle" type="text" placeholder="Ex: Livres, Tech…">
              </div>
            </div>
            <div id="fGift">
              <div class="fg"><label>Titre</label>
                <input id="eTitle" type="text" placeholder="Nom du cadeau">
              </div>
              <div class="fg"><label>Description</label>
                <textarea id="eDesc" rows="2" placeholder="Informations, taille, couleur…"></textarea>
              </div>
              <div class="fg"><label>Image (URL)</label>
                <input id="eImg" type="text" placeholder="https://…">
              </div>
              <div class="fg"><label>Quantité</label>
                <select id="eQty" onchange="toggleQty()">
                  <option value="unique">Unique (1 personne)</option>
                  <option value="limited">Multiple (quantité limitée)</option>
                  <option value="unlimited">Multiple (illimité)</option>
                </select>
              </div>
              <div id="eQtyNum" class="fg" style="display:none">
                <label>Quantité max</label>
                <input id="eMaxQty" type="number" min="1" value="1">
              </div>
              <div class="fg">
                <label>Liens</label>
                <div id="linksWrap"></div>
                <button type="button" class="add-link-btn" onclick="addLinkRow()">
                  <i class="fas fa-plus"></i> Ajouter un lien
                </button>
              </div>
            </div>
            <div class="btn-row">
              <button class="btn-primary" onclick="saveEl()">
                <i class="fas fa-save"></i> <span id="saveLbl">Ajouter</span>
              </button>
              <button class="btn-ghost" onclick="cancelEdit()">Annuler</button>
            </div>
          </div>

          <!-- Liste des éléments -->
          <div class="admin-list-wrap">
            <h3><i class="fas fa-list"></i> Éléments <small id="elCount"></small></h3>
            <div id="adminItems" class="admin-items"></div>
          </div>
        </div>
      </div>

      <!-- Onglet Profil -->
      <div id="tabProfile" class="tab-pane" style="display:none">
        <div class="row-2">
          <div class="fg"><label>Prénom</label><input id="pNom" type="text"></div>
          <div class="fg"><label>Emoji</label><input id="pEmoji" type="text" maxlength="4"></div>
        </div>
        <div class="fg"><label>Description / message d'intro</label>
          <textarea id="pDesc" rows="3"></textarea>
        </div>
        <div class="fg"><label>URL de l'avatar</label>
          <input id="pAvatar" type="text">
        </div>
        <div class="fg"><label>Couleur principale</label>
          <div class="color-row">
            <input id="pColor" type="color">
            <div class="presets">
              <span class="dot" style="background:#a71d2a" onclick="setColor('pColor','#a71d2a')"></span>
              <span class="dot" style="background:#1a4fa0" onclick="setColor('pColor','#1a4fa0')"></span>
              <span class="dot" style="background:#1a6b3c" onclick="setColor('pColor','#1a6b3c')"></span>
              <span class="dot" style="background:#8b1a8b" onclick="setColor('pColor','#8b1a8b')"></span>
              <span class="dot" style="background:#c47a1a" onclick="setColor('pColor','#c47a1a')"></span>
              <span class="dot" style="background:#1a7a8b" onclick="setColor('pColor','#1a7a8b')"></span>
            </div>
          </div>
        </div>
        <button class="btn-primary" onclick="saveProfile()">
          <i class="fas fa-save"></i> Enregistrer le profil
        </button>
      </div>

      <!-- Onglet Backup -->
      <div id="tabBackup" class="tab-pane" style="display:none">
        <p class="muted">Exportez ou importez les données JSON de votre liste.</p>
        <div class="btn-row" style="margin-top:16px">
          <button class="btn-primary" onclick="exportData()">
            <i class="fas fa-download"></i> Exporter
          </button>
          <label class="btn-ghost" style="cursor:pointer">
            <i class="fas fa-upload"></i> Importer
            <input type="file" accept=".json" style="display:none" onchange="importData(event)">
          </label>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- Toast notification -->
<div id="toast" class="toast"></div>

<!-- Scripts -->
<script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js"></script>
<script>
  // PHP injects person data once — everything else is handled by script.js
  const SLUG   = <?= json_encode($slug) ?>;
  const PERSON = <?= json_encode($person, JSON_UNESCAPED_UNICODE) ?>;
</script>
<script src="script.js"></script>

</body>
</html>
