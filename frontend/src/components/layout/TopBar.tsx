import { Search, Bell } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Badge } from "@/components/ui/badge";

export function TopBar() {
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
        <div className="h-8 w-8 rounded-full bg-primary/20 border border-primary/30 flex items-center justify-center text-xs font-semibold text-primary">
          OP
        </div>
      </div>
    </header>
  );
}
