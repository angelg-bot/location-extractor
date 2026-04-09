"""
Location & Character Extractor — Streamlit App
上传剧本文件，自动提取场景库和角色库。
"""

import asyncio
import os
import json
import streamlit as st

from config import DEFAULT_CONFIG
from splitter import split_episodes, split_md_files, Episode
from parsers import parse_uploaded
from parsers.md_parser import parse_md
from parsers.xlsx_parser import parse_xlsx as parse_xlsx_file
from aggregator import aggregate_locations
from canonicalizer import canonicalize_locations, canonicalize_characters
from exporters.md_exporter import export_locations_md, export_characters_md
from exporters.json_exporter import export_locations_json, export_characters_json
from exporters.xlsx_exporter import export_xlsx
from extractors.location_extractor import extract_locations
from extractors.character_extractor import extract_characters

# ──────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────
st.set_page_config(page_title="场景 & 角色提取器", page_icon="🎬", layout="wide")
st.title("🎬 场景 & 角色提取器")
st.caption("上传剧本文件 → 自动提取场景库 + 角色库 → 下载 MD / JSON / XLSX")

# ──────────────────────────────────────────────
# Sidebar config
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 设置")

    env_key = (
        st.secrets.get("ANTHROPIC_API_KEY", "")
        if hasattr(st, "secrets") and "ANTHROPIC_API_KEY" in st.secrets
        else os.environ.get("ANTHROPIC_API_KEY", "")
    )
    if env_key:
        api_key = env_key
        st.success("API Key ✅")
    else:
        api_key = st.text_input(
            "Claude API Key",
            type="password",
            help="或设置环境变量 ANTHROPIC_API_KEY 后重启",
        )

    model = st.selectbox(
        "模型",
        ["claude-sonnet-4-20250514", "claude-opus-4-20250514"],
        index=0,
    )

    batch_size = st.number_input("每 batch 集数", min_value=1, max_value=30, value=10)
    max_concurrent = st.number_input("最大并行数", min_value=1, max_value=10, value=5)

    st.divider()
    st.subheader("提取内容")
    do_locations = st.checkbox("场景提取", value=True)
    do_characters = st.checkbox("角色提取", value=True)

# ──────────────────────────────────────────────
# Main area — file upload
# ──────────────────────────────────────────────
st.subheader("📎 上传剧本文件")
uploaded_files = st.file_uploader(
    "支持 PDF / FDX / MD（可多文件）",
    type=["pdf", "fdx", "md"],
    accept_multiple_files=True,
    help="如果是已拆分的 MD 文件，一次性上传所有集",
)

st.subheader("📎 上传参考文档（可选）")
ref_file = st.file_uploader(
    "Loop Sheet / 已有场景表（XLSX/MD），用于辅助标准化命名",
    type=["xlsx", "md"],
    accept_multiple_files=False,
    key="ref_upload",
)

col1, col2 = st.columns(2)
with col1:
    show_title = st.text_input("剧名", placeholder="e.g. Veronica's Sinister Spell")
with col2:
    ep_offset = st.number_input(
        "集数偏移",
        value=-1,
        help="文件名数字与实际集数的差值。如 2.md=第1集 → 偏移为 -1",
    )

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def parse_all_uploads(files) -> list[Episode]:
    """Parse uploaded files and split into episodes."""
    if not files:
        return []

    # If multiple MD files → treat as pre-split episodes
    md_files = [f for f in files if f.name.endswith(".md")]
    if len(md_files) > 1:
        file_texts = {}
        for f in md_files:
            file_texts[f.name] = f.getvalue().decode("utf-8")
        return split_md_files(file_texts, offset=int(ep_offset))

    # Single file or mixed — parse and split
    all_text = []
    for f in files:
        text = parse_uploaded(f.name, f.getvalue())
        all_text.append(text)

    combined = "\n\n".join(all_text)
    return split_episodes(combined)


def parse_ref_locations(ref) -> list[str] | None:
    """Extract location names from reference file."""
    if not ref:
        return None
    try:
        if ref.name.endswith(".xlsx"):
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp.write(ref.getvalue())
                tmp.flush()
                text = parse_xlsx_file(tmp.name)
            os.unlink(tmp.name)
        else:
            text = ref.getvalue().decode("utf-8")
        # Extract lines that look like location names (non-empty, short)
        names = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) < 80]
        return names[:100] if names else None
    except Exception:
        return None


