"""模板业务逻辑 — 文件处理、变量提取、AI 解析编排。"""

from __future__ import annotations

import logging
from pathlib import Path

from docx import Document

logger = logging.getLogger(__name__)


def extract_text_from_docx(file_path: str | Path) -> str:
    """从 .docx 文件中提取纯文本供 AI 解析。

    提取段落文本 + 表格文本，按原始顺序拼合。
    不处理页眉/页脚/文本框/图片。

    Args:
        file_path: .docx 文件路径。

    Returns:
        提取出的纯文本字符串。

    Raises:
        FileNotFoundError: 文件不存在。
        ValueError: 非 .docx 文件或文件损坏。
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"模板文件不存在: {path}")
    if path.suffix.lower() != ".docx":
        raise ValueError(f"仅支持 .docx 文件: {path.suffix}")

    try:
        doc = Document(str(path))
    except Exception as exc:
        raise ValueError(f"无法打开 .docx 文件: {exc}") from exc

    parts: list[str] = []

    for element in doc.element.body:
        tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

        if tag == "p":
            # 段落
            para = _find_paragraph(doc, element)
            if para and para.text.strip():
                parts.append(para.text.strip())

        elif tag == "tbl":
            # 表格 — 提取所有单元格文本
            for row in element.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr"):
                cells = []
                for cell in row.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc"):
                    texts = [
                        t.text or ""
                        for t in cell.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
                    ]
                    cells.append("".join(texts).strip())
                if cells:
                    parts.append(" | ".join(cells))

    return "\n".join(parts)


def _find_paragraph(doc: Document, element) -> object | None:
    """通过 XML 元素查找对应的 Paragraph 对象。"""
    for para in doc.paragraphs:
        if para._element is element:
            return para
    return None
