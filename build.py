#!/usr/bin/env python3
"""Builds the static site of Le Bistrot du Théâtre into dist/.

Python 3 standard library only. Everything that changes (hours, menu, shows) lives in the
data blocks at the top of this file: edit them, run `python3 build.py`, upload dist/.

Shows whose date has passed drop off the "upcoming" list by themselves at each build.
Set BUILD_DATE=2026-12-01 to preview the site as of another day.
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
STATIC = ROOT / "static"

# --------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------

SITE = {
    "base_url": "https://www.le-bistrot-du-theatre-restaurant-jouy-le-moutier.fr",
    "name": "Le Bistrot du Théâtre",
    "theatre": "Théâtre Saint-Vincent",
    "phone_display": "01 30 38 06 00",
    "phone_tel": "+33130380600",
    "street": "44 rue Gabriel Lainé",
    "street_note": "anciennement Grande Rue",
    "postal_code": "95280",
    "city": "Jouy-le-Moutier",
    "lat": 49.016892,
    "lon": 2.046311,
    "booking_url": "https://www.le-bistrot-du-theatre-restaurant-jouy-le-moutier.fr/v2/reservation/date?restaurantToken=fa9d587d9bb77d34f49aab063f4bf822",
    "facebook": "https://www.facebook.com/p/Le-Bistrot-du-Th%C3%A9%C3%A2tre-100054685273168/",
    "chef": "Christophe Bayle",
    "company": "LES MIJOTES",
    "siret": "494 944 903",
}
SITE["maps_url"] = (
    "https://www.google.com/maps/search/?api=1&query="
    "Le+Bistrot+du+Th%C3%A9%C3%A2tre+44+rue+Gabriel+Lain%C3%A9+95280+Jouy-le-Moutier"
)
SITE["waze_url"] = f"https://waze.com/ul?ll={SITE['lat']},{SITE['lon']}&navigate=yes"

# One entry per day, Monday first. Each slot is (opens, closes).
HOURS = [
    ("Lundi", []),
    ("Mardi", [("12:00", "15:00")]),
    ("Mercredi", [("12:00", "15:00")]),
    ("Jeudi", [("12:00", "15:00"), ("19:00", "23:00")]),
    ("Vendredi", [("12:00", "15:00"), ("19:00", "23:00")]),
    ("Samedi", [("19:00", "23:00")]),
    ("Dimanche", []),
]

MENUS = [
    {
        "id": "midi",
        "name": "Formule du midi",
        "price": 26,
        "when": "Du mardi au vendredi, le midi",
        "unit": "Entrée 8 € · Plat 16 € · Dessert 7 €",
        "sections": [
            ("Entrées", [
                "Betterave, saumon frais et cervelle de canut",
                "Velouté de butternut, chorizo et croûtons, œuf poché",
            ]),
            ("Plats", [
                "Croustillant de julienne, épinards et beurre amandes citron",
                "Saucisse au couteau, jus à l’échalote et purée maison",
            ]),
            ("Desserts", [
                "Cantal entre-deux, figue rôtie au vin",
                "Crumble aux pommes et fruits rouges, glace yaourt",
                "Mousse au chocolat maison, tuiles aux amandes",
            ]),
        ],
    },
    {
        "id": "soir",
        "name": "La carte du soir",
        "price": 44,
        "when": "Du jeudi au samedi, le soir",
        "unit": "Entrée 12 € · Plat 27 € · Dessert 10 €",
        "sections": [
            ("Entrées", [
                "Os à moelle en croûte d’herbes",
                "Nougat de bœuf et foie gras, pickles",
                "Carpaccio de saint-jacques, crémeux de butternut",
                "Fricassée de girolles, crème de comté, œuf bio au plat et jambon ibérique",
            ]),
            ("Plats", [
                "Lotte et coquillages en waterzoï",
                "Pièce de bœuf, jus moutardé et grenailles",
                "Cocotte de rognons de veau grand-mère",
                "T-bone de veau, échalote confite, tian niçois",
            ]),
            ("Desserts", [
                "Cantal entre-deux, figue au vin",
                "La nouvelle profiterole",
                "Baba au rhum arrangé, fruits frais",
                "Riz au lait, caramel au beurre salé, mendiants",
                "Trois boules au choix : glaces et sorbets artisanaux",
            ]),
        ],
    },
]

# Shows at the Théâtre Saint-Vincent. `online_until`: last day of online booking, phone only after.
EVENTS = [
    {
        "date": "2026-12-11", "time": "19:45", "price": 55,
        "title": "Les Saint-Vincent du Rire",
        "subtitle": "Nouveau spectacle, programmation en cours",
        "description": "Un dîner-spectacle avec le menu du chef et une nouvelle soirée d’humour sur la scène du théâtre.",
        "online_until": "2026-12-06",
    },
    {
        "date": "2026-11-13", "time": "19:45", "price": 55,
        "title": "Les Saint-Vincent du Rire",
        "subtitle": "Dîner-spectacle humour",
        "description": "",
        "online_until": "2026-11-09",
    },
    {
        "date": "2026-10-09", "time": "20:00", "price": 55,
        "title": "Soirée cabaret avec Tony Saint Laurent",
        "subtitle": "Stand-up",
        "description": "",
        "online_until": "2026-10-03",
    },
    {
        "date": "2026-09-18", "time": "19:45", "price": 55,
        "title": "Gigi, Dalida & moi",
        "subtitle": "Spectacle musical humoristique",
        "description": "",
        "online_until": "2026-09-13",
    },
    {
        "date": "2026-07-03", "time": "19:45", "price": 53,
        "title": "Patrick Le Chinois, « Itinéraire Bis »",
        "subtitle": "Seul-en-scène",
        "description": "",
        "online_until": "2026-06-28",
    },
]

# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

PREVIEW = os.environ.get("PREVIEW") == "1"  # demo copy: banner, never indexed
# Site served from a sub-folder (GitHub Pages project site), e.g. BASE_PATH=/le-bistrot-du-theatre
BASE_PATH = os.environ.get("BASE_PATH", "").rstrip("/")
if os.environ.get("BASE_URL"):
    SITE["base_url"] = os.environ["BASE_URL"].rstrip("/")
TODAY = date.fromisoformat(os.environ["BUILD_DATE"]) if os.environ.get("BUILD_DATE") else date.today()
DAYS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
             "septembre", "octobre", "novembre", "décembre"]
MONTHS_ABBR = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]
SCHEMA_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

e = html.escape


def fr_date(d: date, weekday: bool = True) -> str:
    s = f"{d.day if d.day > 1 else '1er'} {MONTHS_FR[d.month - 1]} {d.year}"
    return f"{DAYS_FR[d.weekday()]} {s}" if weekday else s


def fr_time(t: str) -> str:
    h, m = t.split(":")
    return f"{int(h)} h" if m == "00" else f"{int(h)} h {m}"


def slots_fr(slots) -> str:
    return " et ".join(f"{fr_time(a)} à {fr_time(b)}" for a, b in slots) if slots else "Fermé"


def paris_offset(d: date) -> str:
    """UTC offset of Paris on a given day (last Sunday of March to last Sunday of October)."""
    def last_sunday(year, month):
        d0 = date(year, month, 31)
        return d0.replace(day=31 - (d0.weekday() + 1) % 7)
    return "+02:00" if last_sunday(d.year, 3) <= d < last_sunday(d.year, 10) else "+01:00"


def webp_size(path: Path) -> tuple[int, int]:
    b = path.read_bytes()[:30]
    kind = b[12:16]
    if kind == b"VP8 ":
        return int.from_bytes(b[26:28], "little") & 0x3FFF, int.from_bytes(b[28:30], "little") & 0x3FFF
    if kind == b"VP8L":
        bits = int.from_bytes(b[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if kind == b"VP8X":
        return int.from_bytes(b[24:27], "little") + 1, int.from_bytes(b[27:30], "little") + 1
    raise ValueError(f"not a WebP file: {path}")


def variants(name: str) -> list[tuple[int, str]]:
    found = []
    for f in (STATIC / "img").glob(f"{name}-*.webp"):
        m = re.fullmatch(rf"{re.escape(name)}-(\d+)\.webp", f.name)
        if m:
            found.append((int(m.group(1)), f"/img/{f.name}"))
    if not found:
        raise SystemExit(f"image missing: {name} (run ./images.sh)")
    return sorted(found)


def srcset(name: str) -> str:
    return ", ".join(f"{url} {w}w" for w, url in variants(name))


def img(name: str, alt: str, sizes: str = "100vw", eager: bool = False) -> str:
    vs = variants(name)
    w, h = webp_size(STATIC / vs[-1][1].lstrip("/"))
    src = next((url for vw, url in vs if vw >= 960), vs[-1][1])
    load = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return (f'<img src="{src}" srcset="{srcset(name)}" sizes="{sizes}" width="{w}" height="{h}" '
            f'alt="{e(alt)}" {load} decoding="async">')


def photo(name: str, alt: str, ratio: str = "ratio-43", sizes: str = "(min-width:860px) 50vw, 100vw") -> str:
    return f'<figure class="photo {ratio}" style="margin:0">{img(name, alt, sizes)}</figure>'


def events_split():
    evs = sorted(({**ev, "d": date.fromisoformat(ev["date"])} for ev in EVENTS), key=lambda x: x["d"])
    upcoming = [ev for ev in evs if ev["d"] >= TODAY]
    past = [ev for ev in reversed(evs) if ev["d"] < TODAY]
    return upcoming, past


def booking_note(ev) -> str:
    until = date.fromisoformat(ev["online_until"])
    phone = f'<a href="tel:{SITE["phone_tel"]}">{SITE["phone_display"]}</a>'
    if TODAY <= until:
        return f"Réservation en ligne jusqu’au {fr_date(until, weekday=False)}, puis uniquement par téléphone au {phone}."
    return f"La réservation en ligne est close : appelez-nous au {phone}."


def event_card(ev, heading="h3") -> str:
    d = ev["d"]
    until = date.fromisoformat(ev["online_until"])
    cta = (f'<a class="btn btn-primary" href="{e(SITE["booking_url"])}" rel="nofollow">Réserver ma place</a>'
           if TODAY <= until else "")
    desc = f"<p>{e(ev['description'])}</p>" if ev["description"] else ""
    return f"""
