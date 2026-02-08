import sys
from pathlib import Path

DB_TBL_NAME = "PLEASE SPECIFY"
WIDGET_ROOT = Path(__file__).resolve().parent
SCRIPTS_DIR = WIDGET_ROOT / "scripts"
SIYUAN_DATA_DIR = WIDGET_ROOT.parents[2]   # .../SiYuan/data
SCRIPT_FOLDER = Path(__file__).resolve().parent
PORTFOLIO_SCRIPT = SCRIPT_FOLDER / "portfolio_exposure.py"
VISUALIZER_SCRIPT = SCRIPT_FOLDER / "risk_visualizer.py"
OUTPUT_DIR = SIYUAN_DATA_DIR / "storage" / "petal" / "portfolio-importer"
SIYUAN_ASSETS_DIR = SIYUAN_DATA_DIR / "assets"

SIYUAN_JSON = SIYUAN_DATA_DIR / "storage" / "av" / f"{DB_TBL_NAME}.json"
UNIFIED_HISTORY = OUTPUT_DIR / "portfolio_history_unified.csv"
NEWS_HISTORY = OUTPUT_DIR / "portfolio_news_history.csv"
CHART_HTML = OUTPUT_DIR / "portfolio_sectors_unified.html"
PYTHON_PATH = sys.executable
