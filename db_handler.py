"""
数据库操作模块 - 负责SQLite数据存储
"""
import sqlite3
from pathlib import Path

# 数据类型与表配置
TABLE_CONFIG = {
    'FD': {
        'table': 'financial_data',
        'columns': ['公司代码', '报告日期', '项目编号', '值'],
        'desc': '财务报表'
    },
    'CI': {
        'table': 'corporation_information',
        'columns': [
            '公司代码', '公司名称', '公司英文名称', '上市市场', '上市日期',
            '发行价格', '主承销商', '成立日期', '注册资本_万元', '机构类型',
            '组织形式', '董事会秘书', '公司电话', '董秘电话', '公司传真',
            '董秘传真', '公司电子邮箱', '董秘电子邮箱', '公司网址', '邮政编码',
            '信息披露网址', '证券简称更名历史', '注册地址', '办公地址', '公司简介', '经营范围'
        ],
        'desc': '公司信息'
    },
    'II': {
        'table': 'issue_information',
        'columns': [
            '公司代码', '上市地', '主承销商', '承销方式', '上市推荐人',
            '每股发行价_元', '发行方式', '发行市盈率_按发行后总股本',
            '首发前总股本_万股', '首发后总股本_万股', '实际发行量_万股',
            '预计募集资金_万元', '实际募集资金合计_万元', '发行费用总额_万元',
            '募集资金净额_万元', '承销费用_万元', '招股公告日', '上市日期'
        ],
        'desc': '发行信息'
    }
}

# 建表SQL模板
CREATE_TABLE_SQL = {
    'financial_data': """CREATE TABLE IF NOT EXISTS financial_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        公司代码 TEXT,
        报告日期 TEXT,
        项目编号 TEXT,
        值 TEXT
    )""",
    'corporation_information': """CREATE TABLE IF NOT EXISTS corporation_information (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        公司代码 TEXT,
        公司名称 TEXT,
        公司英文名称 TEXT,
        上市市场 TEXT,
        上市日期 TEXT,
        发行价格 TEXT,
        主承销商 TEXT,
        成立日期 TEXT,
        注册资本_万元 TEXT,
        机构类型 TEXT,
        组织形式 TEXT,
        董事会秘书 TEXT,
        公司电话 TEXT,
        董秘电话 TEXT,
        公司传真 TEXT,
        董秘传真 TEXT,
        公司电子邮箱 TEXT,
        董秘电子邮箱 TEXT,
        公司网址 TEXT,
        邮政编码 TEXT,
        信息披露网址 TEXT,
        证券简称更名历史 TEXT,
        注册地址 TEXT,
        办公地址 TEXT,
        公司简介 TEXT,
        经营范围 TEXT
    )""",
    'issue_information': """CREATE TABLE IF NOT EXISTS issue_information (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        公司代码 TEXT,
        上市地 TEXT,
        主承销商 TEXT,
        承销方式 TEXT,
        上市推荐人 TEXT,
        每股发行价_元 TEXT,
        发行方式 TEXT,
        发行市盈率_按发行后总股本 TEXT,
        首发前总股本_万股 TEXT,
        首发后总股本_万股 TEXT,
        实际发行量_万股 TEXT,
        预计募集资金_万元 TEXT,
        实际募集资金合计_万元 TEXT,
        发行费用总额_万元 TEXT,
        募集资金净额_万元 TEXT,
        承销费用_万元 TEXT,
        招股公告日 TEXT,
        上市日期 TEXT
    )"""
}


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_name='stock_data.db'):
        self._db_path = Path(__file__).parent / db_name
        self._ensure_tables()
    
    def _get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(str(self._db_path))
    
    def _ensure_tables(self):
        """确保所有表已创建"""
        conn = self._get_connection()
        cur = conn.cursor()
        for tbl_name, sql in CREATE_TABLE_SQL.items():
            cur.execute(sql)
        conn.commit()
        conn.close()
    
    def _check_exists(self, cur, tbl_name, stock_code):
        """检查记录是否存在"""
        cur.execute(f"SELECT 1 FROM {tbl_name} WHERE 公司代码 = ? LIMIT 1", (stock_code,))
        return cur.fetchone() is not None
    
    def _remove_existing(self, cur, tbl_name, stock_code):
        """删除已有记录"""
        cur.execute(f"DELETE FROM {tbl_name} WHERE 公司代码 = ?", (stock_code,))
    
    def _convert_row(self, row):
        """将行数据转换为字符串列表"""
        return [str(v) if v is not None else None for v in row]
    
    def _build_insert_sql(self, tbl_name, columns):
        """构建插入SQL"""
        cols_str = ', '.join(columns)
        placeholders = ', '.join(['?'] * len(columns))
        return f"INSERT INTO {tbl_name} ({cols_str}) VALUES ({placeholders})"
    
    def store(self, data_pack):
        """存储数据到数据库"""
        if not data_pack or len(data_pack) < 2 or not data_pack[1]:
            print("无有效数据")
            return False
        
        data_type, records = data_pack
        config = TABLE_CONFIG.get(data_type)
        if not config:
            print("未知数据类型")
            return False
        
        tbl_name = config['table']
        columns = config['columns']
        desc = config['desc']
        stock_code = records[0][0]
        
        conn = self._get_connection()
        cur = conn.cursor()
        
        if self._check_exists(cur, tbl_name, stock_code):
            confirm = input(f'该股票的{desc}已存在，输入y覆盖：')
            if confirm.lower() == 'y':
                self._remove_existing(cur, tbl_name, stock_code)
            else:
                print("已取消")
                conn.close()
                return False
        
        print(f"正在写入{desc}...")
        sql = self._build_insert_sql(tbl_name, columns)
        converted = [self._convert_row(r) for r in records]
        cur.executemany(sql, converted)
        conn.commit()
        conn.close()
        
        print(f"写入完成，数据库：{self._db_path}")
        return True
    
    def query_financial_data(self, stock_code, report_date=None):
        """查询财务数据"""
        conn = self._get_connection()
        cur = conn.cursor()
        if report_date:
            cur.execute(
                "SELECT 项目编号, 值 FROM financial_data WHERE 公司代码 = ? AND 报告日期 = ?",
                (stock_code, report_date)
            )
        else:
            cur.execute(
                "SELECT 报告日期, 项目编号, 值 FROM financial_data WHERE 公司代码 = ? ORDER BY 报告日期 DESC",
                (stock_code,)
            )
        rows = cur.fetchall()
        conn.close()
        return rows
    
    def get_report_dates(self, stock_code):
        """获取某股票的所有报告日期"""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT 报告日期 FROM financial_data WHERE 公司代码 = ? ORDER BY 报告日期 DESC",
            (stock_code,)
        )
        dates = [r[0] for r in cur.fetchall()]
        conn.close()
        return dates
    
    def get_all_stock_codes(self):
        """获取数据库中所有股票代码"""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT 公司代码 FROM financial_data")
        codes = [r[0] for r in cur.fetchall()]
        conn.close()
        return codes
