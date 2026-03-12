import { useEffect, useMemo, useState } from "react";
import { Download } from "lucide-react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import * as XLSX from "xlsx";
import { toast } from "sonner";
import { DISPLAY_DAYS } from "@/lib/timetableFormat";
import { listTimetables, type TimetableRecord } from "@/services/apiClient";
import { ACADEMIC_METADATA, toAcademicYear } from "@/lib/academicMetadata";

type FacultyScheduleEntry = {
  subject: string;
  year: string;
  section: string;
};

type FacultyWorkloadType = {
  name: string;
  schedule: Record<string, (FacultyScheduleEntry[] | null)[]>;
};

const TOTAL_COLUMNS = 10;

function subjectCode(subject: string): string {
  const words = subject.replace(/[^A-Za-z0-9 ]/g, " ").trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "SUB";
  if (words.length === 1) {
    const word = words[0].toUpperCase();
    return word.length <= 4 ? word : word.slice(0, 4);
  }
  return words.map((word) => word[0].toUpperCase()).join("").slice(0, 5);
}

function entryCode(entry: FacultyScheduleEntry): string {
  const yearShort = entry.year.replace(/[^0-9]/g, "") || entry.year;
  return `${yearShort}${entry.section}-${subjectCode(entry.subject)}`;
}

function padRow(values: string[]): string[] {
  if (values.length >= TOTAL_COLUMNS) return values.slice(0, TOTAL_COLUMNS);
  return [...values, ...Array.from({ length: TOTAL_COLUMNS - values.length }, () => "")];
}

function getWorkloadLegend(schedule: Record<string, (FacultyScheduleEntry[] | null)[]>) {
  const byKey = new Map<string, { code: string; label: string }>();
  for (const day of DISPLAY_DAYS) {
    for (const entries of schedule[day.full] ?? []) {
      if (!entries) continue;
      for (const entry of entries) {
        const key = `${entry.year}|${entry.section}|${entry.subject}`;
        if (byKey.has(key)) continue;
        byKey.set(key, {
          code: entryCode(entry),
          label: `${entry.year} ${entry.section} - ${entry.subject}`,
        });
      }
    }
  }
  return Array.from(byKey.values()).sort((a, b) => a.code.localeCompare(b.code));
}

