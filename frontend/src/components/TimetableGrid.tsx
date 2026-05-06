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

  const renderDayRow = (day: string, rowIndex: number) => {
    const dayCells = grid[day] ?? [];
    const cells: JSX.Element[] = [
      <td
        key={`${day}-label`}
        className="font-semibold text-[10px] whitespace-pre leading-[1.05]"
      >
        {DISPLAY_DAYS.find((d) => d.full === day)?.shortVertical}
      </td>,
    ];

    // Helper function to render a cell or merged cells
    const renderPeriodCells = (startPeriod: number, endPeriod: number) => {
      const periodCells = [];
      let currentGroup: {
        cell: TimetableCell | null;
        start: number;
        count: number;
      } | null = null;

      for (let i = startPeriod; i <= endPeriod; i++) {
        const cell = dayCells[i];
        const cellLabel = getCellLabel(cell);

        if (currentGroup && areGridCellsEquivalent(currentGroup.cell, cell)) {
          // Extend current group
          currentGroup.count++;
        } else {
          // Render previous group if exists
          if (currentGroup) {
            periodCells.push(
              <td
                key={`${day}-period-${currentGroup.start + 1}-${currentGroup.start + currentGroup.count}`}
                colSpan={currentGroup.count}
                className={currentGroup.cell?.isLab ? "lab-cell" : ""}
              >
                <div className="flex flex-col gap-0.5 items-center justify-center">
                  <div className="font-semibold text-[11px] leading-tight text-foreground">
                    {currentGroup.cell?.subjectName ?? currentGroup.cell?.subject ?? ""}
                  </div>
                  {isRoomTimetable && currentGroup.cell?.section ? (
                    <div className="font-normal text-[10px] text-muted-foreground leading-tight">
                      {currentGroup.cell.year ? `${currentGroup.cell.year.replace(" Year", "")} - ` : ""}{currentGroup.cell.section}
                    </div>
                  ) : getCellRoomLabel(currentGroup.cell) ? (
                    <div className="font-normal text-[10px] text-muted-foreground leading-tight">
                      ({getCellRoomLabel(currentGroup.cell)})
                    </div>
                  ) : null}
                </div>
              </td>,
            );
          }
          // Start new group
          currentGroup = { cell, start: i, count: 1 };
        }
      }

      // Render last group
      if (currentGroup) {
        periodCells.push(
          <td
            key={`${day}-period-${currentGroup.start + 1}-${currentGroup.start + currentGroup.count}`}
            colSpan={currentGroup.count}
            className={currentGroup.cell?.isLab ? "lab-cell" : ""}
          >
            <div className="flex flex-col gap-0.5 items-center justify-center">
              <div className="font-semibold text-[11px] leading-tight text-foreground">
                {currentGroup.cell?.subjectName ?? currentGroup.cell?.subject ?? ""}
              </div>
              {isRoomTimetable && currentGroup.cell?.section ? (
                <div className="font-normal text-[10px] text-muted-foreground leading-tight">
                  {currentGroup.cell.year ? `${currentGroup.cell.year.replace(" Year", "")} - ` : ""}{currentGroup.cell.section}
                </div>
              ) : getCellRoomLabel(currentGroup.cell) ? (
                <div className="font-normal text-[10px] text-muted-foreground leading-tight">
                  ({getCellRoomLabel(currentGroup.cell)})
                </div>
              ) : null}
            </div>
          </td>,
        );
      }

      return periodCells;
    };

    // Periods 1-2 (before break)
    cells.push(...renderPeriodCells(0, 1));

    // Break cell (only on first row)
    if (rowIndex === 0) {
      cells.push(
        <td
          key="break-cell"
          rowSpan={DISPLAY_DAYS.length}
          className="break-cell font-semibold text-[18px] tracking-widest whitespace-pre leading-7"
        >
          {"B\nR\nE\nA\nK"}
        </td>,
      );
    }

    // Periods 3-4 (after break, before lunch)
    cells.push(...renderPeriodCells(2, 3));

    // Lunch cell (only on first row)
    if (rowIndex === 0) {
      cells.push(
        <td
          key="lunch-cell"
          rowSpan={DISPLAY_DAYS.length}
          className="lunch-cell font-semibold text-[18px] tracking-widest whitespace-pre leading-7"
        >
          {"L\nU\nN\nC\nH"}
        </td>,
      );
    }

    // Periods 5-7 (after lunch)
    cells.push(...renderPeriodCells(4, 6));

    return <tr key={day}>{cells}</tr>;
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
              {header.room && <span>Room No : {header.room}</span>}
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
                        className="text-left text-[11px] px-2 py-1"
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
                        className="text-left text-[11px] px-2 py-1"
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
                <td colSpan={5} className="text-center font-semibold py-2">
                  HEAD OF THE DEPARTMENT
                </td>
                <td colSpan={5} className="text-center font-semibold py-2">
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
