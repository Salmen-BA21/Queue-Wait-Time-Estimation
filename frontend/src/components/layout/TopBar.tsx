import { Search, Bell, LogOut } from "lucide-react";
import { useContext } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Badge } from "@/components/ui/badge";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { AuthContext } from "@/auth/AuthProvider";

export function TopBar() {
  const auth = useContext(AuthContext);
  const user = auth?.user ?? null;
  const logout = auth?.logout;
  const navigate = useNavigate();

  const initials = (user?.display_name || user?.email || "?")
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((segment) => segment[0]?.toUpperCase() ?? "")
    .join("") || "?";

  const handleLogout = async () => {
    if (logout) {
      await logout();
    }
    toast.success("Signed out.");
    navigate("/login", { replace: true });
  };

  return (
    <header className="flex h-14 items-center gap-4 border-b border-border bg-card/50 px-4">
      <SidebarTrigger className="text-muted-foreground hover:text-foreground" />

      <div className="relative flex-1 max-w-md">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search cameras, zones..."
          className="h-9 bg-background/50 border-border pl-9 text-sm placeholder:text-muted-foreground/60"
        />
      </div>

      <div className="ml-auto flex items-center gap-2">
        <Button variant="ghost" size="icon" className="relative text-muted-foreground hover:text-foreground">
          <Bell className="h-4 w-4" />
          <Badge className="absolute -right-0.5 -top-0.5 h-4 w-4 items-center justify-center p-0 text-[10px] bg-destructive text-destructive-foreground border-0">
            3
          </Badge>
        </Button>

        {user && (
          <div className="hidden text-right sm:block">
            <p className="text-xs font-medium text-foreground">{user.display_name}</p>
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{user.role}</p>
          </div>
        )}

        <div className="h-8 w-8 rounded-full bg-primary/20 border border-primary/30 flex items-center justify-center text-xs font-semibold text-primary">
          {initials}
        </div>

        <Button variant="outline" size="sm" onClick={() => void handleLogout()} disabled={!logout}>
          <LogOut className="h-3.5 w-3.5 mr-1" /> Sign out
        </Button>
      </div>
    </header>
  );
}
