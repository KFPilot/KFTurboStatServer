import json
import os
import sqlite3
import time
from datetime import datetime

DB_PATH = os.environ.get(
    "TURBO_DB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "TurboDatabase.db"),
)

PERK_NAMES = {
    "SHA": "Sharpshooter",
    "DEM": "Demolitions",
    "SUP": "Support Specialist",
    "COM": "Commando",
    "FIR": "Firebug",
    "MED": "Field Medic",
    "BER": "Berserker",
}

GAMETYPE_NAMES = {
    "turbo": "Turbo",
    "turbocardgame": "Card Game",
    "turboplus": "Turbo+",
    "turborandomizer": "Randomizer",
}

DIFFICULTY_NAMES = {
    0: "Unknown",
    4: "Hard",
    5: "Suicidal",
    7: "Hell on Earth",
}
KNOWN_DIFFICULTIES = [4, 5, 7, 0]


def perk_display_name(code):
    if not code:
        return "Unknown"
    return PERK_NAMES.get(code, code)


def difficulty_display_name(value):
    try:
        return DIFFICULTY_NAMES.get(int(value), str(value))
    except (TypeError, ValueError):
        return "Unknown"


def parse_session_time(time_str):
    """Parse 'YYYY-M-D H:M:S' (unpadded) into a datetime, or None on failure."""
    if not time_str:
        return None
    try:
        return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return None


def elapsed_string(time_str, now=None):
    dt = parse_session_time(time_str)
    if dt is None:
        return time_str or ""
    if now is None:
        now = datetime.utcnow()
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "in the future"
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 30:
        return f"{days}d ago"
    months = days // 30
    if months < 12:
        return f"{months}mo ago"
    years = days // 365
    return f"{years}y ago"


with open(os.path.join(os.path.dirname(__file__), "card_names.json")) as f:
    CARD_NAMES = json.load(f)


def card_display_name(card_id):
    if not card_id:
        return "Unknown"
    return CARD_NAMES.get(card_id, card_id)


def gametype_display_name(code):
    if not code:
        return "Unknown"
    return GAMETYPE_NAMES.get(code, code)


def _table_has_column(cur, table, column):
    cols = [row[1] for row in cur.execute(f"PRAGMA table_info([{table}])").fetchall()]
    return column in cols


_cache = {}
CACHE_TTL = 60


def _filter_part(values):
    if values is None:
        return "*"
    if not values:
        return "_"
    return ",".join(sorted(str(v) for v in values))


def _cache_key(base, gametypes, difficulties=None):
    return f"{base}:gt={_filter_part(gametypes)}:diff={_filter_part(difficulties)}"


def _get_cached(key):
    if key in _cache:
        value, ts = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return value
    return None


def _set_cached(key, value):
    _cache[key] = (value, time.time())


def get_db():
    db = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    return db


def _session_where(gametypes, prefix=""):
    """Build a WHERE clause filtering sessiontable by gametypes."""
    if not gametypes:
        return "", []
    col = f"{prefix}gametype" if not prefix else f"{prefix}.gametype"
    placeholders = ",".join("?" for _ in gametypes)
    return f" AND {col} IN ({placeholders})", list(gametypes)


def _get_filtered_session_ids(cur, gametypes, difficulties=None):
    """Return set of sessionids matching the filters, or None if no filter is active.

    When either filter is set but empty (explicit "none selected"), returns set().
    """
    if gametypes is None and difficulties is None:
        return None
    # Either filter being empty means "show nothing"
    if (gametypes is not None and not gametypes) or (
        difficulties is not None and not difficulties
    ):
        return set()
    where_parts = []
    params = []
    if gametypes:
        where_parts.append(f"gametype IN ({','.join('?' for _ in gametypes)})")
        params.extend(gametypes)
    if difficulties:
        where_parts.append(f"difficulty IN ({','.join('?' for _ in difficulties)})")
        params.extend(difficulties)
    where_clause = " WHERE " + " AND ".join(where_parts) if where_parts else ""
    rows = cur.execute(
        f"SELECT sessionid FROM sessiontable{where_clause}", params
    ).fetchall()
    return set(r[0] for r in rows)


