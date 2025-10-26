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

# === データの初期化/モックデータの準備 ===
def load_all_mock_data():
    """データロードロジック"""
    
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
    
    df_merged['is_new_record'] = df_merged['product_name_prod'].isna()
    
    for col in review_cols:
        col_cand = f'{col}_cand'
        col_prod = f'{col}_prod'
        col_changed = f'{col}_changed'
            
        s_cand_str = df_merged[col_cand].astype(str).fillna('__NONE__')
        s_prod_str = df_merged[col_prod].astype(str).fillna('__NONE__')

        df_merged[col_changed] = (s_cand_str != s_prod_str)
            
    df_merged['review_status'] = df_merged['requires_review_cand'].apply(
        lambda x: STATUS_OPTIONS['レビュー待ち'] if x else STATUS_OPTIONS['承認']
    )
    
    df_merged['created_date_cand_date'] = pd.to_datetime(df_merged['created_date_cand']).dt.date
    
    return df_merged

# === 補助関数 1：変更サマリーの自動生成 ===
def create_vertical_summary(df_row: pd.Series):
    is_new_record = pd.isna(df_row.get('product_name_prod', np.nan)) 
    
    if is_new_record:
        return "**新規レコード**が登録されようとしています。"
        
    changes = []
    for key, is_changed in df_row.filter(like='_changed').items():
        if is_changed:
            base_col = key.replace('_changed', '')
            col_name = base_col.replace('_', ' ').title()
            val_prod = df_row.get(f'{base_col}_prod', 'N/A')
            val_cand = df_row.get(f'{base_col}_cand', 'N/A')
            
            if base_col == 'product_name':
                changes.append(f"品名が変更されました。")
            elif base_col == 'price':
                changes.append(f"価格が {val_prod} から {val_cand} に変更されました。")
            else:
                 changes.append(f"{col_name}が変更されました。")

    if changes:
        return " | ".join(changes)
    else:
        return "変更なし (レビュー対象外の可能性)"

# === 補助関数 2：縦型比較データの作成（ハイライト対応版） ===
def create_vertical_diff(df_row: pd.Series):
    data = []
    
    for col in df_row.index:
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
    
    is_changed_list = diff_df['差分あり'].tolist()
    
    def highlight_changes(s):
        if s.name == '変更後 (Candidate)':
            return ['background-color: #ffcccc' if changed else '' for changed in is_changed_list]
        
        return [''] * len(s)

    styled_df = diff_df.drop(columns=['差分あり']).style.apply(highlight_changes, axis=0)
    
    return styled_df

# === 承認ロジックの模擬 (ページ単位で実行) ===
def execute_page_action(df_page: pd.DataFrame, bulk_approve_checked: bool):
    
    processed_ids = []
    
    # 提案 6: コメントログの初期化
    if 'comments_log' not in st.session_state:
        st.session_state['comments_log'] = {}
    
    for index, row in df_page.iterrows():
        record_id = row['id']
        action_key = f'action_{record_id}'
        comment_key = f'comment_{record_id}'
        
        action_label = st.session_state.get(action_key)
        comment_text = st.session_state.get(comment_key, '').strip() 
        
        action_to_be_executed = action_label
        # 一括承認がチェックされており、かつ個別アクションが「レビュー待ち」の場合に上書き
        if bulk_approve_checked and action_label == 'レビュー待ち':
            action_to_be_executed = '承認'
        
        # コードを取得
        action = next((code for label, code in STATUS_OPTIONS.items() if label == action_to_be_executed), STATUS_OPTIONS['レビュー待ち'])
        
        if action != STATUS_OPTIONS['レビュー待ち']:
            
            # 状態更新
            st.session_state['df_merged'].loc[
                st.session_state['df_merged']['id'] == record_id, 
                'review_status'
            ] = action
            
            # 提案 6: コメントログの保存
            if comment_text or action != STATUS_OPTIONS['レビュー待ち']:
                 st.session_state['comments_log'][record_id] = {
                    'comment': comment_text,
                    'action': action_to_be_executed,
                    'timestamp': datetime.now()
                }

            processed_ids.append(record_id)
            
    if processed_ids:
        # 提案 3: 成功メッセージを簡潔に
        st.success(f"✅ {len(processed_ids)}件を処理しました。")
        return True # 処理成功
    else:
        st.warning("このページで承認または差し戻しのアクションは実行されませんでした。")
        return False # 処理失敗

