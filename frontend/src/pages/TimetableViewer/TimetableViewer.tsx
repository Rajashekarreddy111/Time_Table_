import { useEffect, useMemo, useState } from "react";
import { Download, Printer, Trash2 } from "lucide-react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { TimetableGrid } from "@/components/TimetableGrid";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { type SectionTimetable } from "@/data/mockData";
import { toast } from "sonner";
import * as XLSX from "xlsx";
import {
  buildLegend,
  DISPLAY_DAYS,
  getCellByPeriod,
} from "@/lib/timetableFormat";
import {
  listTimetables,
  type GeneratedWorkbookFile,
  type TimetableRecord,
  type TimetableMetadata,
  deleteTimetable,
  getAllSectionsWorkbook,
  getSectionWorkbook,
} from "@/services/apiClient";
import {
  ACADEMIC_METADATA,
  formatSemesterLabel,
  formatWithEffectFrom,
  toAcademicYear,
} from "@/lib/academicMetadata";
import { useSearchParams } from "react-router-dom";

const TOTAL_COLUMNS = 10;

function toClassLine(year: string, section: string, semesterLabel?: string): string {
  const yearMap: Record<string, string> = {
    "2nd Year": "II B.Tech",
    "3rd Year": "III B.Tech",
    "4th Year": "IV B.Tech",
  };
  const normalized = yearMap[year] ?? year;
  return `${normalized} [CSE - ${section}] ${semesterLabel ?? ACADEMIC_METADATA.SEMESTER} TIME TABLE`;
}

function getResolvedMetadata(metadata?: TimetableMetadata) {
  return {
    academicYear: metadata?.academicYear ?? toAcademicYear(new Date()),
    semester: formatSemesterLabel(metadata?.semester ?? 2),
    withEffectFrom: formatWithEffectFrom(metadata?.withEffectFrom),
  };
}

