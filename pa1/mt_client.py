"""
mt_client.py - WORDQ client that sends many queries (CSE3300 PA1, multi-threaded part).

Usage:  python3 mt_client.py [host] [port]
        defaults: 127.0.0.1 and 12000.

Connects ONCE and keeps the connection open: each line typed at the prompt is
sent as "QUERY <line>" and the reply is printed. Typing "quit" (or Ctrl-D/EOF)
sends QUIT, reads the server's "200 BYE" and exits. Empty lines are ignored.
All code written by me.
"""

import sys                   # command-line arguments and exit codes

import wordq_protocol as wq  # shared WORDQ protocol code


def print_result(code, reason, words):
    """Print one reply (same format as basic_client.py)."""
    print("Server replied: %d %s" % (code, reason))
    print("Number of matching words: %d" % len(words))
    for w in words:                               # one word per line
        print(w)


def main():
    """Connect, then loop: read a query, send it, print the reply."""
    host = sys.argv[1] if len(sys.argv) > 1 else wq.DEFAULT_HOST
    try:
        port = int(sys.argv[2]) if len(sys.argv) > 2 else wq.DEFAULT_PORT
    except ValueError:                            # port not a number
        print("Usage: python3 mt_client.py [host] [port]")
        sys.exit(1)

    try:
        sock, rfile = wq.connect(host, port)      # one connection for the session
    except OSError as e:                          # refused, unreachable, timeout
        print("Could not connect to %s:%d (%s). Is the server running?"
              % (host, port, e))
        sys.exit(1)
    print("Connected to %s:%d" % (host, port))

    status = 0                                    # process exit code
    try:
        while True:
            try:
                query = input("Enter query (or 'quit'): ").strip()
            except EOFError:                      # end of input counts as quit
                query = "quit"
                print()
            if not query:                         # ignore empty lines
                continue
            if query.lower() == "quit":
                wq.send_line(sock, "QUIT")        # polite goodbye
                code, reason, _ = wq.read_response(rfile)
                print("Server replied: %d %s" % (code, reason))
                break
            wq.send_line(sock, "QUERY " + query)
            code, reason, words = wq.read_response(rfile)
            print_result(code, reason, words)
    except (OSError, wq.ProtocolError) as e:      # lost connection / bad reply
        print("Error talking to server: %s" % e)
        status = 1
    except KeyboardInterrupt:                     # Ctrl-C: leave without QUIT
        print("\nInterrupted.")
    finally:
        rfile.close()                             # always release both
        sock.close()
    sys.exit(status)


if __name__ == "__main__":
    main()
