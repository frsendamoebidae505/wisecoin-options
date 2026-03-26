"""
SeekTop 预测模型公共功能模块 v2.1 (统一日志版)
提供数据处理、评估指标计算、可视化等通用功能
使用统一的日志系统，保持数据原汁原味
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import mean_absolute_error, mean_squared_error
from typing import Dict, List, Tuple, Optional, Any
from numpy.typing import NDArray
import warnings
import logging
from datetime import datetime
from pathlib import Path
import os
import sys
import logging
import torch

warnings.filterwarnings('ignore')

class UnifiedLogger:
    """统一日志管理器 - 确保所有脚本日志格式一致"""
    
    @staticmethod
    def setup_logger(script_name: str, log_dir: Path = Path("logs")) -> logging.Logger:
        """设置统一的日志记录器"""
        try:
            # 尝试创建日志目录，如果失败则忽略（日志记录不了也就算了）
            if not log_dir.exists():
                log_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        
        logger = logging.getLogger(script_name)
        logger.setLevel(logging.INFO)
        
        # 避免重复添加处理器
        if logger.handlers:
            return logger
            
        # 1. 控制台处理器 - 简洁格式，便于阅读 (无论如何都要保留)
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # 2. 文件处理器 - 尝试设置，不带锁（延迟创建），如果权限报错则跳过
        log_file = log_dir / f"{script_name}.log"
        try:
            # 使用 delay=True 延迟到第一次写入时才打开文件，减少启动时的锁竞争和权限检查
            file_handler = logging.FileHandler(log_file, encoding='utf-8', delay=True)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # 【优化】日志记录不了也就算了，用户明确表示可以不记文件日志
            print(f"⚠️  警告: 无法初始化文件日志 ({log_file}): {e}")
            print("💡 程序将仅使用控制台输出运行。")
        
        return logger

    @staticmethod
    def setup_logger_auto(caller_file: str, log_dir: Path = Path("logs")) -> logging.Logger:
        """自动从调用者文件名获取脚本名称的日志记录器 - 无需硬编码脚本名"""
        script_name = Path(caller_file).stem
        return UnifiedLogger.setup_logger(script_name, log_dir)

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class PredictionCommon:
    """预测模型公共功能类"""
    
    # 评估指标常量
    DEFAULT_EPS = 1e-8
    SHORT_SEQUENCE_THRESHOLD = 3
    TREND_OVERALL_WEIGHT = 0.6
    TREND_WINDOW_WEIGHT = 0.4
    WINDOW_SIZE_RATIO = 0.25  # 1/4
    VOLATILITY_GOOD_RANGE = (0.8, 1.2)
    SMAPE_HIGH_THRESHOLD = 20.0
    TREND_ACC_LOW_THRESHOLD = 0.5
    VOLATILITY_DEVIATION_THRESHOLD = 0.3
    RMSE_HIGH_THRESHOLD = 50.0
    
    # 标准指标名称映射
    METRIC_ALIASES = {
        'sMAPE': ['SMAPE', 'smape'],
        'Theils_U': ['Theil_U', 'theils_u', 'theil_u'],
        'RMSE': ['rmse'],
        'Trend_Acc': ['trend_acc', 'TrendAcc'],
        'Volatility_Ratio': ['volatility_ratio', 'VolatilityRatio']
    }

    def __init__(self):
        self.results = {}
        self.logger = UnifiedLogger.setup_logger_auto(__file__)

    @staticmethod
    def load_and_prepare_data(file_path: str,
                              date_column: str = 'date',
                              target_column: str = 'close',
                              sort_by_date: bool = True) -> pd.DataFrame:
        """
        加载和预处理数据 (保持原始数据不变)
        """
        logger = UnifiedLogger.setup_logger_auto(__file__)
        
        try:
            df = pd.read_csv(file_path)

            # 兼容datetime/timestamps
            if 'datetime' in df.columns and date_column == 'date':
                date_column = 'datetime'
            if 'timestamps' in df.columns and date_column == 'date':
                date_column = 'timestamps'

            df[date_column] = pd.to_datetime(df[date_column])
            if sort_by_date:
                df = df.sort_values(date_column).reset_index(drop=True)

            # 统一日期列名为 'datetime' 以便后续使用
            if date_column != 'datetime':
                df['datetime'] = df[date_column]

            # 严格的chengjiao到amount字段映射 - 不允许fallback处理
            if 'chengjiao' in df.columns:
                # 直接使用chengjiao数据作为amount，保持数据原模原样
                df['amount'] = df['chengjiao']
            elif 'amount' not in df.columns:
                raise ValueError("Required column 'chengjiao' or 'amount' missing from data.")

            # 严格的数据类型检查 - 不允许fallback处理
            numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount']
            for col in numeric_columns:
                if col in df.columns:
                    # 严格检查数据类型，不允许强制转换
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    # 检查是否有NaN值，如有则报告但不处理
                    nan_count = df[col].isna().sum()
                    if nan_count > 0:
                        logger.warning(f"Column '{col}' has {nan_count} NaN values. Data preserved as-is.")
                        # 不进行任何填充，保持数据原模原样

            logger.info(f"数据加载成功: {len(df)} 行 {len(df.columns)} 列")
            logger.info(f"日期范围: {df[date_column].min()} 到 {df[date_column].max()}")

            if target_column not in df.columns:
                raise ValueError(f"目标列 '{target_column}' 不存在于数据中，可用列: {list(df.columns)}")

            # 严格检查目标列数据类型
            df[target_column] = pd.to_numeric(df[target_column], errors='coerce')
            nan_count = df[target_column].isna().sum()
            if nan_count > 0:
                logger.warning(f"目标列 '{target_column}' 包含 {nan_count} 个非数值数据，已转换为NaN但保持原样")
                # 不进行填充，保持数据完整性

            return df

        except Exception as e:
            logger.error(f"数据加载失败: {e}")
            raise

    @staticmethod
    def split_data(df: pd.DataFrame,
                   train_ratio: float = 0.8,
                   target_column: str = 'close') -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        分割训练和测试数据
        """
        logger = UnifiedLogger.setup_logger_auto(__file__)
        
        split_idx = int(len(df) * train_ratio)
        train_data = df[:split_idx].copy()
        test_data = df[split_idx:].copy()

        logger.info(f"训练集大小: {len(train_data)}")
        logger.info(f"测试集大小: {len(test_data)}")

        return train_data, test_data

    @staticmethod
    def calculate_metrics(y_true, y_pred, last_historical_value: float) -> Dict[str, float]:
        """
        计算优化后的专业预测评估指标集：RMSE, sMAPE, Trend_Acc, Volatility_Ratio, Theils_U
        基于金融时间序列预测最佳实践，选择最具代表性和特异性的5个指标
        
        参数:
        - y_true: 预测期间的真实值
        - y_pred: 模型的预测值
        - last_historical_value: 预测前的最后一个历史值（用于Theil's U计算）
        """
        # 辅助函数
        def _create_nan_metrics():
            return {
                'RMSE': np.nan, 'sMAPE': np.nan, 'Trend_Acc': np.nan, 
                'Volatility_Ratio': np.nan, 'Theils_U': np.nan
            }

        def _calculate_trend_accuracy(y_true, y_pred):
            """计算趋势准确率：预测趋势方向的准确性（简化版）"""
            if len(y_true) <= 1:
                return np.nan
            
            # 只关注整体趋势：从第一个点到最后一个点的方向
            true_overall_trend = y_true[-1] - y_true[0]
            pred_overall_trend = y_pred[-1] - y_pred[0]
            overall_match = float(np.sign(true_overall_trend) == np.sign(pred_overall_trend))
            
            return overall_match

        def _calculate_volatility_ratio(y_true, y_pred):
            """计算波动性比率：预测波动性与实际波动性的匹配程度"""
            if len(y_true) <= 1:
                return np.nan
            # 计算实际和预测的波动性（标准差）
            true_vol = np.std(y_true)
            pred_vol = np.std(y_pred)
            # 避免除零
            if true_vol == 0:
                return np.nan
            vol_ratio = pred_vol / true_vol
            return vol_ratio

        def _calculate_theils_u(y_true, y_pred, last_historical_value, eps):
            """计算Theil's U：与朴素预测的比较
            
            朴素预测策略：使用预测前的最后一个历史值作为所有预测时间点的预测值
            参数:
            - y_true: 预测期间的真实值
            - y_pred: 模型的预测值  
            - last_historical_value: 预测前的最后一个历史值
            - eps: 避免除零的小值
            """
            if len(y_true) <= 1:
                return np.nan
            
            # 确保预测序列和真实序列长度一致
            if len(y_pred) != len(y_true):
                min_len = min(len(y_pred), len(y_true))
                y_pred = y_pred[:min_len]
                y_true = y_true[:min_len]
                
            # 朴素预测：使用预测前的最后一个历史值作为所有预测时间点的预测值
            naive_pred = np.full(len(y_true), last_historical_value)
            naive_error = np.sqrt(np.mean((naive_pred - y_true) ** 2))
            
            # 预测误差：使用完整序列进行比较
            pred_error = np.sqrt(np.mean((y_pred - y_true) ** 2))
            
            # 避免除零
            if naive_error == 0 or naive_error < eps:
                return np.nan
                
            theils_u = pred_error / naive_error
            return theils_u

        # 保持原始数据，不做任何过滤清洗，同时检查NaN
        y_true = np.asarray(y_true, dtype=float)
        y_pred = np.asarray(y_pred, dtype=float)
        
        # 一次性检查NaN值，避免重复扫描
        has_nan_true = np.any(np.isnan(y_true))
        has_nan_pred = np.any(np.isnan(y_pred))
        
        if has_nan_true or has_nan_pred:
    
            return _create_nan_metrics()
        eps = PredictionCommon.DEFAULT_EPS

        # 计算5个核心指标
        rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
        # sMAPE计算：只在分母为0时添加eps
        denominator = np.abs(y_true) + np.abs(y_pred)
        denominator = np.where(denominator == 0, eps, denominator)
        smape = float(np.mean(2.0 * np.abs(y_pred - y_true) / denominator) * 100)
        trend_acc = _calculate_trend_accuracy(y_true, y_pred)
        vol_ratio = _calculate_volatility_ratio(y_true, y_pred)
        
        # Theil's U需要历史数据的最后一个值
        theils_u = _calculate_theils_u(y_true, y_pred, last_historical_value, eps)

        return {
            'RMSE': float(rmse),           # 绝对误差指标
            'sMAPE': float(smape),         # 相对误差指标  
            'Trend_Acc': float(trend_acc), # 趋势预测准确性
            'Volatility_Ratio': float(vol_ratio), # 波动性匹配度
            'Theils_U': float(theils_u)    # 基准比较指标
        }
    
    @staticmethod
    def normalize_metric_names(metrics_dict: Dict) -> Dict[str, float]:
        """
        标准化指标名称，将各种变体统一为标准名称
        """
        normalized = {}
        
        # 标准名称到别名的反向映射
        name_to_standard = {}
        for standard, aliases in PredictionCommon.METRIC_ALIASES.items():
            name_to_standard[standard] = standard
            for alias in aliases:
                name_to_standard[alias] = standard
        
        for key, value in metrics_dict.items():
            standard_name = name_to_standard.get(key, key)
            normalized[standard_name] = value
            
        return normalized

    @staticmethod
    def print_metrics(metrics: Dict[str, float], model_name: str = "模型"):
        """
        打印评估指标 (使用统一日志)
        """
        logger = UnifiedLogger.setup_logger_auto(__file__)
        
        logger.info(f"{model_name} 评估结果（优化后的指标集）:")
        logger.info("-" * 50)
        logger.info(f"RMSE (均方根误差): {metrics.get('RMSE', np.nan):.4f}")
        logger.info(f"sMAPE (对称平均绝对百分比误差): {metrics.get('sMAPE', np.nan):.2f}%")
        logger.info(f"Trend Accuracy (趋势准确率): {metrics.get('Trend_Acc', np.nan):.2%}")
        logger.info(f"Volatility Ratio (波动性比率): {metrics.get('Volatility_Ratio', np.nan):.4f}")
        logger.info(f"Theil's U (泰尔不等系数): {metrics.get('Theils_U', np.nan):.4f}")
        logger.info("-" * 50)
        
        # 全面的指标解释
        logger.info("📊 指标解释:")
        
        # RMSE解释
        rmse_value = metrics.get('RMSE', np.nan)
        if not np.isnan(rmse_value):
            if rmse_value <= PredictionCommon.RMSE_HIGH_THRESHOLD:
                logger.info(f"✅ RMSE {rmse_value:.4f}: 绝对误差在可接受范围内")
            else:
                logger.info(f"⚠️  RMSE {rmse_value:.4f}: 绝对误差较高，建议优化模型")
        
        # sMAPE解释  
        smape_value = metrics.get('sMAPE', np.nan)
        if not np.isnan(smape_value):
            if smape_value <= 10:
                logger.info(f"✅ sMAPE {smape_value:.2f}%: 相对误差很低，预测精度优秀")
            elif smape_value <= PredictionCommon.SMAPE_HIGH_THRESHOLD:
                logger.info(f"✅ sMAPE {smape_value:.2f}%: 相对误差在合理范围内")
            else:
                logger.info(f"⚠️  sMAPE {smape_value:.2f}%: 相对误差较高，需要改进")
        
        # Trend_Acc解释
        trend_acc_value = metrics.get('Trend_Acc', np.nan)
        if not np.isnan(trend_acc_value):
            if trend_acc_value >= 0.7:
                logger.info(f"✅ Trend_Acc {trend_acc_value:.2%}: 趋势预测能力优秀")
            elif trend_acc_value >= PredictionCommon.TREND_ACC_LOW_THRESHOLD:
                logger.info(f"✅ Trend_Acc {trend_acc_value:.2%}: 趋势预测能力良好")
            else:
                logger.info(f"❌ Trend_Acc {trend_acc_value:.2%}: 趋势预测能力需要提升")
        
        # Volatility_Ratio解释
        vol_ratio_value = metrics.get('Volatility_Ratio', np.nan)
        if not np.isnan(vol_ratio_value):
            min_range, max_range = PredictionCommon.VOLATILITY_GOOD_RANGE
            if min_range <= vol_ratio_value <= max_range:
                logger.info(f"✅ Volatility_Ratio {vol_ratio_value:.4f}: 波动性预测匹配良好")
            elif vol_ratio_value < min_range:
                logger.info(f"⚠️  Volatility_Ratio {vol_ratio_value:.4f}: 预测波动性偏低")
            else:
                logger.info(f"⚠️  Volatility_Ratio {vol_ratio_value:.4f}: 预测波动性偏高")
        
        # Theil's U解释
        theils_u_value = metrics.get('Theils_U', np.nan)
        if not np.isnan(theils_u_value):
            if theils_u_value < 0.8:
                logger.info(f"✅ Theil's U {theils_u_value:.4f}: 明显优于朴素预测")
            elif theils_u_value < 1:
                logger.info(f"✅ Theil's U {theils_u_value:.4f}: 优于朴素预测")
            elif theils_u_value < 1.2:
                logger.info(f"⚠️  Theil's U {theils_u_value:.4f}: 略优于朴素预测")
            else:
                logger.info(f"❌ Theil's U {theils_u_value:.4f}: 不如朴素预测，需要改进")

    @staticmethod
    def plot_detailed_prediction(symbol: str, train_df: pd.DataFrame, result: Dict, out_dir: 'Path', prediction_id: int, model_suffix: str = 'timesfm', time_str: str = None):
        """
        为单次预测生成详细图片并直接保存（支持优化后的指标集）
        显示历史数据、预测值和实际值的对比，包含主图和放大图。
        """
        # --- 嵌套辅助函数以保持命名空间清洁 ---\
        def _prepare_plot_data(train_df, hist_len):
            if len(train_df) > hist_len:
                return train_df.tail(hist_len).reset_index(drop=True)
            return train_df

        def _extract_prediction_data(result):
            # 支持不同的预测数据格式
            pred_data = {}

            # 优先使用median（Chronos-Bolt）
            if 'y_pred_median' in result:
                pred_data['mean'] = result['y_pred_median']  # 使用median作为主预测线
            elif 'y_pred_mean' in result:
                pred_data['mean'] = result['y_pred_mean']
            else:
                # 如果没有找到预测数据，返回空字典
                return {}
            
            # 确保预测数据不为空
            if 'mean' not in pred_data or pred_data['mean'] is None:
                return {}
            
            # 转换为numpy数组确保数据格式正确
            try:
                pred_data['mean'] = np.array(pred_data['mean'], dtype=np.float64)
                if len(pred_data['mean']) == 0:
                    return {}
            except (ValueError, TypeError):
                return {}

            # 可选的区间预测 - 确保数据类型为numpy数组且包含数值类型
            if 'y_pred_min' in result:
                min_data = result['y_pred_min']
                # 转换为numpy数组并确保是数值类型
                if hasattr(min_data, '__iter__') and not isinstance(min_data, (str, bytes)):
                    try:
                        min_array = np.array(min_data, dtype=np.float64)
                        # 检查是否有无效值并替换为NaN
                        min_array = np.where(np.isfinite(min_array), min_array, np.nan)
                        if len(min_array) == len(pred_data['mean']):
                            pred_data['min'] = min_array
                    except (ValueError, TypeError):
                        pass

            if 'y_pred_max' in result:
                max_data = result['y_pred_max']
                # 转换为numpy数组并确保是数值类型
                if hasattr(max_data, '__iter__') and not isinstance(max_data, (str, bytes)):
                    try:
                        max_array = np.array(max_data, dtype=np.float64)
                        # 检查是否有无效值并替换为NaN
                        max_array = np.where(np.isfinite(max_array), max_array, np.nan)
                        if len(max_array) == len(pred_data['mean']):
                            pred_data['max'] = max_array
                    except (ValueError, TypeError):
                        pass

            return pred_data

        def _extract_valid_actuals(actual_values, hist_len):
            valid_indices, valid_values = [], []
            for i, val in enumerate(actual_values):
                if not np.isnan(val):
                    valid_indices.append(hist_len + i)
                    valid_values.append(val)
            return valid_indices, valid_values

        def _draw_connection_lines_index(ax, last_hist_idx, last_hist_price, pred_indices, pred_values, actual_indices, actual_values):
            if len(pred_values) > 0:
                first_pred_idx = list(pred_indices)[0]
                ax.plot([last_hist_idx, first_pred_idx], [last_hist_price, pred_values[0]], color='darkorange', linewidth=2.0, linestyle='-')
            if actual_indices and len(actual_values) > 0:
                first_actual_idx = actual_indices[0]
                ax.plot([last_hist_idx, first_actual_idx], [last_hist_price, actual_values[0]], color='red', linewidth=2.0, linestyle='-')

        def _setup_time_axis(ax, train_df, result, hist_len, pred_len):
            time_col = 'datetime' if 'datetime' in train_df.columns else 'timestamps'
            index_positions = [0, hist_len // 4, hist_len // 2, hist_len * 3 // 4, hist_len - 1]
            if pred_len > 0:
                index_positions.append(hist_len + pred_len - 1)
            
            time_labels = []
            for idx in index_positions:
                if idx < hist_len:
                    dt = train_df[time_col].iloc[idx]
                else:
                    pred_idx = idx - hist_len
                    # 支持不同的预测数据格式
                    if 'y_pred_median' in result:
                        pred_len = len(result['y_pred_median'])
                    elif 'y_pred_mean' in result:
                        pred_len = len(result['y_pred_mean'])
                    else:
                        pred_len = len(result['y_true'])  # 备选方案
                    pred_times = pd.date_range(start=result['train_end_time'] + pd.Timedelta(minutes=1), periods=pred_len, freq='T')
                    dt = pred_times[pred_idx] if pred_idx < len(pred_times) else pred_times[-1]
                time_labels.append(dt.strftime('%m-%d %H:%M'))
            
            ax.set_xticks(index_positions)
            ax.set_xticklabels(time_labels, fontsize=11, rotation=20)

        def _draw_main_plot(ax_main, train_df, pred_data, result, symbol, hist_len):
            hist_indices = range(hist_len)
            pred_indices = range(hist_len, hist_len + len(pred_data['mean']))
            ax_main.plot(hist_indices, train_df['close'].values, color='steelblue', label='Historical Price', linewidth=1.5, alpha=0.8)
            ax_main.plot(pred_indices, pred_data['mean'], color='darkorange', label='Predicted Price', linewidth=2.0)
            
            # 只有在有有效的区间数据时才绘制预测范围
            if ('min' in pred_data and 'max' in pred_data and
                hasattr(pred_data['min'], '__len__') and hasattr(pred_data['max'], '__len__') and
                len(pred_data['min']) > 0 and len(pred_data['max']) > 0 and
                len(pred_data['min']) == len(pred_indices)):
                try:
                    # 确保数据是数值类型且有限
                    min_values = np.asarray(pred_data['min'], dtype=np.float64)
                    max_values = np.asarray(pred_data['max'], dtype=np.float64)

                    # 检查是否有有效的数值数据
                    if np.any(np.isfinite(min_values)) and np.any(np.isfinite(max_values)):
                        ax_main.fill_between(pred_indices, min_values, max_values, color='orange', alpha=0.3, label='Prediction Range')
                except (ValueError, TypeError, RuntimeError):
                    # 如果数据处理失败，跳过绘制区间
                    pass
            valid_actual_indices, valid_actual_values = _extract_valid_actuals(result['y_true'], hist_len)
            if valid_actual_indices:
                ax_main.plot(valid_actual_indices, valid_actual_values, color='red', label='Actual Price', linewidth=2.0)
            ax_main.axvline(x=hist_len - 1, color='gray', linestyle='--', linewidth=2, alpha=0.8, label='Prediction Start')
            _draw_connection_lines_index(ax_main, hist_len - 1, train_df['close'].iloc[-1], pred_indices, pred_data['mean'], valid_actual_indices, valid_actual_values)
            
            split_time = result['train_end_time']
            pred_len = len(pred_data['mean'])
            ax_main.set_title(f'{symbol} - Prediction at {split_time.strftime("%Y-%m-%d %H:%M")}\nUsing {hist_len} historical points to predict next {pred_len} points', fontsize=16, weight='bold')
            ax_main.set_ylabel('Close Price', fontsize=14)
            ax_main.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)
            ax_main.legend(fontsize=12, loc='upper left')
            _setup_time_axis(ax_main, train_df, result, hist_len, pred_len)

        def _draw_zoom_plot(ax_zoom, train_df, pred_data, result, hist_len):
            zoom_hist_len = 100
            zoom_pred_len = len(pred_data['mean'])  # 使用实际预测长度（64个点）
            zoom_start = max(0, hist_len - zoom_hist_len)
            zoom_end = hist_len + zoom_pred_len
            
            zoom_hist_indices = range(zoom_start, hist_len)
            zoom_pred_indices = range(hist_len, zoom_end)
            
            zoom_hist_values = train_df['close'].values[-(hist_len - zoom_start):]
            ax_zoom.plot(zoom_hist_indices, zoom_hist_values, color='steelblue', label='Historical Price', linewidth=2.0)
            
            zoom_pred_values = pred_data['mean'][:zoom_pred_len]
            ax_zoom.plot(zoom_pred_indices, zoom_pred_values, color='darkorange', label='Predicted Price', linewidth=2.0)
            
            # 只有在有区间数据时才绘制预测范围
            if 'min' in pred_data and 'max' in pred_data:
                zoom_pred_min = pred_data['min'][:zoom_pred_len]
                zoom_pred_max = pred_data['max'][:zoom_pred_len]
                ax_zoom.fill_between(zoom_pred_indices, zoom_pred_min, zoom_pred_max, color='orange', alpha=0.3)
            
            valid_actual_indices, valid_actual_values = _extract_valid_actuals(result['y_true'], hist_len)
            zoom_actual_indices = [i for i in valid_actual_indices if zoom_start <= i < zoom_end]
            zoom_actual_values = [result['y_true'][i - hist_len] for i in zoom_actual_indices]
            if zoom_actual_indices:
                ax_zoom.plot(zoom_actual_indices, zoom_actual_values, color='red', label='Actual Price', linewidth=2.0)
            
            ax_zoom.axvline(x=hist_len - 1, color='gray', linestyle='--', linewidth=2, alpha=0.8)
            _draw_connection_lines_index(ax_zoom, hist_len - 1, train_df['close'].iloc[-1], zoom_pred_indices, zoom_pred_values, zoom_actual_indices, zoom_actual_values)

            ax_zoom.set_title(f'Zoomed Prediction Area (Last {zoom_hist_len} Historical + {zoom_pred_len} Prediction Points)', fontsize=14)
            ax_zoom.set_ylabel('Close Price', fontsize=12)
            ax_zoom.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)
            
            time_col = 'datetime' if 'datetime' in train_df.columns else 'timestamps'
            ticks = [zoom_start, hist_len -1, zoom_end -1]
            labels = []
            labels.append(train_df[time_col].iloc[-(hist_len-zoom_start)].strftime('%m-%d %H:%M'))
            labels.append(train_df[time_col].iloc[-1].strftime('%m-%d %H:%M'))
            # 支持不同的预测数据格式
            if 'y_pred_median' in result:
                pred_len = len(result['y_pred_median'])
            elif 'y_pred_mean' in result:
                pred_len = len(result['y_pred_mean'])
            else:
                pred_len = len(result['y_true'])  # 备选方案
            pred_times = pd.date_range(start=result['train_end_time'] + pd.Timedelta(minutes=1), periods=pred_len, freq='T')
            labels.append(pred_times[zoom_pred_len-1].strftime('%m-%d %H:%M'))
            ax_zoom.set_xticks(ticks)
            ax_zoom.set_xticklabels(labels, fontsize=11, rotation=20)

        # --- `plot_detailed_prediction` 主体 ---
        fig = plt.figure(figsize=(16, 10))
        ax_main = plt.subplot2grid((3, 3), (0, 0), colspan=3, rowspan=2)
        ax_zoom = plt.subplot2grid((3, 3), (2, 0), colspan=3, rowspan=1)

        hist_len = len(train_df)
        plot_train_df = _prepare_plot_data(train_df, hist_len)
        pred_data = _extract_prediction_data(result)

        _draw_main_plot(ax_main, plot_train_df, pred_data, result, symbol, hist_len)
        _draw_zoom_plot(ax_zoom, plot_train_df, pred_data, result, hist_len)

        fig.tight_layout()
        
        # --- 文件保存逻辑 ---
        # 使用传入的time_str参数，如果没有则使用train_end_time
        if time_str is not None:
            chart_filename = f'{symbol.replace(".", "_")}_{time_str}_{model_suffix}.png'
        else:
            chart_filename = f'{symbol.replace(".", "_")}_{result["train_end_time"].strftime("%Y%m%d_%H%M")}_{model_suffix}.png'
        chart_path = out_dir / chart_filename
        fig.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close(fig)

    @staticmethod
    def plot_combined_predictions(symbol: str, train_df: pd.DataFrame, 
                                 kronos_result: Dict, chronos_result: Dict, timesfm_result: Dict,
                                 out_dir: 'Path', time_str: str, show_actual: bool = False):
        """
        生成集合3个模型预测值的综合图片（只显示预测线，不显示预测区域）
        """
        # 设置图片大小和布局
        fig = plt.figure(figsize=(16, 10))
        ax_main = plt.subplot2grid((3, 3), (0, 0), colspan=3, rowspan=2)
        ax_zoom = plt.subplot2grid((3, 3), (2, 0), colspan=3, rowspan=1)
        
        hist_len = len(train_df)
        hist_indices = range(hist_len)
        
        # 绘制历史数据
        ax_main.plot(hist_indices, train_df['close'].values, 
                    color='steelblue', label='Historical Price', linewidth=1.5, alpha=0.8)
        
        # 提取各模型预测数据并绘制预测线
        # 使用浅色系：橙色(Kronos)、蓝色(Chronos)、绿色(TimesFM)
        models_data = [
            (kronos_result, 'Kronos', '#FFA07A', 'y_pred_mean'),  # 浅橙色
            (chronos_result, 'Chronos', '#87CEEB', 'y_pred_median'),  # 天蓝色  
            (timesfm_result, 'TimesFM', '#90EE90', 'y_pred_mean')  # 浅绿色
        ]
        
        pred_len = 64  # 固定64个预测点
        pred_indices = range(hist_len, hist_len + pred_len)
        
        for result, model_name, color, pred_key in models_data:
            if result and pred_key in result:
                pred_values = result[pred_key][:pred_len]  # 只取前64个点
                # 验证pred_values不为空且有有效数据
                if len(pred_values) > 0 and not np.all(np.isnan(pred_values)):
                    ax_main.plot(pred_indices, pred_values, 
                               color=color, label=f'{model_name} Prediction', linewidth=2.0)
                    
                    # 绘制连接线
                    ax_main.plot([hist_len - 1, hist_len], 
                               [train_df['close'].iloc[-1], pred_values[0]], 
                               color=color, linewidth=2.0, linestyle='-')
        
        # 绘制分割线
        ax_main.axvline(x=hist_len - 1, color='gray', linestyle='--', 
                       linewidth=2, alpha=0.8, label='Prediction Start')
        
        # 在historical模式下绘制实际值（红色线）
        if show_actual:
            logger = UnifiedLogger.setup_logger_auto(__file__)
            logger.debug("show_actual=True，开始查找实际值数据")
            # 从任一模型结果中获取实际值（y_true）
            actual_values = None
            for i, (result, model_name, _, _) in enumerate(models_data):
                if result and 'y_true' in result and result['y_true'] is not None:
                    actual_values = result['y_true'][:pred_len]  # 只取前64个点
                    logger.debug(f"从{model_name}获取到实际值数据，长度: {len(actual_values)}")
                    logger.debug(f"前5个实际值: {actual_values[:5] if len(actual_values) >= 5 else actual_values}")
                    break
                else:
                    logger.debug(f"{model_name}模型结果中无有效y_true数据")
            
            if actual_values is not None and len(actual_values) > 0:
                # 过滤出非NaN的实际值
                valid_actual_indices = []
                valid_actual_values = []
                for i, val in enumerate(actual_values):
                    if not np.isnan(val):
                        valid_actual_indices.append(hist_len + i)
                        valid_actual_values.append(val)
                
                logger.debug(f"找到{len(valid_actual_indices)}个有效实际值点")
                if valid_actual_indices:
                    ax_main.plot(valid_actual_indices, valid_actual_values, 
                               color='red', label='Actual Price', linewidth=2.5, alpha=0.9)
                    logger.debug(f"成功绘制实际值线，点数: {len(valid_actual_indices)}")
                else:
                    logger.debug("所有实际值都是NaN，无法绘制")
            else:
                logger.debug("未找到实际值数据")
        
        # 设置主图标题和标签
        split_time = train_df['datetime'].iloc[-1] if 'datetime' in train_df.columns else train_df.index[-1]
        if hasattr(split_time, 'strftime'):
            time_str_display = split_time.strftime("%Y-%m-%d %H:%M")
        else:
            time_str_display = str(split_time)
        ax_main.set_title(f'{symbol} - Combined Model Predictions at {time_str_display}\nUsing {hist_len} historical points to predict next {pred_len} points', 
                         fontsize=16, weight='bold')
        ax_main.set_ylabel('Close Price', fontsize=14)
        ax_main.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)
        ax_main.legend(fontsize=12, loc='upper left')
        
        # 设置时间轴
        time_col = None
        for col in ['datetime', 'timestamps', 'date']:
            if col in train_df.columns:
                time_col = col
                break
        
        index_positions = [0, hist_len // 4, hist_len // 2, hist_len * 3 // 4, hist_len - 1, hist_len + pred_len - 1]
        time_labels = []
        
        for idx in index_positions:
            if idx < hist_len:
                if time_col:
                    dt = train_df[time_col].iloc[idx]
                    if hasattr(dt, 'strftime'):
                        time_labels.append(dt.strftime('%m-%d %H:%M'))
                    else:
                        time_labels.append(str(dt))
                else:
                    time_labels.append(f'T{idx}')
            else:
                pred_idx = idx - hist_len
                if time_col and hasattr(split_time, 'strftime'):
                    pred_times = pd.date_range(start=split_time + pd.Timedelta(minutes=1), periods=pred_len, freq='T')
                    dt = pred_times[pred_idx] if pred_idx < len(pred_times) else pred_times[-1]
                    time_labels.append(dt.strftime('%m-%d %H:%M'))
                else:
                    time_labels.append(f'P{pred_idx}')
        
        ax_main.set_xticks(index_positions)
        ax_main.set_xticklabels(time_labels, fontsize=11, rotation=20)
        
        # 绘制放大图（最后100个历史点 + 64个预测点）
        zoom_hist_len = 100
        zoom_start = max(0, hist_len - zoom_hist_len)
        zoom_end = hist_len + pred_len
        
        zoom_hist_indices = range(zoom_start, hist_len)
        zoom_pred_indices = range(hist_len, zoom_end)
        
        # 历史数据
        zoom_hist_values = train_df['close'].values[-(hist_len - zoom_start):]
        ax_zoom.plot(zoom_hist_indices, zoom_hist_values, 
                    color='steelblue', label='Historical Price', linewidth=2.0)
        
        # 各模型预测线
        for result, model_name, color, pred_key in models_data:
            if result and pred_key in result:
                zoom_pred_values = result[pred_key][:pred_len]
                # 验证zoom_pred_values不为空且有有效数据
                if len(zoom_pred_values) > 0 and not np.all(np.isnan(zoom_pred_values)):
                    ax_zoom.plot(zoom_pred_indices, zoom_pred_values, 
                               color=color, label=f'{model_name} Prediction', linewidth=2.0)
                    
                    # 绘制连接线
                    ax_zoom.plot([hist_len - 1, hist_len], 
                               [train_df['close'].iloc[-1], zoom_pred_values[0]], 
                               color=color, linewidth=2.0, linestyle='-')
        
        # 分割线
        ax_zoom.axvline(x=hist_len - 1, color='gray', linestyle='--', linewidth=2, alpha=0.8)
        
        # 在historical模式下绘制实际值（红色线）到zoom图
        if show_actual:
            # 从任一模型结果中获取实际值（y_true）
            actual_values = None
            for result, _, _, _ in models_data:
                if result and 'y_true' in result and result['y_true'] is not None:
                    actual_values = result['y_true'][:pred_len]  # 只取前64个点
                    break
            
            if actual_values is not None and len(actual_values) > 0:
                # 过滤出非NaN的实际值，限制在zoom范围内
                zoom_actual_indices = []
                zoom_actual_values = []
                for i, val in enumerate(actual_values):
                    if not np.isnan(val):
                        actual_index = hist_len + i
                        if zoom_start <= actual_index < zoom_end:
                            zoom_actual_indices.append(actual_index)
                            zoom_actual_values.append(val)
                
                if zoom_actual_indices:
                    ax_zoom.plot(zoom_actual_indices, zoom_actual_values, 
                               color='red', label='Actual Price', linewidth=2.5, alpha=0.9)
        
        # 设置放大图标题和标签
        ax_zoom.set_title(f'Zoomed Prediction Area (Last {zoom_hist_len} Historical + {pred_len} Prediction Points)', fontsize=14)
        ax_zoom.set_ylabel('Close Price', fontsize=12)
        ax_zoom.grid(True, linestyle='--', linewidth=0.5, alpha=0.7)
        
        # 放大图时间轴
        ticks = [zoom_start, hist_len - 1, zoom_end - 1]
        labels = []
        if time_col:
            dt1 = train_df[time_col].iloc[-(hist_len-zoom_start)]
            dt2 = train_df[time_col].iloc[-1]
            if hasattr(dt1, 'strftime'):
                labels.append(dt1.strftime('%m-%d %H:%M'))
                labels.append(dt2.strftime('%m-%d %H:%M'))
                if hasattr(split_time, 'strftime'):
                    pred_times = pd.date_range(start=split_time + pd.Timedelta(minutes=1), periods=pred_len, freq='T')
                    labels.append(pred_times[pred_len-1].strftime('%m-%d %H:%M'))
                else:
                    labels.append(f'P{pred_len-1}')
            else:
                labels.append(str(dt1))
                labels.append(str(dt2))
                labels.append(f'P{pred_len-1}')
        else:
            labels.append(f'T{zoom_start}')
            labels.append(f'T{hist_len-1}')
            labels.append(f'P{pred_len-1}')
        ax_zoom.set_xticks(ticks)
        ax_zoom.set_xticklabels(labels, fontsize=11, rotation=20)
        
        fig.tight_layout()
        
        # 保存图片
        chart_filename = f'{symbol.replace(".", "_")}_{time_str}_runall.png'
        chart_path = out_dir / chart_filename
        fig.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        
        return chart_path

    @staticmethod
    def warmup_all_models():
        """
        完全预热所有3个模型，确保：
        1. 所有模型都已加载到缓存
        2. 没有任何网络检查
        3. 所有模型完全就绪用于生产
        """
        import os
        
        # 强制完全离线模式
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        
        logger = UnifiedLogger.setup_logger_auto(__file__)
        logger.info("=" * 60)
        logger.info("🔥 开始完全预热所有预测模型...")
        logger.info("=" * 60)
        
        start_time = time.time()
        models_status = {}
        
        try:
            # 1. 预热Kronos模型
            logger.info("\n📦 [1/3] 预热Kronos模型...")
            kronos_start = time.time()
            try:
                from pb_quant_seektop_predictions_kronos import load_kronos_model
                kronos_model = load_kronos_model()
                kronos_time = time.time() - kronos_start
                if kronos_model is not None:
                    models_status['Kronos'] = f"✅ 就绪 ({kronos_time:.1f}s)"
                    logger.info(f"✅ Kronos模型预热完成，耗时: {kronos_time:.1f}秒")
                else:
                    models_status['Kronos'] = "❌ 加载失败"
                    logger.error("❌ Kronos模型加载失败")
            except Exception as e:
                models_status['Kronos'] = f"❌ 错误: {str(e)[:30]}"
                logger.error(f"❌ Kronos预热失败: {e}")
        
            # 2. 预热TimesFM模型（TimesFM 2.5）
            logger.info("\n📦 [2/3] 预热TimesFM模型...")
            timesfm_start = time.time()
            try:
                from pb_quant_seektop_predictions_timesfm2p5 import load_timesfm_model
                timesfm_model = load_timesfm_model()
                timesfm_time = time.time() - timesfm_start
                if timesfm_model is not None:
                    models_status['TimesFM'] = f"✅ 就绪 ({timesfm_time:.1f}s)"
                    logger.info(f"✅ TimesFM模型预热完成，耗时: {timesfm_time:.1f}秒")
                else:
                    models_status['TimesFM'] = "❌ 加载失败"
                    logger.error("❌ TimesFM模型加载失败")
            except Exception as e:
                models_status['TimesFM'] = f"❌ 错误: {str(e)[:30]}"
                logger.error(f"❌ TimesFM预热失败: {e}")
        
            # 3. 预热Chronos模型
            logger.info("\n📦 [3/3] 预热Chronos模型...")
            chronos_start = time.time()
            try:
                from pb_quant_seektop_predictions_chronos2 import load_chronos_model
                chronos_model = load_chronos_model()
                chronos_time = time.time() - chronos_start
                if chronos_model is not None:
                    models_status['Chronos'] = f"✅ 就绪 ({chronos_time:.1f}s)"
                    logger.info(f"✅ Chronos模型预热完成，耗时: {chronos_time:.1f}秒")
                else:
                    models_status['Chronos'] = "❌ 加载失败"
                    logger.error("❌ Chronos模型加载失败")
            except Exception as e:
                models_status['Chronos'] = f"❌ 错误: {str(e)[:30]}"
                logger.error(f"❌ Chronos预热失败: {e}")
        
            # 总结
            total_time = time.time() - start_time
            logger.info("\n" + "=" * 60)
            logger.info("🎉 模型预热完成汇总:")
            logger.info("=" * 60)
            for model_name, status in models_status.items():
                logger.info(f"  {model_name}: {status}")
            logger.info(f"📊 总耗时: {total_time:.1f}秒")
            logger.info("✅ 所有模型已完全就绪，可以开始生产预测")
            logger.info("=" * 60)
            
            return all("✅" in status for status in models_status.values())
            
        except Exception as e:
            logger.error(f"❌ 模型预热过程出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


# =============================================================================
# CSV 管理器模块 (从 pb_quant_seektop_csv_manager.py 迁移)
# =============================================================================

import fcntl
import time
from contextlib import contextmanager
import threading
import shutil

class PredictionCSVManager:
    """预测结果CSV文件的统一管理器"""
    
    def __init__(self):
        self._write_lock = threading.Lock()
        self._retry_times = 3
        self._retry_delay = 0.1
    
    @contextmanager
    def file_lock(self, file_path: Path, mode='r+'):
        """文件锁上下文管理器"""
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts:
            try:
                with open(file_path, mode, encoding='utf-8') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    yield f
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                return
            except (BlockingIOError, IOError) as e:
                attempt += 1
                if attempt >= max_attempts:
                    logger = logging.getLogger(__name__)
                    logger.error(f"无法获取文件锁，已尝试{max_attempts}次: {file_path}")
                    raise e
                time.sleep(0.05 * attempt)  # 递增延迟
    
    def save_predictions_thread_safe(
        self, 
        csv_path: Path, 
        new_prediction_data: Dict,
        keys: List[str] = ['prediction_time', 'model_name', 'symbol']
    ) -> bool:
        """线程安全的预测数据保存"""
        
        with self._write_lock:
            try:
                return self._save_predictions_internal(csv_path, new_prediction_data, keys)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"CSV写入失败: {e}")
                return False
    
    def _save_predictions_internal(
        self, 
        csv_path: Path, 
        new_prediction_data: Dict,
        keys: List[str]
    ) -> bool:
        """先删除后写入 - 简单粗暴模式"""
        
        # 确保目录存在
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 删除现有文件（如果存在）
        if csv_path.exists():
            csv_path.unlink()
        
        # 创建新数据并写入
        new_df = pd.DataFrame([new_prediction_data])
        new_df.to_csv(csv_path, index=False, float_format="%.4f")
        
        return True
    
    def save_predictions_append_mode(
        self, 
        csv_path: Path, 
        new_prediction_data: Dict
    ) -> bool:
        """线程安全的预测数据保存 - 追加模式"""
        
        with self._write_lock:
            try:
                return self._save_predictions_append_internal(csv_path, new_prediction_data)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"CSV追加写入失败: {e}")
                return False
    
    def _save_predictions_append_internal(
        self, 
        csv_path: Path, 
        new_prediction_data: Dict
    ) -> bool:
        """追加模式保存预测数据"""
        
        # 确保目录存在
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建新数据行
        new_df = pd.DataFrame([new_prediction_data])
        
        if csv_path.exists():
            # 文件存在，追加写入（不包含表头）
            new_df.to_csv(csv_path, mode='a', header=False, index=False, float_format="%.4f")
        else:
            # 文件不存在，创建新文件（包含表头）
            new_df.to_csv(csv_path, mode='w', header=True, index=False, float_format="%.4f")
        
        return True
    
    
    def save_metrics_thread_safe(
        self,
        csv_path: Path,
        new_metrics_data: Dict,
        keys: List[str] = ['prediction_time', 'model_name', 'symbol']
    ) -> bool:
        """线程安全的指标数据保存"""
        
        with self._write_lock:
            try:
                return self._save_metrics_internal(csv_path, new_metrics_data, keys)
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"指标CSV写入失败: {e}")
                return False
    
    def _save_metrics_internal(
        self,
        csv_path: Path,
        new_metrics_data: Dict,
        keys: List[str]
    ) -> bool:
        """先删除后写入 - 简单粗暴模式"""
        
        # 确保目录存在
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 删除现有文件（如果存在）
        if csv_path.exists():
            csv_path.unlink()
        
        # 创建新数据并写入
        new_df = pd.DataFrame([new_metrics_data])
        new_df.to_csv(csv_path, index=False)
        
        return True


