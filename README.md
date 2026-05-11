# 财报智能问数系统

泰迪杯第十四届数据挖掘竞赛B题——构建上市公司财报智能问数系统。

从PDF年报自动提取财务数据 → 字段映射+五维校验入库 → 前端自然语言查询。双引擎（规则优先 + LLM兜底），规则能拿到的就不调API，省成本。

---

## 项目结构

```
任务B_财报智能抽取/
├── app.py                      FastAPI后端入口
├── pipeline.py                 端到端问答流水线（核心）
├── config_loader.py            .env配置加载
├── config/                     财务术语映射表
├── data/                       公司别名等数据文件
├── extractors/                 PDF提取引擎
│   ├── engine_a_rules.py       规则引擎（核心）
│   ├── engine_b_deepseek.py    LLM兜底
│   └── pdf_extractor.py        统一入口
├── models/                     意图分类模型
├── field_matcher.py            字段映射ETL
├── llm_filler.py               LLM填充缺失数据
├── validator.py                五维校验
├── preprocess_pipeline.py      文本预处理
├── predict_intent.py           意图分类推理
├── slot_filler.py              槽位填充
├── nl2sql.py                   NL2SQL生成
├── sql_validator.py            SQL安全校验
├── knowledge_graph.py          财务知识图谱
├── visualizer.py               可视化与结论生成
├── run_batch_extract.py        批量PDF处理
├── train_intent_classifier.py  意图分类训练
├── frontend/                   ← 前端React项目
│   ├── src/
│   │   ├── pages/Chat/         智能问答页
│   │   ├── pages/Login/        用户登录页
│   │   ├── components/         布局&思考过程组件
│   │   ├── services/api.ts     API调用
│   │   ├── store/              Zustand状态管理
│   │   └── utils/              工具函数
│   ├── package.json
│   └── vite.config.ts
├── README.md
└── .env                        数据库密码+API Key
```

---

## 数据流

```
PDF年报 → pdf_extractor.py → raw_extracted（原始数据）
                                   ↓
                           field_matcher.py（字段映射）
                                   ↓
                           validator.py（五维校验）
                                   ↓
                    四张标准表（balance_sheet等）
                                   ↓
                         pipeline.py（自然语言查询）
                                   ↓
                         答案 + 图表 + 结论
```


踩过的坑

深交所PDF列错位。一开始只处理上交所的PDF，能跑通。后面跑深交所的万邦德年报，提取出来全是空值。原因是深交所的表格结构不一样，年份标签（如"2022年"）在奇数列，实际数值在相邻偶数列。规则引擎直接取标签列的下一格，那里是空的。解决：双向扫描，优先向右找数值，找不到再向左。

raw_extracted的表类型不可信。PDF提取阶段会给每条记录打一个auto_table_type标记，但这个标记经常不准。一页PDF里可能有多种数据混在一起，系统只是根据页面特征猜了一个类型。结果就是字段被写进错误的表。比如other_income（营业外收入）只存在于stock_income_statement_data表，但有记录被标记为income_sheet，写不进去报错。解决：不再信任auto_table_type，按实际字段内容决定目标表。每个表有一批专属字段，匹配最多的就是目标表。

百分比格式导致数据库超范围。毛利率、资产负债率这些字段，PDF里通常不带百分号，存的是85.23这样的数。MySQL里是decimal(10,4)，超过9999就爆了。解决：值大于1的统一除100转成小数，超过0.9999的直接扔掉。

映射表里有不存在的字段。一开始收集财务术语映射的时候比较随意，映射了一些字段名，数据库里根本没有。写入的时候报Unknown column错误。解决：以数据库实际列名为准，只保留四张表里真实存在的字段映射。

DeepSeek API Key被拒。一开始用的key调DeepSeek官方接口，一直401。解决：换成SiliconFlow的代理端点和key。

LLM兜底的原则。调LLM填充缺失数据的时候有个原则：只填规则拿不到的，不覆盖已有数据。避免LLM产生幻觉结果覆盖掉正确结果。

五维校验。数据进标准表之前要过一遍校验：表内平衡（资产等于负债加权益）、表间钩稽、时序连续性（增长率不能太离谱）、业务逻辑（净利润不能大于营业收入）、跨报告一致（年报和季报冲突以年报为准）。逻辑校验发现明显错误会拒绝入库，其他情况只打标记让人去看。

---

## 启动

### 后端

```bash
# 安装依赖
pip install pdfplumber pymysql fastapi uvicorn scikit-learn sqlparse matplotlib cryptography

# 配置 .env（数据库密码+API Key）
# MYSQL_HOST=127.0.0.1
# MYSQL_PASSWORD=xxx
# SILICONFLOW_API_KEY=xxx

# 启动
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev          # → localhost:5173
```

Vite代理 `/api` → `localhost:8000`，无需手动改baseURL。

### 数据处理（按需）

```bash
python run_batch_extract.py          # 批量PDF提取
python field_matcher.py              # 字段映射
python field_matcher.py --reprocess failed  # 重试失败记录
python llm_filler.py                 # LLM兜底填充
python validator.py                  # 五维校验
```

数据库在 127.0.0.1:3306，配置在 .env。

---

## 核心模块说明

| 模块 | 文件 | 说明 |
|------|------|------|
| PDF解析 | extractors/ | 规则引擎优先+LLM兜底，86%成功率 |
| 字段映射 | field_matcher.py | 中文术语→数据库字段映射 |
| 五维校验 | validator.py | 表内平衡/表间钩稽/时序/业务逻辑/跨报 |
| 意图分类 | predict_intent.py | TF-IDF+LR，5类F1=0.80 |
| 槽位填充 | slot_filler.py | 提取公司/年份/指标 |
| NL2SQL | nl2sql.py | 自然语言转SQL+双层校验 |
| 知识图谱 | knowledge_graph.py | 派生指标推理(ROE=净利/净资产) |
| 可视化 | visualizer.py | 图表自动选择+结论生成 |
| 流水线 | pipeline.py | Plan-and-Execute多步执行 |