def get_difficulties():
    """Return list of difficulty values to display in the filter UI.

    Always includes Hard, Suicidal, and Hell on Earth even if no sessions of
    that difficulty exist in the DB. Any other difficulty values found in the
    DB (e.g. Unknown=0) are appended after.
    """
    db = get_db()
    cur = db.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(sessiontable)").fetchall()]
    extras = []
    if "difficulty" in cols:
        rows = cur.execute(
            "SELECT DISTINCT difficulty FROM sessiontable WHERE difficulty IS NOT NULL"
        ).fetchall()
        present = [r[0] for r in rows]
        extras = sorted(v for v in present if v not in (4, 5, 7))
    db.close()
    return [4, 5, 7] + extras


def get_gametypes():
    db = get_db()
    cur = db.cursor()
    rows = cur.execute(
        "SELECT DISTINCT gametype FROM sessiontable ORDER BY gametype"
    ).fetchall()
    db.close()
    return [r[0] for r in rows]


def _session_filter_clause(gametypes, difficulties):
    """Return (where_sql, params) for filtering sessiontable directly."""
    parts = []
    params = []
    if gametypes:
        parts.append(f"gametype IN ({','.join('?' for _ in gametypes)})")
        params.extend(gametypes)
    if difficulties:
        parts.append(f"difficulty IN ({','.join('?' for _ in difficulties)})")
        params.extend(difficulties)
    return (" WHERE " + " AND ".join(parts) if parts else "", params)


def get_aggregate_overview(gametypes=None, difficulties=None):
    key = _cache_key("overview", gametypes, difficulties)
    cached = _get_cached(key)
    if cached:
        return cached

    # Either filter explicitly empty = show nothing
    if (gametypes is not None and not gametypes) or (
        difficulties is not None and not difficulties
    ):
        result = {
            "total_sessions": 0,
            "total_players": 0,
            "status_counts": {},
            "top_maps": [],
            "recent_sessions": [],
        }
        _set_cached(key, result)
        return result

    db = get_db()
    cur = db.cursor()

    where_clause, params = _session_filter_clause(gametypes, difficulties)

    total_sessions = cur.execute(
        f"SELECT COUNT(*) FROM sessiontable{where_clause}", params
    ).fetchone()[0]
    total_players = cur.execute("SELECT COUNT(*) FROM playertable").fetchone()[0]

    status_counts = {}
    for row in cur.execute(
        f"SELECT status, COUNT(*) as cnt FROM sessiontable{where_clause} GROUP BY status",
        params,
    ):
        status_counts[row["status"]] = row["cnt"]

    # Reclassify InProgress sessions whose session table has 0 rows as Abort
    if status_counts.get("InProgress", 0) > 0:
        ip_where = where_clause + (
            " AND status='InProgress'" if where_clause else " WHERE status='InProgress'"
        )
        ip_sessions = cur.execute(
            f"SELECT sessionid FROM sessiontable{ip_where}", params
        ).fetchall()
        empty_count = 0
        for s in ip_sessions:
            sid = s[0]
            table_exists = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (sid,)
            ).fetchone()
            if not table_exists:
                empty_count += 1
                continue
            row_count = cur.execute(f"SELECT COUNT(*) FROM [{sid}]").fetchone()[0]
            if row_count == 0:
                empty_count += 1
        if empty_count > 0:
            status_counts["InProgress"] -= empty_count
            if status_counts["InProgress"] <= 0:
                del status_counts["InProgress"]
            status_counts["Abort"] = status_counts.get("Abort", 0) + empty_count

    # Merge "Ended" into "Abort"
    if "Ended" in status_counts:
        status_counts["Abort"] = status_counts.get("Abort", 0) + status_counts.pop(
            "Ended"
        )

    map_counts = []
    for row in cur.execute(
        f"SELECT map, COUNT(*) as cnt FROM sessiontable{where_clause} GROUP BY map ORDER BY cnt DESC LIMIT 10",
        params,
    ):
        map_counts.append({"map": row["map"], "count": row["cnt"]})

    # Newest sessions: parse time in Python because the column is unpadded ('2026-4-11 8:4:34')
    # which sorts incorrectly as a string in SQL.
    all_sessions = cur.execute(
        f"SELECT sessionid, version, gametype, status, map, time, difficulty FROM sessiontable{where_clause}",
        params,
    ).fetchall()
    now = datetime.utcnow()
    parsed = []
    for row in all_sessions:
        dt = parse_session_time(row["time"])
        parsed.append((dt or datetime.min, row))
    parsed.sort(key=lambda x: x[0], reverse=True)
    recent_sessions = []
    for dt, row in parsed[:5]:
        status = row["status"]
        if status == "Ended":
            status = "Abort"
        recent_sessions.append(
            {
                "sessionid": row["sessionid"],
                "version": row["version"],
                "gametype": row["gametype"],
                "status": status,
                "map": row["map"],
                "time": row["time"],
                "elapsed": elapsed_string(row["time"], now),
                "difficulty": row["difficulty"],
            }
        )

    db.close()
    result = {
        "total_sessions": total_sessions,
        "total_players": total_players,
        "status_counts": status_counts,
        "top_maps": map_counts,
        "recent_sessions": recent_sessions,
    }
    _set_cached(key, result)
    return result


