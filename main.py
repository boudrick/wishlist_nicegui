import json
import secrets
import unicodedata
from nicegui import ui, app
from db import (
    init_db, hash_password, verify_password,
    get_wishlists, get_wishlist, create_wishlist, update_wishlist,
    update_wishlist_link, delete_wishlist, set_wishlist_password,
    get_categories, create_category, update_category, delete_category,
    swap_category_position,
    get_items_with_links, create_item, update_item, delete_item,
    swap_item_position, get_item_counts,
    add_reservation, delete_reservation, delete_reservations_for_item,
    parse_families, get_all_families,
)
from theme import (
    apply_theme, page_container, apply_gradient,
    DEFAULT_GRADIENT, DEFAULT_SOLID, WISHLIST_COLORS,
    solid_css, light_bg,
)

init_db()


# ============================================================
# Helpers
# ============================================================
def render_visual(value, emoji_class='text-3xl', img_class='w-12 h-12'):
    """Affiche soit une image (URL), soit un emoji, soit rien."""
    if not value:
        return
    v = str(value).strip()
    if v.startswith('http://') or v.startswith('https://'):
        # `lazy` : l'image ne se charge que quand elle est visible.
        # `contain` : l'image entière reste visible (aucun recadrage).
        ui.image(v).classes(f'{img_class} rounded-lg flex-shrink-0')\
            .props('lazy fit=contain')
    else:
        ui.label(v).classes(f'{emoji_class} leading-none')


def _is_image_url(value):
    v = str(value or '').strip().lower()
    return v.startswith('http://') or v.startswith('https://')


def _open_wishlist(wid, url, is_internal):
    if is_internal:
        ui.navigate.to(f'/wishlist/{wid}')
    elif url:
        ui.run_javascript(f'window.open({json.dumps(url)}, "_blank")')


def _my_reservations_set():
    return set(app.storage.user.get('my_reservations', []))


def _add_my_reservation(res_id):
    lst = list(app.storage.user.get('my_reservations', []))
    if res_id not in lst:
        lst.append(res_id)
    app.storage.user['my_reservations'] = lst


def _remove_my_reservation(res_id):
    lst = [r for r in app.storage.user.get('my_reservations', [])
           if r != res_id]
    app.storage.user['my_reservations'] = lst


# ============================================================
# Familles / filtre d'accueil
# ============================================================
FAMILY_FILTER_KEY = 'home_family_filter'


def _wishlist_families(w):
    """Familles autorisées à voir une liste ([] = tout le monde)."""
    return parse_families((w or {}).get('families'))


def _family_matches(w, family):
    """Une liste sans famille est visible par toutes les familles."""
    if not family:
        return True
    families = _wishlist_families(w)
    if not families:
        return True
    wanted = family.casefold()
    return any(f.casefold() == wanted for f in families)


def _read_family_filter():
    try:
        return app.storage.user.get(FAMILY_FILTER_KEY) or ''
    except RuntimeError:
        return ''


def _write_family_filter(value):
    try:
        if value:
            app.storage.user[FAMILY_FILTER_KEY] = value
        else:
            app.storage.user.pop(FAMILY_FILTER_KEY, None)
    except RuntimeError:
        pass


def _norm_search(value):
    """Minuscules sans accents, pour une recherche tolérante."""
    text = unicodedata.normalize('NFKD', str(value or '').casefold())
    return ''.join(c for c in text if not unicodedata.combining(c))


def _wishlist_matches_search(w, query):
    if not query:
        return True
    haystack = ' '.join(str(w.get(k) or '') for k in
                        ('title', 'owner', 'description'))
    haystack += ' ' + ' '.join(_wishlist_families(w))
    return query in _norm_search(haystack)


# ============================================================
# Réinitialisation au départ de la page wishlist
# ============================================================
_RESET_JS_ADDED = False


def add_reset_on_leave_js():
    """Installe (une seule fois) le script qui réinitialise l'état
    (mode édition + affichage des offres) quand on quitte la page.

    Au lieu d'un polling par setInterval (400 ms, coûteux en CPU),
    on intercepte directement les navigations SPA : history.pushState /
    replaceState (navigation interne NiceGUI) et popstate (bouton
    retour du navigateur). `pagehide` couvre la fermeture de l'onglet.
    """
    global _RESET_JS_ADDED
    if _RESET_JS_ADDED:
        return
    _RESET_JS_ADDED = True
    ui.add_head_html('''<script>
(function () {
  if (window.__wlResetInstalled) return;
  window.__wlResetInstalled = true;

  function resetIfLeaving() {
    var wid = window.__wlCurrentWid;
    if (!wid || !window.__wlExpectedPath) return;
    try {
      navigator.sendBeacon(
        '/api/reset_wishlist/' + wid);
    } catch (e) {}
    window.__wlCurrentWid = null;
  }

  // Navigation interne (SPA) : on vérifie la destination avant
  // que le routeur ne l'applique.
  function checkTarget(url) {
    if (!url || !window.__wlCurrentWid) return;
    try {
      var resolved = new URL(String(url), window.location.href).pathname;
    } catch (e) {
      return;
    }
    if (resolved !== window.__wlExpectedPath) resetIfLeaving();
  }

  var origPushState = history.pushState.bind(history);
  var origReplaceState = history.replaceState.bind(history);
  history.pushState = function (state, title, url) {
    checkTarget(url);
    return origPushState(state, title, url);
  };
  history.replaceState = function (state, title, url) {
    checkTarget(url);
    return origReplaceState(state, title, url);
  };

  // Bouton retour / avant du navigateur.
  window.addEventListener('popstate', function () {
    setTimeout(function () {
      if (window.__wlCurrentWid &&
          window.location.pathname !== window.__wlExpectedPath) {
        resetIfLeaving();
      }
    }, 0);
  });

  // Fermeture de l'onglet / navigation hors du site.
  window.addEventListener('pagehide', function () {
    if (window.__wlCurrentWid) resetIfLeaving();
  });
})();
</script>''')


@app.get('/api/reset_wishlist/{wid}')
def api_reset_wishlist(wid):
    app.storage.user.pop(f'admin_wl_{wid}', None)
    app.storage.user[f'show_offers_wl_{wid}'] = False
    return 'ok'


# ============================================================
# Header
# ============================================================
def render_header(title='Listes de cadeaux', back_url=None,
                  action_builder=None, header_color=None):
    header = ui.header().classes('shadow-lg px-4 py-3 items-center')
    apply_gradient(header, header_color)

    if back_url:
        btn = ui.button(icon='arrow_back',
                        on_click=lambda: ui.navigate.to(back_url))
        btn.props('flat round')
        btn.style('color: #ffffff !important;')
    else:
        emoji = ui.label('🎁').classes('text-3xl')
        emoji.style('color: #ffffff !important;')

    # [MOBILE] police plus petite sur mobile
    lbl = ui.label(title).classes(
        'text-xl md:text-2xl font-extrabold tracking-tight')
    lbl.style('color: #ffffff !important;')

    ui.space()
    if action_builder:
        action_builder()


# ============================================================
# Dialog mot de passe
# ============================================================
async def prompt_password(title='Mot de passe requis', subtitle=None):
    # [MOBILE] largeur plafonnée + padding réduit
    with ui.dialog() as dialog, ui.card().classes(
        'w-96 max-w-[calc(100vw-2rem)] p-4 md:p-6 rounded-2xl'
    ):
        lbl = ui.label(title).classes('text-lg font-bold mb-2')
        lbl.style('color: #1e293b !important;')
        if subtitle:
            s = ui.label(subtitle).classes('text-sm mb-3 break-words')
            s.style('color: #64748b !important;')
        pwd = ui.input('Mot de passe', password=True,
                       password_toggle_button=True) \
            .props('outlined rounded').classes('w-full')

        def submit_password():
            dialog.submit(pwd.value)

        # La touche Entrée valide le mot de passe.
        pwd.on('keydown.enter', submit_password)

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button('Annuler',
                      on_click=lambda: dialog.submit(None)) \
                .props('flat rounded-lg color=grey-7')
            ui.button('Valider', on_click=submit_password) \
                .props('unelevated rounded-lg color=primary')

        # Le champ est prêt à la saisie dès l'ouverture.
        dialog.on('show', lambda: pwd.run_method('focus'))
    return await dialog


