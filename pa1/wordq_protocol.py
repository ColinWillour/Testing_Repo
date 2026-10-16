"""
wordq_protocol.py - shared code for the WORDQ word-query protocol.
CSE3300 Programming Assignment 1. All code in this file was written for this
assignment (nothing borrowed). Used by basic_server.py, basic_client.py,
mt_server.py and mt_client.py so all four speak exactly the same protocol.

APPLICATION PROTOCOL "WORDQ"
----------------------------
Transport : TCP (reliable, ordered byte stream). Default port 12000.
Encoding  : UTF-8 text, line oriented; every line ends with "\n".
Max line  : a request line may be at most 1024 bytes including the "\n".

Requests (client -> server), command keyword is case-insensitive:
    QUERY <pattern>\n   find every word that CONTAINS <pattern> as a substring
                        (i.e. "*<pattern>*"); each '?' in the pattern matches
                        exactly one arbitrary character (letters, '-', '(' ...).
                        Matching is case-insensitive.
    QUIT\n              end the session.

Response (server -> client):
    <code> <reason> <count>\n     status line
    <word>\n  (exactly <count> times)

    200 OK <n>           n >= 1 matching words follow, one per line
    200 BYE 0            reply to QUIT; the server then closes the connection
    404 NOT_FOUND 0      the query was valid but no word matched
    400 BAD_REQUEST 0    empty pattern, unknown command, invalid UTF-8, or a
                         line longer than 1024 bytes. The connection stays open
                         except for the over-long line, after which the server
                         closes it (it can no longer find the next line start).

Framing: TCP has no message boundaries, so the <count> in the status line tells
the client exactly how many word lines to read; no terminator line is needed.

Example session (C = client, S = server):
    C: QUERY -?-
    S: 200 OK 13
    S: <13 lines, one word each>
    C: QUERY zzzzqx
    S: 404 NOT_FOUND 0
    C: QUIT
    S: 200 BYE 0
    (server closes the connection)
"""

import re      # regular expressions, used to implement the '?' wildcard
import socket  # TCP sockets

DEFAULT_HOST = "127.0.0.1"   # clients connect to the local machine by default
DEFAULT_PORT = 12000         # non-reserved port shared by servers and clients
MAX_LINE = 1024              # longest allowed request line, in bytes, incl. "\n"
ENCODING = "utf-8"           # character encoding of every protocol line
CLIENT_READ_TIMEOUT = 30     # seconds a client waits for a reply before giving up


class ProtocolError(Exception):
    """Raised by the client side when the server's reply breaks the protocol
    (malformed status line, or the connection closes in the middle of a reply)."""


def load_words(path):
    """Read the word list once at server start-up.
    Returns a list of words: each line stripped of whitespace, blank lines skipped."""
    with open(path, encoding=ENCODING) as f:              # file closes automatically
        return [line.strip() for line in f if line.strip()]  # drop "\n" and blanks


def compile_pattern(query):
    """Turn a WORDQ query into a compiled regular expression.
    '?' becomes '.' (any ONE character); every other character is escaped so
    characters such as '(' or '-' are matched literally. No anchors are added,
    so re.search() gives the substring ("*query*") semantics."""
    regex = "".join("." if ch == "?" else re.escape(ch) for ch in query)
    # IGNORECASE: 'A?T' finds 'ant'. DOTALL: '.' would match any char even "\n".
    return re.compile(regex, re.IGNORECASE | re.DOTALL)


def find_matches(words, query):
    """Return every word (in word-list order) that contains the query pattern."""
    pattern = compile_pattern(query)                 # compile once, reuse per word
    return [w for w in words if pattern.search(w)]   # linear scan of the list


def status_line(code, reason, count):
    """Build the status line '<code> <reason> <count>\\n' as text."""
    return "%d %s %d\n" % (code, reason, count)


def _bad_request():
    """The 400 reply used for every kind of malformed request (no words follow)."""
    return status_line(400, "BAD_REQUEST", 0).encode(ENCODING)


