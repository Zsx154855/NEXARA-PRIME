from test_relay import FakeAPI, NOW, req
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import relay

class Safety(unittest.TestCase):
    def test_numeric_owner_is_required(self):
        c=req(); c["user"]["id"]=99
        self.assertIsNone(relay.request_from_comment(c,"Zsx154855",NOW))

    def test_duplicate_json_keys_fail_closed(self):
        c=req(); c["body"]=c["body"].replace('"args": {}', '"args": {}, "args": {}')
        with self.assertRaises(relay.RelayError):
            relay.request_from_comment(c,"Zsx154855",NOW)

    def test_exact_expiry_is_not_eligible(self):
        self.assertIsNone(relay.request_from_comment(req(),"Zsx154855",NOW+dt.timedelta(minutes=5)))

    def test_post_is_not_complete_without_readback(self):
        with tempfile.TemporaryDirectory() as d:
            a=FakeAPI([req()]); p=Path(d).resolve()/"state.json"
            with patch.object(relay.dt,"datetime",wraps=dt.datetime) as t, patch.object(relay,"call_mcp",return_value={"status":"PASS"}) as call, patch.object(a,"post",return_value={"id":555}) as post:
                t.now.return_value=NOW
                self.assertIn("POST_UNCERTAIN_QUARANTINED",relay.process_once(a,"Zsx154855",p,["dummy"],{}))
                self.assertEqual(json.loads(p.read_text())["jobs"]["nexara-request-00001"]["phase"],"POST_UNCERTAIN")
                relay.process_once(a,"Zsx154855",p,["dummy"],{})
                self.assertEqual(call.call_count,1)
                self.assertEqual(post.call_count,1)

    def test_read_disconnect_does_not_claim(self):
        with tempfile.TemporaryDirectory() as d:
            a=FakeAPI([req()]); p=Path(d).resolve()/"state.json"
            with patch.object(a,"comments",side_effect=ConnectionError),patch.object(relay,"call_mcp") as call:
                with self.assertRaises(ConnectionError):
                    relay.process_once(a,"Zsx154855",p,["dummy"],{})
                self.assertFalse(p.exists())
                call.assert_not_called()

    def test_partial_stdio_frame_has_a_deadline(self):
        import os,time,sys
        # Real child emits a partial line and stays alive. Timeout must not wait for EOF.
        import subprocess
        child=subprocess.Popen([sys.executable,"-c","import sys,time;sys.stdout.write('{');sys.stdout.flush();time.sleep(.5)"],stdout=subprocess.PIPE)
        try:
            begin=time.monotonic()
            with self.assertRaises(relay.RelayError):
                relay.jsonrpc_read(child.stdout,1,.12)
            self.assertLess(time.monotonic()-begin,.35)
        finally:
            child.terminate()
            child.wait(timeout=1)
            child.stdout.close()

    def test_ambiguous_mcp_never_publishes_or_replays(self):
        with tempfile.TemporaryDirectory() as d:
            a=FakeAPI([req()]);p=Path(d).resolve()/"state.json"
            with patch.object(relay.dt,"datetime",wraps=dt.datetime) as t,patch.object(relay,"call_mcp",side_effect=relay.RelayError("mcp_timeout")) as call:
                t.now.return_value=NOW
                relay.process_once(a,"Zsx154855",p,["dummy"],{})
                relay.process_once(a,"Zsx154855",p,["dummy"],{})
                self.assertEqual(call.call_count,1)
                self.assertFalse(a.posted)

    def test_actual_process_exit_preserves_claim_and_prevents_replay(self):
        import subprocess,sys
        with tempfile.TemporaryDirectory() as d:
            p=Path(d).resolve()/"state.json"
            child=Path(__file__).with_name("crash_fixture.py")
            result=subprocess.run([sys.executable,"-B",str(child),str(p)],capture_output=True,timeout=3)
            self.assertEqual(result.returncode,23)
            self.assertEqual(json.loads(p.read_text())["jobs"]["nexara-request-00001"]["phase"],"INFLIGHT")
            a=FakeAPI([req()])
            with patch.object(relay.dt,"datetime",wraps=dt.datetime) as t,patch.object(relay,"call_mcp") as mcp:
                t.now.return_value=NOW
                self.assertEqual(relay.process_once(a,"Zsx154855",p,["dummy"],{}),["INFLIGHT_QUARANTINED"])
            mcp.assert_not_called()
            self.assertFalse(a.posted)
