# SAFER editable architecture diagrams

Created 26 October 2026 from the current application architecture (`eea1e14`), the architecture-diagram plan and synthetic prototype captures.

## Start here

- **SAFER-v2-slide-fit.excalidraw** — L-shaped technical-slide composition, including two cropped prototype captures.
- **SAFER-v2-all-views.excalidraw** — all five views on one canvas, organized into named frames.
- **SAFER-v2-overview.excalidraw** — detailed application structure and lifecycle guide.
- **SAFER-v2-security-data-flow.excalidraw** — evidence provenance and sensitive-data boundaries.
- **SAFER-v2-oci-proposed-deployment.excalidraw** — proposed private Oracle deployment, explicitly not deployed.
- **SAFER-v2-ai-sequence.excalidraw** — guarded advisory-generation flow and fallback/error outcomes.

## Editing and presentation

Open a `.excalidraw` file in [Excalidraw](https://excalidraw.com/) using the editor's Open action or drag the file onto its canvas. All diagram labels, boxes and connectors are native elements. Related box/icon/text elements are grouped; enter a group or ungroup it to edit individual items. Architecture connectors are bound to their boxes. Sequence messages remain independently editable along their lifelines.

Logos and prototype captures are embedded image elements, so these files have no remote image dependencies. Images can be moved, resized and replaced; text inside a screenshot is part of the capture rather than editable diagram text. The two captures show evidence comparison and deadline/replacement panels from the same synthetic reviewer case.

Use the matching **SVG** for sharp slide insertion or the **PNG** for compatibility. Both are visual exports; edit the `.excalidraw` source and export again when changing content. PNGs are rendered at twice the design resolution. The contact sheet is a quick overview, not a presentation slide.

The slide-fit version is a standalone composition for the white content area of the technical slide. It does not modify an existing PowerPoint, add a team logo or claim exact measurements from an editable PPT template. Resize proportionally and inspect the final slide at presentation size.

## Status and interpretation

- Core review/lifecycle capabilities are implemented in the local synthetic application.
- OpenBao document encryption is shown as a local readiness-profile capability.
- Gemini integration exists but is **off by default**; external synthetic processing and live model evaluation remain gated.
- The bank exchange is a labelled simulator; recorded manual evidence is a separate source.
- Text extraction proposes values. OCR is not configured, and clean malware scans do not establish authenticity.
- Oracle is a proposed single-VM private-demo topology; account/region/capacity and deployment approvals remain unresolved. It is not an HA or deployed-production diagram.

The main view uses C4-inspired presentation notation; the security view is DFD-style. They are not strict formal UML/DFD models. The Mermaid file provides an additional text-editable AI sequence.

## Checks performed

Native JSON geometry, unique IDs, embedded file references, frame references and connector targets were checked. SVG/PNG exports were visually inspected. Text widths were checked in a local browser and overlong labels shortened. These checks do not constitute a security audit or a live cloud/provider test.

The native files were generated directly in Excalidraw's scene format; the checks above do not claim an interactive import test in the Excalidraw application.
