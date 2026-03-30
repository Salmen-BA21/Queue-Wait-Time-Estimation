import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useState } from "react";
import { Save, Trash2, Plus, TestTube, Camera, Bell, Webhook, SlidersHorizontal } from "lucide-react";
import { toast } from "sonner";
import { useMutation, useQuery } from "@tanstack/react-query";

import { getWebhookIntegrationStatus, testWebhookIntegration } from "@/lib/api";

export default function SettingsPage() {
  const [thresholds, setThresholds] = useState({ maxWaitTime: 15, maxQueueSize: 20 });
  const [cameras, setCameras] = useState([
    { id: "1", name: "Entrance A", url: "rtsp://192.168.1.101/stream", enabled: true },
    { id: "2", name: "Entrance B", url: "rtsp://192.168.1.102/stream", enabled: true },
    { id: "3", name: "Checkout 1", url: "rtsp://192.168.1.103/stream", enabled: true },
    { id: "4", name: "Checkout 2", url: "rtsp://192.168.1.104/stream", enabled: false },
  ]);
  const [notifications, setNotifications] = useState({ email: true, push: false, webhook: true });

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
