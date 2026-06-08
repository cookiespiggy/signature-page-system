# 签字页管理系统 MVP - Session 开发计划

## 依赖图
```
Session 1a (后端初始化+数据层)
  └─> Session 1b (后端 API + LLM 抽象层)
        ├─> Session 2 (模板管理 + AI 解析)
        ├─> Session 3 (变量填写 + AI 去重校验)
        └─> Session 4 (文档生成 + 异步下载)
              └─> Session 5a-1 (前端初始化 + 列表页)
                    └─> Session 5a-2 (前端详情页)
                          └─> Session 5b (前端 AI 集成)
                                └─> Session 6 (联调测试)
                                      └─> Session 7 (报告)
```

## Session 清单

| Session | 对应 Task | 内容 | 耗时估计 |
|---------|-----------|------|---------|
| 1a | Task 1a | 后端项目脚手架 + 数据模型 + Alembic + variable_registry | ~200 行 |
| 1b | Task 1b | LLMProvider 抽象层 + 项目 CRUD API + health check | ~300 行 |
| 2 | Task 2 | 3 个 Word模板 + 模板管理 API + AI 解析 | ~400 行 |
| 3 | Task 3 | 变量去重/保存/Excel/AI去重校验 API | ~400 行 |
| 4 | Task 4 | 异步生成 ThreadPoolExecutor + 取消 + 下载 | ~300 行 |
| 5a-1 | Task 5a-1 | 前端初始化 + 项目列表页 | ~300 行 |
| 5a-2 | Task 5a-2 | 前端三步流程详情页 | ~500 行 |
| 5b | Task 5b | 前端 AI 功能集成 | ~200 行 |
| 6 | Task 6 | 联调 + pytest | ~200 行 |
| 7 | Task 7 | 报告 | ~50 行 |

## 当前状态
- 开始时间: 2026-06-08
- 当前 Session: 1a（待启动）
- 上一个 Session: 无
