import mimetypes
import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import db

# On Windows, Python's mimetypes reads from the registry and may serve .js as
# text/plain, which browsers reject for <script type="module">. Force correct types.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")

BASE_DIR = Path(__file__).parent

app = FastAPI(title="KFTurbo Stats API")


def _gametypes_filter(request: Request):
    raw = request.query_params.get("gametypes")
    if raw is None:
        return None
    all_gt = db.get_gametypes()
    selected = [v for v in raw.split(",") if v in all_gt]
    return selected if selected else []


def _difficulties_filter(request: Request):
    raw = request.query_params.get("difficulties")
    if raw is None:
        return None
    all_diff = db.get_difficulties()
    selected = []
    for d in raw.split(","):
        try:
            v = int(d)
            if v in all_diff:
                selected.append(v)
        except ValueError:
            pass
    return selected if selected else []


PLAYER_ID_RE = re.compile(r"^player_[a-zA-Z]+$")
SESSION_ID_RE = re.compile(r"^session_[a-zA-Z0-9_]+$")


@app.get("/api/filters")
def api_filters():
    return {
        "gametypes": db.get_gametypes(),
        "difficulties": db.get_difficulties(),
        "gametype_names": db.GAMETYPE_NAMES,
        "difficulty_names": {str(k): v for k, v in db.DIFFICULTY_NAMES.items()},
        "perk_names": db.PERK_NAMES,
    }


@app.get("/api/overview")
def api_overview(request: Request):
    return db.get_aggregate_overview(
        _gametypes_filter(request), _difficulties_filter(request)
    )


@app.get("/api/leaderboards")
def api_leaderboards(request: Request):
    return {
        "players": db.get_all_player_stats(
            _gametypes_filter(request), _difficulties_filter(request)
        )
    }


@app.get("/api/player/{playertableid}")
def api_player(playertableid: str, request: Request):
    if not PLAYER_ID_RE.match(playertableid):
        raise HTTPException(status_code=404)
    data = db.get_player_detail(
        playertableid, _gametypes_filter(request), _difficulties_filter(request)
    )
    if not data:
        raise HTTPException(status_code=404)
    return data


@app.get("/api/sessions")
def api_sessions(request: Request):
    return {
        "sessions": db.get_sessions_list(
            _gametypes_filter(request), _difficulties_filter(request)
        )
    }


@app.get("/api/session/{sessionid}")
def api_session(sessionid: str):
    if not SESSION_ID_RE.match(sessionid):
        raise HTTPException(status_code=404)
    data = db.get_session_detail(sessionid)
    if not data:
        raise HTTPException(status_code=404)
    return data


@app.get("/api/cards")
def api_cards():
    return {"cards": db.get_card_stats(), "card_names": db.CARD_NAMES}


@app.get("/api/perks")
def api_perks(request: Request):
    return {
        "perks": db.get_perk_stats(
            _gametypes_filter(request), _difficulties_filter(request)
        )
    }


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/")
@app.get("/{full_path:path}")
def spa(full_path: str = ""):
    if full_path.startswith("api/") or full_path.startswith("static/"):
        raise HTTPException(status_code=404)
    return FileResponse(BASE_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("TURBO_DASHBOARD_PORT", "5000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
