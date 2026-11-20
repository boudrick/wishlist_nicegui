from nicegui import ui

HEAD_HTML = '''
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  body {
    font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
    background-color: #f8fafc;
    color: #0f172a;
  }
  .soft-card {
    background-color: #ffffff;
    border-radius: 16px;
    border: 1px solid #e2e8f0;
    transition: all .2s ease;
    color: #0f172a;
  }
  .hover-lift:hover {
    box-shadow: 0 12px 28px -12px rgba(99,102,241,.25);
    border-color: #c7d2fe;
    transform: translateY(-2px);
  }

  /* [MOBILE] Boutons compacts : on garde l'icône, on masque le texte. */
  @media (max-width: 640px) {
    .hide-label-mobile .q-btn__content > span,
    .hide-label-mobile .q-btn__content > .q-btn__content-text {
      display: none !important;
    }
    .hide-label-mobile {
      min-width: 0 !important;
      padding-left: 6px !important;
      padding-right: 6px !important;
    }
  }

  /* ============================================================
     Carte cadeau
     - mobile : titre, photo, description, liens (dans cet ordre)
     - desktop : photo pleine hauteur à gauche, titre/description au
       centre (la zone la plus large), liens à droite.
     - sans photo et/ou sans lien : titre + description pleine largeur.
     ============================================================ */
  .wl-item-body {
    display: flex;
    flex-direction: column;
    gap: .6rem;
    width: 100%;
    flex: 1 1 auto;
    min-height: 0;
  }
  .wl-item-title { order: 1; }
  .wl-item-media { order: 2; }
  .wl-item-desc { order: 3; }
  .wl-item-links {
    order: 4;
    display: flex;
    flex-direction: column;
    gap: .25rem;
    width: 100%;
  }

  .wl-item-media {
    width: 100%;
    border-radius: 12px;
    overflow: hidden;
    background-color: rgba(255, 255, 255, .55);
  }
  .wl-item-media.has-image {
    aspect-ratio: 16 / 10;
    max-height: 240px;
  }
  .wl-item-media.is-emoji {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 72px;
  }
  .wl-item-media .q-img {
    width: 100%;
    height: 100%;
  }
  .wl-item-media img {
    display: block;
    width: 100%;
    height: 100%;
    max-height: 240px;
    object-fit: cover;
  }

  /* Nom du site + prix : jamais tronqués (le nom peut passer à la
     ligne, le prix reste toujours entier). */
  .wl-item-link {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: .2rem .5rem;
    width: 100%;
    border-radius: 8px;
    padding: .25rem .5rem;
    background-color: #ffffff;
  }
  .wl-item-link .site {
    flex: 1 1 auto;
    min-width: 0;
    font-size: .75rem;
    font-weight: 500;
    line-height: 1.3;
    white-space: normal;
    overflow-wrap: anywhere;
    text-decoration: none;
  }
  .wl-item-link .price {
    flex: 0 0 auto;
    font-size: .75rem;
    font-weight: 700;
    white-space: nowrap;
  }

  /* Pied d'actions des longues fenêtres de dialogue : reste visible
     même quand le formulaire défile. */
  .wl-dialog-footer {
    position: sticky;
    bottom: 0;
    z-index: 2;
    background-color: #ffffff;
  }

  /* Statut des offres : bandeau compact pour laisser la part belle
     au cadeau lui-même. */
  .wl-offer-zone {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: .3rem;
    flex: 0 0 auto;
    padding: .35rem .75rem;
    border-top: 1px solid rgba(0, 0, 0, .05);
  }

  @media (min-width: 768px) {
    .wl-item-body {
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: auto 1fr;
      grid-template-areas:
        "title"
        "desc";
      align-items: start;
    }
    .wl-item-body.has-media {
      grid-template-columns: 112px minmax(0, 1fr);
      grid-template-areas:
        "media title"
        "media desc";
    }
    .wl-item-body.has-links {
      grid-template-columns: minmax(0, 1fr) 190px;
      grid-template-areas:
        "title links"
        "desc links";
    }
    .wl-item-body.has-media.has-links {
      grid-template-columns: 112px minmax(0, 1fr) 190px;
      grid-template-areas:
        "media title links"
        "media desc links";
    }

    .wl-item-title { grid-area: title; }
    .wl-item-desc { grid-area: desc; }
    .wl-item-links { grid-area: links; }

    .wl-item-media {
      grid-area: media;
      height: 100%;
      /* La photo occupe toute la hauteur du contenu du cadeau. */
      min-height: 150px;
      max-height: none;
      aspect-ratio: auto;
    }
    .wl-item-media img {
      height: 100%;
      max-height: none;
    }
  }
</style>
'''

DEFAULT_GRADIENT = 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #d946ef 100%)'
DEFAULT_SOLID = '#6366f1'

WISHLIST_COLORS = {
    'indigo':  ('#6366f1', '#8b5cf6'),
    'rose':    ('#f43f5e', '#ec4899'),
    'emerald': ('#10b981', '#14b8a6'),
    'amber':   ('#f59e0b', '#f97316'),
    'sky':     ('#0ea5e9', '#3b82f6'),
    'violet':  ('#8b5cf6', '#d946ef'),
    'slate':   ('#64748b', '#475569'),
    'red':     ('#ef4444', '#dc2626'),
}


def _darken(hex_color, amount=0.45):
    try:
        hex_color = hex_color.lstrip('#')
        r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
        factor = 1 - amount
        r, g, b = (max(0, int(c * factor)) for c in (r, g, b))
        return f'#{r:02x}{g:02x}{b:02x}'
    except Exception:
        return DEFAULT_SOLID


def gradient_css(color_value):
    if not color_value:
        return DEFAULT_GRADIENT
    if color_value.startswith('custom:'):
        hex_color = color_value[7:]
        return f'linear-gradient(135deg, {hex_color}, {_darken(hex_color)})'
    c1, c2 = WISHLIST_COLORS.get(color_value, WISHLIST_COLORS['indigo'])
    return f'linear-gradient(135deg, {c1}, {c2})'


def solid_css(color_value):
    """Couleur solide de secours (fallback si le gradient ne rend pas)."""
    if not color_value:
        return DEFAULT_SOLID
    if color_value.startswith('custom:'):
        return _darken(color_value[7:], 0.3)
    c1, _ = WISHLIST_COLORS.get(color_value, WISHLIST_COLORS['indigo'])
    return c1


def light_bg(color_value, opacity='20'):
    """Retourne la couleur solide avec une opacité hex (ex: 20 = 12%)."""
    return f'{solid_css(color_value)}{opacity}'


def apply_gradient(element, color_value):
    """Applique gradient + fallback solide en !important, séparément."""
    element.style(
        f'background-color: {solid_css(color_value)} !important; '
        f'background-image: {gradient_css(color_value)} !important; '
        'color: #ffffff !important;'
    )


def apply_theme():
    ui.add_head_html(HEAD_HTML)
    ui.colors(primary='#6366f1', secondary='#8b5cf6', accent='#d946ef')


def page_container():
    # [MOBILE] padding réduit sur petit écran
    return ui.column().classes(
        'w-full max-w-6xl mx-auto px-3 md:px-4 py-4 md:py-8 gap-4 md:gap-6'
    )