<article class="event">
  <div class="event-date" aria-hidden="true"><span class="m">{DAYS_FR[d.weekday()][:3]}.</span><span class="d">{d.day}</span><span class="m">{MONTHS_ABBR[d.month-1]}</span></div>
  <div>
    <span class="eyebrow">{e(ev['subtitle'])}</span>
    <{heading}>{e(ev['title'])}</{heading}>
    <p class="meta"><time datetime="{ev['date']}T{ev['time']}">{fr_date(d).capitalize()} à {fr_time(ev['time'])}</time><span>{ev['price']} € par personne, dîner compris</span></p>
    {desc}
    <p class="note">{booking_note(ev)}</p>
    <div class="actions">{cta}<a class="btn btn-ghost" href="tel:{SITE['phone_tel']}">Appeler le {SITE['phone_display']}</a></div>
  </div>
</article>"""


def hours_table(cls="hours") -> str:
    rows = "".join(
        f'<tr><th scope="row">{day}</th><td{" class=closed" if not slots else ""}>{slots_fr(slots)}</td></tr>'
        for day, slots in HOURS)
    return f'<table class="{cls}"><caption class="sr-only">Horaires d’ouverture</caption><tbody>{rows}</tbody></table>'


def address_html() -> str:
    return (f'<address>{SITE["street"]}<br>{SITE["postal_code"]} {SITE["city"]}</address>')


# --------------------------------------------------------------------------------------
# Structured data
# --------------------------------------------------------------------------------------

def restaurant_ld() -> dict:
    specs = {}
    for i, (_, slots) in enumerate(HOURS):
        for a, b in slots:
            specs.setdefault((a, b), []).append(SCHEMA_DAYS[i])
    return {
        "@type": "Restaurant",
        "@id": f"{SITE['base_url']}/#restaurant",
        "name": SITE["name"],
        "url": f"{SITE['base_url']}/",
        "telephone": SITE["phone_tel"],
        "image": [f"{SITE['base_url']}/og.jpg", f"{SITE['base_url']}{variants('theatre-salle')[-1][1]}"],
        "address": {
            "@type": "PostalAddress", "streetAddress": SITE["street"], "postalCode": SITE["postal_code"],
            "addressLocality": SITE["city"], "addressRegion": "Île-de-France", "addressCountry": "FR",
        },
        "geo": {"@type": "GeoCoordinates", "latitude": SITE["lat"], "longitude": SITE["lon"]},
        "servesCuisine": ["Française", "Traditionnelle", "Cuisine de marché"],
        "priceRange": "26 € à 55 €",
        "acceptsReservations": True,
        "hasMenu": f"{SITE['base_url']}/la-carte/",
        "openingHoursSpecification": [
            {"@type": "OpeningHoursSpecification", "dayOfWeek": days, "opens": a, "closes": b}
            for (a, b), days in specs.items()
        ],
        "sameAs": [SITE["facebook"]],
        "potentialAction": {
            "@type": "ReserveAction",
            "target": {"@type": "EntryPoint", "urlTemplate": SITE["booking_url"],
                       "actionPlatform": ["https://schema.org/DesktopWebPlatform", "https://schema.org/MobileWebPlatform"]},
            "result": {"@type": "FoodEstablishmentReservation", "name": "Réserver une table"},
        },
    }


def event_ld(ev) -> dict:
    start = f"{ev['date']}T{ev['time']}:00{paris_offset(ev['d'])}"
    return {
        "@type": "Event",
        "name": f"Dîner-spectacle : {ev['title']}",
        "startDate": start,
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "description": ev["description"] or f"Dîner-spectacle au {SITE['theatre']}, menu du chef compris.",
        "image": [f"{SITE['base_url']}{variants('theatre-salle')[-1][1]}"],
        "location": {
            "@type": "Place", "name": f"{SITE['theatre']}, {SITE['name']}",
            "address": {"@type": "PostalAddress", "streetAddress": SITE["street"],
                        "postalCode": SITE["postal_code"], "addressLocality": SITE["city"], "addressCountry": "FR"},
        },
        "organizer": {"@id": f"{SITE['base_url']}/#restaurant"},
        "offers": {"@type": "Offer", "price": ev["price"], "priceCurrency": "EUR",
                   "url": SITE["booking_url"], "availability": "https://schema.org/InStock"},
    }


def menu_ld() -> dict:
    return {
        "@type": "Menu",
        "name": f"La carte du {SITE['name']}",
        "url": f"{SITE['base_url']}/la-carte/",
        "inLanguage": "fr",
        "hasMenuSection": [
            {"@type": "MenuSection", "name": m["name"], "description": f"{m['when']}. {m['unit']}.",
             "offers": {"@type": "Offer", "price": m["price"], "priceCurrency": "EUR"},
             "hasMenuSection": [
                 {"@type": "MenuSection", "name": title,
                  "hasMenuItem": [{"@type": "MenuItem", "name": item} for item in items]}
                 for title, items in m["sections"]
             ]}
            for m in MENUS
        ],
    }


def breadcrumb_ld(name: str, path: str) -> dict:
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Accueil", "item": f"{SITE['base_url']}/"},
        {"@type": "ListItem", "position": 2, "name": name, "item": f"{SITE['base_url']}{path}"},
    ]}


# --------------------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------------------

NAV = [
    ("/", "Accueil"),
    ("/la-carte/", "La carte"),
    ("/diners-spectacles/", "Dîners-spectacles"),
    ("/groupes-et-receptions/", "Groupes et réceptions"),
    ("/notre-histoire/", "Notre histoire"),
    ("/contact/", "Accès et horaires"),
]

ICON_MENU = '<svg class="i-open" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>'
ICON_CLOSE = '<svg class="i-close" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>'

CSS = (ROOT / "site.css").read_text()
CSS = re.sub(r"\s*\n\s*", "", re.sub(r"/\*.*?\*/", "", CSS, flags=re.S))


def nav_links(current: str) -> str:
    return "".join(
        f'<li><a href="{href}"{" aria-current=page" if href == current else ""}>{label}</a></li>'
        for href, label in NAV)


def layout(*, path: str, title: str, description: str, body: str, ld: list[dict], preload: tuple | None = None,
           noindex: bool = False) -> str:
    canonical = f"{SITE['base_url']}{path}"
    graph = json.dumps({"@context": "https://schema.org", "@graph": [restaurant_ld(), *ld]},
                       ensure_ascii=False, separators=(",", ":"))
    pre = ""
    if preload:
        name, sizes = preload
        pre = f'<link rel="preload" as="image" type="image/webp" imagesrcset="{srcset(name)}" imagesizes="{sizes}" fetchpriority="high">'
    robots = ('<meta name="robots" content="noindex, nofollow">' if PREVIEW
              else '<meta name="robots" content="noindex, follow">' if noindex else "")
    banner = ('<div style="background:#211916;color:#f2e8d8;text-align:center;font:600 .85rem/1.4 var(--sans);padding:.5rem 1rem">'
              'Maquette, site en préparation. Ce n’est pas le site officiel du restaurant.</div>' if PREVIEW else "")
    year = TODAY.year
    footer_hours = hours_table("hours")
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(description)}">
<link rel="canonical" href="{canonical}">
{robots}
<meta name="theme-color" content="#7a1420">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preload" href="/fonts/fraunces.woff2" as="font" type="font/woff2" crossorigin>
{pre}
<meta property="og:type" content="restaurant">
<meta property="og:locale" content="fr_FR">
<meta property="og:site_name" content="{e(SITE['name'])}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{SITE['base_url']}/og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<style>{CSS}</style>
<script type="application/ld+json">{graph}</script>
</head>
<body>
<a class="skip" href="#contenu">Aller au contenu</a>
{banner}
<header class="site-header">
  <div class="wrap">
    <a class="brand" href="/"><b>Le Bistrot du Théâtre</b><span>{SITE['theatre']} · Jouy-le-Moutier</span></a>
    <nav class="nav-desktop" aria-label="Navigation principale"><ul>{nav_links(path)}</ul></nav>
    <a class="btn btn-primary header-cta" href="{e(SITE['booking_url'])}" rel="nofollow">Réserver</a>
    <details class="nav-mobile">
      <summary aria-label="Ouvrir le menu">{ICON_MENU}{ICON_CLOSE}Menu</summary>
      <nav aria-label="Navigation mobile"><ul>{nav_links(path)}</ul></nav>
    </details>
  </div>
</header>
<main id="contenu">
{body}
</main>
<footer class="site-footer">
  <div class="wrap">
    <div class="grid">
      <div>
        <h2>{SITE['name']}</h2>
        {address_html()}
        <p class="small" style="color:#a79b90">({SITE['street_note']})</p>
        <p><a href="tel:{SITE['phone_tel']}">{SITE['phone_display']}</a></p>
        <p><a href="{SITE['maps_url']}" rel="noopener">Itinéraire Google Maps</a> · <a href="{SITE['waze_url']}" rel="noopener">Waze</a></p>
      </div>
      <div>
        <h2>Horaires</h2>
        {footer_hours}
      </div>
      <div>
        <h2>Le site</h2>
        <ul>{nav_links(path)}<li><a href="{SITE['facebook']}" rel="noopener">Facebook</a></li></ul>
      </div>
    </div>
    <div class="legal"><span>© {year} {SITE['name']}</span><a href="/mentions-legales/">Mentions légales</a></div>
  </div>
</footer>
<div class="callbar">
  <a class="btn btn-ghost" href="tel:{SITE['phone_tel']}">Appeler</a>
  <a class="btn btn-primary" href="{e(SITE['booking_url'])}" rel="nofollow">Réserver</a>
</div>
</body>
</html>
"""


