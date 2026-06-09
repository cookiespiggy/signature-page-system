---
name: ui-design-system
description: >-
  Applies the 签字页管理系统 black-and-gold law firm UI design system. Covers
  CSS tokens in index.css, layout components (AppLayout, PageHeader, GoldPanel),
  typography, spacing, and forbidden patterns (hardcoded colors, light theme).
  Use when creating or modifying any frontend component, page, or styling in
  frontend/src/.
---

# UI 设计规范 — 黑金律所风

## 三层防跑偏

| 层级 | 位置 |
|------|------|
| Agent 规则 | `.cursor/rules/002-frontend.mdc` |
| 设计 Token | `frontend/src/index.css` `:root` |
| 布局组件 | `frontend/src/components/layout/` |

**流程**：先找可复用组件 → 写业务内容 → 对照 Checklist。

## 色彩（禁止写死颜色）

只用 Tailwind 语义 class，颜色定义在 `index.css` `:root`：

```
background / foreground / card / primary / muted / border / destructive
```

金色边框透明度：
- 分隔线、面板：`border-primary/15`
- 按钮、输入框：`border-primary/25` ~ `/30`
- 表头、Badge：`border-primary/35` ~ `/50`

### 禁止

- ❌ `bg-white`、`bg-blue-500`、`text-gray-900`
- ❌ 内联 `style={{ color: '#D4AF37' }}`
- ❌ 亮色主题切换
- ❌ AI 区域蓝色边框（统一金色）

## 字体

| 场景 | 用法 |
|------|------|
| 标题、品牌 | `font-heading`（Playfair Display） |
| 正文、表单 | 默认 sans（Geist） |
| 英文副标签 | `text-[11px] tracking-[0.25em] text-primary/70 uppercase` |

## 布局组件

```tsx
// 页面骨架
<div className="space-y-8">
  <PageHeader englishLabel="..." title="..." description="..." action={...} />
  <GoldPanel>{/* 主内容 */}</GoldPanel>
</div>
```

- 页面级间距：`space-y-8`
- 宽度：由 `AppLayout` 的 `max-w-6xl` 控制，页面内不再套 max-width

## 典型模式

```tsx
// 主按钮
<Button className="border border-primary/30 bg-primary text-primary-foreground hover:bg-primary/90">

// AI 卡片
<GoldPanel className="border-primary/30 p-4">
  <Badge className="border-primary/40 bg-primary/10 text-primary">AI</Badge>
</GoldPanel>
```

## 变更流程

调整整体风格时：**只改** `index.css` `:root` → 同步本文档 → `npm run build`。**不要**逐页改 class。

## 参考文件

| 文件 | 说明 |
|------|------|
| `frontend/src/index.css` | Token 定义 |
| `frontend/src/components/layout/AppLayout.tsx` | 顶栏 |
| `frontend/src/pages/ListPage.tsx` | 完整范例 |

更多场景示例见 [reference.md](reference.md)。