def get_all_player_stats(gametypes=None, difficulties=None):
    key = _cache_key("all_player_stats", gametypes, difficulties)
    cached = _get_cached(key)
    if cached:
        return cached

    db = get_db()
    cur = db.cursor()

    session_ids = _get_filtered_session_ids(cur, gametypes, difficulties)

    players = cur.execute(
        "SELECT playerid, playertableid, playername, deaths, wincount, losecount FROM playertable"
    ).fetchall()

    result = []
    for p in players:
        tableid = p["playertableid"]
        exists = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tableid,)
        ).fetchone()
        if not exists:
            continue

        if session_ids is not None:
            if not session_ids:
                continue
            placeholders = ",".join("?" for _ in session_ids)
            session_filter = f" WHERE sessionid IN ({placeholders})"
            filter_params = list(session_ids)
        else:
            session_filter = ""
            filter_params = []

        row = cur.execute(
            f"""
            SELECT
                SUM(kills) as kills, SUM(kills_fp) as kills_fp, SUM(kills_sc) as kills_sc,
                SUM(damage) as damage, SUM(damage_fp) as damage_fp, SUM(damage_sc) as damage_sc,
                SUM(shotsfired) as shotsfired, SUM(meleeswings) as meleeswings,
                SUM(shotshit) as shotshit, SUM(shotsheadshot) as shotsheadshot,
                SUM(reloads) as reloads, SUM(heals) as heals,
                SUM(damagetaken) as damagetaken, SUM(deaths) as deaths,
                COUNT(*) as waves_played
            FROM [{tableid}]{session_filter}
        """,
            filter_params,
        ).fetchone()

        if not row["waves_played"]:
            continue

        # Win/loss counts need recalculating when filtered
        if session_ids is not None:
            wins = 0
            losses = 0
            player_sessions = cur.execute(
                f"SELECT DISTINCT sessionid FROM [{tableid}]{session_filter}",
                filter_params,
            ).fetchall()
            for ps in player_sessions:
                sid = ps[0]
                status = cur.execute(
                    "SELECT status FROM sessiontable WHERE sessionid=?", (sid,)
                ).fetchone()
                if status:
                    if status[0] == "Win":
                        wins += 1
                    elif status[0] == "Lose":
                        losses += 1
        else:
            wins = p["wincount"] or 0
            losses = p["losecount"] or 0

        total_shots = (row["shotsfired"] or 0) + (row["meleeswings"] or 0)
        accuracy = (row["shotshit"] or 0) / total_shots * 100 if total_shots > 0 else 0
        headshot_pct = (
            (row["shotsheadshot"] or 0) / (row["shotshit"] or 1) * 100
            if (row["shotshit"] or 0) > 0
            else 0
        )
        games = wins + losses
        win_rate = wins / games * 100 if games > 0 else 0

        result.append(
            {
                "playerid": p["playerid"],
                "playertableid": tableid,
                "playername": p["playername"],
                "kills": row["kills"] or 0,
                "kills_fp": row["kills_fp"] or 0,
                "kills_sc": row["kills_sc"] or 0,
                "damage": row["damage"] or 0,
                "damage_fp": row["damage_fp"] or 0,
                "damage_sc": row["damage_sc"] or 0,
                "shotsfired": row["shotsfired"] or 0,
                "meleeswings": row["meleeswings"] or 0,
                "shotshit": row["shotshit"] or 0,
                "shotsheadshot": row["shotsheadshot"] or 0,
                "reloads": row["reloads"] or 0,
                "heals": row["heals"] or 0,
                "damagetaken": row["damagetaken"] or 0,
                "deaths": row["deaths"] or 0,
                "waves_played": row["waves_played"] or 0,
                "wins": wins,
                "losses": losses,
                "accuracy": round(accuracy, 1),
                "headshot_pct": round(headshot_pct, 1),
                "win_rate": round(win_rate, 1),
            }
        )

    db.close()
    _set_cached(key, result)
    return result


