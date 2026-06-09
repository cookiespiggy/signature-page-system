"""AI 输出交叉验证 — 三层防御的中间层。

架构：AI 输出 → Guardrail 交叉验证 → 可信评级 → 业务层决策

可信评级：
  HIGH   — 规则确认 + AI 一致 → 自动通过
  MEDIUM — 规则/AI 单方支持 → 标记待确认
  LOW    — 规则与 AI 矛盾或均无依据 → 强制逐条审核
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from app.services.variable_registry import get_merged_registry


class TrustLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


def cross_validate_parsed_variables(
    variables: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """AI-1 模板解析交叉验证。

    对 AI 返回的每个变量，检查其 key/label 是否与注册表匹配。
    """
    registry = get_merged_registry()
    enriched: list[dict[str, Any]] = []
    for var in variables:
        key = var.get("key", "")
        label = var.get("label", "")
        is_registered = var.get("is_registered", False)
        category = var.get("category", "")
        warnings: list[str] = []
        trust = TrustLevel.HIGH
        suggested_key: str | None = None

        if not is_registered:
            matched = _find_by_alias(label, registry) or _find_by_alias(key, registry)
            if matched:
                trust = TrustLevel.MEDIUM
                suggested_key = matched
                warnings.append(
                    f"变量 '{key}' ({label}) 可能对应标准变量 '{matched_key}'，"
                    f"建议使用标准 key"
                )
            else:
                trust = TrustLevel.LOW
                warnings.append(
                    f"变量 '{key}' ({label}) 未在注册表中找到匹配项，"
                    f"请人工确认其命名和数据类型"
                )

        if is_registered:
            defn = registry.get(key)
            if defn and defn.get("category") and defn["category"] != category:
                warnings.append(
                    f"AI 分类 '{category}' 与注册表 '{defn['category']}' 不一致"
                )
                if trust == TrustLevel.HIGH:
                    trust = TrustLevel.MEDIUM

        var["trust_level"] = trust.value
        var["warnings"] = warnings
        if suggested_key:
            var["suggested_key"] = suggested_key
        enriched.append(var)

    return enriched


def cross_validate_dedup_suggestions(
    ai_suggestions: list[dict[str, Any]],
    alias_suggestions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """AI-2 去重建议交叉验证。

    将 AI 建议与别名规则建议交叉比对：
    - AI 与规则一致 → HIGH
    - 仅 AI 建议 → MEDIUM（需人工确认），confidence<0.5 降为 LOW
    - AI 与规则冲突 → LOW
    """
    registry = get_merged_registry()

    alias_pairs: set[tuple[str, str]] = set()
    for s in alias_suggestions:
        for mk in s.get("merge_keys", []):
            alias_pairs.add((s["keep_key"], mk))

    validated_ai: list[dict[str, Any]] = []
    for s in ai_suggestions:
        keep = s["keep_key"]
        merges = s.get("merge_keys", [])
        confidence = s.get("confidence", 0.0)

        all_match = all((keep, mk) in alias_pairs for mk in merges) if merges else False
        has_conflict = _any_dedup_conflict(keep, merges, registry)

        if all_match:
            if confidence >= 0.8:
                s["trust_level"] = TrustLevel.HIGH.value
            elif confidence >= 0.5:
                s["trust_level"] = TrustLevel.MEDIUM.value
            else:
                s["trust_level"] = TrustLevel.LOW.value
            s["rules_match"] = True
        elif has_conflict:
            s["trust_level"] = TrustLevel.LOW.value
            s["rules_match"] = False
            s.setdefault("warnings", []).append(
                f"AI 建议合并 '{keep}' 与 '{merges}' 可能与注册表别名关系冲突"
            )
        else:
            if confidence >= 0.5:
                s["trust_level"] = TrustLevel.MEDIUM.value
            else:
                s["trust_level"] = TrustLevel.LOW.value
            s["rules_match"] = False
            s.setdefault("warnings", []).append(
                "该建议未得到注册表规则确认，请人工判断"
            )

        validated_ai.append(s)

    for s in alias_suggestions:
        s["trust_level"] = TrustLevel.HIGH.value
        s["rules_match"] = True

    return validated_ai, alias_suggestions


def cross_validate_issues(
    ai_issues: list[dict[str, Any]],
    regex_issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """AI-3 校验结果交叉验证。

    合并 AI 和正则校验结果，去重，标注交叉验证状态。
    """
    regex_keys = {i["variable_key"] for i in regex_issues}
    ai_keys = {i["variable_key"] for i in ai_issues}
    cross_validated_keys = regex_keys & ai_keys

    merged = [{**i, "cross_validated": i["variable_key"] in cross_validated_keys} for i in regex_issues]

    for issue in ai_issues:
        if issue["variable_key"] in regex_keys:
            continue
        merged.append({**issue, "cross_validated": False, "source": "ai_only"})

    return merged


def _find_by_alias(name: str, registry: dict) -> str | None:
    """在注册表中搜索别名匹配的 key。

    先精确匹配（不区分大小写），再尝试包含匹配。
    包含匹配要求字符串长度 >= 4，防止短词误匹配（如"有限"匹配到"股份有限公司"）。
    """
    name_lower = name.strip().lower()
    if not name_lower:
        return None
    for key, defn in registry.items():
        for alias in defn.get("aliases", []):
            alias_lower = alias.strip().lower()
            if not alias_lower:
                continue
            if name_lower == alias_lower:
                return key
            if len(name_lower) >= 4 and len(alias_lower) >= 4:
                if name_lower in alias_lower or alias_lower in name_lower:
                    return key
    return None


def _any_dedup_conflict(keep: str, merges: list[str], registry: dict) -> bool:
    """检查 AI 合并建议是否与注册表 alias 关系冲突。"""
    for mk in merges:
        keep_defn = registry.get(keep)
        mk_defn = registry.get(mk)
        if keep_defn and mk_defn:
            keep_aliases = {a.lower() for a in keep_defn.get("aliases", [])}
            mk_aliases = {a.lower() for a in mk_defn.get("aliases", [])}
            if not keep_aliases & mk_aliases:
                return True
    return False
