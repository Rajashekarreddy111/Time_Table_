export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5000/api";

const SESSION_STORAGE_KEY = "tt_session_id";
const SESSION_HEADER_NAME = "X-Session-Id";

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface FacultyAvailabilityRequest {
  date: string;
  periods: number[];
  startTime?: string;
  endTime?: string;
  facultyRequired: number;
  ignoredYears: string[];
  ignoredSections: string[];
  availabilityFileId?: string;
  facultyIdMapFileId?: string;
}

export interface FacultyAvailabilityResponse {
  day: string;
  periods: { period: number; time: string }[];
  startTime?: string;
  endTime?: string;
  faculty: string[];
  availableFaculty: string[];
  availableFacultyCount: number;
  sufficientFaculty: boolean;
  shortageCount: number;
  message: string;
}

export interface BulkFacultyAvailabilityItem extends FacultyAvailabilityResponse {
  date: string;
  facultyRequired: number;
}

export interface BulkFacultyAvailabilityRequest {
  availabilityFileId: string;
  queryFileId: string;
  ignoredYears: string[];
  ignoredSections: string[];
  facultyIdMapFileId?: string;
}

export interface BulkFacultyAvailabilityResponse {
  results: BulkFacultyAvailabilityItem[];
}

export interface UploadResponse {
  fileId: string;
  fileName: string;
  rowsParsed: number;
  message: string;
}

export interface MappingStatusResponse {
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
  classroomsUploaded?: boolean;
  classroomsFileName?: string | null;
  periodConfigUploaded?: boolean;
  periodConfigFileName?: string | null;
  fixedClassroomBlocksUploaded?: boolean;
  fixedClassroomBlocksFileName?: string | null;
}

export interface FacultyIdStatusResponse {
  facultyIdMapUploaded: boolean;
  facultyIdMapFileName?: string | null;
}

export interface ManualEntryMode {
  year: string;
  section: string;
  subjectId: string;
  facultyId: string;
  noOfHours: number;
  continuousHours: number;
  compulsoryContinuousHours: number;
}

export interface SubjectIdNameMappingEntry {
  subjectId: string;
  subjectName: string;
}

export interface SubjectContinuousRuleEntry {
  subjectId: string;
  compulsoryContinuousHours: number;
}

export interface ManualLabEntry {
  year: string;
  section: string;
  subjectId: string;
  day: number;
  hours: number[];
  venue: string;
}

export interface TimetableMetadata {
  academicYear: string;
  semester: 1 | 2;
  withEffectFrom: string;
}

export interface GenerateTimetableRequest {
  year: string;
  section: string;
  timetableMetadata: TimetableMetadata;
  labsOnly?: boolean;
  priorTimetableIds?: string[];
  manualEntries?: ManualEntryMode[];
  subjects?: { subject: string; faculty: string }[];
  labs?: { lab: string; faculty: string[] }[];
  sharedClasses?: { year: string; sections: string[]; subject: string }[];
  subjectHours?: { subject: string; hours: number; continuousHours: number }[];
  facultyAvailability?: {
    facultyId: string;
    availablePeriodsByDay: Record<string, number[]>;
  }[];
  mappingFileIds?: {
    facultyIdMap?: string;
    mainTimetableConfig?: string;
    labTimetableConfig?: string;
    subjectIdMapping?: string;
    subjectContinuousRules?: string;
    classrooms?: string;
    periodConfig?: string;
    fixedClassroomBlocks?: string;
  };
  subjectIdNameMapping?: SubjectIdNameMappingEntry[];
  subjectContinuousRules?: SubjectContinuousRuleEntry[];
  manualLabEntries?: ManualLabEntry[];
}

export interface GenerateTimetableResponse {
  timetableId: string;
  message: string;
}

export interface FeasibilitySectionSummary {
  section: string;
  requiredHours: number;
  freeSlots: number;
  deficitHours: number;
  lockedSlots: number;
}

export interface TimetableFeasibilityResponse {
  year?: string;
  feasible: boolean;
  blockingSections?: FeasibilitySectionSummary[];
  sectionSummary?: FeasibilitySectionSummary[];
  issues: Array<Record<string, unknown>>;
}

export interface GeneratedWorkbookFile {
  fileName: string;
  contentType: string;
  contentBase64: string;
}

