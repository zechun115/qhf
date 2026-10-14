"""实验一主流程：从数据加载到最终预测的完整证据链。

流程（每一步都单独记录结果，便于报告中追溯）：
    阶段 0  数据探索与划分
    阶段 1  文本预处理消融（控制其他条件不变）
    阶段 2  TF-IDF 特征表示消融
    阶段 3  四个模型的超参数网格搜索（只在验证集上比较）
    阶段 4  交叉验证确认最优方案（稳定性）
    阶段 5  锁定方案 -> 在训练集+验证集上重训 -> 预测无标签测试集
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold, cross_val_score

from . import data as data_mod
from . import evaluate as ev
from . import features as feat_mod
from . import models as model_mod
from . import plotting as plot_mod
from . import preprocess as pp
from .utils import METRICS_DIR, RESULTS_DIR, SEED, save_json

# ---------------------------------------------------------------------------


def run_eda(bundle: data_mod.DataBundle, logger) -> dict:
    """阶段 0：数据探索。"""
    logger.info("=" * 68)
    logger.info("阶段 0 / 数据探索与划分")
    summary = data_mod.describe(bundle.train_df, bundle.test_df)
    summary["val_size_ratio"] = round(len(bundle.X_val) / (
        len(bundle.X_train) + len(bundle.X_val)), 4)
    summary["n_train_split"] = len(bundle.X_train)
    summary["n_val"] = len(bundle.X_val)

    fig = plot_mod.plot_class_distribution(summary["class_counts"])
    summary["figure_class_distribution"] = fig
    save_json(summary, METRICS_DIR / "dataset_summary.json")

    logger.info(f"训练集 {summary['n_train']} 条 / 测试集 {summary['n_test']} 条 / "
                f"{summary['n_classes']} 个类别")
    logger.info(f"划分后：训练 {summary['n_train_split']} 条，验证 {summary['n_val']} 条"
                f"（验证比例 {summary['val_size_ratio']:.1%}，分层抽样）")
    logger.info(f"文本长度 中位数 {summary['text_len_median']} 字符，"
                f"P95 {summary['text_len_p95']}，最大 {summary['text_len_max']}")
    logger.info(f"训练集重复文本数 {summary['dup_text_train']}")
    return summary


def run_preprocess_ablation(bundle, feat_cfg, logger) -> list[dict]:
    """阶段 1：预处理消融。固定模型与特征配置，只改变清洗方案。"""
    logger.info("=" * 68)
    logger.info("阶段 1 / 文本预处理消融（固定 LR(C=10) + TF-IDF 基准特征）")
    rows = []
    probe_model_params = {"C": 10.0, "max_iter": 2000, "solver": "lbfgs"}

    for cname, ccfg in pp.preset_configs().items():
        t0 = time.perf_counter()
        Xtr = pp.clean_corpus(bundle.X_train, ccfg)
        Xva = pp.clean_corpus(bundle.X_val, ccfg)
        clean_s = time.perf_counter() - t0

        fb = feat_mod.build_features(Xtr, Xva, Xva, feat_cfg)
        res = ev.evaluate_model(
            model_mod.make_model("LR", probe_model_params),
            fb.X_train, bundle.y_train, fb.X_val, bundle.y_val,
            "LR", probe_model_params, "C=10", keep_confusion=False,
        )
        rows.append({
            "name": cname,
            "description": ccfg.describe(),
            "clean_seconds": round(clean_s, 2),
            "avg_tokens": round(float(np.mean([len(t.split()) for t in Xtr])), 1),
            "accuracy": round(res.accuracy, 4),
            "macro_f1": round(res.macro_f1, 4),
        })
        logger.info(f"  {cname:<20} acc={res.accuracy:.4f}  macroF1={res.macro_f1:.4f}  "
                    f"平均词数={rows[-1]['avg_tokens']:.0f}")

    best = max(rows, key=lambda r: r["accuracy"])
    logger.info(f"  -> 最优清洗方案：{best['name']}（acc={best['accuracy']:.4f}）")
    fig = plot_mod.plot_preprocess_ablation(rows)
    pd.DataFrame(rows).to_csv(METRICS_DIR / "preprocess_ablation.csv",
                              index=False, encoding="utf-8-sig")
    save_json({"rows": rows, "best": best["name"], "figure": fig},
              METRICS_DIR / "preprocess_ablation.json")
    return rows


def run_feature_ablation(bundle, clean_cfg, logger) -> list[dict]:
    """阶段 2：特征表示消融。固定清洗方案与模型，只改变 TF-IDF 配置。"""
    logger.info("=" * 68)
    logger.info("阶段 2 / TF-IDF 特征表示消融（固定 LR(C=10)）")
    Xtr = pp.clean_corpus(bundle.X_train, clean_cfg)
    Xva = pp.clean_corpus(bundle.X_val, clean_cfg)
    probe_params = {"C": 10.0, "max_iter": 2000, "solver": "lbfgs"}
    rows = []

    for fname, fcfg in feat_mod.preset_feature_configs().items():
        fb = feat_mod.build_features(Xtr, Xva, Xva, fcfg)
        res = ev.evaluate_model(
            model_mod.make_model("LR", probe_params),
            fb.X_train, bundle.y_train, fb.X_val, bundle.y_val,
            "LR", probe_params, "C=10",
        )
        rows.append({
            "name": fname,
            "config": fcfg.describe(),
            "n_features": fb.n_features,
            "vectorize_seconds": fb.fit_seconds,
            "accuracy": round(res.accuracy, 4),
            "macro_f1": round(res.macro_f1, 4),
        })
        logger.info(f"  {fname:<22} dim={fb.n_features:<6} acc={res.accuracy:.4f}  "
                    f"macroF1={res.macro_f1:.4f}")

    best = max(rows, key=lambda r: r["accuracy"])
    logger.info(f"  -> 最优特征配置：{best['name']}（acc={best['accuracy']:.4f}）")
    fig = plot_mod.plot_feature_ablation(rows)
    pd.DataFrame(rows).to_csv(METRICS_DIR / "feature_ablation.csv",
                              index=False, encoding="utf-8-sig")
    save_json({"rows": rows, "best": best["name"], "figure": fig},
              METRICS_DIR / "feature_ablation.json")
    return rows


def run_model_tuning(bundle, clean_cfg, feat_cfg, logger) -> dict:
    """阶段 3：四个模型的超参数网格搜索，全部以验证集准确率为选择依据。"""
    logger.info("=" * 68)
    logger.info("阶段 3 / 模型超参数网格搜索（评价指标：验证集准确率 / Macro-F1）")
    Xtr = pp.clean_corpus(bundle.X_train, clean_cfg)
    Xva = pp.clean_corpus(bundle.X_val, clean_cfg)
    fb = feat_mod.build_features(Xtr, Xva, Xva, feat_cfg)
    logger.info(f"  特征矩阵：train {fb.X_train.shape}，稀疏度 "
                f"{1 - fb.X_train.nnz / (fb.X_train.shape[0] * fb.X_train.shape[1]):.4f}")

    all_rows: list[dict] = []
    curves: dict[str, list] = {}
    best_models: dict[str, dict] = {}
    grids = model_mod.param_grids()

    for mname, grid in grids.items():
        logger.info(f"  --- {model_mod.MODEL_INFO[mname]['full_name']} ---")
        round_rows = []
        for params in grid:
            pstr = model_mod.param_str(params)
            res = ev.evaluate_model(
                model_mod.make_model(mname, params),
                fb.X_train, bundle.y_train, fb.X_val, bundle.y_val,
                mname, params, pstr, keep_confusion=True,
            )
            row = res.to_row()
            row["grid_stage"] = "主网格"
            row["confusion"] = res.confusion
            row["params_raw"] = params
            round_rows.append(row)
            logger.info(f"    {pstr:<38} acc={res.accuracy:.4f}  "
                        f"macroF1={res.macro_f1:.4f}  训练 {res.train_seconds:.1f}s")

        # MLP 第二阶段：固定最优结构，搜索 L2 正则化 alpha
        if mname == "MLP":
            best_struct_row = max(round_rows, key=lambda r: r["accuracy"])
            struct = best_struct_row["params_raw"]["hidden_layer_sizes"]
            logger.info(f"    [二阶] 固定结构 {struct}，搜索 alpha")
            for params in model_mod.mlp_alpha_grid(struct):
                pstr = model_mod.param_str(params)
                res = ev.evaluate_model(
                    model_mod.make_model("MLP", params),
                    fb.X_train, bundle.y_train, fb.X_val, bundle.y_val,
                    "MLP", params, pstr, keep_confusion=True,
                )
                row = res.to_row()
                row["grid_stage"] = "alpha搜索"
                row["confusion"] = res.confusion
                row["params_raw"] = params
                round_rows.append(row)
                logger.info(f"    {pstr:<38} acc={res.accuracy:.4f}  "
                            f"macroF1={res.macro_f1:.4f}  训练 {res.train_seconds:.1f}s")

        best = max(round_rows, key=lambda r: (r["accuracy"], r["macro_f1"]))
        best_models[mname] = best
        all_rows.extend(round_rows)

        # 超参数敏感性曲线：横轴标签按参数语义生成（不从字符串反解析）
        def _label(r: dict) -> str:
            p = r["params_raw"]
            if r["grid_stage"] == "alpha搜索":
                return f"α={p['alpha']}"
            if mname == "NB":
                return f"α={p['alpha']}"
            if mname in ("LR", "SVM"):
                return f"C={p['C']:g}"
            h = p["hidden_layer_sizes"]
            return f"h={h[0]}" + (f",{h[1]}" if len(h) > 1 else "")

        if mname == "MLP":
            # MLP 是两阶段搜索：结构（阶段一）+ alpha（阶段二），一并画入
            curves[mname] = [(_label(r), r["accuracy"]) for r in round_rows]
        else:
            curves[mname] = [(_label(r), r["accuracy"]) for r in round_rows]
        logger.info(f"  -> {mname} 最优：{best['params']}  acc={best['accuracy']:.4f}")

    fig4 = plot_mod.plot_param_curves(curves)

    fig6 = plot_mod.plot_model_comparison([best_models[m] for m in grids])

    # 落盘（剔除不便序列化的字段）
    drop = {"confusion", "params_raw"}
    tbl = pd.DataFrame([{k: v for k, v in r.items() if k not in drop} for r in all_rows])
    tbl.to_csv(METRICS_DIR / "model_tuning.csv", index=False, encoding="utf-8-sig")
    save_json({
        "rows": [{k: v for k, v in r.items() if k not in drop} for r in all_rows],
        "best": {m: {k: v for k, v in best_models[m].items() if k not in drop}
                 for m in best_models},
        "figure_param_curves": fig4,
        "figure_model_comparison": fig6,
    }, METRICS_DIR / "model_tuning.json")

    return {"all_rows": all_rows, "best": best_models,
            "feature_bundle": fb, "X_train_clean": Xtr, "X_val_clean": Xva,
            "figures": {"param_curves": fig4, "model_comparison": fig6}}


def run_cv_confirm(bundle, clean_cfg, feat_cfg, best_models: dict, logger) -> dict:
    """阶段 4：对每个模型的最优配置做 5 折分层交叉验证，衡量稳定性。"""
    logger.info("=" * 68)
    logger.info("阶段 4 / 5 折分层交叉验证（稳定性确认，只在训练集上进行）")
    Xtr = pp.clean_corpus(bundle.X_train, clean_cfg)
    fb = feat_mod.build_features(Xtr, Xtr, Xtr, feat_cfg)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)

    out = {}
    for mname, best in best_models.items():
        params = best["params_raw"]
        # n_jobs=-1 只并行化「折与折之间」，不改变任何随机性，结果与串行一致
        scores = cross_val_score(
            model_mod.make_model(mname, params), fb.X_train, bundle.y_train,
            cv=skf, scoring="accuracy", n_jobs=-1,
        )
        f1s = cross_val_score(
            model_mod.make_model(mname, params), fb.X_train, bundle.y_train,
            cv=skf, scoring="f1_macro", n_jobs=-1,
        )
        out[mname] = {
            "params": model_mod.param_str(params),
            "cv_accuracy_mean": round(float(scores.mean()), 4),
            "cv_accuracy_std": round(float(scores.std()), 4),
            "cv_macro_f1_mean": round(float(f1s.mean()), 4),
            "cv_macro_f1_std": round(float(f1s.std()), 4),
            "folds": [round(float(s), 4) for s in scores],
            "val_accuracy_single_split": best["accuracy"],
        }
        logger.info(f"  {mname}: 5 折 acc = {scores.mean():.4f} ± {scores.std():.4f}  |  "
                    f"单次验证 acc = {best['accuracy']:.4f}")

    save_json(out, METRICS_DIR / "cv_results.json")
    return out


def run_final(bundle, clean_cfg, feat_cfg, best_row: dict, logger) -> dict:
    """阶段 5：锁定方案，在训练集+验证集上重训，预测无标签测试集。"""
    logger.info("=" * 68)
    logger.info("阶段 5 / 锁定最优方案并进行最终预测")
    mname = best_row["model"]
    params = best_row["params_raw"]
    logger.info(f"  最优模型：{model_mod.MODEL_INFO[mname]['full_name']}  "
                f"[{model_mod.param_str(params)}]")

    X_full = pp.clean_corpus(bundle.X_train, clean_cfg) + pp.clean_corpus(bundle.X_val, clean_cfg)
    y_full = np.concatenate([bundle.y_train, bundle.y_val])
    X_test = pp.clean_corpus(bundle.X_test, clean_cfg)
    logger.info(f"  最终训练样本数：{len(X_full)}（原训练集 + 验证集）")

    # 向量器在全体有标签数据上重新拟合（测试集仍不参与任何统计）
    fb = feat_mod.build_features(X_full, X_full, X_test, feat_cfg)
    model = model_mod.make_model(mname, params)

    t0 = time.perf_counter()
    model.fit(fb.X_train, y_full)
    train_s = time.perf_counter() - t0
    t1 = time.perf_counter()
    y_test_pred = model.predict(fb.X_test)
    predict_s = time.perf_counter() - t1
    logger.info(f"  训练 {train_s:.1f}s，预测 {len(y_test_pred)} 条用时 {predict_s:.2f}s")

    # 提交文件：单列、无表头，与助教提供的 predictions.csv 示例格式一致
    pred_df = pd.DataFrame({"target": y_test_pred})
    root_pred = RESULTS_DIR.parent / "predictions.csv"
    pred_df.to_csv(root_pred, index=False, header=False)
    pred_df.to_csv(RESULTS_DIR / "predictions.csv", index=False, header=False)

    dist = pd.Series(y_test_pred).value_counts().sort_index().to_dict()
    logger.info(f"  预测类别分布：{ {int(k): int(v) for k, v in dist.items()} }")
    logger.info(f"  已写出 {root_pred}")

    info = {
        "model": mname,
        "model_full_name": model_mod.MODEL_INFO[mname]["full_name"],
        "params": model_mod.param_str(params),
        "params_raw": params,
        "n_final_train": int(len(X_full)),
        "n_test": int(len(y_test_pred)),
        "n_features": fb.n_features,
        "train_seconds": round(train_s, 2),
        "predict_seconds": round(predict_s, 3),
        "prediction_distribution": {int(k): int(v) for k, v in dist.items()},
        "predictions_file": str(root_pred),
    }
    save_json(info, METRICS_DIR / "final_model.json")
    return info


def run_best_model_diagnostics(bundle, clean_cfg, feat_cfg, best_row: dict, logger) -> dict:
    """在验证集上对最优模型做详细诊断：分类报告、混淆矩阵、误差分析、关键词。"""
    logger.info("=" * 68)
    logger.info("阶段 5b / 最优模型诊断（验证集）")
    Xtr = pp.clean_corpus(bundle.X_train, clean_cfg)
    Xva = pp.clean_corpus(bundle.X_val, clean_cfg)
    fb = feat_mod.build_features(Xtr, Xva, Xva, feat_cfg)
    model = model_mod.make_model(best_row["model"], best_row["params_raw"])
    res = ev.evaluate_model(model, fb.X_train, bundle.y_train, fb.X_val, bundle.y_val,
                            best_row["model"], best_row["params_raw"], best_row["params"],
                            keep_confusion=True)

    report = ev.text_report(bundle.y_val, res.y_pred)
    logger.info("  分类报告：\n" + report)

    fig5 = plot_mod.plot_confusion_matrix(
        res.confusion,
        title=f"图 6  最优模型（{best_row['model']}）混淆矩阵（验证集）")
    fig7 = plot_mod.plot_per_class_f1(res.per_class, best_row["model"])

    errors = ev.summarize_errors(bundle.y_val, res.y_pred, bundle.X_val)
    top_terms = feat_mod.top_terms_by_class(fb.vectorizer, fb.X_train, bundle.y_train)

    logger.info("  最易混淆类别对：" + "; ".join(
        f"{e['true']}->{e['pred']}({e['count']}次)" for e in errors["top_confusions"][:5]))

    out = {
        "accuracy": round(res.accuracy, 4),
        "macro_f1": round(res.macro_f1, 4),
        "weighted_f1": round(res.weighted_f1, 4),
        "per_class": {str(k): v for k, v in res.per_class.items()},
        "confusion_matrix": res.confusion,
        "classification_report": report,
        "error_analysis": errors,
        "top_terms_by_class": {str(k): v for k, v in top_terms.items()},
        "figures": {"confusion_matrix": fig5, "per_class_f1": fig7},
        "train_seconds": res.train_seconds,
    }
    save_json(out, METRICS_DIR / "best_model_diagnostics.json")
    return out
