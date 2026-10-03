# ============================================================
# Alfa Commander - Adapters Package
# طبقة تجريد محولات Alfa
# ============================================================

from app.core.adapters.base_adapter import (
    BaseAlfaAdapter,
    AdapterCapabilities,
    ReadinessReport,
)
from app.core.adapters.rtl8187 import RTL8187Adapter
from app.core.adapters.rtl8812au import RTL8812AUAdapter
from app.core.adapters.rtl8814au import RTL8814AUAdapter
from app.core.adapters.mt7610u import MT7610UAdapter
from app.core.adapters.mt7921aun import MT7921AUNAdapter
from app.core.adapters.registry import (
    ADAPTER_REGISTRY,
    MODEL_REGISTRY,
    get_adapter_class,
    get_adapter_class_by_model,
    list_supported_models,
)
from app.core.adapters.detector import (
    AdapterDetector,
    detect_adapters,
    detect_and_describe,
)
from app.core.adapters.rt3070 import RT3070Adapter
__all__ = [
    "BaseAlfaAdapter",
    "AdapterCapabilities",
    "ReadinessReport",
    "RTL8187Adapter",
    "RTL8812AUAdapter",
    "RTL8814AUAdapter",
    "MT7610UAdapter",
    "MT7921AUNAdapter",
    "ADAPTER_REGISTRY",
    "MODEL_REGISTRY",
    "get_adapter_class",
    "get_adapter_class_by_model",
    "list_supported_models",
    "AdapterDetector",
    "detect_adapters",
    "detect_and_describe",
    "RT3070Adapter",
]
