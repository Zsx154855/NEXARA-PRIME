# G11 ROLLBACK (真实验证)

流程: golden 备份 → 破坏 → 回滚 → 恢复

1. golden 备份: cp com.nexara.runtime.plist → .golden-20260821-015858
   golden SHA = d92fafbf... = 当前 SHA (一致 ✓)
2. 破坏: ThrottleInterval 5→99 (patch)
   破坏版 SHA = 2915440afc6f36fd5fba77d6ff66e1fd4fb96da8ff72501356e0a3cfdf59ed97 (已变)
3. 回滚: cp .golden → plist
   恢复版 SHA = d92fafbf... (恢复 golden ✓)
4. 恢复: bootstrap → runtime PID 16488 (0) + health ok/provider=deepseek/db=ok
5. 校验: diff golden vs plist = IDENTICAL ✓ | ThrottleInterval 恢复为 5

判定: G11 ROLLBACK = PASS (回滚机制真实验证, 非仅脚本存在)
