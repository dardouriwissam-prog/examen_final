# pipeline.py - Pipeline de donnees BookWorld

import os
import sqlite3

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ------------------------------------------------------------
# CONFIGURATION : si un nom de fichier, une adresse ou un reglage
# change, on le modifie ICI et nulle part ailleurs.
# ------------------------------------------------------------
# Fichiers
CSV_FILE = "sales_raw.csv"
DB_FILE = "bookworld_reference.db"
FINAL_DB_FILE = "bookworld_final.db"
SCHEMA_FILE = "schema_final.sql"

# Adresses web
SCRAPING_URL = "https://books.toscrape.com/"
API_URL = "https://api.frankfurter.dev/v1/latest"

# Taux de change : de quelle monnaie vers quelle monnaie
FX_BASE_CURRENCY = "GBP"
FX_TARGET_CURRENCY = "EUR"

# Nombre de secondes d'attente maximum pour un site web
REQUEST_TIMEOUT = 10

# Pays presents dans les ventes mais absents de la base de reference
# (code pays : nom du pays). A completer si un autre pays manque un jour.
MISSING_COUNTRY_NAMES = {"NL": "Netherlands"}

# Nom utilise si un pays reste introuvable
UNKNOWN_COUNTRY_LABEL = "Unknown"

# Table finale sales_by_country : cle primaire (une seule ligne par valeur)
SALES_BY_COUNTRY_KEY = "country_code"

# Table finale sales_by_country : colonnes dans l'ordre exige par l'enonce
SALES_BY_COUNTRY_COLUMNS = [
    "country_code",
    "country_name",
    "total_orders",
    "total_quantity",
    "total_revenue_gbp",
    "total_revenue_eur",
]

# Base finale : les 5 tables, dans l'ordre de remplissage (les tables "parents" d'abord)
FINAL_TABLES = ["countries", "channels", "books", "sales", "sales_by_country"]

# RGPD - liste blanche : SEULES ces colonnes sont copiees dans la table sales.
# Les noms et prenoms des clients n'y figurent pas : ils ne sont pas necessaires.
FINAL_SALES_COLUMNS = [
    "order_id", "order_date", "book_id", "country_code", "channel_code",
    "quantity", "discount_rate", "revenue_gbp", "revenue_eur",
]

# RGPD - securite : si un de ces mots apparait dans le nom d'une colonne
# de la base finale, le pipeline refuse de la creer.
PERSONAL_DATA_WORDS = ["first_name", "last_name", "customer"]

# Requetes SQL (la version finale sera recopiee dans queries.sql)
QUERY_ACTIVE_CHANNELS = """
    SELECT channel_code, channel_name
    FROM channels
    WHERE is_active = 1
"""
QUERY_COUNTRIES = """
    SELECT country_code, country_name
    FROM countries
"""

# Requetes de controle sur la base FINALE
QUERY_FINAL_COUNTS = """
    SELECT (SELECT COUNT(*) FROM countries) AS countries,
           (SELECT COUNT(*) FROM channels) AS channels,
           (SELECT COUNT(*) FROM books) AS books,
           (SELECT COUNT(*) FROM sales) AS sales,
           (SELECT COUNT(*) FROM sales_by_country) AS sales_by_country
"""
QUERY_FINAL_CHECK_BY_COUNTRY = """
    SELECT s.country_code,
           c.country_name,
           COUNT(*) AS total_orders,
           SUM(s.quantity) AS total_quantity,
           ROUND(SUM(s.revenue_gbp), 2) AS total_revenue_gbp,
           ROUND(SUM(s.revenue_eur), 2) AS total_revenue_eur
    FROM sales AS s
    JOIN countries AS c ON c.country_code = s.country_code
    GROUP BY s.country_code, c.country_name
    ORDER BY s.country_code
"""
QUERY_FINAL_SALES_BY_COUNTRY = """
    SELECT country_code, country_name, total_orders, total_quantity,
           total_revenue_gbp, total_revenue_eur
    FROM sales_by_country
    ORDER BY country_code
"""
# ------------------------------------------------------------


