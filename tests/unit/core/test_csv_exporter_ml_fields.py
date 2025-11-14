"""
Unit tests for CSV Exporter ML field support.

Tests the new ML prediction fields added for monitoring mode.
"""
import pytest
import os
import pandas as pd
from core.csv_exporter import CSVExporter


class TestCSVExporterMLFields:
    """Test CSV exporter with ML prediction fields"""

    def test_flatten_with_ml_fields(self):
        """Test that ML fields are correctly flattened for CSV export"""
        exporter = CSVExporter(output_dir="test_output")

        analysis_result = {
            'ticker': 'TEST.NS',
            'status': 'success',
            'verdict': 'buy',
            'last_close': 100.0,
            'signals': ['rsi_oversold', 'hammer'],
            'rsi': 25.5,
            'pe': 15.0,
            'pb': 2.5,
            'avg_vol': 100000,
            'today_vol': 150000,
            'buy_range': [98, 102],
            'target': 110,
            'stop': 95,
            # ML prediction fields
            'ml_verdict': 'watch',
            'ml_confidence': 65.4,
            'ml_probabilities': {'strong_buy': 0.05, 'buy': 0.20, 'watch': 0.65, 'avoid': 0.10}
        }

        flattened = exporter.flatten_analysis_data(analysis_result)

        # Verify ML fields are in flattened output
        assert 'ml_verdict' in flattened
        assert 'ml_confidence' in flattened
        assert flattened['ml_verdict'] == 'watch'
        assert flattened['ml_confidence'] == 65.4

    def test_flatten_without_ml_fields(self):
        """Test that missing ML fields are handled gracefully"""
        exporter = CSVExporter(output_dir="test_output")

        analysis_result = {
            'ticker': 'TEST.NS',
            'status': 'success',
            'verdict': 'buy',
            'last_close': 100.0,
            # No ML fields
        }

        flattened = exporter.flatten_analysis_data(analysis_result)

        # Verify ML fields default to empty
        assert 'ml_verdict' in flattened
        assert 'ml_confidence' in flattened
        assert flattened['ml_verdict'] == ''
        assert flattened['ml_confidence'] == ''

    def test_export_with_ml_fields(self, tmp_path):
        """Test full export including ML fields"""
        output_dir = str(tmp_path / "csv_output")
        exporter = CSVExporter(output_dir=output_dir)

        analysis_result = {
            'ticker': 'TEST.NS',
            'status': 'success',
            'verdict': 'buy',
            'last_close': 100.0,
            'signals': ['rsi_oversold'],
            'rsi': 25.5,
            'pe': 15.0,
            'pb': 2.5,
            'avg_vol': 100000,
            'today_vol': 150000,
            'buy_range': [98, 102],
            'target': 110,
            'stop': 95,
            'ml_verdict': 'watch',
            'ml_confidence': 72.3
        }

        # Export to CSV
        filepath = exporter.export_single_stock(analysis_result, filename="test_export.csv")

        assert filepath is not None
        assert os.path.exists(filepath)

        # Read back and verify ML fields
        df = pd.read_csv(filepath)
        assert len(df) == 1
        assert df.iloc[0]['ticker'] == 'TEST.NS'
        assert df.iloc[0]['ml_verdict'] == 'watch'
        assert df.iloc[0]['ml_confidence'] == 72.3

    def test_ml_field_types(self):
        """Test that ML fields handle different data types correctly"""
        exporter = CSVExporter(output_dir="test_output")

        # Test with None values (get() returns None for missing keys)
        result1 = {
            'ticker': 'TEST1.NS',
            'ml_verdict': None,
            'ml_confidence': None
        }
        flattened1 = exporter.flatten_analysis_data(result1)
        # When value is None, get() with default '' returns ''
        # But if key exists with None value, it returns None
        # This is expected behavior for CSV export
        assert flattened1.get('ml_verdict') in (None, '')
        assert flattened1.get('ml_confidence') in (None, '')

        # Test with decimal confidence (0-1 range)
        result2 = {
            'ticker': 'TEST2.NS',
            'ml_verdict': 'buy',
            'ml_confidence': 0.851
        }
        flattened2 = exporter.flatten_analysis_data(result2)
        assert flattened2['ml_verdict'] == 'buy'
        assert flattened2['ml_confidence'] == 0.851

        # Test with percentage confidence (0-100 range)
        result3 = {
            'ticker': 'TEST3.NS',
            'ml_verdict': 'strong_buy',
            'ml_confidence': 92.7
        }
        flattened3 = exporter.flatten_analysis_data(result3)
        assert flattened3['ml_verdict'] == 'strong_buy'
        assert flattened3['ml_confidence'] == 92.7

