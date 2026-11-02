# Release

```sh
bash scripts/release/build.sh
bash scripts/release/verify.sh dist
```

Produces in `dist/`:

| File | Purpose |
|---|---|
| `nexara_prime-<version>-py3-none-any.whl` | installable package |
| `nexara-prime-<version>-image.tar.gz` | container image (`docker load < …`) |
| `SBOM.cdx.json` | CycloneDX 1.5 SBOM, one component per installed distribution |
| `SHA256SUMS` | checksums for every artifact above |

## Rules
- A release is the **directory**, not a git tag: without `SHA256SUMS` verified, it is not shipped.
- The image is tagged with the `pyproject.toml` version; bump it in the release commit.
- SBOM components come from `pip freeze` inside the image, so it describes what runs, not what was intended.
- Rollback: `docker load` the previous tarball and run it with the same `-v nexara-data:/data`.

## Known gaps
- No signing/attestation yet (`cosign` not in the pipeline).
- No reproducible-build check.
