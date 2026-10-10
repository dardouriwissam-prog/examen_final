# BookWorld — Pipeline de données et API des ventes par pays

BookWorld est une librairie en ligne internationale. Ce projet collecte les données de ventes depuis plusieurs sources (CSV, base SQLite, scraping web, API de taux de change), construit une base SQL finale propre et conforme au RGPD, puis expose les ventes agrégées par pays via une API protégée par un token.

Dépôt GitHub (public) : https://github.com/dardouriwissam-prog/examen_final

**Comment lire ce guide** : les commandes sont données pour **Windows avec PowerShell**. Tapez-les (ou collez-les) **une par une** et attendez que la ligne de commande réapparaisse avant de passer à la suivante. Les blocs gris sont les commandes à taper.

---

## 1. Installer les dépendances

### 1.1 Vérifier les prérequis

Ouvrez PowerShell (menu Démarrer, tapez « PowerShell ») et vérifiez que Python et Git sont installés :

```powershell
python --version
git --version
```

- `python --version` doit afficher `Python 3.10` ou une version plus récente. Sinon, installez Python depuis https://www.python.org/downloads/ et **cochez « Add Python to PATH »** pendant l'installation.
- `git --version` doit afficher un numéro de version. Sinon, installez Git depuis https://git-scm.com/downloads.

Fermez puis rouvrez PowerShell après une installation.

### 1.2 Télécharger le projet

Le dépôt est public : aucune clé ni mot de passe n'est nécessaire pour le télécharger. Placez-vous d'abord dans le dossier de votre choix (ici le Bureau), puis clonez :

```powershell
cd $env:USERPROFILE\Desktop
git clone https://github.com/dardouriwissam-prog/examen_final.git
cd examen_final
```

Vous êtes maintenant dans le dossier du projet. Vérifiez avec `dir` : vous devez voir `pipeline.py`, `api.py`, `requirements.txt`, `README.md`, etc.

### 1.3 Créer l'environnement virtuel

Un environnement virtuel garde les bibliothèques du projet séparées du reste de votre ordinateur.

```powershell
python -m venv .venv
```

Autorisez ensuite l'activation (valable uniquement pour cette fenêtre PowerShell) :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

PowerShell pose la question **« Voulez-vous modifier la stratégie d'exécution ? »**. Tapez **`O`** puis Entrée. (Si aucune question n'apparaît, continuez.)

Activez l'environnement :

```powershell
.\.venv\Scripts\Activate.ps1
```

Si l'activation a réussi, `(.venv)` apparaît **au début de la ligne** de commande. Tant que vous ne le voyez pas, les commandes suivantes ne fonctionneront pas.

### 1.4 Installer les bibliothèques

```powershell
pip install -r requirements.txt
```

L'installation prend une à deux minutes. Elle est terminée quand la ligne de commande réapparaît.

> **À chaque nouvelle fenêtre PowerShell**, il faut se replacer dans le dossier du projet (`cd ...\examen_final`), refaire l'autorisation (`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, réponse `O`) puis l'activation (`.\.venv\Scripts\Activate.ps1`). Sans cela, un message rouge « l'exécution de scripts est désactivée sur ce système » apparaît. L'installation, elle, ne se refait pas.

---

## 2. Exécuter le pipeline

Une connexion internet est nécessaire (scraping et API de taux de change). Dans le dossier du projet, avec `(.venv)` actif :

```powershell
python pipeline.py
```

Le pipeline exécute six étapes dans l'ordre : lecture du CSV, lecture de la base de référence, scraping des livres, récupération des taux de change (API Frankfurter), nettoyage et agrégation, création de la base finale `bookworld_final.db`. En cas d'erreur, un message indique l'étape concernée, le problème et ce qu'il faut faire.

Le pipeline a réussi si les dernières lignes ressemblent à ceci :

```
Lignes par table : countries 11 | channels 3 | books 20 | sales 240 | sales_by_country 8
Controle OK : cles etrangeres valides | aucune donnee personnelle | sales_by_country = recalcul SQL depuis le detail
```

suivies du tableau des 8 pays (BE, DE, ES, FR, IE, IT, NL, PT).

---

## 3. Lancer l'API

L'API a besoin du pipeline déjà exécuté (étape 2) et d'un token.

### 3.1 Créer le token (une seule fois)

Le token est un mot de passe aléatoire que l'API exige pour donner ses résultats. Il est enregistré dans un fichier local `.env`, qui n'est jamais publié sur GitHub.

```powershell
$token = python -c "import secrets; print(secrets.token_urlsafe(32))"
"BOOKWORLD_API_TOKEN=$token" | Set-Content -Encoding ascii .env
```

Ces commandes n'affichent rien : c'est normal. Un fichier `.env` apparaît dans le dossier.

### 3.2 Démarrer l'API

```powershell
python api.py
```

Vous devez voir `Uvicorn running on http://127.0.0.1:8000`. **Cette fenêtre reste occupée tant que l'API fonctionne : ne tapez rien dedans et ne la fermez pas.** Pour arrêter l'API plus tard : `Ctrl+C`.

Si vous voyez `[Errno 10048]`, une autre API tourne déjà : fermez l'ancienne fenêtre (`Ctrl+C`) et relancez.

### 3.3 Interroger l'API

