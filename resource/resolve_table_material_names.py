"""Resolve only the mission-table material and slot hashes from pinned unit records."""

import hashlib
import json
from pathlib import Path
import struct
import urllib.request

from inspect_hologram import murmur64
from resolve_hologram_names import URL


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "analysis/stock-table-units-24735202"
OUT = ROOT / "analysis/table-material-names-24735202.json"
DICTIONARY_SHA = "33cc674d9fe278ead021761c41a20f4f6bcf61066e045e114755202d99d17d35"


def main():
    if OUT.exists():
        raise ValueError("Dictionary research output exists")
    pinned = json.loads((INPUT / "provenance.json").read_text())
    tokens = {}
    slots = {}
    for item in pinned["resources"]:
        raw = (INPUT / item["record"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != item["record_sha256"]:
            raise ValueError("Table unit drift")
        for position in range(len(raw) - min(4096, len(raw)), len(raw) - 7):
            name, = struct.unpack_from("<Q", raw, position)
            if name in (0x8444EBA9758F6C3E, 0xC8D2ECAADF3F01D2, 0x699F6E8D07891A10,
                        0x76417C9EFD8C575F, 0xC15C78699B09E74D, 0xC56CA949883914F8,
                        0xEFA39C1B6ED1CE92, 0x2148EBBCD6136849, 0x5CAAD4888B29504D,
                        0xF8773EE4B041DCBA, 0xC9E8EB80644AF7DD, 0x3A68AED43DFD8B93,
                        0x6ABEE6E5878630E5):
                tokens.setdefault(name, []).append(item["name"])
                slot, = struct.unpack_from("<I", raw, position - 4)
                slots.setdefault(slot, []).append(item["name"])
    digest = hashlib.sha256()
    found = {key: [] for key in tokens}
    named_slots = {key: [] for key in slots}
    with urllib.request.urlopen(URL, timeout=35) as source:
        for line in source:
            digest.update(line)
            text = line.strip().decode("utf-8", errors="replace")
            if not text:
                continue
            value = murmur64(text)
            if value in found:
                found[value].append(text)
            if value >> 32 in named_slots:
                named_slots[value >> 32].append(text)
    if digest.hexdigest() != DICTIONARY_SHA or len(tokens) != 13:
        raise ValueError("Dictionary or table identities changed")
    entries = [{"hash": f"{key:016x}", "names": found[key],
                "unit_references": sorted(set(tokens[key]))} for key in sorted(tokens)]
    output = {"dictionary_sha256": DICTIONARY_SHA, "materials": entries,
              "slot_names": [{"hash32": f"{key:08x}", "names": named_slots[key]}
                             for key in sorted(slots)]}
    OUT.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
