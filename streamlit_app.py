import streamlit as st
import pandas as pd
import time
from datetime import datetime
import numpy as np

# Streamlitのページ設定は必ずスクリプトの先頭で行う
st.set_page_config(layout="wide")

# --- 定数 ---
CANDIDATE_TBL = "candidate_master_tbl"
HISTORY_TBL = "approval_history_tbl"

# === データの初期化/モックデータの準備 ===
@st.cache_data
def get_mock_data():
    """本番データと承認候補データを模擬"""
    
    # DataFrameの作成 (データ型の安定化のため、全て明示的に定義)
    data_production = {
        'id': [1, 2, 3, 4],
        'product_name': ["Alpha Widget", "Beta Gadget", "Gamma Thing", "Delta Plate"],
        'price': [100.0, 50.0, 10.0, 70.0],
        'vendor_id': ['V001', 'V002', 'V003', 'V004'],
        'region': ['Tokyo', 'Osaka', 'Tokyo', 'Nagoya'],
        'status': ['ACTIVE', 'ACTIVE', 'ACTIVE', 'ACTIVE'],
        'tax_code': ['A-10', 'A-10', 'A-10', 'B-20'],
        'created_date': [datetime(2023, 1, 1), datetime(2023, 5, 10), datetime(2024, 1, 1), datetime(2024, 7, 1)],
    }
    df_prod = pd.DataFrame(data_production)

    data_candidate = {
        'id': [1, 3, 4, 101, 102],
        'product_name': ["Alpha Widget", "Gamma Thing (Changed)", "Delta Plate", "New Item-X", "New Item-Y"], 
        'price': [100.0, 15.0, 70.0, 500.0, 75.0],                                            
        'vendor_id': ['V001', 'V003', 'V005', 'V006', 'V007'], 
        'region': ['Tokyo', 'Fukuoka', 'Nagoya', 'Sapporo', 'Sendai'],                                
        'status': ['ACTIVE', 'DEPRECATED', 'ACTIVE', 'ACTIVE', 'ACTIVE'],
        'tax_code': ['A-10', 'A-10', 'B-20', 'C-30', 'A-10'],
        'created_date': [datetime(2023, 1, 1), datetime(2024, 1, 1), datetime(2024, 7, 1), datetime.now(), datetime.now()],
        'requires_review': [True, True, True, True, True]
    }
    df_cand = pd.DataFrame(data_candidate)
    
    review_cols = df_cand.columns.tolist()[:-1] 
    df_merged = df_cand.merge(df_prod, on='id', how='left', suffixes=('_cand', '_prod'))
    
    # 変更フラグの列を作成
    for col in review_cols:
        if col != 'id':
            col_cand = f'{col}_cand'
            col_prod = f'{col}_prod'
            col_changed = f'{col}_changed'
            
            # 比較のために、文字列に変換し、NaN/NaTを特定の文字列で埋める
            s_cand_str = df_merged[col_cand].astype(str).fillna('__NONE__')
            s_prod_str = df_merged[col_prod].astype(str).fillna('__NONE__')

            # 値が変更されたかどうかのブーリアン列
            df_merged[col_changed] = (s_cand_str != s_prod_str)
            
    return df_merged

# === 補助関数：縦型比較データの作成 ===
def create_vertical_diff(df_row: pd.Series):
    """選択された1レコードを縦型比較のためのDataFrameに変換"""
    data = []
    all_cols = set(df_row.index) 
    
    for col in all_cols:
        if col.endswith('_cand'):
            base_col = col.replace('_cand', '')
            
            col_prod = col.replace('_cand', '_prod')
            col_changed = f'{base_col}_changed'
            
            prod_value = df_row.get(col_prod, np.nan) 
            is_changed = df_row.get(col_changed, False)
            
            # Production の値が NaN の場合（新規レコード）は「N/A (新規レコード)」と表示
            if pd.isna(prod_value):
                 prod_display = 'N/A (新規レコード)'
            else:
                 prod_display = prod_value

            data.append({
                '項目': base_col.replace('_', ' ').title(),
                '変更前 (Production)': prod_display,
                '変更後 (Candidate)': df_row[col],
                '差分あり': is_changed
            })
    
    diff_df = pd.DataFrame(data)
    
    def style_diff(s):
        if '差分あり' in s.index:
            return ['background-color: #ffe6e6' if s['差分あり'] else ''] * len(s)
        return [''] * len(s)

    if '差分あり' in diff_df.columns:
        return diff_df.drop(columns=['差分あり']).style.apply(style_diff, axis=1)
    else:
        return diff_df.style.apply(style_diff, axis=1) 

# === 承認ロジックの模擬 (一括処理対応) ===
def execute_action(selected_ids: list, action: str, reason: str):
    ids_str = ", ".join(map(str, selected_ids))
    current_user = "MOCK_USER"
    
    st.info(f"合計 {len(selected_ids)} 件のレコードに対してアクション実行中... ({action})")
    time.sleep(1) 
    
    if action == "APPROVE":
        st.success(f"✅ 承認完了。レコードID {ids_str} が本番に展開されました。(模擬)")
    elif action == "REJECT":
        st.error(f"❌ 差し戻し完了。レコードID {ids_str} が候補テーブルから削除されました。(模擬)")
    
    # 処理後、data_editorの状態をリセットするため、セッションキーを削除してrerun
    del st.session_state['data_editor_state']
    st.rerun() 