# ------------------------------------------------------------
# AFFICHAGE DES ERREURS
# ------------------------------------------------------------
def show_error(step, problem, advice):
    """Affiche une erreur claire : ou, quoi, et que faire."""
    print("")
    print("ERREUR a l'etape :", step)
    print("   Probleme  :", problem)
    print("   Que faire :", advice)
    print("")


def explain_web_error(step, url, error):
    """Explique pourquoi un appel vers un site web a echoue."""
    if isinstance(error, requests.exceptions.Timeout):
        problem = "le site ne repond pas en moins de " + str(REQUEST_TIMEOUT) + " secondes"
        advice = "reessayer plus tard, ou augmenter REQUEST_TIMEOUT en haut du fichier"
    elif isinstance(error, requests.exceptions.ConnectionError):
        problem = "impossible de joindre le site " + url
        advice = "verifier la connexion internet, puis que l'adresse est correcte"
    elif isinstance(error, requests.exceptions.HTTPError):
        code = error.response.status_code
        problem = "le site a repondu par une erreur (code " + str(code) + ") : " + url
        advice = "verifier l'adresse en haut du fichier ; le site est peut-etre en panne"
    else:
        problem = str(error)
        advice = "lire le message ci-dessus ; verifier l'adresse " + url
    show_error(step, problem, advice)


# ------------------------------------------------------------
# EXTRACTION DES 4 SOURCES
# Chaque fonction renvoie les donnees, ou None si elle a echoue.
# ------------------------------------------------------------
def read_csv():
    """Source 1 : lit le fichier CSV des ventes."""
    print("Lecture du fichier CSV...")
    try:
        sales = pd.read_csv(CSV_FILE, dtype=str)
    except FileNotFoundError:
        show_error("lecture du CSV",
                   "fichier introuvable : " + CSV_FILE,
                   "mettre le fichier dans le meme dossier que pipeline.py, ou corriger CSV_FILE")
        return None
    except pd.errors.EmptyDataError:
        show_error("lecture du CSV", "le fichier " + CSV_FILE + " est vide",
                   "verifier que le bon fichier a ete copie")
        return None
    except Exception as error:
        show_error("lecture du CSV", str(error), "verifier le contenu du fichier " + CSV_FILE)
        return None

    print("Nombre de lignes lues :", len(sales))
    return sales


def read_table(query, table_name):
    """Source 2 : execute une requete SQL sur la base de reference."""
    print("Lecture de la table", table_name, "dans la base SQLite...")

    # Attention : sqlite3 cree un fichier VIDE si le fichier n'existe pas.
    # On verifie donc nous-memes qu'il existe.
    if not os.path.exists(DB_FILE):
        show_error("lecture SQLite (" + table_name + ")",
                   "base introuvable : " + DB_FILE,
                   "mettre la base dans le meme dossier que pipeline.py, ou corriger DB_FILE")
        return None

    connection = sqlite3.connect(DB_FILE)
    try:
        result = pd.read_sql_query(query, connection)
    except Exception as error:
        show_error("lecture SQLite (" + table_name + ")",
                   str(error),
                   "verifier que la table et les colonnes de la requete existent (voir queries.sql)")
        return None
    finally:
        connection.close()

    print("Lignes lues :", len(result))
    return result


