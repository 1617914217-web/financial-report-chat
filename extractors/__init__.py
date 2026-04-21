# -*- coding: utf-8 -*-
"""extractors - 财务报表提取引擎包（懒加载，避免缺少模块时崩溃）"""

def _safe_import(name):
    try:
        return __import__(name, fromlist=[name.split(".")[-1]])
    except Exception:
        return None

_engine_a = _safe_import("extractors.engine_a_rules")
_engine_b = _safe_import("extractors.engine_b_deepseek")
_pdf_ext = _safe_import("extractors.pdf_extractor")
_mapper = _safe_import("extractors.table_mapper")

PDFExtractorEngineA = getattr(_engine_a, "PDFExtractorEngineA", None)
PDFExtractorEngineB = getattr(_engine_b, "PDFExtractorEngineB", None)
PDFExtractor = getattr(_pdf_ext, "PDFExtractor", None)
FieldMapper = getattr(_mapper, "FieldMapper", None)
get_mapper = getattr(_mapper, "get_mapper", None)

__all__ = [x for x in [
    "PDFExtractorEngineA", "PDFExtractorEngineB",
    "PDFExtractor", "FieldMapper", "get_mapper",
] if x is not None]

