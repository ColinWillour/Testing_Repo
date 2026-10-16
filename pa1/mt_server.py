"""
mt_server.py - multi-threaded WORDQ server (CSE3300 PA1, multi-threaded part).

Usage:  python3 mt_server.py [port] [wordlist_path]
        defaults: port 12000, wordlist.txt in the same folder as this script.

The main thread loads the word list once and runs dispatcher(), which accepts
connections and starts a new thread (handle_client) for each client, so many
clients are served at the same time. All threads share the same word list.
The list is only ever READ after start-up, so no lock is needed.

BORROWED CODE
-------------
Adapted from the provided sample thread-server.py (Mark Lutz,
"Programming Python", O'Reilly). Borrowed from it:
  * the dispatcher / per-client handler structure: dispatcher() loops on
    accept() and calls thread.start_new_thread(handler, (conn, ...))
  * the now() helper (time.ctime(time.time()))
  * listen backlog of 5
  * use of the low-level _thread module ("import _thread as thread")
Written by me:
  * the WORDQ protocol and wildcard matching (wordq_protocol.py)
  * the read-only word list shared by all threads
  * error handling in handle_client (try/except/finally, always closes)
  * command-line arguments, SO_REUSEADDR, bind-error and Ctrl-C handling
Removed from the sample: time.sleep(5) (simulated blocking work) and the
"Echo=>" reply loop, replaced by wq.serve_client().
Comments marked [BORROWED] below label lines taken from the sample.
"""

import os                    # build the default word-list path
import socket                # TCP sockets
import sys                   # command-line arguments and exit codes
import time                  # [BORROWED] used by now()
import _thread as thread     # [BORROWED] low-level threads, as in the sample

import wordq_protocol as wq  # shared WORDQ protocol code (written by me)


def now():
    """[BORROWED] Current time on the server, as a readable string."""
    return time.ctime(time.time())


def handle_client(conn, addr, words):
    """Runs in its own thread: serve one client, then report when finished.
    [BORROWED structure] replaces the sample's handleClient echo loop."""
    try:
        wq.serve_client(conn, addr, words)        # whole session for this client
    except Exception as e:                        # never let a thread die silently
        print("Error while serving %s: %s" % (addr, e))
    finally:
        conn.close()                              # safe even if already closed
        print("Client %s finished at %s" % (addr, now()))


def dispatcher(server_sock, words):
    """[BORROWED structure] Accept clients forever; hand each to a new thread
    so the main thread can immediately go back to accept()."""
    while True:
        try:
            conn, addr = server_sock.accept()     # wait for the next connection
        except socket.timeout:                    # 1 s tick so Ctrl-C works on
            continue                              # every OS (see main)
        conn.settimeout(None)                     # client socket: fully blocking
        print("Server connected by", addr, "at", now())   # [BORROWED]
        # [BORROWED] one new thread per client; the word list is passed in and
        # shared read-only by every thread.
        thread.start_new_thread(handle_client, (conn, addr, words))


def parse_args(argv):
    """Return (port, wordlist_path) from the command line, using defaults."""
    here = os.path.dirname(os.path.abspath(__file__))       # this script's folder
    port = int(argv[1]) if len(argv) > 1 else wq.DEFAULT_PORT
    path = argv[2] if len(argv) > 2 else os.path.join(here, "wordlist.txt")
    return port, path


def main():
    """Load words, open the listening socket, run the dispatcher."""
    try:
        port, path = parse_args(sys.argv)
    except ValueError:                                       # port not a number
        print("Usage: python3 mt_server.py [port] [wordlist_path]")
        sys.exit(1)
    try:
        words = wq.load_words(path)                          # read once, share
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
    server_sock.listen(5)                                    # [BORROWED] backlog 5
    # accept() wakes up every second so Ctrl-C is noticed (on Windows a fully
    # blocking accept() ignores Ctrl-C).
    server_sock.settimeout(1.0)
    print("Multi-threaded WORDQ server listening on port %d (Ctrl-C to stop)" % port)

    try:
        dispatcher(server_sock, words)                       # runs until Ctrl-C
    except KeyboardInterrupt:
        print("\nServer shutting down.")
    finally:
        server_sock.close()                                  # free the port


if __name__ == "__main__":
    main()
