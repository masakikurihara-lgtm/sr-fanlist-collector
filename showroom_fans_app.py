import streamlit as st
import requests
import pandas as pd
from io import BytesIO
from zipfile import ZipFile
from datetime import datetime
import time
import logging
import io
from dateutil.relativedelta import relativedelta

# ページ設定
st.set_page_config(page_title="SHOWROOM ファンリスト取得", layout="wide")

# ----- ▼ここから追加▼ -----
# 認証用のルームリストURL
ROOM_LIST_URL = "https://mksoul-pro.com/showroom/file/room_list.csv"
# ----- ▲ここまで追加▲ -----

if "authenticated" not in st.session_state:  #認証用
    st.session_state.authenticated = False  #認証用

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


# ▼▼ 認証ステップ ▼▼
if not st.session_state.authenticated:
    st.markdown("##### 🔑 認証コードを入力してください")
    input_room_id = st.text_input(
        "認証コードを入力してください:",
        placeholder="",
        type="password",
        key="room_id_input"
    )

    # 認証ボタン
    if st.button("認証する"):
        if input_room_id:  # 入力が空でない場合のみ
            try:
                response = requests.get(ROOM_LIST_URL, timeout=5)
                response.raise_for_status()
                room_df = pd.read_csv(io.StringIO(response.text), header=None)

                valid_codes = set(str(x).strip() for x in room_df.iloc[:, 0].dropna())

                if input_room_id.strip() in valid_codes:
                    st.session_state.authenticated = True
                    st.success("✅ 認証に成功しました。ツールを利用できます。")
                    st.rerun()  # 認証成功後に再読み込み
                else:
                    st.error("❌ 認証コードが無効です。正しい認証コードを入力してください。")
            except Exception as e:
                st.error(f"認証リストを取得できませんでした: {e}")
        else:
            st.warning("認証コードを入力してください。")

    # 認証が終わるまで他のUIを描画しない
    st.stop()
# ▲▲ 認証ステップここまで ▲▲


# ルームID入力
room_id = st.text_input("対象のルームID:", placeholder="例: 154851", value="")

# 月の範囲を作成（現在から2025年1月まで遡る）
start_date = datetime(2025, 1, 1)
current_date = datetime.now()

month_labels = []
tmp_date = current_date
while tmp_date >= start_date:
    month_labels.append(tmp_date.strftime("%Y%m"))
    tmp_date -= relativedelta(months=1) # 1ヶ月ずつ遡る

# 月選択
selected_months = st.multiselect("取得したい月を選択（複数選択可）:", options=month_labels, default=[])

# 月選択と実行ボタンの間に余白
st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)

# 実行ボタン（左寄せ）
start_button = st.button("データ取得 & ZIP作成")

