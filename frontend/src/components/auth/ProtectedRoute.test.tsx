import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AuthUser } from "@/lib/api";
import { useAuth } from "@/auth/useAuth";

import { ProtectedRoute } from "./ProtectedRoute";

vi.mock("@/auth/useAuth", () => ({
  useAuth: vi.fn(),
}));

const adminUser: AuthUser = {
  id: 1,
  email: "admin@queuevision.local",
  display_name: "Admin User",
  role: "admin",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  last_login_at: null,
};

const managerUser: AuthUser = {
  id: 2,
  email: "manager@queuevision.local",
  display_name: "Manager User",
  role: "manager",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  last_login_at: null,
};

function mockAuthUser(user: AuthUser | null, isLoading = false) {
  vi.mocked(useAuth).mockReturnValue({
    user,
    isLoading,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refresh: vi.fn(),
  });
}

function renderProtectedRoutes(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route
          path="/dashboard"
          element={(
            <ProtectedRoute allowedRoles={["manager"]}>
              <div>Manager Dashboard</div>
            </ProtectedRoute>
          )}
        />
        <Route
          path="/admin/managers"
          element={(
            <ProtectedRoute allowedRoles={["admin"]}>
              <div>Admin Managers Console</div>
            </ProtectedRoute>
          )}
        />
        <Route path="/login" element={<div>Login Page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects managers away from admin managers route", async () => {
    mockAuthUser(managerUser);

    renderProtectedRoutes("/admin/managers");

    await waitFor(() => {
      expect(screen.getByText("Manager Dashboard")).toBeInTheDocument();
    });
  });

  it("redirects admins away from manager-only routes to /admin/managers", async () => {
    mockAuthUser(adminUser);

    renderProtectedRoutes("/dashboard");

    await waitFor(() => {
      expect(screen.getByText("Admin Managers Console")).toBeInTheDocument();
    });
  });

  it("redirects unauthenticated users to login", async () => {
    mockAuthUser(null);

    renderProtectedRoutes("/admin/managers");

    await waitFor(() => {
      expect(screen.getByText("Login Page")).toBeInTheDocument();
    });
  });
});
