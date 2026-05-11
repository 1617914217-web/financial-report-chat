# -*- coding: utf-8 -*-
"""
可视化与结论生成模块

图表选择策略：
- 趋势变化 → 折线图
- 分类对比 → 柱状图
- 占比分布 → 饼图
- 明细数据 → 表格

保存路径: ./result/B[题号]_[序号].jpg
"""
import os, json, re
import matplotlib
matplotlib.use('Agg')  # 无GUI后端
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from typing import List, Dict, Optional


class Visualizer:
    """财务数据可视化器"""

    RESULT_DIR = "./result"

    def _setup_font(self):
        """设置中文字体"""
        # 尝试常见中文字体
        # 微软雅黑优先：汉字覆盖范围最广（含生僻字如"癀"），SimHei存在glyph缺失
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",        # 微软雅黑（推荐）
            "C:/Windows/Fonts/msyhbd.ttc",      # 微软雅黑粗体
            "C:/Windows/Fonts/simhei.ttf",      # 黑体
            "C:/Windows/Fonts/simsun.ttc",      # 宋体
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                self.font_prop = fm.FontProperties(fname=fp)
                plt.rcParams['font.family'] = self.font_prop.get_name()
                plt.rcParams['axes.unicode_minus'] = False
                return
        self.font_prop = None

    def _next_path(self, problem_no: str = "2") -> str:
        """生成下一个保存路径"""
        path = os.path.join(self.RESULT_DIR, f"B{problem_no}_{self.counter:02d}.jpg").replace("\\", "/")
        self.counter += 1
        return path

    def render(self, data: List[dict], chart_type: str = "auto",
               title: str = "", xlabel: str = "", ylabel: str = "",
               problem_no: str = "2") -> str:
        """
        渲染图表
        data: [{"label": str, "value": float, ...}, ...]
        chart_type: auto|line|bar|pie|table
        返回: 保存的文件路径
        """
        if chart_type == "auto":
            chart_type = self._infer_chart_type(data)

        path = self._next_path(problem_no)

        if chart_type == "line":
            self._draw_line(data, title, xlabel, ylabel, path)
        elif chart_type == "bar":
            self._draw_bar(data, title, xlabel, ylabel, path)
        elif chart_type == "pie":
            self._draw_pie(data, title, path)
        elif chart_type == "table":
            self._draw_table(data, title, path)
        else:
            self._draw_bar(data, title, xlabel, ylabel, path)

        return path

    def _infer_chart_type(self, data: List[dict]) -> str:
        """自动推断图表类型"""
        if len(data) <= 1:
            return "table"
        # 检查是否有时间序列特征
        labels = [d.get("label", "") for d in data]
        has_time = any(re.search(r'20\d{2}', str(l)) for l in labels)
        if has_time and len(data) >= 3:
            return "line"
        # 检查是否有占比特征（值加起来接近100或1）
        values = [float(d.get("value", 0)) for d in data]
        if values and sum(values) > 0:
            total = sum(abs(v) for v in values)
            if total > 0 and max(values) / total < 0.9:
                return "pie"
        return "bar"

    def _draw_line(self, data, title, xlabel, ylabel, path):
        fig, ax = plt.subplots(figsize=(10, 6))
        labels = [d.get("label", "") for d in data]
        values = [float(d.get("value", 0)) for d in data]
        ax.plot(labels, values, marker='o', linewidth=2, markersize=8)
        ax.set_title(title or "趋势图", fontproperties=self.font_prop, fontsize=14)
        ax.set_xlabel(xlabel or "", fontproperties=self.font_prop)
        ax.set_ylabel(ylabel or "", fontproperties=self.font_prop)
        ax.tick_params(axis='x', rotation=45)
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()

    def _draw_bar(self, data, title, xlabel, ylabel, path):
        fig, ax = plt.subplots(figsize=(10, 6))
        labels = [d.get("label", "") for d in data]
        values = [float(d.get("value", 0)) for d in data]
        colors = ['#2E86AB' if v >= 0 else '#E94F37' for v in values]
        bars = ax.bar(range(len(labels)), values, color=colors)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, fontproperties=self.font_prop, rotation=45, ha='right')
        ax.set_title(title or "对比图", fontproperties=self.font_prop, fontsize=14)
        ax.set_xlabel(xlabel or "", fontproperties=self.font_prop)
        ax.set_ylabel(ylabel or "", fontproperties=self.font_prop)
        # 添加数值标签
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax.annotate(f'{val:.2f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=9)
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()

    def _draw_pie(self, data, title, path):
        fig, ax = plt.subplots(figsize=(8, 8))
        labels = [d.get("label", "") for d in data]
        values = [abs(float(d.get("value", 0))) for d in data]
        # 过滤0值
        pairs = [(l, v) for l, v in zip(labels, values) if v > 0]
        if not pairs:
            return self._draw_table(data, title, path)
        labels, values = zip(*pairs)
        colors = plt.cm.Set3(range(len(labels)))
        wedges, texts, autotexts = ax.pie(values, labels=labels, autopct='%1.1f%%',
                                           colors=colors, startangle=90)
        for t in texts:
            t.set_fontproperties(self.font_prop)
        for t in autotexts:
            t.set_fontproperties(self.font_prop)
            t.set_fontsize(10)
        ax.set_title(title or "占比分布", fontproperties=self.font_prop, fontsize=14)
        plt.tight_layout()
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()

    def _draw_table(self, data, title, path):
        fig, ax = plt.subplots(figsize=(12, max(4, len(data) * 0.5 + 1)))
        ax.axis('off')
        # 提取表头和数据
        if not data:
            ax.text(0.5, 0.5, "无数据", ha='center', va='center',
                    fontproperties=self.font_prop, fontsize=14)
            plt.savefig(path, dpi=150, bbox_inches='tight')
            plt.close()
            return
        headers = list(data[0].keys())
        cell_text = [[str(d.get(h, "")) for h in headers] for d in data]
        table = ax.table(cellText=cell_text, colLabels=headers,
                         cellLoc='center', loc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 2)
        # 设置表头样式
        for i in range(len(headers)):
            table[(0, i)].set_facecolor('#2E86AB')
            table[(0, i)].set_text_props(weight='bold', color='white',
                                          fontproperties=self.font_prop)
        # 设置数据行字体
        for i in range(1, len(cell_text) + 1):
            for j in range(len(headers)):
                table[(i, j)].set_text_props(fontproperties=self.font_prop)
        ax.set_title(title or "数据明细", fontproperties=self.font_prop, fontsize=14, pad=20)
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()

    def __init__(self):
        os.makedirs(self.RESULT_DIR, exist_ok=True)
        self._setup_font()
        self.counter = 1
        # 加载公司别名映射，用于将股票代码转为正确中文名
        self._company_alias = {}
        alias_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "company_alias.json")
        if os.path.exists(alias_path):
            try:
                with open(alias_path, "r", encoding="utf-8-sig") as f:
                    raw_alias = json.load(f)
                # 清理 \ufffd 替换符
                for k, v in list(raw_alias.items()):
                    if isinstance(v, str) and '\ufffd' in v:
                        c = v.replace('\ufffd', '').strip()
                        if c:
                            self._company_alias[k] = c
                        else:
                            pass
                    elif isinstance(v, str):
                        self._company_alias[k] = v
            except Exception:
                pass

    def _get_company_name(self, stock_code: str) -> str:
        """根据股票代码返回正确的中文公司名"""
        if stock_code in self._company_alias:
            name = self._company_alias[stock_code]
            # 如果映射值也是股票代码，说明没有中文名，退回原值
            if name in self._company_alias:
                return stock_code
            return name
        return stock_code

    def generate_conclusion(self, data: List[dict], question: str = "") -> str:
        """生成自然语言结论"""
        if not data:
            return "未查询到相关数据。"

        # 统一数据格式：支持 {"label": ..., "value": ...} 和原始SQL结果
        normalized_data = []
        for d in data:
            if "label" in d and "value" in d:
                normalized_data.append(d)
            else:
                keys = list(d.keys())
                label = ""
                value = None
                for k in keys:
                    if k == "stock_abbr" and d[k]:
                        label = str(d[k])
                    elif k == "stock_code" and not label:
                        label = str(d[k])
                    elif value is None and d[k] is not None:
                        try:
                            value = float(d[k])
                        except (TypeError, ValueError):
                            continue
                if value is not None:
                    normalized_data.append({"label": label or "结果", "value": value})

        if not normalized_data:
            return "查询到数据但无法解析数值。"

        # 多指标情况：检查原始data中是否包含多个数值字段（如毛利率+净利率同时查询）
        if len(data) == 1 and len(normalized_data) == 1:
            d = data[0]
            # 提取所有数值字段
            numeric_fields = []
            skip_keys = {"serial_number", "stock_code", "stock_abbr", "report_period", 
                         "auto_table_type", "report_year", "validation_status", "validation_tags"}
            for k, v in d.items():
                if k in skip_keys:
                    continue
                if v is not None:
                    try:
                        numeric_fields.append((k, float(v)))
                    except (TypeError, ValueError):
                        continue
            
            if len(numeric_fields) > 1:
                # 多指标结论：列出所有数值
                label = ""
                if "stock_abbr" in d and d["stock_abbr"]:
                    label = str(d["stock_abbr"])
                elif "stock_code" in d:
                    label = str(d["stock_code"])
                
                # 字段名翻译
                field_names = {
                    "gross_profit_margin": "毛利率", "net_profit_margin": "净利率",
                    "total_operating_revenue": "营业收入", "net_profit": "净利润",
                    "total_operating_profit": "营业利润", "total_profit": "利润总额",
                    "eps": "每股收益", "roe": "净资产收益率",
                    "operating_revenue_yoy_growth": "营收同比增长",
                    "net_profit_yoy_growth": "净利润同比增长",
                    "asset_total_assets": "总资产",
                    "equity_total_equity": "净资产",
                    "operating_expense_cost_of_sales": "营业成本",
                }
                
                parts = []
                for k, v in numeric_fields:
                    name = field_names.get(k, k.replace("_", " "))
                    # 百分比字段
                    if any(x in k for x in ["margin", "rate", "ratio", "growth", "roe"]):
                        parts.append(f"{name}{v:.2f}%")
                    else:
                        if abs(v) >= 100000000:
                            parts.append(f"{name}{v/100000000:.2f}亿")
                        elif abs(v) >= 10000:
                            parts.append(f"{name}{v/10000:.2f}万")
                        else:
                            parts.append(f"{name}{v:.2f}")
                
                if parts:
                    return f"{label}：{'，'.join(parts)}。"

        if len(normalized_data) == 1:
            d = normalized_data[0]
            label = d.get("label", "")
            value = d.get("value", "")
            if label and isinstance(label, bytes):
                label = label.decode('utf-8', errors='ignore')
            if "stock_code" in d and d["stock_code"]:
                label = self._get_company_name(str(d["stock_code"]))
            return f"{label}为{value:,.2f}。"

        # 多值情况
        values = [float(d.get("value", 0)) for d in normalized_data]
        labels = [d.get("label", "") for d in normalized_data]
        labels = [l.decode('utf-8', errors='ignore') if isinstance(l, bytes) else l for l in labels]
        corrected_labels = []
        for i, d in enumerate(normalized_data):
            if "stock_code" in d and d["stock_code"]:
                corrected_labels.append(self._get_company_name(str(d["stock_code"])))
            else:
                corrected_labels.append(labels[i])
        labels = corrected_labels
        max_idx = values.index(max(values))
        min_idx = values.index(min(values))
        return (f"共查询到{len(normalized_data)}条数据。"
                f"其中{labels[max_idx]}最高，为{values[max_idx]:,.2f}；"
                f"{labels[min_idx]}最低，为{values[min_idx]:,.2f}。")


if __name__ == "__main__":
    vis = Visualizer()

    # 测试柱状图
    data_bar = [
        {"label": "金花股份", "value": 12345.67},
        {"label": "万邦德", "value": 23456.78},
        {"label": "乐普医疗", "value": 34567.89},
    ]
    path = vis.render(data_bar, chart_type="bar", title="2022年净利润对比",
                      xlabel="公司", ylabel="净利润(万元)")
    print(f"Bar chart: {path}")

    # 测试折线图
    data_line = [
        {"label": "2020", "value": 10000},
        {"label": "2021", "value": 12000},
        {"label": "2022", "value": 15000},
    ]
    path = vis.render(data_line, chart_type="line", title="净利润趋势",
                      xlabel="年份", ylabel="净利润(万元)")
    print(f"Line chart: {path}")

    # 测试结论生成
    conclusion = vis.generate_conclusion(data_bar, "2022年净利润对比")
    print(f"Conclusion: {conclusion}")
