# ============================================================
# Alfa Commander - Adapter Registry
# سجل كل محولات Alfa المدعومة
# ============================================================

from __future__ import annotations

from typing import Type

from app.core.adapters.base_adapter import BaseAlfaAdapter
from app.core.adapters.rtl8187 import RTL8187Adapter
from app.core.adapters.rtl8812au import RTL8812AUAdapter
from app.core.adapters.rtl8814au import RTL8814AUAdapter
from app.core.adapters.mt7610u import MT7610UAdapter
from app.core.adapters.mt7921aun import MT7921AUNAdapter
from app.core.adapters.rt3070 import RT3070Adapter


# ------------------------------------------------------------
# السجل: USB ID → class
# ------------------------------------------------------------
ADAPTER_REGISTRY: dict[str, Type[BaseAlfaAdapter]] = {
    # RTL8187L / RTL8187B
    "0bda:8187": RTL8187Adapter,
    "0bda:8189": RTL8187Adapter,

    # RTL8812AU
    "0bda:8812": RTL8812AUAdapter,
    "0bda:8813": RTL8812AUAdapter,

    # RTL8814AU
    "0bda:8814": RTL8814AUAdapter,

    # MT7610U / MT7612U
    "0e8d:7610": MT7610UAdapter,
    "0e8d:7612": MT7610UAdapter,

    # MT7921AUN
    "0e8d:7961": MT7921AUNAdapter,
    "0e8d:7962": MT7921AUNAdapter,

    # ============================================================
    # Ralink RT2870/RT3070 (محولات Alfa AWUS036NH و المتشابهة)
    # ============================================================
    "148f:3070": RT3070Adapter,
    "148f:2870": RT3070Adapter,
    "148f:3572": RT3070Adapter,
    "148f:3071": RT3070Adapter,
}


# ------------------------------------------------------------
# السجل: اسم الطراز → class
# ------------------------------------------------------------
MODEL_REGISTRY: dict[str, Type[BaseAlfaAdapter]] = {
    "AWUS036H": RTL8187Adapter,
    "AWUS036ACH": RTL8812AUAdapter,
    "AWUS036AC": RTL8812AUAdapter,
    "AWUS1900": RTL8814AUAdapter,
    "AWUS036ACHM": MT7610UAdapter,
    "AWUS036ACM": MT7610UAdapter,
    "AWUS036AXM": MT7921AUNAdapter,
    "AWUS036AXML": MT7921AUNAdapter,
    # Ralink
    "AWUS036NH": RT3070Adapter,
    "AWUS036NEH": RT3070Adapter,
    "AWUS051NH": RT3070Adapter,
    "RT3070": RT3070Adapter,
    "RT2870": RT3070Adapter,
}


# ------------------------------------------------------------
# دوال البحث
# ------------------------------------------------------------
def get_adapter_class(usb_id: str) -> Type[BaseAlfaAdapter] | None:
    return ADAPTER_REGISTRY.get(usb_id.lower())


def get_adapter_class_by_model(model: str) -> Type[BaseAlfaAdapter] | None:
    return MODEL_REGISTRY.get(model.upper())


def list_supported_models() -> list[dict]:
    """قائمة بكل الطرازات المدعومة."""
    seen = set()
    result = []
    for usb_id, cls in ADAPTER_REGISTRY.items():
        if cls.MODEL in seen:
            continue
        seen.add(cls.MODEL)
        result.append({
            "model": cls.MODEL,
            "chipset": cls.CHIPSET,
            "usb_ids": cls.USB_IDS,
            "bands": cls.DEFAULT_BANDS,
            "max_standard": cls.MAX_STANDARD,
            "driver": cls.DEFAULT_DRIVER,
            "driver_type": cls.DRIVER_TYPE,
            "min_kernel": cls.MIN_KERNEL,
            "supports_monitor": cls.SUPPORTS_MONITOR,
            "supports_injection": cls.SUPPORTS_INJECTION,
            "supports_ap": cls.SUPPORTS_AP,
            "known_issues": cls.KNOWN_ISSUES,
        })
    return result


def is_supported_usb_id(usb_id: str) -> bool:
    return usb_id.lower() in ADAPTER_REGISTRY


def is_supported_model(model: str) -> bool:
    return model.upper() in MODEL_REGISTRY
