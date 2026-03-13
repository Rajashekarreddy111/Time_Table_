import { useMemo, useState } from "react";
import { CalendarDays, Search, Upload, Users } from "lucide-react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { FileUpload } from "@/components/FileUpload";
import { PERIODS, DAYS } from "@/data/mockData";
import { toast } from "sonner";
import { API_BASE_URL } from "@/services/apiClient";
import {
  getBulkFacultyAvailability,
  uploadFacultyAvailability,
  uploadFacultyAvailabilityQuery,
  BulkFacultyAvailabilityItem
} from "@/services/apiClient";
import { getAllSectionKeys, readAcademicConfig } from "@/lib/academicConfig";

const actualPeriods = PERIODS.filter((p) => typeof p.period === "number") as { period: number; time: string }[];

const config = readAcademicConfig();
const ALL_YEAR_OPTIONS = Array.from(new Set(getAllSectionKeys(config).map((item) => item.year))).map((year) => ({
  label: year,
  value: year,
  type: "year" as const,
}));
const ALL_SECTION_OPTIONS: { label: string; value: string; type: "section" }[] = getAllSectionKeys(config).map((item) => ({
  label: `${item.year.replace(" Year", "")}${item.section}`,
  value: `${item.year}|${item.section}`,
  type: "section",
}));

type AvailabilityResults = {
  day: string;
  periods: { period: number; time: string }[];
  faculty: string[];
};