# ============================================================
# Color picker
# ============================================================
def color_picker(initial='indigo'):
    if initial and isinstance(initial, str) and initial.startswith('custom:'):
        initial_key = 'custom'
        initial_custom = initial[7:]
    else:
        initial_key = initial or 'indigo'
        initial_custom = None

    state = {'value': initial_key, 'custom': initial_custom}
    swatches = {}

    def _highlight():
        for k, sw in swatches.items():
            if k == state['value']:
                sw.classes(remove='ring-transparent',
                           add='ring-indigo-500')
            else:
                sw.classes(remove='ring-indigo-500',
                           add='ring-transparent')

    def select(key):
        state['value'] = key
        if key != 'custom':
            state['custom'] = None
        _highlight()

    async def open_custom():
        default_val = state['custom'] or '#6366f1'
        # [MOBILE] largeur plafonnée + padding réduit
        with ui.dialog() as dialog, ui.card().classes(
            'w-96 max-w-[calc(100vw-2rem)] p-4 md:p-6 rounded-2xl'
        ):
            t = ui.label('Couleur personnalisée').classes(
                'text-lg font-bold mb-3')
            t.style('color: #1e293b !important;')
            ci = ui.color_input(
                label='Choisir une couleur', value=default_val,
                preview=True,
            ).props('outlined rounded').classes('w-full')
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Annuler',
                          on_click=lambda: dialog.submit(None)) \
                    .props('flat rounded-lg color=grey-7')
                ui.button('Valider',
                          on_click=lambda: dialog.submit(ci.value)) \
                    .props('unelevated rounded-lg color=primary')
        val = await dialog
        if val:
            state['value'] = 'custom'
            state['custom'] = val
            if 'custom' in swatches:
                swatches['custom'].style(f'background: {val};')
            _highlight()

    def render(size='w-10 h-10'):
        swatches.clear()
        with ui.row().classes('gap-3 flex-wrap items-center'):
            for key in WISHLIST_COLORS.keys():
                c1, c2 = WISHLIST_COLORS[key]
                base = ('ring-indigo-500'
                        if key == state['value'] else 'ring-transparent')
                sw = ui.element('div').classes(
                    f'{size} rounded-full cursor-pointer '
                    f'ring-2 ring-offset-2 {base}'
                ).style(
                    f'background: linear-gradient(135deg, {c1}, {c2});'
                )
                sw.on('click', lambda k=key: select(k))
                swatches[key] = sw

            is_custom_active = (state['value'] == 'custom'
                                and state['custom'])
            bg = (f'background: {state["custom"]};'
                  if is_custom_active else 'background: #e2e8f0;')
            base = ('ring-indigo-500'
                    if state['value'] == 'custom' else 'ring-transparent')
            custom_el = ui.element('div').classes(
                f'{size} rounded-full cursor-pointer '
                f'ring-2 ring-offset-2 {base} '
                'flex items-center justify-center'
            ).style(bg)
            with custom_el:
                if not is_custom_active:
                    ui.icon('palette').classes('text-slate-500')
            custom_el.on('click', open_custom)
            swatches['custom'] = custom_el

    def get_value():
        if state['value'] == 'custom' and state['custom']:
            return f'custom:{state["custom"]}'
        return state['value'] or 'indigo'

    return state, render, get_value


# ============================================================
# Formulaire d'item (layout 3 colonnes)
# ============================================================
def build_item_fields(item=None, categories=None, default_category_id=None):
    item = item or {}
    categories = categories or []

    # Row 1 : catégorie (pleine largeur)
    cat_options = {0: 'Sans catégorie'}
    for c in categories:
        cat_options[c['id']] = c['name']
    initial_cat = item.get('category_id') or default_category_id or 0
    if initial_cat not in cat_options:
        initial_cat = 0

    category_select = ui.select(
        cat_options, value=initial_cat, label='Catégorie',
    ).props('outlined rounded dense').classes('w-full')

    # Row 2 : 3 colonnes responsives
    with ui.element('div').classes(
        # [MOBILE] colonnes réduites, devient 1 colonne sous md
        'grid grid-cols-1 md:grid-cols-[100px_1fr_360px] '
        'gap-3 items-start w-full mt-3'
    ):
        # Col 1 : visual
        with ui.column().classes('gap-1'):
            ul = ui.label('Photo / émoji').classes('text-xs font-semibold')
            ul.style('color: #64748b !important;')
            visual_input = ui.input(
                placeholder='🎁 ou https://...',
                value=item.get('image_url') or '',
            ).props('outlined rounded dense').classes('w-full')

        # Col 2 : titre + desc
        with ui.column().classes('gap-2'):
            sec = ui.label('Cadeau').classes(
                'text-xs font-semibold')
            sec.style('color: #64748b !important;')
            name_input = ui.input('Titre du cadeau',
                                  value=item.get('name', '')) \
                .props('outlined rounded dense').classes('w-full')
            desc_input = ui.textarea(
                'Description (optionnel)',
                value=item.get('description') or '') \
                .props('outlined rounded dense autogrow') \
                .classes('w-full')

        # Col 3 : liens dynamiques
        with ui.column().classes('gap-1'):
            ll = ui.label('Liens').classes('text-xs font-semibold')
            ll.style('color: #64748b !important;')

            links_container = ui.column().classes('w-full gap-2')
            link_rows = []

            def add_link_row(site_val='', url_val='', price_val=None):
                with links_container:
                    with ui.row().classes(
                        'w-full items-center gap-1 no-wrap '
                        'bg-slate-50 rounded-lg p-2'
                    ) as box:
                        # [MOBILE] largeurs minimales réduites
                        site = ui.input(
                            placeholder='Site', value=site_val,
                        ).props('outlined rounded dense') \
                            .classes('flex-1 min-w-[60px]')
                        url = ui.input(
                            placeholder='https://...', value=url_val,
                        ).props('outlined rounded dense') \
                            .classes('flex-[2] min-w-[80px]')
                        price = ui.number(
                            placeholder='€', value=price_val,
                            format='%.2f',
                        ).props('outlined rounded dense') \
                            .classes('w-14 flex-shrink-0')

                        entry = {'site': site, 'url': url,
                                 'price': price, 'box': box}

                        def remove(e=entry):
                            if e in link_rows:
                                link_rows.remove(e)
                            e['box'].delete()

                        ui.button(icon='close', on_click=remove) \
                            .props('flat round dense '
                                   'color=negative size=xs')
                        link_rows.append(entry)

            existing = item.get('links') or []
            if existing:
                for ln in existing:
                    add_link_row(ln.get('site') or '',
                                 ln.get('url') or '',
                                 ln.get('price'))
            else:
                add_link_row()

            ui.button('Ajouter un autre lien', icon='add',
                      on_click=lambda: add_link_row()) \
                .props('flat dense no-caps color=primary') \
                .classes('mt-1')

    # Row 3 : offre options — même ligne de séparation que la zone
    # d'offres des cartes cadeau (border-t rgba(0,0,0,0.05)).
    sep = ui.element('div').classes('w-full border-t my-3')
    sep.style('border-color: rgba(0,0,0,0.05) !important;')

    mo = item.get('max_offers', 1)
    if mo is None:
        initial_mode = 'unlimited'
        initial_qty = 1
    else:
        initial_mode = 'limited'
        initial_qty = int(mo or 1)

    off_lb = ui.label(
        "Combien de fois ce cadeau peut-il être offert ?") \
        .classes('text-xs font-semibold mb-1')
    off_lb.style('color: #64748b !important;')

    with ui.row().classes('items-center gap-3 flex-wrap'):
        quantity_mode = ui.radio(
            {'limited': 'Limité', 'unlimited': 'Illimité'},
            value=initial_mode,
        ).props('inline dense')

        qty_row = ui.row().classes('items-center gap-1')
        with qty_row:
            ql = ui.label('×').classes('text-sm')
            ql.style('color: #475569 !important;')
            qty_input = ui.number(value=initial_qty, min=1, max=99,
                                  format='%d') \
                .props('outlined rounded dense').classes('w-20')

        qty_row.set_visibility(initial_mode == 'limited')
        quantity_mode.on_value_change(
            lambda e: qty_row.set_visibility(e.value == 'limited'))

    def get_values():
        links = []
        for e in link_rows:
            u = (e['url'].value or '').strip()
            if u:
                links.append({
                    'site': (e['site'].value or '').strip() or None,
                    'url': u,
                    'price': e['price'].value,
                })
        mode = quantity_mode.value
        if mode == 'unlimited':
            max_offers = None
        else:
            max_offers = int(qty_input.value or 1)
        return {
            'name': (name_input.value or '').strip(),
            'description': (desc_input.value or '').strip() or None,
            'image_url': (visual_input.value or '').strip() or None,
            'category_id': (category_select.value
                            if category_select.value else None),
            'links': links,
            'max_offers': max_offers,
        }

    return get_values


# ============================================================
# Dialog ajout / édition d'un item
# ============================================================
async def open_add_item_dialog(wid, categories, refresh_fn,
                               default_category_id=None):
    # [MOBILE] en-tête + champs défilent, pied d'actions toujours visible
    with ui.dialog() as dialog, ui.card().classes(
        'wl-dialog-card w-[1150px] max-w-[calc(100vw-1rem)] '
        'p-0 rounded-2xl'
    ):
        with ui.column().classes(
            'wl-dialog-body w-full p-4 md:p-6 gap-0'
        ):
            lbl = ui.label('Ajouter un cadeau').classes(
                'text-lg font-bold mb-4')
            lbl.style('color: #1e293b !important;')

            get_values = build_item_fields(
                categories=categories,
                default_category_id=default_category_id)

        def submit():
            v = get_values()
            if not v['name']:
                ui.notify('Titre requis', type='negative')
                return
            create_item(wid, v['name'], v['description'],
                        v['image_url'], v['category_id'], v['links'],
                        v['max_offers'])
            dialog.submit(True)

        with ui.row().classes(
            'wl-dialog-footer w-full justify-between items-center '
            'p-3 md:px-6 flex-wrap gap-2'
        ):
            ui.button('Annuler',
                      on_click=lambda: dialog.submit(None)) \
                .props('flat rounded-lg color=grey-7')
            ui.button('Ajouter le cadeau', icon='check',
                      on_click=submit) \
                .props('unelevated rounded-lg color=primary')

    if await dialog:
        refresh_fn()
        ui.notify('Cadeau ajouté !', type='positive')


