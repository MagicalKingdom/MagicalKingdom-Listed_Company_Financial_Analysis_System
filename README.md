# 上市公司财务数据分析系统

基于 Python + Flask 的上市公司财务数据采集与分析系统，支持从新浪财经抓取财务报表数据，并提供多维度的财务分析功能。

## 功能特性

- **数据采集**：自动从新浪财经抓取上市公司资产负债表、利润表、现金流量表
- **获利能力分析**：毛利率、净利率、ROA、ROE、杜邦分析等
- **总体运行分析**：资产负债结构、偿债能力、营运能力、现金流分析
- **自定义分析**：支持选择任意财务指标进行查看和对比
- **趋势图表**：可视化展示财务指标的历史变化趋势
- **行业对比**：与行业平均水平进行对比评估

## 技术栈

- **后端**：Python 3.9+、Flask
- **数据库**：SQLite
- **前端**：HTML5、CSS3、JavaScript、Chart.js
- **数据源**：新浪财经

## 项目结构

```
financial_analysis_for_public_companies/
├── app.py              # Flask Web 应用主程序
├── data_crawler.py     # 数据采集模块
├── db_handler.py       # 数据库操作模块
├── analyzer.py         # 财务分析模块
├── main.py             # 命令行入口
├── requirements.txt    # 依赖包列表
├── stock_data.db       # SQLite 数据库文件
└── templates/
    └── index.html      # 前端页面
```

## 安装配置

### 1. 克隆项目

```bash
git clone https://github.com/MagicalKingdom/MagicalKingdom-Listed_Company_Financial_Analysis_System.git
cd financial_analysis_for_public_companies
```

### 2. 创建虚拟环境

```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 启动服务

```bash
python app.py
```

服务启动后访问 http://127.0.0.1:5000

## 使用说明

### Web 界面

1. **下载数据**：在左侧输入 6 位股票代码（如 600519），点击"下载财务数据"
2. **选择分析**：从已下载的股票中选择一只，选择报告日期
3. **执行分析**：
   - 自定义分析：选择需要查看的财务指标
   - 获利能力分析：分析公司盈利能力和成长性
   - 总体运行分析：全面分析公司财务状况

### 命令行

```bash
python main.py
```

按提示选择功能并输入股票代码。

## 支持的股票

- 沪市 A 股：以 600、601、603、605 开头
- 深市 A 股：以 000、001、002、003 开头
- 创业板：以 300、301 开头
- 科创板：以 688 开头

## 注意事项

- 数据来源于新浪财经，仅供学习研究使用
- 首次下载某只股票数据可能需要较长时间
- 分析结论仅供参考，不构成投资建议
