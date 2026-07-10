---
id: DOC-FRONTMATTER-SCHEMA
title: Document Frontmatter Schema
type: data-contract
status: canonical
owner: human
source_of_truth: git
runtime_effect: indirect
created_at: 2026-07-11
updated_at: 2026-07-11
supersedes: []
related: []
tags: [data-contract, knowledge-fabric]
---
# Document Frontmatter Schema

权威文档必须包含：

```yaml
id: UNIQUE-ID
title: Human readable title
type: product | architecture | policy | decision | mission | evidence-index | template | generated
status: draft | review | approved | canonical | superseded | archived
owner: human | hermes | named-agent
source_of_truth: git | runtime | evidence
runtime_effect: none | indirect | policy
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
supersedes: []
related: []
tags: []
```

`generated` 内容必须放在 `_generated/`，`draft` 内容可以放在 `_inbox/`；二者不得被索引为 Canonical。
