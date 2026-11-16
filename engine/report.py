# report.py
# Generates a shareable Markdown report compiling optimization iterations and stats.
# Preserves all existing functionality while adding experiment-level reporting,
# rejection reasons, and configuration snapshots in AutoTune 2.0.

import os
import sqlite3
import datetime
import json
import base64
import io
from typing import Optional
import config
import eval_harness
import db

def generate_report(run_id: str = "current", db_path: Optional[str] = None, compute_holdout: bool = False) -> str:
    """
    Pulls iterations from SQLite database and formats a comprehensive,
    self-contained Markdown optimization report with inline encoded charts.
    Supports specific experiment_id or 'current' latest experiment.
    """
    if db_path is None:
        engine_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(engine_dir, "autotune.db")

    if not os.path.exists(db_path):
        return "# Error: AutoTune database (autotune.db) not found."

    conn = db.get_connection(db_path)
    cursor = conn.cursor()

    # Determine which experiment to report
    exp_filter = None
    if run_id and run_id != "current":
        cursor.execute("SELECT COUNT(*) FROM iterations WHERE experiment_id = ?", (run_id,))
        if cursor.fetchone()[0] > 0:
            exp_filter = run_id

    if exp_filter:
        cursor.execute("""
            SELECT iteration_number, hypothesis, param, old_value, new_value,
                   old_score, new_score, accepted, timestamp, motivated_by,
                   avg_latency_ms, total_tokens, composite_score, project_id,
                   experiment_id, trial_id, config_snapshot, score_improvement,
                   rejection_reason, proposal_status
            FROM iterations
            WHERE experiment_id = ?
            ORDER BY iteration_number ASC
        """, (exp_filter,))
    else:
        cursor.execute("""
            SELECT iteration_number, hypothesis, param, old_value, new_value,
                   old_score, new_score, accepted, timestamp, motivated_by,
                   avg_latency_ms, total_tokens, composite_score, project_id,
                   experiment_id, trial_id, config_snapshot, score_improvement,
                   rejection_reason, proposal_status
            FROM iterations
            ORDER BY iteration_number ASC
        """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "# Error: No iterations found in the AutoTune database."

    iterations = [dict(r) for r in rows]
    baseline = iterations[0]
    experiment_id = baseline.get("experiment_id", run_id)

    # Identify the best accepted iteration
    best_iteration = baseline
    for item in iterations:
        if item["accepted"]:
            item_comp = item.get("composite_score") if item.get("composite_score") is not None else item["new_score"]
            best_comp = best_iteration.get("composite_score") if best_iteration.get("composite_score") is not None else best_iteration["new_score"]
            if item_comp >= best_comp:
                best_iteration = item

    starting_score = baseline["new_score"]
    final_score = best_iteration["new_score"]
    final_latency = best_iteration.get("avg_latency_ms") or 0.0
    final_tokens = best_iteration.get("total_tokens") or 0
    final_composite = best_iteration.get("composite_score") or final_score
    total_runs = len(iterations) - 1 if len(iterations) > 1 else 1

    # Calculate holdout score only if requested
    holdout_score_val = None
    if compute_holdout:
        try:
            res = eval_harness.evaluate_holdout(config.CONFIG, is_experimental=False)
            holdout_score_val = res["aggregate_score"]
        except Exception as e:
            print(f"Warning: Could not compute holdout score for report: {e}")

    # Generate chart
    chart_base64 = ""
    chart_ascii = ""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        x = [item["iteration_number"] for item in iterations]
        y_score = [item["new_score"] for item in iterations]
        y_composite = [item.get("composite_score") if item.get("composite_score") is not None else item["new_score"] for item in iterations]

        plt.figure(figsize=(9, 4.5))
        plt.style.use('dark_background')

        plt.plot(x, y_score, color='#818cf8', linestyle='--', linewidth=1.5, label='Accuracy')
        plt.plot(x, y_composite, color='#10b981', marker='o', linewidth=2.5, markersize=4, label='Composite Score')

        accepted_x = [item["iteration_number"] for item in iterations if item["accepted"] and item["iteration_number"] > 0]
        accepted_y = [item.get("composite_score") if item.get("composite_score") is not None else item["new_score"] for item in iterations if item["accepted"] and item["iteration_number"] > 0]
        if accepted_x:
            plt.scatter(accepted_x, accepted_y, color='#10b981', s=70, zorder=5, label='Accepted Config')

        rejected_x = [item["iteration_number"] for item in iterations if not item["accepted"] and item["iteration_number"] > 0]
        rejected_y = [item.get("composite_score") if item.get("composite_score") is not None else item["new_score"] for item in iterations if not item["accepted"] and item["iteration_number"] > 0]
        if rejected_x:
            plt.scatter(rejected_x, rejected_y, color='#ef4444', s=70, zorder=5, label='Rejected Config')

        plt.title(f'AutoTune Optimization Progression ({experiment_id})', fontsize=12, pad=15, color='#e2e8f0', fontweight='bold')
        plt.xlabel('Iteration Number', color='#94a3b8', fontsize=9)
        plt.ylabel('Score Metric', color='#94a3b8', fontsize=9)
        plt.ylim(-0.05, 1.05)
        plt.grid(True, linestyle='--', alpha=0.15, color='#334155')
        plt.legend(frameon=True, facecolor='#1e293b', edgecolor='none', loc='lower right', fontsize=8)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150)
        plt.close()
        buf.seek(0)
        chart_base64 = base64.b64encode(buf.read()).decode('utf-8')
    except Exception as e:
        chart_ascii = "\n### Score Progression Chart (ASCII Fallback)\n```text\n"
        for item in iterations:
            item_comp = item.get("composite_score") if item.get("composite_score") is not None else item["new_score"]
            bar_len = int(item_comp * 25)
            bar = "█" * bar_len + "░" * (25 - bar_len)
            status = " [OK]" if item["accepted"] else " [REJECTED]"
            if item["iteration_number"] == 0:
                status = " [BASELINE]"
            chart_ascii += f"Iter #{item['iteration_number']:2d} (Comp: {item_comp:.4f} | Acc: {item['new_score']:.4f}) | {bar} |{status}\n"
        chart_ascii += "```\n"

    holdout_text = f"**{holdout_score_val * 100:.1f}%**" if holdout_score_val is not None else "Not evaluated in this report (blind holdout isolation preserved)"

    # Assemble Markdown report
    md = f"""# 🎯 AutoTune Optimization Report

## 📋 Run Metadata
- **Experiment ID**: `{experiment_id}`
- **Generated On**: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **Total Optimization Loops**: {total_runs} iterations
- **Tuning Set Accuracy**: **{final_score * 100:.1f}%** (Starting: {starting_score * 100:.1f}%)
- **Tuning Set Avg Latency**: **{final_latency:.0f}ms**
- **Tuning Set Total Tokens**: **{final_tokens} tokens**
- **Composite Score (Accuracy/Latency/Cost)**: **{final_composite:.4f}**
- **Holdout Set Accuracy**: {holdout_text}
- **Model Backend**: Dual Ollama + Gemini API (Auto-Detect Mode)

---

## 📈 Optimization Trajectory
"""
    if chart_base64:
        md += f"![Score Progression](data:image/png;base64,{chart_base64})\n\n"
    else:
        md += chart_ascii + "\n"

    md += """
## 🔄 Log of Accepted Tuning Changes
Below are the parameter modifications that were approved and committed by the optimizer:

| Iteration | Parameter | Modification | Accuracy | Latency | Composite Score | Improvement | Targeted Failure |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
"""
    for item in iterations:
        if item["accepted"] and item["iteration_number"] > 0:
            failures = "N/A"
            if item.get("motivated_by"):
                failures = item["motivated_by"].split(" | ")[0]
                if len(failures) > 60:
                    failures = failures[:57] + "..."
            item_comp = item.get("composite_score") if item.get("composite_score") is not None else item["new_score"]
            imp = item.get("score_improvement") or 0.0
            lat = item.get("avg_latency_ms") or 0.0
            old_sc = item.get("old_score") or 0.0
            new_sc = item.get("new_score") or 0.0
            md += f"| {item['iteration_number']} | `{item['param']}` | `{item['old_value']}` &rarr; `{item['new_value']}` | {old_sc:.3f} &rarr; {new_sc:.3f} | {lat:.0f}ms | {item_comp:.4f} | +{imp:.4f} | *\"{failures}\"* |\n"

    md += """
## ❌ Log of Rejected Trials
Below are the trials that were rejected along with explicit rejection reasons:

| Iteration | Parameter | Proposed Value | Score | Composite | Rejection Reason |
| :---: | :--- | :--- | :---: | :---: | :--- |
"""
    for item in iterations:
        if not item["accepted"] and item["iteration_number"] > 0:
            item_comp = item.get("composite_score") if item.get("composite_score") is not None else (item.get("new_score") or 0.0)
            reason = item.get("rejection_reason") or "Did not outperform current baseline"
            if len(reason) > 80:
                reason = reason[:77] + "..."
            sc = item.get("new_score") or 0.0
            md += f"| {item['iteration_number']} | `{item['param']}` | `{item['new_value']}` | {sc:.3f} | {item_comp:.4f} | {reason} |\n"

    # Print hypotheses for accepted configurations
    md += "\n### Accepted Hypotheses:\n"
    for item in iterations:
        if item["accepted"] and item["iteration_number"] > 0:
            md += f"- **Iteration #{item['iteration_number']} (`{item['param']}`):** *\"{item['hypothesis']}\"*\n"

    # Serialize final config
    final_config_str = json.dumps(config.CONFIG, indent=2)
    md += f"""
---

## ⚙️ Active Production Configuration (config.py)
This is the current active configuration saved in production:

```json
{final_config_str}
```

---
*Report generated automatically by the AutoTune self-optimization loop.*
"""
    return md
