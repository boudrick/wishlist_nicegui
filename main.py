import json
from nicegui import ui, app
from db import (
    init_db, hash_password, verify_password,
    get_wishlists, get_wishlist, create_wishlist, update_wishlist,
    delete_wishlist, set_wishlist_password,
    get_categories, create_category, update_category, delete_category,
    swap_category_position,
    get_items_with_links, create_item, update_item, delete_item,
    swap_item_position, get_item_counts,
    add_reservation, delete_reservation, delete_reservations_for_item,
)
from theme import (
    apply_theme, page_container, apply_gradient,
    DEFAULT_GRADIENT, DEFAULT_SOLID, WISHLIST_COLORS,
    solid_css, light_bg,
)
from demo import seed_demo, has_demo_data

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
        ui.image(v).classes(f'{img_class} rounded-lg flex-shrink-0')\
            .props('fit=cover')
    else:
        ui.label(v).classes(f'{emoji_class} leading-none')


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
# Réinitialisation au départ de la page wishlist
# ============================================================
_RESET_JS_ADDED = False


def add_reset_on_leave_js():
    """Installe (une seule fois) le script qui réinitialise l'état
    (mode édition + affichage des offres) quand on quitte la page."""
    global _RESET_JS_ADDED
    if _RESET_JS_ADDED:
        return
    _RESET_JS_ADDED = True
    ui.add_head_html('''<script>
(function () {
  if (window.__wlResetInstalled) return;
  window.__wlResetInstalled = true;
  setInterval(function () {
    var cur = window.location.pathname;
    if (cur !== window.__wlExpectedPath && window.__wlCurrentWid) {
      try {
        navigator.sendBeacon(
          '/api/reset_wishlist/' + window.__wlCurrentWid);
      } catch (e) {}
      window.__wlCurrentWid = null;
    }
  }, 400);
  window.addEventListener('pagehide', function () {
    if (window.__wlCurrentWid) {
      try {
        navigator.sendBeacon(
          '/api/reset_wishlist/' + window.__wlCurrentWid);
      } catch (e) {}
    }
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

    lbl = ui.label(title).classes('text-2xl font-extrabold tracking-tight')
    lbl.style('color: #ffffff !important;')

    ui.space()
    if action_builder:
        action_builder()


# ============================================================
# Dialog mot de passe
# ============================================================
async def prompt_password(title='Mot de passe requis'):
    with ui.dialog() as dialog, ui.card().classes('w-96 p-6 rounded-2xl'):
        lbl = ui.label(title).classes('text-lg font-bold mb-2')
        lbl.style('color: #1e293b !important;')
        pwd = ui.input('Mot de passe', password=True,
                       password_toggle_button=True) \
            .props('outlined rounded').classes('w-full')
        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button('Annuler',
                      on_click=lambda: dialog.submit(None)) \
                .props('flat rounded-lg color=grey-7')
            ui.button('Valider',
                      on_click=lambda: dialog.submit(pwd.value)) \
                .props('unelevated rounded-lg color=primary')
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
        with ui.dialog() as dialog, ui.card().classes(
            'w-96 p-6 rounded-2xl'
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
        'grid grid-cols-1 md:grid-cols-[120px_1fr_400px] '
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
                        site = ui.input(
                            placeholder='Site', value=site_val,
                        ).props('outlined rounded dense') \
                            .classes('flex-1 min-w-[70px]')
                        url = ui.input(
                            placeholder='https://...', value=url_val,
                        ).props('outlined rounded dense') \
                            .classes('flex-[2] min-w-[90px]')
                        price = ui.number(
                            placeholder='€', value=price_val,
                            format='%.2f',
                        ).props('outlined rounded dense') \
                            .classes('w-16 flex-shrink-0')

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
    with ui.dialog() as dialog, ui.card().classes(
        'w-[1150px] max-w-full p-6 rounded-2xl max-h-[90vh] '
        'overflow-y-auto'
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
            'w-full justify-between items-center mt-4'
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
    with ui.dialog() as dialog, ui.card().classes(
        'w-[1150px] max-w-full p-6 rounded-2xl max-h-[90vh] '
        'overflow-y-auto'
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
            'w-full justify-between items-center mt-4'
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
    with ui.dialog() as dialog, ui.card().classes(
        'w-[600px] max-w-full p-6 rounded-2xl'
    ):
        lbl = ui.label('Ajouter une catégorie').classes(
            'text-lg font-bold mb-4')
        lbl.style('color: #1e293b !important;')

        with ui.row().classes('w-full items-center gap-2'):
            visual_in = ui.input(placeholder='🎁 ou https://...') \
                .props('outlined rounded dense').classes('w-40')
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
    with ui.dialog() as dialog, ui.card().classes(
        'w-96 p-6 rounded-2xl'
    ):
        lbl = ui.label("J'offre ce cadeau").classes(
            'text-lg font-bold mb-1')
        lbl.style('color: #1e293b !important;')
        sub = ui.label(f'« {it["name"]} »').classes('text-sm mb-4')
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


def render_offer_zone(it, refresh_fn, is_admin=False):
    reservations = it.get('reservations') or []
    max_offers = it.get('max_offers')
    count = len(reservations)
    my_res = _my_reservations_set()
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

    with ui.row().classes(
        'w-full items-center gap-2 flex-wrap '
        'pt-2 pb-2 px-3 border-t border-black/5'
    ):
        badge = ui.label(text).classes(
            'text-xs font-semibold px-2 py-1 rounded-full')
        badge.style(f'background-color: {bg} !important; '
                    f'color: {fg} !important;')

        if reservations:
            par = ui.label('Offert par :').classes('text-xs')
            par.style('color: #475569 !important;')
            for r in reservations:
                nm = r['offerer_name'] or 'anonyme'
                with ui.element('div').classes(
                    'inline-flex items-center bg-white/80 '
                    'rounded-full pl-2 pr-0.5 py-0.5'
                ):
                    nl = ui.label(nm).classes('text-xs')
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
                      categories, move_item, wid, show_offers):
    with ui.element('div').classes(
        'grid grid-cols-1 lg:grid-cols-2 gap-4 w-full auto-rows-fr'
    ):
        for idx, it in enumerate(items):
            render_item(it, is_admin, refresh_fn, color, categories,
                        move_item, idx == 0,
                        idx == len(items) - 1, wid, show_offers)


def render_item(it, is_admin, refresh_fn, color, categories,
                move_item, is_first, is_last, wid, show_offers):
    item_bg = (
        f'radial-gradient(circle at center, '
        f'{light_bg(color, "90")} 0%, '
        f'{light_bg(color, "30")} 100%)'
    )

    with ui.element('div').classes(
        'rounded-2xl flex flex-col overflow-hidden'
    ).style(
        f'background-color: {light_bg(color, "40")} !important; '
        f'background-image: {item_bg} !important; '
        'box-shadow: 0 1px 3px rgba(0,0,0,0.04);'
    ):
        # --- Barre d'actions (admin uniquement) ---
        if is_admin:
            with ui.row().classes(
                'w-full items-center justify-between px-2 pt-1 pb-0'
            ):
                with ui.row().classes('gap-0 items-center'):
                    b_up = ui.button(
                        icon='arrow_upward', text='Monter',
                        on_click=lambda: move_item(it['id'], 'up'))
                    b_up.props('flat dense no-caps color=primary size=sm')
                    b_up.set_enabled(not is_first)
                    b_dn = ui.button(
                        icon='arrow_downward', text='Descendre',
                        on_click=lambda: move_item(it['id'], 'down'))
                    b_dn.props('flat dense no-caps color=primary size=sm')
                    b_dn.set_enabled(not is_last)
                    b_ed = ui.button(
                        icon='edit', text='Modifier',
                        on_click=lambda item=it:
                            open_edit_item_dialog(item, categories,
                                                  refresh_fn))
                    b_ed.props('flat dense no-caps color=primary size=sm')
                b_del = ui.button(
                    icon='delete', text='Supprimer',
                    on_click=lambda i=it['id']:
                        _delete_and_refresh(i, refresh_fn))
                b_del.props('flat dense no-caps color=negative size=sm')

        # --- Contenu principal ---
        with ui.element('div').classes('p-4 flex gap-3 items-start'):
            with ui.element('div').classes(
                'flex-shrink-0 w-16 h-16 flex items-center justify-center'
            ):
                if it.get('image_url'):
                    render_visual(it['image_url'],
                                  emoji_class='text-3xl',
                                  img_class='w-16 h-16')
                else:
                    with ui.element('div').classes(
                        'w-16 h-16 rounded-xl bg-white/60 flex '
                        'items-center justify-center'
                    ):
                        ui.icon('image').classes(
                            'text-3xl text-slate-300')

            with ui.column().classes('flex-1 min-w-0 gap-1'):
                t = ui.label(it['name']).classes(
                    'text-base font-bold break-words leading-tight')
                t.style('color: #1e293b !important;')
                if it.get('description'):
                    d = ui.label(it['description']).classes(
                        'text-sm break-words leading-snug')
                    d.style('color: #334155 !important;')

            if it.get('links'):
                with ui.column().classes(
                    'w-36 flex-shrink-0 gap-1'
                ):
                    for link in it['links']:
                        with ui.element('div').classes(
                            'rounded-lg px-2 py-1 flex items-center '
                            'justify-between gap-2 w-full '
                            'overflow-hidden'
                        ).style(
                            'background-color: #ffffff !important;'
                        ):
                            lk = ui.link(
                                link.get('site') or 'Lien',
                                link['url'], new_tab=True,
                            ).classes(
                                'text-xs font-medium truncate '
                                'no-underline min-w-0 flex-1')
                            lk.style('color: #4338ca !important;')
                            if link.get('price') is not None:
                                p = ui.label(
                                    f"{link['price']:.0f}€"
                                ).classes(
                                    'text-xs font-bold '
                                    'whitespace-nowrap flex-shrink-0')
                                p.style('color: #059669 !important;')

        # --- Zone offres : masquée en mode édition (anti-spoiler),
        #     sinon contrôlée par le toggle « Afficher/Masquer ». ---
        if show_offers and not is_admin:
            render_offer_zone(it, refresh_fn, is_admin)


def _delete_and_refresh(item_id, refresh_fn):
    delete_item(item_id)
    refresh_fn()
    ui.notify('Cadeau supprimé.', type='info')


# ============================================================
# En-tête de catégorie
# ============================================================
def render_category_header_editable(cat, idx, total, move_cat,
                                    del_cat, refresh_fn, color):
    with ui.row().classes(
        'w-full items-center gap-2 rounded-2xl px-4 py-3 mt-4'
    ).style(
        'background-color: #ffffff !important; '
        'background-image: radial-gradient(circle at center, '
        '#ffffff 0%, #f1f5f9 100%) !important; '
        'box-shadow: 0 1px 3px rgba(0,0,0,0.04);'
    ):
        visual_in = ui.input(
            value=cat.get('emoji') or '', placeholder='🎁',
        ).props('outlined rounded dense').classes('w-24')
        name_in = ui.input(value=cat['name']) \
            .props('outlined rounded dense').classes('flex-1')

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
        h = ui.label(cat['name']).classes('text-lg font-semibold')
        h.style(f'color: {color_solid} !important;')


# ============================================================
# Page d'accueil
# ============================================================
@ui.page('/')
def home():
    apply_theme()
    add_reset_on_leave_js()
    wishlists = get_wishlists()

    def load_demo():
        seed_demo()
        ui.notify('Exemples chargés ! Mot de passe : "demo"',
                  type='positive', timeout=8000)
        ui.navigate.to('/')

    with page_container():
        with ui.row().classes(
            'w-full items-center justify-between mt-4 mb-2'
        ):
            sec = ui.label('Listes de cadeaux').classes(
                'text-3xl font-extrabold')
            sec.style('color: #1e293b !important;')

            with ui.row().classes('gap-3 items-center'):
                if not has_demo_data():
                    b1 = ui.button('Exemples', icon='auto_awesome',
                                   on_click=load_demo)
                    b1.props('flat no-caps rounded-full color=primary')
                b2 = ui.button('Créer ma liste', icon='add',
                               on_click=lambda: ui.navigate.to('/add'))
                b2.props('unelevated no-caps rounded-full color=primary')

        if not wishlists:
            with ui.column().classes(
                'w-full items-center justify-center py-16 gap-4'
            ):
                ui.icon('inventory_2').classes('text-6xl text-slate-300')
                t = ui.label('Aucune liste pour le moment').classes(
                    'text-xl font-semibold')
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
                    ui.button('Voir un exemple', icon='auto_awesome',
                              on_click=load_demo) \
                        .props('outline rounded-full color=primary '
                               'no-caps')
            return

        counts = get_item_counts()
        with ui.element('div').classes(
            'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 '
            'gap-6 w-full auto-rows-fr'
        ):
            for w in wishlists:
                render_wishlist_card(w, counts.get(w['id'], 0))


def render_wishlist_card(w, item_count):
    is_internal = w['type'] == 'internal'
    color = w.get('color') or 'indigo'

    card = ui.element('div').classes(
        'soft-card hover-lift overflow-hidden flex flex-col '
        'h-full cursor-pointer'
    )
    card.on('click',
            lambda wid=w['id'], url=w['url'], internal=is_internal:
                _open_wishlist(wid, url, internal))

    with card:
        band = ui.element('div').classes(
            'px-5 py-6 flex items-center gap-3'
        )
        apply_gradient(band, color)
        with band:
            render_visual(w.get('emoji'), emoji_class='text-4xl',
                          img_class='w-12 h-12')
            t = ui.label(w['title']).classes(
                'text-lg font-bold line-clamp-1 min-w-0 flex-1')
            t.style('color: #ffffff !important;')

        with ui.column().classes('p-4 flex-1 justify-end'):
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


# ============================================================
# Création d'une liste
# ============================================================
@ui.page('/add')
def add_page():
    apply_theme()
    add_reset_on_leave_js()
    render_header('Nouvelle liste', back_url='/')

    color_state, render_picker, get_color = color_picker('indigo')

    with page_container():
        with ui.element('div').classes(
            'soft-card p-6 md:p-8 max-w-2xl mx-auto w-full'
        ):
            t = ui.label('Créer une liste').classes('text-2xl font-bold')
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
                )
                app.storage.user[f'admin_wl_{wid}'] = True
                ui.notify('Liste créée ! Mode édition activé.',
                          type='positive')
                ui.navigate.to(f'/wishlist/{wid}')

            ui.button('Créer la liste', icon='check', on_click=submit) \
                .props('unelevated rounded-full color=primary') \
                .classes('w-full mt-6 py-3 text-base font-semibold')


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
                'w-full items-center justify-center py-16 gap-3'
            ):
                ui.icon('error').classes('text-6xl text-slate-300')
                t = ui.label('Liste introuvable').classes(
                    'text-xl font-semibold')
                t.style('color: #334155 !important;')
                s = ui.label("Cette liste n'existe pas ou a été "
                             "supprimée.").classes('text-center max-w-md')
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
        pwd = await prompt_password()
        if not pwd:
            return
        if not w['password']:
            set_wishlist_password(wid, hash_password(pwd))
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
        with ui.dialog() as dialog, ui.card().classes(
            'w-[520px] p-6 rounded-2xl max-h-[90vh] overflow-y-auto'
        ):
            t0 = ui.label('Modifier la liste').classes(
                'text-lg font-bold mb-4')
            t0.style('color: #1e293b !important;')
            t = ui.input('Titre', value=w['title']) \
                .props('outlined rounded').classes('w-full')
            d = ui.textarea('Description',
                            value=w.get('description') or '') \
                .props('outlined rounded').classes('w-full mt-3')
            u = ui.input('URL (si externe)',
                         value=w.get('url') or '') \
                .props('outlined rounded').classes('w-full mt-3')

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

            async def delete_wishlist_dialog():
                with ui.dialog() as confirm, ui.card().classes(
                    'w-96 p-6 rounded-2xl'
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
                    app.storage.user.pop(admin_key, None)
                    ui.navigate.to('/')

            def save():
                update_wishlist(
                    wid, t.value.strip(), t.value.strip(),
                    d.value.strip() or None,
                    u.value.strip() or None,
                    get_color(),
                    (visual_in.value or '').strip() or None)
                dialog.submit(True)

            with ui.row().classes(
                'w-full justify-between items-center mt-6'
            ):
                ui.button('Supprimer', icon='delete',
                          on_click=delete_wishlist_dialog) \
                    .props('flat rounded-lg color=negative')
                with ui.row().classes('gap-2'):
                    ui.button('Annuler',
                              on_click=lambda: dialog.submit(None)) \
                        .props('flat rounded-lg color=grey-7')
                    ui.button('Enregistrer', on_click=save) \
                        .props('unelevated rounded-lg color=primary')

        if await dialog:
            ui.navigate.to(f'/wishlist/{wid}')

    @ui.refreshable
    def page_body():
        nonlocal w
        w = get_wishlist(wid)
        items = get_items_with_links(wid)
        categories = get_categories(wid)
        color = w.get('color') or 'indigo'
        c_solid = solid_css(color)

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
                        'w-full items-center justify-between gap-2'
                ):
                    back = ui.button('Accueil', icon='arrow_back',
                                     on_click=lambda: ui.navigate.to('/'))
                    back.props('flat no-caps rounded-full')
                    back.style(f'color: {c_solid} !important;')

                    with ui.row().classes('gap-2 items-center'):
                        admin_button()

                # Titre + description
                with ui.element('div').classes(
                    'p-6 md:p-8 rounded-2xl w-full'
                ).style(
                    f'background-color: {light_bg(color, "60")} !important; '
                    'box-shadow: 0 4px 12px -4px rgba(0,0,0,0.06);'
                ):
                    with ui.row().classes(
                        'w-full items-start justify-between gap-4'
                    ):
                        with ui.row().classes(
                            'items-start gap-3 flex-1'
                        ):
                            render_visual(
                                w.get('emoji'),
                                emoji_class='text-4xl',
                                img_class='w-14 h-14')
                            with ui.column().classes(
                                'gap-1 min-w-0'
                            ):
                                t = ui.label(w['title']).classes(
                                    'text-2xl font-bold')
                                t.style(
                                    f'color: {c_solid} !important;')
                                if w.get('description'):
                                    d = ui.label(
                                        w['description']).classes('mt-1')
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
                    t = ui.label('Mes envies').classes(
                        'text-2xl font-bold')
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
                        'w-full items-center justify-center py-16 gap-3'
                    ):
                        ui.icon('redeem').classes(
                            'text-6xl text-slate-300')
                        t = ui.label('Aucune envie pour le moment') \
                            .classes('text-xl font-semibold')
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
                                color, categories, move_item, wid, show_offers)

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
                            color, categories, move_item, wid, show_offers)

    page_body()


# ============================================================
# Run
# ============================================================
ui.run(
    title='Listes de cadeaux',
    storage_secret='change-me-in-production',
    reload=False,
)