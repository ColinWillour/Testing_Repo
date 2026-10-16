"""
basic_client.py - the one-and-done WORDQ client (CSE3300 PA1, basic part).

How to run:  python3 basic_client.py [host] [port]
             defaults: 127.0.0.1 and 12000.

Asks you for ONE query, sends "QUERY <q>", prints what the server says
(status, how many words, and the words), then leaves. Commitment issues.
(Code written with Claude, AI assistant - see design doc.)
"""

import sys                   # command-line arguments and exit codes

import wordq_protocol as wq  # our shared protocol rulebook


def print_result(code, reason, words):
    """Print a reply the same way both clients do."""
    print("Server replied: %d %s" % (code, reason))
    print("Number of matching words: %d" % len(words))
    for w in words:                               # one word per line, could be a LOT of lines
        print(w)


def main():
    """Ask for one query, send it, print the answer, exit."""
    host = sys.argv[1] if len(sys.argv) > 1 else wq.DEFAULT_HOST
    try:
        port = int(sys.argv[2]) if len(sys.argv) > 2 else wq.DEFAULT_PORT
    except ValueError:                            # port wasn't a number
        print("Usage: python3 basic_client.py [host] [port]")
        sys.exit(1)

    try:
        query = input("Enter query: ").strip()    # e.g. a?t
    except (EOFError, KeyboardInterrupt):         # Ctrl-D / Ctrl-C at the prompt, ok fine
        print()
        sys.exit(1)
    if not query:                                 # empty query? don't even bother the server
        print("Query must not be empty.")
        sys.exit(1)

    try:
        sock, rfile = wq.connect(host, port)
    except OSError as e:                          # refused / unreachable / timed out
        print("Could not connect to %s:%d (%s). Is the server running?"
              % (host, port, e))
        sys.exit(1)

    try:
        wq.send_line(sock, "QUERY " + query)      # one question...
        code, reason, words = wq.read_response(rfile)   # ...one answer
        print_result(code, reason, words)
    except (OSError, wq.ProtocolError) as e:      # connection died or the reply was weird
        print("Error talking to server: %s" % e)
        sys.exit(1)
    finally:
        rfile.close()                             # always clean up after yourself
        sock.close()


if __name__ == "__main__":
    main()
