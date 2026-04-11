import sqlite3
import time
import os

DB_PATH = os.environ.get("TURBO_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "TurboDatabase.db"))

PERK_NAMES = {
    "SHA": "Sharpshooter",
    "DEM": "Demolitions",
    "SUP": "Support Specialist",
    "COM": "Commando",
    "FIR": "Firebug",
    "MED": "Field Medic",
}

GAMETYPE_NAMES = {
    "turbo": "Turbo",
    "turbocardgame": "Card Game",
    "turboplus": "Turbo+",
}

def perk_display_name(code):
    if not code:
        return "Unknown"
    return PERK_NAMES.get(code, code)

def gametype_display_name(code):
    if not code:
        return "Unknown"
    return GAMETYPE_NAMES.get(code, code)

def _table_has_column(cur, table, column):
    cols = [row[1] for row in cur.execute(f"PRAGMA table_info([{table}])").fetchall()]
    return column in cols

_cache = {}
CACHE_TTL = 60

def _cache_key(base, gametypes):
    if gametypes:
        return base + ":" + ",".join(sorted(gametypes))
    return base

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

def _get_filtered_session_ids(cur, gametypes):
    """Return set of sessionids matching the gametype filter, or None if no filter."""
    if not gametypes:
        return None
    placeholders = ",".join("?" for _ in gametypes)
    rows = cur.execute(f"SELECT sessionid FROM sessiontable WHERE gametype IN ({placeholders})", gametypes).fetchall()
    return set(r[0] for r in rows)

def get_gametypes():
    db = get_db()
    cur = db.cursor()
    rows = cur.execute("SELECT DISTINCT gametype FROM sessiontable ORDER BY gametype").fetchall()
    db.close()
    return [r[0] for r in rows]

def get_aggregate_overview(gametypes=None):
    key = _cache_key("overview", gametypes)
    cached = _get_cached(key)
    if cached:
        return cached

    db = get_db()
    cur = db.cursor()

    where_clause, params = "", []
    if gametypes:
        placeholders = ",".join("?" for _ in gametypes)
        where_clause = f" WHERE gametype IN ({placeholders})"
        params = list(gametypes)

    total_sessions = cur.execute(f"SELECT COUNT(*) FROM sessiontable{where_clause}", params).fetchone()[0]
    total_players = cur.execute("SELECT COUNT(*) FROM playertable").fetchone()[0]

    status_counts = {}
    for row in cur.execute(f"SELECT status, COUNT(*) as cnt FROM sessiontable{where_clause} GROUP BY status", params):
        status_counts[row["status"]] = row["cnt"]

    # Reclassify InProgress sessions whose session table has 0 rows as Abort
    if status_counts.get("InProgress", 0) > 0:
        ip_sessions = cur.execute(
            f"SELECT sessionid FROM sessiontable WHERE status='InProgress'{' AND gametype IN (' + ','.join('?' for _ in params) + ')' if params else ''}",
            params
        ).fetchall()
        empty_count = 0
        for s in ip_sessions:
            sid = s[0]
            table_exists = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (sid,)).fetchone()
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

    map_counts = []
    for row in cur.execute(f"SELECT map, COUNT(*) as cnt FROM sessiontable{where_clause} GROUP BY map ORDER BY cnt DESC LIMIT 10", params):
        map_counts.append({"map": row["map"], "count": row["cnt"]})

    db.close()
    result = {
        "total_sessions": total_sessions,
        "total_players": total_players,
        "status_counts": status_counts,
        "top_maps": map_counts,
    }
    _set_cached(key, result)
    return result

