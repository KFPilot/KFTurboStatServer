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

---

**Security related note:**  
On Linux, use ports **above 1024**, as ports **below 1024** require root permissions. Avoid running as root for obvious security reasons. Ensure proper firewall rules are in place to restrict access and prevent exposure to the entire internet.
