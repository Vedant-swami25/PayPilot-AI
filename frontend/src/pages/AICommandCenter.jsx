import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  CreditCard,
  History,
  PlusCircle,
  ShieldAlert,
  ShieldCheck,
  ShoppingBag,
  StopCircle,
} from "lucide-react";
import { PageContainer } from "@/components/layout/MainLayout";
import { PageTransition } from "@/components/animations/PageTransition";
import {
  ShoppingProgress,
  ShoppingStatusBadge,
  formatShoppingStepLabel,
} from "@/components/commerce/ShoppingStatus";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { ProductGrid } from "@/components/commerce/ProductCard";
import { RecommendationCard } from "@/components/commerce/RecommendationCard";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  useApproveWorkflow,
  useCancelWorkflow,
  useCommerce,
  useCommerceHistory,
  useSubmitCommerceRequest,
  useWorkflow,
} from "@/hooks/useCommerce";
import { useAuth } from "@/hooks/useAuth";
import { useAppStore } from "@/store/useAppStore";
import { SUGGESTED_PROMPTS } from "@/utils/constants";
import { formatCurrency, getDisplayMoney } from "@/utils/formatCurrency";
import { formatDateTime, formatRelativeTime } from "@/utils/formatDate";

export default function AICommandCenter() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const { compareIds, toggleCompareProduct, activeWorkflowId, setActiveWorkflowId } =
    useCommerce();
  const aiPreferences = useAppStore((s) => s.aiPreferences);

  const paramWorkflowId = searchParams.get("workflowId");
  const paramPrompt = searchParams.get("prompt") || "";
  const [selectedWorkflowId, setSelectedWorkflowId] = useState(
    paramWorkflowId || activeWorkflowId || null
  );

  useEffect(() => {
    if (paramWorkflowId && paramWorkflowId !== selectedWorkflowId) {
      setSelectedWorkflowId(paramWorkflowId);
      setActiveWorkflowId(paramWorkflowId);
    }
  }, [paramWorkflowId, selectedWorkflowId, setActiveWorkflowId]);

  const { data: historyData, isLoading: historyLoading } = useCommerceHistory({
    limit: 20,
  });
  const { data: workflow, isLoading: workflowLoading } = useWorkflow(
    selectedWorkflowId
  );

  const submitMutation = useSubmitCommerceRequest();
  const approveMutation = useApproveWorkflow();
  const cancelMutation = useCancelWorkflow();

  const isRunning =
    submitMutation.isPending ||
    workflow?.status === "RUNNING" ||
    workflow?.status === "PENDING";

  const handleSelectWorkflow = (id) => {
    setSelectedWorkflowId(id);
    setActiveWorkflowId(id);
    if (id) {
      setSearchParams({ workflowId: id });
    } else {
      setSearchParams({});
    }
  };

  const handleSubmitRequest = async (payload) => {
    try {
      const created = await submitMutation.mutateAsync(payload);
      setSelectedWorkflowId(created.id);
      setActiveWorkflowId(created.id);
      setSearchParams({ workflowId: created.id });
    } catch {
      // Handled by hook toast
    }
  };

  const handleApproveAndCheckout = async () => {
    if (!workflow) return;
    if (workflow.order_id) {
      navigate(
        `/checkout?paymentId=${encodeURIComponent(
          workflow.order_id
        )}&workflowId=${encodeURIComponent(workflow.id)}`
      );
      return;
    }

    const recommendedId =
      workflow.recommendation?.recommended_product_id ||
      workflow.discovered_products?.[0]?.id ||
      null;

    try {
      const res = await approveMutation.mutateAsync({
        workflowId: workflow.id,
        productId: recommendedId,
        quantity: 1,
        confirmPurchase: true,
        createPaypalOrder: true,
      });
      const orderId = res?.payment_order?.id || res?.workflow?.order_id;
      if (orderId) {
        navigate(
          `/checkout?paymentId=${encodeURIComponent(
            orderId
          )}&workflowId=${encodeURIComponent(workflow.id)}`
        );
      }
    } catch {
      // Handled by hook toast
    }
  };

  const handleSelectProductCheckout = (product) => {
    navigate(
      `/checkout?productId=${encodeURIComponent(product.id)}${
        workflow?.id ? `&workflowId=${encodeURIComponent(workflow.id)}` : ""
      }`
    );
  };

  const handleOpenComparison = () => {
    if (!workflow?.discovered_products?.length) return;
    workflow.discovered_products.slice(0, 4).forEach((p) => {
      if (!compareIds.includes(p.id)) {
        toggleCompareProduct(p.id);
      }
    });
    navigate(`/compare?workflowId=${encodeURIComponent(workflow.id)}`);
  };

  const defaultCurrency =
    aiPreferences?.preferredCurrency ||
    user?.spending_limit?.currency ||
    "USD";

  const processingMessage = workflow?.current_step
    ? `${formatShoppingStepLabel(workflow.current_step)}...`
    : "Understanding your request & searching live merchant listings...";

  return (
    <PageTransition>
      <PageContainer
        title="Shopping Assistant"
        subtitle="Describe what you're looking for to compare live merchant prices and check out safely with PayPal."
        action={
          <div className="flex items-center gap-2">
            {compareIds.length > 0 && (
              <Link to="/compare">
                <Button variant="secondary" size="sm">
                  Compare ({compareIds.length})
                </Button>
              </Link>
            )}
            <Button
              variant="outline"
              size="sm"
              icon={<PlusCircle className="h-4 w-4" />}
              onClick={() => handleSelectWorkflow(null)}
            >
              New Search
            </Button>
          </div>
        }
      >
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Left Panel: Shopping Sessions */}
          <Card className="lg:col-span-3 space-y-3 max-h-[760px] flex flex-col">
            <div className="flex items-center justify-between border-b border-border-subtle pb-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-text-primary">
                <History className="h-4 w-4 text-text-secondary" />
                <span>Shopping Sessions</span>
              </div>
              <Badge tone="slate">{historyData?.total ?? 0}</Badge>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {historyLoading ? (
                <div className="space-y-2">
                  <Skeleton className="h-14 w-full" />
                  <Skeleton className="h-14 w-full" />
                </div>
              ) : !historyData?.workflows?.length ? (
                <p className="text-xs text-text-secondary py-6 text-center">
                  Your shopping searches will appear here.
                </p>
              ) : (
                historyData.workflows.map((wf) => {
                  const selected = wf.id === selectedWorkflowId;
                  return (
                    <button
                      key={wf.id}
                      type="button"
                      onClick={() => handleSelectWorkflow(wf.id)}
                      className={`w-full text-left rounded-xl border p-3 transition-colors ${
                        selected
                          ? "border-[#16A36A] bg-emerald-50/70 dark:bg-emerald-500/10"
                          : "border-border-subtle bg-bg-secondary hover:border-slate-300 dark:hover:border-slate-600"
                      }`}
                    >
                      <p className="text-xs font-medium text-text-primary line-clamp-2">
                        {wf.request_text}
                      </p>
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <ShoppingStatusBadge status={wf.status} />
                        <span className="text-[10px] text-text-muted">
                          {formatRelativeTime(wf.created_at)}
                        </span>
                      </div>
                    </button>
                  );
                })
              )}
            </div>
          </Card>

          {/* Center Panel: Interactive Conversation & Results */}
          <Card className="lg:col-span-6 flex flex-col min-h-[640px] max-h-[820px]">
            <div className="flex items-center justify-between border-b border-border-subtle pb-3 mb-2">
              <div className="flex items-center gap-2">
                <ShoppingBag className="h-4 w-4 text-[#16A36A]" />
                <span className="text-sm font-semibold text-text-primary">
                  Shopping Assistant
                </span>
              </div>
              <div className="flex items-center gap-2">
                {workflow && (
                  <ShoppingStatusBadge
                    status={workflow.status}
                    currentStep={workflow.current_step}
                    showStage
                  />
                )}
                {isRunning && workflow?.id && (
                  <Button
                    variant="danger"
                    size="xs"
                    icon={<StopCircle className="h-3.5 w-3.5" />}
                    loading={cancelMutation.isPending}
                    onClick={() => cancelMutation.mutate(workflow.id)}
                  >
                    Stop
                  </Button>
                )}
              </div>
            </div>

            <ChatWindow isProcessing={isRunning} processingText={processingMessage}>
              {!workflow && !submitMutation.isPending && !workflowLoading && (
                <div className="py-10 px-4 text-center space-y-5">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-bg-secondary border border-border-subtle text-[#16A36A]">
                    <ShoppingBag className="h-6 w-6" />
                  </div>
                  <div className="max-w-md mx-auto space-y-1.5">
                    <h3 className="text-base font-semibold text-text-primary">
                      What are you shopping for today?
                    </h3>
                    <p className="text-xs text-text-secondary leading-relaxed">
                      Share your preferences, brand specs, and maximum budget. PayPilot searches real-time merchant listings, compares prices, checks spending limits, and prepares PayPal checkout strictly after your confirmation.
                    </p>
                  </div>
                  <div className="flex flex-wrap justify-center gap-2 max-w-lg mx-auto">
                    {SUGGESTED_PROMPTS.map((sample) => (
                      <button
                        key={sample}
                        type="button"
                        onClick={() =>
                          handleSubmitRequest({
                            requestText: sample,
                            currency: defaultCurrency,
                            quantity: 1,
                          })
                        }
                        className="rounded-lg border border-border-subtle bg-bg-secondary px-3 py-1.5 text-xs text-text-secondary hover:border-[#16A36A]/50 hover:text-text-primary transition-colors text-left"
                      >
                        {sample}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {workflowLoading && selectedWorkflowId && (
                <div className="space-y-4 py-4">
                  <Skeleton className="h-16 w-3/4 ml-auto" />
                  <Skeleton className="h-44 w-full" />
                </div>
              )}

              {workflow && (
                <>
                  {/* User Message */}
                  <ChatMessage
                    role="user"
                    content={workflow.request_text}
                    timestamp={formatDateTime(workflow.created_at)}
                  />

                  {/* Search Criteria Summary */}
                  {workflow.parsed_intent && (
                    <ChatMessage
                      role="assistant"
                      title="Search Criteria"
                      content={
                        workflow.parsed_intent.clarification_question ||
                        workflow.parsed_intent.reasoning ||
                        "Extracted product requirements and budget target."
                      }
                    >
                      <div className="flex flex-wrap gap-1.5">
                        {workflow.parsed_intent.search_query && (
                          <Badge tone="slate">
                            Search: {workflow.parsed_intent.search_query}
                          </Badge>
                        )}
                        {workflow.parsed_intent.budget && (
                          <Badge tone="emerald">
                            Budget: {workflow.parsed_intent.budget}{" "}
                            {workflow.parsed_intent.currency || "USD"}
                          </Badge>
                        )}
                        {workflow.parsed_intent.category && (
                          <Badge tone="slate">
                            {workflow.parsed_intent.category}
                          </Badge>
                        )}
                      </div>
                    </ChatMessage>
                  )}

                  {/* Edge States */}
                  {workflow.status === "NEEDS_CLARIFICATION" && (
                    <div className="rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10 p-4 text-xs text-amber-800 dark:text-amber-200 flex items-start gap-2.5">
                      <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
                      <div>
                        <p className="font-semibold">A few more details needed</p>
                        <p className="mt-1">
                          {workflow.error_message ||
                            workflow.parsed_intent?.clarification_question ||
                            "Submit a follow-up request below with product category, specs, or budget."}
                        </p>
                      </div>
                    </div>
                  )}

                  {workflow.status === "BLOCKED_BY_SECURITY" && (
                    <div className="rounded-xl border border-rose-200 bg-rose-50 dark:border-rose-500/35 dark:bg-rose-500/10 p-4 text-xs text-[#B42318] dark:text-rose-200 flex items-start gap-2.5">
                      <ShieldAlert className="h-4 w-4 shrink-0 text-[#D92D20] mt-0.5" />
                      <div>
                        <p className="font-semibold">Blocked by Spending Limit</p>
                        <p className="mt-1">
                          {workflow.error_message ||
                            workflow.security_assessment?.assessment_summary ||
                            "This request exceeds your configured account spending limits."}
                        </p>
                      </div>
                    </div>
                  )}

                  {(workflow.status === "FAILED" ||
                    workflow.status === "NOT_CONFIGURED" ||
                    workflow.status === "NO_PRODUCTS_FOUND") && (
                    <div className="rounded-xl border border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10 p-4 text-xs text-amber-800 dark:text-amber-200 space-y-2">
                      <p className="font-semibold">
                        {workflow.status === "NO_PRODUCTS_FOUND"
                          ? "No matching products found"
                          : "Unable to complete search"}
                      </p>
                      <p>
                        {workflow.error_message ||
                          "No matching in-stock items were found. Try adjusting your keywords or budget."}
                      </p>
                      {workflow.status !== "NO_PRODUCTS_FOUND" && (
                        <Link
                          to="/settings"
                          className="inline-block font-semibold text-[#16A36A] hover:underline"
                        >
                          Check Connected Services in Settings &rarr;
                        </Link>
                      )}
                    </div>
                  )}

                  {/* Recommendation & Approval Checkpoint */}
                  {workflow.recommendation && (
                    <RecommendationCard
                      recommendation={workflow.recommendation}
                      securityAssessment={workflow.security_assessment}
                      approving={approveMutation.isPending}
                      alreadyApproved={Boolean(workflow.order_id)}
                      onCompare={
                        workflow.discovered_products?.length > 1
                          ? handleOpenComparison
                          : null
                      }
                      onApproveAndCheckout={handleApproveAndCheckout}
                    />
                  )}

                  {/* Discovered Products Grid */}
                  {workflow.discovered_products?.length > 0 && (
                    <div className="space-y-3 pt-2">
                      <div className="flex items-center justify-between">
                        <h4 className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
                          Product Matches ({workflow.discovered_products.length})
                        </h4>
                        {workflow.discovered_products.length > 1 && (
                          <button
                            type="button"
                            onClick={handleOpenComparison}
                            className="text-xs font-semibold text-[#16A36A] hover:underline"
                          >
                            Compare Side by Side
                          </button>
                        )}
                      </div>
                      <ProductGrid
                        products={workflow.discovered_products}
                        recommendedProductId={
                          workflow.recommendation?.recommended_product_id
                        }
                        compareIds={compareIds}
                        onToggleCompare={toggleCompareProduct}
                        onSelectForCheckout={handleSelectProductCheckout}
                      />
                    </div>
                  )}
                </>
              )}
            </ChatWindow>

            <div className="mt-3 pt-3 border-t border-border-subtle">
              <ChatInput
                onSubmit={handleSubmitRequest}
                loading={submitMutation.isPending}
                defaultCurrency={defaultCurrency}
                initialText={paramPrompt}
              />
            </div>
          </Card>

          {/* Right Panel: Clean Order Progress & Checkout Summary */}
          <div className="lg:col-span-3 space-y-5">
            <Card className="p-5 space-y-4">
              <ShoppingProgress
                workflow={workflow}
                isSubmitting={submitMutation.isPending}
              />
              {workflow?.order_id && (
                <Link
                  to={`/checkout?paymentId=${encodeURIComponent(
                    workflow.order_id
                  )}&workflowId=${encodeURIComponent(workflow.id)}`}
                  className="block w-full pt-1"
                >
                  <Button
                    variant="emerald"
                    size="sm"
                    className="w-full"
                    icon={<CreditCard className="h-4 w-4" />}
                  >
                    Open PayPal Checkout
                  </Button>
                </Link>
              )}
            </Card>

            <Card className="p-5 space-y-3 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-text-primary">Order Summary</span>
                <ShieldCheck className="h-4 w-4 text-[#16A36A]" />
              </div>
              {workflow?.recommendation ? (
                <div className="space-y-2">
                  <div className="rounded-xl border border-border-subtle bg-bg-secondary p-3">
                    <p className="text-[11px] text-text-muted">Recommended Product</p>
                    <p className="font-medium text-text-primary mt-0.5 line-clamp-2">
                      {workflow.recommendation.recommended_product_name}
                    </p>
                    {(() => {
                      const recMoney = getDisplayMoney(workflow.recommendation);
                      return (
                        <div className="mt-1 space-y-0.5">
                          <p className="font-mono font-semibold text-text-primary tabular-nums">
                            {formatCurrency(
                              recMoney.displayPrice,
                              recMoney.displayCurrency
                            )}
                          </p>
                          {recMoney.hasConversion && (
                            <p className="text-[11px] text-text-muted tabular-nums">
                              Merchant:{" "}
                              {formatCurrency(
                                recMoney.originalPrice,
                                recMoney.originalCurrency
                              )}{" "}
                              {recMoney.originalCurrency}
                            </p>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                  {workflow.discovered_products?.length > 1 && (
                    <Button
                      variant="secondary"
                      size="xs"
                      className="w-full"
                      onClick={handleOpenComparison}
                    >
                      Compare {workflow.discovered_products.length} Options
                    </Button>
                  )}
                </div>
              ) : (
                <p className="text-text-secondary leading-relaxed">
                  Every search checks your configured spending caps and requires explicit confirmation before a PayPal order is created.
                </p>
              )}
              <Link
                to="/settings"
                className="inline-block text-[11px] font-semibold text-[#16A36A] hover:underline"
              >
                Adjust spending limits in Settings &rarr;
              </Link>
            </Card>
          </div>
        </div>
      </PageContainer>
    </PageTransition>
  );
}
