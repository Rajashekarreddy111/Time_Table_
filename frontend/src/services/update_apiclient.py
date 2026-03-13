import os

client_path = r"c:\Users\rajas\OneDrive\Desktop\Timetable\frontend\src\services\apiClient.ts"
with open(client_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace MappingStatusResponse
start = content.find("export interface MappingStatusResponse {")
end = content.find("export interface FacultyIdStatusResponse {")
new_mapping_status = """export interface MappingStatusResponse {
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
}

"""
content = content[:start] + new_mapping_status + content[end:]

# Replace GenerateTimetableRequest
start = content.find("export interface GenerateTimetableRequest {")
end = content.find("export interface GenerateTimetableResponse {")
new_req = """export interface ManualEntryMode {
  year: string;
  section: string;
  subjectId: string;
  facultyId: string;
  noOfHours: number;
  continuousHours: number;
  compulsoryContinuousHours: number;
}

export interface GenerateTimetableRequest {
  year: string;
  section: string;
  manualEntries?: ManualEntryMode[];
  subjects?: { subject: string; faculty: string }[];
  labs?: { lab: string; faculty: string[] }[];
  sharedClasses?: { year: string; sections: string[]; subject: string }[];
  subjectHours?: { subject: string; hours: number; continuousHours: number }[];
  facultyAvailability?: { facultyId: string; availablePeriodsByDay: Record<string, number[]> }[];
  mappingFileIds?: {
    facultyIdMap?: string;
    mainTimetableConfig?: string;
    labTimetableConfig?: string;
    subjectIdMapping?: string;
    subjectContinuousRules?: string;
  };
}

"""
content = content[:start] + new_req + content[end:]

# Replace old endpoints
start = content.find("export async function uploadSubjectFacultyMap")
end = content.find("export async function uploadFacultyAvailability")
new_eps = """export async function uploadMainTimetableConfig(file: File, year: string): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("year", year);

  const path = "/uploads/main-timetable-config";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

export async function uploadLabTimetable(file: File, year: string): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("year", year);

  const path = "/uploads/lab-timetable";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

export async function uploadSubjectIdMapping(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const path = "/uploads/subject-id-mapping";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

export async function uploadSubjectContinuousRules(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const path = "/uploads/subject-continuous-rules";
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw await parseResponseError(response, "POST", path);
  }

  return response.json() as Promise<UploadResponse>;
}

"""
content = content[:start] + new_eps + content[end:]

with open(client_path, "w", encoding="utf-8") as f:
    f.write(content)

print("apiClient.ts updated successfully")
