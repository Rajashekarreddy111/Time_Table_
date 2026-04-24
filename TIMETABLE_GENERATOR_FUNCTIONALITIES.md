# Timetable Generator Documentation

## Overview

The timetable generator is responsible for building weekly academic timetables for a selected year and section set. It combines uploaded configuration files, manual entries, faculty mappings, subject mappings, availability rules, shared-class rules, and lab locks to produce timetable records and downloadable workbook outputs.

It works on a weekly structure of:

- 6 working days: Monday to Saturday
- 7 periods per day
- 42 total weekly slots per section

## Functionalities

- Generates a complete weekly timetable for the selected academic year.
- Merges uploaded file-based configuration with manual entries sent in the API request.
- Supports section-wise theory subject scheduling.
- Supports fixed lab scheduling through manually locked lab entries and uploaded lab timetable configuration.
- Supports shared classes across multiple sections for the same subject.
- Resolves faculty IDs to faculty names using uploaded mappings and inline mappings.
- Resolves subject IDs to subject names using uploaded mappings and inline mappings.
- Applies subject continuous-hour rules while placing sessions.
- Uses faculty weekly availability while choosing valid slots.
- Prevents faculty timetable collisions within the same generation.
- Prevents cross-year faculty conflicts by considering previously generated timetable occupancy.
- Runs a feasibility-only mode to check whether the current configuration is schedulable before final generation.
- Generates timetable reports even when there are constraint violations, instead of failing silently.
- Stores generated timetable data for later listing, viewing, export, and workload reporting.

## Requirements It Solves

- Ensures each section is configured for exactly 42 weekly hours.
- Prevents two sessions from occupying the same section slot.
- Prevents the same faculty from being assigned in multiple places at the same time.
- Honors faculty availability restrictions.
- Honors compulsory continuous-hour requirements for subjects.
- Honors maximum continuous-hour values from the main timetable configuration.
- Prevents invalid lab day or period values from being scheduled.
- Prevents lab overlaps in already occupied slots.
- Reduces remaining theory hours after locked lab sessions are applied.
- Validates that shared classes reference valid sections.
- Validates that shared-class subject rows exist across all participating sections.
- Validates that shared sections have compatible remaining hours and faculty pools.
- Preserves cross-year faculty occupancy to avoid reusing a faculty member in a conflicting slot.
- Produces detailed constraint and unscheduled-subject reports when the schedule cannot be completed fully.

## Main Request Input

The timetable generator accepts a `GenerateTimetableRequest` object.

### Top-Level Fields

- `year: string`
- `section: string`
- `timetableMetadata: object`
- `dailySubjectLimit: integer`
- `labsOnly: boolean`
- `priorTimetableIds: string[]`
- `manualEntries: object[]`
- `subjects: object[]`
- `labs: object[]`
- `sharedClasses: object[]`
- `subjectHours: object[]`
- `mappingFileIds: object | null`
- `facultyAvailability: object[]`
- `facultyIdNameMapping: object[]`
- `subjectIdNameMapping: object[]`
- `subjectContinuousRules: object[]`
- `manualLabEntries: object[]`

## Input Data Formats

### 1. Timetable Metadata

```json
{
  "academicYear": "2025-2026",
  "semester": 1,
  "withEffectFrom": "2025-06-16"
}
```

Rules:

- `academicYear` format: `YYYY-YYYY`
- `semester` allowed values: `1` or `2`
- `withEffectFrom` format: `YYYY-MM-DD`

### 2. Manual Theory Entry

```json
{
  "year": "2nd Year",
  "section": "C1",
  "subjectId": "CS201",
  "facultyId": "F12",
  "noOfHours": 4,
  "continuousHours": 2,
  "compulsoryContinuousHours": 1
}
```

Purpose:

- Adds theory hours directly into the generation request.
- Can override or supplement uploaded main timetable configuration for the selected year.

### 3. Shared Class Entry

```json
{
  "year": "2nd Year",
  "sections": ["C1", "C2"],
  "subject": "CS201"
}
```

Purpose:

- Tells the generator that the subject must be placed as a shared session across multiple sections.

### 4. Mapping File IDs

