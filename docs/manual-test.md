# 签字页管理系统 — 完整手动测试指南

> 环境：后端 `http://localhost:8000`  
> 前置条件：`LONGCAT_API_KEY` 已设置，已执行 `alembic upgrade head`

---

## 目录

1. [健康检查](#1-健康检查)
2. [项目 CRUD](#2-项目-crud)
3. [模板管理](#3-模板管理)
4. [项目-模板关联](#4-项目-模板关联)
5. [变量填写与操作](#5-变量填写与操作)
6. [AI 功能](#6-ai-功能)
7. [文档生成与下载](#7-文档生成与下载)
8. [Excel 导入导出](#8-excel-导入导出)
9. [异常场景](#9-异常场景)

---

## 1. 健康检查

### 1.1 正常健康检查

```bash
curl -s http://localhost:8000/api/health | python3 -m json.tool
```

预期响应：

```json
{
    "status": "ok",
    "database": "connected",
    "llm_provider": "longcat",
    "llm_available": true
}
```

---

## 2. 项目 CRUD

### 2.1 创建项目

```bash
curl -s -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "海通证券 IPO 法律意见书签字页项目"}' \
  | python3 -m json.tool
```

预期响应（201 Created）：

```json
{
    "id": 1,
    "name": "海通证券 IPO 法律意见书签字页项目",
    "status": "draft",
    "created_at": "2026-06-21T10:00:00",
    "updated_at": "2026-06-21T10:00:00"
}
```

### 2.2 再创建两个项目（供列表测试）

```bash
# 项目 2
curl -s -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "中芯国际股东大会签字页项目"}' \
  | python3 -m json.tool

# 项目 3
curl -s -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "字节跳动融资签字页项目"}' \
  | python3 -m json.tool
```

### 2.3 项目列表

```bash
curl -s http://localhost:8000/api/projects | python3 -m json.tool
```

预期响应：按 `updated_at` 降序排列的 3 个项目列表。

### 2.4 获取单个项目

```bash
curl -s http://localhost:8000/api/projects/1 | python3 -m json.tool
```

### 2.5 更新项目

```bash
curl -s -X PUT http://localhost:8000/api/projects/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "海通证券 IPO 法律意见书签字页项目（已更新）"}' \
  | python3 -m json.tool
```

### 2.6 删除项目

```bash
curl -s -o /dev/null -w "HTTP %{http_code}" -X DELETE http://localhost:8000/api/projects/3
```

预期：204 No Content。

验证删除：

```bash
curl -s -w "\nHTTP %{http_code}" http://localhost:8000/api/projects/3
```

预期 404：

```json
{"detail": "项目 3 不存在"}
```

---

## 3. 模板管理

### 3.1 模板列表

```bash
curl -s http://localhost:8000/api/templates | python3 -m json.tool
```

预期响应（3 个预置模板）：

```json
[
    {
        "id": 1,
        "name": "律所签字页",
        "description": "适用于律所出具法律意见书的签字页",
        "category": "lawyer_signing",
        "tags": ["IPO", "法律意见书", "律所"],
        "applicable_scenarios": "IPO 上市项目法律意见书",
        "variable_count": 8,
        "is_preset": true,
        "variables_json": [
            {"key": "target_company_name", "label": "目标公司名称", "category": "company", "data_type": "company_name", "required": true, "is_multiple": false},
            {"key": "law_firm_name", "label": "律师事务所名称", "category": "lawyer", "data_type": "company_name", "required": true, "is_multiple": false},
            {"key": "law_firm_director", "label": "律师事务所负责人", "category": "lawyer", "data_type": "text", "required": true, "is_multiple": false},
            {"key": "handling_lawyer", "label": "经办律师", "category": "lawyer", "data_type": "text", "required": true, "is_multiple": true},
            {"key": "signing_date", "label": "签署日期", "category": "date", "data_type": "date", "required": true, "is_multiple": false},
            {"key": "exchange_name", "label": "交易所名称", "category": "company", "data_type": "text", "required": false, "is_multiple": false},
            {"key": "document_type", "label": "文件类型", "category": "document", "data_type": "text", "required": false, "is_multiple": false},
            {"key": "target_investor_type", "label": "投资者类型", "category": "document", "data_type": "text", "required": false, "is_multiple": false}
        ],
        "version": 1,
        "is_preset": true
    },
    {
        "id": 2,
        "name": "自然人股东签字页",
        "variable_count": 6,
        "is_preset": true
    },
    {
        "id": 3,
        "name": "机构股东签字页",
        "variable_count": 6,
        "is_preset": true
    }
]
```

### 3.2 获取单个模板

```bash
curl -s http://localhost:8000/api/templates/1 | python3 -m json.tool
```

### 3.3 上传自定义模板（AI 解析 → 创建）

**步骤 A：先上传解析，看看 AI 识别出哪些变量**

```bash
# 准备一个自定义模板文件（可跳过，仅演示 AI 解析流程）
# 使用预置模板文件演示解析
curl -s -X POST http://localhost:8000/api/templates/parse \
  -F "file=@backend/app/templates/law_firm_signing_page.docx" \
  | python3 -m json.tool
```

预期响应示例（Mock 模式）：

```json
{
    "variables": [
        {"key": "law_firm_name", "label": "律师事务所名称", "category": "company", "data_type": "company_name", "required": true, "is_registered": true, "trust_level": "high", "warnings": []},
        {"key": "law_firm_director", "label": "律师事务所负责人", "category": "lawyer", "data_type": "text", "required": true, "is_registered": true, "trust_level": "high", "warnings": []},
        {"key": "handling_lawyer", "label": "经办律师", "category": "lawyer", "data_type": "text", "required": true, "is_multiple": true, "is_registered": true, "trust_level": "high", "warnings": []}
    ],
    "ai_used": true,
    "parse_duration_ms": 1234
}
```

**步骤 B：用解析结果创建自定义模板**

```bash
curl -s -X POST http://localhost:8000/api/templates \
  -F "file=@backend/app/templates/law_firm_signing_page.docx" \
  -F "name=君合律所专用签字页模板" \
  -F "description=君合律师事务所定制的签字页模板" \
  -F "category=lawyer_signing" \
  -F "tags=[\"君合\",\"法律意见书\",\"定制\"]" \
  -F "applicable_scenarios=君合律所 IPO 项目签字页" \
  -F 'variables_json=[{"key":"law_firm_name","label":"律师事务所名称","category":"lawyer","data_type":"company_name","required":true},{"key":"law_firm_director","label":"律师事务所负责人","category":"lawyer","data_type":"text","required":true},{"key":"handling_lawyer","label":"经办律师","category":"lawyer","data_type":"text","required":true,"is_multiple":true},{"key":"signing_date","label":"签署日期","category":"date","data_type":"date","required":true}]' \
  -F "register_custom_variables=true" \
  | python3 -m json.tool
```

预期（201 Created）：

```json
{
    "id": 4,
    "name": "君合律所专用签字页模板",
    "category": "lawyer_signing",
    "is_preset": false,
    "variable_count": 4,
    "version": 1
}
```

### 3.4 更新自定义模板

```bash
curl -s -X PUT http://localhost:8000/api/templates/4 \
  -F "name=君合律所专用签字页模板-v2" \
  -F 'tags=["君合","法律意见书","定制","v2"]' \
  -F 'variables_json=[{"key":"law_firm_name","label":"律师事务所名称","category":"lawyer","data_type":"company_name","required":true},{"key":"law_firm_director","label":"律师事务所负责人","category":"lawyer","data_type":"text","required":true},{"key":"handling_lawyer","label":"经办律师","category":"lawyer","data_type":"text","required":true,"is_multiple":true},{"key":"signing_date","label":"签署日期","category":"date","data_type":"date","required":true},{"key":"law_firm_phone","label":"律所电话","category":"lawyer","data_type":"text","required":false}]' \
  | python3 -m json.tool
```

预期：`version` 变为 2，`variable_count` 变为 5。

### 3.5 删除自定义模板

```bash
curl -s -o /dev/null -w "HTTP %{http_code}" -X DELETE http://localhost:8000/api/templates/4
```

预期：204。

### 3.6 尝试删除预置模板（应返回 403）

```bash
curl -s -w "\nHTTP %{http_code}" -X DELETE http://localhost:8000/api/templates/1
```

预期 403：

```json
{"detail": "预置模板不可删除"}
```

---

## 4. 项目-模板关联

### 4.1 为项目选择模板（多选）

```bash
# 项目 1 选模板 1（律所签字页）+ 模板 3（机构股东签字页）
curl -s -X POST http://localhost:8000/api/projects/1/templates \
  -H "Content-Type: application/json" \
  -d '{"template_ids": [1, 3]}' \
  | python3 -m json.tool
```

预期（201 Created），返回 2 个 ProjectTemplate 记录：

```json
[
    {
        "id": 1,
        "project_id": 1,
        "template_id": 1,
        "template_version": 1,
        "variables_snapshot_json": [ ... ],
        "needs_refresh": false,
        "latest_template_version": 1
    },
    {
        "id": 2,
        "project_id": 1,
        "template_id": 3,
        "template_version": 1,
        "variables_snapshot_json": [ ... ],
        "needs_refresh": false,
        "latest_template_version": 1
    }
]
```

### 4.2 查看项目的模板列表

```bash
curl -s http://localhost:8000/api/projects/1/templates | python3 -m json.tool
```

### 4.3 刷新模板版本

选完模板后修改模板，然后刷新：

先更新模板 1 增加一个新变量：

```bash
curl -s -X PUT http://localhost:8000/api/templates/1 \
  -F 'variables_json=[{"key":"target_company_name","label":"目标公司名称","category":"company","data_type":"company_name","required":true},{"key":"law_firm_name","label":"律师事务所名称","category":"lawyer","data_type":"company_name","required":true},{"key":"law_firm_director","label":"律师事务所负责人","category":"lawyer","data_type":"text","required":true},{"key":"handling_lawyer","label":"经办律师","category":"lawyer","data_type":"text","required":true,"is_multiple":true},{"key":"signing_date","label":"签署日期","category":"date","data_type":"date","required":true},{"key":"exchange_name","label":"交易所名称","category":"company","data_type":"text","required":false},{"key":"document_type","label":"文件类型","category":"document","data_type":"text","required":false},{"key":"target_investor_type","label":"投资者类型","category":"document","data_type":"text","required":false},{"key":"law_firm_office_address","label":"律所办公地址","category":"lawyer","data_type":"text","required":false}]' \
  | python3 -m json.tool | grep -E '"version"|"variable_count"'
```

预期：version=2, variable_count=9。

现在刷新项目中的模板引用：

```bash
curl -s -X POST http://localhost:8000/api/projects/1/templates/1/refresh \
  | python3 -m json.tool
```

预期：

```json
{
    "added": 1,
    "removed": 0,
    "kept": 8
}
```

### 4.4 移除项目中的模板

```bash
curl -s -o /dev/null -w "HTTP %{http_code}" \
  -X DELETE http://localhost:8000/api/projects/1/templates/3
```

预期：204。

验证：

```bash
curl -s http://localhost:8000/api/projects/1/templates | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'剩余 {len(d)} 个模板')"
```

预期：剩余 1 个模板。

重新添加模板 3 供后续测试：

```bash
curl -s -X POST http://localhost:8000/api/projects/1/templates \
  -H "Content-Type: application/json" \
  -d '{"template_ids": [3]}' > /dev/null
```

---

## 5. 变量填写与操作

### 5.1 查看项目变量列表

选模板后自动去重合并，查看变量：

```bash
curl -s http://localhost:8000/api/projects/1/variables | python3 -m json.tool
```

预期响应（去重后变量列表，`is_merged` 为 `true` 表示跨模板共享变量）：

```json
{
    "variables": [
        {
            "key": "target_company_name",
            "label": "目标公司名称",
            "value": "",
            "category": "company",
            "data_type": "company_name",
            "required": true,
            "is_multiple": false,
            "sort_order": 1,
            "source_template_ids": [1, 3],
            "is_merged": true,
            "merged_from_keys": null,
            "updated_at": "2026-06-21T10:00:00"
        },
        {
            "key": "law_firm_name",
            "label": "律师事务所名称",
            "category": "lawyer",
            "data_type": "company_name",
            "required": true,
            "source_template_ids": [1],
            "is_merged": false,
            "sort_order": 2
        },
        {
            "key": "law_firm_director",
            "label": "律师事务所负责人",
            "category": "lawyer",
            "data_type": "text",
            "required": true,
            "source_template_ids": [1],
            "sort_order": 3
        },
        {
            "key": "handling_lawyer_1",
            "label": "经办律师",
            "value": "",
            "category": "lawyer",
            "data_type": "text",
            "required": true,
            "is_multiple": true,
            "sort_order": 4,
            "source_template_ids": [1]
        },
        {
            "key": "handling_lawyer_2",
            "label": "经办律师",
            "value": "",
            "category": "lawyer",
            "data_type": "text",
            "required": true,
            "is_multiple": true,
            "sort_order": 5,
            "source_template_ids": [1]
        },
        {
            "key": "signing_date",
            "label": "签署日期",
            "category": "date",
            "data_type": "date",
            "required": true,
            "is_merged": true,
            "source_template_ids": [1, 3],
            "sort_order": 6
        },
        {
            "key": "exchange_name",
            "label": "交易所名称",
            "category": "company",
            "data_type": "text",
            "required": false,
            "sort_order": 7,
            "source_template_ids": [1]
        },
        {
            "key": "document_type",
            "label": "文件类型",
            "category": "document",
            "data_type": "text",
            "required": false,
            "sort_order": 8,
            "source_template_ids": [1]
        },
        {
            "key": "target_investor_type",
            "label": "投资者类型",
            "category": "document",
            "data_type": "text",
            "required": false,
            "sort_order": 9,
            "source_template_ids": [1]
        },
        {
            "key": "institutional_shareholder_name",
            "label": "机构股东名称",
            "category": "shareholder",
            "data_type": "company_name",
            "required": true,
            "sort_order": 10,
            "source_template_ids": [3]
        },
        {
            "key": "authorized_representative_name",
            "label": "授权代表姓名",
            "category": "shareholder",
            "data_type": "text",
            "required": true,
            "sort_order": 11,
            "source_template_ids": [3]
        },
        {
            "key": "meeting_year",
            "label": "股东大会年份",
            "category": "meeting",
            "data_type": "text",
            "required": true,
            "sort_order": 12,
            "source_template_ids": [3]
        },
        {
            "key": "meeting_session",
            "label": "股东大会次数",
            "category": "meeting",
            "data_type": "text",
            "required": true,
            "sort_order": 13,
            "source_template_ids": [3]
        }
    ]
}
```

### 5.2 填写变量值

先获取当前时间戳（后续乐观锁需要）：

```bash
# 先获取最新 updated_at
export VAR_UPDATED_AT=$(curl -s http://localhost:8000/api/projects/1/variables | python3 -c "
import sys, json
data = json.load(sys.stdin)
vars_data = {v['key']: v['updated_at'] for v in data['variables']}
print(json.dumps(vars_data))
")
echo $VAR_UPDATED_AT
```

逐行保存变量值：

```bash
# 批量保存变量
curl -s -X PUT http://localhost:8000/api/projects/1/variables \
  -H "Content-Type: application/json" \
  -d '{
    "variables": [
      {"key": "target_company_name", "value": "海通证券股份有限公司", "updated_at": "2026-06-21T10:00:00"},
      {"key": "law_firm_name", "value": "君合律师事务所上海分所", "updated_at": "2026-06-21T10:00:00"},
      {"key": "law_firm_director", "value": "张明", "updated_at": "2026-06-21T10:00:00"},
      {"key": "handling_lawyer_1", "value": "王芳", "updated_at": "2026-06-21T10:00:00"},
      {"key": "handling_lawyer_2", "value": "李强", "updated_at": "2026-06-21T10:00:00"},
      {"key": "signing_date", "value": "2026年6月21日", "updated_at": "2026-06-21T10:00:00"},
      {"key": "exchange_name", "value": "上海证券交易所", "updated_at": "2026-06-21T10:00:00"},
      {"key": "document_type", "value": "法律意见书", "updated_at": "2026-06-21T10:00:00"},
      {"key": "target_investor_type", "value": "合格机构投资者", "updated_at": "2026-06-21T10:00:00"},
      {"key": "institutional_shareholder_name", "value": "金石投资有限公司", "updated_at": "2026-06-21T10:00:00"},
      {"key": "authorized_representative_name", "value": "赵刚", "updated_at": "2026-06-21T10:00:00"},
      {"key": "meeting_year", "value": "2026", "updated_at": "2026-06-21T10:00:00"},
      {"key": "meeting_session", "value": "第一次", "updated_at": "2026-06-21T10:00:00"}
    ]
  }' \
  | python3 -m json.tool
```

预期响应：

```json
{
    "success": [
        {"key": "target_company_name", "value": "海通证券股份有限公司", "updated_at": "2026-06-21T10:00:01"},
        {"key": "law_firm_name", "value": "君合律师事务所上海分所", "updated_at": "..."},
        ...
    ],
    "errors": [],
    "summary": {"total": 13, "succeeded": 13, "failed": 0}
}
```

### 5.3 乐观锁冲突测试

用旧的 updated_at 提交：

```bash
curl -s -X PUT http://localhost:8000/api/projects/1/variables \
  -H "Content-Type: application/json" \
  -d '{
    "variables": [
      {"key": "target_company_name", "value": "旧值冲突测试", "updated_at": "2020-01-01T00:00:00"}
    ]
  }' \
  | python3 -m json.tool
```

预期冲突错误：

```json
{
    "success": [],
    "errors": [
        {"row": 1, "key": "target_company_name", "message": "数据已被其他操作修改，请刷新后重试"}
    ],
    "summary": {"total": 1, "succeeded": 0, "failed": 1}
}
```

### 5.4 动态新增 multiple 变量行

保存一个不存在的 `handling_lawyer_3`：

```bash
curl -s -X PUT http://localhost:8000/api/projects/1/variables \
  -H "Content-Type: application/json" \
  -d '{
    "variables": [
      {"key": "handling_lawyer_3", "value": "陈伟", "updated_at": null}
    ]
  }' \
  | python3 -m json.tool
```

预期：系统自动创建 handling_lawyer_3 并写入值。

### 5.5 不存在的变量保存

```bash
curl -s -X PUT http://localhost:8000/api/projects/1/variables \
  -H "Content-Type: application/json" \
  -d '{
    "variables": [
      {"key": "nonexistent_var", "value": "test", "updated_at": null}
    ]
  }' \
  | python3 -m json.tool
```

预期错误。

---

## 6. AI 功能

### 6.1 AI 变量去重

```bash
curl -s -X POST http://localhost:8000/api/projects/1/variables/ai-dedup \
  | python3 -m json.tool
```

预期响应：

```json
{
    "alias_suggestions": [],
    "ai_suggestions": [],
    "ai_used": true,
    "message": null
}
```

（如果 LLM 可用则 `ai_used=true`，否则 `ai_used=false`，`message` 提示降级信息）

### 6.2 应用去重建议

```bash
curl -s -X POST http://localhost:8000/api/projects/1/variables/apply-dedup \
  -H "Content-Type: application/json" \
  -d '{
    "suggestions": [
      {
        "keep_key": "law_firm_director",
        "merge_keys": ["firm_director"],
        "reason": "测试",
        "confidence": 0.9,
        "source": "ai"
      }
    ]
  }' \
  | python3 -m json.tool
```

预期：

```json
{"merged_rows": 0}
```

### 6.3 AI 数据校验

```bash
curl -s -X POST http://localhost:8000/api/projects/1/variables/ai-validate \
  | python3 -m json.tool
```

预期响应的 `regex_issues` 会包含对 `target_company_name` 格式的正则校验（值 `海通证券股份有限公司` 匹配 `.+(股份有限公司|有限责任公司)` 所以无 error）：

```json
{
    "regex_issues": [],
    "ai_issues": [],
    "issues": [],
    "ai_used": true,
    "message": null
}
```

### 6.4 校验触发正则错误

修改 `signing_date` 为非法格式：

```bash
# 先保存一个非法日期
curl -s -X PUT http://localhost:8000/api/projects/1/variables \
  -H "Content-Type: application/json" \
  -d '{
    "variables": [
      {"key": "signing_date", "value": "2026/06/21", "updated_at": null}
    ]
  }' > /dev/null

# 再校验
curl -s -X POST http://localhost:8000/api/projects/1/variables/ai-validate \
  | python3 -m json.tool
```

预期包含一条 regex error：

```json
{
    "regex_issues": [
        {
            "level": "error",
            "variable_key": "signing_date",
            "message": "变量 signing_date 的值不符合格式要求",
            "suggestion": "请修正格式后重试",
            "source": "regex"
        }
    ],
    ...
}
```

改回合法值：

```bash
curl -s -X PUT http://localhost:8000/api/projects/1/variables \
  -H "Content-Type: application/json" \
  -d '{
    "variables": [
      {"key": "signing_date", "value": "2026年6月21日", "updated_at": null}
    ]
  }' > /dev/null
```

---

## 7. 文档生成与下载

### 7.1 启动生成

```bash
curl -s -X POST http://localhost:8000/api/projects/1/generate \
  | python3 -m json.tool
```

预期（202 Accepted）：

```json
{
    "task_id": 1,
    "status": "pending"
}
```

### 7.2 轮询生成状态

```bash
# 立即查状态
curl -s http://localhost:8000/api/projects/1/generate/status \
  | python3 -m json.tool

# 3 秒后重试
sleep 3 && curl -s http://localhost:8000/api/projects/1/generate/status \
  | python3 -m json.tool
```

任务完成后的预期：

```json
{
    "id": 1,
    "project_id": 1,
    "status": "completed",
    "total_count": 2,
    "completed_count": 2,
    "error_message": null,
    "template_progress": [
        {
            "template_id": 1,
            "template_name": "律所签字页",
            "template_category": "lawyer_signing",
            "status": "completed",
            "file_id": 1
        },
        {
            "template_id": 3,
            "template_name": "机构股东签字页",
            "template_category": "institutional_shareholder",
            "status": "completed",
            "file_id": 2
        }
    ],
    "logs": [
        {"timestamp": "...", "level": "info", "message": "生成任务已创建，共 2 个模板待处理"},
        {"timestamp": "...", "level": "info", "message": "后台生成已开始"},
        {"timestamp": "...", "level": "success", "message": "「律所签字页」生成完成"},
        {"timestamp": "...", "level": "success", "message": "「机构股东签字页」生成完成"},
        {"timestamp": "...", "level": "success", "message": "全部 2 个文件生成完成"}
    ]
}
```

### 7.3 获取生成文件列表

```bash
curl -s http://localhost:8000/api/projects/1/files \
  | python3 -m json.tool
```

预期：

```json
{
    "files": [
        {
            "id": 1,
            "project_id": 1,
            "template_id": 1,
            "template_name": "律所签字页",
            "file_path": "data/generated/1/律所签字页_abc12345.docx",
            "status": "completed"
        },
        {
            "id": 2,
            "project_id": 1,
            "template_id": 3,
            "template_name": "机构股东签字页",
            "file_path": "data/generated/1/机构股东签字页_def67890.docx",
            "status": "completed"
        }
    ]
}
```

### 7.4 下载单文件

```bash
curl -s -o /tmp/signed_page.docx -w "HTTP %{http_code}, Size: %{size_download} bytes\n" \
  http://localhost:8000/api/files/1/download
```

用 Python 验证文件是有效的 docx：

```bash
python3 -c "
from zipfile import ZipFile
with ZipFile('/tmp/signed_page.docx') as z:
    names = z.namelist()
    print(f'DOCX 有效, 包含 {len(names)} 个文件')
    assert '[Content_Types].xml' in names
    print('Content_Types.xml 存在 ✓')
"
```

### 7.5 打包下载全部文件

```bash
curl -s -o /tmp/all_files.zip -w "HTTP %{http_code}, Size: %{size_download} bytes\n" \
  http://localhost:8000/api/projects/1/download-all
```

验证 ZIP：

```bash
python3 -c "
from zipfile import ZipFile
with ZipFile('/tmp/all_files.zip') as z:
    names = z.namelist()
    print(f'ZIP 包含 {len(names)} 个文件:')
    for n in names:
        print(f'  - {n}')
"
```

### 7.6 取消生成测试

**注意：** 取消会清理已完成的部分文件，建议单独开项目测试。

```bash
# 先创建一个新项目并选模板
curl -s -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "取消测试项目"}' > /dev/null

curl -s -X POST http://localhost:8000/api/projects/2/templates \
  -H "Content-Type: application/json" \
  -d '{"template_ids": [1, 2, 3]}' > /dev/null

# 启动生成
curl -s -X POST http://localhost:8000/api/projects/2/generate > /dev/null

# 立即取消（不等待完成）
curl -s -X POST http://localhost:8000/api/projects/2/generate/cancel \
  | python3 -m json.tool
```

预期 cancel 响应：

```json
{
    "status": "cancelled",
    "total_count": 3,
    "completed_count": 2,
    "cancelled_at": "...",
    "logs": [
        {"level": "warning", "message": "任务已取消，已完成 2/3 个文件"}
    ]
}
```

### 7.7 验证生成 √ 禁止重复生成

```bash
curl -s -w "\nHTTP %{http_code}" -X POST http://localhost:8000/api/projects/2/generate
```

预期 409 Conflict：

```json
{"detail": "该项目已有进行中的生成任务"}
```

### 7.8 验证未选模板不允许生成

```bash
# 新建项目不选模板
curl -s -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "空项目"}' > /dev/null

curl -s -w "\nHTTP %{http_code}" -X POST http://localhost:8000/api/projects/4/generate
```

预期 400：

```json
{"detail": "请先为项目选择至少一个模板"}
```

---

## 8. Excel 导入导出

### 8.1 导出 Excel 模板

```bash
curl -s -o /tmp/import_template.xlsx \
  http://localhost:8000/api/projects/1/variables/export-template

# 验证
python3 -c "
from openpyxl import load_workbook
wb = load_workbook('/tmp/import_template.xlsx')
ws = wb.active
print(f'Sheet: {ws.title}')
print(f'表头: {[c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]}')
print(f'总行数: {ws.max_row - 1} 个变量')
for row in ws.iter_rows(min_row=2, values_only=True):
    print(f'  {row[0]:40s} {row[1]:20s} {row[2]}')
"
```

预期表头：`变量标识(key)` | `变量名称(label)` | `值(value)`

### 8.2 导出填写好的变量数据

```bash
curl -s -o /tmp/filled_variables.xlsx \
  http://localhost:8000/api/projects/1/variables/export

python3 -c "
from openpyxl import load_workbook
wb = load_workbook('/tmp/filled_variables.xlsx')
ws = wb.active
for row in ws.iter_rows(min_row=2, values_only=True):
    print(f'{row[0]:40s} = {row[2]}')
"
```

### 8.3 Excel 导入预览

```bash
# 准备导入文件：修改 signing_date 为合法值
python3 -c "
from openpyxl import Workbook
wb = Workbook()
ws = wb.active
ws.title = '变量'
ws.append(['变量标识(key)', '变量名称(label)', '值(value)'])
ws.append(['target_company_name', '目标公司名称', '海通证券股份有限公司'])
ws.append(['law_firm_name', '律师事务所名称', '君合律师事务所'])
ws.append(['signing_date', '签署日期', '2026年12月31日'])
ws.append(['nonexistent_key', '不存在的变量', 'test'])
wb.save('/tmp/import_test.xlsx')
"

# 上传预览
curl -s -X POST http://localhost:8000/api/projects/1/variables/import-preview \
  -F "file=@/tmp/import_test.xlsx" \
  | python3 -m json.tool
```

预期响应：

```json
{
    "success": [
        {"row": 2, "key": "target_company_name", "value": "海通证券股份有限公司"},
        {"row": 3, "key": "law_firm_name", "value": "君合律师事务所"},
        {"row": 4, "key": "signing_date", "value": "2026年12月31日"}
    ],
    "errors": [
        {"row": 5, "key": "nonexistent_key", "message": "变量 nonexistent_key 不存在于当前项目"}
    ],
    "summary": {"total": 4, "succeeded": 3, "failed": 1}
}
```

### 8.4 Excel 导入确认

```bash
curl -s -X POST http://localhost:8000/api/projects/1/variables/import \
  -H "Content-Type: application/json" \
  -d '{
    "rows": [
      {"key": "target_company_name", "value": "海通证券股份有限公司"},
      {"key": "law_firm_name", "value": "君合律师事务所"},
      {"key": "signing_date", "value": "2026年12月31日"}
    ]
  }' \
  | python3 -m json.tool
```

---

## 9. 异常场景

### 9.1 404 — 项目不存在

```bash
curl -s -w "\nHTTP %{http_code}" http://localhost:8000/api/projects/999
```

预期 404。

### 9.2 404 — 模板不存在

```bash
curl -s -w "\nHTTP %{http_code}" http://localhost:8000/api/templates/999
```

### 9.3 422 — 参数校验

```bash
# 项目名为空
curl -s -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": ""}' \
  | python3 -m json.tool
```

预期 422：

```json
{
    "detail": [
        {
            "type": "string_too_short",
            "loc": ["body", "name"],
            "msg": "String should have at least 1 character"
        }
    ]
}
```

### 9.4 409 — 重复选模板

```bash
curl -s -X POST http://localhost:8000/api/projects/1/templates \
  -H "Content-Type: application/json" \
  -d '{"template_ids": [1]}' \
  | python3 -m json.tool
```

不报错，自动跳过已存在关联（返回空列表）。

---

## 附录：完整业务流程

### 【端到端黄金流程】

```bash
# Step 0: 启动后端（确保 LONGCAT_API_KEY 已设置）
# cd backend && uv run uvicorn app.main:app --port 8000

# Step 1: 健康检查
curl -s http://localhost:8000/api/health | python3 -m json.tool

# Step 2: 创建项目
curl -s -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "海通证券 IPO 签字页项目"}' | python3 -m json.tool
# → 得到 project_id=1

# Step 3: 查看可用模板 → 选模板（选律所签字页 + 机构股东签字页）
curl -s -X POST http://localhost:8000/api/projects/1/templates \
  -H "Content-Type: application/json" \
  -d '{"template_ids": [1, 3]}' | python3 -m json.tool

# Step 4: 查看自动生成的去重变量列表
curl -s http://localhost:8000/api/projects/1/variables | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f'共 {len(data[\"variables\"])} 个变量（去重后）')
for v in data['variables']:
    print(f'  [{v[\"sort_order\"]:2d}] {v[\"key\"]:35s} {v[\"label\"]:15s} req={v[\"required\"]} multi={v[\"is_multiple\"]}')
"

# Step 5: 批量填写变量
curl -s -X PUT http://localhost:8000/api/projects/1/variables \
  -H "Content-Type: application/json" \
  -d '{
    "variables": [
      {"key": "target_company_name", "value": "海通证券股份有限公司", "updated_at": null},
      {"key": "law_firm_name", "value": "君合律师事务所上海分所", "updated_at": null},
      {"key": "law_firm_director", "value": "张明", "updated_at": null},
      {"key": "handling_lawyer_1", "value": "王芳", "updated_at": null},
      {"key": "handling_lawyer_2", "value": "李强", "updated_at": null},
      {"key": "signing_date", "value": "2026年6月21日", "updated_at": null},
      {"key": "exchange_name", "value": "上海证券交易所", "updated_at": null},
      {"key": "document_type", "value": "法律意见书", "updated_at": null},
      {"key": "target_investor_type", "value": "合格机构投资者", "updated_at": null},
      {"key": "institutional_shareholder_name", "value": "金石投资有限公司", "updated_at": null},
      {"key": "authorized_representative_name", "value": "赵刚", "updated_at": null},
      {"key": "meeting_year", "value": "2026", "updated_at": null},
      {"key": "meeting_session", "value": "第一次临时", "updated_at": null}
    ]
  }' | python3 -m json.tool

# Step 6: 生成文档
curl -s -X POST http://localhost:8000/api/projects/1/generate | python3 -m json.tool

# Step 7: 轮询等待完成
for i in 1 2 3 4 5; do
  sleep 2
  STATUS=$(curl -s http://localhost:8000/api/projects/1/generate/status | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('status',''))")
  echo "第 ${i} 次轮询: status=${STATUS}"
  if [ "$STATUS" = "completed" ]; then
    echo "生成完成！"
    break
  fi
done

# Step 8: 查看生成文件
curl -s http://localhost:8000/api/projects/1/files | python3 -m json.tool

# Step 9: 下载
FILE_ID=$(curl -s http://localhost:8000/api/projects/1/files | python3 -c "import sys, json; d=json.load(sys.stdin); print(d['files'][0]['id'])")
curl -s -o /tmp/generated_signing_page.docx "http://localhost:8000/api/files/${FILE_ID}/download"
echo "下载完成: $(ls -lh /tmp/generated_signing_page.docx | awk '{print $5}')"
```
