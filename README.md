# botconnectserver

A standard-library asyncio TCP server for authenticated clients. Python 3.10+ required; no runtime dependencies.

## Deployment

Set a unique, long random key for each client. Configure a comma-separated `CLIENT_KEYS` environment variable, or set `CLIENT_KEYS_FILE` to a UTF-8 file with one key per line (blank lines and lines beginning with `#` are ignored). Both sources are combined. Changes require a restart. The server refuses to start without keys. Protect the keys file and environment from other users.

```sh
export CLIENT_KEYS_FILE=/secure/path/to/keys.txt
export HOST=0.0.0.0 PORT=9000
python -m botconnectserver
```

See `config.example`. Alternatively install with `pip install .` and run `botconnectserver`. Stop with SIGINT or SIGTERM. For local testing, in separate terminals:

```sh
CLIENT_KEY='your-client-key' HOST=127.0.0.1 PORT=9000 python example_client.py
```

Enter text and press Return; other authenticated clients receive it. The server logs message payloads, so avoid sending sensitive content if logs are retained.

## Protocol

TCP frames are UTF-8 JSON objects terminated by a newline, at most 65536 bytes including the newline. Each connection must send an authentication frame within 10 seconds:

```json
{"type":"auth","key":"client-specific-key"}
```

Success returns `{"type":"auth_ok"}`. An invalid or missing key returns `{"type":"error","error":"authentication failed"}` and closes the connection; timeout, malformed JSON, incomplete and oversized frames close it. After authentication, send `{"type":"message","payload":...}`; payload can be any JSON value. The server logs the payload and broadcasts the same message frame to all *other* currently authenticated clients. There is no delivery acknowledgement or persistence. An unsupported frame receives an error and the connection remains open. A slow or disconnected recipient may be dropped.

TCP is unencrypted: keys and messages are visible on the network. For deployment across untrusted networks, use a TLS-terminating proxy or private encrypted tunnel and restrict direct access to the server. Use random, distinct keys; key identity, revocation without restart, rate limiting, and durable delivery are not provided.
