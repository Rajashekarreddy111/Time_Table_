import { useState } from "react";
import { Navigate } from "react-router-dom";
import { Shield, Users } from "lucide-react";

import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/PasswordInput";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";

export default function LoginPage() {
  const { user, loading, login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"admin" | "coordinator">("admin");
  const [submitting, setSubmitting] = useState(false);

  if (!loading && user) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await login(username, password, role);
      toast.success("Login successful");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,rgba(14,165,233,0.10),transparent_40%),linear-gradient(180deg,#f8fafc,#eef2ff)] px-4 py-10">
      <div className="mx-auto grid max-w-5xl gap-8 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="hero-shell">
          <div className="space-y-5">
            <div className="hero-chip">Role Based Access</div>
            <div className="space-y-3">
              <h1 className="text-4xl font-bold tracking-tight text-foreground">Timetable Access Portal</h1>
              <p className="max-w-2xl text-sm leading-7 text-muted-foreground">
                Sign in as an admin to manage coordinators and passwords, or continue as a coordinator with restricted access to the scheduling workspace.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="panel-card">
                <Shield className="h-6 w-6 text-primary" />
                <h2 className="mt-4 text-lg font-semibold text-foreground">Admin</h2>
                <p className="mt-2 text-sm text-muted-foreground">Create coordinators, reset coordinator passwords, and change your own password.</p>
              </div>
              <div className="panel-card">
                <Users className="h-6 w-6 text-primary" />
                <h2 className="mt-4 text-lg font-semibold text-foreground">Coordinator</h2>
                <p className="mt-2 text-sm text-muted-foreground">Use the system with restricted access and without coordinator management controls.</p>
              </div>
            </div>
          </div>
        </section>

        <section className="panel-card">
          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <h2 className="text-2xl font-semibold text-foreground">Sign In</h2>
              <p className="mt-2 text-sm text-muted-foreground">Enter your credentials and choose the role you are signing in as.</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input id="username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Enter username" />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <PasswordInput id="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter password" />
            </div>

            <div className="space-y-3">
              <Label>Select role</Label>
              <div className="grid gap-3 sm:grid-cols-2">
                <button type="button" onClick={() => setRole("admin")} className={`rounded-2xl border p-4 text-left transition-colors ${role === "admin" ? "border-primary bg-primary/10" : "border-border bg-muted/20"}`}>
                  <div className="font-semibold text-foreground">Login as Admin</div>
                  <div className="mt-1 text-xs text-muted-foreground">Full coordinator management access</div>
                </button>
                <button type="button" onClick={() => setRole("coordinator")} className={`rounded-2xl border p-4 text-left transition-colors ${role === "coordinator" ? "border-primary bg-primary/10" : "border-border bg-muted/20"}`}>
                  <div className="font-semibold text-foreground">Login as Coordinator</div>
                  <div className="mt-1 text-xs text-muted-foreground">Restricted access to the app</div>
                </button>
              </div>
            </div>

            <Button type="submit" className="w-full" disabled={submitting}>
              {submitting ? "Signing in..." : "Login"}
            </Button>
          </form>
        </section>
      </div>
    </div>
  );
}
