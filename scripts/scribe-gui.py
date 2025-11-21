"""
Scribe GUI Launcher

Launches the professional Scribe GUI interface.
"""

import sys
import os

# Add src to path to enable imports (handle both direct run and installed)
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)  # Go up from scripts/ to project root
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, src_dir)

from scribe.gui.app_pro import ScribeProGUI

if __name__ == "__main__":
    app = ScribeProGUI()
    app.run()
