from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.core.config import Settings, clear_settings_cache, get_settings
from app.integrations.products.channel3 import Channel3ProductProvider


def _make_provider(monkeypatch: pytest.MonkeyPatch | None = None, base_url: str | None = None) -> Channel3ProductProvider:
    if monkeypatch is not None:
        monkeypatch.setenv("CHANNEL3_API_KEY", "test-channel3-key")
        if base_url is not None:
            monkeypatch.setenv("CHANNEL3_BASE_URL", base_url)
        clear_settings_cache()
    return Channel3ProductProvider(get_settings())


def test_channel3_default_and_override_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CHANNEL3_BASE_URL", raising=False)
    clear_settings_cache()
    default_cfg = Settings(_env_file=None)
    assert default_cfg.channel3_base_url == "https://api.trychannel3.com/v1"

    override_cfg = Settings(_env_file=None, CHANNEL3_BASE_URL="https://custom.channel3.test/v1/")
    provider = Channel3ProductProvider(override_cfg)
    assert provider.base_url == "https://custom.channel3.test/v1"


def test_normalize_valid_channel3_v1_product() -> None:
    provider = Channel3ProductProvider(Settings(_env_file=None, CHANNEL3_API_KEY="k"))
    raw: dict[str, Any] = {
        "id": "zNQps8G",
        "title": "Sennheiser Accentum Wireless Headphones",
        "description": "Wireless ANC headphones with 50-hour battery life.",
        "brands": [{"id": "TkaC", "name": "Sennheiser"}],
        "images": [
            {
                "url": "https://cdn.trychannel3.com/secondary.jpg",
                "cleaned_url": None,
                "is_main_image": False,
            },
            {
                "url": "https://cdn.trychannel3.com/main.jpg",
                "cleaned_url": "https://cdn.trychannel3.com/cleaned/main.jpg",
                "is_main_image": True,
            },
        ],
        "category": {
            "slug": "over-ear-headphones",
            "title": "Over-Ear Headphones",
            "has_children": False,
        },
        "key_features": ["50-hour battery life", "Hybrid ANC"],
        "materials": ["Silicone"],
        "offers": [
            {
                "url": "https://buy.trychannel3.com/zNQps8G-offer",
                "domain": "newegg.com",
                "price": {"price": 175.0, "compare_at_price": None, "currency": "USD"},
                "availability": "InStock",
                "condition": "new",
            }
        ],
        "variants": None,
        "ratings": {"value": 4.14, "count": 108, "source_count": 1},
        "structured_attributes": {"connectivity-technology": ["Bluetooth"]},
    }

    normalized = provider._normalize_product(raw)
    assert normalized is not None
    assert normalized.external_product_id == "zNQps8G"
    assert normalized.name == "Sennheiser Accentum Wireless Headphones"
    assert normalized.description == "Wireless ANC headphones with 50-hour battery life."
    assert normalized.price == Decimal("175.00")
    assert isinstance(normalized.price, Decimal)
    assert normalized.currency == "USD"
    assert normalized.merchant == "newegg.com"
    assert normalized.merchant_details is not None
    assert normalized.merchant_details.name == "newegg.com"
    assert normalized.merchant_details.url is None
    assert normalized.availability == "IN_STOCK"
    assert normalized.image_url == "https://cdn.trychannel3.com/main.jpg"
    assert normalized.product_url == "https://buy.trychannel3.com/zNQps8G-offer"
    assert normalized.category == "Over-Ear Headphones"
    assert normalized.specifications["brand"] == "Sennheiser"
    assert normalized.specifications["domain"] == "newegg.com"
    assert normalized.specifications["ratings"]["value"] == 4.14
    assert normalized.provider == "channel3"
    assert normalized.is_test_data is False


def test_normalize_nested_offers_prefers_in_stock_valid_offer() -> None:
    provider = Channel3ProductProvider(Settings(_env_file=None, CHANNEL3_API_KEY="k"))
    raw: dict[str, Any] = {
        "id": "00JoAsr",
        "title": "Anker Soundcore Space One",
        "offers": [
            {
                "url": "https://buy.trychannel3.com/oos",
                "domain": "oosmerchant.com",
                "price": {"price": 89.99, "currency": "USD"},
                "availability": "OutOfStock",
            },
            {
                "url": "https://buy.trychannel3.com/in-stock",
                "domain": "bestbuy.com",
                "price": {"price": 99.99, "currency": "usd"},
                "availability": "InStock",
            },
        ],
    }

    normalized = provider._normalize_product(raw)
    assert normalized is not None
    assert normalized.price == Decimal("99.99")
    assert normalized.currency == "USD"
    assert normalized.merchant == "bestbuy.com"
    assert normalized.availability == "IN_STOCK"
    assert normalized.product_url == "https://buy.trychannel3.com/in-stock"


