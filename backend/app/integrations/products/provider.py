from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.utils.currency import quantize_amount


class ProviderUnavailableError(RuntimeError):
    """Raised when a product provider fails or is unreachable."""


class MerchantDetails(BaseModel):
    name: str
    url: str | None = None
    verified: bool = False


class ProviderProduct(BaseModel):
    external_product_id: str
    name: str
    description: str | None = None
    price: Decimal
    currency: str = "USD"
    merchant: str
    merchant_details: MerchantDetails | None = None
    availability: str = "UNKNOWN"
    image_url: str | None = None
    product_url: str | None = None
    category: str | None = None
    specifications: dict[str, Any] = Field(default_factory=dict)
    provider: str
    is_test_data: bool = False


class ProductSearchResult(BaseModel):
    query: str
    provider: str
    provider_status: str
    is_test_data: bool = False
    products: list[ProviderProduct] = Field(default_factory=list)
    message: str | None = None


class ProductProvider(ABC):
    """Abstract interface for external product discovery providers."""

    provider_name: str = "unknown"

    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if credentials required by this provider are configured."""

    @abstractmethod
    async def search_products(
        self,
        query: str,
        *,
        max_price: Decimal | None = None,
        currency: str = "USD",
        limit: int = 10,
    ) -> ProductSearchResult:
        """Search products matching query and optional price cap."""

    @abstractmethod
    async def get_product_details(
        self, external_product_id: str
    ) -> ProviderProduct | None:
        """Retrieve detailed product information by provider external ID."""


class TestFixtureProductProvider(ProductProvider):
    """Deterministic fixture provider strictly labeled as TEST DATA for local development/testing."""

    provider_name = "test_fixtures"

    _FIXTURES: list[dict[str, Any]] = [
        {
            "external_product_id": "test-wh-1000xm5",
            "name": "[TEST DATA] AcousticPro ANC Wireless Headphones",
            "description": "Deterministic test fixture item: active noise cancelling over-ear headphones.",
            "price": Decimal("279.99"),
            "currency": "USD",
            "merchant": "TestAudioDirect",
            "merchant_url": "https://example.test/merchants/testaudiodirect",
            "availability": "IN_STOCK",
            "image_url": "https://example.test/images/wh-anc-1000.png",
            "product_url": "https://example.test/products/test-wh-1000xm5",
            "category": "headphones",
            "specifications": {
                "anc": True,
                "battery_hours": 30,
                "bluetooth": "5.3",
                "weight_grams": 250,
                "usb_c_charging": True,
            },
        },
        {
            "external_product_id": "test-bose-qc-se",
            "name": "[TEST DATA] StudioQuiet Comfort ANC Headphones",
            "description": "Deterministic test fixture item: lightweight ANC wireless headphones.",
            "price": Decimal("249.00"),
            "currency": "USD",
            "merchant": "TestSoundHub",
            "merchant_url": "https://example.test/merchants/testsoundhub",
            "availability": "IN_STOCK",
            "image_url": "https://example.test/images/studio-quiet.png",
            "product_url": "https://example.test/products/test-bose-qc-se",
            "category": "headphones",
            "specifications": {
                "anc": True,
                "battery_hours": 24,
                "bluetooth": "5.1",
                "weight_grams": 240,
                "usb_c_charging": True,
            },
        },
        {
            "external_product_id": "test-keychron-q1",
            "name": "[TEST DATA] TactilePro Q1 Mechanical Keyboard",
            "description": "Deterministic test fixture item: aluminum hot-swappable mechanical keyboard.",
            "price": Decimal("189.50"),
            "currency": "USD",
            "merchant": "TestMechKeys",
            "merchant_url": "https://example.test/merchants/testmechkeys",
            "availability": "IN_STOCK",
            "image_url": "https://example.test/images/tactilepro-q1.png",
            "product_url": "https://example.test/products/test-keychron-q1",
            "category": "keyboards",
            "specifications": {
                "layout": "75%",
                "hot_swappable": True,
                "wireless": True,
                "frame": "CNC Aluminum",
            },
        },
        {
            "external_product_id": "test-usb-dock-pro",
            "name": "[TEST DATA] DockStation 12-in-1 Thunderbolt Hub",
            "description": "Deterministic test fixture item: dual-4K USB-C docking station.",
            "price": Decimal("149.00"),
            "currency": "USD",
            "merchant": "TestWorkGear",
            "merchant_url": "https://example.test/merchants/testworkgear",
            "availability": "IN_STOCK",
            "image_url": "https://example.test/images/dock-pro.png",
            "product_url": "https://example.test/products/test-usb-dock-pro",
            "category": "accessories",
            "specifications": {
                "power_delivery_watts": 100,
                "hdmi_ports": 2,
                "ethernet": "2.5Gbps",
            },
        },
    ]

    def is_configured(self) -> bool:
        return True

    def _to_model(self, raw: dict[str, Any]) -> ProviderProduct:
        return ProviderProduct(
            external_product_id=raw["external_product_id"],
            name=raw["name"],
            description=raw["description"],
            price=quantize_amount(raw["price"], raw["currency"]),
            currency=raw["currency"],
            merchant=raw["merchant"],
            merchant_details=MerchantDetails(
                name=raw["merchant"],
                url=raw.get("merchant_url"),
                verified=False,
            ),
            availability=raw["availability"],
            image_url=raw.get("image_url"),
            product_url=raw.get("product_url"),
            category=raw.get("category"),
            specifications={**raw.get("specifications", {}), "data_origin": "TEST_DATA"},
            provider=self.provider_name,
            is_test_data=True,
        )

    async def search_products(
        self,
        query: str,
        *,
        max_price: Decimal | None = None,
        currency: str = "USD",
        limit: int = 10,
    ) -> ProductSearchResult:
        terms = [t for t in query.lower().split() if len(t) > 1]
        matched: list[ProviderProduct] = []
        for raw in self._FIXTURES:
            haystack = " ".join(
                [
                    raw["name"],
                    raw["description"] or "",
                    raw.get("category") or "",
                    raw["merchant"],
                ]
            ).lower()
            if terms and not any(term in haystack for term in terms):
                continue
            if max_price is not None and raw["currency"] == currency.upper() and raw["price"] > max_price:
                continue
            matched.append(self._to_model(raw))

        return ProductSearchResult(
            query=query,
            provider=self.provider_name,
            provider_status="TEST_FIXTURES",
            is_test_data=True,
            products=matched[:limit],
            message="TEST DATA ONLY: Not live inventory. Configure CHANNEL3_API_KEY for live catalog discovery.",
        )

    async def get_product_details(
        self, external_product_id: str
    ) -> ProviderProduct | None:
        for raw in self._FIXTURES:
            if raw["external_product_id"] == external_product_id:
                return self._to_model(raw)
        return None


def get_product_provider(settings: Settings | None = None) -> ProductProvider:
    """Resolve the active product provider without fabricating live inventory."""
    from app.integrations.products.channel3 import Channel3ProductProvider

    cfg = settings or get_settings()
    channel3 = Channel3ProductProvider(cfg)
    if channel3.is_configured():
        return channel3
    if cfg.enable_test_product_fixtures:
        return TestFixtureProductProvider()
    return channel3

