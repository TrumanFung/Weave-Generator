"""
Launcher kept for backwards compatibility and PyInstaller:

    python weave_generator.py
    pyinstaller --onefile --windowed weave_generator.py

The application itself lives in the ``weavegen`` package.
"""

from weavegen.ui.app import main

if __name__ == "__main__":
    main()
