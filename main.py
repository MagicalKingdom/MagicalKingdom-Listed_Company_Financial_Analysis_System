"""
股票数据采集与分析系统 - 主程序入口
"""
import os
from data_crawler import StockDataCrawler
from db_handler import DatabaseManager
from analyzer import AnalysisMenu


class Application:
    """应用程序主类"""
    
    def __init__(self):
        self._crawler = StockDataCrawler()
        self._db = DatabaseManager()
        self._analysis_menu = AnalysisMenu()
    
    def _clear_screen(self):
        """清空控制台"""
        os.system('cls')
    
    def _show_main_menu(self):
        """显示主菜单"""
        print("\n" + "=" * 40)
        print("  股票财务数据采集与分析系统")
        print("=" * 40)
        print("  1. 下载财务数据")
        print("  2. 财务数据分析")
        print("  0. 退出系统")
        print("-" * 40)
        return input("请选择功能：")
    
    def _download_data(self):
        """下载数据功能"""
        fetched_data = self._crawler.fetch_stock_data()
        self._db.store(fetched_data)
        input("\n按回车键继续...")
    
    def _analyze_data(self):
        """分析数据功能"""
        self._analysis_menu.show()
    
    def execute(self):
        """运行主程序"""
        while True:
            self._clear_screen()
            choice = self._show_main_menu()
            
            if choice == '1':
                self._download_data()
            elif choice == '2':
                self._analyze_data()
            elif choice == '0':
                print("感谢使用，再见！")
                break
            else:
                print("无效选项，请重新选择")
                input("按回车键继续...")


if __name__ == '__main__':
    app = Application()
    app.execute()
