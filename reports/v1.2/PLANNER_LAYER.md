# V1.2 PHASE 1 — AGENT PLANNING LAYER (Acceptance)

## Object Contract
- Goal: id/user_intent/objective/constraints/success_criteria/priority/deadline
- Plan: id/goal_id/steps/dependencies/risk/estimated_cost/estimated_time
- PlanStep: id/description/kind(tool|agent|verification)/dependencies/estimated_cost
- TaskGraph: goal_id/nodes(TaskNode: id/name/kind/dependencies) + as_adjacency()

## Architecture Evidence
- src/nexara_prime/intelligence/planner/contracts.py (对象定义)
- src/nexara_prime/intelligence/planner/planner.py (Planner Interface: understand→decompose→build_graph→to_mission→plan_mission→run_mission→plan_and_execute)
- 通过 HTTP 桥接 V1.1 Mission API, 零 Runtime Core 修改

## Test Evidence (真实 Runtime)
- Goal: goal_fe8cae4a2a6a (objective 提取 + success_criteria)
- Plan: plan_762322ccc576 (3 步骤 + 依赖链 step2→step1, step3→step2)
- TaskGraph: 3 nodes, goal_id match=True
- to_mission: mission_e676fe0e9b2b (真实 V1.1 POST /api/missions)
- plan→approve→run: Completed (真实 deepseek 执行)
- FINAL: Completed, evidence=16

## Acceptance Gate
PLANNER = PASS
GOAL_PLAN_MISSION_MAPPING = PASS
V1.1_DRIFT = 0 (src_mod=6 未变, intelligence/ 为新增 untracked)
P0=0 P1=0 P2=0
