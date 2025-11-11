#!/usr/bin/env python3
"""
ML Model Retraining Script

Retrains ML models with custom configuration.
"""

import sys
import os
from pathlib import Path
import argparse
import pandas as pd
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.strategy_config import StrategyConfig
from services.ml_training_service import MLTrainingService
from utils.model_versioning import get_next_version, register_model


def main():
    parser = argparse.ArgumentParser(description="Retrain ML models with custom configuration")
    parser.add_argument("--rsi-period", type=int, default=10, help="RSI period")
    parser.add_argument("--vol-lookback", type=int, default=20, help="Volume exhaustion lookback (daily)")
    parser.add_argument("--support-lookback", type=int, default=20, help="Support/resistance lookback (daily)")
    parser.add_argument("--training-data", type=str, required=True, help="Path to training data CSV")
    parser.add_argument("--validation-data", type=str, help="Path to validation data CSV")
    parser.add_argument("--model-type", type=str, choices=["verdict", "price", "both"], default="both", help="Model type to train")
    
    args = parser.parse_args()
    
    # Create configuration
    config = StrategyConfig(
        rsi_period=args.rsi_period,
        volume_exhaustion_lookback_daily=args.vol_lookback,
        support_resistance_lookback_daily=args.support_lookback
    )
    
    print(f"\n{'='*80}")
    print(f"ML Model Retraining")
    print(f"{'='*80}")
    print(f"Configuration:")
    print(f"  RSI Period: {config.rsi_period}")
    print(f"  Volume Lookback: {config.volume_exhaustion_lookback_daily}")
    print(f"  Support Lookback: {config.support_resistance_lookback_daily}")
    print(f"  Model Type: {args.model_type}")
    print(f"{'='*80}\n")
    
    # Load training data
    print(f"Loading training data from {args.training_data}...")
    if not Path(args.training_data).exists():
        print(f"ERROR: Training data file not found: {args.training_data}")
        return 1
    
    training_data = pd.read_csv(args.training_data)
    print(f"  Loaded {len(training_data)} samples")
    
    # Load validation data if provided
    validation_data = None
    if args.validation_data:
        if Path(args.validation_data).exists():
            validation_data = pd.read_csv(args.validation_data)
            print(f"  Loaded {len(validation_data)} validation samples")
        else:
            print(f"WARNING: Validation data file not found: {args.validation_data}")
    
    # Initialize training service
    try:
        trainer = MLTrainingService()  # models_dir defaults to "models"
    except Exception as e:
        print(f"ERROR: Failed to initialize training service: {e}")
        return 1
    
    performance = {}
    
    # Train verdict model
    if args.model_type in ["verdict", "both"]:
        print(f"\n{'='*80}")
        print("Training Verdict Model...")
        print(f"{'='*80}")
        
        try:
            # Save training data to temp file for train_verdict_classifier
            temp_training_file = "data/temp_training_for_retraining.csv"
            training_data.to_csv(temp_training_file, index=False)
            
            # Train model (returns path to saved model)
            verdict_path = trainer.train_verdict_classifier(
                training_data_path=temp_training_file,
                test_size=0.2,
                model_type="random_forest"
            )
            
            # Get next version
            version = get_next_version(config, "verdict")
            
            # Rename to versioned filename
            import shutil
            versioned_path = f"models/verdict_model_rsi{config.rsi_period}_vol{config.volume_exhaustion_lookback_daily}_support{config.support_resistance_lookback_daily}_v{version}.pkl"
            shutil.copy(verdict_path, versioned_path)
            
            print(f"  Model saved: {verdict_path}")
            
            # Evaluate if validation data available
            if validation_data is not None:
                verdict_perf = trainer.evaluate_verdict_model(validation_data)
                performance["verdict"] = verdict_perf
                print(f"  Performance: {verdict_perf}")
            else:
                performance["verdict"] = {}
            
            # Register model
            register_model(config, "verdict", verdict_path, version, performance.get("verdict"))
            print(f"  Model registered: v{version}")
            
        except Exception as e:
            print(f"ERROR: Failed to train verdict model: {e}")
            import traceback
            traceback.print_exc()
            return 1
    
    # Train price model
    if args.model_type in ["price", "both"]:
        print(f"\n{'='*80}")
        print("Training Price Model...")
        print(f"{'='*80}")
        
        try:
            # Save training data to temp file
            temp_training_file = "data/temp_training_for_retraining.csv"
            training_data.to_csv(temp_training_file, index=False)
            
            # Train model (returns path to saved model)
            price_path = trainer.train_price_regressor(
                training_data_path=temp_training_file,
                target_column="actual_pnl_pct",
                test_size=0.2,
                model_type="random_forest"
            )
            
            # Get next version
            version = get_next_version(config, "price")
            
            # Rename to versioned filename
            import shutil
            versioned_path = f"models/price_model_rsi{config.rsi_period}_vol{config.volume_exhaustion_lookback_daily}_support{config.support_resistance_lookback_daily}_v{version}.pkl"
            shutil.copy(price_path, versioned_path)
            
            print(f"  Model saved: {price_path}")
            
            # Evaluate if validation data available
            if validation_data is not None:
                price_perf = trainer.evaluate_price_model(validation_data)
                performance["price"] = price_perf
                print(f"  Performance: {price_perf}")
            else:
                performance["price"] = {}
            
            # Register model
            register_model(config, "price", price_path, version, performance.get("price"))
            print(f"  Model registered: v{version}")
            
        except Exception as e:
            print(f"ERROR: Failed to train price model: {e}")
            import traceback
            traceback.print_exc()
            return 1
    
    print(f"\n{'='*80}")
    print("Model Retraining Complete!")
    print(f"{'='*80}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

