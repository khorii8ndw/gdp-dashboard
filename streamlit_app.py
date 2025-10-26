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

# === データの初期化/モックデータの準備 (初回起動時のみ実行) ===
@st.cache_data(show_spinner=False) # スピナーを抑制し、裏側でデータを保持
def load_all_mock_data():
    """本番データと承認候補データを模擬し、全レビュー対象データを一度だけロードする"""
    
    data_production = {
        'id': [1, 2, 3, 4],
        'product_name': ["Alpha Widget", "Beta Gadget", "Gamma Thing", "Delta Plate"],
        'price': [100.0, 50.0, 10.0, 70.0],
        'vendor_id': ['V001', 'V002', 'V003', 'V004'],
        'region': ['Tokyo', 'Osaka', 'Tokyo', 'Nagoya'],
        'status': ['ACTIVE', 'ACTIVE', 'ACTIVE', 'ACTIVE'],
        'tax_code': ['A-10', 'A-10', 'A-10', 'B-20'],
        'created_date': [datetime(2023, 1, 1), datetime(2023, 5, 10), datetime(2024, 1, 1), datetime(2024, 7, 1)],
        'requires_review': [False, False, False, False]
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
    
    review_cols = [col for col in df_cand.columns if col not in ['id', 'requires_review']]
    df_merged = df_cand.merge(df_prod, on='id', how='left', suffixes=('_cand', '_prod'))
    
    for col in review_cols:
        col_cand = f'{col}_cand'
        col_prod = f'{col}_prod'
        col_changed = f'{col}_changed'
            
        s_cand_str = df_merged[col_cand].astype(str).fillna('__NONE__')
        s_prod_str = df_merged[col_prod].astype(str).fillna('__NONE__')

        df_merged[col_changed] = (s_cand_str != s_prod_str)
            
    # 全レビュー対象IDのリストを作成し、セッションに保持
    initial_review_ids = df_merged[df_merged['requires_review_cand'] == True]['id'].tolist()
    
    return df_merged, initial_review_ids # DataFrameと初期IDリストを返す


# === 補助関数 1：変更サマリーの自動生成 (変更なし) ===
def create_vertical_summary(df_row: pd.Series):
    """変更された項目とその差分を抽出し、自然言語のサマリーを生成する"""
    
    is_new_record = pd.isna(df_row.get('product_name_prod', np.nan)) 
    
    if is_new_record:
        summary_text = f"**新規レコード**が登録されようとしています。これは完全に新しいマスタエントリです。"
        return summary_text
        
    changes = []
    
    for key, is_changed in df_row.filter(like='_changed').items():
        if is_changed:
            base_col = key.replace('_changed', '')
            col_name = base_col.replace('_', ' ').title()
            
            val_prod = df_row.get(f'{base_col}_prod', 'N/A')
            val_cand = df_row.get(f'{base_col}_cand', 'N/A')
            
            if base_col == 'created_date':
                 changes.append(f"作成日 ({col_name}) が更新されました。")
            elif val_prod == '__NONE__':
                 changes.append(f"{col_name} が {val_cand} に設定されました。")
            else:
                 changes.append(f"{col_name} が **{val_prod}** から **{val_cand}** に変更されました。")

    if changes:
        return "**既存レコードの変更点:** " + " ".join(changes)
    else:
        return "このレコードには明らかな変更点はありません。(エラーの可能性)"


# === 補助関数 2：縦型比較データの作成 (変更なし) ===
def create_vertical_diff(df_row: pd.Series):
    """選択された1レコードを縦型比較のためのDataFrameに変換"""
    # 以前のコードと同一

    data = []
    all_cols = set(df_row.index) 
    
    for col in all_cols:
        if col.endswith('_cand') and col not in ['requires_review_cand']:
            base_col = col.replace('_cand', '')
            
            col_prod = col.replace('_cand', '_prod')
            col_changed = f'{base_col}_changed'
            
            prod_value = df_row.get(col_prod, np.nan) 
            is_changed = df_row.get(col_changed, False)
            
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

# === 承認ロジックの模擬 (低負荷対応版) ===
def execute_action(selected_ids: list, action: str, reason: str):
    
    st.info(f"合計 {len(selected_ids)} 件のレコードに対してアクション実行中... ({action})")
    time.sleep(0.5) # 処理待ちを短縮
    
    # 1. 処理成功メッセージの模擬
    if action == "APPROVE":
        st.success(f"✅ 承認完了。レコードID {selected_ids} が本番に展開されました。(模擬)")
    elif action == "REJECT":
        st.error(f"❌ 差し戻し完了。レコードID {selected_ids} が候補テーブルから削除されました。(模擬)")
    
    # 2. 【最重要】セッション状態のIDリストから処理済みIDを削除
    if 'all_review_ids' in st.session_state:
        st.session_state['all_review_ids'] = [
            id_val for id_val in st.session_state['all_review_ids'] if id_val not in selected_ids
        ]
    
    # 3. data_editorの状態をリセット (選択解除)
    if 'data_editor_state' in st.session_state:
        del st.session_state['data_editor_state']

    # 4. Streamlitを再実行 (データ再ロードなしでUIのみ更新)
    st.rerun() 


# === リスト描画補助関数 (タブのロジックを分離) ===
def render_review_list(df_data, group_key, default_selected_id):
    """フィルタリングとdata_editorの描画を担う補助関数"""

    st.markdown("##### 絞り込み条件")
    max_changes = df_data['変更列数'].max()
    
    min_changes = st.slider(
        '変更列数がこれ以上のレコードを表示',
        min_value=0, 
        max_value=max_changes if max_changes > 0 else 0,
        value=0,
        key=f'change_filter_slider_{group_key}' 
    )
    
    df_filtered = df_data[df_data['変更列数'] >= min_changes].reset_index(drop=True)
    
    if df_filtered.empty:
        st.info("フィルタ条件を満たすレコードはありません。")
        return pd.DataFrame(), [], []
        
    st.markdown("---")

    df_filtered['select'] = False 
    
    edited_df = st.data_editor(
        df_filtered,
        column_config={
            "select": st.column_config.CheckboxColumn("アクション対象", default=False),
            "変更列数": st.column_config.NumberColumn("変更列数")
        },
        disabled=("id", "変更列数"), 
        hide_index=True,
        use_container_width=True,
        key=f'data_editor_state_{group_key}' 
    )

    selected_ids_for_action = edited_df[edited_df.select]['id'].tolist()
    available_ids = df_filtered['id'].tolist()
    
    return df_filtered, selected_ids_for_action, available_ids


# === アプリケーションの UI メイン関数 ===
def master_approval_app():
    st.title("マスタ変更レビュー (高速レスポンス・サマリー対応)")
    st.markdown("---")

    # 1. データとセッション状態の初期化
    # load_all_mock_data はキャッシュされるため、初回以外は高速
    with st.spinner('データをロード中...'):
        df_merged, initial_review_ids = load_all_mock_data()
    
    # 【セッション状態の核】レビュー対象IDの管理
    if 'all_review_ids' not in st.session_state:
        st.session_state['all_review_ids'] = initial_review_ids

    # 【その他の初期化】
    if 'selected_record_id' not in st.session_state:
        st.session_state['selected_record_id'] = None
    if 'detail_select_id' not in st.session_state:
        st.session_state['detail_select_id'] = None
    if 'selected_group' not in st.session_state:
        st.session_state['selected_group'] = 'existing' # デフォルトは既存

    # 2. 現在のレビュー対象DFの生成 (メモリ内のIDリストでフィルタリング)
    if not st.session_state['all_review_ids']:
        st.success("🎉 承認待ちのレコードはありません。")
        return

    df_active_review = df_merged[df_merged['id'].isin(st.session_state['all_review_ids'])].copy()
    
    # 3. 新規レコードと既存レコードへの分割
    df_active_review['変更列数'] = df_active_review.filter(like='_changed').sum(axis=1)
    df_new = df_active_review[df_active_review['product_name_prod'].isna()]
    df_existing = df_active_review[df_active_review['product_name_prod'].notna()]

    # UIを左右に分割
    col_list, col_detail = st.columns([1, 1.5]) 
    
    # ---------------------------
    # 【左カラム: フィルタと一覧 (グルーピング)】
    # ---------------------------
    with col_list:
        st.subheader("承認待ちレコード一覧")

        # 【負荷軽減】st.radioでグループを切り替え、セッションに保持
        selected_group = st.radio(
            "レビュー対象のグループを選択:",
            options=['既存レコード変更', '新規レコード'],
            index=0 if st.session_state['selected_group'] == 'existing' else 1,
            format_func=lambda x: f"{x} ({len(df_existing) if x=='既存レコード変更' else len(df_new)})",
            key='review_group_radio',
            horizontal=True
        )
        st.session_state['selected_group'] = 'existing' if selected_group == '既存レコード変更' else 'new'

        current_df_data = df_existing if st.session_state['selected_group'] == 'existing' else df_new

        # 4. リスト描画 (フィルタリングとデータエディタ)
        if current_df_data.empty:
            st.info(f"選択されたグループにレビュー対象レコードはありません。")
            df_filtered, selected_ids_for_action, available_ids = pd.DataFrame(), [], []
        else:
            df_filtered, selected_ids_for_action, available_ids = render_review_list(
                current_df_data, 
                st.session_state['selected_group'],
                st.session_state['selected_record_id']
            )

        # 5. 単一レコードの縦型比較ビュー用IDの選択
        if available_ids:
            
            default_index = 0
            if st.session_state.selected_record_id in available_ids:
                default_index = available_ids.index(st.session_state.selected_record_id)
            else:
                # 前回の選択IDがフィルタやグループ切り替えで消えた場合、リストの最初のIDを強制的に選択
                st.session_state['selected_record_id'] = available_ids[0]

            detail_review_id = st.selectbox(
                "詳細レビューするレコードを選択:",
                available_ids,
                index=default_index,
                key='detail_select_id',
            )
            st.session_state['selected_record_id'] = detail_review_id
        else:
            st.session_state['selected_record_id'] = None
                
    # ---------------------------
    # 【右カラム: 縦型比較とアクション実行】
    # ---------------------------
    with col_detail:
        is_id_available = st.session_state['selected_record_id'] is not None and st.session_state['selected_record_id'] in df_active_review['id'].tolist()
        
        if is_id_available:
            
            selected_row_id = st.session_state['selected_record_id']
            selected_row = df_merged[df_merged['id'] == selected_row_id].iloc[0]
            
            st.subheader(f"ID: {selected_row_id} の変更点レビュー")

            # 変更サマリーの表示
            summary_text = create_vertical_summary(selected_row)
            st.info(summary_text)

            # 縦型比較データフレームを作成し表示
            st.markdown("##### 項目別 差分詳細")
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
        else:
            st.info("左側のリストでレコードを選択するか、フィルタ条件を変更してください。")


# === アプリケーション実行 ===
if __name__ == "__main__":
    master_approval_app()
