"""通用工具：随机种子、日志、结果落盘。

实验要求「固定随机数种子，确保实验结果可复现」，因此所有涉及随机性的环节
（数据划分、模型初始化、MLP 权重初始化）都统一从这里取种子。
"""

from __future__ import annotations

import json
import logging
import os
import random
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

# ----------------------------------------------------------------------------
# 项目路径（全部使用相对项目根目录的路径，避免绝对路径）
# ----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
METRICS_DIR = RESULTS_DIR / "metrics"
LOGS_DIR = RESULTS_DIR / "logs"
REPORT_DIR = PROJECT_ROOT / "report"

# 全局随机种子：助教可据此复现全部实验
SEED = 42


def set_seed(seed: int = SEED) -> None:
    """固定所有随机源，保证实验可复现。"""
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)


def ensure_dirs() -> None:
    """确保输出目录存在。"""
    for d in (DATA_DIR, RESULTS_DIR, FIGURES_DIR, METRICS_DIR, LOGS_DIR, REPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)


def get_logger(name: str = "exp1", log_file: Path | None = None) -> logging.Logger:
    """同时输出到控制台与日志文件，便于保存运行过程。"""
    logger = logging.getLogger(name)
    if logger.handlers:  # 避免重复添加 handler
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S")

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    logger.addHandler(stream)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


def save_json(obj, path: Path) -> None:
    """保存 JSON（numpy 类型自动转换）。"""
    path.parent.mkdir(parents=True, exist_ok=True)

    def _default(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return round(float(o), 6)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, Path):
            return str(o)
        raise TypeError(f"无法序列化: {type(o)}")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=_default)


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")