export interface TimetableRecord {
  id: string;
  year: string;
  section: string;
  timetableMetadata?: TimetableMetadata;
  hasValidTimetable?: boolean;
  grid: Record<
    string,
    ({
      subject: string;
      subjectName?: string;
      faculty?: string;
      facultyName?: string;
      isLab?: boolean;
      classroom?: string;
      labRoom?: string;
      fallbackLab?: string;
      sharedSections?: string[];
    } | null)[]
  >;
  allGrids?: Record<
    string,
    Record<
      string,
      ({
        subject: string;
        subjectName?: string;
        faculty?: string;
        facultyName?: string;
        isLab?: boolean;
        classroom?: string;
        labRoom?: string;
        fallbackLab?: string;
        sharedSections?: string[];
      } | null)[]
    >
  >;
  roomGrids?: Record<
    string,
    Record<
      string,
      ({
        subject: string;
        subjectName?: string;
        faculty?: string;
        facultyName?: string;
        isLab?: boolean;
        classroom?: string;
        labRoom?: string;
        fallbackLab?: string;
        sharedSections?: string[];
        year?: string;
        section?: string;
      } | null)[]
    >
  >;
  facultyWorkloads?: Record<string, Record<string, (string | null)[]>>;
  generatedFiles?: {
    sectionTimetables?: GeneratedWorkbookFile;
    facultyWorkload?: GeneratedWorkbookFile;
    sharedClassesReport?: GeneratedWorkbookFile;
    constraintViolationReport?: GeneratedWorkbookFile;
    roomTimetables?: GeneratedWorkbookFile;
    constraintReport?: GeneratedWorkbookFile;
  };
  sharedClasses?: Array<{
    year: string;
    subject_id: string;
    subject_name?: string;
    faculty_id: string;
    faculty_name?: string;
    sections: string[];
    day: string;
    periods: number[];
    venue?: string;
    isLab?: boolean;
    shared?: boolean;
  }>;
  constraintViolations?: Array<{
    year: string;
    sections: string[];
    subject_id: string;
    subject_name?: string;
    faculty_id: string;
    faculty_name?: string;
    constraint: string;
    detail: string;
  }>;
  unscheduledSubjects?: Array<{
    year: string;
    sections: string[];
    subject_id: string;
    subject_name?: string;
    faculty_id: string;
    faculty_name?: string;
    detail: string;
  }>;
  source?: unknown;
}

export interface BackendHealthResponse {
  status: "ok" | "degraded";
  mongo?: string;
  mongo_error?: string | null;
  cloudinary?: string;
}

export class ApiError extends Error {
  status: number;
  details: Record<string, unknown>[];

