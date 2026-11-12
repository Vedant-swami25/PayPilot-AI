from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_product_service
from app.core.database import get_db
from app.models.user import User
from app.schemas.product import (
    ProductCompareRequest,
    ProductComparisonResponse,
    ProductResponse,
    ProductSearchResponse,
)
from app.services.product_service import ProductService

router = APIRouter(prefix="/products", tags=["Products"])


@router.get(
    "/search",
    response_model=ProductSearchResponse,
    summary="Search verified product providers for matching commerce listings",
)
async def search_products(
    query: str = Query(..., min_length=2, max_length=200),
    max_price: Decimal | None = Query(default=None, gt=0),
    currency: str = Query(default="USD", min_length=3, max_length=3),
    limit: int = Query(default=10, ge=1, le=30),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    product_service: ProductService = Depends(get_product_service),
) -> ProductSearchResponse:
    return await product_service.search_products(
        session,
        query=query,
        max_price=max_price,
        currency=currency,
        limit=limit,
    )


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Retrieve detailed product metadata by internal or external product ID",
)
async def get_product_details(
    product_id: str,
    currency: str | None = Query(default=None, min_length=3, max_length=3),
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    product_service: ProductService = Depends(get_product_service),
) -> ProductResponse:
    product = await product_service.get_product(session, product_id)
    return await product_service.to_product_response(product, target_currency=currency)


@router.post(
    "/compare",
    response_model=ProductComparisonResponse,
    summary="Deterministically compare prices, budget compliance, and specifications across products",
)
async def compare_products(
    payload: ProductCompareRequest,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    product_service: ProductService = Depends(get_product_service),
) -> ProductComparisonResponse:
    return await product_service.compare_products(session, payload)

