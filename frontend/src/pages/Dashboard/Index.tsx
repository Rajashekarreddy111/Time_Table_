import { useEffect, useMemo, useState } from "react";
import { Calendar, Users, GraduationCap, Clock, ArrowRight, FileText } from "lucide-react";
import { Link } from "react-router-dom";
import { DashboardLayout } from "@/components/DashboardLayout";
import { listTimetables, type TimetableRecord } from "@/services/apiClient";
import { getAllSectionKeys, readAcademicConfig } from "@/lib/academicConfig";
import { PERIODS } from "@/data/mockData";
import { DISPLAY_DAYS } from "@/lib/timetableFormat";
import { ACADEMIC_METADATA } from "@/lib/academicMetadata";

const quickLinks = [
  { title: "Generate Timetable", desc: "Create new timetable with constraints", url: "/generator", icon: Calendar },
  { title: "View Timetables", desc: "Browse generated timetables", url: "/timetables", icon: GraduationCap },
  { title: "Faculty Workload", desc: "View faculty schedules", url: "/workload", icon: Clock },
  { title: "Generated Outputs", desc: "Open shared and violation reports", url: "/outputs", icon: FileText },
  { title: "Find Availability", desc: "Find free faculty for a period", url: "/availability", icon: Users },
];

const Dashboard = () => {
  const [records, setRecords] = useState<TimetableRecord[]>([]);

  useEffect(() => {
    const load = async () => {
      try {
        const response = await listTimetables();
        setRecords(response.items ?? []);
      } catch {
        setRecords([]);
      }
    };
    void load();
  }, []);

  const stats = useMemo(() => {
    const config = readAcademicConfig();
    const totalSections = getAllSectionKeys(config).length;
    const timetableCount = records.length;
    const allFaculty = new Set<string>();
    let totalAssignments = 0;
    
    records.forEach(r => {
      const grids = r.allGrids ?? { [r.section]: r.grid };
      Object.values(grids).forEach((grid) => {
        Object.values(grid).forEach((daySlots) => {
          daySlots.forEach((slot) => {
            if (!slot) return;
            totalAssignments++;
            const facultyName = slot.facultyName ?? slot.faculty;
            if (facultyName) {
              allFaculty.add(facultyName);
            }
          });
        });
      });
    });

    return [
      { label: "Total Sections", value: totalSections, icon: GraduationCap, color: "text-primary" },
      { label: "Faculty Members", value: allFaculty.size || "-", icon: Users, color: "text-accent" },
      { label: "Timetables Generated", value: timetableCount, icon: Calendar, color: "text-success" },
      { label: "Total Assignments", value: totalAssignments, icon: Clock, color: "text-warning" },
    ];
  }, [records]);

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Welcome to {ACADEMIC_METADATA.COLLEGE_NAME} - Timetable Management System</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map((s) => (
          <div key={s.label} className="stat-card flex items-center gap-4">
            <div className={`h-12 w-12 rounded-xl bg-muted flex items-center justify-center ${s.color}`}>
              <s.icon className="h-6 w-6" />
            </div>
            <div>
              <p className="text-2xl font-bold text-foreground">{s.value}</p>
              <p className="text-xs text-muted-foreground">{s.label}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
        <div className="lg:col-span-2 space-y-6">
          <div className="page-header">
            <h2 className="text-lg font-semibold text-foreground">Section Coverage</h2>
            <p className="text-xs text-muted-foreground mt-1">Percentage of required periods assigned for each year</p>
          </div>
          
          <div className="bg-card rounded-xl p-6 shadow-sm space-y-6">
            {["2nd Year", "3rd Year", "4th Year"].map(year => {
              const yearRecords = records.filter(r => r.year === year);
              const sectionKeys = getAllSectionKeys(readAcademicConfig()).filter(k => k.year === year);
              const totalPossible = sectionKeys.length * 6 * 7; // Approx 42 periods per section
              const assigned = yearRecords.reduce((acc, r) => {
                let count = 0;
                if (r.grid) Object.values(r.grid).forEach(day => day.forEach(s => { if(s) count++ }));
                return acc + count;
              }, 0);
              const percentage = totalPossible > 0 ? Math.min(100, Math.round((assigned / totalPossible) * 100)) : 0;
              
              return (
                <div key={year} className="space-y-2">
                  <div className="flex justify-between text-xs font-semibold">
                    <span className="text-foreground">{year}</span>
                    <span className="text-primary">{percentage}%</span>
                  </div>
                  <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-primary transition-all duration-1000 ease-out" 
                      style={{ width: `${percentage}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="space-y-6">
          <div className="page-header">
            <h2 className="text-lg font-semibold text-foreground">Recent Activity</h2>
          </div>
          <div className="bg-card rounded-xl p-4 shadow-sm space-y-4">
            {records.slice(0, 3).length > 0 ? records.slice(0, 3).map((r, i) => (
              <div key={r.id} className="flex items-center gap-3 pb-3 border-b border-border last:border-0 last:pb-0">
                <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center text-primary text-[10px] font-bold">
                  {i + 1}
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-semibold text-foreground truncate">{r.year} - {r.section || "Multi"}</p>
                  <p className="text-[10px] text-muted-foreground">Generated recently</p>
                </div>
                <Link to={`/timetables?timetableId=${r.id}`} className="ml-auto">
                   <ArrowRight className="h-3.5 w-3.5 text-muted-foreground hover:text-primary transition-colors" />
                </Link>
              </div>
            )) : (
              <p className="text-xs text-center py-4 text-muted-foreground">No recent activity</p>
            )}
          </div>
        </div>
      </div>

      <div className="page-header">
        <h2 className="text-lg font-semibold text-foreground">Quick Actions</h2>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {quickLinks.map((link) => (
          <Link key={link.url} to={link.url} className="stat-card group flex items-start gap-4 cursor-pointer">
            <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary flex-shrink-0">
              <link.icon className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                {link.title}
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">{link.desc}</p>
            </div>
            <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors mt-1" />
          </Link>
        ))}
      </div>
    </DashboardLayout>
  );
};

export default Dashboard;
