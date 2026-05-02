# -*- coding: utf-8 -*-
"""
SQL安全校验模块

使用sqlparse解析语法树，拦截危险操作，仅放行SELECT查询。
"""
import sqlparse
from sqlparse.sql import Statement


class SQLValidator:

    FORBIDDEN_KEYWORDS = frozenset([
        'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE',
        'TRUNCATE', 'GRANT', 'REVOKE', 'EXEC', 'EXECUTE',
        'INTO', 'SET', 'CALL',
    ])

    @classmethod
    def validate(cls, sql: str) -> dict:
        """
        校验SQL安全性
        返回: {"valid": bool, "reason": str, "normalized": str}
        """
        if not sql or not sql.strip():
            return {"valid": False, "reason": "SQL为空", "normalized": ""}

        sql = sql.strip()
        if sql.endswith(";"):
            sql = sql[:-1].strip()

        # 格式化SQL
        normalized = sqlparse.format(sql, reindent=True, keyword_case='upper')

        # 解析
        parsed = sqlparse.parse(sql)
        if not parsed:
            return {"valid": False, "reason": "SQL语法解析失败", "normalized": ""}

        stmt = parsed[0]

        # 仅允许SELECT
        if stmt.get_type() != 'SELECT':
            return {"valid": False, "reason": f"仅允许SELECT查询，检测到{stmt.get_type()}", "normalized": normalized}

        # 检查危险关键词（在tokens中检测，避免误报列名）
        sql_upper = ' '.join(t.value for t in stmt.flatten()).upper()
        for kw in cls.FORBIDDEN_KEYWORDS:
            # 用词边界匹配，避免误报
            pattern = rf'\b{kw}\b'
            import re
            if re.search(pattern, sql_upper):
                return {"valid": False, "reason": f"包含禁止的关键词: {kw}", "normalized": normalized}

        # 检查多语句
        if len(parsed) > 1:
            return {"valid": False, "reason": "禁止执行多条SQL语句", "normalized": normalized}

        # 检查子查询中的危险操作
        for token in stmt.flatten():
            val = token.value.upper().strip()
            if val in ('DROP', 'DELETE', 'UPDATE', 'INSERT') and token.ttype is not None:
                return {"valid": False, "reason": f"子查询中包含禁止操作: {val}", "normalized": normalized}

        return {"valid": True, "reason": "OK", "normalized": normalized}


if __name__ == "__main__":
    tests = [
        "SELECT stock_code, net_profit FROM stock_income_statement_data WHERE report_year=2022",
        "DROP TABLE stock_income_statement_data",
        "DELETE FROM balance_sheet WHERE 1=1",
        "SELECT * FROM income_sheet; DROP TABLE users",
        "INSERT INTO balance_sheet VALUES (1,'test')",
        "UPDATE income_sheet SET net_profit=999",
    ]
    for sql in tests:
        r = SQLValidator.validate(sql)
        status = "[PASS]" if r["valid"] else "[BLOCK]"
        print(f"{status} {sql[:50]}")
        if not r["valid"]:
            print(f"   原因: {r['reason']}")
