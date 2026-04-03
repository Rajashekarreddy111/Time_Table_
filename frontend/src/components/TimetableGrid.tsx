import { type TimetableCell } from "@/data/mockData";
import {
  buildLegend,
  DISPLAY_DAYS,
  getCellByPeriod,
  PERIOD_TEMPLATE,
} from "@/lib/timetableFormat";

interface TimetableGridProps {
  grid: Record<string, (TimetableCell | null)[]>;
  header?: {
    college?: string;
    department?: string;
    year?: string;
    semester?: string;
    section?: string;
    room?: string;
  };
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
    (left.sharedSections ?? []).join(",") ===
      (right.sharedSections ?? []).join(",")
  );
}

type Run = {
  start: number;
  end: number;
  cell: TimetableCell | null | undefined;
};

function buildDayRuns(
  day: string,
  grid: Record<string, (TimetableCell | null)[]>,
): Run[] {
  const runs: Run[] = [];
  let period = 1;

  while (period <= 7) {
    const current = getCellByPeriod(grid, day, period);
    let end = period;

    while (end < 7) {
      const next = getCellByPeriod(grid, day, end + 1);
      if (!areGridCellsEquivalent(current, next)) break;
      if ((end === 2 || end === 4) && !Boolean(current?.isLab)) break;
      end += 1;
    }

    runs.push({ start: period, end, cell: current });
    period = end + 1;
  }

  return runs;
}

export function TimetableGrid({ grid, header }: TimetableGridProps) {
  const legendRows = buildLegend(grid);

  const renderDayRow = (day: string) => {
    const runs = buildDayRuns(day, grid);
    const cells: JSX.Element[] = [
      <td
        key={`${day}-label`}
        className="font-semibold text-[10px] whitespace-pre leading-[1.05]"
      >
        {DISPLAY_DAYS.find((d) => d.full === day)?.shortVertical}
      </td>,
    ];

    runs.forEach((run, index) => {
      const containsBreak = run.start <= 2 && run.end >= 3;
      const containsLunch = run.start <= 4 && run.end >= 5;
      const span =
        run.end -
        run.start +
        1 +
        (containsBreak ? 1 : 0) +
        (containsLunch ? 1 : 0);

      cells.push(
        <td
          key={`${day}-run-${run.start}-${run.end}`}
          colSpan={span}
          className={run.cell?.isLab ? "lab-cell" : ""}
        >
          <div className="font-semibold text-[11px] leading-tight">
            {getCellLabel(run.cell)}
          </div>
        </td>,
      );

      if (run.end === 2 && index < runs.length - 1) {
        cells.push(
          <td
            key={`${day}-break-${index}`}
            className="break-cell font-semibold text-[10px] tracking-widest whitespace-pre leading-7"
          >
            {"B\nR\nE\nA\nK"}
          </td>,
        );
      }

      if (run.end === 4 && index < runs.length - 1) {
        cells.push(
          <td
            key={`${day}-lunch-${index}`}
            className="lunch-cell font-semibold text-[10px] tracking-widest whitespace-pre leading-7"
          >
            {"L\nU\nN\nC\nH"}
          </td>,
        );
      }
    });

    return <tr key={day}>{cells}</tr>;
  };

  return (
    <div className="overflow-x-auto">
      {header && (
        <div className="text-center mb-2 border border-border">
          {header.college && (
            <h3 className="text-base font-semibold uppercase leading-tight border-b border-border py-1">
              {header.college}
            </h3>
          )}
          <p className="text-sm font-semibold leading-tight border-b border-border py-0.5">
            (AUTONOMOUS)
          </p>
          {header.department && (
            <p className="text-sm font-semibold leading-tight border-b border-border py-0.5">
              {header.department}
            </p>
          )}
          <div className="text-sm font-semibold leading-tight border-b border-border py-0.5">
            {header.year && <span>ACADEMIC YEAR : {header.year}</span>}
            {header.semester && <span> {header.semester}</span>}
          </div>
          <div className="text-sm font-semibold leading-tight border-b border-border py-0.5">
            {header.section && <span>{header.section} TIME TABLE</span>}
          </div>
          <div className="grid grid-cols-2 text-xs font-semibold text-center">
            <div className="px-2 py-0.5 border-r border-border">
              {header.room && <span>Room No : {header.room}</span>}
            </div>
            <div className="px-2 py-0.5">
              <span>With effect from :</span>
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
            {PERIOD_TEMPLATE.map((slot, idx) => (
              <th
                key={`slot-num-${idx}`}
                className={`min-w-[90px] ${slot.period === "BREAK" ? "break-header" : slot.period === "LUNCH" ? "lunch-header" : ""}`}
              >
                {typeof slot.period === "number" ? slot.period : ""}
              </th>
            ))}
          </tr>
          <tr>
            {PERIOD_TEMPLATE.map((slot, idx) => (
              <th
                key={`slot-time-${idx}`}
                className={`text-[10px] ${slot.period === "BREAK" ? "break-header" : slot.period === "LUNCH" ? "lunch-header" : ""}`}
              >
                {slot.time}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {DISPLAY_DAYS.map((day) => renderDayRow(day.full))}

          {legendRows.length > 0 && (
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
