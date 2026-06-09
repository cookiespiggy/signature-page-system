# UI 全流程录屏演示报告

> 工具: Playwright（Chromium `recordVideo`）  
> 时间: 2026/6/9 13:11:26  
> 项目: Playwright演示-202606090510

## 为什么选择 Playwright 而非 agent-browser？

| 维度 | Playwright | agent-browser |
|------|-----------|---------------|
| 录屏 | 内置 `recordVideo`，一条配置即可 | 需额外 ffmpeg / 系统录屏 |
| React 表单 | `fill()` 原生支持受控组件 | 日期等字段需 InputEvent hack |
| 选择器 | `getByRole` / `getByLabel` 语义化、稳定 | snapshot ref 随页面变化，脚本易碎 |
| 项目集成 | Session 6 已有完整 E2E 脚本 | 零集成，需从零摸索 |
| 适用场景 | **确定性演示 / 回归测试** | **AI Agent 探索未知 UI** |

## 流程

```
列表页 → 新建项目 → 选模板(×3) → 填变量 → AI去重/校验 → 生成 → ZIP下载 → 返回列表
```

## 步骤结果

| # | 步骤 | 状态 | 备注 |
|---|------|------|------|
| 1 | 项目列表页 | PASS |  |
| 2 | 新建项目 | PASS | Playwright演示-202606090510 |
| 3 | 进入项目详情 · Step 1 | PASS |  |
| 4 | 选择 3 个预置模板 | PASS |  |
| 5 | 进入 Step 2 · 变量填写 | PASS |  |
| 6 | 填写变量 | PASS |  |
| 7 | AI 智能去重 | PASS |  |
| 8 | AI 校验 | PASS |  |
| 9 | 进入 Step 3 · 生成下载 | PASS |  |
| 10 | 确认生成 | PASS |  |
| 11 | 异步生成 Word | PASS |  |
| 12 | ZIP 打包下载 | PASS | project_12_all_20260609_051124.zip |
| 13 | 返回项目列表 | PASS |  |

## 录屏文件

- `demo/demo-recording.webm` — 浏览器窗口内录屏（1440×900）
