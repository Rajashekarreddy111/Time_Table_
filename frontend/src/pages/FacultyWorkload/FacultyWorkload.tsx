import { useEffect, useMemo, useState } from "react";
import { Download } from "lucide-react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import * as XLSX from "xlsx";
import { toast } from "sonner";
import { DISPLAY_DAYS } from "@/lib/timetableFormat";
import {
  listTimetables,
  type GeneratedWorkbookFile,
  type TimetableMetadata,
  type TimetableRecord,
  getFacultyWorkloadWorkbook,
} from "@/services/apiClient";
import {
  ACADEMIC_METADATA,
  formatSemesterLabel,
  formatWithEffectFrom,
  toAcademicYear,
} from "@/lib/academicMetadata";

type FacultyScheduleEntry = {
  subject: string;
  year: string;
  section: string;
  classroom?: string;
  labRoom?: string;
  fallbackLab?: string;
  isLab?: boolean;
};

type FacultyWorkloadType = {
  name: string;
  schedule: Record<string, (FacultyScheduleEntry[] | null)[]>;
};

const TOTAL_COLUMNS = 10;

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

function formatWorkloadEntry(entry: FacultyScheduleEntry): string {
  const roomLabel = entry.isLab
    ? entry.labRoom ?? ""
    : entry.fallbackLab && entry.classroom
      ? `${entry.fallbackLab}/${entry.classroom}`
      : entry.fallbackLab ?? entry.classroom ?? "";
  const roomLine = entry.isLab
    ? roomLabel ? `\n(${roomLabel})` : ""
    : roomLabel ? `\n(${roomLabel})` : "";
  return `${entry.subject}\n${entry.year} ${entry.section}${roomLine}`;
}

function buildWorkloadCellText(entries: FacultyScheduleEntry[] | null | undefined): string {
  if (!entries || entries.length === 0) return "";
  return entries.map(formatWorkloadEntry).join("\n\n");
}

function padRow(values: string[]): string[] {
  if (values.length >= TOTAL_COLUMNS) return values.slice(0, TOTAL_COLUMNS);
  return [...values, ...Array.from({ length: TOTAL_COLUMNS - values.length }, () => "")];
}

function getWorkloadLegend(schedule: Record<string, (FacultyScheduleEntry[] | null)[]>) {
  const labels = new Set<string>();
  for (const day of DISPLAY_DAYS) {
    for (const entries of schedule[day.full] ?? []) {
      if (!entries) continue;
      for (const entry of entries) {
        labels.add(`${entry.year} ${entry.section} - ${entry.subject}`);
      }
    }
  }
  return Array.from(labels).sort((a, b) => a.localeCompare(b));
}

function areEntryGroupsEquivalent(
  left: FacultyScheduleEntry[] | null | undefined,
  right: FacultyScheduleEntry[] | null | undefined,
): boolean {
  if (!left || !right || left.length !== right.length) return false;
  return left.every((entry, idx) => formatWorkloadEntry(entry) === formatWorkloadEntry(right[idx]));
}

function appendMergedWorkloadRuns(
  row: string[],
  entries: Array<FacultyScheduleEntry[] | null | undefined>,
  displayColumns: number[],
  worksheetRow: number,
  merges: XLSX.Range[],
) {
  let idx = 0;
  while (idx < entries.length) {
    const current = entries[idx];
    let end = idx;
    while (end + 1 < entries.length && areEntryGroupsEquivalent(current, entries[end + 1])) {
      end += 1;
    }
    row.push(buildWorkloadCellText(current));
    for (let filler = idx + 1; filler <= end; filler += 1) {
      row.push("");
    }
    if (end > idx) {
      merges.push({
        s: { r: worksheetRow, c: displayColumns[idx] },
        e: { r: worksheetRow, c: displayColumns[end] },
      });
    }
    idx = end + 1;
  }
}

