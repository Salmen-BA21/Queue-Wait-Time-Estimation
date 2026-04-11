import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useState, type FormEvent } from "react";
import { Save, Trash2, Plus, TestTube, Camera, Bell, Webhook, SlidersHorizontal, ShieldCheck, UserCog, KeyRound } from "lucide-react";
import { toast } from "sonner";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/useAuth";
import {
  createManager,
  getWebhookIntegrationStatus,
  listManagers,
  resetManagerPassword,
  testWebhookIntegration,
  updateManagerStatus,
} from "@/lib/api";

export default function SettingsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const isAdmin = user?.role === "admin";

  const [thresholds, setThresholds] = useState({ maxWaitTime: 15, maxQueueSize: 20 });
  const [cameras, setCameras] = useState([
    { id: "1", name: "Entrance A", url: "rtsp://192.168.1.101/stream", enabled: true },
    { id: "2", name: "Entrance B", url: "rtsp://192.168.1.102/stream", enabled: true },
    { id: "3", name: "Checkout 1", url: "rtsp://192.168.1.103/stream", enabled: true },
    { id: "4", name: "Checkout 2", url: "rtsp://192.168.1.104/stream", enabled: false },
  ]);
  const [notifications, setNotifications] = useState({ email: true, push: false, webhook: true });
  const [newManager, setNewManager] = useState({ email: "", display_name: "", password: "" });
  const [passwordByManagerId, setPasswordByManagerId] = useState<Record<number, string>>({});
  const [statusTargetManagerId, setStatusTargetManagerId] = useState<number | null>(null);
  const [resetTargetManagerId, setResetTargetManagerId] = useState<number | null>(null);

  const managersQuery = useQuery({
    queryKey: ["admin-managers"],
    queryFn: listManagers,
    enabled: isAdmin,
  });

  const webhookStatusQuery = useQuery({
    queryKey: ["webhook-integration-status"],
    queryFn: getWebhookIntegrationStatus,
  });

  const testWebhookMutation = useMutation({
    mutationFn: testWebhookIntegration,
    onSuccess: (result) => {
      toast.success(result.message);
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Webhook test failed");
    },
  });

  const createManagerMutation = useMutation({
    mutationFn: createManager,
    onSuccess: (createdManager) => {
      toast.success(`Manager account created for ${createdManager.email}`);
      setNewManager({ email: "", display_name: "", password: "" });
      void queryClient.invalidateQueries({ queryKey: ["admin-managers"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Failed to create manager account");
    },
  });

  const updateManagerStatusMutation = useMutation({
    mutationFn: ({ managerId, isActive }: { managerId: number; isActive: boolean }) =>
      updateManagerStatus(managerId, { is_active: isActive }),
    onMutate: ({ managerId }) => {
      setStatusTargetManagerId(managerId);
    },
    onSuccess: (updatedManager) => {
      toast.success(`${updatedManager.display_name} is now ${updatedManager.is_active ? "active" : "inactive"}`);
      void queryClient.invalidateQueries({ queryKey: ["admin-managers"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Failed to update manager status");
    },
    onSettled: () => {
      setStatusTargetManagerId(null);
    },
  });

  const resetManagerPasswordMutation = useMutation({
    mutationFn: ({ managerId, password }: { managerId: number; password: string }) =>
      resetManagerPassword(managerId, { password }),
    onMutate: ({ managerId }) => {
      setResetTargetManagerId(managerId);
    },
    onSuccess: (_, variables) => {
      setPasswordByManagerId((previous) => ({ ...previous, [variables.managerId]: "" }));
      toast.success("Manager password reset.");
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Failed to reset manager password");
    },
    onSettled: () => {
      setResetTargetManagerId(null);
    },
  });

  const handleCreateManager = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!newManager.email.trim() || !newManager.display_name.trim() || !newManager.password.trim()) {
      toast.error("Email, display name, and password are required.");
      return;
    }

    createManagerMutation.mutate({
      email: newManager.email.trim(),
      display_name: newManager.display_name.trim(),
      password: newManager.password,
    });
  };

  const handleResetManagerPassword = (managerId: number) => {
    const password = passwordByManagerId[managerId]?.trim() || "";
    if (!password) {
      toast.error("Enter a new password before resetting.");
      return;
    }

    resetManagerPasswordMutation.mutate({ managerId, password });
  };

  const handleSave = () => toast.success("Settings saved successfully");

  return (
    <AppLayout>
      <div className="space-y-6 max-w-4xl">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Settings</h1>
          <p className="text-sm text-muted-foreground">Configure thresholds, webhooks, and system parameters</p>
        </div>

        {/* Thresholds */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <SlidersHorizontal className="h-4 w-4 text-primary" /> Thresholds
            </CardTitle>
            <CardDescription>Set alert trigger limits</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground">Max Wait Time (minutes)</Label>
              <Input
                type="number"
                value={thresholds.maxWaitTime}
                onChange={(e) => setThresholds((p) => ({ ...p, maxWaitTime: +e.target.value }))}
                className="bg-background border-border"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground">Max Queue Size</Label>
              <Input
                type="number"
                value={thresholds.maxQueueSize}
                onChange={(e) => setThresholds((p) => ({ ...p, maxQueueSize: +e.target.value }))}
                className="bg-background border-border"
              />
            </div>
          </CardContent>
        </Card>

        {/* Webhooks */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Webhook className="h-4 w-4 text-primary" /> Webhook Integration
            </CardTitle>
            <CardDescription>Connect to the backend-managed n8n webhook integration</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground">Configured Webhook URL</Label>
              <div className="flex gap-2">
                <Input
                  value={webhookStatusQuery.data?.webhook_url ?? "Loading backend configuration..."}
                  readOnly
                  className="bg-background border-border font-mono text-xs"
                />
                <Button variant="outline" size="sm" onClick={() => testWebhookMutation.mutate()} disabled={testWebhookMutation.isPending}>
                  <TestTube className="h-3 w-3 mr-1" /> {testWebhookMutation.isPending ? "Testing" : "Test"}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                {webhookStatusQuery.data?.webhook_enabled
                  ? "Webhook delivery is enabled in the backend."
                  : "Webhook delivery is disabled in the backend."}
                {webhookStatusQuery.data && (
                  <span>
                    {" "}
                    Shared secret {webhookStatusQuery.data.secret_configured ? "is configured" : "is missing"}.
                  </span>
                )}
              </p>
            </div>
          </CardContent>
        </Card>

        {isAdmin && (
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-primary" /> Manager Accounts
              </CardTitle>
              <CardDescription>Create, activate, deactivate, and reset manager credentials</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <form className="grid grid-cols-1 gap-3 sm:grid-cols-4" onSubmit={handleCreateManager}>
                <Input
                  type="email"
                  value={newManager.email}
                  onChange={(event) => setNewManager((previous) => ({ ...previous, email: event.target.value }))}
                  placeholder="manager@queuevision.local"
                />
                <Input
                  value={newManager.display_name}
                  onChange={(event) => setNewManager((previous) => ({ ...previous, display_name: event.target.value }))}
                  placeholder="Display name"
                />
                <Input
                  type="password"
                  value={newManager.password}
                  onChange={(event) => setNewManager((previous) => ({ ...previous, password: event.target.value }))}
                  placeholder="Temporary password"
                />
                <Button type="submit" disabled={createManagerMutation.isPending}>
                  <UserCog className="mr-1 h-3 w-3" />
                  {createManagerMutation.isPending ? "Creating..." : "Create Manager"}
                </Button>
              </form>

              <div className="space-y-3">
                {managersQuery.isLoading && <p className="text-sm text-muted-foreground">Loading manager accounts...</p>}
                {managersQuery.isError && <p className="text-sm text-destructive">Failed to load manager accounts.</p>}
                {!managersQuery.isLoading && !managersQuery.isError && (managersQuery.data?.length ?? 0) === 0 && (
                  <p className="text-sm text-muted-foreground">No manager accounts created yet.</p>
                )}

                {managersQuery.data?.map((manager) => (
                  <div key={manager.id} className="rounded-lg border border-border/60 bg-background/50 p-3 space-y-3">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <p className="text-sm font-medium text-foreground">{manager.display_name}</p>
                        <p className="text-xs font-mono text-muted-foreground">{manager.email}</p>
                      </div>
                      <p className={`text-xs font-medium ${manager.is_active ? "text-emerald-400" : "text-amber-400"}`}>
                        {manager.is_active ? "Active" : "Inactive"}
                      </p>
                    </div>

                    <div className="flex flex-col gap-2 sm:flex-row">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={statusTargetManagerId === manager.id}
                        onClick={() =>
                          updateManagerStatusMutation.mutate({
                            managerId: manager.id,
                            isActive: !manager.is_active,
                          })
                        }
                      >
                        {statusTargetManagerId === manager.id
                          ? "Updating..."
                          : manager.is_active
                            ? "Deactivate"
                            : "Activate"}
                      </Button>

                      <Input
                        type="password"
                        value={passwordByManagerId[manager.id] ?? ""}
                        onChange={(event) =>
                          setPasswordByManagerId((previous) => ({
                            ...previous,
                            [manager.id]: event.target.value,
                          }))
                        }
                        placeholder="New password"
                      />

                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={resetTargetManagerId === manager.id}
                        onClick={() => handleResetManagerPassword(manager.id)}
                      >
                        <KeyRound className="mr-1 h-3 w-3" />
                        {resetTargetManagerId === manager.id ? "Resetting..." : "Reset Password"}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Cameras */}
        <Card className="bg-card border-border">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                <Camera className="h-4 w-4 text-primary" /> Camera Management
              </CardTitle>
              <CardDescription>Manage connected camera feeds</CardDescription>
            </div>
            <Button size="sm" variant="outline">
              <Plus className="h-3 w-3 mr-1" /> Add Camera
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {cameras.map((cam) => (
              <div key={cam.id} className="flex items-center gap-3 rounded-lg border border-border/50 bg-background/50 p-3">
                <Switch
                  checked={cam.enabled}
                  onCheckedChange={(checked) =>
                    setCameras((prev) => prev.map((c) => (c.id === cam.id ? { ...c, enabled: checked } : c)))
                  }
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground">{cam.name}</p>
                  <p className="text-xs text-muted-foreground font-mono truncate">{cam.url}</p>
                </div>
                <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-destructive">
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Notifications */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Bell className="h-4 w-4 text-primary" /> Notification Preferences
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {Object.entries(notifications).map(([key, val]) => (
              <div key={key} className="flex items-center justify-between">
                <Label className="text-sm text-foreground capitalize">{key} Notifications</Label>
                <Switch
                  checked={val}
                  onCheckedChange={(checked) => setNotifications((p) => ({ ...p, [key]: checked }))}
                />
              </div>
            ))}
          </CardContent>
        </Card>

        <Separator className="bg-border" />

        <div className="flex justify-end">
          <Button onClick={handleSave} className="glow-cyan">
            <Save className="h-4 w-4 mr-1" /> Save All Settings
          </Button>
        </div>
      </div>
    </AppLayout>
  );
}
