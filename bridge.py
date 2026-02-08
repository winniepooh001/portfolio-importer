"""
Flask Bridge Server for Portfolio Importer Widget
Connects Siyuan widget to Python portfolio scripts
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import subprocess
import pandas as pd
import shutil
import os
from pathlib import Path
from datetime import datetime

from configs import PORTFOLIO_SCRIPT, VISUALIZER_SCRIPT, OUTPUT_DIR, SIYUAN_ASSETS_DIR, UNIFIED_HISTORY, NEWS_HISTORY, \
    CHART_HTML, PYTHON_PATH

app = Flask(__name__)
CORS(app)  # Allow cross-origin requests from Siyuan widget


# =========================
# ROUTE 1: Run Portfolio Update
# =========================


@app.route('/run-task', methods=['POST'])
def run_task():
    try:
        # Create a copy of the current environment and force UTF-8
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        print(f"📡 Attempting to run: {PORTFOLIO_SCRIPT}")

        # Ensure the output directory exists first
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # Use sys.executable to ensure we use the same python interpreter
        # We also set the 'cwd' (current working directory) to the script's folder
        result = subprocess.run(
            [PYTHON_PATH, PORTFOLIO_SCRIPT],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=os.path.dirname(PORTFOLIO_SCRIPT),
            env = env,  # <--- Add this
            encoding = 'utf-8'  # <--- Add this to ensure output is read as UTF-8
        )

        if result.returncode != 0:
            print(f"❌ Script Error Output: {result.stderr}")
            return jsonify({
                'status': 'error',
                'message': f'Python Script Error: {result.stderr}'
            }), 500

        summary = get_portfolio_summary()
        return jsonify({
            'status': 'success',
            'summary': summary
        })

    except Exception as e:
        print(f"❌ Server Exception: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# =========================
# ROUTE 2: Get Latest News
# =========================
@app.route('/get-latest-news', methods=['GET'])
def get_latest_news():
    try:
        print("Loading News")
        if not NEWS_HISTORY.exists():
            return jsonify({'status': 'error', 'message': 'News history file not found'}), 404

        # 1. Read with pipe delimiter
        # Note: If your file is still comma-separated, change sep to ','
        # or update your portfolio_exposure_unified.py to save with sep='|'
        news_df = pd.read_csv(NEWS_HISTORY, sep='|')

        # 2. IMPORTANT: Replace NaN with empty strings so JSON doesn't break
        news_df = news_df.fillna('')

        # Get latest date
        latest_date = news_df['Date'].max()
        latest_news = news_df[news_df['Date'] == latest_date]

        symbol_info = {}
        if UNIFIED_HISTORY.exists():
            print("Get Latest News Snapshot Date")
            # Apply same logic to unified history
            history_df = pd.read_csv(UNIFIED_HISTORY).fillna('')
            latest_portfolio = history_df[history_df['Date'] == latest_date]
            for ticker in latest_portfolio['Symbol'].unique():
                ticker_data = latest_portfolio[latest_portfolio['Symbol'] == ticker].iloc[0]
                symbol_info[ticker] = {
                    'sector': ticker_data.get('Sector', ''),
                    'earnings_date': ticker_data.get('EarningsDate', '')
                }

        print("Prepare News List")
        news_list = []
        for _, row in latest_news.iterrows():
            ticker = row['ticker']
            news_item = {
                'ticker': ticker,
                'symbol_info': symbol_info.get(ticker, {}),
                'thesis': row.get('thesis', '')  # Include thesis block ID
            }
            # Fill 5 news slots
            for i in range(1, 6):
                news_item[f'news_{i}_title'] = row.get(f'news_{i}_title', '')
                news_item[f'news_{i}_date'] = row.get(f'news_{i}_date', '')
                news_item[f'news_{i}_link'] = row.get(f'news_{i}_link', '')
            news_list.append(news_item)

        if len(news_list) == 0:
            print("There is no News")
        return jsonify({
            'status': 'success',
            'date': str(latest_date),
            'news': news_list
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# =========================
# ROUTE 3: Generate Chart
# =========================
import traceback  # Add this at the top


@app.route('/generate-chart', methods=['POST'])
def generate_chart():
    try:
        print(f"📊 Running visualizer: {VISUALIZER_SCRIPT}")

        # Ensure the environment is UTF-8
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"

        # Check if input file exists
        if not UNIFIED_HISTORY.exists():
            return jsonify({'status': 'error', 'message': f'Input CSV not found: {UNIFIED_HISTORY}'}), 404

        result = subprocess.run(
            [PYTHON_PATH, VISUALIZER_SCRIPT],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
            encoding='utf-8'
        )

        # If the script printed anything to stderr, we want to see it
        if result.returncode != 0:
            print(f"❌ Visualizer Stderr: {result.stderr}")
            print(f"❌ Visualizer Stdout: {result.stdout}")
            return jsonify({
                'status': 'error',
                'message': 'Visualizer Script Error',
                'details': result.stderr
            }), 500

        return jsonify({
            'status': 'success',
            'chart_path': str(CHART_HTML)
        })

    except Exception as e:
        # This prints the red error text in your Python terminal
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e),
            'traceback': traceback.format_exc()
        }), 500

# =========================
# ROUTE 4: Copy Chart to Siyuan Assets
# =========================
@app.route('/copy-chart-to-siyuan', methods=['POST'])
def copy_chart_to_siyuan():
    """
    将生成的图表复制到思源 assets 目录
    """
    try:
        data = request.get_json()
        chart_path = Path(data.get('chart_path'))
        
        if not chart_path.exists():
            return jsonify({
                'status': 'error',
                'message': 'Chart file not found'
            }), 404
        
        # Create assets directory if it doesn't exist
        SIYUAN_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        asset_filename = f'portfolio_chart_{timestamp}.html'
        asset_path = SIYUAN_ASSETS_DIR / asset_filename
        
        # Copy file
        shutil.copy2(chart_path, asset_path)
        
        print(f"✅ Chart copied to: {asset_path}")
        
        # Return relative path for use in Siyuan
        relative_path = f'assets/{asset_filename}'
        
        return jsonify({
            'status': 'success',
            'message': 'Chart copied to Siyuan assets',
            'asset_path': relative_path,
            'full_path': str(asset_path)
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


# =========================
# HELPER: Get Portfolio Summary
# =========================
def get_portfolio_summary():
    """
    从 unified history 获取最新投资组合摘要
    """
    try:
        if not UNIFIED_HISTORY.exists():
            return None
        
        df = pd.read_csv(UNIFIED_HISTORY)
        
        # Get latest date
        latest_date = df['Date'].max()
        latest_data = df[df['Date'] == latest_date]
        
        # Calculate summary
        total_value = latest_data['Value'].sum()
        total_pl = latest_data['UnrealizedPL'].sum()
        total_dividends = latest_data['TotalDividends'].sum()
        position_count = latest_data['Symbol'].nunique()
        
        return {
            'date': latest_date,
            'total_value': f'${total_value:,.2f}',
            'unrealized_pl': f'${total_pl:,.2f}',
            'total_dividends': f'${total_dividends:,.2f}',
            'position_count': position_count
        }
        
    except Exception as e:
        print(f"Error getting summary: {e}")
        return None


# =========================
# ROUTE 5: Health Check
# =========================
@app.route('/health', methods=['GET'])
def health_check():
    """
    健康检查端点
    """
    return jsonify({
        'status': 'ok',
        'message': 'Bridge server is running',
        'files': {
            'unified_history': UNIFIED_HISTORY.exists(),
            'news_history': NEWS_HISTORY.exists(),
            'chart_html': CHART_HTML.exists()
        }
    })


# =========================
# MAIN
# =========================
if __name__ == '__main__':
    print("="*70)
    print("Portfolio Importer Bridge Server")
    print("="*70)
    print(f"Portfolio script: {PORTFOLIO_SCRIPT}")
    print(f"Visualizer script: {VISUALIZER_SCRIPT}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Siyuan assets: {SIYUAN_ASSETS_DIR}")
    print("="*70)
    print("\n🚀 Starting server on http://127.0.0.1:5000")
    print("📡 Listening for widget requests...\n")
    
    app.run(host='127.0.0.1', port=5000, debug=True)
