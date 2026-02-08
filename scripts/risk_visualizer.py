#!/usr/bin/env python3
"""
Portfolio Visualizer for Unified History Format
Works with portfolio_history_unified.csv that includes ETF look-through
"""

import pandas as pd
import json
from datetime import datetime
from configs import OUTPUT_DIR
from pathlib import Path
import sys
from configs import UNIFIED_HISTORY, CHART_HTML, NEWS_HISTORY

# Ensure default recursion limit is high enough for complex HTML generation
sys.setrecursionlimit(2000)


def load_unified_history(csv_path):
    """Load unified portfolio history"""
    df = pd.read_csv(csv_path)
    df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d')
    return df


def generate_interactive_html(csv_path, output_path='portfolio_multicurrency.html', base_currency='CAD'):
    """
    Generate interactive HTML with currency toggle

    Args:
        csv_path: Path to portfolio_history_unified.csv
        output_path: Output HTML file path
        base_currency: Base currency for conversion (default: CAD)
    """
    # Load main data
    try:
        df = load_unified_history(csv_path)
    except FileNotFoundError:
        print(f"❌ Error: File not found at {csv_path}")
        return

    # Load news data
    news_path = NEWS_HISTORY
    news_df = None

    if news_path.exists():
        try:
            news_df = pd.read_csv(news_path, sep="|", encoding='utf-8-sig')
            news_df['Date'] = pd.to_datetime(news_df['Date'])
            print(f"✓ Loaded news data from {news_path}")
        except Exception as e:
            print(f"⚠️ Could not load news data: {e}")

    # Get unique dates
    dates = sorted(df['Date'].unique())
    date_strings = [d.strftime('%Y-%m-%d') for d in dates]

    # Get all currencies present in the portfolio
    all_currencies = sorted(df['Currency'].dropna().unique().tolist())

    # Prepare data for each date
    data_by_date = []

    for date in dates:
        date_data = df[df['Date'] == date]

        # Get news for this date
        news_for_date = {}
        if news_df is not None:
            date_news = news_df[news_df['Date'] == date]
            for _, news_row in date_news.iterrows():
                ticker = news_row['ticker']
                news_for_date[ticker] = {
                    'has_news': bool(news_row.get('news_1_title')),
                    'news_link': news_row.get('news_1_link', None),
                    'thesis': news_row.get('thesis', '')
                }

        # ====================================
        # BASE CURRENCY VIEW (CAD)
        # ====================================
        sector_totals_base = date_data.groupby('Sector')['Value_BaseCcy'].sum().reset_index()
        sector_totals_base = sector_totals_base.sort_values('Value_BaseCcy', ascending=False)

        risk_totals_base = date_data.groupby('RiskCategory')['Value_BaseCcy'].sum().reset_index()
        risk_totals_base = risk_totals_base.sort_values('Value_BaseCcy', ascending=False)

        # ====================================
        # ORIGINAL CURRENCY VIEW
        # ====================================
        sector_totals_orig = date_data.groupby('Sector')['Value'].sum().reset_index()
        sector_totals_orig = sector_totals_orig.sort_values('Value', ascending=False)

        risk_totals_orig = date_data.groupby('RiskCategory')['Value'].sum().reset_index()
        risk_totals_orig = risk_totals_orig.sort_values('Value', ascending=False)

        # Currency breakdown
        currency_totals = date_data.groupby('Currency').agg({
            'Value': 'sum',
            'Value_BaseCcy': 'sum'
        }).reset_index()

        # ====================================
        # AGGREGATED POSITIONS
        # ====================================
        aggregated_positions = date_data.groupby('Symbol').agg({
            'Value': 'sum',
            'Value_BaseCcy': 'sum',
            'Shares': 'first',
            'Price': 'first',
            'BookCost': 'first',
            'BookCost_BaseCcy': 'first',
            'CostBasis': 'sum',
            'CostBasis_BaseCcy': 'sum',
            'UnrealizedPL': 'sum',
            'UnrealizedPL_BaseCcy': 'sum',
            'UnrealizedPL_Pct': 'first',
            'TotalDividends': 'sum',
            'TotalDividends_BaseCcy': 'sum',
            'FX_PnL': 'sum',
            'Currency': 'first',
            'CurrentFX': 'first',
            'AvgFX': 'first',
            'Source': 'first',
            'EarningsDate': 'first'
        }).reset_index().sort_values('Value_BaseCcy', ascending=False)

        positions_list = []
        for _, row in aggregated_positions.iterrows():
            ticker = row['Symbol']
            news_info = news_for_date.get(ticker, {'has_news': False, 'news_link': None, 'thesis': ''})

            positions_list.append({
                'symbol': ticker,
                'value': float(row['Value']),
                'value_base': float(row['Value_BaseCcy']),
                'shares': float(row['Shares']),
                'price': float(row['Price']),
                'bookCost': float(row['BookCost']) if pd.notna(row['BookCost']) else 0,
                'bookCost_base': float(row['BookCost_BaseCcy']) if pd.notna(row['BookCost_BaseCcy']) else 0,
                'costBasis': float(row['CostBasis']) if pd.notna(row['CostBasis']) else 0,
                'costBasis_base': float(row['CostBasis_BaseCcy']) if pd.notna(row['CostBasis_BaseCcy']) else 0,
                'unrealizedPL': float(row['UnrealizedPL']) if pd.notna(row['UnrealizedPL']) else 0,
                'unrealizedPL_base': float(row['UnrealizedPL_BaseCcy']) if pd.notna(row['UnrealizedPL_BaseCcy']) else 0,
                'unrealizedPL_Pct': float(row['UnrealizedPL_Pct']) if pd.notna(row['UnrealizedPL_Pct']) else 0,
                'totalDividends': float(row['TotalDividends']) if pd.notna(row['TotalDividends']) else 0,
                'totalDividends_base': float(row['TotalDividends_BaseCcy']) if pd.notna(
                    row['TotalDividends_BaseCcy']) else 0,
                'fx_pnl': float(row['FX_PnL']) if pd.notna(row['FX_PnL']) else 0,
                'currency': row['Currency'],
                'current_fx': float(row['CurrentFX']) if pd.notna(row['CurrentFX']) else 1.0,
                'avg_fx': float(row['AvgFX']) if pd.notna(row['AvgFX']) else 1.0,
                'source': row['Source'],
                'earningsDate': str(row['EarningsDate']) if pd.notna(row['EarningsDate']) else None,
                'hasNews': news_info['has_news'],
                'newsLink': news_info['news_link'],
                'thesis': news_info['thesis']
            })

        # ====================================
        # BREAKDOWN DATA (for drill-down)
        # ====================================
        # Sector breakdown
        sector_breakdown_base = {}
        sector_breakdown_orig = {}

        for sector in sector_totals_base['Sector']:
            sector_data = date_data[date_data['Sector'] == sector]
            sector_value_base = sector_totals_base[sector_totals_base['Sector'] == sector]['Value_BaseCcy'].iloc[0]
            sector_value_orig = sector_totals_orig[sector_totals_orig['Sector'] == sector]['Value'].iloc[0]

            symbol_contributions_base = sector_data.groupby('Symbol')['Value_BaseCcy'].sum().reset_index()
            symbol_contributions_base = symbol_contributions_base.sort_values('Value_BaseCcy', ascending=False)

            symbol_contributions_orig = sector_data.groupby('Symbol')['Value'].sum().reset_index()
            symbol_contributions_orig = symbol_contributions_orig.sort_values('Value', ascending=False)

            breakdown_list_base = []
            breakdown_list_orig = []

            for _, sym_row in symbol_contributions_base.iterrows():
                ticker = sym_row['Symbol']
                sym_value_base = float(sym_row['Value_BaseCcy'])
                contribution_pct_base = (sym_value_base / sector_value_base * 100) if sector_value_base > 0 else 0

                sym_value_orig = float(
                    symbol_contributions_orig[symbol_contributions_orig['Symbol'] == ticker]['Value'].iloc[0])
                contribution_pct_orig = (sym_value_orig / sector_value_orig * 100) if sector_value_orig > 0 else 0

                breakdown_list_base.append({
                    'symbol': ticker,
                    'value': sym_value_base,
                    'contribution': contribution_pct_base,
                    'source': 'ETF' if date_data[(date_data['Sector'] == sector) &
                                                 (date_data['Symbol'] == ticker)]['Source'].iloc[0].startswith(
                        'ETF') else 'Stock'
                })

                breakdown_list_orig.append({
                    'symbol': ticker,
                    'value': sym_value_orig,
                    'contribution': contribution_pct_orig,
                    'source': 'ETF' if date_data[(date_data['Sector'] == sector) &
                                                 (date_data['Symbol'] == ticker)]['Source'].iloc[0].startswith(
                        'ETF') else 'Stock'
                })

            sector_breakdown_base[sector] = breakdown_list_base
            sector_breakdown_orig[sector] = breakdown_list_orig

        # Risk category breakdown
        risk_breakdown_base = {}
        risk_breakdown_orig = {}

        for risk_cat in risk_totals_base['RiskCategory']:
            risk_data = date_data[date_data['RiskCategory'] == risk_cat]
            risk_value_base = risk_totals_base[risk_totals_base['RiskCategory'] == risk_cat]['Value_BaseCcy'].iloc[0]
            risk_value_orig = risk_totals_orig[risk_totals_orig['RiskCategory'] == risk_cat]['Value'].iloc[0]

            symbol_contributions_base = risk_data.groupby('Symbol')['Value_BaseCcy'].sum().reset_index()
            symbol_contributions_base = symbol_contributions_base.sort_values('Value_BaseCcy', ascending=False)

            symbol_contributions_orig = risk_data.groupby('Symbol')['Value'].sum().reset_index()
            symbol_contributions_orig = symbol_contributions_orig.sort_values('Value', ascending=False)

            breakdown_list_base = []
            breakdown_list_orig = []

            for _, sym_row in symbol_contributions_base.iterrows():
                ticker = sym_row['Symbol']
                sym_value_base = float(sym_row['Value_BaseCcy'])
                contribution_pct_base = (sym_value_base / risk_value_base * 100) if risk_value_base > 0 else 0

                sym_value_orig = float(
                    symbol_contributions_orig[symbol_contributions_orig['Symbol'] == ticker]['Value'].iloc[0])
                contribution_pct_orig = (sym_value_orig / risk_value_orig * 100) if risk_value_orig > 0 else 0

                breakdown_list_base.append({
                    'symbol': ticker,
                    'value': sym_value_base,
                    'contribution': contribution_pct_base,
                    'source': 'ETF' if date_data[(date_data['RiskCategory'] == risk_cat) &
                                                 (date_data['Symbol'] == ticker)]['Source'].iloc[0].startswith(
                        'ETF') else 'Stock'
                })

                breakdown_list_orig.append({
                    'symbol': ticker,
                    'value': sym_value_orig,
                    'contribution': contribution_pct_orig,
                    'source': 'ETF' if date_data[(date_data['RiskCategory'] == risk_cat) &
                                                 (date_data['Symbol'] == ticker)]['Source'].iloc[0].startswith(
                        'ETF') else 'Stock'
                })

            risk_breakdown_base[risk_cat] = breakdown_list_base
            risk_breakdown_orig[risk_cat] = breakdown_list_orig

        data_by_date.append({
            'date': date.strftime('%Y-%m-%d'),
            # Base currency data
            'sectors_base': sector_totals_base['Sector'].tolist(),
            'values_base': sector_totals_base['Value_BaseCcy'].tolist(),
            'risk_categories_base': risk_totals_base['RiskCategory'].tolist(),
            'risk_values_base': risk_totals_base['Value_BaseCcy'].tolist(),
            'sector_breakdown_base': sector_breakdown_base,
            'risk_breakdown_base': risk_breakdown_base,
            # Original currency data
            'sectors_orig': sector_totals_orig['Sector'].tolist(),
            'values_orig': sector_totals_orig['Value'].tolist(),
            'risk_categories_orig': risk_totals_orig['RiskCategory'].tolist(),
            'risk_values_orig': risk_totals_orig['Value'].tolist(),
            'sector_breakdown_orig': sector_breakdown_orig,
            'risk_breakdown_orig': risk_breakdown_orig,
            # Currency breakdown
            'currencies': currency_totals['Currency'].tolist(),
            'currency_values_orig': currency_totals['Value'].tolist(),
            'currency_values_base': currency_totals['Value_BaseCcy'].tolist(),
            # Positions
            'positions': positions_list
        })

    # Generate color palettes
    colors = [
        '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
        '#FF9F40', '#E7E9ED', '#8E5EA2', '#3CBA9F', '#C9CBCF'
    ]

    risk_colors = {
        'Equity': '#FF6384',
        'Fixed Income': '#36A2EB',
        'Cash': '#FFCE56',
        'Alternative': '#4BC0C0',
        'Hybrid': '#9966FF',
        'Real Estate': '#FF9F40'
    }

    # Currency symbols
    currency_symbols = {
        'CAD': 'C$',
        'USD': '$',
        'EUR': '€',
        'GBP': '£',
        'JPY': '¥',
        'CNY': '¥',
        'CHF': 'Fr'
    }

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Multi-Currency Portfolio Analysis</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 30px;
        }}

        h1 {{
            text-align: center;
            color: #2d3748;
            margin-bottom: 10px;
            font-size: 2.5em;
            font-weight: 700;
        }}

        .subtitle {{
            text-align: center;
            color: #718096;
            margin-bottom: 30px;
            font-size: 1.1em;
        }}

        .currency-toggle {{
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-bottom: 20px;
        }}

        .toggle-btn {{
            padding: 12px 30px;
            border: 2px solid #667eea;
            background: white;
            color: #667eea;
            border-radius: 25px;
            cursor: pointer;
            font-weight: 600;
            font-size: 16px;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .toggle-btn.active {{
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }}

        .toggle-btn:hover:not(.active) {{
            background: #f7fafc;
        }}

        .info-banner {{
            background: #e6f7ff;
            border: 1px solid #91d5ff;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            color: #0050b3;
        }}

        .controls {{
            margin-bottom: 30px;
        }}

        .slider-container {{
            background: #f7fafc;
            padding: 20px;
            border-radius: 12px;
            border: 2px solid #e2e8f0;
        }}

        .slider-label {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-weight: 600;
            color: #2d3748;
        }}

        .current-date {{
            font-size: 1.2em;
            color: #667eea;
        }}

        .date-range {{
            color: #718096;
            font-size: 0.9em;
        }}

        input[type="range"] {{
            width: 100%;
            height: 8px;
            border-radius: 5px;
            background: #e2e8f0;
            outline: none;
            -webkit-appearance: none;
        }}

        input[type="range"]::-webkit-slider-thumb {{
            -webkit-appearance: none;
            appearance: none;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #667eea;
            cursor: pointer;
        }}

        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}

        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            border-radius: 12px;
            color: white;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            min-height: 100px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}

        .stat-label {{
            font-size: 0.85em;
            opacity: 0.9;
            margin-bottom: 5px;
        }}

        .stat-value {{
            font-size: 1.8em;
            font-weight: 700;
            line-height: 1.2;
        }}

        .chart-row {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 40px;
        }}

        .chart-container {{
            position: relative;
            height: 400px;
            cursor: pointer;
        }}

        .chart-hint {{
            text-align: center;
            color: #718096;
            font-size: 0.9em;
            margin-top: 10px;
            font-style: italic;
        }}

        .details {{
            margin-top: 40px;
        }}

        .details h3 {{
            color: #2d3748;
            margin-bottom: 20px;
            font-size: 1.5em;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .view-toggle {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }}

        .position-grid {{
            display: grid;
            gap: 12px;
        }}

        .position-item {{
            display: grid;
            grid-template-columns: 200px 1fr auto auto;
            gap: 15px;
            padding: 15px;
            background: #f7fafc;
            border-radius: 8px;
            align-items: center;
            transition: all 0.2s;
            border: 2px solid transparent;
        }}

        .position-item:hover {{
            background: #edf2f7;
            border-color: #667eea;
            transform: translateX(5px);
        }}

        .position-symbol {{
            font-weight: 700;
            font-size: 1.1em;
            color: #2d3748;
        }}

        .position-badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            margin-left: 8px;
        }}

        .badge-stock {{
            background: #bee3f8;
            color: #2c5282;
        }}

        .badge-etf {{
            background: #feebc8;
            color: #7c2d12;
        }}

        .currency-badge {{
            background: #fbb6ce;
            color: #702459;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            margin-left: 8px;
        }}

        .earnings-badge {{
            background: #fff3cd;
            color: #856404;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            margin-left: 8px;
            cursor: help;
            position: relative;
        }}

        .earnings-badge:hover::after {{
            content: attr(data-date);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: #2d3748;
            color: white;
            padding: 6px 12px;
            border-radius: 6px;
            white-space: nowrap;
            font-size: 1em;
            margin-bottom: 8px;
            z-index: 1000;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}

        .earnings-badge:hover::before {{
            content: '';
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            border: 6px solid transparent;
            border-top-color: #2d3748;
            margin-bottom: 2px;
        }}

        .news-icon {{
            background: #d1ecf1;
            color: #0c5460;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            margin-left: 8px;
            text-decoration: none;
            display: inline-block;
        }}

        .position-details {{
            display: flex;
            flex-direction: column;
            gap: 4px;
            color: #4a5568;
            font-size: 0.9em;
        }}

        .position-value {{
            font-weight: 700;
            font-size: 1.1em;
            color: #2d3748;
        }}

        .position-percent {{
            color: #667eea;
            font-weight: 600;
        }}

        .pl-positive {{
            color: #22c55e;
        }}

        .pl-negative {{
            color: #ef4444;
        }}

        .fx-pnl {{
            font-size: 0.85em;
            font-style: italic;
        }}

        .fx-positive {{
            color: #10b981;
        }}

        .fx-negative {{
            color: #f97316;
        }}

        @media (max-width: 768px) {{
            .chart-row {{
                grid-template-columns: 1fr;
            }}

            .position-item {{
                grid-template-columns: 1fr;
                gap: 8px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Multi-Currency Portfolio</h1>
        <p class="subtitle">Toggle between {base_currency} and original currencies</p>

        <div class="currency-toggle">
            <button class="toggle-btn active" id="baseCcyBtn" onclick="toggleCurrency('base')">
                <span>🏠</span> {base_currency} (Home Currency)
            </button>
            <button class="toggle-btn" id="multiCcyBtn" onclick="toggleCurrency('multi')">
                <span>🌍</span> Multi-Currency View
            </button>
        </div>

        <div class="info-banner">
            ℹ️ <strong>Currency Mode:</strong> <span id="currencyModeInfo">{base_currency} view shows all positions converted to {base_currency}. Switch to Multi-Currency to see original values with FX rates.</span>
        </div>

        <div class="controls">
            <div class="slider-container">
                <div class="slider-label">
                    <span class="current-date" id="currentDate">Loading...</span>
                    <span class="date-range" id="dateRange"></span>
                </div>
                <input type="range" id="dateSlider" min="0" max="{len(date_strings) - 1}" value="{len(date_strings) - 1}" step="1">
            </div>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">Total Portfolio Value</div>
                <div class="stat-value" id="totalValue">$0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Unrealized P&L</div>
                <div class="stat-value" id="unrealizedPL">$0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Dividends</div>
                <div class="stat-value" id="totalDividends" style="color: #fff;">$0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">FX Gain/Loss</div>
                <div class="stat-value" id="fxPnL">$0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Number of Sectors</div>
                <div class="stat-value" id="sectorCount">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Largest Sector</div>
                <div class="stat-value" id="largestSector">-</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Number of Positions</div>
                <div class="stat-value" id="positionCount">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Top Risk Category</div>
                <div class="stat-value" id="topRisk">-</div>
            </div>
        </div>

        <div class="chart-row">
            <div>
                <div class="chart-container">
                    <canvas id="sectorChart"></canvas>
                </div>
                <div class="chart-hint">💡 Click a segment to see contributing positions</div>
            </div>
            <div>
                <div class="chart-container">
                    <canvas id="riskChart"></canvas>
                </div>
                <div class="chart-hint">💡 Click a segment to see contributing positions</div>
            </div>
        </div>

        <div class="details">
            <h3 id="detailsTitle">📋 All Positions</h3>
            <div id="detailsContent"></div>
        </div>
    </div>

    <script>
        const portfolioData = {json.dumps(data_by_date, indent=4)};
        const baseCurrency = '{base_currency}';
        const currencySymbols = {json.dumps(currency_symbols)};

        let sectorChart;
        let riskChart;
        const sectorCtx = document.getElementById('sectorChart').getContext('2d');
        const riskCtx = document.getElementById('riskChart').getContext('2d');

        const colors = {json.dumps(colors)};
        const riskColors = {json.dumps(risk_colors)};

        let currentData = null;
        let currentTotal = 0;
        let currencyMode = 'base';  // 'base' or 'multi'

        function getCurrencySymbol(currency) {{
            return currencySymbols[currency] || currency + ' ';
        }}

        function formatCurrency(value, currency = null) {{
            const absValue = Math.abs(value);

            if (currencyMode === 'base' || !currency) {{
                return getCurrencySymbol(baseCurrency) + absValue.toLocaleString('en-US', {{
                    minimumFractionDigits: 0,
                    maximumFractionDigits: 0
                }});
            }} else {{
                return getCurrencySymbol(currency) + absValue.toLocaleString('en-US', {{
                    minimumFractionDigits: 0,
                    maximumFractionDigits: 0
                }});
            }}
        }}

        function toggleCurrency(mode) {{
            currencyMode = mode;

            // Update button states
            document.getElementById('baseCcyBtn').classList.toggle('active', mode === 'base');
            document.getElementById('multiCcyBtn').classList.toggle('active', mode === 'multi');

            // Update info text
            const infoText = mode === 'base' 
                ? `${{baseCurrency}} view shows all positions converted to ${{baseCurrency}} for easy comparison.`
                : `Multi-Currency view groups positions by currency with subtotals. Charts still use ${{baseCurrency}} for allocation percentages.`;
            document.getElementById('currencyModeInfo').textContent = infoText;

            // Refresh current view
            const slider = document.getElementById('dateSlider');
            updateChart(parseInt(slider.value));
        }}

        function updateChart(dateIndex) {{
            const data = portfolioData[dateIndex];
            currentData = data;

            // Select data based on currency mode
            const sectors = currencyMode === 'base' ? data.sectors_base : data.sectors_orig;
            const values = currencyMode === 'base' ? data.values_base : data.values_orig;
            const riskCategories = currencyMode === 'base' ? data.risk_categories_base : data.risk_categories_orig;
            const riskValues = currencyMode === 'base' ? data.risk_values_base : data.risk_values_orig;

            const total = values.reduce((a, b) => a + b, 0);
            currentTotal = total;

            document.getElementById('currentDate').textContent = data.date;

            // Calculate stats
            let totalPL = 0;
            let totalDividends = 0;
            let totalFxPnL = 0;

            if (currencyMode === 'base') {{
                // CAD mode: Single totals
                data.positions.forEach(pos => {{
                    totalPL += pos.unrealizedPL_base || 0;
                    totalDividends += pos.totalDividends_base || 0;
                    totalFxPnL += pos.fx_pnl || 0;
                }});

                document.getElementById('totalValue').innerHTML = formatCurrency(total);

                const plElement = document.getElementById('unrealizedPL');
                const plSign = totalPL < 0 ? '-' : '';
                plElement.innerHTML = `${{plSign}}${{formatCurrency(Math.abs(totalPL))}}`;
                plElement.style.color = totalPL >= 0 ? '#4ade80' : '#f87171';

                document.getElementById('totalDividends').innerHTML = formatCurrency(totalDividends);

                const fxElement = document.getElementById('fxPnL');
                const fxSign = totalFxPnL < 0 ? '-' : '';
                fxElement.innerHTML = `${{fxSign}}${{formatCurrency(Math.abs(totalFxPnL))}}`;
                fxElement.style.color = totalFxPnL >= 0 ? '#4ade80' : '#f87171';
            }} else {{
                // Multi-currency mode: Show breakdown by currency
                const statsByCurrency = {{}};

                data.positions.forEach(pos => {{
                    if (!statsByCurrency[pos.currency]) {{
                        statsByCurrency[pos.currency] = {{
                            value: 0,
                            value_base: 0,
                            pl: 0,
                            pl_base: 0,
                            dividends: 0,
                            dividends_base: 0,
                            fx_pnl: 0
                        }};
                    }}
                    statsByCurrency[pos.currency].value += pos.value || 0;
                    statsByCurrency[pos.currency].value_base += pos.value_base || 0;
                    statsByCurrency[pos.currency].pl += pos.unrealizedPL || 0;
                    statsByCurrency[pos.currency].pl_base += pos.unrealizedPL_base || 0;
                    statsByCurrency[pos.currency].dividends += pos.totalDividends || 0;
                    statsByCurrency[pos.currency].dividends_base += pos.totalDividends_base || 0;
                    statsByCurrency[pos.currency].fx_pnl += pos.fx_pnl || 0;
                }});

                // Sort currencies (CAD first)
                const currencies = Object.keys(statsByCurrency).sort((a, b) => {{
                    if (a === baseCurrency) return -1;
                    if (b === baseCurrency) return 1;
                    return a.localeCompare(b);
                }});

                // Dynamic font size adjustment to ensure fit
                // If more than 2 currencies, reduce size slightly
                const baseFontSize = currencies.length > 2 ? '1.1em' : '1.3em';

                // Build multi-line display for Total Value
                let totalValueHtml = '';
                currencies.forEach((currency) => {{
                    const stats = statsByCurrency[currency];
                    // Uniform styling for all currencies
                    totalValueHtml += `<div style="font-size: ${{baseFontSize}};">${{formatCurrency(stats.value, currency)}}</div>`;
                }});
                document.getElementById('totalValue').innerHTML = totalValueHtml;

                // Build multi-line display for Unrealized P&L
                let plHtml = '';
                totalPL = 0;

                // Use base currency PnL when in base mode, original currency PnL when in original mode
                if (currencyMode === 'base') {{
                    // In base currency mode, sum all the base PnL values
                    currencies.forEach((currency) => {{
                        const stats = statsByCurrency[currency];
                        totalPL += stats.pl_base;
                    }});

                    // Display single total in base currency
                    const plClass = totalPL >= 0 ? 'color: #4ade80;' : 'color: #f87171;';
                    const plSign = totalPL < 0 ? '-' : '';
                    plHtml = `<div style="font-size: ${{baseFontSize}}; ${{plClass}}">${{plSign}}${{formatCurrency(Math.abs(totalPL), baseCurrency)}}</div>`;
                }} else {{
                    // In original currency mode, show PnL per currency
                    currencies.forEach((currency) => {{
                        const stats = statsByCurrency[currency];
                        totalPL += stats.pl;

                        const plClass = stats.pl >= 0 ? 'color: #4ade80;' : 'color: #f87171;';
                        const plSign = stats.pl < 0 ? '-' : '';

                        plHtml += `<div style="font-size: ${{baseFontSize}}; ${{plClass}}">${{plSign}}${{formatCurrency(Math.abs(stats.pl), currency)}}</div>`;
                    }});
                }}
                document.getElementById('unrealizedPL').innerHTML = plHtml;

                // Build multi-line display for Dividends
                let divHtml = '';
                totalDividends = 0;
                currencies.forEach((currency) => {{
                    const stats = statsByCurrency[currency];
                    totalDividends += stats.dividends_base;
                    divHtml += `<div style="font-size: ${{baseFontSize}};">${{formatCurrency(stats.dividends, currency)}}</div>`;
                }});
                document.getElementById('totalDividends').innerHTML = divHtml;

                // FX P&L (always in CAD, so single value)
                currencies.forEach(currency => {{
                    totalFxPnL += statsByCurrency[currency].fx_pnl;
                }});

                const fxElement = document.getElementById('fxPnL');
                const fxSign = totalFxPnL < 0 ? '-' : '';
                fxElement.innerHTML = `${{fxSign}}${{formatCurrency(Math.abs(totalFxPnL))}}`;
                fxElement.style.color = totalFxPnL >= 0 ? '#4ade80' : '#f87171';
            }}

            document.getElementById('sectorCount').textContent = sectors.length;
            document.getElementById('largestSector').textContent = sectors[0];
            document.getElementById('positionCount').textContent = data.positions.length;
            document.getElementById('topRisk').textContent = riskCategories[0] || '-';

            // Update or create sector chart
            if (sectorChart) {{
                sectorChart.data.labels = sectors;
                sectorChart.data.datasets[0].data = values;
                sectorChart.update('none');
            }} else {{
                sectorChart = new Chart(sectorCtx, {{
                    type: 'doughnut',
                    data: {{
                        labels: sectors,
                        datasets: [{{
                            data: values,
                            backgroundColor: colors,
                            borderWidth: 2,
                            borderColor: '#ffffff'
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        onClick: (event, elements) => {{
                            if (elements.length > 0) {{
                                const index = elements[0].index;
                                const sector = sectors[index];
                                showSectorBreakdown(sector);
                            }}
                        }},
                        plugins: {{
                            title: {{
                                display: true,
                                text: 'Sector Allocation',
                                font: {{ size: 16, weight: 'bold' }}
                            }},
                            legend: {{
                                position: 'bottom',
                                labels: {{
                                    padding: 15,
                                    font: {{ size: 12 }}
                                }}
                            }},
                            tooltip: {{
                                callbacks: {{
                                    label: function(context) {{
                                        const label = context.label || '';
                                        const value = context.parsed || 0;
                                        const percent = (value / total * 100).toFixed(1);
                                        return label + ': ' + formatCurrency(value) + ' (' + percent + '%)';
                                    }}
                                }}
                            }}
                        }}
                    }}
                }});
            }}

            // Update or create risk chart
            const riskChartColors = riskCategories.map(cat => riskColors[cat] || '#C9CBCF');

            if (riskChart) {{
                riskChart.data.labels = riskCategories;
                riskChart.data.datasets[0].data = riskValues;
                riskChart.data.datasets[0].backgroundColor = riskChartColors;
                riskChart.update('none');
            }} else {{
                riskChart = new Chart(riskCtx, {{
                    type: 'doughnut',
                    data: {{
                        labels: riskCategories,
                        datasets: [{{
                            data: riskValues,
                            backgroundColor: riskChartColors,
                            borderWidth: 2,
                            borderColor: '#ffffff'
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        onClick: (event, elements) => {{
                            if (elements.length > 0) {{
                                const index = elements[0].index;
                                const riskCat = riskCategories[index];
                                showRiskBreakdown(riskCat);
                            }}
                        }},
                        plugins: {{
                            title: {{
                                display: true,
                                text: 'Risk Category Allocation',
                                font: {{ size: 16, weight: 'bold' }}
                            }},
                            legend: {{
                                position: 'bottom',
                                labels: {{
                                    padding: 15,
                                    font: {{ size: 12 }}
                                }}
                            }},
                            tooltip: {{
                                callbacks: {{
                                    label: function(context) {{
                                        const label = context.label || '';
                                        const value = context.parsed || 0;
                                        const percent = (value / total * 100).toFixed(1);
                                        return label + ': ' + formatCurrency(value) + ' (' + percent + '%)';
                                    }}
                                }}
                            }}
                        }}
                    }}
                }});
            }}

            showAllPositions();
        }}

        function showAllPositions() {{
            if (!currentData) return;

            document.getElementById('detailsTitle').textContent = '📋 All Positions';

            const detailsDiv = document.getElementById('detailsContent');
            let html = '';

            if (currencyMode === 'base') {{
                // CAD mode: Show all positions in one list
                html += '<div class="position-grid">';

                currentData.positions.forEach(pos => {{
                    const value = pos.value_base;
                    const bookCost = pos.bookCost_base;
                    const dividends = pos.totalDividends_base;

                    const posPercent = (value / currentTotal * 100).toFixed(1);
                    const isETF = pos.source && pos.source.includes('ETF');
                    const sourceLabel = isETF ? 'ETF' : 'Stock';
                    const badgeClass = isETF ? 'badge-etf' : 'badge-stock';

                    const plClass = pos.unrealizedPL >= 0 ? 'pl-positive' : 'pl-negative';
                    const plSign = pos.unrealizedPL >= 0 ? '+' : '';

                    const fxClass = pos.fx_pnl >= 0 ? 'fx-positive' : 'fx-negative';
                    const fxSign = pos.fx_pnl >= 0 ? '+' : '';

                    const hasDividends = dividends > 0;
                    const dividendText = hasDividends ? ` | Div: ${{formatCurrency(dividends)}}` : '';

                    const fxPnlText = Math.abs(pos.fx_pnl) > 0.01
                        ? `<div class="fx-pnl ${{fxClass}}">FX P&L: ${{fxSign}}${{formatCurrency(Math.abs(pos.fx_pnl))}}</div>`
                        : '';

                    let badges = '';
                    if (pos.earningsDate) {{
                        badges += `<span class="earnings-badge" data-date="Next earnings: ${{pos.earningsDate}}">📅</span>`;
                    }}
                    if (pos.hasNews && pos.newsLink) {{
                        badges += `<a href="${{pos.newsLink}}" target="_blank" class="news-icon" title="View latest news">📰</a>`;
                    }}
                    if (pos.currency !== baseCurrency) {{
                        badges += `<span class="currency-badge">${{pos.currency}}</span>`;
                    }}

                    html += `
                        <div class="position-item">
                            <div>
                                <span class="position-symbol">${{pos.symbol}}</span>
                                <span class="position-badge ${{badgeClass}}">${{sourceLabel}}</span>
                                ${{badges}}
                            </div>
                            <div class="position-details">
                                <div>${{pos.shares.toFixed(2)}} shares @ ${{formatCurrency(pos.price, pos.currency)}}</div>
                                <div>Book: ${{formatCurrency(bookCost)}} | 
                                    <span class="${{plClass}}">${{plSign}}${{formatCurrency(Math.abs(pos.unrealizedPL), pos.currency)}} (${{plSign}}${{pos.unrealizedPL_Pct.toFixed(1)}}%)</span>
                                    ${{dividendText}}
                                </div>
                                ${{fxPnlText}}
                            </div>
                            <div class="position-value">${{formatCurrency(value)}}</div>
                            <div class="position-percent">${{posPercent}}%</div>
                        </div>
                    `;
                }});

                html += '</div>';
            }} else {{
                // Multi-currency mode: Group by currency
                const positionsByCurrency = {{}};

                currentData.positions.forEach(pos => {{
                    if (!positionsByCurrency[pos.currency]) {{
                        positionsByCurrency[pos.currency] = [];
                    }}
                    positionsByCurrency[pos.currency].push(pos);
                }});

                // Sort currencies: CAD first, then alphabetically
                const currencies = Object.keys(positionsByCurrency).sort((a, b) => {{
                    if (a === baseCurrency) return -1;
                    if (b === baseCurrency) return 1;
                    return a.localeCompare(b);
                }});

                currencies.forEach(currency => {{
                    const positions = positionsByCurrency[currency];

                    // Calculate subtotal for this currency
                    const subtotal = positions.reduce((sum, pos) => sum + pos.value, 0);
                    const subtotalBase = positions.reduce((sum, pos) => sum + pos.value_base, 0);
                    const subtotalPercent = (subtotalBase / currentTotal * 100).toFixed(1);

                    // Currency group header
                    html += `
                        <div style="background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 15px 20px; border-radius: 8px; margin-top: 20px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <span style="font-size: 1.3em; font-weight: 700;">${{getCurrencySymbol(currency)}} ${{currency}} Holdings</span>
                                ${{currency !== baseCurrency ? `<span style="opacity: 0.9; margin-left: 15px; font-size: 0.9em;">@ ${{positions[0].current_fx.toFixed(4)}} ${{baseCurrency}}</span>` : ''}}
                            </div>
                            <div style="text-align: right;">
                                <div style="font-size: 1.4em; font-weight: 700;">${{formatCurrency(subtotal, currency)}}</div>
                                <div style="font-size: 0.9em; opacity: 0.9;">${{formatCurrency(subtotalBase, baseCurrency)}} · ${{subtotalPercent}}%</div>
                            </div>
                        </div>
                    `;

                    html += '<div class="position-grid">';

                    positions.forEach(pos => {{
                        const value = currencyMode === 'base' ? pos.value_base : pos.value;
                        const bookCost = currencyMode === 'base' ? pos.bookCost_base : pos.bookCost;
                        const dividends = currencyMode === 'base' ? pos.totalDividends_base : pos.totalDividends;
                        const displayCurrency = currencyMode === 'base' ? baseCurrency : currency;
                        const unrealizedPL = currencyMode === 'base' ? pos.unrealizedPL_base : pos.unrealizedPL;

                        const isETF = pos.source && pos.source.includes('ETF');
                        const sourceLabel = isETF ? 'ETF' : 'Stock';
                        const badgeClass = isETF ? 'badge-etf' : 'badge-stock';

                        const plClass = unrealizedPL >= 0 ? 'pl-positive' : 'pl-negative';
                        const plSign = unrealizedPL < 0 ? '-' : '';

                        const fxClass = pos.fx_pnl >= 0 ? 'fx-positive' : 'fx-negative';
                        const fxSign = pos.fx_pnl < 0 ? '-' : '';

                        const hasDividends = dividends > 0;
                        const dividendText = hasDividends ? ` | Div: ${{formatCurrency(dividends, displayCurrency)}}` : '';

                        const fxInfo = currency !== baseCurrency && currencyMode !== 'base'
                            ? ` | FX: ${{pos.current_fx.toFixed(4)}} (avg: ${{pos.avg_fx.toFixed(4)}})`
                            : '';

                        const fxPnlText = Math.abs(pos.fx_pnl) > 0.01 && currencyMode !== 'base'
                            ? `<div class="fx-pnl ${{fxClass}}">FX P&L: ${{fxSign}}${{formatCurrency(Math.abs(pos.fx_pnl), baseCurrency)}}</div>`
                            : '';

                        let badges = '';
                        if (pos.earningsDate) {{
                            badges += `<span class="earnings-badge" data-date="Next earnings: ${{pos.earningsDate}}">📅</span>`;
                        }}
                        if (pos.hasNews && pos.newsLink) {{
                            badges += `<a href="${{pos.newsLink}}" target="_blank" class="news-icon" title="View latest news">📰</a>`;
                        }}

                        html += `
                            <div class="position-item">
                                <div>
                                    <span class="position-symbol">${{pos.symbol}}</span>
                                    <span class="position-badge ${{badgeClass}}">${{sourceLabel}}</span>
                                    ${{badges}}
                                </div>
                                <div class="position-details">
                                    <div>${{pos.shares.toFixed(2)}} shares @ ${{formatCurrency(pos.price, currency)}}</div>
                                    <div>Book: ${{formatCurrency(bookCost, displayCurrency)}} | 
                                        <span class="${{plClass}}">${{plSign}}${{formatCurrency(Math.abs(unrealizedPL), displayCurrency)}} (${{plSign}}${{pos.unrealizedPL_Pct.toFixed(1)}}%)</span>
                                        ${{dividendText}}${{fxInfo}}
                                    </div>
                                    ${{fxPnlText}}
                                </div>
                                <div class="position-value">${{formatCurrency(value, displayCurrency)}}</div>
                                <div class="position-percent" style="color: #718096; font-size: 0.85em;">${{formatCurrency(pos.value_base, baseCurrency)}}</div>
                            </div>
                        `;
                    }});

                    html += '</div>';
                }});

                // Grand total in CAD (for reference)
                html += `
                    <div style="background: #f7fafc; padding: 15px 20px; border-radius: 8px; margin-top: 20px; display: flex; justify-content: space-between; align-items: center; border: 2px solid #667eea;">
                        <div style="font-size: 1.1em; font-weight: 600; color: #2d3748;">Total Portfolio (in ${{baseCurrency}})</div>
                        <div style="font-size: 1.5em; font-weight: 700; color: #667eea;">${{formatCurrency(currentTotal, baseCurrency)}}</div>
                    </div>
                `;
            }}

            detailsDiv.innerHTML = html;
        }}

        function showSectorBreakdown(sector) {{
            if (!currentData) return;

            document.getElementById('detailsTitle').textContent = `🔍 Sector: ${{sector}}`;

            const breakdown = currencyMode === 'base' 
                ? currentData.sector_breakdown_base[sector]
                : currentData.sector_breakdown_orig[sector];

            const sectorValue = currencyMode === 'base'
                ? currentData.values_base[currentData.sectors_base.indexOf(sector)]
                : currentData.values_orig[currentData.sectors_orig.indexOf(sector)];

            const detailsDiv = document.getElementById('detailsContent');
            let html = `
                <div style="background: #f7fafc; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                    <strong>${{sector}} - ${{formatCurrency(sectorValue)}}</strong>
                    <span style="color: #718096; font-size: 0.9em; margin-left: 15px;">Click "📋 All Positions" to return</span>
                    <button onclick="showAllPositions()" style="margin-left: 15px; padding: 6px 12px; border-radius: 6px; border: 1px solid #667eea; background: white; color: #667eea; cursor: pointer;">Back to All</button>
                </div>
                <div class="position-grid">
            `;

            breakdown.forEach(item => {{
                const isETF = item.source === 'ETF';
                const sourceLabel = isETF ? 'ETF Contribution' : 'Stock';
                const badgeClass = isETF ? 'badge-etf' : 'badge-stock';

                html += `
                    <div class="position-item">
                        <div>
                            <span class="position-symbol">${{item.symbol}}</span>
                            <span class="position-badge ${{badgeClass}}">${{sourceLabel}}</span>
                        </div>
                        <div class="position-details">
                            <div>${{isETF ? 'ETF sector allocation' : 'Direct holding'}}</div>
                        </div>
                        <div class="position-value">${{formatCurrency(item.value)}}</div>
                        <div class="position-percent">${{item.contribution.toFixed(1)}}%</div>
                    </div>
                `;
            }});

            html += '</div>';
            detailsDiv.innerHTML = html;
        }}

        function showRiskBreakdown(riskCat) {{
            if (!currentData) return;

            document.getElementById('detailsTitle').textContent = `🔍 Risk: ${{riskCat}}`;

            const breakdown = currencyMode === 'base'
                ? currentData.risk_breakdown_base[riskCat]
                : currentData.risk_breakdown_orig[riskCat];

            const riskValue = currencyMode === 'base'
                ? currentData.risk_values_base[currentData.risk_categories_base.indexOf(riskCat)]
                : currentData.risk_values_orig[currentData.risk_categories_orig.indexOf(riskCat)];

            const detailsDiv = document.getElementById('detailsContent');
            let html = `
                <div style="background: #f7fafc; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                    <strong>${{riskCat}} - ${{formatCurrency(riskValue)}}</strong>
                    <span style="color: #718096; font-size: 0.9em; margin-left: 15px;">Click "📋 All Positions" to return</span>
                    <button onclick="showAllPositions()" style="margin-left: 15px; padding: 6px 12px; border-radius: 6px; border: 1px solid #667eea; background: white; color: #667eea; cursor: pointer;">Back to All</button>
                </div>
                <div class="position-grid">
            `;

            breakdown.forEach(item => {{
                const isETF = item.source === 'ETF';
                const sourceLabel = isETF ? 'ETF Contribution' : 'Stock';
                const badgeClass = isETF ? 'badge-etf' : 'badge-stock';

                html += `
                    <div class="position-item">
                        <div>
                            <span class="position-symbol">${{item.symbol}}</span>
                            <span class="position-badge ${{badgeClass}}">${{sourceLabel}}</span>
                        </div>
                        <div class="position-details">
                            <div>${{isETF ? 'ETF risk allocation' : 'Direct holding'}}</div>
                        </div>
                        <div class="position-value">${{formatCurrency(item.value)}}</div>
                        <div class="position-percent">${{item.contribution.toFixed(1)}}%</div>
                    </div>
                `;
            }});

            html += '</div>';
            detailsDiv.innerHTML = html;
        }}

        const slider = document.getElementById('dateSlider');
        const dateRange = document.getElementById('dateRange');

        dateRange.textContent = `${{portfolioData[0].date}} - ${{portfolioData[portfolioData.length-1].date}}`;

        slider.addEventListener('input', (e) => {{
            updateChart(parseInt(e.target.value));
        }});

        // Initialize with latest date
        updateChart(portfolioData.length - 1);
    </script>
</body>
</html>
"""

    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n✅ Multi-currency HTML generated: {output_path}")
    print(f"   Base currency: {base_currency}")
    print(f"   Currencies detected: {', '.join(all_currencies)}")


if __name__ == '__main__':

    # output_file = sys.argv[1] if len(sys.argv) > 1 else f'{SIYUAN_FOLDER}//portfolio_sectors_unified.html'
    output_file = sys.argv[1] if len(sys.argv) > 1 else CHART_HTML
    generate_interactive_html(UNIFIED_HISTORY, output_file)
    print("\n✨ Visualization ready!")
    print(f"\n📂 Open in browser: {output_file}")
    print("📂 Or drag into Siyuan notes for interactive viewing")