"""Importe une liste de cadeaux exportée de l'ancien site (JSON) dans la base
SQLite du nouveau site.

Format attendu (export de l'ancien site), tableau mêlant catégories et cadeaux :
[
    {"type": "categorie", "id": ..., "titre": ...},
    {"type": "cadeau", "id": ..., "titre": ..., "image": ..., "description": ...,
     "liens": [{"url": ..., "text": ...}],
     "statut": "libre" | "pris", "reserve_par": "",
     "multiple": bool, "max_quantity": int, "unlimited": bool}
]

Correspondance avec le nouveau schéma :
- categorie            -> categories (ordre du fichier conservé)
- cadeau               -> items (+ item_links + reservations si statut = pris)
- unlimited=true       -> max_offers NULL (illimité), sinon max_quantity
- liens[].text         -> site, avec le prix extrait s'il y a un « N€ »

Usage :
    python import_legacy.py Marion.json \
        --title "Liste de Marion" --owner "Marion" --color rose --emoji 💝

La liste est créée SANS mot de passe : au premier passage en mode édition,
le mot de passe saisi devient le mot de passe administrateur de la liste.
"""

import argparse
import json
import re
import sys

from db import (
    connection, create_wishlist, create_category,
    create_item, add_reservation, get_wishlists,
)


def parse_link(text, url):
    """Transforme un lien de l'ancien format {'url', 'text'} en
    {'site', 'url', 'price'} du nouveau site.

    Le prix est extrait du texte s'il contient « N€ » (ex : "65€",
    "En grise 829€") ; le reste devient l'étiquette affichée.
    """
    text = (text or '').strip()
    price = None
    site = text

    m = re.search(r'(\d+[.,]?\d*)\s*€', text)
    if m:
        try:
            price = float(m.group(1).replace(',', '.'))
        except ValueError:
            price = None
        # Retire le prix du texte, puis nettoie les parenthèses vides.
        site = re.sub(r'\s+', ' ', text.replace(m.group(0), ' ')).strip()
        site = re.sub(r'\(\s*\)', '', site).strip()

    return {'site': site or None, 'url': url, 'price': price}


def import_legacy(path, title, owner, color='indigo', emoji=None):
    """Importe un export JSON dans la base. Retourne les compteurs."""
    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    # Garde-fou : ne pas créer de doublon si déjà importée.
    for w in get_wishlists():
        if w['title'] == title and w['owner'] == owner:
            raise SystemExit(
                f"Arrêté : une liste « {title} » (propriétaire « {owner} ») "
                f"existe déjà (id {w['id']}). Supprimez-la d'abord ou "
                f"utilisez un autre titre.")

    n_cat = n_item = n_link = n_res = 0
    current_category = None

    with connection() as conn:
        wid = create_wishlist(
            title, owner, 'internal', None, None, None, color, emoji,
            _conn=conn)

        for entry in data:
            if not isinstance(entry, dict):
                continue
            etype = entry.get('type')

            if etype == 'categorie':
                name = (entry.get('titre') or '').strip()
                if not name:
                    continue
                current_category = create_category(
                    wid, name, None, _conn=conn)
                n_cat += 1

            elif etype == 'cadeau':
                name = (entry.get('titre') or '').strip()
                if not name:
                    continue

                links = [
                    parse_link(l.get('text'), l['url'])
                    for l in (entry.get('liens') or [])
                    if isinstance(l, dict) and l.get('url')
                ]
                n_link += len(links)

                max_offers = None if entry.get('unlimited') \
                    else int(entry.get('max_quantity') or 1)

                item_id = create_item(
                    wid, name,
                    (entry.get('description') or '').strip() or None,
                    entry.get('image'), current_category, links,
                    max_offers=max_offers, _conn=conn)

                if entry.get('statut') == 'pris' and \
                        (entry.get('reserve_par') or '').strip():
                    add_reservation(
                        item_id, entry['reserve_par'].strip(), _conn=conn)
                    n_res += 1

                n_item += 1

    return wid, n_cat, n_item, n_link, n_res


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('fichier', help='Export JSON de l\'ancien site')
    ap.add_argument('--title', required=True, help='Titre de la liste')
    ap.add_argument('--owner', required=True, help='Propriétaire (destinataire)')
    ap.add_argument('--color', default='indigo',
                    help="Couleur : indigo, rose, emerald, amber, sky, "
                         "violet, slate, red ou custom:#hex")
    ap.add_argument('--emoji', default=None,
                    help='Émoji (ou URL d\'image) pour la carte de la liste')
    args = ap.parse_args()

    wid, n_cat, n_item, n_link, n_res = import_legacy(
        args.fichier, args.title, args.owner, args.color, args.emoji)

    print(f"Liste « {args.title} » créée (id {wid}).")
    print(f"  Catégories : {n_cat}")
    print(f"  Cadeaux    : {n_item}")
    print(f"  Liens      : {n_link}")
    print(f"  Réservations déjà prises : {n_res}")


if __name__ == '__main__':
    main()
