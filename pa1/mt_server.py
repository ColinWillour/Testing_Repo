"""
mt_server.py - the multi-threaded WORDQ server (CSE3300 PA1, multi-threaded part).

How to run:  python3 mt_server.py [port] [wordlist_path]
             defaults: port 12000, and wordlist.txt sitting next to this file.

The main thread loads the words once and runs dispatcher(), which accepts
connections and hands each client to its own brand-new thread
(handle_client). So lots of clients can be served at the same time, no
waiting in line. Every thread shares the same word list, and since nobody
ever changes it after loading, no locks are needed. Peaceful.
(Code written with Claude, AI assistant - see design doc.)

BORROWED CODE
-------------
Adapted from the provided sample thread-server.py (Mark Lutz,
"Programming Python", O'Reilly). Borrowed from it:
  * the dispatcher / per-client handler structure: dispatcher() loops on
    accept() and calls thread.start_new_thread(handler, (conn, ...))
  * the now() helper (time.ctime(time.time()))
  * listen backlog of 5
  * the low-level _thread module ("import _thread as thread")
New (not from the sample):
  * the WORDQ protocol and wildcard matching (wordq_protocol.py)
  * the read-only word list shared by all threads
  * error handling in handle_client (try/except/finally, always closes)
  * command-line arguments, SO_REUSEADDR, bind-error and Ctrl-C handling
Removed from the sample: time.sleep(5) (fake "busy work") and the
"Echo=>" reply loop, swapped out for wq.serve_client().
Lines marked [BORROWED] below came from the sample.
"""

import os                    # to find wordlist.txt next to this script
import socket                # TCP sockets
import sys                   # command-line arguments and exit codes
import time                  # [BORROWED] used by now()
import _thread as thread     # [BORROWED] low-level threads, same as the sample

import wordq_protocol as wq  # our shared protocol rulebook (not borrowed)


def now():
    """[BORROWED] What time is it on the server? Returns a readable string."""
    return time.ctime(time.time())


def handle_client(conn, addr, words):
    """Runs in its own thread: deal with one client, then announce we're done.
    [BORROWED structure] - replaces the sample's handleClient echo loop."""
    try:
        wq.serve_client(conn, addr, words)        # the whole conversation with this client
    except Exception as e:                        # don't let a thread die silently in a corner
        print("Error while serving %s: %s" % (addr, e))
    finally:
        conn.close()                              # safe even if it's already closed
        print("Client %s finished at %s" % (addr, now()))


def dispatcher(server_sock, words):
    """[BORROWED structure] The bouncer: accept clients forever and give each
    one its own thread, so the main thread can go right back to the door."""
    while True:
        try:
            conn, addr = server_sock.accept()     # wait for the next client
        except socket.timeout:                    # 1 second tick so Ctrl-C works
            continue                              # on every OS (see main)
        conn.settimeout(None)                     # client socket: wait as long as needed
        print("Server connected by", addr, "at", now())   # [BORROWED]
        # [BORROWED] one new thread per client. They all get the same word
        # list, which is fine because nobody writes to it. Sharing is caring.
        thread.start_new_thread(handle_client, (conn, addr, words))


def parse_args(argv):
    """Grab (port, wordlist_path) from the command line, or use the defaults."""
    here = os.path.dirname(os.path.abspath(__file__))       # the folder this file lives in
    port = int(argv[1]) if len(argv) > 1 else wq.DEFAULT_PORT
    path = argv[2] if len(argv) > 2 else os.path.join(here, "wordlist.txt")
    return port, path


def main():
    """Load the words, open the socket, and let the dispatcher take it from there."""
    try:
        port, path = parse_args(sys.argv)
    except ValueError:                                       # someone typed a port like "banana"
        print("Usage: python3 mt_server.py [port] [wordlist_path]")
        sys.exit(1)
    try:
        words = wq.load_words(path)                          # read once, share with everyone
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
    server_sock.listen(5)                                    # [BORROWED] up to 5 in the waiting room
    # accept() wakes up every second so Ctrl-C actually works (on Windows a
    # blocking accept() ignores Ctrl-C until a client shows up. Rude.)
    server_sock.settimeout(1.0)
    print("Multi-threaded WORDQ server listening on port %d (Ctrl-C to stop)" % port)

    try:
        dispatcher(server_sock, words)                       # runs until Ctrl-C
    except KeyboardInterrupt:
        print("\nServer shutting down.")
    finally:
        server_sock.close()                                  # give the port back


if __name__ == "__main__":
    main()
