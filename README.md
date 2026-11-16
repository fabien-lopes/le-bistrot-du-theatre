# Le Bistrot du Théâtre : site statique

Site du restaurant écrit en HTML et CSS, sans JavaScript, sans cookie et sans service tiers.
Seule la réservation passe encore par le module RestoPro.

## Modifier le contenu

Les horaires, la carte et les spectacles sont dans les blocs `SITE`, `HOURS`, `MENUS` et `EVENTS`
en haut de `build.py`. Après une modification :

```bash
python3 build.py                 # génère dist/
python3 -m http.server 8811 -d dist   # aperçu sur http://127.0.0.1:8811
```

Un spectacle passé sort tout seul de la liste « À l'affiche » à la génération suivante.
Pour voir le site tel qu'il sera à une autre date : `BUILD_DATE=2026-12-20 python3 build.py`.

## Ajouter une photo

Déposez le JPEG d'origine dans `src-images/`, lancez `./images.sh` (il faut `brew install webp`),
puis utilisez son nom sans extension dans `build.py`, par exemple `photo('ma-photo', 'description')`.

## Mettre en ligne

Envoyez le contenu de `dist/` (y compris le fichier caché `.htaccess`) à la racine de l'hébergement.
Le `.htaccess` redirige en 301 les anciennes adresses RestoPro vers les nouvelles pages, force HTTPS,
compresse les pages et règle le cache.

## Reste à faire

- Mentions légales : forme juridique, capital et hébergeur (marqués « à compléter »).
- Logo : il n'existe qu'en PNG de 107 px. Il faut un SVG pour l'afficher net dans l'en-tête.
- Mesure d'audience : l'ancien site avait Google Analytics. Pour garder une mesure sans bandeau
  cookies, il faut un outil exempté de consentement (Plausible ou Matomo configuré selon la CNIL).
- Newsletter et offres d'emploi : à rebrancher si besoin.
