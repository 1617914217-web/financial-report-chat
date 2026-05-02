# -*- coding: utf-8 -*-
"""
实体对齐模块 - Entity Resolution

在槽位填充后、生成SQL前，增加对齐验证步骤：
1. 公司名 → 股票代码
2. 科目名 → 数据库字段名
3. 时间表达 → 标准报告期格式

解决金融实体称谓多样化问题：
  "平安银行" → "000001.SZ"
  "净利润" → "net_profit" / "net_profit_parent_company"
  "2023年" → "2023-12-31" / "2023FY"
"""
import os, json, re
from typing import Dict, Optional, Tuple


class EntityAligner:
    """实体对齐器"""

    def __init__(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))

        # 加载公司映射
        with open(os.path.join(base_dir, "data", "company_alias.json"), "r", encoding="utf-8") as f:
            self.company_alias = json.load(f)

        # 加载科目映射（从financial_dictionary.json，如存在）
        self.subject_mapping = {}
        fin_dict_path = os.path.join(base_dir, "data", "financial_dictionary.json")
        if os.path.exists(fin_dict_path):
            with open(fin_dict_path, "r", encoding="utf-8") as f:
                fin_dict = json.load(f)
                for item in fin_dict:
                    std_name = item.get("标准名称", "")
                    db_field = item.get("数据库字段", "")
                    aliases = item.get("别名", [])
                    if std_name and db_field:
                        self.subject_mapping[std_name] = db_field
                        for alias in aliases:
                            self.subject_mapping[alias] = db_field
        else:
            # 使用默认映射
            self.subject_mapping = {
                "净利润": "net_profit",
                "营业收入": "operating_revenue",
                "总资产": "asset_total_assets",
                "总负债": "liability_total_liabilities",
                "净资产": "net_assets",
                "毛利率": "gross_profit_margin",
                "净利率": "net_profit_margin",
                "roe": "roe",
                "资产负债率": "asset_liability_ratio",
            }

        # 时间正则
        self.time_patterns = [
            (r"20(\d{2})年", self._parse_year),
            (r"20(\d{2})年(\d{1,2})月", self._parse_year_month),
            (r"20(\d{2})年(\d{1,2})月(\d{1,2})日", self._parse_full_date),
            (r"(第?[一二三四]季度)", self._parse_quarter),
            (r"(上半年|下半年)", self._parse_half_year),
            (r"(去年|前年|今年)", self._parse_relative_year),
        ]

    def align(self, slots: Dict) -> Dict:
        """
        对齐槽位中的实体

        Args:
            slots: 槽位填充结果
                {
                    "company": "平安银行",
                    "year": "2023年",
                    "subject": "净利润",
                    ...
                }

        Returns:
            对齐后的槽位
                {
                    "company": "平安银行",
                    "company_code": "000001.SZ",
                    "year": "2023年",
                    "report_period": "2023-12-31",
                    "subject": "净利润",
                    "db_column": "net_profit",
                    ...
                }
        """
        aligned = slots.copy()

        # 1. 公司对齐
        if slots.get("company"):
            company_code = self._align_company(slots["company"])
            if company_code:
                aligned["company_code"] = company_code

        # 2. 科目对齐
        if slots.get("subjects"):
            db_columns = []
            for subj in slots["subjects"]:
                col = self._align_subject(subj)
                if col:
                    db_columns.append(col)
            if db_columns:
                aligned["db_columns"] = db_columns
                aligned["db_column"] = db_columns[0]  # 兼容旧接口

        # 3. 时间对齐
        if slots.get("year"):
            report_period = self._align_time(slots["year"])
            if report_period:
                aligned["report_period"] = report_period

        return aligned

    def _align_company(self, company_name: str) -> Optional[str]:
        """公司名 → 股票代码"""
        # 直接匹配
        if company_name in self.company_alias:
            code = self.company_alias[company_name]
            if not code.startswith("_"):
                return code

        # 模糊匹配（包含关系）
        for alias, code in self.company_alias.items():
            if alias.startswith("_"):
                continue
            if alias in company_name or company_name in alias:
                return code

        return None

    def _align_subject(self, subject_name: str) -> Optional[str]:
        """科目名 → 数据库字段名"""
        # 直接匹配
        if subject_name in self.subject_mapping:
            return self.subject_mapping[subject_name]

        # 模糊匹配
        for alias, field in self.subject_mapping.items():
            if alias in subject_name or subject_name in alias:
                return field

        # 常见映射兜底
        fallback = {
            "净利润": "net_profit",
            "营业收入": "operating_revenue",
            "总资产": "asset_total_assets",
            "总负债": "liability_total_liabilities",
            "净资产": "net_assets",
            "毛利率": "gross_profit_margin",
            "净利率": "net_profit_margin",
            "roe": "roe",
            "资产负债率": "asset_liability_ratio",
        }
        return fallback.get(subject_name)

    def _align_time(self, time_expr: str) -> Optional[str]:
        """时间表达 → 标准报告期"""
        for pattern, parser in self.time_patterns:
            match = re.search(pattern, time_expr)
            if match:
                return parser(match)
        return None

    def _parse_year(self, match) -> str:
        year = match.group(1)
        return f"20{year}-12-31"

    def _parse_year_month(self, match) -> str:
        year = match.group(1)
        month = match.group(2).zfill(2)
        return f"20{year}-{month}-01"  # 简化处理

    def _parse_full_date(self, match) -> str:
        year = match.group(1)
        month = match.group(2).zfill(2)
        day = match.group(3).zfill(2)
        return f"20{year}-{month}-{day}"

    def _parse_quarter(self, match) -> str:
        quarter_map = {
            "第一季度": "03-31", "Q1": "03-31", "一季度": "03-31",
            "第二季度": "06-30", "Q2": "06-30", "二季度": "06-30", "上半年": "06-30", "中报": "06-30",
            "第三季度": "09-30", "Q3": "09-30", "三季度": "09-30",
            "第四季度": "12-31", "Q4": "12-31", "四季度": "12-31", "年报": "12-31",
        }
        q = match.group(1)
        # 需要结合年份，这里简化返回
        return quarter_map.get(q, "12-31")

    def _parse_half_year(self, match) -> str:
        return "06-30" if "上" in match.group(1) else "12-31"

    def _parse_relative_year(self, match) -> str:
        # 相对年份需要当前年份上下文，简化处理
        return None

    def validate(self, aligned_slots: Dict) -> Tuple[bool, str]:
        """
        验证对齐结果是否完整

        Returns:
            (是否有效, 错误信息)
        """
        if not aligned_slots.get("company_code") and aligned_slots.get("company"):
            return False, f"无法识别公司: {aligned_slots.get('company')}"

        if aligned_slots.get("subjects") and not aligned_slots.get("db_columns"):
            return False, f"无法识别科目: {aligned_slots.get('subjects')}"

        return True, ""


if __name__ == "__main__":
    aligner = EntityAligner()

    test_cases = [
        {"company": "金花股份", "year": "2022年", "subjects": ["净利润"]},
        {"company": "万邦德", "year": "2023年", "subjects": ["资产总计"]},
        {"company": "平安银行", "year": "2024年", "subjects": ["营业收入", "毛利率"]},
    ]

    for slots in test_cases:
        print(f"\n输入: {slots}")
        aligned = aligner.align(slots)
        print(f"对齐: {aligned}")
        valid, msg = aligner.validate(aligned)
        print(f"验证: {'通过' if valid else '失败'} - {msg}")
