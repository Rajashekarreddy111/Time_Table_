import { type TimetableCell } from "@/data/mockData";
import { buildLegend, DISPLAY_DAYS, getCellRoomLabel } from "@/lib/timetableFormat";

interface TimetableGridProps {
  grid: Record<string, (TimetableCell | null)[]>;
  header?: {
    college?: string;
    department?: string;
    year?: string;
    semester?: string;
    section?: string;
    room?: string;
    withEffectFrom?: string;
  };
  isRoomTimetable?: boolean;
  hideLegend?: boolean;
}

function getCellLabel(cell: TimetableCell | null | undefined): string {
  return cell?.subjectName ?? cell?.subject ?? "";
}

function areGridCellsEquivalent(
  left: TimetableCell | null | undefined,
  right: TimetableCell | null | undefined,
): boolean {
  if (!left || !right) return false;
  return (
    getCellLabel(left) === getCellLabel(right) &&
    (left.facultyName ?? left.faculty ?? "") ===
      (right.facultyName ?? right.faculty ?? "") &&
    Boolean(left.isLab) === Boolean(right.isLab) &&
    (left.classroom ?? "") === (right.classroom ?? "") &&
    (left.labRoom ?? "") === (right.labRoom ?? "") &&
    (left.fallbackLab ?? "") === (right.fallbackLab ?? "") &&
    (left.sharedSections ?? []).join(",") ===
      (right.sharedSections ?? []).join(",") &&
    (left.year ?? "") === (right.year ?? "") &&
    (left.section ?? "") === (right.section ?? "")
  );
}

