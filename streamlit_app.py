import streamlit as st
import pandas as pd
import time
from datetime import datetime
import numpy as np
import math

# Streamlitのページ設定は必ずスクリプトの先頭で行う
st.set_page_config(layout="wide")

# --- 定数 ---
RECORDS_PER_PAGE = 10 # ページごとの表示件数
STATUS_OPTIONS = {'レビュー待ち': 'PENDING', '承認': 'APPROVE', '差し戻し': 'REJECT'}
OPTIONS_JP = list(STATUS_OPTIONS.keys())

# === データの初期化/モックデータの準備 (KeyError修正) ===
@st.cache_data(show_spinner=False)
def load_all_mock_data():
    """データロードロジック（KeyError修正）"""
    
    # データを増やすために1〜25番まで追加
    data_production = {
        'id': list(range(1, 26)),
        'product_name': [f"Item {i:03d}" for i in range(1, 26)],
        'price': [100.0 + i*5 for i in range(1, 26)],
        'vendor_id': [f'V{i:03d}' for i in range(1, 26)],
        'region': ['Tokyo', 'Osaka', 'Nagoya'] * 8 + ['Sapporo'],
        'status': ['ACTIVE'] * 25,
        'tax_code': ['A-10', 'B-20'] * 12 + ['A-10'],
        'created_date': [datetime(2023, 1, 1)] * 25,
        'requires_review': [False] * 25
    }
    df_prod = pd.DataFrame(data_production)

    # 変更候補データを20件作成
    changed_ids = [1, 5, 10, 15, 20] # 5件
    new_ids = list(range(101, 116))   # 15件
    
    data_candidate = {
        'id': changed_ids + new_ids,
        'product_name': [df_prod[df_prod['id']==i]['product_name'].iloc[0] + ' (UPDATED)' for i in changed_ids] + [f"New Item {i}" for i in new_ids],
        'price': [150.0, 550.0, 110.0, 75.0, 1050.0] + [50.0 + i for i in new_ids],
        'vendor_id': ['V001', 'V005', 'V010', 'V015', 'V020'] + [f'V{i:03d}' for i in new_ids],
        'region': ['Fukuoka', 'Osaka', 'Tokyo', 'Sendai', 'Sapporo'] + ['Hokkaido'] * 15,
        'status': ['ACTIVE', 'DEPRECATED', 'ACTIVE', 'DEPRECATED', 'ACTIVE'] + ['ACTIVE'] * 14 + ['DEPRECATED'],
        'tax_code': ['A-10', 'C-30', 'A-10', 'B-20', 'C-30'] + ['A-10'] * 15,
        'created_date': [datetime(2023, 1, 1)] * 5 + [datetime.now()] * 15,
        'requires_review': [True] * 20
    }
    df_cand = pd.DataFrame(data_candidate)
    
    review_cols = [col for col in df_cand.columns if col not in ['id', 'requires_review']]
    df_merged = df_cand.merge(df_prod, on='id', how='left', suffixes=('_cand', '_prod'))
    
    # 新規レコードかどうかのフラグ
    df_merged['is_new_record'] = df_merged['product_name_prod'].isna()
    
    for col in review_cols:
        col_cand = f'{col}_cand'
        col_prod = f'{col}_prod'
        col_changed = f'{col}_changed'
            
        s_cand_str = df_merged[col_cand].astype(str).fillna('__NONE__')
        s_prod_str = df_merged[col_prod].astype(str).fillna('__NONE__')

        df_merged[col_changed] = (s_cand_str != s_prod_str)
            
    # 【★修正箇所】カラム名を 'requires_review_cand' に修正
    df_merged['review_status'] = df_merged['requires_review_cand'].apply(
        lambda x: STATUS_OPTIONS['レビュー待ち'] if x else STATUS_OPTIONS['承認']
    )
    
    # 日付型を日付のみにする（フィルタのため）
    df_merged['created_date_cand_date'] = pd.to_datetime(df_merged['created_date_cand']).dt.date
    
    return df_merged

# === 補助関数 1：変更サマリーの自動生成 (変更なし) ===
def create_vertical_summary(df_row: pd.Series):
    is_new_record = pd.isna(df_row.get('product_name_prod', np.nan)) 
    
    if is_new_record:
        return f"**新規レコード**が登録されようとしています。"
        
    changes = []
    for key, is_changed in df_row.filter(like='_changed').items():
        if is_changed:
            base_col = key.replace('_changed', '')
            col_name = base_col.replace('_', ' ').title()
            val_prod = df_row.get(f'{base_col}_prod', 'N/A')
            val_cand = df_row.get(f'{base_col}_cand', 'N/A')
            if base_col == 'created_date':
                 changes.append(f"作成日 ({col_name}) が更新されました。")
            elif pd.isna(val_prod):
                 changes.append(f"{col_name} が {val_cand} に設定されました。")
            else:
                 changes.append(f"{col_name} が **{val_prod}** から **{val_cand}** に変更されました。")

    if changes:
        return "**既存レコードの変更点:** " + " ".join(changes)
    else:
        return "このレコードには明らかな変更点はありません。(エラーの可能性)"

