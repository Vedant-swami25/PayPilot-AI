import React from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, PackageX } from "lucide-react";
import { PageContainer } from "@/components/layout/MainLayout";
import { PageTransition } from "@/components/animations/PageTransition";
import { ProductDetailsView } from "@/components/commerce/ProductDetails";
import { Button } from "@/components/ui/Button";
import { EmptyState, Skeleton } from "@/components/ui/Skeleton";
import { useCommerce, useProductDetails } from "@/hooks/useCommerce";
import { useAppStore } from "@/store/useAppStore";

export default function ProductDetails() {
  const { productId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const aiPreferences = useAppStore((s) => s.aiPreferences);
  const displayCurrency =
    searchParams.get("currency") || aiPreferences?.preferredCurrency || null;
  const { compareIds, toggleCompareProduct } = useCommerce();
  const { data: product, isLoading, error } = useProductDetails(productId, {
    currency: displayCurrency,
  });

  return (
    <PageTransition>
      <PageContainer
        title={product ? product.name : "Product Specifications"}
        subtitle="Verified merchant pricing, seller details, and specifications."
        action={
          <Link to="/products">
            <Button variant="secondary" size="sm" icon={<ArrowLeft className="h-4 w-4" />}>
              Back to Discover
            </Button>
          </Link>
        }
      >
        {isLoading ? (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <Skeleton className="lg:col-span-5 h-96" />
            <Skeleton className="lg:col-span-7 h-96" />
          </div>
        ) : error || !product ? (
          <EmptyState
            icon={<PackageX className="h-5 w-5" />}
            title="Product record unavailable"
            description={error?.message || "This product could not be found in the verified catalog."}
            action={
              <Link to="/products">
                <Button variant="primary" size="sm">
                  Search Catalog
                </Button>
              </Link>
            }
          />
        ) : (
          <ProductDetailsView
            product={product}
            isCompared={compareIds.includes(product.id)}
            onToggleCompare={toggleCompareProduct}
            onProceedToCheckout={(prod, qty) =>
              navigate(
                `/checkout?productId=${encodeURIComponent(prod.id)}&quantity=${qty}${
                  prod.display_currency || displayCurrency
                    ? `&currency=${encodeURIComponent(
                        prod.display_currency || displayCurrency
                      )}`
                    : ""
                }`
              )
            }
          />
        )}
      </PageContainer>
    </PageTransition>
  );
}
