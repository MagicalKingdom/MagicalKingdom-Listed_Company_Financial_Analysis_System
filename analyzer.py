"""
财务数据分析模块 - 提供多维度财务分析功能
"""
from db_handler import DatabaseManager
from decimal import Decimal, InvalidOperation


# 财务指标项目编号映射（基于新浪财经报表结构）
# BS = 资产负债表, PS = 利润表, CF = 现金流量表
INDICATOR_MAP = {
    # 资产负债表项目
    '总资产': 'BS-94',
    '总负债': 'BS-46',
    '所有者权益': 'BS-81',
    '流动资产': 'BS-16',
    '流动负债': 'BS-33',
    '货币资金': 'BS-3',
    '应收账款': 'BS-6',
    '存货': 'BS-15',
    '固定资产': 'BS-22',
    '非流动资产': 'BS-47',
    
    # 利润表项目
    '营业收入': 'PS-2',
    '营业成本': 'PS-3',
    '营业利润': 'PS-16',
    '利润总额': 'PS-19',
    '净利润': 'PS-22',
    '毛利润': 'PS-4',
    
    # 现金流量表项目
    '经营活动现金流入': 'CF-9',
    '经营活动现金流出': 'CF-18',
    '经营活动现金流净额': 'CF-19',
    '投资活动现金流净额': 'CF-30',
    '筹资活动现金流净额': 'CF-40',
}


