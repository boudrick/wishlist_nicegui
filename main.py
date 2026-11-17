import json
from nicegui import ui, app
from db import (
    init_db, hash_password, verify_password,
    get_wishlists, get_wishlist, create_wishlist, update_wishlist,
    delete_wishlist, set_wishlist_password,
    get_categories, create_category, delete_category,
    get_items_with_links, create_item, delete_item, get_item_counts,
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
def _open_wishlist(wid, url, is_internal):
    if is_internal:
        ui.navigate.to(f'/wishlist/{wid}')
    elif url:
        ui.run_javascript(f'window.open({json.dumps(url)}, "_blank")')


def wishlist_emoji(w):
    return w.get('emoji') or '🎁'


# ============================================================
# Emoji picker
# ============================================================
EMOJIS = [
    '🎁', '🎄', '🎂', '🎉', '🎈', '💝', '🧸', '🎮',
    '📚', '👕', '🍳', '🎵', '📷', '🎧', '💻', '✈️',
    '🏠', '🌱', '🎨', '🏋️', '🍷', '🌍', '💍', '🐶',
    '🐱', '⭐', '🎯', '🎬', '🏀', '🌻',
]


def emoji_picker(initial='🎁'):
    state = {'value': initial or '🎁'}
    buttons = {}

    def _highlight():
        for e, b in buttons.items():
            if e == state['value']:
                b.classes(remove='ring-transparent',
                          add='ring-indigo-500 bg-indigo-50')
            else:
                b.classes(remove='ring-indigo-500 bg-indigo-50',
                          add='ring-transparent')

    def select(emoji):
        state['value'] = emoji
        _highlight()

    def render():
        buttons.clear()
        with ui.row().classes('gap-1 flex-wrap'):
            for e in EMOJIS:
                btn = ui.element('div').classes(
                    'cursor-pointer rounded-lg w-10 h-10 flex '
                    'items-center justify-center text-2xl '
                    'hover:bg-slate-100 ring-2 ring-transparent'
                )
                btn.on('click', lambda x=e: select(x))
                with btn:
                    ui.label(e)
                buttons[e] = btn
        _highlight()

    def get_value():
        return state['value'] or '🎁'

    return state, render, get_value


# ============================================================
# Header (uniquement page /add et erreurs)
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
# Page d'accueil
# ============================================================
@ui.page('/')
def home():
    apply_theme()
    wishlists = get_wishlists()

    def load_demo():
        seed_demo()
        ui.notify('Exemples chargés ! Mot de passe : "demo"',
                  type='positive', timeout=8000)
        ui.navigate.to('/')

    with page_container():
        # --- Titre à gauche, boutons à droite ---
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
        # Bandeau : emoji + titre
        band = ui.element('div').classes(
            'px-5 py-6 flex items-center gap-3'
        )
        apply_gradient(band, color)
        with band:
            ui.label(wishlist_emoji(w)).classes(
                'text-4xl flex-shrink-0 leading-none')
            t = ui.label(w['title']).classes(
                'text-lg font-bold line-clamp-1 min-w-0 flex-1')
            t.style('color: #ffffff !important;')

        # Footer
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
    render_header('Nouvelle liste', back_url='/')

    color_state, render_picker, get_color = color_picker('indigo')
    emoji_state, render_emoji, get_emoji = emoji_picker('🎁')

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

            # Emoji
            lb_e = ui.label('Émoji').classes('text-sm font-semibold mb-2')
            lb_e.style('color: #334155 !important;')
            render_emoji()

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
            lb2 = ui.label('Couleur de la liste').classes(
                'text-sm font-semibold mb-3')
            lb2.style('color: #334155 !important;')
            render_picker()

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
                    get_emoji(),
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

    # --- Fond uni teinté sur toute la page (sans bordure blanche) ---
    color = w.get('color') or 'indigo'
    ui.query('.q-page').style(
        'padding: 0 !important; background: transparent !important;')
    ui.query('body').style(
        f'background-color: {light_bg(color, "20")} !important;')

    admin_key = f'admin_wl_{wid}'
    is_admin = app.storage.user.get(admin_key, False)

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
            'w-[480px] p-6 rounded-2xl'
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

            lb_e = ui.label('Émoji').classes(
                'text-sm font-semibold mt-4 mb-2')
            lb_e.style('color: #334155 !important;')
            _, render_emoji, get_emoji = emoji_picker(wishlist_emoji(w))
            render_emoji()

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
                    get_color(), get_emoji())
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

        def add_cat(name):
            if not name or not name.strip():
                return
            create_category(wid, name.strip())
            page_body.refresh()
            ui.notify('Catégorie ajoutée.', type='positive')

        def del_cat(cid):
            delete_category(cid)
            page_body.refresh()
            ui.notify('Catégorie supprimée.', type='info')

        with ui.element('div').classes('w-full min-h-screen').style(
            f'background-color: {light_bg(color, "20")} !important;'
        ):
            with page_container():
                # --- Barre : Accueil (gauche) + Mode édition (droite) ---
                with ui.row().classes(
                    'w-full items-center justify-between'
                ):
                    back = ui.button('Accueil', icon='arrow_back',
                                     on_click=lambda: ui.navigate.to('/'))
                    back.props('flat no-caps rounded-full')
                    back.style(f'color: {c_solid} !important;')
                    admin_button()

                # --- Box titre + description (fond coloré) ---
                with ui.element('div').classes(
                    'p-6 md:p-8 rounded-2xl w-full'
                ).style(
                    f'background-color: {light_bg(color, "60")} !important; '
                    'box-shadow: 0 4px 12px -4px rgba(0,0,0,0.06);'
                ):
                    with ui.row().classes(
                        'w-full items-start justify-between gap-4'
                    ):
                        with ui.row().classes('items-start gap-3 flex-1'):
                            ui.label(wishlist_emoji(w)).classes(
                                'text-4xl leading-none pt-1')
                            with ui.column().classes('gap-1 min-w-0'):
                                t = ui.label(w['title']).classes(
                                    'text-2xl font-bold')
                                t.style(
                                    f'color: {c_solid} !important;')
                                if w.get('description'):
                                    d = ui.label(w['description']) \
                                        .classes('mt-1')
                                    d.style(
                                        'color: #334155 !important;')
                        if is_admin:
                            ui.button(icon='edit',
                                      on_click=edit_wishlist_dialog) \
                                .props('flat round color=primary')

                # --- Catégories (admin) ---
                if is_admin:
                    with ui.element('div').classes('soft-card p-6'):
                        ct = ui.label('Catégories').classes(
                            'text-lg font-bold mb-3')
                        ct.style('color: #1e293b !important;')
                        if categories:
                            with ui.row().classes(
                                'gap-2 flex-wrap mb-3'
                            ):
                                for cat in categories:
                                    with ui.element('div').classes(
                                        'bg-indigo-50 text-indigo-700 '
                                        'px-3 py-1 rounded-full '
                                        'flex items-center gap-1'
                                    ):
                                        cl = ui.label(cat['name']) \
                                            .classes('text-sm font-medium')
                                        cl.style(
                                            'color: #4338ca !important;')
                                        ui.button(
                                            icon='close',
                                            on_click=lambda cid=cat['id']:
                                                del_cat(cid),
                                        ).props('flat round dense '
                                                'color=indigo size=xs')
                        with ui.row().classes(
                            'gap-2 w-full items-center'
                        ):
                            new_cat = ui.input(
                                placeholder='Nouvelle catégorie') \
                                .props('outlined rounded dense') \
                                .classes('flex-1')
                            ui.button(icon='add',
                                      on_click=lambda:
                                          add_cat(new_cat.value)) \
                                .props('unelevated rounded-lg '
                                       'color=primary')

                # --- "Mes envies" + badge édition ---
                with ui.row().classes(
                    'w-full items-center justify-between mt-2'
                ):
                    t = ui.label('Mes envies').classes(
                        'text-2xl font-bold')
                    t.style(f'color: {c_solid} !important;')
                    if is_admin:
                        mb = ui.label('Mode édition').classes(
                            'text-xs font-semibold bg-amber-100 '
                            'text-amber-700 px-3 py-1 rounded-full')
                        mb.style('color: #b45309 !important;')

                # --- Items ---
                if not items:
                    with ui.column().classes(
                        'w-full items-center justify-center py-16 gap-3'
                    ):
                        ui.icon('redeem').classes(
                            'text-6xl text-slate-300')
                        t = ui.label('Aucune envie pour le moment') \
                            .classes('text-xl font-semibold')
                        t.style('color: #334155 !important;')
                        s = ui.label(
                            "Ajoutez votre première envie ci-dessous."
                            if is_admin
                            else "Cette liste n'a pas encore d'envie."
                        ).classes('text-center max-w-md')
                        s.style('color: #64748b !important;')
                else:
                    if by_cat[None]:
                        if categories:
                            h = ui.label('Sans catégorie').classes(
                                'text-sm font-semibold uppercase '
                                'tracking-wide mt-2')
                            h.style(f'color: {c_solid} !important;')
                        render_items_grid(by_cat[None], is_admin,
                                          page_body.refresh, color)
                    for cat in categories:
                        cat_items = by_cat.get(cat['id'], [])
                        if not cat_items:
                            continue
                        h = ui.label(cat['name']).classes(
                            'text-sm font-semibold uppercase '
                            'tracking-wide mt-4')
                        h.style(f'color: {c_solid} !important;')
                        render_items_grid(cat_items, is_admin,
                                          page_body.refresh, color)

                if is_admin:
                    render_add_item_form(wid, categories,
                                         page_body.refresh)

    page_body()