# --------------------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------------------

def menu_summary_cards() -> str:
    return "".join(
        f'<div class="card"><div class="body"><span class="eyebrow">{e(m["when"])}</span>'
        f'<h3>{e(m["name"])} · {m["price"]} €</h3><p>{e(m["unit"])}</p>'
        f'<a class="more" href="/la-carte/#{m["id"]}">Voir le détail</a></div></div>'
        for m in MENUS)


def page_home():
    upcoming, _ = events_split()
    if upcoming:
        next_show = event_card(upcoming[0])
        ld_events = [event_ld(ev) for ev in upcoming]
    else:
        next_show = (f'<div class="event"><div><h3>Prochaine date bientôt annoncée</h3>'
                     f'<p>Appelez-nous au <a href="tel:{SITE["phone_tel"]}">{SITE["phone_display"]}</a> pour connaître la programmation.</p></div></div>')
        ld_events = []
    hero_sizes = "100vw"
    body = f"""
<section class="hero">
  {img('theatre-salle', 'La salle du Théâtre Saint-Vincent, ses fresques, son lustre et ses rideaux rouges', hero_sizes, eager=True)}
  <div class="wrap">
    <span class="eyebrow">Restaurant et théâtre depuis 1811</span>
    <h1>Restaurant et dîners-spectacles à Jouy-le-Moutier</h1>
    <p>Une cuisine française faite maison, au cœur du village, à dix minutes de Cergy. Et à l’étage, un théâtre de 1811 pour les soirées spectacle.</p>
    <div class="actions">
      <a class="btn btn-primary" href="{e(SITE['booking_url'])}" rel="nofollow">Réserver une table</a>
      <a class="btn btn-light" href="/la-carte/">Voir la carte</a>
    </div>
    <ul class="facts">
      <li>Midi du mardi au vendredi</li>
      <li>Soir du jeudi au samedi</li>
      <li><a href="tel:{SITE['phone_tel']}" style="color:inherit">{SITE['phone_display']}</a></li>
    </ul>
  </div>
</section>

<section class="section section-dark" aria-labelledby="spectacle">
  <div class="wrap">
    <span class="eyebrow">Au Théâtre Saint-Vincent</span>
    <h2 id="spectacle">Prochain dîner-spectacle</h2>
    {next_show}
    <p style="margin-top:1.5rem"><a href="/diners-spectacles/">Tous les dîners-spectacles</a></p>
  </div>
</section>

<section class="section" aria-labelledby="cuisine">
  <div class="wrap split">
    <div>
      <span class="eyebrow">La cuisine du chef {SITE['chef']}</span>
      <h2 id="cuisine">Une cuisine maison qui suit les saisons</h2>
      <p class="lead">Tout est fait maison, à partir de produits frais. La carte change avec les saisons et les arrivages, avec des maraîchers et des artisans du coin, pour le pain comme pour la pâtisserie.</p>
      <p>Le midi, une formule courte : deux entrées, deux plats, trois desserts. Le soir, une carte plus étoffée.</p>
      <div class="actions"><a class="btn btn-ghost" href="/la-carte/">Découvrir la carte</a></div>
    </div>
    <div class="mosaic">
      {photo('plat-signature', 'Plat du chef dressé, sauce brune et légumes de saison', 'ratio-45', '(min-width:860px) 25vw, 50vw')}
      {photo('plat-poisson', 'Filet de poisson, sauce crème et petits légumes', 'ratio-11', '(min-width:860px) 25vw, 50vw')}
      {photo('dessert-poire', 'Poire pochée au vin et sa glace', 'ratio-11', '(min-width:860px) 25vw, 50vw')}
    </div>
  </div>
  <div class="wrap"><div class="cards">{menu_summary_cards()}
    <div class="card"><div class="body"><span class="eyebrow">Selon le marché</span><h3>Suggestions du jour</h3><p>Quelques plats du retour de marché, à l’ardoise.</p></div></div>
  </div></div>
</section>

<section class="section section-alt" aria-labelledby="lieux">
  <div class="wrap">
    <span class="eyebrow">Deux salles, deux ambiances</span>
    <h2 id="lieux">Le bistrot en bas, le théâtre à l’étage</h2>
    <div class="cards">
      <article class="card">{photo('bistrot-salle', 'La salle du bistrot avec ses poutres et son carrelage ancien', 'ratio-43', '(min-width:760px) 33vw, 100vw')}
        <div class="body"><h3>Le bistrot</h3><p>Poutres apparentes, cheminée, mobilier en bois : un cadre chaleureux pour le déjeuner comme pour le dîner.</p></div></article>
      <article class="card">{photo('theatre-plafond', 'Le plafond peint et le lustre du théâtre', 'ratio-43', '(min-width:760px) 33vw, 100vw')}
        <div class="body"><h3>Le théâtre</h3><p>Construit en 1811, restauré par les Beaux-Arts de Paris : fresques, balcon ancien, parquet de chêne et grand lustre.</p><a class="more" href="/notre-histoire/">Son histoire</a></div></article>
      <article class="card">{photo('patio', 'Le patio fleuri et son escalier rouge', 'ratio-43', '(min-width:760px) 33vw, 100vw')}
        <div class="body"><h3>Le patio</h3><p>Un petit patio extérieur, ouvert aux invités lors des réceptions.</p></div></article>
    </div>
  </div>
</section>

<section class="section" aria-labelledby="groupes">
  <div class="wrap split reverse">
    <div>
      <span class="eyebrow">Jusqu’à 120 invités</span>
      <h2 id="groupes">Repas de groupe et réceptions</h2>
      <p class="lead">Anniversaire, mariage, repas d’association ou séminaire : le théâtre se privatise et le chef compose le menu avec vous.</p>
      <ul class="checklist"><li>Salle de 120 m² avec scène et loges</li><li>Cocktails et repas</li><li>Formules adaptées à la saison et à vos envies</li></ul>
      <div class="actions"><a class="btn btn-primary" href="/groupes-et-receptions/">Préparer mon événement</a></div>
    </div>
    {photo('table-reception', 'Grande table dressée pour une réception, bouquets de fleurs', 'ratio-43')}
  </div>
</section>

<section class="section section-alt" aria-labelledby="venir">
  <div class="wrap info">
    <div>
      <span class="eyebrow">Nous trouver</span>
      <h2 id="venir">Au cœur du village de Jouy-le-Moutier</h2>
      {address_html()}
      <p class="muted small">({SITE['street_note']}) · À 10 minutes de Cergy-Pontoise</p>
      <a class="big-phone" href="tel:{SITE['phone_tel']}">{SITE['phone_display']}</a>
      <div class="actions" style="margin-top:0"><a class="btn btn-ghost" href="{SITE['maps_url']}" rel="noopener">Itinéraire</a><a class="btn btn-ghost" href="/contact/">Accès et horaires</a></div>
    </div>
    <div>{hours_table()}</div>
  </div>
</section>
"""
    return layout(
        path="/",
        title="Le Bistrot du Théâtre · Restaurant à Jouy-le-Moutier (95)",
        description="Cuisine française faite maison et dîners-spectacles dans un théâtre de 1811, à 10 minutes de Cergy. Formule midi 26 €, carte du soir. Réservation en ligne.",
        body=body, ld=ld_events, preload=("theatre-salle", hero_sizes))


