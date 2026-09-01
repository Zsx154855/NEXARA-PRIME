/**
 * 白话 → 专业提示词（确定性转换，无模型调用）。
 * 将自然语言输入整理为 角色 / 背景 / 任务目标 / 约束 / 输出要求 的结构化 Prompt，
 * 参考 Qoder 的提示词组织方式：角色先行、目标明确、约束可执行、输出可验收。
 */

export interface ProfessionalPrompt {
  role: string;
  background: string;
  goal: string;
  constraints: string[];
  output: string;
}

const DOMAIN_RULES: { match: RegExp; role: string; output: string }[] = [
  {
    match: /(代码|程序|bug|修|开发|实现|函数|接口|api|脚本|重构)/i,
    role: "资深软件工程师（TypeScript/全栈）",
    output: "给出可运行的关键代码与实现说明；指出边界与潜在风险。",
  },
  {
    match: /(写|文章|文案|报告|总结|改写|润色|翻译)/,
    role: "资深内容专家",
    output: "输出结构清晰、可直接使用的成稿；标注可复核的事实来源。",
  },
  {
    match: /(分析|调研|研究|对比|评估|趋势)/,
    role: "资深分析师",
    output: "给出结论先行、论据分层的分析报告；注明数据/证据出处。",
  },
  {
    match: /(计划|项目|方案|规划|排期|风险)/,
    role: "资深项目经理",
    output: "输出分阶段可执行的方案与检查清单；标注依赖与风险。",
  },
];

const CONSTRAINT_HINTS = /(不要|不能|禁止|必须|务必|确保|注意|限制|尽量|优先|要求|避免|只|范围|截止|<=|>=)/;

const DEFAULT_ROLE = "领域专家";
const DEFAULT_OUTPUT = "给出清晰、结构化、可直接使用的结果；如有不确定之处如实说明。";

function detectRule(text: string): { role: string; output: string } {
  for (const rule of DOMAIN_RULES) {
    if (rule.match.test(text)) {
      return { role: rule.role, output: rule.output };
    }
  }
  return { role: DEFAULT_ROLE, output: DEFAULT_OUTPUT };
}

/** 按句读切分（句号/逗号），便于从句级提取约束。 */
function splitClauses(text: string): string[] {
  return text
    .split(/[。！？!?；;\n，,]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export function toProfessionalPrompt(raw: string): ProfessionalPrompt {
  const text = raw.trim();
  const { role, output } = detectRule(text);
  const clauses = splitClauses(text);
  const constraints = clauses.filter((c) => CONSTRAINT_HINTS.test(c));
  const backgroundClauses = clauses.filter((c) => !constraints.includes(c));
  const background = backgroundClauses.join("，").slice(0, 400);
  return {
    role,
    background: background || "（补充需求背景，便于精准执行）",
    goal: text.slice(0, 600),
    constraints: constraints.length > 0 ? constraints : ["按专业标准执行并如实报告结果"],
    output,
  };
}

export function toPromptText(p: ProfessionalPrompt): string {
  return [
    "你是" + p.role + "。",
    "",
    "## 背景",
    p.background,
    "",
    "## 任务目标",
    p.goal,
    "",
    "## 约束",
    ...p.constraints.map((c, i) => `${i + 1}. ${c}`),
    "",
    "## 输出要求",
    p.output,
  ].join("\n");
}

/** 供 UI 展示的结构化 JSON 视图（可选）。 */
export function toPromptOutline(p: ProfessionalPrompt): Array<[string, string]> {
  return [
    ["角色", p.role],
    ["背景", p.background],
    ["任务目标", p.goal],
    ["约束", p.constraints.join("；")],
    ["输出要求", p.output],
  ];
}
