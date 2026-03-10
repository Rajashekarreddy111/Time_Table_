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
  SubjectEntry,
  LabEntry,
  SharedClassEntry,
  SubjectHours,
} from "@/data/mockData";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { FileUpload } from "@/components/FileUpload";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  API_BASE_URL,
  generateTimetable,
  getMappingStatus,
  uploadFacultyIdMap,
  uploadSubjectFacultyMap,
  uploadSubjectPeriodsMap,
  uploadSharedClasses,
  uploadFacultyAvailability,
  ApiError,
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
  subjectPeriodsMapUploaded: boolean;
  creamSubjectPeriodsMapUploaded?: boolean;
  generalSubjectPeriodsMapUploaded?: boolean;
  subjectFacultyMapUploaded: boolean;
  creamSubjectFacultyMapUploaded?: boolean;
  generalSubjectFacultyMapUploaded?: boolean;
  facultyIdMapFileName?: string | null;
  subjectPeriodsMapFileName?: string | null;
  creamSubjectPeriodsMapFileName?: string | null;
  generalSubjectPeriodsMapFileName?: string | null;
  subjectFacultyMapFileName?: string | null;
  creamSubjectFacultyMapFileName?: string | null;
  generalSubjectFacultyMapFileName?: string | null;
  sharedClassesUploaded?: boolean;
  sharedClassesFileName?: string | null;
  facultyAvailabilityUploaded?: boolean;
};

const EMPTY_MAPPING_STATUS: MappingStatus = {
  facultyIdMapUploaded: false,
  subjectPeriodsMapUploaded: false,
  creamSubjectPeriodsMapUploaded: false,
  generalSubjectPeriodsMapUploaded: false,
  subjectFacultyMapUploaded: false,
  creamSubjectFacultyMapUploaded: false,
  generalSubjectFacultyMapUploaded: false,
  sharedClassesUploaded: false,
  facultyAvailabilityUploaded: false,
};