if start_button:
    if not room_id or not selected_months:
        st.warning("ルームIDの入力と月の選択を必ず行ってください。")
    else:
        # ----- ▼ここから変更▼ -----
        # 認証チェック
        is_authenticated = False
        try:
            df_room_list = pd.read_csv(ROOM_LIST_URL, header=None)
            # A列（0番目の列）を文字列に変換してリスト化
            auth_ids = df_room_list.iloc[:, 0].astype(str).tolist()
            if room_id in auth_ids:
                is_authenticated = True
            else:
                st.error("指定されたルームIDは認証されていません。")
        except Exception as e:
            st.error(f"認証リストの取得に失敗しました。管理者にご確認ください。 (Error: {e})")

        # 認証成功時のみ後続の処理を実行
        if is_authenticated:
        # ----- ▲ここまで変更▲ -----
            st.info(f"{len(selected_months)}か月分のデータを取得します。")
            monthly_counts = {}
            overall_progress = st.progress(0)
            overall_text = st.empty()
            processed_fans = 0
            total_fans_overall = 0

            # ZIPバッファ
            zip_buffer = BytesIO()
            zip_file = ZipFile(zip_buffer, "w")

            # 総ファン数（マージ用）
            for month in selected_months:
                url = f"https://www.showroom-live.com/api/active_fan/users?room_id={room_id}&ym={month}"
                resp = requests.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    monthly_counts[month] = data.get("count", 0)
                    total_fans_overall += monthly_counts[month]
                else:
                    monthly_counts[month] = 0

            # 月ごとの取得
            all_fans_data = []  # マージ用
            orig_order_counter = 0  # 取得順を付与
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
                    # 取得順を付与
                    for u in users:
                        u['orig_order'] = orig_order_counter
                        orig_order_counter += 1
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
                    if total_fans_overall > 0:
                        overall_progress.progress(min(processed_fans / total_fans_overall, 1.0))
                        overall_text.markdown(
                            f"<p style='font-size:14px; color:#1f2937;'>"
                            f"全体進捗: {processed_fans}/{total_fans_overall} 件 ({processed_fans/total_fans_overall*100:.1f}%)"
                            f"</p>",
                            unsafe_allow_html=True
                        )

                    time.sleep(0.05)

                # CSV作成（各月）
                if fans_data:
                    df = pd.DataFrame(fans_data)
                    df = df[['avatar_id','level','title_id','user_id','user_name']]  # 列順維持
                    csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                    csv_name = f"active_fans_{room_id}_{month}.csv"
                    zip_file.writestr(csv_name, csv_bytes)

                month_text.markdown(
                    f"<p style='font-size:14px; color:#10b981;'><b>{month} の取得完了 ({len(fans_data)} 件)</b></p>",
                    unsafe_allow_html=True
                )
                month_progress.progress(1.0)

            # ---------- マージCSV作成（画面表示とCSV作成） ----------
            agg_df = None
            if all_fans_data:
                st.markdown(
                    f"<div style='background-color:#f3f4f6; padding:10px; border-radius:10px; margin-bottom:10px;'>"
                    f"<h2 style='font-size:20px; color:#111827;'>マージファイル作成処理</h2>"
                    f"<p style='font-size:12px; color:#dc2626; font-weight:bold; margin-top:0;'>※退会ユーザーはマージデータには含まれません</p>"
                    f"</div>",
                    unsafe_allow_html=True
                )
                merge_progress = st.progress(0)
                merge_text = st.empty()

                # マージ集計（ユーザーIDのみをキー、最新月のアバター・ユーザーネームを使用）
                merge_df = pd.DataFrame(all_fans_data)
                # 最新月順（処理順の逆）で並び替え
                merge_df = merge_df.iloc[::-1]
                agg_df = merge_df.groupby('user_id', as_index=False).agg({
                    'level': 'sum',
                    'avatar_id': 'first',  # 逆順にしているので first が最新月の値
                    'user_name': 'first',
                    'orig_order': 'first'
                })
                agg_df['title_id'] = (agg_df['level'] // 5).astype(int)
                agg_df = agg_df[['avatar_id','level','title_id','user_id','user_name','orig_order']]
                # ソート: レベル降順 + 取得順
                agg_df = agg_df.sort_values(by=['level','orig_order'], ascending=[False, True]).reset_index(drop=True)

                # CSV書き込み
                merge_csv_bytes = agg_df.drop(columns='orig_order').to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                merge_csv_name = f"active_fans_{room_id}_merge.csv"
                zip_file.writestr(merge_csv_name, merge_csv_bytes)

                merge_progress.progress(1.0)
                merge_text.markdown(
                    f"<p style='font-size:14px; color:#10b981;'><b>マージCSV作成完了 ({len(agg_df)} 件)</b></p>",
                    unsafe_allow_html=True
                )

            zip_file.close()
            zip_buffer.seek(0)

            # ZIPダウンロード（データがある場合のみ表示）
            if all_fans_data:
                st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)
                st.download_button(
                    label="ZIPをダウンロード",
                    data=zip_buffer,
                    file_name=f"active_fans_{room_id}.zip",
                    mime="application/zip",
                    key="zip_download"
                )
            else:
                st.warning("該当データがありませんでした。")

            # ---------- マージ集計表示（画面） ----------
            if agg_df is not None and not agg_df.empty:
                display_df = agg_df.copy()
                display_df['順位'] = 0
                last_level = None
                rank = 0
                for i, row in display_df.iterrows():
                    if row['level'] != last_level:
                        rank = i + 1
                        last_level = row['level']
                    display_df.at[i, '順位'] = rank
                display_df = display_df[display_df['順位'] <= 100]

                display_df = display_df[['順位','avatar_id','level','user_name']]
                display_df.rename(columns={
                    'avatar_id': 'アバター',
                    'level': 'レベル合計値',
                    'user_name': 'ユーザー名'
                }, inplace=True)

                st.markdown(
                    "<h3 style='text-align:center; color:#111827; margin-top:0; margin-bottom:4px; line-height:1.2; font-size:18px;'>"
                    "マージ集計（上位100位）</h3>",
                    unsafe_allow_html=True
                )

                table_html = "<table style='width:100%; border-collapse:collapse;'>"
                table_html += "<thead><tr style='background-color:#f3f4f6;'>"
                for col in display_df.columns:
                    table_html += f"<th style='border-bottom:1px solid #ccc; padding:4px; text-align:center;'>{col}</th>"
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
                st.markdown("<p style='font-size:12px; text-align:left; margin-top:4px;'>※100位まで表示しています</p>", unsafe_allow_html=True)