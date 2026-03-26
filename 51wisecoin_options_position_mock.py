"""
期权模拟持仓生成器 by playbonze
功能：读取期货/期权行情生成 wisecoin-模拟持仓.xlsx
"""

import logging
import pandas as pd
import numpy as np
import os
import sys
import traceback
import re
from typing import Any

sys.path.append(os.path.join(os.path.dirname(__file__), "wisecoin-catboost"))
try:
    from pb_quant_seektop_common import UnifiedLogger
    logger = UnifiedLogger.setup_logger_auto(__file__)
except ImportError:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

TEMP_DIR = "wisecoin_options_client_live_temp"
TEMPLATE_FILE = "wisecoin-持仓.xlsx"
OUTPUT_EXCEL_FILE = "wisecoin-模拟持仓.xlsx"
STRATEGY_FILE = "wisecoin-期权策略.xlsx"
ARBITRAGE_FILE = "wisecoin-期权套利.xlsx"
EXCLUDED_ARBITRAGE_SHEETS = {"套利汇总", "策略指南", "时间价值低估", "转换逆转套利"}


def resolve_input_path(filename, prefer_temp=True):
    candidates = []
    if prefer_temp:
        candidates.append(os.path.join(TEMP_DIR, filename))
    candidates.append(filename)
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def load_template():
    template_path = resolve_input_path(TEMPLATE_FILE, prefer_temp=False)
    if not template_path:
        logger.error(f"模板文件不存在: {TEMPLATE_FILE}")
        return None, None, None
    try:
        template_df = pd.read_excel(template_path)
        if template_df.empty:
            logger.error(f"模板文件为空: {template_path}")
            return None, None, None
        template_cols = list(template_df.columns)
        first_row = template_df.iloc[0].to_dict()
        return template_df, template_cols, first_row
    except Exception as e:
        logger.error(f"读取模板文件失败: {template_path}，错误: {e}")
        logger.error(traceback.format_exc())
        return None, None, None


def sanitize_sheet_name(name):
    if name is None:
        return ""
    text = str(name)
    for ch in ['\\', '/', '*', '[', ']', ':', '?']:
        text = text.replace(ch, '_')
    return text[:31]


def is_index_underlying(underlying):
    if is_missing(underlying):
        return False
    text = str(underlying)
    return text.startswith('SSE.') or text.startswith('SZSE.') or text.startswith('CFFEX.')


def normalize_expiry(value):
    if is_missing(value):
        return None
    text = str(value).strip()
    if text.endswith('.0'):
        text = text[:-2]
    digits = re.findall(r'\d{4,6}', text)
    if not digits:
        return None
    return digits[0]


def extract_expiry_from_symbol(symbol):
    if is_missing(symbol):
        return None
    text = str(symbol)
    match = re.search(r'\.(?:[A-Za-z]+)?(\d{4})', text)
    if match:
        return match.group(1)
    match = re.search(r'(\d{4})', text)
    if match:
        return match.group(1)
    return None


def extract_expiry_from_legs(legs):
    for leg in legs:
        expiry = extract_expiry_from_symbol(leg.get('symbol'))
        if expiry:
            return expiry
    return None


def pick_value(row, candidates):
    for cand in candidates:
        if cand in row and not pd.isna(row[cand]):
            return row[cand]
    return np.nan


def to_float(value):
    return pd.to_numeric(value, errors='coerce')


def is_missing(value):
    try:
        return bool(pd.isna(value))
    except Exception:
        return value is None


def to_number(value, default=np.nan):
    try:
        value = float(value)
        if np.isnan(value):
            return default
        return value
    except Exception:
        return default


def parse_legs_from_text(text):
    if text is None or (isinstance(text, float) and np.isnan(text)):
        return []
    raw = str(text)
    if '｜' in raw:
        raw = raw.split('｜')[0]
    parts = [p.strip() for p in raw.replace('；', ';').split(';') if p.strip()]
    legs = []
    for part in parts:
        action = None
        if part.startswith('买入'):
            action = 'buy'
            part = part.replace('买入', '', 1)
        elif part.startswith('卖出'):
            action = 'sell'
            part = part.replace('卖出', '', 1)
        if not action:
            continue
        symbol = None
        qty = None
        price = None
        if '*' in part:
            sym_part, rest = part.split('*', 1)
            symbol = sym_part.strip()
            if '@' in rest:
                qty_part, price_part = rest.split('@', 1)
                qty = to_number(qty_part.strip())
                price = to_number(price_part.strip())
            else:
                qty = to_number(rest.strip())
        else:
            if '@' in part:
                sym_part, price_part = part.split('@', 1)
                symbol = sym_part.strip()
                price = to_number(price_part.strip())
        if symbol and qty:
            legs.append({'action': action, 'symbol': symbol, 'qty': int(qty), 'price': price})
    return legs


