#!/usr/bin/env python
"""
GUI launcher for Queue Estimation System.

Usage::
    python gui.py
    
This opens a graphical interface for:
- Selecting video files
- Defining queue zones interactively
- Configuring analysis parameters
- Running the analysis without terminal commands
"""

from backend.src.gui.app import main

if __name__ == "__main__":
    main()
