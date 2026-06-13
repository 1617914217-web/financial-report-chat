# 财报智能问数系统

泰迪杯第十四届数据挖掘竞赛B题：从PDF年报自动提取财务数据 → 字段映射+五维校验入库 → 自然语言查数。

双引擎（规则优先 + LLM兜底），规则能拿到的就不调API，省成本。

---

## 数据怎么流

```
┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐
│ 1252份   │───→│ 双引擎提取    │───→│ raw_extracted │───→│ 字段映射  │
│ PDF年报  │    │ 规则+LLM兜底  │    │ (原始数据)    │    │          │
└──────────┘    └──────────────┘    └──────────────┘    └──────────┘
                                                               │
                                                               ▼
┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────┐
│ 答案+图表 │←───│ 可视化+结论  │←───│ SQL执行      │←───│ 四张标准表│
│          │    │              │    │              │    │          │
└──────────┘    └──────────────┘    └──────────────┘    └──────────┘
     ↑                                    ↑
     │                                    │
┌────┴─────┐    ┌──────┐    ┌────────┐   ┌─┴────────┐
│ 用户问句 │→→→→│预处理│→→→→│意图分类│→→→│ 槽位填充 │
│          │    │      │    │        │   │          │
└──────────┘    └──────┘    └────────┘   └────┬─────┘
                                              │
                          ┌───────────────────┘
                          ▼
                    ┌──────────┐
                    │ NL2SQL   │
                    │ 自然语言→SQL│
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │ SQL校验  │
                    │ 安全拦截 │
                    └──────────┘
```

两条线：
- **离线**：PDF → 提取 → 映射 → 校验 → 四张表
- **在线**：问句 → 预处理 → 意图 → 槽位 → NL2SQL → 执行 → 可视化

---

## 技术栈

| 层 | 技术 | 为什么 |
|---|------|--------|
| PDF解析 | pdfplumber | 比pymupdf对表格更友好，能拿字符坐标 |
| LLM兜底 | DeepSeek-V3 (SiliconFlow) | 便宜，中文强，免备案 |
| 意图分类 | TF-IDF + 逻辑回归 | 样本少（1708条），传统ML泛化更好 |
| 槽位填充 | 规则匹配 | 准确率够用，零训练成本 |
| NL2SQL | Prompt + Few-Shot | 不用微调，schema变了改prompt就行 |
| 数据库 | MySQL 8 | 窗口函数、复杂查询 |
| 后端 | FastAPI | 异步，自动生成文档 |
| 前端 | React + TypeScript + Vite | 组件化，热重载快 |
| 图表 | Matplotlib + ECharts | 后端静态图 + 前端交互 |
| 向量检索 | BAAI/bge-large-zh-v1.5 | 中文embedding效果最好之一 |

---

## 文件结构

```
任务B_财报智能抽取/
│
├── 📊 数据管道（离线）
│   ├── extractors/
│   │   ├── engine_a_rules.py       ⭐ 规则引擎：pdfplumber提取表格数据
│   │   ├── engine_b_deepseek.py    LLM兜底：API提取规则搞不定的数据
│   │   ├── pdf_extractor.py        统一入口：调度双引擎
│   │   └── table_mapper.py         表类型映射
│   ├── run_batch_extract.py        批量处理所有PDF
│   ├── field_matcher.py            ⭐ 字段映射：中文术语→数据库字段名
│   ├── llm_filler.py               LLM填充规则缺漏的字段
│   └── validator.py               ⭐ 五维校验
│
├── 🧠 智能问答（在线）
│   ├── preprocess_pipeline.py      文本预处理
│   ├── predict_intent.py           意图分类推理
│   ├── train_intent_classifier.py  训练意图分类器
│   ├── slot_filler.py              ⭐ 槽位填充：抽取公司/年份/指标
│   ├── slot_filler_bert.py         BERT版（代码完整，待GPU）
│   ├── nl2sql.py                  ⭐ NL2SQL生成
│   ├── sql_validator.py           SQL安全校验
│   ├── knowledge_graph.py         ⭐ 派生指标推理
│   ├── visualizer.py              可视化+结论生成
│   └── pipeline.py                ⭐ 端到端流水线
│
├── 🔍 RAG检索增强
│   ├── rag_knowledge_base.py       文档切分+向量化+混合检索
│   ├── entity_aligner.py           实体对齐
│   ├── agent_planner.py            Plan-and-Execute Agent
│   └── task3_pipeline.py           统一入口
│
├── 🌐 后端服务
│   ├── app.py                      FastAPI入口（/chat /sql等）
│   ├── config_loader.py            加载.env
│   └── start_backend.bat           Windows启动
│
├── 🖥️ 前端
│   └── frontend/
│       ├── src/pages/Chat/         智能问答页（思考过程展示）
│       ├── src/pages/Login/        登录页
│       ├── src/components/Layout/  侧边栏
│       ├── src/services/api.ts     API封装
│       ├── src/store/              Zustand状态管理
│       └── vite.config.ts          代理/api→后端
│
├── 📦 数据与配置
│   ├── .env                        ⚠️ 不进Git
│   ├── .gitignore
│   └── data/
│       ├── company_alias.json      公司名→代码映射
│       ├── financial_dictionary.json 术语标准词典
│       ├── intent_train.csv        意图训练数据
│       └── subject_synonym.json    科目同义词
│
└── 📖 README.md                    本文档
```

