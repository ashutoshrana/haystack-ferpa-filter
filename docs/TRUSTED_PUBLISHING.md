# PyPI trusted publishing

The release workflow builds and validates the tagged commit without publishing permission. A separate `publish` job downloads that run's artifact by ID, checks its SHA-256 manifest, then uses GitHub OIDC to publish the exact distributions and PyPI attestations. It never checks out or builds application code. There is no API-token fallback.

## Required account setup before a release

An authorized owner of the **existing PyPI project `ferpa-haystack`** must open its Publishing settings and add a GitHub trusted publisher with these exact values:

| Setting | Value |
|---|---|
| PyPI project | `ferpa-haystack` |
| GitHub owner | `ashutoshrana` |
| Repository | `haystack-ferpa-filter` |
| Workflow filename | `release.yml` |
| GitHub environment | `pypi` |

Create or verify the matching `pypi` environment in the GitHub repository, including the intended tag/protection rules. The PyPI project name differs from the GitHub repository name. Register `release.yml`, not its full `.github/workflows/` path. Confirm these settings before pushing a release tag; adding workflow YAML alone does not configure PyPI trust. Account configuration cannot be inferred from public package metadata.

See [PyPI's registration instructions](https://docs.pypi.org/trusted-publishers/adding-a-publisher/). This change does not establish that account setup has been completed. Publishing remains blocked until it is verified.

## Release checks

Use a new release version and its matching `v` tag after the intended commit has passed CI. The workflow verifies checkout/tag identity, source/package identity, unit and integration tests, wheel/sdist metadata, isolated wheel imports and dependency consistency. It uploads only those verified distributions and a checksum manifest to the publish job. Only that job receives `id-token: write`.

The pinned PyPA action generates attestations using the same OIDC identity used for publication. No username/password is supplied. If trust is missing or mismatched, fix the publisher configuration; do not add a token fallback or disable attestations. Keep artifact validation failures blocking publication. Existing release files are not overwritten or retroactively attested by this change. [Official attestation production guidance](https://docs.pypi.org/attestations/producing-attestations/).

## Independently verify the published files

Install the [PyPI attestation verifier](https://docs.pypi.org/attestations/consuming-attestations/) in a separate verification environment:

```sh
python -m pip install pypi-attestations
```

For both the wheel and source distribution, obtain its exact `files.pythonhosted.org` URL from that release's PyPI JSON metadata. Set `ARTIFACT_URL` to that URL and run:

```sh
python -m pypi_attestations verify pypi \
  --repository https://github.com/ashutoshrana/haystack-ferpa-filter \
  "$ARTIFACT_URL"
```

Require successful cryptographic verification for **both files**, matching the expected repository. Inspect the associated provenance and verified signing identity against workflow `release.yml`, environment `pypi`, and the intended release tag/commit; retain the verifier output and artifact hashes with release validation records. A provenance endpoint returning HTTP 200 or a matching checksum alone is insufficient. Provenance attests publication identity; it does not certify application correctness or FERPA compliance.

After an OIDC release and independent verification succeed, an authorized owner may retire the obsolete publishing token if no other workflow uses it. This workflow neither reads nor deletes that secret.
