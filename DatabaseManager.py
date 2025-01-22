# Killing Floor Turbo Database Manager
# Manages database tables. Takes json payloads and uses their type property to figure out how to handle them.
# I am not familiar with Python nor SQLite so this should only be used as an example implementation. 
# Distributed under the terms of the GPL-2.0 License.
# For more information see https://github.com/KFPilot/KFTurbo.
import time
import json
import os
import sqlite3
import ast

def GetPlayerID(ID):
    ID = str(ID)
    LetterID = ""
    for Char in ID:
        if Char.isnumeric():
            LetterID = LetterID + chr(ord('A') + int(Char))
        else:
            LetterID = LetterID + Char
    return "player_"+LetterID

# Makes sure the dictionary we pass to the SQLite API has all the columns we expect, even if they're just zero-filled.
def FillStatsData(StatsData):
    StatsDataList = ["Kills", "KillsFP", "KillsSC", "Damage", "DamageFP", "DamageSC", "ShotsFired", "MeleeSwings", "ShotsHit", "ShotsHeadshot", "Reloads", "Heals", "DamageTaken"]
    for key in StatsDataList:
        if key not in StatsData:
            StatsData[key] = 0
    return StatsData

class DatabaseManager:
    def __init__(self):
        self.Database = sqlite3.connect("TurboDatabase.db")
        self.Database.isolation_level = None # Autocommit mode
        self.DatabaseCursor = self.Database.cursor()
        self.DatabaseCursor.execute("CREATE TABLE IF NOT EXISTS sessiontable(sessionid, version, gametype, status, map, time, UNIQUE(sessionid))")
        self.DatabaseCursor.execute("CREATE TABLE IF NOT EXISTS playertable(playerid, playername, deaths, wincount, losecount, UNIQUE(playerid))")
        self.DatabaseCursor.execute("CREATE TABLE IF NOT EXISTS cardtable(cardid VARCHAR(255), selectedcount INT(255), showncount INT(255), wincount INT(255), losecount INT(255), UNIQUE(cardid))")
        self.CleanupPreviousSessions()
    
########################################
# GAME PAYLOADS

    def ProcessPayload(self, SessionID, JsonPayload):
        # Sessions are prefixed with "session_"
        SessionID = "session_" + SessionID
        # By default all sessions generate their own table.
        self.DatabaseCursor.execute("CREATE TABLE IF NOT EXISTS "+SessionID+"(wave, status, players)")
        match JsonPayload['type']:
            case "gamebegin":
                self.ProcessGameBeginPayload(SessionID, JsonPayload)
            case "gameend":
                self.ProcessGameEndPayload(SessionID, JsonPayload)
            case "wavestart":
                self.ProcessWaveStartPayload(SessionID, JsonPayload)
            case "waveend":
                self.ProcessWaveEndPayload(SessionID, JsonPayload)
            case "wavestats":
                self.ProcessPlayerStatsPayload(SessionID, JsonPayload)
            case "cardgame_vote":
                self.ProcessCardVotePayload(SessionID, JsonPayload)
            case "cardgame_endgame":
                self.ProcessCardGameEndPayload(SessionID, JsonPayload)

    def ProcessGameBeginPayload(self, SessionID, JsonPayload):
        print(SessionID, JsonPayload)
        #Mutate this for preparation to be inserted into table.
        SessionData = JsonPayload['session'].split("|")
        JsonPayload['map'] = SessionData[1]
        JsonPayload['time'] = SessionData[0]
        JsonPayload['session'] = SessionID
        JsonPayload['status'] = "InProgress"
        self.DatabaseCursor.execute("INSERT INTO sessiontable VALUES(:session, :version, :gametype, :status, :map, :time)", JsonPayload)

    def ProcessGameEndPayload(self, SessionID, JsonPayload):
        print(SessionID, JsonPayload)
        match JsonPayload['result']:
            case "won":
                JsonPayload['result'] = "Win"
            case "lost":
                JsonPayload['result'] = "Lose"
            case "aborted":
                JsonPayload['result'] = "Abort"

        self.DatabaseCursor.execute("UPDATE "+SessionID+" SET status = '"+JsonPayload['result']+"' WHERE status IS 'InProgress'")
        self.DatabaseCursor.execute("UPDATE sessiontable SET status = '"+JsonPayload['result']+"' WHERE sessionid IS '"+SessionID+"'")

        # Don't update player wins/losses if the game was aborted.
        if JsonPayload['result'] == "Abort":
            return

        # Turn all the lists of participants in the rows into one set of participants.
        PlayerList = set()
        Result = self.DatabaseCursor.execute("SELECT players FROM "+SessionID).fetchall()
        for PlayerIDListString in Result:
            PlayerIDList = ast.literal_eval(PlayerIDListString[0])
            for PlayerID in PlayerIDList:
                PlayerList.add(PlayerID)

        # Update win/lose counts for all participants.
        if JsonPayload['result'] == "Win":
            for Player in PlayerList:
                Player = GetPlayerID(Player)
                self.DatabaseCursor.execute("UPDATE playertable SET wincount = wincount + 1 WHERE playerid = '"+Player+"'")
        else:
            for Player in PlayerList:
                Player = GetPlayerID(Player)
                self.DatabaseCursor.execute("UPDATE playertable SET losecount = losecount + 1 WHERE playerid = '"+Player+"'")

    def ProcessWaveStartPayload(self, SessionID, JsonPayload):
        print(SessionID, JsonPayload)
        JsonPayload['status'] = "InProgress"
        JsonPayload['playerlist'] = str(JsonPayload['playerlist'])
        self.DatabaseCursor.execute("INSERT INTO "+SessionID+" VALUES(:wavenum, :status, :playerlist)", JsonPayload)

        # In case we missed a ProcessWaveEndPayload.
        if (JsonPayload['wavenum'] > 1):
            self.DatabaseCursor.execute("UPDATE "+SessionID+" SET status = 'Complete' WHERE wave < "+str(JsonPayload['wavenum']))

    def ProcessWaveEndPayload(self, SessionID, JsonPayload):
        print(SessionID, JsonPayload)
        self.DatabaseCursor.execute("UPDATE "+SessionID+" SET status = 'Complete'")
    
