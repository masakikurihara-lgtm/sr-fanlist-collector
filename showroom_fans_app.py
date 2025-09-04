import streamlit as st
import requests
import pandas as pd
from io import BytesIO
from zipfile import ZipFile
from datetime import datetime
import time

# ページ設定
st.set_page_config(page_title="SHOWROOM ファンリスト取得", layout="wide")

# タイトル
st.markdown(
    "<h1 style='font-size:28px; text-align:center; color:#1f2937;'>SHOWROOM ファンリスト取得ツール</h1>",
    unsafe_allow_html=True
)

# 説明文
st.markdown(
    "<p style='font-size:16px; text-align:center; color:#4b5563;'>"
    "ルームIDを入力して、取得したい月を選択してください。取得後は ZIP でまとめてダウンロードできます。"
    "</p>",
    unsafe_allow_html=True
)

st.markdown("---")

# ルームID入力
room_id = st.text_input(
    "対象のルームID（例：481475）",
    value=""
)

# 月の範囲（最新月上）
start_month = 202501
current_month = int(datetime.now().strftime("%Y%m"))
months_list = list(range(start_month, current_month + 1))
months_list.reverse()
month_labels = [str(m) for m in months_list]

# 月選択
selected_months = st.multiselect(
    "取得したい月を選択",
    options=month_labels,
    default=[]
)

# 月選択とボタンの間に余白
st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)

# ZIPバッファ
zip_buffer = BytesIO()
zip_file = ZipFile(zip_buffer, "w")

# 実行ボタン
start_button = st.button("データ取得 & ZIP作成")

if start_button:

    if not room_id or not selected_months:
        st.warning("ルームIDと月を必ず選択してください。")
    else:
        st.info(f"{len(selected_months)}か月分のデータを取得します。")

        monthly_counts = {}
        overall_progress = st.progress(0)
        overall_text = st.empty()
        processed_fans = 0
        total_fans_overall = 0

        # 総ファン数
        for month in selected_months:
            url = f"https://www.showroom-live.com/api/active_fan/users?room_id={room_id}&ym={month}"
            resp = requests.get(url)
            if resp.status_code == 200:
                data = resp.json()
                monthly_counts[month] = data.get("count", 0)
                total_fans_overall += monthly_counts[month]
            else:
                monthly_counts[month] = 0

        st.markdown(
            f"<div style='background-color:#e5e7eb; padding:10px; border-radius:10px; text-align:center;'>"
            f"<b>総ファン数合計:</b> {total_fans_overall} 件"
            f"</div>",
            unsafe_allow_html=True
        )

        all_fans_data = []

        # 月ごとに取得
        for idx, month in enumerate(selected_months):
            bg_color = "#f9fafb" if idx % 2 == 0 else "#e0f2fe"

            st.markdown(
                f"<div style='background-color:{bg_color}; padding:15px; border-radius:10px; margin-bottom:10px;'>"
                f"<h2 style='font-size:20px; color:#111827;'>{month} の処理</h2>"
                f"</div>",
                unsafe_allow_html=True
            )

            col_text, col_bar = st.columns([3,1])
            with col_text:
                month_text = st.empty()
            with col_bar:
                month_progress = st.progress(0)

            fans_data = []
            count = monthly_counts[month]
            per_page = 50
            retrieved = 0

            while retrieved < count:
                url = f"https://www.showroom-live.com/api/active_fan/users?room_id={room_id}&ym={month}&offset={retrieved}&limit={per_page}"
                resp = requests.get(url)
                if resp.status_code != 200:
                    st.error(f"{month} の取得でエラー発生")
                    break
                data = resp.json()
                users = data.get("users", [])
                fans_data.extend(users)
                all_fans_data.extend(users)
                retrieved += len(users)

                if count > 0:
                    month_progress.progress(min(retrieved/count,1.0))
                    month_text.markdown(
                        f"<p style='font-size:14px; color:#374151;'>{retrieved}/{count} 件取得中…</p>",
                        unsafe_allow_html=True
                    )

                processed_fans += len(users)
                overall_progress.progress(min(processed_fans/total_fans_overall,1.0))
                overall_text.markdown(
                    f"<p style='font-size:14px; color:#1f2937;'>全体進捗: {processed_fans}/{total_fans_overall} 件 ({processed_fans/total_fans_overall*100:.1f}%)</p>",
                    unsafe_allow_html=True
                )
                time.sleep(0.05)

            df = pd.DataFrame(fans_data)
            csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            csv_name = f"active_fans_{room_id}_{month}.csv"
            zip_file.writestr(csv_name, csv_bytes)

            month_text.markdown(
                f"<p style='font-size:14px; color:#10b981;'><b>{month} の取得完了 ({len(fans_data)} 件)</b></p>",
                unsafe_allow_html=True
            )
            month_progress.progress(1.0)

        # マージ集計
        merge_df = pd.DataFrame(all_fans_data)
        if not merge_df.empty:
            merge_df = merge_df.groupby(['user_id','user_name','avatar_id'], as_index=False).agg({'level':'sum'})
            merge_df['title_id'] = (merge_df['level']//5).astype(int)
            merge_df = merge_df.sort_values(by='level', ascending=False)
            merge_df = merge_df[['avatar_id','level','title_id','user_id','user_name']]

            merge_csv_bytes = merge_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            zip_file.writestr(f"active_fans_{room_id}_merge.csv", merge_csv_bytes)

        zip_file.close()
        zip_buffer.seek(0)

        # ZIPダウンロード前に余白
        st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
        st.download_button(
            label="ZIPをダウンロード",
            data=zip_buffer,
            file_name=f"active_fans_{room_id}.zip",
            mime="application/zip"
        )

        # --- マージ集計上位100位表示 ---
        if not merge_df.empty:
            display_df = merge_df[['avatar_id','level','user_name']].copy()
            display_df = display_df.rename(columns={
                'avatar_id':'アバター',
                'level':'レベル合計値',
                'user_name':'ユーザー名'
            })
            display_df['順位'] = 0
            last_level = None
            rank = 0
            for i, row in enumerate(display_df.itertuples()):
                if last_level != row._2:
                    rank = i+1
                    last_level = row._2
                display_df.at[i,'順位'] = rank
            display_df = display_df[display_df['順位']<=100]

            st.markdown("<h3 style='font-size:16px; color:#111827; margin-top:16px;'>マージ集計（上位100位）</h3>", unsafe_allow_html=True)

            table_html = "<table style='width:100%; border-collapse:collapse;'>"
            table_html += "<thead><tr>"
            for col in ['順位','アバター','レベル合計値','ユーザー名']:
                table_html += (
                    f"<th style='border-bottom:1px solid #ccc; padding:4px; "
                    f"text-align:center; background-color:#f3f4f6;'>{col}</th>"
                )
            table_html += "</tr></thead><tbody>"

            for idx, row in display_df.iterrows():
                table_html += "<tr>"
                table_html += f"<td style='text-align:center;'>{row['順位']}</td>"
                table_html += f"<td style='text-align:center;'><img src='https://static.showroom-live.com/image/avatar/{row['アバター']}.png' width='40'></td>"
                table_html += f"<td style='text-align:center;'>{row['レベル合計値']}</td>"
                table_html += f"<td style='text-align:left; padding-left:8px;'>{row['ユーザー名']}</td>"
                table_html += "</tr>"
            table_html += "</tbody></table>"

            st.markdown(table_html, unsafe_allow_html=True)
            st.markdown(
                "<p style='font-size:12px; text-align:left; margin-top:4px;'>※100位まで表示しています</p>",
                unsafe_allow_html=True
            )
