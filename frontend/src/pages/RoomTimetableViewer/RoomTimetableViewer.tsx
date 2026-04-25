import { useEffect, useMemo, useState } from "react";
import { Download, Printer } from "lucide-react";
import { DashboardLayout } from "@/components/DashboardLayout";
import { TimetableGrid } from "@/components/TimetableGrid";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { type RoomTimetable } from "@/data/mockData";
import { toast } from "sonner";
import {
  listTimetables,
  type TimetableRecord,
  type TimetableMetadata,
  getAllRoomsWorkbook,
} from "@/services/apiClient";
import {
  ACADEMIC_METADATA,
  formatSemesterLabel,
  formatWithEffectFrom,
  toAcademicYear,
} from "@/lib/academicMetadata";
import { useSearchParams } from "react-router-dom";

function getResolvedMetadata(metadata?: TimetableMetadata) {
  return {
    academicYear: metadata?.academicYear ?? toAcademicYear(new Date()),
    semester: formatSemesterLabel(metadata?.semester ?? 2),
    withEffectFrom: formatWithEffectFrom(metadata?.withEffectFrom),
  };
}

function downloadGeneratedWorkbook(file: { contentBase64: string; contentType: string; fileName: string }) {
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

function extractRoomTimetables(records: TimetableRecord[]): RoomTimetable[] {
  const roomGrids: Record<string, Record<string, (TimetableCell | null)[]>> = {};

  for (const record of records) {
    if (record.roomGrids) {
      for (const [room, grid] of Object.entries(record.roomGrids)) {
        if (!roomGrids[room]) {
          roomGrids[room] = {};
        }
        for (const [day, slots] of Object.entries(grid)) {
          if (!roomGrids[room][day]) {
            roomGrids[room][day] = Array(slots.length).fill(null);
          }
          slots.forEach((slot, index) => {
            if (slot) {
              const current = roomGrids[room][day][index];
              if (current) {
                const years = new Set((current.year || "").split(", "));
                if (slot.year) years.add(slot.year.replace(" Year", ""));
                
                const sections = new Set((current.section || "").split(", "));
                if (slot.section) {
                  slot.section.split(", ").forEach(s => sections.add(s));
                }

                roomGrids[room][day][index] = {
                  ...current,
                  year: Array.from(years).filter(Boolean).join(", "),
                  section: Array.from(sections).filter(Boolean).join(", "),
                };
              } else {
                roomGrids[room][day][index] = { 
                  ...slot, 
                  year: (slot.year || "").replace(" Year", "") 
                };
              }
            }
          });
        }
      }
    }
  }

  const items: RoomTimetable[] = [];
  for (const [room, grid] of Object.entries(roomGrids)) {
    const hasData = Object.values(grid).some(
      (daySlots) =>
        Array.isArray(daySlots) &&
        daySlots.some((slot) => slot !== null && slot !== undefined),
    );
    if (hasData) {
      items.push({ section: room, grid });
    }
  }
  return items;
}

const RoomTimetableViewer = () => {
  const [searchParams] = useSearchParams();
  const timetableId = searchParams.get("timetableId");

  const [records, setRecords] = useState<TimetableRecord[]>([]);
  const [selectedRoom, setSelectedRoom] = useState<string>("");

  useEffect(() => {
    if (timetableId && records.length > 0) {
      const target = records.find((r) => r.id === timetableId);
      if (target && target.roomGrids) {
        const rooms = Object.keys(target.roomGrids);
        if (rooms.length > 0) setSelectedRoom(rooms[0]);
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

  const validRecords = useMemo(() => records, [records]);
  const allTimetables = useMemo(() => extractRoomTimetables(validRecords), [validRecords]);
  const availableRooms = useMemo(
    () => Array.from(new Set(allTimetables.map((item) => item.section))),
    [allTimetables],
  );

  useEffect(() => {
    if (availableRooms.length > 0 && !availableRooms.includes(selectedRoom)) {
      setSelectedRoom(availableRooms[0]);
    }
  }, [availableRooms, selectedRoom]);

  const timetable = allTimetables.find((t) => t.section === selectedRoom);

  const activeRecord = validRecords.length > 0 ? validRecords[0] : null;
  const resolvedMetadata = getResolvedMetadata(activeRecord?.timetableMetadata);

  const handleExportExcel = async () => {
    if (!selectedRoom) return;
    try {
      const workbook = await getAllRoomsWorkbook(selectedRoom);
      downloadGeneratedWorkbook(workbook);
      toast.success("Room timetable downloaded.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to download room timetable");
    }
  };

  const handleExportAllTimetables = async () => {
    try {
      const workbook = await getAllRoomsWorkbook();
      downloadGeneratedWorkbook(workbook);
      toast.success("All room timetables exported.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to download all timetables");
    }
  };

  const handlePrint = () => window.print();

  return (
    <DashboardLayout>
      <section className="hero-shell mb-8">
        <div className="relative z-10 grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_340px] xl:items-end">
          <div className="space-y-4">
            <div className="hero-chip">Room Timetable Viewer</div>
            <div className="space-y-2">
              <h1 className="text-4xl font-bold tracking-tight text-foreground">View Room Timetables</h1>
              <p className="max-w-2xl text-sm leading-7 text-muted-foreground">
                View and export timetables grouped by classrooms and labs.
              </p>
            </div>
          </div>
          <div className="panel-card">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Live Summary</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-1">
              <div className="panel-muted">
                <p className="text-2xl font-bold text-foreground">{availableRooms.length}</p>
                <p className="mt-1 text-xs text-muted-foreground">Rooms available</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {availableRooms.length > 1 && (
        <div className="panel-card mb-6 print:hidden">
          <h3 className="text-xs font-semibold text-primary uppercase tracking-wider mb-3">Available Rooms</h3>
          <div className="flex flex-wrap gap-2">
            {availableRooms.map((room) => (
              <Button
                key={room}
                variant={selectedRoom === room ? "default" : "outline"}
                size="sm"
                className="h-8 text-xs"
                onClick={() => setSelectedRoom(room)}
              >
                {room}
              </Button>
            ))}
          </div>
        </div>
      )}

      <div className="panel-card mb-6 print:hidden">
        <div className="flex flex-wrap items-end gap-4">
          <div className="w-64">
            <Label className="text-xs text-muted-foreground">Select Room</Label>
            <Select value={selectedRoom} onValueChange={setSelectedRoom}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {availableRooms.map((room) => (
                  <SelectItem key={room} value={room}>{room}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="flex gap-2 ml-auto">
            <Button variant="outline" size="sm" onClick={handleExportExcel} className="gap-1.5">
              <Download className="h-3.5 w-3.5" /> Download Excel
            </Button>
            <Button variant="outline" size="sm" onClick={handleExportAllTimetables} className="gap-1.5">
              <Download className="h-3.5 w-3.5" /> Download All Classrooms
            </Button>
            <Button variant="outline" size="sm" onClick={handlePrint} className="gap-1.5">
              <Printer className="h-3.5 w-3.5" /> Print
            </Button>
          </div>
        </div>
      </div>

      <div className="panel-card print:shadow-none print:p-0">
        {timetable ? (
          <div className="space-y-4">
            <TimetableGrid
              grid={timetable.grid}
              isRoomTimetable={true}
              hideLegend={true}
              header={{
                college: ACADEMIC_METADATA.COLLEGE_NAME,
                department: ACADEMIC_METADATA.DEPARTMENT_NAME,
                year: resolvedMetadata.academicYear,
                semester: resolvedMetadata.semester,
                section: `ROOM TIMETABLE: ${selectedRoom}`,
                room: selectedRoom,
                withEffectFrom: resolvedMetadata.withEffectFrom,
              }}
            />
          </div>
        ) : (
          <div className="text-center py-16">
            <p className="text-muted-foreground">No room timetable is available.</p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default RoomTimetableViewer;
