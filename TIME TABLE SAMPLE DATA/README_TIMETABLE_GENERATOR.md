# Strict Timetable Generator

This project now includes a strict constraint-satisfaction timetable generator:

- Enforces no section overlap
- Enforces no faculty double-booking
- Enforces strict faculty availability (`only` listed slots are allowed)
- Assigns fixed labs first and deducts lab hours from remaining load
- Applies only explicit shared classes
- Uses backtracking (does not force invalid placement)
- Fails with explicit reason if constraints are infeasible

## Files

- `generate_timetable.js` - main scheduler
- `generated_section_timetables.xlsx` - output (if feasible)
- `generated_faculty_workload_report.xlsx` - output (if feasible)
- `generated_faculty_availability_usage.xlsx` - output (if feasible)
- `generated_shared_classes_report.xlsx` - output (if feasible)
- `generated_constraint_report.xlsx` - always generated with success/failure

## Run

```powershell
node generate_timetable.js
```

Optional custom input order:

```powershell
node generate_timetable.js <mainConfig> <labs> <shared> <availability> <facultyMap> <subjectMap> <continuousRules>
```

Default expected names:

1. `UPDATED TIMETABLE TOTAL.xlsx`
2. `LAB.xlsx`
3. `shared-classes-template.xlsx`
4. `faculty-availability-template.xlsx`
5. `FACULTY ID MAPPING.xlsx`
6. `SUBJECT ID MAPPING.xlsx`
7. `subject-continuous-rules-template.xlsx`

## Important

Your current availability file appears to have only sample rows, so strict feasibility currently fails (for example: faculty `5` has required hours but `0` available slots).

The scheduler intentionally stops instead of producing an invalid timetable.
