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
    return ui.column().classes('w-full max-w-6xl mx-auto px-4 py-8 gap-6')