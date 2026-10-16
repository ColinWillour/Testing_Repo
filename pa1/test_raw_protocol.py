"""
test_raw_protocol.py - sends hand-made protocol lines to a running WORDQ server
to test the error cases the normal clients never send (CSE3300 PA1 testing aid).

Usage:  python3 test_raw_protocol.py [host] [port]
Tests: empty QUERY -> 400, unknown command -> 400 and connection stays open,
lower-case command, 2000-character line -> 400 and the server closes.
All code written by me.
"""

import socket                # to detect the server closing the connection
import sys                   # command-line arguments

import wordq_protocol as wq  # connect / read_response helpers


def exchange(sock, rfile, raw):
    """Send raw bytes, read one reply, print what was sent and received."""
    shown = raw if len(raw) <= 40 else raw[:20] + b"...(%d bytes)" % len(raw)
    print("SEND %r" % shown)
    sock.sendall(raw)
    code, reason, words = wq.read_response(rfile)
    print("RECV %d %s %d" % (code, reason, len(words)))
    return code


def still_open(sock, rfile):
    """True if the server still answers on this connection (sends a real query)."""
    try:
        return exchange(sock, rfile, b"QUERY -?-\n") == 200
    except (OSError, wq.ProtocolError):
        return False


def main():
    """Run the error-case tests against the server given on the command line."""
    host = sys.argv[1] if len(sys.argv) > 1 else wq.DEFAULT_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else wq.DEFAULT_PORT
    sock, rfile = wq.connect(host, port)

    print("--- Test: empty QUERY")
    exchange(sock, rfile, b"QUERY\n")
    exchange(sock, rfile, b"QUERY    \n")              # only blanks
    print("--- Test: unknown command, then check connection stays open")
    exchange(sock, rfile, b"FIND a?t\n")
    print("connection still open:", still_open(sock, rfile))
    print("--- Test: lower-case command (commands are case-insensitive)")
    exchange(sock, rfile, b"query zzzzqx\n")
    print("--- Test: 2000-character line")
    exchange(sock, rfile, b"QUERY " + b"a" * 2000 + b"\n")
    rest = rfile.read()                                # b"" once server sent FIN
    print("server closed connection:", rest == b"")
    rfile.close()
    sock.close()


if __name__ == "__main__":
    main()
