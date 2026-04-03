import { useEffect, useRef, useState } from "react";
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
  checkTimetableFeasibility,
  deleteUploadedMapping,
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
  ManualLabEntry,
  SubjectContinuousRuleEntry,
  SubjectIdNameMappingEntry,
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
import { buildTemplateLinks } from "@/utils/templateLinks";

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
  facultyAvailabilityFileName?: string | null;
};

type MappingUploadType =
  | "faculty-id-map"
  | "main-timetable-config"
  | "lab-timetable-config"
  | "subject-id-mapping"
  | "subject-continuous-rules"
  | "shared-classes"
  | "faculty-availability";

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
  const [academicYearInput, setAcademicYearInput] = useState("");
  const [semesterInput, setSemesterInput] = useState<"1" | "2">("2");
  const [withEffectFromInput, setWithEffectFromInput] = useState("");

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
  const [subjectIdNameMapping, setSubjectIdNameMapping] = useState<SubjectIdNameMappingEntry[]>([
    { subjectId: "", subjectName: "" },
  ]);
  const [subjectContinuousRules, setSubjectContinuousRules] = useState<SubjectContinuousRuleEntry[]>([
    { subjectId: "", compulsoryContinuousHours: 1 },
  ]);
  const [manualLabEntries, setManualLabEntries] = useState<ManualLabEntry[]>([
    { year: initialYear, section: initialSections[0] ?? "A", subjectId: "", day: 1, hours: [], venue: "" },
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

  const clearUploadState = () => {
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
  };

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

  const addSubjectIdNameMapping = () => {
    setSubjectIdNameMapping([...subjectIdNameMapping, { subjectId: "", subjectName: "" }]);
  };

  const removeSubjectIdNameMapping = (i: number) => {
    setSubjectIdNameMapping(subjectIdNameMapping.filter((_, idx) => idx !== i));
  };

  const addSubjectContinuousRule = () => {
    setSubjectContinuousRules([...subjectContinuousRules, { subjectId: "", compulsoryContinuousHours: 1 }]);
  };

  const removeSubjectContinuousRule = (i: number) => {
    setSubjectContinuousRules(subjectContinuousRules.filter((_, idx) => idx !== i));
  };

  const addManualLabEntry = () => {
    setManualLabEntries([
      ...manualLabEntries,
      { year: selectedYear, section: selectedSection, subjectId: "", day: 1, hours: [], venue: "" },
    ]);
  };

  const removeManualLabEntry = (i: number) => {
    setManualLabEntries(manualLabEntries.filter((_, idx) => idx !== i));
  };

  const updateAcademicConfig = (next: AcademicConfig) => {
    setAcademicConfig(next);
    saveAcademicConfig(next);

    const years = getYearOptions(next);
    const safeYear = years.includes(selectedYear) ? selectedYear : years[0];
    if (safeYear) {
      setSelectedYear(safeYear);
      if (!selectedSection.trim()) {
        const sections = getSectionOptionsForYear(next, safeYear);
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
      const template = academicConfig.years[0] ?? {
        hasCreamGeneral: false,
        sectionCount: 4,
        creamSectionCount: 0,
        generalSectionCount: 0,
      };
      next.years[yearIndex] = {
        ...template,
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

  const isAcademicYearValid = (value: string) => /^\d{4}-\d{4}$/.test(value);

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
    clearUploadState();
  }, [selectedYear, selectedSection]);

  const showDetailedError = (error: unknown, fallbackMessage: string) => {
    if (error instanceof ApiError) {
      toast.error(formatApiErrorMessage(error), { duration: 10000 });
      return;
    }
    if (error instanceof Error && error.message.includes("Failed to fetch")) {
      toast.error("Network error: Failed to fetch. Please check if the backend server is running and reachable.", { duration: 8000 });
      return;
    }
    toast.error(error instanceof Error ? error.message : fallbackMessage);
  };

  const formatApiErrorMessage = (error: ApiError) => {
    const firstDetail = error.details?.[0] as Record<string, unknown> | undefined;
    if (!firstDetail) {
      return error.message;
    }

    const violatingSections = firstDetail.violating_sections;
    if (Array.isArray(violatingSections) && violatingSections.length > 0) {
      return `${error.message} Problem sections: ${violatingSections.join(", ")}.`;
    }

    const missingSection = typeof firstDetail.section === "string" ? firstDetail.section : "";
    const subjectId = typeof firstDetail.subject_id === "string" ? firstDetail.subject_id : "";
    const mainConfigSections = Array.isArray(firstDetail.mainConfigSections) ? firstDetail.mainConfigSections.join(", ") : "";
    if (missingSection && mainConfigSections) {
      return `${error.message} Section "${missingSection}"${subjectId ? ` for subject ${subjectId}` : ""} is not present in the main config for that year. Valid sections are: ${mainConfigSections}.`;
    }

    const missingSections = Array.isArray(firstDetail.missingSections) ? firstDetail.missingSections.join(", ") : "";
    if (missingSections) {
      return `${error.message} Missing sections: ${missingSections}.`;
    }

    const hint = typeof firstDetail.hint === "string" ? firstDetail.hint : typeof firstDetail.tip === "string" ? firstDetail.tip : "";
    const sections = Array.isArray(firstDetail.sections) ? firstDetail.sections.join(", ") : "";
    const taskCount = typeof firstDetail.taskCount === "number" ? firstDetail.taskCount : undefined;
    const facultyCount = typeof firstDetail.facultyCount === "number" ? firstDetail.facultyCount : undefined;
    const labEntryCount = typeof firstDetail.labEntryCount === "number" ? firstDetail.labEntryCount : undefined;
    const sharedClassCount = typeof firstDetail.sharedClassCount === "number" ? firstDetail.sharedClassCount : undefined;

    if (error.message.toLowerCase().includes("timed out")) {
      const parts = [
        hint,
        sections ? `Sections involved: ${sections}.` : "",
        taskCount !== undefined ? `Scheduling blocks to place: ${taskCount}.` : "",
        facultyCount !== undefined ? `Faculty involved: ${facultyCount}.` : "",
        labEntryCount !== undefined ? `Fixed lab entries: ${labEntryCount}.` : "",
        sharedClassCount !== undefined ? `Shared class groups: ${sharedClassCount}.` : "",
      ].filter(Boolean);
      return `${error.message} ${parts.join(" ")}`.trim();
    }

    if (hint) {
      return `${error.message} ${hint}`;
    }

    return error.message;
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
      const response = await uploadMainTimetableConfig(file);
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
      const response = await uploadLabTimetable(file);
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

  const handleRemoveUploadedFile = async (
    mappingType: MappingUploadType,
    onLocalClear: () => void,
    successMessage: string,
  ) => {
    try {
      await deleteUploadedMapping(mappingType);
      onLocalClear();
      await loadMappingStatus(selectedYear);
      toast.success(successMessage);
    } catch (error) {
      showDetailedError(error, "Failed to remove uploaded file");
    }
  };

  const clearAllUploadedFiles = async () => {
    const mappingTypes: MappingUploadType[] = [
      "faculty-id-map",
      "main-timetable-config",
      "lab-timetable-config",
      "subject-id-mapping",
      "subject-continuous-rules",
      "shared-classes",
      "faculty-availability",
    ];

    await Promise.all(
      mappingTypes.map(async (mappingType) => {
        try {
          await deleteUploadedMapping(mappingType);
        } catch {
          // Ignore missing uploads during automatic cleanup.
        }
      }),
    );

    clearUploadState();
    await loadMappingStatus(selectedYear);
  };

  const buildPayload = (yearOverride?: string, sectionOverride?: string, priorTimetableIds: string[] = []) => {
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
      timetableMetadata: {
        academicYear: academicYearInput.trim(),
        semester: Number(semesterInput) as 1 | 2,
        withEffectFrom: withEffectFromInput,
      },
      priorTimetableIds,
      manualEntries: manualEntries
        .filter((m) => m.subjectId && m.facultyId)
        .map(m => ({
          ...m,
          year: targetYear,
          section: targetSection,
          compulsoryContinuousHours: subjectContinuousRules.find(r => r.subjectId === m.subjectId)?.compulsoryContinuousHours || 0
        })),
      manualLabEntries: manualLabEntries
        .map((entry) => ({
          ...entry,
          year: entry.year,
          section: entry.section.trim(),
          subjectId: entry.subjectId.trim(),
          venue: entry.venue.trim(),
          hours: entry.hours.filter((hour) => Number.isInteger(hour) && hour >= 1 && hour <= 7),
        }))
        .filter((entry) => entry.subjectId && entry.section && entry.hours.length > 0),
      sharedClasses: cleanedShared,
      facultyAvailability,
      facultyIdNameMapping: facultyIdMapping.filter(f => f.facultyId.trim() && f.facultyName.trim()),
      subjectIdNameMapping: subjectIdNameMapping.filter((entry) => entry.subjectId.trim() && entry.subjectName.trim()),
      subjectContinuousRules: subjectContinuousRules.filter((entry) => entry.subjectId.trim()),
      mappingFileIds: {
        facultyIdMap: mappingFileIds.facultyIdMap || undefined,
        mainTimetableConfig: mappingFileIds.mainTimetableConfig || undefined,
        labTimetableConfig: mappingFileIds.labTimetableConfig || undefined,
        subjectIdMapping: mappingFileIds.subjectIdMapping || undefined,
        subjectContinuousRules: mappingFileIds.subjectContinuousRules || undefined,
      },
    };
  };

  const formatBlockingSections = (
    sections: Array<{ section: string; requiredHours: number; freeSlots: number; deficitHours: number }>,
  ) => {
    const top = sections.slice(0, 5);
    const summary = top
      .map((item) => `${item.section}: needs ${item.requiredHours}, free ${item.freeSlots}, deficit ${item.deficitHours}`)
      .join(" | ");
    return sections.length > 5 ? `${summary} | ...` : summary;
  };

  const handleGenerate = async () => {
    if (!isAcademicYearValid(academicYearInput.trim())) {
      toast.error("Academic year is required in yyyy-yyyy format.");
      return;
    }

    if (!withEffectFromInput) {
      toast.error("With effect from date is required.");
      return;
    }

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
      const payload = buildPayload();
      const feasibility = await checkTimetableFeasibility(payload);
      if (!feasibility.feasible) {
        toast.error(
          `Generation blocked: infeasible section capacity for ${feasibility.year}. ${formatBlockingSections(feasibility.blockingSections)}`,
          { duration: 12000 },
        );
        return;
      }

      const response = await generateTimetable(payload);
      localStorage.setItem("latestTimetableId", response.timetableId);
      const reportOnly = response.message.toLowerCase().includes("report");
      await clearAllUploadedFiles();
      toast.success(response.message);
      navigate(reportOnly
        ? `/outputs?timetableId=${encodeURIComponent(response.timetableId)}`
        : `/timetables?timetableId=${encodeURIComponent(response.timetableId)}`);
    } catch (error) {
      showDetailedError(error, "Failed to generate timetable");
    } finally {
      setGenerating(false);
    }
  };

  const handleGenerateAll = async () => {
    if (!isAcademicYearValid(academicYearInput.trim())) {
      toast.error("Academic year is required in yyyy-yyyy format.");
      return;
    }

    if (!withEffectFromInput) {
      toast.error("With effect from date is required.");
      return;
    }

    const configuredYears = getYearOptions(academicConfig);
    const allYears = [...configuredYears].sort((left, right) => {
      const sectionDelta =
        getSectionOptionsForYear(academicConfig, right).length -
        getSectionOptionsForYear(academicConfig, left).length;
      if (sectionDelta !== 0) {
        return sectionDelta;
      }
      return configuredYears.indexOf(left) - configuredYears.indexOf(right);
    });
    if (allYears.length < 2) {
      await handleGenerate();
      return;
    }

    setGenerating(true);
    let firstTimetableId: string | null = null;
    let successCount = 0;
    const errors: string[] = [];
    const generatedTimetableIds: string[] = [];

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
        const payload = buildPayload(year, primarySection, generatedTimetableIds);

        if (inputMode === "manual" && payload.manualEntries?.length === 0 && payload.facultyIdNameMapping.length === 0) {
          errors.push(`${year}: No manual configurations found`);
          continue;
        }

        try {
          const feasibility = await checkTimetableFeasibility(payload);
          if (!feasibility.feasible) {
            errors.push(`${year}: Infeasible section capacity (${formatBlockingSections(feasibility.blockingSections)})`);
            continue;
          }
          const response = await generateTimetable(payload);
          if (!firstTimetableId) {
            firstTimetableId = response.timetableId;
          }
          generatedTimetableIds.push(response.timetableId);
          successCount++;
        } catch (error) {
          const msg = error instanceof ApiError
            ? formatApiErrorMessage(error)
            : error instanceof Error
              ? error.message
              : "Unknown error";
          errors.push(`${year}: ${msg}`);
        }
      }
    } finally {
      setGenerating(false);
    }

    if (successCount > 0) {
      await clearAllUploadedFiles();
      if (errors.length > 0) {
        toast.warning(`Generated ${successCount} year(s). Issues: ${errors.join("; ")}`, { duration: 8000 });
      } else {
        toast.success(`Timetables generated for all ${successCount} year(s) successfully.`);
      }
      if (firstTimetableId) {
        localStorage.setItem("latestTimetableId", firstTimetableId);
        navigate(`/outputs?timetableId=${encodeURIComponent(firstTimetableId)}`);
      }
    } else {
      toast.error(errors.length > 0 ? `Generation failed for all years: ${errors.join("; ")}` : "No years could be generated.", { duration: 8000 });
    }
  };

  return (
    <DashboardLayout>
      <section className="hero-shell mb-8">
        <div className="relative z-10 grid gap-6 xl:grid-cols-[minmax(0,1.05fr)_380px] xl:items-end">
          <div className="space-y-4">
            <div className="hero-chip">Constraint Planning Workspace</div>
            <div className="space-y-2">
              <h1 className="text-4xl font-bold tracking-tight text-foreground">Timetable Generator</h1>
              <p className="max-w-3xl text-sm leading-7 text-muted-foreground">
                Configure academic structure, lock fixed inputs, and generate single-year or multi-year timetable runs from one orchestrated screen.
              </p>
            </div>
          </div>
          <div className="panel-card">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Current Focus</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="panel-muted">
                <p className="text-xs text-muted-foreground">Selected year</p>
                <p className="mt-2 text-2xl font-bold text-foreground">{selectedYear}</p>
              </div>
              <div className="panel-muted">
                <p className="text-xs text-muted-foreground">Selected section</p>
                <p className="mt-2 text-2xl font-bold text-foreground">{selectedSection}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {generating ? (
        <div className="panel-card p-8">
          <LoadingSpinner message="Generating timetable... Applying constraints and resolving conflicts\n\nNote: Generating large sets might take some time finding valid combinations." />
        </div>
      ) : (
        <div className="space-y-6 w-full">
          <div className="panel-card">
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
                              nextYears.push({
                                ...(academicConfig.years[0] ?? {
                                  hasCreamGeneral: false,
                                  sectionCount: 4,
                                  creamSectionCount: 0,
                                  generalSectionCount: 0,
                                }),
                              });
                            } else if (!checked && isActive) {
                              const removeIdx = nextActive.indexOf(yearStr);
                              if (removeIdx > -1) {
                                nextActive.splice(removeIdx, 1);
                                nextYears.splice(removeIdx, 1);
                              }
                            }
                            if (nextActive.length === 0) {
                              nextActive = ["1st Year"];
                              nextYears = [{
                                ...(academicConfig.years[0] ?? {
                                  hasCreamGeneral: false,
                                  sectionCount: 4,
                                  creamSectionCount: 0,
                                  generalSectionCount: 0,
                                }),
                              }];
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
                <Label className="text-xs text-muted-foreground mb-2 block">Sections Per Year (Count only)</Label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {getYearOptions(academicConfig).map((yearLabel, idx) => (
                    <div key={yearLabel} className="rounded-md border border-border/60 px-3 py-3 bg-muted/20 space-y-2">
                      <Label className="text-[11px] font-semibold">{yearLabel}</Label>
                      <div className="grid grid-cols-2 gap-2">
                        <Input
                          type="number"
                          min={1}
                          max={26}
                          value={academicConfig.years[idx]?.sectionCount ?? 4}
                          className="h-8 text-[11px]"
                          placeholder="4"
                          onChange={(e) => {
                            const sectionCount = Math.max(1, Number(e.target.value) || 1);
                            updateYearStructure(idx, (current) => ({
                              ...current,
                              sectionCount,
                            }));
                          }}
                        />
                        <div className="text-[10px] text-muted-foreground flex items-center">
                          Auto sections: A, B, C... (you can type any section manually below)
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
          <div className="panel-card">
            <h2 className="text-base font-semibold text-foreground mb-4">Select Year and Section</h2>
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 w-full max-w-3xl">
              <div>
                <Label className="text-xs text-muted-foreground">Year</Label>
                <Select
                  value={selectedYear}
                  onValueChange={(year) => {
                    setSelectedYear(year);
                    if (!selectedSection.trim()) {
                      const sections = getSectionOptionsForYear(academicConfig, year);
                      setSelectedSection(sections[0] ?? "A");
                    }
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
                <Input
                  value={selectedSection}
                  onChange={(e) => setSelectedSection(e.target.value)}
                  placeholder="Type section name"
                />
              </div>
            </div>
            <div className="mt-5">
              <h3 className="text-sm font-semibold text-foreground mb-3">Timetable Metadata</h3>
              <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 w-full max-w-4xl">
                <div>
                  <Label className="text-xs text-muted-foreground">Academic Year</Label>
                  <Input
                    value={academicYearInput}
                    onChange={(e) => setAcademicYearInput(e.target.value)}
                    placeholder="2026-2027"
                  />
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    Required. Format: `yyyy-yyyy`
                  </p>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">Semester</Label>
                  <Select value={semesterInput} onValueChange={(value: "1" | "2") => setSemesterInput(value)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">1</SelectItem>
                      <SelectItem value="2">2</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">With Effect From</Label>
                  <Input
                    type="date"
                    value={withEffectFromInput}
                    onChange={(e) => setWithEffectFromInput(e.target.value)}
                  />
                </div>
              </div>
            </div>
          </div>
          <div className="panel-card">
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
            <div className="panel-card space-y-5">
              <p className="text-xs text-muted-foreground">
                Follow the Excel-driven process exactly. All uploaded files in this section are stored globally and reused across timetable generation, including Main Config, Lab Timetable, Shared Classes, and Faculty Availability.
              </p>
              
              <div className="grid grid-cols-1 xl:grid-cols-2 2xl:grid-cols-3 gap-4">
                <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                  <p className="text-xs font-semibold mb-2"><Users className="h-4 w-4 text-primary inline-block mr-1" /> Faculty Name/ID Mapping (Global)</p>
                  <FileUpload file={facultyIdFile} onFileSelect={uploadFacultyId} onClear={() => setFacultyIdFile(null)} label="Upload Faculty Map" templateLinks={buildTemplateLinks(templateBase, "faculty-id-map")} />
                  {mappingStatus.facultyIdMapUploaded && (
                    <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-background p-3 text-xs">
                      <span>Uploaded: <span className="font-medium">{mappingStatus.facultyIdMapFileName}</span></span>
                      <Button variant="outline" size="sm" onClick={() => handleRemoveUploadedFile("faculty-id-map", () => { setFacultyIdFile(null); setMappingFileIds((prev) => ({ ...prev, facultyIdMap: "" })); }, "Faculty ID map removed.")}>Remove</Button>
                    </div>
                  )}
                </div>

                <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                  <p className="text-xs font-semibold mb-2"><BookOpen className="h-4 w-4 text-primary inline-block mr-1" /> Main Config (Global)</p>
                  <FileUpload file={mainTimetableFile} onFileSelect={handleUploadMainTimetable} onClear={() => setMainTimetableFile(null)} label="Upload Main Timetable" templateLinks={buildTemplateLinks(templateBase, "main-timetable-config")} />
                  {mappingStatus.mainTimetableConfigUploaded && (
                    <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-background p-3 text-xs">
                      <span>Uploaded: <span className="font-medium">{mappingStatus.mainTimetableConfigFileName}</span></span>
                      <Button variant="outline" size="sm" onClick={() => handleRemoveUploadedFile("main-timetable-config", () => { setMainTimetableFile(null); setMappingFileIds((prev) => ({ ...prev, mainTimetableConfig: "" })); }, "Main timetable config removed.")}>Remove</Button>
                    </div>
                  )}
                </div>

                <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                  <p className="text-xs font-semibold mb-2"><BookOpen className="h-4 w-4 text-primary inline-block mr-1" /> Lab Timetable (Global)</p>
                  <FileUpload file={labTimetableFile} onFileSelect={handleUploadLabTimetable} onClear={() => setLabTimetableFile(null)} label="Upload Lab Timetable" templateLinks={buildTemplateLinks(templateBase, "lab-timetable")} />
                  {mappingStatus.labTimetableConfigUploaded && (
                    <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-background p-3 text-xs">
                      <span>Uploaded: <span className="font-medium">{mappingStatus.labTimetableConfigFileName}</span></span>
                      <Button variant="outline" size="sm" onClick={() => handleRemoveUploadedFile("lab-timetable-config", () => { setLabTimetableFile(null); setMappingFileIds((prev) => ({ ...prev, labTimetableConfig: "" })); }, "Lab timetable config removed.")}>Remove</Button>
                    </div>
                  )}
                </div>

                <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                  <p className="text-xs font-semibold mb-2"><BookOpen className="h-4 w-4 text-primary inline-block mr-1" /> Subject ID Mapping (Global)</p>
                  <FileUpload file={subjectIdMappingFile} onFileSelect={handleUploadSubjectIdMapping} onClear={() => setSubjectIdMappingFile(null)} label="Upload Subject ID Map" templateLinks={buildTemplateLinks(templateBase, "subject-id-mapping")} />
                  {mappingStatus.subjectIdMappingUploaded && (
                    <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-background p-3 text-xs">
                      <span>Uploaded: <span className="font-medium">{mappingStatus.subjectIdMappingFileName}</span></span>
                      <Button variant="outline" size="sm" onClick={() => handleRemoveUploadedFile("subject-id-mapping", () => { setSubjectIdMappingFile(null); setMappingFileIds((prev) => ({ ...prev, subjectIdMapping: "" })); }, "Subject ID mapping removed.")}>Remove</Button>
                    </div>
                  )}
                </div>

                <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                  <p className="text-xs font-semibold mb-2"><Clock3 className="h-4 w-4 text-primary inline-block mr-1" /> Subject Continuous Rules (Global)</p>
                  <FileUpload file={subjectContinuousRulesFile} onFileSelect={handleUploadSubjectContinuousRules} onClear={() => setSubjectContinuousRulesFile(null)} label="Upload Continuous Rules" templateLinks={buildTemplateLinks(templateBase, "subject-continuous-rules")} />
                  {mappingStatus.subjectContinuousRulesUploaded && (
                    <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-background p-3 text-xs">
                      <span>Uploaded: <span className="font-medium">{mappingStatus.subjectContinuousRulesFileName}</span></span>
                      <Button variant="outline" size="sm" onClick={() => handleRemoveUploadedFile("subject-continuous-rules", () => { setSubjectContinuousRulesFile(null); setMappingFileIds((prev) => ({ ...prev, subjectContinuousRules: "" })); }, "Subject continuous rules removed.")}>Remove</Button>
                    </div>
                  )}
                </div>

                <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                  <p className="text-xs font-semibold mb-2"><Users className="h-4 w-4 text-primary inline-block mr-1" /> Shared Classes (Global)</p>
                  <FileUpload file={sharedClassesFile} onFileSelect={uploadSharedClassesDoc} onClear={() => setSharedClassesFile(null)} label="Upload Shared Classes" templateLinks={buildTemplateLinks(templateBase, "shared-classes")} />
                  {mappingStatus.sharedClassesUploaded && (
                    <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-background p-3 text-xs">
                      <span>Uploaded: <span className="font-medium">{mappingStatus.sharedClassesFileName}</span></span>
                      <Button variant="outline" size="sm" onClick={() => handleRemoveUploadedFile("shared-classes", () => setSharedClassesFile(null), "Shared classes file removed.")}>Remove</Button>
                    </div>
                  )}
                </div>

                <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                  <p className="text-xs font-semibold mb-2"><Users className="h-4 w-4 text-primary inline-block mr-1" /> Faculty Availability (Global)</p>
                  <FileUpload file={facultyAvailabilityFile} onFileSelect={uploadFacultyAvailabilityDoc} onClear={() => setFacultyAvailabilityFile(null)} label="Upload Faculty Availability" templateLinks={buildTemplateLinks(templateBase, "faculty-availability")} />
                  {mappingStatus.facultyAvailabilityUploaded && (
                    <div className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-background p-3 text-xs">
                      <span>Uploaded: <span className="font-medium">{mappingStatus.facultyAvailabilityFileName}</span></span>
                      <Button variant="outline" size="sm" onClick={() => handleRemoveUploadedFile("faculty-availability", () => setFacultyAvailabilityFile(null), "Faculty availability file removed.")}>Remove</Button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {inputMode === "manual" && (
            <Tabs defaultValue="entries" className="w-full mt-6">
              <TabsList className="bg-muted w-full justify-start overflow-x-auto">
                <TabsTrigger value="entries">Manual Entries</TabsTrigger>
                <TabsTrigger value="subjectRules">Subject Rules</TabsTrigger>
                <TabsTrigger value="subjectMapping">Subject Mapping</TabsTrigger>
                <TabsTrigger value="labs">Lab Timetable</TabsTrigger>
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

              <TabsContent value="subjectRules" className="panel-card mt-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">Subject ID and Compulsory Continuous Hours</h3>
                  <Button variant="outline" size="sm" onClick={addSubjectContinuousRule}>
                    <Plus className="h-3.5 w-3.5 mr-1" /> Add Rule
                  </Button>
                </div>
                <div className="space-y-3">
                  {subjectContinuousRules.map((rule, i) => (
                    <div key={i} className="flex gap-3 items-end">
                      <div className="flex-1">
                        <Label className="text-xs text-muted-foreground">Subject ID</Label>
                        <Input
                          placeholder="SUB_001"
                          value={rule.subjectId}
                          onChange={(e) => {
                            const c = [...subjectContinuousRules];
                            c[i].subjectId = e.target.value;
                            setSubjectContinuousRules(c);
                          }}
                        />
                      </div>
                      <div className="w-40">
                        <Label className="text-xs text-muted-foreground">Compulsory Continuous Hours</Label>
                        <Input
                          type="number"
                          min={1}
                          max={5}
                          value={rule.compulsoryContinuousHours}
                          onChange={(e) => {
                            const c = [...subjectContinuousRules];
                            c[i].compulsoryContinuousHours = parseInt(e.target.value) || 1;
                            setSubjectContinuousRules(c);
                          }}
                        />
                      </div>
                      {subjectContinuousRules.length > 1 && (
                        <Button variant="ghost" size="icon" onClick={() => removeSubjectContinuousRule(i)} className="text-destructive">
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="subjectMapping" className="panel-card mt-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">Subject ID and Name Mapping</h3>
                  <Button variant="outline" size="sm" onClick={addSubjectIdNameMapping}>
                    <Plus className="h-3.5 w-3.5 mr-1" /> Add Mapping
                  </Button>
                </div>
                <div className="space-y-3">
                  {subjectIdNameMapping.map((entry, i) => (
                    <div key={i} className="flex gap-3 items-end">
                      <div className="w-48">
                        <Label className="text-xs text-muted-foreground">Subject ID</Label>
                        <Input
                          placeholder="SUB_001"
                          value={entry.subjectId}
                          onChange={(e) => {
                            const c = [...subjectIdNameMapping];
                            c[i].subjectId = e.target.value;
                            setSubjectIdNameMapping(c);
                          }}
                        />
                      </div>
                      <div className="flex-1">
                        <Label className="text-xs text-muted-foreground">Subject Name</Label>
                        <Input
                          placeholder="Data Structures"
                          value={entry.subjectName}
                          onChange={(e) => {
                            const c = [...subjectIdNameMapping];
                            c[i].subjectName = e.target.value;
                            setSubjectIdNameMapping(c);
                          }}
                        />
                      </div>
                      {subjectIdNameMapping.length > 1 && (
                        <Button variant="ghost" size="icon" onClick={() => removeSubjectIdNameMapping(i)} className="text-destructive">
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="labs" className="panel-card mt-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold">Lab Timetable Input</h3>
                  <Button variant="outline" size="sm" onClick={addManualLabEntry}>
                    <Plus className="h-3.5 w-3.5 mr-1" /> Add Lab Entry
                  </Button>
                </div>
                <div className="space-y-4">
                  {manualLabEntries.map((entry, i) => (
                    <div key={i} className="rounded-lg border border-border/50 p-4 bg-muted/10">
                      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-6 gap-3 items-end">
                        <div>
                          <Label className="text-xs text-muted-foreground">Year</Label>
                          <Select
                            value={entry.year}
                            onValueChange={(value) => {
                              const c = [...manualLabEntries];
                              c[i].year = value;
                              const sections = getSectionOptionsForYear(academicConfig, value);
                              if (!sections.includes(c[i].section)) {
                                c[i].section = sections[0] ?? "";
                              }
                              setManualLabEntries(c);
                            }}
                          >
                            <SelectTrigger><SelectValue /></SelectTrigger>
                            <SelectContent>
                              {getYearOptions(academicConfig).map((year) => (
                                <SelectItem key={year} value={year}>{year}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label className="text-xs text-muted-foreground">Section</Label>
                          <Select
                            value={entry.section}
                            onValueChange={(value) => {
                              const c = [...manualLabEntries];
                              c[i].section = value;
                              setManualLabEntries(c);
                            }}
                          >
                            <SelectTrigger><SelectValue /></SelectTrigger>
                            <SelectContent>
                              {getSectionOptionsForYear(academicConfig, entry.year).map((section) => (
                                <SelectItem key={section} value={section}>{section}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label className="text-xs text-muted-foreground">Subject ID</Label>
                          <Input
                            placeholder="LAB_001"
                            value={entry.subjectId}
                            onChange={(e) => {
                              const c = [...manualLabEntries];
                              c[i].subjectId = e.target.value;
                              setManualLabEntries(c);
                            }}
                          />
                        </div>
                        <div>
                          <Label className="text-xs text-muted-foreground">Day</Label>
                          <Select
                            value={String(entry.day)}
                            onValueChange={(value) => {
                              const c = [...manualLabEntries];
                              c[i].day = parseInt(value, 10);
                              setManualLabEntries(c);
                            }}
                          >
                            <SelectTrigger><SelectValue /></SelectTrigger>
                            <SelectContent>
                              {DAYS.map((day, dayIndex) => (
                                <SelectItem key={day} value={String(dayIndex + 1)}>
                                  {dayIndex + 1} - {day}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label className="text-xs text-muted-foreground">Hours</Label>
                          <Input
                            placeholder="1,2"
                            value={entry.hours.join(",")}
                            onChange={(e) => {
                              const c = [...manualLabEntries];
                              c[i].hours = toPeriodList(e.target.value);
                              setManualLabEntries(c);
                            }}
                          />
                        </div>
                        <div>
                          <Label className="text-xs text-muted-foreground">Venue</Label>
                          <Input
                            placeholder="2201"
                            value={entry.venue}
                            onChange={(e) => {
                              const c = [...manualLabEntries];
                              c[i].venue = e.target.value;
                              setManualLabEntries(c);
                            }}
                          />
                        </div>
                      </div>
                      {manualLabEntries.length > 1 && (
                        <div className="mt-3 flex justify-end">
                          <Button variant="ghost" size="sm" onClick={() => removeManualLabEntry(i)} className="text-destructive">
                            <Trash2 className="h-4 w-4 mr-1" /> Remove
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="facultyId" className="panel-card mt-4">
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

              <TabsContent value="sharedClasses" className="panel-card mt-4">
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
                        <Label className="text-xs text-muted-foreground">Sections (comma list or count)</Label>
                        <Input
                          placeholder="e.g. 1,2 or 3 (count)"
                          value={sc.sections.join(", ")}
                          onChange={(e) => {
                            const c = [...sharedClasses];
                            const raw = e.target.value.trim();
                            // Single number means "count"; backend will convert it to first N sections.
                            if (/^\\d+$/.test(raw)) {
                              c[i].sections = [raw];
                            } else {
                              c[i].sections = raw.split(",").map((s) => s.trim()).filter(Boolean);
                            }
                            setSharedClasses(c);
                          }}
                        />
                      </div>
                      <Button variant="ghost" size="icon" onClick={() => removeSharedClass(i)} className="text-destructive h-9 w-9"><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  ))}
                </div>
              </TabsContent>

              <TabsContent value="availability" className="panel-card mt-4">
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

          <div className="panel-card flex justify-end gap-3 mt-8">
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
