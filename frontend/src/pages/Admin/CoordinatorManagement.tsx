import { useEffect, useState } from "react";

import { DashboardLayout } from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/PasswordInput";
import { Label } from "@/components/ui/label";
import {
  createCoordinator,
  deleteCoordinator,
  listCoordinators,
  updateCoordinatorPassword,
  type AuthUser,
} from "@/services/authService";
import { toast } from "sonner";

export default function CoordinatorManagementPage() {
  const [coordinators, setCoordinators] = useState<AuthUser[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [passwordDrafts, setPasswordDrafts] = useState<Record<string, string>>({});

  const loadCoordinators = async () => {
    setLoading(true);
    try {
      const items = await listCoordinators();
      setCoordinators(items);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to load coordinators");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadCoordinators();
  }, []);

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await createCoordinator(username, password);
      setUsername("");
      setPassword("");
      toast.success("Coordinator created");
      await loadCoordinators();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create coordinator");
    } finally {
      setSubmitting(false);
    }
  };

  const handleResetPassword = async (targetUsername: string) => {
    const draft = passwordDrafts[targetUsername]?.trim();
    if (!draft) {
      toast.error("Enter a new password first");
      return;
    }
    try {
      await updateCoordinatorPassword(targetUsername, draft);
      setPasswordDrafts((previous) => ({ ...previous, [targetUsername]: "" }));
      toast.success(`Password updated for ${targetUsername}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update password");
    }
  };

  const handleDelete = async (targetUsername: string) => {
    try {
      await deleteCoordinator(targetUsername);
      toast.success(`Deleted ${targetUsername}`);
      await loadCoordinators();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to delete coordinator");
    }
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <section className="hero-shell">
          <div className="space-y-3">
            <div className="hero-chip">Admin Controls</div>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">Coordinator Management</h1>
            <p className="text-sm leading-7 text-muted-foreground">Create coordinators, review the coordinators you created, reset their passwords, and remove accounts when needed.</p>
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
          <div className="panel-card">
            <h2 className="text-lg font-semibold text-foreground">Add Coordinator</h2>
            <form className="mt-5 space-y-4" onSubmit={handleCreate}>
              <div className="space-y-2">
                <Label htmlFor="newCoordinatorUsername">Username</Label>
                <Input id="newCoordinatorUsername" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Coordinator username" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="newCoordinatorPassword">Password</Label>
                <PasswordInput id="newCoordinatorPassword" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Minimum 6 characters" />
              </div>
              <Button type="submit" disabled={submitting}>
                {submitting ? "Creating..." : "Add Coordinator"}
              </Button>
            </form>
          </div>

          <div className="panel-card">
            <h2 className="text-lg font-semibold text-foreground">Your Coordinators</h2>
            {loading ? (
              <p className="mt-4 text-sm text-muted-foreground">Loading coordinators...</p>
            ) : coordinators.length === 0 ? (
              <p className="mt-4 text-sm text-muted-foreground">No coordinators created yet.</p>
            ) : (
              <div className="mt-5 space-y-4">
                {coordinators.map((coordinator) => (
                  <div key={coordinator.username} className="rounded-2xl border border-border/70 bg-muted/20 p-4">
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                      <div>
                        <div className="text-base font-semibold text-foreground">{coordinator.username}</div>
                        <div className="mt-1 text-xs uppercase tracking-[0.14em] text-muted-foreground">{coordinator.role}</div>
                      </div>
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                        <div className="min-w-56 space-y-2">
                          <Label className="text-xs text-muted-foreground">Reset Password</Label>
                          <PasswordInput
                            value={passwordDrafts[coordinator.username] ?? ""}
                            onChange={(event) =>
                              setPasswordDrafts((previous) => ({
                                ...previous,
                                [coordinator.username]: event.target.value,
                              }))
                            }
                            placeholder="New password"
                          />
                        </div>
                        <Button variant="outline" onClick={() => void handleResetPassword(coordinator.username)}>
                          Update Password
                        </Button>
                        <Button variant="destructive" onClick={() => void handleDelete(coordinator.username)}>
                          Delete
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </div>
    </DashboardLayout>
  );
}