function padRow(values: string[]): string[] {
  if (values.length >= TOTAL_COLUMNS) return values.slice(0, TOTAL_COLUMNS);
  return [
    ...values,
    ...Array.from({ length: TOTAL_COLUMNS - values.length }, () => ""),
  ];
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

function getSubjectLabel(
  cell: SectionTimetable["grid"][string][number] | null | undefined,
): string {
  return cell?.subjectName ?? cell?.subject ?? "";
}

function areCellsEquivalent(
  left: SectionTimetable["grid"][string][number] | null | undefined,
  right: SectionTimetable["grid"][string][number] | null | undefined,
): boolean {
  if (!left || !right) return false;
  return (
    getSubjectLabel(left) === getSubjectLabel(right) &&
    (left.facultyName ?? left.faculty ?? "") ===
      (right.facultyName ?? right.faculty ?? "") &&
    Boolean(left.isLab) === Boolean(right.isLab) &&
    (left.sharedSections ?? []).join(",") ===
      (right.sharedSections ?? []).join(",")
  );
}

type Run = {
  start: number;
  end: number;
  cell: SectionTimetable["grid"][string][number] | null | undefined;
};

function buildDayRuns(
  cells: Array<SectionTimetable["grid"][string][number] | null | undefined>,
): Run[] {
  const runs: Run[] = [];
  let idx = 0;

  while (idx < cells.length) {
    const current = cells[idx];
    let end = idx;

    while (
      end + 1 < cells.length &&
      areCellsEquivalent(current, cells[end + 1])
    ) {
      if (end === 1 || end === 3) break;
      end += 1;
    }

    runs.push({ start: idx + 1, end: end + 1, cell: current });
    idx = end + 1;
  }

  return runs;
}

function appendMergedRowWithBreakLunch(
  row: string[],
  cells: Array<SectionTimetable["grid"][string][number] | null | undefined>,
  worksheetRow: number,
  merges: XLSX.Range[],
) {
  const runs = buildDayRuns(cells);
  let column = 1; // after DAY/th

  runs.forEach((run, index) => {
    const label = getSubjectLabel(run.cell);
    const span = run.end - run.start + 1;

    row.push(label);
    for (let i = 1; i < span; i += 1) {
      row.push("");
    }

    if (span > 1) {
      merges.push({
        s: { r: worksheetRow, c: column },
        e: { r: worksheetRow, c: column + span - 1 },
      });
    }

    column += span;

    if (run.end === 2 && index < runs.length - 1) {
      row.push("BREAK");
      column += 1;
    }

    if (run.end === 4 && index < runs.length - 1) {
      row.push("LUNCH");
      column += 1;
    }
  });
}

function buildTimetableWorksheet(
  timetable: SectionTimetable,
  metadata?: TimetableMetadata,
) {
  const resolvedMetadata = getResolvedMetadata(metadata);
  const legend = buildLegend(timetable.grid);
  const data: string[][] = [];
  const merges: XLSX.Range[] = [];

  data.push(padRow([ACADEMIC_METADATA.COLLEGE_NAME]));
  data.push(padRow(["(AUTONOMOUS)"]));
  data.push(padRow([ACADEMIC_METADATA.DEPARTMENT_NAME]));
  data.push(
    padRow([
      `ACADEMIC YEAR : ${resolvedMetadata.academicYear} ${resolvedMetadata.semester}`,
    ]),
  );
  data.push(padRow([toClassLine(timetable.year, timetable.section, resolvedMetadata.semester)]));
  data.push(padRow(["Room No :", "", "", "", "", `With effect from : ${resolvedMetadata.withEffectFrom}`]));

  const tableHeaderRow = data.length;
  data.push(padRow(["DAY", "1", "2", "", "3", "4", "", "5", "6", "7"]));
  data.push(
    padRow([
      "",
      "9.10-10.00",
      "10.00-10.50",
      "10.50-11.00",
      "11.00-11.50",
      "11.50-12.40",
      "12.40-1.30",
      "1.30-2.20",
      "2.20-3.10",
      "3.10-4.00",
    ]),
  );

  const dayStartRow = data.length;
  DISPLAY_DAYS.forEach((day) => {
    const cells = [
      getCellByPeriod(timetable.grid, day.full, 1),
      getCellByPeriod(timetable.grid, day.full, 2),
      getCellByPeriod(timetable.grid, day.full, 3),
      getCellByPeriod(timetable.grid, day.full, 4),
      getCellByPeriod(timetable.grid, day.full, 5),
      getCellByPeriod(timetable.grid, day.full, 6),
      getCellByPeriod(timetable.grid, day.full, 7),
    ];
    const worksheetRow = data.length;
    const row = [day.shortVertical];
    appendMergedRowWithBreakLunch(row, cells, worksheetRow, merges);
    data.push(padRow(row));
  });

  data.push(padRow([""]));
  const legendStart = data.length;
  for (let i = 0; i < legend.length; i += 2) {
    const left = legend[i];
    const right = legend[i + 1];
    data.push(
      padRow([
        left ? `${left.subject} : ${left.faculty}` : "",
        "",
        "",
        "",
        "",
        right ? `${right.subject} : ${right.faculty}` : "",
        "",
        "",
        "",
        "",
      ]),
    );
  }

  data.push(padRow([""]));
  data.push(padRow(["HEAD OF THE DEPARTMENT", "", "", "", "", "PRINCIPAL"]));

  const ws = XLSX.utils.aoa_to_sheet(data);
  ws["!cols"] = [
    { wch: 7 },
    { wch: 12 },
    { wch: 12 },
    { wch: 10 },
    { wch: 12 },
    { wch: 12 },
    { wch: 10 },
    { wch: 12 },
    { wch: 12 },
    { wch: 12 },
  ];
  ws["!rows"] = data.map((_, idx) => {
    if (idx >= dayStartRow && idx < dayStartRow + DISPLAY_DAYS.length)
      return { hpt: 34 };
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
    {
      s: { r: dayStartRow, c: 3 },
      e: { r: dayStartRow + DISPLAY_DAYS.length - 1, c: 3 },
    },
    {
      s: { r: dayStartRow, c: 6 },
      e: { r: dayStartRow + DISPLAY_DAYS.length - 1, c: 6 },
    },
    ...Array.from({ length: Math.ceil(legend.length / 2) }).flatMap(
      (_, idx) => {
        const row = legendStart + idx;
        return [
          { s: { r: row, c: 0 }, e: { r: row, c: 4 } },
          { s: { r: row, c: 5 }, e: { r: row, c: 9 } },
        ];
      },
    ),
    { s: { r: data.length - 1, c: 0 }, e: { r: data.length - 1, c: 4 } },
    { s: { r: data.length - 1, c: 5 }, e: { r: data.length - 1, c: 9 } },
    ...merges,
  ];

  return ws;
}

function extractSectionTimetables(
  records: TimetableRecord[],
): SectionTimetable[] {
  const items: SectionTimetable[] = [];
  for (const record of records) {
    if (record.allGrids) {
      for (const [section, grid] of Object.entries(record.allGrids)) {
        // Only include grids that have at least one non-empty day
        if (grid && typeof grid === "object" && Object.keys(grid).length > 0) {
          const hasData = Object.values(grid).some(
            (daySlots) =>
              Array.isArray(daySlots) &&
              daySlots.some((slot) => slot !== null && slot !== undefined),
          );
          if (hasData) {
            items.push({ year: record.year, section, grid });
          }
        }
      }
      continue;
    }
    if (record.grid) {
      // Only include grids that have at least one non-empty day
      if (
        record.grid &&
        typeof record.grid === "object" &&
        Object.keys(record.grid).length > 0
      ) {
        const hasData = Object.values(record.grid).some(
          (daySlots) =>
            Array.isArray(daySlots) &&
            daySlots.some((slot) => slot !== null && slot !== undefined),
        );
        if (hasData) {
          items.push({
            year: record.year,
            section: record.section,
            grid: record.grid,
          });
        }
      }
    }
  }
  return items;
}

const TimetableViewer = () => {
  const [searchParams] = useSearchParams();
  const timetableId = searchParams.get("timetableId");

  const [records, setRecords] = useState<TimetableRecord[]>([]);
  const [selectedYear, setSelectedYear] = useState<string>("");
  const [selectedSection, setSelectedSection] = useState<string>("");

  useEffect(() => {
    if (timetableId && records.length > 0) {
      const target = records.find((r) => r.id === timetableId);
      if (target) {
        setSelectedYear(target.year);
        setSelectedSection(target.section);
      }
    }
  }, [timetableId, records]);

  useEffect(() => {
    const load = async () => {
      try {
        const response = await listTimetables();
        setRecords(response.items ?? []);
      } catch (error) {
        toast.error(
          error instanceof Error ? error.message : "Failed to load timetables",
        );
      }
    };
    void load();
  }, []);

  const validRecords = useMemo(
    () => records.filter((record) => record.hasValidTimetable !== false),
    [records],
  );
  const allTimetables = useMemo(
    () => extractSectionTimetables(validRecords),
    [validRecords],
  );
  const availableYears = useMemo(
    () => Array.from(new Set(allTimetables.map((item) => item.year))),
    [allTimetables],
  );
  const availableSections = useMemo(
    () =>
      Array.from(
        new Set(
          allTimetables
            .filter((item) => item.year === selectedYear)
            .map((item) => item.section),
        ),
      ),
    [allTimetables, selectedYear],
  );

  useEffect(() => {
    if (availableYears.length > 0 && !availableYears.includes(selectedYear)) {
      setSelectedYear(availableYears[0]);
    }
  }, [availableYears, selectedYear]);

  useEffect(() => {
    if (
      availableSections.length > 0 &&
      !availableSections.includes(selectedSection)
    ) {
      setSelectedSection(availableSections[0]);
    }
  }, [availableSections, selectedSection]);

  const timetable = allTimetables.find(
    (item) => item.year === selectedYear && item.section === selectedSection,
  );
  const activeRecord = validRecords.find(
    (record) =>
      (record.year === selectedYear && record.section === selectedSection) ||
      Boolean(
        record.year === selectedYear &&
        record.allGrids &&
        record.allGrids[selectedSection],
      ),
  );
  const resolvedMetadata = getResolvedMetadata(activeRecord?.timetableMetadata);

  const handleExportExcel = async () => {
    if (!timetable) return;
    if (activeRecord) {
      try {
        const workbook = await getSectionWorkbook(
          activeRecord.id,
          selectedSection,
        );
        downloadGeneratedWorkbook(workbook);
        toast.success("Selected timetable downloaded.");
        return;
      } catch (error) {
        toast.error(
          error instanceof Error
            ? error.message
            : "Failed to download selected timetable",
        );
        return;
      }
    }
    toast.error("No backend workbook available for the selected timetable.");
  };

  const handleExportAllTimetables = async () => {
    try {
      const workbook = await getAllSectionsWorkbook();
      downloadGeneratedWorkbook(workbook);
      toast.success("All class timetables exported.");
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Failed to download all timetables",
      );
    }
  };

  const handlePrint = () => window.print();

  const handleDelete = async () => {
    const record = activeRecord;

    if (!record) return;

    if (!confirm("Are you sure you want to delete this timetable?")) return;

    try {
      await deleteTimetable(record.id);
      toast.success("Timetable deleted successfully");
      // Refresh list
      const response = await listTimetables();
      setRecords(response.items ?? []);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Failed to delete timetable",
      );
    }
  };

  return (
    <DashboardLayout>
      <section className="hero-shell mb-8">
        <div className="relative z-10 grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_340px] xl:items-end">
          <div className="space-y-4">
            <div className="hero-chip">Timetable Viewing Studio</div>
            <div className="space-y-2">
              <h1 className="text-4xl font-bold tracking-tight text-foreground">
                View Timetables
              </h1>
              <p className="max-w-2xl text-sm leading-7 text-muted-foreground">
                Switch between years and sections, export polished sheets, and
                print the current timetable directly from one workspace.
              </p>
            </div>
          </div>
          <div className="panel-card">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Live Summary
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="panel-muted">
                <p className="text-2xl font-bold text-foreground">
                  {availableYears.length}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Years available
                </p>
              </div>
              <div className="panel-muted">
                <p className="text-2xl font-bold text-foreground">
                  {allTimetables.length}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Section timetables
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {allTimetables.length > 1 && (
        <div className="panel-card mb-6 print:hidden">
          <h3 className="text-xs font-semibold text-primary uppercase tracking-wider mb-3">
            Recently Generated / Available Sections
          </h3>
          <div className="flex flex-wrap gap-2">
            {allTimetables.map((item, idx) => (
              <Button
                key={`${item.year}-${item.section}-${idx}`}
                variant={
                  selectedYear === item.year && selectedSection === item.section
                    ? "default"
                    : "outline"
                }
                size="sm"
                className="h-8 text-xs"
                onClick={() => {
                  setSelectedYear(item.year);
                  setSelectedSection(item.section);
                }}
              >
                {item.year.replace(" Year", "")} - {item.section}
              </Button>
            ))}
          </div>
        </div>
      )}

      <div className="panel-card mb-6 print:hidden">
        <div className="flex flex-wrap items-end gap-4">
          <div className="w-48">
            <Label className="text-xs text-muted-foreground">Year</Label>
            <Select value={selectedYear} onValueChange={setSelectedYear}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {availableYears.map((year) => (
                  <SelectItem key={year} value={year}>
                    {year}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="w-48">
            <Label className="text-xs text-muted-foreground">Section</Label>
            <Select value={selectedSection} onValueChange={setSelectedSection}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {availableSections.map((section) => (
                  <SelectItem key={section} value={section}>
                    {section}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex gap-2 ml-auto">
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportExcel}
              className="gap-1.5"
            >
              <Download className="h-3.5 w-3.5" /> Download Excel
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExportAllTimetables}
              className="gap-1.5"
            >
              <Download className="h-3.5 w-3.5" /> Download All Timetables
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handlePrint}
              className="gap-1.5"
            >
              <Printer className="h-3.5 w-3.5" /> Print
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDelete}
              className="gap-1.5"
            >
              <Trash2 className="h-3.5 w-3.5" /> Delete
            </Button>
          </div>
        </div>
      </div>

      <div className="panel-card print:shadow-none print:p-0">
        {timetable ? (
          <div className="space-y-4">
            <TimetableGrid
              grid={timetable.grid}
              header={{
                college: ACADEMIC_METADATA.COLLEGE_NAME,
                department: ACADEMIC_METADATA.DEPARTMENT_NAME,
                year: resolvedMetadata.academicYear,
                semester: resolvedMetadata.semester,
                section: toClassLine(selectedYear, selectedSection, resolvedMetadata.semester),
                room: selectedSection,
                withEffectFrom: resolvedMetadata.withEffectFrom,
              }}
            />
          </div>
        ) : (
          <div className="text-center py-16">
            <p className="text-muted-foreground">
              No valid timetable is available for {selectedYear} - Section{" "}
              {selectedSection}.
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              If generation failed, check the Generated Outputs page for the
              constraint report.
            </p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default TimetableViewer;
