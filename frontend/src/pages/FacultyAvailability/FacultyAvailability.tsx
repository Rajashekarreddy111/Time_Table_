import { useMemo, useState } from "react";
import { AlertTriangle, CalendarDays, CheckCircle2, Clock3, Download, FileSpreadsheet, Search, Sparkles, Upload, Users, XCircle } from "lucide-react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { FileUpload } from "@/components/FileUpload";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { PERIODS } from "@/data/mockData";
import { readAcademicConfig } from "@/lib/academicConfig";
import { API_BASE_URL, type BulkFacultyAvailabilityItem, getBulkFacultyAvailability, uploadFacultyAvailability, uploadFacultyAvailabilityQuery } from "@/services/apiClient";
import { toast } from "sonner";

type PeriodInfo = { period: number; time: string };
type SummaryStat = { label: string; value: string | number; hint: string; tone: string };

const actualPeriods: PeriodInfo[] = PERIODS.filter(
  (item): item is { period: number; time: string } => typeof item.period === "number",
).map((item) => ({ period: item.period, time: item.time.replace(/â€“|Ã¢â‚¬â€œ|ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“/g, "-") }));

function escapeCsv(value: string | number | boolean): string {
  const stringValue = String(value ?? "");
  return `"${stringValue.replace(/"/g, '""')}"`;
}

