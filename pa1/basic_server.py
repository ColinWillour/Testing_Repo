"""
basic_server.py - single-threaded WORDQ server (CSE3300 PA1, basic part).

Usage:  python3 basic_server.py [port] [wordlist_path]
        defaults: port 12000, wordlist.txt in the same folder as this script.

It loads the word list once, then accepts ONE client at a time and serves it
until that client quits. While one client is connected, others wait in the
listen queue (they are not served until the current client finishes).
The protocol itself lives in wordq_protocol.py. All code written by me.
"""

import os      # build the default word-list path next to this script
import socket  # TCP sockets
import sys     # command-line arguments and exit codes

import wordq_protocol as wq   # shared WORDQ protocol code


def parse_args(argv):
    """Return (port, wordlist_path) from the command line, using defaults."""
    here = os.path.dirname(os.path.abspath(__file__))       # this script's folder
    port = int(argv[1]) if len(argv) > 1 else wq.DEFAULT_PORT
    path = argv[2] if len(argv) > 2 else os.path.join(here, "wordlist.txt")
    return port, path


def main():
    """Load words, open the listening socket, and serve clients one by one."""
    try:
        port, path = parse_args(sys.argv)
    except ValueError:                                       # port not a number
        print("Usage: python3 basic_server.py [port] [wordlist_path]")
        sys.exit(1)
    try:
        words = wq.load_words(path)                          # read the list once
    except OSError as e:
        print("Cannot read word list %s: %s" % (path, e))
        sys.exit(1)
    print("Loaded %d words from %s" % (len(words), path))

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # TCP/IPv4
    # Allow an immediate restart on the same port (skip TIME_WAIT delay).
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_sock.bind(("", port))                         # "" = all interfaces
    except OSError as e:                                     # port in use, etc.
        print("Cannot bind to port %d: %s" % (port, e))
        server_sock.close()
        sys.exit(1)
    server_sock.listen(1)                                    # small backlog
    # accept() wakes up every second so Ctrl-C is noticed right away (on
    # Windows a fully blocking accept() ignores Ctrl-C until a client connects).
    server_sock.settimeout(1.0)
    print("Basic WORDQ server listening on port %d (Ctrl-C to stop)" % port)

    try:
        while True:
            try:
                conn, addr = server_sock.accept()            # wait for a client
            except socket.timeout:                           # 1 s tick, no client:
                continue                                     # check Ctrl-C, retry
            conn.settimeout(None)                            # client socket: blocking
            print("Connected by", addr)
            # Served directly in this thread: no other client is accepted
            # until this call returns, i.e. until this client is finished.
            wq.serve_client(conn, addr, words)
            print("Finished with", addr)
    except KeyboardInterrupt:                                # Ctrl-C
        print("\nServer shutting down.")
    finally:
        server_sock.close()                                  # free the port


if __name__ == "__main__":
    main()
