import sqlite3
import hashlib
import secrets
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path('wishlist.db')


# ============================================================
# Sécurité — mots de passe
# ============================================================
def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        'sha256', password.encode(), salt.encode(), 100_000).hex()
    return f"{salt}${digest}"


def verify_password(password, stored):
    if not stored or '$' not in stored:
        return False
    salt = stored.split('$', 1)[0]
    return hash_password(password, salt) == stored


# ============================================================
# Connexion
# ============================================================
@contextmanager
def connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================
# Initialisation / migrations
# ============================================================
def init_db():
    with connection() as conn:
        c = conn.cursor()

        # --- Tables ---
        c.execute('''CREATE TABLE IF NOT EXISTS wishlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            owner TEXT NOT NULL,
            type TEXT NOT NULL,
            url TEXT,
            description TEXT,
            password TEXT,
            color TEXT,
            emoji TEXT DEFAULT '🎁',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wishlist_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            image_url TEXT,
            category_id INTEGER,
            FOREIGN KEY (wishlist_id) REFERENCES wishlists(id)
                ON DELETE CASCADE
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS item_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            site TEXT,
            url TEXT NOT NULL,
            price REAL,
            FOREIGN KEY (item_id) REFERENCES items(id)
                ON DELETE CASCADE
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wishlist_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            position INTEGER DEFAULT 0,
            FOREIGN KEY (wishlist_id) REFERENCES wishlists(id)
                ON DELETE CASCADE
        )''')

        # --- Migrations de colonnes ---
        def has_column(table, column):
            c.execute(f"PRAGMA table_info({table})")
            return any(row[1] == column for row in c.fetchall())

        if not has_column('wishlists', 'password'):
            c.execute('ALTER TABLE wishlists ADD COLUMN password TEXT')
        if not has_column('wishlists', 'color'):
            c.execute('ALTER TABLE wishlists ADD COLUMN color TEXT')
        if not has_column('wishlists', 'emoji'):
            c.execute(
                "ALTER TABLE wishlists ADD COLUMN emoji TEXT DEFAULT '🎁'")
        if not has_column('items', 'image_url'):
            c.execute('ALTER TABLE items ADD COLUMN image_url TEXT')
        if not has_column('items', 'category_id'):
            c.execute('ALTER TABLE items ADD COLUMN category_id INTEGER')

        # --- Migration des anciens items.url / items.price vers item_links ---
        if (has_column('items', 'url')
                or has_column('items', 'price')):
            c.execute('''SELECT id, url, price FROM items
                         WHERE (url IS NOT NULL OR price IS NOT NULL)
                         AND id NOT IN (
                            SELECT DISTINCT item_id FROM item_links
                         )''')
            for item_id, old_url, old_price in c.fetchall():
                if old_url or old_price is not None:
                    c.execute(
                        'INSERT INTO item_links (item_id, site, url, price) '
                        'VALUES (?,?,?,?)',
                        (item_id, None, old_url or '', old_price))


# ============================================================
# Wishlists
# ============================================================
def get_wishlists():
    with connection() as conn:
        return [dict(r) for r in conn.execute(
            'SELECT * FROM wishlists ORDER BY created_at DESC')]


def get_wishlist(wid):
    with connection() as conn:
        row = conn.execute(
            'SELECT * FROM wishlists WHERE id=?', (wid,)).fetchone()
        return dict(row) if row else None


def create_wishlist(title, owner, wtype, url, description, password_hash,
                    color, emoji='🎁'):
    with connection() as conn:
        cur = conn.execute(
            'INSERT INTO wishlists '
            '(title, owner, type, url, description, password, color, emoji) '
            'VALUES (?,?,?,?,?,?,?,?)',
            (title, owner, wtype, url, description, password_hash,
             color, emoji or '🎁'))
        return cur.lastrowid


def update_wishlist(wid, title, owner, description, url, color,
                    emoji='🎁'):
    with connection() as conn:
        conn.execute(
            'UPDATE wishlists '
            'SET title=?, owner=?, description=?, url=?, color=?, emoji=? '
            'WHERE id=?',
            (title, owner, description, url, color,
             emoji or '🎁', wid))


def set_wishlist_password(wid, password_hash):
    with connection() as conn:
        conn.execute(
            'UPDATE wishlists SET password=? WHERE id=?',
            (password_hash, wid))


def delete_wishlist(wid):
    with connection() as conn:
        conn.execute('DELETE FROM wishlists WHERE id=?', (wid,))


def get_item_counts():
    """Retourne {wishlist_id: nombre d'items} pour toutes les wishlists."""
    with connection() as conn:
        return {r['wishlist_id']: r['c'] for r in conn.execute(
            'SELECT wishlist_id, COUNT(*) AS c FROM items '
            'GROUP BY wishlist_id')}


# ============================================================
# Catégories
# ============================================================
def get_categories(wid):
    with connection() as conn:
        return [dict(r) for r in conn.execute(
            'SELECT * FROM categories WHERE wishlist_id=? '
            'ORDER BY position, id', (wid,))]


def create_category(wid, name):
    with connection() as conn:
        cur = conn.execute(
            'INSERT INTO categories (wishlist_id, name) VALUES (?,?)',
            (wid, name))
        return cur.lastrowid


def delete_category(cid):
    with connection() as conn:
        conn.execute(
            'UPDATE items SET category_id=NULL WHERE category_id=?', (cid,))
        conn.execute('DELETE FROM categories WHERE id=?', (cid,))


# ============================================================
# Items
# ============================================================
def get_items_with_links(wid):
    with connection() as conn:
        items = [dict(r) for r in conn.execute(
            'SELECT * FROM items WHERE wishlist_id=? ORDER BY id DESC',
            (wid,))]
        for it in items:
            it['links'] = [dict(r) for r in conn.execute(
                'SELECT * FROM item_links WHERE item_id=? '
                'ORDER BY price IS NULL, price', (it['id'],))]
        return items


def create_item(wishlist_id, name, description, image_url,
                category_id, links):
    with connection() as conn:
        cur = conn.execute(
            'INSERT INTO items '
            '(wishlist_id, name, description, image_url, category_id) '
            'VALUES (?,?,?,?,?)',
            (wishlist_id, name, description, image_url, category_id))
        item_id = cur.lastrowid
        for link in links:
            if link.get('url'):
                conn.execute(
                    'INSERT INTO item_links (item_id, site, url, price) '
                    'VALUES (?,?,?,?)',
                    (item_id, link.get('site'), link['url'],
                     link.get('price')))
        return item_id


def delete_item(item_id):
    with connection() as conn:
        conn.execute('DELETE FROM items WHERE id=?', (item_id,))