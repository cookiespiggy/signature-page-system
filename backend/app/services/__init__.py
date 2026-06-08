"""业务服务层。"""

__all__ = ["get_extract_text"]


def get_extract_text() -> callable:
    """延迟加载 extract_text_from_docx，避免 python-docx 未安装时阻断应用启动。"""
    from app.services.template_service import extract_text_from_docx

    return extract_text_from_docx