def page_menu():
    blocks = []
    for m in MENUS:
        sections = "".join(
            f"<h3>{e(title)}</h3><ul>{''.join(f'<li>{e(i)}</li>' for i in items)}</ul>"
            for title, items in m["sections"])
        blocks.append(f"""
<section class="menu" id="{m['id']}" aria-labelledby="t-{m['id']}">
  <header><h2 id="t-{m['id']}">{e(m['name'])}</h2><span class="price">{m['price']} €</span></header>
  <p class="when">{e(m['when'])}. Entrée, plat et dessert.</p>
  <p class="unit">À l’unité : {e(m['unit'])}</p>
  {sections}
  <p class="foot">Et quelques suggestions du retour de marché.</p>
</section>""")
    body = f"""
<section class="hero hero-sm">
  {img('plat-mijote', 'Plat mijoté du chef servi dans une assiette creuse', '100vw', eager=True)}
  <div class="wrap">
    <span class="eyebrow">Cuisine française faite maison</span>
    <h1>La carte du Bistrot du Théâtre</h1>
    <p>Le chef {SITE['chef']} renouvelle la carte au fil des saisons. Elle peut changer selon les arrivages.</p>
  </div>
</section>
<section class="section">
  <div class="wrap">
    <div class="menus">{''.join(blocks)}</div>
    <p class="muted small" style="margin-top:1.5rem">Prix nets, service compris. Allergènes : demandez-nous, nous vous renseignons volontiers.</p>
    <div class="actions"><a class="btn btn-primary" href="{e(SITE['booking_url'])}" rel="nofollow">Réserver une table</a><a class="btn btn-ghost" href="tel:{SITE['phone_tel']}">{SITE['phone_display']}</a></div>
    <div class="gallery">
      {photo('plat-viande', 'Pièce de viande, jus réduit et légumes', 'ratio-11', '(min-width:760px) 25vw, 50vw')}
      {photo('plat-poisson', 'Poisson, sauce crème et légumes', 'ratio-11', '(min-width:760px) 25vw, 50vw')}
      {photo('dessert-baba', 'Baba au rhum, crème et fruits frais', 'ratio-11', '(min-width:760px) 25vw, 50vw')}
      {photo('dessert-poire', 'Poire pochée au vin et sa glace', 'ratio-11', '(min-width:760px) 25vw, 50vw')}
    </div>
  </div>
</section>
"""
    return layout(
        path="/la-carte/",
        title="La carte · Le Bistrot du Théâtre, Jouy-le-Moutier",
        description=f"Formule du midi à {MENUS[0]['price']} € et carte du soir à {MENUS[1]['price']} € : cuisine française traditionnelle, faite maison avec des produits frais et de saison.",
        body=body, ld=[menu_ld(), breadcrumb_ld("La carte", "/la-carte/")], preload=("plat-mijote", "100vw"))