const FacultyAvailability = () => {
  const [ignoredYears, setIgnoredYears] = useState<string[]>([]);
  const [ignoredSections, setIgnoredSections] = useState<string[]>([]);
  const [availabilityFile, setAvailabilityFile] = useState<File | null>(null);
  const [availabilityFileId, setAvailabilityFileId] = useState<string>("");
  const [queryFile, setQueryFile] = useState<File | null>(null);
  const [queryFileId, setQueryFileId] = useState<string>("");
  const [results, setResults] = useState<BulkFacultyAvailabilityItem[] | null>(null);
  const [searching, setSearching] = useState(false);
  const templateBase = `${API_BASE_URL}/templates`;

  const toggleIgnoreYear = (year: string) => {
    setIgnoredYears((prev) =>
      prev.includes(year) ? prev.filter((y) => y !== year) : [...prev, year],
    );
  };

  const toggleIgnoreSection = (sectionKey: string) => {
    setIgnoredSections((prev) =>
      prev.includes(sectionKey) ? prev.filter((s) => s !== sectionKey) : [...prev, sectionKey],
    );
  };

  const handleSearch = async () => {
    if (!availabilityFileId || !queryFileId) {
      toast.error("Please upload both workload and query files.");
      return;
    }

    try {
      setSearching(true);
      const response = await getBulkFacultyAvailability({
        availabilityFileId,
        queryFileId,
        ignoredYears,
        ignoredSections,
      });
      setResults(response.results);
      toast.success("Availability report generated.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to fetch availability");
    } finally {
      setSearching(false);
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

  const handleDownloadCsv = () => {
    if (!results || results.length === 0) return;
    
    const headers = ["Date", "Day", "Periods", "Faculty Required", "Available Faculty Found", "Available Faculty Names"];
    const rows = results.map(r => {
      const periodsStr = r.periods.map(p => `P${p.period}`).join(", ");
      const facStr = r.faculty.join(" | ");
      return [
        r.date || "",
        r.day || "",
        `"${periodsStr}"`,
        r.facultyRequired,
        r.faculty.length,
        `"${facStr}"`
      ].join(",");
    });
    
    const csvContent = [headers.join(","), ...rows].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "faculty_availability_report.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
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

  return (
    <DashboardLayout>
      <div className="w-full space-y-6">
        <div className="page-header">
          <h1>Faculty Availability Bulk Finder</h1>
          <p>Upload faculty workload sheets and find who is free for the requested dates and periods</p>
        </div>

        <div className="grid grid-cols-1 2xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)] gap-6 w-full">
          <div className="space-y-6">
            <div className="bg-card rounded-xl p-6 xl:p-7 shadow-sm space-y-4 border border-border/60">
            <h3 className="text-sm font-semibold text-foreground flex items-center justify-between">
              Search Parameters
              <span className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-full bg-primary/10 text-primary">
                <Upload className="h-3.5 w-3.5" />
                Faculty Upload Ready
              </span>
            </h3>

            <div>
              <Label className="text-xs text-muted-foreground mb-2 block">Faculty Workload Upload</Label>
              <FileUpload
                file={availabilityFile}
                onFileSelect={handleAvailabilityUpload}
                onClear={() => {
                  setAvailabilityFile(null);
                  setAvailabilityFileId("");
                }}
                accept=".xlsx,.xls,.csv"
                label="Upload faculty workload file"
                description="Upload faculty workload sheets in the college format or a plain availability sheet"
                icon={<Upload className="h-9 w-9 text-primary" />}
                templateLinks={[
                  { label: "Workload Template", href: `${templateBase}/faculty-workload` },
                  { label: "Availability Template", href: `${templateBase}/faculty-availability` },
                ]}
              />
              <p className="text-[11px] text-muted-foreground mt-1">
                {availabilityFileId ? `Upload ID: ${availabilityFileId}` : "Upload faculty workload file to enable search."}
              </p>
            </div>

            <div>
              <Label className="text-xs text-muted-foreground mb-2 block">Availability Query Upload</Label>
              <FileUpload
                file={queryFile}
                onFileSelect={handleQueryUpload}
                onClear={() => {
                  setQueryFile(null);
                  setQueryFileId("");
                }}
                accept=".xlsx,.xls,.csv"
                label="Upload query file"
                description="Upload file with Date, Number of Faculty Required, and Periods (XLSX/CSV)"
                icon={<CalendarDays className="h-9 w-9 text-primary" />}
                templateLinks={[
                  {
                    label: "Query Template",
                    href: `${templateBase}/faculty-availability-query`,
                  },
                ]}
              />
              <p className="text-[11px] text-muted-foreground mt-1">
                {queryFileId ? `Query ID: ${queryFileId}` : "Upload query file containing the dates and periods to search."}
              </p>
            </div>

            <Button onClick={handleSearch} className="w-full gap-2" disabled={searching || !availabilityFileId || !queryFileId}>
              <Search className="h-4 w-4" /> {searching ? "Generating Report..." : "Generate Availability Report"}
            </Button>
          </div>

            <div className="bg-card rounded-xl p-6 xl:p-7 shadow-sm space-y-4 border border-border/60">
            <h3 className="text-sm font-semibold text-foreground">Ignore Rules (Treat as Free)</h3>
            <p className="text-xs text-muted-foreground">
              If a faculty is teaching any of the selected years or sections during a chosen period, treat that slot as free.
            </p>

            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Ignore Entire Year</p>
              <div className="flex flex-wrap gap-2">
                {ALL_YEAR_OPTIONS.map((opt) => (
                  <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                    <Checkbox
                      checked={ignoredYears.includes(opt.value)}
                      onCheckedChange={() => toggleIgnoreYear(opt.value)}
                    />
                    <span className="text-sm text-foreground">{opt.label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Ignore Specific Sections</p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {ALL_SECTION_OPTIONS.map((opt) => (
                  <label key={opt.value} className="flex items-center gap-2 cursor-pointer">
                    <Checkbox
                      checked={ignoredSections.includes(opt.value)}
                      onCheckedChange={() => toggleIgnoreSection(opt.value)}
                    />
                    <span className="text-sm text-foreground">{opt.label}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
          </div>

          <div>
            {results ? (
              <div className="bg-card rounded-xl p-6 xl:p-7 shadow-sm border border-border/60 min-h-full">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                  <Users className="h-4 w-4 text-primary" /> Report Generated ({results.length} rows)
                </h3>
                <Button onClick={handleDownloadCsv} size="sm" variant="secondary" className="gap-2">
                  Download CSV
                </Button>
              </div>

              <div className="bg-muted/50 rounded-lg p-4 mb-5 space-y-1">
                {(ignoredYears.length > 0 || ignoredSections.length > 0) ? (
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Ignoring:</span>
                    <span className="font-medium text-foreground text-right flex-1 ml-4 truncate">
                      {[
                        ...ignoredYears,
                        ...ignoredSections.map((s) => {
                          const [y, sec] = s.split("|");
                          return `${y.replace(" Year", "")}${sec}`;
                        }),
                      ].join(", ")}
                    </span>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">No ignore constraints active.</p>
                )}
              </div>

              <div className="mb-5 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                {results.slice(0, 10).map((r, i) => (
                  <div key={i} className="mb-4 pb-4 border-b border-border last:border-0 last:mb-0 last:pb-0">
                    <div className="flex justify-between items-start mb-2">
                      <div className="font-medium text-sm text-foreground">
                        {r.date} <span className="text-muted-foreground text-xs font-normal">({r.day})</span>
                      </div>
                      <div className="text-xs font-medium bg-primary/10 text-primary px-2 py-0.5 rounded">
                        Required: {r.facultyRequired}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1 mb-2">
                      {r.periods.map(p => (
                         <span key={p.period} className="text-[10px] font-semibold bg-muted text-muted-foreground px-1.5 py-0.5 rounded">
                           P{p.period} ({p.time})
                         </span>
                      ))}
                    </div>
                    {r.faculty.length > 0 ? (
                      <p className="text-xs text-foreground mt-1">
                        <span className="font-semibold text-primary">{r.faculty.length} found:</span> {r.faculty.join(", ")}
                      </p>
                    ) : (
                      <p className="text-xs text-muted-foreground italic">No faculty available.</p>
                    )}
                  </div>
                ))}
                {results.length > 10 && (
                  <p className="text-xs text-muted-foreground text-center pt-2">
                    ...and {results.length - 10} more rows. Download CSV to see full report.
                  </p>
                )}
              </div>
              </div>
            ) : (
              <div className="bg-card rounded-xl p-12 shadow-sm flex flex-col items-center justify-center text-center border border-border/60 min-h-[420px]">
                <Users className="h-12 w-12 text-muted-foreground/30 mb-4" />
                <p className="text-sm text-muted-foreground">
                  Upload your faculty workload file and a query file to generate a bulk report.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
};

export default FacultyAvailability;
