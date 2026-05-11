import { useState } from 'react'
import { Table, Tag, Space, Tabs, Badge, Button, Drawer, Descriptions, Statistic, Tooltip, Card, Row, Col } from 'antd'
import {
  DatabaseOutlined, TableOutlined, BranchesOutlined, ThunderboltOutlined,
  CopyOutlined
} from '@ant-design/icons'
// import type { ColumnsType } from 'antd/es/table'
import type { TableInfo } from '../../types'
import { formatMoney } from '../../utils'
import './DatabasePage.css'

const MOCK_TABLES: TableInfo[] = [
  {
    name: 'balance_sheet',
    label: '资产负债表',
    rowCount: 847,
    columns: [
      { name: 'id', type: 'int', comment: '主键' },
      { name: 'stock_code', type: 'varchar', comment: '股票代码' },
      { name: 'report_date', type: 'date', comment: '报告期' },
      { name: 'total_assets', type: 'decimal', comment: '资产总计' },
      { name: 'total_liabilities', type: 'decimal', comment: '负债合计' },
      { name: 'total_equity', type: 'decimal', comment: '所有者权益合计' },
      { name: 'monetary_fund', type: 'decimal', comment: '货币资金' },
      { name: 'accounts_receivable', type: 'decimal', comment: '应收账款' },
      { name: 'inventory', type: 'decimal', comment: '存货' },
      { name: 'fixed_assets', type: 'decimal', comment: '固定资产' },
    ],
  },
  {
    name: 'income_sheet',
    label: '利润表',
    rowCount: 912,
    columns: [
      { name: 'id', type: 'int', comment: '主键' },
      { name: 'stock_code', type: 'varchar', comment: '股票代码' },
      { name: 'report_date', type: 'date', comment: '报告期' },
      { name: 'operating_revenue', type: 'decimal', comment: '营业总收入' },
      { name: 'operating_cost', type: 'decimal', comment: '营业总成本' },
      { name: 'net_profit', type: 'decimal', comment: '净利润' },
      { name: 'operating_profit', type: 'decimal', comment: '营业利润' },
      { name: 'total_profit', type: 'decimal', comment: '利润总额' },
      { name: 'financial_expense', type: 'decimal', comment: '财务费用' },
      { name: 'selling_expense', type: 'decimal', comment: '销售费用' },
      { name: 'administrative_expense', type: 'decimal', comment: '管理费用' },
    ],
  },
  {
    name: 'core_performance_indicators_sheet',
    label: '核心指标表',
    rowCount: 634,
    columns: [
      { name: 'id', type: 'int', comment: '主键' },
      { name: 'stock_code', type: 'varchar', comment: '股票代码' },
      { name: 'report_date', type: 'date', comment: '报告期' },
      { name: 'gross_margin', type: 'decimal', comment: '毛利率' },
      { name: 'net_margin', type: 'decimal', comment: '净利率' },
      { name: 'weighted_roe', type: 'decimal', comment: '加权净资产收益率' },
      { name: 'revenue_growth_rate', type: 'decimal', comment: '营收增长率' },
      { name: 'profit_growth_rate', type: 'decimal', comment: '利润增长率' },
    ],
  },
  {
    name: 'stock_income_statement_data',
    label: '个股行情数据',
    rowCount: 1205,
    columns: [
      { name: 'id', type: 'int', comment: '主键' },
      { name: 'stock_code', type: 'varchar', comment: '股票代码' },
      { name: 'trade_date', type: 'date', comment: '交易日期' },
      { name: 'open_price', type: 'decimal', comment: '开盘价' },
      { name: 'close_price', type: 'decimal', comment: '收盘价' },
      { name: 'volume', type: 'bigint', comment: '成交量' },
      { name: 'turnover', type: 'decimal', comment: '成交额' },
    ],
  },
]

const TABLE_COLORS = {
  balance_sheet: 'blue',
  income_sheet: 'green',
  core_performance_indicators_sheet: 'orange',
  stock_income_statement_data: 'purple',
}

