import { useCallback, useRef } from "react";
import { Upload, FileSpreadsheet, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ReactNode } from "react";

interface FileUploadProps {
  onFileSelect: (file: File) => void;
  file: File | null;
  onClear: () => void;
  accept?: string;
  label?: string;
  description?: string;
  icon?: ReactNode;
  templateLinks?: { label: string; href: string }[];
}

export function FileUpload({
  onFileSelect,
  file,
  onClear,
  accept = ".xlsx,.xls",
  label = "Upload File",
  description = "Drag & drop or click to browse",
  icon,
  templateLinks = [],
}: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const f = e.dataTransfer.files[0];
      if (f) onFileSelect(f);
    },
    [onFileSelect],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      if (f) {
        onFileSelect(f);
        if (inputRef.current) inputRef.current.value = "";
      }
    },
    [onFileSelect],
  );

  return (
    <div
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      className="border-2 border-dashed border-border rounded-xl p-8 text-center hover:border-primary/50 transition-colors bg-muted/30"
    >
      {file ? (
        <div className="flex flex-col items-center gap-3">
          <div className="flex items-center justify-center gap-3">
            <FileSpreadsheet className="h-8 w-8 text-primary" />
            <div className="text-left">
              <p className="text-sm font-medium text-foreground">{file.name}</p>
              <p className="text-xs text-muted-foreground">
                {(file.size / 1024).toFixed(1)} KB
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClear}
              className="ml-2"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
          {templateLinks.length > 0 && (
            <div className="flex flex-wrap justify-center gap-2">
              {templateLinks.map((template) => (
                <Button key={template.href} variant="outline" size="sm" asChild>
                  <a href={template.href} target="_blank" rel="noreferrer">
                    {template.label}
                  </a>
                </Button>
              ))}
            </div>
          )}
        </div>
      ) : (
        <label className="cursor-pointer flex flex-col items-center gap-3">
          {icon ?? <Upload className="h-10 w-10 text-muted-foreground" />}
          <div>
            <p className="text-sm font-medium text-foreground">{label}</p>
            <p className="text-xs text-muted-foreground mt-1">{description}</p>
            <p className="text-xs text-muted-foreground">
              Supports: {accept.toUpperCase()}
            </p>
          </div>
          {templateLinks.length > 0 && (
            <div className="flex flex-wrap justify-center gap-2">
              {templateLinks.map((template) => (
                <Button key={template.href} variant="outline" size="sm" asChild>
                  <a href={template.href} target="_blank" rel="noreferrer">
                    {template.label}
                  </a>
                </Button>
              ))}
            </div>
          )}
          <input
            type="file"
            accept={accept}
            className="hidden"
            onChange={handleChange}
            ref={inputRef}
          />
        </label>
      )}
    </div>
  );
}
