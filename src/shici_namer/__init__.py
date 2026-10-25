"""shici-namer · 诗词摘词命名器

设计目标见 AGENTS.md / docs/SPEC.md。
对外主入口：`from shici_namer import run`
"""
from .config import Config, load_config
from .pipeline import run, RunResult

__version__ = "1.0.0"
__all__ = ["Config", "load_config", "run", "RunResult", "__version__"]