def page_shows():
    upcoming, past = events_split()
    if upcoming:
        up = "".join(f'<div style="margin-top:1.25rem">{event_card(ev, "h2")}</div>' for ev in upcoming)
    else:
        up = (f'<div class="event"><div><h2>Prochaine date bientôt annoncée</h2>'
              f'<p>Appelez-nous au <a href="tel:{SITE["phone_tel"]}">{SITE["phone_display"]}</a> ou suivez-nous sur '
              f'<a href="{SITE["facebook"]}" rel="noopener">Facebook</a>.</p></div></div>')
    archive = "".join(
        f'<li><time datetime="{ev["date"]}">{fr_date(ev["d"], weekday=False)}</time><span>{e(ev["title"])}</span></li>'
        for ev in past[:6])
    body = f"""
<section class="hero hero-sm">
  {img('theatre-lustre', 'Le lustre et les fresques du Théâtre Saint-Vincent', '100vw', eager=True)}
  <div class="wrap">
    <span class="eyebrow">Théâtre Saint-Vincent · Jouy-le-Moutier</span>
    <h1>Dîners-spectacles près de Cergy</h1>
    <p>Humour, chanson et seul-en-scène, avec un menu préparé par le chef, dans un théâtre de 1811.</p>
  </div>
</section>
<section class="section section-dark" aria-label="À l’affiche">
  <div class="wrap">
    <span class="eyebrow">À l’affiche</span>
    {up}
  </div>
</section>
<section class="section">
  <div class="wrap split">
    <div>
      <span class="eyebrow">Comment ça se passe</span>
      <h2>Une soirée complète, du dîner au rideau</h2>
      <ul class="checklist">
        <li>Rendez-vous à 19 h 45 dans la salle du théâtre</li>
        <li>Un tarif unique par personne, dîner et spectacle compris</li>
        <li>Réservation en ligne jusqu’à quelques jours avant, puis par téléphone</li>
        <li>Spectacles familiaux, brunchs-spectacles et soirées dansantes au fil de l’année</li>
      </ul>
    </div>
    {photo('humoriste', 'Un humoriste sur la scène du théâtre devant le public', 'ratio-43')}
  </div>
  <div class="wrap" style="margin-top:3rem">
    <h2>Ils sont passés sur scène</h2>
    <ul class="archive">{archive}</ul>
  </div>
</section>
"""
    return layout(
        path="/diners-spectacles/",
        title="Dîners-spectacles près de Cergy · Théâtre Saint-Vincent",
        description="Dîners-spectacles d’humour et de chanson au Théâtre Saint-Vincent de Jouy-le-Moutier, à 10 minutes de Cergy. Dîner et spectacle à prix unique, réservation en ligne.",
        body=body, ld=[*(event_ld(ev) for ev in upcoming), breadcrumb_ld("Dîners-spectacles", "/diners-spectacles/")],
        preload=("theatre-lustre", "100vw"))


