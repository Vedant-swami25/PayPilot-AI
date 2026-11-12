import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppProviders, createAppQueryClient } from "@/app/providers";
import { AppRoutes } from "@/app/routes";
import {
  ShoppingProgress,
  ShoppingStatusBadge,
  deriveStageIndex,
  formatShoppingStepLabel,
} from "@/components/commerce/ShoppingStatus";
import { ProductComparison } from "@/components/commerce/ProductComparison";
import { PaymentApproval } from "@/components/payments/PaymentApproval";
import { PayPalCheckout } from "@/components/payments/PayPalCheckout";
import { PayPilotLogo } from "@/components/ui/Logo";
import { formatCurrency, getDisplayMoney } from "@/utils/formatCurrency";
import { tokenVault } from "@/services/api";
import { authService } from "@/services/authService";
import { paymentService } from "@/services/paymentService";
import { productService } from "@/services/productService";
import { useAppStore } from "@/store/useAppStore";

function renderAtRoute(initialEntry = "/") {
  const queryClient = createAppQueryClient();
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AppProviders queryClient={queryClient} useRouter={false}>
        <AppRoutes />
      </AppProviders>
    </MemoryRouter>
  );
}

describe("PayPilot AI Frontend Core Suite", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    tokenVault.clear();
    useAppStore.setState({
      compareIds: [],
      activeWorkflowId: null,
      toasts: [],
    });
    vi.restoreAllMocks();
  });

  it("never stores refresh tokens in localStorage or sessionStorage", () => {
    tokenVault.setTokens(
      {
        accessToken: "access_secret_123",
        refreshToken: "refresh_secret_999",
      },
      true
    );

    expect(tokenVault.getAccessToken()).toBe("access_secret_123");
    expect(tokenVault.getRefreshToken()).toBe("refresh_secret_999");

    const serializedLocal = JSON.stringify(window.localStorage);
    const serializedSession = JSON.stringify(window.sessionStorage);
    expect(serializedLocal).not.toContain("refresh_secret_999");
    expect(serializedSession).not.toContain("refresh_secret_999");

    tokenVault.clear();
    expect(tokenVault.getAccessToken()).toBeNull();
    expect(tokenVault.getRefreshToken()).toBeNull();
  });

  it("maps internal workflow steps to customer-friendly shopping stages without leaking agent names", () => {
    expect(deriveStageIndex(null, false)).toBe(-1);
    expect(deriveStageIndex(null, true)).toBe(0);
    expect(
      deriveStageIndex({
        status: "RUNNING",
        current_step: "DISCOVERY_AGENT",
      })
    ).toBe(1);
    expect(
      deriveStageIndex({
        status: "AWAITING_USER_APPROVAL",
      })
    ).toBe(3);
    expect(deriveStageIndex({ status: "COMPLETED" })).toBe(4);
    expect(formatShoppingStepLabel("DISCOVERY_AGENT")).toBe(
      "Searching live merchant listings"
    );

    render(
      <div>
        <ShoppingStatusBadge
          status="RUNNING"
          currentStep="DISCOVERY_AGENT"
          showStage
        />
        <ShoppingProgress
          workflow={{
            status: "RUNNING",
            current_step: "DISCOVERY_AGENT",
          }}
        />
      </div>
    );
    expect(
      screen.getByText(/Searching live merchant listings/i)
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Searching merchant listings/i)
    ).toBeInTheDocument();
    expect(screen.queryByText(/DISCOVERY_AGENT/)).not.toBeInTheDocument();
  });

  it("protects private routes and redirects unauthenticated users to /login", async () => {
    renderAtRoute("/dashboard");

    await waitFor(() => {
      expect(screen.getByText(/Sign in to PayPilot AI/i)).toBeInTheDocument();
    });
  });

  it("renders deterministic ProductComparison matrix and fires selection callback", () => {
    const onSelect = vi.fn();
    render(
      <ProductComparison
        onSelectProduct={onSelect}
        comparison={{
          currency: "USD",
          lowest_price: "799.00",
          highest_price: "999.00",
          average_price: "899.00",
          price_spread: "200.00",
          best_value_product_id: "prod_1",
          summary: "Model A saves $200 vs Model B.",
          items: [
            {
              product_id: "prod_1",
              name: "Laptop Alpha",
              merchant: "TechHub",
              price: "799.00",
              currency: "USD",
              availability: "IN_STOCK",
              price_delta_from_lowest: "0.00",
              price_delta_percent: 0,
              within_budget: true,
              requirement_match_score: 0.96,
              pros: ["Best price"],
              cons: [],
              specifications: { ram: "16GB" },
            },
            {
              product_id: "prod_2",
              name: "Laptop Beta",
              merchant: "StoreB",
              price: "999.00",
              currency: "USD",
              availability: "IN_STOCK",
              price_delta_from_lowest: "200.00",
              price_delta_percent: 25,
              within_budget: true,
              requirement_match_score: 0.85,
              pros: ["Larger panel"],
              cons: ["Higher price"],
              specifications: { ram: "16GB" },
            },
          ],
        }}
      />
    );

    expect(screen.getAllByText("Laptop Alpha").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Best Overall Match").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("96% match")).toBeInTheDocument();

    const buttons = screen.getAllByRole("button", { name: /Select & Checkout/i });
    fireEvent.click(buttons[0]);
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ product_id: "prod_1" })
    );
  });

  it("enforces human consent & security guardrails in PaymentApproval", () => {
    const onAuthorize = vi.fn();
    const product = {
      id: "prod_1",
      name: "Workstation Pro",
      price: "950.00",
      currency: "USD",
      merchant: "VerifiedStore",
      availability: "IN_STOCK",
    };

    const { rerender } = render(
      <PaymentApproval
        product={product}
        workflow={{ status: "AWAITING_USER_APPROVAL", security_assessment: { risk_level: "LOW" } }}
        onAuthorizeOrder={onAuthorize}
      />
    );

    const authBtn = screen.getByRole("button", {
      name: /Authorize & Create PayPal Order/i,
    });
    expect(authBtn).toBeDisabled();

    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);
    expect(authBtn).toBeEnabled();

    fireEvent.click(authBtn);
    expect(onAuthorize).toHaveBeenCalledTimes(1);

    // Blocked by Security Agent must hard-disable order creation
    rerender(
      <PaymentApproval
        product={product}
        workflow={{
          status: "BLOCKED_BY_SECURITY",
          security_assessment: {
            risk_level: "HIGH",
            block_execution: true,
            assessment_summary: "Exceeds daily spending limit.",
          },
        }}
        onAuthorizeOrder={onAuthorize}
      />
    );

    expect(
      screen.getByRole("button", { name: /Authorize & Create PayPal Order/i })
    ).toBeDisabled();
    expect(screen.getByText(/Blocked by Security/i)).toBeInTheDocument();
  });

  it("shows Capture button only when APPROVED and success animation only when COMPLETED", () => {
    const baseOrder = {
      id: "ord_local_1",
      paypal_order_id: "PAYPAL_ABC123",
      amount: "450.00",
      currency: "USD",
      quantity: 1,
      merchant: "VerifiedAudio",
      status: "PENDING_APPROVAL",
      allowed_actions: ["cancel"],
    };

    const { rerender } = render(<PayPalCheckout order={baseOrder} />);
    expect(
      screen.queryByRole("button", { name: /Capture Verified Payment/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Verified PayPal Capture Completed/i)
    ).not.toBeInTheDocument();

    rerender(
      <PayPalCheckout
        order={{
          ...baseOrder,
          status: "APPROVED",
          allowed_actions: ["capture", "cancel"],
        }}
      />
    );
    expect(
      screen.getByRole("button", { name: /Capture Verified Payment/i })
    ).toBeInTheDocument();

    rerender(
      <PayPalCheckout
        order={{
          ...baseOrder,
          status: "COMPLETED",
          allowed_actions: [],
        }}
      />
    );
    expect(
      screen.getByText(/Verified PayPal Capture Completed/i)
    ).toBeInTheDocument();
    expect(screen.getByText(/Payment Confirmed/i)).toBeInTheDocument();
  });

  it("renders Login page and validates empty password error note cleanly", async () => {
    renderAtRoute("/login");
    expect(screen.getByText(/Sign in to PayPilot AI/i)).toBeInTheDocument();
    const forgotBtn = screen.getByRole("button", { name: /Forgot password\?/i });
    fireEvent.click(forgotBtn);
    expect(
      screen.getByText(/Self-service password recovery is not currently exposed/i)
    ).toBeInTheDocument();
  });

  it("enforces password complexity aligned with backend security rules on Register", async () => {
    renderAtRoute("/register");
    fireEvent.change(screen.getByLabelText(/Full Name/i), {
      target: { value: "Alex Rivera" },
    });
    fireEvent.change(screen.getByLabelText(/Email Address/i), {
      target: { value: "alex@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/^Password$/i), {
      target: { value: "alllowercase" },
    });
    fireEvent.change(screen.getByLabelText(/Confirm Password/i), {
      target: { value: "alllowercase" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Create Account/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/one uppercase letter, one lowercase letter, and one digit/i)
      ).toBeInTheDocument();
    });
  });

  it("handles PayPal /checkout/success?token=... redirect return cleanly when authenticated", async () => {
    tokenVault.setTokens({
      accessToken: "valid_access_token",
      refreshToken: "valid_refresh_token",
    });
    vi.spyOn(authService, "getMe").mockResolvedValue({
      id: "user_1",
      name: "Alex Rivera",
      email: "alex@example.com",
      spending_limit: { max_single_transaction: "500.00" },
    });
    const getPaymentSpy = vi
      .spyOn(paymentService, "getPayment")
      .mockResolvedValue({
        id: "ord_99",
        paypal_order_id: "PAYPAL_RETURN_123",
        amount: "299.00",
        currency: "USD",
        quantity: 1,
        merchant: "SoundGear",
        status: "APPROVED",
        allowed_actions: ["capture", "cancel"],
      });

    renderAtRoute("/checkout/success?token=PAYPAL_RETURN_123&PayerID=PAYER1");

    await waitFor(() => {
      expect(getPaymentSpy).toHaveBeenCalledWith("PAYPAL_RETURN_123", {
        sync: true,
      });
      expect(
        screen.getByText(/PayPal Authorization Confirmed/i)
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /Capture Verified Payment/i })
      ).toBeInTheDocument();
    });
  });

  it("defaults to commercial light theme and renders PayPilot brand logo", () => {
    expect(useAppStore.getState().theme).toBe("light");
    const { container } = render(<PayPilotLogo variant="full" surface="auto" />);
    expect(screen.getByText("PayPilot")).toBeInTheDocument();
    const img = container.querySelector('img[src="/logo.jpg"]');
    expect(img).toBeInTheDocument();
  });

  it("renders returned Channel3 USD products when currency preference is INR and never displays AVAILABLE on zero results", async () => {
    tokenVault.setTokens({
      accessToken: "valid_access_token",
      refreshToken: "valid_refresh_token",
    });
    vi.spyOn(authService, "getMe").mockResolvedValue({
      id: "user_1",
      name: "Alex Rivera",
      email: "alex@example.com",
      spending_limit: { currency: "INR", max_single_transaction: "50000.00" },
    });
    useAppStore.setState({
      aiPreferences: { preferredCurrency: "INR" },
    });

    const searchSpy = vi
      .spyOn(productService, "searchProducts")
      .mockResolvedValueOnce({
        query: "headphone",
        provider: "channel3",
        provider_status: "AVAILABLE",
        is_test_data: false,
        total: 1,
        products: [
          {
            id: "prod_kph7",
            external_product_id: "YSD8j4q",
            name: "KPH7 Headphone",
            price: "26.52",
            currency: "USD",
            merchant: "bestbuy.com",
            availability: "IN_STOCK",
            category: "Over-Ear Headphones",
            image_url: "https://cdn.trychannel3.com/sample.jpg",
            specifications: { brand: "Koss" },
          },
        ],
        message: null,
      })
      .mockResolvedValueOnce({
        query: "zzzzunknown",
        provider: "channel3",
        provider_status: "NO_RESULTS",
        is_test_data: false,
        total: 0,
        products: [],
        message: "No matching products found for 'zzzzunknown'.",
      });

    renderAtRoute("/products?query=headphone");

    expect(await screen.findByText("KPH7 Headphone")).toBeInTheDocument();
    expect(screen.getByText("bestbuy.com")).toBeInTheDocument();
    expect(screen.getByText("$26.52")).toBeInTheDocument();
    expect(screen.getAllByText("USD").length).toBeGreaterThanOrEqual(2);
    expect(searchSpy).toHaveBeenCalledWith(
      expect.objectContaining({ query: "headphone", currency: "INR" })
    );

    const searchInput = screen.getByPlaceholderText(/Search products by keyword/i);
    fireEvent.change(searchInput, { target: { value: "zzzzunknown" } });
    fireEvent.click(screen.getByRole("button", { name: /Search Products/i }));

    expect(
      await screen.findByText(/No products found for "zzzzunknown"/i)
    ).toBeInTheDocument();
    expect(screen.queryByText(/AVAILABLE/i)).not.toBeInTheDocument();
  });

  it("formats INR cleanly and displays converted INR + original USD merchant prices in Discovery and Comparison", async () => {
    expect(formatCurrency("2300.00", "INR")).toBe("₹2,300.00");
    expect(formatCurrency("26.52", "USD")).toBe("$26.52");

    const convInfo = getDisplayMoney({
      price: "26.52",
      currency: "USD",
      original_price: "26.52",
      original_currency: "USD",
      display_price: "2300.08",
      display_currency: "INR",
      exchange_rate: "86.730000",
    });
    expect(convInfo.hasConversion).toBe(true);
    expect(convInfo.displayCurrency).toBe("INR");
    expect(convInfo.originalCurrency).toBe("USD");

    tokenVault.setTokens({
      accessToken: "valid_access_token",
      refreshToken: "valid_refresh_token",
    });
    vi.spyOn(authService, "getMe").mockResolvedValue({
      id: "user_1",
      name: "Alex Rivera",
      email: "alex@example.com",
    });
    useAppStore.setState({
      aiPreferences: { preferredCurrency: "INR" },
    });

    vi.spyOn(productService, "searchProducts").mockResolvedValueOnce({
      query: "headphone",
      provider: "channel3",
      provider_status: "AVAILABLE",
      is_test_data: false,
      display_currency: "INR",
      exchange_rate: "86.730000",
      total: 1,
      products: [
        {
          id: "prod_kph7",
          external_product_id: "YSD8j4q",
          name: "KPH7 Headphone",
          price: "26.52",
          currency: "USD",
          original_price: "26.52",
          original_currency: "USD",
          display_price: "2300.08",
          display_currency: "INR",
          exchange_rate: "86.730000",
          merchant: "bestbuy.com",
          availability: "IN_STOCK",
          category: "Over-Ear Headphones",
          specifications: { brand: "Koss" },
        },
      ],
    });

    renderAtRoute("/products?query=headphone");

    expect(await screen.findByText("KPH7 Headphone")).toBeInTheDocument();
    expect(screen.getByText("₹2,300.08")).toBeInTheDocument();
    expect(screen.getByText(/Merchant: \$26\.52 USD/i)).toBeInTheDocument();

    // Comparison also shows converted INR alongside original merchant price
    render(
      <ProductComparison
        comparison={{
          currency: "INR",
          lowest_price: "2300.08",
          highest_price: "7360.00",
          average_price: "4830.04",
          price_spread: "5059.92",
          best_value_product_id: "prod_kph7",
          summary: "Compared 2 products in INR.",
          items: [
            {
              product_id: "prod_kph7",
              external_product_id: "YSD8j4q",
              name: "KPH7 Headphone",
              merchant: "bestbuy.com",
              price: "2300.08",
              currency: "INR",
              original_price: "26.52",
              original_currency: "USD",
              display_price: "2300.08",
              display_currency: "INR",
              availability: "IN_STOCK",
              price_delta_from_lowest: "0.00",
              price_delta_percent: "0.00",
              within_budget: true,
              requirement_match_score: "100.00",
              pros: [],
              cons: [],
              specifications: {},
            },
          ],
        }}
      />
    );
    expect(screen.getAllByText("₹2,300.08").length).toBeGreaterThanOrEqual(2);
  });

  it("shows original, display INR, and authoritative PayPal payable amount in PaymentApproval and blocks unreconciled quotes", () => {
    const product = {
      id: "prod_kph7",
      name: "KPH7 Headphone",
      price: "26.52",
      currency: "USD",
      merchant: "bestbuy.com",
      availability: "IN_STOCK",
    };

    const { rerender } = render(
      <PaymentApproval
        product={product}
        quantity={1}
        quote={{
          product_id: "prod_kph7",
          product_name: "KPH7 Headphone",
          merchant: "bestbuy.com",
          quantity: 1,
          original_unit_price: "26.52",
          original_amount: "26.52",
          original_currency: "USD",
          display_amount: "2300.08",
          display_currency: "INR",
          display_exchange_rate: "86.730000",
          payable_amount: "26.52",
          payable_currency: "USD",
          payment_conversion_required: false,
          can_checkout: true,
        }}
        onAuthorizeOrder={vi.fn()}
      />
    );

    expect(screen.getAllByText(/₹2,300\.08 INR/i).length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText(/\$26\.52 USD/i).length).toBeGreaterThanOrEqual(2);
    expect(
      screen.getByText(/PayPal executes this payment in USD/i)
    ).toBeInTheDocument();

    // When backend blocks conversion reconciliation, authorization must remain disabled
    rerender(
      <PaymentApproval
        product={product}
        quantity={1}
        quote={{
          product_id: "prod_kph7",
          product_name: "KPH7 Headphone",
          merchant: "bestbuy.com",
          quantity: 1,
          original_unit_price: "2000.00",
          original_amount: "2000.00",
          original_currency: "INR",
          display_amount: "2000.00",
          display_currency: "INR",
          display_exchange_rate: "1.000000",
          payable_amount: "2000.00",
          payable_currency: "USD",
          payment_conversion_required: true,
          can_checkout: false,
          blocking_reason: "Live exchange rate unavailable for INR -> USD.",
        }}
        onAuthorizeOrder={vi.fn()}
      />
    );

    expect(
      screen.getByText(/Live exchange rate unavailable for INR -> USD/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Authorize & Create PayPal Order/i })
    ).toBeDisabled();
  });

  it("displays India Sandbox merchant currency notice when order snapshot reports IN merchant", () => {
    render(
      <PayPalCheckout
        order={{
          id: "pay-in-1",
          paypal_order_id: "6RN28895VT836810M",
          status: "PENDING_APPROVAL",
          amount: "26.52",
          currency: "USD",
          original_amount: "26.52",
          original_currency: "USD",
          display_amount: "2493.94",
          display_currency: "INR",
          quantity: 1,
          merchant: "bestbuy.com",
          approval_status: "PAYER_ACTION_REQUIRED",
          approval_url: "https://www.sandbox.paypal.com/checkoutnow?token=6RN28895VT836810M",
          allowed_actions: ["cancel"],
          order_snapshot: {
            paypal_payee_merchant_id: "8KF3K9RFMJEGG",
            paypal_merchant_country: "IN",
          },
        }}
      />
    );

    expect(screen.getByText(/\$26\.52/i)).toBeInTheDocument();
    expect(screen.getByText(/Est\. display:/i)).toBeInTheDocument();
    expect(
      screen.getByText(/PayPal Sandbox Merchant Region Notice \(India \/ IN\)/i)
    ).toBeInTheDocument();
  });
});
