# PyInstaller build of the FastAPI backend. Run through build.sh.
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []
for package in ("sentence_transformers", "transformers", "tokenizers", "fitz", "pymupdf"):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports

analysis = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["sklearn.metrics.pairwise"],
    excludes=["tensorflow", "matplotlib", "IPython", "pytest", "tkinter", "eval", "tests"],
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="clasp-backend", console=True)
COLLECT(exe, analysis.binaries, analysis.datas, name="clasp-backend")
