#!/usr/bin/env python3

# Killing Floor Turbo Connection Manager
# Spins up a Database Manager and manages incomming connections, routing payloads received to it.
# I am not familiar with Python nor SQLite so this should only be used as an example implementation.
# Distributed under the terms of the GPL-2.0 License.
# For more information see https://github.com/KFPilot/KFTurbo.

import signal
import sys
import json
import os
import socket
import socketserver
import threading
from queue import Queue
import DatabaseManager
from argparse import ArgumentParser, ArgumentError

parser = ArgumentParser(description="Killing Floor Turbo Connection Manager. Spins up a Database Manager and manages incoming connections, routing payloads received to it.")
parser.add_argument("-p", "--port", dest="port", type=int, required=True,
                    help="Port to bind to (required).", metavar="PORT")
parser.add_argument("-c", "--con", dest="maxcon", type=int,
                    help="Max number of connections for the server socket. Default is 10.", metavar="CON", default=10)
parser.add_argument("-v", "--verbose", dest="verbose", type=bool, default=False)

try:
    args = parser.parse_args()
except SystemExit as e:
    # Handle invalid or missing arguments
    if e.code != 0:  # Non-zero exit code means an error
        print("\nError: Missing required arguments or invalid inputs.")
        exit(1)

PayloadList = Queue()

Database = DatabaseManager.DatabaseManager()

ServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ServerSocket.bind(("0.0.0.0", int(args.port)))
ServerSocket.listen(int(args.maxcon))

def ShutdownServer(signal_received, frame):
    print("Shutting down server...")
    ServerSocket.close()
    sys.exit(0)

signal.signal(signal.SIGINT, ShutdownServer) 
signal.signal(signal.SIGTERM, ShutdownServer)

def HandlePayload(JsonData):
    Database.ProcessPayload(JsonData['session'], JsonData)

def HandleConnection(ClientSocket, Address):
    print("Started thread for connection at "+str(Address))
    Buffer = ""
    OpenSession = None
    try:
        while (True):
            Data = ClientSocket.recv(8192)
            StringData = Data.decode('utf-8')

            if (StringData == ""):
                print("Breaking out of connection loop for "+str(Address))
                break

            Buffer += StringData
            Lines = Buffer.split("\r\n")
            Buffer = Lines.pop()

            for Line in Lines:
                Line = Line.strip()

                if (Line == "" or Line == "keepalive"):
                    continue

                if (args.verbose):
                    print("RECEIVED: " + Line)

                JsonData = None

                try:
                    JsonData = json.loads(Line)
                except Exception:
                    print("Error attempting to decode data:"+Line)
                    continue

                if (JsonData == None):
                    continue

                if ((not 'type' in JsonData) or (not 'session' in JsonData)):
                    print("Malformed data - missing payload type or session ID.")
                    continue

                if JsonData['type'] == 'gamebegin':
                    OpenSession = JsonData['session']
                elif JsonData['type'] == 'gameend':
                    OpenSession = None

                PayloadList.put(JsonData)
    except Exception as Error:
        print("Error "+str(Error)+" occurred for connection at "+str(Address))

    if OpenSession is not None:
        print("Connection at "+str(Address)+" closed with open session "+str(OpenSession)+" - marking aborted.")
        PayloadList.put({
            'type': 'gameend',
            'session': OpenSession,
            'wavenum': 0,
            'result': 'aborted',
        })

    print("Stopping thread for connection at "+str(Address))

def StartServer():
    print("Started server thread and waiting for connections...")
    while (True):
        (ClientSocket, Address) = ServerSocket.accept()
        print("Accepted connection...")
        ClientSocket.settimeout(30)
        ConnectionThread = threading.Thread(target=HandleConnection, args=(ClientSocket, Address))
        ConnectionThread.daemon = True
        ConnectionThread.start()

try:
    ServerThread = threading.Thread(target=StartServer)
    ServerThread.daemon = True
    ServerThread.start()
except:
    ShutdownServer(None, None)

# Main thread watches queue populated by connection threads and tells the database manager about items as they're popped.
while (True):
    Payload = PayloadList.get()
    if (Payload == None):
        continue
    HandlePayload(Payload)