def test_normalize_price_and_currency_precision_and_cleaned_image_fallback() -> None:
    provider = Channel3ProductProvider(Settings(_env_file=None, CHANNEL3_API_KEY="k"))
    raw: dict[str, Any] = {
        "id": "jp-1",
        "title": "Japan Audio DAC",
        "brands": [{"name": "Sony"}],
        "images": [
            {"url": "", "cleaned_url": "https://cdn.trychannel3.com/cleaned/dac.jpg"}
        ],
        "offers": [
            {
                "price": {"amount": "14800", "currency": "jpy"},
                "availability": "PreOrder",
            }
        ],
    }

    normalized = provider._normalize_product(raw)
    assert normalized is not None
    assert normalized.price == Decimal("14800")
    assert normalized.currency == "JPY"
    assert normalized.availability == "PRE_ORDER"
    assert normalized.image_url == "https://cdn.trychannel3.com/cleaned/dac.jpg"
    assert normalized.merchant == "Sony"
    assert normalized.product_url is None


def test_normalize_preserves_valid_product_with_missing_optional_fields() -> None:
    provider = Channel3ProductProvider(Settings(_env_file=None, CHANNEL3_API_KEY="k"))
    raw: dict[str, Any] = {
        "id": "min-1",
        "title": "Minimal Valid Product",
        "description": None,
        "brands": [],
        "images": [],
        "category": None,
        "offers": [
            {
                "price": {"price": 49.5, "currency": "USD"},
            }
        ],
    }

    normalized = provider._normalize_product(raw)
    assert normalized is not None
    assert normalized.external_product_id == "min-1"
    assert normalized.name == "Minimal Valid Product"
    assert normalized.price == Decimal("49.50")
    assert normalized.currency == "USD"
    assert normalized.description is None
    assert normalized.image_url is None
    assert normalized.product_url is None
    assert normalized.category is None
    assert normalized.availability == "UNKNOWN"
    assert normalized.merchant == "Unknown Merchant"


@pytest.mark.parametrize(
    "raw_item",
    [
        None,
        "not-a-dict",
        {},
        {"id": "no-title", "offers": [{"price": {"price": 20.0, "currency": "USD"}}]},
        {"title": "No ID", "offers": [{"price": {"price": 20.0, "currency": "USD"}}]},
        {"id": "empty-offers", "title": "No Offers", "offers": []},
        {"id": "null-offers", "title": "Null Offers", "offers": None},
        {
            "id": "bad-price",
            "title": "Bad Price",
            "offers": [{"price": {"price": "invalid", "currency": "USD"}}],
        },
        {
            "id": "zero-price",
            "title": "Zero Price",
            "offers": [{"price": {"price": 0, "currency": "USD"}}],
        },
        {
            "id": "bad-currency",
            "title": "Bad Currency",
            "offers": [{"price": {"price": 19.99, "currency": "XYZ"}}],
        },
        {
            "id": "malformed-offer-list",
            "title": "Bad Offer Entry",
            "offers": ["not-an-offer", None, {"price": None}],
        },
    ],
)
def test_normalize_empty_offers_and_malformed_records_safely(raw_item: Any) -> None:
    provider = Channel3ProductProvider(Settings(_env_file=None, CHANNEL3_API_KEY="k"))
    assert provider._normalize_product(raw_item) is None


def test_normalize_backward_compatibility_with_legacy_v0_shape() -> None:
    provider = Channel3ProductProvider(Settings(_env_file=None, CHANNEL3_API_KEY="k"))
    legacy: dict[str, Any] = {
        "product_id": "legacy-42",
        "name": "Legacy Mechanical Keyboard",
        "description": "Legacy schema product.",
        "price": {"amount": "129.95", "currency": "EUR"},
        "brand_name": "Keychron",
        "merchant": {"name": "Keychron Official", "url": "https://keychron.example"},
        "verified_merchant": True,
        "availability": "in_stock",
        "image_urls": ["https://legacy.example/kb.png"],
        "product_url": "https://legacy.example/products/42",
        "categories": ["Keyboards"],
        "specifications": {"layout": "75%"},
        "variants": [{"id": "v1"}, {"id": "v2"}],
    }

    normalized = provider._normalize_product(legacy)
    assert normalized is not None
    assert normalized.external_product_id == "legacy-42"
    assert normalized.name == "Legacy Mechanical Keyboard"
    assert normalized.price == Decimal("129.95")
    assert normalized.currency == "EUR"
    assert normalized.merchant == "Keychron Official"
    assert normalized.merchant_details is not None
    assert normalized.merchant_details.url == "https://keychron.example"
    assert normalized.merchant_details.verified is True
    assert normalized.availability == "IN_STOCK"
    assert normalized.image_url == "https://legacy.example/kb.png"
    assert normalized.product_url == "https://legacy.example/products/42"
    assert normalized.category == "Keyboards"
    assert normalized.specifications["brand"] == "Keychron"
    assert normalized.specifications["layout"] == "75%"
    assert normalized.specifications["variant_count"] == 2


