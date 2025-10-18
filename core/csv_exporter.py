import csv
import os
from datetime import datetime
import pandas as pd
from utils.logger import logger

class CSVExporter:
    """
    Handles exporting stock analysis data to CSV files
    """
    
    def __init__(self, output_dir="analysis_results"):
        """
        Initialize CSV exporter
        
        Args:
            output_dir: Directory to store CSV files
        """
        self.output_dir = output_dir
        self.ensure_output_directory()
        
    def ensure_output_directory(self):
        """Create output directory if it doesn't exist"""
        try:
            if not os.path.exists(self.output_dir):
                os.makedirs(self.output_dir)
                logger.info(f"Created output directory: {self.output_dir}")
        except Exception as e:
            logger.error(f"Failed to create output directory {self.output_dir}: {e}")
            
    def flatten_analysis_data(self, analysis_result):
        """
        Flatten nested analysis data for CSV export
        
        Args:
            analysis_result: Dictionary containing analysis results
            
        Returns:
            Dictionary with flattened data suitable for CSV
        """
        try:
            flattened = {}
            
            # Basic information
            flattened['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            flattened['ticker'] = analysis_result.get('ticker', '')
            flattened['status'] = analysis_result.get('status', '')
            flattened['verdict'] = analysis_result.get('verdict', '')
            flattened['last_close'] = analysis_result.get('last_close', 0)
            
            # Trading signals
            signals = analysis_result.get('signals', [])
            flattened['signals_count'] = len(signals)
            flattened['signals'] = ', '.join(signals)
            
            # Pattern signals
            pattern_signals = [s for s in signals if s in ['hammer', 'bullish_engulfing', 'bullish_divergence', 'rsi_oversold']]
            flattened['pattern_signals'] = ', '.join(pattern_signals)
            
            # Timeframe signals
            timeframe_signals = [s for s in signals if 'timeframe_alignment' in s]
            flattened['timeframe_signals'] = ', '.join(timeframe_signals)
            
            # Technical indicators
            flattened['rsi'] = analysis_result.get('rsi', 0)
            flattened['pe'] = analysis_result.get('pe', 0)
            flattened['pb'] = analysis_result.get('pb', 0)
            
            # Volume analysis
            flattened['avg_volume'] = analysis_result.get('avg_vol', 0)
            flattened['current_volume'] = analysis_result.get('today_vol', 0)
            volume_ratio = flattened['current_volume'] / flattened['avg_volume'] if flattened['avg_volume'] > 0 else 0
            flattened['volume_ratio'] = round(volume_ratio, 2)
            
            # Trading parameters
            buy_range = analysis_result.get('buy_range', [])
            if buy_range and isinstance(buy_range, (list, tuple)) and len(buy_range) >= 2:
                flattened['buy_range_low'] = buy_range[0]
                flattened['buy_range_high'] = buy_range[1]
            else:
                flattened['buy_range_low'] = 0
                flattened['buy_range_high'] = 0
                
            flattened['target'] = analysis_result.get('target', 0)
            flattened['stop'] = analysis_result.get('stop', 0)
            
            # Calculate potential returns
            if flattened['target'] and flattened['last_close']:
                potential_gain = ((flattened['target'] / flattened['last_close']) - 1) * 100
                flattened['potential_gain_pct'] = round(potential_gain, 2)
            else:
                flattened['potential_gain_pct'] = 0
                
            if flattened['stop'] and flattened['last_close']:
                potential_loss = ((flattened['stop'] / flattened['last_close']) - 1) * 100
                flattened['potential_loss_pct'] = round(potential_loss, 2)
                risk_reward = abs(potential_gain / potential_loss) if potential_loss != 0 else 0
                flattened['risk_reward_ratio'] = round(risk_reward, 2)
            else:
                flattened['potential_loss_pct'] = 0
                flattened['risk_reward_ratio'] = 0
            
            # Justifications
            justifications = analysis_result.get('justification', [])
            flattened['justifications'] = ', '.join(justifications)
            
            # Multi-timeframe analysis
            timeframe_analysis = analysis_result.get('timeframe_analysis')
            if timeframe_analysis:
                flattened['mtf_alignment_score'] = timeframe_analysis.get('alignment_score', 0)
                flattened['mtf_confirmation'] = timeframe_analysis.get('confirmation', 'none')
                
                # Daily analysis (new dip-buying structure)
                daily_analysis = timeframe_analysis.get('daily_analysis', {})
                if daily_analysis:
                    # Support analysis
                    support_analysis = daily_analysis.get('support_analysis', {})
                    flattened['daily_support_quality'] = support_analysis.get('quality', 'neutral')
                    flattened['daily_support_distance'] = support_analysis.get('distance_pct', 0)
                    
                    # Oversold analysis
                    oversold_analysis = daily_analysis.get('oversold_analysis', {})
                    flattened['daily_oversold_condition'] = oversold_analysis.get('condition', 'neutral')
                    flattened['daily_oversold_severity'] = oversold_analysis.get('severity', 'neutral')
                    
                    # Volume exhaustion
                    volume_exhaustion = daily_analysis.get('volume_exhaustion', {})
                    flattened['daily_volume_trend'] = volume_exhaustion.get('volume_trend', 'neutral')
                    flattened['daily_volume_exhaustion_score'] = volume_exhaustion.get('exhaustion_score', 0)
                    
                    # Reversion setup
                    reversion_setup = daily_analysis.get('reversion_setup', {})
                    flattened['daily_reversion_quality'] = reversion_setup.get('quality', 'neutral')
                    flattened['daily_reversion_score'] = reversion_setup.get('score', 0)
                    
                    # Resistance analysis
                    resistance_analysis = daily_analysis.get('resistance_analysis', {})
                    flattened['daily_resistance_quality'] = resistance_analysis.get('quality', 'neutral')
                    flattened['daily_resistance_distance'] = resistance_analysis.get('distance_pct', 0)
                
                # Weekly analysis (new dip-buying structure)
                weekly_analysis = timeframe_analysis.get('weekly_analysis', {})
                if weekly_analysis:
                    # Support analysis
                    support_analysis = weekly_analysis.get('support_analysis', {})
                    flattened['weekly_support_quality'] = support_analysis.get('quality', 'neutral')
                    flattened['weekly_support_distance'] = support_analysis.get('distance_pct', 0)
                    
                    # Oversold analysis
                    oversold_analysis = weekly_analysis.get('oversold_analysis', {})
                    flattened['weekly_oversold_condition'] = oversold_analysis.get('condition', 'neutral')
                    flattened['weekly_oversold_severity'] = oversold_analysis.get('severity', 'neutral')
                    
                    # Volume exhaustion
                    volume_exhaustion = weekly_analysis.get('volume_exhaustion', {})
                    flattened['weekly_volume_trend'] = volume_exhaustion.get('volume_trend', 'neutral')
                    flattened['weekly_volume_exhaustion_score'] = volume_exhaustion.get('exhaustion_score', 0)
                    
                    # Reversion setup
                    reversion_setup = weekly_analysis.get('reversion_setup', {})
                    flattened['weekly_reversion_quality'] = reversion_setup.get('quality', 'neutral')
                    flattened['weekly_reversion_score'] = reversion_setup.get('score', 0)
            else:
                # Set default values when no timeframe analysis
                mtf_fields = [
                    'mtf_alignment_score', 'mtf_confirmation', 
                    'daily_support_quality', 'daily_support_distance', 'daily_oversold_condition', 'daily_oversold_severity',
                    'daily_volume_trend', 'daily_volume_exhaustion_score', 'daily_reversion_quality', 'daily_reversion_score',
                    'daily_resistance_quality', 'daily_resistance_distance',
                    'weekly_support_quality', 'weekly_support_distance', 'weekly_oversold_condition', 'weekly_oversold_severity',
                    'weekly_volume_trend', 'weekly_volume_exhaustion_score', 'weekly_reversion_quality', 'weekly_reversion_score'
                ]
                for field in mtf_fields:
                    flattened[field] = 0 if 'score' in field or 'distance' in field else 'neutral'
            
            return flattened
            
        except Exception as e:
            logger.error(f"Error flattening analysis data: {e}")
            return {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'ticker': analysis_result.get('ticker', ''),
                'status': 'export_error',
                'error': str(e)
            }
    
    def export_single_stock(self, analysis_result, filename=None):
        """
        Export single stock analysis to CSV
        
        Args:
            analysis_result: Analysis result dictionary
            filename: Optional custom filename
        """
        try:
            ticker = analysis_result.get('ticker', 'unknown')
            
            if filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{ticker}_analysis_{timestamp}.csv"
            
            filepath = os.path.join(self.output_dir, filename)
            flattened_data = self.flatten_analysis_data(analysis_result)
            
            # Create DataFrame and export to CSV
            df = pd.DataFrame([flattened_data])
            df.to_csv(filepath, index=False)
            
            logger.info(f"Exported {ticker} analysis to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to export single stock analysis: {e}")
            return None
    
    def export_multiple_stocks(self, analysis_results, filename=None):
        """
        Export multiple stock analyses to a single CSV
        
        Args:
            analysis_results: List of analysis result dictionaries
            filename: Optional custom filename
        """
        try:
            if filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"bulk_analysis_{timestamp}.csv"
            
            filepath = os.path.join(self.output_dir, filename)
            
            # Flatten all analysis data
            flattened_data = []
            for result in analysis_results:
                flattened_data.append(self.flatten_analysis_data(result))
            
            # Create DataFrame and export to CSV
            df = pd.DataFrame(flattened_data)
            
            # Sort by verdict priority and alignment score
            verdict_priority = {'strong_buy': 1, 'buy': 2, 'watch': 3, 'avoid': 4}
            df['verdict_priority'] = df['verdict'].map(verdict_priority).fillna(5)
            df = df.sort_values(['verdict_priority', 'mtf_alignment_score'], ascending=[True, False])
            df = df.drop('verdict_priority', axis=1)
            
            df.to_csv(filepath, index=False)
            
            logger.info(f"Exported {len(analysis_results)} stock analyses to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to export multiple stock analyses: {e}")
            return None
    
    def append_to_master_csv(self, analysis_result, master_filename="master_analysis.csv"):
        """
        Append analysis result to a master CSV file for historical tracking
        
        Args:
            analysis_result: Analysis result dictionary
            master_filename: Name of master CSV file
        """
        try:
            master_filepath = os.path.join(self.output_dir, master_filename)
            flattened_data = self.flatten_analysis_data(analysis_result)
            
            # Check if master file exists
            file_exists = os.path.isfile(master_filepath)
            
            # Create DataFrame
            df = pd.DataFrame([flattened_data])
            
            if file_exists:
                # Append to existing file
                df.to_csv(master_filepath, mode='a', header=False, index=False)
            else:
                # Create new file with headers
                df.to_csv(master_filepath, index=False)
                
            logger.debug(f"Appended {analysis_result.get('ticker', 'unknown')} to master CSV")
            return master_filepath
            
        except Exception as e:
            logger.error(f"Failed to append to master CSV: {e}")
            return None
    
    def get_csv_headers(self):
        """
        Get the standard CSV headers for reference
        
        Returns:
            List of column headers
        """
        return [
            'timestamp', 'ticker', 'status', 'verdict', 'last_close',
            'signals_count', 'signals', 'pattern_signals', 'timeframe_signals',
            'rsi', 'pe', 'pb', 'avg_volume', 'current_volume', 'volume_ratio',
            'buy_range_low', 'buy_range_high', 'target', 'stop',
            'potential_gain_pct', 'potential_loss_pct', 'risk_reward_ratio',
            'justifications', 'mtf_alignment_score', 'mtf_confirmation',
            'daily_price_trend', 'daily_trend_strength', 'daily_ema_alignment', 'daily_price_position',
            'daily_short_momentum', 'daily_medium_momentum', 'daily_volume_trend', 'daily_rsi_trend', 'daily_rsi_level',
            'weekly_price_trend', 'weekly_trend_strength', 'weekly_ema_alignment', 'weekly_price_position',
            'weekly_short_momentum', 'weekly_medium_momentum', 'weekly_rsi_trend', 'weekly_rsi_level'
        ]