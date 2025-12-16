"""
股票数据采集模块 - 负责从新浪财经抓取上市公司数据
"""
import re
from datetime import datetime
from decimal import Decimal, getcontext
import pandas as pd

# 金额精度设置
getcontext().prec = 22

# 数据类型标识
TYPE_FINANCE = 'FD'
TYPE_COMPANY = 'CI'
TYPE_IPO = 'II'


class DataCleaner:
    """数据清洗工具类"""
    
    @staticmethod
    def sanitize_text(val):
        """清理文本中的特殊字符"""
        if pd.isna(val):
            return '--'
        if not isinstance(val, str):
            return val
        chars_to_remove = ['\r\n', ' ', '"', "'"]
        result = val
        for ch in chars_to_remove:
            result = result.replace(ch, '')
        return result
    
    @staticmethod
    def parse_date(date_str, fmt='%Y-%m-%d'):
        """解析日期字符串"""
        return datetime.strptime(str(date_str), fmt).date()
    
    @staticmethod
    def parse_money(val):
        """解析金额，保留两位小数"""
        return Decimal(val).quantize(Decimal('0.00'))
    
    @staticmethod
    def extract_number(text):
        """从文本中提取数字"""
        nums = re.findall(r'\d+', text)
        return nums[0] if nums else '0'


class FinanceReportFetcher:
    """财务报表数据抓取器"""
    
    REPORT_CONFIG = {
        1: ('BalanceSheet', '资产负债表', 'BS'),
        2: ('ProfitStatement', '利润表', 'PS'),
        3: ('CashFlow', '现金流量表', 'CF'),
    }
    
    def __init__(self, stock_code):
        self._code = stock_code
        self._cleaner = DataCleaner()
    
    def _build_url(self, report_type):
        """构建下载链接"""
        base = 'http://money.finance.sina.com.cn/corp/go.php/vDOWN_'
        return f"{base}{report_type}/displaytype/4/stockid/{self._code}/ctrl/all.phtml"
    
    def _transform_to_records(self, df, prefix):
        """将二维表格转换为记录列表"""
        records = []
        rows, cols = df.shape
        col_idx = 1
        while col_idx < cols - 2:
            row_idx = 2
            while row_idx < rows:
                cell_val = df.iloc[row_idx, col_idx]
                if pd.isnull(cell_val) or cell_val == '0':
                    row_idx += 1
                    continue
                item_id = f"{prefix}-{row_idx}"
                report_dt = self._cleaner.parse_date(str(df.iloc[0, col_idx]), '%Y%m%d')
                amount = self._cleaner.parse_money(cell_val)
                records.append([self._code, report_dt, item_id, amount])
                row_idx += 1
            col_idx += 1
        return records
    
    def crawl(self):
        """抓取全部财务报表"""
        all_records = []
        for idx in range(1, 4):
            rpt_type, rpt_name, prefix = self.REPORT_CONFIG[idx]
            print(f"正在获取{self._code}的{rpt_name}...")
            url = self._build_url(rpt_type)
            df = pd.read_csv(url, encoding='gbk', header=None, sep='\t')
            print("获取完成")
            print("正在解析数据...")
            records = self._transform_to_records(df, prefix)
            all_records.extend(records)
            print("解析完成")
        return [TYPE_FINANCE, all_records]


