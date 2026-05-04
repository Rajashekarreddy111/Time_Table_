export const ACADEMIC_METADATA = {
  COLLEGE_NAME: "Narasaraopeta Engineering College",
  DEPARTMENT_NAME: "Department of Computer Science and Engineering",
  SEMESTER: "II Semester",
} as const;

function pad(value: number) {
  return String(value).padStart(2, "0");
}

export function toAcademicYear(date: Date): string {
  const month = date.getMonth() + 1;
  const year = date.getFullYear();
  const startYear = month >= 6 ? year : year - 1;
  return `${startYear}-${startYear + 1}`;
}

export function formatSemesterLabel(semester: number | string): string {
  const normalized = Number(semester);
  if (normalized === 1) return "I Semester";
  if (normalized === 2) return "II Semester";
  return `Semester ${semester}`;
}

export function formatWithEffectFrom(value?: string | null): string {
  if (!value) return "";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return `${pad(date.getDate())}-${pad(date.getMonth() + 1)}-${date.getFullYear()}`;
}
