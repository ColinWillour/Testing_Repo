"""
wordq_protocol.py - the shared brain of the whole project (CSE3300 PA1).

All four programs (basic_server, basic_client, mt_server, mt_client) import
this file, so they all speak the exact same language. Think of it as the
rulebook everyone agreed on before the game started.
(Code written with Claude, AI assistant - see the design doc. Nothing in here
is borrowed from anywhere else.)

THE PROTOCOL, AKA "WORDQ" (yes I named it, no I will not be taking questions)
-----------------------------------------------------------------------------
Transport : TCP, because we want our words to actually arrive. Port 12000.
Encoding  : UTF-8 text, one message per line, every line ends with "\n".
Max line  : 1024 bytes including the "\n". Nobody needs a longer query. Nobody.

What the client can say (upper or lower case, the server isn't picky):
    QUERY <pattern>\n   "find me every word that has <pattern> somewhere in it"
                        each '?' means "any ONE character, I don't care which"
                        (letters, '-', '(' ... anything). Case doesn't matter.
    QUIT\n              "ok I'm done, bye"

What the server says back:
    <code> <reason> <count>\n     the status line
    <word>\n  (exactly <count> of these)

    200 OK <n>           found n words (n >= 1), here they come
    200 BYE 0            reply to QUIT, then the server hangs up
    404 NOT_FOUND 0      valid question, zero answers. Sad.
    400 BAD_REQUEST 0    empty pattern, made-up command, broken UTF-8, or a
                         line over 1024 bytes. Connection stays open so you
                         can try again - EXCEPT for the giant line, then we
                         hang up because we lost track of where lines start.

Why is <count> there? TCP is one long stream of bytes with no "message
ended here" markers, so the count tells the client exactly how many lines
to read. No guessing, no waiting forever.

Example conversation (C = client, S = server):
    C: QUERY -?-
    S: 200 OK 13
    S: <13 words, one per line>
    C: QUERY zzzzqx
    S: 404 NOT_FOUND 0
    C: QUIT
    S: 200 BYE 0
    (server hangs up, end of story)
"""

import re      # regular expressions - how we turn '?' into "any character"
import socket  # the star of the show: TCP sockets

DEFAULT_HOST = "127.0.0.1"   # "this computer" - clients connect here by default
DEFAULT_PORT = 12000         # our port. High enough that nobody important uses it
MAX_LINE = 1024              # longest request line we accept, in bytes (with "\n")
ENCODING = "utf-8"           # how text turns into bytes and back
CLIENT_READ_TIMEOUT = 30     # client waits 30 s for a reply, then gives up on life


class ProtocolError(Exception):
    """The client raises this when the server breaks the rules: a weird status
    line, or the connection dying halfway through a reply."""


def load_words(path):
    """Read the word list ONE time when the server starts up.
    Returns a list of words with the "\\n" chopped off and blank lines skipped."""
    with open(path, encoding=ENCODING) as f:              # 'with' closes the file for us
        return [line.strip() for line in f if line.strip()]  # strip junk, skip empties


def compile_pattern(query):
    """Turn a query like 'a?t' into a regular expression the computer understands.
    '?' becomes '.' (regex for "any one character"). Everything else gets
    escaped so stuff like '(' or '-' is matched literally and doesn't make
    regex do something weird. No ^ or $ on purpose, so it can match anywhere
    inside the word (that's the "*pattern*" part of the assignment)."""
    regex = "".join("." if ch == "?" else re.escape(ch) for ch in query)
    # IGNORECASE: 'A?T' still finds 'ant'. DOTALL: '.' really means ANY character.
    return re.compile(regex, re.IGNORECASE | re.DOTALL)


def find_matches(words, query):
    """Go through all 69,903 words and keep the ones that contain the pattern.
    Brute force, but computers are fast and I am patient."""
    pattern = compile_pattern(query)                 # build the regex once, not 69,903 times
    return [w for w in words if pattern.search(w)]   # search() = "is it anywhere in here?"


def status_line(code, reason, count):
    """Build the first line of every reply, like '200 OK 13\\n'."""
    return "%d %s %d\n" % (code, reason, count)


def _bad_request():
    """The standard '400 BAD_REQUEST 0' reply, already turned into bytes."""
    return status_line(400, "BAD_REQUEST", 0).encode(ENCODING)


