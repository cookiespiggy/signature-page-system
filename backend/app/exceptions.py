"""领域层异常 — service 层使用，routers 层翻译为 HTTP 响应。"""

from __future__ import annotations


class DomainError(Exception):
    """领域层基类异常。"""


# --- 项目相关 ---

class ProjectNotFoundError(DomainError):
    """项目不存在。"""


# --- 模板相关 ---

class TemplateNotFoundError(DomainError):
    """模板不存在。"""


class TemplateReferencedError(DomainError):
    """模板仍被项目引用，不可删除。"""


class TemplateFileMissingError(DomainError):
    """模板文件不存在，无法生成。"""


class NoTemplatesSelectedError(DomainError):
    """未选择任何模板，无法生成。"""


class PresetTemplateDeleteForbidden(DomainError):
    """预置模板不可删除。"""


class ProjectTemplateNotLinkedError(DomainError):
    """项目未关联该模板。"""


# --- 变量相关 ---

class VariableNotFoundError(DomainError):
    """变量不存在。"""


class OptimisticLockConflictError(DomainError):
    """乐观锁冲突，数据已被其他操作修改。"""


# --- 生成任务相关 ---

class InvalidStateTransition(DomainError):
    """状态机非法转换。"""


class ActiveTaskExistsError(DomainError):
    """已有进行中的生成任务。"""


class NoActiveTaskError(DomainError):
    """没有进行中的生成任务。"""


# --- Excel 导入相关 ---

class ExcelFormatError(DomainError):
    """Excel 文件格式错误。"""


class ExcelParseError(DomainError):
    """Excel 文件解析失败。"""
