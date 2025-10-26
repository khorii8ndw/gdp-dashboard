import streamlit as st
import pandas as pd
import time
from datetime import datetime
import numpy as np

# --- 定数 ---
CANDIDATE_TBL = "candidate_master_tbl"
HISTORY_TBL = "approval_history_tbl"

# === モックデータの準備 (再修正版: 比較ロジック強化) ===
def get_mock_data():
    """本番データと承認候補データを模擬"""
    
    # 横に長いマスタを模擬 (10列)
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

    # 承認候補データ (変更点を含む)
    data_candidate = {
        'id': [1, 3, 4, 101, 102],
        'product_name': ["Alpha Widget", "Gamma Thing (Changed)", "Delta Plate", "New Item-X", "New Item-Y"], 
        'price': [100.0, 15.0, 70.0, 500.0, 75.0],                                            
        'vendor_id': ['V001', 'V003', 'V005', 'V006', 'V007'], # V005は変更
        'region': ['Tokyo', 'Fukuoka', 'Nagoya', 'Sapporo', 'Sendai'],                                
        'status': ['ACTIVE', 'DEPRECATED', 'ACTIVE', 'ACTIVE', 'ACTIVE'],
        'tax_code': ['A-10', 'A-10', 'B-20', 'C-30', 'A-10'],
        'created_date': [datetime(2023, 1, 1), datetime(2024, 1, 1), datetime(2024, 7, 1), datetime.now(), datetime.now()],
        'requires_review': [True, True, True, True, True]
    }
    df_cand = pd.DataFrame(data_candidate)
    
    review_cols = df_cand.columns.tolist()[:-1] # 最後のrequires_reviewを除外
    
    # 候補と本番をマージ
    df_merged = df_cand.merge(df_prod, on='id', how='left', suffixes=('_cand', '_prod'))
    
    # 変更フラグの列を作成
    for col in review_cols:
        if col != 'id':
            
            col_cand = f'{col}_cand'
            col_prod = f'{col}_prod'
            col_changed = f'{col}_changed'
            
            # 【修正点】比較のために、両方の列を文字列に変換してから NaN を '$$NONE$$' という特殊な文字列で埋める
            # これにより、型ミスマッチと NaN/None の扱いの両方を安全にする
            s_cand_str = df_merged[col_cand].astype(str).fillna('$$NONE$$')
            s_prod_str = df_merged[col_prod].astype(str).fillna('$$NONE$$')

            # 値が変更されたかどうかのブーリアン列
            df_merged[col_changed] = (s_cand_str != s_prod_str)
            
            # 【新規レコードの特別な扱い】
            # prod_str が '$$NONE$$' であり、かつ cand_str が '$$NONE$$' ではない場合、それは新規レコード（変更あり）
            is_new_record = (s_prod_str == '$$NONE$$') & (s_cand_str != '$$NONE$$')
            
            # 変更フラグに新規レコードを統合
            df_merged[col_changed] = df_merged[col_changed] | is_new_record


    return df_merged

# === 補助関数：縦型比較データの作成 ===
# （この関数は、外部からアクセスされるため、以前の安全なロジックを維持）
def create_vertical_diff(df_row: pd.Series):
    """選択された1レコードを縦型比較のためのDataFrameに変換"""
    data = []
    all_cols = set(df_row.index) 
    
    for col in all_cols:
        if col.endswith('_cand'):
            base_col = col.replace('_cand', '')
            
            col_prod = col.replace('_cand', '_prod')
            col_changed = f'{base_col}_changed'
            
            # .get()を使用して KeyError を回避
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
    # IDリストを文字列に変換
    ids_str = ", ".join(map(str, selected_ids))
    current_user = "MOCK_USER"
    time.sleep(1) 
    
    st.info(f"合計 {len(selected_ids)} 件のレコードに対してアクション実行中... ({action})")
    
    try:
        if action == "APPROVE":
            st.code(f"[処理模擬] MERGE INTO PRODUCTION_TBL WHERE id IN ({ids_str})")
            st.code(f"INSERT INTO {HISTORY_TBL} VALUES ('{datetime.now().isoformat()}', '{current_user}', 'APPROVED', [{ids_str}], NULL)")
            st.success(f"✅ 承認完了。レコードID {ids_str} が本番に展開されました。")
        elif action == "REJECT":
            st.code(f"DELETE FROM CANDIDATE_TBL WHERE id IN ({ids_str})")
            st.code(f"INSERT INTO {HISTORY_TBL} VALUES ('{datetime.now().isoformat()}', '{current_user}', 'REJECTED', [{ids_str}], '{reason}')")
            st.error(f"❌ 差し戻し完了。レコードID {ids_str} が候補テーブルから削除されました。")
        
        st.rerun() 

    except Exception as e:
        st.error("エラーが発生しました。処理は中断されました。")
        st.exception(e)
        st.rerun()


# === アプリケーションの UI メイン関数 ===
def master_approval_app():
    st.set_page_config(layout="wide")
    st.title("マスタ変更レビュー (縦型比較 & 差分ハイライト)")
    st.markdown("---")

    # 1. データの準備とセッション状態の初期化
    df_merged = get_mock_data()
    df_review = df_merged[df_merged['requires_review_cand'] == True]

    # 【初期化の強化】
    if 'selected_record_id' not in st.session_state:
        st.session_state['selected_record_id'] = None
    if 'radio_select_id' not in st.session_state:
        st.session_state['radio_select_id'] = None
    if 'data_editor_state' not in st.session_state:
        st.session_state['data_editor_state'] = None


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
            value=0 # デフォルトはすべて表示
        )
        
        df_filtered = df_summary[df_summary['変更列数'] >= min_changes].reset_index(drop=True)
        
        if df_filtered.empty:
            st.info("フィルタ条件を満たすレコードはありません。")
            st.stop()
            
        st.markdown("---")
            
        # 2. データエディタでの一覧表示と選択
        
        # 'select' 列を追加し、全てのレコードをデフォルトで未チェックにする
        # Streamlitのdata_editorの挙動として、編集されていない行はセッションに残らないため、この方法を取る
        df_filtered['select'] = False 
        
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
            key='data_editor_state' # セッション状態で変更状態を保持
        )

        # ユーザーがチェックを入れたレコードのIDを取得 (一括承認用)
        selected_ids_for_action = edited_df[edited_df.select]['id'].tolist()
        
        st.info(f"現在、**{len(selected_ids_for_action)}** 件のレコードが選択されています。")
        st.markdown("---")

        # 3. 単一レコードの縦型比較ビュー用IDの選択
        
        # 詳細レビュー用IDの選択ロジック
        available_ids = df_filtered['id'].tolist()
        
        # 前回選択したIDがリストから消えていたら、リストの最初のIDをデフォルトにする
        if st.session_state.selected_record_id not in available_ids:
            default_index = 0
            st.session_state.selected_record_id = available_ids[0]
        else:
            default_index = available_ids.index(st.session_state.selected_record_id)

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
            
            # 選択された行を抽出
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