def process_request(line_bytes, words):
    """The server's main decision-maker. Takes ONE line from a client and
    figures out what to say back.
    Returns (response_bytes, keep_open): what to send, and whether we keep
    talking to this client afterwards."""
    # readline(MAX_LINE) stops after 1024 bytes. If we got all 1024 and still
    # no "\n", this client is writing a novel -> 400 and hang up (the rest of
    # their novel is still coming, so we can't find where the next line starts).
    if len(line_bytes) > MAX_LINE or (len(line_bytes) == MAX_LINE
                                      and not line_bytes.endswith(b"\n")):
        return _bad_request(), False
    try:
        text = line_bytes.decode(ENCODING)        # bytes -> normal text
    except UnicodeDecodeError:                    # not real UTF-8, just gibberish
        return _bad_request(), True               # bad line, but we can keep going
    text = text.rstrip("\r\n")                    # chop the line ending (Windows "\r" too)
    command, _, argument = text.partition(" ")    # split at the FIRST space only
    command = command.upper()                     # "quit", "Quit", "QuIt" all count

    if command == "QUIT":                         # client is leaving, be polite
        return status_line(200, "BYE", 0).encode(ENCODING), False
    if command == "QUERY":
        pattern = argument.strip()                # ignore extra spaces around it
        if not pattern:                           # "QUERY" with nothing after it. Bold move.
            return _bad_request(), True
        matches = find_matches(words, pattern)
        if not matches:                           # good question, no answers
            return status_line(404, "NOT_FOUND", 0).encode(ENCODING), True
        # Status line + one word per line, all glued into one big chunk to send.
        body = "".join(w + "\n" for w in matches)
        return (status_line(200, "OK", len(matches)) + body).encode(ENCODING), True
    return _bad_request(), True                   # some command we've never heard of


def _close_gracefully(conn):
    """Hang up nicely when the client might still be sending stuff (like the
    rest of that too-long line). If you just close() with unread data, the OS
    panics and sends a TCP reset, which can wipe out our last reply before the
    client reads it. So: say we're done sending, eat whatever they still send,
    THEN close. Basically letting them finish their sentence before leaving."""
    try:
        conn.shutdown(socket.SHUT_WR)             # "I'm done talking" (sends FIN)
        conn.settimeout(2.0)                      # but I'm not waiting forever
        drained = 0
        while drained < 1 << 20:                  # throw away at most 1 MB
            chunk = conn.recv(4096)
            if not chunk:                         # they hung up too, we're done
                break
            drained += len(chunk)
    except OSError:                               # timeout or reset - whatever, we tried
        pass


def serve_client(conn, addr, words, log=print):
    """Talk to one client until they QUIT, send a giant line, or just leave.
    BOTH servers use this: the basic one calls it directly, the multi-threaded
    one calls it inside a new thread. 'log' is where messages go (print by
    default). The socket always gets closed at the end, no matter what."""
    rfile = conn.makefile("rb")                   # wrap the socket so we can use readline()
    try:
        while True:
            line = rfile.readline(MAX_LINE)       # read one line, max 1024 bytes
            if not line:                          # empty = client closed the connection
                log("Client %s closed the connection" % (addr,))
                break
            response, keep_open = process_request(line, words)
            conn.sendall(response)                # sendall keeps going until it's ALL sent
            # Log what they asked (cut to 60 chars) and what we answered.
            log("%s  %r -> %s" % (addr, line[:60],
                                  response.split(b"\n", 1)[0].decode(ENCODING)))
            if not keep_open:                     # QUIT or giant line = time to go
                _close_gracefully(conn)
                break
    except OSError as e:                          # connection reset, broken pipe, etc.
        log("Connection error with %s: %s" % (addr, e))
    finally:
        rfile.close()                             # clean up the file wrapper
        conn.close()                              # and the socket. Leave no trace.


def connect(host, port, timeout=10):
    """Client side: connect to the server.
    Returns (sock, rfile) - the socket plus a reader for the replies.
    Raises OSError (like ConnectionRefusedError) if nobody's home."""
    sock = socket.create_connection((host, port), timeout=timeout)  # 10 s to connect
    sock.settimeout(CLIENT_READ_TIMEOUT)          # then 30 s max to wait for each reply
    return sock, sock.makefile("rb")


def send_line(sock, text):
    """Send one line to the other side (we add the "\\n" for you)."""
    sock.sendall((text + "\n").encode(ENCODING))


def read_response(rfile):
    """Client side: read one whole reply from the server.
    Returns (code, reason, words). Raises ProtocolError if the status line
    looks wrong or the reply gets cut off early."""
    status = rfile.readline()                     # should look like "200 OK 13\n"
    if not status:
        raise ProtocolError("server closed the connection without replying")
    parts = status.decode(ENCODING).split()
    # Must be exactly 3 pieces, and the code and count must be numbers.
    if len(parts) != 3 or not parts[0].isdigit() or not parts[2].isdigit():
        raise ProtocolError("malformed status line: %r" % status)
    code, reason, count = int(parts[0]), parts[1], int(parts[2])
    words = []
    for _ in range(count):                        # read exactly <count> lines, no more no less
        line = rfile.readline()
        if not line.endswith(b"\n"):              # empty or half a line = reply got cut off
            raise ProtocolError("reply truncated after %d of %d words"
                                % (len(words), count))
        words.append(line.decode(ENCODING).rstrip("\n"))
    return code, reason, words
