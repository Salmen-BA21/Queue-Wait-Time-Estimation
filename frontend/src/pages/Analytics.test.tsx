import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  getAlertDistributionStatistics,
  getStatisticsOverview,
  getTimeBasedStatistics,
  getZoneStatistics,
} from "@/lib/api";

import Analytics from "./Analytics";

vi.mock("@/components/layout/AppLayout", () => ({
  AppLayout: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("recharts", () => {
  const MockContainer = ({ children }: { children?: ReactNode }) => <div>{children}</div>;
  return {
    ResponsiveContainer: MockContainer,
    LineChart: MockContainer,
    BarChart: MockContainer,
    PieChart: MockContainer,
    Pie: MockContainer,
    Cell: () => null,
    CartesianGrid: () => null,
    XAxis: () => null,
    YAxis: () => null,
    Tooltip: () => null,
    Legend: () => null,
    Line: () => null,
    Bar: () => null,
  };
});

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getStatisticsOverview: vi.fn(),
    getZoneStatistics: vi.fn(),
    getTimeBasedStatistics: vi.fn(),
    getAlertDistributionStatistics: vi.fn(),
  };
});

function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function renderAnalytics() {
  const queryClient = createQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <Analytics />
    </QueryClientProvider>,
  );
}

describe("Analytics", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(getStatisticsOverview).mockResolvedValue({
      date_range: {
        from_date: "2026-05-01",
        to_date: "2026-05-06",
      },
      avg_wait_time: 42.5,
      peak_queue_length: 21,
      stability_score: 84,
      total_alerts: 12,
      critical_alerts: 4,
      warning_alerts: 8,
      avg_people_in_zone: 8.4,
      avg_service_rate: 0.22,
      avg_arrival_rate: 0.18,
    });

    vi.mocked(getZoneStatistics).mockResolvedValue([
      {
        camera_id: "cam_01",
        zone_id: "checkout_lane_1",
        total_alerts: 6,
        avg_wait_time: 55.3,
        max_wait_time: 130,
        min_wait_time: 12,
        avg_people_in_zone: 9.1,
        peak_queue_length: 18,
        avg_service_rate: 0.2,
        stability_score: 78,
        critical_alerts: 2,
        warning_alerts: 4,
      },
    ]);

    vi.mocked(getTimeBasedStatistics).mockResolvedValue([
      {
        period: "2026-05-01",
        alert_count: 3,
        avg_wait_time: 40.0,
        peak_queue_length: 12,
        stability_score: 88,
        avg_service_rate: 0.21,
        avg_arrival_rate: 0.17,
      },
    ]);

    vi.mocked(getAlertDistributionStatistics).mockResolvedValue([
      {
        alert_type: "WAIT_TIME_WARNING",
        severity: "warning",
        count: 8,
        percentage: 66.67,
      },
      {
        alert_type: "WAIT_TIME_CRITICAL",
        severity: "critical",
        count: 4,
        percentage: 33.33,
      },
    ]);
  });

  it("renders live statistics data in KPIs and table", async () => {
    renderAnalytics();

    await screen.findByText("42.5s");

    expect(screen.getByText("Analytics")).toBeInTheDocument();
    expect(screen.getByText("21")).toBeInTheDocument();
    expect(screen.getByText("84%")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("cam_01")).toBeInTheDocument();
    expect(screen.getByText("checkout_lane_1")).toBeInTheDocument();
    expect(screen.getByText("WAIT_TIME_WARNING")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Export CSV/i })).toBeEnabled();

    expect(getStatisticsOverview).toHaveBeenCalledWith({ from: null, to: null });
    expect(getZoneStatistics).toHaveBeenCalledWith({ from: null, to: null });
    expect(getTimeBasedStatistics).toHaveBeenCalledWith("daily", { from: null, to: null });
    expect(getAlertDistributionStatistics).toHaveBeenCalledWith({ from: null, to: null });
  });

  it("shows an error banner when statistics loading fails", async () => {
    vi.mocked(getStatisticsOverview).mockRejectedValueOnce(new Error("overview failed"));

    renderAnalytics();

    expect(await screen.findByText("overview failed")).toBeInTheDocument();
  });

  it("exports CSV for current zone statistics", async () => {
    const originalCreateObjectURL = URL.createObjectURL;
    const originalRevokeObjectURL = URL.revokeObjectURL;

    if (!URL.createObjectURL) {
      Object.defineProperty(URL, "createObjectURL", {
        writable: true,
        value: vi.fn(),
      });
    }

    if (!URL.revokeObjectURL) {
      Object.defineProperty(URL, "revokeObjectURL", {
        writable: true,
        value: vi.fn(),
      });
    }

    const createObjectURLSpy = vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:mock");
    const revokeObjectURLSpy = vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
    const anchorClickSpy = vi.fn();
    const originalCreateElement = document.createElement.bind(document);
    const createElementSpy = vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
      if (tagName.toLowerCase() === "a") {
        return {
          click: anchorClickSpy,
          set href(_value: string) {},
          set download(_value: string) {},
        } as unknown as HTMLAnchorElement;
      }
      return originalCreateElement(tagName);
    });

    renderAnalytics();

    const exportButton = await screen.findByRole("button", { name: /Export CSV/i });
    fireEvent.click(exportButton);

    expect(createObjectURLSpy).toHaveBeenCalledTimes(1);
    expect(anchorClickSpy).toHaveBeenCalledTimes(1);
    expect(revokeObjectURLSpy).toHaveBeenCalledTimes(1);

    createElementSpy.mockRestore();
    createObjectURLSpy.mockRestore();
    revokeObjectURLSpy.mockRestore();

    if (!originalCreateObjectURL) {
      Object.defineProperty(URL, "createObjectURL", {
        writable: true,
        value: undefined,
      });
    }
    if (!originalRevokeObjectURL) {
      Object.defineProperty(URL, "revokeObjectURL", {
        writable: true,
        value: undefined,
      });
    }
  });
});
