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
room_id = st.text_input("対象のルームID（例：481475）", value="")

# 月の範囲（最新月が上に来る）
start_month = 202501
current_month = int(datetime.now().strftime("%Y%m"))
months_list = list(range(start_month, current_month + 1))
months_list.reverse()
month_labels = [str(m) for m in months_list]

# 月選択
selected_months = st.multiselect("取得したい月を選択", options=month_labels, default=[])

# 月選択と実行ボタンの間に余白
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

        # 各月の総ファン数を取得
        for month in selected_months:
            url = f"https://www.showroom-live.com/api/active_fan/users?room_id={room_id}&ym={month}"
            resp = requests.get(url)
            if resp.status_code == 200:
                data = resp.json()
                monthly_counts[month] = data.get("count", 0)
                total_fans_overall += monthly_counts[month]
            else:
                monthly_counts[month] = 0

        # 各月のデータ取得
        all_fans_data = []  # マージ用
        for idx, month in enumerate(selected_months):
            bg_color = "#f9fafb" if idx % 2 == 0 else "#e0f2fe"
            st.markdown(
                f"<div style='background-color:{bg_color}; padding:15px; border-radius:10px; margin-bottom:10px;'>"
                f"<h2 style='font-size:20px; color:#111827;'>{month} の処理</h2>"
                f"</div>",
                unsafe_allow_html=True
            )

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
                all_fans_data.extend(users)
                retrieved += len(users)

                if count > 0:
                    month_progress.progress(min(retrieved / count, 1.0))
                    month_text.markdown(
                        f"<p style='font-size:14px; color:#374151;'>{retrieved}/{count} 件取得中…</p>",
                        unsafe_allow_html=True
                    )

                processed_fans += len(users)
                overall_progress.progress(min(processed_fans / total_fans_overall, 1.0))
                overall_text.markdown(
                    f"<p style='font-size:14px; color:#1f2937;'>"
                    f"全体進捗: {processed_fans}/{total_fans_overall} 件 ({processed_fans/total_fans_overall*100:.1f}%)"
                    f"</p>",
                    unsafe_allow_html=True
                )
                time.sleep(0.05)

            # 月別CSV作成
            df = pd.DataFrame(fans_data)
            csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            csv_name = f"active_fans_{room_id}_{month}.csv"
            zip_file.writestr(csv_name, csv_bytes)

            month_text.markdown(
                f"<p style='font-size:14px; color:#10b981;'><b>{month} の取得完了 ({len(fans_data)} 件)</b></p>",
                unsafe_allow_html=True
            )
            month_progress.progress(1.0)

        # ---------- マージCSV作成 ----------
        if all_fans_data:
            st.markdown(
                f"<div style='background-color:#f3f4f6; padding:10px; border-radius:10px; margin-bottom:10px;'>"
                f"<h2 style='font-size:20px; color:#111827;'>マージファイル作成中…</h2>"
                f"</div>",
                unsafe_allow_html=True
            )
            merge_progress = st.progress(0)
            merge_text = st.empty()

            # ユーザーごとにlevel合計して集計
            merge_df = pd.DataFrame(all_fans_data)
            agg_df = merge_df.groupby(['avatar_id','user_id','user_name'], as_index=False)['level'].sum()
            agg_df['title_id'] = (agg_df['level'] // 5).astype(int)
            agg_df = agg_df.sort_values(by=['level','user_name'], ascending=[False, True]).reset_index(drop=True)

            # マージCSV作成（1行ずつ進捗表示）
            merge_csv_rows = len(agg_df)
            merge_csv_bytes_list = []
            for i, row in agg_df.iterrows():
                temp_df = pd.DataFrame([row])
                merge_csv_bytes_list.append(temp_df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"))
                merge_progress.progress((i+1)/merge_csv_rows)
                merge_text.markdown(
                    f"<p style='font-size:14px; color:#374151;'>{i+1}/{merge_csv_rows} 件マージ中…</p>",
                    unsafe_allow_html=True
                )
                time.sleep(0.01)

            merge_csv_bytes = b"".join(merge_csv_bytes_list)
            merge_csv_name = f"active_fans_{room_id}_merge.csv"
            zip_file.writestr(merge_csv_name, merge_csv_bytes)

        zip_file.close()
        zip_buffer.seek(0)

        # ZIPダウンロード
        st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
        st.download_button(
            label="ZIPをダウンロード",
            data=zip_buffer,
            file_name=f"active_fans_{room_id}.zip",
            mime="application/zip"
        )

        # ---------- マージ集計表示（上位100位） ----------
        if all_fans_data:
            # 上位100位のみ抽出
            agg_df = merge_df.groupby(['avatar_id','user_id','user_name'], as_index=False)['level'].sum()
            agg_df = agg_df.sort_values(by=['level','user_name'], ascending=[False, True]).reset_index(drop=True)

            agg_df['順位'] = 0
            last_level = None
            rank = 0
            for i, row in agg_df.iterrows():
                if row['level'] != last_level:
                    rank = i+1
                    last_level = row['level']
                agg_df.at[i,'順位'] = rank
            agg_df = agg_df[agg_df['順位'] <= 100]

            display_df = agg_df[['順位','avatar_id','level','user_name']]
            display_df.rename(columns={
                'avatar_id':'アバター',
                'level':'レベル合計値',
                'user_name':'ユーザー名'
            }, inplace=True)

            # 表示タイトル
            st.markdown(
                "<h3 style='text-align:center; color:#111827; margin-top:0; margin-bottom:4px; line-height:1.2; font-size:18px;'>"
                "マージ集計（上位100位）</h3>",
                unsafe_allow_html=True
            )

            # HTML表作成
            table_html = "<table style='width:100%; border-collapse:collapse;'>"
            table_html += "<thead><tr style='background-color:#f3f4f6;'>"
            for col in display_df.columns:
                table_html += f"<th style='border-bottom:1px solid #ccc; padding:4px; text-align:center;'>{col}</th>"
            table_html += "</tr></thead><tbody>"
            for idx,row in display_df.iterrows():
                table_html += "<tr>"
                table_html += f"<td style='text-align:center;'>{row['順位']}</td>"
                table_html += f"<td style='text-align:center;'><img src='https://static.showroom-live.com/image/avatar/{row['アバター']}.png' width='40'></td>"
                table_html += f"<td style='text-align:center;'>{row['レベル合計値']}</td>"
                table_html += f"<td style='text-align:left; padding-left:8px;'>{row['ユーザー名']}</td>"
                table_html += "</tr>"
            table_html += "</tbody></table>"

            st.markdown(table_html, unsafe_allow_html=True)
            st.markdown("<p style='font-size:12px; text-align:left; margin-top:4px;'>※100位まで表示しています</p>", unsafe_allow_html=True)
