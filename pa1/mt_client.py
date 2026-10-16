"""
mt_client.py - the WORDQ client that won't stop asking questions
(CSE3300 PA1, multi-threaded part).

How to run:  python3 mt_client.py [host] [port]
             defaults: 127.0.0.1 and 12000.

Connects ONCE and keeps the connection open. Every line you type gets sent
as "QUERY <line>" and the answer is printed. Type "quit" (or hit Ctrl-D /
end of input) to send QUIT, get the server's "200 BYE", and leave.
Empty lines are ignored, because pressing Enter by accident happens.
(Code written with Claude, AI assistant - see design doc.)
"""

import sys                   # command-line arguments and exit codes

import wordq_protocol as wq  # our shared protocol rulebook


def print_result(code, reason, words):
    """Print a reply (same format as basic_client.py)."""
    print("Server replied: %d %s" % (code, reason))
    print("Number of matching words: %d" % len(words))
    for w in words:                               # one word per line, could be a LOT of lines
        print(w)


def main():
    """Connect, then loop: read a query, send it, print the answer, repeat."""
    host = sys.argv[1] if len(sys.argv) > 1 else wq.DEFAULT_HOST
    try:
        port = int(sys.argv[2]) if len(sys.argv) > 2 else wq.DEFAULT_PORT
    except ValueError:                            # port wasn't a number
        print("Usage: python3 mt_client.py [host] [port]")
        sys.exit(1)

    try:
        sock, rfile = wq.connect(host, port)      # one connection for the whole session
    except OSError as e:                          # refused / unreachable / timed out
        print("Could not connect to %s:%d (%s). Is the server running?"
              % (host, port, e))
        sys.exit(1)
    print("Connected to %s:%d" % (host, port))

    status = 0                                    # exit code: 0 = all good
    try:
        while True:
            try:
                query = input("Enter query (or 'quit'): ").strip()
            except EOFError:                      # out of input? treat it like quit
                query = "quit"
                print()
            if not query:                         # just pressed Enter, ignore it
                continue
            if query.lower() == "quit":
                wq.send_line(sock, "QUIT")        # say goodbye properly
                code, reason, _ = wq.read_response(rfile)
                print("Server replied: %d %s" % (code, reason))
                break
            wq.send_line(sock, "QUERY " + query)
            code, reason, words = wq.read_response(rfile)
            print_result(code, reason, words)
    except (OSError, wq.ProtocolError) as e:      # connection died or the reply was weird
        print("Error talking to server: %s" % e)
        status = 1
    except KeyboardInterrupt:                     # Ctrl-C: leave without saying bye. Rude, but allowed.
        print("\nInterrupted.")
    finally:
        rfile.close()                             # always clean up after yourself
        sock.close()
    sys.exit(status)


if __name__ == "__main__":
    main()
