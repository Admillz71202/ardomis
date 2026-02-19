from __future__ import annotations

import ast
import operator
import platform
import re
import shutil
import socket
from datetime import datetime
from zoneinfo import ZoneInfo


_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    raise ValueError("Unsupported math expression.")


def calculate(expr: str) -> str:
    cleaned = re.sub(r"[^0-9\+\-\*\/\(\)\.\%\^ ]", "", expr or "")
    if "^" in cleaned:
        cleaned = cleaned.replace("^", "**")
    tree = ast.parse(cleaned, mode="eval")
    result = _safe_eval(tree)
    if int(result) == result:
        return str(int(result))
    return f"{result:.8f}".rstrip("0").rstrip(".")


def system_snapshot() -> str:
    total, used, free = shutil.disk_usage("/")
    host = socket.gethostname()
    return (
        f"host={host}, os={platform.system()} {platform.release()}, "
        f"python={platform.python_version()}, "
        f"disk_used={used // (1024**3)}GB/{total // (1024**3)}GB, free={free // (1024**3)}GB"
    )


def eastern_time(timezone_name: str) -> str:
    zone = ZoneInfo(timezone_name)
    now = datetime.now(zone)
    return now.strftime("%I:%M %p on %A, %B %d, %Y")