# === 補助関数 2：縦型比較データの作成 (変更なし) ===
def create_vertical_diff(df_row: pd.Series):
    data = []
    all_cols = set(df_row.index) 
    
    for col in all_cols:
        if col.endswith('_cand') and col not in ['requires_review_cand', 'review_status', 'is_new_record', 'created_date_cand_date']:
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

# === 承認ロジックの模擬 (ページ単位で実行) (変更なし) ===
def execute_page_action(df_page: pd.DataFrame, submitted_data: dict, current_page: int, total_pages: int):
    
    processed_ids = []
    
    for index, row in df_page.iterrows():
        record_id = row['id']
        action_key = f'action_{record_id}'
        
        action_label = st.session_state.get(action_key)
        
        action = next((code for label, code in STATUS_OPTIONS.items() if label == action_label), STATUS_OPTIONS['レビュー待ち'])
        
        if action != STATUS_OPTIONS['レビュー待ち']:
            
            st.session_state['df_merged'].loc[
                st.session_state['df_merged']['id'] == record_id, 
                'review_status'
            ] = action
            
            processed_ids.append(record_id)
            
            # 処理後のラジオボタンの状態をクリアして次回描画に備える
            del st.session_state[action_key]
            
    # 一括承認ボタンのデフォルト状態もクリア
    if 'bulk_set_approve' in st.session_state:
        del st.session_state['bulk_set_approve']

    if processed_ids:
        st.success(f"✅ このページで合計 **{len(processed_ids)} 件** のアクションが実行され、状態が更新されました。")
    else:
        st.warning("このページで承認または差し戻しのアクションは実行されませんでした。")
        
    # 次のページへ自動で移動
    if current_page < total_pages:
        st.session_state['current_page'] = current_page + 1
    else:
        st.info("全てのページのレビューが完了しました。")
        st.session_state['current_page'] = 1 # 最初のページに戻す

    st.rerun()