def page_groups():
    body = f"""
<section class="hero hero-sm">
  {img('table-fleurs', 'Table de réception dressée avec des bouquets dans la salle du théâtre', '100vw', eager=True)}
  <div class="wrap">
    <span class="eyebrow">Jusqu’à 120 invités</span>
    <h1>Repas de groupe et réceptions</h1>
    <p>Anniversaire, mariage, repas d’association ou séminaire : un lieu qui ne ressemble à aucun autre, et une cuisine faite maison.</p>
  </div>
</section>
<section class="section">
  <div class="wrap split">
    <div>
      <span class="eyebrow">Le lieu</span>
      <h2>Le théâtre privatisé pour vous</h2>
      <p>La salle du Théâtre Saint-Vincent mesure 120 m² et reçoit jusqu’à 120 invités. Elle dispose d’une scène, de loges et d’un petit patio extérieur. Pour un comité plus restreint, le bistrot offre une ambiance plus intime.</p>
      <ul class="checklist"><li>Salle de 120 m², scène, loges et patio</li><li>Le bistrot pour les petits groupes</li></ul>
    </div>
    {photo('theatre-salle', 'La salle du théâtre dressée, vue depuis le balcon', 'ratio-43')}
  </div>
</section>
<section class="section section-alt">
  <div class="wrap split reverse">
    <div>
      <span class="eyebrow">Le traiteur</span>
      <h2>Un menu composé avec le chef</h2>
      <p>Cocktails ou repas : le chef {SITE['chef']} adapte la formule à votre événement, à la saison et à vos envies.</p>
      <div class="cards" style="grid-template-columns:1fr">
        <div class="card"><div class="body"><h3>Événements familiaux</h3><p>Anniversaires, mariages, baptêmes, repas de fête.</p></div></div>
        <div class="card"><div class="body"><h3>Entreprises et associations</h3><p>Séminaires, repas d’équipe, conférences, assemblées.</p></div></div>
      </div>
    </div>
    {photo('table-reception', 'Grande table dressée pour une réception', 'ratio-45')}
  </div>
</section>
<section class="section section-dark">
  <div class="wrap">
    <span class="eyebrow">Votre demande</span>
    <h2>Parlons de votre événement</h2>
    <p>Donnez-nous la date, le nombre d’invités et le type de réception : nous vous rappelons avec une proposition.</p>
    <a class="big-phone" style="color:#fff" href="tel:{SITE['phone_tel']}">{SITE['phone_display']}</a>
    <div class="actions"><a class="btn btn-light" href="{e(SITE['booking_url'])}" rel="nofollow">Faire une demande en ligne</a></div>
  </div>
</section>
"""
    return layout(
        path="/groupes-et-receptions/",
        title="Repas de groupe et réceptions · Le Bistrot du Théâtre",
        description="Privatisez le Théâtre Saint-Vincent à Jouy-le-Moutier pour un anniversaire, un mariage ou un séminaire : jusqu’à 120 invités, menu sur mesure du chef.",
        body=body, ld=[breadcrumb_ld("Groupes et réceptions", "/groupes-et-receptions/")], preload=("table-fleurs", "100vw"))


