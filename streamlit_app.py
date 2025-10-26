import streamlit as st
import pandas as pd
import time
from datetime import datetime
import numpy as np

# Streamlitのページ設定は必ずスクリプトの先頭で行う
st.set_page_config(layout="wide")

# --- 定数 ---
# (データ生成ロジックは安定しているため省略)

# === データの初期化/モックデータの準備 (初回起動時のみ実行) ===
@st.cache_data(show_spinner=False)
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
            
    initial_review_ids = df_merged[df_merged['requires_review_cand'] == True]['id'].tolist()
    
    return df_merged, initial_review_ids


# === 補助関数 1：変更サマリーの自動生成 (変更なし) ===
def create_vertical_summary(df_row: pd.Series):
    """変更された項目とその差分を抽出し、自然言語のサマリーを生成する"""
    is_new_record = pd.isna(df_row.get('product_name_prod', np.nan)) 
    
    if is_new_record:
        return f"**新規レコード**が登録されようとしています。これは完全に新しいマスタエントリです。"
        
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
    # ... (前回のロジックと同一) ...
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

# === 承認ロジックの模擬 (操作性最適化版) ===
def execute_action(selected_ids: list, action: str, reason: str, available_ids: list, current_id: int):
    
    st.info(f"合計 {len(selected_ids)} 件のレコードに対してアクション実行中... ({action})")
    time.sleep(0.5)
    
    if action == "APPROVE":
        st.success(f"✅ 承認完了。レコードID {selected_ids} が本番に展開されました。(模擬)")
    elif action == "REJECT":
        st.error(f"❌ 差し戻し完了。レコードID {selected_ids} が候補テーブルから削除されました。(模擬)")
    
    # 1. セッション状態のIDリストから処理済みIDを削除
    if 'all_review_ids' in st.session_state:
        st.session_state['all_review_ids'] = [
            id_val for id_val in st.session_state['all_review_ids'] if id_val not in selected_ids
        ]
    
    # 2. 次のレコードIDを決定し、セッションにセット
    new_available_ids = [id_val for id_val in available_ids if id_val not in selected_ids]
    
    if not new_available_ids:
        st.session_state['selected_record_id'] = None
    elif current_id in available_ids:
        current_index = available_ids.index(current_id)
        
        next_id_candidate = None
        for i in range(current_index + 1, len(available_ids)):
            if available_ids[i] in new_available_ids:
                next_id_candidate = available_ids[i]
                break
        
        if next_id_candidate is not None:
            st.session_state['selected_record_id'] = next_id_candidate
        elif new_available_ids:
            st.session_state['selected_record_id'] = new_available_ids[0] # リストの最初に戻る

    # 3. data_editorの状態をリセット
    if 'data_editor_state_existing' in st.session_state:
        del st.session_state['data_editor_state_existing']
    if 'data_editor_state_new' in st.session_state:
        del st.session_state['data_editor_state_new']

    st.rerun() 


# === リスト描画補助関数 (アクションボタン列の追加) ===
def render_review_list(df_data, group_key):
    """フィルタリング、data_editor、アクションボタン列の描画を担う補助関数"""

    st.markdown("##### 絞り込み条件")
    max_changes = df_data['変更列数'].max()
    
    min_changes = st.slider(
        '変更列数がこれ以上のレコードを表示',
        min_value=0, 
        max_value=max_changes if max_changes > 0 else 0,
        value=0,
        key=f'change_filter_slider_{group_key}' 
    )
    
    # フィルタリングの結果
    df_filtered = df_data[df_data['変更列数'] >= min_changes].reset_index(drop=True)
    
    if df_filtered.empty:
        st.info("フィルタ条件を満たすレコードはありません。")
        return pd.DataFrame(), [], []
        
    st.markdown("---")

    # 【重要】アクションボタンの列を追加
    df_filtered['select'] = False 
    df_filtered['承認'] = '承認' # ButtonColumn用
    df_filtered['差し戻し'] = '差し戻し' # ButtonColumn用
    
    edited_df = st.data_editor(
        df_filtered,
        column_config={
            "select": st.column_config.CheckboxColumn("一括対象", default=False),
            "変更列数": st.column_config.NumberColumn("変更列数", width='small'),
            "承認": st.column_config.ButtonColumn("個別承認", help="このレコードのみを承認します", width='small', on_click=handle_single_action, args=['APPROVE']),
            "差し戻し": st.column_config.ButtonColumn("個別差し戻し", help="このレコードのみを差し戻します", width='small', on_click=handle_single_action, args=['REJECT'])
        },
        disabled=("id", "変更列数"), 
        hide_index=True,
        use_container_width=True,
        # height=500, # スクロール可能にする
        key=f'data_editor_state_{group_key}' 
    )

    selected_ids_for_action = edited_df[edited_df.select]['id'].tolist()
    available_ids = df_filtered['id'].tolist()
    
    return df_filtered, selected_ids_for_action, available_ids


