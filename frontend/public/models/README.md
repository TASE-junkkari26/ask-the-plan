# FZK-Haus demonstration model

`fzk-haus.frag` is a browser-viewer derivative of
`kit-fzk-haus_ac20-fzk-haus.ifc` (FZK-Haus / Simple Phantasy Building) supplied in
the Junction dataset. The original IFC is not modified or bundled here.

Source and attribution: **Institute for Automation and Applied Informatics (IAI),
Karlsruhe Institute of Technology (KIT)** —
[KIT IFC Examples](https://www.ifcwiki.org/index.php?title=KIT_IFC_Examples&oldid=552).
The supplied dataset's license inventory describes KIT models as “for unrestricted
use” and assigns `LicenseRef-KIT-unrestricted`, with the above attribution.

The derivative contains geometry/properties converted with That Open's IFC importer.
Its [manifest](fzk-haus.json) records the original file's SHA-256, original byte
size, converter/configuration identity, source URL, attribution, and license.
It is a real model for viewing and inspection; it has no prepared QA answers.

Regenerate from the repository root with
`npm --prefix frontend run prepare:ifc-demo`. The checked-in artifact remains a
viewer fixture; the application library shows imports only, and normal startup
does not require the dataset. Dependency licenses remain those of
That Open Components/Fragments (MIT), Three.js (MIT), camera-controls (MIT), and
web-ifc (MPL-2.0); the runtime preparation copies web-ifc's license beside its WASM.