function buildWorkloadWorksheet(workload: FacultyWorkloadType) {
  const legend = getWorkloadLegend(workload.schedule);
  const data: string[][] = [];

  data.push(padRow([ACADEMIC_METADATA.COLLEGE_NAME]));
  data.push(padRow(["(AUTONOMOUS)"]));
  data.push(padRow([ACADEMIC_METADATA.DEPARTMENT_NAME]));
  data.push(padRow([`ACADEMIC YEAR : ${toAcademicYear(new Date())} ${ACADEMIC_METADATA.SEMESTER}`]));
  data.push(padRow([`FACULTY WORKLOAD : ${workload.name}`]));
  data.push(padRow(["Room No :", "", "", "", "", `With effect from : ${ACADEMIC_METADATA.EFFECTIVE_DATE}`]));

  const tableHeaderRow = data.length;
  data.push(padRow(["DAY", "1", "2", "", "3", "4", "", "5", "6", "7"]));
  data.push(padRow(["", "9.10-10.00", "10.00-10.50", "10.50-11.00", "11.00-11.50", "11.50-12.40", "12.40-1.30", "1.30-2.20", "2.20-3.10", "3.10-4.00"]));

  const dayStartRow = data.length;
  DISPLAY_DAYS.forEach((day, dayIdx) => {
    const dayEntries = workload.schedule[day.full] ?? [];
    const getCode = (entries: FacultyScheduleEntry[] | null | undefined) => {
      if (!entries || entries.length === 0) return "";
      return entries.map(entryCode).join(" | ");
    };

    data.push(
      padRow([
        day.shortVertical,
        getCode(dayEntries[0]),
        getCode(dayEntries[1]),
        dayIdx === 0 ? "BREAK" : "",
        getCode(dayEntries[2]),
        getCode(dayEntries[3]),
        dayIdx === 0 ? "LUNCH" : "",
        getCode(dayEntries[4]),
        getCode(dayEntries[5]),
        getCode(dayEntries[6]),
      ]),
    );
  });

  data.push(padRow([""]));
  const legendStart = data.length;
  for (let idx = 0; idx < legend.length; idx += 2) {
    const left = legend[idx];
    const right = legend[idx + 1];
    data.push(padRow([
      left ? `${left.code} : ${left.label}` : "",
      "", "", "", "",
      right ? `${right.code} : ${right.label}` : "",
      "", "", "", "",
    ]));
  }

  data.push(padRow([""]));
  data.push(padRow(["HEAD OF THE DEPARTMENT", "", "", "", "", "PRINCIPAL"]));

  const ws = XLSX.utils.aoa_to_sheet(data);
  ws["!cols"] = [
    { wch: 7 }, { wch: 12 }, { wch: 12 }, { wch: 10 }, { wch: 12 },
    { wch: 12 }, { wch: 10 }, { wch: 12 }, { wch: 12 }, { wch: 12 },
  ];
  ws["!rows"] = data.map((_, idx) => {
    if (idx >= dayStartRow && idx < dayStartRow + DISPLAY_DAYS.length) return { hpt: 34 };
    if (idx <= 5) return { hpt: 20 };
    return { hpt: 18 };
  });

  ws["!merges"] = [
    { s: { r: 0, c: 0 }, e: { r: 0, c: 9 } },
    { s: { r: 1, c: 0 }, e: { r: 1, c: 9 } },
    { s: { r: 2, c: 0 }, e: { r: 2, c: 9 } },
    { s: { r: 3, c: 0 }, e: { r: 3, c: 9 } },
    { s: { r: 4, c: 0 }, e: { r: 4, c: 9 } },
    { s: { r: 5, c: 0 }, e: { r: 5, c: 4 } },
    { s: { r: 5, c: 5 }, e: { r: 5, c: 9 } },
    { s: { r: tableHeaderRow, c: 0 }, e: { r: tableHeaderRow + 1, c: 0 } },
    { s: { r: dayStartRow, c: 3 }, e: { r: dayStartRow + DISPLAY_DAYS.length - 1, c: 3 } },
    { s: { r: dayStartRow, c: 6 }, e: { r: dayStartRow + DISPLAY_DAYS.length - 1, c: 6 } },
    ...Array.from({ length: Math.ceil(legend.length / 2) }).flatMap((_, idx) => {
      const row = legendStart + idx;
      return [
        { s: { r: row, c: 0 }, e: { r: row, c: 4 } },
        { s: { r: row, c: 5 }, e: { r: row, c: 9 } },
      ];
    }),
    { s: { r: data.length - 1, c: 0 }, e: { r: data.length - 1, c: 4 } },
    { s: { r: data.length - 1, c: 5 }, e: { r: data.length - 1, c: 9 } },
  ];

  return ws;
}

function parseFacultyWorkloads(records: TimetableRecord[]): FacultyWorkloadType[] {
  const mergedWorkloads: Record<string, Record<string, (FacultyScheduleEntry[] | null)[]>> = {};

  records.forEach((record) => {
    const year = record.year;
    const raw = record.facultyWorkloads ?? {};

    for (const [name, dayMap] of Object.entries(raw)) {
      if (!mergedWorkloads[name]) {
        mergedWorkloads[name] = {};
        for (const day of DISPLAY_DAYS) {
          mergedWorkloads[name][day.full] = Array.from({ length: 7 }, () => null);
        }
      }

      for (const day of DISPLAY_DAYS) {
        const slots = dayMap[day.full] ?? [];
        slots.forEach((value, idx) => {
          if (value && idx < 7) {
            const rawText = String(value);
            const splitIndex = rawText.indexOf(" ");
            let entry: FacultyScheduleEntry;
            if (splitIndex <= 0) {
              entry = { subject: rawText, year, section: "" };
            } else {
              const section = rawText.slice(0, splitIndex).trim();
              const subject = rawText.slice(splitIndex + 1).trim();
              entry = { subject, year, section };
            }

            if (!mergedWorkloads[name][day.full][idx]) {
              mergedWorkloads[name][day.full][idx] = [entry];
            } else {
              // Push to existing array for conflict detection
              const existingArray = mergedWorkloads[name][day.full][idx];
              if (existingArray) {
                // Check if it's already there to avoid duplicates from potential data issues
                const isDuplicate = existingArray.some(e => e.subject === entry.subject && e.section === entry.section && e.year === entry.year);
                if (!isDuplicate) {
                  existingArray.push(entry);
                }
              }
            }
          }
        });
      }
    }
  });

  const items: FacultyWorkloadType[] = Object.entries(mergedWorkloads).map(([name, schedule]) => ({
    name,
    schedule,
  }));

  return items.sort((a, b) => a.name.localeCompare(b.name));
}