```json
{
  "facultyIdMap": "file_1",
  "mainTimetableConfig": "file_2",
  "labTimetableConfig": "file_3",
  "subjectIdMapping": "file_4",
  "subjectContinuousRules": "file_5"
}
```

Purpose:

- References uploaded files already stored by the backend.
- Allows the generator to recover config data even after backend restarts when scoped mappings are missing.

### 5. Faculty Weekly Availability Entry

```json
{
  "facultyId": "F12",
  "availablePeriodsByDay": {
    "Monday": [1, 2, 3, 4],
    "Tuesday": [2, 3, 5],
    "6": [1, 2]
  }
}
```

Purpose:

- Restricts which periods a faculty member may be assigned on each day.
- Day values may be provided as day names or numeric day values.

### 6. Faculty ID to Name Mapping Entry

```json
{
  "facultyId": "F12",
  "facultyName": "Dr. Rao"
}
```

Purpose:

- Maps faculty IDs into readable faculty names for timetable output and reports.

### 7. Subject ID to Name Mapping Entry

```json
{
  "subjectId": "CS201",
  "subjectName": "Data Structures"
}
```

Purpose:

- Maps subject IDs into readable subject names for timetable output and reports.

### 8. Subject Continuous Rule Entry

```json
{
  "subjectId": "CS201",
  "compulsoryContinuousHours": 2
}
```

Purpose:

- Forces the subject to be placed with at least the given number of consecutive periods.

### 9. Manual Lab Entry

```json
{
  "year": "2nd Year",
  "section": "C1",
  "subjectId": "CSL201",
  "day": 4,
  "hours": [5, 6, 7],
  "venue": "Lab-2"
}
```

Purpose:

- Creates a locked lab session for the given section and subject.
- These hours are treated as already occupied before theory scheduling begins.

## Uploaded File Inputs Used by the Generator

The generator also consumes row-based data from uploaded files. The important expected row formats are below.

### 1. Main Timetable Config

Expected fields:

- `year`
- `section`
- `subject_id`
- `faculty_id`
- `hours`
- `continuous_hours`

Purpose:

- Defines the weekly subject-hour demand for each section.

### 2. Lab Timetable Config

Expected fields:

- `year`
- `section`
- `subject_id`
- `day`
- `hours`
- `venue`
- optional `sections`

Purpose:

- Defines fixed lab sessions that must be locked into the schedule.

### 3. Shared Classes File

Expected fields:

- `year`
- `subject` or `subject_id`
- `sections`
- optional `sections_count`

Purpose:

- Defines subjects that should be scheduled jointly across multiple sections.

### 4. Faculty ID Map

Expected fields:

- `faculty_id`
- `faculty_name`

Purpose:

- Converts faculty IDs into readable names.

### 5. Subject ID Mapping

Expected fields:

- `subject_id`
- `subject_name`

Purpose:

- Converts subject IDs into readable names.

### 6. Subject Continuous Rules

Expected fields:

- `subject_id`
- `compulsory_continuous_hours`

Purpose:

- Supplies compulsory consecutive-hour requirements.

### 7. Faculty Availability File

Expected fields:

- `faculty_id`
- `faculty_name`
- `day`
- `period`

Purpose:

- Defines which periods are available for each faculty member.

## Feasibility Check Output

The generator can run in precheck mode to test whether the timetable is feasible before final generation.

Output structure:

```json
{
  "year": "2nd Year",
  "feasible": true,
  "blockingSections": [],
  "sectionSummary": [
    {
      "section": "C1",
      "requiredHours": 36,
      "freeSlots": 38,
      "deficitHours": 0,
      "lockedSlots": 4
    }
  ],
  "issues": []
}
```

Meaning:

- `feasible`: whether the remaining demand fits into the available section slots
- `blockingSections`: sections that still have more required hours than free slots
- `sectionSummary`: per-section capacity analysis
- `issues`: validation or constraint issues found during precheck

## Final Generation Response

The immediate API response after successful request processing is:

```json
{
  "timetableId": "tt_20260418_001",
  "message": "Timetable generated successfully."
}
```

If constraints remain unresolved, the message may indicate that the timetable was generated with constraint violations.

## Stored Timetable Output Structure

The generated timetable record includes:

