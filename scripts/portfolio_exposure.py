import pandas as pd
import yfinance as yf
import feedparser
import os
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from pathlib import Path
import numpy as np
from enum import Enum
from typing import Tuple

# Import your existing parser
from Siyuan_parser import parse_siyuan_trades
from configs import OUTPUT_DIR, SIYUAN_JSON


# =========================
# Enums (Inherit from str to fix Col Errors)
# =========================
class StrEnum(str, Enum):
    def __str__(self) -> str:
        return str(self.value)

class PortfolioColumns(StrEnum):
    EVENT_TYPE = "Event Type"
    QUANTITY = "Quantity"
    EXCLUDE = "exclude"
    TICKER = "ticker"
    DATE = "Date"
    PRICE = "Price"
    BOOK_COST = "book_cost"
    COST_BASIS = "total_cost_basis"
    BOOK_COST_BASE = "book_cost_baseccy"
    COST_BASIS_BASE = "total_cost_basis_baseccy"
    DIVIDENDS = "dividends"
    DIVIDENDS_BASE = "dividends_baseccy"
    SHARES = "shares"
    VALUE = "value"
    VALUE_BASE = "value_baseccy"
    THESIS = "thesis"
    CCY = "CCY"
    CUR_FX = "current_fx_to_cad"
    AVG_FX = "avg_fx_to_cad"
    FX = "FX_COST"
    FX_PNL = "FX_PNL"
    PNL_BASE = "UnrealizedPL_baseccy"



class EventType(StrEnum):
    DIVIDEND = "Dividend"
    BUY = "Buy"
    SELL = "Sell"


# Helper for filtering
NORMAL_TRADE_TYPES = [EventType.BUY, EventType.SELL]


class YahooCols(StrEnum):
    TICKER = "ticker"
    DATE = "Date"
    SECTOR = "sector"
    INDUSTRY = "industry"
    COUNTRY = "country"
    QUOTE_TYPE = "quoteType"
    PRICE = "price"
    SHARES = "shares"
    VALUE = "value"
    BOOK_COST = "book_cost"
    COST_BASIS = "total_cost_basis"
    DIVIDENDS = "total_dividends"
    UNREALIZED_PL = "UnrealizedPL"
    PL_PCT = "UnrealizedPL_Pct"
    EARNINGS_DATE = "EarningsDate"

ASSET_RISK_MAPPING = {
    'Stock': 'Equity',
    'Equity': 'Equity',
    'Bond': 'Fixed Income',
    'Cash & Cash Equivalents': 'Cash',
    'Other': 'Alternative',
    'Preferred Stock': 'Hybrid',
    'Convertible': 'Hybrid',
    'Real Estate': 'Real Estate',
    "cashPosition": "Cash",
    "stockPosition": "Equity",
    "bondPosition": "Fixed Income",
    "preferredPosition": "Hybrid",
    "convertiblePosition": "Hybrid",
    "otherPosition": "Other"

}


