"""
basic_server.py - the single-threaded WORDQ server (CSE3300 PA1, basic part).

How to run:  python3 basic_server.py [port] [wordlist_path]
             defaults: port 12000, and wordlist.txt sitting next to this file.

Loads the word list once, then serves ONE client at a time, start to finish.
Everyone else waits in line like it's the DMV. The protocol stuff lives in
wordq_protocol.py. (Code written with Claude, AI assistant - see design doc.)
"""

import os      # to find wordlist.txt next to this script
import socket  # TCP sockets
import sys     # command-line arguments and exit codes

import wordq_protocol as wq   # our shared protocol rulebook


def parse_args(argv):
    """Grab (port, wordlist_path) from the command line, or use the defaults."""
    here = os.path.dirname(os.path.abspath(__file__))       # the folder this file lives in
    port = int(argv[1]) if len(argv) > 1 else wq.DEFAULT_PORT
    path = argv[2] if len(argv) > 2 else os.path.join(here, "wordlist.txt")
    return port, path


def main():
    """Load the words, open the socket, serve clients one at a time forever."""
    try:
        port, path = parse_args(sys.argv)
    except ValueError:                                       # someone typed a port like "banana"
        print("Usage: python3 basic_server.py [port] [wordlist_path]")
        sys.exit(1)
    try:
        words = wq.load_words(path)                          # read all 69,903 words once
    except OSError as e:                                     # file missing or unreadable
        print("Cannot read word list %s: %s" % (path, e))
        sys.exit(1)
    print("Loaded %d words from %s" % (len(words), path))

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # IPv4 + TCP
    # Lets us restart the server right away instead of waiting for the OS to
    # let go of the port (the dreaded "Address already in use").
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_sock.bind(("", port))                         # "" = listen on every network card
    except OSError as e:                                     # port taken, probably another server
        print("Cannot bind to port %d: %s" % (port, e))
        server_sock.close()
        sys.exit(1)
    server_sock.listen(1)                                    # tiny waiting line, we're basic
    # accept() wakes up every second so Ctrl-C actually works (on Windows a
    # blocking accept() ignores Ctrl-C until a client shows up. Rude.)
    server_sock.settimeout(1.0)
    print("Basic WORDQ server listening on port %d (Ctrl-C to stop)" % port)

    try:
        while True:
            try:
                conn, addr = server_sock.accept()            # wait for someone to connect
            except socket.timeout:                           # 1 second passed, nobody came
                continue                                     # check for Ctrl-C, try again
            conn.settimeout(None)                            # client socket: wait as long as needed
            print("Connected by", addr)
            # Serve this client RIGHT HERE in the main thread. Nobody else
            # gets in until this one is completely done. One at a time, folks.
            wq.serve_client(conn, addr, words)
            print("Finished with", addr)
    except KeyboardInterrupt:                                # Ctrl-C pressed
        print("\nServer shutting down.")
    finally:
        server_sock.close()                                  # give the port back


if __name__ == "__main__":
    main()
