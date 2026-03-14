import { useEffect, useMemo, useState } from "react";
import { Download, Printer, Trash2 } from "lucide-react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { TimetableGrid } from "@/components/TimetableGrid";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { type SectionTimetable } from "@/data/mockData";
import { toast } from "sonner";
import * as XLSX from "xlsx";
import { buildLegend, DISPLAY_DAYS, getCellByPeriod } from "@/lib/timetableFormat";
import { listTimetables, type TimetableRecord, deleteTimetable } from "@/services/apiClient";
import { ACADEMIC_METADATA, toAcademicYear } from "@/lib/academicMetadata";
import { useSearchParams } from "react-router-dom";

const TOTAL_COLUMNS = 10;

function toClassLine(year: string, section: string): string {
  const yearMap: Record<string, string> = {
    "2nd Year": "II B.Tech",
    "3rd Year": "III B.Tech",
    "4th Year": "IV B.Tech",
  };
  const normalized = yearMap[year] ?? year;
  return `${normalized} [CSE - ${section}] ${ACADEMIC_METADATA.SEMESTER} TIME TABLE`;
}

function padRow(values: string[]): string[] {
  if (values.length >= TOTAL_COLUMNS) return values.slice(0, TOTAL_COLUMNS);
  return [...values, ...Array.from({ length: TOTAL_COLUMNS - values.length }, () => "")];
}

function buildTimetableWorksheet(timetable: SectionTimetable) {
  const legend = buildLegend(timetable.grid);
  const codeBySubject = new Map(legend.map((item) => [item.subject, item.code]));
  const data: string[][] = [];

  data.push(padRow([ACADEMIC_METADATA.COLLEGE_NAME]));
  data.push(padRow(["(AUTONOMOUS)"]));
  data.push(padRow([ACADEMIC_METADATA.DEPARTMENT_NAME]));
  data.push(padRow([`ACADEMIC YEAR : ${toAcademicYear(new Date())} ${ACADEMIC_METADATA.SEMESTER}`]));
  data.push(padRow([toClassLine(timetable.year, timetable.section)]));
  data.push(padRow(["Room No :", "", "", "", "", `With effect from : ${ACADEMIC_METADATA.EFFECTIVE_DATE}`]));

  const tableHeaderRow = data.length;
  data.push(padRow(["DAY", "1", "2", "", "3", "4", "", "5", "6", "7"]));
  data.push(padRow(["", "9.10-10.00", "10.00-10.50", "10.50-11.00", "11.00-11.50", "11.50-12.40", "12.40-1.30", "1.30-2.20", "2.20-3.10", "3.10-4.00"]));

  const dayStartRow = data.length;
  DISPLAY_DAYS.forEach((day, dayIdx) => {
    const p1 = getCellByPeriod(timetable.grid, day.full, 1);
    const p2 = getCellByPeriod(timetable.grid, day.full, 2);
    const p3 = getCellByPeriod(timetable.grid, day.full, 3);
    const p4 = getCellByPeriod(timetable.grid, day.full, 4);
    const p5 = getCellByPeriod(timetable.grid, day.full, 5);
    const p6 = getCellByPeriod(timetable.grid, day.full, 6);
    const p7 = getCellByPeriod(timetable.grid, day.full, 7);

    data.push(
      padRow([
        day.shortVertical,
        (p1?.subjectName ?? p1?.subject) ? codeBySubject.get(p1?.subjectName ?? p1?.subject ?? "") ?? (p1?.subjectName ?? p1?.subject ?? "") : "",
        (p2?.subjectName ?? p2?.subject) ? codeBySubject.get(p2?.subjectName ?? p2?.subject ?? "") ?? (p2?.subjectName ?? p2?.subject ?? "") : "",
        dayIdx === 0 ? "BREAK" : "",
        (p3?.subjectName ?? p3?.subject) ? codeBySubject.get(p3?.subjectName ?? p3?.subject ?? "") ?? (p3?.subjectName ?? p3?.subject ?? "") : "",
        (p4?.subjectName ?? p4?.subject) ? codeBySubject.get(p4?.subjectName ?? p4?.subject ?? "") ?? (p4?.subjectName ?? p4?.subject ?? "") : "",
        dayIdx === 0 ? "LUNCH" : "",
        (p5?.subjectName ?? p5?.subject) ? codeBySubject.get(p5?.subjectName ?? p5?.subject ?? "") ?? (p5?.subjectName ?? p5?.subject ?? "") : "",
        (p6?.subjectName ?? p6?.subject) ? codeBySubject.get(p6?.subjectName ?? p6?.subject ?? "") ?? (p6?.subjectName ?? p6?.subject ?? "") : "",
        (p7?.subjectName ?? p7?.subject) ? codeBySubject.get(p7?.subjectName ?? p7?.subject ?? "") ?? (p7?.subjectName ?? p7?.subject ?? "") : "",
      ]),
    );
  });

  data.push(padRow([""]));
  const legendStart = data.length;
  for (let i = 0; i < legend.length; i += 2) {
    const left = legend[i];
    const right = legend[i + 1];
    data.push(
      padRow([
        left ? `${left.code} : ${left.subject} : ${left.faculty}` : "",
        "",
        "",
        "",
        "",
        right ? `${right.code} : ${right.subject} : ${right.faculty}` : "",
        "",
        "",
        "",
        "",
      ]),
    );
  }

  data.push(padRow([""]));
  data.push(padRow(["HEAD OF THE DEPARTMENT", "", "", "", "", "PRINCIPAL"]));

  const ws = XLSX.utils.aoa_to_sheet(data);
  ws["!cols"] = [
    { wch: 7 },
    { wch: 12 },
    { wch: 12 },
    { wch: 10 },
    { wch: 12 },
    { wch: 12 },
    { wch: 10 },
    { wch: 12 },
    { wch: 12 },
    { wch: 12 },
  ];
  ws["!rows"] = data.map((_, idx) => {
    if (idx >= dayStartRow && idx < dayStartRow + DISPLAY_DAYS.length) return { hpt: 34 };
    if (idx <= 5) return { hpt: 20 };
    return { hpt: 18 };
  });
  ws["!merges"] = [
    { s: { r: 0, c: 0 }, e: { r: 0, c: 9 } },
    { s: { r: 1, c: 0 }, e: { r: 1, c: 9 } },
    { s: { r: 2, c: 0 }, e: { r: 2, c: 9 } },
    { s: { r: 3, c: 0 }, e: { r: 3, c: 9 } },
    { s: { r: 4, c: 0 }, e: { r: 4, c: 9 } },
    { s: { r: 5, c: 0 }, e: { r: 5, c: 4 } },
    { s: { r: 5, c: 5 }, e: { r: 5, c: 9 } },
    { s: { r: tableHeaderRow, c: 0 }, e: { r: tableHeaderRow + 1, c: 0 } },
    { s: { r: dayStartRow, c: 3 }, e: { r: dayStartRow + DISPLAY_DAYS.length - 1, c: 3 } },
    { s: { r: dayStartRow, c: 6 }, e: { r: dayStartRow + DISPLAY_DAYS.length - 1, c: 6 } },
    ...Array.from({ length: Math.ceil(legend.length / 2) }).flatMap((_, idx) => {
      const row = legendStart + idx;
      return [
        { s: { r: row, c: 0 }, e: { r: row, c: 4 } },
        { s: { r: row, c: 5 }, e: { r: row, c: 9 } },
      ];
    }),
    { s: { r: data.length - 1, c: 0 }, e: { r: data.length - 1, c: 4 } },
    { s: { r: data.length - 1, c: 5 }, e: { r: data.length - 1, c: 9 } },
  ];

  return ws;
}

