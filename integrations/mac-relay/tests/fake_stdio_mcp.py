#!/usr/bin/env python3
import json
import sys

for line in sys.stdin:
    try:
        req=json.loads(line)
    except ValueError:
        continue
    mid=req.get('id')
    if mid is None:
        continue
    method=req.get('method')
    if method=='initialize':
        out={'protocolVersion':'2025-03-26','capabilities':{'tools':{}},'serverInfo':{'name':'fixture','version':'0'}}
    elif method=='tools/list':
        out={'tools':[{'name':'nexara_bridge_state','description':'Read only state','inputSchema':{'type':'object','properties':{},'additionalProperties':False}}]}
    elif method=='tools/call':
        if req.get('params') != {'name':'nexara_bridge_state','arguments':{}}:
            print(json.dumps({'jsonrpc':'2.0','id':mid,'error':{'code':-32602,'message':'bad params'}}),flush=True)
            continue
        out={'content':[{'type':'text','text':json.dumps({'bridge_job_inflight':True,'receipt_ready':False,'secret':'NOT_FOR_PUBLIC'})}]}
    else:
        out={}
    print(json.dumps({'jsonrpc':'2.0','id':mid,'result':out}),flush=True)
