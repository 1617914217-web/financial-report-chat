import { useState } from 'react'
import { Input, Button, Table, Tag, Space, Popconfirm } from 'antd'
import {
  SearchOutlined, PlusOutlined, UploadOutlined, DeleteOutlined,
  FilePdfOutlined, FileTextOutlined, GlobalOutlined, EditOutlined
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { KBDocument } from '../../types'
import './KnowledgeBasePage.css'

const MOCK_DATA: KBDocument[] = [
  { id: '1', title: '金花股份2023年年报.pdf', type: 'pdf', tags: ['年报', '2023'], createdAt: '2026-04-10', updatedAt: '2026-04-10' },
  { id: '2', title: '万邦德2023年半年报.pdf', type: 'pdf', tags: ['半年报', '2023'], createdAt: '2026-04-10', updatedAt: '2026-04-10' },
  { id: '3', title: '贵州茅台招股说明书.pdf', type: 'pdf', tags: ['招股书'], createdAt: '2026-04-08', updatedAt: '2026-04-08' },
  { id: '4', title: '证监会财务规则.pdf', type: 'pdf', tags: ['法规', '财务'], createdAt: '2026-04-05', updatedAt: '2026-04-05' },
  { id: '5', title: '行业分析笔记', type: 'note', tags: ['笔记', '行业'], createdAt: '2026-04-03', updatedAt: '2026-04-03' },
]

const TYPE_ICON = { pdf: <FilePdfOutlined />, doc: <FileTextOutlined />, url: <GlobalOutlined />, note: <EditOutlined /> }
const TYPE_COLOR: Record<string, string> = { pdf: 'red', doc: 'blue', url: 'green', note: 'orange' }

export default function KnowledgeBasePage() {
  const [data] = useState<KBDocument[]>(MOCK_DATA)
  const [keyword, setKeyword] = useState('')

  const filtered = data.filter(d =>
    d.title.includes(keyword) || d.tags.some(t => t.includes(keyword))
  )

  const columns: ColumnsType<KBDocument> = [
    {
      title: '文件名',
      key: 'title',
      render: (_, r) => (
        <span className="kb-title-cell">
          <span className="kb-icon">{TYPE_ICON[r.type]}</span>
          {r.title}
        </span>
      ),
    },
    {
      title: '类型',
      dataIndex: 'type',
      width: 90,
      render: t => <Tag color={TYPE_COLOR[t]}>{t.toUpperCase()}</Tag>,
    },
    {
      title: '标签',
      key: 'tags',
      render: (_, r) => (
        <Space size={4} wrap>
          {r.tags.map(tag => <Tag key={tag} className="kb-tag">{tag}</Tag>)}
        </Space>
      ),
    },
    {
      title: '更新时间',
      dataIndex: 'updatedAt',
      width: 110,
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: () => (
        <Space>
          <Button type="text" size="small" icon={<EditOutlined />} className="kb-action-btn" />
          <Popconfirm title="确定删除？" okText="删除">
            <Button type="text" size="small" danger icon={<DeleteOutlined />} className="kb-action-btn" />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div className="kb-page">
      <div className="kb-header">
        <div className="kb-header-left">
          <h2 className="kb-page-title">📚 知识库</h2>
          <span className="kb-count">共 {filtered.length} 个文档</span>
        </div>
        <Space>
          <Button icon={<UploadOutlined />} className="kb-upload-btn">
            上传文件
          </Button>
          <Button type="primary" icon={<PlusOutlined />}>
            添加笔记
          </Button>
        </Space>
      </div>

      <div className="kb-toolbar">
        <Input
          prefix={<SearchOutlined style={{ color: '#5a6a8a' }} />}
          placeholder="搜索文档名称或标签..."
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          className="kb-search"
          allowClear
        />
      </div>

      <div className="kb-body">
        {/* 分类卡片 */}
        <div className="kb-category-cards">
          {[
            { label: '年报', count: 12, color: '#1677ff' },
            { label: '半年报', count: 8, color: '#52c41a' },
            { label: '季报', count: 24, color: '#faad14' },
            { label: '法规', count: 5, color: '#f5222d' },
            { label: '笔记', count: 17, color: '#722ed1' },
          ].map(cat => (
            <div key={cat.label} className="kb-cat-card" style={{ '--cat-color': cat.color } as React.CSSProperties}>
              <div className="kb-cat-count">{cat.count}</div>
              <div className="kb-cat-label">{cat.label}</div>
            </div>
          ))}
        </div>

        {/* 文档列表 */}
        <div className="kb-table-wrap">
          <Table
            columns={columns}
            dataSource={filtered}
            rowKey="id"
            pagination={{ pageSize: 10, size: 'small' }}
            className="kb-table"
            size="middle"
          />
        </div>
      </div>
    </div>
  )
}
