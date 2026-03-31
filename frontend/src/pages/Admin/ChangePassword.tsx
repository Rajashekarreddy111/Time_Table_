import { useState } from "react";

import { DashboardLayout } from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/PasswordInput";
import { Label } from "@/components/ui/label";
import { changeAdminPassword, changeAdminUsername } from "@/services/authService";
import { useAuth } from "@/hooks/useAuth";
import { toast } from "sonner";

export default function ChangePasswordPage() {
  const { user, setUser } = useAuth();
  const [currentUsernamePassword, setCurrentUsernamePassword] = useState("");
  const [newUsername, setNewUsername] = useState(user?.username ?? "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [savingUsername, setSavingUsername] = useState(false);

  const handleUsernameSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSavingUsername(true);
    try {
      const updatedUser = await changeAdminUsername(currentUsernamePassword, newUsername);
      setUser(updatedUser);
      setCurrentUsernamePassword("");
      toast.success("Username updated");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update username");
    } finally {
      setSavingUsername(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (newPassword !== confirmPassword) {
      toast.error("New password and confirmation do not match");
      return;
    }
    setSaving(true);
    try {
      await changeAdminPassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      toast.success("Password updated");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update password");
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="mx-auto max-w-2xl space-y-6">
        <section className="hero-shell">
          <div className="space-y-3">
            <div className="hero-chip">Admin Security</div>
            <h1 className="text-3xl font-bold tracking-tight text-foreground">Change Password</h1>
            <p className="text-sm leading-7 text-muted-foreground">Update your admin password securely. Coordinators do not have access to this page.</p>
          </div>
        </section>

        <section className="panel-card">
          <form className="space-y-4 border-b border-border/70 pb-6 mb-6" onSubmit={handleUsernameSubmit}>
            <div>
              <h2 className="text-lg font-semibold text-foreground">Change Username</h2>
              <p className="mt-1 text-sm text-muted-foreground">Update the admin username used for login. Coordinator ownership will follow the new admin username.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="newUsername">New Username</Label>
              <Input id="newUsername" value={newUsername} onChange={(event) => setNewUsername(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="currentUsernamePassword">Current Password</Label>
              <PasswordInput id="currentUsernamePassword" value={currentUsernamePassword} onChange={(event) => setCurrentUsernamePassword(event.target.value)} />
            </div>
            <Button type="submit" disabled={savingUsername}>
              {savingUsername ? "Updating..." : "Change Username"}
            </Button>
          </form>

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <h2 className="text-lg font-semibold text-foreground">Change Password</h2>
              <p className="mt-1 text-sm text-muted-foreground">Update your current admin password securely.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="currentPassword">Current Password</Label>
              <PasswordInput id="currentPassword" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="newPassword">New Password</Label>
              <PasswordInput id="newPassword" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirm New Password</Label>
              <PasswordInput id="confirmPassword" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
            </div>
            <Button type="submit" disabled={saving}>
              {saving ? "Updating..." : "Change Password"}
            </Button>
          </form>
        </section>
      </div>
    </DashboardLayout>
  );
}
