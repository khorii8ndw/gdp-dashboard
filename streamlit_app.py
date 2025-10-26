import streamlit as st
import pandas as pd
import time
from datetime import datetime

# --- 定数 ---
CANDIDATE_TBL = "candidate_master_tbl"
HISTORY_TBL = "approval_history_tbl"

# === モックデータの準備 ===
def get_mock_data():
    """本番データと承認候補データを模擬"""
    
    # 横に長いマスタを模擬 (10列)
    data_production = {
        'id': [1, 2, 3],
        'product_name': ["Alpha Widget", "Beta Gadget", "Gamma Thing"],
        'price': [100.0, 50.0, 10.0],
        'vendor_id': ['V001', 'V002', 'V003'],
        'region': ['Tokyo', 'Osaka', 'Tokyo'],
        'status': ['ACTIVE', 'ACTIVE', 'ACTIVE'],
        'tax_code': ['A-10', 'A-10', 'A-10'],
        'memo_internal': ['Stable product.', 'Low stock.', 'New pricing needed.'],
        'created_date': [datetime(2023, 1, 1), datetime(2023, 5, 10), datetime(2024, 1, 1)],
        'requires_review': [False, False, False]
    }
    df_prod = pd.DataFrame(data_production)

    # 承認候補データ (変更点を含む)
    data_candidate = {
        'id': [1, 3, 101],
        'product_name': ["Alpha Widget", "Gamma Thing (Changed)", "New Item-X"], # 変更あり
        'price': [100.0, 15.0, 500.0],                                            # 変更あり
        'vendor_id': ['V001', 'V003', 'V004'],
        'region': ['Tokyo', 'Fukuoka', 'Sapporo'],                                # 変更あり
        'status': ['ACTIVE', 'DEPRECATED', 'ACTIVE'],
        'tax_code': ['A-10', 'A-10', 'B-20'],
        'memo_internal': ['Stable product.', 'Pricing approved by MGR.', 'Initial listing.'],
        'created_date': [datetime(2023, 1, 1), datetime(2024, 1, 1), datetime.now()],
        'requires_review': [True, True, True]
    }
    df_cand = pd.DataFrame(data_candidate)

    # DataFrameを結合して比較しやすい形式にする
    # 'id', 'product_name', 'price', 'vendor_id', 'region', 'status', 'tax_code', 'memo_internal', 'created_date', 'requires_review'
    review_cols = df_cand.columns.tolist()[:-1] # 最後のrequires_reviewを除外
    
    # 候補と本番をマージ
    df_merged = df_cand.merge(df_prod, on='id', how='left', suffixes=('_cand', '_prod'))
    
    # 変更フラグの列を作成
    for col in review_cols:
        if col != 'id':
             # 変更があったかどうかのブーリアン列を作成
            df_merged[f'{col}_changed'] = df_merged[f'{col}_cand'] != df_merged[f'{col}_prod']
            # 新規レコードの場合はTrueにする
            df_merged[f'{col}_changed'] = df_merged[f'{col}_changed'].fillna(df_merged[f'{col}_cand'].notna())

    return df_merged

# === 補助関数：変更のハイライト ===
def style_candidate_df(df):
    """変更があった列のみを黄色でハイライトするスタイル関数"""
    highlight_style = 'background-color: yellow'
    
    def highlight_row(row):
        styles = [''] * len(row)
        for i, col in enumerate(df.columns):
            # '_changed' フラグが立っている列を探し、対応する候補データをハイライト
            if col.endswith('_cand'):
                base_col = col.replace('_cand', '')
                if row[f'{base_col}_changed']:
                    styles[i] = highlight_style
        return styles

    # 表示用に必要な列だけを抽出
    display_cols = ['id'] + [col for col in df.columns if col.endswith('_cand')]
    
    return df[display_cols].rename(columns=lambda x: x.replace('_cand', '')).style.apply(highlight_row, axis=1)