# === アプリケーションの UI メイン関数 ===
def master_approval_app_v6():
    st.title("マスタ変更レビュー (表形式スクロールワークスペース)")

    # 1. データとセッション状態の初期化
    if 'df_merged' not in st.session_state:
        st.session_state['df_merged'] = load_all_mock_data().copy()
        
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = 1
        
    # --- フィルタ設定エリア ---
    with st.expander("⚙️ レビュー対象のフィルタ設定", expanded=True):
        col_group, col_date_start, col_date_end = st.columns([1, 1, 1])
        
        with col_group:
            filter_group = st.radio(
                "レコード種別",
                options=['全て', '新規レコード', '既存レコード変更'],
                index=0,
                horizontal=True,
                key='filter_group_radio'
            )
        
        # 提案 5: 日付フィルタのエラー回避
        try:
            min_date = st.session_state['df_merged']['created_date_cand_date'].min()
            max_date = st.session_state['df_merged']['created_date_cand_date'].max()
        except:
            min_date = max_date = datetime.now().date()
            
        
        with col_date_start:
            filter_date_start = st.date_input(
                "更新開始日", 
                value=min_date, 
                min_value=min_date, 
                max_value=max_date,
                key='filter_date_start'
            )
        with col_date_end:
            filter_date_end = st.date_input(
                "更新終了日", 
                value=max_date, 
                min_value=min_date, 
                max_value=max_date,
                key='filter_date_end'
            )
    
    # フィルタ変更検知とページリセット
    current_filter = (filter_group, filter_date_start, filter_date_end)
    if st.session_state.get('last_filter') != current_filter:
        st.session_state['current_page'] = 1
        st.session_state['last_filter'] = current_filter
        st.session_state['selected_detail_id'] = None 
        keys_to_delete = [k for k in st.session_state.keys() 
                          if k.startswith('action_') or k.startswith('comment_')]
        for k in keys_to_delete:
            del st.session_state[k]

    # 2. フィルタの適用
    df_active_review = st.session_state['df_merged'][
        st.session_state['df_merged']['review_status'] == STATUS_OPTIONS['レビュー待ち']
    ].copy()
    
    if filter_group == '新規レコード':
        df_active_review = df_active_review[df_active_review['is_new_record'] == True]
    elif filter_group == '既存レコード変更':
        df_active_review = df_active_review[df_active_review['is_new_record'] == False]
        
    df_active_review = df_active_review[
        (df_active_review['created_date_cand_date'] >= filter_date_start) & 
        (df_active_review['created_date_cand_date'] <= filter_date_end)
    ].sort_values(by='id').reset_index(drop=True)
    
    total_records = len(df_active_review)
    if total_records == 0:
        st.success("🎉 現在のフィルタ条件を満たすレビュー対象レコードはありません。")
        return

    # --- ページネーションの計算 ---
    total_pages = math.ceil(total_records / RECORDS_PER_PAGE)
    start_index = (st.session_state['current_page'] - 1) * RECORDS_PER_PAGE
    end_index = min(start_index + RECORDS_PER_PAGE, total_records)
    
    df_page = df_active_review.iloc[start_index:end_index].copy()
    current_page_ids = df_page['id'].tolist()

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
    # 【メインコンテンツ: 表形式レビューフォーム】
    # ---------------------------
    
    # 一括承認チェックボックス
    col_bulk, col_bulk_info = st.columns([2, 5])
    with col_bulk:
        bulk_approve_checked = st.checkbox(
            "🚀 このページの**「レビュー待ち」**レコードを、**一括で承認**する",
            value=False,
            key='bulk_approve_checkbox_ui',
            help="このチェックボックスをオンにしてフォームを送信すると、個別に選択されていないレコードは全て「承認」として処理されます。",
        )
    with col_bulk_info:
         st.caption("⚠️ 個別のアクション選択が優先されます")
    
    # 提案 2: 一括承認の挙動を視覚的にフィードバック
    if bulk_approve_checked:
        pending_count = sum(1 for rid in current_page_ids 
                            if st.session_state.get(f'action_{rid}') == 'レビュー待ち')
        st.info(f"ℹ️ 現在のページで一括承認対象となる「レビュー待ち」レコードは **{pending_count}件** です。")


    # フォームの前に action_ の初期値を一括設定
    for record_id in current_page_ids:
        action_key = f'action_{record_id}'
        if action_key not in st.session_state:
            st.session_state[action_key] = 'レビュー待ち'

    # Streamlit Form
    with st.form(key=f'review_form_{st.session_state["current_page"]}'):
        
        # ヘッダー行
        header_cols = st.columns([0.5, 2.5, 1.5, 3])
        header_cols[0].markdown("**ID**")
        header_cols[1].markdown("**変更サマリ**")
        header_cols[2].markdown("##### **✅ アクション**")
        header_cols[3].markdown("##### **📝 コメント**")
        st.markdown("---")
        
        for index, row in df_page.iterrows():
            record_id = row['id']
            action_key = f'action_{record_id}'
            comment_key = f'comment_{record_id}'
            
            current_label = st.session_state[action_key]
            default_index = OPTIONS_JP.index(current_label) 

            # レコード行
            row_cols = st.columns([0.5, 2.5, 1.5, 3])
            
            with row_cols[0]:
                st.markdown(f"**{record_id}**")
                
            with row_cols[1]:
                summary_text = create_vertical_summary(row)
                st.info(summary_text)
            
            with row_cols[2]:
                st.radio(
                    "アクション",
                    options=OPTIONS_JP,
                    index=default_index, 
                    format_func=lambda x: f"✅ {x}" if x=='承認' else (f"❌ {x}" if x=='差し戻し' else x),
                    key=action_key,
                    horizontal=True,
                    label_visibility="collapsed"
                )
            
            with row_cols[3]:
                st.text_area(
                    "コメント",
                    value=st.session_state.get(comment_key, ""),
                    key=comment_key,
                    height=70,
                    label_visibility="collapsed" 
                )
            
            st.divider()

        # 送信ボタン
        submitted = st.form_submit_button(
            f"🎉 選択した {len(df_page)} 件を一括申請・実行", 
            type="primary",
            use_container_width=True
        )

        if submitted:
            processing_success = execute_page_action(df_page, bulk_approve_checked)

            # ページ遷移ロジック
            if processing_success:
                if st.session_state['current_page'] < total_pages:
                    st.session_state['current_page'] += 1
                else:
                    # 提案 4: 最後のページで処理完了後もページを維持
                    st.success("🎉 全てのページのレビューが完了しました！")
            
            # フォーム送信で自動的にrerunされる

    # フォームの後に詳細表示セクションを配置
    st.markdown("---")
    st.subheader("🔍 詳細差分ビュー")
    
    col_detail_select, col_detail_placeholder = st.columns([2, 5])
    
    with col_detail_select:
        selected_detail_id = st.selectbox(
            "詳細を表示するレコードを選択", 
            options=[None] + current_page_ids, 
            format_func=lambda x: f"ID: {x}" if x else "レコードIDを選択してください",
            key='selected_detail_id'
        )
    
    if selected_detail_id:
        # 提案 1: df_pageから取得することで効率化
        detail_row = df_page[df_page['id'] == selected_detail_id].iloc[0]
        st.dataframe(
            create_vertical_diff(detail_row),
            use_container_width=True,
            hide_index=True
        )


# === アプリケーション実行 ===
if __name__ == "__main__":
    master_approval_app_v6()
