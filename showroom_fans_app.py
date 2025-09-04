import streamlit as st
import requests
import pandas as pd
from io import BytesIO
from zipfile import ZipFile
from datetime import datetime
import time

st.set_page_config(page_title="Showroom アクティブファン取得", layout="wide")

st.title("SHOWROOM ファンリスト取得ツール")
st.markdown(
    "ルームIDを入力して、取得したい月を選択してください。取得後は ZIP でまとめてダウンロードできます。"
)

# ルームID入力
room_id = st.text_input("対象のルームIDを入力してください", value="")

# 月の範囲
start_month = 202501
current_month = int(datetime.now().strftime("%Y%m"))
months_list = list(range(start_month, current_month + 1))
month_labels = [str(m) for m in months_list]

# 月選択（複数可） ← 修正①
selected_months = st.multiselect(
    "取得したい月を選択",
    options=month_labels,
    default=[]  # 初期値は空、取得したい月だけチェック
)

# ZIP作成用
zip_buffer = BytesIO()
zip_file = ZipFile(zip_buffer, "w")

# 実行ボタン
if st.button("データ取得 & ZIP作成"):

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

        st.write(f"総ファン数合計: {total_fans_overall}")

        # 月ごとに取得
        for month in selected_months:
            st.subheader(f"{month} の処理")
            month_progress = st.progress(0)
            month_text = st.empty()

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
                    month_text.text(f"{retrieved}/{count} 件取得中…")

                # 全体進捗更新
                processed_fans += len(users)
                overall_progress.progress(min(processed_fans / total_fans_overall, 1.0))
                overall_text.text(
                    f"全体進捗: {processed_fans}/{total_fans_overall} 件 ({processed_fans/total_fans_overall*100:.1f}%)"
                )

                time.sleep(0.05)

            # DataFrameに変換して UTF-8 BOM 付きで保存
            df = pd.DataFrame(fans_data)
            csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
            csv_name = f"active_fans_{room_id}_{month}.csv"
            zip_file.writestr(csv_name, csv_bytes)

            # 修正②：処理完了後に表示を更新
            month_text.text(f"{month} の取得完了 ({len(fans_data)} 件)")
            month_progress.progress(1.0)
            st.success(f"{month} のCSV保存完了 ({len(fans_data)} 件)")

        zip_file.close()
        zip_buffer.seek(0)
        st.download_button(
            label="ZIPをダウンロード",
            data=zip_buffer,
            file_name=f"active_fans_{room_id}.zip",
            mime="application/zip"
        )
