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
  faculty?: string;
  isLab?: boolean;
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

// Mock generated timetable data
export const mockTimetables: SectionTimetable[] = [
  {
    year: "2nd Year", section: "A",
    grid: {
      Monday: [
        { subject: "Data Structures", faculty: "Dr. Rajani" },
        { subject: "DBMS", faculty: "Dr. Sireesha" },
        null,
        { subject: "OS", faculty: "Dr. Bhavani" },
        null,
        { subject: "DS Lab", faculty: "Dr. Rajani", isLab: true },
        { subject: "DS Lab", faculty: "Dr. Rajani", isLab: true },
      ],
      Tuesday: [
        { subject: "OS", faculty: "Dr. Bhavani" },
        { subject: "Data Structures", faculty: "Dr. Rajani" },
        null,
        { subject: "DBMS", faculty: "Dr. Sireesha" },
        { subject: "Maths III", faculty: "Dr. Kumar" },
        null,
        { subject: "English", faculty: "Prof. Lakshmi" },
      ],
      Wednesday: [
        { subject: "Maths III", faculty: "Dr. Kumar" },
        { subject: "English", faculty: "Prof. Lakshmi" },
        null,
        { subject: "DBMS Lab", faculty: "Dr. Sireesha", isLab: true },
        { subject: "DBMS Lab", faculty: "Dr. Sireesha", isLab: true },
        { subject: "DBMS Lab", faculty: "Dr. Sireesha", isLab: true },
        null,
      ],
      Thursday: [
        { subject: "Data Structures", faculty: "Dr. Rajani" },
        { subject: "OS", faculty: "Dr. Bhavani" },
        null,
        { subject: "Maths III", faculty: "Dr. Kumar" },
        { subject: "DBMS", faculty: "Dr. Sireesha" },
        null,
        { subject: "English", faculty: "Prof. Lakshmi" },
      ],
      Friday: [
        { subject: "OS", faculty: "Dr. Bhavani" },
        { subject: "Maths III", faculty: "Dr. Kumar" },
        null,
        { subject: "Data Structures", faculty: "Dr. Rajani" },
        { subject: "English", faculty: "Prof. Lakshmi" },
        null,
        { subject: "OS Lab", faculty: "Dr. Bhavani", isLab: true },
      ],
      Saturday: [
        { subject: "DBMS", faculty: "Dr. Sireesha" },
        { subject: "Data Structures", faculty: "Dr. Rajani" },
        null,
        { subject: "English", faculty: "Prof. Lakshmi" },
        null,
        null,
        null,
      ],
    },
  },
];

export const mockFacultyWorkloads: FacultyWorkload[] = [
  {
    name: "Dr. Rajani",
    schedule: {
      Monday: [
        { subject: "Data Structures", year: "2nd", section: "A" },
        null, null,
        { subject: "Data Structures", year: "2nd", section: "B" },
        null,
        { subject: "DS Lab", year: "2nd", section: "A" },
        { subject: "DS Lab", year: "2nd", section: "A" },
      ],
      Tuesday: [
        null,
        { subject: "Data Structures", year: "2nd", section: "A" },
        null, null,
        { subject: "Data Structures", year: "2nd", section: "C" },
        null, null,
      ],
      Wednesday: [
        null, null, null,
        { subject: "ML", year: "3rd", section: "A" },
        null, null, null,
      ],
      Thursday: [
        { subject: "Data Structures", year: "2nd", section: "A" },
        null, null, null,
        { subject: "Data Structures", year: "2nd", section: "D" },
        null, null,
      ],
      Friday: [
        null, null, null,
        { subject: "Data Structures", year: "2nd", section: "A" },
        null, null,
        { subject: "OS Lab", year: "4th", section: "B" },
      ],
      Saturday: [
        null,
        { subject: "Data Structures", year: "2nd", section: "A" },
        null, null, null, null, null,
      ],
    },
  },
  {
    name: "Dr. Sireesha",
    schedule: {
      Monday: [
        null,
        { subject: "DBMS", year: "2nd", section: "A" },
        null, null, null,
        { subject: "DBMS", year: "2nd", section: "C" },
        null,
      ],
      Tuesday: [
        null, null, null,
        { subject: "DBMS", year: "2nd", section: "A" },
        null,
        { subject: "Cloud Computing", year: "3rd", section: "B" },
        null,
      ],
      Wednesday: [
        null, null, null,
        { subject: "DBMS Lab", year: "2nd", section: "A" },
        { subject: "DBMS Lab", year: "2nd", section: "A" },
        { subject: "DBMS Lab", year: "2nd", section: "A" },
        null,
      ],
      Thursday: [
        null, null, null, null,
        { subject: "DBMS", year: "2nd", section: "A" },
        null, null,
      ],
      Friday: [
        null, null, null, null,
        { subject: "DBMS", year: "2nd", section: "B" },
        null, null,
      ],
      Saturday: [
        { subject: "DBMS", year: "2nd", section: "A" },
        null, null, null, null, null, null,
      ],
    },
  },
  {
    name: "Dr. Bhavani",
    schedule: {
      Monday: [
        null, null, null,
        { subject: "OS", year: "2nd", section: "A" },
        null, null, null,
      ],
      Tuesday: [
        { subject: "OS", year: "2nd", section: "A" },
        null, null, null, null, null, null,
      ],
      Wednesday: [
        null, null, null, null, null, null, null,
      ],
      Thursday: [
        null,
        { subject: "OS", year: "2nd", section: "A" },
        null, null, null, null, null,
      ],
      Friday: [
        { subject: "OS", year: "2nd", section: "A" },
        null, null, null, null, null, null,
      ],
      Saturday: [
        null, null, null, null, null, null, null,
      ],
    },
  },
];

export const ALL_FACULTY = [
  "Dr. Rajani", "Dr. Sireesha", "Dr. Bhavani", "Dr. Kumar",
  "Prof. Lakshmi", "Dr. Venkat", "Dr. Priya", "Dr. Ramesh",
];