def get_player_detail(playertableid, gametypes=None, difficulties=None):
    db = get_db()
    cur = db.cursor()

    player = cur.execute(
        "SELECT * FROM playertable WHERE playertableid=?", (playertableid,)
    ).fetchone()
    if not player:
        db.close()
        return None

    exists = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (playertableid,)
    ).fetchone()
    if not exists:
        db.close()
        return {
            "player": dict(player),
            "waves": [],
            "perk_summary": [],
            "session_summary": [],
        }

    session_ids = _get_filtered_session_ids(cur, gametypes, difficulties)

    if session_ids is not None:
        if not session_ids:
            db.close()
            return {
                "player": dict(player),
                "waves": [],
                "perk_summary": [],
                "session_summary": [],
            }
        placeholders = ",".join("?" for _ in session_ids)
        session_filter = f" WHERE sessionid IN ({placeholders})"
        filter_params = list(session_ids)
    else:
        session_filter = ""
        filter_params = []

    waves = [
        dict(r)
        for r in cur.execute(
            f"SELECT * FROM [{playertableid}]{session_filter} ORDER BY sessionid, wave",
            filter_params,
        ).fetchall()
    ]

    # Per-perk aggregation
    has_perk = _table_has_column(cur, playertableid, "perk")
    perk_select = "perk" if has_perk else "'Unknown' as perk"
    group_by = " GROUP BY perk" if has_perk else ""
    perk_summary = []
    for row in cur.execute(
        f"""
        SELECT {perk_select},
            COUNT(*) as waves_played,
            SUM(kills) as kills, SUM(kills_fp) as kills_fp, SUM(kills_sc) as kills_sc,
            SUM(damage) as damage, SUM(shotsfired) as shotsfired, SUM(meleeswings) as meleeswings,
            SUM(shotshit) as shotshit, SUM(shotsheadshot) as shotsheadshot,
            SUM(heals) as heals, SUM(damagetaken) as damagetaken, SUM(deaths) as deaths
        FROM [{playertableid}]{session_filter}{group_by}
    """,
        filter_params,
    ).fetchall():
        total_shots = (row["shotsfired"] or 0) + (row["meleeswings"] or 0)
        accuracy = (row["shotshit"] or 0) / total_shots * 100 if total_shots > 0 else 0
        perk_summary.append(
            {
                "perk": perk_display_name(row["perk"]),
                "waves_played": row["waves_played"],
                "kills": row["kills"] or 0,
                "kills_fp": row["kills_fp"] or 0,
                "kills_sc": row["kills_sc"] or 0,
                "damage": row["damage"] or 0,
                "heals": row["heals"] or 0,
                "deaths": row["deaths"] or 0,
                "accuracy": round(accuracy, 1),
            }
        )

    # Per-session summary
    session_id_list = list(set(w["sessionid"] for w in waves))
    session_summary = []
    for sid in session_id_list:
        session_info = cur.execute(
            "SELECT * FROM sessiontable WHERE sessionid=?", (sid,)
        ).fetchone()
        session_waves = [w for w in waves if w["sessionid"] == sid]
        perks_used = list(
            set(
                perk_display_name(w.get("perk", ""))
                for w in session_waves
                if w.get("perk")
            )
        )
        session_summary.append(
            {
                "sessionid": sid,
                "map": session_info["map"] if session_info else "Unknown",
                "status": session_info["status"] if session_info else "Unknown",
                "waves_played": len(session_waves),
                "perks": ", ".join(perks_used) if perks_used else "Unknown",
                "kills": sum(w["kills"] or 0 for w in session_waves),
                "damage": sum(w["damage"] or 0 for w in session_waves),
            }
        )

    db.close()
    return {
        "player": dict(player),
        "waves": waves,
        "perk_summary": perk_summary,
        "session_summary": session_summary,
    }


