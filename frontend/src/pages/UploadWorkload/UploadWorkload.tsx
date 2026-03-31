import { useEffect, useState } from "react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { FileUpload } from "@/components/FileUpload";
import { buildTemplateLinks } from "@/utils/templateLinks";
import { toast } from "sonner";
import { API_BASE_URL, getFacultyIdStatus, uploadFacultyAvailability, uploadFacultyIdMap } from "@/services/apiClient";

const UploadWorkload = () => {
  const [workloadFile, setWorkloadFile] = useState<File | null>(null);
  const [facultyIdFile, setFacultyIdFile] = useState<File | null>(null);
  const [workloadUploadId, setWorkloadUploadId] = useState<string>("");
  const [facultyIdUploadId, setFacultyIdUploadId] = useState<string>("");
  const [facultyIdMapUploaded, setFacultyIdMapUploaded] = useState(false);
  const [facultyIdMapFileName, setFacultyIdMapFileName] = useState<string | null>(null);
  const templateBase = `${API_BASE_URL}/templates`;

  const loadFacultyIdStatus = async () => {
    try {
      const status = await getFacultyIdStatus();
      setFacultyIdMapUploaded(status.facultyIdMapUploaded);
      setFacultyIdMapFileName(status.facultyIdMapFileName ?? null);
    } catch {
      setFacultyIdMapUploaded(false);
      setFacultyIdMapFileName(null);
    }
  };

  useEffect(() => {
    loadFacultyIdStatus();
  }, []);

  const handleWorkloadFileSelect = async (f: File) => {
    setWorkloadFile(f);
    try {
      const response = await uploadFacultyAvailability(f);
      setWorkloadUploadId(response.fileId);
      toast.success(`Workload uploaded: "${f.name}"`);
    } catch (error) {
      setWorkloadUploadId("");
      toast.error(error instanceof Error ? error.message : "Workload upload failed");
    }
  };

  const handleFacultyIdFileSelect = async (f: File) => {
    if (facultyIdMapUploaded) {
      toast.error("Faculty-ID mapping is already uploaded globally for this academic year.");
      return;
    }
    setFacultyIdFile(f);
    try {
      const response = await uploadFacultyIdMap(f);
      setFacultyIdUploadId(response.fileId);
      setFacultyIdMapUploaded(true);
      setFacultyIdMapFileName(response.fileName);
      toast.success(`Faculty-ID map uploaded: "${f.name}"`);
    } catch (error) {
      setFacultyIdUploadId("");
      toast.error(error instanceof Error ? error.message : "Faculty-ID upload failed");
    }
  };

  return (
    <DashboardLayout>
      <div className="page-header">
        <h1>Upload Faculty Workload</h1>
        <p>Upload workload files to parse faculty schedules</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-card rounded-xl p-6 shadow-sm">
          <FileUpload
            file={workloadFile}
            onFileSelect={handleWorkloadFileSelect}
            onClear={() => {
              setWorkloadFile(null);
              setWorkloadUploadId("");
            }}
            label="Upload Faculty Workload File"
            accept=".xlsx,.xls,.csv"
            description="Upload faculty workload file (XLSX/XLS/CSV)"
            templateLinks={buildTemplateLinks(templateBase, "faculty-workload")}
          />
          <p className="text-xs text-muted-foreground mt-2">
            {workloadUploadId ? `Workload upload id: ${workloadUploadId}` : "No workload file uploaded yet."}
          </p>
        </div>

        <div className="bg-card rounded-xl p-6 shadow-sm">
          {facultyIdMapUploaded ? (
            <div className="rounded-lg border border-border/70 bg-background p-4 text-xs text-muted-foreground">
              Faculty-ID map already uploaded globally:{" "}
              <span className="font-medium text-foreground">{facultyIdMapFileName ?? "Already uploaded"}</span>
            </div>
          ) : (
            <FileUpload
              file={facultyIdFile}
              onFileSelect={handleFacultyIdFileSelect}
              onClear={() => {
                setFacultyIdFile(null);
                setFacultyIdUploadId("");
              }}
              label="Upload Faculty ID Map"
              accept=".xlsx,.xls,.csv"
              description="Upload faculty name-id mapping file (XLSX/XLS/CSV)"
              templateLinks={buildTemplateLinks(templateBase, "faculty-id-map")}
            />
          )}
          <p className="text-xs text-muted-foreground mt-2">
            {facultyIdUploadId
              ? `Faculty-ID upload id: ${facultyIdUploadId}`
              : facultyIdMapUploaded
                ? "Faculty-id map is locked after first upload."
                : "No faculty-id map uploaded yet."}
          </p>
        </div>
      </div>

      {workloadFile && (
        <div className="bg-card rounded-xl p-6 shadow-sm">
          <h3 className="text-sm font-semibold text-foreground mb-3">File Preview</h3>
          <div className="border border-border rounded-lg p-6 bg-muted/30 text-center">
            <p className="text-sm text-muted-foreground">
              Uploaded workload file: <span className="font-medium text-foreground">{workloadFile.name}</span>
            </p>
            <p className="text-xs text-muted-foreground mt-2">
              This file is now sent to backend and can be used in faculty availability search.
            </p>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
};

export default UploadWorkload;
