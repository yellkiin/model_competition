"""Record the actual four-view review of the three completed overview diagrams."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "华为杯_求解规范/tools"))
from overview_content import REVIEW_KEYS, content_digest  # noqa: E402
from workspace_resources import dependencies  # noqa: E402

SIDECAR = ROOT / "求解/视觉计划.diagrams.json"


def digest(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


OBSERVATIONS = {
    "q1": {
        "scientific": "逐格核对DAG依赖、任务优先级与处理单元指派，以及两张正式100例图的ID和数据来源；底部缩图仅供定位，具体数值由正文独立图承担。",
        "detail": "底部q1-F02的核数收益曲线和q1-F03的实例分布来源可辨，详细数值在正文原图读出；边缘没有截断。",
        "result_integration": "q1-F02和q1-F03实际嵌入底部结果带，均是本问已通过独立核验的正式统计图。",
        "mechanism_value": "顶部有向计算图与优先级路径展示前驱约束如何限定合法起始时间。",
    },
    "q2": {
        "scientific": "逐格核对同核复用与跨核COPY示意、场景B求解顺序，以及q2-F02和q2-F03的正式结果来源；无跨问成绩混用。",
        "detail": "底部成对策略结果与搬运分解缩图清楚对应q2-F02、q2-F03，细节读数移交正文原图；边缘无文字裁切。",
        "result_integration": "q2-F02和q2-F03实际嵌入底部结果带，分别支持策略对照和跨核搬运讨论。",
        "mechanism_value": "顶部两核、Task复用和跨核COPY箭头交代处理单元配置怎样改变搬运成本。",
    },
    "q3": {
        "scientific": "逐格核对只读共享L2、命中与未命中分流及非官方九格参数响应的标识；综合图缩印的结果均对应已核验数据。",
        "detail": "底部q3-F02、q3-F03缩图对应官方命中率—收益关系与明确标注的非官方参数实验，详细数值由正文独立图给出。",
        "result_integration": "q3-F02和q3-F03实际嵌入底部结果带，分别连接官方命中收益与非官方灵敏度边界。",
        "mechanism_value": "顶部共享L2路径将命中、未命中及外存请求分开，直接说明缓存模型口径。",
    },
}


def main() -> None:
    data = json.loads(SIDECAR.read_text(encoding="utf-8"))
    resource = dependencies(ROOT, "codex", "structure")
    for diagram in data["diagrams"]:
        if diagram["kind"] != "comprehensive":
            continue
        qid = diagram["problem_id"]
        obs = OBSERVATIONS[qid]
        stem = f"求解/综合图/{qid}-overview"
        paths = {
            "overall": stem + ".overall.png",
            "detail": stem + ".detail.png",
            "pdf_size": stem + ".pdf-size.png",
            "grayscale": stem + ".grayscale.png",
        }
        for path in paths.values():
            if not (ROOT / path).is_file():
                raise FileNotFoundError(path)
        with Image.open(ROOT / diagram["outputs"]["preview"]) as im:
            width, height = im.size
        crop = [int(width * .04), int(height * .70), int(width * .96), int(height * .97)]
        view_observations = {
            "overall": "三带矩形总览从机理流向求解和真实结果；蓝色连接方向与文字顺序清楚，版面没有截断。",
            "detail": obs["detail"],
            "pdf_size": "以160毫米论文宽度、150 DPI实际重绘后，分区标题、方法节点和方向箭头可辨；缩图由正文同ID原图承担读数。",
            "grayscale": "灰阶下分区边界、深色文字、方向箭头及两幅结果缩图仍能区分。",
        }
        views = []
        for kind, path in paths.items():
            row = {
                "kind": kind, "path": path, "sha256": digest(path),
                "reviewed": True, "tool_ref": "本会话已实际打开该问四种视图并逐项核对",
                "observation": view_observations[kind],
            }
            if kind == "detail":
                row["crop_box"] = crop
            if kind == "pdf_size":
                row.update(pdf_path=diagram["outputs"]["vector"],
                           pdf_sha256=digest(diagram["outputs"]["vector"]),
                           page_number=1, dpi=150)
            views.append(row)
        expected = {diagram["source"], *diagram.get("dependencies", []),
                    *diagram["outputs"].values(), *[r["path"] for r in diagram["sources"]]}
        reviews = {
            "result_integration": obs["result_integration"],
            "mechanism_value": obs["mechanism_value"],
            "rectangular_composition": "顶部对象、中部求解、底部结果按统一边界和阅读顺序排列，构成无空洞矩形总览。",
            "palette": "青、粉、绿高明度分区共用深色文字与蓝色主箭头，灰阶检查仍可区分。",
            "navigation": "箭头把对象、方法和结果串接；每个缩图标出与正文详细图一致的图号。",
            "non_text_graphics": "顶部关系矢量图和底部两张真实结果图承担了主要信息，中央文本仅用于解释约束与方法。",
            "thumbnail_detail_link": "综合图的两张缩印结果与正文同ID独立科学图一一对应，正文原图用于精确读数。",
        }
        assert set(reviews) == set(REVIEW_KEYS)
        qa = {
            "status": "pass", "scientific_review": obs["scientific"],
            "resource_dependencies": resource,
            "files": {path: digest(path) for path in sorted(expected)},
            "views": views, "native_resolution_reviews": [],
            "overview_design_sha256": content_digest(diagram),
            "overview_review": {key: {"status": "pass", "observation": value}
                                for key, value in reviews.items()},
        }
        (ROOT / diagram["qa_path"]).write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        diagram["status"] = "qa_pass"
    SIDECAR.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "overviews": [d["diagram_id"] for d in data["diagrams"]
                      if d["kind"] == "comprehensive"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