function buildWorkloadWorksheet(
  workload: FacultyWorkloadType,
  metadata?: TimetableMetadata,
) {
  const resolvedAcademicYear = metadata?.academicYear ?? toAcademicYear(new Date());
  const resolvedSemester = formatSemesterLabel(metadata?.semester ?? 2);
  const resolvedWithEffectFrom = formatWithEffectFrom(metadata?.withEffectFrom);
  const legend = getWorkloadLegend(workload.schedule);
  const data: string[][] = [];
  const merges: XLSX.Range[] = [];

  data.push(padRow([ACADEMIC_METADATA.COLLEGE_NAME]));
  data.push(padRow(["(AUTONOMOUS)"]));
  data.push(padRow([ACADEMIC_METADATA.DEPARTMENT_NAME]));
  data.push(padRow([`ACADEMIC YEAR : ${resolvedAcademicYear} ${resolvedSemester}`]));
  data.push(padRow([`FACULTY WORKLOAD : ${workload.name}`]));
  data.push(padRow(["Room No :", "", "", "", "", `With effect from : ${resolvedWithEffectFrom}`]));

  const tableHeaderRow = data.length;
  data.push(padRow(["DAY", "1", "2", "", "3", "4", "", "5", "6", "7"]));
  data.push(padRow(["", "9.10-10.00", "10.00-10.50", "10.50-11.00", "11.00-11.50", "11.50-12.40", "12.40-1.30", "1.30-2.20", "2.20-3.10", "3.10-4.00"]));

  const dayStartRow = data.length;
  DISPLAY_DAYS.forEach((day, dayIdx) => {
    const dayEntries = workload.schedule[day.full] ?? [];
    const worksheetRow = data.length;
    const row = [day.shortVertical];
    appendMergedWorkloadRuns(row, [dayEntries[0], dayEntries[1]], [1, 2], worksheetRow, merges);
    row.push(dayIdx === 0 ? "BREAK" : "");
    appendMergedWorkloadRuns(row, [dayEntries[2], dayEntries[3]], [4, 5], worksheetRow, merges);
    row.push(dayIdx === 0 ? "LUNCH" : "");
    appendMergedWorkloadRuns(row, [dayEntries[4], dayEntries[5], dayEntries[6]], [7, 8, 9], worksheetRow, merges);
    data.push(padRow(row));
  });

  data.push(padRow([""]));
  const legendStart = data.length;
  for (let idx = 0; idx < legend.length; idx += 2) {
    const left = legend[idx];
    const right = legend[idx + 1];
    data.push(padRow([
      left ?? "",
      "", "", "", "",
      right ?? "",
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
    ...merges,
  ];

  return ws;
}

function parseFacultyWorkloads(records: TimetableRecord[]): FacultyWorkloadType[] {
  const latestSections = new Map<string, { year: string; section: string; grid: TimetableRecord["grid"] }>();
  records.forEach((record) => {
    const grids = record.allGrids ?? { [record.section]: record.grid };
    for (const [section, grid] of Object.entries(grids)) {
      const key = `${record.year}::${section}`;
      if (!latestSections.has(key)) {
        latestSections.set(key, { year: record.year, section, grid });
      }
    }
  });
  const mergedWorkloads: Record<string, Record<string, (FacultyScheduleEntry[] | null)[]>> = {};

  const ensureFacultySchedule = (facultyName: string) => {
    if (!mergedWorkloads[facultyName]) {
      mergedWorkloads[facultyName] = {};
      for (const day of DISPLAY_DAYS) {
        mergedWorkloads[facultyName][day.full] = Array.from({ length: 7 }, () => null);
      }
    }
    return mergedWorkloads[facultyName];
  };

  latestSections.forEach(({ year, section, grid }) => {
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
          year,
          section: sections,
          classroom: cell.classroom,
          labRoom: cell.labRoom,
          fallbackLab: cell.fallbackLab,
          isLab: cell.isLab,
        };

        const facultySchedule = ensureFacultySchedule(facultyName);
        if (!facultySchedule[day.full][idx]) {
          facultySchedule[day.full][idx] = [entry];
          return;
        }

        const existingArray = facultySchedule[day.full][idx];
        if (!existingArray) return;
        const isDuplicate = existingArray.some(
          (existing) =>
            existing.subject === entry.subject &&
            existing.section === entry.section &&
            existing.year === entry.year,
        );
        if (!isDuplicate) {
          existingArray.push(entry);
        }
      });
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

  const validRecords = useMemo(
    () => records,
    [records],
  );
  const workloadMetadata = validRecords[0]?.timetableMetadata;
  const resolvedAcademicYear = workloadMetadata?.academicYear ?? toAcademicYear(new Date());
  const resolvedSemester = formatSemesterLabel(workloadMetadata?.semester ?? 2);
  const resolvedWithEffectFrom = formatWithEffectFrom(workloadMetadata?.withEffectFrom);
  const workloads = useMemo(() => validRecords.length > 0 ? parseFacultyWorkloads(validRecords) : [], [validRecords]);
  const facultyNames = useMemo(() => workloads.map((item) => item.name), [workloads]);

  useEffect(() => {
    if (facultyNames.length > 0 && !facultyNames.includes(selectedFaculty)) {
      setSelectedFaculty(facultyNames[0]);
    }
  }, [facultyNames, selectedFaculty]);

  const workload = workloads.find((faculty) => faculty.name === selectedFaculty);
  const handleExport = async () => {
    if (selectedFaculty) {
      try {
        const workbook = await getFacultyWorkloadWorkbook(selectedFaculty);
        downloadGeneratedWorkbook(workbook);
        toast.success("Selected faculty workload downloaded.");
        return;
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to download faculty workload");
      }
    }
    if (!workload) {
      toast.error("No workload data available for this faculty.");
      return;
    }
    const wb = XLSX.utils.book_new();
    const ws = buildWorkloadWorksheet(workload, workloadMetadata);
    XLSX.utils.book_append_sheet(wb, ws, selectedFaculty.replace(/\s/g, "_"));
    XLSX.writeFile(wb, `Workload_${selectedFaculty.replace(/\s/g, "_")}_Format.xlsx`);
    toast.success("Workload exported in timetable format.");
  };

  const handleExportAll = async () => {
    try {
      const workbook = await getFacultyWorkloadWorkbook();
      downloadGeneratedWorkbook(workbook);
      toast.success("All faculty workloads exported.");
      return;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to download all faculty workloads");
    }
    if (workloads.length === 0) {
      toast.error("No faculty workloads available.");
      return;
    }
    const wb = XLSX.utils.book_new();
    workloads.forEach((item, idx) => {
      const ws = buildWorkloadWorksheet(item, workloadMetadata);
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
            {entry.subject}
            <div className="font-normal text-[10px] text-muted-foreground">
              {entry.year} {entry.section}
            </div>
            {(entry.classroom || entry.labRoom || entry.fallbackLab) && (
              <div className="font-normal text-[10px] text-muted-foreground">
                ({entry.isLab
                  ? (entry.labRoom ?? "")
                  : entry.fallbackLab && entry.classroom
                    ? `${entry.fallbackLab}/${entry.classroom}`
                    : entry.fallbackLab ?? entry.classroom ?? ""})
              </div>
            )}
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

  const renderMergedEntryCells = (
    daySchedule: (FacultyScheduleEntry[] | null)[],
    startIndex: number,
    endIndex: number,
  ) => {
    const cells: JSX.Element[] = [];
    let idx = startIndex;

    while (idx <= endIndex) {
      const current = daySchedule[idx];
      let end = idx;
      while (end + 1 <= endIndex && areEntryGroupsEquivalent(current, daySchedule[end + 1])) {
        end += 1;
      }

      const colSpan = end - idx + 1;
      const hasConflict = Boolean(current && current.length > 1);
      cells.push(
        <td
          key={`faculty-slot-${startIndex}-${idx}`}
          colSpan={colSpan}
          className={hasConflict ? "bg-destructive/5" : ""}
        >
          {renderCell(current)}
        </td>,
      );
      idx = end + 1;
    }

    return cells;
  };

  const legend = workload ? getWorkloadLegend(workload.schedule) : [];

  return (
    <DashboardLayout>
      <div className="w-full space-y-6">
        <div className="page-header">
          <h1>Faculty Workload</h1>
          <p>View and export faculty schedules in timetable format</p>
        </div>

        <div className="bg-card rounded-xl p-6 xl:p-7 shadow-sm mb-6 w-full">
          <div className="flex flex-wrap items-end gap-4">
            <div className="w-full sm:w-80">
              <Label className="text-xs text-muted-foreground">Select Faculty</Label>
              <Select value={selectedFaculty} onValueChange={setSelectedFaculty}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {facultyNames.map((faculty) => <SelectItem key={faculty} value={faculty}>{faculty}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>

            <Button variant="outline" size="sm" onClick={handleExport} className="gap-1.5 sm:ml-auto">
              <Download className="h-3.5 w-3.5" /> Export Workload
            </Button>
            <Button variant="outline" size="sm" onClick={handleExportAll} className="gap-1.5">
              <Download className="h-3.5 w-3.5" /> Export All Workloads
            </Button>
          </div>
        </div>

        <div className="bg-card rounded-xl p-4 sm:p-6 xl:p-8 shadow-sm overflow-x-auto w-full">
          {workload ? (
            <>
              <div className="timetable-sheet-frame text-center mb-3 border min-w-[980px]">
                <h3 className="text-base font-semibold uppercase leading-tight border-b py-1">{ACADEMIC_METADATA.COLLEGE_NAME}</h3>
                <p className="text-sm font-semibold leading-tight border-b py-0.5">(AUTONOMOUS)</p>
                <p className="text-sm font-semibold leading-tight border-b py-0.5">{ACADEMIC_METADATA.DEPARTMENT_NAME}</p>
                <div className="text-sm font-semibold leading-tight border-b py-0.5">ACADEMIC YEAR : {resolvedAcademicYear} {resolvedSemester}</div>
                <div className="text-sm font-semibold leading-tight border-b py-0.5">FACULTY WORKLOAD : {selectedFaculty}</div>
                <div className="grid grid-cols-2 text-xs font-semibold text-center">
                  <div className="px-2 py-0.5 border-r">Room No :</div>
                  <div className="px-2 py-0.5">With effect from : {resolvedWithEffectFrom}</div>
                </div>
              </div>

              <table className="timetable-grid rounded-none overflow-hidden min-w-[980px]">
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
                      {renderMergedEntryCells(daySchedule, 0, 1)}
                      {idx === 0 && (
                        <td rowSpan={DISPLAY_DAYS.length} className="break-cell font-semibold text-[18px] tracking-widest whitespace-pre leading-7">
                          {"B\nR\nE\nA\nK"}
                        </td>
                      )}
                      {renderMergedEntryCells(daySchedule, 2, 3)}
                      {idx === 0 && (
                        <td rowSpan={DISPLAY_DAYS.length} className="lunch-cell font-semibold text-[18px] tracking-widest whitespace-pre leading-7">
                          {"L\nU\nN\nC\nH"}
                        </td>
                      )}
                      {renderMergedEntryCells(daySchedule, 4, 6)}
                    </tr>
                  );
                })}

                <tr>
                  <td colSpan={10} className="bg-white p-0.5 border-b"></td>
                </tr>

                {Array.from({ length: Math.ceil(legend.length / 2) }).map((_, rowIdx) => {
                  const left = legend[rowIdx * 2];
                  const right = legend[rowIdx * 2 + 1];
                  return (
                    <tr key={`legend-${rowIdx}`}>
                      <td colSpan={5} className="text-left text-[11px] px-2 py-1">{left ?? ""}</td>
                      <td colSpan={5} className="text-left text-[11px] px-2 py-1">{right ?? ""}</td>
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
      </div>
    </DashboardLayout>
  );
};

export default FacultyWorkload;
