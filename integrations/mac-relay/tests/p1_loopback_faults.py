"""Inject real TCP response loss against an isolated HTTP mailbox fixture."""

import http.server
import json
from pathlib import Path
import sys
import tempfile
import threading
from urllib.request import Request, build_opener, ProxyHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import durable
import relay
from test_durable import NOW, RID, request


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send_json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/comments":
            if self.server.fail_read:
                self.server.fail_read = False
                return  # Close the connection without an HTTP response.
            self.send_json(list(self.server.rows.values()))
        else:
            self.send_json(self.server.rows[int(self.path.rsplit("/", 1)[1])])

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))["body"]
        self.server.rows[51] = {"id": 51, "body": body, "user": {"id": relay.OWNER_ID, "login": relay.OWNER}}
        self.server.posts += 1
        # Keep the TCP connection open without sending headers until the client times out.
        self.server.finish_post.wait(5)


class Mailbox:
    actor_id = relay.OWNER_ID

    def __init__(self, port):
        self.base = f"http://127.0.0.1:{port}"
        self.opener = build_opener(ProxyHandler({}))
        self.timeout_observed = False

    def wire(self, path, data=None):
        try:
            with self.opener.open(Request(self.base + path, data=data), timeout=0.75) as result:
                return json.load(result)
        except TimeoutError as exc:
            self.timeout_observed = True
            raise relay.RelayError("fixture_timeout") from exc
        except OSError as exc:
            raise relay.RelayError("fixture_disconnected") from exc

    def comments(self, _since=None):
        return self.wire("/comments")

    def comment(self, ident):
        return self.wire(f"/comments/{ident}")

    def post(self, body):
        return self.wire("/comments", json.dumps({"body": body}).encode())

    def assert_open(self):
        pass

    def assert_actor(self):
        pass


def main():
    with tempfile.TemporaryDirectory() as directory, http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        server.rows, server.fail_read, server.posts = {41: request()}, True, 0
        server.finish_post = threading.Event()
        runner = threading.Thread(target=server.serve_forever, daemon=True)
        runner.start()
        try:
            calls = []

            def invoke(*_):
                calls.append(1)
                return {"status": "PASS"}

            cfg = {"owner": relay.OWNER, "mcp_argv": ["/fixture"], "field_paths": {}}
            mailbox = Mailbox(server.server_port)
            with durable.Controller(Path(directory).resolve(), mailbox, cfg, now=lambda: NOW, invoke=invoke) as worker:
                try:
                    worker.tick()
                except relay.RelayError as exc:
                    assert str(exc) == "fixture_disconnected"
                else:
                    raise AssertionError("the injected read disconnect was not observed")
                assert worker.job(RID) is None and not calls
                assert worker.tick() == "UNKNOWN_OUTCOME" and mailbox.timeout_observed
                assert worker.tick() == "COMPLETED"
                assert len(calls) == server.posts == 1
        finally:
            server.finish_post.set()
            server.shutdown()
            runner.join()
    print(json.dumps({"loopback_tcp_read_disconnect": True, "resumed": True,
                      "actual_post_response_timeout": True, "fixture_receipts": 1,
                      "reconciled_without_repost": True, "github_service_used": False}))


if __name__ == "__main__":
    main()
