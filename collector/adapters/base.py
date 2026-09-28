"""所有数据源适配器的抽象基类。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class DiseaseRecord:
    source_key: str
    disease_name: str
    region: str
    stat_date: date
    confirmed: int = 0
    cured: int = 0
    deaths: int = 0
    extra: dict = field(default_factory=dict)
    admin_level: str = "national"          # national / province
    province_code: str | None = None
    province_name: str | None = None
    disease_category: str | None = None    # 甲 / 乙 / 丙


class BaseAdapter(ABC):
    source_key: str = ""
    admin_level: str = "national"
    province_code: str | None = None
    province_name: str | None = None

    def __init__(self, config: dict[str, Any] | None = None):
        if not self.source_key:
            raise ValueError(f"{self.__class__.__name__} 必须定义 source_key")
        self.config = config or {}

    @abstractmethod
    def fetch(self) -> list[DiseaseRecord]:
        ...
    """数据源适配器基类。"""

    source_key: str = ""   # 子类必须覆盖，唯一标识

    def __init__(self, config: dict[str, Any] | None = None):
        if not self.source_key:
            raise ValueError(f"{self.__class__.__name__} 必须定义 source_key")
        self.config = config or {}

    @abstractmethod
    def fetch(self) -> list[DiseaseRecord]:
        """抓取数据并返回标准化记录列表。"""
        ...