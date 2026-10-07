-- schema_final.sql : structure de la base finale (bookworld_final.db)
-- RGPD : aucune donnee personnelle n'est stockee (pas de nom ni de prenom de client).

-- On supprime les anciennes tables (les tables "enfants" d'abord)
-- pour pouvoir relancer le pipeline autant de fois que necessaire.
DROP TABLE IF EXISTS sales_by_country;
DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS books;
DROP TABLE IF EXISTS channels;
DROP TABLE IF EXISTS countries;

-- Table 1 : les pays
CREATE TABLE countries (
    country_code  TEXT PRIMARY KEY,
    country_name  TEXT NOT NULL
);

-- Table 2 : les canaux de vente
CREATE TABLE channels (
    channel_code  TEXT PRIMARY KEY,
    channel_name  TEXT NOT NULL
);

-- Table 3 : les livres (prix en pounds, recuperes par scraping)
CREATE TABLE books (
    book_id    TEXT PRIMARY KEY,
    book_name  TEXT NOT NULL,
    price_gbp  REAL NOT NULL
);

-- Table 4 : les ventes detaillees, une ligne par commande
CREATE TABLE sales (
    order_id       TEXT PRIMARY KEY,
    order_date     DATE NOT NULL,
    book_id        TEXT NOT NULL,
    country_code   TEXT NOT NULL,
    channel_code   TEXT NOT NULL,
    quantity       INTEGER NOT NULL CHECK (quantity > 0),
    discount_rate  REAL NOT NULL CHECK (discount_rate >= 0 AND discount_rate <= 1),
    revenue_gbp    REAL NOT NULL,
    revenue_eur    REAL NOT NULL,
    FOREIGN KEY (book_id)      REFERENCES books (book_id),
    FOREIGN KEY (country_code) REFERENCES countries (country_code),
    FOREIGN KEY (channel_code) REFERENCES channels (channel_code)
);

-- Table 5 : les ventes agregees par pays (le resultat final du projet)
CREATE TABLE sales_by_country (
    country_code       TEXT PRIMARY KEY,
    country_name       TEXT NOT NULL,
    total_orders       INTEGER NOT NULL,
    total_quantity     INTEGER NOT NULL,
    total_revenue_gbp  REAL NOT NULL,
    total_revenue_eur  REAL NOT NULL,
    FOREIGN KEY (country_code) REFERENCES countries (country_code)
);