def process_request(line_bytes, words):
    """Handle ONE raw request line (as returned by readline) from a client.
    Returns (response_bytes, keep_open): the bytes to send back and whether the
    connection should stay open afterwards."""
    # readline(MAX_LINE) stops after MAX_LINE bytes; if it got that many bytes
    # and still no "\n", the client's line is too long -> 400, then close
    # (the rest of that line is still in the stream, so we cannot re-sync).
    if len(line_bytes) > MAX_LINE or (len(line_bytes) == MAX_LINE
                                      and not line_bytes.endswith(b"\n")):
        return _bad_request(), False
    try:
        text = line_bytes.decode(ENCODING)        # bytes -> str
    except UnicodeDecodeError:                    # not valid UTF-8
        return _bad_request(), True               # bad line, but stream still in sync
    text = text.rstrip("\r\n")                    # drop line ending (also tolerate CRLF)
    command, _, argument = text.partition(" ")    # split at the first space only
    command = command.upper()                     # commands are case-insensitive

    if command == "QUIT":                         # client wants to end the session
        return status_line(200, "BYE", 0).encode(ENCODING), False
    if command == "QUERY":
        pattern = argument.strip()                # ignore surrounding blanks
        if not pattern:                           # "QUERY" with nothing after it
            return _bad_request(), True
        matches = find_matches(words, pattern)
        if not matches:                           # valid query, nothing found
            return status_line(404, "NOT_FOUND", 0).encode(ENCODING), True
        # Status line followed by one word per line, sent as a single buffer.
        body = "".join(w + "\n" for w in matches)
        return (status_line(200, "OK", len(matches)) + body).encode(ENCODING), True
    return _bad_request(), True                   # unknown / empty command


def _close_gracefully(conn):
    """Close a connection that may still hold unread client data (e.g. the rest
    of an over-long line). Closing a socket with unread data makes the kernel
    send a TCP RST, which can destroy our last reply before the client reads it.
    So: stop sending (FIN), discard what the client still sends, then close."""
    try:
        conn.shutdown(socket.SHUT_WR)             # tell client we are done sending
        conn.settimeout(2.0)                      # do not wait forever while draining
        drained = 0
        while drained < 1 << 20:                  # discard at most 1 MiB
            chunk = conn.recv(4096)
            if not chunk:                         # client closed its side
                break
            drained += len(chunk)
    except OSError:                               # timeout / reset: nothing to save
        pass


def serve_client(conn, addr, words, log=print):
    """Serve one connected client until it sends QUIT, sends a fatal bad line,
    or closes the connection. Used by BOTH servers: the basic server calls it
    directly, the multi-threaded server calls it inside a new thread.
    The socket is always closed when this function returns."""
    rfile = conn.makefile("rb")                   # buffered reader -> readline()
    try:
        while True:
            line = rfile.readline(MAX_LINE)       # read at most MAX_LINE bytes
            if not line:                          # b"" means the client closed
                log("Client %s closed the connection" % (addr,))
                break
            response, keep_open = process_request(line, words)
            conn.sendall(response)                # sendall loops until all sent
            # Log the request (shortened) and the status line we answered with.
            log("%s  %r -> %s" % (addr, line[:60],
                                  response.split(b"\n", 1)[0].decode(ENCODING)))
            if not keep_open:                     # QUIT or over-long line
                _close_gracefully(conn)
                break
    except OSError as e:                          # reset, broken pipe, etc.
        log("Connection error with %s: %s" % (addr, e))
    finally:
        rfile.close()                             # release the file wrapper
        conn.close()                              # and the socket itself


def connect(host, port, timeout=10):
    """Client side: open a TCP connection to the server.
    Returns (sock, rfile) where rfile is a buffered reader for replies.
    Raises OSError (e.g. ConnectionRefusedError) if the server is not reachable."""
    sock = socket.create_connection((host, port), timeout=timeout)  # connect timeout
    sock.settimeout(CLIENT_READ_TIMEOUT)          # then a longer timeout for replies
    return sock, sock.makefile("rb")


def send_line(sock, text):
    """Send one protocol line (adds the terminating "\\n")."""
    sock.sendall((text + "\n").encode(ENCODING))


def read_response(rfile):
    """Client side: read one complete reply.
    Returns (code, reason, words). Raises ProtocolError if the status line is
    malformed or the connection closes before all <count> words arrived."""
    status = rfile.readline()                     # "<code> <reason> <count>\n"
    if not status:
        raise ProtocolError("server closed the connection without replying")
    parts = status.decode(ENCODING).split()
    # Exactly three fields, numeric code, non-negative numeric count.
    if len(parts) != 3 or not parts[0].isdigit() or not parts[2].isdigit():
        raise ProtocolError("malformed status line: %r" % status)
    code, reason, count = int(parts[0]), parts[1], int(parts[2])
    words = []
    for _ in range(count):                        # the count is the framing
        line = rfile.readline()
        if not line.endswith(b"\n"):              # b"" or partial line = cut off
            raise ProtocolError("reply truncated after %d of %d words"
                                % (len(words), count))
        words.append(line.decode(ENCODING).rstrip("\n"))
    return code, reason, words
