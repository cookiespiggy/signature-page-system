# Session Handoff: 5a-2 - 前端详情页（三步流程）

## 已完成
- 实现 `DetailPage` 三步流程框架：StepNav 导航 + 步骤切换 + 状态流转
- **Step 1 模板选择**：卡片网格、多选、搜索/分类筛选、预置/自定义徽标、详情展开、上传自定义模板（AI 解析 + 创建）、移除模板、模板更新刷新
- **Step 2 变量填写**：按 category 分组、multiple 变量动态增减、基础正则实时校验、Excel 导入预览/确认/错误报告下载、模板/数据导出、beforeunload 防丢
- **Step 3 生成下载**：生成前变量确认弹窗、异步生成 + 指数退避轮询（2s→4s→8s→max 10s）、取消生成、文件列表、单文件/ZIP 下载
- 扩展 `services/api.ts` — templatesApi / variablesApi / generationApi + FormData 上传 + Blob 下载
- 新增类型定义 `types/template.ts`、`types/variable.ts`、`types/generation.ts`
- 新增工具 `lib/validation.ts`、`lib/variable-utils.ts`
- 后端小补丁：`variable_service.save_variables` 支持 multiple 变量动态新增行（如 handling_lawyer_3）

## 文件变更
- `frontend/src/pages/DetailPage.tsx` — **[重写]** 三步流程主页面
- `frontend/src/components/detail/StepNav.tsx` — **[新增]** 步骤导航
- `frontend/src/components/detail/TemplateStep.tsx` — **[新增]** Step 1
- `frontend/src/components/detail/VariableStep.tsx` — **[新增]** Step 2
- `frontend/src/components/detail/GenerationStep.tsx` — **[新增]** Step 3
- `frontend/src/services/api.ts` — 扩展模板/变量/生成 API
- `frontend/src/types/` — template / variable / generation 类型
- `frontend/src/lib/validation.ts`、`variable-utils.ts` — **[新增]**
- `backend/app/services/variable_service.py` — multiple 行 auto-create

## 当前状态
- `npm run build` 构建成功
- **DoD 全部验证通过**：
  - 三步 API 流程：选模板 → 填变量 → 生成 → 下载（curl E2E）
  - multiple 变量动态新增行 save 成功（handling_lawyer_3）
  - 前端 TypeScript 编译无错误
- 启动命令：
  ```bash
  # 后端（VM 内）
  orb -m oh-agent LLM_PROVIDER=mock uv run --directory /Users/jimmy/Workspaces/junhe-mvp/backend uvicorn app.main:app --port 8000 --host 0.0.0.0
  
  # 前端（宿主机）
  cd frontend && npm run dev
  ```

## 遗留问题
- 本机 macOS `localhost:8000` 被 omlx 占用，已通过 `.env.development` 指向 OrbStack VM IP（`198.19.249.128`）；VM IP 变更时需更新
- AI 解析结果展示、AI 去重/校验 UI 留待 Session 5b
- 模板上传后 AI 解析仅展示变量列表，无采纳/修正/删除交互（5b 实现）

## 下一个 Session
继续 Session 5b: 前端 AI 功能集成
需要读取此 handoff + AGENTS.md 中 Session 5b 章节
