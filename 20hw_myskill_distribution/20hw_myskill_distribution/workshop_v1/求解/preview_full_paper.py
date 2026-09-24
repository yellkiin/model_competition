"""Prepare a provisional full paper; the formal generator will overwrite it."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "华为杯_论文规范模板/tools"))
from build_latex import build_main, copy_assets, load_manifest

manifest = load_manifest(ROOT / "论文/论文输入.json")
main, inputs = build_main(manifest, ROOT / "论文", include_appendix=True)
copy_assets(ROOT.parent / "华为杯_论文规范模板", ROOT / "论文", include_appendix=True)
(ROOT / "论文/论文.tex").write_text(main, encoding="utf-8")
(ROOT / "论文/论文.inputs.json").write_text(json.dumps({
    "main": "论文.tex", "inputs": inputs, "title": manifest["title"],
    "appendix_manifest": "../求解/附录清单.json", "requires_shell_escape": True,
    "pygments_style": "lovelace", "pygments_palette": "appendix_academic_light",
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(len(inputs))
