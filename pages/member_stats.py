"""
pages/member_stats.py
統計紀錄頁面：今日/本週/本月/累計，自訂日期區間，每日紀錄。
"""
from datetime import date

import streamlit as st

from modules.rbac import require_permission, P, is_superadmin
from modules.recitation import get_user_items
from modules.statistics import (
    get_item_stats, get_all_items_stats, get_daily_records,
    get_today_range, get_week_range, get_month_range, get_custom_range,
    format_range_label, now_tw,
)
from modules.ui_components import (
    page_header, render_nav, gold_divider, info_box
)


def render(user_doc: dict) -> None:
    user_id = user_doc["id"]
    require_permission(user_id, P.STATS_SELF)
    admin = is_superadmin(user_id)
    render_nav("stats", is_admin=admin)
    page_header("📊 統計紀錄", "以台灣時區計算各項統計")

    items = get_user_items(user_id, include_archived=True)
    if not items:
        info_box("尚無誦經項目，請先新增項目後開始計數。")
        return

    all_stats = get_all_items_stats(user_id)

    # ── 各項目統計表 ──
    st.subheader("各項目統計")

    # 顯示日期區間說明
    today_start, today_end = get_today_range()
    week_start, week_end = get_week_range()
    month_start, month_end = get_month_range()

    st.markdown(f"""
    <div style='font-size:0.95rem;color:#8a7060;margin-bottom:0.8rem'>
    　本日：{format_range_label(today_start, today_end)}　|　
    本週：{format_range_label(week_start, week_end)}　|　
    本月：{format_range_label(month_start, month_end)}
    </div>
    """, unsafe_allow_html=True)

    # 彙總列表
    total_today = total_week = total_month = total_all = 0
    for item in items:
        iid = item["id"]
        s = all_stats.get(iid, {"today": 0, "week": 0, "month": 0, "total": 0})
        total_today += s["today"]
        total_week += s["week"]
        total_month += s["month"]
        total_all += s["total"]

        archived_tag = "（封存中）" if item.get("is_archived") else ""
        with st.container():
            st.markdown(
                f'<div class="card card-gold"><b class="item-name">{item["name"]}</b>'
                f'<span style="color:#8a7060;font-size:0.9rem"> {archived_tag}</span></div>',
                unsafe_allow_html=True,
            )
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("今日", s["today"])
            c2.metric("本週", s["week"])
            c3.metric("本月", s["month"])
            c4.metric("累計", s["total"])

    gold_divider()

    # ── 全部加總 ──
    st.subheader("全部項目加總")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("今日合計", total_today)
    c2.metric("本週合計", total_week)
    c3.metric("本月合計", total_month)
    c4.metric("累計合計", total_all)

    gold_divider()

    # ── 自訂日期區間 ──
    st.subheader("自訂日期區間")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        item_options = {item["name"]: item["id"] for item in items}
        item_options["（全部項目）"] = None
        selected_name = st.selectbox("選擇項目", ["（全部項目）"] + [i["name"] for i in items])
        selected_iid = item_options.get(selected_name)

    with col2:
        start_date = st.date_input("開始日期", value=date.today().replace(day=1))
    with col3:
        end_date = st.date_input("結束日期", value=date.today())

    if st.button("查詢", key="query_range"):
        if start_date > end_date:
            st.error("開始日期不得晚於結束日期。")
        else:
            start_dt, end_dt = get_custom_range(start_date, end_date)
            records = get_daily_records(user_id, selected_iid, start_dt, end_dt)

            st.markdown(
                f"<p style='color:#8a7060'>查詢區間：{format_range_label(start_dt, end_dt)}</p>",
                unsafe_allow_html=True,
            )

            if not records:
                info_box("此區間內無計數紀錄。")
            else:
                # 分組顯示
                from collections import defaultdict
                by_date = defaultdict(int)
                by_date_item = defaultdict(lambda: defaultdict(int))
                item_name_map = {i["id"]: i["name"] for i in items}

                for r in records:
                    ds = r.get("date_str", "")
                    iid = r.get("item_id", "")
                    cnt = r.get("net_count", 0)
                    by_date[ds] += cnt
                    by_date_item[ds][iid] += cnt

                for ds in sorted(by_date.keys()):
                    with st.expander(f"📅 {ds}　合計 {by_date[ds]} 次"):
                        for iid, cnt in by_date_item[ds].items():
                            name = item_name_map.get(iid, iid)
                            st.markdown(
                                f"　<b class='item-name'>{name}</b>：{cnt} 次",
                                unsafe_allow_html=True,
                            )
