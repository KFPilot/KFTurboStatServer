#!/usr/bin/env python3

# Killing Floor Turbo Connection Manager
# Spins up a Database Manager and manages incomming connections, routing payloads received to it.
# I am not familiar with Python nor SQLite so this should only be used as an example implementation. 
# Distributed under the terms of the GPL-2.0 License.
# For more information see https://github.com/KFPilot/KFTurbo.

import time
import json
import os
import socket
import socketserver
import threading
from queue import Queue
import DatabaseManager
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument("-p", "--port", dest="port",
                    help="Port to bind to.", metavar="PORT")
parser.add_argument("-c", "--con", dest="maxcon",
                    help="Max number of connections for server socket.", metavar="CON", default=10)

args = parser.parse_args()

PayloadList = Queue()

Database = DatabaseManager.DatabaseManager()

ServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ServerSocket.bind((socket.gethostname(), int(args.port)))
ServerSocket.listen(int(args.maxcon))

def GetSessionID(ID):
    ID = str(ID)
    LetterID = ""
    for Char in ID:
        LetterID = LetterID + chr(ord('A') + int(Char))
    return LetterID

def HandlePayload(JsonData):
    Database.ProcessPayload(GetSessionID(abs(hash(JsonData['session']))), JsonData)

def HandleConnection(ClientSocket, Address):
    print("Started thread for connection...")
    while (True):
        Data = ClientSocket.recv(8192)
        StringData = Data.decode('utf-8')

        if (StringData == ""):
            continue

        JsonData = None

        try:
            JsonData = json.loads(StringData)
        except:
            print("Error attempting to decode data.")
        
        if (JsonData == None):
            continue

        if ((not 'type' in JsonData) or (not 'session' in JsonData)):
            print("Malformed data - missing payload type or session ID.")
            continue

        PayloadList.put(JsonData)

def StartServer():
    while (True):
        (ClientSocket, Address) = ServerSocket.accept()
        print("Accepted connection...")
        threading.Thread(target=HandleConnection, args=(ClientSocket, Address)).start()
    
threading.Thread(target=StartServer).start()

# Main thread watches queue populated by connection threads and tells the database manager about items as they're popped.
while (True):
    Payload = PayloadList.get()
    if (Payload == None):
        continue
    HandlePayload(Payload)
