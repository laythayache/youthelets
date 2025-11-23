#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Download InsightFace models"""
import os
import sys

# Set UTF-8 encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    from insightface.model_zoo import get_model
    print("Downloading InsightFace models...")
    print("This may take a few minutes...")
    
    models_to_download = ['buffalo_l']
    
    for model_name in models_to_download:
        try:
            print(f"\nDownloading {model_name}...")
            model = get_model(model_name, download=True)
            if model:
                print(f"[OK] {model_name} downloaded successfully")
            else:
                print(f"[WARNING] {model_name} download returned None")
        except Exception as e:
            print(f"[ERROR] Error downloading {model_name}: {e}")
    
    print("\nModel download complete!")
    print("You can now run the Flask app with: python app.py")
except ImportError as e:
    print(f"Error: Could not import insightface: {e}")
    print("Please install insightface first: pip install insightface")

