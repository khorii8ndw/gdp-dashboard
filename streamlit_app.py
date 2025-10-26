import streamlit as st
import pandas as pd
import time
from datetime import datetime

# --- 定数 ---
# Databricksのテーブルを模擬
CANDIDATE_TBL = "candidate_master_tbl"
PRODUCTION_TBL = "production_master_tbl"
HISTORY_TBL = "approval_history_tbl"

# === モックデータの準備 ===
def get_mock_candidate_data():
    """Databricksから読み込むデータを模擬"""
    data = {
        'id': [1, 2, 3, 101, 102],
        'product_name': ["A-Widget", "B-Gadget (No Change)", "C-Thing", "New-Item-X", "New-Item-Y"],
        'price': [10.0, 25.0, 5.0, 50.0, 75.0],
        'status': ["ACTIVE", "ACTIVE", "DEPRECATED", "ACTIVE", "ACTIVE"],
        'requires_review': [True, False, True, True, True] # レビューが必要なレコード
    }
    df = pd.DataFrame(data)
    # レビューが必要なものだけを返す
    return df[df['requires_review'] == True].head(100)

# === 承認ロジック本体 ===
def execute_action(ids_str, action, reason):
    # Databricks環境の代わりに現在のユーザーと時刻を模擬
    current_user = "MOCK_USER_ID_123"
    
    record_ids = [id.strip() for id in ids_str.split(',') if id.strip().isdigit()]
    if not record_ids:
        st.error("有効なレコードIDが指定されていません。")
        return

    st.info(f"アクション実行中... ({action})")
    time.sleep(1) # 処理時間を模擬

    try:
        if action == "APPROVE":
            # 1. 本番マスタへのマージ（模擬）
            st.code(f"""
                [Databricks 処理の模擬]
                MERGE INTO {PRODUCTION_TBL} AS target
                USING candidate_master_tbl
                ... 承認されたID ({ids_str}) のみを本番にマージ ...
            """)

            # 2. 履歴の記録（模擬）
            st.code(f"INSERT INTO {HISTORY_TBL} VALUES ('{datetime.now().isoformat()}', '{current_user}', 'APPROVED', {record_ids}, NULL)")
            st.success(f"✅ 承認完了。レコードID {ids_str} は本番環境に展開されました。(模擬)")

        elif action == "REJECT":
            # 1. 候補テーブルからの削除（模擬）
            st.code(f"DELETE FROM {CANDIDATE_TBL} WHERE id IN ({ids_str})")

            # 2. 履歴の記録（模擬）
            st.code(f"INSERT INTO {HISTORY_TBL} VALUES ('{datetime.now().isoformat()}', '{current_user}', 'REJECTED', {record_ids}, '{reason}')")
            st.error(f"❌ 差し戻し完了。レコードID {ids_str} は候補テーブルから削除されました。(模擬)")

    except Exception as e:
        st.error("エラーが発生しました。")
        st.exception(e)
        return

    # 処理後、画面を再描画して承認済みレコードを消す (Streamlitの標準機能)
    st.rerun()


# === アプリケーションの UI メイン関数 ===
def master_approval_app():
    st.title("マスタ変更 承認ダッシュボード (モック版)")
    st.markdown("---")

    # 1. モックデータの読み込み
    candidate_df_pd = get_mock_candidate_data()

    if candidate_df_pd.empty:
        st.success("🎉 現在、承認待ちのレコードはありません。")
        return

    st.subheader(f"承認待ちのレコード（{len(candidate_df_pd)} 件）")
    
    # 変更を強調表示
    def highlight_review(s):
        return ['background-color: #e6f7ff'] * len(s) if s['requires_review'] else [''] * len(s)

    # DataFrame表示
    st.dataframe(
        candidate_df_pd.style.apply(highlight_review, axis=1),
        use_container_width=True
    )

    # 2. アクションエリア
    st.markdown("---")
    st.subheader("アクション実行")

    # 以前の値がセッションに残っている場合のリセット（Streamlitの挙動）
    if 'record_ids_input' not in st.session_state:
        st.session_state['record_ids_input'] = "1, 101"

    record_ids_input = st.text_input("承認または差し戻しするレコード ID (カンマ区切り)", 
                                    value=st.session_state['record_ids_input'], 
                                    key='record_ids_key')
    
    col1, col2 = st.columns(2)
    with col1:
        approve_button = st.button("✅ 承認実行 (APPROVE)", use_container_width=True, type="primary")
    with col2:
        reject_button = st.button("❌ 差し戻し (REJECT)", use_container_width=True)

    reason = st.text_area("差し戻し理由 (REJECT時のみ)", "")
    
    # 3. アクション実行のトリガー
    if approve_button or reject_button:
        action = "APPROVE" if approve_button else "REJECT"
        execute_action(st.session_state.record_ids_key, action, reason)

# アプリケーションの実行
if __name__ == "__main__":
    master_approval_app()
