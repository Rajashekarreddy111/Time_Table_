import { type TimetableCell } from "@/data/mockData";

export const DISPLAY_DAYS = [
  { full: "Monday", shortVertical: "M\nO\nN" },
  { full: "Tuesday", shortVertical: "T\nU\nE" },
  { full: "Wednesday", shortVertical: "W\nE\nD" },
  { full: "Thursday", shortVertical: "T\nH\nU" },
  { full: "Friday", shortVertical: "F\nR\nI" },
  { full: "Saturday", shortVertical: "S\nA\nT" },
] as const;

type LegendItem = {
  subject: string;
  faculty: string;
};

export function getCellByPeriod(
  grid: Record<string, (TimetableCell | null)[]>,
  day: string,
  period: number,
): TimetableCell | null {
  return grid[day]?.[period - 1] ?? null;
}

export function getCellRoomLabel(cell: TimetableCell | null | undefined): string {
  if (!cell) return "";
  if (cell.isLab) return cell.labRoom ?? "";
  if (cell.fallbackLab && cell.classroom) return `${cell.fallbackLab}/${cell.classroom}`;
  return cell.fallbackLab ?? cell.classroom ?? "";
}

export function buildLegend(grid: Record<string, (TimetableCell | null)[]>): LegendItem[] {
  const seen = new Map<string, LegendItem>();

  Object.values(grid).forEach((daySlots) => {
    daySlots.forEach((cell) => {
      if (!cell) return;

      const subject = cell.subjectName ?? cell.subject ?? "";
      const faculty = cell.facultyName ?? cell.faculty ?? "";
      if (!subject || !faculty) return;

      const key = `${subject}::${faculty}`;
      if (!seen.has(key)) {
        seen.set(key, { subject, faculty });
      }
    });
  });

  return Array.from(seen.values()).sort((left, right) => {
    const subjectCompare = left.subject.localeCompare(right.subject);
    if (subjectCompare !== 0) return subjectCompare;
    return left.faculty.localeCompare(right.faculty);
  });
}
