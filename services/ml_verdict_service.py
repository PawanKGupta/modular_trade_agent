"""
ML Verdict Service

ML-enhanced verdict service that uses trained models to predict verdicts.
Falls back to rule-based logic if ML model is unavailable.
"""

import os
import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Tuple, Any
from pathlib import Path
import joblib

from utils.logger import logger
from services.verdict_service import VerdictService


class MLVerdictService(VerdictService):
    """
    ML-enhanced verdict service
    
    Uses ML model to predict verdict probabilities,
    falls back to rule-based logic if ML unavailable.
    """
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        config=None
    ):
        """
        Initialize ML verdict service
        
        Args:
            model_path: Path to trained ML model (if None, will try to find based on config)
            config: Strategy configuration (uses default if None)
        """
        super().__init__(config)
        
        self.model = None
        self.model_loaded = False
        self.feature_cols = []
        
        # If no model_path provided, try to find model based on configuration
        if model_path is None:
            try:
                from utils.model_versioning import get_model_path
                model_path = get_model_path(self.config, "verdict")
                if model_path:
                    logger.info(f"Found model for config: {model_path}")
            except Exception as e:
                logger.debug(f"Could not find model for config: {e}")
        
        # Fallback to default model if no config-based model found
        # This provides a sensible default for production use
        if model_path is None:
            default_model = "models/verdict_model_random_forest.pkl"
            if Path(default_model).exists():
                model_path = default_model
                logger.info(f"Using default model: {default_model}")
        
        if model_path and Path(model_path).exists():
            try:
                self.model = joblib.load(model_path)
                self.model_loaded = True
                logger.info(f"✅ ML verdict model loaded from {model_path}")
                
                # Load feature columns if available
                feature_cols_path = Path(model_path).parent / f"{Path(model_path).stem.replace('model_', '')}_features.txt"
                if feature_cols_path.exists():
                    with open(feature_cols_path, 'r') as f:
                        self.feature_cols = [line.strip() for line in f if line.strip()]
                    logger.info(f"   Loaded {len(self.feature_cols)} feature columns")
                else:
                    logger.warning("Feature columns file not found. Will extract features dynamically.")
                    
            except Exception as e:
                logger.warning(f"⚠️ Failed to load ML model: {e}, using rule-based logic")
                self.model = None
                self.model_loaded = False
        else:
            if model_path:
                logger.warning(f"⚠️ Model file not found: {model_path}, using rule-based logic")
            else:
                logger.info("ℹ️ No ML model path provided, using rule-based logic")
    
    def determine_verdict(
        self,
        signals: List[str],
        rsi_value: Optional[float],
        is_above_ema200: bool,
        vol_ok: bool,
        vol_strong: bool,
        fundamental_ok: bool,
        timeframe_confirmation: Optional[Dict[str, Any]],
        news_sentiment: Optional[Dict[str, Any]],
        chart_quality_passed: bool = True,
        fundamental_assessment: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, List[str]]:
        """
        Determine verdict using ML if available, else rule-based
        
        Two-Stage Approach:
        1. Stage 1: Chart quality filter (hard filter) - MUST pass before ML
        2. Stage 2: ML model prediction (only if chart quality passed)
        
        Args:
            signals: List of detected signals
            rsi_value: Current RSI value
            is_above_ema200: Whether price is above EMA200
            vol_ok: Whether volume is OK
            vol_strong: Whether volume is strong
            fundamental_ok: Whether fundamentals are OK (backward compatibility)
            timeframe_confirmation: Multi-timeframe confirmation data
            news_sentiment: News sentiment data
            chart_quality_passed: Whether chart quality check passed (hard filter)
            fundamental_assessment: Optional fundamental assessment dict from assess_fundamentals()
                                    If provided, overrides fundamental_ok for more flexible logic
                                    (FLEXIBLE FUNDAMENTAL FILTER - 2025-11-09)
            
        Returns:
            Tuple of (verdict, justification)
        """
        # Stage 1: Chart quality filter (hard filter)
        # If chart quality fails, immediately return "avoid" without ML prediction
        # This is a CRITICAL filter - ML model should NEVER predict when chart quality fails
        if not chart_quality_passed:
            logger.info(f"ML verdict service: Chart quality FAILED - returning 'avoid' immediately (hard filter)")
            logger.info(f"ML verdict service: Skipping ML prediction (chart quality is mandatory)")
            return "avoid", ["Chart quality failed - too many gaps/extreme candles/flat movement"]
        
        # FLEXIBLE FUNDAMENTAL FILTER (2025-11-09): Check fundamental_avoid flag
        # If fundamental_avoid is True, force "avoid" verdict (expensive loss-making company)
        if fundamental_assessment is not None:
            fundamental_avoid = fundamental_assessment.get('fundamental_avoid', False)
            if fundamental_avoid:
                fundamental_reason = fundamental_assessment.get('fundamental_reason', 'loss_making_expensive')
                logger.info(f"ML verdict service: Fundamental filter FAILED - returning 'avoid' immediately (hard filter)")
                logger.info(f"ML verdict service: Skipping ML prediction (fundamental filter: {fundamental_reason})")
                return "avoid", [f"Fundamental filter: {fundamental_reason}"]
        
        # Stage 2: ML model prediction (TEMPORARILY DISABLED - 2025-11-09)
        # Using rule-based logic only until ML model is fully trained and calibrated
        # ML model predictions are logged for future training data collection
        
        # TEMPORARY: Use rule-based logic only (2025-11-09)
        # ML model is not fully trained yet, so we use rule-based logic for now
        # Log ML prediction for training data collection but don't use it for verdict
        if self.model_loaded:
            try:
                logger.info(f"ML verdict service: ML model loaded but using rule-based logic (ML not fully trained yet)")
                logger.debug(f"ML verdict service: Chart quality passed - would proceed with ML prediction")
                
                # Get ML prediction for logging/training data collection (but don't use it)
                ml_verdict = self._predict_with_ml(
                    signals, rsi_value, is_above_ema200,
                    vol_ok, vol_strong, fundamental_ok,
                    timeframe_confirmation, news_sentiment
                )
                if ml_verdict:
                    ml_justification = self._build_ml_justification(ml_verdict)
                    logger.info(f"ML verdict service: ML would predict '{ml_verdict}' (not used - using rule-based instead)")
                    logger.debug(f"ML prediction (for training data): {ml_verdict}, justification: {ml_justification}")
                else:
                    logger.debug(f"ML prediction returned None - using rule-based logic")
            except Exception as e:
                logger.warning(f"ML prediction failed: {e}, using rule-based logic")
                import traceback
                logger.debug(traceback.format_exc())
        else:
            logger.debug(f"ML verdict service: ML model not loaded - using rule-based logic")
        
        # Use rule-based logic (only if chart quality passed)
        # FLEXIBLE FUNDAMENTAL FILTER (2025-11-09): Pass fundamental_assessment to parent
        logger.debug(f"ML verdict service: Using rule-based logic for verdict determination")
        return super().determine_verdict(
            signals, rsi_value, is_above_ema200,
            vol_ok, vol_strong, fundamental_ok,
            timeframe_confirmation, news_sentiment,
            chart_quality_passed=chart_quality_passed,
            fundamental_assessment=fundamental_assessment
        )
    
    def _predict_with_ml(
        self,
        signals: List[str],
        rsi_value: Optional[float],
        is_above_ema200: bool,
        vol_ok: bool,
        vol_strong: bool,
        fundamental_ok: bool,
        timeframe_confirmation: Optional[Dict[str, Any]],
        news_sentiment: Optional[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Predict verdict using ML model
        
        Returns:
            Verdict string or None if prediction fails
        """
        try:
            # Extract features (note: _predict_with_ml is only called from determine_verdict
            # which doesn't have access to indicators/fundamentals/df, so they'll be None)
            features = self._extract_features(
                signals, rsi_value, is_above_ema200,
                vol_ok, vol_strong, fundamental_ok,
                timeframe_confirmation, news_sentiment,
                None, None, None
            )
            
            if not features:
                return None
            
            # Create feature vector matching model's expected format
            if self.feature_cols:
                # Use saved feature columns order
                feature_vector = [features.get(col, 0) for col in self.feature_cols]
            else:
                # Extract features dynamically (assumes model was trained with same features)
                feature_vector = list(features.values())
            
            # Predict
            probabilities = self.model.predict_proba([feature_vector])[0]
            verdicts = self.model.classes_  # ['strong_buy', 'buy', 'watch', 'avoid']
            
            # Get verdict with highest probability
            verdict_idx = probabilities.argmax()
            verdict = verdicts[verdict_idx]
            confidence = probabilities[verdict_idx]
            
            # Only use ML prediction if confidence > threshold
            if confidence > 0.5:  # 50% confidence threshold
                logger.debug(f"ML verdict: {verdict} (confidence: {confidence:.2%})")
                return verdict
            else:
                logger.debug(f"ML confidence too low ({confidence:.2%}), falling back to rules")
                return None
                
        except Exception as e:
            logger.debug(f"ML prediction error: {e}")
            return None
    
    def _extract_features(
        self,
        signals: List[str],
        rsi_value: Optional[float],
        is_above_ema200: bool,
        vol_ok: bool,
        vol_strong: bool,
        fundamental_ok: bool,
        timeframe_confirmation: Optional[Dict[str, Any]],
        news_sentiment: Optional[Dict[str, Any]],
        indicators: Optional[Dict[str, Any]] = None,
        fundamentals: Optional[Dict[str, Any]] = None,
        df: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Extract features for ML model matching training data format
        
        Training features: rsi_10, ema200, price, price_above_ema200, volume,
        avg_volume_20, volume_ratio, vol_strong, recent_high_20, recent_low_20,
        support_distance_pct, has_hammer, has_bullish_engulfing, has_divergence,
        alignment_score, pe, pb, fundamental_ok
        
        Returns:
            Dict with feature values
        """
        import pandas as pd
        
        features = {}
        
        # Get configurable parameters from config (defaults for backward compatibility)
        rsi_period = self.config.rsi_period if self.config else 10
        volume_lookback = self.config.volume_exhaustion_lookback_daily if self.config else 20
        support_lookback = self.config.support_resistance_lookback_daily if self.config else 20
        
        # Basic indicators - use configurable RSI period
        rsi_feature_name = f'rsi_{rsi_period}'
        features[rsi_feature_name] = float(rsi_value) if rsi_value is not None else 50.0
        
        # Also keep 'rsi_10' for backward compatibility if period == 10
        if rsi_period == 10:
            features['rsi_10'] = features[rsi_feature_name]
        
        features['ema200'] = float(indicators.get('ema200', 0)) if indicators else 0.0
        features['price'] = float(indicators.get('close', 0)) if indicators else 0.0
        features['price_above_ema200'] = 1.0 if is_above_ema200 else 0.0
        
        # Volume features - use configurable volume lookback
        if df is not None and not df.empty:
            try:
                features['volume'] = float(df['volume'].iloc[-1])
                avg_volume_feature_name = f'avg_volume_{volume_lookback}'
                features[avg_volume_feature_name] = float(df['volume'].tail(volume_lookback).mean()) if len(df) >= volume_lookback else features['volume']
                
                # Also keep 'avg_volume_20' for backward compatibility if lookback == 20
                if volume_lookback == 20:
                    features['avg_volume_20'] = features[avg_volume_feature_name]
                
                features['volume_ratio'] = features['volume'] / features[avg_volume_feature_name] if features[avg_volume_feature_name] > 0 else 1.0
            except:
                features['volume'] = 0.0
                avg_volume_feature_name = f'avg_volume_{volume_lookback}'
                features[avg_volume_feature_name] = 0.0
                if volume_lookback == 20:
                    features['avg_volume_20'] = 0.0
                features['volume_ratio'] = 1.0
        else:
            features['volume'] = 0.0
            avg_volume_feature_name = f'avg_volume_{volume_lookback}'
            features[avg_volume_feature_name] = 0.0
            if volume_lookback == 20:
                features['avg_volume_20'] = 0.0
            features['volume_ratio'] = 1.0
        
        features['vol_strong'] = 1.0 if vol_strong else 0.0
        
        # Price action features - use configurable support/resistance lookback
        if df is not None and not df.empty:
            try:
                recent_high_feature_name = f'recent_high_{support_lookback}'
                recent_low_feature_name = f'recent_low_{support_lookback}'
                
                features[recent_high_feature_name] = float(df['high'].tail(support_lookback).max()) if len(df) >= support_lookback else features['price']
                features[recent_low_feature_name] = float(df['low'].tail(support_lookback).min()) if len(df) >= support_lookback else features['price']
                
                # Also keep 'recent_high_20' and 'recent_low_20' for backward compatibility if lookback == 20
                if support_lookback == 20:
                    features['recent_high_20'] = features[recent_high_feature_name]
                    features['recent_low_20'] = features[recent_low_feature_name]
                
                if features['price'] > 0:
                    features['support_distance_pct'] = ((features['price'] - features[recent_low_feature_name]) / features['price']) * 100
                else:
                    features['support_distance_pct'] = 0.0
            except:
                recent_high_feature_name = f'recent_high_{support_lookback}'
                recent_low_feature_name = f'recent_low_{support_lookback}'
                features[recent_high_feature_name] = features['price']
                features[recent_low_feature_name] = features['price']
                if support_lookback == 20:
                    features['recent_high_20'] = features['price']
                    features['recent_low_20'] = features['price']
                features['support_distance_pct'] = 0.0
        else:
            recent_high_feature_name = f'recent_high_{support_lookback}'
            recent_low_feature_name = f'recent_low_{support_lookback}'
            features[recent_high_feature_name] = features['price']
            features[recent_low_feature_name] = features['price']
            if support_lookback == 20:
                features['recent_high_20'] = features['price']
                features['recent_low_20'] = features['price']
            features['support_distance_pct'] = 0.0
        
        # Pattern signals
        features['has_hammer'] = 1.0 if 'hammer' in signals else 0.0
        features['has_bullish_engulfing'] = 1.0 if 'bullish_engulfing' in signals else 0.0
        features['has_divergence'] = 1.0 if 'bullish_divergence' in signals else 0.0
        
        # Multi-timeframe
        features['alignment_score'] = float(timeframe_confirmation.get('alignment_score', 0)) if timeframe_confirmation else 0.0
        
        # Fundamentals
        if fundamentals:
            features['pe'] = float(fundamentals.get('pe', 0)) if fundamentals.get('pe') is not None else 0.0
            features['pb'] = float(fundamentals.get('pb', 0)) if fundamentals.get('pb') is not None else 0.0
        else:
            features['pe'] = 0.0
            features['pb'] = 0.0
        
        features['fundamental_ok'] = 1.0 if fundamental_ok else 0.0
        
        return features
    
    def _build_ml_justification(self, verdict: str) -> List[str]:
        """Build justification for ML verdict"""
        return [f"ML prediction: {verdict}"]
    
    def predict_verdict_with_confidence(
        self,
        signals: List[str],
        rsi_value: Optional[float],
        is_above_ema200: bool,
        vol_ok: bool,
        vol_strong: bool,
        fundamental_ok: bool,
        timeframe_confirmation: Optional[Dict[str, Any]],
        news_sentiment: Optional[Dict[str, Any]],
        indicators: Optional[Dict[str, Any]] = None,
        fundamentals: Optional[Dict[str, Any]] = None,
        df: Optional[Any] = None,
        chart_quality_passed: bool = True
    ) -> Tuple[Optional[str], float]:
        """
        Predict verdict with confidence score (for testing/comparison)
        
        Two-Stage Approach:
        1. Stage 1: Chart quality filter (hard filter) - MUST pass before ML
        2. Stage 2: ML model prediction (only if chart quality passed)
        
        Args:
            signals: List of detected signals
            rsi_value: Current RSI value
            is_above_ema200: Whether price is above EMA200
            vol_ok: Whether volume is OK
            vol_strong: Whether volume is strong
            fundamental_ok: Whether fundamentals are OK
            timeframe_confirmation: Multi-timeframe confirmation data
            news_sentiment: News sentiment data
            indicators: Optional indicators dict
            fundamentals: Optional fundamentals dict
            df: Optional DataFrame
            chart_quality_passed: Whether chart quality check passed (hard filter)
            
        Returns:
            Tuple of (verdict, confidence) or (None, 0.0) if unavailable or chart quality failed
        """
        # Stage 1: Chart quality filter (hard filter)
        # If chart quality fails, return None (skip ML prediction)
        if not chart_quality_passed:
            logger.debug("ML prediction skipped: Chart quality failed (two-stage filter)")
            return None, 0.0
        
        if not self.model_loaded:
            return None, 0.0
        
        try:
            features = self._extract_features(
                signals, rsi_value, is_above_ema200,
                vol_ok, vol_strong, fundamental_ok,
                timeframe_confirmation, news_sentiment,
                indicators, fundamentals, df
            )
            
            if self.feature_cols:
                feature_vector = [features.get(col, 0) for col in self.feature_cols]
            else:
                feature_vector = list(features.values())
            
            probabilities = self.model.predict_proba([feature_vector])[0]
            verdicts = self.model.classes_
            
            verdict_idx = probabilities.argmax()
            verdict = verdicts[verdict_idx]
            confidence = probabilities[verdict_idx]
            
            return verdict, confidence
            
        except Exception as e:
            logger.debug(f"ML prediction error: {e}")
            return None, 0.0