def get_all_player_stats(gametypes=None):
    key = _cache_key("all_player_stats", gametypes)
    cached = _get_cached(key)
    if cached:
        return cached

    db = get_db()
    cur = db.cursor()

    session_ids = _get_filtered_session_ids(cur, gametypes)

    players = cur.execute("SELECT playerid, playertableid, playername, deaths, wincount, losecount FROM playertable").fetchall()

    result = []
    for p in players:
        tableid = p["playertableid"]
        exists = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tableid,)).fetchone()
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

        row = cur.execute(f"""
            SELECT
                SUM(kills) as kills, SUM(kills_fp) as kills_fp, SUM(kills_sc) as kills_sc,
                SUM(damage) as damage, SUM(damage_fp) as damage_fp, SUM(damage_sc) as damage_sc,
                SUM(shotsfired) as shotsfired, SUM(meleeswings) as meleeswings,
                SUM(shotshit) as shotshit, SUM(shotsheadshot) as shotsheadshot,
                SUM(reloads) as reloads, SUM(heals) as heals,
                SUM(damagetaken) as damagetaken, SUM(deaths) as deaths,
                COUNT(*) as waves_played
            FROM [{tableid}]{session_filter}
        """, filter_params).fetchone()

        if not row["waves_played"]:
            continue

        # Win/loss counts need recalculating when filtered
        if session_ids is not None:
            wins = 0
            losses = 0
            player_sessions = cur.execute(f"SELECT DISTINCT sessionid FROM [{tableid}]{session_filter}", filter_params).fetchall()
            for ps in player_sessions:
                sid = ps[0]
                status = cur.execute("SELECT status FROM sessiontable WHERE sessionid=?", (sid,)).fetchone()
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
        headshot_pct = (row["shotsheadshot"] or 0) / (row["shotshit"] or 1) * 100 if (row["shotshit"] or 0) > 0 else 0
        games = wins + losses
        win_rate = wins / games * 100 if games > 0 else 0

        result.append({
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
        })

    db.close()
    _set_cached(key, result)
    return result

def get_player_detail(playertableid, gametypes=None):
    db = get_db()
    cur = db.cursor()

    player = cur.execute("SELECT * FROM playertable WHERE playertableid=?", (playertableid,)).fetchone()
    if not player:
        db.close()
        return None

    exists = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (playertableid,)).fetchone()
    if not exists:
        db.close()
        return {"player": dict(player), "waves": [], "perk_summary": [], "session_summary": []}

    session_ids = _get_filtered_session_ids(cur, gametypes)

    if session_ids is not None:
        if not session_ids:
            db.close()
            return {"player": dict(player), "waves": [], "perk_summary": [], "session_summary": []}
        placeholders = ",".join("?" for _ in session_ids)
        session_filter = f" WHERE sessionid IN ({placeholders})"
        filter_params = list(session_ids)
    else:
        session_filter = ""
        filter_params = []

    waves = [dict(r) for r in cur.execute(f"SELECT * FROM [{playertableid}]{session_filter} ORDER BY sessionid, wave", filter_params).fetchall()]

    # Per-perk aggregation
    has_perk = _table_has_column(cur, playertableid, "perk")
    perk_select = "perk" if has_perk else "'Unknown' as perk"
    group_by = " GROUP BY perk" if has_perk else ""
    perk_summary = []
    for row in cur.execute(f"""
        SELECT {perk_select},
            COUNT(*) as waves_played,
            SUM(kills) as kills, SUM(kills_fp) as kills_fp, SUM(kills_sc) as kills_sc,
            SUM(damage) as damage, SUM(shotsfired) as shotsfired, SUM(meleeswings) as meleeswings,
            SUM(shotshit) as shotshit, SUM(shotsheadshot) as shotsheadshot,
            SUM(heals) as heals, SUM(damagetaken) as damagetaken, SUM(deaths) as deaths
        FROM [{playertableid}]{session_filter}{group_by}
    """, filter_params).fetchall():
        total_shots = (row["shotsfired"] or 0) + (row["meleeswings"] or 0)
        accuracy = (row["shotshit"] or 0) / total_shots * 100 if total_shots > 0 else 0
        perk_summary.append({
            "perk": perk_display_name(row["perk"]),
            "waves_played": row["waves_played"],
            "kills": row["kills"] or 0,
            "kills_fp": row["kills_fp"] or 0,
            "kills_sc": row["kills_sc"] or 0,
            "damage": row["damage"] or 0,
            "heals": row["heals"] or 0,
            "deaths": row["deaths"] or 0,
            "accuracy": round(accuracy, 1),
        })

    # Per-session summary
    session_id_list = list(set(w["sessionid"] for w in waves))
    session_summary = []
    for sid in session_id_list:
        session_info = cur.execute("SELECT * FROM sessiontable WHERE sessionid=?", (sid,)).fetchone()
        session_waves = [w for w in waves if w["sessionid"] == sid]
        perks_used = list(set(perk_display_name(w.get("perk", "")) for w in session_waves if w.get("perk")))
        session_summary.append({
            "sessionid": sid,
            "map": session_info["map"] if session_info else "Unknown",
            "status": session_info["status"] if session_info else "Unknown",
            "waves_played": len(session_waves),
            "perks": ", ".join(perks_used) if perks_used else "Unknown",
            "kills": sum(w["kills"] or 0 for w in session_waves),
            "damage": sum(w["damage"] or 0 for w in session_waves),
        })

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
        cards.append({
            "cardid": row["cardid"],
            "shown": shown,
            "selected": selected,
            "wins": wins,
            "losses": losses,
            "pick_rate": round(pick_rate, 1),
            "win_rate": round(win_rate, 1),
        })

    db.close()
    _set_cached("card_stats", cards)
    return cards

