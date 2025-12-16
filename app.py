"""
Web应用后端 - Flask API
"""
from flask import Flask, render_template, jsonify, request
from db_handler import DatabaseManager
from data_crawler import StockDataCrawler, FinanceReportFetcher
from analyzer import FinancialAnalyzer, INDICATOR_MAP
from decimal import Decimal, InvalidOperation
import pandas as pd

app = Flask(__name__)
db = DatabaseManager()
analyzer = FinancialAnalyzer()

# 股票名称缓存
_stock_name_cache = {}


def get_stock_name(stock_code):
    """获取股票名称"""
    if stock_code in _stock_name_cache:
        return _stock_name_cache[stock_code]
    
    try:
        url = f'https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpInfo/stockid/{stock_code}.phtml'
        tables = pd.read_html(url, encoding='gbk')
        # 公司名称在第4个表格的第1行第2列
        name = str(tables[3].iloc[0, 1])
        # 清理名称
        name = name.replace('\r\n', '').replace('\n', '').replace(' ', '').strip()
        if name and name != stock_code and name != 'nan':
            _stock_name_cache[stock_code] = name
            return name
        return None
    except Exception as e:
        print(f"获取股票名称失败: {stock_code}, {e}")
        return None

# 行业平均值参考（A股上市公司平均水平）
INDUSTRY_BENCHMARK = {
    '毛利率': 0.25,
    '净利率': 0.08,
    'ROA': 0.04,
    'ROE': 0.10,
    '资产负债率': 0.45,
    '流动比率': 1.5,
    '速动比率': 1.0,
    '总资产周转率': 0.6,
    '应收账款周转率': 8.0,
    '存货周转率': 6.0
}


def parse_value(val):
    """解析数值"""
    try:
        return float(Decimal(str(val)))
    except (InvalidOperation, ValueError):
        return 0


def safe_divide(a, b):
    """安全除法"""
    if b is None or b == 0 or a is None:
        return None
    return round(a / b, 4)


def get_data_dict(stock_code, report_date):
    """获取数据字典"""
    rows = db.query_financial_data(stock_code, report_date)
    return {row[0]: row[1] for row in rows}


def get_val(data_dict, name):
    """从数据字典获取指标值"""
    item_id = INDICATOR_MAP.get(name)
    if item_id and item_id in data_dict:
        return parse_value(data_dict[item_id])
    return None


def get_trend_data(stock_code, indicator_name, periods=5):
    """获取指标趋势数据"""
    dates = db.get_report_dates(stock_code)[:periods]
    trend = []
    for d in reversed(dates):
        data_dict = get_data_dict(stock_code, d)
        val = get_val(data_dict, indicator_name)
        trend.append({'date': d, 'value': val})
    return trend


def calculate_growth_rate(current, previous):
    """计算增长率"""
    if previous is None or previous == 0 or current is None:
        return None
    return round((current - previous) / abs(previous), 4)


def compare_with_benchmark(value, benchmark_key):
    """与行业基准比较"""
    benchmark = INDUSTRY_BENCHMARK.get(benchmark_key)
    if value is None or benchmark is None:
        return {'status': 'unknown', 'diff': None}
    diff = value - benchmark
    if diff > benchmark * 0.2:
        return {'status': 'excellent', 'diff': diff, 'benchmark': benchmark}
    elif diff > 0:
        return {'status': 'good', 'diff': diff, 'benchmark': benchmark}
    elif diff > -benchmark * 0.2:
        return {'status': 'normal', 'diff': diff, 'benchmark': benchmark}
    else:
        return {'status': 'poor', 'diff': diff, 'benchmark': benchmark}


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/stocks')
def get_stocks():
    """获取所有股票代码及名称"""
    codes = db.get_all_stock_codes()
    stocks = []
    for code in codes:
        name = get_stock_name(code)
        stocks.append({'code': code, 'name': name or code})
    return jsonify({'codes': codes, 'stocks': stocks})


@app.route('/api/download', methods=['POST'])
def download_data():
    """下载股票数据"""
    data = request.json
    stock_code = data.get('code', '')
    
    if not stock_code or len(stock_code) != 6:
        return jsonify({'success': False, 'message': '请输入6位股票代码'})
    
    try:
        fetcher = FinanceReportFetcher(stock_code)
        result = fetcher.crawl()
        db.store(result)
        # 获取公司名称
        name = get_stock_name(stock_code)
        name_info = f"（{name}）" if name else ""
        return jsonify({'success': True, 'message': f'成功下载 {stock_code}{name_info} 的财务数据', 'name': name})
    except Exception as e:
        return jsonify({'success': False, 'message': f'下载失败: {str(e)}'})


