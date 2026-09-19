# Strict retrieval authorization (unreleased)

Private records must contain non-empty string student, institution, and category metadata. Missing, null, empty, or malformed values are denied. Existing valid scopes retain their category allowlists. This is an intentional breaking security change: repair ingestion metadata before upgrading; do not automatically classify missing metadata as public.

Shared documents must be explicitly tagged `classification: public` and contain neither student nor institution identity keys. The public classification is an ingestion trust boundary: only trusted ingestion administrators may apply it after reviewing the content. A public label does not override conflicting identity tags. Custom identity/category field names continue to apply.

Use an explicit authorization step immediately before prompt assembly. Treat metadata and scope supplied by an authenticated application as policy inputs; do not let model output or untrusted callers choose their own scope. These software controls do not themselves establish regulatory compliance.

## Verification

Run the ordinary tests and `pytest integration_tests` separately: legacy tests use module-level framework mocks. Real integration tests require installed SDKs and record model inputs locally without model API calls. No release or package publication occurs from these changes. Repository source versions can be ahead of GitHub/PyPI releases; install a reviewed commit when testing unreleased changes.

## Canonical package source

`haystack-ferpa-filter` is the canonical repository for the existing `ferpa-haystack` distribution and `haystack_integrations.components.filters.ferpa_filter` namespace. The legacy `ferpa-haystack` repository preserves history and code but no longer publishes. Do not install both checkouts in one environment. Review and release from the canonical repository only.

Multitenant serialization now retains the tenant authorization map, including categories and cross-institution basis; async execution uses the identical filter. Existing serialized configurations that omitted authorization maps still restore without grants, denying private records until configured.

## Authorization configuration validation (unreleased)

Single-tenant filters require non-empty string student and institution IDs; multitenant filters require a non-empty string student ID. Tenant authorization map keys must match the authorization record institution ID. Invalid configuration now raises `ValueError` during construction or deserialization rather than creating an ambiguous scope. Published package versions remain unchanged until a separately approved release.
