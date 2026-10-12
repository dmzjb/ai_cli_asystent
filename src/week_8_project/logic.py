"""Definicje narzędzi i ich implementacje."""

import ast
import operator
from pathlib import Path
from typing import Any

allowed_operators: dict[type[ast.AST], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv, #type:ignore
    ast.Pow: operator.pow, #type:ignore
    ast.Mod: operator.mod,
    ast.USub: operator.neg
}

def safe_exec(wezel: ast.AST) -> float:
    if isinstance(wezel, ast.Expression):
        return safe_exec(wezel.body)
    if isinstance(wezel, ast.Constant) and isinstance(wezel.value, (int, float)):
        return wezel.value
    if isinstance(wezel, ast.BinOp):
        typ_op = type(wezel.op)
        if typ_op not in allowed_operators:
            raise ValueError(f"niedozwolony operator: {typ_op.__name__}")
        return allowed_operators[typ_op](
            safe_exec(wezel.left),
            safe_exec(wezel.right),
        )
    if isinstance(wezel, ast.UnaryOp):
        typ_op = type(wezel.op)
        if typ_op not in allowed_operators:
            raise ValueError(f"niedozwolony operator: {typ_op.__name__}")
        return allowed_operators[typ_op](safe_exec(wezel.operand))
    raise ValueError(f"niedozwolony element wyrażenia: {type(wezel).__name__}")

def save_note_function(plik: Path, note: str) -> None:
    """Przyjmuje sciezke oraz notatke jako parametr, zapisuje notatke w podanej lokalizacji"""
    plik.parent.mkdir(parents = True, exist_ok = True)

    with plik.open("a", encoding="utf-8") as file:
        file.write(note + "\n")