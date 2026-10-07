-- queries.sql : requetes SQL utilisees par le pipeline
-- On ne lit que les colonnes dont le pipeline a besoin.

-- =========================================================
-- A. Extraction depuis la base de reference (bookworld_reference.db)
-- =========================================================

-- Requete 1 (avec filtre) : les canaux de vente actifs uniquement
SELECT channel_code, channel_name
FROM channels
WHERE is_active = 1;

-- Requete 2 (enrichissement) : les pays, pour ajouter le nom du pays aux ventes
SELECT country_code, country_name
FROM countries;

-- =========================================================
-- B. Controles sur la base finale (bookworld_final.db)
-- =========================================================

-- Requete 3 : nombre de lignes de chaque table
SELECT (SELECT COUNT(*) FROM countries) AS countries,
       (SELECT COUNT(*) FROM channels) AS channels,
       (SELECT COUNT(*) FROM books) AS books,
       (SELECT COUNT(*) FROM sales) AS sales,
       (SELECT COUNT(*) FROM sales_by_country) AS sales_by_country;

-- Requete 4 (jointure) : totaux par pays recalcules depuis le detail des ventes
SELECT s.country_code,
       c.country_name,
       COUNT(*) AS total_orders,
       SUM(s.quantity) AS total_quantity,
       ROUND(SUM(s.revenue_gbp), 2) AS total_revenue_gbp,
       ROUND(SUM(s.revenue_eur), 2) AS total_revenue_eur
FROM sales AS s
JOIN countries AS c ON c.country_code = s.country_code
GROUP BY s.country_code, c.country_name
ORDER BY s.country_code;

-- Requete 5 : la table finale sales_by_country (celle que l'API exposera)
SELECT country_code, country_name, total_orders, total_quantity,
       total_revenue_gbp, total_revenue_eur
FROM sales_by_country
ORDER BY country_code;