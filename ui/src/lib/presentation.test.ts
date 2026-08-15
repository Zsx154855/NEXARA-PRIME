import { test } from "node:test";
import assert from "node:assert/strict";
import {
  sanitizeAssistantContent,
  isQaMission,
  filterProductMissions,
} from "./presentation.ts";

const MOCK_CONTENT = `DETERMINISTIC_MOCK_RESULT
Objective: QA-E2E-xyz 请执行一个演示使命
Context keys: intent, transcript
Decision: produce a bounded local report`;

test("conversation hides deterministic mock result in default presentation", () => {
  const output = sanitizeAssistantContent(MOCK_CONTENT);
  assert.ok(!output.includes("DETERMINISTIC_MOCK_RESULT"));
});

test("conversation hides context keys in default presentation", () => {
  const output = sanitizeAssistantContent(MOCK_CONTENT);
  assert.ok(!output.includes("Context keys"));
});

test("conversation hides internal decision in default presentation", () => {
  const output = sanitizeAssistantContent(MOCK_CONTENT);
  assert.ok(!output.includes("Decision"));
});

test("conversation hides internal objective line in default presentation", () => {
  const output = sanitizeAssistantContent(MOCK_CONTENT);
  assert.ok(!output.includes("Objective"));
});

test("normal user content passes through unchanged", () => {
  const normal = "今天天气很好，帮我总结一下这份文档。";
  assert.equal(sanitizeAssistantContent(normal), normal);
});

test("default missions exclude qa-e2e test missions", () => {
  const missions = [
    { mission_id: "mission_a", title: "QA-E2E-rhgecb 验证对话链路", state: "Approval" },
    { mission_id: "mission_b", title: "整理季度报告", state: "Completed" },
    { mission_id: "mission_c", title: "QA-VIS-rpneep 视觉测试", state: "Completed" },
  ];
  const product = filterProductMissions(missions);
  assert.equal(product.length, 1);
  assert.equal(product[0]?.mission_id, "mission_b");
});

test("qa mission detection matches e2e and visual prefixes only", () => {
  assert.equal(isQaMission("QA-E2E-rhgecb 验证对话链路"), true);
  assert.equal(isQaMission("QA-VIS-rpneep 视觉测试"), true);
  assert.equal(isQaMission("QA-GEO 超长文本验证"), true);
  assert.equal(isQaMission("整理季度报告"), false);
});

test("governance path preserves original content", () => {
  // presentation 层只做映射，原始数据不动：sanitize 返回占位但不修改输入
  const original = MOCK_CONTENT;
  sanitizeAssistantContent(original);
  assert.equal(original, MOCK_CONTENT);
});
