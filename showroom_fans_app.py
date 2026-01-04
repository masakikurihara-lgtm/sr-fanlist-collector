import streamlit as st
import requests
import pandas as pd
from io import BytesIO
from zipfile import ZipFile
from datetime import datetime
import time
import io
from dateutil.relativedelta import relativedelta

# ページ設定
st.set_page_config(page_title="SHOWROOM ファンデータ分析ツール", layout="wide")

# 認証用のルームリストURL
ROOM_LIST_URL = "https://mksoul-pro.com/showroom/file/room_list.csv"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# タイトル
st.markdown(
    "<h1 style='font-size:28px; text-align:center; color:#1f2937;'>SHOWROOM ファンデータ分析ツール</h1>",
    unsafe_allow_html=True
)

# ▼▼ 認証ステップ ▼▼
if not st.session_state.authenticated:
    st.markdown("##### 🔑 認証コードを入力してください")
    input_room_id = st.text_input(
        "認証コードを入力してください:",
        placeholder="",
        type="password",
        key="room_id_input"
    )

    if st.button("認証する"):
        if input_room_id:
            try:
                response = requests.get(ROOM_LIST_URL, timeout=5)
                response.raise_for_status()
                room_df = pd.read_csv(io.StringIO(response.text), header=None)
                valid_codes = set(str(x).strip() for x in room_df.iloc[:, 0].dropna())

                if input_room_id.strip() in valid_codes:
                    st.session_state.authenticated = True
                    st.success("✅ 認証に成功しました。")
                    st.rerun()
                else:
                    st.error("❌ 認証コードが無効です。")
            except Exception as e:
                st.error(f"認証リストを取得できませんでした: {e}")
        else:
            st.warning("認証コードを入力してください。")
    st.stop()

# --- メインコンテンツ ---

# 共通設定エリア
with st.sidebar:
    st.header("共通設定")
    room_id = st.text_input("対象のルームID:", placeholder="例: 154851", value="")
    
    # 月の選択肢生成
    start_date = datetime(2025, 1, 1)
    current_date = datetime.now()
    month_options = []
    tmp_date = current_date
    while tmp_date >= start_date:
        month_options.append(tmp_date.strftime("%Y%m"))
        tmp_date -= relativedelta(months=1)
    
    selected_months = st.multiselect("対象月を選択:", options=month_options)

# タブ分け
tab1, tab2 = st.tabs(["📈 ファン推移分析 (統計)", "📄 ファンリスト取得 (詳細)"])