# 全局单例实例
csv_manager = PredictionCSVManager()

def save_prediction_lines_unified(
    prediction_lines_csv_path: Path, 
    new_prediction_data: Dict, 
    keys: List[str] = ['prediction_time', 'model_name', 'symbol']
) -> bool:
    """统一的预测线数据保存函数"""
    return csv_manager.save_predictions_thread_safe(prediction_lines_csv_path, new_prediction_data, keys)

def save_metrics_unified(
    metrics_csv_path: Path,
    new_metrics_data: Dict,
    keys: List[str] = ['prediction_time', 'model_name', 'symbol']
) -> bool:
    """统一的指标数据保存函数"""
    return csv_manager.save_metrics_thread_safe(metrics_csv_path, new_metrics_data, keys)


# =============================================================================
# 预测模型公共函数 (从三个预测模型文件中提取)
# =============================================================================

def save_metrics_with_key_update(
    metrics_csv_path: Path, 
    new_metrics_data: list, 
    keys: list = ['prediction_time', 'model_name', 'symbol', 'evaluation_type']
):
    """保存指标数据，支持基于指定键的更新"""
    return save_metrics_unified(metrics_csv_path, new_metrics_data, keys)

def save_prediction_lines_with_key_update(
    prediction_lines_csv_path: Path, 
    new_prediction_data: dict, 
    keys: list = ['prediction_time', 'model_name', 'symbol']
):
    """保存预测线数据，支持基于指定键的更新"""
    return save_prediction_lines_unified(prediction_lines_csv_path, new_prediction_data, keys)

