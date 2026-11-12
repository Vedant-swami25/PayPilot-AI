import React, { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, CreditCard, ReceiptText, RotateCcw, ShieldCheck } from "lucide-react";
import { PageContainer } from "@/components/layout/MainLayout";
import { PageTransition } from "@/components/animations/PageTransition";
import { PaymentStatusBadge } from "@/components/payments/PaymentStatus";
import { Card, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { EmptyState, Skeleton } from "@/components/ui/Skeleton";
import {
  usePaymentOrder,
  useRefundPayment,
  useTransactionDetails,
} from "@/hooks/usePayments";
import { formatCurrency } from "@/utils/formatCurrency";
import { formatDateTime } from "@/utils/formatDate";

export default function TransactionDetails() {
  const { transactionId } = useParams();
  const [confirmRefund, setConfirmRefund] = useState(false);
  const {
    data: transaction,
    isLoading,
    error,
  } = useTransactionDetails(transactionId);

  const { data: order } = usePaymentOrder(transaction?.order_id, {
    sync: false,
    enabled: Boolean(transaction?.order_id),
  });
  const refundMutation = useRefundPayment();

  return (
    <PageTransition>
      <PageContainer
        title="Transaction Receipt & Audit"
        subtitle="Cryptographically tracked PayPal capture metadata and order snapshot."
        action={
          <Link to="/transactions">
            <Button variant="secondary" size="sm" icon={<ArrowLeft className="h-4 w-4" />}>
              Back to Ledger
            </Button>
          </Link>
        }
      >
        <div className="max-w-3xl mx-auto space-y-5">
          {isLoading ? (
            <Skeleton className="h-72 w-full" />
          ) : error || !transaction ? (
            <EmptyState
              icon={<ReceiptText className="h-5 w-5" />}
              title="Transaction not found"
              description={error?.message || "Unable to load this transaction record."}
            />
          ) : (
            <>
              <Card className="space-y-5">
                <CardHeader
                  title="Settlement Record"
                  subtitle={`Transaction ID: ${transaction.id}`}
                  action={<PaymentStatusBadge status={transaction.status} />}
                />

                <div className="rounded-xl border border-border-subtle bg-bg-secondary p-5 flex flex-wrap items-center justify-between gap-4">
                  <div>
                    <p className="text-xs font-medium text-text-secondary">
                      Authorized Amount
                    </p>
                    <p className="mt-1 text-3xl font-mono font-bold text-text-primary tabular-nums">
                      {formatCurrency(transaction.amount, transaction.currency)}
                    </p>
                  </div>
                  {order?.id &&
                    ["CREATED", "PENDING_APPROVAL", "APPROVED"].includes(
                      order.status
                    ) && (
                      <Link
                        to={`/checkout?paymentId=${encodeURIComponent(order.id)}`}
                      >
                        <Button
                          variant="primary"
                          size="sm"
                          icon={<CreditCard className="h-4 w-4" />}
                        >
                          Resume Checkout
                        </Button>
                      </Link>
                    )}
                  {order?.id &&
                    order.status === "COMPLETED" &&
                    transaction.paypal_capture_id &&
                    (!confirmRefund ? (
                      <Button
                        variant="outline"
                        size="sm"
                        icon={<RotateCcw className="h-4 w-4" />}
                        onClick={() => setConfirmRefund(true)}
                      >
                        Request Refund
                      </Button>
                    ) : (
                      <div className="flex items-center gap-2">
                        <Button
                          variant="danger"
                          size="sm"
                          loading={refundMutation.isPending}
                          disabled={refundMutation.isPending}
                          onClick={async () => {
                            await refundMutation.mutateAsync({
                              paymentId: order.id,
                              reason: "Requested from transaction receipt",
                            });
                            setConfirmRefund(false);
                          }}
                        >
                          Confirm Refund
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={refundMutation.isPending}
                          onClick={() => setConfirmRefund(false)}
                        >
                          Keep
                        </Button>
                      </div>
                    ))}
                </div>

                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                  <div className="rounded-xl border border-border-subtle bg-bg-secondary p-3.5">
                    <dt className="text-text-secondary">Order ID</dt>
                    <dd className="mt-1 font-mono text-text-primary break-all">
                      {transaction.order_id}
                    </dd>
                  </div>
                  <div className="rounded-xl border border-border-subtle bg-bg-secondary p-3.5">
                    <dt className="text-text-secondary">PayPal Capture ID</dt>
                    <dd className="mt-1 font-mono text-text-primary break-all">
                      {transaction.paypal_capture_id || "Pending / Not Captured"}
                    </dd>
                  </div>
                  <div className="rounded-xl border border-border-subtle bg-bg-secondary p-3.5">
                    <dt className="text-text-secondary">Payment Method</dt>
                    <dd className="mt-1 font-medium text-text-primary">
                      {transaction.payment_method || "PayPal"}
                    </dd>
                  </div>
                  <div className="rounded-xl border border-border-subtle bg-bg-secondary p-3.5">
                    <dt className="text-text-secondary">Timestamp</dt>
                    <dd className="mt-1 font-medium text-text-primary">
                      {formatDateTime(transaction.created_at)}
                    </dd>
                  </div>
                </dl>

                {transaction.failure_reason && (
                  <div
                    className={`rounded-xl border p-3.5 text-xs ${
                      transaction.status === "REFUNDED"
                        ? "border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-200"
                        : "border-rose-200 bg-rose-50 text-[#B42318] dark:border-rose-500/35 dark:bg-rose-500/10 dark:text-rose-300"
                    }`}
                  >
                    <p className="font-semibold">
                      {transaction.status === "REFUNDED"
                        ? "Refund Note"
                        : "Failure Diagnostic"}
                    </p>
                    <p className="mt-1">{transaction.failure_reason}</p>
                  </div>
                )}

                {order && (
                  <div className="rounded-xl border border-border-subtle bg-bg-secondary p-4 space-y-2 text-xs">
                    <p className="font-semibold text-text-primary inline-flex items-center gap-1.5">
                      <ShieldCheck className="h-4 w-4 text-[#16A36A]" />
                      Verified Order Metadata
                    </p>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-1">
                      <div>
                        <span className="text-text-secondary">Merchant</span>
                        <p className="font-medium text-text-primary mt-0.5">
                          {order.merchant || "Verified Seller"}
                        </p>
                      </div>
                      <div>
                        <span className="text-text-secondary">PayPal Order ID</span>
                        <p className="font-mono text-text-primary mt-0.5">
                          {order.paypal_order_id || "—"}
                        </p>
                      </div>
                      <div>
                        <span className="text-text-secondary">Quantity</span>
                        <p className="font-mono text-text-primary mt-0.5">
                          {order.quantity}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </Card>
            </>
          )}
        </div>
      </PageContainer>
    </PageTransition>
  );
}