# === 補助関数：縦型比較データの作成 ===
def create_vertical_diff(df_row):
    """選択された1レコードを縦型比較のためのDataFrameに変換"""
    data = []
    # すべての列をイテレートして、差分データを作成
    for col in df_row.index:
        if col.endswith('_cand'):
            base_col = col.replace('_cand', '')
            is_changed = df_row[f'{base_col}_changed'] if f'{base_col}_changed' in df_row.index else False
            
            data.append({
                '項目': base_col.replace('_', ' ').title(),
                '変更前 (Production)': df_row[col.replace('_cand', '_prod')],
                '変更後 (Candidate)': df_row[col],
                '差分あり': is_changed
            })
    
    diff_df = pd.DataFrame(data)
    # 変更があった行のみをハイライト
    def style_diff(s):
        return ['background-color: #ffe6e6' if s['差分あり'] else ''] * len(s)
        
    return diff_df.drop(columns=['差分あり']).style.apply(style_diff, axis=1)


# === 承認ロジックの模擬 ===
def execute_action(selected_id, action, reason):
    # ロジックは前回のモックと同様。ここではメッセージ表示のみ
    current_user = "MOCK_USER"
    time.sleep(1) 
    
    st.info(f"ID: {selected_id} のレコードに対してアクション実行中... ({action})")
    
    if action == "APPROVE":
        st.code(f"[処理模擬] MERGE INTO PRODUCTION_TBL WHERE id = {selected_id}")
        st.code(f"INSERT INTO {HISTORY_TBL} VALUES ('{datetime.now().isoformat()}', '{current_user}', 'APPROVED', {selected_id}, NULL)")
        st.success(f"✅ 承認完了。ID: {selected_id} が本番に展開されました。")
    elif action == "REJECT":
        st.code(f"DELETE FROM CANDIDATE_TBL WHERE id = {selected_id}")
        st.code(f"INSERT INTO {HISTORY_TBL} VALUES ('{datetime.now().isoformat()}', '{current_user}', 'REJECTED', {selected_id}, '{reason}')")
        st.error(f"❌ 差し戻し完了。ID: {selected_id} が候補テーブルから削除されました。")

    st.rerun()

# === アプリケーションの UI メイン関数 ===
def master_approval_app():
    st.title("マスタ変更レビュー (縦型比較 & 差分ハイライト)")
    st.markdown("---")

    # 1. データの準備とセッション状態の初期化
    df_merged = get_mock_data()
    df_review = df_merged[df_merged['requires_review_cand'] == True]

    if 'selected_record_id' not in st.session_state:
        st.session_state['selected_record_id'] = None

    if df_review.empty:
        st.success("🎉 承認待ちのレコードはありません。")
        return

    # 2. 承認対象の簡易リスト表示 (横スクロールを避けるために最低限の列のみ)
    st.subheader("承認待ちレコード一覧")
    
    # idと変更のあった列数を表示
    df_summary = df_review[['id']].copy()
    df_summary['変更列数'] = df_review.filter(like='_changed').sum(axis=1)
    
    # ユーザーがレコードを選択できるようにラジオボタンを使用
    selected_id = st.radio(
        "詳細を確認するレコードを選択:",
        df_summary['id'].tolist(),
        format_func=lambda x: f"ID: {x} (変更: {df_summary[df_summary['id'] == x]['変更列数'].iloc[0]}項目)",
        key='radio_select_id'
    )
    
    # 選択IDをセッションに保存
    st.session_state['selected_record_id'] = selected_id
    
    st.markdown("---")

    # 3. 縦型比較ビュー (選択されたレコードの詳細)
    if st.session_state['selected_record_id'] is not None:
        st.subheader(f"ID: {st.session_state['selected_record_id']} の変更点レビュー")
        
        # 選択された行を抽出
        selected_row = df_review[df_review['id'] == st.session_state['selected_record_id']].iloc[0]
        
        # 縦型比較データフレームを作成し表示
        st.dataframe(
            create_vertical_diff(selected_row),
            use_container_width=True
        )

        st.markdown("---")
        
        # 4. アクションエリア
        st.subheader("アクション実行")
        
        col1, col2 = st.columns(2)
        with col1:
            approve_button = st.button("✅ 承認実行 (APPROVE)", key="app_btn", use_container_width=True, type="primary")
        with col2:
            reject_button = st.button("❌ 差し戻し (REJECT)", key="rej_btn", use_container_width=True)

        reason = st.text_area("差し戻し理由 (REJECT時のみ)", key="reason_area")

        if approve_button or reject_button:
            action = "APPROVE" if approve_button else "REJECT"
            execute_action(st.session_state['selected_record_id'], action, reason)

# === アプリケーション実行 ===
if __name__ == "__main__":
    # setup_tables_and_data() # 初期データ準備は環境外で実行
    master_approval_app()