function formatPeriods(periods: PeriodInfo[]): string {
  return periods.map((period) => `P${period.period}`).join(", ");
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
        <p className="mt-3 max-w-md text-sm leading-6 text-muted-foreground">Upload the faculty workload file and the query file, then generate the report to see fair faculty selections, shortage details, and CSV export.</p>
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
  const templateBase = `${API_BASE_URL}/templates`;

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

  const handleDownloadCsv = () => {
    if (!results || results.length === 0) {
      toast.error("Generate a report before downloading.");
      return;
    }
    const headers = ["Date", "Day", "Periods", "Period Times", "Faculty Required", "Faculty Available", "Selected Faculty", "Sufficient Faculty", "Shortage Count", "Status Message"];
    const rows = results.map((item) => [
      escapeCsv(item.date),
      escapeCsv(item.day),
      escapeCsv(formatPeriods(item.periods)),
      escapeCsv(item.periods.map((period) => period.time).join(", ")),
      escapeCsv(item.facultyRequired),
      escapeCsv(item.availableFacultyCount),
      escapeCsv(item.faculty.join(" | ")),
      escapeCsv(item.sufficientFaculty),
      escapeCsv(item.shortageCount),
      escapeCsv(item.message),
    ].join(","));
    const csvContent = [headers.join(","), ...rows].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "invisilation_finder_report.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <DashboardLayout>
      <div className="w-full space-y-6">
        <div className="rounded-[30px] border border-border/70 bg-[linear-gradient(135deg,rgba(2,132,199,0.10),rgba(30,41,59,0.05),rgba(255,255,255,0.94))] p-6 shadow-sm">
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)] xl:items-end">
            <div className="space-y-4">
              <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-primary shadow-sm"><Sparkles className="h-3.5 w-3.5" />Invisilation finder</div>
              <div className="space-y-2">
                <h1 className="text-3xl font-bold tracking-tight text-foreground">Invisilation Finder</h1>
                <p className="max-w-2xl text-sm leading-6 text-muted-foreground">Upload the faculty workload workbook and the bulk query file to find available faculty for each requested date and period with fair rotation and clear shortage reporting for invisilation planning.</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-2xl border border-border/70 bg-card/80 p-4"><div className="flex items-center gap-2 text-sm font-semibold text-foreground"><FileSpreadsheet className="h-4 w-4 text-primary" />Workload Upload</div><p className="mt-2 text-xs leading-5 text-muted-foreground">Upload the faculty workbook with all faculty sheets in the same format you already use.</p></div>
                <div className="rounded-2xl border border-border/70 bg-card/80 p-4"><div className="flex items-center gap-2 text-sm font-semibold text-foreground"><CalendarDays className="h-4 w-4 text-primary" />Query Upload</div><p className="mt-2 text-xs leading-5 text-muted-foreground">Upload the request file containing date, faculty count, and periods to check.</p></div>
                <div className="rounded-2xl border border-border/70 bg-card/80 p-4"><div className="flex items-center gap-2 text-sm font-semibold text-foreground"><Users className="h-4 w-4 text-primary" />Fair Selection</div><p className="mt-2 text-xs leading-5 text-muted-foreground">Review balanced faculty picks, available counts, and shortages in one place.</p></div>
              </div>
            </div>

            <div className="rounded-[26px] border border-border/70 bg-card/90 p-5 shadow-sm">
              <div className="flex items-center gap-3">
                <div className="rounded-2xl bg-primary/10 p-3 text-primary"><Clock3 className="h-5 w-5" /></div>
                <div><h2 className="text-sm font-semibold text-foreground">Report readiness</h2><p className="text-xs text-muted-foreground">The button enables after both uploads succeed.</p></div>
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-border/60 bg-muted/30 p-4"><p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Workload file</p><p className="mt-2 text-sm font-semibold text-foreground">{availabilityFileId ? "Uploaded" : "Pending"}</p><p className="mt-1 text-xs text-muted-foreground">{availabilityFile?.name ?? "Upload the faculty workbook"}</p></div>
                <div className="rounded-2xl border border-border/60 bg-muted/30 p-4"><p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Query file</p><p className="mt-2 text-sm font-semibold text-foreground">{queryFileId ? "Uploaded" : "Pending"}</p><p className="mt-1 text-xs text-muted-foreground">{queryFile?.name ?? "Upload the query workbook"}</p></div>
              </div>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-6 2xl:grid-cols-[minmax(0,1.02fr)_minmax(0,0.98fr)]">
          <div className="space-y-6">
            <div className="rounded-[28px] border border-border/60 bg-card p-6 shadow-sm">
              <div className="mb-6 flex items-start justify-between gap-4">
                <div><h2 className="text-lg font-semibold text-foreground">Upload Center</h2><p className="text-sm text-muted-foreground">Add both files here, then generate the invisilation report.</p></div>
                <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary"><Upload className="h-3.5 w-3.5" />{availabilityFileId && queryFileId ? "Ready to generate" : "Waiting for uploads"}</div>
              </div>
              <div className="grid gap-5 xl:grid-cols-2">
                <div className="rounded-[24px] border border-border/70 bg-muted/20 p-4">
                  <div className="mb-4"><h3 className="text-base font-semibold text-foreground">Faculty workload upload</h3><p className="mt-1 text-sm text-muted-foreground">Upload the workbook in the same faculty workload format used by your department.</p></div>
                  <FileUpload file={availabilityFile} onFileSelect={handleAvailabilityUpload} onClear={() => { setAvailabilityFile(null); setAvailabilityFileId(""); }} accept=".xlsx,.xls,.csv" label="Upload faculty workload file" description="Supports the multi-sheet workload workbook format" icon={<FileSpreadsheet className="h-9 w-9 text-primary" />} />
                  <p className="mt-3 text-xs text-muted-foreground">{availabilityFileId ? `Upload ID: ${availabilityFileId}` : "No faculty workload file uploaded yet."}</p>
                </div>
                <div className="rounded-[24px] border border-border/70 bg-muted/20 p-4">
                  <div className="mb-4 flex items-start justify-between gap-3">
                    <div><h3 className="text-base font-semibold text-foreground">Query file upload</h3><p className="mt-1 text-sm text-muted-foreground">Upload the file with date, required faculty, and period values.</p></div>
                    <Button variant="outline" size="sm" asChild className="gap-2"><a href={`${templateBase}/faculty-availability-query`} target="_blank" rel="noreferrer"><Download className="h-3.5 w-3.5" />Template</a></Button>
                  </div>
                  <FileUpload file={queryFile} onFileSelect={handleQueryUpload} onClear={() => { setQueryFile(null); setQueryFileId(""); }} accept=".xlsx,.xls,.csv" label="Upload query file" description="Contains Date, Number of Faculty Required, and Periods" icon={<CalendarDays className="h-9 w-9 text-primary" />} />
                  <p className="mt-3 text-xs text-muted-foreground">{queryFileId ? `Query ID: ${queryFileId}` : "No query file uploaded yet."}</p>
                </div>
              </div>
            </div>

            <div className="rounded-[28px] border border-border/60 bg-card p-6 shadow-sm">
              <div className="mb-6 flex items-start justify-between gap-4">
                <div><h2 className="text-lg font-semibold text-foreground">Ignore Rules</h2><p className="text-sm text-muted-foreground">Optional filters to treat selected loads as available while checking results.</p></div>
                <Button variant="outline" size="sm" onClick={clearFilters} disabled={ignoredYears.length === 0 && ignoredSections.length === 0}>Clear filters</Button>
              </div>
              <div className="space-y-5">
                <div className="rounded-[22px] border border-border/70 bg-muted/20 p-4">
                  <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Ignore entire year</p>
                  <div className="flex flex-wrap gap-2">
                    {yearOptions.map((year) => (
                      <label key={year} className="flex cursor-pointer items-center gap-2 rounded-full border border-border/70 bg-card px-3 py-2 text-sm text-foreground transition-colors hover:border-primary/40">
                        <Checkbox checked={ignoredYears.includes(year)} onCheckedChange={() => toggleIgnoreYear(year)} />
                        <span>{year}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <div className="rounded-[22px] border border-border/70 bg-muted/20 p-4">
                  <Label className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Ignore specific sections</Label>
                  <Textarea value={ignoredSectionsInput} onChange={(event) => setIgnoredSectionsInput(event.target.value)} placeholder={"Enter sections to ignore, separated by commas or new lines.\nExamples: 2C3, 2G4, 3C2, 3C5, 3G1"} className="min-h-28 rounded-2xl bg-card" />
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">Type sections as year plus section, like `2C3`, `2G4`, `3C2`, `3C5`, or `3G1`. Spaces after commas are also handled.</p>
                </div>
                {ignoredSections.length > 0 && (
                  <div className="rounded-[22px] border border-dashed border-border bg-muted/25 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Ignoring sections</p>
                    <div className="mt-3 flex flex-wrap gap-2">{ignoredSections.map((section) => <span key={section} className="rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">{section}</span>)}</div>
                  </div>
                )}
                <Button onClick={handleSearch} className="h-12 w-full gap-2 text-sm" disabled={searching || !availabilityFileId || !queryFileId}>
                  <Search className="h-4 w-4" />
                  {searching ? "Generating invisilation report..." : "Generate invisilation report"}
                </Button>
              </div>
            </div>

            <div className="rounded-[28px] border border-border/60 bg-card p-6 shadow-sm">
              <div className="mb-5 flex items-center gap-3"><div className="rounded-2xl bg-primary/10 p-3 text-primary"><CalendarDays className="h-5 w-5" /></div><div><h2 className="text-base font-semibold text-foreground">Supported periods</h2><p className="text-sm text-muted-foreground">Use these timetable period numbers in the query file.</p></div></div>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {actualPeriods.map((period) => (
                  <div key={period.period} className="rounded-2xl border border-border/70 bg-muted/20 px-4 py-3">
                    <div className="text-sm font-semibold text-foreground">Period {period.period}</div>
                    <div className="mt-1 text-xs text-muted-foreground">{period.time}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              {summaryStats.map((stat) => (
                <div key={stat.label} className="stat-card">
                  <div className={`inline-flex rounded-2xl px-3 py-1 text-xs font-semibold ${stat.tone}`}>{stat.label}</div>
                  <p className="mt-4 text-3xl font-bold text-foreground">{stat.value}</p>
                  <p className="mt-2 text-xs leading-5 text-muted-foreground">{stat.hint}</p>
                </div>
              ))}
            </div>

            {results ? (
              <div className="rounded-[28px] border border-border/60 bg-card p-6 shadow-sm">
                <div className="flex flex-col gap-4 border-b border-border/70 pb-5 lg:flex-row lg:items-end lg:justify-between">
                  <div><h2 className="text-lg font-semibold text-foreground">Availability results</h2><p className="text-sm text-muted-foreground">Fair selection rotates available faculty as evenly as possible across the bulk report.</p></div>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                    <div className="w-full sm:w-64"><Input value={resultSearch} onChange={(event) => setResultSearch(event.target.value)} placeholder="Search by date, faculty, or status" className="rounded-2xl" /></div>
                    <Button onClick={handleDownloadCsv} variant="secondary" className="gap-2"><Download className="h-4 w-4" />Download CSV</Button>
                  </div>
                </div>
                <div className="mt-5 space-y-4">
                  {filteredResults.length > 0 ? filteredResults.map((item, index) => {
                    const coverage = getFacultyCoverageTag(item);
                    return (
                      <div key={`${item.date}-${item.day}-${index}`} className="rounded-[24px] border border-border/70 bg-[linear-gradient(180deg,rgba(248,250,252,0.95),rgba(241,245,249,0.75))] p-5">
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                          <div className="space-y-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="text-lg font-semibold text-foreground">{item.date}</span>
                              <span className="rounded-full bg-secondary px-2.5 py-1 text-xs font-medium text-secondary-foreground">{item.day}</span>
                              <span className={`rounded-full border px-2.5 py-1 text-xs font-medium ${coverage.className}`}>{coverage.label}</span>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              {item.periods.map((period) => <span key={`${item.date}-${period.period}`} className="rounded-full border border-border/60 bg-white px-3 py-1 text-xs font-medium text-foreground">P{period.period} - {period.time}</span>)}
                            </div>
                          </div>
                          <div className="grid grid-cols-3 gap-2 lg:min-w-[330px]">
                            <div className="rounded-2xl border border-border/60 bg-white px-3 py-3"><p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Required</p><p className="mt-2 text-xl font-semibold text-foreground">{item.facultyRequired}</p></div>
                            <div className="rounded-2xl border border-border/60 bg-white px-3 py-3"><p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Available</p><p className="mt-2 text-xl font-semibold text-foreground">{item.availableFacultyCount}</p></div>
                            <div className="rounded-2xl border border-border/60 bg-white px-3 py-3"><p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Shortage</p><p className="mt-2 text-xl font-semibold text-foreground">{item.shortageCount}</p></div>
                          </div>
                        </div>
                        <div className={`mt-4 rounded-2xl border p-4 ${item.sufficientFaculty ? "border-emerald-200 bg-emerald-50/70" : "border-amber-200 bg-amber-50/70"}`}>
                          <div className="flex items-start gap-2 text-sm">
                            {item.sufficientFaculty ? <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-700" /> : <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-700" />}
                            <p className={item.sufficientFaculty ? "text-emerald-800" : "text-amber-800"}>{item.message}</p>
                          </div>
                        </div>
                        <div className="mt-4 rounded-2xl border border-border/60 bg-white p-4">
                          {item.faculty.length > 0 ? (
                            <div className="space-y-3">
                              <div className="flex items-center gap-2 text-sm font-medium text-foreground"><Users className="h-4 w-4 text-primary" />Selected faculty</div>
                              <div className="flex flex-wrap gap-2">{item.faculty.map((facultyName) => <span key={`${item.date}-${facultyName}`} className="rounded-full bg-primary/10 px-3 py-1.5 text-sm font-medium text-primary">{facultyName}</span>)}</div>
                            </div>
                          ) : (
                            <div className="flex items-center gap-2 text-sm text-muted-foreground"><XCircle className="h-4 w-4 text-destructive" />No faculty available for this request.</div>
                          )}
                        </div>
                      </div>
                    );
                  }) : <div className="rounded-2xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">No results matched your search term.</div>}
                </div>
              </div>
            ) : <EmptyState />}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
};

export default FacultyAvailability;