async def open_edit_item_dialog(item, categories, refresh_fn):
    # [MOBILE] en-tête + champs défilent, pied d'actions toujours visible
    with ui.dialog() as dialog, ui.card().classes(
        'wl-dialog-card w-[1150px] max-w-[calc(100vw-1rem)] '
        'p-0 rounded-2xl'
    ):
        with ui.column().classes(
            'wl-dialog-body w-full p-4 md:p-6 gap-0'
        ):
            lbl = ui.label('Modifier le cadeau').classes(
                'text-lg font-bold mb-4')
            lbl.style('color: #1e293b !important;')

            get_values = build_item_fields(
                item=item, categories=categories)

        def save():
            v = get_values()
            if not v['name']:
                ui.notify('Titre requis', type='negative')
                return
            update_item(item['id'], v['name'], v['description'],
                        v['image_url'], v['category_id'], v['links'],
                        v['max_offers'])
            dialog.submit(True)

        with ui.row().classes(
            'wl-dialog-footer w-full justify-between items-center '
            'p-3 md:px-6 flex-wrap gap-2'
        ):
            ui.button('Annuler',
                      on_click=lambda: dialog.submit(None)) \
                .props('flat rounded-lg color=grey-7')
            ui.button('Enregistrer', icon='check', on_click=save) \
                .props('unelevated rounded-lg color=primary')

    if await dialog:
        refresh_fn()
        ui.notify('Cadeau modifié.', type='positive')


# ============================================================
# Dialog ajout de catégorie
# ============================================================
async def open_add_category_dialog(wid, refresh_fn):
    # [MOBILE] largeur plafonnée + padding réduit
    with ui.dialog() as dialog, ui.card().classes(
        'w-[600px] max-w-[calc(100vw-1rem)] p-4 md:p-6 rounded-2xl'
    ):
        lbl = ui.label('Ajouter une catégorie').classes(
            'text-lg font-bold mb-4')
        lbl.style('color: #1e293b !important;')

        with ui.row().classes('w-full items-center gap-2'):
            # [MOBILE] input visuel plus étroit
            visual_in = ui.input(placeholder='🎁 ou https://...') \
                .props('outlined rounded dense') \
                .classes('w-28 md:w-40')
            name_in = ui.input(placeholder='Nom de la catégorie') \
                .props('outlined rounded dense').classes('flex-1')

        def submit():
            n = (name_in.value or '').strip()
            if not n:
                ui.notify('Nom requis', type='negative')
                return
            create_category(wid, n,
                            (visual_in.value or '').strip() or None)
            dialog.submit(True)

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button('Annuler',
                      on_click=lambda: dialog.submit(None)) \
                .props('flat rounded-lg color=grey-7')
            ui.button('Ajouter', icon='check', on_click=submit) \
                .props('unelevated rounded-lg color=primary')

    if await dialog:
        refresh_fn()
        ui.notify('Catégorie ajoutée.', type='positive')


# ============================================================
# Offres / réservations
# ============================================================
def _remove_reservation(res_id, refresh_fn):
    delete_reservation(res_id)
    _remove_my_reservation(res_id)
    refresh_fn()
    ui.notify('Offre supprimée.', type='info')


async def _open_offer_dialog(it, refresh_fn):
    # [MOBILE] largeur plafonnée + padding réduit
    with ui.dialog() as dialog, ui.card().classes(
        'w-96 max-w-[calc(100vw-2rem)] p-4 md:p-6 rounded-2xl'
    ):
        lbl = ui.label("J'offre ce cadeau").classes(
            'text-lg font-bold mb-1')
        lbl.style('color: #1e293b !important;')
        sub = ui.label(f'« {it["name"]} »').classes(
            'text-sm mb-4 break-words')
        sub.style('color: #64748b !important;')

        name_input = ui.input(
            'Votre prénom (optionnel)',
            value=app.storage.user.get('offerer_name', ''),
            placeholder='Ex. Alice',
        ).props('outlined rounded').classes('w-full')

        def confirm():
            name = (name_input.value or '').strip() or None
            if name:
                app.storage.user['offerer_name'] = name
            res_id = add_reservation(it['id'], name)
            _add_my_reservation(res_id)
            dialog.submit(True)

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button('Annuler',
                      on_click=lambda: dialog.submit(None)) \
                .props('flat rounded-lg color=grey-7')
            ui.button('Confirmer', icon='favorite', on_click=confirm) \
                .props('unelevated rounded-lg color=primary')

    if await dialog:
        refresh_fn()
        ui.notify('Merci ! Votre offre est enregistrée.',
                  type='positive')


def render_offer_zone(it, refresh_fn, my_res, is_admin=False):
    # `my_res` est lu une seule fois par page (voir page_body),
    # pas à chaque item rendu.
    reservations = it.get('reservations') or []
    max_offers = it.get('max_offers')
    count = len(reservations)
    i_reserved = any(r['id'] in my_res for r in reservations)

    if max_offers is None:
        text = f'Illimité · {count} offert(s)'
        bg, fg = '#e2e8f0', '#475569'
        available = True
    elif count >= max_offers:
        text = 'Déjà offert ✓'
        bg, fg = '#d1fae5', '#047857'
        available = False
    else:
        text = f'{count}/{max_offers} offert(s)'
        bg, fg = '#fef3c7', '#b45309'
        available = True

    # Bandeau compact : le contenu du cadeau garde la part belle.
    with ui.row().classes('wl-offer-zone w-full'):
        badge = ui.label(text).classes(
            'text-[11px] font-semibold px-2 py-0.5 rounded-full')
        badge.style(f'background-color: {bg} !important; '
                    f'color: {fg} !important;')

        if reservations:
            par = ui.label('Offert par').classes(
                'text-[11px] hidden sm:inline')
            par.style('color: #475569 !important;')
            for r in reservations:
                nm = r['offerer_name'] or 'anonyme'
                with ui.element('div').classes(
                    'inline-flex items-center bg-white/80 '
                    'rounded-full pl-1.5 pr-0.5 py-0'
                ):
                    nl = ui.label(nm).classes(
                        'text-[11px] break-all max-w-[110px]')
                    nl.style('color: #475569 !important;')
                    ui.button(
                        icon='close',
                        on_click=lambda rid=r['id']:
                            _remove_reservation(rid, refresh_fn),
                    ).props('flat round dense size=xs color=negative')

        ui.space()

        if available and not i_reserved and not is_admin:
            ui.button(
                "J'offre", icon='favorite',
                on_click=lambda: _open_offer_dialog(it, refresh_fn),
            ).props('unelevated dense no-caps rounded-full '
                    'color=primary size=sm')


# ============================================================
# Rendu d'un item
# ============================================================
def render_items_grid(items, is_admin, refresh_fn, color,
                      categories, move_item, wid, show_offers, my_res):
    # Liste sur une seule colonne : chaque cadeau occupe toute la
    # largeur, et sa hauteur ne dépend que de son propre contenu
    # (pas de `auto-rows-fr`, qui égalisait toutes les cartes).
    with ui.element('div').classes(
        'flex flex-col gap-3 md:gap-4 w-full'
    ):
        for idx, it in enumerate(items):
            render_item(it, is_admin, refresh_fn, color, categories,
                        move_item, idx == 0,
                        idx == len(items) - 1, wid, show_offers, my_res)


def render_item(it, is_admin, refresh_fn, color, categories,
                move_item, is_first, is_last, wid, show_offers, my_res):
    item_bg = (
        f'radial-gradient(circle at center, '
        f'{light_bg(color, "90")} 0%, '
        f'{light_bg(color, "30")} 100%)'
    )

    with ui.element('div').classes(
        'wl-item-card rounded-2xl flex flex-col overflow-hidden'
    ).style(
        f'background-color: {light_bg(color, "40")} !important; '
        f'background-image: {item_bg} !important; '
        'box-shadow: 0 1px 3px rgba(0,0,0,0.04);'
    ):
        # --- Barre d'actions (admin uniquement) ---
        if is_admin:
            with ui.row().classes(
                'w-full items-center justify-between gap-1 px-2 pt-1 pb-0 '
                'border-b border-black/5 flex-wrap'
            ):
                with ui.row().classes('gap-0 items-center flex-wrap'):
                    b_up = ui.button(
                        icon='arrow_upward', text='Monter',
                        on_click=lambda: move_item(it['id'], 'up'))
                    b_up.props('flat dense no-caps color=primary size=sm')
                    # [MOBILE] texte masqué sur mobile
                    b_up.classes('hide-label-mobile')
                    b_up.set_enabled(not is_first)
                    b_dn = ui.button(
                        icon='arrow_downward', text='Descendre',
                        on_click=lambda: move_item(it['id'], 'down'))
                    b_dn.props('flat dense no-caps color=primary size=sm')
                    b_dn.classes('hide-label-mobile')
                    b_dn.set_enabled(not is_last)
                    b_ed = ui.button(
                        icon='edit', text='Modifier',
                        on_click=lambda item=it:
                            open_edit_item_dialog(item, categories,
                                                  refresh_fn))
                    b_ed.props('flat dense no-caps color=primary size=sm')
                    b_ed.classes('hide-label-mobile')
                b_del = ui.button(
                    icon='delete', text='Supprimer',
                    on_click=lambda i=it['id']:
                        _delete_and_refresh(i, refresh_fn))
                b_del.props('flat dense no-caps color=negative size=sm')
                b_del.classes('hide-label-mobile')

        # --- Contenu principal ---
        # L'ordre du DOM est : titre, photo, description, liens.
        # C'est l'ordre mobile demandé (photo entre titre et description) ;
        # sur desktop, la grille CSS (.wl-item-body) replace la photo à
        # gauche et les liens à droite, la photo prenant toute la hauteur.
        has_media = bool(it.get('image_url'))
        has_links = bool(it.get('links'))
        body_classes = 'p-3 md:p-4 wl-item-body'
        if has_media:
            body_classes += ' has-media'
        if has_links:
            body_classes += ' has-links'

        with ui.element('div').classes(body_classes):
            t = ui.label(it['name']).classes(
                'wl-item-title text-base font-bold break-words leading-tight')
            t.style('color: #1e293b !important;')

            if has_media:
                visual = str(it['image_url']).strip()
                if _is_image_url(visual):
                    with ui.element('div').classes(
                        'wl-item-media has-image'
                    ):
                        ui.image(visual).props('lazy fit=contain') \
                            .classes('w-full h-full')
                else:
                    with ui.element('div').classes(
                        'wl-item-media is-emoji'
                    ):
                        ui.label(visual).classes('text-5xl leading-none')

            if it.get('description'):
                d = ui.label(it['description']).classes(
                    'wl-item-desc text-sm break-words leading-snug')
                d.style('color: #334155 !important;')

            if has_links:
                with ui.column().classes('wl-item-links'):
                    for link in it['links']:
                        with ui.element('div').classes('wl-item-link'):
                            lk = ui.link(
                                link.get('site') or link['url'],
                                link['url'], new_tab=True,
                            ).classes('site')
                            lk.style('color: #4338ca !important;')
                            if link.get('price') is not None:
                                p = ui.label(
                                    f"{link['price']:.0f}€"
                                ).classes('price')
                                p.style('color: #059669 !important;')

        # --- Zone offres : masquée en mode édition (anti-spoiler),
        #     sinon contrôlée par le toggle « Afficher/Masquer ». ---
        if show_offers and not is_admin:
            render_offer_zone(it, refresh_fn, my_res, is_admin)


