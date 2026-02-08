/**
 * Portfolio Importer Widget - Unified System (Optimized)
 * After running "Update Portfolio", news and chart import work independently
 */

const BRIDGE_URL = "http://127.0.0.1:5000/run-task";
const SIYUAN_STORAGE_PATH = "/data/storage/petal/portfolio-importer";
const logOutput = document.getElementById('logOutput');
const workBtn = document.getElementById('workBtn');
const importNewsBtn = document.getElementById('importNewsBtn');
const importChartBtn = document.getElementById('importChartBtn');

// 日志打印函数
function log(msg, type = 'default') {
    const div = document.createElement('div');
    div.className = type !== 'default' ? `log-${type}` : '';
    div.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    logOutput.appendChild(div);
    logOutput.scrollTop = logOutput.scrollHeight;
}

// 清空日志
function clearLogs() {
    logOutput.innerHTML = '等待指令...';
}

// ============================================
// 核心业务逻辑 1: 运行 Python 脚本更新数据
// ============================================
async function runPortfolioUpdate() {
    workBtn.disabled = true;
    logOutput.innerHTML = '';
    log("🚀 开始执行投资组合数据更新...", "info");

    try {
        // 调用 Python Bridge 运行更新脚本（现在会同时生成数据、新闻和图表）
        log("📡 正在运行 portfolio_exposure.py...", "info");
        const bridgeRes = await fetch(BRIDGE_URL, { 
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                task: "update_portfolio"
            })
        });
        
        if (!bridgeRes.ok) {
            throw new Error(`HTTP错误: ${bridgeRes.status}`);
        }

        const pyResult = await bridgeRes.json();

        if (pyResult.status !== 'success') {
            throw new Error(`Python 脚本错误: ${pyResult.message}`);
        }

        log("✅ portfolio_history_unified.csv 已生成", "success");
        log("✅ portfolio_news_history.csv 已生成", "success");
        
        if (pyResult.chart_status === 'success') {
            log("✅ portfolio_sectors_unified.html 已生成", "success");
        } else if (pyResult.chart_status === 'warning') {
            log("⚠️ 图表生成有警告，但数据已完成", "warning");
        }
        
        if (pyResult.summary) {
            log(`📊 投资组合概览:`, "info");
            log(`   总价值: ${pyResult.summary.total_value}`, "default");
            log(`   未实现盈亏: ${pyResult.summary.unrealized_pl}`, "default");
            log(`   总股息: ${pyResult.summary.total_dividends}`, "default");
            log(`   持仓数: ${pyResult.summary.position_count}`, "default");
        }

        log("💡 提示: 现在可以导入新闻或图表到思源笔记（无需 bridge 运行）", "info");

    } catch (e) {
        log(`❌ 失败: ${e.message}`, "error");
        console.error(e);
    } finally {
        workBtn.disabled = false;
    }
}

// ============================================
// 核心业务逻辑 2: 导入新闻到思源文档
// ============================================
async function importNewsToSiyuan() {
    const targetId = document.getElementById('targetDocId').value.trim();
    
    if (!targetId) {
        log("错误: 请输入目标文档 ID", "error");
        return;
    }

    importNewsBtn.disabled = true;
    log("📰 开始导入最新新闻到思源笔记...", "info");

    try {
        // 直接从本地 Siyuan 存储读取新闻文件
        log("📂 正在读取本地新闻数据...", "info");
        const newsPath = `${SIYUAN_STORAGE_PATH}/portfolio_news_history.csv`;
        
        // 读取文件内容
        const fileRes = await fetch(newsPath);
        if (!fileRes.ok) {
            throw new Error(`无法读取新闻文件: ${newsPath}. 请先运行"更新投资组合数据"`);
        }
        
        const csvText = await fileRes.text();
        
        // 解析 CSV (pipe-delimited)
        const newsData = parseNewsCSV(csvText);
        
        if (!newsData || newsData.length === 0) {
            throw new Error('新闻数据为空');
        }

        // 构建 Markdown 内容
        log("📝 正在构建 Markdown 格式...", "info");
        const date = newsData[0].Date; // 获取最新日期
        
        let fullMd = `\n---\n# 📈 Portfolio News Update (${date})\n\n`;

        for (const item of newsData) {
            const ticker = item.ticker;
            const thesis = item.thesis;
            
            log(`处理新闻: ${ticker}`, "default");

            // Format ticker with thesis link if available
            let tickerDisplay = ticker;
            if (thesis && thesis.trim()) {
                tickerDisplay = `((${thesis} '${ticker}'))`;
                log(`  ✓ 已链接到论文: ${thesis}`, "default");
            }

            fullMd += `## ${tickerDisplay}\n\n`;

            // 添加新闻链接
            let hasNews = false;
            for (let i = 1; i <= 5; i++) {
                const title = item[`news_${i}_title`];
                const newsDate = item[`news_${i}_date`];
                const link = item[`news_${i}_link`];

                if (title && title.trim() && link && link.trim()) {
                    fullMd += `- [${title.trim()}](${link.trim()})`;
                    if (newsDate && newsDate.trim()) {
                        fullMd += ` · ${newsDate.trim()}`;
                    }
                    fullMd += `\n`;
                    hasNews = true;
                }
            }

            if (!hasNews) {
                fullMd += `*(暂无新闻)*\n`;
            }

            fullMd += `\n`;
        }

        // 调用思源 API 追加块
        log("📤 正在同步到思源笔记...", "info");
        const appendRes = await fetch("/api/block/appendBlock", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                data: fullMd,
                dataType: "markdown",
                parentID: targetId
            })
        });

        const appendData = await appendRes.json();

        if (appendData.code === 0) {
            const linkedCount = newsData.filter(item => item.thesis && item.thesis.trim()).length;
            log(`🎉 新闻导入成功！已添加 ${newsData.length} 个持仓的新闻`, "success");
            if (linkedCount > 0) {
                log(`🔗 其中 ${linkedCount} 个已链接到投资论文`, "success");
            }
        } else {
            throw new Error(`思源 API 错误: ${appendData.msg}`);
        }

    } catch (e) {
        log(`❌ 失败: ${e.message}`, "error");
        console.error(e);
    } finally {
        importNewsBtn.disabled = false;
    }
}

