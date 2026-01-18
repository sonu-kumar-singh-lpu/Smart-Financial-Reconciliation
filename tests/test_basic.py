"""Basic tests for the financial reconciliation system."""

import os
import sys
import pandas as pd
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_data_files_exist():
    """Test that required data files exist."""
    required_files = [
        'data/bank_statement.csv',
        'data/ledger_entries.csv',
        'data/transactions.csv'
    ]
    
    for file_path in required_files:
        assert os.path.exists(file_path), f"Required file {file_path} does not exist"


def test_csv_files_loadable():
    """Test that CSV files can be loaded without errors."""
    try:
        bank_df = pd.read_csv('data/bank_statement.csv')
        ledger_df = pd.read_csv('data/ledger_entries.csv')
        trans_df = pd.read_csv('data/transactions.csv')
        
        # Basic checks
        assert len(bank_df) > 0, "Bank statement is empty"
        assert len(ledger_df) > 0, "Ledger entries is empty"
        assert len(trans_df) > 0, "Transactions is empty"
        
    except Exception as e:
        pytest.fail(f"Failed to load CSV files: {e}")


def test_module_imports():
    """Test that all main modules can be imported."""
    try:
        import utils
        import anomaly
        import recommendation_engine
        import transaction_classifier
        import report_pdf
    except ImportError as e:
        pytest.fail(f"Failed to import modules: {e}")


def test_requirements_file_exists():
    """Test that requirements.txt exists and is not empty."""
    assert os.path.exists('requirements.txt'), "requirements.txt does not exist"
    
    with open('requirements.txt', 'r') as f:
        content = f.read().strip()
        assert len(content) > 0, "requirements.txt is empty"


def test_dockerfile_exists():
    """Test that Dockerfile exists."""
    assert os.path.exists('Dockerfile'), "Dockerfile does not exist"