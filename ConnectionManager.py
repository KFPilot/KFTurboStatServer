#!/usr/bin/env python3

# Killing Floor Turbo Connection Manager
# Spins up a Database Manager and manages incomming connections, routing payloads received to it.
# I am not familiar with Python nor SQLite so this should only be used as an example implementation.
# Distributed under the terms of the GPL-2.0 License.
# For more information see https://github.com/KFPilot/KFTurbo.

import sys
import json
import os
import socket
import threading
from queue import Queue
from argparse import ArgumentParser
import DatabaseManager

parser = ArgumentParser(description="Killing Floor Turbo Connection Manager. Spins up a Database Manager and manages incoming connections, routing payloads received to it.")
parser.add_argument("-p", "--port", dest="port", type=int, required=True,
                    help="Port to bind to (required).", metavar="PORT")
parser.add_argument("-c", "--con", dest="maxcon", type=int,
                    help="Max number of connections for the server socket. Default is 10.", metavar="CON", default=10)

try:
    args = parser.parse_args()
except SystemExit as e:
    if e.code != 0:
        print("\nError: Missing required arguments or invalid inputs.")
        sys.exit(1)

PayloadList = Queue()
Database = DatabaseManager.DatabaseManager()

ServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ServerSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
ServerSocket.bind((socket.gethostname(), args.port))
ServerSocket.listen(args.maxcon)

def GetSessionID(ID):
    ID = str(ID)
    LetterID = ""
    for Char in ID:
        LetterID += chr(ord('A') + int(Char))
    return LetterID

def ShutdownServer():
    print("Shutting down...")
    ServerSocket.close()
    sys.exit(0)

def HandlePayload(JsonData):
    session_id = GetSessionID(abs(hash(JsonData['session'])))
    Database.ProcessPayload(session_id, JsonData)

def HandleConnection(ClientSocket, Address):
    print("Started thread for connection from", Address)
    while True:
        try:
            Data = ClientSocket.recv(8192)
            if not Data:
                return
            StringData = Data.decode('utf-8')
            if not StringData:
                continue
            try:
                JsonData = json.loads(StringData)
            except:
                print("Error attempting to decode data.")
                continue

            if ('type' not in JsonData) or ('session' not in JsonData):
                print("Malformed data - missing payload type or session ID.")
                continue
            PayloadList.put(JsonData)
        except:
            return

def StartServer():
    while True:
        client_socket, address = ServerSocket.accept()
        print("Accepted connection from", address)
        t = threading.Thread(target=HandleConnection, args=(client_socket, address), daemon=True)
        t.start()

try:
    threading.Thread(target=StartServer, daemon=True).start()
    while True:
        Payload = PayloadList.get()
        if Payload is None:
            continue
        HandlePayload(Payload)
except KeyboardInterrupt:
    pass
finally:
    ShutdownServer()