def page_history():
    body = f"""
<section class="hero hero-sm">
  {img('facade', 'La façade du Bistrot du Théâtre dans la rue du village', '100vw', eager=True)}
  <div class="wrap">
    <span class="eyebrow">Depuis 1811</span>
    <h1>L’histoire du Théâtre Saint-Vincent</h1>
    <p>Une tonnellerie, une épicerie, une salle de bal, puis un théâtre : deux siècles de vie au cœur de Jouy-le-Moutier.</p>
  </div>
</section>
<section class="section">
  <div class="wrap prose">
    <h2>Des commerces au théâtre</h2>
    <p>L’histoire du lieu se confond avec celle du village. Au XVIIIe siècle, le site accueille un atelier de tonnellerie, puis une épicerie et un commerce de vins. Louis Marin Masle y fait construire une première salle de danse.</p>
    <p>En 1923, Maxime Cartry et son épouse Léa reprennent l’épicerie, le commerce de vins et le restaurant. L’établissement se développe, connaît plusieurs gérants puis un déclin. Laurence Cartry entreprend de le faire revivre, jusqu’à l’arrivée de {SITE['chef']} en cuisine en 2007.</p>
    <h2>Un lieu de mémoire et de spectacle</h2>
    <p>Construit en 1811 et restauré par les Beaux-Arts de Paris en 1992, le théâtre a gardé ses fresques, son balcon ancien, son parquet de chêne, sa scène et son lustre central. Il a accueilli fêtes, mariages, banquets, bals et représentations, et perpétue aujourd’hui cette tradition.</p>
  </div>
  <div class="wrap gallery">
    {photo('theatre-plafond', 'Le plafond peint du théâtre', 'ratio-45', '(min-width:760px) 25vw, 50vw')}
    {photo('theatre-lustre', 'Le lustre et la scène', 'ratio-45', '(min-width:760px) 25vw, 50vw')}
    {photo('bistrot-comptoir', 'Le comptoir et le meuble à tiroirs du bistrot', 'ratio-45', '(min-width:760px) 25vw, 50vw')}
    {photo('bistrot-verriere', 'Une table près de la verrière du bistrot', 'ratio-45', '(min-width:760px) 25vw, 50vw')}
  </div>
</section>
<section class="section section-alt">
  <div class="wrap split">
    <h2>Un bistrot de village qui cache un théâtre</h2>
    <div><p>Le chef {SITE['chef']} y cuisine depuis 2007 une cuisine française traditionnelle, généreuse et faite maison.</p>
    <div class="actions"><a class="btn btn-primary" href="{e(SITE['booking_url'])}" rel="nofollow">Réserver une table</a></div></div>
  </div>
</section>
"""
    return layout(
        path="/notre-histoire/",
        title="Notre histoire · Le Théâtre Saint-Vincent de 1811",
        description="De la tonnellerie du XVIIIe siècle au théâtre restauré par les Beaux-Arts : l’histoire du Bistrot du Théâtre et du Théâtre Saint-Vincent à Jouy-le-Moutier.",
        body=body, ld=[breadcrumb_ld("Notre histoire", "/notre-histoire/")], preload=("facade", "100vw"))


def page_contact():
    body = f"""
<section class="section">
  <div class="wrap">
    <span class="eyebrow">Nous trouver</span>
    <h1>Accès, horaires et téléphone</h1>
    <div class="info" style="margin-top:2rem">
      <div>
        <h2>Adresse</h2>
        {address_html()}
        <p class="muted">{SITE['street_note'].capitalize()}, pour les GPS qui ne connaissent pas encore le nouveau nom. Au cœur du village, à 10 minutes de Cergy-Pontoise.</p>
        <div class="actions"><a class="btn btn-primary" href="{SITE['maps_url']}" rel="noopener">Ouvrir dans Google Maps</a><a class="btn btn-ghost" href="{SITE['waze_url']}" rel="noopener">Waze</a></div>
        <h2 style="margin-top:2.5rem">Téléphone</h2>
        <a class="big-phone" href="tel:{SITE['phone_tel']}">{SITE['phone_display']}</a>
        <p>Pour réserver une table, une place en dîner-spectacle ou préparer une réception.</p>
        <div class="actions"><a class="btn btn-primary" href="{e(SITE['booking_url'])}" rel="nofollow">Réserver en ligne</a></div>
      </div>
      <div>
        <h2>Horaires</h2>
        {hours_table()}
        {photo('facade', 'La façade rouge et blanche du Bistrot du Théâtre', 'ratio-43')}
      </div>
    </div>
  </div>
</section>
"""
    return layout(
        path="/contact/",
        title="Adresse, horaires et accès · Le Bistrot du Théâtre",
        description=f"{SITE['street']}, {SITE['postal_code']} {SITE['city']}. Ouvert le midi du mardi au vendredi et le soir du jeudi au samedi. Téléphone {SITE['phone_display']}.",
        body=body, ld=[breadcrumb_ld("Accès et horaires", "/contact/")])


def page_legal():
    todo = '<mark>à compléter</mark>'
    body = f"""
<section class="section">
  <div class="wrap prose">
    <h1>Mentions légales</h1>
    <h2>Éditeur du site</h2>
    <p>{SITE['company']}, exploitant {SITE['name']}<br>{SITE['street']}, {SITE['postal_code']} {SITE['city']}<br>
    SIRET {SITE['siret']} · Forme juridique et capital : {todo}<br>
    Téléphone : {SITE['phone_display']}</p>
    <p>Directeur de la publication : {SITE['company']}</p>
    <h2>Hébergement</h2>
    <p>{todo} (nom, adresse et téléphone de l’hébergeur)</p>
    <h2>Médiation de la consommation</h2>
    <p>En cas de litige, vous pouvez recourir gratuitement au médiateur de la consommation : SMP, 24 rue Albert de Mun, 33000 Bordeaux, <a href="https://www.mediateur-consommation-smp.fr" rel="noopener">mediateur-consommation-smp.fr</a>.</p>
    <h2>Données personnelles</h2>
    <p>Ce site ne dépose aucun cookie et ne contient aucun outil de mesure d’audience. Les réservations en ligne sont gérées par notre prestataire de réservation, selon sa propre politique de confidentialité.</p>
    <h2>Crédits</h2>
    <p>Photographies : {SITE['name']}.</p>
  </div>
</section>
"""
    return layout(
        path="/mentions-legales/",
        title="Mentions légales · Le Bistrot du Théâtre",
        description="Mentions légales du site du Bistrot du Théâtre à Jouy-le-Moutier.",
        body=body, ld=[], noindex=True)