def get_card_stats():
    cached = _get_cached("card_stats")
    if cached:
        return cached

    db = get_db()
    cur = db.cursor()

    cards = []
    for row in cur.execute("SELECT * FROM cardtable ORDER BY selectedcount DESC"):
        shown = row["showncount"] or 0
        selected = row["selectedcount"] or 0
        wins = row["wincount"] or 0
        losses = row["losecount"] or 0
        pick_rate = selected / shown * 100 if shown > 0 else 0
        games = wins + losses
        win_rate = wins / games * 100 if games > 0 else 0
        cards.append(
            {
                "cardid": row["cardid"],
                "shown": shown,
                "selected": selected,
                "wins": wins,
                "losses": losses,
                "pick_rate": round(pick_rate, 1),
                "win_rate": round(win_rate, 1),
            }
        )

    db.close()
    _set_cached("card_stats", cards)
    return cards


def get_perk_stats(gametypes=None, difficulties=None):
    key = _cache_key("perk_stats", gametypes, difficulties)
    cached = _get_cached(key)
    if cached:
        return cached

    db = get_db()
    cur = db.cursor()

    session_ids = _get_filtered_session_ids(cur, gametypes, difficulties)

    # Find all per-player tables (exclude the master 'playertable')
    player_tables = [
        row[0]
        for row in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'player_%'"
        ).fetchall()
        if row[0] != "playertable"
    ]

    if session_ids is not None:
        if not session_ids:
            db.close()
            _set_cached(key, [])
            return []
        placeholders = ",".join("?" for _ in session_ids)
        session_filter = f" WHERE sessionid IN ({placeholders})"
        filter_params = list(session_ids)
    else:
        session_filter = ""
        filter_params = []

    perk_data = {}
    for table in player_tables:
        has_perk = _table_has_column(cur, table, "perk")
        perk_select = "perk" if has_perk else "'Unknown' as perk"
        group_by = " GROUP BY perk" if has_perk else ""
        for row in cur.execute(
            f"""
            SELECT {perk_select},
                COUNT(*) as waves,
                SUM(kills) as kills, SUM(kills_fp) as kills_fp, SUM(kills_sc) as kills_sc,
                SUM(damage) as damage, SUM(damage_fp) as damage_fp, SUM(damage_sc) as damage_sc,
                SUM(shotsfired) as shotsfired, SUM(meleeswings) as meleeswings,
                SUM(shotshit) as shotshit, SUM(shotsheadshot) as shotsheadshot,
                SUM(heals) as heals, SUM(damagetaken) as damagetaken, SUM(deaths) as deaths
            FROM [{table}]{session_filter}{group_by}
        """,
            filter_params,
        ).fetchall():
            if not row["waves"]:
                continue
            perk = perk_display_name(row["perk"])
            if perk not in perk_data:
                perk_data[perk] = {
                    "perk": perk,
                    "waves": 0,
                    "unique_players": set(),
                    "kills": 0,
                    "kills_fp": 0,
                    "kills_sc": 0,
                    "damage": 0,
                    "damage_fp": 0,
                    "damage_sc": 0,
                    "shotsfired": 0,
                    "meleeswings": 0,
                    "shotshit": 0,
                    "shotsheadshot": 0,
                    "heals": 0,
                    "damagetaken": 0,
                    "deaths": 0,
                }
            d = perk_data[perk]
            d["waves"] += row["waves"] or 0
            d["unique_players"].add(table)
            for col in [
                "kills",
                "kills_fp",
                "kills_sc",
                "damage",
                "damage_fp",
                "damage_sc",
                "shotsfired",
                "meleeswings",
                "shotshit",
                "shotsheadshot",
                "heals",
                "damagetaken",
                "deaths",
            ]:
                d[col] += row[col] or 0

    result = []
    for perk, d in sorted(perk_data.items(), key=lambda x: x[1]["waves"], reverse=True):
        total_shots = d["shotsfired"] + d["meleeswings"]
        accuracy = d["shotshit"] / total_shots * 100 if total_shots > 0 else 0
        waves = d["waves"] if d["waves"] > 0 else 1
        result.append(
            {
                "perk": perk,
                "waves": d["waves"],
                "unique_players": len(d["unique_players"]),
                "kills": d["kills"],
                "kills_fp": d["kills_fp"],
                "kills_sc": d["kills_sc"],
                "kills_other": d["kills"] - d["kills_fp"] - d["kills_sc"],
                "damage": d["damage"],
                "damage_fp": d["damage_fp"],
                "damage_sc": d["damage_sc"],
                "heals": d["heals"],
                "deaths": d["deaths"],
                "accuracy": round(accuracy, 1),
                "kills_per_wave": round(d["kills"] / waves, 1),
                "damage_per_wave": round(d["damage"] / waves, 1),
                "heals_per_wave": round(d["heals"] / waves, 1),
            }
        )

    db.close()
    _set_cached(key, result)
    return result


