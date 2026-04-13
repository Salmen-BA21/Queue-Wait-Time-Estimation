import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useAuth } from "@/auth/useAuth";
import { createManager, listManagers, resetManagerPassword, updateManagerStatus } from "@/lib/api";

import SettingsPage from "./SettingsPage";

vi.mock("@/components/layout/AppLayout", () => ({
  AppLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/auth/useAuth", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  createManager: vi.fn(),
  listManagers: vi.fn(),
  resetManagerPassword: vi.fn(),
  updateManagerStatus: vi.fn(),
}));

const adminUser = {
  id: 1,
  email: "admin@queuevision.local",
  display_name: "Platform Admin",
  role: "admin" as const,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  last_login_at: null,
};

const managerUser = {
  id: 2,
  email: "manager@queuevision.local",
  display_name: "Operations Manager",
  role: "manager" as const,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  last_login_at: null,
};

function renderSettingsPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <SettingsPage />
    </QueryClientProvider>,
  );
}

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(useAuth).mockReturnValue({
      user: adminUser,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    vi.mocked(listManagers).mockResolvedValue([managerUser]);
    vi.mocked(createManager).mockResolvedValue(managerUser);
    vi.mocked(updateManagerStatus).mockResolvedValue(managerUser);
    vi.mocked(resetManagerPassword).mockResolvedValue({ password_reset: true });
  });

  it("renders only manager CRUD controls for admins", async () => {
    renderSettingsPage();

    await screen.findByText("Operations Manager");

    expect(screen.getByText("Manager Administration")).toBeInTheDocument();
    expect(screen.getByText("Manager Accounts")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Manager" })).toBeInTheDocument();
    expect(screen.queryByText("Thresholds")).not.toBeInTheDocument();
    expect(screen.queryByText("Camera Management")).not.toBeInTheDocument();
    expect(screen.queryByText("Notification Preferences")).not.toBeInTheDocument();
    expect(screen.queryByText("Webhook Integration")).not.toBeInTheDocument();
    expect(screen.queryByText("Save All Settings")).not.toBeInTheDocument();
  });

  it("shows an access message when the current user is not an admin", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: managerUser,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    renderSettingsPage();

    expect(screen.getByText("Manager Administration")).toBeInTheDocument();
    expect(screen.getByText("Administrator access is required to manage manager accounts.")).toBeInTheDocument();
  });
});
