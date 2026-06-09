# UI 设计规范 — 完整参考

> 源文档：`docs/knowledge-base/UI设计规范.md`

## PageHeader API

```tsx
<PageHeader
  englishLabel="Template Selection"
  title="选择模板"
  description="说明文案"
  action={<Button>...</Button>}
/>
```

## GoldPanel API

```tsx
<GoldPanel>表格或表单内容</GoldPanel>
<GoldPanel dashed className="p-12 text-center">空状态</GoldPanel>
```

## 表格样式

```tsx
<GoldPanel className="overflow-hidden">
  <Table>
    <TableHeader>
      <TableRow className="border-primary/15 hover:bg-transparent">
        <TableHead className="text-xs tracking-wider text-primary/80 uppercase">...</TableHead>
```

## 状态 Badge

- 完成/进行中：金色 `border-primary/35 bg-primary/15 text-primary`
- 草稿：`variant="outline"` + muted 色
