import {
  GraduationCap,
  Calendar,
  Users,
  LayoutDashboard,
  Clock,
  FileText,
  KeyRound,
  LogOut,
  ShieldCheck,
  RotateCcw,
} from "lucide-react";
import { NavLink } from "@/components/NavLink";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarHeader,
  SidebarFooter,
  useSidebar,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useAuth } from "@/hooks/useAuth";
import { resetAllTimetables } from "@/services/apiClient";
import { useState } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const baseNavItems = [
  { title: "Dashboard", url: "/", icon: LayoutDashboard },
  { title: "Timetable Generator", url: "/generator", icon: Calendar },
  { title: "View Timetables", url: "/timetables", icon: GraduationCap },
  { title: "Faculty Workload", url: "/workload", icon: Clock },
  { title: "Generated Outputs", url: "/outputs", icon: FileText },
  { title: "Invisilation Finder", url: "/availability", icon: Users },
];

const adminNavItems = [
  { title: "Change Password", url: "/admin/change-password", icon: KeyRound },
  {
    title: "Manage Coordinators",
    url: "/admin/coordinators",
    icon: ShieldCheck,
  },
];

export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const { user, logout } = useAuth();
  const [isResetting, setIsResetting] = useState(false);
  const [showResetDialog, setShowResetDialog] = useState(false);
  const navItems =
    user?.role === "admin" ? [...baseNavItems, ...adminNavItems] : baseNavItems;

  const handleLogout = async () => {
    await logout();
    toast.success("Logged out successfully");
    window.location.href = "/login";
  };

  const handleReset = () => {
    setShowResetDialog(true);
  };

  const handleConfirmReset = async () => {
    setShowResetDialog(false);
    setIsResetting(true);
    try {
      const result = await resetAllTimetables();
      toast.success(
        `${result.message} (${result.deletedCount} timetables deleted)`,
      );
      window.location.reload();
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Failed to reset timetables";
      toast.error(message);
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="p-4 border-b border-sidebar-border">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-lg bg-sidebar-primary flex items-center justify-center flex-shrink-0">
            <GraduationCap className="h-5 w-5 text-sidebar-primary-foreground" />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <h2 className="text-sm font-bold text-sidebar-accent-foreground truncate">
                NEC Timetable
              </h2>
              <p className="text-xs text-sidebar-foreground truncate">
                Management System
              </p>
            </div>
          )}
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel className="text-xs uppercase tracking-widest text-sidebar-foreground/50">
            Navigation
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild>
                    <NavLink
                      to={item.url}
                      end={item.url === "/"}
                      className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
                      activeClassName="bg-sidebar-accent text-sidebar-primary font-medium"
                    >
                      <item.icon className="h-4 w-4 flex-shrink-0" />
                      {!collapsed && (
                        <span className="text-sm">{item.title}</span>
                      )}
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="p-3 border-t border-sidebar-border">
        {!collapsed && user && (
          <div className="mb-3 rounded-xl border border-sidebar-border px-3 py-2 text-xs">
            <div className="font-semibold text-sidebar-accent-foreground">
              {user.username}
            </div>
            <div className="mt-1 uppercase tracking-[0.14em] text-sidebar-foreground/60">
              {user.role}
            </div>
          </div>
        )}
        <Button
          variant="ghost"
          size={collapsed ? "icon" : "sm"}
          className="w-full text-sidebar-foreground gap-2 mb-2"
          onClick={() => void handleReset()}
          disabled={isResetting}
          title="Delete all timetables from the database"
        >
          <RotateCcw className="h-4 w-4 flex-shrink-0" />
          {!collapsed && (
            <span className="text-sm">
              {isResetting ? "Resetting..." : "Reset All"}
            </span>
          )}
        </Button>
        <Button
          variant="ghost"
          size={collapsed ? "icon" : "sm"}
          className="w-full text-sidebar-foreground gap-2"
          onClick={() => void handleLogout()}
        >
          <LogOut className="h-4 w-4 flex-shrink-0" />
          {!collapsed && <span className="text-sm">Logout</span>}
        </Button>
      </SidebarFooter>
      <AlertDialog open={showResetDialog} onOpenChange={setShowResetDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reset All Timetables</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete ALL timetables? This action cannot be undone and will permanently remove all generated timetables from the database.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmReset} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
              Delete All
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Sidebar>
  );
}
