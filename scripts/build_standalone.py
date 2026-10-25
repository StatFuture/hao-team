"""Publish the team site at its independent repository root."""
import json
from build import ROOT
from build_v2 import build_v2
if __name__ == "__main__":
    result = build_v2(dest=ROOT / "_site")
    result["path"] = "/"
    (ROOT / "_site/.nojekyll").write_text("")
    print(json.dumps(result, ensure_ascii=False))
