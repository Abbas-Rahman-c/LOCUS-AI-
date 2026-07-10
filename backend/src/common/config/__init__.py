"""
Config package.
Dynamically imports all *.config.py files and exposes their functions/classes.
"""
from __future__ import annotations
import os
import sys
import importlib.util

# Get directory path of the config package
config_dir = os.path.dirname(__file__)

# Iterate over all files in the directory
for filename in os.listdir(config_dir):
    if filename.endswith(".config.py"):
        # e.g., 'gmail.config.py' -> name: 'gmail'
        module_name = filename.split(".")[0]
        full_module_name = f"common.config.{module_name}"
        
        file_path = os.path.join(config_dir, filename)
        spec = importlib.util.spec_from_file_location(full_module_name, file_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[full_module_name] = module
            spec.loader.exec_module(module)
            
            # Expose variables in the package namespace
            # e.g. expose `get_gmail_settings`
            for attr in dir(module):
                if not attr.startswith("_"):
                    globals()[attr] = getattr(module, attr)
