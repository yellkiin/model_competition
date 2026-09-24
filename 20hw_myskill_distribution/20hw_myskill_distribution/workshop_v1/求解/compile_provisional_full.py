"""Compile the provisional appendix paper with the verified TinyTeX PATH."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
env_result = json.loads((ROOT / "求解/环境检测.json").read_text(encoding="utf-8"))
exe = next(r["path"] for r in env_result["results"] if r["capability"] == "latex")
env = dict(os.environ, PATH=str(Path(exe).parent) + os.pathsep + os.environ.get("PATH", ""))
command = [exe, "-interaction=nonstopmode", "-halt-on-error", "-shell-escape",
           "-jobname=论文_provisional", "论文.tex"]
for index in range(2):
    run = subprocess.run(command, cwd=ROOT / "论文", env=env, capture_output=True,
                         text=True, encoding="utf-8", errors="replace", timeout=300)
    if run.returncode:
        lines = (ROOT / "论文/论文_provisional.log").read_text(encoding="utf-8", errors="replace").splitlines()
        print("run", index + 1, "failed", run.returncode)
        print("\n".join(line for line in lines if line.startswith("!") or "Error:" in line)[-3000:])
        raise SystemExit(run.returncode)
print("compiled")
