import { useMemo, useState } from "react";
import { AlertTriangle, CalendarDays, CheckCircle2, Clock3, Download, FileSpreadsheet, Search, Sparkles, Upload, Users, XCircle, ChevronDown, ChevronUp, Check, Info } from "lucide-react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { FileUpload } from "@/components/FileUpload";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { PERIODS } from "@/data/mockData";
import { ACADEMIC_METADATA } from "@/lib/academicMetadata";
import { readAcademicConfig } from "@/lib/academicConfig";
import { buildTemplateLinks } from "@/utils/templateLinks";
import { API_BASE_URL, exportBulkFacultyAvailabilityReport, type BulkFacultyAvailabilityItem, type GeneratedWorkbookFile, getBulkFacultyAvailability, uploadFacultyAvailability, uploadFacultyAvailabilityQuery } from "@/services/apiClient";
import { toast } from "sonner";
import * as XLSX from "xlsx";

type PeriodInfo = { period: number; time: string };
type SummaryStat = { label: string; value: string | number; hint: string; tone: string };
type ExportSlot = {
  key: string;
  label: string;
  startMinutes: number;
};

type ExportDateGroup = {
  date: string;
  headerDate: string;
  slots: ExportSlot[];
  usesMeridiemColumns: boolean;
};
type ExportMode = "selected" | "available";

const actualPeriods: PeriodInfo[] = PERIODS.filter(
  (item): item is { period: number; time: string } => typeof item.period === "number",
).map((item) => ({ period: item.period, time: item.time.replace(/â€“|Ã¢â‚¬â€œ|ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“/g, "-") }));

function formatPeriods(periods: PeriodInfo[]): string {
  return periods.map((period) => `P${period.period}`).join(", ");
}

function parseClockToMinutes(value: string): number {
  const trimmed = value.trim().toUpperCase();
  const timeMatch = trimmed.match(/(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?/);
  if (!timeMatch) return 0;

  let hour = Number(timeMatch[1]);
  const minute = Number(timeMatch[2]);
  const meridiem = timeMatch[4] ?? "";

  if (Number.isNaN(hour) || Number.isNaN(minute)) return 0;

  if (meridiem === "AM") {
    if (hour === 12) hour = 0;
  } else if (meridiem === "PM") {
    if (hour !== 12) hour += 12;
  } else if (hour >= 1 && hour <= 4) {
    hour += 12;
  }

  return hour * 60 + minute;
}

function buildSessionRange(periods: PeriodInfo[]): ExportSlot {
  const normalizedTimes = periods.map((period) => period.time.trim()).filter(Boolean);
  if (normalizedTimes.length === 0) {
    return { key: "Session", label: "Session", startMinutes: 0 };
  }

  const firstParts = normalizedTimes[0].split("-").map((part) => part.trim());
  const lastParts = normalizedTimes[normalizedTimes.length - 1].split("-").map((part) => part.trim());
  const startText = firstParts[0] ?? "";
  const endText = lastParts[lastParts.length - 1] ?? startText;
  const startMinutes = parseClockToMinutes(startText);
  const label = `${startText} - ${endText}`;
  return { key: label, label, startMinutes };
}

function formatExportDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value.trim());
  if (!match) return value;
  return `${match[3]}-${match[2]}-${match[1]}`;
}

function getMeridiemLabel(slot: ExportSlot): "AM" | "PM" {
  return slot.startMinutes < 12 * 60 ? "AM" : "PM";
}

function buildTimingSummary(groups: ExportDateGroup[]): string {
  const hasExpandedDays = groups.some((group) => !group.usesMeridiemColumns);
  const labels = hasExpandedDays
    ? Array.from(new Set(groups.flatMap((group) => group.slots.map((slot) => slot.label))))
    : [
        ...Array.from(
          new Set(
            groups.flatMap((group) => group.slots.filter((slot) => getMeridiemLabel(slot) === "AM").map((slot) => slot.label)),
          ),
        ),
        ...Array.from(
          new Set(
            groups.flatMap((group) => group.slots.filter((slot) => getMeridiemLabel(slot) === "PM").map((slot) => slot.label)),
          ),
        ),
      ];
  return labels.map((label) => `(${label})`).join(" & ");
}

