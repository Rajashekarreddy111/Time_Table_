import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Download, FileText, LayoutGrid, Users } from "lucide-react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { TimetableGrid } from "@/components/TimetableGrid";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DISPLAY_DAYS } from "@/lib/timetableFormat";
import { ACADEMIC_METADATA, toAcademicYear } from "@/lib/academicMetadata";
import { listTimetables, type GeneratedWorkbookFile, type TimetableRecord } from "@/services/apiClient";
import { toast } from "sonner";

type FacultyScheduleEntry = {
  subject: string;
  year: string;
  section: string;
};

type FacultyWorkloadView = {
  name: string;
  schedule: Record<string, (FacultyScheduleEntry[] | null)[]>;
};

function toClassLine(year: string, section: string): string {
  const yearMap: Record<string, string> = {
    "1st Year": "I B.Tech",
    "2nd Year": "II B.Tech",
    "3rd Year": "III B.Tech",
    "4th Year": "IV B.Tech",
  };
  const normalized = yearMap[year] ?? year;
  return `${normalized} [CSE - ${section}] ${ACADEMIC_METADATA.SEMESTER}`;
}

function downloadGeneratedWorkbook(file: GeneratedWorkbookFile) {
  const binary = atob(file.contentBase64);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  const blob = new Blob([bytes], { type: file.contentType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = file.fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function buildFacultyWorkloads(record: TimetableRecord | null): FacultyWorkloadView[] {
  if (!record) return [];
  const mergedWorkloads: Record<string, Record<string, (FacultyScheduleEntry[] | null)[]>> = {};
  const grids = record.allGrids ?? { [record.section]: record.grid };

  const ensureFacultySchedule = (facultyName: string) => {
    if (!mergedWorkloads[facultyName]) {
      mergedWorkloads[facultyName] = {};
      for (const day of DISPLAY_DAYS) {
        mergedWorkloads[facultyName][day.full] = Array.from({ length: 7 }, () => null);
      }
    }
    return mergedWorkloads[facultyName];
  };

  for (const [section, grid] of Object.entries(grids)) {
    for (const day of DISPLAY_DAYS) {
      const cells = grid[day.full] ?? [];
      cells.forEach((cell, idx) => {
        if (!cell || idx >= 7) return;
        const facultyName = cell.facultyName ?? cell.faculty;
        const subjectName = cell.subjectName ?? cell.subject;
        if (!facultyName || !subjectName) return;

        const sections = cell.sharedSections?.length ? cell.sharedSections.join(",") : section;
        const entry: FacultyScheduleEntry = {
          subject: subjectName,
          year: record.year,
          section: sections,
        };

        const facultySchedule = ensureFacultySchedule(facultyName);
        if (!facultySchedule[day.full][idx]) {
          facultySchedule[day.full][idx] = [entry];
          return;
        }
        const existing = facultySchedule[day.full][idx];
        if (!existing) return;
        const duplicate = existing.some(
          (item) => item.subject === entry.subject && item.year === entry.year && item.section === entry.section,
        );
        if (!duplicate) {
          existing.push(entry);
        }
      });
    }
  }

  return Object.entries(mergedWorkloads)
    .map(([name, schedule]) => ({ name, schedule }))
    .sort((a, b) => a.name.localeCompare(b.name));
}

function WorkloadMiniTable({ workload }: { workload: FacultyWorkloadView }) {
  return (
    <div className="rounded-xl border border-border/70 bg-card overflow-x-auto">
      <div className="border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold">{workload.name}</h3>
      </div>
      <table className="min-w-[980px] w-full">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left text-xs px-3 py-2">Day</th>
            {Array.from({ length: 7 }, (_, index) => (
              <th key={index} className="text-left text-xs px-3 py-2">{index + 1}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {DISPLAY_DAYS.map((day) => (
            <tr key={day.full} className="border-b border-border/60 last:border-b-0">
              <td className="text-xs font-semibold px-3 py-2">{day.full}</td>
              {(workload.schedule[day.full] ?? []).map((entries, index) => (
                <td key={`${day.full}-${index}`} className="align-top px-3 py-2 text-xs">
                  {entries?.map((entry, entryIndex) => (
                    <div key={entryIndex} className="leading-relaxed">
                      <span className="font-medium">{entry.subject}</span>
                      <span className="text-muted-foreground"> [{entry.year} {entry.section}]</span>
                    </div>
                  )) ?? ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const GeneratedOutputs = () => {
  const [searchParams] = useSearchParams();
  const timetableId = searchParams.get("timetableId");
  const [records, setRecords] = useState<TimetableRecord[]>([]);
  const [selectedRecordId, setSelectedRecordId] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const response = await listTimetables();
        setRecords(response.items ?? []);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to load generated outputs");
      }
    };
    void load();
  }, []);

  useEffect(() => {
    if (!records.length) return;
    const matching = timetableId ? records.find((record) => record.id === timetableId) : null;
    if (matching) {
      setSelectedRecordId(matching.id);
      return;
    }
    if (!records.some((record) => record.id === selectedRecordId)) {
      setSelectedRecordId(records[0].id);
    }
  }, [records, selectedRecordId, timetableId]);

  const activeRecord = useMemo(
    () => records.find((record) => record.id === selectedRecordId) ?? null,
    [records, selectedRecordId],
  );

  const allGrids = activeRecord?.allGrids ?? (activeRecord ? { [activeRecord.section]: activeRecord.grid } : {});
  const sectionEntries = Object.entries(allGrids);
  const workloads = useMemo(() => buildFacultyWorkloads(activeRecord), [activeRecord]);

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="page-header">
          <h1>Generated Outputs</h1>
          <p>See all timetables, faculty workloads, shared class reports, and violation reports in one place</p>
        </div>

        <div className="bg-card rounded-xl p-6 shadow-sm border border-border/60">
          <div className="flex flex-wrap items-end gap-4">
            <div className="w-full md:w-[420px]">
              <Label className="text-xs text-muted-foreground">Generated Run</Label>
              <Select value={selectedRecordId} onValueChange={setSelectedRecordId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a generated run" />
                </SelectTrigger>
                <SelectContent>
                  {records.map((record) => (
                    <SelectItem key={record.id} value={record.id}>
                      {record.year} - {record.section} [{record.id}]
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {activeRecord?.generatedFiles?.sectionTimetables && (
              <Button variant="outline" size="sm" className="gap-1.5" onClick={() => downloadGeneratedWorkbook(activeRecord.generatedFiles!.sectionTimetables!)}>
                <Download className="h-3.5 w-3.5" /> All Timetables File
              </Button>
            )}
            {activeRecord?.generatedFiles?.facultyWorkload && (
              <Button variant="outline" size="sm" className="gap-1.5" onClick={() => downloadGeneratedWorkbook(activeRecord.generatedFiles!.facultyWorkload!)}>
                <Download className="h-3.5 w-3.5" /> Faculty Workload File
              </Button>
            )}
            {activeRecord?.generatedFiles?.sharedClassesReport && (
              <Button variant="outline" size="sm" className="gap-1.5" onClick={() => downloadGeneratedWorkbook(activeRecord.generatedFiles!.sharedClassesReport!)}>
                <Download className="h-3.5 w-3.5" /> Shared Class Report
              </Button>
            )}
            {activeRecord?.generatedFiles?.constraintViolationReport && (
              <Button variant="outline" size="sm" className="gap-1.5" onClick={() => downloadGeneratedWorkbook(activeRecord.generatedFiles!.constraintViolationReport!)}>
                <Download className="h-3.5 w-3.5" /> Constraint Report
              </Button>
            )}
          </div>
        </div>

        {activeRecord ? (
          <Tabs defaultValue="timetables" className="space-y-4">
            <TabsList className="flex flex-wrap h-auto">
              <TabsTrigger value="timetables" className="gap-1.5"><LayoutGrid className="h-4 w-4" /> All Timetables</TabsTrigger>
              <TabsTrigger value="workloads" className="gap-1.5"><Users className="h-4 w-4" /> Faculty Workloads</TabsTrigger>
              <TabsTrigger value="reports" className="gap-1.5"><FileText className="h-4 w-4" /> Reports</TabsTrigger>
            </TabsList>

            <TabsContent value="timetables" className="space-y-6">
              {sectionEntries.map(([section, grid]) => (
                <div key={section} className="bg-card rounded-xl p-6 shadow-sm">
                  <TimetableGrid
                    grid={grid}
                    header={{
                      college: ACADEMIC_METADATA.COLLEGE_NAME,
                      department: ACADEMIC_METADATA.DEPARTMENT_NAME,
                      year: toAcademicYear(new Date()),
                      semester: ACADEMIC_METADATA.SEMESTER,
                      section: toClassLine(activeRecord.year, section),
                      room: section,
                    }}
                  />
                </div>
              ))}
            </TabsContent>

            <TabsContent value="workloads" className="space-y-6">
              {workloads.length ? (
                workloads.map((workload) => <WorkloadMiniTable key={workload.name} workload={workload} />)
              ) : (
                <div className="bg-card rounded-xl p-6 shadow-sm text-sm text-muted-foreground">No faculty workloads available.</div>
              )}
            </TabsContent>

            <TabsContent value="reports" className="space-y-6">
              <div className="bg-card rounded-xl p-6 shadow-sm">
                <h2 className="text-base font-semibold mb-4">Shared Class Report</h2>
                {activeRecord.sharedClasses?.length ? (
                  <div className="overflow-x-auto">
                    <table className="min-w-full">
                      <thead>
                        <tr className="border-b border-border">
                          <th className="text-left text-xs px-3 py-2">Year</th>
                          <th className="text-left text-xs px-3 py-2">Subject</th>
                          <th className="text-left text-xs px-3 py-2">Faculty</th>
                          <th className="text-left text-xs px-3 py-2">Sections</th>
                          <th className="text-left text-xs px-3 py-2">Day</th>
                          <th className="text-left text-xs px-3 py-2">Periods</th>
                        </tr>
                      </thead>
                      <tbody>
                        {activeRecord.sharedClasses.map((item, index) => (
                          <tr key={`${item.subject_id}-${item.day}-${index}`} className="border-b border-border/60 last:border-b-0">
                            <td className="px-3 py-2 text-sm">{item.year}</td>
                            <td className="px-3 py-2 text-sm">{item.subject_name ?? item.subject_id}</td>
                            <td className="px-3 py-2 text-sm">{item.faculty_name ?? item.faculty_id}</td>
                            <td className="px-3 py-2 text-sm">{item.sections.join(", ")}</td>
                            <td className="px-3 py-2 text-sm">{item.day}</td>
                            <td className="px-3 py-2 text-sm">{item.periods.join(", ")}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No shared classes detected for this generated run.</p>
                )}
              </div>

              <div className="bg-card rounded-xl p-6 shadow-sm">
                <h2 className="text-base font-semibold mb-4">Constraint Violation Report</h2>
                {activeRecord.constraintViolations?.length || activeRecord.unscheduledSubjects?.length ? (
                  <div className="space-y-6">
                    {Boolean(activeRecord.constraintViolations?.length) && (
                      <div className="overflow-x-auto">
                        <table className="min-w-full">
                          <thead>
                            <tr className="border-b border-border">
                              <th className="text-left text-xs px-3 py-2">Year</th>
                              <th className="text-left text-xs px-3 py-2">Sections</th>
                              <th className="text-left text-xs px-3 py-2">Subject</th>
                              <th className="text-left text-xs px-3 py-2">Faculty</th>
                              <th className="text-left text-xs px-3 py-2">Constraint</th>
                              <th className="text-left text-xs px-3 py-2">Detail</th>
                            </tr>
                          </thead>
                          <tbody>
                            {activeRecord.constraintViolations?.map((item, index) => (
                              <tr key={`${item.subject_id}-${item.constraint}-${index}`} className="border-b border-border/60 last:border-b-0">
                                <td className="px-3 py-2 text-sm">{item.year}</td>
                                <td className="px-3 py-2 text-sm">{item.sections.join(", ")}</td>
                                <td className="px-3 py-2 text-sm">{item.subject_name ?? item.subject_id}</td>
                                <td className="px-3 py-2 text-sm">{item.faculty_name ?? item.faculty_id}</td>
                                <td className="px-3 py-2 text-sm">{item.constraint}</td>
                                <td className="px-3 py-2 text-sm">{item.detail}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                    {Boolean(activeRecord.unscheduledSubjects?.length) && (
                      <div>
                        <h3 className="text-sm font-semibold mb-3">Unscheduled Subjects</h3>
                        <div className="overflow-x-auto">
                          <table className="min-w-full">
                            <thead>
                              <tr className="border-b border-border">
                                <th className="text-left text-xs px-3 py-2">Year</th>
                                <th className="text-left text-xs px-3 py-2">Sections</th>
                                <th className="text-left text-xs px-3 py-2">Subject</th>
                                <th className="text-left text-xs px-3 py-2">Faculty</th>
                                <th className="text-left text-xs px-3 py-2">Detail</th>
                              </tr>
                            </thead>
                            <tbody>
                              {activeRecord.unscheduledSubjects?.map((item, index) => (
                                <tr key={`${item.subject_id}-unscheduled-${index}`} className="border-b border-border/60 last:border-b-0">
                                  <td className="px-3 py-2 text-sm">{item.year}</td>
                                  <td className="px-3 py-2 text-sm">{item.sections.join(", ")}</td>
                                  <td className="px-3 py-2 text-sm">{item.subject_name ?? item.subject_id}</td>
                                  <td className="px-3 py-2 text-sm">{item.faculty_name ?? item.faculty_id}</td>
                                  <td className="px-3 py-2 text-sm">{item.detail}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No constraint violations for this generated run.</p>
                )}
              </div>
            </TabsContent>
          </Tabs>
        ) : (
          <div className="bg-card rounded-xl p-6 shadow-sm text-sm text-muted-foreground">No generated outputs available.</div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default GeneratedOutputs;