# === data_editorのボタンが押された時のコールバック関数 ===
def handle_single_action(action: str):
    """data_editorのボタンクリック時に実行される。st.session_stateからIDを取得する。"""
    
    # Streamlitのdata_editorのコールバックは、引数として行の情報を直接渡せないため、
    # 最後に変更された data_editor の状態からトリガーされた行を特定する。
    
    # 現在のグループを特定
    group_key = st.session_state['selected_group']
    editor_key = f'data_editor_state_{group_key}'
    
    if editor_key in st.session_state and st.session_state[editor_key].get('edited_rows'):
        
        edited_rows = st.session_state[editor_key]['edited_rows']
        
        # 最後に編集された行（ボタンが押された行）を見つける
        # 承認/差し戻しボタンが押されたとき、その行のインデックスの対応する列に値が設定される
        triggered_index = -1
        for idx, row_dict in edited_rows.items():
            if action in row_dict:
                triggered_index = idx
                break
        
        if triggered_index != -1:
            # 元の DataFrame を取得
            df_review = st.session_state.get('df_review_current_group')
            if df_review is not None:
                
                # フィルタリング後の DF のインデックスを取得
                triggered_id = df_review.iloc[triggered_index]['id']
                
                # 現在の全レビューIDリスト、処理対象IDリストを取得
                available_ids = st.session_state.get('current_available_ids', []) 
                current_id = st.session_state.get('selected_record_id')

                # アクション実行に移る
                execute_action([triggered_id], action, st.session_state.get('reason_area', '理由なし'), available_ids, current_id)
            else:
                 st.error("レビューデータの取得に失敗しました。")
        else:
             st.warning("アクションのトリガー元のレコードを特定できませんでした。")


# === アプリケーションの UI メイン関数 ===
def master_approval_app():
    st.title("マスタ変更レビュー (アクション集約・最終版)")
    st.markdown("---")

    # 1. データとセッション状態の初期化
    with st.spinner('データをロード中...'):
        df_merged, initial_review_ids = load_all_mock_data()
    
    if 'all_review_ids' not in st.session_state:
        st.session_state['all_review_ids'] = initial_review_ids
    if 'selected_record_id' not in st.session_state:
        st.session_state['selected_record_id'] = None
    if 'selected_group' not in st.session_state:
        st.session_state['selected_group'] = 'existing' 
    if 'df_review_current_group' not in st.session_state:
        st.session_state['df_review_current_group'] = pd.DataFrame() 

    if not st.session_state['all_review_ids']:
        st.success("🎉 承認待ちのレコードはありません。")
        return

    df_active_review = df_merged[df_merged['id'].isin(st.session_state['all_review_ids'])].copy()
    df_active_review['変更列数'] = df_active_review.filter(like='_changed').sum(axis=1)
    df_new = df_active_review[df_active_review['product_name_prod'].isna()]
    df_existing = df_active_review[df_active_review['product_name_prod'].notna()]

    col_list, col_detail = st.columns([1, 1.5]) 
    
    # ---------------------------
    # 【左カラム: フィルタと一覧 (グルーピング) - 選別とアクションの集中】
    # ---------------------------
    with col_list:
        st.subheader("承認待ちレコード一覧")

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
        st.session_state['df_review_current_group'] = current_df_data # コールバック用

        # 4. リスト描画 (フィルタリングとデータエディタ)
        if current_df_data.empty:
            st.info(f"選択されたグループにレビュー対象レコードはありません。")
            df_filtered, selected_ids_for_action, available_ids = pd.DataFrame(), [], []
        else:
            df_filtered, selected_ids_for_action, available_ids = render_review_list(
                current_df_data, 
                st.session_state['selected_group']
            )
        
        st.session_state['current_available_ids'] = available_ids # コールバック用

        # 5. 詳細レビューIDの決定と単体アクションのトリガー
        if available_ids:
            
            # 選択IDが現在のリストに存在しない場合、最初のIDを強制的に選択
            if st.session_state.selected_record_id not in available_ids:
                st.session_state['selected_record_id'] = available_ids[0]
            
            # 【新方式】data_editorの選択行を詳細ビューに反映
            if st.session_state[f'data_editor_state_{st.session_state["selected_group"]}']['selection']['rows']:
                selected_row_index = st.session_state[f'data_editor_state_{st.session_state["selected_group"]}']['selection']['rows'][0]
                new_selected_id = df_filtered.iloc[selected_row_index]['id']
                st.session_state['selected_record_id'] = new_selected_id

        else:
            st.session_state['selected_record_id'] = None
                
    # ---------------------------
    # 【右カラム: 純粋な詳細確認ビュー】
    # ---------------------------
    with col_detail:
        is_id_available = st.session_state['selected_record_id'] is not None and st.session_state['selected_record_id'] in df_active_review['id'].tolist()
        
        if is_id_available:
            
            current_id = st.session_state['selected_record_id']
            selected_row = df_merged[df_merged['id'] == current_id].iloc[0]
            
            st.subheader(f"ID: {current_id} の変更点レビュー (確認用)")

            # 変更サマリーの表示
            summary_text = create_vertical_summary(selected_row)
            st.info(summary_text)

            # 縦型比較データフレームを作成し表示
            st.markdown("##### 項目別 差分詳細")
            st.dataframe(
                create_vertical_diff(selected_row),
                use_container_width=True,
                height=400 
            )

            st.markdown("---")
            
            # 2. 一括承認/差し戻しエリア
            st.subheader("一括アクション (左側でチェックしたレコード)")

            if not selected_ids_for_action:
                st.warning("左側の一覧で「一括対象」にレコードが一つもチェックされていません。")
            else:
                col_btn_app, col_btn_rej = st.columns(2)
                with col_btn_app:
                    approve_button = st.button(f"✅ {len(selected_ids_for_action)} 件 一括承認", key="app_btn", use_container_width=True, type="primary")
                with col_btn_rej:
                    reject_button = st.button(f"❌ {len(selected_ids_for_action)} 件 一括差し戻し", key="rej_rej", use_container_width=True)

                reason = st.text_area("差し戻し理由 (REJECT時のみ)", key="reason_area")

                if approve_button or reject_button:
                    action = "APPROVE" if approve_button else "REJECT"
                    execute_action(selected_ids_for_action, action, reason, available_ids, current_id)
        else:
            st.info("左側のリストでレコードを選択してください。")


# === アプリケーション実行 ===
if __name__ == "__main__":
    master_approval_app()