def get_sessions_list(gametypes=None, difficulties=None):
    """Return list of all sessions (filtered), newest first."""
    key = _cache_key("sessions_list", gametypes, difficulties)
    cached = _get_cached(key)
    if cached:
        return cached

    if (gametypes is not None and not gametypes) or (difficulties is not None and not difficulties):
        _set_cached(key, [])
        return []

    db = get_db()
    cur = db.cursor()
    where_clause, params = _session_filter_clause(gametypes, difficulties)
    rows = cur.execute(
        f"SELECT sessionid, version, gametype, status, map, time, difficulty FROM sessiontable{where_clause}",
        params,
    ).fetchall()

    now = datetime.utcnow()
    parsed = []
    for row in rows:
        dt = parse_session_time(row["time"])
        parsed.append((dt or datetime.min, row))
    parsed.sort(key=lambda x: x[0], reverse=True)

    result = []
    for dt, row in parsed:
        status = row["status"]
        if status == "Ended":
            status = "Abort"
        table_exists = cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (row["sessionid"],)
        ).fetchone()
        waves = 0
        if table_exists:
            waves = cur.execute(f"SELECT COUNT(*) FROM [{row['sessionid']}]").fetchone()[0]
        result.append({
            "sessionid": row["sessionid"],
            "version": row["version"],
            "gametype": row["gametype"],
            "status": status,
            "map": row["map"],
            "time": row["time"],
            "elapsed": elapsed_string(row["time"], now),
            "difficulty": row["difficulty"],
            "waves": waves,
        })

    db.close()
    _set_cached(key, result)
    return result


