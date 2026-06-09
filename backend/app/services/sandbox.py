"""
Safe Python sandbox for LLM-generated chart and analysis code.

Allows only pandas, numpy, plotly, scipy, math, and statistics imports.
Strips write-capable builtins. Chart code must assign `fig` (Plotly Figure)
and optionally `summary` (str). Analysis code must assign `result` (dict).
"""
from __future__ import annotations
import json
import logging
from typing import Any, Dict
import pandas as pd

logger = logging.getLogger("sandbox")

_ALLOWED_IMPORTS = {"pandas", "numpy", "plotly", "scipy", "math", "statistics"}


def _safe_import(name: str, *args, **kwargs):
    top = name.split(".")[0]
    if top not in _ALLOWED_IMPORTS:
        raise ImportError(f"Import '{name}' is not allowed in the sandbox.")
    import builtins
    return builtins.__import__(name, *args, **kwargs)


def run_chart_code(code: str, df: pd.DataFrame) -> Dict[str, Any]:
    """
    Execute LLM-generated code in a restricted namespace.
    Code must assign `fig` (a Plotly Figure) and optionally `summary` (str).
    Returns {"ok": True, "chart": {...}, "summary": "..."} or {"ok": False, "error": "...", "chart": None, "summary": ""}.
    """
    import builtins
    safe_builtins = {
        k: v for k, v in vars(builtins).items()
        if k not in ("open", "exec", "eval", "compile", "breakpoint", "__import__",
                     "getattr", "setattr", "delattr", "vars", "dir", "type", "object")
    }
    safe_builtins["__import__"] = _safe_import

    namespace: Dict[str, Any] = {
        "__builtins__": safe_builtins,
        "df": df.copy(),
    }

    try:
        exec(compile(code, "<sandbox>", "exec"), namespace)  # noqa: S102
    except Exception as exc:
        logger.warning("Sandbox exec error: %s", exc)
        return {"ok": False, "error": str(exc), "chart": None, "summary": ""}

    fig = namespace.get("fig")
    summary = str(namespace.get("summary", ""))

    if fig is None:
        return {"ok": False, "error": "Code did not produce a `fig` variable.", "chart": None, "summary": summary}

    try:
        from plotly.basedatatypes import BaseFigure
        from plotly.utils import PlotlyJSONEncoder
        if not isinstance(fig, BaseFigure):
            return {"ok": False, "error": "The `fig` variable must be a Plotly Figure.", "chart": None, "summary": summary}
        chart_json = json.loads(json.dumps(fig.to_dict(), cls=PlotlyJSONEncoder))
        return {"ok": True, "chart": chart_json, "summary": summary}
    except Exception as exc:
        return {"ok": False, "error": f"Failed to serialize figure: {exc}", "chart": None, "summary": summary}


def run_analysis_code(code: str, df: pd.DataFrame) -> Dict[str, Any]:
    """
    Execute LLM-generated analytical code in the same restricted namespace.
    Code must assign `result` to a JSON-serializable dict.
    """
    import builtins
    safe_builtins = {
        k: v for k, v in vars(builtins).items()
        if k not in ("open", "exec", "eval", "compile", "breakpoint", "__import__",
                     "getattr", "setattr", "delattr", "vars", "dir", "type", "object")
    }
    safe_builtins["__import__"] = _safe_import

    namespace: Dict[str, Any] = {
        "__builtins__": safe_builtins,
        "df": df.copy(),
    }

    try:
        exec(compile(code, "<analysis_sandbox>", "exec"), namespace)  # noqa: S102
    except Exception as exc:
        logger.warning("Analysis sandbox exec error: %s", exc)
        return {"ok": False, "error": str(exc), "result": None}

    result = namespace.get("result")
    if not isinstance(result, dict):
        return {"ok": False, "error": "Code did not produce a `result` dict.", "result": None}

    return {"ok": True, "error": "", "result": result}