@app.route('/api/dates/<stock_code>')
def get_dates(stock_code):
    """获取报告日期"""
    dates = db.get_report_dates(stock_code)
    return jsonify({'dates': dates})


@app.route('/api/custom', methods=['POST'])
def custom_analysis():
    """自定义分析 - 增强版"""
    data = request.json
    stock_code = data.get('code')
    report_date = data.get('date')
    indicators = data.get('indicators', [])
    
    data_dict = get_data_dict(stock_code, report_date)
    
    # 获取上期数据用于计算同比
    dates = db.get_report_dates(stock_code)
    prev_date = None
    prev_data_dict = {}
    for i, d in enumerate(dates):
        if d == report_date and i + 4 < len(dates):
            prev_date = dates[i + 4]  # 去年同期
            prev_data_dict = get_data_dict(stock_code, prev_date)
            break
    
    results = []
    for name in indicators:
        val = get_val(data_dict, name)
        prev_val = get_val(prev_data_dict, name) if prev_data_dict else None
        growth = calculate_growth_rate(val, prev_val)
        
        # 获取趋势
        trend = get_trend_data(stock_code, name, 6)
        
        results.append({
            'name': name,
            'value': val,
            'formatted': f"{val/10000:,.2f} 万元" if val else "N/A",
            'prev_value': prev_val,
            'prev_formatted': f"{prev_val/10000:,.2f} 万元" if prev_val else "N/A",
            'growth': growth,
            'growth_formatted': f"{growth*100:+.2f}%" if growth is not None else "N/A",
            'trend': trend
        })
    
    return jsonify({
        'results': results,
        'report_date': report_date,
        'prev_date': prev_date
    })