def _delete_and_refresh(item_id, refresh_fn):
    delete_item(item_id)
    refresh_fn()
    ui.notify('Cadeau supprimé.', type='info')


# ============================================================
# En-tête de catégorie
# ============================================================
def render_category_header_editable(cat, idx, total, move_cat,
                                    del_cat, refresh_fn, color):
    # [MOBILE] flex-wrap + padding réduit
    with ui.row().classes(
        'w-full items-center gap-2 rounded-2xl px-3 md:px-4 py-2 md:py-3 '
        'mt-4 flex-wrap'
    ).style(
        'background-color: #ffffff !important; '
        'background-image: radial-gradient(circle at center, '
        '#ffffff 0%, #f1f5f9 100%) !important; '
        'box-shadow: 0 1px 3px rgba(0,0,0,0.04);'
    ):
        # [MOBILE] input visuel plus étroit
        visual_in = ui.input(
            value=cat.get('emoji') or '', placeholder='🎁',
        ).props('outlined rounded dense').classes('w-20 md:w-24')
        name_in = ui.input(value=cat['name']) \
            .props('outlined rounded dense') \
            .classes('flex-1 min-w-[120px]')

        b_up = ui.button(icon='arrow_upward',
                         on_click=lambda: move_cat(cat['id'], 'up'))
        b_up.props('flat round dense color=primary size=sm')
        b_up.set_enabled(idx > 0)

        b_dn = ui.button(icon='arrow_downward',
                         on_click=lambda: move_cat(cat['id'], 'down'))
        b_dn.props('flat round dense color=primary size=sm')
        b_dn.set_enabled(idx < total - 1)

        def save():
            n = (name_in.value or '').strip()
            if not n:
                ui.notify('Nom requis', type='negative')
                return
            update_category(cat['id'], n,
                            (visual_in.value or '').strip() or None)
            refresh_fn()
            ui.notify('Catégorie modifiée.', type='positive')

        ui.button(icon='check', on_click=save) \
            .props('flat round dense color=primary size=sm')
        ui.button(icon='delete',
                  on_click=lambda: del_cat(cat['id'])) \
            .props('flat round dense color=negative size=sm')


def render_category_header_public(cat, color_solid):
    with ui.row().classes('items-center gap-2 mt-4'):
        render_visual(cat.get('emoji'), emoji_class='text-2xl',
                      img_class='w-8 h-8')
        h = ui.label(cat['name']).classes(
            'text-lg font-semibold break-words min-w-0')
        h.style(f'color: {color_solid} !important;')


# ============================================================
# Déverrouillage / édition d'une liste
# (partagé entre l'accueil et la page détail)
# ============================================================
async def unlock_wishlist_admin(wid):
    """Autorise l'édition d'une liste après mot de passe.

    Un accès admin global (page /admin) ou un déverrouillage déjà
    effectué pour cette liste dispense de ressaisir le mot de passe.
    Retourne la liste à jour, ou None si l'accès est refusé.
    """
    w = get_wishlist(wid)
    if not w:
        return None
    try:
        already = app.storage.user.get(f'admin_wl_{wid}', False)
    except RuntimeError:
        already = False
    if already or _admin_unlocked():
        return w

    if w.get('password'):
        pwd = await prompt_password()
        if not pwd:
            return None
        if not verify_password(pwd, w['password']):
            ui.notify('Mot de passe incorrect.', type='negative')
            return None
    else:
        pwd = await prompt_password(
            "Créer le mot de passe d'édition",
            "Cette liste n'a pas encore de mot de passe. "
            "Choisissez-en un : il sera demandé pour la modifier.")
        if not pwd:
            return None
        set_wishlist_password(wid, hash_password(pwd))
        w = get_wishlist(wid) or w
        ui.notify('Mot de passe défini, mode édition activé.',
                  type='positive')

    app.storage.user[f'admin_wl_{wid}'] = True
    return w


async def open_edit_wishlist_dialog(w):
    """Paramètres d'une liste : titre, description, type, visuel,
    couleur, familles autorisées et mot de passe.

    Retourne 'saved', 'deleted' ou None (annulé). L'appelant décide
    de la navigation / du rafraîchissement.
    """
    wid = w['id']
    existing_families = _wishlist_families(w)
    known_families = sorted(
        set(get_all_families()) | set(existing_families),
        key=str.casefold)

    with ui.dialog() as dialog, ui.card().classes(
        'wl-dialog-card w-[620px] max-w-[calc(100vw-1rem)] '
        'p-0 rounded-2xl'
    ):
        with ui.column().classes(
            'wl-dialog-body w-full p-4 md:p-6 gap-0'
        ):
            t0 = ui.label('Modifier la liste').classes(
                'text-lg font-bold mb-4')
            t0.style('color: #1e293b !important;')

            t = ui.input('Titre', value=w['title']) \
                .props('outlined rounded').classes('w-full')
            d = ui.textarea('Description',
                            value=w.get('description') or '') \
                .props('outlined rounded autogrow').classes('w-full mt-3')

            lb_type = ui.label('Type de liste').classes(
                'text-sm font-semibold mt-4 mb-1')
            lb_type.style('color: #334155 !important;')
            kind = ui.radio(
                {'internal': 'Créer sur ce site',
                 'external': 'Lien vers un autre site'},
                value=w.get('type') or 'internal',
            ).props('inline')

            u = ui.input('URL (si externe)',
                         value=w.get('url') or '',
                         placeholder='https://...') \
                .props('outlined rounded').classes('w-full mt-2')
            u.set_visibility((w.get('type') or 'internal') == 'external')
            kind.on_value_change(
                lambda e: u.set_visibility(e.value == 'external'))

            lb_e = ui.label('Émoji ou URL d\'image').classes(
                'text-sm font-semibold mt-4 mb-2')
            lb_e.style('color: #334155 !important;')
            visual_in = ui.input(placeholder='🎁 ou https://...',
                                 value=w.get('emoji') or '') \
                .props('outlined rounded').classes('w-full')

            lb = ui.label('Couleur').classes(
                'text-sm font-semibold mt-4 mb-2')
            lb.style('color: #334155 !important;')
            _, render_picker, get_color = color_picker(
                w.get('color') or 'indigo')
            render_picker(size='w-8 h-8')

            # --- Familles autorisées ---
            ui.separator().classes('my-4')
            with ui.row().classes('items-center gap-2'):
                ui.icon('family_restroom').classes('text-indigo-500')
                lb_f = ui.label('Familles autorisées').classes(
                    'text-sm font-semibold')
                lb_f.style('color: #334155 !important;')
            hint_f = ui.label(
                'Seules ces familles verront la liste sur l’accueil. '
                'Aucune sélection = visible par tout le monde. '
                'Tapez un nom puis Entrée pour créer une nouvelle famille.'
            ).classes('text-xs mb-3 break-words')
            hint_f.style('color: #64748b !important;')
            family_select = ui.select(
                known_families, multiple=True, value=existing_families,
                label='Familles', new_value_mode='add-unique',
            ).props('outlined rounded use-chips clearable') \
                .classes('w-full')

            # --- Mot de passe d'édition (comme à la création) ---
            ui.separator().classes('my-4')
            lb_pw = ui.label("Mot de passe d'édition").classes(
                'text-sm font-semibold mb-2')
            lb_pw.style('color: #334155 !important;')
            if w.get('password'):
                st_pw = ui.label(
                    'Un mot de passe est défini. Laissez les champs '
                    'vides pour le conserver.')
            else:
                st_pw = ui.label(
                    "Aucun mot de passe défini : la personne pourra en "
                    "choisir un en passant en mode édition.")
            st_pw.classes('text-xs mb-3 break-words')
            st_pw.style('color: #64748b !important;')

            new_pwd = ui.input('Nouveau mot de passe', password=True,
                               password_toggle_button=True) \
                .props('outlined rounded').classes('w-full')
            new_pwd2 = ui.input('Confirmer le nouveau mot de passe',
                                password=True,
                                password_toggle_button=True) \
                .props('outlined rounded').classes('w-full mt-3')
            pw_hint = ui.label('').classes('text-xs h-4 mt-1')

            def check_pw_match(e=None):
                v1 = new_pwd.value or ''
                v2 = new_pwd2.value or ''
                if not v2:
                    pw_hint.text = ''
                    pw_hint.style('color: transparent;')
                elif v1 == v2:
                    pw_hint.text = '✓ Les mots de passe correspondent'
                    pw_hint.style('color: #10b981 !important;')
                else:
                    pw_hint.text = '✗ Les mots de passe ne correspondent pas'
                    pw_hint.style('color: #ef4444 !important;')

            new_pwd.on_value_change(check_pw_match)
            new_pwd2.on_value_change(check_pw_match)

            async def delete_wishlist_dialog():
                with ui.dialog() as confirm, ui.card().classes(
                    'w-96 max-w-[calc(100vw-2rem)] p-4 md:p-6 rounded-2xl'
                ):
                    t1 = ui.label('Supprimer cette liste ?').classes(
                        'text-lg font-bold')
                    t1.style('color: #1e293b !important;')
                    s1 = ui.label('Cette action est irréversible.') \
                        .classes('text-sm mb-4')
                    s1.style('color: #64748b !important;')
                    with ui.row().classes('w-full justify-end gap-2'):
                        ui.button('Annuler',
                                  on_click=lambda:
                                      confirm.submit(False)) \
                            .props('flat rounded-lg color=grey-7')
                        ui.button('Supprimer',
                                  on_click=lambda:
                                      confirm.submit(True)) \
                            .props('unelevated rounded-lg color=negative')
                if await confirm:
                    delete_wishlist(wid)
                    app.storage.user.pop(f'admin_wl_{wid}', None)
                    dialog.submit('deleted')

            def save():
                title_value = (t.value or '').strip()
                if not title_value:
                    ui.notify('Titre requis', type='negative')
                    return
                kind_value = kind.value or 'internal'
                url_value = (u.value or '').strip()
                if kind_value == 'external':
                    if not url_value:
                        ui.notify(
                            'URL requise pour une redirection externe',
                            type='negative')
                        return
                    if not (url_value.startswith('http://')
                            or url_value.startswith('https://')):
                        ui.notify(
                            'URL invalide (http:// ou https:// attendu)',
                            type='negative')
                        return
                else:
                    url_value = None

                p1 = new_pwd.value or ''
                p2 = new_pwd2.value or ''
                if p1 or p2:
                    if not p1:
                        ui.notify('Nouveau mot de passe requis',
                                  type='negative')
                        return
                    if p1 != p2:
                        ui.notify('Les mots de passe ne correspondent pas',
                                  type='negative')
                        return

                update_wishlist(
                    wid, title_value, title_value,
                    (d.value or '').strip() or None,
                    url_value,
                    get_color(),
                    (visual_in.value or '').strip() or None,
                    families=family_select.value)
                update_wishlist_link(wid, kind_value, url_value)
                if p1:
                    set_wishlist_password(wid, hash_password(p1))
                dialog.submit('saved')

        # Pied toujours visible : le corps du formulaire défile.
        with ui.row().classes(
            'wl-dialog-footer w-full justify-between items-center '
            'p-3 md:px-6 flex-wrap gap-2'
        ):
            ui.button('Supprimer', icon='delete',
                      on_click=delete_wishlist_dialog) \
                .props('flat rounded-lg color=negative')
            with ui.row().classes('gap-2 flex-wrap'):
                ui.button('Annuler',
                          on_click=lambda: dialog.submit(None)) \
                    .props('flat rounded-lg color=grey-7')
                ui.button('Enregistrer', icon='check', on_click=save) \
                    .props('unelevated rounded-lg color=primary')

    result = await dialog
    return result if result in ('saved', 'deleted') else None