# === アプリケーションの UI メイン関数 (変更なし) ===
def master_approval_app_v3():
    st.title("マスタ変更レビュー (縦型スクロールワークスペース)")

    # 1. データとセッション状態の初期化
    df_initial_merged = load_all_mock_data()
    
    if 'df_merged' not in st.session_state:
        st.session_state['df_merged'] = df_initial_merged.copy()
        
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = 1
        
    if 'bulk_set_approve' not in st.session_state:
        st.session_state['bulk_set_approve'] = False
        
    # --- フィルタ設定エリア ---
    with st.expander("⚙️ レビュー対象のフィルタ設定", expanded=True):
        col_group, col_date_start, col_date_end = st.columns([1, 1, 1])
        
        with col_group:
            filter_group = st.radio(
                "レコード種別",
                options=['全て', '新規レコード', '既存レコード変更'],
                index=0,
                horizontal=True
            )
        
        # フィルタリング用の日付の最小値/最大値を取得
        min_date = st.session_state['df_merged']['created_date_cand_date'].min()
        max_date = st.session_state['df_merged']['created_date_cand_date'].max()
        
        with col_date_start:
            filter_date_start = st.date_input(
                "更新開始日", 
                value=min_date, 
                min_value=min_date, 
                max_value=max_date
            )
        with col_date_end:
            filter_date_end = st.date_input(
                "更新終了日", 
                value=max_date, 
                min_value=min_date, 
                max_value=max_date
            )

    # 2. フィルタの適用
    df_active_review = st.session_state['df_merged'][
        st.session_state['df_merged']['review_status'] == STATUS_OPTIONS['レビュー待ち']
    ].copy()
    
    # グループフィルタ適用
    if filter_group == '新規レコード':
        df_active_review = df_active_review[df_active_review['is_new_record'] == True]
    elif filter_group == '既存レコード変更':
        df_active_review = df_active_review[df_active_review['is_new_record'] == False]
        
    # 日付フィルタ適用
    df_active_review = df_active_review[
        (df_active_review['created_date_cand_date'] >= filter_date_start) & 
        (df_active_review['created_date_cand_date'] <= filter_date_end)
    ].sort_values(by='id').reset_index(drop=True)
    
    # フィルタ後の件数確認
    if df_active_review.empty:
        st.success("🎉 現在のフィルタ条件を満たすレビュー対象レコードはありません。")
        return

    # --- ページネーションの計算 ---
    total_records = len(df_active_review)
    total_pages = math.ceil(total_records / RECORDS_PER_PAGE)
    
    # フィルタが変わったらページをリセット
    if 'last_filter_records' not in st.session_state or st.session_state['last_filter_records'] != total_records:
        st.session_state['current_page'] = 1
        st.session_state['last_filter_records'] = total_records

    # ページネーションロジック
    start_index = (st.session_state['current_page'] - 1) * RECORDS_PER_PAGE
    end_index = min(start_index + RECORDS_PER_PAGE, total_records)
    
    df_page = df_active_review.iloc[start_index:end_index].copy()

    # --- ページヘッダーとナビゲーション ---
    st.header(f"📚 レビュー対象: {total_records} 件 (残り)")
    
    col_status, col_page_nav = st.columns([1, 1])
    
    with col_status:
        st.markdown(f"**現在のページ:** {st.session_state['current_page']} / {total_pages} (表示件数: {len(df_page)} 件)")
    
    with col_page_nav:
        
        col_prev, col_next = st.columns(2)
        with col_prev:
            if st.session_state['current_page'] > 1:
                st.button("前のページへ", on_click=lambda: st.session_state.update({'current_page': st.session_state['current_page'] - 1}), use_container_width=True)
        with col_next:
            if st.session_state['current_page'] < total_pages:
                st.button("次のページへ", on_click=lambda: st.session_state.update({'current_page': st.session_state['current_page'] + 1}), use_container_width=True)

    st.markdown("---")
    
    # ---------------------------
    # 【メインコンテンツ: 縦型レビューフォーム】
    # ---------------------------

    # 一括承認ボタンが押された際のコールバック関数
    def set_bulk_approve_callback():
        # フラグをTrueにするだけで、フォーム内のラジオボタンのデフォルト値が次回描画時に変わる
        st.session_state['bulk_set_approve'] = True

    # Streamlit Form を使用して、ページ単位で一括送信を可能にする
    with st.form(key=f'review_form_{st.session_state["current_page"]}'):
        
        # === フォーム上部: 一括チェックボタン ===
        st.button(
            "✅ このページの全てを**承認**に設定", 
            on_click=set_bulk_approve_callback, 
            type="secondary",
            use_container_width=False # ページ上のボタンは幅を抑える
        )
        st.markdown("---")
        
        # 各レコードを縦に表示
        for index, row in df_page.iterrows():
            record_id = row['id']
            
            # ページの一括ボタンが押された場合、デフォルト値を '承認' (Index 0) に設定する
            # そうでない場合は、デフォルト値を 'レビュー待ち' (Index 2) に設定する
            default_index = 0 if st.session_state['bulk_set_approve'] else 2
            
            # 各レコードのコンテナ
            with st.container(border=True):
                
                # タイトルとサマリを横並びに
                col_id, col_summary = st.columns([1, 3])
                
                with col_id:
                     st.subheader(f"ID: {record_id}")
                
                with col_summary:
                    summary_text = create_vertical_summary(row)
                    st.info(summary_text)

                # 変更詳細 (「モーダル」の代わりに、ボタン操作に見えるように調整)
                with st.expander("🔍 差分詳細を確認（クリックで開閉）"):
                    st.dataframe(
                        create_vertical_diff(row),
                        use_container_width=True,
                        hide_index=True
                    )
                
                # OK/NG チェック（ラジオボタン）
                st.markdown("##### 💡 アクションを選択してください")
                
                st.radio(
                    "この変更をどうしますか？",
                    options=OPTIONS_JP,
                    # 注意: ラジオボタンはフォーム外でデフォルトインデックスを設定しても、
                    # ユーザーが操作するとセッションステートに値が残り、その値が優先される。
                    # フォーム内の要素なので、フォーム送信時以外はセッションステートを参照させないようにする
                    index=default_index, 
                    format_func=lambda x: f"✅ {x}" if x=='承認' else (f"❌ {x}" if x=='差し戻し' else x),
                    key=f'action_{record_id}', # フォーム送信時にこのキーで値を取得
                    horizontal=True
                )
            
            st.divider() # 各レコード間の視覚的な区切り

        # フォームの送信ボタン (ページ一括アクション)
        st.markdown("##### 📝 一括アクションの理由/コメント (オプション)")
        reason = st.text_area("コメント", key='page_reason')
        
        submitted = st.form_submit_button(
            f"🎉 選択した {len(df_page)} 件を一括申請・実行", 
            type="primary",
            use_container_width=True
        )

        if submitted:
            # execute_page_actionで処理を実行
            execute_page_action(df_page, None, st.session_state['current_page'], total_pages)


# === アプリケーション実行 ===
if __name__ == "__main__":
    master_approval_app_v3()