def build_position_row_from_leg(leg, template_cols, defaults):
    record: dict[str, Any] = {col: np.nan for col in template_cols}
    symbol = leg.get('symbol')
    if is_missing(symbol):
        return None
    if '.' in str(symbol):
        exchange_id, instrument_id = str(symbol).split('.', 1)
    else:
        exchange_id = np.nan
        instrument_id = str(symbol)
    qty = int(leg.get('qty', 0))
    if qty == 0:
        return None
    last_price = to_number(leg.get('price'))
    if 'exchange_id' in record:
        record['exchange_id'] = str(exchange_id) if not is_missing(exchange_id) else np.nan
    if 'instrument_id' in record:
        record['instrument_id'] = str(instrument_id)
    if 'symbol' in record:
        record['symbol'] = str(symbol)
    if 'last_price' in record:
        record['last_price'] = last_price
    if 'user_id' in record and defaults is not None and 'user_id' in defaults:
        record['user_id'] = defaults.get('user_id', np.nan)
    action = leg.get('action')
    pos_long = qty if action == 'buy' else 0
    pos_short = qty if action == 'sell' else 0
    if 'pos_long' in record:
        record['pos_long'] = pos_long
    if 'pos_short' in record:
        record['pos_short'] = pos_short
    if 'pos' in record:
        record['pos'] = pos_long - pos_short
    if 'volume_long' in record:
        record['volume_long'] = pos_long
    if 'volume_long_today' in record:
        record['volume_long_today'] = pos_long
    if 'volume_short' in record:
        record['volume_short'] = pos_short
    if 'volume_short_today' in record:
        record['volume_short_today'] = pos_short
    for col in ['pos_long_his', 'pos_long_today', 'pos_short_his', 'pos_short_today',
                'volume_long_his', 'volume_long_frozen_today', 'volume_long_frozen_his',
                'volume_long_frozen', 'volume_short_today', 'volume_short_his', 'volume_short',
                'volume_short_frozen_today', 'volume_short_frozen_his', 'volume_short_frozen',
                'volume_short_yd', 'volume_long_yd']:
        if col in record and is_missing(record[col]):
            record[col] = 0
    for col in ['open_price_long', 'position_price_long']:
        if col in record and pos_long:
            record[col] = last_price
    for col in ['open_price_short', 'position_price_short']:
        if col in record and pos_short:
            record[col] = last_price
    for col in ['open_cost_long', 'position_cost_long']:
        if col in record and pos_long:
            record[col] = last_price * pos_long if not is_missing(last_price) else np.nan
    for col in ['open_cost_short', 'position_cost_short']:
        if col in record and pos_short:
            record[col] = last_price * pos_short if not is_missing(last_price) else np.nan
    for col in ['float_profit_long', 'position_profit_long', 'float_profit', 'position_profit',
                'margin_long', 'margin', 'market_value_long', 'market_value',
                'float_profit_short', 'position_profit_short', 'margin_short', 'market_value_short']:
        if col in record and is_missing(record[col]):
            record[col] = 0
    return record


def load_strategy_positions(template_cols, defaults):
    path = resolve_input_path(STRATEGY_FILE)
    if not path:
        logger.error(f"策略文件不存在: {STRATEGY_FILE}")
        return {}
    try:
        df = pd.read_excel(path, sheet_name='策略明细')
    except Exception as e:
        logger.error(f"读取策略明细失败: {path}，错误: {e}")
        logger.error(traceback.format_exc())
        return {}
    buckets: dict[str, list[dict[str, Any]]] = {}
    for _, row in df.iterrows():
        underlying = row.get('标的合约', '')
        strategy = row.get('策略类型', '')
        expiry = normalize_expiry(row.get('到期月份', ''))
        if is_index_underlying(underlying) and expiry:
            sheet_name = sanitize_sheet_name(f"{underlying}_{expiry}_{strategy}")
        else:
            sheet_name = sanitize_sheet_name(f"{underlying}_{strategy}")
        legs = parse_legs_from_text(row.get('操作要点', ''))
        for leg in legs:
            record = build_position_row_from_leg(leg, template_cols, defaults)
            if record is None:
                continue
            buckets.setdefault(sheet_name, []).append(record)
    return buckets