# ============================================================
# Page d'accueil
# ============================================================
@ui.page('/')
def home():
    apply_theme()
    add_reset_on_leave_js()
    wishlists = get_wishlists()

    selected_family = {'value': _read_family_filter()}
    known_families = get_all_families()
    if (selected_family['value']
            and selected_family['value'] not in known_families):
        # La famille mémorisée n'existe plus (liste modifiée/supprimée).
        selected_family['value'] = ''
        _write_family_filter('')

    search_input = None

    def select_family(value):
        selected_family['value'] = value
        _write_family_filter(value)
        family_bar.refresh()
        lists_panel.refresh()

    def reset_filters():
        selected_family['value'] = ''
        _write_family_filter('')
        if search_input is not None:
            search_input.value = ''
        family_bar.refresh()
        lists_panel.refresh()

    async def edit_list(w):
        # Le crayon est visible par tous, mais l'édition reste protégée
        # par le mot de passe de la liste (ou l'accès admin global).
        unlocked = await unlock_wishlist_admin(w['id'])
        if not unlocked:
            return
        result = await open_edit_wishlist_dialog(unlocked)
        if result:
            family_bar.refresh()
            lists_panel.refresh()
            if result == 'saved':
                ui.notify('Liste modifiée.', type='positive')
            elif result == 'deleted':
                ui.notify('Liste supprimée.', type='info')

    @ui.refreshable
    def family_bar():
        families_now = get_all_families()
        if (selected_family['value']
                and selected_family['value'] not in families_now):
            selected_family['value'] = ''
            _write_family_filter('')

        if not families_now:
            # Aucune famille définie : le filtre n'aurait que « Toutes ».
            return

        with ui.row().classes('w-full items-center gap-2 flex-wrap'):
            ic = ui.icon('family_restroom').classes('text-indigo-500')
            ic.tooltip('Filtrer les listes par famille')
            lbl = ui.label('Familles :').classes('text-sm font-semibold')
            lbl.style('color: #334155 !important;')

            options = [('', 'Toutes')] + [(f, f) for f in families_now]
            for value, label in options:
                active = selected_family['value'] == value
                b = ui.button(
                    label,
                    on_click=lambda v=value: select_family(v),
                )
                if active:
                    b.props('unelevated no-caps rounded-full '
                            'color=primary size=sm')
                else:
                    b.props('flat no-caps rounded-full '
                            'color=primary size=sm')

    @ui.refreshable
    def lists_panel():
        all_lists = get_wishlists()
        counts = get_item_counts()
        query = _norm_search(search_input.value if search_input else '')
        selected = selected_family['value']
        visible = [
            w for w in all_lists
            if _family_matches(w, selected)
            and _wishlist_matches_search(w, query)
        ]

        if not visible:
            with ui.column().classes(
                'w-full items-center justify-center py-14 gap-3 px-2'
            ):
                ui.icon('search_off').classes('text-6xl text-slate-300')
                t = ui.label('Aucune liste ne correspond à ce filtre') \
                    .classes('text-lg font-semibold text-center')
                t.style('color: #334155 !important;')
                s = ui.label(
                    'Essayez une autre famille ou effacez la recherche.'
                ).classes('text-sm text-center max-w-md')
                s.style('color: #64748b !important;')
                ui.button('Réinitialiser les filtres', icon='filter_alt_off',
                          on_click=reset_filters) \
                    .props('flat no-caps rounded-full color=primary')
            return

        with ui.element('div').classes(
            'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 '
            'gap-4 md:gap-6 w-full auto-rows-fr'
        ):
            for w in visible:
                render_wishlist_card(
                    w, counts.get(w['id'], 0), edit_list)

    with page_container():
        # [MOBILE] titre + boutons adaptatifs
        with ui.row().classes(
            'w-full items-center justify-between mt-4 mb-2 gap-3 flex-wrap'
        ):
            sec = ui.label('Listes de cadeaux').classes(
                'text-2xl md:text-3xl font-extrabold')
            sec.style('color: #1e293b !important;')

            with ui.row().classes('gap-3 items-center flex-wrap'):
                b2 = ui.button('Créer ma liste', icon='add',
                               on_click=lambda: ui.navigate.to('/add'))
                b2.props('unelevated no-caps rounded-full color=primary')

        if not wishlists:
            with ui.column().classes(
                'w-full items-center justify-center py-16 gap-4 px-2'
            ):
                ui.icon('inventory_2').classes('text-6xl text-slate-300')
                t = ui.label('Aucune liste pour le moment').classes(
                    'text-xl font-semibold text-center')
                t.style('color: #334155 !important;')
                s = ui.label('Créez votre première liste ou '
                             'chargez un exemple pour explorer.') \
                    .classes('text-center max-w-md')
                s.style('color: #64748b !important;')
                with ui.row().classes('gap-3 flex-wrap justify-center'):
                    ui.button('Créer ma première liste', icon='add',
                              on_click=lambda: ui.navigate.to('/add')) \
                        .props('unelevated rounded-full color=primary '
                               'no-caps')
            return

        # Barre de filtres : recherche libre + familles.
        with ui.element('div').classes(
            'soft-card w-full px-3 md:px-4 py-3 mb-1'
        ):
            with ui.row().classes('w-full items-center gap-2 flex-wrap'):
                search_input = ui.input(
                    placeholder='Rechercher une liste (titre, famille…)',
                    on_change=lambda e: lists_panel.refresh(),
                ).props('outlined rounded dense clearable debounce=250 '
                        'prepend-icon=search') \
                    .classes('w-full md:max-w-sm')
            family_bar()
        lists_panel()


