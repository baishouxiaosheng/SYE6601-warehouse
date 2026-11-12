import json
import os
from collections import Counter


def load_results(file_path):
    if not os.path.exists(file_path):
        print(f"❌ 找不到文件: {file_path}")
        return {}
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return {item['task_id'].strip(): item for item in data}  # 注意这里加了 strip() 防止空格问题


def compare_results(auto_file, manual_file):
    print("=" * 70)
    print("📊 消融实验对比统计报告 (自动建链 vs 人工预配置)")
    print("=" * 70)

    auto_data = load_results(auto_file)
    manual_data = load_results(manual_file)

    all_task_ids = set(auto_data.keys()).union(set(manual_data.keys()))
    total_cases = len(all_task_ids)

    print(f"\n📌 总案例数: {total_cases}")

    auto_status_dist = Counter()
    manual_status_dist = Counter()
    match_count = 0
    mismatch_cases = []

    for task_id in sorted(all_task_ids):
        auto_res = auto_data.get(task_id, {})
        manual_res = manual_data.get(task_id, {})

        # 获取结论，兼容不同的键名
        auto_status = auto_res.get('model_status', auto_res.get('status', 'UNKNOWN'))
        manual_status = manual_res.get('model_status', manual_res.get('status', 'UNKNOWN'))

        auto_decision = auto_res.get('model_decision', auto_res.get('decision', '转人工'))
        manual_decision = manual_res.get('model_decision', manual_res.get('decision', '转人工'))

        auto_status_dist[auto_status] += 1
        manual_status_dist[manual_status] += 1

        if auto_status == manual_status and auto_decision == manual_decision:
            match_count += 1
        else:
            mismatch_cases.append({
                "task_id": task_id,
                "scenario": auto_res.get('scenario_type', manual_res.get('scenario_type', '未知')),
                "auto": f"{auto_status} / {auto_decision}",
                "manual": f"{manual_status} / {manual_decision}"
            })

    print("\n【1. 结论状态 (Status) 分布对比】")
    print(f"{'状态':<10} | {'自动建链 (Auto)':<15} | {'人工预配置 (Manual)':<15}")
    print("-" * 45)
    all_statuses = sorted(list(set(auto_status_dist.keys()).union(set(manual_status_dist.keys()))))
    for status in all_statuses:
        print(f"{status:<10} | {auto_status_dist[status]:<15} | {manual_status_dist[status]:<15}")

    print(f"\n【2. 结论一致性分析】")
    print(f"✅ 结论完全一致的案例数: {match_count} / {total_cases} ({match_count / total_cases * 100:.1f}%)")
    print(
        f"⚠️  结论存在分歧的案例数: {len(mismatch_cases)} / {total_cases} ({len(mismatch_cases) / total_cases * 100:.1f}%)")

    if mismatch_cases:
        print("\n【3. 核心分歧案例详情 (重点分析对象)】")
        print("-" * 70)
        for case in mismatch_cases:
            print(f"🔹 {case['task_id']} ({case['scenario']})")
            print(f"   ➔ 自动建链: {case['auto']}")
            print(f"   ➔ 人工预配: {case['manual']}")
            print()


if __name__ == "__main__":
    # 确保文件名和你实际生成的一致
    FILE_AUTO = "experiment_results_60.json"
    FILE_MANUAL = "experiment_results_ablation_manual.json"

    compare_results(FILE_AUTO, FILE_MANUAL)