# Constants
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SNAPSHOT_DATE = datetime.now().strftime("%Y-%m-%d")
SNAPSHOT_DATETIME = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# =========================
# Core Logic
# =========================
def build_aggregated_positions(trades: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    print("Building aggregated positions...")

    # Filter for Buy/Sell and exclude nulls
    trade_events = trades[
        trades[PortfolioColumns.EVENT_TYPE].isin(NORMAL_TRADE_TYPES) &
        trades[PortfolioColumns.EXCLUDE].isnull()
        ].copy()

    # Calculate signed quantities
    trade_events["signed_qty"] = np.where(
        trade_events[PortfolioColumns.EVENT_TYPE] == EventType.SELL,
        -trade_events[PortfolioColumns.QUANTITY],
        trade_events[PortfolioColumns.QUANTITY]
    )

    book_cost_data = []
    position_history = {}

    for ticker in trade_events[PortfolioColumns.TICKER].unique():
        ticker_trades = trade_events[trade_events[PortfolioColumns.TICKER] == ticker].sort_values(PortfolioColumns.DATE)

        total_shares = 0
        total_cost_raw = 0.0  # e.g., USD
        total_cost_fx = 0.0  # e.g., CAD (raw * fx)

        position_open_date = None
        current_thesis = ""
        position_closed_periods = []
        ccy = "CAD"

        for _, trade in ticker_trades.iterrows():
            qty = trade[PortfolioColumns.QUANTITY]
            price = trade.get(PortfolioColumns.PRICE, 0)
            fx_rate = trade.get(PortfolioColumns.FX, 1)  # Default to 1 if no FX provided
            ccy = trade.get(PortfolioColumns.CCY, "CAD")

            if trade[PortfolioColumns.EVENT_TYPE] == EventType.BUY:
                if total_shares == 0:
                    position_open_date = trade[PortfolioColumns.DATE]

                current_thesis = trade.get(PortfolioColumns.THESIS, "") or current_thesis
                # Add to both buckets
                trade_cost_raw = qty * price
                trade_cost_fx = qty * price * fx_rate

                total_cost_raw += trade_cost_raw
                total_cost_fx += trade_cost_fx
                total_shares += qty

            elif trade[PortfolioColumns.EVENT_TYPE] == EventType.SELL:
                if total_shares > 0:
                    # Determine what proportion of the "buckets" are being sold
                    # We use the weighted average cost for both
                    avg_cost_raw = total_cost_raw / total_shares
                    avg_cost_fx = total_cost_fx / total_shares

                    total_cost_raw -= (qty * avg_cost_raw)
                    total_cost_fx -= (qty * avg_cost_fx)
                    total_shares -= qty

                    if total_shares <= 0:
                        position_closed_periods.append({
                            'open_date': position_open_date,
                            'close_date': trade[PortfolioColumns.DATE]
                        })
                        position_open_date = None
                        current_thesis = ""
                        total_shares = 0
                        total_cost_raw = 0
                        total_cost_fx = 0

        is_open = total_shares > 0

        # Calculate Averages for the open position
        avg_book_cost_raw = (total_cost_raw / total_shares) if is_open else 0
        avg_book_cost_fx = (total_cost_fx / total_shares) if is_open else 0
        # The average FX rate is the ratio of the total CAD spent vs total USD spent
        avg_fx_rate = (total_cost_fx / total_cost_raw) if (is_open and total_cost_raw > 0) else 1.0

        position_history[ticker] = {
            'current_open_date': position_open_date,
            'closed_periods': position_closed_periods,
            'is_open': is_open
        }

        book_cost_data.append({
            PortfolioColumns.TICKER: ticker,
            # Costs in Raw Currency (e.g. USD)
            PortfolioColumns.BOOK_COST: avg_book_cost_raw,
            PortfolioColumns.COST_BASIS: total_cost_raw,
            # Costs in Base Currency (e.g. CAD)
            PortfolioColumns.BOOK_COST_BASE: avg_book_cost_fx,
            PortfolioColumns.COST_BASIS_BASE: total_cost_fx,
            # Average FX for the holding
            PortfolioColumns.AVG_FX: avg_fx_rate,
            PortfolioColumns.THESIS: current_thesis,
            PortfolioColumns.CCY: ccy
        })

    book_cost_df = pd.DataFrame(book_cost_data)

    # Aggregate shares
    positions = (
        trade_events.groupby(PortfolioColumns.TICKER, as_index=False)["signed_qty"]
        .sum()
        .rename(columns={"signed_qty": PortfolioColumns.SHARES})
    )

    positions = positions[positions[PortfolioColumns.SHARES] > 0]
    positions = positions.merge(book_cost_df, on=PortfolioColumns.TICKER, how='left')

    return positions, position_history


def compute_dividends(positions, dividend_events, position_history: dict):
    print("Calculating dividends...")
    dividend_totals = {}
    dividend_total_base = {}
    for ticker in positions[PortfolioColumns.TICKER]:
        ticker_divs = dividend_events[dividend_events[PortfolioColumns.TICKER] == ticker]
        total_div = 0
        total_div_base = 0
        pos_info = position_history.get(ticker)
        if pos_info and pos_info['is_open']:
            open_date = pos_info['current_open_date']
            # Filter dividends that happened after current position opened
            valid_divs = ticker_divs[ticker_divs[PortfolioColumns.DATE] >= open_date]
            total_div = valid_divs[PortfolioColumns.BOOK_COST].sum()
            total_div_base = valid_divs[PortfolioColumns.BOOK_COST].dot(valid_divs[PortfolioColumns.FX])

        dividend_totals[ticker] = total_div
        dividend_total_base[ticker] = total_div_base

    positions[PortfolioColumns.DIVIDENDS] = positions[PortfolioColumns.TICKER].map(dividend_totals).fillna(0)
    positions[PortfolioColumns.DIVIDENDS_BASE] =positions[PortfolioColumns.TICKER].map(dividend_total_base).fillna(0)
    return positions


def get_ccy(base_ccy, list_of_ccy):
    fx_rates = {}

    for ccy in list_of_ccy:
        if ccy == base_ccy:
            fx_rates[ccy] = 1.0
            continue

        ticker = f"{ccy}{base_ccy}=X"

        df = yf.download(ticker, period="1d", interval="1d", progress=False)

        if df.empty:
            raise ValueError(f"No FX data for {ccy}")

        fx_rates[ccy] = df["Close"].iloc[-1].values[0]

    return fx_rates

def enrich_portfolio_data(positions):
    """Fetches Prices, Metadata, and Earnings in a more efficient way"""
    tickers = positions[PortfolioColumns.TICKER].tolist()
    print(f"Enriching data for {len(tickers)} tickers...")

    # 1. Fetch Prices
    data = yf.download(tickers, period="1d", group_by="ticker", progress=False)

    # 2. Fetch Metadata & Earnings (Ticker by Ticker for .info)
    meta_list = []
    earnings_map = {}

    for t in tickers:
        try:
            t_obj = yf.Ticker(t)
            info = t_obj.info

            # Metadata
            is_etf = info.get("quoteType") == "ETF"
            meta_list.append({
                PortfolioColumns.TICKER: t,
                YahooCols.SECTOR: info.get("sector", "ETF" if is_etf else "Unknown"),
                YahooCols.INDUSTRY: info.get("industry", "ETF" if is_etf else "Unknown"),
                YahooCols.COUNTRY: info.get("country") if not is_etf else info.get("region", "Unknown"),
                YahooCols.QUOTE_TYPE: info.get("quoteType", "Unknown")
            })

            # Current Price from Download or Info
            if len(tickers) == 1:
                positions.loc[positions[PortfolioColumns.TICKER] == t, YahooCols.PRICE] = data["Close"].iloc[-1]
            else:
                positions.loc[positions[PortfolioColumns.TICKER] == t, YahooCols.PRICE] = data[t]["Close"].iloc[-1]

            # Earnings
            if not is_etf:
                cal = t_obj.calendar
                if cal is not None and "Earnings Date" in cal:
                    e_date = cal["Earnings Date"]
                    earnings_map[t] = str(e_date[0]) if isinstance(e_date, (list, pd.Series)) else str(e_date)

        except Exception as e:
            print(f"Error fetching {t}: {e}")

    # Merge Metadata
    meta_df = pd.DataFrame(meta_list)
    positions = positions.merge(meta_df, on=PortfolioColumns.TICKER, how="left")

    # Add Earnings & Values
    positions[YahooCols.EARNINGS_DATE] = positions[PortfolioColumns.TICKER].map(earnings_map)
    positions[PortfolioColumns.VALUE] = positions[PortfolioColumns.SHARES] * positions[YahooCols.PRICE]

    # Calculate Unrealized P/L
    positions[YahooCols.UNREALIZED_PL] = positions[PortfolioColumns.VALUE] - positions[PortfolioColumns.COST_BASIS]


    # compute base currency value
    # get currency rate
    fx_cur = get_ccy('CAD', positions[PortfolioColumns.CCY].unique())
    positions[PortfolioColumns.CUR_FX] = positions[PortfolioColumns.CCY].map(fx_cur).fillna(1)
    positions[PortfolioColumns.VALUE_BASE] = positions[PortfolioColumns.VALUE] * positions[PortfolioColumns.CUR_FX]
    positions[PortfolioColumns.PNL_BASE] = positions[PortfolioColumns.VALUE_BASE] - positions[PortfolioColumns.COST_BASIS_BASE]
    positions[PortfolioColumns.FX_PNL] = positions[PortfolioColumns.SHARES] * positions[PortfolioColumns.BOOK_COST] * (positions[PortfolioColumns.CUR_FX] - positions[PortfolioColumns.AVG_FX])
    return positions


def get_news(tickers, thesis_dic, limit=5):
    print("Fetching News...")
    news_data = []
    cutoff_date = datetime.now().astimezone() - timedelta(days=90)
    for t in tickers:
        clean_t = t.split(".")[0]
        try:
            # 2. Define multiple RSS sources
            # Yahoo Finance (Specific) + Google News (Wide aggregator)
            rss_urls = [
                f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={clean_t}&region=US&lang=en-US",
                f"https://news.google.com/rss/search?q={clean_t}+stock+news&hl=en-US&gl=US&ceid=US:en"
            ]

            collected_articles = []
            seen_titles = set()  # To avoid duplicates between sources

            for url in rss_urls:
                feed = feedparser.parse(url)

                for entry in feed.entries:
                    # Parse date
                    try:
                        # feedparser usually provides a structured time struct
                        if hasattr(entry, 'published'):
                            article_date = date_parser.parse(entry.published)
                        else:
                            # If no date is present, assume it is new enough or skip
                            continue

                            # Normalize timezone for comparison
                        if article_date.tzinfo is None:
                            article_date = article_date.astimezone()

                        # 3. Filter by Date
                        if article_date < cutoff_date:
                            continue

                        # 4. Filter Duplicates
                        if entry.title in seen_titles:
                            continue

                        seen_titles.add(entry.title)
                        collected_articles.append({
                            'title': entry.get('title', ''),
                            'link': entry.get('link', ''),
                            'date': article_date
                        })
                    except Exception as e:
                        # Skip individual bad entries, don't crash the loop
                        continue

            # 5. Sort all collected articles by date (newest first)
            collected_articles.sort(key=lambda x: x['date'], reverse=True)

            # Prepare the row
            row = {PortfolioColumns.TICKER: t, PortfolioColumns.THESIS: thesis_dic.get(t, "")}

            # 6. Slice to limit and flatten structure
            for i, entry in enumerate(collected_articles[:limit], 1):
                row[f'news_{i}_title'] = entry['title']
                row[f'news_{i}_link'] = entry['link']
                row[f'news_{i}_date'] = entry['date'].strftime('%Y-%m-%d')  # Optional: Add date column

            news_data.append(row)

            # Be nice to Google/Yahoo servers
            # time.sleep(0.5)

        except Exception as e:
            print(f"Error fetching for {t}: {e}")
            news_data.append({PortfolioColumns.TICKER: t})

    news_df = pd.DataFrame(news_data)
    news_df["Date"] = SNAPSHOT_DATE # Uncomment if you have this variable
    return news_df


def apply_etf_lookthrough(positions):
    """
    Apply ETF look-through to expand holdings by sector/risk category
    Now preserves currency information and FX calculations
    """
    print("Applying ETF look-through with currency preservation...")

    expanded_rows = []

    for _, row in positions.iterrows():
        ticker = row[PortfolioColumns.TICKER]
        quote_type = row.get(YahooCols.QUOTE_TYPE, "Unknown")

        # For non-ETFs, keep as-is
        if quote_type != "ETF":
            expanded_rows.append({
                'Symbol': ticker,
                'Sector': row.get(YahooCols.SECTOR, 'Unknown'),
                'RiskCategory': determine_risk_category(row),
                'Shares': row[PortfolioColumns.SHARES],
                'Price': row[YahooCols.PRICE],
                'BookCost': row[PortfolioColumns.BOOK_COST],
                'BookCost_BaseCcy': row[PortfolioColumns.BOOK_COST_BASE],
                'Value': row[PortfolioColumns.VALUE],
                'Value_BaseCcy': row[PortfolioColumns.VALUE_BASE],
                'CostBasis': row[PortfolioColumns.COST_BASIS],
                'CostBasis_BaseCcy': row[PortfolioColumns.COST_BASIS_BASE],
                'UnrealizedPL': row[YahooCols.UNREALIZED_PL],
                'UnrealizedPL_BaseCcy': row[PortfolioColumns.PNL_BASE],
                'UnrealizedPL_Pct': (row[YahooCols.UNREALIZED_PL] / row[PortfolioColumns.COST_BASIS] * 100) if row[
                                                                                                                   PortfolioColumns.COST_BASIS] > 0 else 0,
                'TotalDividends': row[PortfolioColumns.DIVIDENDS],
                'TotalDividends_BaseCcy': row[PortfolioColumns.DIVIDENDS_BASE],
                'Source': 'Stock',
                'EarningsDate': row.get(YahooCols.EARNINGS_DATE),
                'Currency': row[PortfolioColumns.CCY],
                'CurrentFX': row[PortfolioColumns.CUR_FX],
                'AvgFX': row[PortfolioColumns.AVG_FX],
                'FX_PnL': row[PortfolioColumns.FX_PNL],
                'Thesis': row.get(PortfolioColumns.THESIS, '')
            })
            continue

        # ETF look-through
        try:
            etf = yf.Ticker(ticker)
            funds_data = etf.funds_data

            # Get sector weights
            sector_weights = {}
            if hasattr(funds_data, 'sector_weightings') and funds_data.sector_weightings:
                sector_weights = funds_data.sector_weightings

            # Get asset class weights for risk categorization
            asset_weights = {}
            if hasattr(funds_data, 'asset_classes') and funds_data.asset_classes:
                asset_weights = funds_data.asset_classes

            # If no sector breakdown, treat as single allocation
            if not sector_weights:
                risk_cat = determine_etf_risk_category(asset_weights)
                expanded_rows.append({
                    'Symbol': ticker,
                    'Sector': 'ETF - Diversified',
                    'RiskCategory': risk_cat,
                    'Shares': row[PortfolioColumns.SHARES],
                    'Price': row[YahooCols.PRICE],
                    'BookCost': row[PortfolioColumns.BOOK_COST],
                    'BookCost_BaseCcy': row[PortfolioColumns.BOOK_COST_BASE],
                    'Value': row[PortfolioColumns.VALUE],
                    'Value_BaseCcy': row[PortfolioColumns.VALUE_BASE],
                    'CostBasis': row[PortfolioColumns.COST_BASIS],
                    'CostBasis_BaseCcy': row[PortfolioColumns.COST_BASIS_BASE],
                    'UnrealizedPL': row[YahooCols.UNREALIZED_PL],
                    'UnrealizedPL_BaseCcy': row[PortfolioColumns.PNL_BASE],
                    'UnrealizedPL_Pct': (row[YahooCols.UNREALIZED_PL] / row[PortfolioColumns.COST_BASIS] * 100) if row[
                                                                                                                       PortfolioColumns.COST_BASIS] > 0 else 0,
                    'TotalDividends': row[PortfolioColumns.DIVIDENDS],
                    'TotalDividends_BaseCcy': row[PortfolioColumns.DIVIDENDS_BASE],
                    'Source': 'ETF',
                    'EarningsDate': None,
                    'Currency': row[PortfolioColumns.CCY],
                    'CurrentFX': row[PortfolioColumns.CUR_FX],
                    'AvgFX': row[PortfolioColumns.AVG_FX],
                    'FX_PnL': row[PortfolioColumns.FX_PNL],
                    'Thesis': row.get(PortfolioColumns.THESIS, '')
                })
                continue

            # Expand by sector with proportional allocation
            total_weight = sum(sector_weights.values())

            for sector, weight in sector_weights.items():
                allocation_pct = weight / total_weight if total_weight > 0 else 0

                # Allocate values proportionally
                allocated_value = row[PortfolioColumns.VALUE] * allocation_pct
                allocated_value_base = row[PortfolioColumns.VALUE_BASE] * allocation_pct
                allocated_cost = row[PortfolioColumns.COST_BASIS] * allocation_pct
                allocated_cost_base = row[PortfolioColumns.COST_BASIS_BASE] * allocation_pct
                allocated_pl = row[YahooCols.UNREALIZED_PL] * allocation_pct
                allocated_pl_base = row[PortfolioColumns.PNL_BASE] * allocation_pct
                allocated_dividends = row[PortfolioColumns.DIVIDENDS] * allocation_pct
                allocated_dividends_base = row[PortfolioColumns.DIVIDENDS_BASE] * allocation_pct
                allocated_fx_pnl = row[PortfolioColumns.FX_PNL] * allocation_pct

                risk_cat = determine_etf_risk_category(asset_weights)

                expanded_rows.append({
                    'Symbol': ticker,
                    'Sector': sector,
                    'RiskCategory': risk_cat,
                    'Shares': row[PortfolioColumns.SHARES],  # Original shares
                    'Price': row[YahooCols.PRICE],
                    'BookCost': row[PortfolioColumns.BOOK_COST],
                    'BookCost_BaseCcy': row[PortfolioColumns.BOOK_COST_BASE],
                    'Value': allocated_value,  # Allocated by sector
                    'Value_BaseCcy': allocated_value_base,
                    'CostBasis': allocated_cost,
                    'CostBasis_BaseCcy': allocated_cost_base,
                    'UnrealizedPL': allocated_pl,
                    'UnrealizedPL_BaseCcy': allocated_pl_base,
                    'UnrealizedPL_Pct': (allocated_pl / allocated_cost * 100) if allocated_cost > 0 else 0,
                    'TotalDividends': allocated_dividends,
                    'TotalDividends_BaseCcy': allocated_dividends_base,
                    'Source': f'ETF_Lookthrough_{ticker}',
                    'EarningsDate': None,
                    'Currency': row[PortfolioColumns.CCY],
                    'CurrentFX': row[PortfolioColumns.CUR_FX],
                    'AvgFX': row[PortfolioColumns.AVG_FX],
                    'FX_PnL': allocated_fx_pnl,
                    'Thesis': row.get(PortfolioColumns.THESIS, '')
                })

        except Exception as e:
            print(f"⚠️ Could not fetch ETF data for {ticker}: {e}")
            # Fallback: treat as single position
            risk_cat = 'Equity'  # Default for ETFs
            expanded_rows.append({
                'Symbol': ticker,
                'Sector': 'ETF - Unknown',
                'RiskCategory': risk_cat,
                'Shares': row[PortfolioColumns.SHARES],
                'Price': row[YahooCols.PRICE],
                'BookCost': row[PortfolioColumns.BOOK_COST],
                'BookCost_BaseCcy': row[PortfolioColumns.BOOK_COST_BASE],
                'Value': row[PortfolioColumns.VALUE],
                'Value_BaseCcy': row[PortfolioColumns.VALUE_BASE],
                'CostBasis': row[PortfolioColumns.COST_BASIS],
                'CostBasis_BaseCcy': row[PortfolioColumns.COST_BASIS_BASE],
                'UnrealizedPL': row[YahooCols.UNREALIZED_PL],
                'UnrealizedPL_BaseCcy': row[PortfolioColumns.PNL_BASE],
                'UnrealizedPL_Pct': (row[YahooCols.UNREALIZED_PL] / row[PortfolioColumns.COST_BASIS] * 100) if row[
                                                                                                                   PortfolioColumns.COST_BASIS] > 0 else 0,
                'TotalDividends': row[PortfolioColumns.DIVIDENDS],
                'TotalDividends_BaseCcy': row[PortfolioColumns.DIVIDENDS_BASE],
                'Source': 'ETF',
                'EarningsDate': None,
                'Currency': row[PortfolioColumns.CCY],
                'CurrentFX': row[PortfolioColumns.CUR_FX],
                'AvgFX': row[PortfolioColumns.AVG_FX],
                'FX_PnL': row[PortfolioColumns.FX_PNL],
                'Thesis': row.get(PortfolioColumns.THESIS, '')
            })

    expanded_df = pd.DataFrame(expanded_rows)

    print(f"✓ Expanded to {len(expanded_df)} rows (from {len(positions)} positions)")

    return expanded_df


def determine_risk_category(row):
    """Determine risk category for a stock position"""
    quote_type = row.get(YahooCols.QUOTE_TYPE, 'Stock')
    return ASSET_RISK_MAPPING.get(quote_type, 'Equity')


def determine_etf_risk_category(asset_weights):
    """
    Determine dominant risk category for ETF based on asset allocation

    Args:
        asset_weights: dict of asset class → percentage

    Returns:
        str: Risk category (Equity, Fixed Income, etc.)
    """
    if not asset_weights:
        return 'Equity'  # Default

    # Map asset classes to risk categories
    category_totals = {}

    for asset, weight in asset_weights.items():
        risk_cat = ASSET_RISK_MAPPING.get(asset, 'Other')
        category_totals[risk_cat] = category_totals.get(risk_cat, 0) + weight

    # Return dominant category
    if category_totals:
        return max(category_totals.items(), key=lambda x: x[1])[0]

    return 'Equity'


def save_unified_snapshot(expanded_df, positions, dividend_events):
    """
    Save portfolio snapshot with currency information
    Includes both original currency and base currency (CAD) columns
    """
    print("Saving unified portfolio snapshot...")

    # Prepare final DataFrame
    snapshot = expanded_df.copy()
    snapshot['Date'] = SNAPSHOT_DATE

    # Column order for CSV (with currency columns)
    columns_order = [
        'Date',
        'Symbol',
        'Sector',
        'RiskCategory',
        'Currency',
        'Shares',
        'Price',
        'BookCost',
        'BookCost_BaseCcy',
        'Value',
        'Value_BaseCcy',
        'CostBasis',
        'CostBasis_BaseCcy',
        'UnrealizedPL',
        'UnrealizedPL_BaseCcy',
        'UnrealizedPL_Pct',
        'TotalDividends',
        'TotalDividends_BaseCcy',
        'CurrentFX',
        'AvgFX',
        'FX_PnL',
        'Source',
        'EarningsDate',
        'Thesis'
    ]

    snapshot = snapshot[columns_order]

    # Remove duplicate data for same date
    unified_history_file = OUTPUT_DIR / "portfolio_history_unified.csv"

    if unified_history_file.exists():
        existing_history = pd.read_csv(unified_history_file)
        existing_history = existing_history[existing_history['Date'] != SNAPSHOT_DATE]
        snapshot = pd.concat([existing_history, snapshot], ignore_index=True)

    snapshot.to_csv(unified_history_file, index=False)
    print(f"✓ Saved unified history: {unified_history_file}")

    return snapshot



def append_to_history(cur_snapshot, history_file="portfolio_history_unified.csv"):
    unified_history_file = OUTPUT_DIR / history_file

    # 1. Ensure Date exists in current snapshot
    if "Date" not in cur_snapshot.columns:
        cur_snapshot = cur_snapshot.copy()  # Avoid SettingWithCopy warning
        cur_snapshot["Date"] = SNAPSHOT_DATE

    if unified_history_file.exists():
        print(f"\nAppending to existing history: {unified_history_file}")

        # 2. Read existing history
        try:
            existing_history = pd.read_csv(unified_history_file)
        except pd.errors.EmptyDataError:
            # Handle edge case where file exists but is empty
            existing_history = pd.DataFrame()

        if not existing_history.empty:
            # 3. Deduplicate: Remove today's data if running update multiple times
            # Ensure column types match for comparison if necessary, but string usually works
            existing_history = existing_history[existing_history['Date'] != SNAPSHOT_DATE]
            print(f"  Removed any existing data for {SNAPSHOT_DATE}")

        # 4. Concatenate (Magic of Backward Compatibility)
        # sort=False prevents pandas from alphabetically sorting columns
        updated_history = pd.concat([existing_history, cur_snapshot], ignore_index=True, sort=False)

        # 5. Column Cleanup / Reordering
        # We want the columns to look like the Current Snapshot (the modern schema).
        # Any old columns that don't exist in current snapshot go to the end.
        current_cols = list(cur_snapshot.columns)
        all_cols = list(updated_history.columns)

        # Create final order: Current Columns + (All Columns - Current Columns)
        final_col_order = current_cols + [c for c in all_cols if c not in current_cols]
        updated_history = updated_history[final_col_order]

    else:
        print(f"\nCreating new unified history: {unified_history_file}")
        updated_history = cur_snapshot

    # 6. Safe Sorting
    # We define our desired sort keys
    sort_keys = ['Date', 'Sector', 'Symbol']
    # We filter these keys to only include columns that actually exist in the final data
    # (prevents KeyError if 'Sector' or 'Symbol' was deleted from schema)
    valid_sort_keys = [col for col in sort_keys if col in updated_history.columns]

    if valid_sort_keys:
        updated_history = updated_history.sort_values(valid_sort_keys)

    # 7. Save
    updated_history.to_csv(unified_history_file, index=False)

    print(f"\n✓ Saved {len(cur_snapshot)} rows for {SNAPSHOT_DATE}")
    print(f"✓ Total history: {len(updated_history)} rows across {updated_history['Date'].nunique()} dates")


def prepare_news_file(news_snapshot, ticker_list):
    print("\nSaving news data to separate file...")


    news_history_file = OUTPUT_DIR / "portfolio_news_history.csv"

    if news_history_file.exists():
        print(f"  Appending to existing news history: {news_history_file}")
        existing_news_history = pd.read_csv(news_history_file, sep='|', encoding='utf-8-sig')

        # Remove today's data if it exists
        existing_news_history = existing_news_history[existing_news_history['Date'] != SNAPSHOT_DATE]
        print(f"  Removed any existing news for {SNAPSHOT_DATE}")

        # Append new snapshot
        updated_news_history = pd.concat([existing_news_history, news_snapshot], ignore_index=True)
    else:
        print(f"  Creating new news history: {news_history_file}")
        updated_news_history = news_snapshot

    # Sort by date and ticker
    updated_news_history = updated_news_history.sort_values(['Date', 'ticker'])

    # Save
    updated_news_history.to_csv(news_history_file, index=False, sep='|', encoding='utf-8-sig')

    print(f"✓ Saved {len(news_snapshot)} ticker news items for {SNAPSHOT_DATE}")
    print(
        f"✓ Total news history: {len(updated_news_history)} rows across {updated_news_history['Date'].nunique()} dates")


# =========================
# Execution
# =========================
if __name__ == "__main__":
    # 1. Load
    raw_trades = parse_siyuan_trades(SIYUAN_JSON)

    # 2. Process
    div_events = raw_trades[raw_trades[PortfolioColumns.EVENT_TYPE] == EventType.DIVIDEND].copy()
    positions, history = build_aggregated_positions(raw_trades)
    positions = compute_dividends(positions, div_events, history)

    # 3. Enrich
    positions = enrich_portfolio_data(positions)
    tickers = positions["ticker"].unique()
    # 4. News raw
    # Keys: 'Ticker', Values: 'Price'
    thesis_dict = dict(zip(positions[PortfolioColumns.TICKER], positions[PortfolioColumns.THESIS]))
    news_df = get_news(positions[PortfolioColumns.TICKER].tolist(), thesis_dict)
    prepare_news_file(news_df, tickers)

    # Final Output
    look_through_positions = apply_etf_lookthrough(positions)
    append_to_history(look_through_positions)

    print("\n" + "=" * 70)
    print("✓ COMPLETE!")