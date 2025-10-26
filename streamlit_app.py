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
@st.cache_data(show_spinner=False)
def load_all_mock_data():
    """データロードロジック"""
    
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
            
    df_merged['review_status'] = df_merged['requires_review_cand'].apply(
        lambda x: STATUS_OPTIONS['レビュー待ち'] if x else STATUS_OPTIONS['承認']
    )
    
    # 日付型を日付のみにする（フィルタのため）
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
            
            # 変更内容を簡潔にまとめる
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
    # 比較対象の列データをリストに格納
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
    
    # スタイルを適用する関数
    def highlight_changes(s):
        # '差分あり'列の値（ブール値）を取得
        is_changed = diff_df['差分あり']
        
        # '変更後 (Candidate)'列のみを対象とする
        if s.name == '変更後 (Candidate)':
            # '差分あり'がTrueの場合にハイライト色を、Falseの場合に空文字列を返す
            return ['background-color: #ffcccc' if changed else '' for changed in is_changed]
        
        # その他の列にはスタイルを適用しない
        return [''] * len(s)

    # st.dataframeに表示するために、不要な '差分あり' 列をドロップし、スタイルを適用
    styled_df = diff_df.drop(columns=['差分あり']).style.apply(highlight_changes, axis=0)
    
    return styled_df

# === 承認ロジックの模擬 (ページ単位で実行) ===
def execute_page_action(df_page: pd.DataFrame, bulk_approve_checked: bool, current_page: int, total_pages: int):
    
    processed_ids = []
    
    for index, row in df_page.iterrows():
        record_id = row['id']
        action_key = f'action_{record_id}'
        comment_key = f'comment_{record_id}'
        
        # 1. ラジオボタンの値を取得 (ユーザーが個別に操作した場合、この値が優先される)
        action_label = st.session_state.get(action_key)
        
        # 2. 一括承認フラグが立っている場合、ラジオボタンが 'レビュー待ち' のレコードを '承認' に上書き
        if bulk_approve_checked and action_label == 'レビュー待ち':
            action_label = '承認'
        
        # ラベルからコードを取得
        action = next((code for label, code in STATUS_OPTIONS.items() if label == action_label), STATUS_OPTIONS['レビュー待ち'])
        
        if action != STATUS_OPTIONS['レビュー待ち']:
            
            st.session_state['df_merged'].loc[
                st.session_state['df_merged']['id'] == record_id, 
                'review_status'
            ] = action
            
            processed_ids.append(record_id)
            
            # 処理後のセッションステートをクリア
            if action_key in st.session_state:
                 del st.session_state[action_key]
            if comment_key in st.session_state:
                 del st.session_state[comment_key] 
            
    # 一括承認チェックボックスの状態をクリア (次回描画でチェックが外れるように)
    if 'bulk_set_approve_checkbox' in st.session_state:
        st.session_state['bulk_set_approve_checkbox'] = False

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

# === アプリケーションの UI メイン関数 ===
def master_approval_app_v4():
    st.title("マスタ変更レビュー (表形式スクロールワークスペース)")

    # 1. データとセッション状態の初期化
    df_initial_merged = load_all_mock_data()
    
    if 'df_merged' not in st.session_state:
        st.session_state['df_merged'] = df_initial_merged.copy()
        
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
        
        # フィルタリング用の日付の最小値/最大値を取得
        min_date = st.session_state['df_merged']['created_date_cand_date'].min()
        max_date = st.session_state['df_merged']['created_date_cand_date'].max()
        
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
        if 'bulk_set_approve_checkbox' in st.session_state:
             st.session_state['bulk_set_approve_checkbox'] = False

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
    # 【メインコンテンツ: 表形式レビューフォーム】
    # ---------------------------

    # Streamlit Form を使用して、ページ単位で一括送信を可能にする
    with st.form(key=f'review_form_{st.session_state["current_page"]}'):
        
        # --- ヘッダー行の表示 ---
        header_cols = st.columns([0.5, 2, 1.5, 2, 2])
        header_cols[0].markdown("**ID**")
        header_cols[1].markdown("**変更サマリ**")
        header_cols[2].markdown("**差分詳細**")
        header_cols[3].markdown("##### **✅ アクション**")
        header_cols[4].markdown("##### **📝 コメント**")
        st.markdown("---")
        
        # 各レコードを縦に表示（各行はst.columnsで構成される）
        for index, row in df_page.iterrows():
            record_id = row['id']
            
            # デフォルトインデックスの決定
            current_label = st.session_state.get(f'action_{record_id}')
            default_index = OPTIONS_JP.index(current_label) if current_label in OPTIONS_JP else OPTIONS_JP.index('レビュー待ち')

            # --- レコード行の表示 ---
            row_cols = st.columns([0.5, 2, 1.5, 2, 2])
            
            # 1. ID
            with row_cols[0]:
                st.markdown(f"**{record_id}**")
                
            # 2. 変更サマリ
            with row_cols[1]:
                summary_text = create_vertical_summary(row)
                st.info(summary_text)

            # 3. 差分詳細 (ボタンとExpander)
            with row_cols[2]:
                with st.expander("🔍 詳細を確認"):
                    # 修正された関数を呼び出し、ハイライトされたDataFrameを表示
                    st.dataframe(
                        create_vertical_diff(row),
                        use_container_width=True,
                        hide_index=True
                    )

            # 4. アクション（OK/NG ラジオボタン）
            with row_cols[3]:
                st.radio(
                    "アクション",
                    options=OPTIONS_JP,
                    index=default_index, 
                    format_func=lambda x: f"✅ {x}" if x=='承認' else (f"❌ {x}" if x=='差し戻し' else x),
                    key=f'action_{record_id}',
                    horizontal=True,
                    label_visibility="collapsed" # ヘッダーがあるため非表示
                )
            
            # 5. コメント欄
            with row_cols[4]:
                st.text_area(
                    "コメント",
                    value=st.session_state.get(f'comment_{record_id}', ""),
                    key=f'comment_{record_id}',
                    height=70,
                    label_visibility="collapsed" # ヘッダーがあるため非表示
                )
            
            st.divider() # レコード間の区切り線

        # フォーム下部の一括チェックと送信ボタン
        
        st.markdown("---")
        st.checkbox(
            "このページの**「レビュー待ち」**レコードを、**一括で承認**する",
            value=st.session_state.get('bulk_set_approve_checkbox', False),
            key='bulk_set_approve_checkbox',
            help="このチェックボックスをオンにしてフォームを送信すると、個別に選択されていないレコードは全て「承認」として処理されます。",
        )
        
        submitted = st.form_submit_button(
            f"🎉 選択した {len(df_page)} 件を一括申請・実行", 
            type="primary",
            use_container_width=True
        )

        if submitted:
            # チェックボックスの状態をフォーム送信時に取得
            bulk_checked = st.session_state.get('bulk_set_approve_checkbox', False)
            
            # 処理を実行
            execute_page_action(df_page, bulk_checked, st.session_state['current_page'], total_pages)


# === アプリケーション実行 ===
if __name__ == "__main__":
    master_approval_app_v4()
