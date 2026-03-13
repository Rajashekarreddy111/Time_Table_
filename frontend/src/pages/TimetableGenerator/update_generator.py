import os

new_generator = '''import { useEffect, useRef, useState } from "react";
import {
  Plus,
  Trash2,
  Wand2,
  Upload,
  Users,
  BookOpen,
  Clock3,
} from "lucide-react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DAYS,
  SharedClassEntry,
} from "@/data/mockData";
import { LoadingSpinner } from "@/components/Loader/LoadingSpinner";
import { FileUpload } from "@/components/FileUpload";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  API_BASE_URL,
  generateTimetable,
  getMappingStatus,
  uploadFacultyIdMap,
  uploadMainTimetableConfig,
  uploadLabTimetable,
  uploadSubjectIdMapping,
  uploadSubjectContinuousRules,
  uploadSharedClasses,
  uploadFacultyAvailability,
  ApiError,
  ManualEntryMode,
} from "@/services/apiClient";
import {
  getAllSectionKeys,
  getSectionBatchMapForYear,
  getSectionOptionsForYear,
  getYearStructure,
  getYearOptions,
  readAcademicConfig,
  saveAcademicConfig,
  type AcademicConfig,
} from "@/lib/academicConfig";

type FacultyWeeklyAvailability = {
  facultyId: string;
  availablePeriodsByDay: Record<string, string>;
};

type MappingStatus = {
  facultyIdMapUploaded: boolean;
  mainTimetableConfigUploaded: boolean;
  labTimetableConfigUploaded: boolean;
  subjectIdMappingUploaded: boolean;
  subjectContinuousRulesUploaded: boolean;
  facultyIdMapFileName?: string | null;
  mainTimetableConfigFileName?: string | null;
  labTimetableConfigFileName?: string | null;
  subjectIdMappingFileName?: string | null;
  subjectContinuousRulesFileName?: string | null;
  sharedClassesUploaded?: boolean;
  sharedClassesFileName?: string | null;
  facultyAvailabilityUploaded?: boolean;
};

const EMPTY_MAPPING_STATUS: MappingStatus = {
  facultyIdMapUploaded: false,
  mainTimetableConfigUploaded: false,
  labTimetableConfigUploaded: false,
  subjectIdMappingUploaded: false,
  subjectContinuousRulesUploaded: false,
  sharedClassesUploaded: false,
  facultyAvailabilityUploaded: false,
};

const TimetableGenerator = () => {
  const navigate = useNavigate();
  const initialConfig = readAcademicConfig();
  const [academicConfig, setAcademicConfig] = useState<AcademicConfig>(initialConfig);
  const yearOptions = getYearOptions(academicConfig);
  const initialYear = yearOptions[0] || "1st Year";
  const initialSections = getSectionOptionsForYear(academicConfig, initialYear);
  const [selectedYear, setSelectedYear] = useState<string>(initialYear);
  const [selectedSection, setSelectedSection] = useState<string>(initialSections[0] ?? "A");

  const [manualEntries, setManualEntries] = useState<ManualEntryMode[]>([
    { year: initialYear, section: initialSections[0] ?? "A", subjectId: "", facultyId: "", noOfHours: 4, continuousHours: 1, compulsoryContinuousHours: 1 },
  ]);

  const [sharedClasses, setSharedClasses] = useState<SharedClassEntry[]>([
    { year: initialYear, sections: [], subject: "" },
  ]);
  const [generating, setGenerating] = useState(false);
  const [inputMode, setInputMode] = useState<"manual" | "file">("manual");
  const [facultyAvailabilityInputs, setFacultyAvailabilityInputs] = useState<FacultyWeeklyAvailability[]>([
    {
      facultyId: "",
      availablePeriodsByDay: DAYS.reduce<Record<string, string>>((acc, day) => {
        acc[day] = "";
        return acc;
      }, {}),
    },
  ]);
  const [facultyIdMapping, setFacultyIdMapping] = useState<{ facultyId: string; facultyName: string }[]>([
    { facultyId: "", facultyName: "" },
  ]);

  const [facultyIdFile, setFacultyIdFile] = useState<File | null>(null);
  const [mainTimetableFile, setMainTimetableFile] = useState<File | null>(null);
  const [labTimetableFile, setLabTimetableFile] = useState<File | null>(null);
  const [subjectIdMappingFile, setSubjectIdMappingFile] = useState<File | null>(null);
  const [subjectContinuousRulesFile, setSubjectContinuousRulesFile] = useState<File | null>(null);
  const [sharedClassesFile, setSharedClassesFile] = useState<File | null>(null);
  const [facultyAvailabilityFile, setFacultyAvailabilityFile] = useState<File | null>(null);

  const [mappingFileIds, setMappingFileIds] = useState({
    facultyIdMap: "",
    mainTimetableConfig: "",
    labTimetableConfig: "",
    subjectIdMapping: "",
    subjectContinuousRules: "",
  });

  const [mappingStatus, setMappingStatus] = useState<MappingStatus>(EMPTY_MAPPING_STATUS);
  const mappingStatusRequestRef = useRef(0);

  const templateBase = `${API_BASE_URL}/templates`;

  const addManualEntry = () =>
    setManualEntries([...manualEntries, { year: selectedYear, section: selectedSection, subjectId: "", facultyId: "", noOfHours: 4, continuousHours: 1, compulsoryContinuousHours: 1 }]);
  const removeManualEntry = (i: number) =>
    setManualEntries(manualEntries.filter((_, idx) => idx !== i));

  const addSharedClass = () => {
    const defaultYear = getYearOptions(academicConfig)[0] ?? "1st Year";
    setSharedClasses([...sharedClasses, { year: defaultYear, sections: [], subject: "" }]);
  };
  const removeSharedClass = (i: number) =>
    setSharedClasses(sharedClasses.filter((_, idx) => idx !== i));

  const addFacultyAvailabilityInput = () => {
    setFacultyAvailabilityInputs([
      ...facultyAvailabilityInputs,
      {
        facultyId: "",
        availablePeriodsByDay: DAYS.reduce<Record<string, string>>((acc, day) => {
          acc[day] = "";
          return acc;
        }, {}),
      },
    ]);
  };

  const removeFacultyAvailabilityInput = (i: number) => {
    setFacultyAvailabilityInputs(facultyAvailabilityInputs.filter((_, idx) => idx !== i));
  };

  const addFacultyIdMapping = () => {
    setFacultyIdMapping([...facultyIdMapping, { facultyId: "", facultyName: "" }]);
  };

  const removeFacultyIdMapping = (i: number) => {
    setFacultyIdMapping(facultyIdMapping.filter((_, idx) => idx !== i));
  };

  const updateAcademicConfig = (next: AcademicConfig) => {
    setAcademicConfig(next);
    saveAcademicConfig(next);

    const years = getYearOptions(next);
    const safeYear = years.includes(selectedYear) ? selectedYear : years[0];
    if (safeYear) {
      setSelectedYear(safeYear);
      const sections = getSectionOptionsForYear(next, safeYear);
      if (!sections.includes(selectedSection)) {
        setSelectedSection(sections[0] ?? "A");
      }
    }
  };

  const updateYearStructure = (
    yearIndex: number,
    updater: (current: AcademicConfig["years"][number]) => AcademicConfig["years"][number],
  ) => {
    const next: AcademicConfig = {
      activeYears: academicConfig.activeYears,
      years: academicConfig.years.map((year) => ({ ...year })),
    };
    if (!next.years[yearIndex]) {
      next.years[yearIndex] = {
        hasCreamGeneral: false,
        sectionCount: 4,
        creamSectionCount: 0,
        generalSectionCount: 0,
      };
    }
    next.years[yearIndex] = updater(next.years[yearIndex]);
    updateAcademicConfig(next);
  };

  const toPeriodList = (raw: string) => {
    return raw
      .split(",")
      .map((item) => Number(item.trim()))
      .filter((num) => Number.isInteger(num) && num >= 1 && num <= 7);
  };

  const loadMappingStatus = async (year: string) => {
    const requestId = ++mappingStatusRequestRef.current;
    try {
      const status = await getMappingStatus(year);
      if (requestId === mappingStatusRequestRef.current) {
        setMappingStatus(status);
      }
    } catch {
      if (requestId === mappingStatusRequestRef.current) {
        setMappingStatus(EMPTY_MAPPING_STATUS);
      }
    }
  };

  useEffect(() => {
    setMappingStatus(EMPTY_MAPPING_STATUS);
    loadMappingStatus(selectedYear);

    setFacultyIdFile(null);
    setMainTimetableFile(null);
    setLabTimetableFile(null);
    setSubjectIdMappingFile(null);
    setSubjectContinuousRulesFile(null);
    setSharedClassesFile(null);
    setFacultyAvailabilityFile(null);

    setMappingFileIds({
      facultyIdMap: "",
      mainTimetableConfig: "",
      labTimetableConfig: "",
      subjectIdMapping: "",
      subjectContinuousRules: "",
    });
  }, [selectedYear, selectedSection]);

  const showDetailedError = (error: unknown, fallbackMessage: string) => {
    if (error instanceof ApiError && error.details && error.details.length > 0) {
      const hint = (error.details[0] as Record<string, string>)?.hint || (error.details[0] as Record<string, string>)?.tip;
      if (hint) {
        toast.error(`${error.message}. Hint: ${hint}`, { duration: 6000 });
        return;
      }
    }
    if (error instanceof Error && error.message.includes("Failed to fetch")) {
      toast.error("Network error: Failed to fetch. Please check if the backend server is running and reachable.", { duration: 8000 });
      return;
    }
    toast.error(error instanceof Error ? error.message : fallbackMessage);
  };

  const uploadFacultyId = async (file: File) => {
    setFacultyIdFile(file);
    try {
      const response = await uploadFacultyIdMap(file);
      setMappingFileIds((prev) => ({ ...prev, facultyIdMap: response.fileId }));
      toast.success("Faculty ID map uploaded.");
      loadMappingStatus(selectedYear);
    } catch (error) {
      showDetailedError(error, "Faculty ID upload failed");
    }
  };

  const handleUploadMainTimetable = async (file: File) => {
    setMainTimetableFile(file);
    try {
      const response = await uploadMainTimetableConfig(file, selectedYear);
      setMappingFileIds((prev) => ({ ...prev, mainTimetableConfig: response.fileId }));
      toast.success("Main Timetable config uploaded.");
      loadMappingStatus(selectedYear);
    } catch (error) {
      showDetailedError(error, "Main Timetable config upload failed");
    }
  };

  const handleUploadLabTimetable = async (file: File) => {
    setLabTimetableFile(file);
    try {
      const response = await uploadLabTimetable(file, selectedYear);
      setMappingFileIds((prev) => ({ ...prev, labTimetableConfig: response.fileId }));
      toast.success("Lab Timetable config uploaded.");
      loadMappingStatus(selectedYear);
    } catch (error) {
      showDetailedError(error, "Lab Timetable config upload failed");
    }
  };

  const handleUploadSubjectIdMapping = async (file: File) => {
    setSubjectIdMappingFile(file);
    try {
      const response = await uploadSubjectIdMapping(file);
      setMappingFileIds((prev) => ({ ...prev, subjectIdMapping: response.fileId }));
      toast.success("Subject ID Mapping uploaded.");
      loadMappingStatus(selectedYear);
    } catch (error) {
      showDetailedError(error, "Subject ID Mapping upload failed");
    }
  };

  const handleUploadSubjectContinuousRules = async (file: File) => {
    setSubjectContinuousRulesFile(file);
    try {
      const response = await uploadSubjectContinuousRules(file);
      setMappingFileIds((prev) => ({ ...prev, subjectContinuousRules: response.fileId }));
      toast.success("Subject Continuous Rules uploaded.");
      loadMappingStatus(selectedYear);
    } catch (error) {
      showDetailedError(error, "Subject Continuous Rules upload failed");
    }
  };

  const uploadSharedClassesDoc = async (file: File) => {
    setSharedClassesFile(file);
    try {
      await uploadSharedClasses(file);
      toast.success("Shared classes constraint uploaded.");
      loadMappingStatus(selectedYear);
    } catch (error) {
      showDetailedError(error, "Shared classes upload failed");
    }
  };

  const uploadFacultyAvailabilityDoc = async (file: File) => {
    setFacultyAvailabilityFile(file);
    try {
      await uploadFacultyAvailability(file);
      toast.success("Faculty availability uploaded.");
      loadMappingStatus(selectedYear);
    } catch (error) {
      showDetailedError(error, "Faculty availability upload failed");
    }
  };

  const buildPayload = (yearOverride?: string, sectionOverride?: string) => {
    const targetYear = yearOverride || selectedYear;
    const targetSection = sectionOverride || selectedSection;

    const cleanedShared = sharedClasses
      .map((entry) => ({
        year: entry.year,
        sections: entry.sections.map((s) => s.trim()).filter(Boolean),
        subject: entry.subject.trim(),
      }))
      .filter((entry) => entry.subject && entry.sections.length > 0);

    const facultyAvailability = facultyAvailabilityInputs
      .map((entry) => ({
        facultyId: entry.facultyId.trim(),
        availablePeriodsByDay: DAYS.reduce<Record<string, number[]>>((acc, day) => {
          acc[day] = toPeriodList(entry.availablePeriodsByDay[day] ?? "");
          return acc;
        }, {}),
      }))
      .filter((entry) => entry.facultyId);

    return {
      year: targetYear,
      section: targetSection,
      manualEntries: manualEntries.filter(m => m.subjectId && m.facultyId),
      sharedClasses: cleanedShared,
      facultyAvailability,
      facultyIdNameMapping: facultyIdMapping.filter(f => f.facultyId.trim() && f.facultyName.trim()),
      mappingFileIds: {
        facultyIdMap: mappingFileIds.facultyIdMap || undefined,
        mainTimetableConfig: mappingFileIds.mainTimetableConfig || undefined,
        labTimetableConfig: mappingFileIds.labTimetableConfig || undefined,
        subjectIdMapping: mappingFileIds.subjectIdMapping || undefined,
        subjectContinuousRules: mappingFileIds.subjectContinuousRules || undefined,
      },
    };
  };

  const handleGenerate = async () => {
    if (
      inputMode === "file" &&
      (!mappingStatus.facultyIdMapUploaded ||
        !mappingStatus.mainTimetableConfigUploaded ||
        !mappingStatus.labTimetableConfigUploaded)
    ) {
      toast.error("Required mappings are missing. Upload them first.");
      return;
    }

    if (inputMode === "manual" && manualEntries.every(m => !m.subjectId || !m.facultyId)) {
      toast.error("Enter at least one valid manual entry configuration.");
      return;
    }

    setGenerating(true);
    try {
      const response = await generateTimetable(buildPayload());
      localStorage.setItem("latestTimetableId", response.timetableId);
      toast.success("Timetable generated successfully.");
      navigate(`/timetables?timetableId=${encodeURIComponent(response.timetableId)}`);
    } catch (error) {
      showDetailedError(error, "Failed to generate timetable");
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateAll = async () => {
    const allYears = getYearOptions(academicConfig);
    if (allYears.length < 2) {
      await handleGenerate();
      return;
    }

    setGenerating(true);
    let firstTimetableId: string | null = null;
    let successCount = 0;
    const errors: string[] = [];

    try {
      for (const year of allYears) {
        const yearSections = getSectionOptionsForYear(academicConfig, year);
        if (yearSections.length === 0) continue;

        if (inputMode === "file") {
          let yearMappingStatus;
          try {
            yearMappingStatus = await getMappingStatus(year);
          } catch {
            errors.push(`${year}: Could not check mapping status`);
            continue;
          }
          if (
            !yearMappingStatus.facultyIdMapUploaded ||
            !yearMappingStatus.mainTimetableConfigUploaded ||
            !yearMappingStatus.labTimetableConfigUploaded
          ) {
            errors.push(`${year}: Required mappings not uploaded — skipped`);
            continue;
          }
        }

        const primarySection = yearSections[0];
        const payload = buildPayload(year, primarySection);

        if (inputMode === "manual" && payload.manualEntries?.length === 0 && payload.facultyIdNameMapping.length === 0) {
          errors.push(`${year}: No manual configurations found`);
          continue;
        }

        try {
          const response = await generateTimetable(payload);
          if (!firstTimetableId) {
            firstTimetableId = response.timetableId;
          }
          successCount++;
        } catch (error) {
          const msg = error instanceof Error ? error.message : "Unknown error";
          errors.push(`${year}: ${msg}`);
        }
      }
    } finally {
      setGenerating(false);
    }

    if (successCount > 0) {
      if (errors.length > 0) {
        toast.warning(`Generated ${successCount} year(s). Issues: ${errors.join("; ")}`, { duration: 8000 });
      } else {
        toast.success(`Timetables generated for all ${successCount} year(s) successfully.`);
      }
      if (firstTimetableId) {
        localStorage.setItem("latestTimetableId", firstTimetableId);
        navigate(`/timetables?timetableId=${encodeURIComponent(firstTimetableId)}`);
      }
    } else {
      toast.error(errors.length > 0 ? `Generation failed for all years: ${errors.join("; ")}` : "No years could be generated.", { duration: 8000 });
    }
  };

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>Timetable Generator</h1>
        <p>Configure constraints and generate timetables</p>
      </div>

      {generating ? (
        <div className="bg-card rounded-xl p-8 shadow-sm">
          <LoadingSpinner message="Generating timetable... Applying constraints and resolving conflicts\\n\\nNote: Generating large sets might take some time finding valid combinations." />
        </div>
      ) : (
        <div className="space-y-6">
          <div className="bg-card rounded-xl p-6 shadow-sm border border-border/60">
            <h2 className="text-base font-semibold text-foreground mb-4">Academic Structure</h2>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
              <div>
                <Label className="text-xs text-muted-foreground mb-2 block">Active Years</Label>
                <div className="flex flex-col gap-2 bg-muted/20 p-3 rounded-md border border-border/60">
                  {["1st Year", "2nd Year", "3rd Year", "4th Year"].map((yearStr) => {
                    const isActive = academicConfig.activeYears.includes(yearStr);
                    return (
                      <label key={yearStr} className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
                        <input
                          type="checkbox"
                          className="rounded border-primary text-primary focus:ring-primary h-4 w-4"
                          checked={isActive}
                          onChange={(e) => {
                            const checked = e.target.checked;
                            let nextActive = [...academicConfig.activeYears];
                            let nextYears = [...academicConfig.years];
                            if (checked && !isActive) {
                              nextActive.push(yearStr);
                              nextActive.sort();
                              nextYears.push({ hasCreamGeneral: false, sectionCount: 4, creamSectionCount: 0, generalSectionCount: 0 });
                            } else if (!checked && isActive) {
                              const removeIdx = nextActive.indexOf(yearStr);
                              if (removeIdx > -1) {
                                nextActive.splice(removeIdx, 1);
                                nextYears.splice(removeIdx, 1);
                              }
                            }
                            if (nextActive.length === 0) {
                              nextActive = ["1st Year"];
                              nextYears = [{ hasCreamGeneral: false, sectionCount: 4, creamSectionCount: 0, generalSectionCount: 0 }];
                            }
                            updateAcademicConfig({ activeYears: nextActive, years: nextYears });
                          }}
                        />
                        {yearStr}
                      </label>
                    );
                  })}
                </div>
              </div>
              <div>
                <Label className="text-xs text-muted-foreground mb-2 block">Sections Per Year</Label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {getYearOptions(academicConfig).map((yearLabel, idx) => (
                    <div key={yearLabel} className="rounded-md border border-border/60 px-3 py-3 bg-muted/20 space-y-2">
                      <Label className="text-[11px] font-semibold">{yearLabel}</Label>
                      <div>
                        <Label className="text-[10px] text-muted-foreground">Number of Sections</Label>
                        <Input
                          type="number"
                          min={1}
                          max={60}
                          value={academicConfig.years[idx]?.sectionCount ?? 4}
                          className="h-8 text-xs"
                          onChange={(e) => {
                            const count = Math.max(1, Math.min(60, parseInt(e.target.value, 10) || 1));
                            updateYearStructure(idx, (current) => ({
                              ...current,
                              hasCreamGeneral: false,
                              sectionCount: count,
                            }));
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="bg-card rounded-xl p-6 shadow-sm border border-border/60">
            <h2 className="text-base font-semibold text-foreground mb-4">Select Year and Section</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-md">
              <div>
                <Label className="text-xs text-muted-foreground">Year</Label>
                <Select
                  value={selectedYear}
                  onValueChange={(year) => {
                    setSelectedYear(year);
                    const sections = getSectionOptionsForYear(academicConfig, year);
                    setSelectedSection(sections[0] ?? "A");
                  }}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {getYearOptions(academicConfig).map((y) => (
                      <SelectItem key={y} value={y}>{y}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Section</Label>
                <Select value={selectedSection} onValueChange={setSelectedSection}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {getSectionOptionsForYear(academicConfig, selectedYear).map((s) => (
                      <SelectItem key={s} value={s}>{s}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <div className="bg-card rounded-xl p-6 shadow-sm border border-border/60">
            <h2 className="text-base font-semibold text-foreground mb-4">Data Input Method</h2>
            <div className="flex flex-wrap gap-3">
              <Button variant={inputMode === "manual" ? "default" : "outline"} onClick={() => setInputMode("manual")} className="gap-2">
                <Wand2 className="h-4 w-4" /> Manual Entry
              </Button>
              <Button variant={inputMode === "file" ? "default" : "outline"} onClick={() => setInputMode("file")} className="gap-2">
                <Upload className="h-4 w-4" /> Upload Excel Files
              </Button>
            </div>
          </div>

          {inputMode === "file" && (
            <div className="bg-card rounded-xl p-6 shadow-sm space-y-5 border border-border/60">
              <p className="text-xs text-muted-foreground">
                Follow the Excel-driven process exactly. Global mappings apply across all timetables. Main and Lab timetables are mapped explicitly to the <span className="font-semibold">{selectedYear}</span>. Please verify your selected year.
              </p>
              
              <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                  <p className="text-xs font-semibold mb-2"><Users className="h-4 w-4 text-primary inline-block mr-1" /> Faculty Name/ID Mapping (Global)</p>
                  {mappingStatus.facultyIdMapUploaded ? (
                    <div className="rounded-lg border border-border/70 bg-background p-4 text-xs">
                      Uploaded: <span className="font-medium">{mappingStatus.facultyIdMapFileName}</span>
                    </div>
                  ) : (
                    <FileUpload file={facultyIdFile} onFileSelect={uploadFacultyId} onClear={() => setFacultyIdFile(null)} label="Upload Faculty Map" templateLinks={[{ label: "Download Template", href: `${templateBase}/faculty-id-map` }]} />
                  )}
                </div>

                <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                  <p className="text-xs font-semibold mb-2"><BookOpen className="h-4 w-4 text-primary inline-block mr-1" /> Main Config ({selectedYear})</p>
                  {mappingStatus.mainTimetableConfigUploaded ? (
                    <div className="rounded-lg border border-border/70 bg-background p-4 text-xs">
                      Uploaded: <span className="font-medium">{mappingStatus.mainTimetableConfigFileName}</span>
                    </div>
                  ) : (
                    <FileUpload file={mainTimetableFile} onFileSelect={handleUploadMainTimetable} onClear={() => setMainTimetableFile(null)} label="Upload Main Timetable" templateLinks={[{ label: "Download Template", href: `${templateBase}/main-timetable-config` }]} />
                  )}
                </div>

                <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                  <p className="text-xs font-semibold mb-2"><BookOpen className="h-4 w-4 text-primary inline-block mr-1" /> Lab Timetable ({selectedYear})</p>
                  {mappingStatus.labTimetableConfigUploaded ? (
                    <div className="rounded-lg border border-border/70 bg-background p-4 text-xs">
                      Uploaded: <span className="font-medium">{mappingStatus.labTimetableConfigFileName}</span>
                    </div>
                  ) : (
                    <FileUpload file={labTimetableFile} onFileSelect={handleUploadLabTimetable} onClear={() => setLabTimetableFile(null)} label="Upload Lab Timetable" templateLinks={[{ label: "Download Template", href: `${templateBase}/lab-timetable` }]} />
                  )}
                </div>

                <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                  <p className="text-xs font-semibold mb-2"><BookOpen className="h-4 w-4 text-primary inline-block mr-1" /> Subject ID Mapping (Global)</p>
                  {mappingStatus.subjectIdMappingUploaded ? (
                    <div className="rounded-lg border border-border/70 bg-background p-4 text-xs">
                      Uploaded: <span className="font-medium">{mappingStatus.subjectIdMappingFileName}</span>
                    </div>
                  ) : (
                    <FileUpload file={subjectIdMappingFile} onFileSelect={handleUploadSubjectIdMapping} onClear={() => setSubjectIdMappingFile(null)} label="Upload Subject ID Map" templateLinks={[{ label: "Download Template", href: `${templateBase}/subject-id-mapping` }]} />
                  )}
                </div>

                <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                  <p className="text-xs font-semibold mb-2"><Clock3 className="h-4 w-4 text-primary inline-block mr-1" /> Subject Continuous Rules (Global)</p>
                  {mappingStatus.subjectContinuousRulesUploaded ? (
                    <div className="rounded-lg border border-border/70 bg-background p-4 text-xs">
                      Uploaded: <span className="font-medium">{mappingStatus.subjectContinuousRulesFileName}</span>
                    </div>
                  ) : (
                    <FileUpload file={subjectContinuousRulesFile} onFileSelect={handleUploadSubjectContinuousRules} onClear={() => setSubjectContinuousRulesFile(null)} label="Upload Continuous Rules" templateLinks={[{ label: "Download Template", href: `${templateBase}/subject-continuous-rules` }]} />
                  )}
                </div>
              </div>
            </div>
          )}

          {inputMode === "manual" && (
            <Tabs defaultValue="entries" className="w-full mt-6">
              <TabsList className="bg-muted w-full justify-start overflow-x-auto">
                <TabsTrigger value="entries">Manual Entries</TabsTrigger>
                <TabsTrigger value="facultyId">Faculty ID Mapping</TabsTrigger>
                <TabsTrigger value="sharedClasses">Shared Classes</TabsTrigger>
                <TabsTrigger value="availability">Faculty Availability</TabsTrigger>
              </TabsList>

              <TabsContent value="entries" className="bg-card rounded-xl p-6 shadow-sm mt-4 border border-border/60">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">Classes Configuration ({selectedYear} - {selectedSection})</h3>
                  <Button variant="outline" size="sm" onClick={addManualEntry}>
                    <Plus className="h-3.5 w-3.5 mr-1" /> Add Entry
                  </Button>
                </div>
                <div className="overflow-x-auto pb-4">
                  <table className="w-full text-sm min-w-[600px]">
                    <thead>
                      <tr className="border-b border-border text-xs text-muted-foreground whitespace-nowrap">
                        <th className="text-left py-2 px-2 font-medium">Subject ID</th>
                        <th className="text-left py-2 px-2 font-medium">Faculty ID</th>
                        <th className="text-left py-2 px-2 font-medium">Hours/Week</th>
                        <th className="text-left py-2 px-2 font-medium">Continuous Hrs (Max)</th>
                        <th className="text-left py-2 px-2 font-medium">Compulsory Continuous Hrs</th>
                        <th className="w-10"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {manualEntries.map((m, i) => (
                        <tr key={i}>
                          <td className="py-1 px-2"><Input value={m.subjectId} onChange={(e) => { const c = [...manualEntries]; c[i].subjectId = e.target.value; setManualEntries(c); }} placeholder="SUB_001" className="h-8"/></td>
                          <td className="py-1 px-2"><Input value={m.facultyId} onChange={(e) => { const c = [...manualEntries]; c[i].facultyId = e.target.value; setManualEntries(c); }} placeholder="FAC_001" className="h-8"/></td>
                          <td className="py-1 px-2"><Input type="number" min={1} max={10} value={m.noOfHours} onChange={(e) => { const c = [...manualEntries]; c[i].noOfHours = parseInt(e.target.value) || 1; setManualEntries(c); }} className="w-20 h-8"/></td>
                          <td className="py-1 px-2"><Input type="number" min={1} max={5} value={m.continuousHours} onChange={(e) => { const c = [...manualEntries]; c[i].continuousHours = parseInt(e.target.value) || 1; setManualEntries(c); }} className="w-20 h-8"/></td>
                          <td className="py-1 px-2"><Input type="number" min={1} max={5} value={m.compulsoryContinuousHours} onChange={(e) => { const c = [...manualEntries]; c[i].compulsoryContinuousHours = parseInt(e.target.value) || 1; setManualEntries(c); }} className="w-20 h-8"/></td>
                          <td className="py-1 px-2">
                            {manualEntries.length > 1 && (
                              <Button variant="ghost" size="icon" onClick={() => removeManualEntry(i)} className="text-destructive h-8 w-8"><Trash2 className="h-3.5 w-3.5" /></Button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="text-xs text-muted-foreground mt-4">Note: The backend enforces that the sum of these hours (plus any globally assigned labs matching this section) perfectly equals exactly 42 hours per week.</p>
                </div>
              </TabsContent>

              <TabsContent value="facultyId" className="bg-card rounded-xl p-6 shadow-sm mt-4 border border-border/60">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">Faculty ID Mapping</h3>
                  <Button variant="outline" size="sm" onClick={addFacultyIdMapping}><Plus className="h-3.5 w-3.5 mr-1" /> Add Mapping</Button>
                </div>
                <div className="space-y-3">
                  {facultyIdMapping.map((f, i) => (
                    <div key={i} className="flex gap-3 items-end">
                      <div className="flex-1">
                        <Label className="text-xs text-muted-foreground">Faculty ID</Label>
                        <Input placeholder="F001" value={f.facultyId} onChange={(e) => { const c = [...facultyIdMapping]; c[i].facultyId = e.target.value; setFacultyIdMapping(c); }} />
                      </div>
                      <div className="flex-1">
                        <Label className="text-xs text-muted-foreground">Name</Label>
                        <Input placeholder="John Doe" value={f.facultyName} onChange={(e) => { const c = [...facultyIdMapping]; c[i].facultyName = e.target.value; setFacultyIdMapping(c); }} />
                      </div>
                      {facultyIdMapping.length > 1 && (
                        <Button variant="ghost" size="icon" onClick={() => removeFacultyIdMapping(i)} className="text-destructive"><Trash2 className="h-4 w-4" /></Button>
                      )}
                    </div>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="sharedClasses" className="bg-card rounded-xl p-6 shadow-sm mt-4 border border-border/60">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">Shared Classes</h3>
                  <Button variant="outline" size="sm" onClick={addSharedClass}><Plus className="h-3.5 w-3.5 mr-1" /> Add Shared Class</Button>
                </div>
                <div className="space-y-3">
                  {sharedClasses.map((sc, i) => (
                    <div key={i} className="flex gap-3 items-end">
                      <div className="w-1/4">
                        <Label className="text-xs text-muted-foreground">Year</Label>
                        <Select value={sc.year} onValueChange={(v) => { const c = [...sharedClasses]; c[i].year = v; setSharedClasses(c); }}>
                          <SelectTrigger className="h-9 truncate"><SelectValue /></SelectTrigger>
                          <SelectContent>{getYearOptions(academicConfig).map(y => <SelectItem key={y} value={y}>{y}</SelectItem>)}</SelectContent>
                        </Select>
                      </div>
                      <div className="flex-1">
                        <Label className="text-xs text-muted-foreground">Subject ID</Label>
                        <Input placeholder="SUB_001" value={sc.subject} onChange={(e) => { const c = [...sharedClasses]; c[i].subject = e.target.value; setSharedClasses(c); }} />
                      </div>
                      <div className="flex-1">
                        <Label className="text-xs text-muted-foreground">Sections (Comma sep)</Label>
                        <Input placeholder="A, B" value={sc.sections.join(", ")} onChange={(e) => { const c = [...sharedClasses]; c[i].sections = e.target.value.split(',').map(s=>s.trim()).filter(Boolean); setSharedClasses(c); }} />
                      </div>
                      <Button variant="ghost" size="icon" onClick={() => removeSharedClass(i)} className="text-destructive h-9 w-9"><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="availability" className="bg-card rounded-xl p-6 shadow-sm mt-4 border border-border/60">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">Faculty Availability</h3>
                  <Button variant="outline" size="sm" onClick={addFacultyAvailabilityInput}><Plus className="h-3.5 w-3.5 mr-1" /> Add Faculty</Button>
                </div>
                <div className="space-y-4">
                  {facultyAvailabilityInputs.map((fa, i) => (
                    <div key={i} className="p-3 rounded-lg border border-border/40 bg-muted/10 relative">
                      <Button variant="ghost" size="icon" onClick={() => removeFacultyAvailabilityInput(i)} className="text-destructive absolute top-1 right-1 h-7 w-7"><Trash2 className="h-3.5 w-3.5" /></Button>
                      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                        <div className="md:col-span-1">
                          <Label className="text-[10px] text-muted-foreground">Faculty ID</Label>
                          <Input placeholder="F-001" value={fa.facultyId} onChange={(e) => { const c = [...facultyAvailabilityInputs]; c[i].facultyId = e.target.value; setFacultyAvailabilityInputs(c); }} className="h-8 text-xs" />
                        </div>
                        <div className="md:col-span-3 grid grid-cols-2 md:grid-cols-6 gap-2">
                          {DAYS.map(day => (
                            <div key={day}>
                              <Label className="text-[10px] text-muted-foreground uppercase">{day.substring(0, 3)}</Label>
                              <Input placeholder="1,2" value={fa.availablePeriodsByDay[day]} onChange={(e) => { const c = [...facultyAvailabilityInputs]; c[i].availablePeriodsByDay[day] = e.target.value; setFacultyAvailabilityInputs(c); }} className="h-7 text-[10px] px-2" />
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </TabsContent>
            </Tabs>
          )}

          <div className="flex justify-end gap-3 mt-8">
            {getYearOptions(academicConfig).length > 1 && (
              <Button onClick={handleGenerateAll} size="lg" variant="outline" className="gap-2">
                <Wand2 className="h-4 w-4" /> Generate All Years
              </Button>
            )}
            <Button onClick={handleGenerate} size="lg" className="gap-2">
              <Wand2 className="h-4 w-4" /> Generate Timetable
            </Button>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
};

export default TimetableGenerator;
'''

with open(r"c:\\Users\\rajas\\OneDrive\\Desktop\\Timetable\\frontend\\src\\pages\\TimetableGenerator\\TimetableGenerator.tsx", "w", encoding="utf-8") as f:
    f.write(new_generator)

print("TimetableGenerator.tsx fully updated successfully")
