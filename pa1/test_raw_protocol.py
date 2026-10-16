"""
test_raw_protocol.py - sends deliberately bad messages to a running WORDQ
server to make sure it handles them (CSE3300 PA1 testing helper).
Basically the chaos monkey of this project.

How to run:  python3 test_raw_protocol.py [host] [port]
What it tries: empty QUERY -> 400, made-up command -> 400 (and the connection
stays open), lower-case command still works, 2000-character line -> 400 and
the server hangs up.
(Code written with Claude, AI assistant - see design doc.)
"""

import socket                # to notice when the server hangs up
import sys                   # command-line arguments

import wordq_protocol as wq  # connect / read_response helpers


def exchange(sock, rfile, raw):
    """Send some raw bytes, read one reply, print both so we can see what happened."""
    shown = raw if len(raw) <= 40 else raw[:20] + b"...(%d bytes)" % len(raw)  # don't print the whole novel
    print("SEND %r" % shown)
    sock.sendall(raw)
    code, reason, words = wq.read_response(rfile)
    print("RECV %d %s %d" % (code, reason, len(words)))
    return code


def still_open(sock, rfile):
    """Is the server still talking to us? Ask a real question and see."""
    try:
        return exchange(sock, rfile, b"QUERY -?-\n") == 200
    except (OSError, wq.ProtocolError):
        return False


def main():
    """Run all the bad-request tests against the server."""
    host = sys.argv[1] if len(sys.argv) > 1 else wq.DEFAULT_HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else wq.DEFAULT_PORT
    sock, rfile = wq.connect(host, port)

    print("--- Test: empty QUERY")
    exchange(sock, rfile, b"QUERY\n")
    exchange(sock, rfile, b"QUERY    \n")              # just spaces, nice try
    print("--- Test: unknown command, then check connection stays open")
    exchange(sock, rfile, b"FIND a?t\n")
    print("connection still open:", still_open(sock, rfile))
    print("--- Test: lower-case command (commands are case-insensitive)")
    exchange(sock, rfile, b"query zzzzqx\n")
    print("--- Test: 2000-character line")
    exchange(sock, rfile, b"QUERY " + b"a" * 2000 + b"\n")
    rest = rfile.read()                                # b"" means the server hung up on us
    print("server closed connection:", rest == b"")
    rfile.close()
    sock.close()


if __name__ == "__main__":
    main()