// ============================================
// 核心业务逻辑 3: 导入交互式图表到思源文档
// ============================================
async function importChartToSiyuan() {
    const targetId = document.getElementById('targetDocId').value.trim();
    
    if (!targetId) {
        log("错误: 请输入目标文档 ID", "error");
        return;
    }

    importChartBtn.disabled = true;
    log("📊 开始导入交互式图表...", "info");

    try {
        // 直接使用本地路径
        const chartPath = `${SIYUAN_STORAGE_PATH}/portfolio_sectors_unified.html`;
        
        log("📂 检查图表文件...", "info");
        
        // 验证文件存在
        const testRes = await fetch(chartPath, { method: 'HEAD' });
        if (!testRes.ok) {
            throw new Error(`图表文件不存在: ${chartPath}. 请先运行"更新投资组合数据"`);
        }
        
        log("✅ 图表文件已找到", "success");

        // 构建 iframe HTML 嵌入代码
        const iframeHtml = `\n<iframe src="${chartPath}" width="100%" height="950px" style="border:none; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);"></iframe>\n`;

        // 追加到思源文档
        log("📤 正在嵌入图表到思源笔记...", "info");
        const appendRes = await fetch("/api/block/appendBlock", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                data: iframeHtml,
                dataType: "markdown",
                parentID: targetId
            })
        });

        const appendData = await appendRes.json();

        if (appendData.code === 0) {
            log("🎉 交互式图表导入成功！", "success");
            log(`💡 图表包含:`, "info");
            log(`   - 扇形图: 板块配置`, "default");
            log(`   - 扇形图: 风险类别配置`, "default");
            log(`   - 日期滑块: 查看历史变化`, "default");
            log(`   - 详细持仓: 盈亏、股息、新闻`, "default");
        } else {
            throw new Error(`思源 API 错误: ${appendData.msg}`);
        }

    } catch (e) {
        log(`❌ 失败: ${e.message}`, "error");
        console.error(e);
    } finally {
        importChartBtn.disabled = false;
    }
}

// ============================================
// 一键完整导入流程
// ============================================
async function importFullPortfolio() {
    const targetId = document.getElementById('targetDocId').value.trim();
    
    if (!targetId) {
        log("错误: 请输入目标文档 ID", "error");
        return;
    }

    // 禁用所有按钮
    workBtn.disabled = true;
    importNewsBtn.disabled = true;
    importChartBtn.disabled = true;
    
    logOutput.innerHTML = '';
    log("🚀 开始执行完整导入流程...", "info");

    try {
        // Step 1: 更新数据（这会生成所有文件）
        log("\n=== 步骤 1/3: 更新投资组合数据 ===", "info");
        await runPortfolioUpdate();
        
        // 等待一小段时间确保文件写入完成
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Step 2: 导入新闻
        log("\n=== 步骤 2/3: 导入新闻 ===", "info");
        await importNewsToSiyuan();
        
        // Step 3: 导入图表
        log("\n=== 步骤 3/3: 导入交互式图表 ===", "info");
        await importChartToSiyuan();
        
        log("\n🎊 完整导入流程执行成功！", "success");
        
    } catch (e) {
        log(`❌ 流程中断: ${e.message}`, "error");
        console.error(e);
    } finally {
        // 恢复按钮
        workBtn.disabled = false;
        importNewsBtn.disabled = false;
        importChartBtn.disabled = false;
    }
}

// ============================================
// 辅助函数: 解析新闻 CSV
// ============================================
function parseNewsCSV(csvText) {
    const lines = csvText.trim().split('\n');
    if (lines.length < 2) return [];
    
    // 第一行是 header
    const headers = lines[0].split('|').map(h => h.trim());
    
    // 解析数据行
    const data = [];
    for (let i = 1; i < lines.length; i++) {
        const values = lines[i].split('|');
        if (values.length !== headers.length) continue;
        
        const row = {};
        headers.forEach((header, index) => {
            row[header] = values[index] ? values[index].trim() : '';
        });
        
        data.push(row);
    }
    
    // 只返回最新日期的数据
    if (data.length === 0) return [];
    
    const latestDate = data[0].Date;
    return data.filter(row => row.Date === latestDate);
}

// 绑定按钮事件
workBtn.addEventListener('click', runPortfolioUpdate);
importNewsBtn.addEventListener('click', importNewsToSiyuan);
importChartBtn.addEventListener('click', importChartToSiyuan);

// 添加一键导入按钮事件（如果存在）
const fullImportBtn = document.getElementById('fullImportBtn');
if (fullImportBtn) {
    fullImportBtn.addEventListener('click', importFullPortfolio);
}