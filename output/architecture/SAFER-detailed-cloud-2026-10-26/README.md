# SAFER detailed architecture

Prepared 26 October 2026 from the current project documentation and container configuration.

The diagram maps the implemented local synthetic application onto the proposed single-VM OCI topology. It does not assert that cloud resources have been deployed. Solid connections describe application relationships, not a complete firewall allowlist. Dashed connections identify proposed or disabled external paths. The cloud boundary is itself proposed. Gemini is implemented but disabled by default. Mailpit and the bank simulator do not deliver real email or verify real bank records. Scanned documents require manual entry; OCR is not configured.

Self-hosted PostgreSQL, SeaweedFS, OpenBao, Keycloak, Valkey and Celery are not managed Oracle services. Proposed OCI components comprise Compute, VCN/security controls, persistent volumes, IAM/cost controls and private Object Storage backups. Keycloak local identity storage is Stage A; a separate PostgreSQL identity DB is a later migration. Full-system recovery and production acceptance remain unproven.

## Sources
- `safer/README.md`
- `safer/compose.yaml`, `safer/compose.containers.yaml`
- `safer/docs/ARCHITECTURE.md`
- `safer/docs/DEPLOYMENT.md`
- `safer/docs/design/OCI-ALWAYS-FREE-SCALING-PLAN.md`
- `safer/docs/design/LLM-INTEGRATION.md`

## Original internet assets
Existing downloaded vendor/project assets were embedded unchanged, preserving aspect ratio. Sources are retained in `sources.json` and `stack-logo-provenance.json`. OCI service symbols come from the official Oracle diagram toolkit: https://docs.oracle.com/en-us/iaas/Content/General/Reference/graphicsfordiagrams.htm . OpenBao branding: https://openbao.org/community/policies/brand/ . Some stack logos were distributed through Devicon; others are from official project sites. Trademark ownership remains with each vendor. No AI-generated logos or decorative stock photographs were used.

The SVG is self-contained and editable as vector artwork. The PNG is for presentation use.