def get_session_detail(sessionid):
    """Return detailed stats for a single session."""
    db = get_db()
    cur = db.cursor()

    session = cur.execute(
        "SELECT sessionid, version, gametype, status, map, time, difficulty FROM sessiontable WHERE sessionid=?",
        (sessionid,),
    ).fetchone()
    if not session:
        db.close()
        return None

    status = session["status"]
    if status == "Ended":
        status = "Abort"

    table_exists = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (sessionid,)
    ).fetchone()
    waves = []
    if table_exists:
        for row in cur.execute(f"SELECT wave, status, players FROM [{sessionid}] ORDER BY wave"):
            try:
                player_ids = json.loads(row["players"]) if row["players"] else []
            except (TypeError, ValueError):
                player_ids = []
            waves.append({
                "wave": row["wave"],
                "status": row["status"],
                "player_count": len(player_ids),
            })

    player_tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'player_%'"
    ).fetchall() if r[0] != "playertable"]

    participants = []
    for ptable in player_tables:
        has_perk = _table_has_column(cur, ptable, "perk")
        perk_col = "perk" if has_perk else "''"
        rows = cur.execute(
            f"""SELECT COUNT(*) as waves_played,
                    SUM(kills) as kills, SUM(kills_fp) as kills_fp, SUM(kills_sc) as kills_sc,
                    SUM(damage) as damage,
                    SUM(shotsfired) as shotsfired, SUM(meleeswings) as meleeswings,
                    SUM(shotshit) as shotshit, SUM(shotsheadshot) as shotsheadshot,
                    SUM(heals) as heals, SUM(damagetaken) as damagetaken, SUM(deaths) as deaths,
                    GROUP_CONCAT(DISTINCT {perk_col}) as perks
                FROM [{ptable}] WHERE sessionid = ?""",
            (sessionid,),
        ).fetchall()
        for row in rows:
            if not row["waves_played"]:
                continue
            p = cur.execute(
                "SELECT playername, playerid FROM playertable WHERE playertableid=?", (ptable,)
            ).fetchone()
            if not p:
                continue
            perks_raw = (row["perks"] or "").split(",")
            perks = [perk_display_name(pk) for pk in perks_raw if pk]
            total_shots = (row["shotsfired"] or 0) + (row["meleeswings"] or 0)
            accuracy = (row["shotshit"] or 0) / total_shots * 100 if total_shots > 0 else 0
            participants.append({
                "playertableid": ptable,
                "playername": p["playername"],
                "waves_played": row["waves_played"],
                "kills": row["kills"] or 0,
                "kills_fp": row["kills_fp"] or 0,
                "kills_sc": row["kills_sc"] or 0,
                "damage": row["damage"] or 0,
                "heals": row["heals"] or 0,
                "damagetaken": row["damagetaken"] or 0,
                "deaths": row["deaths"] or 0,
                "accuracy": round(accuracy, 1),
                "perks": ", ".join(sorted(set(perks))) if perks else "Unknown",
            })

    participants.sort(key=lambda x: x["kills"], reverse=True)

    db.close()
    return {
        "session": {
            "sessionid": session["sessionid"],
            "version": session["version"],
            "gametype": session["gametype"],
            "status": status,
            "map": session["map"],
            "time": session["time"],
            "elapsed": elapsed_string(session["time"]),
            "difficulty": session["difficulty"],
        },
        "waves": waves,
        "participants": participants,
    }
