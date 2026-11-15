import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import relay

NOW = dt.datetime(2026,11,9,12,0,tzinfo=dt.timezone.utc)

def req(i='nexara-request-00001', tool='nexara_bridge_state'):
    payload={"protocol":relay.PROTOCOL,"request_id":i,"tool":tool,"args":{},"issued_at":"2026-11-09T11:59:00Z","expires_at":"2026-11-09T12:05:00Z"}
    return {"id":123,"user":{"login":"Zsx154855","id":170140270},"body":relay.REQUEST_MARKER+'\n'+json.dumps(payload)}

class FakeAPI:
    actor_id = 170140270
    def __init__(self, comments):
        self.entries=comments
        self.posted=[]
    def comments(self):
        return list(self.entries)
    def post(self, body):
        self.posted.append(body)
        self.entries.append({"id":123456, "body":body, "user":{"login":"Zsx154855","id":170140270}})
        return self.entries[-1]

class Tests(unittest.TestCase):
    def test_owner_only(self):
        c=req(); c['user']['login']='someone-else'
        self.assertIsNone(relay.request_from_comment(c,'Zsx154855',NOW))
    def test_valid(self):
        self.assertEqual(relay.request_from_comment(req(),'Zsx154855',NOW)['tool'],'nexara_bridge_state')
    def test_expired(self):
        self.assertIsNone(relay.request_from_comment(req(),'Zsx154855',NOW+dt.timedelta(hours=1)))
    def test_future(self):
        self.assertIsNone(relay.request_from_comment(req(),'Zsx154855',NOW-dt.timedelta(hours=1)))
    def test_nonempty_args_denied(self):
        c=req();p=json.loads(c['body'].split('\n',1)[1]);p['args']={'command':'rm -rf /'};c['body']=relay.REQUEST_MARKER+'\n'+json.dumps(p)
        with self.assertRaises(relay.RelayError): relay.request_from_comment(c,'Zsx154855',NOW)
    def test_unknown_tool_denied(self):
        with self.assertRaises(relay.RelayError): relay.request_from_comment(req(tool='shell_command'),'Zsx154855',NOW)
    def test_extra_key_denied(self):
        c=req();p=json.loads(c['body'].split('\n',1)[1]);p['override']=True;c['body']=relay.REQUEST_MARKER+'\n'+json.dumps(p)
        with self.assertRaises(relay.RelayError): relay.request_from_comment(c,'Zsx154855',NOW)
    def test_short_ttl_only(self):
        c=req();p=json.loads(c['body'].split('\n',1)[1]);p['expires_at']='2026-11-09T13:59:00Z';c['body']=relay.REQUEST_MARKER+'\n'+json.dumps(p)
        with self.assertRaises(relay.RelayError): relay.request_from_comment(c,'Zsx154855',NOW)
    def test_boolean_only_and_unknown(self):
        out=relay.redacted_receipt({'request_id':'valid'},True,{'inflight':True,'receipt':'False','manifest':'SECRET'}, {'bridge_job_inflight':'inflight','receipt_ready':'receipt','manifest_present':'manifest'})
        self.assertEqual(out['bridge_job_inflight'],True)
        self.assertEqual(out['receipt_ready'],'unknown')
        self.assertEqual(out['manifest_present'],'unknown')
        self.assertNotIn('SECRET',json.dumps(out))
    def test_no_raw_results(self):
        s=relay.redacted_receipt({'request_id':'valid'},True,{'localPath':'/private/path','token':'dummy-secret'},{})
        self.assertNotIn('dummy-secret',json.dumps(s));self.assertNotIn('/private/',json.dumps(s))
    def test_receipt_detection(self):
        r=relay.redacted_receipt({'request_id':'foo'},True,{},{});api=FakeAPI([])
        api.post(relay.receipt_body(r))
        self.assertEqual(len(relay.existing_receipts(api.comments(),'foo')),1)
    def test_single_tool_execution_and_post(self):
        with tempfile.TemporaryDirectory() as d:
            a=FakeAPI([req()]);p=Path(d).resolve()/'state.json'
            with patch.object(relay.dt,'datetime',wraps=dt.datetime) as mockdt,patch.object(relay,'call_mcp',return_value={'inflight':True}) as mcp:
                mockdt.now.return_value=NOW
                out=relay.process_once(a,'Zsx154855',p,['dummy'],{'nexara_bridge_state':{'bridge_job_inflight':'inflight'}})
            self.assertEqual(out,['POSTED'])
            self.assertEqual(mcp.call_count,1)
            self.assertEqual(len(a.posted),1)
            self.assertEqual(json.loads(a.posted[0].split('\n',1)[1])['bridge_job_inflight'],True)
            with patch.object(relay,'call_mcp') as mcp2,patch.object(relay.dt,'datetime',wraps=dt.datetime) as mockdt2:
                mockdt2.now.return_value=NOW
                relay.process_once(a,'Zsx154855',p,['dummy'],{})
            mcp2.assert_not_called()
    def test_crash_inflight_never_reruns(self):
        with tempfile.TemporaryDirectory() as d:
            a=FakeAPI([req()]);p=Path(d).resolve()/'state.json'
            relay.atomic_store(p, {'jobs':{'nexara-request-00001':{'phase':'INFLIGHT','source_comment_id':123}}})
            with patch.object(relay,'call_mcp') as mcp,patch.object(relay.dt,'datetime',wraps=dt.datetime) as mockdt:
                mockdt.now.return_value=NOW
                self.assertIn('INFLIGHT_QUARANTINED',relay.process_once(a,'Zsx154855',p,['dummy'],{}))
            mcp.assert_not_called()
    def test_post_error_never_reruns(self):
        with tempfile.TemporaryDirectory() as d:
            a=FakeAPI([req()]);p=Path(d).resolve()/'state.json'
            with patch.object(relay.dt,'datetime',wraps=dt.datetime) as mockdt,patch.object(relay,'call_mcp',return_value={}):
                mockdt.now.return_value=NOW
                with patch.object(a,'post',side_effect=ConnectionError):
                    self.assertEqual(relay.process_once(a,'Zsx154855',p,['dummy'],{}),['POST_UNCERTAIN_QUARANTINED'])
            self.assertEqual(json.loads(p.read_text())['jobs']['nexara-request-00001']['phase'],'POST_UNCERTAIN')
            with patch.object(relay,'call_mcp') as mcp,patch.object(relay.dt,'datetime',wraps=dt.datetime) as mockdt2:
                mockdt2.now.return_value=NOW
                self.assertIn('POST_UNCERTAIN_QUARANTINED',relay.process_once(a,'Zsx154855',p,['dummy'],{}))
            mcp.assert_not_called()
    def test_duplicate_request_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            a=FakeAPI([req(),dict(req(), id=124)]);p=Path(d).resolve()/'s.json'
            with patch.object(relay,'call_mcp') as mcp,patch.object(relay.dt,'datetime',wraps=dt.datetime) as mockdt:
                mockdt.now.return_value=NOW
                self.assertEqual(relay.process_once(a,'Zsx154855',p,['dummy'],{}),['DUPLICATE_REQUEST_REJECTED']*2)
            mcp.assert_not_called()
    def test_tool_allowlist(self):
        with self.assertRaises(relay.RelayError):relay.call_mcp(['echo'],'shell_command')
    def test_load_config_permission(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d).resolve()/'config.json';p.write_text('{}');p.chmod(0o644)
            with self.assertRaises(relay.RelayError):relay.load_config(p)
    def test_request_content_never_shell(self):
        c=req();c['body']+='\nRUN rm -rf /'
        with self.assertRaises(relay.RelayError):relay.request_from_comment(c,'Zsx154855',NOW)

if __name__=='__main__':unittest.main()

class RealStdioFixture(unittest.TestCase):
    def test_call_real_mcp_stdio(self):
        argv=[sys.executable,str(Path(__file__).parent/'fake_stdio_mcp.py')]
        output=relay.call_mcp(argv,'nexara_bridge_state',timeout=5)
        self.assertEqual(output['bridge_job_inflight'],True)
        self.assertEqual(output['receipt_ready'],False)
        safe=relay.redacted_receipt({'request_id':'test'},True,output,{'bridge_job_inflight':'bridge_job_inflight','receipt_ready':'receipt_ready'})
        self.assertNotIn('NOT_FOR_PUBLIC',relay.receipt_body(safe))
        self.assertEqual(safe['bridge_job_inflight'],True)