- `id: string`
- `year: string`
- `section: string`
- `grid: object`
- `allGrids: object`
- `facultyWorkloads: object`
- `sharedClasses: object[]`
- `constraintViolations: object[]`
- `unscheduledSubjects: object[]`
- `hasValidTimetable: boolean`
- `hasConstraintViolations: boolean`
- `generatedFiles: object`
- `generationMeta: object`

## Grid Format

Each section timetable is stored day-wise as an array of seven slots.

Example:

```json
{
  "Monday": [
    null,
    {
      "subject": "Data Structures",
      "subjectName": "Data Structures",
      "subjectId": "CS201",
      "faculty": "Dr. Rao",
      "facultyName": "Dr. Rao",
      "facultyId": "F12",
      "isLab": false,
      "locked": false,
      "venue": "",
      "sharedSections": []
    },
    null,
    null,
    null,
    null,
    null
  ]
}
```

## Faculty Workload Format

Faculty workload output is a per-faculty day map with seven period positions.

Example:

```json
{
  "Dr. Rao": {
    "Monday": ["Data Structures (C1)", null, null, null, null, null, null]
  }
}
```

## Shared Classes Output Format

Example:

```json
{
  "year": "2nd Year",
  "subject_id": "CS201",
  "subject_name": "Data Structures",
  "faculty_id": "F12",
  "faculty_name": "Dr. Rao",
  "faculty_ids": ["F12"],
  "faculty_names": ["Dr. Rao"],
  "sections": ["C1", "C2"],
  "day": "Monday",
  "periods": [2, 3],
  "venue": "",
  "isLab": false,
  "shared": true,
  "source": "shared_class_file"
}
```

## Constraint Violation Format

Example:

```json
{
  "year": "2nd Year",
  "sections": ["C1"],
  "subject_id": "CS201",
  "subject_name": "Data Structures",
  "faculty_id": "F12",
  "faculty_name": "Dr. Rao",
  "constraint": "faculty availability conflict",
  "detail": "Unable to place all remaining subject hours in valid slots."
}
```

## Unscheduled Subject Format

Example:

```json
{
  "year": "2nd Year",
  "sections": ["C1"],
  "subject_id": "CS201",
  "subject_name": "Data Structures",
  "faculty_id": "F12",
  "faculty_name": "Dr. Rao",
  "detail": "missing faculty mapping"
}
```

## Generated File Format

Each generated workbook is returned in this structure:

```json
{
  "fileName": "section_timetables.xlsx",
  "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "contentBase64": "BASE64_STRING"
}
```

## Excel Outputs Produced

### 1. Section Timetables Workbook

File name:

- `section_timetables.xlsx`

Format:

- one sheet per `year_section`
- columns: `DAY, 1, 2, 3, 4, 5, 6, 7`

Cell content format:

- `Subject Name`
- `Subject Name | Faculty Name`
- `Subject Name | Faculty Name | Venue`

### 2. Faculty Workload Workbook

File name:

- `faculty_workload.xlsx`

Format:

- one sheet per faculty
- columns: `DAY, 1, 2, 3, 4, 5, 6, 7`

### 3. Shared Classes Report Workbook

File name:

- `shared_classes_report.xlsx`

Columns:

- `YEAR`
- `SUBJECT`
- `FACULTY`
- `SECTIONS`
- `DAY`
- `PERIODS`

### 4. Constraint Violation Report Workbook

File name:

- `constraint_violation_report.xlsx`

Columns:

- `YEAR`
- `SECTIONS`
- `SUBJECT`
- `FACULTY`
- `CONSTRAINT`
- `DETAIL`

### 5. All Sections Workbook Export

Possible output file:

- `All_Class_Timetables_Format.xlsx`

Purpose:

- Exports the latest available timetable grids across saved records.

### 6. Faculty Workload Export

Possible output files:

- `All_Faculty_Workloads_Format.xlsx`
- `Workload_<FacultyName>_Format.xlsx`

Purpose:

- Exports faculty workload sheets for all faculty or one selected faculty.

## Notes

- Some schema fields exist in the request model but are not clearly used in the current generator flow.
- These include `dailySubjectLimit`, `labsOnly`, `priorTimetableIds`, `subjects`, `labs`, and `subjectHours`.
- The generator currently relies mainly on uploaded mappings, manual entries, shared class entries, faculty availability, and manual lab entries.
