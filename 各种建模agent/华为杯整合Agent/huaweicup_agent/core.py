"""显式输入、内容哈希和依赖检查。哈希证明字节一致，不证明科学结论正确。"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def digest(path: Path, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class Workspace:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if not (self.root / "contract.json").is_file():
            raise ValueError("不是工作区；请先运行 init。")

    def path(self, name: str) -> Path:
        """拒绝绝对路径、目录穿越、Windows 驱动器和符号链接。"""
        if not name or "\\" in name or ":" in name:
            raise ValueError("非法工作区相对路径")
        rel = Path(name)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("路径必须位于工作区内")
        target = self.root / rel
        if any(p.is_symlink() for p in (target, *target.parents)):
            raise ValueError("工作区不接受符号链接")
        target.resolve().relative_to(self.root)
        return target

    def read(self, name: str) -> Any:
        return load(self.path(name))

    def write(self, name: str, value: Any) -> None:
        save(self.path(name), value)

    def inputs(self) -> list[str]:
        paths = ["problem.md", "contract.json"]
        for item in sorted(self.path("inputs").rglob("*")):
            name = item.relative_to(self.root).as_posix()
            self.path(name)
            if item.is_file():
                paths.append(name)
        return paths

    def seal(self) -> dict:
        """显式重封存不会把旧产物刷新为有效；其依赖仍指向旧哈希。"""
        hashes = {name: digest(self.path(name)) for name in self.inputs()}
        value = {"sealed_at": stamp(), "files": hashes}
        self.write("input_manifest.json", value)
        return value

    def input_errors(self) -> list[str]:
        if not self.path("input_manifest.json").exists():
            return ["尚未 seal 题面和输入"]
        frozen = self.read("input_manifest.json")["files"]
        current = {name: digest(self.path(name)) for name in self.inputs()}
        return [f"输入已变更/增删: {name}" for name in sorted(set(frozen) | set(current))
                if frozen.get(name) != current.get(name)]

    def record(self, name: str, dependencies: list[str], kind: str = "artifact") -> None:
        if name in dependencies:
            raise ValueError("产物不能依赖自身")
        path = self.path(name)
        if not path.is_file():
            raise ValueError(f"产物不存在: {name}")
        ledger = self.read("artifacts.json")
        ledger[name] = {"sha256": digest(path), "kind": kind, "created_at": stamp(),
                        "dependencies": {dep: digest(self.path(dep)) for dep in dependencies}}
        self.write("artifacts.json", ledger)

    def require_fresh(self, names: list[str]) -> None:
        errors = set(self.input_errors())
        ledger = self.read("artifacts.json")
        for name in names:
            if name not in ledger:
                errors.add(f"未登记产物: {name}")
            else:
                self._check(name, ledger[name], ledger, set(), errors)
        if errors:
            raise ValueError("; ".join(sorted(errors)))

    def artifact_errors(self) -> list[str]:
        ledger = self.read("artifacts.json")
        errors: set[str] = set()
        for name, entry in ledger.items():
            self._check(name, entry, ledger, set(), errors)
        return sorted(errors)

    def _check(self, name: str, entry: dict, ledger: dict,
               chain: set[str], errors: set[str]) -> None:
        if name in chain:
            errors.add(f"依赖循环: {name}")
            return
        path = self.path(name)
        if not path.is_file() or digest(path) != entry["sha256"]:
            errors.add(f"产物缺失或被改写: {name}")
        for dep, expected in entry["dependencies"].items():
            source = self.path(dep)
            if not source.is_file() or digest(source) != expected:
                errors.add(f"依赖过期: {name} <- {dep}")
            if dep in ledger:
                self._check(dep, ledger[dep], ledger, chain | {name}, errors)

    def snapshot(self) -> str:
        """人工签署绑定当前证据，审批文件本身不进入签署摘要。"""
        names = self.inputs() + ["sources.json", "claims.json", "ai_usage.json", "rules.json"]
        names += list(self.read("artifacts.json"))
        hashes = {name: digest(self.path(name)) for name in sorted(set(names))}
        return hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()


def initialize(root: str | Path, mode: str = "rehearsal") -> Workspace:
    target = Path(root)
    if mode not in {"rehearsal", "competition"}:
        raise ValueError("未知工作区模式")
    if target.exists() and any(target.iterdir()):
        raise ValueError("init 拒绝覆盖非空目录")
    target.mkdir(parents=True, exist_ok=True)
    for name in ("inputs", "notes", "code", "results", "figures", "paper", "build", "tasks"):
        (target / name).mkdir(exist_ok=True)
    save(target / "contract.json", {
        "schema_version": 1, "year": 2026, "mode": mode,
        "problem_id": "TBD", "tasks": [], "fixed_parameters": {},
        "decision_variables": {}, "constraints": [],
        "validation": {"split_strategy": "TBD", "metric": "TBD", "seed": 42},
        "budget": {"max_experiments": 20, "max_wall_seconds": 3600}})
    (target / "problem.md").write_text("请放入完整题面，保留所有条件和子问题。\n", encoding="utf-8")
    for name, value in {"artifacts.json": {}, "sources.json": [], "claims.json": [],
                        "ai_usage.json": [], "approvals.json": {},
                        "rules.json": {"year": 2026, "verified_by": "",
                                       "policy_file": "", "template_file": "",
                                       "checks": {}}}.items():
        save(target / name, value)
    return Workspace(target)


def validate_sources(sources: list[dict]) -> list[str]:
    errors, seen = [], set()
    if not isinstance(sources, list):
        return ["来源库必须为数组"]
    for s in sources:
        if not isinstance(s, dict):
            errors.append("来源卡必须为对象")
            continue
        key = str(s.get("id", ""))
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", key) or key in seen:
            errors.append(f"文献 ID 非法或重复: {key}")
        seen.add(key)
        if not s.get("title") or not str(s.get("url", "")).startswith("https://"):
            errors.append(f"文献缺少题名/HTTPS来源: {key}")
        if s.get("read_status") not in {"metadata", "abstract", "fulltext"}:
            errors.append(f"阅读状态非法: {key}")
        if s.get("read_status") != "metadata" and not s.get("locator"):
            errors.append(f"缺少页码/章节定位: {key}")
    return errors