class CompanyInfoFetcher:
    """公司基本信息抓取器"""
    
    FIELD_MAPPING = [
        ('公司代码', None, None),
        ('公司名称', 0, 1),
        ('公司英文名称', 1, 1),
        ('上市市场', 2, 1),
        ('上市日期', 2, 3),
        ('发行价格', 3, 1),
        ('主承销商', 3, 3),
        ('成立日期', 4, 1),
        ('注册资本_万元', 4, 3),
        ('机构类型', 5, 1),
        ('组织形式', 5, 3),
        ('董事会秘书', 6, 1),
        ('公司电话', 6, 3),
        ('董秘电话', 8, 1),
        ('公司传真', 8, 3),
        ('董秘传真', 10, 1),
        ('公司电子邮箱', 10, 3),
        ('董秘电子邮箱', 12, 1),
        ('公司网址', 12, 3),
        ('邮政编码', 14, 1),
        ('信息披露网址', 14, 3),
        ('证券简称更名历史', 16, 1),
        ('注册地址', 17, 1),
        ('办公地址', 18, 1),
        ('公司简介', 19, 1),
        ('经营范围', 20, 1),
    ]
    
    def __init__(self, stock_code):
        self._code = stock_code
        self._cleaner = DataCleaner()
    
    def _build_url(self):
        """构建请求地址"""
        return f'https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpInfo/stockid/{self._code}.phtml'
    
    def _extract_field(self, df, row, col, field_name):
        """提取并处理字段值"""
        raw_val = df.iloc[row, col]
        if field_name in ('上市日期', '成立日期'):
            return self._cleaner.parse_date(str(raw_val))
        elif field_name == '发行价格':
            return self._cleaner.parse_money(raw_val)
        elif field_name == '注册资本_万元':
            num_str = self._cleaner.extract_number(raw_val)
            return self._cleaner.parse_money(num_str)
        else:
            return self._cleaner.sanitize_text(raw_val)
    
    def crawl(self):
        """抓取公司信息"""
        print(f"正在获取{self._code}的公司资料...")
        url = self._build_url()
        tables = pd.read_html(url)
        df = tables[3]
        print("获取完成")
        
        print("正在解析数据...")
        values = []
        for field_name, row, col in self.FIELD_MAPPING:
            if row is None:
                values.append(self._code)
            else:
                val = self._extract_field(df, row, col, field_name)
                values.append(val)
        print("解析完成")
        return [TYPE_COMPANY, [values]]


class IPOInfoFetcher:
    """发行信息抓取器"""
    
    FIELD_SPEC = [
        ('公司代码', None, 'code'),
        ('上市地', 0, 'text'),
        ('主承销商', 1, 'text'),
        ('承销方式', 2, 'text'),
        ('上市推荐人', 3, 'text'),
        ('每股发行价_元', 4, 'money'),
        ('发行方式', 5, 'text'),
        ('发行市盈率_按发行后总股本', 6, 'money'),
        ('首发前总股本_万股', 7, 'money'),
        ('首发后总股本_万股', 8, 'money'),
        ('实际发行量_万股', 9, 'money'),
        ('预计募集资金_万元', 10, 'money'),
        ('实际募集资金合计_万元', 11, 'money'),
        ('发行费用总额_万元', 12, 'money'),
        ('募集资金净额_万元', 13, 'money'),
        ('承销费用_万元', 14, 'money'),
        ('招股公告日', 15, 'date'),
        ('上市日期', 16, 'date'),
    ]
    
    def __init__(self, stock_code):
        self._code = stock_code
        self._cleaner = DataCleaner()
    
    def _build_url(self):
        """构建请求地址"""
        return f'https://vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_NewStock/stockid/{self._code}.phtml'
    
    def _process_value(self, df, row_idx, val_type):
        """根据类型处理字段值"""
        if val_type == 'code':
            return self._code
        raw = df.iloc[row_idx, 1]
        if val_type == 'text':
            return self._cleaner.sanitize_text(raw)
        elif val_type == 'money':
            return self._cleaner.parse_money(raw)
        elif val_type == 'date':
            return self._cleaner.parse_date(str(raw))
        return raw
    
    def crawl(self):
        """抓取发行信息"""
        print(f"正在获取{self._code}的发行信息...")
        url = self._build_url()
        tables = pd.read_html(url)
        df = tables[12]
        print("获取完成")
        
        print("正在解析数据...")
        values = []
        for field_name, row_idx, val_type in self.FIELD_SPEC:
            val = self._process_value(df, row_idx, val_type)
            values.append(val)
        print("解析完成")
        return [TYPE_IPO, [values]]


class StockDataCrawler:
    """股票数据采集器 - 统一入口"""
    
    def _get_user_input(self):
        """获取用户输入"""
        code = input("请输入股票代码（6位）：")
        return code
    
    def fetch_stock_data(self):
        """获取股票数据（默认下载财务数据）"""
        code = self._get_user_input()
        fetcher = FinanceReportFetcher(code)
        return fetcher.crawl()
