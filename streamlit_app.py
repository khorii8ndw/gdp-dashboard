# === 補助関数 2：縦型比較データの作成（ハイライト対応版） ===
def create_vertical_diff(df_row: pd.Series):
    data = []
    # どの列にスタイルを適用するかを制御するためのリスト
    candidate_cols = [] 
    
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
            # スタイルを適用したい列名 (変更後) を記録
            candidate_cols.append('変更後 (Candidate)')
    
    diff_df = pd.DataFrame(data)
    
    # スタイルを適用する関数
    def highlight_changes(s):
        # '差分あり'列がTrueの行に対して、CSSスタイルを適用
        is_changed = diff_df['差分あり']
        
        # '変更後 (Candidate)'列に対してのみスタイルを適用したい
        if s.name == '変更後 (Candidate)':
            return ['background-color: #ffcccc' if changed else '' for changed in is_changed]
        
        # それ以外の列にはスタイルを適用しない
        return [''] * len(s)

    # st.dataframeに表示するために、不要な '差分あり' 列をドロップし、スタイルを適用
    styled_df = diff_df.drop(columns=['差分あり']).style.apply(highlight_changes, axis=0)
    
    return styled_df
