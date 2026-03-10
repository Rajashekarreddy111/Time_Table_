export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5000/api";

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface FacultyAvailabilityRequest {
  date: string;
  periods: number[];
  facultyRequired: number;
  ignoredYears: string[];
  ignoredSections: string[];
  availabilityFileId?: string;
  facultyIdMapFileId?: string;
}

export interface FacultyAvailabilityResponse {
  day: string;
  periods: { period: number; time: string }[];
  faculty: string[];
}

export interface UploadResponse {
  fileId: string;
  fileName: string;
  rowsParsed: number;
  message: string;
}

export interface MappingStatusResponse {
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
  sharedClassesUploaded?: boolean;
  sharedClassesFileName?: string | null;
}

export interface FacultyIdStatusResponse {
  facultyIdMapUploaded: boolean;
  facultyIdMapFileName?: string | null;
}

export interface GenerateTimetableRequest {
  year: string;
  section: string;
  sectionBatchMap?: Record<string, string>;
  subjects: { subject: string; faculty: string }[];
  labs: { lab: string; faculty: string[] }[];
  sharedClasses: { year: string; sections: string[]; subject: string }[];
  subjectHours: { subject: string; hours: number; continuousHours: number }[];
  batchSubjectHours?: Record<string, { subject: string; hours: number; continuousHours: number }[]>;
  facultyAvailability?: { facultyId: string; availablePeriodsByDay: Record<string, number[]> }[];
  mappingFileIds?: {
    facultyIdMap?: string;
    subjectFacultyMap?: string;
    subjectFacultyMapCream?: string;
    subjectFacultyMapGeneral?: string;
    subjectPeriodsMap?: string;
    subjectPeriodsMapCream?: string;
    subjectPeriodsMapGeneral?: string;
  };
}

export interface GenerateTimetableResponse {
  timetableId: string;
  message: string;
}

export interface TimetableRecord {
  id: string;
  year: string;
  section: string;
  grid: Record<string, ({ subject: string; faculty?: string; isLab?: boolean } | null)[]>;
  allGrids?: Record<string, Record<string, ({ subject: string; faculty?: string; isLab?: boolean } | null)[]>>;
  facultyWorkloads?: Record<string, Record<string, (string | null)[]>>;
  source?: unknown;
}

export interface BackendHealthResponse {
  status: "ok" | "degraded";
  mongo?: string;
  cloudinary?: string;
}

export class ApiError extends Error {
  status: number;
  details: Record<string, unknown>[];

  constructor(message: string, status: number, details: Record<string, unknown>[] = []) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

async function apiRequest<T>(path: string, method: HttpMethod, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let message = `API ${method} ${path} failed (${response.status})`;
    let details: any[] = [];
    try {
      const errorData = await response.json();
      if (errorData.message) {
        message = errorData.message;
        details = errorData.details || [];
      } else if (errorData.detail) {
        if (typeof errorData.detail === "string") {
          message = errorData.detail;
        } else {
          message = errorData.detail.message || message;
          details = errorData.detail.details || [];
        }
      }
    } catch (e) {
      // Not JSON, fallback to text
    }
    throw new ApiError(message, response.status, details);
  }

  return response.json() as Promise<T>;
}

async function parseResponseError(response: Response, method: string, path: string): Promise<ApiError> {
  let message = `Request failed (${response.status}): ${method} ${path}`;
  let details: Record<string, unknown>[] = [];
  try {
    const errorData = await response.json();
    if (errorData.message) {
      message = errorData.message;
      details = errorData.details || [];
    } else if (errorData.detail) {
      if (typeof errorData.detail === "string") {
        message = errorData.detail;
      } else {
        message = errorData.detail.message || message;
        details = errorData.detail.details || [];
      }
    }
  } catch (e) {
    // fallback to status text
    message = response.statusText ? `${message} - ${response.statusText}` : message;
  }
  return new ApiError(message, response.status, details);
}

export async function uploadFacultyIdMap(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const path = "/uploads/faculty-id-map";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

export async function uploadSubjectFacultyMap(
  file: File,
  year: string,
  batchType?: "CREAM" | "GENERAL" | "ALL",
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("year", year);
  if (batchType) {
    formData.append("batchType", batchType);
  }

  const path = "/uploads/subject-faculty-map";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

export async function uploadSubjectPeriodsMap(
  file: File,
  year: string,
  batchType?: "CREAM" | "GENERAL" | "ALL",
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("year", year);
  if (batchType) {
    formData.append("batchType", batchType);
  }

  const path = "/uploads/subject-periods-map";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

export async function uploadFacultyAvailability(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const path = "/uploads/faculty-availability";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

export async function uploadSharedClasses(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const path = "/uploads/shared-classes";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

export function getFacultyAvailability(payload: FacultyAvailabilityRequest) {
  return apiRequest<FacultyAvailabilityResponse>("/faculty/availability", "POST", payload);
}

export function generateTimetable(payload: GenerateTimetableRequest) {
  return apiRequest<GenerateTimetableResponse>("/timetables/generate", "POST", payload);
}

export function listTimetables() {
  return apiRequest<{ items: TimetableRecord[] }>("/timetables", "GET");
}

export function getTimetableById(timetableId: string) {
  return apiRequest<TimetableRecord>(`/timetables/${encodeURIComponent(timetableId)}`, "GET");
}

export function getMappingStatus(year: string) {
  return apiRequest<MappingStatusResponse>(
    `/uploads/mapping-status?year=${encodeURIComponent(year)}`,
    "GET",
  );
}

export function getFacultyIdStatus() {
  return apiRequest<FacultyIdStatusResponse>("/uploads/faculty-id-status", "GET");
}

export function getBackendHealth() {
  return apiRequest<BackendHealthResponse>("/health", "GET");
}
export const deleteTimetable = async (timetableId: string): Promise<{ message: string }> => {
  const response = await fetch(`${API_BASE_URL}/timetables/${timetableId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail?.message || "Failed to delete timetable");
  }
  return response.json();
};
