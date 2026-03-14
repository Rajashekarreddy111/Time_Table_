import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Download, FileText } from "lucide-react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { listTimetables, type GeneratedWorkbookFile, type TimetableRecord } from "@/services/apiClient";
import { toast } from "sonner";

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

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="page-header">
          <h1>Generated Outputs</h1>
          <p>See only the shared class report and constraint violations for each generated run</p>
        </div>

        <div className="bg-card rounded-xl p-6 shadow-sm border border-border/60">
          <div className="flex flex-wrap items-end gap-4">
            <div className="w-full md:w-[420px]">
              <Label className="text-xs text-muted-foreground">Generated Run</Label>
              <Select value={selectedRecordId} onValueChange={setSelectedRecordId}>
                <SelectTrigger>
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

            {activeRecord?.generatedFiles?.sharedClassesReport && (
              <Button variant="outline" size="sm" className="gap-1.5" onClick={() => downloadGeneratedWorkbook(activeRecord.generatedFiles!.sharedClassesReport!)}>
                <Download className="h-3.5 w-3.5" /> Shared Class Report
              </Button>
            )}
            {activeRecord?.generatedFiles?.constraintViolationReport && (
              <Button variant="outline" size="sm" className="gap-1.5" onClick={() => downloadGeneratedWorkbook(activeRecord.generatedFiles!.constraintViolationReport!)}>
                <Download className="h-3.5 w-3.5" /> Constraint Report
              </Button>
            )}
          </div>
        </div>

        {activeRecord ? (
          <div className="space-y-6">
            <div className="bg-card rounded-xl p-6 shadow-sm">
              <div className="flex items-center gap-2 mb-4">
                <FileText className="h-4 w-4" />
                <h2 className="text-base font-semibold">Shared Class Report</h2>
              </div>
              {activeRecord.sharedClasses?.length ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left text-xs px-3 py-2">Year</th>
                        <th className="text-left text-xs px-3 py-2">Subject</th>
                        <th className="text-left text-xs px-3 py-2">Faculty</th>
                        <th className="text-left text-xs px-3 py-2">Sections</th>
                        <th className="text-left text-xs px-3 py-2">Day</th>
                        <th className="text-left text-xs px-3 py-2">Periods</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeRecord.sharedClasses.map((item, index) => (
                        <tr key={`${item.subject_id}-${item.day}-${index}`} className="border-b border-border/60 last:border-b-0">
                          <td className="px-3 py-2 text-sm">{item.year}</td>
                          <td className="px-3 py-2 text-sm">{item.subject_name || "-"}</td>
                          <td className="px-3 py-2 text-sm">{item.faculty_name || "-"}</td>
                          <td className="px-3 py-2 text-sm">{item.sections.join(", ")}</td>
                          <td className="px-3 py-2 text-sm">{item.day}</td>
                          <td className="px-3 py-2 text-sm">{item.periods.join(", ")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No shared classes detected for this generated run.</p>
              )}
            </div>

            <div className="bg-card rounded-xl p-6 shadow-sm">
              <h2 className="text-base font-semibold mb-4">Constraint Violation Report</h2>
              {activeRecord.constraintViolations?.length || activeRecord.unscheduledSubjects?.length ? (
                <div className="space-y-6">
                  {Boolean(activeRecord.constraintViolations?.length) && (
                    <div className="overflow-x-auto">
                      <table className="min-w-full">
                        <thead>
                          <tr className="border-b border-border">
                            <th className="text-left text-xs px-3 py-2">Year</th>
                            <th className="text-left text-xs px-3 py-2">Sections</th>
                            <th className="text-left text-xs px-3 py-2">Subject</th>
                            <th className="text-left text-xs px-3 py-2">Faculty</th>
                            <th className="text-left text-xs px-3 py-2">Constraint</th>
                            <th className="text-left text-xs px-3 py-2">Detail</th>
                          </tr>
                        </thead>
                        <tbody>
                          {activeRecord.constraintViolations?.map((item, index) => (
                            <tr key={`${item.subject_id}-${item.constraint}-${index}`} className="border-b border-border/60 last:border-b-0">
                              <td className="px-3 py-2 text-sm">{item.year}</td>
                              <td className="px-3 py-2 text-sm">{item.sections.join(", ")}</td>
                              <td className="px-3 py-2 text-sm">{item.subject_name || "-"}</td>
                              <td className="px-3 py-2 text-sm">{item.faculty_name || "-"}</td>
                              <td className="px-3 py-2 text-sm">{item.constraint}</td>
                              <td className="px-3 py-2 text-sm">{item.detail}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {Boolean(activeRecord.unscheduledSubjects?.length) && (
                    <div>
                      <h3 className="text-sm font-semibold mb-3">Unscheduled Subjects</h3>
                      <div className="overflow-x-auto">
                        <table className="min-w-full">
                          <thead>
                            <tr className="border-b border-border">
                              <th className="text-left text-xs px-3 py-2">Year</th>
                              <th className="text-left text-xs px-3 py-2">Sections</th>
                              <th className="text-left text-xs px-3 py-2">Subject</th>
                              <th className="text-left text-xs px-3 py-2">Faculty</th>
                              <th className="text-left text-xs px-3 py-2">Detail</th>
                            </tr>
                          </thead>
                          <tbody>
                            {activeRecord.unscheduledSubjects?.map((item, index) => (
                              <tr key={`${item.subject_id}-unscheduled-${index}`} className="border-b border-border/60 last:border-b-0">
                                <td className="px-3 py-2 text-sm">{item.year}</td>
                                <td className="px-3 py-2 text-sm">{item.sections.join(", ")}</td>
                                <td className="px-3 py-2 text-sm">{item.subject_name || "-"}</td>
                                <td className="px-3 py-2 text-sm">{item.faculty_name || "-"}</td>
                                <td className="px-3 py-2 text-sm">{item.detail}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No constraint violations for this generated run.</p>
              )}
            </div>
          </div>
        ) : (
          <div className="bg-card rounded-xl p-6 shadow-sm text-sm text-muted-foreground">
            No generated outputs are available yet.
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default GeneratedOutputs;
