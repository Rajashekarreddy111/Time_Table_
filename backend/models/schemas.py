from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    fileId: str
    fileName: str
    rowsParsed: int
    message: str


class PeriodInfo(BaseModel):
    period: int
    time: str


class FacultyAvailabilityRequest(BaseModel):
    date: str
    periods: list[int] = Field(default_factory=list)
    facultyRequired: int = 3
    ignoredYears: list[str] = Field(default_factory=list)
    ignoredSections: list[str] = Field(default_factory=list)
    availabilityFileId: str | None = None
    facultyIdMapFileId: str | None = None


class FacultyAvailabilityResponse(BaseModel):
    day: str
    periods: list[PeriodInfo]
    faculty: list[str]


class SubjectEntry(BaseModel):
    subject: str
    faculty: str


class LabEntry(BaseModel):
    lab: str
    faculty: list[str]


class SharedClassEntry(BaseModel):
    year: str
    sections: list[str]
    subject: str


class SubjectHoursEntry(BaseModel):
    subject: str
    hours: int
    continuousHours: int


class MappingFileIds(BaseModel):
    facultyIdMap: str | None = None
    subjectFacultyMap: str | None = None
    subjectFacultyMapCream: str | None = None
    subjectFacultyMapGeneral: str | None = None
    subjectPeriodsMap: str | None = None
    subjectPeriodsMapCream: str | None = None
    subjectPeriodsMapGeneral: str | None = None


class FacultyWeeklyAvailabilityEntry(BaseModel):
    facultyId: str
    availablePeriodsByDay: dict[str, list[int]] = Field(default_factory=dict)


class FacultyIdNameMapEntry(BaseModel):
    facultyId: str
    facultyName: str


class GenerateTimetableRequest(BaseModel):
    year: str
    section: str
    sectionBatchMap: dict[str, str] = Field(default_factory=dict)
    subjects: list[SubjectEntry] = Field(default_factory=list)
    labs: list[LabEntry] = Field(default_factory=list)
    sharedClasses: list[SharedClassEntry] = Field(default_factory=list)
    subjectHours: list[SubjectHoursEntry] = Field(default_factory=list)
    batchSubjectHours: dict[str, list[SubjectHoursEntry]] = Field(default_factory=dict)
    mappingFileIds: MappingFileIds | None = None
    facultyAvailability: list[FacultyWeeklyAvailabilityEntry] = Field(default_factory=list)
    facultyIdNameMapping: list[FacultyIdNameMapEntry] = Field(default_factory=list)


class GenerateTimetableResponse(BaseModel):
    timetableId: str
    message: str