const TimetableGenerator = () => {
  const navigate = useNavigate();
  const initialConfig = readAcademicConfig();
  const [academicConfig, setAcademicConfig] =
    useState<AcademicConfig>(initialConfig);
  const yearOptions = getYearOptions(academicConfig);
  const initialYear = yearOptions[0];
  const initialSections = getSectionOptionsForYear(academicConfig, initialYear);
  const [selectedYear, setSelectedYear] = useState<string>(initialYear);
  const [selectedSection, setSelectedSection] = useState<string>(
    initialSections[0] ?? "A",
  );
  const [subjects, setSubjects] = useState<SubjectEntry[]>([
    { subject: "", faculty: "" },
  ]);
  const [labs, setLabs] = useState<LabEntry[]>([{ lab: "", faculty: [] }]);
  const [sharedClasses, setSharedClasses] = useState<SharedClassEntry[]>([
    { year: initialYear, sections: [], subject: "" },
  ]);
  const [subjectHours, setSubjectHours] = useState<SubjectHours[]>([
    { subject: "", hours: 4, continuousHours: 1 },
  ]);
  const [generating, setGenerating] = useState(false);
  const [inputMode, setInputMode] = useState<"manual" | "file">("manual");
  const [facultyAvailabilityInputs, setFacultyAvailabilityInputs] = useState<
    FacultyWeeklyAvailability[]
  >([
    {
      facultyId: "",
      availablePeriodsByDay: DAYS.reduce<Record<string, string>>((acc, day) => {
        acc[day] = "";
        return acc;
      }, {}),
    },
  ]);

  const [facultyIdFile, setFacultyIdFile] = useState<File | null>(null);
  const [subjectFacultyFile, setSubjectFacultyFile] = useState<File | null>(
    null,
  );
  const [creamSubjectFacultyFile, setCreamSubjectFacultyFile] =
    useState<File | null>(null);
  const [generalSubjectFacultyFile, setGeneralSubjectFacultyFile] =
    useState<File | null>(null);
  const [subjectPeriodsFile, setSubjectPeriodsFile] = useState<File | null>(
    null,
  );
  const [creamSubjectPeriodsFile, setCreamSubjectPeriodsFile] =
    useState<File | null>(null);
  const [generalSubjectPeriodsFile, setGeneralSubjectPeriodsFile] =
    useState<File | null>(null);

  const [mappingFileIds, setMappingFileIds] = useState({
    facultyIdMap: "",
    subjectFacultyMap: "",
    subjectFacultyMapCream: "",
    subjectFacultyMapGeneral: "",
    subjectPeriodsMap: "",
    subjectPeriodsMapCream: "",
    subjectPeriodsMapGeneral: "",
  });

  const [mappingStatus, setMappingStatus] =
    useState<MappingStatus>(EMPTY_MAPPING_STATUS);
  const [sharedClassesFile, setSharedClassesFile] = useState<File | null>(null);
  const [facultyAvailabilityFile, setFacultyAvailabilityFile] =
    useState<File | null>(null);
  const mappingStatusRequestRef = useRef(0);

  const templateBase = `${API_BASE_URL}/templates`;
  const [yearConfigs, setYearConfigs] = useState<
    Record<
      string,
      {
        subjects: SubjectEntry[];
        labs: LabEntry[];
        subjectHours: SubjectHours[];
      }
    >
  >({});

  const syncYearConfig = (year: string) => {
    const config = yearConfigs[year] || {
      subjects: [{ subject: "", faculty: "" }],
      labs: [{ lab: "", faculty: [] }],
      subjectHours: [{ subject: "", hours: 4, continuousHours: 1 }],
    };
    setSubjects(config.subjects);
    setLabs(config.labs);
    setSubjectHours(config.subjectHours);
  };

  const saveCurrentYearConfig = (year: string) => {
    setYearConfigs((prev) => ({
      ...prev,
      [year]: {
        subjects,
        labs,
        subjectHours,
      },
    }));
  };

  useEffect(() => {
    syncYearConfig(selectedYear);
  }, [selectedYear]);

  // Update effect to save config periodically or on change
  useEffect(() => {
    const timer = setTimeout(() => {
      saveCurrentYearConfig(selectedYear);
    }, 500);
    return () => clearTimeout(timer);
  }, [subjects, labs, subjectHours]);

  const selectedYearStructure = getYearStructure(academicConfig, selectedYear);
  const hasCreamGeneralForSelectedYear = selectedYearStructure.hasCreamGeneral;
  const currentYearSections = getSectionOptionsForYear(
    academicConfig,
    selectedYear,
  );
  const creamSections = currentYearSections.filter((section) =>
    section.startsWith("C"),
  );
  const generalSections = currentYearSections.filter((section) =>
    section.startsWith("G"),
  );
  const subjectFacultyTemplateHref =
    `${templateBase}/subject-faculty-map` +
    `?year=${encodeURIComponent(selectedYear)}` +
    `&sectionCount=${selectedYearStructure.sectionCount}` +
    `&hasCreamGeneral=${hasCreamGeneralForSelectedYear}` +
    `&creamSectionCount=${selectedYearStructure.creamSectionCount}` +
    `&generalSectionCount=${selectedYearStructure.generalSectionCount}` +
    `&sectionList=${encodeURIComponent(currentYearSections.join(","))}`;
  const creamSubjectFacultyTemplateHref =
    `${templateBase}/subject-faculty-map` +
    `?year=${encodeURIComponent(selectedYear)}` +
    `&hasCreamGeneral=true` +
    `&creamSectionCount=${creamSections.length}` +
    `&generalSectionCount=0` +
    `&sectionList=${encodeURIComponent(creamSections.join(","))}`;
  const generalSubjectFacultyTemplateHref =
    `${templateBase}/subject-faculty-map` +
    `?year=${encodeURIComponent(selectedYear)}` +
    `&hasCreamGeneral=true` +
    `&creamSectionCount=0` +
    `&generalSectionCount=${generalSections.length}` +
    `&sectionList=${encodeURIComponent(generalSections.join(","))}`;

  const addSubject = () =>
    setSubjects([...subjects, { subject: "", faculty: "" }]);
  const removeSubject = (i: number) =>
    setSubjects(subjects.filter((_, idx) => idx !== i));
  const addLab = () => setLabs([...labs, { lab: "", faculty: [] }]);
  const removeLab = (i: number) => setLabs(labs.filter((_, idx) => idx !== i));
  const addSharedClass = () => {
    const defaultYear = getYearOptions(academicConfig)[0] ?? "1st Year";
    setSharedClasses([
      ...sharedClasses,
      { year: defaultYear, sections: [], subject: "" },
    ]);
  };
  const removeSharedClass = (i: number) =>
    setSharedClasses(sharedClasses.filter((_, idx) => idx !== i));
  const addSubjectHour = () =>
    setSubjectHours([
      ...subjectHours,
      { subject: "", hours: 4, continuousHours: 1 },
    ]);
  const removeSubjectHour = (i: number) =>
    setSubjectHours(subjectHours.filter((_, idx) => idx !== i));

  const addFacultyAvailabilityInput = () => {
    setFacultyAvailabilityInputs([
      ...facultyAvailabilityInputs,
      {
        facultyId: "",
        availablePeriodsByDay: DAYS.reduce<Record<string, string>>(
          (acc, day) => {
            acc[day] = "";
            return acc;
          },
          {},
        ),
      },
    ]);
  };

  const removeFacultyAvailabilityInput = (i: number) => {
    setFacultyAvailabilityInputs(
      facultyAvailabilityInputs.filter((_, idx) => idx !== i),
    );
  };

  const updateAcademicConfig = (next: AcademicConfig) => {
    setAcademicConfig(next);
    saveAcademicConfig(next);

    const years = getYearOptions(next);
    const safeYear = years.includes(selectedYear) ? selectedYear : years[0];
    setSelectedYear(safeYear);
    const sections = getSectionOptionsForYear(next, safeYear);
    if (!sections.includes(selectedSection)) {
      setSelectedSection(sections[0] ?? "A");
    }
  };

  const updateYearStructure = (
    yearIndex: number,
    updater: (
      current: AcademicConfig["years"][number],
    ) => AcademicConfig["years"][number],
  ) => {
    const next: AcademicConfig = {
      yearCount: academicConfig.yearCount,
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
    if (next.years[yearIndex].hasCreamGeneral) {
      next.years[yearIndex].sectionCount =
        next.years[yearIndex].creamSectionCount +
        next.years[yearIndex].generalSectionCount;
    } else {
      next.years[yearIndex].creamSectionCount = 0;
      next.years[yearIndex].generalSectionCount = 0;
      next.years[yearIndex].sectionCount = Math.max(
        1,
        next.years[yearIndex].sectionCount,
      );
    }
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

    // Reset local file selection states to prevent state bleed
    setFacultyIdFile(null);
    setSubjectFacultyFile(null);
    setCreamSubjectFacultyFile(null);
    setGeneralSubjectFacultyFile(null);
    setSubjectPeriodsFile(null);
    setCreamSubjectPeriodsFile(null);
    setGeneralSubjectPeriodsFile(null);
    setSharedClassesFile(null);
    setFacultyAvailabilityFile(null);

    // Reset mapping file IDs to prevent mixing between years
    setMappingFileIds({
      facultyIdMap: "",
      subjectFacultyMap: "",
      subjectFacultyMapCream: "",
      subjectFacultyMapGeneral: "",
      subjectPeriodsMap: "",
      subjectPeriodsMapCream: "",
      subjectPeriodsMapGeneral: "",
    });
  }, [selectedYear, selectedSection]);

  const showDetailedError = (error: unknown, fallbackMessage: string) => {
    console.error("DEBUG: Operation failed", { error, fallbackMessage });
    if (
      error instanceof ApiError &&
      error.details &&
      error.details.length > 0
    ) {
      const hint =
        (error.details[0] as Record<string, string>)?.hint ||
        (error.details[0] as Record<string, string>)?.tip;
      if (hint) {
        toast.error(`${error.message}. Hint: ${hint}`, { duration: 6000 });
        return;
      }
    }

    if (error instanceof Error && error.message.includes("Failed to fetch")) {
      toast.error(
        "Network error: Failed to fetch. Please check if the backend server is running and reachable.",
        { duration: 8000 },
      );
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

  const uploadSubjectFaculty = async (file: File) => {
    setSubjectFacultyFile(file);
    try {
      const response = await uploadSubjectFacultyMap(file, selectedYear, "ALL");
      setMappingFileIds((prev) => ({
        ...prev,
        subjectFacultyMap: response.fileId,
      }));
      toast.success("Subject-faculty map uploaded.");
      loadMappingStatus(selectedYear);
    } catch (error) {
      showDetailedError(error, "Subject-faculty upload failed");
    }
  };

  const uploadCreamSubjectFaculty = async (file: File) => {
    setCreamSubjectFacultyFile(file);
    try {
      const response = await uploadSubjectFacultyMap(
        file,
        selectedYear,
        "CREAM",
      );
      setMappingFileIds((prev) => ({
        ...prev,
        subjectFacultyMapCream: response.fileId,
      }));
      toast.success("CREAM subject-faculty map uploaded.");
      loadMappingStatus(selectedYear);
    } catch (error) {
      showDetailedError(error, "CREAM subject-faculty upload failed");
    }
  };

  const uploadGeneralSubjectFaculty = async (file: File) => {
    setGeneralSubjectFacultyFile(file);
    try {
      const response = await uploadSubjectFacultyMap(
        file,
        selectedYear,
        "GENERAL",
      );
      setMappingFileIds((prev) => ({
        ...prev,
        subjectFacultyMapGeneral: response.fileId,
      }));
      toast.success("GENERAL subject-faculty map uploaded.");
      loadMappingStatus(selectedYear);
    } catch (error) {
      showDetailedError(error, "GENERAL subject-faculty upload failed");
    }
  };

  const uploadSubjectPeriods = async (file: File) => {
    setSubjectPeriodsFile(file);
    try {
      const response = await uploadSubjectPeriodsMap(file, selectedYear, "ALL");
      setMappingFileIds((prev) => ({
        ...prev,
        subjectPeriodsMap: response.fileId,
      }));
      toast.success("Subject-periods map uploaded.");
      loadMappingStatus(selectedYear);
    } catch (error) {
      showDetailedError(error, "Subject-periods upload failed");
    }
  };

  const uploadCreamSubjectPeriods = async (file: File) => {
    setCreamSubjectPeriodsFile(file);
    try {
      const response = await uploadSubjectPeriodsMap(
        file,
        selectedYear,
        "CREAM",
      );
      setMappingFileIds((prev) => ({
        ...prev,
        subjectPeriodsMapCream: response.fileId,
      }));
      toast.success("CREAM subject-periods map uploaded.");
      loadMappingStatus(selectedYear);
    } catch (error) {
      showDetailedError(error, "CREAM subject-periods upload failed");
    }
  };

  const uploadGeneralSubjectPeriods = async (file: File) => {
    setGeneralSubjectPeriodsFile(file);
    try {
      const response = await uploadSubjectPeriodsMap(
        file,
        selectedYear,
        "GENERAL",
      );
      setMappingFileIds((prev) => ({
        ...prev,
        subjectPeriodsMapGeneral: response.fileId,
      }));
      toast.success("GENERAL subject-periods map uploaded.");
      loadMappingStatus(selectedYear);
    } catch (error) {
      showDetailedError(error, "GENERAL subject-periods upload failed");
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

  const handleGenerate = async () => {
    const hasRequiredPeriodMaps = hasCreamGeneralForSelectedYear
      ? Boolean(
          mappingStatus.creamSubjectPeriodsMapUploaded &&
          mappingStatus.generalSubjectPeriodsMapUploaded,
        )
      : Boolean(mappingStatus.subjectPeriodsMapUploaded);
    const hasRequiredSubjectFacultyMaps = hasCreamGeneralForSelectedYear
      ? Boolean(
          mappingStatus.creamSubjectFacultyMapUploaded &&
          mappingStatus.generalSubjectFacultyMapUploaded,
        )
      : Boolean(mappingStatus.subjectFacultyMapUploaded);

    if (
      inputMode === "file" &&
      (!mappingStatus.facultyIdMapUploaded ||
        !hasRequiredSubjectFacultyMaps ||
        !hasRequiredPeriodMaps)
    ) {
      toast.error(
        "Required mappings are missing. Upload them once based on scope before generating.",
      );
      return;
    }

    if (inputMode === "manual") {
      const hasSubjects = subjects.some(
        (s) => s.subject.trim() && s.faculty.trim(),
      );
      const hasHours = subjectHours.some(
        (h) => h.subject.trim() && h.hours > 0,
      );
      if (!hasSubjects || !hasHours) {
        toast.error(
          "Enter at least one valid subject/faculty and hours config.",
        );
        return;
      }
    }

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
        availablePeriodsByDay: DAYS.reduce<Record<string, number[]>>(
          (acc, day) => {
            acc[day] = toPeriodList(entry.availablePeriodsByDay[day] ?? "");
            return acc;
          },
          {},
        ),
      }))
      .filter((entry) => entry.facultyId);

    const payload = {
      year: selectedYear,
      section: selectedSection,
      sectionBatchMap: getSectionBatchMapForYear(academicConfig, selectedYear),
      subjects:
        inputMode === "manual"
          ? subjects.filter((s) => s.subject.trim() && s.faculty.trim())
          : [],
      labs:
        inputMode === "manual"
          ? labs.filter((l) => l.lab.trim() && l.faculty.length > 0)
          : [],
      sharedClasses: cleanedShared,
      subjectHours:
        inputMode === "manual"
          ? subjectHours.filter((h) => h.subject.trim() && h.hours > 0)
          : [],
      facultyAvailability,
      mappingFileIds:
        inputMode === "file"
          ? {
              facultyIdMap: mappingFileIds.facultyIdMap || undefined,
              subjectFacultyMap: mappingFileIds.subjectFacultyMap || undefined,
              subjectFacultyMapCream:
                mappingFileIds.subjectFacultyMapCream || undefined,
              subjectFacultyMapGeneral:
                mappingFileIds.subjectFacultyMapGeneral || undefined,
              subjectPeriodsMap: mappingFileIds.subjectPeriodsMap || undefined,
              subjectPeriodsMapCream:
                mappingFileIds.subjectPeriodsMapCream || undefined,
              subjectPeriodsMapGeneral:
                mappingFileIds.subjectPeriodsMapGeneral || undefined,
            }
          : undefined,
    };

    setGenerating(true);
    try {
      const response = await generateTimetable(payload);
      localStorage.setItem("latestTimetableId", response.timetableId);
      toast.success("Timetable generated successfully.");
      navigate(
        `/timetables?timetableId=${encodeURIComponent(response.timetableId)}`,
      );
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
        availablePeriodsByDay: DAYS.reduce<Record<string, number[]>>(
          (acc, day) => {
            acc[day] = toPeriodList(entry.availablePeriodsByDay[day] ?? "");
            return acc;
          },
          {},
        ),
      }))
      .filter((entry) => entry.facultyId);

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

          const yearStructure = getYearStructure(academicConfig, year);
          const hasCreamGeneral = yearStructure.hasCreamGeneral;
          const hasRequiredPeriodMaps = hasCreamGeneral
            ? Boolean(
                yearMappingStatus.creamSubjectPeriodsMapUploaded &&
                  yearMappingStatus.generalSubjectPeriodsMapUploaded,
              )
            : Boolean(yearMappingStatus.subjectPeriodsMapUploaded);
          const hasRequiredSubjectFacultyMaps = hasCreamGeneral
            ? Boolean(
                yearMappingStatus.creamSubjectFacultyMapUploaded &&
                  yearMappingStatus.generalSubjectFacultyMapUploaded,
              )
            : Boolean(yearMappingStatus.subjectFacultyMapUploaded);

          if (
            !yearMappingStatus.facultyIdMapUploaded ||
            !hasRequiredSubjectFacultyMaps ||
            !hasRequiredPeriodMaps
          ) {
            errors.push(`${year}: Required mappings not uploaded — skipped`);
            continue;
          }
        }

        const primarySection = yearSections[0];
        // Use flushSync pattern to ensure the debounce for yearConfigs is applied immediately for the active year
        const currentYearConfig = {
          subjects: [...subjects],
          labs: [...labs],
          subjectHours: [...subjectHours],
        };
        const yearConfig = year === selectedYear ? currentYearConfig : (yearConfigs[year] ?? {
          subjects: [],
          labs: [],
          subjectHours: [],
        });

        const payload = {
          year,
          section: primarySection,
          sectionBatchMap: getSectionBatchMapForYear(academicConfig, year),
          subjects:
            inputMode === "manual"
              ? yearConfig.subjects.filter(
                  (s) => s.subject.trim() && s.faculty.trim(),
                )
              : [],
          labs:
            inputMode === "manual"
              ? yearConfig.labs.filter(
                  (l) => l.lab.trim() && l.faculty.length > 0,
                )
              : [],
          sharedClasses: cleanedShared,
          subjectHours:
            inputMode === "manual"
              ? yearConfig.subjectHours.filter(
                  (h) => h.subject.trim() && h.hours > 0,
                )
              : [],
          facultyAvailability,
          mappingFileIds: inputMode === "file" ? undefined : undefined,
        };

        if (inputMode === "manual" && payload.subjects.length === 0 && payload.labs.length === 0) {
          errors.push(`${year}: No subjects or labs configured`);
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
        toast.warning(
          `Generated ${successCount} year(s). Issues: ${errors.join("; ")}`,
          { duration: 8000 },
        );
      } else {
        toast.success(
          `Timetables generated for all ${successCount} year(s) successfully.`,
        );
      }
      if (firstTimetableId) {
        localStorage.setItem("latestTimetableId", firstTimetableId);
        navigate(
          `/timetables?timetableId=${encodeURIComponent(firstTimetableId)}`,
        );
      }
    } else {
      toast.error(
        errors.length > 0
          ? `Generation failed for all years: ${errors.join("; ")}`
          : "No years could be generated. Please check your uploads.",
        { duration: 8000 },
      );
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
          <LoadingSpinner message="Generating timetable... Applying constraints and resolving conflicts" />
        </div>
      ) : (
        <div className="space-y-6">
          <div className="bg-card rounded-xl p-6 shadow-sm border border-border/60">
            <h2 className="text-base font-semibold text-foreground mb-4">
              Academic Structure
            </h2>
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 items-start">
              <div className="lg:col-span-1">
                <Label className="text-xs text-muted-foreground">
                  Number of Years
                </Label>
                <Input
                  type="number"
                  min={1}
                  max={20}
                  value={academicConfig.yearCount}
                  onFocus={(e) => e.currentTarget.select()}
                  onChange={(e) => {
                    const yearCount = Math.max(
                      1,
                      Math.min(20, parseInt(e.target.value, 10) || 1),
                    );
                    const nextYears = Array.from(
                      { length: yearCount },
                      (_, idx) => {
                        return (
                          academicConfig.years[idx] ?? {
                            hasCreamGeneral: false,
                            sectionCount: 4,
                            creamSectionCount: 0,
                            generalSectionCount: 0,
                          }
                        );
                      },
                    );
                    updateAcademicConfig({ yearCount, years: nextYears });
                  }}
                />
              </div>
              <div className="lg:col-span-2">
                <Label className="text-xs text-muted-foreground">
                  Batch Structure Per Year
                </Label>
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2">
                  {getYearOptions(academicConfig).map((yearLabel, idx) => (
                    <div
                      key={yearLabel}
                      className="rounded-md border border-border/60 px-3 py-3 bg-muted/20 space-y-2"
                    >
                      <Label className="text-[11px] text-muted-foreground whitespace-nowrap">
                        {yearLabel}
                      </Label>
                      <div>
                        <Label className="text-[11px] text-muted-foreground">
                          Has CREAM and GENERAL?
                        </Label>
                        <Select
                          value={
                            academicConfig.years[idx]?.hasCreamGeneral
                              ? "YES"
                              : "NO"
                          }
                          onValueChange={(value) => {
                            updateYearStructure(idx, (current) => {
                              if (value === "YES") {
                                const cream =
                                  current.creamSectionCount > 0
                                    ? current.creamSectionCount
                                    : current.sectionCount;
                                return {
                                  ...current,
                                  hasCreamGeneral: true,
                                  creamSectionCount: cream,
                                  generalSectionCount:
                                    current.generalSectionCount,
                                  sectionCount:
                                    cream + current.generalSectionCount,
                                };
                              }
                              return {
                                ...current,
                                hasCreamGeneral: false,
                                sectionCount: Math.max(
                                  1,
                                  current.sectionCount ||
                                    current.creamSectionCount +
                                      current.generalSectionCount ||
                                    1,
                                ),
                                creamSectionCount: 0,
                                generalSectionCount: 0,
                              };
                            });
                          }}
                        >
                          <SelectTrigger className="h-8">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="YES">YES</SelectItem>
                            <SelectItem value="NO">NO</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      {academicConfig.years[idx]?.hasCreamGeneral ? (
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <Label className="text-[11px] text-muted-foreground">
                              CREAM Sections
                            </Label>
                            <Input
                              type="number"
                              min={0}
                              max={60}
                              value={
                                academicConfig.years[idx]?.creamSectionCount ??
                                0
                              }
                              className="h-8"
                              onFocus={(e) => e.currentTarget.select()}
                              onChange={(e) => {
                                const count = Math.max(
                                  0,
                                  Math.min(
                                    60,
                                    parseInt(e.target.value, 10) || 0,
                                  ),
                                );
                                updateYearStructure(idx, (current) => ({
                                  ...current,
                                  hasCreamGeneral: true,
                                  creamSectionCount: count,
                                  sectionCount:
                                    count + current.generalSectionCount,
                                }));
                              }}
                            />
                          </div>
                          <div>
                            <Label className="text-[11px] text-muted-foreground">
                              GENERAL Sections
                            </Label>
                            <Input
                              type="number"
                              min={0}
                              max={60}
                              value={
                                academicConfig.years[idx]
                                  ?.generalSectionCount ?? 0
                              }
                              className="h-8"
                              onFocus={(e) => e.currentTarget.select()}
                              onChange={(e) => {
                                const count = Math.max(
                                  0,
                                  Math.min(
                                    60,
                                    parseInt(e.target.value, 10) || 0,
                                  ),
                                );
                                updateYearStructure(idx, (current) => ({
                                  ...current,
                                  hasCreamGeneral: true,
                                  generalSectionCount: count,
                                  sectionCount:
                                    count + current.creamSectionCount,
                                }));
                              }}
                            />
                          </div>
                        </div>
                      ) : (
                        <div>
                          <Label className="text-[11px] text-muted-foreground">
                            Number of Sections
                          </Label>
                          <Input
                            type="number"
                            min={1}
                            max={60}
                            value={academicConfig.years[idx]?.sectionCount ?? 4}
                            className="h-8"
                            onFocus={(e) => e.currentTarget.select()}
                            onChange={(e) => {
                              const count = Math.max(
                                1,
                                Math.min(60, parseInt(e.target.value, 10) || 1),
                              );
                              updateYearStructure(idx, (current) => ({
                                ...current,
                                hasCreamGeneral: false,
                                sectionCount: count,
                              }));
                            }}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-3">
              Active sections:{" "}
              {getAllSectionKeys(academicConfig)
                .map(
                  (item) => `${item.year.replace(" Year", "")}${item.section}`,
                )
                .join(", ")}
            </p>
          </div>

          <div className="bg-card rounded-xl p-6 shadow-sm border border-border/60">
            <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
              <Plus className="h-4 w-4 text-primary" /> Global & Cross-Year
              Constraints
            </h2>
            <div className="space-y-6">
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                  <p className="text-xs font-semibold text-foreground mb-2 flex items-center gap-2">
                    Shared Classes Constraints (Document)
                  </p>
                  {mappingStatus.sharedClassesUploaded ? (
                    <div className="rounded-lg border border-border/70 bg-background p-4 text-xs text-muted-foreground">
                      Uploaded once globally:{" "}
                      <span className="font-medium text-foreground">
                        {mappingStatus.sharedClassesFileName ??
                          "Already uploaded"}
                      </span>
                    </div>
                  ) : (
                    <FileUpload
                      file={sharedClassesFile}
                      onFileSelect={uploadSharedClassesDoc}
                      onClear={() => {
                        setSharedClassesFile(null);
                      }}
                      accept=".xlsx,.xls,.csv"
                      label="Upload shared-classes mapping"
                      description="Spreadsheet defining shared classes between sections"
                      templateLinks={[
                        {
                          label: "Download Template",
                          href: `${templateBase}/shared-classes`,
                        },
                      ]}
                    />
                  )}
                </div>
                <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                  <p className="text-xs font-semibold text-foreground mb-2 flex items-center gap-2">
                    Faculty Availability (Document)
                  </p>
                  {mappingStatus.facultyAvailabilityUploaded ? (
                    <div className="rounded-lg border border-border/70 bg-background p-4 text-xs text-muted-foreground">
                      Uploaded:{" "}
                      <span className="font-medium text-foreground">
                        Available globally
                      </span>
                    </div>
                  ) : (
                    <FileUpload
                      file={facultyAvailabilityFile}
                      onFileSelect={uploadFacultyAvailabilityDoc}
                      onClear={() => {
                        setFacultyAvailabilityFile(null);
                      }}
                      accept=".xlsx,.xls,.csv"
                      label="Upload faculty availability"
                      description="Spreadsheet defining faculty constrained periods"
                      templateLinks={[
                        {
                          label: "Download Template",
                          href: `${templateBase}/faculty-availability`,
                        },
                      ]}
                    />
                  )}
                </div>
              </div>

              <div className="space-y-4">
                <div className="rounded-xl border border-border/70 p-4 bg-muted/10">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-foreground">
                      Manual Shared Classes
                    </h3>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={addSharedClass}
                    >
                      <Plus className="h-3.5 w-3.5 mr-1" /> Add Constraint
                    </Button>
                  </div>
                  <div className="space-y-3">
                    {sharedClasses.map((sc, i) => (
                      <div
                        key={i}
                        className="flex gap-3 items-end flex-wrap md:flex-nowrap"
                      >
                        <div className="w-full md:w-32">
                          <Label className="text-[10px] text-muted-foreground">
                            Year
                          </Label>
                          <Select
                            value={sc.year}
                            onValueChange={(v) => {
                              const copy = [...sharedClasses];
                              copy[i].year = v;
                              setSharedClasses(copy);
                            }}
                          >
                            <SelectTrigger className="h-9 text-xs">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {getYearOptions(academicConfig).map((y) => (
                                <SelectItem key={y} value={y}>
                                  {y}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="flex-1 min-w-[120px]">
                          <Label className="text-[10px] text-muted-foreground">
                            Subject
                          </Label>
                          <Input
                            placeholder="Math"
                            value={sc.subject}
                            onChange={(e) => {
                              const copy = [...sharedClasses];
                              copy[i].subject = e.target.value;
                              setSharedClasses(copy);
                            }}
                            className="h-9 text-xs"
                          />
                        </div>
                        <div className="flex-[2] min-w-[200px]">
                          <Label className="text-[10px] text-muted-foreground">
                            Sections (comma-separated)
                          </Label>
                          <Input
                            placeholder="A, B, C"
                            value={sc.sections.join(", ")}
                            onChange={(e) => {
                              const copy = [...sharedClasses];
                              copy[i].sections = e.target.value
                                .split(",")
                                .map((s) => s.trim())
                                .filter(Boolean);
                              setSharedClasses(copy);
                            }}
                            className="h-9 text-xs"
                          />
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => removeSharedClass(i)}
                          className="text-destructive h-9 w-9"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    ))}
                    {sharedClasses.length === 0 && (
                      <p className="text-xs text-muted-foreground italic">
                        No manual shared classes defined.
                      </p>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-border/70 p-4 bg-muted/10">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-foreground">
                      Manual Faculty Availability
                    </h3>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={addFacultyAvailabilityInput}
                    >
                      <Plus className="h-3.5 w-3.5 mr-1" /> Add Faculty
                    </Button>
                  </div>
                  <div className="space-y-4">
                    {facultyAvailabilityInputs.map((fa, i) => (
                      <div
                        key={i}
                        className="p-3 rounded-lg border border-border/40 bg-background/50 relative"
                      >
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => removeFacultyAvailabilityInput(i)}
                          className="text-destructive absolute top-1 right-1 h-7 w-7"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                          <div className="md:col-span-1">
                            <Label className="text-[10px] text-muted-foreground">
                              Faculty ID
                            </Label>
                            <Input
                              placeholder="F-001"
                              value={fa.facultyId}
                              onChange={(e) => {
                                const copy = [...facultyAvailabilityInputs];
                                copy[i].facultyId = e.target.value;
                                setFacultyAvailabilityInputs(copy);
                              }}
                              className="h-8 text-xs"
                            />
                          </div>
                          <div className="md:col-span-3 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
                            {DAYS.map((day) => (
                              <div key={day}>
                                <Label className="text-[10px] text-muted-foreground uppercase">
                                  {day.substring(0, 3)}
                                </Label>
                                <Input
                                  placeholder="1,2"
                                  value={fa.availablePeriodsByDay[day]}
                                  onChange={(e) => {
                                    const copy = [...facultyAvailabilityInputs];
                                    copy[i].availablePeriodsByDay[day] =
                                      e.target.value;
                                    setFacultyAvailabilityInputs(copy);
                                  }}
                                  className="h-7 text-[10px] px-2"
                                />
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    ))}
                    {facultyAvailabilityInputs.length === 0 && (
                      <p className="text-xs text-muted-foreground italic">
                        No manual availability constraints defined.
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-card rounded-xl p-6 shadow-sm border border-border/60">
            <h2 className="text-base font-semibold text-foreground mb-4">
              Select Year and Section
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-w-md">
              <div>
                <Label className="text-xs text-muted-foreground">Year</Label>
                <Select
                  value={selectedYear}
                  onValueChange={(year) => {
                    setSelectedYear(year);
                    const sections = getSectionOptionsForYear(
                      academicConfig,
                      year,
                    );
                    setSelectedSection(sections[0] ?? "A");
                  }}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {getYearOptions(academicConfig).map((y) => (
                      <SelectItem key={y} value={y}>
                        {y}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">Section</Label>
                <Select
                  value={selectedSection}
                  onValueChange={setSelectedSection}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {getSectionOptionsForYear(academicConfig, selectedYear).map(
                      (s) => (
                        <SelectItem key={s} value={s}>
                          {s}
                        </SelectItem>
                      ),
                    )}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <div className="bg-card rounded-xl p-6 shadow-sm border border-border/60">
            <h2 className="text-base font-semibold text-foreground mb-4">
              Data Input Method
            </h2>
            <div className="flex flex-wrap gap-3">
              <Button
                variant={inputMode === "manual" ? "default" : "outline"}
                onClick={() => setInputMode("manual")}
                className="gap-2"
              >
                <Wand2 className="h-4 w-4" /> Manual Entry
              </Button>
              <Button
                variant={inputMode === "file" ? "default" : "outline"}
                onClick={() => setInputMode("file")}
                className="gap-2"
              >
                <Upload className="h-4 w-4" /> Upload Files
              </Button>
            </div>
          </div>

          {inputMode === "file" && (
            <div className="bg-card rounded-xl p-6 shadow-sm space-y-5 border border-border/60">
              <p className="text-xs text-muted-foreground">
                Scope for current selection: Subject-faculty is locked per{" "}
                <span className="font-medium text-foreground">
                  Year ({selectedYear})
                </span>
                , Faculty-ID is global.
                {hasCreamGeneralForSelectedYear ? (
                  <>
                    {" "}
                    Subject-faculty and subject-periods each need two uploads:{" "}
                    <span className="font-medium text-foreground">
                      CREAM + GENERAL
                    </span>
                    .
                  </>
                ) : (
                  <>
                    {" "}
                    Subject-faculty and subject-periods each need one upload for
                    the year.
                  </>
                )}
              </p>
              <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                  <p className="text-xs font-semibold text-foreground mb-2 flex items-center gap-2">
                    <Users className="h-4 w-4 text-primary" /> Faculty Name and
                    ID Mapping
                  </p>
                  {mappingStatus.facultyIdMapUploaded ? (
                    <div className="rounded-lg border border-border/70 bg-background p-4 text-xs text-muted-foreground">
                      Uploaded once globally:{" "}
                      <span className="font-medium text-foreground">
                        {mappingStatus.facultyIdMapFileName ??
                          "Already uploaded"}
                      </span>
                    </div>
                  ) : (
                    <FileUpload
                      file={facultyIdFile}
                      onFileSelect={uploadFacultyId}
                      onClear={() => {
                        setFacultyIdFile(null);
                      }}
                      accept=".xlsx,.xls,.csv"
                      label="Upload faculty-id mapping file"
                      description="Spreadsheet with faculty name mapped to unique faculty id"
                      templateLinks={[
                        {
                          label: "Download Template",
                          href: `${templateBase}/faculty-id-map`,
                        },
                      ]}
                    />
                  )}
                </div>
                <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                  <p className="text-xs font-semibold text-foreground mb-2 flex items-center gap-2">
                    <BookOpen className="h-4 w-4 text-primary" /> Subject and
                    Faculty Mapping{" "}
                    {hasCreamGeneralForSelectedYear ? "(CREAM)" : ""}
                  </p>
                  {hasCreamGeneralForSelectedYear ? (
                    mappingStatus.creamSubjectFacultyMapUploaded ? (
                      <div className="rounded-lg border border-border/70 bg-background p-4 text-xs text-muted-foreground">
                        Uploaded once for {selectedYear} CREAM:{" "}
                        <span className="font-medium text-foreground">
                          {mappingStatus.creamSubjectFacultyMapFileName ??
                            "Already uploaded"}
                        </span>
                      </div>
                    ) : (
                      <FileUpload
                        file={creamSubjectFacultyFile}
                        onFileSelect={uploadCreamSubjectFaculty}
                        onClear={() => {
                          setCreamSubjectFacultyFile(null);
                        }}
                        accept=".xlsx,.xls,.csv"
                        label={`Upload CREAM subject-faculty map (${selectedYear})`}
                        description="Spreadsheet mapping CREAM sections to faculty for this year"
                        templateLinks={[
                          {
                            label: "Download CREAM Template",
                            href: creamSubjectFacultyTemplateHref,
                          },
                        ]}
                      />
                    )
                  ) : mappingStatus.subjectFacultyMapUploaded ? (
                    <div className="rounded-lg border border-border/70 bg-background p-4 text-xs text-muted-foreground">
                      Uploaded once for {selectedYear}:{" "}
                      <span className="font-medium text-foreground">
                        {mappingStatus.subjectFacultyMapFileName ??
                          "Already uploaded"}
                      </span>
                    </div>
                  ) : (
                    <FileUpload
                      file={subjectFacultyFile}
                      onFileSelect={uploadSubjectFaculty}
                      onClear={() => {
                        setSubjectFacultyFile(null);
                      }}
                      accept=".xlsx,.xls,.csv"
                      label={`Upload subject-faculty map (${selectedYear})`}
                      description="Spreadsheet mapping each section's subjects to faculty for this year"
                      templateLinks={[
                        {
                          label: "Download Template",
                          href: subjectFacultyTemplateHref,
                        },
                      ]}
                    />
                  )}
                </div>
                {hasCreamGeneralForSelectedYear && (
                  <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                    <p className="text-xs font-semibold text-foreground mb-2 flex items-center gap-2">
                      <BookOpen className="h-4 w-4 text-primary" /> Subject and
                      Faculty Mapping (GENERAL)
                    </p>
                    {mappingStatus.generalSubjectFacultyMapUploaded ? (
                      <div className="rounded-lg border border-border/70 bg-background p-4 text-xs text-muted-foreground">
                        Uploaded once for {selectedYear} GENERAL:{" "}
                        <span className="font-medium text-foreground">
                          {mappingStatus.generalSubjectFacultyMapFileName ??
                            "Already uploaded"}
                        </span>
                      </div>
                    ) : (
                      <FileUpload
                        file={generalSubjectFacultyFile}
                        onFileSelect={uploadGeneralSubjectFaculty}
                        onClear={() => {
                          setGeneralSubjectFacultyFile(null);
                        }}
                        accept=".xlsx,.xls,.csv"
                        label={`Upload GENERAL subject-faculty map (${selectedYear})`}
                        description="Spreadsheet mapping GENERAL sections to faculty for this year"
                        templateLinks={[
                          {
                            label: "Download GENERAL Template",
                            href: generalSubjectFacultyTemplateHref,
                          },
                        ]}
                      />
                    )}
                  </div>
                )}
                <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                  <p className="text-xs font-semibold text-foreground mb-2 flex items-center gap-2">
                    <Clock3 className="h-4 w-4 text-primary" /> Subject and
                    Period Allocation{" "}
                    {hasCreamGeneralForSelectedYear ? "(CREAM)" : ""}
                  </p>
                  {hasCreamGeneralForSelectedYear ? (
                    mappingStatus.creamSubjectPeriodsMapUploaded ? (
                      <div className="rounded-lg border border-border/70 bg-background p-4 text-xs text-muted-foreground">
                        Uploaded once for {selectedYear} CREAM:{" "}
                        <span className="font-medium text-foreground">
                          {mappingStatus.creamSubjectPeriodsMapFileName ??
                            "Already uploaded"}
                        </span>
                      </div>
                    ) : (
                      <FileUpload
                        file={creamSubjectPeriodsFile}
                        onFileSelect={uploadCreamSubjectPeriods}
                        onClear={() => {
                          setCreamSubjectPeriodsFile(null);
                        }}
                        accept=".xlsx,.xls,.csv"
                        label={`Upload CREAM subject-period map (${selectedYear})`}
                        description="Spreadsheet with CREAM subject hours per week"
                        templateLinks={[
                          {
                            label: "Download CREAM Template",
                            href: `${templateBase}/subject-periods-map?batchType=CREAM`,
                          },
                        ]}
                      />
                    )
                  ) : mappingStatus.subjectPeriodsMapUploaded ? (
                    <div className="rounded-lg border border-border/70 bg-background p-4 text-xs text-muted-foreground">
                      Uploaded once for {selectedYear}:{" "}
                      <span className="font-medium text-foreground">
                        {mappingStatus.subjectPeriodsMapFileName ??
                          "Already uploaded"}
                      </span>
                    </div>
                  ) : (
                    <FileUpload
                      file={subjectPeriodsFile}
                      onFileSelect={uploadSubjectPeriods}
                      onClear={() => {
                        setSubjectPeriodsFile(null);
                      }}
                      accept=".xlsx,.xls,.csv"
                      label={`Upload subject-period map (${selectedYear})`}
                      description="Spreadsheet with subject hours per week"
                      templateLinks={[
                        {
                          label: "Download Template",
                          href: `${templateBase}/subject-periods-map`,
                        },
                      ]}
                    />
                  )}
                </div>
                {hasCreamGeneralForSelectedYear && (
                  <div className="rounded-xl border border-border/70 p-3 bg-muted/20">
                    <p className="text-xs font-semibold text-foreground mb-2 flex items-center gap-2">
                      <Clock3 className="h-4 w-4 text-primary" /> Subject and
                      Period Allocation (GENERAL)
                    </p>
                    {mappingStatus.generalSubjectPeriodsMapUploaded ? (
                      <div className="rounded-lg border border-border/70 bg-background p-4 text-xs text-muted-foreground">
                        Uploaded once for {selectedYear} GENERAL:{" "}
                        <span className="font-medium text-foreground">
                          {mappingStatus.generalSubjectPeriodsMapFileName ??
                            "Already uploaded"}
                        </span>
                      </div>
                    ) : (
                      <FileUpload
                        file={generalSubjectPeriodsFile}
                        onFileSelect={uploadGeneralSubjectPeriods}
                        onClear={() => {
                          setGeneralSubjectPeriodsFile(null);
                        }}
                        accept=".xlsx,.xls,.csv"
                        label={`Upload GENERAL subject-period map (${selectedYear})`}
                        description="Spreadsheet with GENERAL subject hours per week"
                        templateLinks={[
                          {
                            label: "Download GENERAL Template",
                            href: `${templateBase}/subject-periods-map?batchType=GENERAL`,
                          },
                        ]}
                      />
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {inputMode === "manual" && (
            <Tabs defaultValue="subjects" className="w-full">
              <TabsList className="bg-muted w-full justify-start">
                <TabsTrigger value="subjects">Subjects and Faculty</TabsTrigger>
                <TabsTrigger value="labs">Labs</TabsTrigger>
                <TabsTrigger value="hours">Hours Config</TabsTrigger>
              </TabsList>

              <TabsContent
                value="subjects"
                className="bg-card rounded-xl p-6 shadow-sm mt-4 border border-border/60"
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-foreground">
                    Subjects and Faculty Assignment
                  </h3>
                  <Button variant="outline" size="sm" onClick={addSubject}>
                    <Plus className="h-3.5 w-3.5 mr-1" /> Add Subject
                  </Button>
                </div>
                <div className="space-y-3">
                  {subjects.map((s, i) => (
                    <div key={i} className="flex gap-3 items-end">
                      <div className="flex-1">
                        <Label className="text-xs text-muted-foreground">
                          Subject
                        </Label>
                        <Input
                          placeholder={`subject-${i + 1}`}
                          value={s.subject}
                          onChange={(e) => {
                            const copy = [...subjects];
                            copy[i].subject = e.target.value;
                            setSubjects(copy);
                          }}
                        />
                      </div>
                      <div className="flex-1">
                        <Label className="text-xs text-muted-foreground">
                          Faculty
                        </Label>
                        <Input
                          placeholder={`faculty-${i + 1}`}
                          value={s.faculty}
                          onChange={(e) => {
                            const copy = [...subjects];
                            copy[i].faculty = e.target.value;
                            setSubjects(copy);
                          }}
                        />
                      </div>
                      {subjects.length > 1 && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => removeSubject(i)}
                          className="text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </TabsContent>

              <TabsContent
                value="labs"
                className="bg-card rounded-xl p-6 shadow-sm mt-4 border border-border/60"
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-foreground">
                    Labs (Multi-Faculty)
                  </h3>
                  <Button variant="outline" size="sm" onClick={addLab}>
                    <Plus className="h-3.5 w-3.5 mr-1" /> Add Lab
                  </Button>
                </div>
                <div className="space-y-3">
                  {labs.map((l, i) => (
                    <div key={i} className="flex gap-3 items-end">
                      <div className="flex-1">
                        <Label className="text-xs text-muted-foreground">
                          Lab Name
                        </Label>
                        <Input
                          placeholder={`lab-${i + 1}`}
                          value={l.lab}
                          onChange={(e) => {
                            const copy = [...labs];
                            copy[i].lab = e.target.value;
                            setLabs(copy);
                          }}
                        />
                      </div>
                      <div className="flex-[2]">
                        <Label className="text-xs text-muted-foreground">
                          Faculty (comma-separated)
                        </Label>
                        <Input
                          placeholder="faculty-1, faculty-2"
                          value={l.faculty.join(", ")}
                          onChange={(e) => {
                            const copy = [...labs];
                            copy[i].faculty = e.target.value
                              .split(",")
                              .map((f) => f.trim())
                              .filter(Boolean);
                            setLabs(copy);
                          }}
                        />
                      </div>
                      {labs.length > 1 && (
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => removeLab(i)}
                          className="text-destructive"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              </TabsContent>

              <TabsContent
                value="hours"
                className="bg-card rounded-xl p-6 shadow-sm mt-4 border border-border/60"
              >
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-foreground">
                    Subject Hours Configuration
                  </h3>
                  <Button variant="outline" size="sm" onClick={addSubjectHour}>
                    <Plus className="h-3.5 w-3.5 mr-1" /> Add Entry
                  </Button>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left py-2 px-3 text-xs text-muted-foreground font-medium">
                          Subject / Lab
                        </th>
                        <th className="text-left py-2 px-3 text-xs text-muted-foreground font-medium">
                          Hours/Week
                        </th>
                        <th className="text-left py-2 px-3 text-xs text-muted-foreground font-medium">
                          Continuous Hours
                        </th>
                        <th className="w-10"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {subjectHours.map((sh, i) => (
                        <tr key={i}>
                          <td className="py-1.5 px-3">
                            <Input
                              placeholder={`subject-${i + 1}`}
                              value={sh.subject}
                              onChange={(e) => {
                                const copy = [...subjectHours];
                                copy[i].subject = e.target.value;
                                setSubjectHours(copy);
                              }}
                            />
                          </td>
                          <td className="py-1.5 px-3">
                            <Input
                              type="number"
                              min={1}
                              max={10}
                              value={sh.hours}
                              onChange={(e) => {
                                const copy = [...subjectHours];
                                copy[i].hours =
                                  parseInt(e.target.value, 10) || 1;
                                setSubjectHours(copy);
                              }}
                              className="w-20"
                            />
                          </td>
                          <td className="py-1.5 px-3">
                            <Input
                              type="number"
                              min={1}
                              max={5}
                              value={sh.continuousHours}
                              onChange={(e) => {
                                const copy = [...subjectHours];
                                copy[i].continuousHours =
                                  parseInt(e.target.value, 10) || 1;
                                setSubjectHours(copy);
                              }}
                              className="w-20"
                            />
                          </td>
                          <td className="py-1.5 px-3">
                            {subjectHours.length > 1 && (
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => removeSubjectHour(i)}
                                className="text-destructive h-8 w-8"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </Button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </TabsContent>
            </Tabs>
          )}

          <div className="flex justify-end gap-3">
            {getYearOptions(academicConfig).length > 1 && (
              <Button
                onClick={handleGenerateAll}
                size="lg"
                variant="outline"
                className="gap-2"
              >
                <Wand2 className="h-4 w-4" />
                Generate All Years
              </Button>
            )}
            <Button onClick={handleGenerate} size="lg" className="gap-2">
              <Wand2 className="h-4 w-4" />
              Generate Timetable
            </Button>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
};

export default TimetableGenerator;