Ouvrez une **deuxième** fenêtre PowerShell. Elle s'ouvre dans un autre dossier : il faut d'abord retourner dans le dossier du projet (adaptez le chemin si vous l'avez cloné ailleurs) :

```powershell
cd $env:USERPROFILE\Desktop\examen_final
```

Vérifiez que l'API répond (accès libre, sans token) :

```powershell
curl.exe http://127.0.0.1:8000/health
```

Réponse attendue : `{"status":"ok","database":"ok"}`

Lisez le token enregistré, puis demandez les ventes par pays :

```powershell
$token = (Get-Content .env | Select-Object -First 1).Split("=")[1]
curl.exe -H "Authorization: Bearer $token" http://127.0.0.1:8000/sales-by-country
```

Réponse attendue : un texte JSON commençant par `{"count":8,"data":[{"country_code":"BE","country_name":"Belgium",...` avec les 8 pays, leur nombre de commandes, la quantité vendue et le chiffre d'affaires en GBP et en EUR.

Sans le token, l'API refuse :

```powershell
curl.exe http://127.0.0.1:8000/sales-by-country
```

Réponse : `{"detail":"Token manquant : ajouter l'en-tete 'Authorization: Bearer <token>'"}`

| Endpoint | Accès | Rôle |
|---|---|---|
| `GET /health` | libre | Vérifie que l'API et la base fonctionnent |
| `GET /sales-by-country` | token requis | Ventes agrégées par pays |
| `GET /docs` | libre | Documentation interactive, à ouvrir dans un navigateur : http://127.0.0.1:8000/docs |

**Variante dans le navigateur.** Taper l'adresse `/sales-by-country` dans la barre du navigateur affiche « Token manquant » : le navigateur n'envoie pas de token tout seul. Pour voir les résultats, passez par la documentation de l'API :

1. Copiez le token dans le presse-papiers (depuis le dossier du projet) :

```powershell
(Get-Content .env | Select-Object -First 1).Split("=")[1] | Set-Clipboard
```

2. Ouvrez http://127.0.0.1:8000/docs puis cliquez sur le bouton **Authorize** (cadenas).
3. Collez le token avec `Ctrl+V` (seulement le token, sans le mot « Bearer »), cliquez sur **Authorize** puis **Close**.
4. Dépliez `GET /sales-by-country`, cliquez sur **Try it out** puis **Execute**. Le code `200` et les 8 pays s'affichent dans « Response body ». La partie « Example Value » plus bas n'est qu'un exemple de format, pas les vraies données.

> **Important : l'API lit le fichier `.env` une seule fois, au démarrage.** Si vous créez ou modifiez le token (3.1) alors que l'API tourne déjà, elle garde l'ancien et répond « Token invalide ». Dans ce cas : arrêtez l'API avec `Ctrl+C` dans sa fenêtre, relancez `python api.py`, puis recopiez le token. Si la fenêtre de l'API a été fermée, rouvrez une fenêtre PowerShell, replacez-vous dans le dossier du projet, activez l'environnement (`.\.venv\Scripts\Activate.ps1`) et relancez `python api.py`.

---

## 4. Authentification : clé SSH pour GitHub

Le code est publié sur GitHub avec une **clé SSH** (aucun mot de passe n'est tapé). Cette section sert à **publier** des modifications ; elle n'est pas nécessaire pour simplement télécharger et exécuter le projet (voir 1.2).

**1. Générer la clé** (appuyez sur Entrée aux questions pour garder les valeurs par défaut) :

```powershell
ssh-keygen -t ed25519 -C "examen-bookworld"
```

Deux fichiers sont créés dans le dossier `.ssh` de votre profil Windows : la clé **privée** (à ne jamais partager ni copier nulle part) et la clé **publique** `id_ed25519.pub`.

**2. Copier la clé publique** dans le presse-papiers :

```powershell
Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub" | Set-Clipboard
```

**3. L'ajouter à GitHub** : connectez-vous sur github.com, puis cliquez sur votre photo > **Settings** > **SSH and GPG keys** > **New SSH key**. Donnez un titre, laissez le type *Authentication Key*, collez la clé (`Ctrl+V`) et validez.

**4. Tester la connexion** :

```powershell
ssh -T git@github.com
```

À la première connexion, SSH demande de confirmer l'identité de GitHub : vérifiez que l'empreinte est `SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU`, puis tapez `yes`. Réponse attendue :

```
Hi dardouriwissam-prog! You've successfully authenticated, but GitHub does not provide shell access.
```

**5. Relier le dossier au dépôt et publier** (la première fois seulement) :

```powershell
git remote add origin git@github.com:dardouriwissam-prog/examen_final.git
git push -u origin main
```

Pour les publications suivantes : `git add .`, `git commit -m "message"`, `git push`.

---

## 5. Fichiers du projet

| Fichier | Rôle |
|---|---|
| `pipeline.py` | Pipeline complet : collecte des 4 sources, nettoyage, création de la base finale, contrôles |
| `api.py` | API FastAPI protégée par token, expose les ventes par pays |
| `requirements.txt` | Liste des bibliothèques Python à installer et leurs versions |
| `sales_raw.csv` | Source 1 : ventes brutes au format CSV |
| `bookworld_reference.db` | Source 2 : base SQLite de référence (pays, canaux) |
| `bookworld_final.db` | Base SQL finale produite par le pipeline (5 tables, sans donnée personnelle) |
| `schema_final.sql` | Création des tables de la base finale (clés primaires, étrangères, contraintes) |
| `schema_base_finale.png` | Schéma visuel de la base finale |
| `queries.sql` | Les 5 requêtes SQL utilisées par le pipeline |
| `.gitignore` | Liste des fichiers locaux exclus de GitHub (`.env`, `.venv`, etc.) |
| `README.md` | Ce guide |
| `.env` | *Local uniquement, jamais publié* : contient le token de l'API |