class FinancialAnalyzer:
    """财务分析器"""
    
    def __init__(self):
        self._db = DatabaseManager()
    
    def _parse_value(self, val):
        """解析数值"""
        try:
            return Decimal(str(val))
        except (InvalidOperation, ValueError):
            return Decimal('0')
    
    def _get_indicator_value(self, data_dict, indicator_name):
        """获取指标值"""
        item_id = INDICATOR_MAP.get(indicator_name)
        if not item_id or item_id not in data_dict:
            return None
        return self._parse_value(data_dict[item_id])
    
    def _build_data_dict(self, stock_code, report_date):
        """构建数据字典 {项目编号: 值}"""
        rows = self._db.query_financial_data(stock_code, report_date)
        return {row[0]: row[1] for row in rows}
    
    def _safe_divide(self, numerator, denominator, precision=4):
        """安全除法，避免除零"""
        if denominator is None or denominator == 0:
            return None
        if numerator is None:
            return None
        return round(float(numerator / denominator), precision)
    
    def _format_ratio(self, val, as_percent=True):
        """格式化比率"""
        if val is None:
            return "N/A"
        if as_percent:
            return f"{val * 100:.2f}%"
        return f"{val:.4f}"
    
    def _format_amount(self, val):
        """格式化金额（万元）"""
        if val is None:
            return "N/A"
        return f"{float(val) / 10000:,.2f} 万元"
    
    def _print_separator(self, char='=', length=50):
        """打印分隔线"""
        print(char * length)
    
    def _print_header(self, title):
        """打印标题"""
        self._print_separator()
        print(f"  {title}")
        self._print_separator()
    
    # ==================== 1. 自定义分析 ====================
    def custom_analysis(self, stock_code, report_date):
        """自定义分析 - 用户选择查看的指标"""
        data = self._build_data_dict(stock_code, report_date)
        if not data:
            print("未找到该股票的财务数据")
            return
        
        self._print_header(f"自定义分析 - {stock_code} ({report_date})")
        
        print("\n可选指标：")
        indicators = list(INDICATOR_MAP.keys())
        idx = 1
        while idx <= len(indicators):
            name = indicators[idx - 1]
            print(f"  {idx}. {name}")
            idx += 1
        
        print("\n请输入要查看的指标编号（多个用逗号分隔，如: 1,3,5）：")
        choice = input("> ")
        
        selected_indices = []
        for s in choice.split(','):
            s = s.strip()
            if s.isdigit():
                num = int(s)
                if 1 <= num <= len(indicators):
                    selected_indices.append(num - 1)
        
        if not selected_indices:
            print("未选择有效指标")
            return
        
        print("\n" + "-" * 40)
        print("  指标名称                    数值")
        print("-" * 40)
        
        for i in selected_indices:
            name = indicators[i]
            val = self._get_indicator_value(data, name)
            formatted = self._format_amount(val) if val else "N/A"
            print(f"  {name:<20} {formatted:>15}")
        
        print("-" * 40)
    
    # ==================== 2. 获利能力分析 ====================
    def profitability_analysis(self, stock_code, report_date):
        """获利能力分析"""
        data = self._build_data_dict(stock_code, report_date)
        if not data:
            print("未找到该股票的财务数据")
            return
        
        self._print_header(f"获利能力分析 - {stock_code} ({report_date})")
        
        # 获取关键指标
        revenue = self._get_indicator_value(data, '营业收入')
        cost = self._get_indicator_value(data, '营业成本')
        net_profit = self._get_indicator_value(data, '净利润')
        total_assets = self._get_indicator_value(data, '总资产')
        equity = self._get_indicator_value(data, '所有者权益')
        operating_profit = self._get_indicator_value(data, '营业利润')
        
        # 计算获利能力指标
        gross_profit = revenue - cost if revenue and cost else None
        gross_margin = self._safe_divide(gross_profit, revenue)
        net_margin = self._safe_divide(net_profit, revenue)
        roa = self._safe_divide(net_profit, total_assets)
        roe = self._safe_divide(net_profit, equity)
        operating_margin = self._safe_divide(operating_profit, revenue)
        
        print("\n【核心数据】")
        print(f"  营业收入：{self._format_amount(revenue)}")
        print(f"  营业成本：{self._format_amount(cost)}")
        print(f"  净利润：{self._format_amount(net_profit)}")
        print(f"  总资产：{self._format_amount(total_assets)}")
        print(f"  所有者权益：{self._format_amount(equity)}")
        
        print("\n【获利能力指标】")
        print(f"  毛利率：{self._format_ratio(gross_margin)}")
        print(f"  净利率：{self._format_ratio(net_margin)}")
        print(f"  营业利润率：{self._format_ratio(operating_margin)}")
        print(f"  总资产收益率(ROA)：{self._format_ratio(roa)}")
        print(f"  净资产收益率(ROE)：{self._format_ratio(roe)}")
        
        print("\n【分析结论】")
        if roe is not None:
            if roe > 0.15:
                print("  ★ ROE优秀(>15%)，公司盈利能力强")
            elif roe > 0.08:
                print("  ★ ROE良好(8%-15%)，公司盈利能力中等")
            elif roe > 0:
                print("  ★ ROE偏低(<8%)，公司盈利能力较弱")
            else:
                print("  ★ ROE为负，公司处于亏损状态")
        
        if gross_margin is not None:
            if gross_margin > 0.4:
                print("  ★ 毛利率高(>40%)，产品竞争力强")
            elif gross_margin > 0.2:
                print("  ★ 毛利率中等(20%-40%)")
            else:
                print("  ★ 毛利率偏低(<20%)，成本控制压力大")
        
        self._print_separator('-')
    
    # ==================== 3. 总体运行情况分析 ====================
    def overall_analysis(self, stock_code, report_date):
        """总体运行情况分析"""
        data = self._build_data_dict(stock_code, report_date)
        if not data:
            print("未找到该股票的财务数据")
            return
        
        self._print_header(f"总体运行情况分析 - {stock_code} ({report_date})")
        
        # 获取关键指标
        total_assets = self._get_indicator_value(data, '总资产')
        total_liab = self._get_indicator_value(data, '总负债')
        equity = self._get_indicator_value(data, '所有者权益')
        current_assets = self._get_indicator_value(data, '流动资产')
        current_liab = self._get_indicator_value(data, '流动负债')
        cash = self._get_indicator_value(data, '货币资金')
        inventory = self._get_indicator_value(data, '存货')
        receivables = self._get_indicator_value(data, '应收账款')
        revenue = self._get_indicator_value(data, '营业收入')
        net_profit = self._get_indicator_value(data, '净利润')
        op_cashflow = self._get_indicator_value(data, '经营活动现金流净额')
        
        # 计算财务比率
        debt_ratio = self._safe_divide(total_liab, total_assets)
        current_ratio = self._safe_divide(current_assets, current_liab)
        quick_assets = current_assets - inventory if current_assets and inventory else None
        quick_ratio = self._safe_divide(quick_assets, current_liab)
        cash_ratio = self._safe_divide(cash, current_liab)
        asset_turnover = self._safe_divide(revenue, total_assets)
        receivables_turnover = self._safe_divide(revenue, receivables)
        inventory_turnover = self._safe_divide(revenue, inventory)
        
        # === 资产负债结构 ===
        print("\n【一、资产负债结构】")
        print(f"  总资产：{self._format_amount(total_assets)}")
        print(f"  总负债：{self._format_amount(total_liab)}")
        print(f"  所有者权益：{self._format_amount(equity)}")
        print(f"  资产负债率：{self._format_ratio(debt_ratio)}")
        
        if debt_ratio is not None:
            if debt_ratio < 0.4:
                print("  → 负债水平低，财务风险小，但可能财务杠杆利用不足")
            elif debt_ratio < 0.6:
                print("  → 负债水平适中，财务结构较为健康")
            elif debt_ratio < 0.7:
                print("  → 负债水平偏高，需关注偿债能力")
            else:
                print("  → 负债水平过高，存在较大财务风险")
        
        # === 偿债能力 ===
        print("\n【二、偿债能力】")
        print(f"  流动资产：{self._format_amount(current_assets)}")
        print(f"  流动负债：{self._format_amount(current_liab)}")
        print(f"  流动比率：{self._format_ratio(current_ratio, False)}")
        print(f"  速动比率：{self._format_ratio(quick_ratio, False)}")
        print(f"  现金比率：{self._format_ratio(cash_ratio, False)}")
        
        if current_ratio is not None:
            if current_ratio >= 2:
                print("  → 流动比率>=2，短期偿债能力强")
            elif current_ratio >= 1:
                print("  → 流动比率1-2，短期偿债能力一般")
            else:
                print("  → 流动比率<1，短期偿债压力大")
        
        # === 营运能力 ===
        print("\n【三、营运能力】")
        print(f"  营业收入：{self._format_amount(revenue)}")
        print(f"  应收账款：{self._format_amount(receivables)}")
        print(f"  存货：{self._format_amount(inventory)}")
        print(f"  总资产周转率：{self._format_ratio(asset_turnover, False)}")
        print(f"  应收账款周转率：{self._format_ratio(receivables_turnover, False)}")
        print(f"  存货周转率：{self._format_ratio(inventory_turnover, False)}")
        
        # === 现金流状况 ===
        print("\n【四、现金流状况】")
        print(f"  货币资金：{self._format_amount(cash)}")
        print(f"  经营活动现金流净额：{self._format_amount(op_cashflow)}")
        
        if op_cashflow is not None and net_profit is not None:
            if op_cashflow > 0 and net_profit > 0:
                ratio = self._safe_divide(op_cashflow, net_profit)
                print(f"  现金流/净利润比：{self._format_ratio(ratio, False)}")
                if ratio and ratio > 1:
                    print("  → 经营现金流充裕，盈利质量高")
                else:
                    print("  → 经营现金流低于净利润，需关注应收账款回收")
            elif op_cashflow < 0:
                print("  → 经营现金流为负，需关注资金链风险")
        
        # === 综合评价 ===
        print("\n【五、综合评价】")
        score = 0
        comments = []
        
        if debt_ratio is not None and debt_ratio < 0.6:
            score += 1
            comments.append("财务结构稳健")
        if current_ratio is not None and current_ratio >= 1.5:
            score += 1
            comments.append("短期偿债能力良好")
        if op_cashflow is not None and op_cashflow > 0:
            score += 1
            comments.append("经营现金流为正")
        if net_profit is not None and net_profit > 0:
            score += 1
            comments.append("盈利状态")
        
        if score >= 3:
            print(f"  综合评级：★★★ 良好")
        elif score >= 2:
            print(f"  综合评级：★★ 一般")
        else:
            print(f"  综合评级：★ 需关注")
        
        if comments:
            print(f"  主要优势：{', '.join(comments)}")
        
        self._print_separator()


