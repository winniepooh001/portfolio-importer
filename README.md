# 📊 Siyuan Portfolio Importer Widget

## 📖 The Story Behind the Project / 项目背景

> **"From Fragmented Trades to a Single Decision System"** > I wrote a detailed article about why I built this tool and how it transformed my investment workflow.  
> 👉 [Read the full story on Medium](https://medium.com/@wintersweet001/from-fragmented-trades-to-a-single-decision-system-047b5fb29c9e)

> **“从碎片化交易到统一决策系统”** > 我写了一篇详细的文章，介绍了为什么要开发这个工具，以及它如何改变了我的投资流程。  
> 👉 [在 Medium 上阅读全文](https://medium.com/@wintersweet001/from-fragmented-trades-to-a-single-decision-system-047b5fb29c9e)
### 思源笔记投资组合导入挂件

[English](#-english) | [简体中文](#-简体中文)

---

## 🇺🇸 English

### Overview
This is a professional investment tracking widget for **SiYuan Note**. It bridges the gap between your notes and live financial data by using a local Python bridge to fetch market prices, calculate portfolio metrics, and generate interactive visualizations.

### ✨ Key Features
* **Portfolio Analysis**: Automatically calculates cost basis, unrealized P/L, and dividends via `yfinance`.
* **Visual Risk Mapping**: Generates interactive HTML charts for sector and asset allocation.
* **News Aggregator**: Pulls the latest news for your specific tickers and appends them to your documents.
* **Database Driven**: Integrates directly with Siyuan's Attribute View (Database) system.

### 🛠️ System Architecture
The widget uses a "Bridge" architecture to allow a web-based widget to interact with your local file system and Python environment securely.



### 📂 Repository Structure
* `scripts/`: Core Python logic (parsing, visualizer, and exposure scripts).
* `bridge.py`: Flask-based local server that connects the widget to Python.
* `configs.py`: Centralized configuration (Path management and Database names).
* `widget.js / index.html`: The frontend user interface for Siyuan.

### 🚀 Getting Started

1.  **Prerequisites**: Install Python 3.8+ and required libraries:
    ```bash
    pip install flask flask-cors pandas yfinance feedparser
    ```
2.  **Configuration**: Edit `configs.py`. Set `DB_TBL_NAME` to your Siyuan database name.
3.  **Run the Bridge**: Start the server by running `python bridge.py`.
4.  **Install Widget**: Copy this folder to Siyuan's `data/widgets` directory. 
5.  **Use**: Insert the widget into a page and provide your **Target Document ID**.

---

## 🇨🇳 简体中文

### 项目简介
这是一个专为**思源笔记**设计的专业投资追踪挂件。通过本地 Python 桥接技术，它能将您的笔记内容与实时金融数据连接起来，实现行情获取、损益计算及风险可视化。

### ✨ 核心功能
* **投资组合分析**: 利用 `yfinance` 自动计算成本、浮盈及分红数据。
* **风险可视化**: 生成交互式的 HTML 图表，直观展示板块配置和资产分布。
* **新闻聚合**: 获取持仓标的的最新新闻，并以 Markdown 格式自动导入笔记。
* **原生集成**: 深度支持思源笔记的属性视图（数据库）系统。

### 📂 目录结构
* `scripts/`: 核心 Python 逻辑（包含解析器、可视化工具及数据处理脚本）。
* `bridge.py`: 基于 Flask 的本地服务器，连接挂件与 Python 环境。
* `configs.py`: 中心配置文件（管理路径及数据库名称）。
* `widget.js / index.html`: 思源挂件的前端界面与逻辑。

### 🚀 快速开始

1.  **环境要求**: 安装 Python 3.8+ 及必要库：
    ```bash
    pip install flask flask-cors pandas yfinance feedparser
    ```
2.  **配置选项**: 编辑 `configs.py`，将 `DB_TBL_NAME` 设置为您思源数据库的名称。
3.  **启动桥接**: 运行 `python bridge.py` 启动本地服务。
4.  **安装挂件**: 将此文件夹移动至思源笔记的 `data/widgets` 目录中。
5.  **开始使用**: 在页面中插入挂件，并输入您的**目标文档 ID**。

---

## 🔒 Privacy & Security / 隐私与安全
* **Local Only**: The bridge server runs only on `127.0.0.1`. No data is sent to external servers except for market data requests to Yahoo Finance.
* **本地运行**: 桥接服务器仅运行在本地环回地址 `127.0.0.1`。除向 Yahoo Finance 请求行情外，不会向外界上传任何数据。