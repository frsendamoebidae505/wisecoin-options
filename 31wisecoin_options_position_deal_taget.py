import pandas as pd
import os
import sys
import re

# ================= Configuration =================
# Margin Range Configuration (卖方保证金范围)
MIN_MARGIN = 10000
MAX_MARGIN = 80000

# Night Trading Varieties Configuration (夜盘品种代码集合)
# Based on common night trading lists for SHFE, DCE, CZCE, INE
# Users can add or remove varieties here to configure night trading filter
NIGHT_TRADING_VARIETIES = {
    # SHFE (上期所)
    'au', 'ag', 'cu', 'al', 'zn', 'pb', 'ni', 'sn', 'ss', 'ru', 'sp', 'rb', 'hc', 'bu', 'fu',
    # DCE (大商所)
    'm', 'y', 'a', 'b', 'p', 'c', 'cs', 'j', 'jm', 'i', 'l', 'v', 'pp', 'pg', 'eb', 'eg',
    # CZCE (郑商所)
    'CF', 'SR', 'TA', 'MA', 'FG', 'RM', 'OI', 'ZC', 'SA', 'PF', 'PK',
    # INE (能源中心)
    'sc', 'nr', 'lu', 'bc'
}
# =================================================

def get_variety_code(symbol):
    """
    Extracts variety code from symbol string.
    e.g., 'DCE.lh2605-P-14000' -> 'lh'
          'CFFEX.MO2602-C-8400' -> 'MO'
    """
    try:
        if isinstance(symbol, str) and '.' in symbol:
            # Take the part after the exchange prefix (e.g., 'lh2605-P-14000')
            part = symbol.split('.', 1)[1]
            # Extract leading alphabets (e.g., 'lh')
            match = re.match(r'^[A-Za-z]+', part)
            if match:
                return match.group(0)
    except Exception:
        pass
    return None

def main():
    # Define file paths
    quotes_file = 'wisecoin-期权行情.xlsx'
    ref_file = 'wisecoin-期权参考.xlsx'
    output_file = 'wisecoin-吃单.xlsx'

    # Check input files
    if not os.path.exists(quotes_file):
        print(f"Error: {quotes_file} not found.")
        return
    if not os.path.exists(ref_file):
        print(f"Error: {ref_file} not found.")
        return

    print("Loading data...")
    try:
        # Read all sheets from quotes file
        print(f"Reading all sheets from {quotes_file}...")
        quotes_dict = pd.read_excel(quotes_file, sheet_name=None)
        df_quotes = pd.concat(quotes_dict.values(), ignore_index=True)
        
        df_ref = pd.read_excel(ref_file, sheet_name='期权参考')
    except Exception as e:
        print(f"Error reading Excel files: {e}")
        return

    print(f"Quotes records: {len(df_quotes)}")
    print(f"Ref records: {len(df_ref)}")

    # Ensure join keys are strings and strip whitespace
    df_quotes['instrument_id'] = df_quotes['instrument_id'].astype(str).str.strip()
    df_ref['合约代码'] = df_ref['合约代码'].astype(str).str.strip()

    # Merge dataframes
    merged_df = pd.merge(df_ref, df_quotes, left_on='合约代码', right_on='instrument_id', how='inner')
    print(f"Merged records: {len(merged_df)}")

    # Filter 1: 盘口无挂单 (No orders in order book)
    bid_vol = merged_df['bid_volume1'].fillna(0)
    ask_vol = merged_df['ask_volume1'].fillna(0)
    no_orders_mask = (bid_vol <= 0) & (ask_vol <= 0)
    
    # Filter 2: 卖方保证金 in [MIN_MARGIN, MAX_MARGIN]
    merged_df['卖方保证金'] = pd.to_numeric(merged_df['卖方保证金'], errors='coerce')
    margin_mask = (merged_df['卖方保证金'] >= MIN_MARGIN) & (merged_df['卖方保证金'] <= MAX_MARGIN)

    # Filter 3: 夜盘品种 (Night Trading Variety)
    # Extract variety code for each row
    merged_df['variety_code'] = merged_df['合约代码'].apply(get_variety_code)
    # Check if variety code is in the configured set
    night_trading_mask = merged_df['variety_code'].isin(NIGHT_TRADING_VARIETIES)

    # Combine filters
    final_mask = no_orders_mask & margin_mask & night_trading_mask
    result_df = merged_df[final_mask].copy()

    print(f"Records matching 'No Orders': {no_orders_mask.sum()}")
    print(f"Records matching 'Margin {MIN_MARGIN}-{MAX_MARGIN}': {margin_mask.sum()}")
    print(f"Records matching 'Night Trading': {night_trading_mask.sum()}")
    print(f"Final matching records: {len(result_df)}")

    # Select output columns
    output_cols = [
        '合约代码', '合约名称', '标的合约', '期权类型',
        '卖方保证金', '买方期权费', 
        'bid_price1', 'bid_volume1', 'ask_price1', 'ask_volume1',
        'last_price', 'volume', 'open_interest',
        'datetime', '交易所', 'variety_code'
    ]
    
    # Keep only columns that exist
    final_cols = [c for c in output_cols if c in result_df.columns]
    result_df = result_df[final_cols]

    # Save output
    try:
        result_df.to_excel(output_file, index=False)
        print(f"Successfully saved {len(result_df)} records to {output_file}")
    except Exception as e:
        print(f"Error saving output file: {e}")

if __name__ == '__main__':
    main()