---

## 核心模块

### PDF数据提取（engine_a_rules.py）

年报PDF表格 → 财务数据。

**为什么难**：上交深交表格结构不同、同公司不同年份也不同、合并单元格+跨页+水印。

**怎么做的**：
1. pdfplumber提取表格 + 字符坐标
2. 识别表头（年份标签往往不在数据列位置）
3. 双向扫描匹配数值（先向右找，找不到向左）
4. 推断报告类型

**关键——自适应列对齐**：深交所年报年份标签在奇数列、数值在偶数列。不再固定取"年份列+1"，双向扫描取第一个非空数值。万邦德从0张表突破到2张。

**成功率**：1252份年报86%自动提取，14%是极窄表格（2-3列）或扫描件。

### 字段映射（field_matcher.py）

"营业收入（元）" → `total_operating_revenue`。

同一指标不同公司叫法不同（"营业总收入"/"营业收入"/"主营业务收入"），用模糊匹配（编辑距离+关键词）+ 按字段专属度决定目标表。

### 五维校验（validator.py）

| 维度 | 检查什么 | 例子 |
|------|---------|------|
| 表内平衡 | 会计恒等式 | 资产 = 负债 + 所有者权益 |
| 表间钩稽 | 跨表一致性 | 利润表净利 = 资产负债表未分配利润变动 |
| 时序连续性 | 增长率合理 | 营收年增长率不在-80%~300%报警 |
| 业务逻辑 | 常识约束 | 净利不能大于营收 |
| 跨报告一致 | 年报/季报冲突 | 冲突以年报为准 |

### 意图分类（predict_intent.py）

TF-IDF + 逻辑回归，1708条训练，5折交叉F1=0.80。样本少用ML优于DL。

| 类别 | 例子 | SQL类型 |
|------|------|--------|
| QUERY_SINGLE | "金花2022净利" | SELECT ... WHERE |
| CALCULATE | "金花2022毛利率" | SELECT + 计算列 |
| COMPARE | "金花vs万邦德营收" | WHERE IN (...) |
| RANK | "净利Top3" | ORDER BY ... LIMIT |
| QUERY_MULTI | "营收和净利" | 多字段 |

### 槽位填充（slot_filler.py）

"金花股份2022年净利润是多少" → `{company: "金花股份", company_code: "600080", year: "2022", metric: "净利润"}`

### NL2SQL（nl2sql.py）

Prompt Engineering：Schema + 6个Few-Shot + 安全规则 + 槽位信息 → SQL。不微调，schema变了改prompt就行。

### 知识图谱（knowledge_graph.py）

派生指标推理：ROE = 净利/净资产，资产负债率 = 总负债/总资产。递归展开到基础字段。

### Plan-and-Execute Agent（agent_planner.py）

复杂问题拆多步执行。"Top3净利+同比增速" → PLAN(查Top3→查上年→算同比) → 逐步执行 → 汇总。

### RAG知识库（rag_knowledge_base.py）

160份研报 → 语义切分 → bge-large-zh向量化 → Dense+BM25混合检索 → 回答数据库查不到的问题。

---

## 数据库

### raw_extracted（原始提取）
```sql
serial_number INT AUTO_INCREMENT PRIMARY KEY,
pdf_name VARCHAR(255),
company_name VARCHAR(100),
report_period VARCHAR(20),    -- '2022-12-31'
raw_columns JSON, raw_data JSON,
auto_table_type VARCHAR(50),  -- 不可信！
process_status VARCHAR(20),
```

### 四张标准表

| 表 | 内容 | 代表字段 |
|----|------|---------|
| balance_sheet | 资产负债表 | asset_total_assets, liability_total_liabilities |
| stock_income_statement_data | 利润表 | total_operating_revenue, net_profit |
| income_sheet | 现金流量表 | cf_operating_cash_flow |
| core_performance_indicators_sheet | 核心指标 | gross_profit_margin, net_profit_margin, roe |

---

## 跑起来

```bash
git clone https://github.com/1617914217-web/financial-report-chat.git
cd financial-report-chat

# 配置 .env
# MYSQL_HOST=127.0.0.1 MYSQL_PASSWORD=xxx SILICONFLOW_API_KEY=xxx

pip install pdfplumber pymysql fastapi uvicorn scikit-learn sqlparse matplotlib
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload

cd frontend && npm install && npm run dev  # → localhost:5173
```

数据处理（按需）：
```bash
python run_batch_extract.py
python field_matcher.py
python validator.py
```

---

## 踩坑记录

1. **深交所列错位**：年份标签在奇数列、数据在偶数列，直接取+1全是空值。双向扫描解决。

2. **auto_table_type不可信**：PDF混多种数据，推断不准。按字段专属度重新匹配目标表。

3. **百分比超限**：毛利率85.23存decimal(10,4)爆掉。大于1自动/100。

4. **编码噩梦**：库存UTF-8→latin1→PowerShell GBK三层乱码。全链路utf8mb4。

5. **DeepSeek API 401**：官方接口被拒，换SiliconFlow代理。

6. **LLM兜底原则**：只填规则拿不到的，不覆盖已有正确数据。

7. **映射字段不存在**：以数据库实际列名为准，不留虚映射。
