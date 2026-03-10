import { type TimetableCell } from "@/data/mockData";
import { buildLegend, DISPLAY_DAYS, getCellByPeriod, PERIOD_TEMPLATE } from "@/lib/timetableFormat";

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

export function TimetableGrid({ grid, header }: TimetableGridProps) {
  const legendRows = buildLegend(grid);

  return (
    <div className="overflow-x-auto">
      {header && (
        <div className="text-center mb-2 border border-border">
          {header.college && <h3 className="text-base font-semibold uppercase leading-tight border-b border-border py-1">{header.college}</h3>}
          <p className="text-sm font-semibold leading-tight border-b border-border py-0.5">(AUTONOMOUS)</p>
          {header.department && <p className="text-sm font-semibold leading-tight border-b border-border py-0.5">{header.department}</p>}
          <div className="text-sm font-semibold leading-tight border-b border-border py-0.5">
            {header.year && <span>ACADEMIC YEAR : {header.year}</span>}
            {header.semester && <span> {header.semester}</span>}
          </div>
          <div className="text-sm font-semibold leading-tight border-b border-border py-0.5">
            {header.section && <span>{header.section} TIME TABLE</span>}
          </div>
          <div className="grid grid-cols-2 text-xs font-semibold">
            <div className="text-left px-2 py-0.5 border-r border-border">
              {header.room && <span>Room No : {header.room}</span>}
            </div>
            <div className="text-right px-2 py-0.5">
              <span>With effect from : 24-11-2025</span>
            </div>
          </div>
        </div>
      )}

      <table className="timetable-grid rounded-none overflow-hidden">
        <thead>
          <tr>
            <th className="min-w-[40px]" rowSpan={2}>DAY</th>
            {PERIOD_TEMPLATE.map((slot, idx) => (
              <th key={`slot-num-${idx}`} className={`min-w-[90px] ${slot.period === "BREAK" ? "break-header" : slot.period === "LUNCH" ? "lunch-header" : ""}`}>
                {typeof slot.period === "number" ? slot.period : ""}
              </th>
            ))}
          </tr>
          <tr>
            {PERIOD_TEMPLATE.map((slot, idx) => (
              <th key={`slot-time-${idx}`} className={`text-[10px] ${slot.period === "BREAK" ? "break-header" : slot.period === "LUNCH" ? "lunch-header" : ""}`}>
                {slot.time}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {DISPLAY_DAYS.map((day, dayIdx) => (
            <tr key={day.full}>
              <td className="font-semibold text-[10px] whitespace-pre leading-[1.05]">{day.shortVertical}</td>

              {[1, 2].map((period) => {
                const cell = getCellByPeriod(grid, day.full, period);
                return (
                  <td key={`${day.full}-p-${period}`} className={cell?.isLab ? "lab-cell" : ""}>
                    <div className="font-semibold text-[11px] leading-tight">{cell?.subject ?? ""}</div>
                  </td>
                );
              })}

              {dayIdx === 0 && (
                <td rowSpan={DISPLAY_DAYS.length} className="break-cell font-semibold text-[18px] tracking-widest whitespace-pre leading-7">
                  {"B\nR\nE\nA\nK"}
                </td>
              )}

              {[3, 4].map((period) => {
                const cell = getCellByPeriod(grid, day.full, period);
                return (
                  <td key={`${day.full}-p-${period}`} className={cell?.isLab ? "lab-cell" : ""}>
                    <div className="font-semibold text-[11px] leading-tight">{cell?.subject ?? ""}</div>
                  </td>
                );
              })}

              {dayIdx === 0 && (
                <td rowSpan={DISPLAY_DAYS.length} className="lunch-cell font-semibold text-[18px] tracking-widest whitespace-pre leading-7">
                  {"L\nU\nN\nC\nH"}
                </td>
              )}

              {[5, 6, 7].map((period) => {
                const cell = getCellByPeriod(grid, day.full, period);
                return (
                  <td key={`${day.full}-p-${period}`} className={cell?.isLab ? "lab-cell" : ""}>
                    <div className="font-semibold text-[11px] leading-tight">{cell?.subject ?? ""}</div>
                  </td>
                );
              })}
            </tr>
          ))}

          {legendRows.length > 0 && (
            <>
              <tr>
                <td colSpan={10} className="bg-white p-0.5 border-b border-border"></td>
              </tr>
              {Array.from({ length: Math.ceil(legendRows.length / 2) }).map((_, rowIdx) => {
                const left = legendRows[rowIdx * 2];
                const right = legendRows[rowIdx * 2 + 1];
                return (
                  <tr key={`legend-${rowIdx}`}>
                    <td colSpan={5} className="text-left text-[11px] px-2 py-1">
                      {left ? <span><strong>{left.code}</strong> : {left.subject} : {left.faculty}</span> : ""}
                    </td>
                    <td colSpan={5} className="text-left text-[11px] px-2 py-1">
                      {right ? <span><strong>{right.code}</strong> : {right.subject} : {right.faculty}</span> : ""}
                    </td>
                  </tr>
                );
              })}
              <tr>
                <td colSpan={5} className="text-center font-semibold py-2">HEAD OF THE DEPARTMENT</td>
                <td colSpan={5} className="text-center font-semibold py-2">PRINCIPAL</td>
              </tr>
            </>
          )}
        </tbody>
      </table>
    </div>
  );
}
