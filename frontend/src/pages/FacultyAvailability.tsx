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
  getFacultyAvailability,
  uploadFacultyAvailability,
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
  const [date, setDate] = useState("");
  const [selectedPeriods, setSelectedPeriods] = useState<number[]>([]);
  const [numFaculty, setNumFaculty] = useState(3);
  const [ignoredYears, setIgnoredYears] = useState<string[]>([]);
  const [ignoredSections, setIgnoredSections] = useState<string[]>([]);
  const [availabilityFile, setAvailabilityFile] = useState<File | null>(null);
  const [availabilityFileId, setAvailabilityFileId] = useState<string>("");
  const [results, setResults] = useState<AvailabilityResults | null>(null);
  const [searching, setSearching] = useState(false);
  const templateBase = `${API_BASE_URL}/templates`;

  const dayOfWeek = useMemo(() => {
    if (!date) return "";
    const d = new Date(date);
    const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
    return days[d.getDay()] || "";
  }, [date]);

  const togglePeriod = (p: number) => {
    setSelectedPeriods((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p],
    );
  };

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
    if (!date || selectedPeriods.length === 0 || !availabilityFileId) {
      toast.error("Please upload workload file, select date and at least one period");
      return;
    }

    if (!DAYS.includes(dayOfWeek as (typeof DAYS)[number])) {
      toast.error("Selected date is a Sunday - no classes scheduled.");
      return;
    }

    try {
      setSearching(true);
      const response = await getFacultyAvailability({
        date,
        periods: selectedPeriods,
        facultyRequired: numFaculty,
        ignoredYears,
        ignoredSections,
        availabilityFileId,
      });
      setResults(response);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to fetch availability");
    } finally {
      setSearching(false);
    }
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

  const formattedDate = date
    ? new Date(date).toLocaleDateString("en-IN", { day: "2-digit", month: "2-digit", year: "numeric" })
    : "";

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>Faculty Availability Finder</h1>
        <p>Find faculty who are free across all selected periods</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <div className="bg-card rounded-xl p-6 shadow-sm space-y-4 border border-border/60">
            <h3 className="text-sm font-semibold text-foreground flex items-center justify-between">
              Search Parameters
              <span className="inline-flex items-center gap-1 text-[11px] px-2 py-1 rounded-full bg-primary/10 text-primary">
                <Upload className="h-3.5 w-3.5" />
                Faculty Upload Ready
              </span>
            </h3>

            <div>
              <Label className="text-xs text-muted-foreground mb-2 block">Faculty Availability Upload</Label>
              <FileUpload
                file={availabilityFile}
                onFileSelect={handleAvailabilityUpload}
                onClear={() => {
                  setAvailabilityFile(null);
                  setAvailabilityFileId("");
                }}
                accept=".xlsx,.xls,.csv"
                label="Upload faculty availability file"
                description="Upload faculty timetable/availability data (XLSX/XLS/CSV)"
                icon={<Upload className="h-9 w-9 text-primary" />}
                templateLinks={[
                  { label: "Availability Template", href: `${templateBase}/faculty-availability` },
                ]}
              />
              <p className="text-[11px] text-muted-foreground mt-1">
                {availabilityFileId ? `Upload ID: ${availabilityFileId}` : "Upload workload file to enable search."}
              </p>
            </div>

            <div>
              <Label className="text-xs text-muted-foreground">Select Date</Label>
              <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
              {dayOfWeek && (
                <p className="text-xs text-primary mt-1 flex items-center gap-1">
                  <CalendarDays className="h-3 w-3" />
                  {dayOfWeek}
                </p>
              )}
            </div>

            <div>
              <Label className="text-xs text-muted-foreground mb-2 block">Select Period(s)</Label>
              <div className="flex flex-wrap gap-2">
                {actualPeriods.map((p) => (
                  <button
                    key={p.period}
                    onClick={() => togglePeriod(p.period)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                      selectedPeriods.includes(p.period)
                        ? "bg-primary text-primary-foreground border-primary"
                        : "bg-card text-foreground border-border hover:border-primary/50"
                    }`}
                  >
                    P{p.period} ({p.time})
                  </button>
                ))}
              </div>
            </div>

            <div>
              <Label className="text-xs text-muted-foreground">Number of Faculty Required</Label>
              <Input
                type="number"
                min={1}
                max={20}
                value={numFaculty}
                onChange={(e) => setNumFaculty(parseInt(e.target.value, 10) || 1)}
              />
            </div>

            <Button onClick={handleSearch} className="w-full gap-2" disabled={searching || !availabilityFileId}>
              <Search className="h-4 w-4" /> {searching ? "Finding..." : "Find Available Faculty"}
            </Button>
          </div>

          <div className="bg-card rounded-xl p-6 shadow-sm space-y-4 border border-border/60">
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
            <div className="bg-card rounded-xl p-6 shadow-sm border border-border/60">
              <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                <Users className="h-4 w-4 text-primary" /> Common Availability Results
              </h3>

              <div className="bg-muted/50 rounded-lg p-4 mb-5 space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Date:</span>
                  <span className="font-medium text-foreground">{formattedDate}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-muted-foreground">Day:</span>
                  <span className="font-medium text-foreground">{results.day}</span>
                </div>
                {(ignoredYears.length > 0 || ignoredSections.length > 0) && (
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Ignoring:</span>
                    <span className="font-medium text-foreground text-right">
                      {[
                        ...ignoredYears,
                        ...ignoredSections.map((s) => {
                          const [y, sec] = s.split("|");
                          return `${y.replace(" Year", "")}${sec}`;
                        }),
                      ].join(", ")}
                    </span>
                  </div>
                )}
              </div>

              <div className="mb-5">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                  Selected Periods
                </p>
                <div className="flex flex-wrap gap-2">
                  {results.periods.map((pr) => (
                    <span key={pr.period} className="bg-primary/10 text-primary text-xs font-semibold px-2.5 py-1 rounded-md">
                      P{pr.period} ({pr.time})
                    </span>
                  ))}
                </div>
              </div>

              {results.faculty.length > 0 ? (
                <div className="space-y-2">
                  {results.faculty.map((f, i) => (
                    <div key={f} className="flex items-center gap-3 p-3 rounded-lg bg-muted/30 border border-border">
                      <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                        <span className="text-xs font-bold text-primary">{i + 1}</span>
                      </div>
                      <span className="text-sm font-medium text-foreground">{f}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground text-center py-4">
                  No faculty are free for all selected periods.
                </p>
              )}
            </div>
          ) : (
            <div className="bg-card rounded-xl p-12 shadow-sm flex flex-col items-center justify-center text-center border border-border/60">
              <Users className="h-12 w-12 text-muted-foreground/30 mb-4" />
              <p className="text-sm text-muted-foreground">
                Select a date and periods to find faculty free across all selected slots
              </p>
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
};

export default FacultyAvailability;
