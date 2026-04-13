import { AppLayout } from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useState, type FormEvent } from "react";
import { ShieldCheck, UserCog, KeyRound } from "lucide-react";
import { toast } from "sonner";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/useAuth";
import {
  createManager,
  listManagers,
  resetManagerPassword,
  updateManagerStatus,
} from "@/lib/api";

export default function SettingsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const isAdmin = user?.role === "admin";

  const [newManager, setNewManager] = useState({ email: "", display_name: "", password: "" });
  const [passwordByManagerId, setPasswordByManagerId] = useState<Record<number, string>>({});
  const [statusTargetManagerId, setStatusTargetManagerId] = useState<number | null>(null);
  const [resetTargetManagerId, setResetTargetManagerId] = useState<number | null>(null);

  const managersQuery = useQuery({
    queryKey: ["admin-managers"],
    queryFn: listManagers,
    enabled: isAdmin,
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

  if (!isAdmin) {
    return (
      <AppLayout>
        <div className="max-w-3xl space-y-2">
          <h1 className="text-2xl font-bold text-foreground">Manager Administration</h1>
          <p className="text-sm text-muted-foreground">Administrator access is required to manage manager accounts.</p>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="space-y-6 max-w-4xl">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Manager Administration</h1>
          <p className="text-sm text-muted-foreground">Create and maintain manager accounts used for operations.</p>
        </div>

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
      </div>
    </AppLayout>
  );
}
