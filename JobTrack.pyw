"""Double-click to launch the persistent workbench without a console window."""
import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)
from main import main

if __name__ == '__main__':
    main()
