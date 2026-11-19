# SAFER unified architecture — real logos edition

One architecture image, with editable text, shapes and connections in Excalidraw. Product logos and the screenshot are embedded images and can be moved, resized or replaced. All image data is included in the .excalidraw file; no internet connection is required to display its assets.

## Files

- PNG: 6000 × 3200 pixels, white background, suitable for presentation import.
- SVG: scalable image with embedded logos and screenshot.
- Excalidraw: open using Excalidraw → Open → select the file.
- Preview PNG: 2400 × 1280 pixels.

## Diagram scope

The layout represents the existing SAFER modular monolith and its supporting local services. OCI is a proposed deployment. Gemini is optional and disabled by default. Bank simulation and recorded manual evidence remain distinct from an authorized live bank integration. The screenshot is a crop of an actual local synthetic demonstration, not a mockup or real institution data.

## Image provenance

The existing logo collection supplies React, TypeScript, Vite, FastAPI, PostgreSQL, Keycloak, Python, SeaweedFS, ClamAV, Docker, GitHub Actions, Authlib and Pydantic. Its original source manifest is copied alongside this document. Some assets in that collection are recognized logo copies from Devicon; others are directly from project websites or repositories.

New assets were retrieved from official project websites/repositories or vendor asset hosts:

- [nginx.svg](https://nginx.org/img/nginx_logo.svg)
- [openbao.svg](https://raw.githubusercontent.com/openbao/artwork/main/color/openbao-text-color.svg)
- [valkey.svg](https://valkey.io/img/valkey-horizontal.svg)
- [celery.png](https://docs.celeryq.dev/en/stable/_static/celery_512.png)
- [git.svg](https://git-scm.com/images/logos/downloads/Git-Icon-1788C.svg)
- [github.png](https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png)
- [oci-toolkit.zip](https://docs.oracle.com/en-us/iaas/Content/Resources/Assets/OCI-Style-Guide-for-Drawio.zip)
- [gemini.svg](https://www.gstatic.com/lamda/images/gemini_sparkle_aurora_33f86dc0c0257da337c63.svg)
- [mailpit.svg](https://raw.githubusercontent.com/axllent/mailpit/develop/server/ui/favicon.svg)
- [oci-compute.svg](https://docs.oracle.com/en-us/iaas/Content/General/Reference/graphicsfordiagrams.htm)

The OCI VM service icon was converted from the official OCI Architecture Diagram Toolkit draw.io library, retaining its artwork. It is a service symbol, not the Oracle corporate wordmark.

The Git logo is by Jason Long and licensed under [Creative Commons Attribution 3.0](https://creativecommons.org/licenses/by/3.0/), as stated on the [Git logo page](https://git-scm.com/community/logos). Logos remain the trademarks of their owners; their inclusion identifies technologies and does not imply endorsement.

Generic Lucide symbols remain for people, business functions, access controls and bank evidence because these are concepts rather than software brands. Lucide is distributed under the ISC license.

Prototype image source: `safer/apps/web/test-results/review-case.png`, cropped to the claim/evidence comparison and audit trail. Synthetic demonstration only.

## Editing

Open the .excalidraw file to edit individual labels, boxes and arrows. Logos are embedded image objects; original artwork is retained in the workspace's `real-logo-assets` and `SAFER-tech-stack-logos` folders. The unified diagram is not one flattened image inside the editable file.
