"""WEEX klijentski sloj (Faza 3 skeleton).

- `WeexClient`      : apstraktno sucelje (ABC)
- `PaperWeexClient` : lokalna simulacija s fill-ovima na temelju cijene (bez mreze)
- `RestWeexClient`  : skeleton stvarnog REST klijenta (treba API kljuceve, Faza 3)
"""
from .client import OrderRequest, OrderResult, PaperPosition, WeexClient
from .paper import PaperWeexClient
from .rest import RestWeexClient

__all__ = [
    "WeexClient",
    "OrderRequest",
    "OrderResult",
    "PaperPosition",
    "PaperWeexClient",
    "RestWeexClient",
]
