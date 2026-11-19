"""课堂演示页：streamlit run apps/user_sim_demo.py --server.address localhost。"""
import json
import sys
from pathlib import Path

try:
    import streamlit as st
except ImportError:
    raise SystemExit("演示页需要 Streamlit，请先安装 streamlit。") from None

# Streamlit 将 apps/ 加入导入路径，独立运行时也需要能找到同级的 user_sim。
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from user_sim import to_log_record
from user_sim.ui import render_user_sim_button

st.title("用户模拟 Agent")
question = render_user_sim_button()
if question:
    st.subheader("下游日志记录")
    st.code(json.dumps(to_log_record(question), ensure_ascii=False, indent=2), language="json")
