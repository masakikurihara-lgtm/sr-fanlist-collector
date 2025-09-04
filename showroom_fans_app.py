import streamlit as st
import requests
import pandas as pd
from io import BytesIO
from zipfile import ZipFile
from datetime import datetime
import time

# ページ設定
st.set_page_config(page_title="SHOWROOM ファンリスト取得", layout="wide")

# タイトル（スマホでもバランス良く調整）
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

st.markdown("---")  # 区切り線

# ルームID入力（helpは使わず、ラベルに例を直接記載）
room_id = st.text_input(
    "対象のルームID（例：481475）",
    value=""
)

# 月の範囲（最新月が上に来る）
start_month = 202501
current_month = int(datetime.now().strftime("%Y%m"))
months_list = list(range(start_month, current_month + 1))
months_list.reverse()  # 最新月が先頭
month_labels = [str(m) for m in months_list]

# 月選択（複数可、チェック式）
selected_months = st.multiselect(
    "取得したい月を選択",
    options=month_labels,
    default=[]
)

# ZIP作成用バッファ
zip_buffer = BytesIO()
zip_file = ZipFile(zip_buffer, "w")

# 実行ボタン（左寄せに修正）
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

        # 総ファン数合計
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

        # 月ごとに取得
        for idx, month in enumerate(selected_months):
            # 月ごとの背景色（交互）
            bg_color = "#f9fafb" if idx % 2 == 0 else "#e0f2fe"

            st.markdown(
                f"<div style='background-color:{bg_color}; padding:15px; border-radius:10px; margin-bottom:10px;'>"
                f"<h2 style='font-size:20px; color:#111827;'>{month} の処理</h2>"
                f"</div>",
                unsafe_allow_html=True
            )

            # 進捗表示
            col_text, col_bar = st.columns([3, 1])
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
                retrieved += len(users)

                # 月ごと進捗更新
                if count > 0:
                    month_progress.progress(min(retrieved / count, 1.0))
                    month_text.markdown(
                        f"<p style='font-size:14px; color:#374151;'>{retrieved}/{count} 件取得中…</p>",
                        unsafe_allow_html=True
                    )

                # 全体進捗更新
                processed_fans += len(users)
                overall_progress.progress(min(processed_fans / total_fans_overall, 1.0))
                overall_text.markdown(
                    f"<p style='font-size:14px; color:#1f2937;'>"
                    f"全体進捗: {processed_fans}/{total_fans_overall} 件 ({processed_fans/total_fans_overall*100:.1f}%)"
                    f"</p>",
                    unsafe_allow_html=True
                )

                time.sleep(0.05)

            # DataFrameに変換して UTF-8 BOM 付きで保存
            df = pd.DataFrame(fans_data)
            csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            csv_name = f"active_fans_{room_id}_{month}.csv"
            zip_file.writestr(csv_name, csv_bytes)

            # 月処理完了表示
            month_text.markdown(
                f"<p style='font-size:14px; color:#10b981;'><b>{month} の取得完了 ({len(fans_data)} 件)</b></p>",
                unsafe_allow_html=True
            )
            month_progress.progress(1.0)

        zip_file.close()
        zip_buffer.seek(0)

        st.download_button(
            label="ZIPをダウンロード",
            data=zip_buffer,
            file_name=f"active_fans_{room_id}.zip",
            mime="application/zip"
        )