  constructor(
    message: string,
    status: number,
    details: Record<string, unknown>[] = [],
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

function getSessionId(): string | null {
  return window.localStorage.getItem(SESSION_STORAGE_KEY);
}

function clearSessionId() {
  window.localStorage.removeItem(SESSION_STORAGE_KEY);
}

function setSessionId(sessionId: string | null) {
  if (sessionId) {
    window.localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
    return;
  }
  clearSessionId();
}

function buildAuthHeaders(headers?: HeadersInit): HeadersInit {
  const sessionId = getSessionId();
  return {
    ...(headers ?? {}),
    ...(sessionId ? { "X-Session-Id": sessionId } : {}),
  };
}

async function apiRequest<T>(
  path: string,
  method: HttpMethod,
  body?: unknown,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...buildAuthHeaders(),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    if (response.status === 401) {
      clearSessionId();
    }
    let message = `API ${method} ${path} failed (${response.status})`;
    let details: Record<string, unknown>[] = [];
    try {
      const errorData = (await response.json()) as {
        message?: string;
        details?: Record<string, unknown>[];
        detail?: string | { message?: string; details?: Record<string, unknown>[] };
      };
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

  const rotatedSessionId = response.headers.get(SESSION_HEADER_NAME);
  if (rotatedSessionId) {
    setSessionId(rotatedSessionId);
  }

  return response.json() as Promise<T>;
}

async function parseResponseError(
  response: Response,
  method: string,
  path: string,
): Promise<ApiError> {
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
    message = response.statusText
      ? `${message} - ${response.statusText}`
      : message;
  }
  return new ApiError(message, response.status, details);
}

export async function uploadFacultyIdMap(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const path = "/uploads/faculty-id-map";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: buildAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

export async function uploadMainTimetableConfig(
  file: File,
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const path = "/uploads/main-timetable-config";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: buildAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

export async function uploadLabTimetable(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const path = "/uploads/lab-timetable";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: buildAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

export async function uploadSubjectIdMapping(
  file: File,
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const path = "/uploads/subject-id-mapping";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: buildAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

export async function uploadSubjectContinuousRules(
  file: File,
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const path = "/uploads/subject-continuous-rules";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: buildAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

export async function uploadFacultyAvailability(
  file: File,
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const path = "/uploads/faculty-availability";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: buildAuthHeaders(),
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
    credentials: "include",
    headers: buildAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}
export async function uploadClassrooms(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const path = "/uploads/classrooms";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: buildAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

export async function uploadPeriodConfig(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const path = "/uploads/period-config";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: buildAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

export async function uploadFixedClassroomBlocks(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const path = "/uploads/fixed-classroom-blocks";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: buildAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

export function getFacultyAvailability(payload: FacultyAvailabilityRequest) {
  return apiRequest<FacultyAvailabilityResponse>(
    "/faculty/availability",
    "POST",
    payload,
  );
}

export function getBulkFacultyAvailability(
  payload: BulkFacultyAvailabilityRequest,
) {
  return apiRequest<BulkFacultyAvailabilityResponse>(
    "/faculty/availability/bulk",
    "POST",
    payload,
  );
}

export async function uploadFacultyAvailabilityQuery(
  file: File,
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const path = "/uploads/faculty-availability-query";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    credentials: "include",
    headers: buildAuthHeaders(),
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

export function generateTimetable(payload: GenerateTimetableRequest) {
  return apiRequest<GenerateTimetableResponse>(
    "/timetables/generate",
    "POST",
    payload,
  );
}

export function checkTimetableFeasibility(payload: GenerateTimetableRequest) {
  return apiRequest<TimetableFeasibilityResponse>(
    "/timetables/feasibility",
    "POST",
    payload,
  );
}

export function listTimetables() {
  return apiRequest<{ items: TimetableRecord[] }>("/timetables", "GET");
}

export function getTimetableById(timetableId: string) {
  return apiRequest<TimetableRecord>(
    `/timetables/${encodeURIComponent(timetableId)}`,
    "GET",
  );
}

export function getSectionWorkbook(timetableId: string, section: string) {
  return apiRequest<GeneratedWorkbookFile>(
    `/timetables/${encodeURIComponent(timetableId)}/section-workbook?section=${encodeURIComponent(section)}`,
    "GET",
  );
}

export function exportBulkFacultyAvailabilityReport(
  payload: BulkFacultyAvailabilityRequest,
) {
  return apiRequest<GeneratedWorkbookFile>(
    "/faculty/availability/bulk/export-report",
    "POST",
    payload,
  );
}

export function getAllSectionsWorkbook() {
  return apiRequest<GeneratedWorkbookFile>(
    "/timetables/all-sections-workbook",
    "GET",
  );
}

export function getAllRoomsWorkbook(room?: string) {
  const query = room ? `?room=${encodeURIComponent(room)}` : "";
  return apiRequest<GeneratedWorkbookFile>(
    `/timetables/all-rooms-workbook${query}`,
    "GET",
  );
}

export function getRoomWorkbook(timetableId: string) {
  return apiRequest<GeneratedWorkbookFile>(
    `/timetables/${encodeURIComponent(timetableId)}/room-workbook`,
    "GET",
  );
}

export function getConstraintReportWorkbook(timetableId: string) {
  return apiRequest<GeneratedWorkbookFile>(
    `/timetables/${encodeURIComponent(timetableId)}/constraint-report-workbook`,
    "GET",
  );
}

export function getFacultyWorkloadWorkbook(facultyName?: string) {
  const query = facultyName
    ? `?facultyName=${encodeURIComponent(facultyName)}`
    : "";
  return apiRequest<GeneratedWorkbookFile>(
    `/faculty-workloads/workbook${query}`,
    "GET",
  );
}

export function getMappingStatus(year: string) {
  return apiRequest<MappingStatusResponse>(
    `/uploads/mapping-status?year=${encodeURIComponent(year)}`,
    "GET",
  );
}

export function getFacultyIdStatus() {
  return apiRequest<FacultyIdStatusResponse>(
    "/uploads/faculty-id-status",
    "GET",
  );
}

export function getBackendHealth() {
  return apiRequest<BackendHealthResponse>("/health", "GET");
}

export function deleteUploadedMapping(mappingType: string) {
  return apiRequest<{ message: string }>(
    `/uploads/mappings/${encodeURIComponent(mappingType)}`,
    "DELETE",
  );
}
export const deleteTimetable = async (
  timetableId: string,
): Promise<{ message: string }> => {
  const response = await fetch(`${API_BASE_URL}/timetables/${timetableId}`, {
    method: "DELETE",
    credentials: "include",
    headers: buildAuthHeaders(),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail?.message || "Failed to delete timetable");
  }
  return response.json();
};

export const resetAllTimetables = async (): Promise<{
  message: string;
  deletedCount: number;
}> => {
  const response = await fetch(`${API_BASE_URL}/timetables`, {
    method: "DELETE",
    credentials: "include",
    headers: buildAuthHeaders(),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail?.message || "Failed to reset timetables");
  }
  return response.json();
};