export function TimetableGrid({ grid, header, isRoomTimetable, hideLegend }: TimetableGridProps) {
  const legendRows = buildLegend(grid);

  // Compute most common classroom for section timetables
  let mostCommonRoom = "";
  if (!isRoomTimetable) {
    const rooms: string[] = [];
    Object.values(grid).forEach((slots) => {
      slots.forEach((cell) => {
        if (cell && !cell.isLab && cell.classroom) {
          rooms.push(cell.classroom);
        }
      });
    });
    if (rooms.length > 0) {
      const counts: Record<string, number> = {};
      rooms.forEach((r) => {
        counts[r] = (counts[r] || 0) + 1;
      });
      mostCommonRoom = Object.keys(counts).reduce((a, b) => counts[a] > counts[b] ? a : b);
    }
  }

  const roomValue = isRoomTimetable ? header?.room : (mostCommonRoom || header?.room);

  // Helper functions to check if a day has break/lunch overlaps
  const dayHasBreakOverlap = (day: string) => {
    const dayCells = grid[day] ?? [];
    const p2 = dayCells[1];
    const p3 = dayCells[2];
    return p2 && p3 && p2.isLab && p3.isLab && areGridCellsEquivalent(p2, p3);
  };

  const dayHasLunchOverlap = (day: string) => {
    const dayCells = grid[day] ?? [];
    const p4 = dayCells[3];
    const p5 = dayCells[4];
    return p4 && p5 && p4.isLab && p5.isLab && areGridCellsEquivalent(p4, p5);
  };

  // Compute vertical spans for break and lunch columns
  const breakRowSpans = Array(DISPLAY_DAYS.length).fill(0);
  let breakStartIdx = -1;
  for (let i = 0; i < DISPLAY_DAYS.length; i++) {
    const day = DISPLAY_DAYS[i].full;
    if (dayHasBreakOverlap(day)) {
      breakStartIdx = -1;
    } else {
      if (breakStartIdx === -1) {
        breakStartIdx = i;
        breakRowSpans[i] = 1;
      } else {
        breakRowSpans[breakStartIdx]++;
      }
    }
  }

  const lunchRowSpans = Array(DISPLAY_DAYS.length).fill(0);
  let lunchStartIdx = -1;
  for (let i = 0; i < DISPLAY_DAYS.length; i++) {
    const day = DISPLAY_DAYS[i].full;
    if (dayHasLunchOverlap(day)) {
      lunchStartIdx = -1;
    } else {
      if (lunchStartIdx === -1) {
        lunchStartIdx = i;
        lunchRowSpans[i] = 1;
      } else {
        lunchRowSpans[lunchStartIdx]++;
      }
    }
  }

  const isBreakCovered = (d_idx: number) => {
    for (let i = 0; i < d_idx; i++) {
      if (breakRowSpans[i] > 0 && i + breakRowSpans[i] > d_idx) return true;
    }
    return false;
  };

  const isLunchCovered = (d_idx: number) => {
    for (let i = 0; i < d_idx; i++) {
      if (lunchRowSpans[i] > 0 && i + lunchRowSpans[i] > d_idx) return true;
    }
    return false;
  };

  type GridSlot =
    | { type: "period"; periodIdx: number; cell: TimetableCell | null }
    | { type: "interval"; label: "BREAK" | "LUNCH"; rowSpan: number };

  const renderDayRow = (day: string, d_idx: number) => {
    const dayCells = grid[day] ?? [];
    const slots: GridSlot[] = [
      { type: "period", periodIdx: 0, cell: dayCells[0] },
      { type: "period", periodIdx: 1, cell: dayCells[1] },
      { type: "interval", label: "BREAK", rowSpan: breakRowSpans[d_idx] },
      { type: "period", periodIdx: 2, cell: dayCells[2] },
      { type: "period", periodIdx: 3, cell: dayCells[3] },
      { type: "interval", label: "LUNCH", rowSpan: lunchRowSpans[d_idx] },
      { type: "period", periodIdx: 4, cell: dayCells[4] },
      { type: "period", periodIdx: 5, cell: dayCells[5] },
      { type: "period", periodIdx: 6, cell: dayCells[6] },
    ];

    const renderedCols: JSX.Element[] = [];
    let i = 0;
    while (i < slots.length) {
      const slot = slots[i];
      if (slot.type === "interval") {
        const covered = slot.label === "BREAK" ? isBreakCovered(d_idx) : isLunchCovered(d_idx);
        const overlaps = slot.label === "BREAK" ? dayHasBreakOverlap(day) : dayHasLunchOverlap(day);
        if (covered || overlaps) {
          i++;
          continue;
        }
        renderedCols.push(
          <td
            key={`interval-${slot.label}-${d_idx}`}
            rowSpan={slot.rowSpan}
            className={`${slot.label.toLowerCase()}-cell font-semibold text-[18px] tracking-widest whitespace-pre leading-7`}
          >
            {slot.label === "BREAK" ? "B\nR\nE\nA\nK" : "L\nU\nN\nC\nH"}
          </td>
        );
        i++;
      } else {
        let colSpan = 1;
        let nextIdx = i + 1;
        while (nextIdx < slots.length) {
          const nextSlot = slots[nextIdx];
          if (nextSlot.type === "interval") {
            const overlaps = nextSlot.label === "BREAK" ? dayHasBreakOverlap(day) : dayHasLunchOverlap(day);
            if (slot.cell?.isLab && overlaps) {
              colSpan++;
              nextIdx++;
            } else {
              break;
            }
          } else {
            if (areGridCellsEquivalent(slot.cell, nextSlot.cell)) {
              colSpan++;
              nextIdx++;
            } else {
              break;
            }
          }
        }

        renderedCols.push(
          <td
            key={`period-${d_idx}-${slot.periodIdx}`}
            colSpan={colSpan}
            className={slot.cell?.isLab ? "lab-cell" : ""}
          >
            <div className="flex flex-col gap-0.5 items-center justify-center">
              <div className="font-semibold text-[11px] leading-tight text-foreground">
                {slot.cell?.subjectName ?? slot.cell?.subject ?? ""}
              </div>
              {isRoomTimetable && slot.cell?.section ? (
                <div className="font-normal text-[10px] text-muted-foreground leading-tight">
                  {slot.cell.year ? `${slot.cell.year.replace(" Year", "")} - ` : ""}{slot.cell.section}
                </div>
              ) : getCellRoomLabel(slot.cell) ? (
                <div className="font-normal text-[10px] text-muted-foreground leading-tight">
                  ({getCellRoomLabel(slot.cell)})
                </div>
              ) : null}
            </div>
          </td>
        );
        i = nextIdx;
      }
    }

    return (
      <tr key={day}>
        <td className="font-semibold text-[10px] whitespace-pre leading-[1.05]">
          {DISPLAY_DAYS.find((d) => d.full === day)?.shortVertical}
        </td>
        {renderedCols}
      </tr>
    );
  };

  return (
    <div className="overflow-x-auto">
      {header && (
        <div className="timetable-sheet-frame text-center mb-2 border">
          {header.college && (
            <h3 className="text-base font-semibold uppercase leading-tight border-b py-1">
              {header.college}
            </h3>
          )}
          <p className="text-sm font-semibold leading-tight border-b py-0.5">
            (AUTONOMOUS)
          </p>
          {header.department && (
            <p className="text-sm font-semibold leading-tight border-b py-0.5">
              {header.department}
            </p>
          )}
          <div className="text-sm font-semibold leading-tight border-b py-0.5">
            {header.year && <span>ACADEMIC YEAR : {header.year}</span>}
            {header.semester && <span> {header.semester}</span>}
          </div>
          <div className="text-sm font-semibold leading-tight border-b py-0.5">
            {header.section && <span>{header.section} TIME TABLE</span>}
          </div>
          <div className="grid grid-cols-2 text-xs font-semibold text-center">
            <div className="px-2 py-0.5 border-r">
              <span>Room No : {roomValue ?? ""}</span>
            </div>
            <div className="px-2 py-0.5">
              <span>With effect from : {header.withEffectFrom ?? ""}</span>
            </div>
          </div>
        </div>
      )}

      <table className="timetable-grid rounded-none overflow-hidden">
        <thead>
          <tr>
            <th className="min-w-[40px]" rowSpan={2}>
              DAY
            </th>
            <th className="min-w-[90px]">1</th>
            <th className="min-w-[90px]">2</th>
            <th className="min-w-[90px] break-header"></th>
            <th className="min-w-[90px]">3</th>
            <th className="min-w-[90px]">4</th>
            <th className="min-w-[90px] lunch-header"></th>
            <th className="min-w-[90px]">5</th>
            <th className="min-w-[90px]">6</th>
            <th className="min-w-[90px]">7</th>
          </tr>
          <tr>
            <th className="text-[10px]">9.10-10.00</th>
            <th className="text-[10px]">10.00-10.50</th>
            <th className="text-[10px] break-header">10.50-11.00</th>
            <th className="text-[10px]">11.00-11.50</th>
            <th className="text-[10px]">11.50-12.40</th>
            <th className="text-[10px] lunch-header">12.40-1.30</th>
            <th className="text-[10px]">1.30-2.20</th>
            <th className="text-[10px]">2.20-3.10</th>
            <th className="text-[10px]">3.10-4.00</th>
          </tr>
        </thead>
        <tbody>
          {DISPLAY_DAYS.map((day, idx) => renderDayRow(day.full, idx))}

          {!hideLegend && legendRows.length > 0 && (
            <>
              <tr>
                <td
                  colSpan={10}
                  className="bg-white p-0.5 border-b border-border"
                ></td>
              </tr>
              {Array.from({ length: Math.ceil(legendRows.length / 2) }).map(
                (_, rowIdx) => {
                  const left = legendRows[rowIdx * 2];
                  const right = legendRows[rowIdx * 2 + 1];
                  return (
                    <tr key={`legend-${rowIdx}`}>
                      <td
                        colSpan={5}
                        className="text-left text-[11px] px-2 py-1 border-none bg-card"
                      >
                        {left ? (
                          <span>
                            {left.subject} : {left.faculty}
                          </span>
                        ) : (
                          ""
                        )}
                      </td>
                      <td
                        colSpan={5}
                        className="text-left text-[11px] px-2 py-1 border-none bg-card"
                      >
                        {right ? (
                          <span>
                            {right.subject} : {right.faculty}
                          </span>
                        ) : (
                          ""
                        )}
                      </td>
                    </tr>
                  );
                },
              )}
              <tr>
                <td colSpan={5} className="text-center font-semibold py-2 border-none bg-card">
                  HEAD OF THE DEPARTMENT
                </td>
                <td colSpan={5} className="text-center font-semibold py-2 border-none bg-card">
                  PRINCIPAL
                </td>
              </tr>
            </>
          )}
        </tbody>
      </table>
    </div>
  );
}
