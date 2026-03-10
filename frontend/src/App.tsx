import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import TimetableGenerator from "./pages/TimetableGenerator";
import TimetableViewer from "./pages/TimetableViewer";
import FacultyWorkload from "./pages/FacultyWorkload";
import FacultyAvailability from "./pages/FacultyAvailability";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Index />} />
          <Route path="/generator" element={<TimetableGenerator />} />
          <Route path="/timetables" element={<TimetableViewer />} />
          <Route path="/workload" element={<FacultyWorkload />} />
          <Route path="/availability" element={<FacultyAvailability />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