function buildExactInputRange(item: BulkFacultyAvailabilityItem): ExportSlot {
  const start = item.startTime?.trim() ?? "";
  const end = item.endTime?.trim() ?? "";
  if (start && end) {
    return {
      key: `${start}__${end}`,
      label: `${start} - ${end}`,
      startMinutes: parseClockToMinutes(start),
    };
  }
  return buildSessionRange(item.periods);
}

function buildExportDateGroups(items: BulkFacultyAvailabilityItem[]): ExportDateGroup[] {
  const slotsByDate = new Map<string, ExportSlot[]>();

  for (const item of items) {
    const slot = buildExactInputRange(item);
    const existing = slotsByDate.get(item.date) ?? [];
    if (!existing.some((entry) => entry.key === slot.key)) {
      existing.push(slot);
      slotsByDate.set(item.date, existing);
    }
  }

  return Array.from(slotsByDate.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([date, slots]) => {
      const orderedSlots = [...slots].sort((left, right) => left.startMinutes - right.startMinutes || left.label.localeCompare(right.label));
      const usesMeridiemColumns = orderedSlots.length <= 2;
      return {
        date,
        headerDate: formatExportDate(date),
        slots: usesMeridiemColumns
          ? [
              orderedSlots.find((slot) => getMeridiemLabel(slot) === "AM") ?? { key: "__fn__", label: "FN", startMinutes: 0 },
              orderedSlots.find((slot) => getMeridiemLabel(slot) === "PM") ?? { key: "__an__", label: "AN", startMinutes: 12 * 60 },
            ]
          : orderedSlots,
        usesMeridiemColumns,
      };
    });
}

function getFacultyNamesForMode(item: BulkFacultyAvailabilityItem, mode: ExportMode): string[] {
  const source = mode === "selected"
    ? (item.faculty ?? [])
    : (item.availableFaculty ?? []);
  return source
    .map((facultyName) => facultyName.trim())
    .filter(Boolean);
}

