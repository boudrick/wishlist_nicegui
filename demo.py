from db import (
    connection, create_wishlist, create_category,
    create_item, add_reservation, hash_password,
)


def has_demo_data() -> bool:
    """Vérifie la présence de données de démo sans charger toute la table."""
    with connection() as conn:
        return conn.execute(
            "SELECT 1 FROM wishlists WHERE owner LIKE '[Démo]%' LIMIT 1"
        ).fetchone() is not None


def seed_demo() -> bool:
    """Insère les listes de démo en une seule transaction.

    Toutes les opérations partagent la même connexion (`_conn=conn`) :
    si ça échoue à mi-chemin, rien n'est écrit (pas de données partielles).
    """
    with connection() as conn:
        # Nettoyage d'abord, dans la même transaction que l'insertion.
        conn.execute("DELETE FROM wishlists WHERE owner LIKE '[Démo]%'")

        pwd = hash_password('demo')

        # ============================================================
        # 1. Noël 2025 — internal, rose
        # ============================================================
        wid = create_wishlist(
            'Noël 2025', '[Démo] Audrick', 'internal', None,
            'Mes envies pour les fêtes 🎄', pwd, 'rose', '🎄', _conn=conn)
        c_jeux = create_category(wid, 'Jeux vidéo', '🎮', _conn=conn)
        c_livres = create_category(wid, 'Livres & BD', '📚', _conn=conn)
        c_vest = create_category(wid, 'Vêtements', '👕', _conn=conn)
        c_cuisine = create_category(wid, 'Cuisine', '🍳', _conn=conn)
        c_musique = create_category(wid, 'Musique', '🎵', _conn=conn)

        it1 = create_item(
            wid, 'Zelda : Tears of the Kingdom',
            'Pour la Nintendo Switch, édition standard',
            'https://picsum.photos/seed/zelda/400/400', c_jeux,
            [
                {'site': 'Amazon', 'url': 'https://www.amazon.fr', 'price': 49.99},
                {'site': 'Fnac', 'url': 'https://www.fnac.com', 'price': 54.90},
                {'site': 'Micromania', 'url': 'https://www.micromania.fr', 'price': 52.99},
            ],
            max_offers=1, _conn=conn)
        create_item(
            wid, 'Elden Ring', 'Édition standard PS5',
            'https://picsum.photos/seed/eldenring/400/400', c_jeux,
            [
                {'site': 'Amazon', 'url': 'https://www.amazon.fr', 'price': 39.99},
                {'site': 'Steam (PC)', 'url': 'https://store.steampowered.com', 'price': 59.99},
            ],
            max_offers=1, _conn=conn)
        it3 = create_item(
            wid, 'Manette DualSense', 'Coloris blanc, pour PS5',
            'https://picsum.photos/seed/dualsense/400/400', c_jeux,
            [
                {'site': 'Sony', 'url': 'https://www.playstation.com', 'price': 69.99},
                {'site': 'Amazon', 'url': 'https://www.amazon.fr', 'price': 59.99},
            ],
            max_offers=3, _conn=conn)
        create_item(
            wid, 'Dune — Frank Herbert', 'Édition collector reliée',
            'https://picsum.photos/seed/dune/400/400', c_livres,
            [{'site': 'Fnac', 'url': 'https://www.fnac.com', 'price': 32.90}],
            max_offers=1, _conn=conn)
        create_item(
            wid, 'Le Seigneur des Anneaux — Intégrale',
            'Édition reliée, traduction F. Ledoux',
            'https://picsum.photos/seed/lotr/400/400', c_livres,
            [
                {'site': 'Amazon', 'url': 'https://www.amazon.fr', 'price': 45.00},
                {'site': 'Decitre', 'url': 'https://www.decitre.fr', 'price': 49.90},
            ],
            max_offers=1, _conn=conn)
        create_item(
            wid, 'Astérix — Le Bouclier Arverne',
            'Album relié, éditions Hachette',
            '📖', c_livres,  # ← emoji comme visuel (pas d'image)
            [{'site': 'Amazon', 'url': 'https://www.amazon.fr', 'price': 10.50}],
            max_offers=None, _conn=conn)
        create_item(
            wid, 'Pull en laine mérinos',
            'Taille M, coloris marine',
            'https://picsum.photos/seed/pull/400/400', c_vest,
            [
                {'site': 'Uniqlo', 'url': 'https://www.uniqlo.com', 'price': 49.90},
                {'site': 'Asket', 'url': 'https://www.asket.com', 'price': 120.00},
            ],
            max_offers=1, _conn=conn)
        it8 = create_item(
            wid, 'Chaussettes en laine', 'Lot de 3, taille 39-42',
            '🧦', c_vest,  # ← emoji
            [{'site': 'Decathlon', 'url': 'https://www.decathlon.fr', 'price': 14.99}],
            max_offers=None, _conn=conn)
        create_item(
            wid, 'Poêle en fonte 28 cm',
            'Pré-saisonnisée, marque Le Creuset',
            'https://picsum.photos/seed/poele/400/400', c_cuisine,
            [
                {'site': 'Darty', 'url': 'https://www.darty.com', 'price': 79.00},
                {'site': 'Amazon', 'url': 'https://www.amazon.fr', 'price': 72.50},
            ],
            max_offers=1, _conn=conn)
        create_item(
            wid, 'Livre — La Cuisine de référence',
            'Éditions Flammarion',
            '🍳', c_cuisine,  # ← emoji
            [{'site': 'Fnac', 'url': 'https://www.fnac.com', 'price': 39.95}],
            max_offers=1, _conn=conn)
        create_item(
            wid, 'Casque Sony WH-1000XM5',
            'Réduction de bruit active, noir',
            'https://picsum.photos/seed/casque/400/400', c_musique,
            [
                {'site': 'Amazon', 'url': 'https://www.amazon.fr', 'price': 349.00},
                {'site': 'Boulanger', 'url': 'https://www.boulanger.com', 'price': 379.00},
                {'site': 'Fnac', 'url': 'https://www.fnac.com', 'price': 369.00},
            ],
            max_offers=1, _conn=conn)
        create_item(
            wid, 'Vinyle — Daft Punk, Random Access Memories',
            'Édition 10e anniversaire', '🎵', c_musique,  # ← emoji
            [{'site': 'Fnac', 'url': 'https://www.fnac.com', 'price': 34.99}],
            max_offers=1, _conn=conn)

        add_reservation(it1, 'Sophie', _conn=conn)
        add_reservation(it3, 'Marc', _conn=conn)
        add_reservation(it3, 'Léa', _conn=conn)
        add_reservation(it8, 'Alice', _conn=conn)

        # ============================================================
        # 2. Anniversaire — internal, emerald
        # ============================================================
        wid2 = create_wishlist(
            'Anniversaire', '[Démo] Sophie', 'internal', None,
            'Pour mes 30 ans 🎂', pwd, 'emerald', '🎂', _conn=conn)
        c_cuisine2 = create_category(wid2, 'Cuisine', '🍳', _conn=conn)
        c_bien = create_category(wid2, 'Bien-être', '🧘', _conn=conn)
        c_loisirs = create_category(wid2, 'Loisirs créatifs', '🎨', _conn=conn)

        it20 = create_item(
            wid2, 'Robot pâtissier KitchenAid',
            'Coloris crème, bol 4.8 L',
            'https://picsum.photos/seed/kitchenaid/400/400', c_cuisine2,
            [
                {'site': 'Darty', 'url': 'https://www.darty.com', 'price': 449.00},
                {'site': 'Amazon', 'url': 'https://www.amazon.fr', 'price': 429.00},
            ],
            max_offers=1, _conn=conn)
        create_item(
            wid2, 'Couteaux japonais (set de 3)',
            'Acier damas, marque Miyabi',
            'https://picsum.photos/seed/couteaux/400/400', c_cuisine2,
            [{'site': 'Amazon', 'url': 'https://www.amazon.fr', 'price': 189.00}],
            max_offers=1, _conn=conn)
        it22 = create_item(
            wid2, 'Plat à four en céramique',
            'Grand format, gris ardoise',
            'https://picsum.photos/seed/plat/400/400', c_cuisine2,
            [
                {'site': 'Maisons du Monde', 'url': 'https://www.maisonsdumonde.com', 'price': 39.99},
                {'site': 'IKEA', 'url': 'https://www.ikea.com', 'price': 24.99},
            ],
            max_offers=3, _conn=conn)
        create_item(
            wid2, 'Tapis de yoga',
            'Antidérapant, 6 mm, naturel',
            'https://picsum.photos/seed/yoga/400/400', c_bien,
            [{'site': 'Decathlon', 'url': 'https://www.decathlon.fr', 'price': 29.99}],
            max_offers=1, _conn=conn)
        create_item(
            wid2, "Diffuseur d'huiles essentielles",
            'Modèle en céramique, 300 ml',
            'https://picsum.photos/seed/diffuseur/400/400', c_bien,
            [
                {'site': 'Amazon', 'url': 'https://www.amazon.fr', 'price': 34.90},
                {'site': 'Nature & Découvertes', 'url': 'https://www.natureetdecouvertes.com', 'price': 45.00},
            ],
            max_offers=2, _conn=conn)
        create_item(
            wid2, 'Coffret bougies parfumées',
            '3 senteurs, cire de soja', '🕯️', c_bien,  # ← emoji
            [{'site': 'Diptyque', 'url': 'https://www.diptyqueparis.com', 'price': 180.00}],
            max_offers=1, _conn=conn)
        create_item(
            wid2, "Set d'aquarelles professionnelles",
            '24 demi-godets, marque Winsor & Newton',
            'https://picsum.photos/seed/aquarelles/400/400', c_loisirs,
            [
                {'site': 'Amazon', 'url': 'https://www.amazon.fr', 'price': 89.99},
                {'site': 'Le Géant des Beaux-Arts', 'url': 'https://www.geant-beaux-arts.fr', 'price': 95.00},
            ],
            max_offers=1, _conn=conn)
        create_item(
            wid2, 'Carnet de croquis A4',
            'Papier 180g, reliure cousue', '📔', c_loisirs,  # ← emoji
            [{'site': 'Le Géant des Beaux-Arts', 'url': 'https://www.geant-beaux-arts.fr', 'price': 18.50}],
            max_offers=None, _conn=conn)

        add_reservation(it20, 'Audrick', _conn=conn)
        add_reservation(it22, 'Léa', _conn=conn)

        # ============================================================
        # 3. Mariage — external, violet
        # ============================================================
        create_wishlist(
            'Mariage Marc & Julie', '[Démo] Marc', 'external',
            'https://www.mariages.net',
            'Notre liste de mariage chez nos partenaires',
            pwd, 'violet', '💍', _conn=conn)

        # ============================================================
        # 4. Mes envies — internal, custom teal
        # ============================================================
        wid4 = create_wishlist(
            'Mes envies', '[Démo] Léa', 'internal', None,
            'Juste comme ça 💫', pwd, 'custom:#0f766e', '✨', _conn=conn)
        c_photo = create_category(wid4, 'Photo', '📷', _conn=conn)
        c_audio = create_category(wid4, 'Audio', '🎧', _conn=conn)
        c_tech = create_category(wid4, 'Tech', '💻', _conn=conn)
        c_voyage = create_category(wid4, 'Voyage', '✈️', _conn=conn)

        create_item(
            wid4, 'Appareil photo Fujifilm X-T5',
            'Boîtier seul, silver',
            'https://picsum.photos/seed/fuji/400/400', c_photo,
            [
                {'site': 'Amazon', 'url': 'https://www.amazon.fr', 'price': 1699.00},
                {'site': 'Digit-Photo', 'url': 'https://www.digit-photo.com', 'price': 1649.00},
            ],
            max_offers=1, _conn=conn)
        create_item(
            wid4, 'Objectif Fujinon 23 mm f/2',
            'Objectif fixe, noir',
            'https://picsum.photos/seed/objectif/400/400', c_photo,
            [{'site': 'Digit-Photo', 'url': 'https://www.digit-photo.com', 'price': 449.00}],
            max_offers=1, _conn=conn)
        create_item(
            wid4, 'Sac photo Peak Design',
            'Everyday Sling 10L, noir',
            'https://picsum.photos/seed/sacphoto/400/400', c_photo,
            [{'site': 'Amazon', 'url': 'https://www.amazon.fr', 'price': 179.00}],
            max_offers=1, _conn=conn)
        create_item(
            wid4, 'AirPods Max',
            'Coloris gris sidéral',
            'https://picsum.photos/seed/airpods/400/400', c_audio,
            [
                {'site': 'Apple', 'url': 'https://www.apple.com/fr', 'price': 629.00},
                {'site': 'Amazon', 'url': 'https://www.amazon.fr', 'price': 549.00},
            ],
            max_offers=1, _conn=conn)
        create_item(
            wid4, 'Enceinte Bluetooth Marshall',
            'Emberton II, noir',
            'https://picsum.photos/seed/enceinte/400/400', c_audio,
            [
                {'site': 'Fnac', 'url': 'https://www.fnac.com', 'price': 149.99},
                {'site': 'Boulanger', 'url': 'https://www.boulanger.com', 'price': 139.00},
            ],
            max_offers=1, _conn=conn)
        create_item(
            wid4, 'Kindle Paperwhite',
            '11e génération, 16 Go, signature edition',
            'https://picsum.photos/seed/kindle/400/400', c_tech,
            [
                {'site': 'Amazon', 'url': 'https://www.amazon.fr', 'price': 189.99},
                {'site': 'Fnac', 'url': 'https://www.fnac.com', 'price': 199.00},
            ],
            max_offers=1, _conn=conn)
        create_item(
            wid4, 'Écran Dell UltraSharp 27"',
            '4K, USB-C, modèle U2723QE',
            'https://picsum.photos/seed/ecran/400/400', c_tech,
            [{'site': 'Dell', 'url': 'https://www.dell.com/fr-fr', 'price': 649.00}],
            max_offers=1, _conn=conn)
        create_item(
            wid4, 'Valise cabine Rimowa',
            'Essential Cabin, 35 L, noire',
            'https://picsum.photos/seed/valise/400/400', c_voyage,
            [{'site': 'Rimowa', 'url': 'https://www.rimowa.com', 'price': 930.00}],
            max_offers=1, _conn=conn)
        it40 = create_item(
            wid4, 'Guide de voyage Japon',
            'Le Routard 2025-2026', '🗺️', c_voyage,  # ← emoji
            [
                {'site': 'Fnac', 'url': 'https://www.fnac.com', 'price': 18.90},
                {'site': 'Amazon', 'url': 'https://www.amazon.fr', 'price': 17.50},
            ],
            max_offers=None, _conn=conn)
        create_item(
            wid4, 'Oreiller de voyage en mousse à mémoire',
            'Housse lavable, étui inclus', '✈️', c_voyage,  # ← emoji
            [{'site': 'Decathlon', 'url': 'https://www.decathlon.fr', 'price': 24.99}],
            max_offers=2, _conn=conn)

        add_reservation(it40, 'Audrick', _conn=conn)

    return True