def render_wishlist_card(w, item_count, on_edit):
    is_internal = w['type'] == 'internal'
    color = w.get('color') or 'indigo'

    card = ui.element('div').classes(
        'soft-card hover-lift overflow-hidden flex flex-col '
        'h-full relative'
    )

    with card:
        # Zone cliquable séparée du crayon : un clic sur l'icône ne
        # déclenche donc pas l'ouverture de la liste.
        with ui.element('div').classes(
            'flex flex-col h-full w-full cursor-pointer'
        ) as clickable:
            clickable.on(
                'click',
                lambda wid=w['id'], url=w['url'], internal=is_internal:
                    _open_wishlist(wid, url, internal))

            band = ui.element('div').classes(
                'px-4 md:px-5 py-5 md:py-6 pr-12 md:pr-14 '
                'flex items-center gap-3'
            )
            apply_gradient(band, color)
            with band:
                render_visual(w.get('emoji'), emoji_class='text-4xl',
                              img_class='w-12 h-12')
                t = ui.label(w['title']).classes(
                    'text-lg font-bold line-clamp-1 min-w-0 flex-1')
                t.style('color: #ffffff !important;')

            with ui.column().classes('p-4 flex-1 justify-end gap-2'):
                # Familles autorisées à voir la liste.
                with ui.row().classes('gap-1 flex-wrap'):
                    families = _wishlist_families(w)
                    if families:
                        for name in families:
                            ui.label(name).classes(
                                'text-[10px] font-medium px-2 py-0.5 '
                                'rounded-full bg-indigo-50 text-indigo-600'
                            )
                    else:
                        ui.label('Toutes les familles').classes(
                            'text-[10px] font-medium px-2 py-0.5 '
                            'rounded-full bg-slate-100 text-slate-500'
                        )

                with ui.row().classes(
                    'w-full items-center justify-between'
                ):
                    if is_internal:
                        m = ui.label(
                            f'{item_count} cadeau'
                            f'{"x" if item_count != 1 else ""}'
                        ).classes('text-xs font-medium')
                        m.style('color: #94a3b8 !important;')
                    else:
                        m = ui.label("Lien vers un autre site").classes(
                            'text-xs font-medium')
                        m.style('color: #94a3b8 !important;')
                    ui.icon('arrow_forward' if is_internal
                            else 'open_in_new').classes('text-indigo-500')

        edit_btn = ui.button(icon='edit', on_click=lambda: on_edit(w))
        edit_btn.props(
            'flat round dense size=sm aria-label="Modifier la liste"')
        edit_btn.classes('absolute top-2.5 right-2.5 z-20')
        edit_btn.style(
            'color: #1e293b !important; '
            'background-color: rgba(255, 255, 255, .92) !important; '
            'box-shadow: 0 1px 4px rgba(15, 23, 42, .25) !important;')
        edit_btn.tooltip('Modifier les paramètres de la liste')


# ============================================================
# Création d'une liste
# ============================================================
@ui.page('/add')
def add_page():
    apply_theme()
    add_reset_on_leave_js()
    render_header('Nouvelle liste', back_url='/')

    color_state, render_picker, get_color = color_picker('indigo')
    known_families = get_all_families()

    with page_container():
        with ui.element('div').classes(
            'soft-card p-4 md:p-6 lg:p-8 max-w-2xl mx-auto w-full'
        ):
            t = ui.label('Créer une liste').classes(
                'text-xl md:text-2xl font-bold')
            t.style('color: #1e293b !important;')
            s = ui.label('Remplissez les informations ci-dessous.') \
                .classes('mb-6')
            s.style('color: #64748b !important;')

            title = ui.input('Titre de la liste',
                             placeholder='Liste de Audrick') \
                .props('outlined rounded').classes('w-full')
            description = ui.textarea(
                'Description (optionnel)',
                placeholder='Quelques mots sur cette liste...',
            ).props('outlined rounded autogrow').classes('w-full mt-4')

            ui.separator().classes('my-6')

            # --- Visual : emoji ou URL d'image ou rien ---
            lb_v = ui.label('Émoji ou URL d\'image (optionnel)') \
                .classes('text-sm font-semibold mb-2')
            lb_v.style('color: #334155 !important;')
            visual_in = ui.input(
                placeholder='🎁 ou https://...') \
                .props('outlined rounded').classes('w-full')

            ui.separator().classes('my-6')

            # --- Familles autorisées à voir la liste ---
            with ui.row().classes('items-center gap-2'):
                ui.icon('family_restroom').classes('text-indigo-500')
                lb_f = ui.label('Familles autorisées').classes(
                    'text-sm font-semibold')
                lb_f.style('color: #334155 !important;')
            hint_f = ui.label(
                'Choisissez les familles qui peuvent voir cette liste. '
                'Aucune sélection = visible par tout le monde. '
                'Tapez un nom puis Entrée pour créer une nouvelle famille.'
            ).classes('text-xs mb-3 break-words')
            hint_f.style('color: #64748b !important;')
            family_select = ui.select(
                known_families, multiple=True, value=[],
                label='Familles', new_value_mode='add-unique',
            ).props('outlined rounded use-chips clearable') \
                .classes('w-full')

            ui.separator().classes('my-6')

            lb2 = ui.label('Couleur de la liste').classes(
                'text-sm font-semibold mb-3')
            lb2.style('color: #334155 !important;')
            render_picker()

            ui.separator().classes('my-6')
            lb = ui.label('Type de liste').classes(
                'text-sm font-semibold mb-2')
            lb.style('color: #334155 !important;')
            wtype = ui.radio(
                {'internal': 'Créer sur ce site',
                 'external': 'Lien vers un autre site'},
                value='internal',
            ).props('inline')
            url_input = ui.input('URL du site externe',
                                 placeholder='https://...') \
                .props('outlined rounded').classes('w-full mt-3')
            url_input.set_visibility(False)
            wtype.on_value_change(
                lambda e: url_input.set_visibility(
                    e.value == 'external'))

            ui.separator().classes('my-6')
            with ui.row().classes('items-center gap-2'):
                ui.icon('lock').classes('text-indigo-500')
                lb3 = ui.label('Mot de passe administrateur').classes(
                    'text-sm font-semibold')
                lb3.style('color: #334155 !important;')
            hint = ui.label('Nécessaire pour modifier la liste plus tard.') \
                .classes('text-xs mb-3')
            hint.style('color: #64748b !important;')

            password = ui.input('Mot de passe', password=True,
                                password_toggle_button=True) \
                .props('outlined rounded').classes('w-full')
            password2 = ui.input('Confirmer le mot de passe',
                                 password=True,
                                 password_toggle_button=True) \
                .props('outlined rounded').classes('w-full mt-3')
            match_hint = ui.label('').classes('text-xs h-4 mt-1')

            def check_match(e=None):
                if not password2.value:
                    match_hint.text = ''
                    match_hint.style('color: transparent;')
                elif password.value == password2.value:
                    match_hint.text = '✓ Les mots de passe correspondent'
                    match_hint.style('color: #10b981 !important;')
                else:
                    match_hint.text = \
                        '✗ Les mots de passe ne correspondent pas'
                    match_hint.style('color: #ef4444 !important;')

            password.on_value_change(check_match)
            password2.on_value_change(check_match)

            def submit():
                if not title.value:
                    ui.notify('Titre requis', type='negative')
                    return
                if wtype.value == 'external' and not url_input.value:
                    ui.notify('URL requise pour un lien externe',
                              type='negative')
                    return
                if not password.value:
                    ui.notify('Mot de passe requis', type='negative')
                    return
                if password.value != password2.value:
                    ui.notify('Les mots de passe ne correspondent pas',
                              type='negative')
                    return
                wid = create_wishlist(
                    title.value.strip(),
                    title.value.strip(),
                    wtype.value,
                    url_input.value.strip()
                    if wtype.value == 'external' else None,
                    description.value.strip() or None,
                    hash_password(password.value),
                    get_color(),
                    (visual_in.value or '').strip() or None,
                    families=family_select.value,
                )
                app.storage.user[f'admin_wl_{wid}'] = True
                ui.notify('Liste créée ! Mode édition activé.',
                          type='positive')
                ui.navigate.to(f'/wishlist/{wid}')

            ui.button('Créer la liste', icon='check', on_click=submit) \
                .props('unelevated rounded-full color=primary') \
                .classes('w-full mt-6 py-3 text-base font-semibold')


# ============================================================
# Administration — accès masqué par /admin et protégé par mot de
# passe (aucun lien dans l'interface, page en noindex)
# ============================================================
ADMIN_ACCESS_PASSWORD = 'C4deaux'
ADMIN_UNLOCK_KEY = 'admin_site_unlocked'


def _admin_unlocked():
    """Déverrouillé pour l'onglet courant uniquement : aucun cookie
    persistant, le mot de passe est redemandé à la prochaine
    ouverture du site."""
    try:
        return bool(app.storage.tab.get(ADMIN_UNLOCK_KEY, False))
    except RuntimeError:
        # Pas d'onglet identifié (ex. rendu hors session) : verrouillé.
        return False


def _check_admin_password(value):
    """Comparaison en temps constant (les .encode() évitent le
    TypeError de compare_digest sur des caractères non ASCII)."""
    return secrets.compare_digest(
        (value or '').encode('utf-8'),
        ADMIN_ACCESS_PASSWORD.encode('utf-8'))


def render_admin_lock_screen(on_unlock):
    """Écran de saisie du mot de passe d'accès à /admin."""
    with page_container():
        with ui.element('div').classes(
            'soft-card w-full max-w-md mx-auto mt-8 p-6 md:p-8'
        ):
            with ui.row().classes('items-center gap-3 mb-2'):
                ic = ui.icon('lock').classes('text-3xl')
                ic.style('color: #6366f1 !important;')
                t = ui.label("Accès à l'administration").classes(
                    'text-xl font-bold break-words')
                t.style('color: #1e293b !important;')
            s = ui.label(
                "Cette page est protégée. Saisissez le mot de passe "
                "d'accès pour continuer.").classes(
                    'text-sm mb-4 break-words')
            s.style('color: #64748b !important;')

            pwd = ui.input('Mot de passe', password=True,
                           password_toggle_button=True) \
                .props('outlined rounded autofocus') \
                .classes('w-full')

            def submit():
                if _check_admin_password(pwd.value):
                    app.storage.tab[ADMIN_UNLOCK_KEY] = True
                    ui.notify('Accès autorisé.', type='positive')
                    on_unlock()
                else:
                    pwd.value = ''
                    ui.notify('Mot de passe incorrect.', type='negative')

            # La touche Entrée valide le mot de passe.
            pwd.on('keydown.enter', submit)

            ui.button('Entrer', icon='login', on_click=submit) \
                .props('unelevated rounded-full color=primary') \
                .classes('w-full mt-4 py-3 text-base font-semibold')

            with ui.row().classes('w-full justify-center mt-2'):
                ui.button('Retour au site', icon='arrow_back',
                          on_click=lambda: ui.navigate.to('/')) \
                    .props('flat no-caps rounded-full color=grey-7')


