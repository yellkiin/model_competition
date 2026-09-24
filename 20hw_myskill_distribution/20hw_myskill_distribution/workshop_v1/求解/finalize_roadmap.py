"""Fit the reviewed road map to the paper width and create inspectable QA views."""

import hashlib
import json
import sys
from pathlib import Path

import fitz
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "求解"
TOOLS = ROOT.parent / "华为杯_求解规范" / "tools"
sys.path.insert(0, str(TOOLS))
from roadmap_templates import contract_digest  # noqa: E402
from workspace_resources import dependencies  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    final = "--finalize" in sys.argv
    sidecar = DIR / "视觉计划.diagrams.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    diagram = next(d for d in data["diagrams"] if d["diagram_id"] == "GLOBAL-ROADMAP")
    src_path = DIR / "总体路线图_紧凑.pdf"
    dst_path = DIR / "总体路线图_论文宽.pdf"
    if not final:
        source = fitz.open(src_path)
        width = 160 * 72 / 25.4
        height = width * source[0].rect.height / source[0].rect.width
        target = fitz.open()
        page = target.new_page(width=width, height=height)
        page.show_pdf_page(page.rect, source, 0)
        target.save(dst_path)
        diagram["dependencies"] = [*diagram["dependencies"], "求解/总体路线图_紧凑.pdf", "求解/finalize_roadmap.py"]
        diagram["outputs"]["vector"] = "求解/总体路线图_论文宽.pdf"
        save_json(sidecar, data)
        selection = DIR / "总体路线图模板选型.json"
        rec = json.loads(selection.read_text(encoding="utf-8"))
        rec["diagram_contract_sha256"] = contract_digest(diagram)
        save_json(selection, rec)
        with Image.open(DIR / "总体路线图_紧凑.png") as im:
            original = im.convert("RGB")
            w, h = original.size
            original.save(DIR / "总体路线图_整体复核.png")
            box = [int(w * .05), int(h * .25), int(w * .95), int(h * .55)]
            original.crop(box).save(DIR / "总体路线图_局部复核.png")
            ImageOps.grayscale(original).convert("RGB").save(DIR / "总体路线图_灰阶复核.png")
        pdf = fitz.open(dst_path)
        pdf[0].get_pixmap(dpi=150, alpha=False).save(DIR / "总体路线图_PDF尺寸复核.png")
        print({"status": "READY_TO_REVIEW", "width_mm": pdf[0].rect.width * 25.4 / 72, "detail_box": box})
        return

    with Image.open(DIR / "总体路线图_紧凑.png") as im:
        w, h = im.size
    box = [int(w * .05), int(h * .25), int(w * .95), int(h * .55)]
    rows = [
        ("overall", "求解/总体路线图_整体复核.png", "四层彩带从题定输入贯穿三场景，连接顺序与箭头指向清楚，文字无裁切。"),
        ("detail", "求解/总体路线图_局部复核.png", "放大后第二层场景A的候选、输出和评估节点均与题面及实际代码一致。"),
        ("pdf_size", "求解/总体路线图_PDF尺寸复核.png", "以160毫米正文宽度和150 DPI重绘后，四层标题、节点标签及箭头仍可辨认。"),
        ("grayscale", "求解/总体路线图_灰阶复核.png", "灰阶下边框、方向箭头和各层标题仍有可辨的明度层次。"),
    ]
    views = []
    for kind, raw, observation in rows:
        view = {"kind": kind, "path": raw, "sha256": digest(ROOT / raw), "reviewed": True,
                "tool_ref": "本会话实际打开复核图像", "observation": observation}
        if kind == "detail":
            view["crop_box"] = box
        if kind == "pdf_size":
            view.update({"pdf_path": "求解/总体路线图_论文宽.pdf", "pdf_sha256": digest(dst_path),
                         "page_number": 1, "dpi": 150})
        views.append(view)
    expected = {diagram["source"], *diagram["dependencies"], *diagram["outputs"].values(),
                *(item["path"] for item in diagram["sources"]), diagram["template_selection_path"]}
    qa = {
        "status": "pass", "scientific_review": "逐格复核了题定输入、场景A独立Task、场景B同核复用和共享只读L2，箭头表示研究及评价先后，未填入尚未完成的数值。",
        "resource_dependencies": dependencies(ROOT, "codex", "structure"),
        "files": {raw: digest(ROOT / raw) for raw in sorted(expected)},
        "views": views,
        "native_resolution_reviews": [],
        "template_adaptation_review": {
            "status": "pass", "selection_sha256": digest(DIR / "总体路线图模板选型.json"),
            "style_observation": "保留四层横向彩带、白底卡片和逐层单向连接的模板视觉特征，压紧层间空白。",
            "truthfulness_observation": "四层分别对应输入审计和三个题定问题，全部任务节点有题面或正式求解代码依据。",
            "readability_observation": "按论文160毫米正文宽度复核后的矢量PDF文字及箭头可读，无文字溢出。",
            "tool_ref": "本会话实际打开整体、细节、灰阶和PDF版心图像"
        }
    }
    save_json(DIR / "总体路线图.qa.json", qa)
    diagram["status"] = "qa_pass"
    save_json(sidecar, data)
    print({"status": "QA_RECORDED", "views": len(views), "files": len(expected)})


if __name__ == "__main__":
    main()
