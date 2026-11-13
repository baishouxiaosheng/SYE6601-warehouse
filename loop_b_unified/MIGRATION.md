# 当前目录和历史版本

正式路径：仓库根目录 loop_b_unified/。
统一导入：from loop_b_unified import create_provider, make_review_packet。
独立运行：loop_b_unified/run_raw_demo.py。

2026-11-13 核对 main 04da37d906ff359317033b56c970d69cd902721b：
PR #7 已合并；当前 main 没有 modules/loop_b_mock，也没有 modules/loop_b_unified。
因此当前 main 不需要再删除旧模块。旧分支保留备份，不再用于交接。
此前关于 loop-b-mock、PR #6 更新、拖入 modules 的操作说明已过期。

如果搭档本地仍用旧路径，请重新取得最新主分支并改用上述入口。
不要删其他组文件，也不要为了消除导入报错而复制多份同名模块。
当前 main 缺少 dynamic_evidence 控制器，应由组长／Loop A 确认恢复位置；
本次不会从旧历史覆盖整个团队仓库。
