# UI 设计规范 — 高端律所黑金风

> **受众**：前端 Session（5a-2 / 5b 及后续）、任何修改 `frontend/` 的 Agent。
> **原则**：风格通过 **Token + 复用组件** 约束，而不是靠记忆。

---

## 1. 三层防跑偏机制

| 层级 | 位置 | 作用 |
|------|------|------|
| **Agent 规则** | `.cursor/rules/002-frontend.mdc` | 每个前端 Session 自动加载，含 Checklist |
| **设计 Token** | `frontend/src/index.css` `:root` | 唯一改色入口，组件只引用语义 class |
| **布局组件** | `frontend/src/components/layout/` | 页面骨架复用，减少「各写各的」 |

新增页面时：**先找可复用组件 → 再写业务内容 → 最后对照 Checklist**。

---

## 2. 色彩 Token（禁止在 TSX 里写死颜色）

所有颜色定义在 `frontend/src/index.css` 的 `:root`。组件内只用 Tailwind 语义 class：

```
background / foreground     页面底与正文
card / card-foreground      面板
primary / primary-foreground  香槟金强调
muted / muted-foreground    次要文字
border / input / ring       边框与焦点
destructive                 仅危险操作
```

### 金色边框透明度约定
- 分隔线、页眉底边：`border-primary/15`
- 面板、卡片：`border-primary/15`（配合 `gold-panel`）
- 按钮描边、输入框：`border-primary/25` ~ `/30`
- 表头、强调 Badge：`border-primary/35` ~ `/50`

### 禁止事项
- ❌ `bg-white`、`bg-blue-500`、`text-gray-900` 等 Tailwind 默认调色板
- ❌ 组件内 `style={{ color: '#D4AF37' }}` 或内联 `oklch(...)`
- ❌ 引入浅色/亮色主题切换（当前产品定位为固定深色黑金）
- ❌ AI 区域使用蓝色边框（旧方案已废弃，统一金色）

---

## 3. 字体

| 场景 | 用法 |
|------|------|
| 页面标题、区块标题、品牌 | `font-heading` 或 h1–h4（Playfair Display） |
| 正文、表格、表单 | 默认 sans（Geist Variable） |
| 英文副标签 | `text-[11px] tracking-[0.25em] text-primary/70 uppercase` |

---

## 4. 布局组件 API

### `AppLayout`
全局壳：顶栏（天平图标 + 双语品牌 + 金色分隔线）+ `<Outlet />`。

### `PageHeader`
```tsx
<PageHeader
  englishLabel="Template Selection"  // 可选
  title="选择模板"
  description="说明文案"
  action={<Button>...</Button>}        // 可选，右侧操作
/>
```

### `GoldPanel`
```tsx
<GoldPanel>表格或表单内容</GoldPanel>
<GoldPanel dashed className="p-12 text-center">空状态</GoldPanel>
```

---

## 5. 典型页面结构模板

```tsx
export function SomePage() {
  return (
    <div className="space-y-8">
      <PageHeader englishLabel="..." title="..." description="..." action={...} />
      <GoldPanel>
        {/* 主内容 */}
      </GoldPanel>
    </div>
  )
}
```

间距约定：
- 页面级纵向：`space-y-8`
- 页眉与内容：`PageHeader` 自带 `pb-6` + 底部分隔线
- 水平宽度：由 `AppLayout` 的 `max-w-6xl` 统一控制，页面内不要再套一层 max-width

---

## 6. 场景示例

### 主按钮
```tsx
<Button className="border border-primary/30 bg-primary text-primary-foreground hover:bg-primary/90">
```

### 表格
```tsx
<GoldPanel className="overflow-hidden">
  <Table>
    <TableHeader>
      <TableRow className="border-primary/15 hover:bg-transparent">
        <TableHead className="text-xs tracking-wider text-primary/80 uppercase">...</TableHead>
```

### 状态 Badge
- 完成：金色填充系 `border-primary/35 bg-primary/15 text-primary`
- 进行中：同上 + 金色 pulse 圆点
- 草稿：`variant="outline"` + muted 色

### AI 卡片（Session 5b 预留）
```tsx
<GoldPanel className="border-primary/30 p-4">
  <Badge className="border-primary/40 bg-primary/10 text-primary">AI</Badge>
  ...
</GoldPanel>
```

---

## 7. 参考文件（改 UI 前先打开看一遍）

| 文件 | 说明 |
|------|------|
| `frontend/src/index.css` | Token 与 `gold-panel` / `gold-divider` |
| `frontend/src/components/layout/AppLayout.tsx` | 顶栏 |
| `frontend/src/pages/ListPage.tsx` | 列表 + 表格 + 对话框完整范例 |

---

## 8. 变更流程

若需调整整体风格（例如 gold 色相、背景深度）：
1. **只改** `index.css` `:root` Token
2. 同步更新本文档「色彩 Token」说明
3. 跑 `npm run build` 确认无回归
4. **不要**逐个页面改 class
