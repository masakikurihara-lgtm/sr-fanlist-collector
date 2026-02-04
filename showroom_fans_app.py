import streamlit as st
import requests
import pandas as pd
from io import BytesIO
from zipfile import ZipFile
from datetime import datetime
import time
import io
from dateutil.relativedelta import relativedelta
import plotly.graph_objects as go 

# ページ設定
st.set_page_config(page_title="SHOWROOM ファンリスト取得", layout="wide")

# ----- 認証用のルームリストURL -----
ROOM_LIST_URL = "https://mksoul-pro.com/showroom/file/room_list.csv"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
# 特殊コード認証フラグの初期化
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False

# タイトル
st.markdown(
    "<h1 style='font-size:28px; text-align:center; color:#1f2937;'>SHOWROOM ファンデータ取得＆分析ツール</h1>",
    unsafe_allow_html=True
)

# 説明文
st.markdown(
    "<p style='font-size:16px; text-align:center; color:#4b5563;'>"
    "ルームIDを入力して、取得・分析したい月を選択の上、各機能のボタンを押下してください。"
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

    if st.button("認証する"):
        if input_room_id:
            input_val = input_room_id.strip()
            # 【追加】特殊コードの判定
            if input_val == "mksp154851":
                st.session_state.authenticated = True
                st.session_state.is_admin = True
                st.success("✅ 認証に成功しました。")
                st.rerun()
            
            try:
                response = requests.get(ROOM_LIST_URL, timeout=5)
                response.raise_for_status()
                room_df = pd.read_csv(io.StringIO(response.text), header=None)
                valid_codes = set(str(x).strip() for x in room_df.iloc[:, 0].dropna())

                if input_val in valid_codes:
                    st.session_state.authenticated = True
                    st.session_state.is_admin = False
                    st.success("✅ 認証に成功しました。ツールを利用できます。")
                    st.rerun()
                else:
                    st.error("❌ 認証コードが無効です。正しい認証コードを入力してください。")
            except Exception as e:
                st.error(f"認証リストを取得できませんでした: {e}")
        else:
            st.warning("認証コードを入力してください。")
    st.stop()

# ルームID入力
room_id = st.text_input("対象のルームID:", placeholder="例: 154851", value="")

# 月の範囲を作成
start_date = datetime(2025, 1, 1)
current_date = datetime.now()
month_labels = []
tmp_date = current_date
while tmp_date >= start_date:
    month_labels.append(tmp_date.strftime("%Y%m"))
    tmp_date -= relativedelta(months=1)

# 月選択
selected_months = st.multiselect("取得したい月を選択（複数選択可）:", options=month_labels, default=[])

st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)

# 処理を完全に分けるため、カラムでボタンを配置
col_btn1, col_btn2 = st.columns([1, 1])

with col_btn1:
    start_button = st.button("データ取得 & ZIP作成")

with col_btn2:
    stats_button = st.button("📊 ファン統計（推移）を表示")



# ---------------------------------------------------------
# 新機能：ファン統計（推移）処理セクション
# ---------------------------------------------------------
# 表示状態を維持するためのフラグ初期化
if "show_stats_view" not in st.session_state:
    st.session_state.show_stats_view = False
if "show_detail_analysis" not in st.session_state:
    st.session_state.show_detail_analysis = False

# ボタンが押されたらフラグをオンにする
if stats_button:
    st.session_state.show_stats_view = True

