import { Navigate, Outlet, Route, Routes } from "react-router-dom";
import Index from "@/pages/Dashboard/Index";
import TimetableGenerator from "@/pages/TimetableGenerator/TimetableGenerator";
import TimetableViewer from "@/pages/TimetableViewer/TimetableViewer";
import FacultyWorkload from "@/pages/FacultyWorkload/FacultyWorkload";
import FacultyAvailability from "@/pages/FacultyAvailability/FacultyAvailability";
import GeneratedOutputs from "@/pages/GeneratedOutputs/GeneratedOutputs";
import NotFound from "@/pages/NotFound/NotFound";
import LoginPage from "@/pages/Auth/Login";
import ChangePasswordPage from "@/pages/Admin/ChangePassword";
import CoordinatorManagementPage from "@/pages/Admin/CoordinatorManagement";
import { useAuth } from "@/hooks/useAuth";

function RequireAuth() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center text-sm text-muted-foreground">Loading session...</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}

function RequireAdmin() {
  const { user } = useAuth();

  if (user?.role !== "admin") {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/" element={<Index />} />
        <Route path="/generator" element={<TimetableGenerator />} />
        <Route path="/timetables" element={<TimetableViewer />} />
        <Route path="/workload" element={<FacultyWorkload />} />
        <Route path="/outputs" element={<GeneratedOutputs />} />
        <Route path="/availability" element={<FacultyAvailability />} />
        <Route element={<RequireAdmin />}>
          <Route path="/admin/change-password" element={<ChangePasswordPage />} />
          <Route path="/admin/coordinators" element={<CoordinatorManagementPage />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
