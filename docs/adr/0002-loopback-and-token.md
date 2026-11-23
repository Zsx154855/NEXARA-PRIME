# ADR 0002 — Local-first control plane

Status: accepted (2026-11-02)

## Context
42 API routes had no authentication. Binding `0.0.0.0` would expose mission
creation, approval and execution to the network.

## Decision
- Default host is loopback.
- Binding a non-loopback host without `NEXARA_API_TOKEN` is a startup error.
- With a token, every route except `/health` requires `Authorization: Bearer`.

## Consequences
Local single-owner use needs no token; remote exposure requires an explicit
secret. There is no user model, no rotation, no rate limiting — documented as
out of scope until a multi-user gate exists.
