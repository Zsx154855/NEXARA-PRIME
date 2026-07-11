# NEXARA-PRIME Extension Manifest

## What

Drop a directory in `extensions/` with a `manifest.json`. NEXARA auto-discovers and loads it.

## manifest.json Schema

```json
{
  "name": "my-extension",
  "version": "1.0.0",
  "description": "What this extension does",
  "author": "you",
  "entry": "extension.py",
  "tools": ["tool_name"],
  "capabilities": ["capability_name"],
  "risk_level": "R0|R1",
  "requires_approval": false
}
```

## Extension Types

| Type | Risk | Auto-Load? | Example |
|------|------|-----------|---------|
| **Tool** | R0-R1 | Yes | Custom tool implementation |
| **Capability** | R0-R1 | Yes | New capability registration |
| **Connector** | R2 | Approval Required | External service connector |
| **Sandbox** | R4 | BLOCKED | Never auto-load R4 extensions |

## Example: Hello World Tool

```
extensions/
└── hello-world/
    ├── manifest.json
    └── extension.py
```

```json
{
  "name": "hello-world",
  "version": "1.0.0",
  "description": "A hello world example extension",
  "author": "you",
  "entry": "extension.py",
  "tools": ["hello_world"],
  "capabilities": [],
  "risk_level": "R1",
  "requires_approval": false
}
```

```python
# extension.py
def hello_world(name: str = "World") -> str:
    """A hello world tool."""
    return f"Hello, {name}!"
```

## Security: R0-R4 Policy Enforcement

- R0-R1 extensions: auto-discovered and loaded
- R2 extensions: discovered but require user approval before loading
- R3 extensions: discovered but require double approval
- R4 extensions: discovered but NEVER loaded automatically
- All extensions run in the same sandbox as the core runtime
- Extension loading publishes `governance.extension.loaded` events
