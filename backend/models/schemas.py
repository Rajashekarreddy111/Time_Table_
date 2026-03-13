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


class BulkFacultyAvailabilityItem(FacultyAvailabilityResponse):
    date: str
    facultyRequired: int


class BulkFacultyAvailabilityResponse(BaseModel):
    results: list[BulkFacultyAvailabilityItem]


class BulkFacultyAvailabilityRequest(BaseModel):
    availabilityFileId: str
    queryFileId: str
    ignoredYears: list[str] = Field(default_factory=list)
    ignoredSections: list[str] = Field(default_factory=list)
    facultyIdMapFileId: str | None = None


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


class ManualEntryMode(BaseModel):
    year: str
    section: str
    subjectId: str
    facultyId: str
    noOfHours: int
    continuousHours: int
    compulsoryContinuousHours: int


class SubjectHoursEntry(BaseModel):
    subject: str
    hours: int
    continuousHours: int


class MappingFileIds(BaseModel):
    facultyIdMap: str | None = None
    mainTimetableConfig: str | None = None
    labTimetableConfig: str | None = None
    subjectIdMapping: str | None = None
    subjectContinuousRules: str | None = None


class FacultyWeeklyAvailabilityEntry(BaseModel):
    facultyId: str
    availablePeriodsByDay: dict[str, list[int]] = Field(default_factory=dict)


class FacultyIdNameMapEntry(BaseModel):
    facultyId: str
    facultyName: str


class SubjectIdNameMapEntry(BaseModel):
    subjectId: str
    subjectName: str


class SubjectContinuousRuleEntry(BaseModel):
    subjectId: str
    compulsoryContinuousHours: int


class ManualLabEntry(BaseModel):
    year: str
    section: str
    subjectId: str
    day: int
    hours: list[int] = Field(default_factory=list)
    venue: str = ""


class GenerateTimetableRequest(BaseModel):
    year: str
    section: str
    manualEntries: list[ManualEntryMode] = Field(default_factory=list)
    subjects: list[SubjectEntry] = Field(default_factory=list)
    labs: list[LabEntry] = Field(default_factory=list)
    sharedClasses: list[SharedClassEntry] = Field(default_factory=list)
    subjectHours: list[SubjectHoursEntry] = Field(default_factory=list)
    mappingFileIds: MappingFileIds | None = None
    facultyAvailability: list[FacultyWeeklyAvailabilityEntry] = Field(default_factory=list)
    facultyIdNameMapping: list[FacultyIdNameMapEntry] = Field(default_factory=list)
    subjectIdNameMapping: list[SubjectIdNameMapEntry] = Field(default_factory=list)
    subjectContinuousRules: list[SubjectContinuousRuleEntry] = Field(default_factory=list)
    manualLabEntries: list[ManualLabEntry] = Field(default_factory=list)


class GenerateTimetableResponse(BaseModel):
    timetableId: str
    message: str
