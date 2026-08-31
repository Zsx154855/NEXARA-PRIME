#!/bin/bash
cd ~/Library/LaunchAgents
echo "CURRENT_SHA=$(shasum -a 256 com.nexara.runtime.plist | awk '{print $1}')"
python3 -c "s=open('com.nexara.runtime.plist').read(); s=s.replace('<integer>5</integer>','<integer>10</integer>',1); open('com.nexara.runtime.plist','w').write(s)"
echo "UPGRADE_TI=$(grep -A1 ThrottleInterval com.nexara.runtime.plist | grep integer | tr -d ' ') SHA=$(shasum -a 256 com.nexara.runtime.plist | awk '{print $1}')"
launchctl bootout gui/$(id -u)/com.nexara.runtime 2>/dev/null
launchctl bootstrap gui/$(id -u) com.nexara.runtime.plist 2>/dev/null
sleep 6
curl -s -o /tmp/u.json http://127.0.0.1:8765/health
python3 -c "import json;d=json.load(open('/tmp/u.json'));print('UPGRADED health:',d.get('status'),'| pid:',d.get('pid'),'| provider:',d.get('provider'))"
curl -s -X POST -H "Content-Type: application/json" -d '{"title":"upgrade-verify"}' http://127.0.0.1:8765/api/conversations -o /tmp/uc.json
UCID=$(python3 -c "import json;print(json.load(open('/tmp/uc.json')).get('conversation_id'))")
curl -s -X POST -H "Content-Type: application/json" -d '{"content":"你好","execution_mode":"auto"}' "http://127.0.0.1:8765/api/conversations/$UCID/messages" -o /tmp/um.json
python3 -c "import json;d=json.load(open('/tmp/um.json'));m=d.get('assistant_message') or {};print('UPGRADED conv:',(m.get('metadata') or {}).get('provider'),'| reply:',str(m.get('content',''))[:40])"
cp -p com.nexara.runtime.plist.golden-20260821-015858 com.nexara.runtime.plist
echo "ROLLBACK_TI=$(grep -A1 ThrottleInterval com.nexara.runtime.plist | grep integer | tr -d ' ') SHA=$(shasum -a 256 com.nexara.runtime.plist | awk '{print $1}')"
launchctl bootout gui/$(id -u)/com.nexara.runtime 2>/dev/null
launchctl bootstrap gui/$(id -u) com.nexara.runtime.plist 2>/dev/null
sleep 6
curl -s -o /tmp/u2.json http://127.0.0.1:8765/health
python3 -c "import json;d=json.load(open('/tmp/u2.json'));print('RESTORED health:',d.get('status'),'| pid:',d.get('pid'))"
echo "RESTORED_SHA=$(shasum -a 256 com.nexara.runtime.plist | awk '{print $1}')"
