# Chief Brain Runtime Authority

## Authority

| 职责 | 权威实现 |
|------|----------|
| Mission Creation | `NexaraRuntime.create_mission()` |
| Mission State | `NexaraRuntime._advance()` → `MissionStateMachine` |
| Approval | `NexaraRuntime.approve_mission()` |
| Resume | `NexaraRuntime.resume()` (含崩溃恢复) |
| Inspection | `NexaraRuntime.inspect_mission()` |
| Finalization | `NexaraRuntime._completion_gate()` |
| Recovery | `DurableRecovery` + `resume()` crash path |

## Parallel Runtime: NONE

不存在第二套 Chief Brain Runtime、Supervisor 或平行编排器。
