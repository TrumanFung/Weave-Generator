# PyInstaller build recipe:  pyinstaller weave_generator.spec
# Produces dist/WeaveGenerator.exe (one file, no console window, with the icon).

from PyInstaller.utils.hooks import collect_submodules

hidden = collect_submodules("weavegen")

a = Analysis(
    ["weave_generator.py"],
    pathex=["."],
    datas=[("weavegen/assets/icon.png", "assets"), ("weavegen/assets/icon.ico", "assets")],
    hiddenimports=hidden,
    # Nothing here uses these, and leaving them out keeps the exe smaller.
    excludes=["pytest", "matplotlib", "scipy", "pandas", "IPython", "unittest", "pydoc", "doctest"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="WeaveGenerator",
    icon="weavegen/assets/icon.ico",
    console=False,
    upx=False,
)
