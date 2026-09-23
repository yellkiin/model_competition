"""从仓库根目录调用整合工作台；不安装或启动第三方 Agent 服务。"""
from pathlib import Path
import sys

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "各种建模agent" / "华为杯整合Agent"
sys.path.insert(0, str(PACKAGE_ROOT))
from huaweicup_agent.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
