import { useEffect, useState } from "react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { GraduationCap, Server } from "lucide-react";

import { getBackendHealth } from "@/services/apiClient";
import { useAuth } from "@/hooks/useAuth";

export function Navbar() {
  const [backendConnected, setBackendConnected] = useState<boolean | null>(null);
  const [backendDetail, setBackendDetail] = useState<string>("");
  const { user } = useAuth();

  useEffect(() => {
    let mounted = true;

    const checkBackend = async () => {
      try {
        const health = await getBackendHealth();
        if (!mounted) return;
        setBackendConnected(true);
        if (health.status === "degraded") {
          const dbErr = health.mongo_error;
          setBackendDetail(dbErr ? `DB Error: ${dbErr}` : `Backend reachable, DB: ${health.mongo ?? "unknown"}`);
        } else {
          setBackendDetail("Backend and DB connected");
        }
      } catch (err) {
        if (!mounted) return;
        setBackendConnected(false);
        setBackendDetail("Backend API not reachable");
      }
    };

    checkBackend();
    const intervalId = window.setInterval(checkBackend, 15000);

    return () => {
      mounted = false;
      window.clearInterval(intervalId);
    };
  }, []);

  const statusLabel =
    backendConnected === null
      ? "Checking backend..."
      : backendConnected
        ? backendDetail || "Backend connected"
        : "Backend disconnected";

  return (
    <header className="h-14 border-b border-border bg-card flex items-center px-4 gap-4 sticky top-0 z-30">
      <SidebarTrigger className="text-muted-foreground hover:text-foreground" />
      <div className="flex items-center gap-2">
        <GraduationCap className="h-5 w-5 text-primary" />
        <span className="font-semibold text-sm text-foreground">College Timetable Management</span>
      </div>
      <div className="ml-auto flex items-center gap-3">
        <div
          className="flex items-center gap-2 rounded-full border border-border px-3 py-1"
          title={statusLabel}
          aria-label={statusLabel}
        >
          <Server className="h-3.5 w-3.5 text-muted-foreground" />
          <span
            className={`h-2.5 w-2.5 rounded-full ${
              backendConnected === null
                ? "bg-amber-500"
                : backendConnected
                  ? "bg-emerald-500"
                  : "bg-red-500"
            }`}
          />
          <span className="text-xs text-muted-foreground hidden sm:inline">
            {backendConnected === null ? "Checking" : backendConnected ? "Connected" : "Offline"}
          </span>
        </div>
        <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center">
          <span className="text-[10px] font-semibold text-primary-foreground">{user?.username?.slice(0, 3).toUpperCase() ?? "NEC"}</span>
        </div>
      </div>
    </header>
  );
}
