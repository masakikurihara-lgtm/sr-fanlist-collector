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

# 月範囲
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

# 月選択と実行ボタンの余白
st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)

# ZIP用バッファ
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
        all_fans_data = []

        # 総ファン数
        for month in selected_months:
            url = f"https://www.showroom-live.com/api/active_fan/users?room_id={room_id}&ym={month}"
            resp = requests.get(url)
            monthly_counts[month] = resp.json().get("count", 0) if resp.status_code == 200 else 0
            total_fans_overall += monthly_counts[month]

        st.markdown(
            f"<div style='background-color:#e5e7eb; padding:10px; border-radius:10px; text-align:center;'>"
            f"<b>総ファン数合計:</b> {total_fans_overall} 件"
            f"</div>",
            unsafe_allow_html=True
        )

        # 月ごと取得
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

                # 月ごと進捗
                if count > 0:
                    month_progress.progress(min(retrieved / count, 1.0))
                    month_text.markdown(
                        f"<p style='font-size:14px; color:#374151;'>{retrieved}/{count} 件取得中…</p>",
                        unsafe_allow_html=True
                    )

                # 全体進捗
                processed_fans += len(users)
                overall_progress.progress(min(processed_fans / total_fans_overall, 1.0))
                overall_text.markdown(
                    f"<p style='font-size:14px; color:#1f2937;'>"
                    f"全体進捗: {processed_fans}/{total_fans_overall} 件 ({processed_fans/total_fans_overall*100:.1f}%)"
                    f"</p>",
                    unsafe_allow_html=True
                )
                time.sleep(0.05)

            # CSV保存
            df = pd.DataFrame(fans_data)
            csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            csv_name = f"active_fans_{room_id}_{month}.csv"
            zip_file.writestr(csv_name, csv_bytes)

            month_text.markdown(
                f"<p style='font-size:14px; color:#10b981;'><b>{month} の取得完了 ({len(fans_data)} 件)</b></p>",
                unsafe_allow_html=True
            )
            month_progress.progress(1.0)

        # マージファイル
        if all_fans_data:
            merge_df = pd.DataFrame(all_fans_data)
            merge_df = merge_df[['avatar_id','level','user_id','user_name']]
            merge_df = merge_df.groupby(['avatar_id','user_id','user_name'], as_index=False).agg({'level':'sum'})
            merge_df['title_id'] = (merge_df['level']//5).astype(int)
            merge_df = merge_df.sort_values(by='level', ascending=False)

            # 表示用
            display_df = merge_df.rename(columns={'level':'レベル合計値','user_name':'ユーザー名'})
            display_df['順位'] = display_df['レベル合計値'].rank(method='min', ascending=False).astype(int)
            display_df = display_df[['順位','avatar_id','レベル合計値','ユーザー名']]
            display_df = display_df[display_df['順位']<=100]

            # マージCSV保存
            merge_csv_bytes = merge_df.copy()
            merge_csv_bytes = merge_csv_bytes[['avatar_id','level','title_id','user_id','user_name']]
            csv_bytes = merge_csv_bytes.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            zip_file.writestr(f"active_fans_{room_id}_merge.csv", csv_bytes)

        zip_file.close()
        zip_buffer.seek(0)

        st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
        st.download_button(
            label="ZIPをダウンロード",
            data=zip_buffer,
            file_name=f"active_fans_{room_id}.zip",
            mime="application/zip"
        )

        # 表示
        if not display_df.empty:
            st.markdown("<h3 style='text-align:center; color:#111827;'>上位100位（マージ集計）</h3>", unsafe_allow_html=True)
            html_table = '''
            <table style="border-collapse: collapse; width: 100%; font-size:14px; margin:0;">
            <thead>
            <tr style="background-color:#f3f4f6;">
            '''
            for col in display_df.columns:
                html_table += f'<th style="border: 1px solid #ddd; padding: 8px; text-align:center;">{col}</th>'
            html_table += '</tr></thead>'
            for _, row in display_df.iterrows():
                html_table += '<tr>'
                for col in display_df.columns:
                    align = 'center' if col != 'ユーザー名' else 'left'
                    html_table += f'<td style="border: 1px solid #ddd; padding: 8px; text-align:{align};">'
                    if col == 'avatar_id':
                        html_table += f'<img src="https://static.showroom-live.com/image/avatar/{row[col]}.png" width="40">'
                    else:
                        html_table += f'{row[col]}'
                    html_table += '</td>'
                html_table += '</tr>'
            html_table += '</table>'
            st.markdown(html_table, unsafe_allow_html=True)
            st.markdown("<p style='text-align:left; font-size:12px; margin-top:4px; margin-bottom:4px;'>※100位まで表示しています</p>", unsafe_allow_html=True)
