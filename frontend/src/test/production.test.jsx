import React from "react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/context/AuthContext";
import Register from "@/pages/Register";
import TransactionDetails from "@/pages/TransactionDetails";
import { paymentService } from "@/services/paymentService";
import { transactionService } from "@/services/transactionService";

function renderWithAppProviders(ui, initialEntries = ["/"]) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

describe("PayPilot AI Production Flows", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("validates password requirements on Register form before submission", async () => {
    renderWithAppProviders(<Register />, ["/register"]);

    fireEvent.change(screen.getByLabelText(/Full Name/i), {
      target: { value: "Ada Lovelace" },
    });
    fireEvent.change(screen.getByLabelText(/Email Address/i), {
      target: { value: "ada@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/^Password/i), {
      target: { value: "weakpass" },
    });
    fireEvent.change(screen.getByLabelText(/Confirm Password/i), {
      target: { value: "weakpass" },
    });

    fireEvent.click(screen.getByRole("button", { name: /Create Account/i }));

    expect(
      await screen.findByText(/at least one uppercase letter, one lowercase letter, and one digit/i)
    ).toBeInTheDocument();
  });

  it("supports two-step refund confirmation on completed TransactionDetails", async () => {
    const mockTx = {
      id: "tx-100",
      order_id: "ord-100",
      paypal_capture_id: "CAP-100",
      amount: "149.99",
      currency: "USD",
      status: "COMPLETED",
      payment_method: "paypal",
      created_at: "2026-11-12T10:00:00Z",
    };
    const mockOrder = {
      id: "ord-100",
      status: "COMPLETED",
      paypal_order_id: "PP-100",
      merchant: "SoundMart",
      quantity: 1,
    };

    vi.spyOn(transactionService, "getTransaction").mockResolvedValue(mockTx);
    vi.spyOn(paymentService, "getPayment").mockResolvedValue(mockOrder);
    const refundSpy = vi
      .spyOn(paymentService, "refundPayment")
      .mockResolvedValue({ ...mockOrder, status: "REFUNDED" });

    renderWithAppProviders(
      <Routes>
        <Route path="/transactions/:transactionId" element={<TransactionDetails />} />
      </Routes>,
      ["/transactions/tx-100"]
    );

    const requestRefundBtn = await screen.findByRole("button", {
      name: /Request Refund/i,
    });
    fireEvent.click(requestRefundBtn);

    const confirmBtn = await screen.findByRole("button", {
      name: /Confirm Refund/i,
    });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(refundSpy).toHaveBeenCalledWith(
        "ord-100",
        "Requested from transaction receipt"
      );
    });
  });
});