@ui.page('/admin')
def admin_page():
    apply_theme()
    # Page réservée : pas d'indexation par les moteurs de recherche.
    ui.add_head_html('<meta name="robots" content="noindex, nofollow">')

    @ui.refreshable
    def admin_root():
        if not _admin_unlocked():
            render_admin_lock_screen(admin_root.refresh)
            return

        def lock():
            app.storage.tab.pop(ADMIN_UNLOCK_KEY, None)
            ui.notify('Administration verrouillée.', type='info')
            admin_root.refresh()

        with page_container():
            with ui.row().classes(
                'w-full items-center justify-between gap-3 flex-wrap mt-4'
            ):
                with ui.column().classes('gap-0'):
                    t = ui.label('Administration').classes(
                        'text-2xl md:text-3xl font-extrabold')
                    t.style('color: #1e293b !important;')
                    s = ui.label(
                        'Accès masqué : ne partagez pas cette URL.') \
                        .classes('text-sm')
                    s.style('color: #64748b !important;')
                with ui.row().classes('gap-2 items-center flex-wrap'):
                    ui.button('Verrouiller', icon='lock',
                              on_click=lock) \
                        .props('flat no-caps rounded-full color=grey-7')
                    ui.button('Retour au site', icon='arrow_back',
                              on_click=lambda: ui.navigate.to('/')) \
                        .props('flat no-caps rounded-full color=primary')

            @ui.refreshable
            def lists_panel():
                wishlists = get_wishlists()
                counts = get_item_counts()
                if not wishlists:
                    with ui.column().classes(
                        'w-full items-center justify-center py-16 gap-3'
                    ):
                        ui.icon('inventory_2').classes(
                            'text-6xl text-slate-300')
                        empty = ui.label('Aucune liste dans la base.') \
                            .classes('text-xl font-semibold')
                        empty.style('color: #334155 !important;')
                    return
                with ui.column().classes('w-full gap-3'):
                    for w in wishlists:
                        render_admin_wishlist_row(
                            w, counts.get(w['id'], 0), lists_panel.refresh)

            lists_panel()

    admin_root()


def _admin_badge(text, bg, fg):
    b = ui.label(text).classes(
        'text-[11px] font-semibold px-2 py-0.5 rounded-full')
    b.style(f'background-color: {bg} !important; '
            f'color: {fg} !important;')


async def admin_edit_link_dialog(w, refresh_fn):
    with ui.dialog() as dialog, ui.card().classes(
        'w-[560px] max-w-[calc(100vw-1rem)] p-4 md:p-6 rounded-2xl '
        'max-h-[90vh] overflow-y-auto'
    ):
        t = ui.label('Lien et redirection').classes(
            'text-lg font-bold')
        t.style('color: #1e293b !important;')
        sub = ui.label(w['title']).classes('text-sm mb-4 break-words')
        sub.style('color: #64748b !important;')

        kind = ui.radio(
            {'internal': 'Interne (page de ce site)',
             'external': 'Externe (autre site)'},
            value=w['type'],
        ).props('inline')

        url = ui.input('URL de redirection',
                       value=w.get('url') or '',
                       placeholder='https://...') \
            .props('outlined rounded').classes('w-full mt-3')
        url.set_visibility(w['type'] == 'external')
        kind.on_value_change(
            lambda e: url.set_visibility(e.value == 'external'))

        def save():
            value = (url.value or '').strip()
            if kind.value == 'external':
                if not value:
                    ui.notify('URL requise pour une redirection externe',
                              type='negative')
                    return
                if not (value.startswith('http://')
                        or value.startswith('https://')):
                    ui.notify(
                        'URL invalide (http:// ou https:// attendu)',
                        type='negative')
                    return
            update_wishlist_link(w['id'], kind.value, value or None)
            dialog.submit(True)

        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button('Annuler',
                      on_click=lambda: dialog.submit(None)) \
                .props('flat rounded-lg color=grey-7')
            ui.button('Enregistrer', icon='check', on_click=save) \
                .props('unelevated rounded-lg color=primary')

    if await dialog:
        refresh_fn()
        ui.notify('Lien mis à jour.', type='positive')


async def admin_reset_password_dialog(w, refresh_fn):
    with ui.dialog() as dialog, ui.card().classes(
        'w-96 max-w-[calc(100vw-2rem)] p-4 md:p-6 rounded-2xl'
    ):
        t = ui.label('Supprimer le mot de passe ?').classes(
            'text-lg font-bold')
        t.style('color: #1e293b !important;')
        s = ui.label(
            f"Le mot de passe de « {w['title']} » sera effacé. "
            "La personne pourra définir un nouveau mot de passe en "
            "passant en mode édition sur sa page.") \
            .classes('text-sm mt-2 mb-4 break-words')
        s.style('color: #64748b !important;')
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Annuler',
                      on_click=lambda: dialog.submit(False)) \
                .props('flat rounded-lg color=grey-7')
            ui.button('Supprimer le mot de passe', icon='lock_reset',
                      on_click=lambda: dialog.submit(True)) \
                .props('unelevated rounded-lg color=negative')

    if await dialog:
        set_wishlist_password(w['id'], None)
        refresh_fn()
        ui.notify('Mot de passe supprimé.', type='positive')


async def admin_delete_wishlist_dialog(w, refresh_fn):
    with ui.dialog() as dialog, ui.card().classes(
        'w-96 max-w-[calc(100vw-2rem)] p-4 md:p-6 rounded-2xl'
    ):
        t = ui.label('Supprimer cette liste ?').classes(
            'text-lg font-bold')
        t.style('color: #1e293b !important;')
        s = ui.label(
            f"« {w['title']} » et tous ses cadeaux seront supprimés. "
            "Cette action est irréversible.") \
            .classes('text-sm mt-2 mb-4 break-words')
        s.style('color: #64748b !important;')
        with ui.row().classes('w-full justify-end gap-2'):
            ui.button('Annuler',
                      on_click=lambda: dialog.submit(False)) \
                .props('flat rounded-lg color=grey-7')
            ui.button('Supprimer', icon='delete',
                      on_click=lambda: dialog.submit(True)) \
                .props('unelevated rounded-lg color=negative')

    if await dialog:
        delete_wishlist(w['id'])
        refresh_fn()
        ui.notify('Liste supprimée.', type='info')


def render_admin_wishlist_row(w, item_count, refresh_fn):
    is_internal = w['type'] == 'internal'
    has_pwd = bool(w.get('password'))

    with ui.element('div').classes('soft-card p-4 md:p-5 w-full'):
        with ui.row().classes(
            'w-full items-start justify-between gap-3 flex-wrap'
        ):
            with ui.column().classes('gap-1 min-w-0 flex-1'):
                t = ui.label(w['title']).classes(
                    'text-lg font-bold break-words')
                t.style('color: #1e293b !important;')
                m = ui.label(
                    f"Propriétaire : {w['owner']} · {item_count} "
                    f"cadeau{'x' if item_count != 1 else ''}") \
                    .classes('text-xs')
                m.style('color: #64748b !important;')
                fams = _wishlist_families(w)
                fam_label = ui.label(
                    'Familles : ' + (', '.join(fams) if fams else 'toutes')
                ).classes('text-xs break-words')
                fam_label.style('color: #64748b !important;')
                with ui.row().classes(
                    'gap-2 flex-wrap items-center mt-1'
                ):
                    _admin_badge('Interne' if is_internal else 'Externe',
                                 '#e0e7ff', '#4338ca')
                    _admin_badge(
                        'Mot de passe défini' if has_pwd
                        else 'Sans mot de passe',
                        '#d1fae5' if has_pwd else '#fef3c7',
                        '#047857' if has_pwd else '#b45309')
                if not is_internal and w.get('url'):
                    lk = ui.link(w['url'], w['url'], new_tab=True) \
                        .classes('text-xs break-all')
                    lk.style('color: #4338ca !important;')

            with ui.row().classes(
                'gap-1 flex-wrap items-center justify-start md:justify-end '
                'w-full md:w-auto'
            ):
                ui.button('Ouvrir', icon='open_in_new',
                          on_click=lambda: _open_wishlist(
                              w['id'], w.get('url'), is_internal)) \
                    .props('flat dense no-caps color=primary')
                ui.button('Lien', icon='link',
                          on_click=lambda:
                              admin_edit_link_dialog(w, refresh_fn)) \
                    .props('flat dense no-caps color=primary')
                if has_pwd:
                    ui.button(
                        'Mot de passe', icon='lock_reset',
                        on_click=lambda:
                            admin_reset_password_dialog(w, refresh_fn),
                    ).props('flat dense no-caps color=warning')
                ui.button('Supprimer', icon='delete',
                          on_click=lambda:
                              admin_delete_wishlist_dialog(w, refresh_fn)) \
                    .props('flat dense no-caps color=negative')


