# Sandbox Enforcement Report
- MacOSSandboxBackend uses sandbox-exec with .sb profile
- No silent fallback to plain execution
- Capability flags: OS_SANDBOX_CAPABLE, OS_SANDBOX_ENFORCED, FULL_OS_ISOLATION_ACCEPTED
- Path validation blocks ../, absolute paths, symlinks, null bytes
- Command sanitization blocks shell metacharacters
- Process group kill on timeout
