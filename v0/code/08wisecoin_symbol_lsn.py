import pandas as pd
import json
import os

def generate_symbol_lsn():
    """
    Reads 'wisecoin-市场概览.xlsx', filters based on '沉淀资金(亿)' > 0.5,
    and generates 'wisecoin-symbol-lsn.json' with directions based on '品种情绪'.
    """
    input_file = 'wisecoin-市场概览.xlsx'
    output_file = '../wisecoin-symbol-lsn.json'
    sheet_name = '期货品种'
    
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    try:
        # Read the Excel file
        df = pd.read_excel(input_file, sheet_name=sheet_name)
        
        # Filter: 沉淀资金(亿) > 0.5
        # Ensure '沉淀资金(亿)' is numeric
        df['沉淀资金(亿)'] = pd.to_numeric(df['沉淀资金(亿)'], errors='coerce')
        filtered_df = df[df['沉淀资金(亿)'] > 0.5].copy()
        
        if filtered_df.empty:
            print("No symbols found with '沉淀资金(亿)' > 0.5.")
            return

        # Mapping '品种情绪' to '开仓方向'
        # 偏多 -> LONG, 偏空 -> SHORT, 中性 -> NONE
        sentiment_map = {
            '偏多': 'LONG',
            '偏空': 'SHORT',
            '中性': 'NONE'
        }
        
        results = []
        for _, row in filtered_df.iterrows():
            symbol = row['品种代码']
            sentiment = row['品种情绪']
            direction = sentiment_map.get(sentiment, 'NONE')
            
            results.append({
                '品种代码': symbol,
                '开仓方向': direction
            })
            
        # Write to JSON file (replace if exists)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
            
        print(f"Successfully generated {output_file} with {len(results)} symbols.")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    generate_symbol_lsn()
