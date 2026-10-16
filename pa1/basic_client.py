"""
basic_client.py - WORDQ client that sends ONE query (CSE3300 PA1, basic part).

Usage:  python3 basic_client.py [host] [port]
        defaults: 127.0.0.1 and 12000.

Reads one wildcard query from the keyboard, sends "QUERY <q>", prints the
server's status, the number of matching words and each word, then exits.
All code written by me.
"""

import sys                   # command-line arguments and exit codes

import wordq_protocol as wq  # shared WORDQ protocol code


def print_result(code, reason, words):
    """Print one reply in the format shared by both clients."""
    print("Server replied: %d %s" % (code, reason))
    print("Number of matching words: %d" % len(words))
    for w in words:                               # one word per line
        print(w)


def main():
    """Ask for one query, send it, print the reply, exit."""
    host = sys.argv[1] if len(sys.argv) > 1 else wq.DEFAULT_HOST
    try:
        port = int(sys.argv[2]) if len(sys.argv) > 2 else wq.DEFAULT_PORT
    except ValueError:                            # port not a number
        print("Usage: python3 basic_client.py [host] [port]")
        sys.exit(1)

    try:
        query = input("Enter query: ").strip()    # e.g. a?t
    except (EOFError, KeyboardInterrupt):         # Ctrl-D / Ctrl-C at the prompt
        print()
        sys.exit(1)
    if not query:                                 # don't bother the server
        print("Query must not be empty.")
        sys.exit(1)

    try:
        sock, rfile = wq.connect(host, port)
    except OSError as e:                          # refused, unreachable, timeout
        print("Could not connect to %s:%d (%s). Is the server running?"
              % (host, port, e))
        sys.exit(1)

    try:
        wq.send_line(sock, "QUERY " + query)      # one request ...
        code, reason, words = wq.read_response(rfile)   # ... one reply
        print_result(code, reason, words)
    except (OSError, wq.ProtocolError) as e:      # lost connection / bad reply
        print("Error talking to server: %s" % e)
        sys.exit(1)
    finally:
        rfile.close()                             # always release both
        sock.close()


if __name__ == "__main__":
    main()
