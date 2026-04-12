# KFTurbo Stat Server

A simple set of python scripts to handle a network database manager for analytic data from Killing Floor Turbo's TurboStatsTcpLink and TurboCardStatsTcpLink.

## How To Use
This set of scripts can be used by running ConnectionManager.py with the following two command line arguments:
- `-p` or `--port` followed by a number. Port to bind to.
- `-c` or `--con` followed by a number. Max number of connections for server socket.

## Usage Examples

### On Windows
```cmd
py.exe .\ConnectionManager.py -p 10101 -c 5
```

### On Linux
```bash
./ConnectionManager.py -p 10101 -c 5
```

## Docker

### Build image
```bash
docker build -t kfturbo-stat:local .
```

### Run with Docker
```bash
docker run --rm -p 10101:10101 kfturbo-stat:local
```

### Run with Docker Compose
```bash
docker compose up -d --build
```

Compose defaults:
- `KF_LISTEN_PORT=10101`
- `KF_MAX_CONNECTIONS=10`
- `TURBO_DB_PATH=/app/data/TurboDatabase.db`
- database persisted to `./data/TurboDatabase.db`
