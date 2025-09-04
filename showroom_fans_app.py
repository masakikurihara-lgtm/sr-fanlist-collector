import streamlit as st
import requests
import pandas as pd
import zipfile
import os
import tempfile
from datetime import datetime

# ページ設定
st.set_page_config(page_title="SHOWROOM データ取得ツール", layout="centered")

# --- CSS カスタマイズ（スマホ対応＆余白調整） ---
st.markdown("""
    <style>
    h1, h2, h3 { font-size: clamp(18px, 4vw, 28px); }
    .nowrap { white-space: nowrap; }
    .spacer { margin-top: 2em; }
    .month-block:nth-child(odd) {
        background-color: #f9f9f9;
        padding: 1em;
        border-radius: 10px;
    }
    .month-block:nth-child(even) {
        background-color: #eef6ff;
        padding: 1em;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 入力欄 ---
st.title("SHOWROOM データ取得ツール")

col1, col2 = st.columns([2, 1])
with col1:
    room_id = st.text_input("ルームIDを入力してください")
with col2:
    st.markdown('<div class="nowrap">例：481475</div>', unsafe_allow_html=True)

# --- 月リストの準備（最新を上に） ---
months = pd.date_range("2023-01-01", datetime.today(), freq="MS").strftime("%Y-%m").tolist()[::-1]
selected_months = st.multiselect("取得したい月を選択してください", months)

# --- データ取得処理 ---
def fetch_month_data(room_id, month):
    # APIやスクレイピング処理の代わりにダミーデータ生成
    data = [
        {"avatar_id": 1, "level": 10, "title_id": 2, "user_id": "u001", "user_name": "Alice"},
        {"avatar_id": 2, "level": 6,  "title_id": 1, "user_id": "u002", "user_name": "Bob"},
        {"avatar_id": 3, "level": 3,  "title_id": 0, "user_id": "u003", "user_name": "Carol"},
    ]
    df = pd.DataFrame(data)
    return df

# --- 実行ボタン ---
st.markdown('<div class="spacer"></div>', unsafe_allow_html=True)
if st.button("データ取得 & ZIP作成", use_container_width=False):
    if not room_id or not selected_months:
        st.warning("ルームIDと月を選択してください。")
    else:
        with st.spinner("データ取得中..."):
            temp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(temp_dir, "showroom_data.zip")
            all_data = []

            with zipfile.ZipFile(zip_path, "w") as zipf:
                # --- 各月のCSVを順番に格納 ---
                for month in selected_months:
                    df = fetch_month_data(room_id, month)
                    all_data.append(df)

                    file_path = os.path.join(temp_dir, f"data_{month}.csv")
                    # 列順を統一して保存
                    df = df[["avatar_id", "level", "title_id", "user_id", "user_name"]]
                    df.to_csv(file_path, index=False, encoding="utf-8-sig")
                    zipf.write(file_path, arcname=f"data_{month}.csv")

                # --- 集計処理を最後に格納 ---
                if all_data:
                    merged_df = pd.concat(all_data, ignore_index=True)

                    grouped = (
                        merged_df.groupby("user_id", as_index=False)
                        .agg({
                            "avatar_id": "first",
                            "user_name": "first",
                            "level": "sum"
                        })
                    )

                    grouped["title_id"] = (grouped["level"] // 5).astype(int)
                    grouped = grouped.sort_values("level", ascending=False)

                    # 列順を月ファイルと揃える
                    grouped = grouped[["avatar_id", "level", "title_id", "user_id", "user_name"]]

                    merged_csv_path = os.path.join(temp_dir, "merged_data.csv")
                    grouped.to_csv(merged_csv_path, index=False, encoding="utf-8-sig")
                    zipf.write(merged_csv_path, arcname="merged_data.csv")

        st.success("データ取得完了！")
        st.markdown('<div class="spacer"></div>', unsafe_allow_html=True)
        with open(zip_path, "rb") as f:
            st.download_button("ZIPをダウンロード", f, file_name="showroom_data.zip", mime="application/zip")

        # 集計結果を画面にプレビュー
        if all_data:
            st.markdown("### 集計結果プレビュー（上位20件）")
            st.dataframe(grouped.head(20))