########################################
# PLAYER PAYLOADS

    def ProcessPlayerStatsPayload(self, SessionID, JsonPayload):
        print(SessionID, JsonPayload)
        PlayerID = GetPlayerID(JsonPayload['player'])
        StatsData = JsonPayload['stats']
        StatsData['wavenum'] = JsonPayload['wavenum']
        StatsData['sessionid'] = SessionID
        StatsData['Deaths'] = 1 if JsonPayload['died'] else 0
        StatsData = FillStatsData(StatsData)
        self.DatabaseCursor.execute("CREATE TABLE IF NOT EXISTS "+PlayerID+"(sessionid VARCHAR(255), wave INT(255), kills INT(255), kills_fp INT(255), kills_sc INT(255), damage INT(255), damage_fp INT(255), damage_sc INT(255), shotsfired INT(255), meleeswings INT(255), shotshit INT(255), shotsheadshot INT(255), reloads INT(255), heals INT(255), damagetaken INT(255), deaths INT(255))")
        self.DatabaseCursor.execute("INSERT INTO "+PlayerID+" VALUES(:sessionid, :wavenum, :Kills, :KillsFP, :KillsSC, :Damage, :DamageFP, :DamageSC, :ShotsFired, :MeleeSwings, :ShotsHit, :ShotsHeadshot, :Reloads, :Heals, :DamageTaken, :Deaths)", StatsData)
        
        PlayerData = { "deaths" : 0, "wincount" : 0, "losecount" : 0}
        PlayerData['playerid'] = PlayerID
        PlayerData['playername'] = JsonPayload['playername']
        self.DatabaseCursor.execute("INSERT OR IGNORE INTO playertable VALUES(:playerid, :playername, :deaths, :wincount, :losecount)", PlayerData)
        
        if StatsData['Deaths'] == 1:
            self.DatabaseCursor.execute("UPDATE playertable SET deaths = deaths + 1 WHERE playerid = '"+PlayerData['playerid']+"'")


########################################
# CARD PAYLOADS

    def ProcessCardVotePayload(self, SessionID, JsonPayload):
        print(SessionID, JsonPayload)
        CardData = { "cardid" : "", "selectedcount": 0, "showncount" : 0, "wincount" : 0, "losecount" : 0}
        # Try to initialize rows from vote selection list.
        for card in JsonPayload['voteselection']:
            CardData['cardid'] = card
            self.DatabaseCursor.execute("INSERT OR IGNORE INTO cardtable VALUES(:cardid, :selectedcount, :showncount, :wincount, :losecount)", CardData)
            self.DatabaseCursor.execute("UPDATE cardtable SET showncount = showncount + 1 WHERE cardid = '"+card+"'")
            
        self.DatabaseCursor.execute("UPDATE cardtable SET selectedcount = selectedcount + 1 WHERE cardid = '"+JsonPayload['votedcard']+"'")
        
    def ProcessCardGameEndPayload(self, SessionID, JsonPayload):
        print(SessionID, JsonPayload)
        CardData = { "cardid" : "", "selectedcount": 0, "showncount" : 0, "wincount" : 0, "losecount" : 0}
        IncrementKey = ""
        match(JsonPayload['result']):
            case "won":
                IncrementKey = "wincount"
            case "lost":
                IncrementKey = "losecount"
            case _:
                return

        # Try to initialize rows from active card list.
        for card in JsonPayload['activecards']:
            CardData['cardid'] = card
            self.DatabaseCursor.execute("INSERT OR IGNORE INTO cardtable VALUES(:cardid, :selectedcount, :showncount, :wincount, :losecount)", CardData)
            self.DatabaseCursor.execute("UPDATE cardtable SET "+IncrementKey+" = "+IncrementKey+" + 1 WHERE cardid = '"+card+"'")

########################################
# MISC

    def CleanupPreviousSessions(self):
        Result = self.DatabaseCursor.execute("SELECT sessionid FROM sessiontable WHERE status IS 'InProgress'").fetchall()
        for SessionID in Result:
            self.DatabaseCursor.execute("UPDATE sessiontable SET status = 'Ended' WHERE sessionid = '"+SessionID[0]+"'")
            self.DatabaseCursor.execute("UPDATE "+SessionID[0]+" SET status = 'Complete'")

