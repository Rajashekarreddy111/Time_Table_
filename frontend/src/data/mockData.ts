export const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"] as const;

export const PERIODS = [
  { period: 1, time: "9:10 – 10:00" },
  { period: 2, time: "10:00 – 10:50" },
  { period: "BREAK", time: "10:50 – 11:00" },
  { period: 3, time: "11:00 – 11:50" },
  { period: 4, time: "11:50 – 12:40" },
  { period: "LUNCH", time: "12:40 – 1:30" },
  { period: 5, time: "1:30 – 2:20" },
  { period: 6, time: "2:20 – 3:10" },
  { period: 7, time: "3:10 – 4:00" },
] as const;

export const YEARS = ["2nd Year", "3rd Year", "4th Year"] as const;
export const SECTIONS = ["A", "B", "C", "D"] as const;

export type SubjectEntry = {
  subject: string;
  faculty: string;
};

export type LabEntry = {
  lab: string;
  faculty: string[];
};

export type SharedClassEntry = {
  year: string;
  sections: string[];
  subject: string;
};

export type SubjectHours = {
  subject: string;
  hours: number;
  continuousHours: number;
};

export type TimetableCell = {
  subject: string;
  subjectName?: string;
  faculty?: string;
  facultyName?: string;
  isLab?: boolean;
  classroom?: string;
  labRoom?: string;
  sharedSections?: string[];
  year?: string;
  section?: string;
};


export type SectionTimetable = {
  year: string;
  section: string;
  grid: Record<string, (TimetableCell | null)[]>; // day -> periods
};

export type FacultyScheduleEntry = {
  subject: string;
  year: string;
  section: string;
};

export type FacultyWorkload = {
  name: string;
  schedule: Record<string, (FacultyScheduleEntry | null)[]>;
};

export type RoomTimetable = {
  year?: string;
  section: string; // The section key is reused for room name
  grid: Record<string, (TimetableCell & { year?: string, section?: string } | null)[]>; // day -> periods
};