# ============================================================
# Page détail wishlist
# ============================================================
@ui.page('/wishlist/{wid}')
def wishlist_page(wid: int):
    apply_theme()
    add_reset_on_leave_js()
    ui.run_javascript(
        f'window.__wlCurrentWid = {wid}; '
        f'window.__wlExpectedPath = "/wishlist/{wid}";')
    w = get_wishlist(wid)
    if not w:
        render_header('Liste introuvable', back_url='/')
        with page_container():
            with ui.column().classes(
                'w-full items-center justify-center py-16 gap-3 px-2'
            ):
                ui.icon('error').classes('text-6xl text-slate-300')
                t = ui.label('Liste introuvable').classes(
                    'text-xl font-semibold text-center')
                t.style('color: #334155 !important;')
                s = ui.label("Cette liste n'existe pas ou a été "
                             "supprimée.").classes(
                                 'text-center max-w-md')
                s.style('color: #64748b !important;')
        return

    color = w.get('color') or 'indigo'
    ui.query('.q-page').style(
        'padding: 0 !important; background: transparent !important;')
    ui.query('body').style(
        f'background-color: {light_bg(color, "20")} !important;')

    admin_key = f'admin_wl_{wid}'
    is_admin = app.storage.user.get(admin_key, False)

    # --- Masquer/afficher l'état des offres (masqué par défaut) ---
    show_key = f'show_offers_wl_{wid}'
    show_offers = app.storage.user.get(show_key, False)

    def toggle_offers():
        nonlocal show_offers
        show_offers = not show_offers
        app.storage.user[show_key] = show_offers
        page_body.refresh()

    def set_admin(value):
        nonlocal is_admin
        is_admin = value
        if value:
            app.storage.user[admin_key] = True
        else:
            app.storage.user.pop(admin_key, None)
        admin_button.refresh()
        page_body.refresh()

    async def ask_password():
        nonlocal w
        # On relit la liste : le mot de passe a pu être réinitialisé
        # depuis la page d'administration entre-temps.
        w = get_wishlist(wid) or w
        if w.get('password'):
            pwd = await prompt_password()
        else:
            pwd = await prompt_password(
                "Créer le mot de passe d'édition",
                "Cette liste n'a pas encore de mot de passe. "
                "Choisissez-en un : il sera demandé pour la modifier.")
        if not pwd:
            return
        if not w.get('password'):
            set_wishlist_password(wid, hash_password(pwd))
            w = get_wishlist(wid) or w
            set_admin(True)
            ui.notify('Mot de passe défini, mode édition activé.',
                      type='positive')
        elif verify_password(pwd, w['password']):
            set_admin(True)
            ui.notify('Mode édition activé.', type='positive')
        else:
            ui.notify('Mot de passe incorrect.', type='negative')

    def logout_admin():
        set_admin(False)
        ui.notify('Mode édition désactivé.', type='info')

    @ui.refreshable
    def admin_button():
        if is_admin:
            b = ui.button('Quitter le mode édition', icon='lock',
                          on_click=logout_admin)
        else:
            b = ui.button('Mode édition', icon='edit',
                          on_click=ask_password)
        b.props('unelevated no-caps rounded-full color=primary')
        b.classes('shadow-md')

    async def edit_wishlist_dialog():
        result = await open_edit_wishlist_dialog(w)
        if result == 'saved':
            ui.navigate.to(f'/wishlist/{wid}')
        elif result == 'deleted':
            app.storage.user.pop(admin_key, None)
            ui.navigate.to('/')

    @ui.refreshable
    def page_body():
        nonlocal w
        w = get_wishlist(wid)
        if w is None:
            # La liste a disparu pendant la session (ex. supprimée
            # ailleurs) : on renvoie à l'accueil au lieu de crasher.
            ui.navigate.to('/')
            return
        items = get_items_with_links(wid)
        categories = get_categories(wid)
        color = w.get('color') or 'indigo'
        c_solid = solid_css(color)

        # « Mes réservations » : lu une seule fois par rendu de page,
        # puis passé aux items (au lieu d'une lecture du stockage à
        # chaque item).
        my_res = _my_reservations_set()

        by_cat = {None: []}
        for c in categories:
            by_cat[c['id']] = []
        for it in items:
            cid = it.get('category_id')
            if cid in by_cat:
                by_cat[cid].append(it)
            else:
                by_cat[None].append(it)

        def del_cat(cid):
            delete_category(cid)
            page_body.refresh()
            ui.notify('Catégorie supprimée.', type='info')

        def move_cat(cid, direction):
            swap_category_position(cid, direction)
            page_body.refresh()

        def move_item(item_id, direction):
            swap_item_position(item_id, direction)
            page_body.refresh()

        with ui.element('div').classes('w-full min-h-screen').style(
            f'background-color: {light_bg(color, "20")} !important;'
        ):
            with page_container():
                # Barre : Accueil + Mode édition
                with ui.row().classes(
                    'w-full items-center justify-between gap-2 flex-wrap'
                ):
                    back = ui.button('Accueil', icon='arrow_back',
                                     on_click=lambda: ui.navigate.to('/'))
                    back.props('flat no-caps rounded-full')
                    back.style(f'color: {c_solid} !important;')

                    with ui.row().classes('gap-2 items-center flex-wrap'):
                        admin_button()

                # Titre + description
                with ui.element('div').classes(
                    'p-4 md:p-6 lg:p-8 rounded-2xl w-full'
                ).style(
                    f'background-color: {light_bg(color, "60")} !important; '
                    'box-shadow: 0 4px 12px -4px rgba(0,0,0,0.06);'
                ):
                    with ui.row().classes(
                        'w-full items-start justify-between gap-4 flex-wrap'
                    ):
                        with ui.row().classes(
                            'items-start gap-3 flex-1 min-w-0'
                        ):
                            render_visual(
                                w.get('emoji'),
                                emoji_class='text-3xl md:text-4xl',
                                img_class='w-12 h-12 md:w-14 md:h-14')
                            with ui.column().classes(
                                'gap-1 min-w-0'
                            ):
                                # [MOBILE] taille adaptative
                                t = ui.label(w['title']).classes(
                                    'text-xl md:text-2xl font-bold '
                                    'break-words')
                                t.style(
                                    f'color: {c_solid} !important;')
                                if w.get('description'):
                                    d = ui.label(
                                        w['description']).classes(
                                            'mt-1 break-words')
                                    d.style(
                                        'color: #334155 !important;')
                        if is_admin:
                            ui.button(
                                icon='edit',
                                on_click=edit_wishlist_dialog,
                            ).props('flat round color=primary')

                # "Mes envies" + toggle offres + boutons d'ajout
                with ui.row().classes(
                    'w-full items-center justify-between flex-wrap '
                    'gap-2 mt-2'
                ):
                    # [MOBILE] taille adaptative
                    t = ui.label('Mes envies').classes(
                        'text-xl md:text-2xl font-bold')
                    t.style(f'color: {c_solid} !important;')

                    with ui.row().classes(
                        'gap-2 flex-wrap items-center'
                    ):
                        # Toggle : même style/taille que « Mode édition »,
                        # masqué en mode édition (état des offres masqué, anti-spoiler).
                        if not is_admin:
                            lbl = ('Masquer les offres' if show_offers
                                   else 'Afficher les offres')
                            ic = ('visibility_off' if show_offers
                                  else 'visibility')
                            tb = ui.button(lbl, icon=ic,
                                          on_click=toggle_offers)
                            tb.props('unelevated no-caps rounded-full '
                                     'color=primary')
                            tb.classes('shadow-md')

                        if is_admin:
                            ui.button(
                                'Ajouter une catégorie', icon='category',
                                on_click=lambda: open_add_category_dialog(
                                    wid, page_body.refresh),
                            ).props('unelevated no-caps rounded-full '
                                    'color=primary')
                            ui.button(
                                'Ajouter un cadeau', icon='add',
                                on_click=lambda: open_add_item_dialog(
                                    wid, categories, page_body.refresh),
                            ).props('unelevated no-caps rounded-full '
                                    'color=primary')

                # Contenu
                has_items = bool(items)
                has_cats = bool(categories)

                if not has_items and not has_cats:
                    with ui.column().classes(
                        'w-full items-center justify-center py-16 gap-3 px-2'
                    ):
                        ui.icon('redeem').classes(
                            'text-6xl text-slate-300')
                        t = ui.label('Aucune envie pour le moment') \
                            .classes('text-xl font-semibold text-center')
                        t.style('color: #334155 !important;')
                        s = ui.label(
                            "Ajoutez votre première envie ci-dessus."
                            if is_admin
                            else "Cette liste n'a pas encore d'envie."
                        ).classes('text-center max-w-md')
                        s.style('color: #64748b !important;')
                else:
                    # Catégories + items
                    for cat_idx, cat in enumerate(categories):
                        if is_admin:
                            render_category_header_editable(
                                cat, cat_idx, len(categories),
                                move_cat, del_cat, page_body.refresh,
                                color)
                        else:
                            render_category_header_public(cat, c_solid)

                        cat_items = by_cat.get(cat['id'], [])
                        if cat_items:
                            render_items_grid(
                                cat_items, is_admin, page_body.refresh,
                                color, categories, move_item, wid,
                                show_offers, my_res)

                        if is_admin:
                            ui.button(
                                'Ajouter un cadeau', icon='add',
                                on_click=lambda cid=cat['id']:
                                    open_add_item_dialog(
                                        wid, categories,
                                        page_body.refresh,
                                        default_category_id=cid),
                            ).props('unelevated no-caps rounded-full '
                                    'color=primary') \
                                .classes('mt-2')

                    # Items sans catégorie
                    if by_cat[None]:
                        if categories:
                            h = ui.label('Sans catégorie').classes(
                                'text-sm font-semibold uppercase '
                                'tracking-wide mt-4')
                            h.style(f'color: {c_solid} !important;')
                        render_items_grid(
                            by_cat[None], is_admin, page_body.refresh,
                            color, categories, move_item, wid,
                            show_offers, my_res)

    page_body()


# ============================================================
# Run
# ============================================================
ui.run(
    title='Listes de cadeaux',
    storage_secret='change-me-in-production',
    reload=False,
)