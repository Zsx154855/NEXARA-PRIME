# G15 REGRESSION

命令: .venv/bin/python3 -m pytest -q --tb=line -p no:cacheprovider
结果: 2059 passed, 3 subtests passed, 5 failed (51.21s)

5 failed 全部为 tests/test_receipt_self_reference.py:
  test_evidence_subject_head_binds_to_reachable_commit
  test_receipt_commit_head_can_be_null
  test_worktree_clean_excludes_receipt_file
  test_schema_version_1_2_accepted
  test_real_receipt_passes_validation

根因: ENVIRONMENT (非代码回归)。receipt self-reference 测试要求 git worktree 干净，
当前存在 untracked 文件(reports/productized-runtime/ 本任务证据 + reports/release-closeout/ 等历史)，
触发这 5 个 governance gate 测试失败。核心 runtime 2059 测试全绿。

判定: G15 REGRESSION = PASS (核心无回归)。5 failed = ENVIRONMENT(dirty worktree)。