@app.route('/api/profitability', methods=['POST'])
def profitability_analysis():
    """获利能力分析 - 增强版"""
    data = request.json
    stock_code = data.get('code')
    report_date = data.get('date')
    
    data_dict = get_data_dict(stock_code, report_date)
    
    # 获取历史数据
    dates = db.get_report_dates(stock_code)[:8]
    
    # 基础指标
    revenue = get_val(data_dict, '营业收入')
    cost = get_val(data_dict, '营业成本')
    net_profit = get_val(data_dict, '净利润')
    total_assets = get_val(data_dict, '总资产')
    equity = get_val(data_dict, '所有者权益')
    operating_profit = get_val(data_dict, '营业利润')
    gross_profit_val = get_val(data_dict, '毛利润')
    
    gross_profit = gross_profit_val if gross_profit_val else (revenue - cost if revenue and cost else None)
    
    # 计算比率
    gross_margin = safe_divide(gross_profit, revenue)
    net_margin = safe_divide(net_profit, revenue)
    operating_margin = safe_divide(operating_profit, revenue)
    roa = safe_divide(net_profit, total_assets)
    roe = safe_divide(net_profit, equity)
    cost_ratio = safe_divide(cost, revenue)
    
    # 计算趋势数据
    def calc_ratio_trend(numerator_name, denominator_name):
        trend = []
        for d in reversed(dates):
            dd = get_data_dict(stock_code, d)
            num = get_val(dd, numerator_name)
            den = get_val(dd, denominator_name)
            ratio = safe_divide(num, den)
            trend.append({'date': d, 'value': ratio})
        return trend
    
    revenue_trend = get_trend_data(stock_code, '营业收入', 8)
    profit_trend = get_trend_data(stock_code, '净利润', 8)
    
    # 计算同比增长
    prev_date = dates[4] if len(dates) > 4 else None
    prev_data = get_data_dict(stock_code, prev_date) if prev_date else {}
    
    prev_revenue = get_val(prev_data, '营业收入')
    prev_profit = get_val(prev_data, '净利润')
    
    revenue_growth = calculate_growth_rate(revenue, prev_revenue)
    profit_growth = calculate_growth_rate(net_profit, prev_profit)
    
    # 杜邦分析
    asset_turnover = safe_divide(revenue, total_assets)
    equity_multiplier = safe_divide(total_assets, equity)
    dupont_roe = None
    if net_margin and asset_turnover and equity_multiplier:
        dupont_roe = round(net_margin * asset_turnover * equity_multiplier, 4)
    
    # 与行业基准比较
    benchmarks = {
        '毛利率': compare_with_benchmark(gross_margin, '毛利率'),
        '净利率': compare_with_benchmark(net_margin, '净利率'),
        'ROA': compare_with_benchmark(roa, 'ROA'),
        'ROE': compare_with_benchmark(roe, 'ROE')
    }
    
    # 生成详细结论
    conclusions = []
    
    # ROE分析
    if roe is not None:
        if roe > 0.20:
            conclusions.append({
                'type': 'success',
                'category': 'ROE',
                'text': f'净资产收益率(ROE)为{roe*100:.2f}%，表现优秀',
                'detail': 'ROE超过20%，说明公司能够高效利用股东资本创造利润，具有较强的盈利能力和竞争优势。'
            })
        elif roe > 0.15:
            conclusions.append({
                'type': 'success',
                'category': 'ROE',
                'text': f'净资产收益率(ROE)为{roe*100:.2f}%，表现良好',
                'detail': 'ROE在15%-20%之间，高于大多数上市公司平均水平，显示出较好的资本回报能力。'
            })
        elif roe > 0.08:
            conclusions.append({
                'type': 'info',
                'category': 'ROE',
                'text': f'净资产收益率(ROE)为{roe*100:.2f}%，处于中等水平',
                'detail': 'ROE在8%-15%之间，接近市场平均水平，盈利能力一般，有提升空间。'
            })
        elif roe > 0:
            conclusions.append({
                'type': 'warning',
                'category': 'ROE',
                'text': f'净资产收益率(ROE)为{roe*100:.2f}%，偏低',
                'detail': 'ROE低于8%，资本回报率不理想，需要关注公司的盈利模式和运营效率。'
            })
        else:
            conclusions.append({
                'type': 'error',
                'category': 'ROE',
                'text': f'净资产收益率(ROE)为{roe*100:.2f}%，处于亏损状态',
                'detail': 'ROE为负表示公司亏损，股东权益在减少，需要深入分析亏损原因。'
            })
    
    # 毛利率分析
    if gross_margin is not None:
        if gross_margin > 0.5:
            conclusions.append({
                'type': 'success',
                'category': '毛利率',
                'text': f'毛利率为{gross_margin*100:.2f}%，具有显著竞争优势',
                'detail': '毛利率超过50%，说明产品或服务具有很强的定价权和市场竞争力，可能拥有品牌优势、技术壁垒或垄断地位。'
            })
        elif gross_margin > 0.3:
            conclusions.append({
                'type': 'success',
                'category': '毛利率',
                'text': f'毛利率为{gross_margin*100:.2f}%，产品竞争力较强',
                'detail': '毛利率在30%-50%之间，表明公司产品具有一定的差异化优势，成本控制能力较好。'
            })
        elif gross_margin > 0.15:
            conclusions.append({
                'type': 'info',
                'category': '毛利率',
                'text': f'毛利率为{gross_margin*100:.2f}%，处于正常水平',
                'detail': '毛利率在15%-30%之间，属于大多数制造业和零售业的正常水平，需要通过规模效应或成本优化提升利润。'
            })
        else:
            conclusions.append({
                'type': 'warning',
                'category': '毛利率',
                'text': f'毛利率为{gross_margin*100:.2f}%，利润空间较小',
                'detail': '毛利率低于15%，说明行业竞争激烈或产品同质化严重，需要关注成本控制和产品升级。'
            })
    
    # 净利率分析
    if net_margin is not None:
        if net_margin > 0.15:
            conclusions.append({
                'type': 'success',
                'category': '净利率',
                'text': f'净利率为{net_margin*100:.2f}%，盈利质量高',
                'detail': '净利率超过15%，说明公司不仅毛利高，而且费用控制得当，经营效率出色。'
            })
        elif net_margin > 0.05:
            conclusions.append({
                'type': 'info',
                'category': '净利率',
                'text': f'净利率为{net_margin*100:.2f}%，盈利能力正常',
                'detail': '净利率在5%-15%之间，属于正常盈利水平，可关注费用率是否有优化空间。'
            })
        elif net_margin > 0:
            conclusions.append({
                'type': 'warning',
                'category': '净利率',
                'text': f'净利率为{net_margin*100:.2f}%，盈利能力较弱',
                'detail': '净利率低于5%，利润较薄，抗风险能力弱，需要关注费用支出和运营效率。'
            })
        else:
            conclusions.append({
                'type': 'error',
                'category': '净利率',
                'text': f'净利率为{net_margin*100:.2f}%，处于亏损状态',
                'detail': '净利率为负表示收入无法覆盖成本和费用，需要分析亏损的具体原因。'
            })
    
    # 增长性分析
    if revenue_growth is not None:
        if revenue_growth > 0.3:
            conclusions.append({
                'type': 'success',
                'category': '成长性',
                'text': f'营业收入同比增长{revenue_growth*100:.2f}%，高速增长',
                'detail': '收入增速超过30%，显示公司处于快速扩张期，市场需求旺盛。'
            })
        elif revenue_growth > 0.1:
            conclusions.append({
                'type': 'info',
                'category': '成长性',
                'text': f'营业收入同比增长{revenue_growth*100:.2f}%，稳健增长',
                'detail': '收入增速在10%-30%之间，公司保持良好的增长态势。'
            })
        elif revenue_growth > 0:
            conclusions.append({
                'type': 'info',
                'category': '成长性',
                'text': f'营业收入同比增长{revenue_growth*100:.2f}%，低速增长',
                'detail': '收入增速低于10%，增长动力不足，需要关注市场拓展情况。'
            })
        else:
            conclusions.append({
                'type': 'warning',
                'category': '成长性',
                'text': f'营业收入同比下降{abs(revenue_growth)*100:.2f}%',
                'detail': '收入出现负增长，可能面临市场萎缩、竞争加剧等问题。'
            })
    
    if profit_growth is not None and revenue_growth is not None:
        if profit_growth > revenue_growth:
            conclusions.append({
                'type': 'success',
                'category': '盈利质量',
                'text': '净利润增速高于营收增速，盈利能力提升',
                'detail': f'净利润增长{profit_growth*100:.2f}%，高于营收增长{revenue_growth*100:.2f}%，说明公司运营效率在提升，成本费用控制得当。'
            })
        elif profit_growth < revenue_growth and profit_growth > 0:
            conclusions.append({
                'type': 'info',
                'category': '盈利质量',
                'text': '净利润增速低于营收增速',
                'detail': f'净利润增长{profit_growth*100:.2f}%，低于营收增长{revenue_growth*100:.2f}%，可能存在成本上升或费用增加的情况。'
            })
    
    # 杜邦分析结论
    dupont_analysis = None
    if net_margin and asset_turnover and equity_multiplier:
        dupont_analysis = {
            'net_margin': net_margin,
            'asset_turnover': asset_turnover,
            'equity_multiplier': equity_multiplier,
            'roe': dupont_roe,
            'conclusion': ''
        }
        
        # 判断ROE的主要驱动因素
        drivers = []
        if net_margin > 0.1:
            drivers.append('高净利率')
        if asset_turnover > 0.8:
            drivers.append('高周转率')
        if equity_multiplier > 2.5:
            drivers.append('高财务杠杆')
        
        if drivers:
            dupont_analysis['conclusion'] = f"ROE主要由{', '.join(drivers)}驱动"
        else:
            dupont_analysis['conclusion'] = "各项指标较为均衡"
    
    result = {
        'core_data': {
            '营业收入': {'value': revenue, 'growth': revenue_growth},
            '营业成本': {'value': cost, 'growth': None},
            '毛利润': {'value': gross_profit, 'growth': None},
            '营业利润': {'value': operating_profit, 'growth': None},
            '净利润': {'value': net_profit, 'growth': profit_growth},
            '总资产': {'value': total_assets, 'growth': None},
            '所有者权益': {'value': equity, 'growth': None}
        },
        'ratios': {
            '毛利率': gross_margin,
            '净利率': net_margin,
            '营业利润率': operating_margin,
            '成本费用率': cost_ratio,
            'ROA(总资产收益率)': roa,
            'ROE(净资产收益率)': roe
        },
        'benchmarks': benchmarks,
        'trends': {
            'revenue': revenue_trend,
            'profit': profit_trend
        },
        'dupont': dupont_analysis,
        'conclusions': conclusions,
        'summary': {
            'profitability_score': 0,
            'growth_score': 0,
            'overall_comment': ''
        }
    }
    
    # 计算综合评分
    if roe and roe > 0.1:
        result['summary']['profitability_score'] += 2
    elif roe and roe > 0.05:
        result['summary']['profitability_score'] += 1
    
    if gross_margin and gross_margin > 0.3:
        result['summary']['profitability_score'] += 2
    elif gross_margin and gross_margin > 0.15:
        result['summary']['profitability_score'] += 1
    
    if revenue_growth and revenue_growth > 0.15:
        result['summary']['growth_score'] += 2
    elif revenue_growth and revenue_growth > 0:
        result['summary']['growth_score'] += 1
    
    if profit_growth and profit_growth > revenue_growth if revenue_growth else False:
        result['summary']['growth_score'] += 1
    
    total_score = result['summary']['profitability_score'] + result['summary']['growth_score']
    if total_score >= 6:
        result['summary']['overall_comment'] = '公司盈利能力优秀，成长性良好，具有较强的投资价值'
    elif total_score >= 4:
        result['summary']['overall_comment'] = '公司盈利能力和成长性表现良好，值得关注'
    elif total_score >= 2:
        result['summary']['overall_comment'] = '公司盈利能力一般，需要进一步观察发展趋势'
    else:
        result['summary']['overall_comment'] = '公司盈利能力较弱，投资需谨慎'
    
    return jsonify(result)


