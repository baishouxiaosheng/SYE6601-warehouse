# 测试组 B：建链评测与回归实验报告

## 1. 核心交付物
- **一键测试入口**: `pytest tests/test_baselines.py -v -s`
- **消融实验对比脚本**: `python compare_ablation.py`
- **DYN-01 结构增量演示**: `python tests/test_dyn01_demo.py`

## 2. 实验结果摘要
### 2.1 48 例真实模型跑测 (Qwen-7B)
- 成功接入硅基流动 API，完成 48 例运行侧案例推理。
- 原始日志见 `experiment_results_48.json`。
- **典型发现**: 模型在处理 A-039 (身份矛盾) 时正确识别 CONFLICT，但在 A-040 (跨系统矛盾) 时倾向于保守返回 UNKNOWN。

### 2.2 消融实验 (自动建链 vs 人工预配置)
- 运行 `compare_ablation.py` 可见详细对比。
- **结论**: 自动建链模式下模型偏保守 (UNKNOWN 占比 54%)；人工预配置能显著提升明确结论比例 (REFUTE/SUPPORT 占比超 90%)。证明“自动发现 + 规则兜底”是最佳实践。

### 2.3 DYN-01 自动建链验证
- 运行 `test_dyn01_demo.py` 可见完整 5 步观察点。
- 系统成功从合同原文发现“24小时工单”条款，并触发 Loop 补查，最终修正结论。

## 3. 模型波动与失败归因
- **案例 A-040**: 监控与工单系统证据矛盾。7B 模型未能准确输出 CONFLICT，而是降级为 UNKNOWN。表明小参数模型处理复杂双真值冲突存在局限。