# ---------------------------------------------------------
# Tab 1: ファン推移分析 (統計)
# ---------------------------------------------------------
with tab1:
    st.subheader("📊 ファン数・ファンパワーの推移")
    analyze_button = st.button("推移データを取得・表示")

    if analyze_button:
        if not room_id or not selected_months:
            st.warning("ルームIDと月を選択してください。")
        else:
            # 認証チェック
            try:
                df_room_list = pd.read_csv(ROOM_LIST_URL, header=None)
                auth_ids = df_room_list.iloc[:, 0].astype(str).tolist()
                if room_id in auth_ids:
                    stats_data = []
                    progress_bar = st.progress(0)
                    
                    # 昇順で取得（時系列グラフのため）
                    sorted_months = sorted(selected_months)
                    
                    for idx, m in enumerate(sorted_months):
                        url = f"https://www.showroom-live.com/api/active_fan/users?room_id={room_id}&ym={m}"
                        resp = requests.get(url)
                        if resp.status_code == 200:
                            data = resp.json()
                            stats_data.append({
                                "年月": m,
                                "ファン数": data.get("total_user_count", 0),
                                "ファンパワー": data.get("fan_power", 0),
                                "ファン名称": data.get("fan_name", "-")
                            })
                        progress_bar.progress((idx + 1) / len(sorted_months))
                    
                    if stats_data:
                        df_stats = pd.DataFrame(stats_data)
                        
                        # サマリー表示
                        latest = df_stats.iloc[-1]
                        c1, c2, c3 = st.columns(3)
                        c1.metric("最新のファン数", f"{latest['ファン数']} 人")
                        c2.metric("最新のファンパワー", f"{latest['ファンパワー']} Pt")
                        c3.write(f"**最新のファン名**\n\n{latest['ファン名称']}")

                        st.markdown("---")

                        # グラフ表示
                        st.write("#### 推移グラフ")
                        # Streamlit標準の2軸グラフが難しいため、ファン数とパワーを併記
                        st.bar_chart(df_stats.set_index("年月")[["ファン数"]])
                        st.line_chart(df_stats.set_index("年月")[["ファンパワー"]])

                        # テーブル表示
                        st.write("#### データ一覧")
                        st.dataframe(df_stats, use_container_width=True)

                        # CSVダウンロード
                        csv_stats = df_stats.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                        st.download_button(
                            label="統計データをCSVダウンロード",
                            data=csv_stats,
                            file_name=f"fan_stats_{room_id}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.error("データが取得できませんでした。")
                else:
                    st.error("指定されたルームIDは認証されていません。")
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")

# ---------------------------------------------------------
# Tab 2: ファンリスト取得 (詳細) - 既存機能
# ---------------------------------------------------------
with tab2:
    st.subheader("📄 月別ファン詳細リストの生成")
    st.info("全ユーザーの詳細情報を取得し、ZIP形式でエクスポートします。")
    start_button = st.button("データ取得 & ZIP作成", key="list_btn")

    if start_button:
        if not room_id or not selected_months:
            st.warning("ルームIDの入力と月の選択を必ず行ってください。")
        else:
            is_authenticated = False
            try:
                df_room_list = pd.read_csv(ROOM_LIST_URL, header=None)
                auth_ids = df_room_list.iloc[:, 0].astype(str).tolist()
                if room_id in auth_ids:
                    is_authenticated = True
                else:
                    st.error("指定されたルームIDは認証されていません。")
            except Exception as e:
                st.error(f"認証エラー: {e}")

            if is_authenticated:
                monthly_counts = {}
                overall_progress = st.progress(0)
                overall_text = st.empty()
                processed_fans = 0
                total_fans_overall = 0

                zip_buffer = BytesIO()
                zip_file = ZipFile(zip_buffer, "w")

                # 事前カウント
                for month in selected_months:
                    url = f"https://www.showroom-live.com/api/active_fan/users?room_id={room_id}&ym={month}"
                    resp = requests.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        monthly_counts[month] = data.get("count", 0)
                        total_fans_overall += monthly_counts[month]
                    else:
                        monthly_counts[month] = 0

                all_fans_data = []
                orig_order_counter = 0
                for idx, month in enumerate(selected_months):
                    st.write(f"**{month} の詳細リストを取得中...**")
                    month_progress = st.progress(0)
                    fans_data = []
                    count = monthly_counts[month]
                    retrieved = 0

                    while retrieved < count:
                        url = f"https://www.showroom-live.com/api/active_fan/users?room_id={room_id}&ym={month}&offset={retrieved}&limit=50"
                        resp = requests.get(url)
                        if resp.status_code != 200: break
                        data = resp.json()
                        users = data.get("users", [])
                        for u in users:
                            u['orig_order'] = orig_order_counter
                            orig_order_counter += 1
                        fans_data.extend(users)
                        all_fans_data.extend(users)
                        retrieved += len(users)
                        if count > 0:
                            month_progress.progress(min(retrieved / count, 1.0))
                        
                        processed_fans += len(users)
                        if total_fans_overall > 0:
                            overall_progress.progress(min(processed_fans / total_fans_overall, 1.0))
                        time.sleep(0.05)

                    if fans_data:
                        df = pd.DataFrame(fans_data)
                        df = df[['avatar_id','level','title_id','user_id','user_name']]
                        csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                        zip_file.writestr(f"active_fans_{room_id}_{month}.csv", csv_bytes)

                # マージ処理
                if all_fans_data:
                    merge_df = pd.DataFrame(all_fans_data).iloc[::-1]
                    agg_df = merge_df.groupby('user_id', as_index=False).agg({
                        'level': 'sum', 'avatar_id': 'first', 'user_name': 'first', 'orig_order': 'first'
                    })
                    agg_df['title_id'] = (agg_df['level'] // 5).astype(int)
                    agg_df = agg_df.sort_values(by=['level','orig_order'], ascending=[False, True])
                    
                    merge_csv = agg_df.drop(columns='orig_order').to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                    zip_file.writestr(f"active_fans_{room_id}_merge.csv", merge_csv)

                zip_file.close()
                st.download_button("ZIPをダウンロード", zip_buffer.getvalue(), f"active_fans_{room_id}.zip", "application/zip")

                # プレビュー表示（上位10位のみ簡易表示）
                if not agg_df.empty:
                    st.write("### マージ集計プレビュー（上位10名）")
                    st.table(agg_df[['user_name', 'level']].head(10))