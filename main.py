"""实验一 · 文本分类 —— 统一入口。

用法：
    python main.py                      # 跑完整实验（推荐）
    python main.py --stage eda          # 只做数据探索
    python main.py --stage preprocess   # 只做预处理消融
    python main.py --stage features     # 只做特征消融
    python main.py --stage tune         # 只做模型调参
    python main.py --stage final        # 锁定方案 + 生成 predictions.csv
    python main.py --val-size 0.2 --seed 42
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# 允许以 `python main.py` 直接运行时找到 src 包
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import data as data_mod
from src import experiment as exp
from src import features as feat_mod
from src import models as model_mod
from src import preprocess as pp
from src.utils import METRICS_DIR, SEED, ensure_dirs, get_logger, save_json, timestamp

# 复杂度排序：同分或性能差距极小时优先选简单模型（对应评分标准中
# 「综合考虑验证集性能与模型复杂度」）
COMPLEXITY_RANK = {"NB": 1, "LR": 2, "SVM": 3, "MLP": 4}
ACC_TOLERANCE = 0.003


def select_final_model(best_models: dict, logger) -> dict:
    """在「性能接近」的候选中优先选结构更简单的模型。"""
    ranked = sorted(
        best_models.values(),
        key=lambda r: (-r["accuracy"], -r["macro_f1"], COMPLEXITY_RANK[r["model"]]),
    )
    top_acc = ranked[0]["accuracy"]
    candidates = [r for r in ranked if top_acc - r["accuracy"] <= ACC_TOLERANCE]
    chosen = min(candidates, key=lambda r: COMPLEXITY_RANK[r["model"]])
    logger.info("  方案选择：验证准确率最高的模型为 "
                f"{ranked[0]['model']}({ranked[0]['accuracy']:.4f})；"
                f"在 {ACC_TOLERANCE:.1%} 容差内复杂度最低者为 "
                f"{chosen['model']}({chosen['accuracy']:.4f})，据此锁定最终方案。")
    return chosen


def main() -> int:
    parser = argparse.ArgumentParser(description="当代人工智能实验一：文本分类")
    parser.add_argument("--stage", default="all",
                        choices=["all", "eda", "preprocess", "features", "tune", "final"],
                        help="要执行的阶段")
    parser.add_argument("--val-size", type=float, default=0.2, help="验证集比例")
    parser.add_argument("--seed", type=int, default=SEED, help="全局随机种子")
    args = parser.parse_args()

    ensure_dirs()
    log_file = METRICS_DIR.parent / "logs" / f"run-{timestamp()}.log"
    logger = get_logger("exp1", log_file)
    t_start = time.perf_counter()

    logger.info("=" * 68)
    logger.info("当代人工智能实验一 · 文本分类（10 类新闻文本）")
    logger.info(f"随机种子 seed={args.seed}，验证集比例 val_size={args.val_size}")
    logger.info(f"运行阶段：{args.stage}")
    logger.info("=" * 68)

    bundle = data_mod.build_dataset(val_size=args.val_size, seed=args.seed)

    # 中间方案的默认值：若只跑 final 阶段，用调参阶段的落盘结果
    clean_cfg = pp.preset_configs()["C4_完整清洗"]
    feat_cfg = feat_mod.TfidfConfig(
        max_features=20000, ngram_range=(1, 1), min_df=2, max_df=0.9,
        sublinear_tf=True, use_idf=True, name="F1_TF-IDF(sublinear)",
    )

    if args.stage in ("all", "eda"):
        exp.run_eda(bundle, logger)

    if args.stage in ("all", "preprocess"):
        rows = exp.run_preprocess_ablation(bundle, feat_cfg, logger)
        best_name = max(rows, key=lambda r: r["accuracy"])["name"]
        clean_cfg = pp.preset_configs()[best_name]

    if args.stage in ("all", "features"):
        rows = exp.run_feature_ablation(bundle, clean_cfg, logger)
        best_name = max(rows, key=lambda r: r["accuracy"])["name"]
        feat_cfg = feat_mod.preset_feature_configs()[best_name]

    if args.stage in ("all", "tune"):
        tuning = exp.run_model_tuning(bundle, clean_cfg, feat_cfg, logger)
        exp.run_cv_confirm(bundle, clean_cfg, feat_cfg, tuning["best"], logger)
        chosen = select_final_model(tuning["best"], logger)

        diag = exp.run_best_model_diagnostics(bundle, clean_cfg, feat_cfg, chosen, logger)
        final = exp.run_final(bundle, clean_cfg, feat_cfg, chosen, logger)

        save_json({
            "seed": args.seed,
            "val_size": args.val_size,
            "clean_config": clean_cfg.name,
            "clean_config_detail": clean_cfg.describe(),
            "feature_config": feat_cfg.describe(),
            "selected_model": chosen["model"],
            "selected_params": model_mod.param_str(chosen["params_raw"]),
            "validation_accuracy": round(chosen["accuracy"], 4),
            "validation_macro_f1": round(chosen["macro_f1"], 4),
            "final": final,
            "diagnostics_summary": {
                "accuracy": diag["accuracy"],
                "macro_f1": diag["macro_f1"],
                "weighted_f1": diag["weighted_f1"],
            },
        }, METRICS_DIR / "experiment_summary.json")

    if args.stage == "final":
        # 单独执行 final：读取上一次调参的最优方案
        tuning = exp.run_model_tuning(bundle, clean_cfg, feat_cfg, logger)
        chosen = select_final_model(tuning["best"], logger)
        exp.run_final(bundle, clean_cfg, feat_cfg, chosen, logger)

    logger.info("=" * 68)
    logger.info(f"全部完成，总耗时 {time.perf_counter() - t_start:.1f} 秒")
    logger.info(f"结果目录：{METRICS_DIR.parent}")
    logger.info("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
