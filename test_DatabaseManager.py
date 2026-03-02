#!/usr/bin/env python3

# Test cases for DatabaseManager based on payloads sent from UnrealScript.
# Distributed under the terms of the GPL-2.0 License.
# For more information see https://github.com/KFPilot/KFTurbo.

import unittest
import os
import sqlite3
import json
import DatabaseManager

DB_FILE = "TurboTestDatabase.db"

def make_session_id():
    """Mirrors ConnectionManager.GetSessionID(abs(hash(session_string)))."""
    return "ABCDE"

def make_player_id(steam_id):
    return DatabaseManager.GetPlayerID(steam_id)

class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        # Remove stale test DB.
        if os.path.exists(DB_FILE):
            os.remove(DB_FILE)

        # Patch sqlite3.connect so DatabaseManager uses the test DB.
        self._orig_connect = sqlite3.connect
        sqlite3.connect = lambda *a, **kw: self._orig_connect(DB_FILE, **kw)
        self.db = DatabaseManager.DatabaseManager()
        sqlite3.connect = self._orig_connect

        self.session_id = make_session_id()

    def tearDown(self):
        self.db.Database.close()
        if os.path.exists(DB_FILE):
            os.remove(DB_FILE)

    # -------------------------------------------------------
    # Payload helpers (mirrors TurboStatsTcpLink output)
    # -------------------------------------------------------

    def _gamebegin(self, session="1234567890|KF-BioticsLab", version="6.6.8", gametype="turbo"):
        return {
            "type": "gamebegin",
            "version": version,
            "session": session,
            "gametype": gametype
        }

    def _gameend(self, result="won", wavenum=10):
        return {
            "type": "gameend",
            "version": "6.6.8",
            "session": "ignored",
            "wavenum": wavenum,
            "result": result
        }

    def _wavestart(self, wavenum=1, playerlist=None):
        if playerlist is None:
            playerlist = ["76561198000000001", "76561198000000002"]
        return {
            "type": "wavestart",
            "version": "6.6.8",
            "session": "ignored",
            "wavenum": str(wavenum),
            "playerlist": playerlist
        }

    def _waveend(self, wavenum=1):
        return {
            "type": "waveend",
            "version": "6.6.8",
            "session": "ignored",
            "wavenum": wavenum
        }

    def _wavestats(self, player="76561198000000001", playername="TestPlayer", died=False, wavenum=1, stats=None):
        if stats is None:
            stats = {
                "Kills": 15,
                "KillsFP": 2,
                "KillsSC": 1,
                "Damage": 5000,
                "DamageFP": 1200,
                "DamageSC": 800,
                "ShotsFired": 100,
                "MeleeSwings": 5,
                "ShotsHit": 80,
                "ShotsHeadshot": 30,
                "Reloads": 10,
                "Heals": 200,
                "DamageTaken": 50
            }
        return {
            "type": "wavestats",
            "version": "6.6.8",
            "session": "ignored",
            "wavenum": wavenum,
            "player": player,
            "playername": playername,
            "perk": "COM",
            "stats": stats,
            "died": died
        }

    def _cardgame_vote(self, wavenum=1, activecards=None, voteselection=None, votedcard="CardDamageBoost"):
        if activecards is None:
            activecards = ["CardHealthBoost", "CardSpeedBoost"]
        if voteselection is None:
            voteselection = ["CardDamageBoost", "CardArmorBoost", "CardRegenBoost"]
        return {
            "type": "cardgame_vote",
            "version": "6.6.8",
            "session": "ignored",
            "wavenum": wavenum,
            "activecards": activecards,
            "voteselection": voteselection,
            "votedcard": votedcard
        }

    def _cardgame_endgame(self, result="won", activecards=None):
        if activecards is None:
            activecards = ["CardHealthBoost", "CardSpeedBoost", "CardDamageBoost"]
        return {
            "type": "cardgame_endgame",
            "version": "6.6.8",
            "session": "ignored",
            "result": result,
            "activecards": activecards
        }

    def _process(self, payload):
        self.db.ProcessPayload(self.session_id, payload)

    # -------------------------------------------------------
    # gamebegin
    # -------------------------------------------------------

    def test_gamebegin_creates_session_row(self):
        self._process(self._gamebegin())
        row = self.db.DatabaseCursor.execute(
            "SELECT * FROM sessiontable WHERE sessionid = ?", ("session_" + self.session_id,)
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[2], "turbo")       # gametype
        self.assertEqual(row[3], "InProgress")  # status
        self.assertEqual(row[4], "KF-BioticsLab")  # map

    def test_gamebegin_duplicate_ignored(self):
        self._process(self._gamebegin())
        self._process(self._gamebegin())
        rows = self.db.DatabaseCursor.execute(
            "SELECT * FROM sessiontable WHERE sessionid = ?", ("session_" + self.session_id,)
        ).fetchall()
        self.assertEqual(len(rows), 1)

    # -------------------------------------------------------
    # wavestart / waveend
    # -------------------------------------------------------

    def test_wavestart_inserts_row(self):
        self._process(self._gamebegin())
        self._process(self._wavestart(wavenum=1))
        table = "session_" + self.session_id
        row = self.db.DatabaseCursor.execute("SELECT * FROM " + table + " WHERE wave = 1").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[2], "InProgress")  # status

    def test_wavestart_stores_playerlist_as_json(self):
        self._process(self._gamebegin())
        players = ["76561198000000001", "76561198000000002"]
        self._process(self._wavestart(wavenum=1, playerlist=players))
        table = "session_" + self.session_id
        row = self.db.DatabaseCursor.execute("SELECT players FROM " + table + " WHERE wave = 1").fetchone()
        parsed = json.loads(row[0])
        self.assertEqual(parsed, players)

    def test_waveend_marks_complete(self):
        self._process(self._gamebegin())
        self._process(self._wavestart(wavenum=1))
        self._process(self._waveend(wavenum=1))
        table = "session_" + self.session_id
        row = self.db.DatabaseCursor.execute("SELECT status FROM " + table + " WHERE wave = 1").fetchone()
        self.assertEqual(row[0], "Complete")

    def test_wavestart_completes_previous_waves(self):
        self._process(self._gamebegin())
        self._process(self._wavestart(wavenum=1))
        self._process(self._wavestart(wavenum=2))
        table = "session_" + self.session_id
        row = self.db.DatabaseCursor.execute("SELECT status FROM " + table + " WHERE wave = 1").fetchone()
        self.assertEqual(row[0], "Complete")

    # -------------------------------------------------------
    # wavestats
    # -------------------------------------------------------

    def test_wavestats_creates_player_table(self):
        self._process(self._gamebegin())
        self._process(self._wavestats())
        player_id = make_player_id("76561198000000001")
        tables = self.db.DatabaseCursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (player_id,)
        ).fetchall()
        self.assertEqual(len(tables), 1)

    def test_wavestats_records_stats(self):
        self._process(self._gamebegin())
        self._process(self._wavestats(stats={"Kills": 10, "Damage": 3000}))
        player_id = make_player_id("76561198000000001")
        row = self.db.DatabaseCursor.execute("SELECT kills, damage FROM " + player_id).fetchone()
        self.assertEqual(row[0], 10)
        self.assertEqual(row[1], 3000)

    def test_wavestats_fills_missing_stats_with_zero(self):
        self._process(self._gamebegin())
        self._process(self._wavestats(stats={"Kills": 5}))
        player_id = make_player_id("76561198000000001")
        row = self.db.DatabaseCursor.execute("SELECT heals, damagetaken FROM " + player_id).fetchone()
        self.assertEqual(row[0], 0)
        self.assertEqual(row[1], 0)

    def test_wavestats_death_tracked_in_player_table(self):
        self._process(self._gamebegin())
        self._process(self._wavestats(died=True))
        player_id = make_player_id("76561198000000001")
        row = self.db.DatabaseCursor.execute(
            "SELECT deaths FROM playertable WHERE playerid = ?", (player_id,)
        ).fetchone()
        self.assertEqual(row[0], 1)

    def test_wavestats_no_death_zero_in_player_table(self):
        self._process(self._gamebegin())
        self._process(self._wavestats(died=False))
        player_id = make_player_id("76561198000000001")
        row = self.db.DatabaseCursor.execute(
            "SELECT deaths FROM playertable WHERE playerid = ?", (player_id,)
        ).fetchone()
        self.assertEqual(row[0], 0)

    def test_wavestats_deaths_accumulate(self):
        self._process(self._gamebegin())
        self._process(self._wavestats(died=True, wavenum=1))
        self._process(self._wavestats(died=True, wavenum=2))
        self._process(self._wavestats(died=False, wavenum=3))
        player_id = make_player_id("76561198000000001")
        row = self.db.DatabaseCursor.execute(
            "SELECT deaths FROM playertable WHERE playerid = ?", (player_id,)
        ).fetchone()
        self.assertEqual(row[0], 2)

    def test_wavestats_updates_player_name(self):
        self._process(self._gamebegin())
        self._process(self._wavestats(playername="OldName", wavenum=1))
        self._process(self._wavestats(playername="NewName", wavenum=2))
        player_id = make_player_id("76561198000000001")
        row = self.db.DatabaseCursor.execute(
            "SELECT playername FROM playertable WHERE playerid = ?", (player_id,)
        ).fetchone()
        self.assertEqual(row[0], "NewName")

    # -------------------------------------------------------
    # gameend
    # -------------------------------------------------------

    def test_gameend_win_updates_session(self):
        self._process(self._gamebegin())
        self._process(self._wavestart(wavenum=1))
        self._process(self._wavestats(wavenum=1))
        self._process(self._gameend(result="won"))
        row = self.db.DatabaseCursor.execute(
            "SELECT status FROM sessiontable WHERE sessionid = ?", ("session_" + self.session_id,)
        ).fetchone()
        self.assertEqual(row[0], "Win")

    def test_gameend_lose_updates_session(self):
        self._process(self._gamebegin())
        self._process(self._wavestart(wavenum=1))
        self._process(self._wavestats(wavenum=1))
        self._process(self._gameend(result="lost"))
        row = self.db.DatabaseCursor.execute(
            "SELECT status FROM sessiontable WHERE sessionid = ?", ("session_" + self.session_id,)
        ).fetchone()
        self.assertEqual(row[0], "Lose")

    def test_gameend_win_increments_wincount(self):
        players = ["76561198000000001"]
        self._process(self._gamebegin())
        self._process(self._wavestart(wavenum=1, playerlist=players))
        self._process(self._wavestats(player=players[0], wavenum=1))
        self._process(self._gameend(result="won"))
        player_id = make_player_id(players[0])
        row = self.db.DatabaseCursor.execute(
            "SELECT wincount FROM playertable WHERE playerid = ?", (player_id,)
        ).fetchone()
        self.assertEqual(row[0], 1)

    def test_gameend_lose_increments_losecount(self):
        players = ["76561198000000001"]
        self._process(self._gamebegin())
        self._process(self._wavestart(wavenum=1, playerlist=players))
        self._process(self._wavestats(player=players[0], wavenum=1))
        self._process(self._gameend(result="lost"))
        player_id = make_player_id(players[0])
        row = self.db.DatabaseCursor.execute(
            "SELECT losecount FROM playertable WHERE playerid = ?", (player_id,)
        ).fetchone()
        self.assertEqual(row[0], 1)

    def test_gameend_abort_does_not_change_counts(self):
        players = ["76561198000000001"]
        self._process(self._gamebegin())
        self._process(self._wavestart(wavenum=1, playerlist=players))
        self._process(self._wavestats(player=players[0], wavenum=1))
        self._process(self._gameend(result="aborted"))
        player_id = make_player_id(players[0])
        row = self.db.DatabaseCursor.execute(
            "SELECT wincount, losecount FROM playertable WHERE playerid = ?", (player_id,)
        ).fetchone()
        self.assertEqual(row[0], 0)
        self.assertEqual(row[1], 0)

    def test_gameend_win_credits_all_wave_participants(self):
        p1, p2 = "76561198000000001", "76561198000000002"
        self._process(self._gamebegin())
        # p1 in wave 1, p2 joins in wave 2
        self._process(self._wavestart(wavenum=1, playerlist=[p1]))
        self._process(self._wavestats(player=p1, wavenum=1))
        self._process(self._wavestart(wavenum=2, playerlist=[p1, p2]))
        self._process(self._wavestats(player=p1, wavenum=2))
        self._process(self._wavestats(player=p2, wavenum=2))
        self._process(self._gameend(result="won"))
        for p in [p1, p2]:
            pid = make_player_id(p)
            row = self.db.DatabaseCursor.execute(
                "SELECT wincount FROM playertable WHERE playerid = ?", (pid,)
            ).fetchone()
            self.assertEqual(row[0], 1, f"Player {p} should have 1 win")

    # -------------------------------------------------------
    # cardgame_vote
    # -------------------------------------------------------

    def test_cardvote_initializes_cards(self):
        self._process(self._gamebegin())
        self._process(self._cardgame_vote())
        rows = self.db.DatabaseCursor.execute("SELECT * FROM cardtable").fetchall()
        # 3 cards from voteselection
        self.assertEqual(len(rows), 3)

    def test_cardvote_increments_showncount(self):
        self._process(self._gamebegin())
        self._process(self._cardgame_vote(
            voteselection=["CardA", "CardB", "CardC"],
            votedcard="CardA"
        ))
        row = self.db.DatabaseCursor.execute(
            "SELECT showncount FROM cardtable WHERE cardid = ?", ("CardA",)
        ).fetchone()
        self.assertEqual(row[0], 1)

    def test_cardvote_increments_selectedcount(self):
        self._process(self._gamebegin())
        self._process(self._cardgame_vote(
            voteselection=["CardA", "CardB", "CardC"],
            votedcard="CardB"
        ))
        selected = self.db.DatabaseCursor.execute(
            "SELECT selectedcount FROM cardtable WHERE cardid = ?", ("CardB",)
        ).fetchone()
        not_selected = self.db.DatabaseCursor.execute(
            "SELECT selectedcount FROM cardtable WHERE cardid = ?", ("CardA",)
        ).fetchone()
        self.assertEqual(selected[0], 1)
        self.assertEqual(not_selected[0], 0)

    def test_cardvote_accumulates_across_waves(self):
        self._process(self._gamebegin())
        self._process(self._cardgame_vote(
            wavenum=1,
            voteselection=["CardA", "CardB", "CardC"],
            votedcard="CardA"
        ))
        self._process(self._cardgame_vote(
            wavenum=2,
            voteselection=["CardA", "CardD", "CardE"],
            votedcard="CardA"
        ))
        row = self.db.DatabaseCursor.execute(
            "SELECT showncount, selectedcount FROM cardtable WHERE cardid = ?", ("CardA",)
        ).fetchone()
        self.assertEqual(row[0], 2)  # shown twice
        self.assertEqual(row[1], 2)  # selected twice

    # -------------------------------------------------------
    # cardgame_endgame
    # -------------------------------------------------------

    def test_cardgame_endgame_win(self):
        self._process(self._gamebegin())
        cards = ["CardA", "CardB"]
        # Initialize cards via a vote first.
        self._process(self._cardgame_vote(voteselection=cards + ["CardC"], votedcard="CardA"))
        self._process(self._cardgame_endgame(result="won", activecards=cards))
        for card in cards:
            row = self.db.DatabaseCursor.execute(
                "SELECT wincount FROM cardtable WHERE cardid = ?", (card,)
            ).fetchone()
            self.assertEqual(row[0], 1)

    def test_cardgame_endgame_lose(self):
        self._process(self._gamebegin())
        cards = ["CardA", "CardB"]
        self._process(self._cardgame_vote(voteselection=cards + ["CardC"], votedcard="CardA"))
        self._process(self._cardgame_endgame(result="lost", activecards=cards))
        for card in cards:
            row = self.db.DatabaseCursor.execute(
                "SELECT losecount FROM cardtable WHERE cardid = ?", (card,)
            ).fetchone()
            self.assertEqual(row[0], 1)

    def test_cardgame_endgame_abort_ignored(self):
        self._process(self._gamebegin())
        cards = ["CardA"]
        self._process(self._cardgame_vote(voteselection=cards + ["CardB", "CardC"], votedcard="CardA"))
        self._process(self._cardgame_endgame(result="aborted", activecards=cards))
        row = self.db.DatabaseCursor.execute(
            "SELECT wincount, losecount FROM cardtable WHERE cardid = ?", ("CardA",)
        ).fetchone()
        self.assertEqual(row[0], 0)
        self.assertEqual(row[1], 0)

    # -------------------------------------------------------
    # Full game flow
    # -------------------------------------------------------

    def test_full_game_flow(self):
        """Simulates a full 3-wave game with 2 players, ending in a win."""
        p1, p2 = "76561198000000001", "76561198000000002"

        self._process(self._gamebegin())

        for wave in range(1, 4):
            self._process(self._wavestart(wavenum=wave, playerlist=[p1, p2]))
            self._process(self._wavestats(player=p1, wavenum=wave, died=(wave == 2)))
            self._process(self._wavestats(player=p2, wavenum=wave, died=False))
            self._process(self._waveend(wavenum=wave))

        self._process(self._gameend(result="won"))

        # p1 died once (wave 2), p2 never died.
        pid1 = make_player_id(p1)
        pid2 = make_player_id(p2)
        self.assertEqual(
            self.db.DatabaseCursor.execute("SELECT deaths FROM playertable WHERE playerid = ?", (pid1,)).fetchone()[0], 1
        )
        self.assertEqual(
            self.db.DatabaseCursor.execute("SELECT deaths FROM playertable WHERE playerid = ?", (pid2,)).fetchone()[0], 0
        )
        # Both should have 1 win.
        self.assertEqual(
            self.db.DatabaseCursor.execute("SELECT wincount FROM playertable WHERE playerid = ?", (pid1,)).fetchone()[0], 1
        )
        self.assertEqual(
            self.db.DatabaseCursor.execute("SELECT wincount FROM playertable WHERE playerid = ?", (pid2,)).fetchone()[0], 1
        )

    # -------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------

    def test_cleanup_marks_inprogress_as_ended(self):
        self._process(self._gamebegin())
        # Simulate a crash - session is still InProgress. Re-create the manager.
        self.db.Database.close()
        sqlite3.connect = lambda *a, **kw: self._orig_connect(DB_FILE, **kw)
        self.db = DatabaseManager.DatabaseManager()
        sqlite3.connect = self._orig_connect
        row = self.db.DatabaseCursor.execute(
            "SELECT status FROM sessiontable WHERE sessionid = ?", ("session_" + self.session_id,)
        ).fetchone()
        self.assertEqual(row[0], "Ended")

    # -------------------------------------------------------
    # GetPlayerID
    # -------------------------------------------------------

    def test_get_player_id_converts_digits(self):
        result = DatabaseManager.GetPlayerID("12345")
        self.assertEqual(result, "player_BCDEF")

    def test_get_player_id_preserves_non_digits(self):
        result = DatabaseManager.GetPlayerID("1a2b")
        self.assertEqual(result, "player_BaCb")


if __name__ == "__main__":
    unittest.main()
