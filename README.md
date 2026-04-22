# 财报智能问数系统 - 后端

基于泰迪杯数据分析挑战赛B题：从PDF年报/季报/半年报中自动提取财务数据，支持自然语言问数查询。

## 技术架构

```
PDF年报
  │
  ▼
engine_a_rules.py   (pdfplumber + 正则规则，规则先行)
  │                         │
  │  置信度<阈值           │ 规则无法提取
  ▼                         ▼
pdf_extractor.py         engine_b_deepseek.py
(合流，双引擎)               (DeepSeek LLM 兜底)
  │
  ▼
raw_extracted (原始提取数据，JSON格式)
  │
  ▼
field_matcher.py   (字段映射：中文→英文字段)
  │
  ▼
llm_filler.py      (LLM兜底：保守合并，只填NULL)
  │
  ▼
validator.py       (五维财务逻辑校验)
  │
  ▼
4张标准表：income_sheet / balance_sheet /
          stock_income_statement_data / core_performance_indicators_sheet
```

## 目录结构

```
任务B_财报智能抽取/
├── config/                  # 配置（API Key等，见 .env）
├── data/                    # 原始PDF文件
├── models/                  # 意图分类模型
├── extractors/
│   ├── engine_a_rules.py    # 规则引擎（规则先行）
│   ├── engine_b_deepseek.py # LLM引擎（兜底）
│   ├── pdf_extractor.py     # 双引擎合流
│   └── field_matcher.py     # 字段映射ETL
├── predict_intent.py        # 意图分类推理
├── field_matcher.py         # 读raw_extracted→写标准表
├── llm_filler.py            # LLM兜底填充
├── validator.py             # 五维财务校验
├── config_loader.py        # .env配置加载
└── .env                    # 敏感配置（不提交Git）
```

## 环境依赖

```
pip install pdfplumber pymysql requests scikit-learn
```

## 使用流程

### 1. PDF提取 → raw_extracted
```bash
python run_batch_extract.py --limit 50
```

### 2. 字段映射 → 标准表
```bash
python field_matcher.py                    # 处理全部pending
python field_matcher.py --reprocess failed # 重新处理failed记录
python field_matcher.py --limit 100        # 限制条数
```

### 3. LLM兜底（可选）
```bash
python llm_filler.py --dry-run  # 先测试
python llm_filler.py             # 正式执行
```

### 4. 五维校验
```bash
python validator.py
python validator.py --table balance_sheet  # 只校验指定表
```

---

## 踩坑与解决方案

> 以下记录了开发过程中遇到的关键问题及解决方法，供复盘和学习参考。

### 1. 深交所PDF表头列与数据列错位（根本原因）

**问题：** 万邦德（深交所）年报PDF的表格结构与上交所不同——年份标签（如"2022年"）位于奇数列，实际数值位于相邻偶数列，导致规则提取全返回空值。

**原因：** 原始规则引擎直接取年份标签列的数值，但该列只有标签没有数据。

**解决：** 改为**双向扫描**策略，优先向右扫描找数值，找不到再向左扫描。核心代码：
```python
if parse_numeric(val) is not None:
    col_idx = ci
else:
    for nxt in range(ci + 1, len(headers)):
        if parse_numeric(str(row[nxt])) is not None:
            col_idx = nxt; break
    if col_idx is None:
        for prev in range(ci - 1, -1, -1):
            if parse_numeric(str(row[prev])) is not None:
                col_idx = prev; break
```

### 2. raw_extracted的auto_table_type不可信

**问题：** PDF提取时记录的 `auto_table_type`（如 income_sheet）不一定与实际数据内容匹配，导致字段被写入错误的表。例如：`other_income` 只存在于 `stock_income_statement_data` 表，但被写入了 `income_sheet`。

**原因：** PDF提取阶段只根据页面特征推断表类型，但一页可能包含多种类型的数据。

**解决：** 在 `field_matcher.py` 中按**实际字段内容**确定目标表，而非信任 `auto_table_type`。使用各表的专属字段集合打分，取匹配最多的表。

### 3. 小数字段超出MySQL decimal(10,4)范围

**问题：** `gross_profit_margin`（毛利率）等字段的原始值为百分比格式（如 `85.23` 表示 85.23%），直接存入 `decimal(10,4)` 时超范围报错；`asset_liability_ratio`（资产负债率）同样如此。

**原因：** PDF中的百分比数值通常不带 `%` 符号或带 `%` 符号时格式不统一。

**解决：** 在写入前统一处理——**值 > 1 的视为百分比格式，自动除以100转换为小数**；超过 ±0.9999（±99.99%）的值直接置为 NULL 忽略。

### 4. 字段名不存在于目标表

**问题：** `field_matcher.py` 的映射表包含了一些不在4张目标表里的字段（如 `income_tax_expense`、`long_term_loans`），导致写入时报 `Unknown column` 错误。

**原因：** 映射表来自财务术语的广泛收集，未与数据库实际列名对照。

**解决：** 以数据库 `DESCRIBE` 结果为准，逐表核实列名，**只保留4张表实际存在的字段映射**。

### 5. SiliconFlow API Key认证失败

**问题：** 最初配置的 DeepSeek API Key 返回 401 Unauthorized。

**原因：** DeepSeek 官方已对非官方渠道 key 做限制，需要使用 SiliconFlow 代理（`https://api.siliconflow.cn/v1`）并使用 SiliconFlow 颁发的 key。

**解决：** 切换端点为 SiliconFlow，使用其颁发的 API Key。

### 6. LLM兜底原则：保守合并

**问题：** 如果 LLM 提取结果覆盖了规则引擎已正确提取的数据，可能引入幻觉错误。

**原则：** LLM 只填充**规则提取结果为 NULL** 的字段，绝不覆盖已有数据。实现为 `conservative_merge` 方法：读取目标表现有值，仅更新 NULL 或 0 字段。

### 7. 五维财务校验体系

| 维度 | 校验规则 | 处理方式 |
|------|---------|---------|
| 表内平衡 | 资产总计 ≈ 负债合计 + 所有者权益合计（误差<1%） | 警告，数据仍入库，标记待复核 |
| 表间钩稽 | 利润表与资产负债表相关字段一致性 | 以资产负债表为准，记录差异 |
| 时序连续性 | 相邻报告期增长率异常（>500% 或 <-90%） | 标记人工复核，数据入库加异常标签 |
| 业务逻辑 | 营收 < 营业利润，或 净利润 > 营业利润 | 拒绝入库，退回重提取 |
| 跨报告一致 | 同一年年报与季报数据矛盾 | 以年报为准覆盖，记录冲突日志 |

---

## 数据库

- 主机：`127.0.0.1:3306`
- 数据库：`intelligent_data_query`
- 密码：通过 `config_loader.py` 从 `.env` 读取

### 表结构

**raw_extracted**（原始提取）
| 字段 | 说明 |
|------|------|
| raw_columns | JSON，中文列名数组 |
| raw_data | JSON，{"字段名": {"年份": 数值}} |
| auto_table_type | PDF提取时判断的表类型 |
| process_status | pending / mapped / failed |
| stock_code | 股票代码 |
| report_period | 报告期（YYYY-MM-DD） |

**income_sheet / balance_sheet / stock_income_statement_data / core_performance_indicators_sheet**
标准财务表，字段名统一为英文，详见各表 `DESCRIBE`。
