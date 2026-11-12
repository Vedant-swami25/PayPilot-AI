import React, { useEffect, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  CreditCard,
  ShieldCheck,
  ShoppingBag,
} from "lucide-react";
import { PageContainer } from "@/components/layout/MainLayout";
import { PageTransition } from "@/components/animations/PageTransition";
import { PaymentApproval } from "@/components/payments/PaymentApproval";
import { PayPalCheckout } from "@/components/payments/PayPalCheckout";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { EmptyState, Skeleton } from "@/components/ui/Skeleton";
import { useAuth } from "@/hooks/useAuth";
import {
  useApproveWorkflow,
  useCommerceHistory,
  useProductDetails,
  useWorkflow,
} from "@/hooks/useCommerce";
import {
  useCancelPayment,
  useCapturePayment,
  useCheckoutQuote,
  useCreateOrder,
  usePaymentOrder,
} from "@/hooks/usePayments";
import { useAppStore } from "@/store/useAppStore";
import { formatCurrency } from "@/utils/formatCurrency";

export default function Checkout() {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const { user } = useAuth();

  const paramPaymentId = searchParams.get("paymentId");
  const paramPaypalToken = searchParams.get("token");
  const paramPayerId = searchParams.get("PayerID");
  const paramWorkflowId = searchParams.get("workflowId");
  const paramProductId = searchParams.get("productId");
  const paramCurrency = searchParams.get("currency");
  const paramQuantity = Math.max(1, Number(searchParams.get("quantity") || 1));
  const aiPreferences = useAppStore((s) => s.aiPreferences);

  const isCancelReturn = location.pathname.endsWith("/cancel");
  const isSuccessReturn =
    location.pathname.endsWith("/success") || Boolean(paramPayerId);

  const [quantity, setQuantity] = useState(paramQuantity);
  const [activePaymentId, setActivePaymentId] = useState(paramPaymentId);

  useEffect(() => {
    if (paramPaymentId) setActivePaymentId(paramPaymentId);
  }, [paramPaymentId]);

  const { data: workflow, isLoading: workflowLoading } = useWorkflow(
    paramWorkflowId,
    { enabled: Boolean(paramWorkflowId) }
  );

  // _get_owned_order accepts either internal Order.id OR PayPal order token (?token=...)
  const resolvedPaymentId =
    activePaymentId || paramPaypalToken || workflow?.order_id || null;

  const { data: product, isLoading: productLoading } = useProductDetails(
    !resolvedPaymentId ? paramProductId : null,
    paramCurrency ? { currency: paramCurrency } : {}
  );

  const {
    data: order,
    isLoading: orderLoading,
    isFetching: orderSyncing,
    refetch: refetchOrder,
  } = usePaymentOrder(resolvedPaymentId, {
    sync: true,
    enabled: Boolean(resolvedPaymentId),
  });

  const { data: historyData } = useCommerceHistory({
    limit: 6,
    enabled: !resolvedPaymentId && !paramWorkflowId && !paramProductId,
  });

  const approveWorkflowMutation = useApproveWorkflow();
  const createOrderMutation = useCreateOrder();
  const captureMutation = useCapturePayment();
  const cancelMutation = useCancelPayment();

  const effectiveProduct =
    product ||
    (workflow?.discovered_products?.find(
      (p) =>
        p.id ===
        (paramProductId ||
          workflow.approved_product_id ||
          workflow.recommendation?.recommended_product_id)
    ) ||
      workflow?.discovered_products?.[0]);

  const requestedDisplayCurrency =
    paramCurrency ||
    effectiveProduct?.display_currency ||
    workflow?.parsed_intent?.currency ||
    aiPreferences?.preferredCurrency ||
    null;

  const {
    data: checkoutQuote,
    isLoading: quoteLoading,
    error: quoteError,
  } = useCheckoutQuote(
    {
      productId: effectiveProduct?.id,
      quantity,
      displayCurrency: requestedDisplayCurrency,
    },
    { enabled: Boolean(effectiveProduct?.id && !order) }
  );

  const handleAuthorizeOrder = async () => {
    if (checkoutQuote && checkoutQuote.can_checkout === false) {
      return;
    }
    if (workflow && !paramProductId) {
      const targetId =
        workflow.recommendation?.recommended_product_id ||
        effectiveProduct?.id ||
        null;
      const res = await approveWorkflowMutation.mutateAsync({
        workflowId: workflow.id,
        productId: targetId,
        quantity,
        confirmPurchase: true,
        createPaypalOrder: true,
      });
      const newOrderId = res?.payment_order?.id || res?.workflow?.order_id;
      if (newOrderId) {
        setActivePaymentId(newOrderId);
        setSearchParams({
          paymentId: newOrderId,
          workflowId: workflow.id,
        });
      }
      return;
    }

    if (effectiveProduct?.id) {
      const created = await createOrderMutation.mutateAsync({
        workflowId: workflow?.id || null,
        productId: effectiveProduct.id,
        quantity,
        expectedAmount: checkoutQuote?.payable_amount ?? null,
        expectedCurrency: checkoutQuote?.payable_currency ?? null,
        displayCurrency:
          checkoutQuote?.display_currency || requestedDisplayCurrency || null,
      });
      if (created?.id) {
        setActivePaymentId(created.id);
        setSearchParams({
          paymentId: created.id,
          ...(workflow?.id ? { workflowId: workflow.id } : {}),
        });
      }
    }
  };

  const authError =
    approveWorkflowMutation.error?.message ||
    createOrderMutation.error?.message ||
    "";

  const isLoadingContext =
    (Boolean(resolvedPaymentId) && orderLoading) ||
    (Boolean(paramWorkflowId) && workflowLoading && !order) ||
    (Boolean(paramProductId) && productLoading && !order);

  return (
    <PageTransition>
      <PageContainer
        title="Authorized PayPal Checkout"
        subtitle="Human-approved purchase review and backend-verified PayPal Orders v2 capture."
        action={
          <div className="flex items-center gap-2">
            <Link to="/transactions">
              <Button variant="outline" size="sm">
                Transaction Ledger
              </Button>
            </Link>
            <Link to="/command-center">
              <Button
                variant="secondary"
                size="sm"
                icon={<ArrowLeft className="h-4 w-4" />}
              >
                Shopping Assistant
              </Button>
            </Link>
          </div>
        }
      >
        <div className="max-w-4xl mx-auto space-y-6">
          {isCancelReturn && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10 p-4 text-xs text-amber-800 dark:text-amber-200 flex items-start gap-2.5">
              <AlertCircle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
              <div>
                <p className="font-semibold">PayPal Approval Cancelled</p>
                <p className="mt-0.5 opacity-90">
                  You cancelled authorization on PayPal. No funds were captured; you may retry checkout or cancel the uncaptured order below.
                </p>
              </div>
            </div>
          )}

          {isSuccessReturn && order && order.status === "APPROVED" && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 dark:border-emerald-500/30 dark:bg-emerald-500/10 p-4 text-xs text-[#067647] dark:text-emerald-200 flex items-start gap-2.5">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-[#12B76A] mt-0.5" />
              <div>
                <p className="font-semibold">PayPal Authorization Confirmed</p>
                <p className="mt-0.5 opacity-90">
                  PayPal reports this order as APPROVED. Click &ldquo;Capture Verified Payment&rdquo; below to finalize the transaction on the backend.
                </p>
              </div>
            </div>
          )}

          {isLoadingContext ? (
            <div className="space-y-4">
              <Skeleton className="h-56 w-full" />
              <Skeleton className="h-40 w-full" />
            </div>
          ) : order ? (
            <PayPalCheckout
              order={order}
              isSyncing={orderSyncing}
              onSyncOrder={refetchOrder}
              isCapturing={captureMutation.isPending}
              onCapturePayment={(id) => captureMutation.mutateAsync(id)}
              isCancelling={cancelMutation.isPending}
              onCancelOrder={(id) =>
                cancelMutation.mutateAsync({
                  paymentId: id,
                  reason: "Cancelled by user at checkout",
                })
              }
            />
          ) : effectiveProduct ? (
            <PaymentApproval
              product={effectiveProduct}
              workflow={workflow}
              quote={checkoutQuote}
              quoteLoading={quoteLoading}
              quoteError={quoteError?.message || ""}
              quantity={quantity}
              onQuantityChange={setQuantity}
              spendingLimit={user?.spending_limit}
              onAuthorizeOrder={handleAuthorizeOrder}
              isAuthorizing={
                approveWorkflowMutation.isPending || createOrderMutation.isPending
              }
              errorMessage={authError}
            />
          ) : (
            <div className="space-y-6">
              <EmptyState
                icon={<CreditCard className="h-5 w-5" />}
                title="No active checkout item selected"
                description="Start a shopping search or select any product in Discover to begin a protected PayPal checkout."
                action={
                  <div className="flex flex-wrap justify-center gap-2">
                    <Link to="/command-center">
                      <Button variant="primary" size="sm">
                        Open Shopping Assistant
                      </Button>
                    </Link>
                    <Link to="/products">
                      <Button variant="outline" size="sm">
                        Browse Products
                      </Button>
                    </Link>
                  </div>
                }
              />

              {historyData?.workflows?.some((w) => w.order_id || w.recommendation) && (
                <Card>
                  <CardHeader
                    title="Resume Saved Checkout"
                    subtitle="Recent recommendations ready for confirmation or PayPal payment"
                  />
                  <div className="space-y-2.5">
                    {historyData.workflows
                      .filter((w) => w.order_id || w.recommendation)
                      .slice(0, 4)
                      .map((wf) => (
                        <div
                          key={wf.id}
                          className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border-subtle bg-bg-secondary p-3.5"
                        >
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-text-primary truncate">
                              {wf.recommendation?.recommended_product_name ||
                                wf.request_text}
                            </p>
                            {wf.recommendation?.recommended_price != null && (
                              <p className="text-xs font-mono font-semibold text-text-secondary mt-0.5 tabular-nums">
                                {formatCurrency(
                                  wf.recommendation.recommended_price,
                                  wf.recommendation.currency
                                )}
                              </p>
                            )}
                          </div>
                          <Button
                            variant="primary"
                            size="xs"
                            icon={<ShoppingBag className="h-3.5 w-3.5" />}
                            onClick={() =>
                              setSearchParams(
                                wf.order_id
                                  ? { paymentId: wf.order_id, workflowId: wf.id }
                                  : { workflowId: wf.id }
                              )
                            }
                          >
                            {wf.order_id ? "Continue PayPal" : "Review & Approve"}
                          </Button>
                        </div>
                      ))}
                  </div>
                </Card>
              )}
            </div>
          )}

          <div className="flex items-center justify-center gap-2 text-xs text-text-muted pt-2">
            <ShieldCheck className="h-4 w-4 text-[#16A36A]" />
            <span>
              All payment totals and capture confirmations are cryptographically verified server-side via PayPal Orders v2.
            </span>
          </div>
        </div>
      </PageContainer>
    </PageTransition>
  );
}
