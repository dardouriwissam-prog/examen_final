# BookWorld — Pipeline de données et API des ventes par pays

BookWorld est une librairie en ligne internationale. Ce projet collecte les données de ventes depuis plusieurs sources (CSV, base SQLite, scraping web, API de taux de change), construit une base SQL finale propre et conforme au RGPD, puis expose les ventes agrégées par pays via une API protégée par token.

Dépôt : https://github.com/dardouriwissam-prog/examen_final

---

## 1. Installer les dépendances

**Prérequis** : Python 3.10 ou plus récent, et Git. Un accès internet est nécessaire (scraping et API de taux de change).

Cloner le projet (le dépôt est public) puis entrer dans le dossier :

```powershell
git clone https://github.com/dardouriwissam-prog/examen_final.git
cd examen_final
```

Créer et activer un environnement virtuel, puis installer les dépendances :

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 2. Exécuter le pipeline

```powershell
python pipeline.py
```

Le pipeline exécute six étapes : lecture du CSV, lecture de la base de référence, scraping des livres, récupération des taux de change (API Frankfurter), construction de la base finale, contrôles de cohérence. Chaque erreur affiche l'étape concernée, le problème et ce qu'il faut faire.

Résultat attendu à la fin :

```
Lignes par table : countries 11 | channels 3 | books 20 | sales 240 | sales_by_country 8
Controle OK : ...
```

Le fichier `bookworld_final.db` est alors créé (ou recréé).

---

## 3. Lancer l'API

**a) Créer le token de l'API** (une seule fois). Il est stocké dans un fichier local `.env`, jamais publié sur GitHub :

```powershell
$token = python -c "import secrets; print(secrets.token_urlsafe(32))"
"BOOKWORLD_API_TOKEN=$token" | Set-Content -Encoding ascii .env
```

**b) Démarrer l'API** :

```powershell
python api.py
```

L'API écoute sur http://127.0.0.1:8000. Si le token est modifié, il faut redémarrer l'API.

**c) L'interroger** depuis une deuxième fenêtre PowerShell :

```powershell
$token = (Get-Content .env | Select-Object -First 1).Split("=")[1]
curl.exe http://127.0.0.1:8000/health
curl.exe -H "Authorization: Bearer $token" http://127.0.0.1:8000/sales-by-country
```

| Endpoint | Accès | Rôle |
|---|---|---|
| `GET /health` | libre | Vérifie que l'API fonctionne |
| `GET /sales-by-country` | token requis | Ventes agrégées par pays |
| `GET /docs` | libre | Documentation interactive générée automatiquement |

Sans token ou avec un mauvais token, `/sales-by-country` répond `401`.

---

## 4. Authentification

### Token de l'API

L'accès à `/sales-by-country` exige l'en-tête `Authorization: Bearer <token>`. Le token est lu dans le fichier `.env` (variable `BOOKWORLD_API_TOKEN`) et comparé de façon sécurisée (`secrets.compare_digest`). Le fichier `.env` est dans `.gitignore` : il reste sur votre machine.

### Clé SSH pour GitHub

Le dépôt est publié avec une authentification SSH (aucun mot de passe ni token GitHub n'est utilisé).

1. Générer une clé :

```powershell
ssh-keygen -t ed25519 -C "examen-bookworld"
```

2. Copier la clé publique dans le presse-papiers :

```powershell
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub" | Set-Clipboard
```

3. Sur GitHub : **Settings > SSH and GPG keys > New SSH key** (type *Authentication Key*), puis coller la clé publique.

4. Tester la connexion :

```powershell
ssh -T git@github.com
```

Réponse attendue : `Hi dardouriwissam-prog! You've successfully authenticated, but GitHub does not provide shell access.`

5. Relier le dossier au dépôt et publier :

```powershell
git remote add origin git@github.com:dardouriwissam-prog/examen_final.git
git push -u origin main
```

Seule la clé **publique** (`.pub`) est donnée à GitHub. La clé privée reste sur votre ordinateur.

---

## 5. Fichiers du projet

| Fichier | Rôle |
|---|---|
| `pipeline.py` | Pipeline complet : collecte des 4 sources, nettoyage, création de la base finale, contrôles |
| `api.py` | API FastAPI protégée par token, expose les ventes par pays |
| `requirements.txt` | Liste des dépendances Python et de leurs versions |
| `sales_raw.csv` | Source 1 : ventes brutes au format CSV |
| `bookworld_reference.db` | Source 2 : base SQLite de référence (pays, canaux) |
| `bookworld_final.db` | Base SQL finale produite par le pipeline (5 tables, sans donnée personnelle) |
| `schema_final.sql` | Création des tables de la base finale (clés primaires, étrangères, contraintes) |
| `schema_base_finale.png` | Schéma visuel de la base finale |
| `queries.sql` | Les 5 requêtes SQL utilisées par le pipeline |
| `.gitignore` | Exclut du dépôt les fichiers locaux (`.env`, `.venv`, etc.) |
| `README.md` | Ce fichier |
| `.env` | *Local uniquement, non publié* : contient le token de l'API |