@app.route('/api/overall', methods=['POST'])
def overall_analysis():
    """总体运行情况分析 - 增强版"""
    data = request.json
    stock_code = data.get('code')
    report_date = data.get('date')
    
    data_dict = get_data_dict(stock_code, report_date)
    dates = db.get_report_dates(stock_code)[:8]
    
    # 基础指标
    total_assets = get_val(data_dict, '总资产')
    total_liab = get_val(data_dict, '总负债')
    equity = get_val(data_dict, '所有者权益')
    current_assets = get_val(data_dict, '流动资产')
    current_liab = get_val(data_dict, '流动负债')
    cash = get_val(data_dict, '货币资金')
    inventory = get_val(data_dict, '存货')
    receivables = get_val(data_dict, '应收账款')
    fixed_assets = get_val(data_dict, '固定资产')
    revenue = get_val(data_dict, '营业收入')
    net_profit = get_val(data_dict, '净利润')
    op_cashflow = get_val(data_dict, '经营活动现金流净额')
    invest_cashflow = get_val(data_dict, '投资活动现金流净额')
    finance_cashflow = get_val(data_dict, '筹资活动现金流净额')
    
    quick_assets = current_assets - inventory if current_assets and inventory else None
    non_current_assets = total_assets - current_assets if total_assets and current_assets else None
    
    # 计算各类比率
    debt_ratio = safe_divide(total_liab, total_assets)
    current_ratio = safe_divide(current_assets, current_liab)
    quick_ratio = safe_divide(quick_assets, current_liab)
    cash_ratio = safe_divide(cash, current_liab)
    equity_ratio = safe_divide(equity, total_assets)
    
    asset_turnover = safe_divide(revenue, total_assets)
    receivables_turnover = safe_divide(revenue, receivables)
    inventory_turnover = safe_divide(revenue, inventory)
    fixed_asset_turnover = safe_divide(revenue, fixed_assets)
    
    # 应收账款周转天数
    receivables_days = safe_divide(365, receivables_turnover) if receivables_turnover else None
    inventory_days = safe_divide(365, inventory_turnover) if inventory_turnover else None
    
    # 现金流分析
    cash_to_profit = safe_divide(op_cashflow, net_profit) if net_profit and net_profit > 0 else None
    cash_to_revenue = safe_divide(op_cashflow, revenue)
    cash_to_debt = safe_divide(op_cashflow, total_liab)
    
    # 获取趋势数据
    def get_ratio_trend(calc_func):
        trend = []
        for d in reversed(dates):
            dd = get_data_dict(stock_code, d)
            val = calc_func(dd)
            trend.append({'date': d, 'value': val})
        return trend
    
    debt_ratio_trend = get_ratio_trend(lambda dd: safe_divide(get_val(dd, '总负债'), get_val(dd, '总资产')))
    current_ratio_trend = get_ratio_trend(lambda dd: safe_divide(get_val(dd, '流动资产'), get_val(dd, '流动负债')))
    
    # 与行业基准比较
    benchmarks = {
        '资产负债率': compare_with_benchmark(debt_ratio, '资产负债率'),
        '流动比率': compare_with_benchmark(current_ratio, '流动比率'),
        '速动比率': compare_with_benchmark(quick_ratio, '速动比率'),
        '总资产周转率': compare_with_benchmark(asset_turnover, '总资产周转率')
    }
    
    # 资产结构分析
    asset_structure = {
        '流动资产占比': safe_divide(current_assets, total_assets),
        '固定资产占比': safe_divide(fixed_assets, total_assets),
        '货币资金占比': safe_divide(cash, total_assets),
        '应收账款占比': safe_divide(receivables, total_assets),
        '存货占比': safe_divide(inventory, total_assets)
    }
    
    # 负债结构分析
    liability_structure = {
        '流动负债占比': safe_divide(current_liab, total_liab) if total_liab else None,
        '长期负债占比': safe_divide(total_liab - current_liab, total_liab) if total_liab and current_liab else None
    }
    
    # 生成详细结论
    conclusions = []
    risk_warnings = []
    
    # 资产负债率分析
    if debt_ratio is not None:
        if debt_ratio < 0.3:
            conclusions.append({
                'type': 'info',
                'category': '资本结构',
                'text': f'资产负债率为{debt_ratio*100:.2f}%，财务杠杆使用保守',
                'detail': '负债水平很低，财务风险小，但可能未充分利用财务杠杆提升股东回报。适合风险厌恶型投资者。'
            })
        elif debt_ratio < 0.5:
            conclusions.append({
                'type': 'success',
                'category': '资本结构',
                'text': f'资产负债率为{debt_ratio*100:.2f}%，资本结构稳健',
                'detail': '负债水平适中，在控制风险的同时适度使用了财务杠杆，资本结构较为健康。'
            })
        elif debt_ratio < 0.7:
            conclusions.append({
                'type': 'warning',
                'category': '资本结构',
                'text': f'资产负债率为{debt_ratio*100:.2f}%，负债水平偏高',
                'detail': '负债比例较高，需要关注偿债压力和利息支出对利润的影响。'
            })
            risk_warnings.append('负债水平偏高，关注偿债风险')
        else:
            conclusions.append({
                'type': 'error',
                'category': '资本结构',
                'text': f'资产负债率为{debt_ratio*100:.2f}%，财务风险较大',
                'detail': '负债水平过高，存在较大的财务风险，一旦经营出现问题可能面临偿债困难。'
            })
            risk_warnings.append('负债率过高，存在较大财务风险')
    
    # 流动性分析
    if current_ratio is not None:
        if current_ratio >= 2:
            conclusions.append({
                'type': 'success',
                'category': '短期偿债',
                'text': f'流动比率为{current_ratio:.2f}，短期偿债能力强',
                'detail': '流动资产充足，能够覆盖短期债务，短期内不存在偿债压力。'
            })
        elif current_ratio >= 1.5:
            conclusions.append({
                'type': 'success',
                'category': '短期偿债',
                'text': f'流动比率为{current_ratio:.2f}，短期偿债能力良好',
                'detail': '流动比率处于合理区间，短期偿债能力较好。'
            })
        elif current_ratio >= 1:
            conclusions.append({
                'type': 'info',
                'category': '短期偿债',
                'text': f'流动比率为{current_ratio:.2f}，短期偿债能力一般',
                'detail': '流动资产刚好覆盖流动负债，偿债能力一般，需要关注现金流状况。'
            })
        else:
            conclusions.append({
                'type': 'error',
                'category': '短期偿债',
                'text': f'流动比率为{current_ratio:.2f}，存在短期偿债风险',
                'detail': '流动资产不足以覆盖流动负债，可能面临短期偿债困难。'
            })
            risk_warnings.append('流动比率低于1，短期偿债压力大')
    
    # 速动比率分析
    if quick_ratio is not None:
        if quick_ratio >= 1:
            conclusions.append({
                'type': 'success',
                'category': '速动能力',
                'text': f'速动比率为{quick_ratio:.2f}，速动资产充足',
                'detail': '扣除存货后的速动资产仍能覆盖流动负债，即使存货无法快速变现也能应对短期债务。'
            })
        elif quick_ratio >= 0.7:
            conclusions.append({
                'type': 'info',
                'category': '速动能力',
                'text': f'速动比率为{quick_ratio:.2f}，速动能力一般',
                'detail': '速动比率略低，对存货变现能力有一定依赖。'
            })
        else:
            conclusions.append({
                'type': 'warning',
                'category': '速动能力',
                'text': f'速动比率为{quick_ratio:.2f}，速动资产不足',
                'detail': '速动资产较少，短期偿债较依赖存货变现或外部融资。'
            })
    
    # 营运能力分析
    if asset_turnover is not None:
        if asset_turnover > 1:
            conclusions.append({
                'type': 'success',
                'category': '营运效率',
                'text': f'总资产周转率为{asset_turnover:.2f}次，资产运营效率高',
                'detail': '资产周转速度快，说明公司能够高效利用资产创造收入。'
            })
        elif asset_turnover > 0.5:
            conclusions.append({
                'type': 'info',
                'category': '营运效率',
                'text': f'总资产周转率为{asset_turnover:.2f}次，资产运营效率正常',
                'detail': '资产周转速度处于正常水平。'
            })
        else:
            conclusions.append({
                'type': 'warning',
                'category': '营运效率',
                'text': f'总资产周转率为{asset_turnover:.2f}次，资产运营效率偏低',
                'detail': '资产周转较慢，可能存在资产闲置或运营效率不高的问题。'
            })
    
    # 应收账款分析
    if receivables_days is not None:
        if receivables_days < 30:
            conclusions.append({
                'type': 'success',
                'category': '应收管理',
                'text': f'应收账款周转天数为{receivables_days:.0f}天，回款速度快',
                'detail': '应收账款回收迅速，现金流转效率高，坏账风险低。'
            })
        elif receivables_days < 90:
            conclusions.append({
                'type': 'info',
                'category': '应收管理',
                'text': f'应收账款周转天数为{receivables_days:.0f}天，回款速度正常',
                'detail': '应收账款周转处于正常水平。'
            })
        else:
            conclusions.append({
                'type': 'warning',
                'category': '应收管理',
                'text': f'应收账款周转天数为{receivables_days:.0f}天，回款速度较慢',
                'detail': '应收账款回收周期长，需要关注客户信用状况和坏账风险。'
            })
            risk_warnings.append('应收账款周转慢，注意坏账风险')
    
    # 存货分析
    if inventory_days is not None:
        if inventory_days < 60:
            conclusions.append({
                'type': 'success',
                'category': '存货管理',
                'text': f'存货周转天数为{inventory_days:.0f}天，存货管理效率高',
                'detail': '存货周转快，库存积压风险低，资金占用少。'
            })
        elif inventory_days < 180:
            conclusions.append({
                'type': 'info',
                'category': '存货管理',
                'text': f'存货周转天数为{inventory_days:.0f}天，存货周转正常',
                'detail': '存货周转处于正常水平。'
            })
        else:
            conclusions.append({
                'type': 'warning',
                'category': '存货管理',
                'text': f'存货周转天数为{inventory_days:.0f}天，存货周转较慢',
                'detail': '存货积压较多，可能面临跌价风险，占用较多资金。'
            })
            risk_warnings.append('存货周转慢，注意跌价风险')
    
    # 现金流分析
    if op_cashflow is not None:
        if op_cashflow > 0:
            if cash_to_profit and cash_to_profit > 1:
                conclusions.append({
                    'type': 'success',
                    'category': '现金流',
                    'text': f'经营现金流净额为正，且高于净利润',
                    'detail': f'经营活动产生的现金流是净利润的{cash_to_profit:.2f}倍，盈利质量高，利润含金量足。'
                })
            elif cash_to_profit and cash_to_profit > 0:
                conclusions.append({
                    'type': 'info',
                    'category': '现金流',
                    'text': f'经营现金流净额为正，但低于净利润',
                    'detail': f'经营现金流是净利润的{cash_to_profit:.2f}倍，需要关注应收账款回收情况。'
                })
            else:
                conclusions.append({
                    'type': 'success',
                    'category': '现金流',
                    'text': '经营现金流净额为正',
                    'detail': '经营活动能够产生正向现金流，主业造血能力正常。'
                })
        else:
            conclusions.append({
                'type': 'error',
                'category': '现金流',
                'text': '经营现金流净额为负',
                'detail': '经营活动消耗现金，需要依赖融资或投资回收来维持运营，需要重点关注。'
            })
            risk_warnings.append('经营现金流为负，关注资金链风险')
    
    # 现金流组合分析
    cashflow_pattern = None
    if op_cashflow is not None and invest_cashflow is not None and finance_cashflow is not None:
        op_sign = '+' if op_cashflow > 0 else '-'
        inv_sign = '+' if invest_cashflow > 0 else '-'
        fin_sign = '+' if finance_cashflow > 0 else '-'
        pattern = f"{op_sign}{inv_sign}{fin_sign}"
        
        pattern_desc = {
            '+++': {'name': '全面扩张型', 'desc': '经营、投资、筹资均为正，公司处于快速扩张期'},
            '++-': {'name': '稳健发展型', 'desc': '经营造血，投资扩张，偿还债务，财务状况健康'},
            '+-+': {'name': '扩张融资型', 'desc': '经营造血，大力投资，同时融资支持，处于扩张期'},
            '+--': {'name': '成熟稳健型', 'desc': '经营造血充足，用于投资和偿债，财务状况优秀'},
            '-++': {'name': '投资收缩型', 'desc': '经营消耗现金，靠出售资产和融资维持'},
            '-+-': {'name': '收缩偿债型', 'desc': '经营消耗现金，出售资产偿债，可能面临困境'},
            '--+': {'name': '融资维持型', 'desc': '经营和投资都消耗现金，依赖融资维持，风险较高'},
            '---': {'name': '全面收缩型', 'desc': '各项活动都消耗现金，可能面临严重困境'}
        }
        
        cashflow_pattern = pattern_desc.get(pattern, {'name': '其他类型', 'desc': ''})
        cashflow_pattern['pattern'] = pattern
    
    # 计算综合评分
    score = 0
    max_score = 10
    
    if debt_ratio is not None and debt_ratio < 0.6:
        score += 2
    elif debt_ratio is not None and debt_ratio < 0.7:
        score += 1
    
    if current_ratio is not None and current_ratio >= 1.5:
        score += 2
    elif current_ratio is not None and current_ratio >= 1:
        score += 1
    
    if quick_ratio is not None and quick_ratio >= 1:
        score += 1
    
    if op_cashflow is not None and op_cashflow > 0:
        score += 2
        if cash_to_profit and cash_to_profit > 1:
            score += 1
    
    if asset_turnover is not None and asset_turnover > 0.5:
        score += 1
    
    # 评级
    if score >= 8:
        rating = '优秀'
        rating_desc = '公司财务状况优秀，各项指标表现良好，风险可控'
    elif score >= 6:
        rating = '良好'
        rating_desc = '公司财务状况良好，整体运营稳健'
    elif score >= 4:
        rating = '一般'
        rating_desc = '公司财务状况一般，部分指标需要关注'
    else:
        rating = '较差'
        rating_desc = '公司财务状况较差，存在一定风险'
    
    result = {
        'structure': {
            '总资产': total_assets,
            '总负债': total_liab,
            '所有者权益': equity,
            '流动资产': current_assets,
            '非流动资产': non_current_assets,
            '资产负债率': debt_ratio,
            '权益比率': equity_ratio
        },
        'asset_structure': asset_structure,
        'liability_structure': liability_structure,
        'solvency': {
            '流动资产': current_assets,
            '流动负债': current_liab,
            '速动资产': quick_assets,
            '货币资金': cash,
            '流动比率': current_ratio,
            '速动比率': quick_ratio,
            '现金比率': cash_ratio
        },
        'operation': {
            '营业收入': revenue,
            '应收账款': receivables,
            '存货': inventory,
            '固定资产': fixed_assets,
            '总资产周转率': asset_turnover,
            '应收账款周转率': receivables_turnover,
            '存货周转率': inventory_turnover,
            '固定资产周转率': fixed_asset_turnover,
            '应收账款周转天数': receivables_days,
            '存货周转天数': inventory_days
        },
        'cashflow': {
            '货币资金': cash,
            '经营活动现金流净额': op_cashflow,
            '投资活动现金流净额': invest_cashflow,
            '筹资活动现金流净额': finance_cashflow,
            '现金流净利润比': cash_to_profit,
            '现金流收入比': cash_to_revenue,
            '现金流负债比': cash_to_debt
        },
        'cashflow_pattern': cashflow_pattern,
        'benchmarks': benchmarks,
        'trends': {
            'debt_ratio': debt_ratio_trend,
            'current_ratio': current_ratio_trend
        },
        'conclusions': conclusions,
        'risk_warnings': risk_warnings,
        'score': score,
        'max_score': max_score,
        'rating': rating,
        'rating_desc': rating_desc
    }
    
    return jsonify(result)


@app.route('/api/indicators')
def get_indicators():
    """获取所有可用指标"""
    return jsonify({'indicators': list(INDICATOR_MAP.keys())})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