const FacultyWorkload = () => {
  const [records, setRecords] = useState<TimetableRecord[]>([]);
  const [selectedFaculty, setSelectedFaculty] = useState<string>("");

  useEffect(() => {
    const load = async () => {
      try {
        const response = await listTimetables();
        setRecords(response.items ?? []);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to load workloads");
      }
    };
    void load();
  }, []);

  const workloads = useMemo(() => records.length > 0 ? parseFacultyWorkloads(records) : [], [records]);
  const facultyNames = useMemo(() => workloads.map((item) => item.name), [workloads]);

  useEffect(() => {
    if (facultyNames.length > 0 && !facultyNames.includes(selectedFaculty)) {
      setSelectedFaculty(facultyNames[0]);
    }
  }, [facultyNames, selectedFaculty]);

  const workload = workloads.find((faculty) => faculty.name === selectedFaculty);

  const handleExport = () => {
    if (!workload) {
      toast.error("No workload data available for this faculty.");
      return;
    }
    const wb = XLSX.utils.book_new();
    const ws = buildWorkloadWorksheet(workload);
    XLSX.utils.book_append_sheet(wb, ws, selectedFaculty.replace(/\s/g, "_"));
    XLSX.writeFile(wb, `Workload_${selectedFaculty.replace(/\s/g, "_")}_Format.xlsx`);
    toast.success("Workload exported in timetable format.");
  };

  const handleExportAll = () => {
    if (workloads.length === 0) {
      toast.error("No faculty workloads available.");
      return;
    }
    const wb = XLSX.utils.book_new();
    workloads.forEach((item, idx) => {
      const ws = buildWorkloadWorksheet(item);
      const base = item.name.replace(/[^A-Za-z0-9]/g, "_").slice(0, 25) || `Faculty_${idx + 1}`;
      const sheetName = `${idx + 1}_${base}`.slice(0, 31);
      XLSX.utils.book_append_sheet(wb, ws, sheetName);
    });
    XLSX.writeFile(wb, "All_Faculty_Workloads_Format.xlsx");
    toast.success("All faculty workloads exported.");
  };

  const renderCell = (entries: FacultyScheduleEntry[] | null | undefined) => {
    if (!entries || entries.length === 0) return null;
    const isConflict = entries.length > 1;
    return (
      <div className={`flex flex-col gap-1 ${isConflict ? "text-destructive" : ""}`}>
        {entries.map((entry, i) => (
          <div key={i} className="font-semibold text-[11px] leading-tight">
            {entryCode(entry)}
          </div>
        ))}
        {isConflict && (
          <div className="text-[9px] font-bold border-t border-destructive/30 pt-0.5 mt-0.5 uppercase">
            Conflict
          </div>
        )}
      </div>
    );
  };

  const legend = workload ? getWorkloadLegend(workload.schedule) : [];

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>Faculty Workload</h1>
        <p>View and export faculty schedules in timetable format</p>
      </div>

      <div className="bg-card rounded-xl p-6 shadow-sm mb-6">
        <div className="flex flex-wrap items-end gap-4">
          <div className="w-64">
            <Label className="text-xs text-muted-foreground">Select Faculty</Label>
            <Select value={selectedFaculty} onValueChange={setSelectedFaculty}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {facultyNames.map((faculty) => <SelectItem key={faculty} value={faculty}>{faculty}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          <Button variant="outline" size="sm" onClick={handleExport} className="gap-1.5 ml-auto">
            <Download className="h-3.5 w-3.5" /> Export Workload
          </Button>
          <Button variant="outline" size="sm" onClick={handleExportAll} className="gap-1.5">
            <Download className="h-3.5 w-3.5" /> Export All Workloads
          </Button>
        </div>
      </div>

      <div className="bg-card rounded-xl p-6 shadow-sm overflow-x-auto">
        {workload ? (
          <>
            <div className="text-center mb-2 border border-border">
              <h3 className="text-base font-semibold uppercase leading-tight border-b border-border py-1">{ACADEMIC_METADATA.COLLEGE_NAME}</h3>
              <p className="text-sm font-semibold leading-tight border-b border-border py-0.5">(AUTONOMOUS)</p>
              <p className="text-sm font-semibold leading-tight border-b border-border py-0.5">{ACADEMIC_METADATA.DEPARTMENT_NAME}</p>
              <div className="text-sm font-semibold leading-tight border-b border-border py-0.5">ACADEMIC YEAR : {toAcademicYear(new Date())} {ACADEMIC_METADATA.SEMESTER}</div>
              <div className="text-sm font-semibold leading-tight border-b border-border py-0.5">FACULTY WORKLOAD : {selectedFaculty}</div>
              <div className="grid grid-cols-2 text-xs font-semibold">
                <div className="text-left px-2 py-0.5 border-r border-border">Room No :</div>
                <div className="text-right px-2 py-0.5">With effect from : {ACADEMIC_METADATA.EFFECTIVE_DATE}</div>
              </div>
            </div>

            <table className="timetable-grid rounded-none overflow-hidden">
              <thead>
                <tr>
                  <th className="min-w-[40px]" rowSpan={2}>DAY</th>
                  <th className="min-w-[90px]">1</th>
                  <th className="min-w-[90px]">2</th>
                  <th className="min-w-[90px] break-header"></th>
                  <th className="min-w-[90px]">3</th>
                  <th className="min-w-[90px]">4</th>
                  <th className="min-w-[90px] lunch-header"></th>
                  <th className="min-w-[90px]">5</th>
                  <th className="min-w-[90px]">6</th>
                  <th className="min-w-[90px]">7</th>
                </tr>
                <tr>
                  <th className="text-[10px]">9.10-10.00</th>
                  <th className="text-[10px]">10.00-10.50</th>
                  <th className="text-[10px] break-header">10.50-11.00</th>
                  <th className="text-[10px]">11.00-11.50</th>
                  <th className="text-[10px]">11.50-12.40</th>
                  <th className="text-[10px] lunch-header">12.40-1.30</th>
                  <th className="text-[10px]">1.30-2.20</th>
                  <th className="text-[10px]">2.20-3.10</th>
                  <th className="text-[10px]">3.10-4.00</th>
                </tr>
              </thead>
              <tbody>
                {DISPLAY_DAYS.map((day, idx) => {
                  const daySchedule = workload.schedule[day.full] ?? [];
                  return (
                    <tr key={day.full}>
                      <td className="font-semibold text-[10px] whitespace-pre leading-[1.05]">{day.shortVertical}</td>
                      <td className={daySchedule[0] && daySchedule[0].length > 1 ? "bg-destructive/5" : ""}>{renderCell(daySchedule[0])}</td>
                      <td className={daySchedule[1] && daySchedule[1].length > 1 ? "bg-destructive/5" : ""}>{renderCell(daySchedule[1])}</td>
                      {idx === 0 && (
                        <td rowSpan={DISPLAY_DAYS.length} className="break-cell font-semibold text-[18px] tracking-widest whitespace-pre leading-7">
                          {"B\nR\nE\nA\nK"}
                        </td>
                      )}
                      <td className={daySchedule[2] && daySchedule[2].length > 1 ? "bg-destructive/5" : ""}>{renderCell(daySchedule[2])}</td>
                      <td className={daySchedule[3] && daySchedule[3].length > 1 ? "bg-destructive/5" : ""}>{renderCell(daySchedule[3])}</td>
                      {idx === 0 && (
                        <td rowSpan={DISPLAY_DAYS.length} className="lunch-cell font-semibold text-[18px] tracking-widest whitespace-pre leading-7">
                          {"L\nU\nN\nC\nH"}
                        </td>
                      )}
                      <td className={daySchedule[4] && daySchedule[4].length > 1 ? "bg-destructive/5" : ""}>{renderCell(daySchedule[4])}</td>
                      <td className={daySchedule[5] && daySchedule[5].length > 1 ? "bg-destructive/5" : ""}>{renderCell(daySchedule[5])}</td>
                      <td className={daySchedule[6] && daySchedule[6].length > 1 ? "bg-destructive/5" : ""}>{renderCell(daySchedule[6])}</td>
                    </tr>
                  );
                })}

                <tr>
                  <td colSpan={10} className="bg-white p-0.5 border-b border-border"></td>
                </tr>

                {Array.from({ length: Math.ceil(legend.length / 2) }).map((_, rowIdx) => {
                  const left = legend[rowIdx * 2];
                  const right = legend[rowIdx * 2 + 1];
                  return (
                    <tr key={`legend-${rowIdx}`}>
                      <td colSpan={5} className="text-left text-[11px] px-2 py-1">{left ? <span><strong>{left.code}</strong> : {left.label}</span> : ""}</td>
                      <td colSpan={5} className="text-left text-[11px] px-2 py-1">{right ? <span><strong>{right.code}</strong> : {right.label}</span> : ""}</td>
                    </tr>
                  );
                })}

                <tr>
                  <td colSpan={5} className="text-center font-semibold py-2">HEAD OF THE DEPARTMENT</td>
                  <td colSpan={5} className="text-center font-semibold py-2">PRINCIPAL</td>
                </tr>
              </tbody>
            </table>
          </>
        ) : (
          <div className="text-center py-16 text-muted-foreground">No workload data available for this faculty.</div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default FacultyWorkload;