function buildInvigilationWorkbook(items: BulkFacultyAvailabilityItem[], mode: ExportMode) {
  const workbook = XLSX.utils.book_new();
  const groups = buildExportDateGroups(items);
  const facultyNames = Array.from(
    new Set(items.flatMap((item) => getFacultyNamesForMode(item, mode))),
  ).sort((left, right) => left.localeCompare(right));

  const totalColumns = 3 + groups.reduce((sum, group) => sum + group.slots.length, 0);
  const data: (string | number)[][] = [];
  const merges: XLSX.Range[] = [];
  const padRow = (values: (string | number)[]) => [
    ...values,
    ...Array.from({ length: Math.max(0, totalColumns - values.length) }, () => ""),
  ];

  const departmentShortName = ACADEMIC_METADATA.DEPARTMENT_NAME.includes("Computer Science") ? "CSE" : "Department";
  data.push(padRow([departmentShortName, "", "", buildTimingSummary(groups)]));
  data.push(padRow(["S.No", "Faculty Name", "Total"]));
  data.push(padRow(["", "", ""]));

  let columnCursor = 3;
  for (const group of groups) {
    data[1][columnCursor] = group.headerDate;
    for (let slotIndex = 0; slotIndex < group.slots.length; slotIndex += 1) {
      data[2][columnCursor + slotIndex] = group.usesMeridiemColumns ? (slotIndex === 0 ? "FN" : "AN") : group.slots[slotIndex].label;
    }
    merges.push({ s: { r: 1, c: columnCursor }, e: { r: 1, c: columnCursor + group.slots.length - 1 } });
    columnCursor += group.slots.length;
  }
  merges.push({ s: { r: 0, c: 0 }, e: { r: 2, c: 0 } });
  merges.push({ s: { r: 0, c: 1 }, e: { r: 2, c: 1 } });
  merges.push({ s: { r: 0, c: 2 }, e: { r: 2, c: 2 } });
  if (totalColumns > 3) {
    merges.push({ s: { r: 0, c: 3 }, e: { r: 0, c: totalColumns - 1 } });
  }

  const slotColumnMap = new Map<string, number>();
  columnCursor = 3;
  for (const group of groups) {
    for (let slotIndex = 0; slotIndex < group.slots.length; slotIndex += 1) {
      const slot = group.slots[slotIndex];
      const mapKey = group.usesMeridiemColumns ? `${group.date}__${slotIndex === 0 ? "AM" : "PM"}` : `${group.date}__${slot.key}`;
      slotColumnMap.set(mapKey, columnCursor);
      columnCursor += 1;
    }
  }

  const facultyTotals = new Map<string, number>();
  for (const item of items) {
    for (const facultyName of getFacultyNamesForMode(item, mode)) {
      facultyTotals.set(facultyName, (facultyTotals.get(facultyName) ?? 0) + 1);
    }
  }

  facultyNames.forEach((facultyName, index) => {
    data.push(padRow([index + 1, facultyName, facultyTotals.get(facultyName) ?? 0]));
  });

  const facultyRowMap = new Map<string, number>();
  facultyNames.forEach((facultyName, index) => {
    facultyRowMap.set(facultyName, index + 3);
  });

  const slotTotals = new Map<number, number>();
  for (const item of items) {
    const slot = buildExactInputRange(item);
    const group = groups.find((entry) => entry.date === item.date);
    if (!group) continue;
    const lookupKey = group.usesMeridiemColumns ? `${item.date}__${getMeridiemLabel(slot)}` : `${item.date}__${slot.key}`;
    const columnIndex = slotColumnMap.get(lookupKey);
    if (columnIndex === undefined) continue;
    const currentNames = getFacultyNamesForMode(item, mode);
    slotTotals.set(columnIndex, currentNames.length);
    for (const facultyName of currentNames) {
      const rowIndex = facultyRowMap.get(facultyName.trim());
      if (rowIndex === undefined) continue;
      data[rowIndex][columnIndex] = "X";
    }
  }

  const totalRow = padRow(["", "Total", Array.from(slotTotals.values()).reduce((sum, value) => sum + value, 0)]);
  for (const [columnIndex, total] of slotTotals.entries()) {
    totalRow[columnIndex] = total;
  }
  data.push(totalRow);

  const worksheet = XLSX.utils.aoa_to_sheet(data);
  worksheet["!merges"] = merges;
  worksheet["!cols"] = [
    { wch: 8 },
    { wch: 30 },
    { wch: 12 },
    ...groups.flatMap((group) => group.slots.map((slot, index) => ({ wch: Math.max(12, (group.usesMeridiemColumns ? (index === 0 ? "FN" : "AN") : slot.label).length + 2) }))),
  ];
  worksheet["!rows"] = [{ hpt: 28 }, { hpt: 24 }, { hpt: 24 }, ...facultyNames.map(() => ({ hpt: 21 })), { hpt: 22 }];

  const sheetRange = XLSX.utils.decode_range(worksheet["!ref"] ?? `A1:${XLSX.utils.encode_cell({ r: data.length - 1, c: totalColumns - 1 })}`);
  for (let rowIndex = sheetRange.s.r; rowIndex <= sheetRange.e.r; rowIndex += 1) {
    for (let columnIndex = sheetRange.s.c; columnIndex <= sheetRange.e.c; columnIndex += 1) {
      const cellAddress = XLSX.utils.encode_cell({ r: rowIndex, c: columnIndex });
      if (!worksheet[cellAddress]) {
        worksheet[cellAddress] = { t: "s", v: "" };
      }
      worksheet[cellAddress].s = {
        alignment: {
          horizontal: "center",
          vertical: "center",
          wrapText: true,
        },
        border: {
          top: { style: "thin", color: { rgb: "000000" } },
          bottom: { style: "thin", color: { rgb: "000000" } },
          left: { style: "thin", color: { rgb: "000000" } },
          right: { style: "thin", color: { rgb: "000000" } },
        },
        font: {
          bold: rowIndex <= 2 || rowIndex === data.length - 1,
          name: "Calibri",
          sz: 11,
        },
      };
    }
  }

  XLSX.utils.book_append_sheet(workbook, worksheet, mode === "selected" ? "Fair Selection" : "All Available");
  return workbook;
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

function normalizeText(value: string): string {
  return value.trim().toLowerCase();
}

function parseIgnoredSections(value: string): string[] {
  return value.split(/[\n,]+/).map((item) => item.trim()).filter(Boolean);
}

function getFacultyCoverageTag(item: BulkFacultyAvailabilityItem) {
  if (item.sufficientFaculty) return { label: "Sufficient faculty", className: "bg-emerald-100 text-emerald-700 border-emerald-200" };
  if (item.availableFacultyCount > 0) return { label: "Insufficient faculty", className: "bg-amber-100 text-amber-700 border-amber-200" };
  return { label: "No faculty available", className: "bg-rose-100 text-rose-700 border-rose-200" };
}

function EmptyState() {
  return (
    <div className="rounded-[28px] border border-border/60 bg-card p-8 shadow-sm">
      <div className="flex min-h-[500px] flex-col items-center justify-center rounded-[24px] border border-dashed border-border/70 bg-[radial-gradient(circle_at_top,rgba(14,165,233,0.08),transparent_45%),linear-gradient(180deg,rgba(248,250,252,0.92),rgba(241,245,249,0.8))] px-6 text-center">
        <div className="rounded-3xl bg-primary/10 p-5 text-primary"><Users className="h-10 w-10" /></div>
        <h3 className="mt-6 text-xl font-semibold text-foreground">No report generated yet</h3>
        <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">Upload the faculty workload file and the query file, then generate the report to see fair faculty selections, shortage details, and Excel export.</p>
      </div>
    </div>
  );
}

const FacultyAvailability = () => {
  const config = useMemo(() => readAcademicConfig(), []);
  const yearOptions = useMemo(() => config.activeYears ?? [], [config]);

  const [ignoredYears, setIgnoredYears] = useState<string[]>([]);
  const [ignoredSectionsInput, setIgnoredSectionsInput] = useState("");
  const [availabilityFile, setAvailabilityFile] = useState<File | null>(null);
  const [availabilityFileId, setAvailabilityFileId] = useState("");
  const [queryFile, setQueryFile] = useState<File | null>(null);
  const [queryFileId, setQueryFileId] = useState("");
  const [results, setResults] = useState<BulkFacultyAvailabilityItem[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [resultSearch, setResultSearch] = useState("");
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({});
  const templateBase = `${API_BASE_URL}/templates`;

  const toggleRow = (rowKey: string) => {
    setExpandedRows((prev) => ({ ...prev, [rowKey]: !prev[rowKey] }));
  };

  const ignoredSections = useMemo(() => parseIgnoredSections(ignoredSectionsInput), [ignoredSectionsInput]);

  const filteredResults = useMemo(() => {
    if (!results) return [];
    const query = normalizeText(resultSearch);
    if (!query) return results;
    return results.filter((item) =>
      [item.date, item.day, item.faculty.join(" "), item.message, formatPeriods(item.periods), String(item.facultyRequired), String(item.availableFacultyCount)]
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  }, [resultSearch, results]);

  const summaryStats = useMemo<SummaryStat[]>(() => {
    if (!results || results.length === 0) {
      return [
        { label: "Requests", value: 0, hint: "Rows returned from the bulk query", tone: "bg-sky-100 text-sky-700" },
        { label: "Sufficient", value: 0, hint: "Rows where requirement was satisfied", tone: "bg-emerald-100 text-emerald-700" },
        { label: "Insufficient", value: 0, hint: "Rows where enough faculty were not found", tone: "bg-amber-100 text-amber-700" },
        { label: "Available", value: 0, hint: "Total selected faculty across all rows", tone: "bg-indigo-100 text-indigo-700" },
      ];
    }
    const sufficient = results.filter((item) => item.sufficientFaculty).length;
    const insufficient = results.length - sufficient;
    const totalChosen = results.reduce((sum, item) => sum + item.faculty.length, 0);
    return [
      { label: "Requests", value: results.length, hint: "Rows returned from the bulk query", tone: "bg-sky-100 text-sky-700" },
      { label: "Sufficient", value: sufficient, hint: "Rows where requirement was satisfied", tone: "bg-emerald-100 text-emerald-700" },
      { label: "Insufficient", value: insufficient, hint: "Rows where enough faculty were not found", tone: "bg-amber-100 text-amber-700" },
      { label: "Available", value: totalChosen, hint: "Total selected faculty across all rows", tone: "bg-indigo-100 text-indigo-700" },
    ];
  }, [results]);

  const toggleIgnoreYear = (year: string) => {
    setIgnoredYears((previous) => previous.includes(year) ? previous.filter((value) => value !== year) : [...previous, year]);
  };

  const clearFilters = () => {
    setIgnoredYears([]);
    setIgnoredSectionsInput("");
  };

  const handleAvailabilityUpload = async (file: File) => {
    setAvailabilityFile(file);
    try {
      const response = await uploadFacultyAvailability(file);
      setAvailabilityFileId(response.fileId);
      toast.success(`Uploaded "${file.name}" successfully.`);
    } catch (error) {
      setAvailabilityFileId("");
      toast.error(error instanceof Error ? error.message : "Upload failed");
    }
  };

  const handleQueryUpload = async (file: File) => {
    setQueryFile(file);
    try {
      const response = await uploadFacultyAvailabilityQuery(file);
      setQueryFileId(response.fileId);
      toast.success(`Uploaded "${file.name}" successfully.`);
    } catch (error) {
      setQueryFileId("");
      toast.error(error instanceof Error ? error.message : "Query upload failed");
    }
  };

  const handleSearch = async () => {
    if (!availabilityFileId || !queryFileId) {
      toast.error("Please upload both the faculty workload file and query file.");
      return;
    }
    try {
      setSearching(true);
      const response = await getBulkFacultyAvailability({ availabilityFileId, queryFileId, ignoredYears, ignoredSections });
      setResults(response.results);
      setResultSearch("");
      toast.success("Invisilation report generated.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to fetch invisilation report");
    } finally {
      setSearching(false);
    }
  };

  const handleDownloadReport = () => {
    if (!results || results.length === 0 || !availabilityFileId || !queryFileId) {
      toast.error("Generate a report before downloading.");
      return;
    }
    exportBulkFacultyAvailabilityReport({ availabilityFileId, queryFileId, ignoredYears, ignoredSections })
      .then((file) => {
        downloadGeneratedWorkbook(file);
      })
      .catch((error) => {
        toast.error(error instanceof Error ? error.message : "Failed to download report");
      });
  };

  return (
    <DashboardLayout>
      <div className="w-full space-y-6">
        {/* Clean Hero Header */}
        <div className="hero-shell">
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-primary shadow-sm">
              <Sparkles className="h-3.5 w-3.5" />
              Invisilation finder
            </div>
            <div className="space-y-2">
              <h1 className="text-3xl font-bold tracking-tight text-foreground">Invisilation Finder</h1>
              <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
                Upload the faculty workload workbook and the bulk query file to find available faculty for each requested date and period with fair rotation and clear shortage reporting for invisilation planning.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-3 max-w-4xl">
              <div className="rounded-2xl border border-border/70 bg-card/80 p-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <FileSpreadsheet className="h-4 w-4 text-primary" />
                  Workload Upload
                </div>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  Upload the faculty workbook with all faculty workload sheets in single or stacked layouts.
                </p>
              </div>
              <div className="rounded-2xl border border-border/70 bg-card/80 p-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <CalendarDays className="h-4 w-4 text-primary" />
                  Query Upload
                </div>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  Upload the request query file containing dates, required counts, and periods.
                </p>
              </div>
              <div className="rounded-2xl border border-border/70 bg-card/80 p-4">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <Users className="h-4 w-4 text-primary" />
                  Fair Selection
                </div>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">
                  Review balanced faculty picks, available counts, and shortages in one place.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Configuration Grid */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          {/* Upload Center */}
          <div className="lg:col-span-7 space-y-6">
            <div className="panel-card h-full flex flex-col justify-between">
              <div>
                <div className="mb-6 flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-semibold text-foreground">Upload Center</h2>
                    <p className="text-sm text-muted-foreground">Add both required files to configure the invisilation finder.</p>
                  </div>
                  <div className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${availabilityFileId && queryFileId ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>
                    <span className={`h-2 w-2 rounded-full ${availabilityFileId && queryFileId ? "bg-emerald-500 animate-pulse" : "bg-amber-500"}`} />
                    {availabilityFileId && queryFileId ? "Ready to generate" : "Waiting for uploads"}
                  </div>
                </div>

                <div className="grid gap-5 sm:grid-cols-2">
                  {/* Faculty Workload Card */}
                  <div className="flex flex-col justify-between rounded-[24px] border border-border/70 bg-muted/20 p-4">
                    <div>
                      <div className="mb-4 flex items-center justify-between">
                        <h3 className="text-sm font-semibold text-foreground">Faculty Workload</h3>
                        {availabilityFileId ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-100">
                            <Check className="h-3 w-3" /> Uploaded
                          </span>
                        ) : (
                          <span className="text-[11px] text-muted-foreground">Pending</span>
                        )}
                      </div>
                      <FileUpload
                        file={availabilityFile}
                        onFileSelect={handleAvailabilityUpload}
                        onClear={() => {
                          setAvailabilityFile(null);
                          setAvailabilityFileId("");
                        }}
                        accept=".xlsx,.xls,.csv"
                        label="Upload workload file"
                        description="Supports single or stacked workload workbook layouts"
                        icon={<FileSpreadsheet className="h-7 w-7 text-primary" />}
                      />
                    </div>
                    {availabilityFile && (
                      <p className="mt-3 truncate text-xs text-muted-foreground font-mono bg-white/60 p-1.5 rounded border border-border/50">
                        {availabilityFile.name}
                      </p>
                    )}
                  </div>

                  {/* Query File Card */}
                  <div className="flex flex-col justify-between rounded-[24px] border border-border/70 bg-muted/20 p-4">
                    <div>
                      <div className="mb-4 flex items-center justify-between">
                        <h3 className="text-sm font-semibold text-foreground">Query File</h3>
                        {queryFileId ? (
                          <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-100">
                            <Check className="h-3 w-3" /> Uploaded
                          </span>
                        ) : (
                          <span className="text-[11px] text-muted-foreground">Pending</span>
                        )}
                      </div>
                      <FileUpload
                        file={queryFile}
                        onFileSelect={handleQueryUpload}
                        onClear={() => {
                          setQueryFile(null);
                          setQueryFileId("");
                        }}
                        accept=".xlsx,.xls,.csv"
                        label="Upload query file"
                        description="Date, Faculty Required, Periods"
                        icon={<CalendarDays className="h-7 w-7 text-primary" />}
                        templateLinks={buildTemplateLinks(templateBase, "faculty-availability-query")}
                      />
                    </div>
                    {queryFile && (
                      <p className="mt-3 truncate text-xs text-muted-foreground font-mono bg-white/60 p-1.5 rounded border border-border/50">
                        {queryFile.name}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Ignore Rules & Action */}
          <div className="lg:col-span-5 space-y-6">
            <div className="panel-card flex flex-col justify-between h-full">
              <div>
                <div className="mb-6 flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-semibold text-foreground">Ignore Rules & Filters</h2>
                    <p className="text-sm text-muted-foreground">Exclude busy slots from availability checks.</p>
                  </div>
                  {(ignoredYears.length > 0 || ignoredSections.length > 0) && (
                    <Button variant="ghost" size="sm" onClick={clearFilters} className="text-xs text-muted-foreground hover:text-foreground">
                      Reset
                    </Button>
                  )}
                </div>

                <div className="space-y-4">
                  <div>
                    <Label className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Ignore Entire Year</Label>
                    <div className="flex flex-wrap gap-2">
                      {yearOptions.map((year) => (
                        <label key={year} className={`flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-1.5 text-xs text-foreground transition-all ${ignoredYears.includes(year) ? "border-primary/50 bg-primary/5 font-medium text-primary shadow-sm" : "border-border/70 bg-card hover:border-border-hover"}`}>
                          <Checkbox checked={ignoredYears.includes(year)} onCheckedChange={() => toggleIgnoreYear(year)} className="h-3.5 w-3.5" />
                          <span>{year}</span>
                        </label>
                      ))}
                    </div>
                  </div>

                  <div>
                    <Label className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Ignore Specific Sections</Label>
                    <Input
                      value={ignoredSectionsInput}
                      onChange={(event) => setIgnoredSectionsInput(event.target.value)}
                      placeholder="e.g. 2C3, 2G4, 3C2"
                      className="rounded-xl h-10 text-xs"
                    />
                    <p className="mt-1 text-[11px] leading-4 text-muted-foreground">
                      Separate section names by commas or spaces.
                    </p>
                  </div>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-border/40">
                <Button onClick={handleSearch} className="h-11 w-full gap-2 text-sm font-semibold shadow-sm" disabled={searching || !availabilityFileId || !queryFileId}>
                  {searching ? (
                    <>
                      <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
                      Generating Report...
                    </>
                  ) : (
                    <>
                      <Search className="h-4 w-4" />
                      Generate Report
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Supported Periods Collapsible */}
        <details className="group rounded-2xl border border-border/60 bg-muted/10 p-4 transition-all">
          <summary className="flex cursor-pointer items-center justify-between text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground select-none">
            <span className="flex items-center gap-2">
              <Clock3 className="h-4 w-4 text-primary" />
              View Department Period Reference Timings ({actualPeriods.length} Periods)
            </span>
            <span className="transition-transform duration-200 group-open:rotate-180">
              <ChevronDown className="h-4 w-4" />
            </span>
          </summary>
          <div className="mt-4 grid gap-3 grid-cols-2 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8">
            {actualPeriods.map((period) => (
              <div key={period.period} className="rounded-xl border border-border/50 bg-white p-2.5 text-center shadow-sm">
                <div className="text-xs font-bold text-foreground">P{period.period}</div>
                <div className="mt-0.5 text-[10px] text-muted-foreground whitespace-nowrap">{period.time}</div>
              </div>
            ))}
          </div>
        </details>

        {/* Results / Empty State */}
        {results ? (
          <div className="space-y-6">
            {/* Summary Statistics Panel */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {summaryStats.map((stat) => (
                <div key={stat.label} className="stat-card border border-border/60 shadow-sm rounded-2xl p-4 bg-white hover:shadow-md transition-all">
                  <div className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${stat.tone}`}>{stat.label}</div>
                  <p className="mt-3 text-3xl font-extrabold text-foreground">{stat.value}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{stat.hint}</p>
                </div>
              ))}
            </div>

            {/* Results Table Panel */}
            <div className="panel-card">
              <div className="border-b border-border/70 pb-5">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-semibold text-foreground">Availability Reports</h2>
                    <p className="text-sm text-muted-foreground">Fair selection rotates available faculty as evenly as possible across the bulk report.</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <div className="relative w-full sm:w-72">
                      <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                      <Input
                        value={resultSearch}
                        onChange={(event) => setResultSearch(event.target.value)}
                        placeholder="Search by date, faculty, or status..."
                        className="pl-9 pr-4 rounded-xl h-10 text-sm"
                      />
                    </div>
                    <Button onClick={handleDownloadReport} variant="secondary" className="gap-2 rounded-xl h-10 shadow-sm">
                      <Download className="h-4 w-4" />
                      Download Report
                    </Button>
                  </div>
                </div>
              </div>

              {filteredResults.length > 0 ? (
                <div className="mt-6 overflow-x-auto rounded-xl border border-border/60">
                  <table className="w-full border-collapse text-left text-sm">
                    <thead className="bg-muted/40 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      <tr>
                        <th className="px-5 py-4 border-b border-border/60">Date & Day</th>
                        <th className="px-5 py-4 border-b border-border/60">Periods Checked</th>
                        <th className="px-5 py-4 border-b border-border/60 text-center">Required</th>
                        <th className="px-5 py-4 border-b border-border/60 text-center">Available</th>
                        <th className="px-5 py-4 border-b border-border/60 text-center">Shortage</th>
                        <th className="px-5 py-4 border-b border-border/60">Coverage Status</th>
                        <th className="px-5 py-4 border-b border-border/60 text-right">Details</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {filteredResults.map((item, index) => {
                        const rowKey = `${item.date}-${item.day}-${index}`;
                        const isExpanded = !!expandedRows[rowKey];
                        const coverage = getFacultyCoverageTag(item);
                        const hasShortage = item.shortageCount > 0;
                        return (
                          <>
                            <tr
                              key={rowKey}
                              onClick={() => toggleRow(rowKey)}
                              className={`cursor-pointer hover:bg-muted/10 transition-colors ${isExpanded ? "bg-muted/5" : ""}`}
                            >
                              <td className="px-5 py-4 font-semibold text-foreground whitespace-nowrap">
                                <div>{item.date}</div>
                                <div className="text-xs font-normal text-muted-foreground">{item.day}</div>
                              </td>
                              <td className="px-5 py-4 whitespace-nowrap">
                                <span className="inline-flex flex-wrap gap-1 max-w-[200px]">
                                  {item.periods.map((p) => (
                                    <span key={p.period} className="rounded bg-secondary/60 px-1.5 py-0.5 text-xs text-secondary-foreground font-medium">
                                      P{p.period}
                                    </span>
                                  ))}
                                </span>
                              </td>
                              <td className="px-5 py-4 text-center font-medium text-foreground">{item.facultyRequired}</td>
                              <td className="px-5 py-4 text-center font-medium text-foreground">{item.availableFacultyCount}</td>
                              <td className={`px-5 py-4 text-center font-bold ${hasShortage ? "text-destructive" : "text-emerald-600"}`}>
                                {item.shortageCount}
                              </td>
                              <td className="px-5 py-4 whitespace-nowrap">
                                <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${coverage.className}`}>
                                  {coverage.label}
                                </span>
                              </td>
                              <td className="px-5 py-4 text-right">
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-8 w-8 rounded-lg"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    toggleRow(rowKey);
                                  }}
                                >
                                  {isExpanded ? (
                                    <ChevronUp className="h-4 w-4 text-muted-foreground" />
                                  ) : (
                                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                                  )}
                                </Button>
                              </td>
                            </tr>
                            {isExpanded && (
                              <tr className="bg-muted/10">
                                <td colSpan={7} className="px-6 py-5 border-t border-border/40">
                                  <div className="grid gap-6 md:grid-cols-12">
                                    <div className="md:col-span-4 space-y-4">
                                      <div>
                                        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Periods Details</h4>
                                        <div className="mt-2 space-y-1.5">
                                          {item.periods.map((p) => (
                                            <div key={p.period} className="flex items-center gap-2 text-xs text-foreground bg-white/60 p-1.5 rounded-lg border border-border/50">
                                              <span className="font-bold text-primary">P{p.period}</span>
                                              <span className="text-muted-foreground">|</span>
                                              <span>{p.time}</span>
                                            </div>
                                          ))}
                                        </div>
                                      </div>

                                      <div className={`rounded-xl border p-3.5 text-xs ${item.sufficientFaculty ? "border-emerald-200 bg-emerald-50/50 text-emerald-800" : "border-amber-200 bg-amber-50/50 text-amber-800"}`}>
                                        <div className="flex items-start gap-2">
                                          {item.sufficientFaculty ? (
                                            <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600 flex-shrink-0" />
                                          ) : (
                                            <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-600 flex-shrink-0" />
                                          )}
                                          <p className="leading-relaxed">{item.message}</p>
                                        </div>
                                      </div>
                                    </div>

                                    <div className="md:col-span-8 space-y-4">
                                      <div>
                                        <div className="flex items-center gap-2 mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                          <Users className="h-3.5 w-3.5 text-primary" />
                                          Selected Faculty for Rotation ({item.faculty.length})
                                        </div>
                                        {item.faculty.length > 0 ? (
                                          <div className="flex flex-wrap gap-2 p-3 bg-white/60 rounded-xl border border-border/50">
                                            {item.faculty.map((facultyName) => (
                                              <span key={facultyName} className="inline-flex items-center gap-1.5 rounded-lg bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary border border-primary/20">
                                                <span className="h-1.5 w-1.5 rounded-full bg-primary" />
                                                {facultyName}
                                              </span>
                                            ))}
                                          </div>
                                        ) : (
                                          <div className="flex items-center gap-2 text-xs text-muted-foreground p-3 bg-white/60 rounded-xl border border-border/50">
                                            <XCircle className="h-4 w-4 text-destructive" />
                                            No faculty members could be selected.
                                          </div>
                                        )}
                                      </div>

                                      <div>
                                        <div className="flex items-center gap-2 mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                          <Info className="h-3.5 w-3.5 text-muted-foreground" />
                                          Other Free Faculty (Backups/Alternatives: {item.availableFaculty.length})
                                        </div>
                                        {item.availableFaculty.length > 0 ? (
                                          <div className="flex flex-wrap gap-2 p-3 bg-white/40 rounded-xl border border-border/40">
                                            {item.availableFaculty.map((facultyName) => {
                                              const isSelected = item.faculty.includes(facultyName);
                                              return (
                                                <span
                                                  key={facultyName}
                                                  className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs ${
                                                    isSelected
                                                      ? "bg-muted/80 text-muted-foreground/60 line-through decoration-muted-foreground/30"
                                                      : "bg-muted/60 text-foreground border border-border/50 hover:bg-muted transition-colors"
                                                  }`}
                                                  title={isSelected ? "Selected in the current schedule" : "Available backup"}
                                                >
                                                  {facultyName}
                                                </span>
                                              );
                                            })}
                                          </div>
                                        ) : (
                                          <div className="text-xs text-muted-foreground p-3 bg-white/40 rounded-xl border border-border/40">
                                            No alternative faculty members are available during this slot.
                                          </div>
                                        )}
                                      </div>
                                    </div>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground mt-6">
                  No results matched your search term.
                </div>
              )}
            </div>
          </div>
        ) : (
          <EmptyState />
        )}
      </div>
    </DashboardLayout>
  );
};

export default FacultyAvailability;