def load_arbitrage_positions(template_cols, defaults):
    path = resolve_input_path(ARBITRAGE_FILE)
    if not path:
        logger.error(f"套利文件不存在: {ARBITRAGE_FILE}")
        return {}
    buckets: dict[str, list[dict[str, Any]]] = {}
    try:
        xls = pd.ExcelFile(path)
        for sheet_name in xls.sheet_names:
            if sheet_name in EXCLUDED_ARBITRAGE_SHEETS:
                continue
            df = pd.read_excel(xls, sheet_name=sheet_name)
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                underlying = row.get('标的合约', '')
                strategy = row.get('套利类型', sheet_name)
                text = row.get('交易指令', '') or row.get('操作建议', '')
                legs = parse_legs_from_text(text)
                expiry = extract_expiry_from_legs(legs)
                if is_index_underlying(underlying) and expiry:
                    out_sheet = sanitize_sheet_name(f"{underlying}_{expiry}_{strategy}")
                else:
                    out_sheet = sanitize_sheet_name(f"{underlying}_{strategy}")
                for leg in legs:
                    record = build_position_row_from_leg(leg, template_cols, defaults)
                    if record is None:
                        continue
                    buckets.setdefault(out_sheet, []).append(record)
        return buckets
    except Exception as e:
        logger.error(f"读取套利文件失败: {path}，错误: {e}")
        logger.error(traceback.format_exc())
        return {}


def merge_records(records):
    merged: dict[str, dict[str, Any]] = {}
    for record in records:
        symbol = record.get('symbol')
        if is_missing(symbol):
            continue
        key = str(symbol)
        if key not in merged:
            merged[key] = record
            continue
        target = merged[key]
        for col in ['pos_long', 'pos_short', 'pos', 'volume_long', 'volume_long_today',
                    'volume_short', 'volume_short_today']:
            if col in target and col in record:
                target[col] = int(to_number(target.get(col), 0) + to_number(record.get(col), 0))
        if 'last_price' in target and is_missing(target.get('last_price')):
            target['last_price'] = record.get('last_price')
    return list(merged.values())


def build_mock_positions():
    template_df, template_cols, defaults = load_template()
    if template_cols is None or template_df is None:
        return False
    buckets = {}
    for name, bucket in load_strategy_positions(template_cols, defaults).items():
        buckets.setdefault(name, []).extend(bucket)
    for name, bucket in load_arbitrage_positions(template_cols, defaults).items():
        buckets.setdefault(name, []).extend(bucket)
    if not buckets:
        logger.error("未生成任何有效持仓记录。")
        return False
    try:
        with pd.ExcelWriter(OUTPUT_EXCEL_FILE, engine='openpyxl') as writer:
            total_rows = 0
            for sheet_name, records in buckets.items():
                merged_records = merge_records(records)
                if not merged_records:
                    continue
                result_df = pd.DataFrame(merged_records)
                result_df = result_df.reindex(columns=[str(c) for c in template_cols])
                for col in template_cols:
                    if col in template_df.columns:
                        dtype = template_df[col].dtype
                        try:
                            if dtype.kind in ['i', 'u']:
                                result_df[col] = pd.to_numeric(result_df[col], errors='coerce')
                                result_df[col] = result_df[col].fillna(0).astype('int64')
                            elif dtype.kind == 'f':
                                result_df[col] = pd.to_numeric(result_df[col], errors='coerce')
                        except Exception:
                            continue
                result_df.to_excel(writer, sheet_name=sheet_name, index=False)
                total_rows += len(result_df)
        logger.info(f"✅ 模拟持仓导出完成: {OUTPUT_EXCEL_FILE}，分页数 {len(buckets)}，记录数 {total_rows}")
        return True
    except Exception as e:
        logger.error(f"写入模拟持仓文件失败: {e}")
        logger.error(traceback.format_exc())
        return False


def main():
    try:
        build_mock_positions()
    except Exception as e:
        logger.error(f"运行异常: {e}")
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    main()
