const STORAGE_KEY = "nec-timetable-academic-config";

export type YearStructure = {
  hasCreamGeneral: boolean;
  sectionCount: number;
  creamSectionCount: number;
  generalSectionCount: number;
};

export type AcademicConfig = {
  activeYears: string[];
  years: YearStructure[];
};

type SectionKey = {
  year: string;
  section: string;
};

const DEFAULT_ACTIVE_YEARS = ["2nd Year", "3rd Year", "4th Year"];

const DEFAULT_YEAR_STRUCTURE: YearStructure = {
  hasCreamGeneral: false,
  sectionCount: 4,
  creamSectionCount: 0,
  generalSectionCount: 0,
};

const DEFAULT_CONFIG: AcademicConfig = {
  activeYears: DEFAULT_ACTIVE_YEARS,
  years: DEFAULT_ACTIVE_YEARS.map(() => ({ ...DEFAULT_YEAR_STRUCTURE })),
};

function cloneYearStructure(value?: Partial<YearStructure>): YearStructure {
  return {
    hasCreamGeneral: Boolean(value?.hasCreamGeneral),
    sectionCount: Math.max(1, Number(value?.sectionCount) || DEFAULT_YEAR_STRUCTURE.sectionCount),
    creamSectionCount: Math.max(0, Number(value?.creamSectionCount) || 0),
    generalSectionCount: Math.max(0, Number(value?.generalSectionCount) || 0),
  };
}

function normalizeConfig(value: unknown): AcademicConfig {
  if (!value || typeof value !== "object") {
    return DEFAULT_CONFIG;
  }

  const raw = value as Partial<AcademicConfig>;
  const activeYears = Array.isArray(raw.activeYears) && raw.activeYears.length > 0
    ? raw.activeYears.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : DEFAULT_ACTIVE_YEARS;

  const years = Array.isArray(raw.years) ? raw.years : [];

  return {
    activeYears,
    years: activeYears.map((_, index) => cloneYearStructure(years[index])),
  };
}

function getAlphabetSection(index: number): string {
  let current = index + 1;
  let result = "";

  while (current > 0) {
    current -= 1;
    result = String.fromCharCode(65 + (current % 26)) + result;
    current = Math.floor(current / 26);
  }

  return result;
}

export function getYearOptions(config: AcademicConfig): string[] {
  return normalizeConfig(config).activeYears;
}

export function getYearStructure(config: AcademicConfig, year: string): YearStructure {
  const normalized = normalizeConfig(config);
  const index = normalized.activeYears.indexOf(year);
  return cloneYearStructure(normalized.years[index]);
}

export function getSectionOptionsForYear(config: AcademicConfig, year: string): string[] {
  const structure = getYearStructure(config, year);

  if (structure.hasCreamGeneral) {
    const sections = [
      ...Array.from({ length: structure.creamSectionCount }, (_, index) => `C${index + 1}`),
      ...Array.from({ length: structure.generalSectionCount }, (_, index) => `G${index + 1}`),
    ];

    if (sections.length > 0) {
      return sections;
    }
  }

  return Array.from({ length: structure.sectionCount }, (_, index) => getAlphabetSection(index));
}

export function getSectionBatchMapForYear(config: AcademicConfig, year: string): Record<string, string> {
  const structure = getYearStructure(config, year);
  const sections = getSectionOptionsForYear(config, year);

  return sections.reduce<Record<string, string>>((acc, section) => {
    if (!structure.hasCreamGeneral) {
      acc[section] = "GENERAL";
    } else if (section.startsWith("C")) {
      acc[section] = "CREAM";
    } else if (section.startsWith("G")) {
      acc[section] = "GENERAL";
    } else {
      acc[section] = "GENERAL";
    }
    return acc;
  }, {});
}

export function getAllSectionKeys(config: AcademicConfig): SectionKey[] {
  return getYearOptions(config).flatMap((year) =>
    getSectionOptionsForYear(config, year).map((section) => ({ year, section })),
  );
}

export function readAcademicConfig(): AcademicConfig {
  if (typeof window === "undefined") {
    return DEFAULT_CONFIG;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_CONFIG;
    return normalizeConfig(JSON.parse(raw));
  } catch {
    return DEFAULT_CONFIG;
  }
}

export function saveAcademicConfig(config: AcademicConfig): AcademicConfig {
  const normalized = normalizeConfig(config);

  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
    } catch {
      // Ignore local storage failures and continue with in-memory data.
    }
  }

  return normalized;
}
