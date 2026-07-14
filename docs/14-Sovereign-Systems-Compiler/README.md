# NEXARA Sovereign Systems Compiler

SSC turns one strict, machine-readable Sovereign System IR into deterministic contracts, policy projections, adversarial-test definitions, architecture metadata, documentation, and a SHA-256 build manifest.

## Constitutional baseline

Every accepted IR preserves five non-disableable properties:

- mission-first execution;
- verified evidence for consequential state changes;
- reversibility by default;
- explicit human authority;
- deterministic builds.

Rules and generated tests are linked bidirectionally. Every rule must bind happy, negative, boundary, replay, mutation, and rollback tests. Unknown, orphaned, duplicate, or incompletely tested rules fail validation. Every build must include the evidence target.

## Commands

```bash
nexara ssc validate examples/ssc/product_reality.system.json
nexara ssc compile examples/ssc/product_reality.system.json --output build/product_reality
nexara ssc verify build/product_reality
```

Compilation refuses a non-empty destination so generated output cannot silently overwrite human-owned files. The compiler writes into a staging directory and atomically publishes the completed build.

## Deterministic evidence

`build-manifest.json` binds:

- compiler version;
- system identity and version;
- canonical IR SHA-256;
- every generated artifact path, byte length, and SHA-256;
- one build SHA-256 over the complete ordered artifact ledger.

The same valid IR and compiler version produce byte-for-byte identical output.
Verification rejects missing, unexpected, modified, or symlinked artifacts and succeeds only when the complete build is exactly reproducible by the declared compiler version.
