import { Route, Routes } from "react-router-dom";
import Index from "@/pages/Dashboard/Index";
import TimetableGenerator from "@/pages/TimetableGenerator/TimetableGenerator";
import TimetableViewer from "@/pages/TimetableViewer/TimetableViewer";
import FacultyWorkload from "@/pages/FacultyWorkload/FacultyWorkload";
import FacultyAvailability from "@/pages/FacultyAvailability/FacultyAvailability";
import GeneratedOutputs from "@/pages/GeneratedOutputs/GeneratedOutputs";
import NotFound from "@/pages/NotFound/NotFound";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Index />} />
      <Route path="/generator" element={<TimetableGenerator />} />
      <Route path="/timetables" element={<TimetableViewer />} />
      <Route path="/workload" element={<FacultyWorkload />} />
      <Route path="/outputs" element={<GeneratedOutputs />} />
      <Route path="/availability" element={<FacultyAvailability />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