function extractSectionTimetables(records: TimetableRecord[]): SectionTimetable[] {
  const items: SectionTimetable[] = [];
  for (const record of records) {
    if (record.allGrids) {
      for (const [section, grid] of Object.entries(record.allGrids)) {
        items.push({ year: record.year, section, grid });
      }
      continue;
    }
    if (record.grid) {
      items.push({ year: record.year, section: record.section, grid: record.grid });
    }
  }
  return items;
}

const TimetableViewer = () => {
  const [searchParams] = useSearchParams();
  const timetableId = searchParams.get("timetableId");

  const [records, setRecords] = useState<TimetableRecord[]>([]);
  const [selectedYear, setSelectedYear] = useState<string>("");
  const [selectedSection, setSelectedSection] = useState<string>("");

  useEffect(() => {
    if (timetableId && records.length > 0) {
      const target = records.find(r => r.id === timetableId);
      if (target) {
        setSelectedYear(target.year);
        setSelectedSection(target.section);
      }
    }
  }, [timetableId, records]);

  useEffect(() => {
    const load = async () => {
      try {
        const response = await listTimetables();
        setRecords(response.items ?? []);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to load timetables");
      }
    };
    void load();
  }, []);

  const validRecords = useMemo(
    () => records.filter((record) => record.hasValidTimetable !== false),
    [records],
  );
  const allTimetables = useMemo(() => extractSectionTimetables(validRecords), [validRecords]);
  const availableYears = useMemo(() => Array.from(new Set(allTimetables.map((item) => item.year))), [allTimetables]);
  const availableSections = useMemo(
    () => Array.from(new Set(allTimetables.filter((item) => item.year === selectedYear).map((item) => item.section))),
    [allTimetables, selectedYear],
  );

  useEffect(() => {
    if (availableYears.length > 0 && !availableYears.includes(selectedYear)) {
      setSelectedYear(availableYears[0]);
    }
  }, [availableYears, selectedYear]);

  useEffect(() => {
    if (availableSections.length > 0 && !availableSections.includes(selectedSection)) {
      setSelectedSection(availableSections[0]);
    }
  }, [availableSections, selectedSection]);

  const timetable = allTimetables.find((item) => item.year === selectedYear && item.section === selectedSection);
  const activeRecord = validRecords.find((record) =>
    (record.year === selectedYear && record.section === selectedSection) ||
    Boolean(record.allGrids && record.allGrids[selectedSection]),
  );

  const handleExportExcel = () => {
    if (!timetable) return;
    const wb = XLSX.utils.book_new();
    const ws = buildTimetableWorksheet(timetable);
    XLSX.utils.book_append_sheet(wb, ws, `${selectedYear.replace(" ", "")}-${selectedSection}`);
    XLSX.writeFile(wb, `Timetable_${selectedYear.replace(" ", "_")}_${selectedSection}_Format.xlsx`);
    toast.success("Excel file downloaded in timetable format.");
  };

  const handleExportAllTimetables = () => {
    if (allTimetables.length === 0) {
      toast.error("No timetables available.");
      return;
    }
    const wb = XLSX.utils.book_new();
    allTimetables.forEach((item) => {
      const ws = buildTimetableWorksheet(item);
      const sheetName = `${item.year.replace(" ", "")}-${item.section}`.slice(0, 31);
      XLSX.utils.book_append_sheet(wb, ws, sheetName);
    });
    XLSX.writeFile(wb, "All_Class_Timetables_Format.xlsx");
    toast.success("All class timetables exported.");
  };

  const handlePrint = () => window.print();

  const handleDelete = async () => {
    const record = activeRecord;

    if (!record) return;

    if (!confirm("Are you sure you want to delete this timetable?")) return;

    try {
      await deleteTimetable(record.id);
      toast.success("Timetable deleted successfully");
      // Refresh list
      const response = await listTimetables();
      setRecords(response.items ?? []);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to delete timetable");
    }
  };

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>View Timetables</h1>
        <p>Browse and export generated section timetables</p>
      </div>

      {allTimetables.length > 1 && (
        <div className="bg-primary/5 border border-primary/20 rounded-xl p-4 mb-6 print:hidden">
          <h3 className="text-xs font-semibold text-primary uppercase tracking-wider mb-3">Recently Generated / Available Sections</h3>
          <div className="flex flex-wrap gap-2">
            {allTimetables.map((item, idx) => (
              <Button
                key={`${item.year}-${item.section}-${idx}`}
                variant={selectedYear === item.year && selectedSection === item.section ? "default" : "outline"}
                size="sm"
                className="h-8 text-xs"
                onClick={() => {
                  setSelectedYear(item.year);
                  setSelectedSection(item.section);
                }}
              >
                {item.year.replace(" Year", "")} - {item.section}
              </Button>
            ))}
          </div>
        </div>
      )}

      <div className="bg-card rounded-xl p-6 shadow-sm mb-6 print:hidden">
        <div className="flex flex-wrap items-end gap-4">
          <div className="w-48">
            <Label className="text-xs text-muted-foreground">Year</Label>
            <Select value={selectedYear} onValueChange={setSelectedYear}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {availableYears.map((year) => <SelectItem key={year} value={year}>{year}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          <div className="w-48">
            <Label className="text-xs text-muted-foreground">Section</Label>
            <Select value={selectedSection} onValueChange={setSelectedSection}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {availableSections.map((section) => <SelectItem key={section} value={section}>{section}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          <div className="flex gap-2 ml-auto">
            <Button variant="outline" size="sm" onClick={handleExportExcel} className="gap-1.5">
              <Download className="h-3.5 w-3.5" /> Download Excel
            </Button>
            <Button variant="outline" size="sm" onClick={handleExportAllTimetables} className="gap-1.5">
              <Download className="h-3.5 w-3.5" /> Download All Timetables
            </Button>
            <Button variant="outline" size="sm" onClick={handlePrint} className="gap-1.5">
              <Printer className="h-3.5 w-3.5" /> Print
            </Button>
            <Button variant="destructive" size="sm" onClick={handleDelete} className="gap-1.5">
              <Trash2 className="h-3.5 w-3.5" /> Delete
            </Button>
          </div>
        </div>
      </div>

      <div className="bg-card rounded-xl p-6 shadow-sm print:shadow-none print:p-0">
        {timetable ? (
          <div className="space-y-4">
            <TimetableGrid
              grid={timetable.grid}
              header={{
                college: ACADEMIC_METADATA.COLLEGE_NAME,
                department: ACADEMIC_METADATA.DEPARTMENT_NAME,
                year: toAcademicYear(new Date()),
                semester: ACADEMIC_METADATA.SEMESTER,
                section: toClassLine(selectedYear, selectedSection),
                room: selectedSection,
              }}
            />
          </div>
        ) : (
          <div className="text-center py-16">
            <p className="text-muted-foreground">No valid timetable is available for {selectedYear} - Section {selectedSection}.</p>
            <p className="text-xs text-muted-foreground mt-1">If generation failed, check the Generated Outputs page for the constraint report.</p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default TimetableViewer;
