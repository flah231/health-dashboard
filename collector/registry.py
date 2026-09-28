"""自动扫描 adapters 包，发现所有 BaseAdapter 子类。"""
import importlib
import inspect
import pkgutil
from pathlib import Path

from adapters.base import BaseAdapter


def discover_adapters() -> dict[str, type[BaseAdapter]]:
    """返回 {source_key: AdapterClass}。"""
    import adapters as adapters_pkg

    result: dict[str, type[BaseAdapter]] = {}
    pkg_path = Path(adapters_pkg.__file__).parent

    for _, module_name, _ in pkgutil.iter_modules([str(pkg_path)]):
        if module_name.startswith("_") or module_name == "base":
            continue
        module = importlib.import_module(f"adapters.{module_name}")
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseAdapter)
                and obj is not BaseAdapter
                and obj.__module__ == module.__name__
                and getattr(obj, "source_key", "")
            ):
                result[obj.source_key] = obj
    return result