export default function DatabasePage() {
  const [, setActiveTable] = useState<string>('')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [selectedTable, setSelectedTable] = useState<TableInfo | null>(null)

  // const currentTable = MOCK_TABLES.find(t => t.name === activeTable) ?? null

  // 预览数据
  const previewRows = [
    { id: 1, stock_code: '600080', report_date: '2023-12-31', operating_revenue: 1978234567.89, net_profit: 123456789.12, financial_expense: 24699467.22 },
    { id: 2, stock_code: '600080', report_date: '2023-09-30', operating_revenue: 1456789012.34, net_profit: 98765432.10, financial_expense: 18500000.00 },
    { id: 3, stock_code: '002112', report_date: '2023-12-31', operating_revenue: 1786428308.52, net_profit: 45678901.23, financial_expense: 24499467.22 },
    { id: 4, stock_code: '600519', report_date: '2023-12-31', operating_revenue: 147218234567.89, net_profit: 74734567890.12, financial_expense: -12345678.90 },
  ]

  function openDrawer(t: TableInfo) {
    setSelectedTable(t)
    setActiveTable(t.name)
    setDrawerOpen(true)
  }

  const tabItems = MOCK_TABLES.map(t => ({
    key: t.name,
    label: (
      <Space>
        <DatabaseOutlined style={{ color: TABLE_COLORS[t.name as keyof typeof TABLE_COLORS] }} />
        <span>{t.label}</span>
        <Badge count={t.rowCount} size="small" style={{ backgroundColor: '#1e2a4a', color: '#8a9bcf', fontSize: 10 }} />
      </Space>
    ),
    children: (
      <div className="db-preview">
        <div className="db-preview-header">
          <Space>
            <Tag color={TABLE_COLORS[t.name as keyof typeof TABLE_COLORS]}>{t.name}</Tag>
            <span className="db-preview-hint">预览前 4 条</span>
          </Space>
          <Button size="small" icon={<CopyOutlined />} className="db-copy-btn" onClick={() => navigator.clipboard.writeText(`SELECT * FROM ${t.name} LIMIT 100;`)}>
            复制查询
          </Button>
        </div>
        <Table
          columns={t.columns.slice(0, 6).map(c => ({
            title: <Tooltip title={c.comment}>{c.name}</Tooltip>,
            dataIndex: c.name,
            key: c.name,
            ellipsis: true,
            width: 140,
            render: (v: unknown) => {
              if (v === null || v === undefined) return <span className="db-null">NULL</span>
              if (typeof v === 'number' && Math.abs(v) > 10000) return formatMoney(v)
              return String(v)
            }
          }))}
          dataSource={previewRows}
          rowKey="id"
          pagination={false}
          size="small"
          className="db-preview-table"
          scroll={{ x: 700 }}
        />
      </div>
    ),
  }))

  return (
    <div className="db-page">
      <div className="db-header">
        <div className="db-header-left">
          <BranchesOutlined style={{ color: '#00d4ff', marginRight: 10, fontSize: 18 }} />
          <span className="db-title">数据库总览</span>
          <Badge count={`4 张表`} style={{ backgroundColor: '#1e2a4a', color: '#8a9bcf', marginLeft: 8 }} />
        </div>
        <Space>
          <Button icon={<ThunderboltOutlined />} className="db-btn" onClick={() => openDrawer(MOCK_TABLES[0])}>
            SQL控制台
          </Button>
        </Space>
      </div>

      {/* 统计卡片 */}
      <div className="db-stats">
        <Row gutter={16}>
          {[
            { label: '总记录数', value: MOCK_TABLES.reduce((a, t) => a + t.rowCount, 0), icon: '📄', color: '#1677ff' },
            { label: '股票数量', value: 47, icon: '🏢', color: '#52c41a' },
            { label: '时间跨度', value: '2019-2024', icon: '📅', color: '#faad14' },
            { label: '核心指标', value: 18, icon: '📊', color: '#722ed1' },
          ].map(s => (
            <Col span={6} key={s.label}>
              <Card className="db-stat-card" style={{ '--stat-color': s.color } as React.CSSProperties} size="small">
                <Statistic
                  title={<span style={{ color: '#5a6a8a', fontSize: 12 }}>{s.icon} {s.label}</span>}
                  value={s.value}
                  valueStyle={{ color: s.color, fontSize: 22, fontWeight: 700 }}
                />
              </Card>
            </Col>
          ))}
        </Row>
      </div>

      {/* 表切换 */}
      <div className="db-tabs-area">
        <Tabs
          items={tabItems}
          className="db-tabs"
          tabPosition="top"
          size="small"
        />
      </div>

      {/* 表结构抽屉 */}
      <Drawer
        title={
          <Space>
            <TableOutlined style={{ color: '#00d4ff' }} />
            表结构详情
          </Space>
        }
        placement="right"
        width={500}
        onClose={() => setDrawerOpen(false)}
        open={drawerOpen}
        className="db-drawer"
      >
        {selectedTable && (
          <>
            <Descriptions column={2} size="small" className="db-desc" bordered>
              <Descriptions.Item label="表名" span={2}>
                <Tag color={TABLE_COLORS[selectedTable.name as keyof typeof TABLE_COLORS]}>{selectedTable.name}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="中文名">{selectedTable.label}</Descriptions.Item>
              <Descriptions.Item label="记录数">
                <span style={{ color: '#52c41a', fontWeight: 600 }}>{selectedTable.rowCount.toLocaleString()}</span>
              </Descriptions.Item>
            </Descriptions>
            <div style={{ marginTop: 16 }}>
              <h4 className="db-col-title">字段列表</h4>
              <Table
                columns={[
                  { title: '字段名', dataIndex: 'name', key: 'name', render: (t: string) => <code style={{ color: '#8a9bcf' }}>{t}</code> },
                  { title: '类型', dataIndex: 'type', key: 'type', render: (t: string) => <Tag>{t}</Tag> },
                  { title: '注释', dataIndex: 'comment', key: 'comment', ellipsis: true },
                ]}
                dataSource={selectedTable.columns}
                rowKey="name"
                pagination={false}
                size="small"
              />
            </div>
          </>
        )}
      </Drawer>
    </div>
  )
}
