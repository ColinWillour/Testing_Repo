# PA1 - WORDQ TCP word-query project (CSE3300)

Python 3, standard library only. Run from this folder, each program in its own terminal.

| File | Purpose |
|---|---|
| `wordq_protocol.py` | Shared protocol module (spec in its docstring) |
| `basic_server.py` / `basic_client.py` | Single-threaded server / one-query client |
| `mt_server.py` / `mt_client.py` | Multi-threaded server / multi-query client (`quit` to exit) |
| `test_raw_protocol.py` | Sends malformed requests to test the 400 cases |
| `wordlist.txt` | 69,903 words, one per line |
| `logs/` | Captured output of every test run |
| `PA1_Design_Document.docx` (+ `.pdf`) | Design document |

```
python3 mt_server.py [port] [wordlist_path]   # defaults 12000, ./wordlist.txt
python3 mt_client.py [host] [port]            # defaults 127.0.0.1, 12000
```

Required test counts: `??????????` = 24071, `?` = 69903, `?(a)` = 414, `-?-` = 13.