def scrape_books():
    """Source 3 : recupere le titre et le prix (en pounds) des livres de la page 1."""
    print("Scraping de la page 1 du catalogue...")

    # 1. On telecharge la page web
    try:
        response = requests.get(SCRAPING_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()  # provoque une erreur si le site repond "erreur"
    except requests.exceptions.RequestException as error:
        explain_web_error("scraping du catalogue", SCRAPING_URL, error)
        return None

    # 2. On cherche les livres : chacun est dans <article class="product_pod">
    soup = BeautifulSoup(response.content, "html.parser")
    articles = soup.select("article.product_pod")
    if len(articles) == 0:
        show_error("scraping du catalogue",
                   "la page est telechargee mais aucun livre n'a ete trouve",
                   "le site a peut-etre change : verifier la balise article.product_pod dans scrape_books()")
        return None

    # 3. Pour chaque livre, on lit le titre et le prix
    books = []
    for article in articles:
        try:
            # Le titre COMPLET est dans l'attribut "title" du lien
            # (le texte affiche a l'ecran est coupe avec des "...")
            title = article.h3.a["title"]

            # Le prix ressemble a "51.77" precede du symbole livre :
            # on garde seulement les chiffres et le point
            price_text = article.select_one("p.price_color").text
            price_gbp = float("".join(c for c in price_text if c.isdigit() or c == "."))
        except (AttributeError, KeyError, TypeError, ValueError):
            print("Attention : un livre ignore (titre ou prix illisible)")
            continue
        books.append({"book_name": title, "price_gbp": price_gbp})

    print("Livres recuperes :", len(books))
    return pd.DataFrame(books)


def get_exchange_rate():
    """Source 4 : recupere le taux de change pounds -> euros (API Frankfurter)."""
    print("Recuperation du taux de change...")
    step = "taux de change (API Frankfurter)"
    pair = FX_BASE_CURRENCY + " -> " + FX_TARGET_CURRENCY

    # 1. On appelle l'API, avec la monnaie de depart et celle d'arrivee
    params = {"base": FX_BASE_CURRENCY, "symbols": FX_TARGET_CURRENCY}
    try:
        response = requests.get(API_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except ValueError:
        show_error(step, "l'API a repondu, mais pas dans le format attendu (JSON)",
                   "verifier API_URL en haut du fichier : " + API_URL)
        return None
    except requests.exceptions.RequestException as error:
        explain_web_error(step, API_URL, error)
        return None

    # 2. On cherche le taux dans la reponse, par exemple :
    #    {"base": "GBP", "date": "2026-10-02", "rates": {"EUR": 1.15}}
    if "rates" not in data or FX_TARGET_CURRENCY not in data["rates"]:
        show_error(step, "reponse recue, mais sans le taux " + pair,
                   "reponse de l'API : " + str(data) + " | verifier FX_BASE_CURRENCY et FX_TARGET_CURRENCY")
        return None

    rate = data["rates"][FX_TARGET_CURRENCY]
    print("Taux du", data["date"], ": 1", FX_BASE_CURRENCY, "=", rate, FX_TARGET_CURRENCY)
    return rate


# ------------------------------------------------------------
# NETTOYAGE
# ------------------------------------------------------------
def clean_sales(sales):
    """Nettoie le tableau des ventes : espaces, types, doublons, valeurs invalides."""
    print("Nettoyage des ventes...")
    rows_before = len(sales)

    try:
        # 1. On enleve les espaces parasites autour de tous les textes
        for column in sales.columns:
            sales[column] = sales[column].str.strip()

        # 2. On met les codes pays en majuscules (fr -> FR)
        sales["country_code"] = sales["country_code"].str.upper()

        # 3. On convertit chaque colonne dans le bon type
        #    errors="coerce" : une valeur impossible a convertir devient "vide"
        sales["order_date"] = pd.to_datetime(sales["order_date"], format="%Y-%m-%d", errors="coerce")
        sales["quantity"] = pd.to_numeric(sales["quantity"], errors="coerce")
        sales["discount_rate"] = pd.to_numeric(sales["discount_rate"], errors="coerce")

        # 4. On supprime les commandes en double (meme order_id)
        sales = sales.drop_duplicates(subset="order_id").copy()

        # 5. On supprime les lignes inutilisables
        sales = sales.dropna(subset=["order_date", "quantity", "discount_rate", "country_code", "book_name"])
        sales = sales[sales["quantity"] > 0]
        sales = sales[(sales["discount_rate"] >= 0) & (sales["discount_rate"] <= 1)].copy()

        # La quantite est un nombre entier
        sales["quantity"] = sales["quantity"].astype(int)
    except KeyError as error:
        show_error("nettoyage des ventes", "colonne manquante dans le CSV : " + str(error),
                   "verifier la premiere ligne (les titres de colonnes) de " + CSV_FILE)
        return None

    print("Lignes avant :", rows_before, "| apres :", len(sales),
          "| supprimees :", rows_before - len(sales))
    return sales


# ------------------------------------------------------------
# ENRICHISSEMENT
# ------------------------------------------------------------
def enrich_sales(sales, books, countries, channels, rate):
    """Ajoute aux ventes le prix, le nom du pays et les revenus (GBP et EUR)."""
    print("Enrichissement des ventes...")
    rows_before = len(sales)

    # 1. PRIX : on relie chaque vente au prix du livre grace au titre.
    #    On enleve d'abord les espaces et les titres en double du catalogue,
    #    sinon une vente pourrait apparaitre deux fois.
    books = books.copy()
    books["book_name"] = books["book_name"].str.strip()
    books = books.drop_duplicates(subset="book_name")
    sales = sales.merge(books, on="book_name", how="left")

    no_price = sales["price_gbp"].isna()
    if no_price.sum() > 0:
        print("Attention :", no_price.sum(), "ventes ignorees car le livre n'est pas dans le catalogue scrape :")
        print(sorted(sales.loc[no_price, "book_name"].unique()))
        sales = sales[~no_price].copy()

    # 2. PAYS : on ajoute le nom du pays (how="left" = on garde toutes les ventes,
    #    meme si le pays n'est pas dans la base de reference)
    countries = countries[["country_code", "country_name"]].drop_duplicates(subset="country_code")
    sales = sales.merge(countries, on="country_code", how="left")

    # Pays absents de la base : on utilise le dictionnaire de la configuration
    missing_before = sales["country_name"].isna().sum()
    sales["country_name"] = sales["country_name"].fillna(sales["country_code"].map(MISSING_COUNTRY_NAMES))
    missing_after = sales["country_name"].isna().sum()
    print("Noms de pays completes avec MISSING_COUNTRY_NAMES :", missing_before - missing_after, "ventes")
    if missing_after > 0:
        print("Attention :", missing_after, "ventes avec un pays totalement inconnu :")
        print(sorted(sales.loc[sales["country_name"].isna(), "country_code"].unique()))
        sales["country_name"] = sales["country_name"].fillna(UNKNOWN_COUNTRY_LABEL)

    # 3. CANAUX : simple verification (on ne supprime rien)
    unknown_channel = ~sales["channel_code"].isin(channels["channel_code"])
    if unknown_channel.sum() > 0:
        print("Attention :", unknown_channel.sum(), "ventes sur un canal inactif ou inconnu")

    # 4. REVENUS : quantite x prix x (1 - remise)
    #    On n'arrondit PAS chaque ligne : arrondir ligne par ligne ajoute de petites
    #    erreurs qui se cumulent. On arrondira seulement les totaux.
    sales["revenue_gbp"] = sales["quantity"] * sales["price_gbp"] * (1 - sales["discount_rate"])
    sales["revenue_eur"] = sales["revenue_gbp"] * rate

    # Controle : les jointures ne doivent pas avoir ajoute ou perdu de lignes
    print("Lignes avant :", rows_before, "| apres :", len(sales))
    return sales


# ------------------------------------------------------------
# AGREGATION
# ------------------------------------------------------------
def aggregate_sales(sales):
    """Calcule sales_by_country : une seule ligne par pays (cle primaire : country_code)."""
    print("Agregation par pays...")
    step = "agregation par pays"

    # 0. Y a-t-il des ventes a agreger ?
    if len(sales) == 0:
        show_error(step, "aucune vente a agreger (le tableau est vide)",
                   "verifier les etapes precedentes : nettoyage et enrichissement")
        return None

    try:
        # 1. Un meme code pays doit toujours avoir le meme nom
        names_per_code = sales.groupby(SALES_BY_COUNTRY_KEY)["country_name"].nunique()
        bad_codes = names_per_code[names_per_code > 1]
        if len(bad_codes) > 0:
            show_error(step, "ces codes pays ont plusieurs noms differents : " + str(list(bad_codes.index)),
                       "verifier la table countries et MISSING_COUNTRY_NAMES en haut du fichier")
            return None

        # 2. On regroupe les ventes par pays et on calcule les totaux
        grouped = sales.groupby(SALES_BY_COUNTRY_KEY).agg({
            "country_name": "first",   # le nom du pays
            "order_id": "nunique",     # nombre de commandes differentes
            "quantity": "sum",         # nombre de livres vendus
            "revenue_gbp": "sum",      # chiffre d'affaires en pounds
            "revenue_eur": "sum",      # chiffre d'affaires en euros
        })
    except KeyError as error:
        show_error(step, "colonne introuvable dans les ventes : " + str(error),
                   "verifier que enrich_sales() cree bien cette colonne")
        return None

    # 3. On donne aux colonnes les noms de l'enonce
    result = grouped.reset_index()
    result = result.rename(columns={
        "order_id": "total_orders",
        "quantity": "total_quantity",
        "revenue_gbp": "total_revenue_gbp",
        "revenue_eur": "total_revenue_eur",
    })

    # 4. On arrondit les totaux au centime (et seulement ici)
    result["total_revenue_gbp"] = result["total_revenue_gbp"].round(2)
    result["total_revenue_eur"] = result["total_revenue_eur"].round(2)

    # 5. On met les colonnes dans l'ordre de l'enonce (liste en haut du fichier)
    try:
        result = result[SALES_BY_COUNTRY_COLUMNS]
    except KeyError as error:
        show_error(step, "colonne introuvable pour la table finale : " + str(error),
                   "verifier SALES_BY_COUNTRY_COLUMNS en haut du fichier")
        return None

    # 6. On trie par cle primaire
    result = result.sort_values(SALES_BY_COUNTRY_KEY).reset_index(drop=True)

    # 7. Controles : la cle primaire doit etre unique, et rien ne doit etre perdu
    if result[SALES_BY_COUNTRY_KEY].duplicated().any():
        show_error(step, "la cle primaire " + SALES_BY_COUNTRY_KEY + " n'est pas unique",
                   "verifier l'agregation : il doit y avoir une seule ligne par pays")
        return None

    if result["total_orders"].sum() != len(sales):
        show_error(step, "le total des commandes (" + str(result["total_orders"].sum())
                   + ") ne correspond pas au nombre de ventes (" + str(len(sales)) + ")",
                   "il y a probablement des order_id en double : verifier clean_sales()")
        return None

    if result["total_quantity"].sum() != sales["quantity"].sum():
        show_error(step, "le total des quantites ne correspond pas aux ventes",
                   "verifier l'agregation de la colonne quantity")
        return None

    gap = abs(result["total_revenue_gbp"].sum() - sales["revenue_gbp"].sum())
    if gap > 0.05:
        show_error(step, "le total des revenus en GBP ne correspond pas aux ventes (ecart : " + str(round(gap, 2)) + ")",
                   "verifier le calcul des revenus dans enrich_sales()")
        return None

    print("Controle OK :", result["total_orders"].sum(), "commandes |",
          result["total_quantity"].sum(), "livres |",
          round(result["total_revenue_gbp"].sum(), 2), "GBP |",
          round(result["total_revenue_eur"].sum(), 2), "EUR")
    return result


# ------------------------------------------------------------
# BASE FINALE
# ------------------------------------------------------------
def prepare_final_tables(sales, countries, channels, sales_by_country):
    """Prepare les 5 tableaux a ecrire dans la base finale (sans donnees personnelles)."""
    print("Preparation de la base finale...")
    step = "preparation de la base finale"

    try:
        # 1. Pays : ceux de la base de reference + ceux des ventes qui y manquent (ex : NL)
        final_countries = countries[["country_code", "country_name"]].copy()
        known_codes = list(final_countries["country_code"])
        added = []
        for code in sorted(sales["country_code"].unique()):
            if code not in known_codes:
                name = MISSING_COUNTRY_NAMES.get(code, UNKNOWN_COUNTRY_LABEL)
                added.append({"country_code": code, "country_name": name})
        if len(added) > 0:
            final_countries = pd.concat([final_countries, pd.DataFrame(added)], ignore_index=True)
            print("Pays ajoutes a la base finale :", [row["country_code"] for row in added])

        # 2. Canaux
        final_channels = channels[["channel_code", "channel_name"]].copy()

        # 3. Livres : un par book_id, avec le titre et le prix scrape
        final_books = sales[["book_id", "book_name", "price_gbp"]].drop_duplicates().reset_index(drop=True)

        # 4. Ventes : on ne garde QUE les colonnes de la liste blanche (RGPD)
        final_sales = sales[FINAL_SALES_COLUMNS].copy()
        final_sales["order_date"] = final_sales["order_date"].dt.strftime("%Y-%m-%d")

        # 5. Ventes par pays
        final_by_country = sales_by_country[SALES_BY_COUNTRY_COLUMNS].copy()
    except KeyError as error:
        show_error(step, "colonne introuvable : " + str(error),
                   "verifier FINAL_SALES_COLUMNS et SALES_BY_COUNTRY_COLUMNS en haut du fichier")
        return None

    tables = [("countries", final_countries), ("channels", final_channels), ("books", final_books),
              ("sales", final_sales), ("sales_by_country", final_by_country)]

    # Controles avant d'ecrire (pour donner un message precis plutot qu'une erreur SQL)
    duplicated_books = final_books[final_books["book_id"].duplicated()]["book_id"].tolist()
    if len(duplicated_books) > 0:
        show_error(step, "ces livres ont plusieurs titres ou prix differents : " + str(duplicated_books),
                   "verifier le titre des livres dans le CSV et le scraping")
        return None

    if final_sales["order_id"].duplicated().any():
        show_error(step, "des order_id sont en double dans les ventes", "verifier clean_sales()")
        return None

    missing_channels = sorted(set(final_sales["channel_code"]) - set(final_channels["channel_code"]))
    if len(missing_channels) > 0:
        show_error(step, "ces canaux sont utilises dans les ventes mais absents de la table channels : " + str(missing_channels),
                   "verifier le filtre is_active dans QUERY_ACTIVE_CHANNELS (canal inactif ?)")
        return None

    for table_name, table in tables:
        for column in table.columns:
            for word in PERSONAL_DATA_WORDS:
                if word in column.lower():
                    show_error(step, "la colonne '" + column + "' de la table " + table_name + " ressemble a une donnee personnelle",
                               "retirer cette colonne de la liste blanche FINAL_SALES_COLUMNS (RGPD)")
                    return None

    return tables


def write_final_db(tables):
    """Cree la base finale avec schema_final.sql, puis la remplit."""
    print("Creation de la base finale", FINAL_DB_FILE, "...")
    step = "creation de la base finale"

    if not os.path.exists(SCHEMA_FILE):
        show_error(step, "fichier de structure introuvable : " + SCHEMA_FILE,
                   "mettre schema_final.sql dans le meme dossier que pipeline.py, ou corriger SCHEMA_FILE")
        return False

    with open(SCHEMA_FILE, encoding="utf-8-sig") as file:
        schema = file.read()

    success = False
    connection = sqlite3.connect(FINAL_DB_FILE)
    try:
        connection.execute("PRAGMA foreign_keys = ON")   # SQLite verifie alors les cles etrangeres
        connection.executescript(schema)                 # cree les 5 tables (supprime les anciennes)
        for table_name, table in tables:
            table.to_sql(table_name, connection, if_exists="append", index=False)
        connection.commit()
        success = True
    except Exception as error:
        show_error(step, str(error),
                   "verifier que schema_final.sql correspond aux colonnes preparees ; fermer tout programme qui utilise " + FINAL_DB_FILE)
    finally:
        connection.close()

    if not success and os.path.exists(FINAL_DB_FILE):
        try:
            os.remove(FINAL_DB_FILE)                     # on ne laisse pas une base a moitie remplie
        except OSError:
            pass
    return success


def check_final_db():
    """Controle la base finale en SQL. Renvoie la table sales_by_country lue dans la base."""
    print("Controle de la base finale...")
    step = "controle de la base finale"

    connection = sqlite3.connect(FINAL_DB_FILE)
    try:
        counts = pd.read_sql_query(QUERY_FINAL_COUNTS, connection)
        from_detail = pd.read_sql_query(QUERY_FINAL_CHECK_BY_COUNTRY, connection)
        stored = pd.read_sql_query(QUERY_FINAL_SALES_BY_COUNTRY, connection)
        broken_links = connection.execute("PRAGMA foreign_key_check").fetchall()
        columns = []
        for table_name in FINAL_TABLES:
            for row in connection.execute("PRAGMA table_info(" + table_name + ")"):
                columns.append(row[1])
    except Exception as error:
        show_error(step, str(error), "verifier la base " + FINAL_DB_FILE + " et les requetes QUERY_FINAL_...")
        return None
    finally:
        connection.close()

    # Controle 1 : toutes les cles etrangeres pointent vers une ligne qui existe
    if len(broken_links) > 0:
        show_error(step, str(len(broken_links)) + " cle(s) etrangere(s) cassee(s)", "verifier l'ordre de remplissage des tables")
        return None

    # Controle 2 : aucune colonne de donnee personnelle dans la base
    for column in columns:
        for word in PERSONAL_DATA_WORDS:
            if word in column.lower():
                show_error(step, "colonne suspecte dans la base finale : " + column, "verifier schema_final.sql (RGPD)")
                return None

    # Controle 3 : sales_by_country doit etre identique au recalcul SQL fait depuis le detail
    compared = stored.merge(from_detail, on="country_code", suffixes=("", "_sql"))
    different = []
    for _, row in compared.iterrows():
        if (row["total_orders"] != row["total_orders_sql"] or row["total_quantity"] != row["total_quantity_sql"]
                or abs(row["total_revenue_gbp"] - row["total_revenue_gbp_sql"]) > 0.011
                or abs(row["total_revenue_eur"] - row["total_revenue_eur_sql"]) > 0.011):
            different.append(row["country_code"])
    if len(compared) != len(stored) or len(different) > 0:
        show_error(step, "sales_by_country ne correspond pas au recalcul depuis le detail : " + str(different),
                   "verifier aggregate_sales() et le remplissage de la table sales")
        return None

    row = counts.iloc[0]
    print("Lignes par table :", " | ".join(name + " " + str(row[name]) for name in FINAL_TABLES))
    print("Controle OK : cles etrangeres valides | aucune donnee personnelle | sales_by_country = recalcul SQL depuis le detail")
    return stored


# ------------------------------------------------------------
# POINT D'ENTREE : le pipeline demarre ici
# ------------------------------------------------------------
def main():
    # Etape 1 : extraire les 4 sources
    sales = read_csv()
    channels = read_table(QUERY_ACTIVE_CHANNELS, "channels")
    countries = read_table(QUERY_COUNTRIES, "countries")
    books = scrape_books()
    rate = get_exchange_rate()

    # Si une source a echoue, on s'arrete (les erreurs sont affichees plus haut)
    if sales is None or channels is None or countries is None or books is None or rate is None:
        print("Le pipeline s'arrete : corriger l'erreur affichee ci-dessus, puis relancer.")
        return

    # Etape 2 : nettoyer
    sales = clean_sales(sales)
    if sales is None:
        print("Le pipeline s'arrete : corriger l'erreur affichee ci-dessus, puis relancer.")
        return

    # Etape 3 : enrichir (prix, pays, revenus)
    sales = enrich_sales(sales, books, countries, channels, rate)

    # Etape 4 : agreger par pays
    sales_by_country = aggregate_sales(sales)
    if sales_by_country is None:
        print("Le pipeline s'arrete : corriger l'erreur affichee ci-dessus, puis relancer.")
        return

    # Etape 5 : creer et remplir la base finale (sans donnees personnelles)
    tables = prepare_final_tables(sales, countries, channels, sales_by_country)
    if tables is None or not write_final_db(tables):
        print("Le pipeline s'arrete : corriger l'erreur affichee ci-dessus, puis relancer.")
        return

    # Etape 6 : controler la base finale, puis afficher son contenu
    final_result = check_final_db()
    if final_result is None:
        print("Le pipeline s'arrete : corriger l'erreur affichee ci-dessus, puis relancer.")
        return
    print("Table sales_by_country lue dans la base finale :")
    print(final_result.to_string(index=False))

if __name__ == "__main__":
    main()