def save_prediction_lines_append_mode(
    prediction_lines_csv_path: Path, 
    new_prediction_data: dict
):
    """保存预测线数据，使用追加模式（用于预测脚本）"""
    return csv_manager.save_predictions_append_mode(prediction_lines_csv_path, new_prediction_data)

def print_header():
    """打印通用的标题头部"""
    logger = UnifiedLogger.setup_logger_auto(__file__)
    logger.info("="*60)
    logger.info("SeekTop 预测模型系统")
    logger.info("="*60)

# ============================================================================
# MPS/GPU 设备优化工具
# ============================================================================

DEVICE_CONFIG = {
    'ENABLE_MPS': True,              # 启用Apple Silicon MPS加速
    'USE_GPU_IF_AVAILABLE': True,    # 自动检测并使用GPU加速
    'AUTO_DEVICE_SELECTION': True,   # 自动选择最佳设备
    'FORCE_CPU': False,              # 强制使用CPU（用于调试）
}

def get_optimal_device(logger=None):
    """
    自动选择最佳计算设备 - 优先使用MPS (Apple Silicon)，次选CUDA，最后CPU
    支持Apple Silicon M1/M2/M3芯片的MPS加速
    """
    if DEVICE_CONFIG['FORCE_CPU']:
        return "cpu"
        
    if DEVICE_CONFIG['AUTO_DEVICE_SELECTION'] and DEVICE_CONFIG['USE_GPU_IF_AVAILABLE']:
        try:
            # 优先级1: Apple Silicon MPS
            if DEVICE_CONFIG['ENABLE_MPS'] and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                try:
                    test_tensor = torch.randn(1, device='mps')
                    if logger:
                        logger.info(f"✅ 检测到Apple Silicon (MPS)，使用GPU加速")
                        logger.info("🎯 性能提升: 2-8x (相比CPU)")
                    return "mps"
                except Exception as mps_error:
                    if logger:
                        logger.warning(f"⚠️ MPS初始化失败: {mps_error}，尝试其他设备")
            
            # 优先级2: NVIDIA CUDA
            if torch.cuda.is_available():
                gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
                if gpu_memory >= 4:
                    if logger:
                        logger.info(f"✅ 检测到CUDA GPU (内存: {gpu_memory:.1f}GB)，使用GPU加速")
                        logger.info("🎯 性能提升: 5-12x (相比CPU)")
                    return "cuda:0"
                else:
                    if logger:
                        logger.info(f"⚠️ GPU内存不足 ({gpu_memory:.1f}GB < 4GB)")
            
            # 优先级3: CPU with多线程优化
            cpu_count = torch.get_num_threads()
            if logger:
                logger.info(f"ℹ️ 使用CPU多线程优化 ({cpu_count}核心)")
                logger.info("🎯 性能提升: 1x (基线)")
            
        except Exception as e:
            if logger:
                logger.warning(f"设备检测失败: {e}，使用CPU")
    
    return "cpu"

def enable_mps_optimizations():
    """启用MPS特定的优化设置"""
    try:
        if hasattr(torch.backends, 'mps'):
            torch.backends.mps.deterministic = False  # 提高MPS性能
            torch.backends.mps.enabled = True
    except:
        pass