# ============================================================
# Grille + Item (dégradé radial)
# ============================================================
def render_items_grid(items, is_admin, refresh_fn, color):
    with ui.element('div').classes(
        'grid grid-cols-1 lg:grid-cols-2 gap-4 w-full auto-rows-fr'
    ):
        for it in items:
            render_item(it, is_admin, refresh_fn, color)


def render_item(it, is_admin, refresh_fn, color):
    # Dégradé radial : plus coloré au centre, plus clair sur les bords
    item_bg = (
        f'radial-gradient(circle at center, '
        f'{light_bg(color, "90")} 0%, '
        f'{light_bg(color, "30")} 100%)'
    )

    with ui.element('div').classes(
        'p-4 flex gap-3 h-full items-start rounded-2xl'
    ).style(
        f'background-color: {light_bg(color, "40")} !important; '
        f'background-image: {item_bg} !important; '
        'box-shadow: 0 1px 3px rgba(0,0,0,0.04);'
    ):
        # Colonne 1 : photo
        with ui.element('div').classes('flex-shrink-0'):
            if it.get('image_url'):
                ui.image(it['image_url']) \
                    .classes('w-24 h-24 rounded-xl') \
                    .props('fit=cover')
            else:
                with ui.element('div').classes(
                    'w-24 h-24 rounded-xl bg-white/60 flex '
                    'items-center justify-center'
                ):
                    ui.icon('image').classes('text-3xl text-slate-400')

        # Colonne 2 : titre + description
        with ui.column().classes('flex-1 min-w-0 gap-1'):
            with ui.row().classes(
                'w-full items-start justify-between gap-1'
            ):
                t = ui.label(it['name']).classes(
                    'text-base font-bold break-words leading-tight')
                t.style('color: #1e293b !important;')
                if is_admin:
                    ui.button(
                        icon='delete',
                        on_click=lambda i=it['id']:
                            _delete_and_refresh(i, refresh_fn),
                    ).props('flat round color=negative size=xs')
            if it.get('description'):
                d = ui.label(it['description']).classes(
                    'text-sm break-words leading-snug')
                d.style('color: #334155 !important;')

        # Colonne 3 : liens (prix à droite)
        if it.get('links'):
            with ui.column().classes('w-36 flex-shrink-0 gap-1'):
                for link in it['links']:
                    with ui.element('div').classes(
                        'rounded-lg px-2 py-1 flex items-center '
                        'justify-between gap-2 w-full overflow-hidden'
                    ).style(
                        'background-color: #ffffff !important;'
                    ):
                        site_name = link.get('site') or 'Lien'
                        lk = ui.link(site_name, link['url'],
                                     new_tab=True).classes(
                            'text-xs font-medium truncate '
                            'no-underline min-w-0 flex-1'
                        )
                        lk.style('color: #4338ca !important;')
                        if link.get('price') is not None:
                            p = ui.label(
                                f"{link['price']:.0f}€"
                            ).classes(
                                'text-xs font-bold whitespace-nowrap '
                                'flex-shrink-0'
                            )
                            p.style('color: #059669 !important;')


