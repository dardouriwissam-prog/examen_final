# api.py - API REST BookWorld : expose les ventes agregees par pays
#
# Lancer l'API :   python api.py
# Documentation :  http://127.0.0.1:8000/docs

import os
import secrets
import sqlite3
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# ------------------------------------------------------------
# CONFIGURATION : si un nom de fichier ou un reglage change,
# on le modifie ICI et nulle part ailleurs.
# ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
FINAL_DB_FILE = "bookworld_final.db"      # base creee par pipeline.py
ENV_FILE = ".env"                         # fichier (non publie sur GitHub) qui contient le token
TOKEN_VARIABLE = "BOOKWORLD_API_TOKEN"    # nom de la variable qui contient le token

HOST = "127.0.0.1"                        # l'API n'est accessible que depuis cet ordinateur
PORT = 8000

API_TITLE = "BookWorld API"
API_VERSION = "1.0"

# Requete SQL (la meme que dans queries.sql)
QUERY_SALES_BY_COUNTRY = """
    SELECT country_code, country_name, total_orders, total_quantity,
           total_revenue_gbp, total_revenue_eur
    FROM sales_by_country
    ORDER BY country_code
"""
# ------------------------------------------------------------

DB_PATH = BASE_DIR / FINAL_DB_FILE


def load_env_file():
    """Lit le fichier .env (lignes NOM=valeur) et les ajoute aux variables d'environnement."""
    path = BASE_DIR / ENV_FILE
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line == "" or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        # setdefault : une variable deja definie dans PowerShell est prioritaire
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


load_env_file()


# ------------------------------------------------------------
# BASE DE DONNEES
# ------------------------------------------------------------
def open_database():
    """Ouvre la base finale en LECTURE SEULE : l'API ne peut rien modifier."""
    return sqlite3.connect(DB_PATH.as_uri() + "?mode=ro", uri=True)


def check_database():
    """Renvoie 'ok' si la base est utilisable, sinon une phrase qui explique le probleme."""
    if not DB_PATH.exists():
        return "base introuvable (" + FINAL_DB_FILE + ") : lancer d'abord 'python pipeline.py'"
    connection = None
    try:
        connection = open_database()
        connection.execute("SELECT COUNT(*) FROM sales_by_country").fetchone()
    except sqlite3.Error as error:
        return "base illisible : " + str(error)
    finally:
        if connection is not None:
            connection.close()
    return "ok"


# ------------------------------------------------------------
# AUTHENTIFICATION PAR TOKEN
# Le client doit envoyer l'en-tete :  Authorization: Bearer <token>
# ------------------------------------------------------------
bearer = HTTPBearer(auto_error=False)


def check_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    """Refuse la requete si le token est absent ou incorrect."""
    expected = os.environ.get(TOKEN_VARIABLE, "")

    # Si le serveur n'a pas de token, on refuse TOUT (jamais d'acces libre par oubli)
    if expected == "":
        raise HTTPException(
            status_code=500,
            detail="Le serveur n'a pas de token configure : definir " + TOKEN_VARIABLE
                   + " (variable d'environnement ou fichier " + ENV_FILE + ")")

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Token manquant : ajouter l'en-tete 'Authorization: Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"})

    # compare_digest : comparaison qui ne revele rien sur le token par le temps de reponse
    if not secrets.compare_digest(credentials.credentials.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(
            status_code=401,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"})


# ------------------------------------------------------------
# FORMAT DES REPONSES (sert aussi a la documentation automatique)
# ------------------------------------------------------------
class CountrySales(BaseModel):
    country_code: str
    country_name: str
    total_orders: int
    total_quantity: int
    total_revenue_gbp: float
    total_revenue_eur: float


class SalesByCountryResponse(BaseModel):
    count: int
    data: list[CountrySales]


# ------------------------------------------------------------
# L'API ET SES ENDPOINTS
# ------------------------------------------------------------
app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description="Expose les ventes de BookWorld agregees par pays. "
                "/health est libre ; /sales-by-country demande un token (en-tete Authorization: Bearer).")


@app.get("/health", summary="L'API fonctionne-t-elle ?",
         responses={503: {"description": "La base finale est introuvable ou illisible"}})
def health():
    """Acces libre (sans token). Repond 'ok' si l'API tourne et si la base finale est lisible."""
    database = check_database()
    if database != "ok":
        return JSONResponse(status_code=503, content={"status": "error", "database": database})
    return {"status": "ok", "database": "ok"}


@app.get("/sales-by-country", response_model=SalesByCountryResponse,
         summary="Ventes agregees par pays",
         dependencies=[Depends(check_token)],
         responses={401: {"description": "Token manquant ou invalide"},
                    503: {"description": "La base finale est introuvable"}})
def sales_by_country():
    """Renvoie une ligne par pays : commandes, livres vendus, chiffre d'affaires en GBP et en EUR."""
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Base finale introuvable (" + FINAL_DB_FILE + ") : lancer d'abord 'python pipeline.py'")

    connection = None
    try:
        connection = open_database()
        connection.row_factory = sqlite3.Row
        rows = connection.execute(QUERY_SALES_BY_COUNTRY).fetchall()
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=500,
            detail="Erreur dans la base finale : " + str(error) + " (relancer 'python pipeline.py')")
    finally:
        if connection is not None:
            connection.close()

    data = [dict(row) for row in rows]
    return {"count": len(data), "data": data}


# ------------------------------------------------------------
# POINT D'ENTREE : python api.py
# ------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host=HOST, port=PORT, use_colors=False)
