"""Deliberately kills this test child after the journal claim; never uses GitHub."""
import datetime as dt
import os
from pathlib import Path
import sys
from unittest.mock import patch
from test_relay import FakeAPI, NOW, req
import relay

with patch.object(relay.dt,"datetime",wraps=dt.datetime) as t, patch.object(relay,"call_mcp",side_effect=lambda *_: os._exit(23)):
    t.now.return_value=NOW
    relay.process_once(FakeAPI([req()]),"Zsx154855",Path(sys.argv[1]),["fixture"],{})