def _delete_and_refresh(item_id, refresh_fn):
    delete_item(item_id)
    refresh_fn()
    ui.notify('Cadeau supprimé.', type='info')


# ============================================================
# Formulaire ajout cadeau
# ============================================================
def render_add_item_form(wid, categories, refresh_fn):
    with ui.element('div').classes('soft-card p-6 mt-4'):
        t = ui.label('Ajouter un cadeau').classes(
            'text-lg font-bold mb-4')
        t.style('color: #1e293b !important;')

        name = ui.input('Nom du cadeau',
                        placeholder='Ex. Casque audio') \
            .props('outlined rounded').classes('w-full')
        description = ui.textarea('Description (optionnel)') \
            .props('outlined rounded autogrow').classes('w-full mt-3')
        image_url = ui.input("URL de l'image (optionnel)",
                             placeholder='https://...') \
            .props('outlined rounded').classes('w-full mt-3')

        cat_options = {0: 'Sans catégorie'}
        for c in categories:
            cat_options[c['id']] = c['name']
        category_select = ui.select(
            cat_options, value=0, label='Catégorie',
        ).props('outlined rounded').classes('w-full mt-3')

        ui.separator().classes('my-4')
        l = ui.label('Liens (site · URL · prix)').classes(
            'text-sm font-semibold mb-2')
        l.style('color: #334155 !important;')

        links_container = ui.column().classes('w-full gap-3')
        link_rows = []

        def add_link_row():
            with links_container:
                with ui.row().classes(
                    'w-full items-center gap-2 no-wrap'
                ) as row:
                    site = ui.input('Site', placeholder='Amazon') \
                        .props('outlined rounded dense') \
                        .classes('w-32')
                    url = ui.input('URL', placeholder='https://...') \
                        .props('outlined rounded dense') \
                        .classes('flex-1')
                    price = ui.number('Prix (€)', format='%.2f') \
                        .props('outlined rounded dense') \
                        .classes('w-28')

                    entry = {'site': site, 'url': url, 'price': price}

                    def remove(e=entry, r=row):
                        if e in link_rows:
                            link_rows.remove(e)
                        r.delete()

                    ui.button(icon='delete', on_click=remove) \
                        .props('flat round color=negative size=sm')
                link_rows.append(entry)

        add_link_row()
        ui.button('Ajouter un autre lien', icon='add',
                  on_click=add_link_row) \
            .props('flat rounded-lg color=primary no-caps') \
            .classes('mt-2')

        def submit():
            if not name.value:
                ui.notify('Nom requis', type='negative')
                return
            links = [
                {'site': e['site'].value.strip() or None,
                 'url': e['url'].value.strip(),
                 'price': e['price'].value}
                for e in link_rows if e['url'].value
            ]
            cid = (category_select.value
                   if category_select.value else None)
            create_item(
                wid, name.value.strip(),
                description.value.strip() or None,
                image_url.value.strip() or None,
                cid, links,
            )
            refresh_fn()
            ui.notify('Cadeau ajouté !', type='positive')

        ui.button('Ajouter le cadeau', icon='check',
                  on_click=submit) \
            .props('unelevated rounded-lg color=primary') \
            .classes('w-full mt-4 py-2 text-base font-semibold')


# ============================================================
# Run
# ============================================================
ui.run(
    title='Listes de cadeaux',
    storage_secret='change-me-in-production',
    reload=False,
)