import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  Download,
  FileSpreadsheet,
  FileText,
  Layers3,
  Link2,
} from "lucide-react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { listTimetables, type GeneratedWorkbookFile, type TimetableRecord } from "@/services/apiClient";
import { toast } from "sonner";
import * as XLSX from "xlsx";

function downloadGeneratedWorkbook(file: GeneratedWorkbookFile) {
  const binary = atob(file.contentBase64);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  const blob = new Blob([bytes], { type: file.contentType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = file.fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function exportSharedClassesWorkbook(record: TimetableRecord) {
  const items = record.sharedClasses ?? [];
  if (items.length === 0) {
    toast.error("No shared class report data available.");
    return;
  }

  const rows = items.map((item) => ({
    Year: item.year,
    Subject: item.subject_name || item.subject_id || "-",
    Faculty: item.faculty_name || item.faculty_id || "-",
    Sections: item.sections.join(", "),
    Day: item.day,
    Periods: item.periods.join(", "),
    Venue: item.venue || "",
    Type: item.isLab ? "Lab" : "Class",
  }));

  const workbook = XLSX.utils.book_new();
  const worksheet = XLSX.utils.json_to_sheet(rows);
  XLSX.utils.book_append_sheet(workbook, worksheet, "Shared Classes");
  XLSX.writeFile(workbook, `${record.id}_shared_classes_report.xlsx`);
}

function exportConstraintWorkbook(record: TimetableRecord) {
  const violations = record.constraintViolations ?? [];
  const unscheduled = record.unscheduledSubjects ?? [];

  if (violations.length === 0 && unscheduled.length === 0) {
    toast.error("No constraint report data available.");
    return;
  }

  const workbook = XLSX.utils.book_new();

  if (violations.length > 0) {
    const violationRows = violations.map((item) => ({
      Year: item.year,
      Sections: item.sections.join(", "),
      Subject: item.subject_name || item.subject_id || "-",
      Faculty: item.faculty_name || item.faculty_id || "-",
      Constraint: item.constraint,
      Detail: item.detail,
    }));
    const violationSheet = XLSX.utils.json_to_sheet(violationRows);
    XLSX.utils.book_append_sheet(workbook, violationSheet, "Violations");
  }

  if (unscheduled.length > 0) {
    const unscheduledRows = unscheduled.map((item) => ({
      Year: item.year,
      Sections: item.sections.join(", "),
      Subject: item.subject_name || item.subject_id || "-",
      Faculty: item.faculty_name || item.faculty_id || "-",
      Detail: item.detail,
    }));
    const unscheduledSheet = XLSX.utils.json_to_sheet(unscheduledRows);
    XLSX.utils.book_append_sheet(workbook, unscheduledSheet, "Unscheduled");
  }

  XLSX.writeFile(workbook, `${record.id}_constraint_report.xlsx`);
}

function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-border/70 bg-muted/20 p-8 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-muted text-muted-foreground">
        <FileText className="h-6 w-6" />
      </div>
      <h3 className="mt-4 text-base font-semibold text-foreground">{title}</h3>
      <p className="mx-auto mt-2 max-w-xl text-sm text-muted-foreground">{description}</p>
    </div>
  );
}

function DataTable({
  headers,
  rows,
}: {
  headers: string[];
  rows: React.ReactNode[][];
}) {
  return (
    <div className="overflow-hidden rounded-2xl border border-border/70">
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead className="bg-slate-100/80">
            <tr>
              {headers.map((header) => (
                <th
                  key={header}
                  className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-600"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-card">
            {rows.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                className="border-t border-border/60 transition-colors hover:bg-muted/20"
              >
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex} className="px-4 py-3 text-sm text-foreground align-top">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const GeneratedOutputs = () => {
  const [searchParams] = useSearchParams();
  const timetableId = searchParams.get("timetableId");
  const [records, setRecords] = useState<TimetableRecord[]>([]);
  const [selectedRecordId, setSelectedRecordId] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const response = await listTimetables();
        setRecords(response.items ?? []);
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Failed to load generated outputs");
      }
    };
    void load();
  }, []);

  useEffect(() => {
    if (!records.length) return;
    const matching = timetableId ? records.find((record) => record.id === timetableId) : null;
    if (matching) {
      setSelectedRecordId(matching.id);
      return;
    }
    if (!records.some((record) => record.id === selectedRecordId)) {
      setSelectedRecordId(records[0].id);
    }
  }, [records, selectedRecordId, timetableId]);

  const activeRecord = useMemo(
    () => records.find((record) => record.id === selectedRecordId) ?? null,
    [records, selectedRecordId],
  );

  const sharedCount = activeRecord?.sharedClasses?.length ?? 0;
  const violationCount = activeRecord?.constraintViolations?.length ?? 0;
  const unscheduledCount = activeRecord?.unscheduledSubjects?.length ?? 0;

  const statCards = [
    {
      label: "Shared Classes",
      value: sharedCount,
      hint: "Cross-section or linked sessions in this run",
      icon: Link2,
      tone: "text-sky-700 bg-sky-100",
    },
    {
      label: "Violations",
      value: violationCount,
      hint: "Constraint conflicts captured in the report",
      icon: AlertTriangle,
      tone: "text-amber-700 bg-amber-100",
    },
    {
      label: "Unscheduled",
      value: unscheduledCount,
      hint: "Subjects that could not be placed",
      icon: Layers3,
      tone: "text-rose-700 bg-rose-100",
    },
  ];

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="rounded-3xl border border-border/70 bg-[linear-gradient(135deg,rgba(15,23,42,0.04),rgba(14,165,233,0.10),rgba(255,255,255,0.92))] p-6 shadow-sm">
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px] xl:items-end">
            <div className="space-y-4">
              <div className="inline-flex items-center gap-2 rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-primary shadow-sm">
                <FileSpreadsheet className="h-3.5 w-3.5" />
                Generated reporting hub
              </div>
              <div className="space-y-2">
                <h1 className="text-3xl font-bold tracking-tight text-foreground">
                  Generated Outputs
                </h1>
                <p className="max-w-2xl text-sm text-muted-foreground">
                  Review shared classes, constraint issues, and unscheduled subjects
                  for each generated timetable run, then download polished Excel outputs
                  directly from this page.
                </p>
              </div>
            </div>

            <div className="rounded-2xl border border-border/70 bg-card/90 p-5 shadow-sm">
              <Label className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                Generated Run
              </Label>
              <div className="mt-3">
                <Select value={selectedRecordId} onValueChange={setSelectedRecordId}>
                  <SelectTrigger className="h-12">
                    <SelectValue placeholder="Select a generated run" />
                  </SelectTrigger>
                  <SelectContent>
                    {records.map((record) => (
                      <SelectItem key={record.id} value={record.id}>
                        {record.year} - {record.section} [{record.id}]
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {activeRecord ? (
                <div className="mt-4 rounded-xl bg-muted/40 p-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                    Selected
                  </p>
                  <p className="mt-2 text-base font-semibold text-foreground">
                    {activeRecord.year} - {activeRecord.section}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">{activeRecord.id}</p>
                </div>
              ) : (
                <p className="mt-4 text-sm text-muted-foreground">
                  Select a generated run to open its reports and Excel downloads.
                </p>
              )}
            </div>
          </div>
        </div>

        {activeRecord ? (
          <>
            <div className="grid gap-4 md:grid-cols-3">
              {statCards.map((card) => (
                <div key={card.label} className="stat-card flex items-start gap-4">
                  <div className={`rounded-2xl p-3 ${card.tone}`}>
                    <card.icon className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                      {card.label}
                    </p>
                    <p className="mt-2 text-3xl font-bold text-foreground">{card.value}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{card.hint}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="rounded-2xl border border-border/60 bg-card p-6 shadow-sm">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-foreground">Download Center</h2>
                  <p className="text-sm text-muted-foreground">
                    Export either the original generated workbook files or fresh Excel
                    files built from the report data shown below.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {activeRecord.generatedFiles?.sharedClassesReport && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1.5"
                      onClick={() =>
                        downloadGeneratedWorkbook(activeRecord.generatedFiles!.sharedClassesReport!)
                      }
                    >
                      <Download className="h-3.5 w-3.5" />
                      Shared Report File
                    </Button>
                  )}
                  {sharedCount > 0 && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1.5"
                      onClick={() => exportSharedClassesWorkbook(activeRecord)}
                    >
                      <Download className="h-3.5 w-3.5" />
                      Shared Classes Excel
                    </Button>
                  )}
                  {activeRecord.generatedFiles?.constraintViolationReport && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1.5"
                      onClick={() =>
                        downloadGeneratedWorkbook(activeRecord.generatedFiles!.constraintViolationReport!)
                      }
                    >
                      <Download className="h-3.5 w-3.5" />
                      Constraint Report File
                    </Button>
                  )}
                  {(violationCount > 0 || unscheduledCount > 0) && (
                    <Button
                      size="sm"
                      className="gap-1.5"
                      onClick={() => exportConstraintWorkbook(activeRecord)}
                    >
                      <Download className="h-3.5 w-3.5" />
                      Constraint Excel
                    </Button>
                  )}
                </div>
              </div>
            </div>

            <div className="grid gap-6">
              <div className="rounded-2xl border border-border/60 bg-card p-6 shadow-sm">
                <div className="mb-5 flex items-center gap-3">
                  <div className="rounded-2xl bg-sky-100 p-3 text-sky-700">
                    <Link2 className="h-5 w-5" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold text-foreground">Shared Class Report</h2>
                    <p className="text-sm text-muted-foreground">
                      Sessions that are linked across sections or shared as combined classes.
                    </p>
                  </div>
                </div>

                {sharedCount > 0 ? (
                  <DataTable
                    headers={["Year", "Subject", "Faculty", "Sections", "Day", "Periods"]}
                    rows={activeRecord.sharedClasses!.map((item) => [
                      <span className="font-medium">{item.year}</span>,
                      item.subject_name || "-",
                      item.faculty_name || "-",
                      <div className="flex flex-wrap gap-1.5">
                        {item.sections.map((section) => (
                          <span
                            key={`${item.subject_id}-${item.day}-${section}`}
                            className="rounded-full bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-700"
                          >
                            {section}
                          </span>
                        ))}
                      </div>,
                      item.day,
                      item.periods.join(", "),
                    ])}
                  />
                ) : (
                  <EmptyState
                    title="No shared classes detected"
                    description="This generated run does not contain any linked or shared class entries."
                  />
                )}
              </div>

              <div className="rounded-2xl border border-border/60 bg-card p-6 shadow-sm">
                <div className="mb-5 flex items-center gap-3">
                  <div className="rounded-2xl bg-amber-100 p-3 text-amber-700">
                    <AlertTriangle className="h-5 w-5" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold text-foreground">
                      Constraint Violation Report
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      Placement conflicts and unscheduled subjects for the selected run.
                    </p>
                  </div>
                </div>

                {violationCount > 0 || unscheduledCount > 0 ? (
                  <div className="space-y-6">
                    {violationCount > 0 && (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <h3 className="text-sm font-semibold text-foreground">Violations</h3>
                          <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-700">
                            {violationCount} items
                          </span>
                        </div>
                        <DataTable
                          headers={["Year", "Sections", "Subject", "Faculty", "Constraint", "Detail"]}
                          rows={activeRecord.constraintViolations!.map((item) => [
                            <span className="font-medium">{item.year}</span>,
                            <div className="flex flex-wrap gap-1.5">
                              {item.sections.map((section) => (
                                <span
                                  key={`${item.subject_id}-${item.constraint}-${section}`}
                                  className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground"
                                >
                                  {section}
                                </span>
                              ))}
                            </div>,
                            item.subject_name || "-",
                            item.faculty_name || "-",
                            <span className="font-medium text-amber-700">{item.constraint}</span>,
                            <span className="text-muted-foreground">{item.detail}</span>,
                          ])}
                        />
                      </div>
                    )}

                    {unscheduledCount > 0 && (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <h3 className="text-sm font-semibold text-foreground">Unscheduled Subjects</h3>
                          <span className="rounded-full bg-rose-100 px-2.5 py-1 text-xs font-medium text-rose-700">
                            {unscheduledCount} items
                          </span>
                        </div>
                        <DataTable
                          headers={["Year", "Sections", "Subject", "Faculty", "Detail"]}
                          rows={activeRecord.unscheduledSubjects!.map((item) => [
                            <span className="font-medium">{item.year}</span>,
                            <div className="flex flex-wrap gap-1.5">
                              {item.sections.map((section) => (
                                <span
                                  key={`${item.subject_id}-unscheduled-${section}`}
                                  className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground"
                                >
                                  {section}
                                </span>
                              ))}
                            </div>,
                            item.subject_name || "-",
                            item.faculty_name || "-",
                            <span className="text-muted-foreground">{item.detail}</span>,
                          ])}
                        />
                      </div>
                    )}
                  </div>
                ) : (
                  <EmptyState
                    title="No constraint issues found"
                    description="This generated run does not contain constraint violations or unscheduled subjects."
                  />
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="rounded-2xl border border-border/60 bg-card p-8 shadow-sm">
            <EmptyState
              title="No generated outputs available"
              description="Create or select a timetable run to review shared classes, violations, and downloadable Excel outputs."
            />
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default GeneratedOutputs;
