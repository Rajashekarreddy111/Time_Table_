import { useState, useCallback, useRef } from "react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { mergeWorkloads, MergedWorkloadsResponse, GeneratedWorkbookFile } from "@/services/apiClient";
import {
  Upload,
  FileSpreadsheet,
  X,
  Sparkles,
  GitMerge,
  AlertTriangle,
  CheckCircle,
  FileDown,
} from "lucide-react";

function downloadGeneratedWorkbook(file: GeneratedWorkbookFile) {
  const byteCharacters = atob(file.contentBase64);
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  const byteArray = new Uint8Array(byteNumbers);
  const blob = new Blob([byteArray], { type: file.contentType });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = file.fileName;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

export default function FacultyWorkloadMerger() {
  const [files, setFiles] = useState<File[]>([]);
  const [isMerging, setIsMerging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [mergedResult, setMergedResult] = useState<MergedWorkloadsResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files) {
      const newFiles = Array.from(e.dataTransfer.files).filter(
        (f) =>
          f.name.endsWith(".xlsx") ||
          f.name.endsWith(".xls") ||
          f.name.endsWith(".csv"),
      );
      if (newFiles.length > 0) {
        setFiles((prev) => [...prev, ...newFiles]);
        setSuccess(false);
        setError(null);
        toast.success(`Added ${newFiles.length} file(s)`);
      }
    }
  }, []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files) {
        const newFiles = Array.from(e.target.files);
        if (newFiles.length > 0) {
          setFiles((prev) => [...prev, ...newFiles]);
          setSuccess(false);
          setError(null);
          toast.success(`Added ${newFiles.length} file(s)`);
        }
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
      }
    },
    [],
  );

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
    setSuccess(false);
    setError(null);
  }, []);

  const clearAll = useCallback(() => {
    setFiles([]);
    setSuccess(false);
    setError(null);
  }, []);

  const handleMerge = async () => {
    if (files.length < 2) {
      toast.error("Please upload at least 2 workload sheets to merge.");
      return;
    }

    setIsMerging(true);
    setError(null);
    setSuccess(false);

    try {
      const response = await mergeWorkloads(files);
      setMergedResult(response);
      setSuccess(true);
      toast.success("Workloads merged successfully!");
    } catch (err) {
      const errMsg =
        err instanceof Error ? err.message : "Failed to merge workloads.";
      setError(errMsg);
      toast.error("Workload merging failed");
    } finally {
      setIsMerging(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="w-full space-y-6">
        <div className="page-header">
          <h1 className="flex items-center gap-2">
            <GitMerge className="h-6 w-6 text-primary" />
            Merge Faculty Workloads
          </h1>
          <p>
            Upload and merge multiple faculty workload spreadsheets into a single consolidated workbook.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            {/* Upload Area */}
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              className="border-2 border-dashed border-border rounded-xl p-10 text-center hover:border-primary/50 transition-all bg-card shadow-sm hover:shadow-md flex flex-col items-center justify-center min-h-[260px] relative overflow-hidden group"
            >
              <div className="absolute inset-0 bg-gradient-to-tr from-primary/5 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />

              <label className="cursor-pointer flex flex-col items-center gap-4 w-full h-full justify-center">
                <div className="h-16 w-16 rounded-2xl bg-primary/10 flex items-center justify-center text-primary group-hover:scale-110 transition-transform">
                  <Upload className="h-8 w-8" />
                </div>
                <div className="space-y-1.5 max-w-md">
                  <p className="text-base font-semibold text-foreground">
                    Drag and drop workload files here
                  </p>
                  <p className="text-sm text-muted-foreground">
                    or <span className="text-primary font-semibold hover:underline">browse local files</span>
                  </p>
                  <p className="text-xs text-muted-foreground/80 mt-1">
                    Supports multiple Excel formats (.xlsx, .xls, .csv)
                  </p>
                </div>
                <input
                  type="file"
                  multiple
                  accept=".xlsx,.xls,.csv"
                  className="hidden"
                  onChange={handleFileChange}
                  ref={fileInputRef}
                />
              </label>
            </div>

            {/* Success and Error Indicators */}
            {success && mergedResult && (
              <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-5 flex flex-col gap-4 text-emerald-700 dark:text-emerald-400">
                <div className="flex gap-3 items-start">
                  <CheckCircle className="h-5 w-5 mt-0.5 flex-shrink-0" />
                  <div className="space-y-1">
                    <p className="font-semibold text-sm">Workloads Merged Successfully</p>
                    <p className="text-xs opacity-90">
                      The workloads have been merged successfully. Any duplicate availability conflicts detected have been logged in the "Validation Report" sheet of both workbooks.
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-3 pl-8">
                  <Button
                    onClick={() => downloadGeneratedWorkbook(mergedResult.facultyWorkloadWorkbook)}
                    className="flex items-center gap-2 font-semibold shadow-sm text-white bg-emerald-600 hover:bg-emerald-700 dark:bg-emerald-500 dark:hover:bg-emerald-600"
                    size="sm"
                  >
                    <FileDown className="h-4 w-4" /> Download Workload
                  </Button>
                  <Button
                    onClick={() => downloadGeneratedWorkbook(mergedResult.printableWorkloadWorkbook)}
                    className="flex items-center gap-2 font-semibold shadow-sm text-white bg-emerald-600 hover:bg-emerald-700 dark:bg-emerald-500 dark:hover:bg-emerald-600"
                    size="sm"
                  >
                    <FileDown className="h-4 w-4" /> Printable Download
                  </Button>
                </div>
              </div>
            )}

            {error && (
              <div className="rounded-xl border border-destructive/20 bg-destructive/5 p-4 flex gap-3 items-start text-destructive">
                <AlertTriangle className="h-5 w-5 mt-0.5 flex-shrink-0" />
                <div className="space-y-1">
                  <p className="font-semibold text-sm">Merging Failed</p>
                  <p className="text-xs opacity-90">{error}</p>
                </div>
              </div>
            )}

            {/* Selected Files List */}
            {files.length > 0 && (
              <div className="bg-card rounded-xl border border-border p-6 shadow-sm space-y-4">
                <div className="flex items-center justify-between border-b border-border/80 pb-3">
                  <h3 className="font-semibold text-sm flex items-center gap-2 text-foreground">
                    <FileSpreadsheet className="h-4 w-4 text-primary" />
                    Selected Sheets ({files.length})
                  </h3>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={clearAll}
                    className="text-xs text-muted-foreground hover:text-destructive transition-colors h-8"
                  >
                    Clear All
                  </Button>
                </div>

                <div className="max-h-[300px] overflow-y-auto space-y-2 pr-1">
                  {files.map((file, idx) => (
                    <div
                      key={`${file.name}-${idx}`}
                      className="flex items-center justify-between p-3 rounded-lg border border-border/60 bg-muted/20 hover:bg-muted/40 transition-colors"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="h-8 w-8 rounded-lg bg-green-500/10 flex items-center justify-center text-green-600 dark:text-green-400 flex-shrink-0">
                          <FileSpreadsheet className="h-4.5 w-4.5" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-xs font-semibold text-foreground truncate max-w-[280px] sm:max-w-[400px]">
                            {file.name}
                          </p>
                          <p className="text-[10px] text-muted-foreground">
                            {(file.size / 1024).toFixed(1)} KB
                          </p>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => removeFile(idx)}
                        className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-full"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Action sidebar / info panel */}
          <div className="space-y-6">
            <div className="bg-card rounded-xl border border-border p-6 shadow-sm space-y-5">
              <h3 className="font-bold text-sm text-foreground flex items-center gap-1.5 pb-2 border-b">
                <Sparkles className="h-4 w-4 text-amber-500" />
                Workload Merge Guide
              </h3>

              <div className="text-xs space-y-4 text-muted-foreground leading-relaxed">
                <div>
                  <p className="font-semibold text-foreground mb-1">
                    1. Upload Individual Sheets
                  </p>
                  <p>
                    Select or drag-and-drop the workload files for each faculty or department.
                  </p>
                </div>
                <div>
                  <p className="font-semibold text-foreground mb-1">
                    2. Resolve Names and IDs
                  </p>
                  <p>
                    The system automatically maps records by matching both "Faculty Name" and "Faculty ID" headers, merging availability into a single timeline.
                  </p>
                </div>
                <div>
                  <p className="font-semibold text-foreground mb-1">
                    3. Validation & Conflicts
                  </p>
                  <p>
                    If multiple workloads schedule a faculty member for different subjects at the same period, the merger automatically flags it in a "Validation Report" tab inside the downloaded Excel file.
                  </p>
                </div>
              </div>

              <div className="pt-2 border-t">
                <Button
                  onClick={handleMerge}
                  disabled={files.length < 2 || isMerging}
                  className="w-full flex items-center justify-center gap-2 font-semibold shadow-sm h-11"
                >
                  {isMerging ? (
                    <>
                      <div className="h-4 w-4 border-2 border-background border-t-transparent rounded-full animate-spin" />
                      Merging Workloads...
                    </>
                  ) : (
                    <>
                      <GitMerge className="h-4.5 w-4.5" />
                      Merge {files.length > 0 ? `${files.length} Workloads` : ""}
                    </>
                  )}
                </Button>
                {files.length < 2 && (
                  <p className="text-[10px] text-muted-foreground text-center mt-2.5">
                    Select at least 2 files to begin merging.
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
