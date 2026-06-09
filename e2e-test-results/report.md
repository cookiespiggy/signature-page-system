# E2E 测试报告

## 测试结果汇总

| # | 测试项 | 结果 | 截图 | 备注 |
|---|--------|------|------|------|
| 1.1 | 页面加载 | PASS | 有 | 项目列表、新建按钮、黑金 UI |
| 1.2 | 创建项目 | PASS | 有 | E2E测试-IPO签字页 草稿 |
| 1.3 | 进入项目详情 | PASS | 有 | 三步导航 Step1 高亮 |
| 2.1 | 模板列表渲染 | PASS | 有 | 见 2.4，3 个预置模板卡片 |
| 2.2 | 搜索功能 | PASS | 有 | 搜索「律所」仅 1 个结果 |
| 2.3 | 分类筛选 | FAIL | 有 | 「股东」分类无结果，预期 2 个模板 |
| 2.4 | 选择全部模板 | PASS | 有 | 3 模板选中高亮 |
| 2.5 | 展开模板详情 | PASS | 有 | 变量 key 列表可见 |
| 2.6 | 进入 Step 2 | PASS | 有 | 变量表单加载 |
| 3.1 | 变量分组渲染 | PASS | 有 | 公司/律师/会议等分组，去重正常 |
| 3.2 | 填写核心变量 | PASS | 有 | 核心字段已填写 |
| 3.3 | AI 去重 | DEGRADED | 有 | AI 服务不可用降级 Banner |
| 3.4 | AI 校验 | PASS | 有 | 校验报告展示 11 条（含误报必填未填） |
| 3.5 | 进入 Step 3 | PASS | 有 | 生成下载步骤，变量已保存 toast |
| 4.1 | 变量确认弹窗 | PASS | 有 |  |
| 4.2 | 确认生成 | PASS | 有 | 进度条/日志面板出现 |
| 4.3 | 等待生成完成 | PASS | 有 | 3/3 完成 |
| 4.4 | 文件列表 | PASS | 有 | 预览:true 下载:true |
| 4.5 | 打包下载 ZIP | PASS | 有 | 文件: project_8_all_20260609_045057.zip |
| 5.1 | 回退 Step 2 | PASS | 有 | 值=测试科技股份有限公司 |
| 5.2 | 回退 Step 1 | PASS | 有 | 3 个模板 checkbox 仍选中，金色边框 |
| 6.1 | 返回列表 | PASS | 有 |  |
| 6.2 | 删除项目 | PASS | 有 |  |

## 发现的问题

### 1. ~~分类筛选「股东」无结果（Test 2.3 FAIL）~~ 已修复

~~点击「股东」分类后显示「未找到匹配的模板」~~  
**原因**：预置模板 category 为 `natural_shareholder` / `institutional_shareholder`，前端筛选用 `shareholder` 做精确匹配。  
**修复**：`TemplateStep.tsx` 改为按 category 包含关系匹配（如 `shareholder` 匹配 `*_shareholder*`）。  
验证截图: `e2e-test-results/screenshots/fix-2.3-shareholder-filter.png`

### 2. ~~AI 校验报告与表单状态不一致~~ 已修复

~~表单已填值但报告仍报「必填变量未填写」~~  
**原因**：AI 校验读数据库，用户填表后未保存时 DB 仍为空。  
**修复**：`VariableStep.tsx` 在 AI 去重/校验前自动 `persistFields()` 保存当前表单。  
验证截图: `e2e-test-results/screenshots/fix-3.4-ai-validate-saved.png`

## 截图清单

- e2e-test-results/screenshots/1.1-page-load.png
- e2e-test-results/screenshots/1.2-create-project.png
- e2e-test-results/screenshots/1.3-project-detail.png
- e2e-test-results/screenshots/2.2-search-filter.png
- e2e-test-results/screenshots/2.3-category-filter-bug.png
- e2e-test-results/screenshots/2.4-select-all-templates.png
- e2e-test-results/screenshots/2.5-template-details.png
- e2e-test-results/screenshots/2.6-step2-variables.png
- e2e-test-results/screenshots/3.1-variable-groups.png
- e2e-test-results/screenshots/3.2-fill-variables.png
- e2e-test-results/screenshots/3.3-ai-dedup-loading.png
- e2e-test-results/screenshots/3.3-ai-dedup-degraded.png
- e2e-test-results/screenshots/3.4-ai-validate-loading.png
- e2e-test-results/screenshots/3.4-ai-validate-result.png
- e2e-test-results/screenshots/3.5-step3-generate.png
- e2e-test-results/screenshots/4.1-confirm-dialog.png
- e2e-test-results/screenshots/4.2-generation-progress.png
- e2e-test-results/screenshots/4.3-generation-complete.png
- e2e-test-results/screenshots/4.4-file-list.png
- e2e-test-results/screenshots/4.5-zip-download.png
- e2e-test-results/screenshots/5.1-back-to-step2.png
- e2e-test-results/screenshots/5.2-back-to-step1.png
- e2e-test-results/screenshots/6.1-back-to-list.png
- e2e-test-results/screenshots/6.2-delete-dialog.png
- e2e-test-results/screenshots/6.2-delete-complete.png

## 总结

- 通过: 21 / 总计: 23
- 失败: 1
- 降级 (AI): 1
- 测试时间: 2026-06-09T04:51:08.139Z
- 执行: 前序 agent Phase 1–2 + Test 3.2/3.3；本 session 续跑 Test 3.1/3.4/3.5 及 Phase 4–6
