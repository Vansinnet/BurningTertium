"""Report only hub sublevels and target-specific strings from the pinned level record."""

import hashlib
import json
from pathlib import Path
import re


OUT = Path(__file__).resolve().parents[1] / "analysis" / "stock-mourningstar-24735202"
report = json.loads((OUT / "provenance.json").read_text())
raw = (OUT / "mourningstar.level.record").read_bytes()
if hashlib.sha256(raw).hexdigest() != report["resource_sha256"]:
    raise ValueError("Stock record differs from recorded extraction")

strings = [(match.start(), match.group().decode("ascii"))
           for match in re.finditer(rb"[ -~]{8,256}", raw)]
level_paths = [(offset, text) for offset, text in strings
               if text.startswith("content/environment/artsets/imperial/hub/")]
target_strings = [(offset, text) for offset, text in strings
                  if any(term in text.lower() for term in
                         ("hologram", "mission_board", "mission_table", "map_table", "tertium"))]
print(json.dumps({"hub_asset_paths": level_paths[:35], "hub_asset_total": len(level_paths),
                  "target_strings": target_strings[:50], "target_total": len(target_strings)}, indent=2))
