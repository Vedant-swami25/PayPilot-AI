from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    external_product_id: str
    name: str
    description: str | None = None
    image_url: str | None = None
    price: Decimal
    currency: str
    original_price: Decimal | None = None
    original_currency: str | None = None
    display_price: Decimal | None = None
    display_currency: str | None = None
    exchange_rate: Decimal | None = None
    exchange_rate_timestamp: datetime | None = None
    merchant: str
    product_url: str | None = None
    availability: str
    category: str | None = None
    specifications: dict[str, Any] | None = None
    provider: str
    is_test_data: bool = False
    created_at: datetime | None = None

    @model_validator(mode="after")
    def _fill_currency_defaults(self) -> "ProductResponse":
        if self.original_price is None:
            self.original_price = self.price
        if self.original_currency is None:
            self.original_currency = self.currency
        if self.display_price is None:
            self.display_price = self.price
        if self.display_currency is None:
            self.display_currency = self.currency
        return self


class ProductSearchResponse(BaseModel):
    query: str
    provider: str
    is_test_data: bool = False
    provider_status: str = "AVAILABLE"
    total: int
    products: list[ProductResponse]
    message: str | None = None
    display_currency: str | None = None
    exchange_rate: Decimal | None = None
    exchange_rate_timestamp: datetime | None = None


class ProductCompareRequest(BaseModel):
    product_ids: list[str] = Field(
        ...,
        min_length=2,
        max_length=10,
        description="List of persisted product IDs or external product IDs to compare.",
    )
    budget: Decimal | None = Field(default=None, gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    requirements: list[str] = Field(default_factory=list)


class ProductComparisonItem(BaseModel):
    product_id: str
    external_product_id: str
    name: str
    merchant: str
    price: Decimal
    currency: str
    original_price: Decimal | None = None
    original_currency: str | None = None
    display_price: Decimal | None = None
    display_currency: str | None = None
    exchange_rate: Decimal | None = None
    exchange_rate_timestamp: datetime | None = None
    availability: str
    price_delta_from_lowest: Decimal
    price_delta_percent: Decimal
    within_budget: bool | None = None
    requirement_match_score: Decimal
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    specifications: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _fill_comparison_currency_defaults(self) -> "ProductComparisonItem":
        if self.original_price is None:
            self.original_price = self.price
        if self.original_currency is None:
            self.original_currency = self.currency
        if self.display_price is None:
            self.display_price = self.price
        if self.display_currency is None:
            self.display_currency = self.currency
        return self


class ProductComparisonResponse(BaseModel):
    currency: str
    lowest_price: Decimal
    highest_price: Decimal
    average_price: Decimal
    price_spread: Decimal
    best_value_product_id: str | None = None
    items: list[ProductComparisonItem]
    summary: str
    exchange_rate: Decimal | None = None
    exchange_rate_timestamp: datetime | None = None