# 「統計を表示」フラグがオンの間は、ずっと表示され続ける
if st.session_state.show_stats_view:
    if not room_id or not selected_months:
        st.warning("ルームIDの入力と月の選択を必ず行ってください。")
    else:
        try:
            df_room_list = pd.read_csv(ROOM_LIST_URL, header=None)
            auth_ids = df_room_list.iloc[:, 0].astype(str).tolist()
            
            if st.session_state.is_admin or (room_id in auth_ids):
                st.markdown("### 📈 ファン数・ファンパワーの推移")
                stats_list = []
                all_fans_data_for_analysis = [] 
                
                for m in sorted(selected_months): 
                    url = f"https://www.showroom-live.com/api/active_fan/users?room_id={room_id}&ym={m}"
                    resp = requests.get(url)
                    if resp.status_code == 200:
                        data = resp.json()
                        stats_list.append({
                            "年月": m,
                            "ファン数": data.get("total_user_count", 0),
                            "ファンパワー": data.get("fan_power", 0),
                            "ファン名称": data.get("fan_name", "-")
                        })
                        users = data.get("users", [])
                        # --- 【修正点1】 各ユーザーデータに年月(ym)を注入してエラーを回避 ---
                        for u in users:
                            u['ym'] = m
                        all_fans_data_for_analysis.extend(users)
                
                if stats_list:
                    df_stats = pd.DataFrame(stats_list)

                    # --- グラフ作成（Plotly 2軸） ---
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=df_stats["年月"], y=df_stats["ファン数"],
                        name="ファン数", marker_color='rgba(55, 128, 191, 0.7)',
                        yaxis="y1"
                    ))
                    fig.add_trace(go.Scatter(
                        x=df_stats["年月"], y=df_stats["ファンパワー"],
                        name="ファンパワー", line=dict(color='firebrick', width=3),
                        yaxis="y2"
                    ))
                    fig.update_layout(
                        xaxis=dict(title="対象月"),
                        yaxis=dict(title="ファン数（人）", side="left"),
                        yaxis2=dict(title="ファンパワー（Pt）", side="right", overlaying="y", showgrid=False),
                        legend=dict(x=0.01, y=0.99),
                        template="plotly_white", height=450, margin=dict(l=20, r=20, t=20, b=20)
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # --- 統計テーブル表示 ---
                    st.markdown("#### 📋 統計データ一覧")
                    column_order = ["年月", "ファン名称", "ファン数", "ファンパワー"]
                    df_display_stats = df_stats.sort_values("年月", ascending=False)[column_order]
                    
                    table_html = "<table style='width:100%; border-collapse:collapse; font-size:14px;'><thead><tr style='background-color:#f3f4f6; border-bottom:2px solid #e5e7eb;'><th style='padding:12px; text-align:center;'>年月</th><th style='padding:12px; text-align:center;'>ファン名称</th><th style='padding:12px; text-align:center;'>ファン数</th><th style='padding:12px; text-align:center;'>ファンパワー</th></tr></thead><tbody>"
                    for idx, row in df_display_stats.iterrows():
                        table_html += f"<tr style='border-bottom:1px solid #f0f0f0;'><td style='padding:10px; text-align:center; font-weight:bold;'>{row['年月']}</td><td style='padding:10px; text-align:center; color:#2563eb;'>{row['ファン名称']}</td><td style='padding:10px; text-align:center;'>{row['ファン数']:,}</td><td style='padding:10px; text-align:center;'>{row['ファンパワー']:,}</td></tr>"
                    table_html += "</tbody></table>"
                    st.markdown(table_html, unsafe_allow_html=True)

                    csv_stats = df_display_stats.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                    st.download_button(label="統計CSVをダウンロード", data=csv_stats, file_name=f"fan_stats_{room_id}.csv", mime="text/csv")



                    # --- 追加分析セクション ---
                    st.markdown("---")

                    if st.button("🔍 さらに詳細分析する", key="detail_analysis_btn"):
                        with st.spinner("詳細分析のため、全ファンデータを取得中..."):
                            full_analysis_data = []
                            for m in sorted(selected_months):
                                # --- 【修正点1】最初にその月の総数を取得する ---
                                init_url = f"https://www.showroom-live.com/api/active_fan/users?room_id={room_id}&ym={m}&offset=0&limit=1"
                                try:
                                    init_resp = requests.get(init_url)
                                    init_data = init_resp.json()
                                    total_count = init_data.get("total_user_count", 0)
                                except:
                                    total_count = 0

                                retrieved = 0
                                per_page = 100 
                                
                                # --- 【修正点2】取得数が総数に達するまで回す（while Trueをやめる） ---
                                while retrieved < total_count:
                                    url = f"https://www.showroom-live.com/api/active_fan/users?room_id={room_id}&ym={m}&offset={retrieved}&limit={per_page}"
                                    try:
                                        resp = requests.get(url)
                                        if resp.status_code != 200:
                                            break
                                        data = resp.json()
                                        users = data.get("users", [])
                                        
                                        if not users:
                                            # データが空でも、取得数が総数に達していなければオフセットを強引に進める
                                            # (APIの一時的な空レスポンス対策)
                                            retrieved += per_page
                                            continue
                                        
                                        for u in users:
                                            u['ym'] = m
                                            full_analysis_data.append(u)
                                        
                                        retrieved += len(users)
                                    except Exception:
                                        break
                                
                                # サーバー負荷軽減のため微小な待機（正常処理に合わせる）
                                time.sleep(0.05)
                                
                            st.session_state.full_fans_data = full_analysis_data
                            st.session_state.show_detail_analysis = True

                    # 分析表示セクション
                    if st.session_state.get('show_detail_analysis', False):
                        st.markdown("### 🧬 ファンデータ詳細分析")
                        
                        # セッション内の全量データ(full_fans_data)を使用して分析
                        if "full_fans_data" in st.session_state and st.session_state.full_fans_data:
                            full_df = pd.DataFrame(st.session_state.full_fans_data)

                            # --- 🏆 合算ランキング表示 ---
                            st.markdown("#### 🏆 合算ランキング <span style='font-size: 0.6em; color: gray;'>(選択月累計)</span>", unsafe_allow_html=True)

                            # 修正：aggの中でlambdaを使用して「レベル10以上の月数」をカウントする

                            analysis_df = full_df.groupby('user_id').agg({
                                'level': [
                                    ('レベル合計値', 'sum'),
                                    ('ファン回数', lambda x: (x >= 10).sum())
                                ],
                                'user_name': 'first',
                                'avatar_id': 'first'
                            }).reset_index()

                            # マルチカラムをフラット化
                            analysis_df.columns = ['user_id', 'レベル合計値', 'ファン回数', 'ユーザー名', 'アバター']
                            
                            analysis_df['平均レベル'] = analysis_df['レベル合計値'] / len(selected_months)

                            # 以降の処理（フィルタ・順位付け）
                            analysis_df = analysis_df[analysis_df['レベル合計値'] >= 0]
                            analysis_df['順位'] = analysis_df['レベル合計値'].rank(method='min', ascending=False).astype(int)
                            analysis_df = analysis_df.sort_values('順位', ascending=True).reset_index(drop=True)

                            # 順位引き出し用の辞書作成
                            rank_map = analysis_df.set_index('user_id')['順位'].to_dict()

                            table_style = "<style>.scroll-table { max-height: 70vh; overflow-y: auto; border: 1px solid #e5e7eb; position: relative; } .scroll-table table { width: 100%; border-collapse: collapse; font-size: 14px; } .scroll-table thead th { position: sticky; top: 0; background-color: #f3f4f6; z-index: 1; border-bottom: 2px solid #e5e7eb; padding: 10px; } .scroll-table td { padding: 8px; border-bottom: 1px solid #f0f0f0; }</style>"
                            
                            table_html_detail = f"{table_style}<div class='scroll-table'><table><thead><tr><th>順位</th><th>アバター</th><th>ユーザー名</th><th>レベル合計値</th><th>平均レベル</th><th>ファン回数</th></tr></thead><tbody>"
                            for _, row in analysis_df.iterrows():
                                table_html_detail += f"<tr><td style='text-align:center; font-weight:bold;'>{row['順位']}</td><td style='text-align:center;'><img src='https://static.showroom-live.com/image/avatar/{row['アバター']}.png' width='30'></td><td>{row['ユーザー名']}</td><td style='text-align:center;'>{row['レベル合計値']:,}</td><td style='text-align:center;'>{row['平均レベル']:.1f}</td><td style='text-align:center;'>{int(row['ファン回数'])}回</td></tr>"
                            table_html_detail += "</tbody></table></div>"
                            st.markdown(table_html_detail, unsafe_allow_html=True)

                            # --- 📈 レベル変動（急上昇・急下落）分析 ---
                            st.write("---")
                            col_head1, col_head2 = st.columns([2, 1])
                            with col_head1:
                                st.markdown("#### 📈 レベル急変動アラート")
                            with col_head2:
                                threshold = st.number_input("検知しきい値 (±)", min_value=1, value=10, step=1)

                            if 'ym' not in full_df.columns:
                                st.error("エラー：データ内に年月情報が見つかりません。")
                            else:
                                sorted_yms = sorted(list(full_df['ym'].unique()))
                                if len(sorted_yms) < 2:
                                    st.info("レベルの変動を分析するには、2ヶ月以上のデータを選択してください。")
                                else:
                                    alert_list = []
                                    
                                    # 全ユーザーIDを網羅
                                    for uid, group in full_df.groupby('user_id'):
                                        u_name = group['user_name'].iloc[-1]
                                        lv_map = group.set_index('ym')['level'].to_dict()
                                        u_rank = rank_map.get(uid, 999999) 
                                        
                                        user_temp_alerts = []
                                        
                                        # 【修正の肝】レコードの有無に関わらず、選択期間の「全月」を走査
                                        for i in range(len(sorted_yms) - 1):
                                            prev_m, curr_m = sorted_yms[i], sorted_yms[i+1]
                                            
                                            # レコードがない月は 0 として取得
                                            prev_lv = lv_map.get(prev_m, 0)
                                            curr_lv = lv_map.get(curr_m, 0)
                                            
                                            # 両方0（ずっと活動なし）なら無視
                                            if prev_lv == 0 and curr_lv == 0:
                                                continue
                                                
                                            diff = curr_lv - prev_lv
                                            
                                            # 絶対値でしきい値を判定（これで 5→8 の +3 も拾えるようになる）
                                            if abs(diff) >= threshold:
                                                kind_html = f"<span style='color:#ef4444; font-weight:bold;'>🚀大幅上昇</span>" if diff > 0 else f"<span style='color:#3b82f6; font-weight:bold;'>🔻大幅下落</span>"
                                                user_temp_alerts.append({
                                                    "順位": u_rank if u_rank != 999999 else "-",
                                                    "ユーザー名": u_name,
                                                    "種別": kind_html,
                                                    "前月": prev_m,
                                                    "前月Lv": prev_lv,
                                                    "当月": curr_m,
                                                    "当月Lv": curr_lv,
                                                    "変動": f"{diff:+d}",
                                                    "raw_rank": u_rank,
                                                    "raw_month": curr_m
                                                })
                                        
                                        if user_temp_alerts:
                                            # 月が新しい順に並べ替え
                                            user_temp_alerts.sort(key=lambda x: -int(str(x['raw_month']).replace('/','')))
                                            alert_list.append({
                                                "rank": u_rank,
                                                "alerts": user_temp_alerts
                                            })
                                    
                                    if alert_list:
                                        alert_list.sort(key=lambda x: x['rank'])
                                        alert_html = f"{table_style}<div class='scroll-table' style='max-height:50vh;'><table><thead><tr><th>順位</th><th>ユーザー名</th><th>種別</th><th>前月</th><th>前月Lv</th><th>当月</th><th>当月Lv</th><th>変動</th></tr></thead><tbody>"
                                        for user_block in alert_list:
                                            for a in user_block['alerts']:
                                                alert_html += f"<tr><td style='text-align:center; font-weight:bold;'>{a['順位']}</td><td>{a['ユーザー名']}</td><td style='text-align:center;'>{a['種別']}</td><td style='text-align:center;'>{a['前月']}</td><td style='text-align:center;'>{a['前月Lv']}</td><td style='text-align:center;'>{a['当月']}</td><td style='text-align:center;'>{a['当月Lv']}</td><td style='text-align:center; font-weight:bold;'>{a['変動']}</td></tr>"
                                        alert_html += "</tbody></table></div>"
                                        st.markdown(alert_html, unsafe_allow_html=True)
                                    else:
                                        st.info(f"条件（レベル変動±{threshold}以上）に該当するユーザーはいませんでした。")

                            # --- 🔍 特定ユーザーの詳細分析 ---
                            st.write("---")
                            st.markdown("#### 🔍 特定ユーザーの詳細推移")

                            # 1. ユーザー選択リスト作成（表示上だけ整数にする）
                            user_options = {
                                str(row['user_id']): f"{int(row['順位'])}位：{row['ユーザー名']} ({int(row['user_id'])})" 
                                for _, row in analysis_df.iterrows()
                            }

                            target_uid = st.selectbox(
                                "分析するユーザーを選択", 
                                options=list(user_options.keys()), 
                                format_func=lambda x: user_options[x],
                                key="user_selector"
                            )

                            if target_uid:
                                # 2. 【重要】比較対象の型を合わせる（target_uidは文字列、full_df['user_id']も文字列にキャストして比較）
                                u_data_existing = full_df[full_df['user_id'].astype(str) == str(target_uid)].copy()
                                
                                # 3. 全期間(sorted_yms)の器を作成し、データがない月をレベル0で埋める
                                plot_data = []
                                for ym in sorted_yms:
                                    row = u_data_existing[u_data_existing['ym'] == ym]
                                    if not row.empty:
                                        # 取得したレベルを数値として保持
                                        plot_data.append({"ym": ym, "level": int(row['level'].values[0])})
                                    else:
                                        plot_data.append({"ym": ym, "level": 0})
                                
                                # グラフ用(昇順)とテーブル用(降順)のDFを作成
                                u_full_display_df = pd.DataFrame(plot_data)
                                u_data_graph = u_full_display_df.sort_values('ym')
                                u_data_table = u_full_display_df.sort_values('ym', ascending=False)
                                
                                col_left, col_right = st.columns([1, 2])
                                with col_left:
                                    st.write("##### 📋 月別レベル一覧")
                                    u_table_html = f"{table_style}<div class='scroll-table' style='max-height:300px;'><table><thead><tr><th>対象月</th><th>レベル</th></tr></thead><tbody>"
                                    for _, u_row in u_data_table.iterrows():
                                        # レベル0は強調するなど、視認性を上げることも可能です
                                        lv_display = u_row['level']
                                        u_table_html += f"<tr><td style='text-align:center; font-weight:bold;'>{u_row['ym']}</td><td style='text-align:center;'>{lv_display}</td></tr>"
                                    u_table_html += "</tbody></table></div>"
                                    st.markdown(u_table_html, unsafe_allow_html=True)
                                
                                with col_right:
                                    st.write("##### 📈 レベル推移グラフ")
                                    line_fig = go.Figure()
                                    line_fig.add_trace(go.Scatter(
                                        x=u_data_graph['ym'], y=u_data_graph['level'], mode='lines+markers+text',
                                        text=u_data_graph['level'], textposition="top center",
                                        line=dict(color='#FF4B4B', width=3), name="ファンレベル",
                                        connectgaps=True # 念のため隙間を繋ぐ設定
                                    ))
                                    
                                    max_lv = u_data_graph['level'].max()
                                    line_fig.update_layout(
                                        xaxis_title="年月", yaxis_title="レベル", height=300, 
                                        margin=dict(l=20, r=20, t=40, b=20),
                                        # y軸の最小値を0に固定し、レベル0が底辺に見えるようにする
                                        yaxis=dict(range=[0, max_lv + (max_lv * 0.2) + 2] if max_lv > 0 else [0, 10]),
                                        template="plotly_white"
                                    )
                                    st.plotly_chart(line_fig, use_container_width=True)
                        else:
                            st.warning("詳細分析用のデータが取得できていません。")

                else:
                    st.error("データの取得に失敗しました。")
            else:
                st.error("指定されたルームIDは認証されていません。")
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")



# ---------------------------------------------------------
# 既存機能：データ取得 & ZIP作成セクション（変更なし）
# ---------------------------------------------------------
if start_button:
    if not room_id or not selected_months:
        st.warning("ルームIDの入力と月の選択を必ず行ってください。")
    else:
        is_authenticated = False
        try:
            df_room_list = pd.read_csv(ROOM_LIST_URL, header=None)
            auth_ids = df_room_list.iloc[:, 0].astype(str).tolist()
            # 【修正】管理者フラグがある場合はリストチェックをパス
            if st.session_state.is_admin or (room_id in auth_ids):
                is_authenticated = True
            else:
                st.error("指定されたルームIDは認証されていません。")
        except Exception as e:
            st.error(f"認証リストの取得に失敗しました。管理者にご確認ください。 (Error: {e})")

        if is_authenticated:
            st.info(f"{len(selected_months)}か月分のデータを取得します。")
            monthly_counts = {}
            overall_progress = st.progress(0)
            overall_text = st.empty()
            processed_fans = 0
            total_fans_overall = 0

            zip_buffer = BytesIO()
            zip_file = ZipFile(zip_buffer, "w")

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

                if fans_data:
                    df = pd.DataFrame(fans_data)
                    df = df[['avatar_id','level','title_id','user_id','user_name']]
                    csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                    zip_file.writestr(f"active_fans_{room_id}_{month}.csv", csv_bytes)

                month_text.markdown(
                    f"<p style='font-size:14px; color:#10b981;'><b>{month} の取得完了 ({len(fans_data)} 件)</b></p>",
                    unsafe_allow_html=True
                )
                month_progress.progress(1.0)

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

                merge_df = pd.DataFrame(all_fans_data)
                merge_df = merge_df.iloc[::-1]
                agg_df = merge_df.groupby('user_id', as_index=False).agg({
                    'level': 'sum',
                    'avatar_id': 'first',
                    'user_name': 'first',
                    'orig_order': 'first'
                })
                agg_df['title_id'] = (agg_df['level'] // 5).astype(int)
                agg_df = agg_df[['avatar_id','level','title_id','user_id','user_name','orig_order']]
                agg_df = agg_df.sort_values(by=['level','orig_order'], ascending=[False, True]).reset_index(drop=True)

                merge_csv_bytes = agg_df.drop(columns='orig_order').to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                zip_file.writestr(f"active_fans_{room_id}_merge.csv", merge_csv_bytes)

                merge_progress.progress(1.0)
                merge_text.markdown(
                    f"<p style='font-size:14px; color:#10b981;'><b>マージCSV作成完了 ({len(agg_df)} 件)</b></p>",
                    unsafe_allow_html=True
                )

            zip_file.close()
            zip_buffer.seek(0)

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

                # 外側に70vhのスクロール用divを追加し、thにsticky（見出し固定）を適用
                table_html = "<div style='max-height: 70vh; overflow-y: auto; border-bottom: 1px solid #ccc;'>"
                table_html += "<table style='width:100%; border-collapse:collapse;'>"
                table_html += "<thead><tr style='background-color:#f3f4f6;'>"
                for col in display_df.columns:
                    # 見出しを固定するためのスタイル（position: sticky）を追加
                    table_html += f"<th style='border-bottom:1px solid #ccc; padding:4px; text-align:center; position: sticky; top: 0; background-color: #f3f4f6; z-index: 1;'>{col}</th>"
                table_html += "</tr></thead><tbody>"
                for idx, row in display_df.iterrows():
                    table_html += "<tr>"
                    table_html += f"<td style='text-align:center;'>{row['順位']}</td>"
                    table_html += f"<td style='text-align:center;'><img src='https://static.showroom-live.com/image/avatar/{row['アバター']}.png' width='40'></td>"
                    table_html += f"<td style='text-align:center;'>{row['レベル合計値']}</td>"
                    table_html += f"<td style='text-align:left; padding-left:8px;'>{row['ユーザー名']}</td>"
                    table_html += "</tr>"
                table_html += "</tbody></table></div>"

                st.markdown(table_html, unsafe_allow_html=True)
                st.markdown("<p style='font-size:12px; text-align:left; margin-top:4px;'>※100位まで表示しています</p>", unsafe_allow_html=True)