# === アプリケーションの UI メイン関数 ===
def master_approval_app():
    st.title("マスタ変更レビュー (縦型比較 & 差分ハイライト)")
    st.markdown("---")

    # 1. データの準備とセッション状態の初期化
    df_merged = get_mock_data()
    df_review = df_merged[df_merged['requires_review_cand'] == True]

    # 【初期化ロジックの強化】: アプリケーション実行時に必要なキーをすべて確保する
    if 'selected_record_id' not in st.session_state:
        st.session_state['selected_record_id'] = None
    if 'detail_select_id' not in st.session_state:
        st.session_state['detail_select_id'] = None
    if 'data_editor_state' not in st.session_state:
        # data_editor の状態は、初回は None または空のリストにしておく
        st.session_state['data_editor_state'] = []


    if df_review.empty:
        st.success("🎉 承認待ちのレコードはありません。")
        st.session_state['selected_record_id'] = None 
        return

    # 変更列数の集計
    df_summary = df_review[['id']].copy()
    df_summary['変更列数'] = df_review.filter(like='_changed').sum(axis=1)

    # UIを左右に分割
    col_list, col_detail = st.columns([1, 1.5]) 
    
    # ---------------------------
    # 【左カラム: フィルタと一覧】
    # ---------------------------
    with col_list:
        st.subheader("承認待ちレコード一覧")
        
        # 1. フィルタリングUIの配置
        st.markdown("##### 絞り込み条件")
        
        max_changes = df_summary['変更列数'].max()
        min_changes = st.slider(
            '変更列数がこれ以上のレコードを表示',
            min_value=0, 
            max_value=max_changes, 
            value=0,
            key='change_filter_slider' 
        )
        
        df_filtered = df_summary[df_summary['変更列数'] >= min_changes].reset_index(drop=True)
        
        if df_filtered.empty:
            st.info("フィルタ条件を満たすレコードはありません。")
            st.stop()
            
        st.markdown("---")
            
        # 2. データエディタでの一覧表示と選択
        
        # 'select' 列をデータフレームに追加 (st.data_editor の仕様)
        df_filtered['select'] = False 
        
        # st.data_editor は key='data_editor_state' で状態を保持
        edited_df = st.data_editor(
            df_filtered,
            column_config={
                "select": st.column_config.CheckboxColumn(
                    "アクション対象",
                    help="承認/差し戻しのアクション対象としてマーク",
                    default=False
                ),
                "変更列数": st.column_config.NumberColumn("変更列数")
            },
            disabled=("id", "変更列数"), 
            hide_index=True,
            use_container_width=True,
            key='data_editor_state'
        )

        # ユーザーがチェックを入れたレコードのIDを取得 (一括承認用)
        selected_ids_for_action = edited_df[edited_df.select]['id'].tolist()
        
        st.info(f"現在、**{len(selected_ids_for_action)}** 件のレコードが選択されています。")
        st.markdown("---")

        # 3. 単一レコードの縦型比較ビュー用IDの選択
        
        available_ids = df_filtered['id'].tolist()
        
        # デフォルト選択のロジック
        default_id = available_ids[0]
        default_index = 0
        
        if st.session_state.selected_record_id in available_ids:
            default_index = available_ids.index(st.session_state.selected_record_id)
            default_id = st.session_state.selected_record_id

        # st.selectbox は key='detail_select_id' で状態を保持
        detail_review_id = st.selectbox(
            "詳細レビューするレコードを選択:",
            available_ids,
            index=default_index,
            key='detail_select_id',
        )
        
        # 選択IDをセッションに保存
        st.session_state['selected_record_id'] = detail_review_id

    # ---------------------------
    # 【右カラム: 縦型比較とアクション実行】
    # ---------------------------
    with col_detail:
        if st.session_state['selected_record_id'] is not None:
            st.subheader(f"ID: {st.session_state['selected_record_id']} の変更点レビュー")
            
            selected_row_id = st.session_state['selected_record_id']
            # df_review（元の全レビュー対象）から行を抽出
            selected_row = df_review[df_review['id'] == selected_row_id].iloc[0]
            
            # 縦型比較データフレームを作成し表示
            st.dataframe(
                create_vertical_diff(selected_row),
                use_container_width=True,
                height=300 
            )

            st.markdown("---")
            
            # 4. アクションエリア (一括承認)
            st.subheader("一括承認/差し戻し")
            
            if not selected_ids_for_action:
                st.warning("アクション対象としてレコードが一つも選択されていません。")
            else:
                col_btn_app, col_btn_rej = st.columns(2)
                with col_btn_app:
                    approve_button = st.button(f"✅ {len(selected_ids_for_action)} 件 承認実行", key="app_btn", use_container_width=True, type="primary")
                with col_btn_rej:
                    reject_button = st.button(f"❌ {len(selected_ids_for_action)} 件 差し戻し", key="rej_btn", use_container_width=True)

                reason = st.text_area("差し戻し理由 (REJECT時のみ)", key="reason_area")

                if approve_button or reject_button:
                    action = "APPROVE" if approve_button else "REJECT"
                    execute_action(selected_ids_for_action, action, reason)


# === アプリケーション実行 ===
if __name__ == "__main__":
    master_approval_app()
