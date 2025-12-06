#!/usr/bin/env python3
"""
Simple test runner script to verify pytest setup works correctly.
Run this to test the Discord bot commands with mocked dependencies.
"""
import sys
import os
from pathlib import Path

# Add bot directory to Python path
bot_dir = Path(__file__).parent / "bot"
sys.path.insert(0, str(bot_dir))

if __name__ == "__main__":
    # Set environment variable for testing
    os.environ['TESTING'] = '1'
    
    # Run pytest with basic configuration
    import pytest
    
    args = [
        "tests/",
        "-v", 
        "--tb=short",
        "--disable-warnings"
    ]
    
    sys.exit(pytest.main(args))