def get_perk_stats(gametypes=None):
    key = _cache_key("perk_stats", gametypes)
    cached = _get_cached(key)
    if cached:
        return cached

    db = get_db()
    cur = db.cursor()

    session_ids = _get_filtered_session_ids(cur, gametypes)

    # Find all per-player tables (exclude the master 'playertable')
    player_tables = [row[0] for row in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'player_%'"
    ).fetchall() if row[0] != "playertable"]

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
        for row in cur.execute(f"""
            SELECT {perk_select},
                COUNT(*) as waves,
                SUM(kills) as kills, SUM(kills_fp) as kills_fp, SUM(kills_sc) as kills_sc,
                SUM(damage) as damage, SUM(damage_fp) as damage_fp, SUM(damage_sc) as damage_sc,
                SUM(shotsfired) as shotsfired, SUM(meleeswings) as meleeswings,
                SUM(shotshit) as shotshit, SUM(shotsheadshot) as shotsheadshot,
                SUM(heals) as heals, SUM(damagetaken) as damagetaken, SUM(deaths) as deaths
            FROM [{table}]{session_filter}{group_by}
        """, filter_params).fetchall():
            if not row["waves"]:
                continue
            perk = perk_display_name(row["perk"])
            if perk not in perk_data:
                perk_data[perk] = {
                    "perk": perk, "waves": 0, "unique_players": set(),
                    "kills": 0, "kills_fp": 0, "kills_sc": 0,
                    "damage": 0, "damage_fp": 0, "damage_sc": 0,
                    "shotsfired": 0, "meleeswings": 0,
                    "shotshit": 0, "shotsheadshot": 0,
                    "heals": 0, "damagetaken": 0, "deaths": 0,
                }
            d = perk_data[perk]
            d["waves"] += row["waves"] or 0
            d["unique_players"].add(table)
            for col in ["kills", "kills_fp", "kills_sc", "damage", "damage_fp", "damage_sc",
                        "shotsfired", "meleeswings", "shotshit", "shotsheadshot",
                        "heals", "damagetaken", "deaths"]:
                d[col] += row[col] or 0

    result = []
    for perk, d in sorted(perk_data.items(), key=lambda x: x[1]["waves"], reverse=True):
        total_shots = d["shotsfired"] + d["meleeswings"]
        accuracy = d["shotshit"] / total_shots * 100 if total_shots > 0 else 0
        waves = d["waves"] if d["waves"] > 0 else 1
        result.append({
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
        })

    db.close()
    _set_cached(key, result)
    return result