def page_404():
    body = f"""
<section class="section">
  <div class="wrap">
    <span class="eyebrow">Erreur 404</span>
    <h1>Cette page a quitté la scène</h1>
    <p>Elle n’existe pas ou plus. Voici où aller :</p>
    <div class="actions"><a class="btn btn-primary" href="/">Accueil</a><a class="btn btn-ghost" href="/la-carte/">La carte</a><a class="btn btn-ghost" href="/diners-spectacles/">Dîners-spectacles</a></div>
  </div>
</section>
"""
    return layout(path="/404.html", title="Page introuvable · Le Bistrot du Théâtre",
                  description="Page introuvable.", body=body, ld=[], noindex=True)


# Old RestoPro URLs and where they now live (301 in .htaccess, so Google keeps the ranking).
REDIRECTS = {
    "/le-restaurant-le-bistrot-du-theatre-jouy-le-moutier-cristophe-bayle": "/notre-histoire/",
    "/repas-de-groupe-anniversaire-conference-congres-seminaire-le-bistrot-du-theatre-restaurant-jouy-le-moutier-spectacle-cergy": "/groupes-et-receptions/",
    "/programmation-le-bistrot-du-theatre-restaurant-jouy-le-moutier": "/diners-spectacles/",
    "/diners-spectacles-le-bistrot-du-theatre-restaurant-jouy-le-moutier-soiree-artiste-scene-spectacle-musique-chnateur-humouriste-comedyclub-95-cergy": "/diners-spectacles/",
    "/la-carte-le-bistrot-du-theatre-restaurant-jouy-le-moutier-resto-cergy-95": "/la-carte/",
    "/reception-le-bistrot-du-theatre-restaurant-service-traiteur-jouy-le-moutier-cergy-95": "/groupes-et-receptions/",
    "/notre-histoire-le-bistrot-du-theatre-restaurant-jouy-le-moutier": "/notre-histoire/",
    "/adresse-horaires-telephone-le-bistrot-du-theatre-restaurant-jouy-le-moutier-95280-95": "/contact/",
}

HTACCESS = """# Apache (OVH): HTTPS + www, old URLs, compression, cache.
Options -Indexes
ErrorDocument 404 /404.html
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteCond %{HTTPS} off [OR]
RewriteCond %{HTTP_HOST} !^www\\. [NC]
RewriteRule ^ https://www.le-bistrot-du-theatre-restaurant-jouy-le-moutier.fr%{REQUEST_URI} [L,R=301]
</IfModule>
<IfModule mod_alias.c>
{redirects}
</IfModule>
<IfModule mod_deflate.c>
AddOutputFilterByType DEFLATE text/html text/css text/plain text/xml application/xml image/svg+xml application/ld+json
</IfModule>
<IfModule mod_headers.c>
Header always set X-Content-Type-Options "nosniff"
Header always set Referrer-Policy "strict-origin-when-cross-origin"
Header always set Strict-Transport-Security "max-age=31536000"
<FilesMatch "\\.(woff2)$">
Header set Cache-Control "public, max-age=31536000, immutable"
</FilesMatch>
<FilesMatch "\\.(webp|jpg|svg)$">
Header set Cache-Control "public, max-age=2592000"
</FilesMatch>
<FilesMatch "\\.(html|xml|txt)$">
Header set Cache-Control "public, max-age=300, must-revalidate"
</FilesMatch>
</IfModule>
"""

FAVICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#7a1420"/><text x="32" y="45" text-anchor="middle" font-family="Georgia,serif" font-size="38" font-weight="700" fill="#fbf7f0">B</text></svg>
"""


def with_base(page: str) -> str:
    """Prefixes every root-relative URL (links, images, fonts) with BASE_PATH."""
    if not BASE_PATH:
        return page
    page = re.sub(r'((?:href|src)=")/(?!/)', rf"\1{BASE_PATH}/", page)
    page = re.sub(r'(?<=[\s",])/(img|fonts)/', rf"{BASE_PATH}/\1/", page)
    return page.replace("url(/fonts/", f"url({BASE_PATH}/fonts/")


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    for sub in ("img", "fonts"):
        shutil.copytree(STATIC / sub, DIST / sub)
    if (STATIC / "og.jpg").exists():
        shutil.copy(STATIC / "og.jpg", DIST / "og.jpg")

    pages = {
        "/": page_home(),
        "/la-carte/": page_menu(),
        "/diners-spectacles/": page_shows(),
        "/groupes-et-receptions/": page_groups(),
        "/notre-histoire/": page_history(),
        "/contact/": page_contact(),
        "/mentions-legales/": page_legal(),
    }
    for path, content in pages.items():
        out = DIST / path.strip("/") / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(with_base(content))
    (DIST / "404.html").write_text(with_base(page_404()))

    sitemap_paths = [p for p in pages if p != "/mentions-legales/"]
    urls = "".join(f"<url><loc>{SITE['base_url']}{p}</loc><lastmod>{TODAY.isoformat()}</lastmod></url>"
                   for p in sitemap_paths)
    (DIST / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    if PREVIEW:
        (DIST / "robots.txt").write_text("User-agent: *\nDisallow: /\n")
        (DIST / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow\n")
        (DIST / ".nojekyll").write_text("")
    else:
        (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE['base_url']}/sitemap.xml\n")
    redirects = "\n".join(f"Redirect 301 {old} {new}" for old, new in REDIRECTS.items())
    (DIST / ".htaccess").write_text(HTACCESS.replace("{redirects}", redirects))
    (DIST / "favicon.svg").write_text(FAVICON)

    total = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file())
    print(f"dist/ built for {TODAY.isoformat()}: {len(pages) + 1} pages, {total / 1e6:.1f} MB in all")


if __name__ == "__main__":
    main()