async def run_pipeline(episodes, api_key, model, batch_size, max_concurrent,
                       do_loc, do_char, ref_locs, title):
    """Run the full extraction pipeline."""
    results = {}

    if do_loc:
        st.write("**场景提取中...**")
        loc_progress = st.progress(0, text="场景提取 0/?")

        def loc_cb(batch_idx, total, batch_result):
            if total > 0:
                loc_progress.progress(
                    batch_idx / total,
                    text=f"场景提取 {batch_idx}/{total}"
                    + (f" ✅ {len(batch_result)} scenes" if batch_result else " ❌ 失败"),
                )

        scenes, loc_errors = await extract_locations(
            episodes, api_key, model, batch_size, max_concurrent,
            ref_locations=ref_locs, progress_callback=loc_cb,
        )
        loc_progress.progress(1.0, text=f"场景提取完成 — {len(scenes)} 条")

        if loc_errors:
            st.warning(f"场景提取有 {len(loc_errors)} 个 batch 失败: {loc_errors}")

        # Canonicalize
        st.write("**场景标准化中...**")
        raw_names = list(set(s["location_raw"] for s in scenes if not s.get("continuation_only")))
        try:
            canon_map = await canonicalize_locations(raw_names, api_key, model)
        except Exception as e:
            st.warning(f"标准化失败，使用原名: {e}")
            canon_map = None

        # Aggregate
        groups_ordered, groups_raw = aggregate_locations(scenes, canon_map)

        results["scenes"] = scenes
        results["canon_map"] = canon_map
        results["groups_ordered"] = groups_ordered
        results["groups_raw"] = groups_raw
        results["loc_errors"] = loc_errors

    if do_char:
        st.write("**角色提取中...**")
        char_progress = st.progress(0, text="角色提取 0/?")

        def char_cb(batch_idx, total, batch_result):
            if batch_idx == -1:
                char_progress.progress(0.9, text="角色合并去重中...")
            elif total > 0:
                char_progress.progress(
                    batch_idx / total * 0.85,
                    text=f"角色提取 {batch_idx}/{total}"
                    + (f" ✅ {len(batch_result)} chars" if batch_result else " ❌ 失败"),
                )

        characters, char_errors = await extract_characters(
            episodes, api_key, model, batch_size, max_concurrent,
            progress_callback=char_cb,
        )
        char_progress.progress(1.0, text=f"角色提取完成 — {len(characters)} 个角色")

        if char_errors:
            st.warning(f"角色提取有错误: {char_errors}")

        results["characters"] = characters
        results["char_errors"] = char_errors

    return results


# ──────────────────────────────────────────────
# Main action
# ──────────────────────────────────────────────

if uploaded_files:
    episodes = parse_all_uploads(uploaded_files)
    if episodes:
        st.success(f"✅ 文件解析完成 — 检测到 **{len(episodes)} 集**（E{episodes[0].number} ~ E{episodes[-1].number}）")
    else:
        st.error("❌ 未检测到有效集数内容")
        st.stop()

    if st.button("🚀 开始提取", type="primary", disabled=not api_key):
        if not api_key:
            st.error("请在侧边栏填写 API Key")
            st.stop()

        ref_locs = parse_ref_locations(ref_file)

        results = asyncio.run(run_pipeline(
            episodes, api_key, model, batch_size, max_concurrent,
            do_locations, do_characters, ref_locs, show_title,
        ))

        st.session_state["results"] = results
        st.session_state["title"] = show_title

# ──────────────────────────────────────────────
# Preview & Download
# ──────────────────────────────────────────────

if "results" in st.session_state:
    results = st.session_state["results"]
    title = st.session_state.get("title", "")

    st.divider()
    st.subheader("📋 预览")

    tabs = []
    tab_labels = []
    if "groups_ordered" in results:
        tab_labels.append("场景库")
    if "characters" in results:
        tab_labels.append("角色库")

    if tab_labels:
        tabs = st.tabs(tab_labels)

    tab_idx = 0
    loc_md = ""
    loc_json = ""
    char_md = ""
    char_json = ""

    if "groups_ordered" in results:
        with tabs[tab_idx]:
            loc_md = export_locations_md(results["groups_ordered"], results["groups_raw"], title)
            loc_json = export_locations_json(results["groups_ordered"], results["groups_raw"])
            st.markdown(loc_md)
        tab_idx += 1

    if "characters" in results:
        with tabs[tab_idx]:
            char_md = export_characters_md(results["characters"], title)
            char_json = export_characters_json(results["characters"])
            st.markdown(char_md)

    # Download section
    st.divider()
    st.subheader("📥 下载")

    dl_cols = st.columns(3)

    # MD downloads
    with dl_cols[0]:
        if loc_md:
            st.download_button(
                "📥 场景库 MD",
                loc_md,
                file_name=f"{title or 'Locations'}_Extracted.md",
                mime="text/markdown",
            )
        if char_md:
            st.download_button(
                "📥 角色库 MD",
                char_md,
                file_name=f"{title or 'Characters'}_Extracted.md",
                mime="text/markdown",
            )

    # JSON downloads
    with dl_cols[1]:
        if loc_json:
            st.download_button(
                "📥 场景库 JSON",
                loc_json,
                file_name=f"{title or 'Locations'}_Extracted.json",
                mime="application/json",
            )
        if char_json:
            st.download_button(
                "📥 角色库 JSON",
                char_json,
                file_name=f"{title or 'Characters'}_Extracted.json",
                mime="application/json",
            )

    # XLSX download
    with dl_cols[2]:
        xlsx_data = export_xlsx(
            groups_ordered=results.get("groups_ordered"),
            groups_raw=results.get("groups_raw"),
            characters=results.get("characters"),
        )
        if xlsx_data:
            st.download_button(
                "📥 XLSX（场景+角色）",
                xlsx_data,
                file_name=f"{title or 'Extraction'}_Result.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