class AnalysisMenu:
    """分析功能菜单"""
    
    def __init__(self):
        self._analyzer = FinancialAnalyzer()
        self._db = DatabaseManager()
    
    def _select_stock(self):
        """选择股票"""
        codes = self._db.get_all_stock_codes()
        if not codes:
            print("数据库中暂无股票数据，请先下载数据")
            return None
        
        print("\n已有数据的股票：")
        for c in codes:
            print(f"  {c}")
        
        code = input("\n请输入要分析的股票代码：")
        if code not in codes:
            print("该股票暂无数据")
            return None
        return code
    
    def _select_report_date(self, stock_code):
        """选择报告日期"""
        dates = self._db.get_report_dates(stock_code)
        if not dates:
            print("该股票暂无报告数据")
            return None
        
        print("\n可用报告日期：")
        idx = 1
        for d in dates[:10]:  # 最多显示10个
            print(f"  {idx}. {d}")
            idx += 1
        
        choice = input("\n请选择报告日期编号（直接回车选择最新）：")
        if not choice:
            return dates[0]
        
        if choice.isdigit():
            num = int(choice)
            if 1 <= num <= len(dates):
                return dates[num - 1]
        
        print("无效选择，使用最新日期")
        return dates[0]
    
    def show(self):
        """显示分析菜单"""
        stock_code = self._select_stock()
        if not stock_code:
            return
        
        report_date = self._select_report_date(stock_code)
        if not report_date:
            return
        
        while True:
            print("\n" + "=" * 40)
            print("  财务分析功能")
            print("=" * 40)
            print("  1. 自定义分析")
            print("  2. 获利能力分析")
            print("  3. 总体运行情况分析")
            print("  0. 返回主菜单")
            print("-" * 40)
            
            choice = input("请选择分析类型：")
            
            if choice == '1':
                self._analyzer.custom_analysis(stock_code, report_date)
            elif choice == '2':
                self._analyzer.profitability_analysis(stock_code, report_date)
            elif choice == '3':
                self._analyzer.overall_analysis(stock_code, report_date)
            elif choice == '0':
                break
            else:
                print("无效选项")
            
            input("\n按回车键继续...")