@pytest.mark.asyncio
async def test_search_products_v1_mock_handles_valid_and_malformed_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _make_provider(monkeypatch)
    seen_urls: list[str] = []
    seen_bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        import json

        seen_bodies.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "products": [
                    {
                        "id": "p-valid",
                        "title": "Valid v1 Headphones",
                        "brands": [{"id": "b1", "name": "AudioBrand"}],
                        "images": [{"url": "https://cdn.example/h.jpg", "is_main_image": True}],
                        "offers": [
                            {
                                "url": "https://buy.example/h",
                                "domain": "shop.example",
                                "price": {"price": 149.99, "currency": "USD"},
                                "availability": "InStock",
                            }
                        ],
                    },
                    {"id": "p-empty-offers", "title": "No Offers Item", "offers": []},
                    "corrupted-item",
                ],
                "next_page_token": None,
            },
        )

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", PatchedAsyncClient)
    try:
        result = await provider.search_products(
            "wireless headphones", max_price=Decimal("200.00"), limit=2
        )
    finally:
        monkeypatch.setattr(httpx, "AsyncClient", real_async_client)

    assert seen_urls == ["https://api.trychannel3.com/v1/search"]
    assert seen_bodies[0].get("filters") == {"price": {"max_price": 200.0}}
    assert "config" not in seen_bodies[0]
    assert result.provider_status == "AVAILABLE"
    assert result.is_test_data is False
    assert len(result.products) == 1
    assert result.products[0].external_product_id == "p-valid"
    assert result.products[0].price == Decimal("149.99")


@pytest.mark.asyncio
async def test_search_products_with_inr_preserves_usd_listings_and_distinguishes_zero_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _make_provider(monkeypatch)
    seen_bodies: list[dict[str, Any]] = []
    mode = {"empty": False}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen_bodies.append(json.loads(request.content.decode("utf-8")))
        if mode["empty"]:
            return httpx.Response(200, json={"products": [], "next_page_token": None})
        return httpx.Response(
            200,
            json={
                "products": [
                    {
                        "id": "YSD8j4q",
                        "title": "KPH7 Headphone",
                        "brands": [{"id": "uVCT", "name": "Koss"}],
                        "images": [{"url": "https://cdn.trychannel3.com/h.jpg", "is_main_image": True}],
                        "offers": [
                            {
                                "url": "https://buy.trychannel3.com/YSD8j4q",
                                "domain": "bestbuy.com",
                                "price": {"price": 26.52, "currency": "USD"},
                                "availability": "InStock",
                            }
                        ],
                    }
                ],
                "next_page_token": None,
            },
        )

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", PatchedAsyncClient)
    try:
        # 1. currency="INR" without max_price must NOT filter out USD listings
        inr_res = await provider.search_products("headphone", currency="INR", limit=10)
        assert inr_res.provider_status == "AVAILABLE"
        assert len(inr_res.products) == 1
        assert inr_res.products[0].price == Decimal("26.52")
        assert inr_res.products[0].currency == "USD"
        assert "filters" not in seen_bodies[0]

        # 2. currency="INR" WITH max_price must not forward INR amount as USD filter or drop USD listings
        inr_budget_res = await provider.search_products(
            "headphone", max_price=Decimal("500"), currency="INR", limit=10
        )
        assert len(inr_budget_res.products) == 1
        assert inr_budget_res.products[0].currency == "USD"
        assert "filters" not in seen_bodies[1]
        assert "original merchant prices" in (inr_budget_res.message or "").lower()

        # 3. Zero results must return NO_RESULTS rather than AVAILABLE
        mode["empty"] = True
        empty_res = await provider.search_products("headphone", currency="INR", limit=10)
        assert empty_res.provider_status == "NO_RESULTS"
        assert empty_res.products == []
    finally:
        monkeypatch.setattr(httpx, "AsyncClient", real_async_client)

