import sqlite3
import hashlib
import secrets
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path('wishlist.db')


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


def init_db():
    with connection() as conn:
        c = conn.cursor()

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
            position INTEGER DEFAULT 0,
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

        # --- Nouvelle colonne position sur items ---
        if not has_column('items', 'position'):
            c.execute(
                'ALTER TABLE items ADD COLUMN position INTEGER DEFAULT 0')
            # Initialise les positions par (wishlist, catégorie) selon l'id
            rows = c.execute(
                'SELECT id, wishlist_id, category_id FROM items '
                'ORDER BY wishlist_id, category_id, id').fetchall()
            counters = {}
            for r in rows:
                key = (r[1], r[2])
                counters[key] = counters.get(key, 0) + 1
                c.execute('UPDATE items SET position=? WHERE id=?',
                          (counters[key], r[0]))

        # Migration items.url/price → item_links
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
        row = conn.execute(
            'SELECT MAX(position) AS p FROM categories WHERE wishlist_id=?',
            (wid,)).fetchone()
        pos = (row['p'] or 0) + 1
        cur = conn.execute(
            'INSERT INTO categories (wishlist_id, name, position) '
            'VALUES (?,?,?)',
            (wid, name, pos))
        return cur.lastrowid


def delete_category(cid):
    with connection() as conn:
        conn.execute(
            'UPDATE items SET category_id=NULL WHERE category_id=?', (cid,))
        conn.execute('DELETE FROM categories WHERE id=?', (cid,))


def swap_category_position(cid, direction):
    """Échange la position avec le voisin précédent ('up') ou suivant ('down')."""
    with connection() as conn:
        row = conn.execute(
            'SELECT * FROM categories WHERE id=?', (cid,)).fetchone()
        if not row:
            return
        wid = row['wishlist_id']
        cur_pos = row['position'] or 0
        if direction == 'up':
            nb = conn.execute(
                'SELECT * FROM categories '
                'WHERE wishlist_id=? AND position < ? '
                'ORDER BY position DESC LIMIT 1',
                (wid, cur_pos)).fetchone()
        else:
            nb = conn.execute(
                'SELECT * FROM categories '
                'WHERE wishlist_id=? AND position > ? '
                'ORDER BY position ASC LIMIT 1',
                (wid, cur_pos)).fetchone()
        if nb:
            conn.execute('UPDATE categories SET position=? WHERE id=?',
                         (nb['position'], cid))
            conn.execute('UPDATE categories SET position=? WHERE id=?',
                         (cur_pos, nb['id']))


# ============================================================
# Items
# ============================================================
def get_items_with_links(wid):
    with connection() as conn:
        items = [dict(r) for r in conn.execute(
            'SELECT * FROM items WHERE wishlist_id=? '
            'ORDER BY position, id', (wid,))]
        for it in items:
            it['links'] = [dict(r) for r in conn.execute(
                'SELECT * FROM item_links WHERE item_id=? '
                'ORDER BY price IS NULL, price', (it['id'],))]
        return items


def create_item(wishlist_id, name, description, image_url,
                category_id, links):
    with connection() as conn:
        if category_id:
            row = conn.execute(
                'SELECT MAX(position) AS p FROM items '
                'WHERE wishlist_id=? AND category_id=?',
                (wishlist_id, category_id)).fetchone()
        else:
            row = conn.execute(
                'SELECT MAX(position) AS p FROM items '
                'WHERE wishlist_id=? AND category_id IS NULL',
                (wishlist_id,)).fetchone()
        pos = (row['p'] or 0) + 1
        cur = conn.execute(
            'INSERT INTO items '
            '(wishlist_id, name, description, image_url, '
            'category_id, position) '
            'VALUES (?,?,?,?,?,?)',
            (wishlist_id, name, description, image_url,
             category_id, pos))
        item_id = cur.lastrowid
        for link in links:
            if link.get('url'):
                conn.execute(
                    'INSERT INTO item_links (item_id, site, url, price) '
                    'VALUES (?,?,?,?)',
                    (item_id, link.get('site'), link['url'],
                     link.get('price')))
        return item_id


def update_item(item_id, name, description, image_url,
                category_id, links):
    with connection() as conn:
        old = conn.execute(
            'SELECT * FROM items WHERE id=?', (item_id,)).fetchone()
        if not old:
            return
        # Si la catégorie change, on place l'item à la fin de la nouvelle
        if (old['category_id'] or 0) != (category_id or 0):
            if category_id:
                row = conn.execute(
                    'SELECT MAX(position) AS p FROM items '
                    'WHERE wishlist_id=? AND category_id=?',
                    (old['wishlist_id'], category_id)).fetchone()
            else:
                row = conn.execute(
                    'SELECT MAX(position) AS p FROM items '
                    'WHERE wishlist_id=? AND category_id IS NULL',
                    (old['wishlist_id'],)).fetchone()
            new_pos = (row['p'] or 0) + 1
        else:
            new_pos = old['position'] or 0

        conn.execute(
            'UPDATE items SET name=?, description=?, image_url=?, '
            'category_id=?, position=? WHERE id=?',
            (name, description, image_url, category_id, new_pos, item_id))
        conn.execute('DELETE FROM item_links WHERE item_id=?', (item_id,))
        for link in links:
            if link.get('url'):
                conn.execute(
                    'INSERT INTO item_links (item_id, site, url, price) '
                    'VALUES (?,?,?,?)',
                    (item_id, link.get('site'), link['url'],
                     link.get('price')))


def delete_item(item_id):
    with connection() as conn:
        conn.execute('DELETE FROM items WHERE id=?', (item_id,))


def swap_item_position(item_id, direction):
    """Échange la position avec le voisin dans la même catégorie."""
    with connection() as conn:
        row = conn.execute(
            'SELECT * FROM items WHERE id=?', (item_id,)).fetchone()
        if not row:
            return
        wid = row['wishlist_id']
        cat_id = row['category_id']
        cur_pos = row['position'] or 0

        if cat_id:
            if direction == 'up':
                nb = conn.execute(
                    'SELECT * FROM items '
                    'WHERE wishlist_id=? AND category_id=? AND position < ? '
                    'ORDER BY position DESC LIMIT 1',
                    (wid, cat_id, cur_pos)).fetchone()
            else:
                nb = conn.execute(
                    'SELECT * FROM items '
                    'WHERE wishlist_id=? AND category_id=? AND position > ? '
                    'ORDER BY position ASC LIMIT 1',
                    (wid, cat_id, cur_pos)).fetchone()
        else:
            if direction == 'up':
                nb = conn.execute(
                    'SELECT * FROM items '
                    'WHERE wishlist_id=? AND category_id IS NULL '
                    'AND position < ? '
                    'ORDER BY position DESC LIMIT 1',
                    (wid, cur_pos)).fetchone()
            else:
                nb = conn.execute(
                    'SELECT * FROM items '
                    'WHERE wishlist_id=? AND category_id IS NULL '
                    'AND position > ? '
                    'ORDER BY position ASC LIMIT 1',
                    (wid, cur_pos)).fetchone()

        if nb:
            conn.execute('UPDATE items SET position=? WHERE id=?',
                         (nb['position'], item_id))
            conn.execute('UPDATE items SET position=? WHERE id=?',
                         (cur_pos, nb['id']))