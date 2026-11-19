"""Streamlit 组件（SPEC §9）：render_user_sim_button(key="user_sim", on_generate=None) -> dict | None"""
from .generator import generate_question
from .personas import PERSONAS


def render_user_sim_button(key: str = "user_sim", on_generate=None):
    try:
        import streamlit as st
    except ImportError:
        raise RuntimeError("演示组件需要 Streamlit，请先安装 streamlit。") from None

    domains = {"industrial": "工业", "insurance": "保险"}
    domain = st.radio("领域", list(domains), format_func=domains.get, horizontal=True, key=key + "_domain")
    options = {"": "随机", **{pid: p["label_zh"] for pid, p in PERSONAS.items()}}
    persona = st.selectbox("画像", list(options), format_func=options.get, key=key + "_persona")
    if st.button("生成一个用户问题", key=key + "_generate"):
        with st.spinner("正在生成问题…"):
            q = generate_question(domain=domain, persona=persona or None)
        st.session_state["user_sim_question"] = q
        if on_generate is not None:
            on_generate(q)
    q = st.session_state.get("user_sim_question")
    if q:
        with st.container(border=True):
            st.caption(domains[q["domain"]] + " · " + q["persona"]["label_zh"])
            st.write(q["user_question"])
            if q["generator"]["mode"] == "offline_fallback":
                st.caption("离线备用题")
    return q
