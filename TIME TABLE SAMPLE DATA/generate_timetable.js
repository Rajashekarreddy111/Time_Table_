#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const XLSX = require('xlsx');

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const DAY_INDEX = Object.fromEntries(DAYS.map((d, i) => [d.toLowerCase(), i]));
const PERIODS = [1, 2, 3, 4, 5, 6, 7];
const TOTAL_WEEKLY_HOURS = 42;

function num(v) {
  if (v === null || v === undefined || v === '') return 0;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function normSection(section) {
  return String(section || '').trim().toUpperCase();
}

function sectionKey(year, section) {
  return `Y${Number(year)}-${normSection(section)}`;
}

function parseIntList(value) {
  if (value === null || value === undefined) return [];
  return String(value)
    .split(',')
    .map((x) => x.trim())
    .filter((x) => x.length > 0)
    .map((x) => Number(x))
    .filter((x) => Number.isFinite(x));
}

function parseFacultyIds(value) {
  const many = parseIntList(value);
  if (many.length > 0) return [...new Set(many)];
  const single = num(value);
  return single ? [single] : [];
}

function slotKey(day, period) {
  return `${day + 1}-${period}`;
}

function readWorkbookRows(filePath) {
  const wb = XLSX.readFile(filePath);
  const sheet = wb.Sheets[wb.SheetNames[0]];
  return XLSX.utils.sheet_to_json(sheet, { defval: null });
}

function readWorkbookAoA(filePath) {
  const wb = XLSX.readFile(filePath);
  const sheet = wb.Sheets[wb.SheetNames[0]];
  return XLSX.utils.sheet_to_json(sheet, { header: 1, defval: null });
}

function parseMainConfig(mainConfigPath) {
  const aoa = readWorkbookAoA(mainConfigPath);
  if (aoa.length < 3) {
    throw new Error('Main config has insufficient rows.');
  }

  const header = aoa[0];
  const sectionCols = [];
  for (let c = 2; c < header.length; c += 3) {
    const section = normSection(header[c]);
    if (!section) continue;
    sectionCols.push({ section, hoursCol: c, facultyCol: c + 1, contCol: c + 2 });
  }

  if (sectionCols.length === 0) {
    throw new Error('No sections found in main config header.');
  }

  const sectionMeta = new Map();
  const sectionLookup = new Map();
  const subjectsBySection = new Map();

  for (let r = 2; r < aoa.length; r += 1) {
    const row = aoa[r];
    const year = num(row[0]);
    const subjectId = num(row[1]);
    if (!year || !subjectId) continue;

    for (const sc of sectionCols) {
      const hours = num(row[sc.hoursCol]);
      const facultyIds = parseFacultyIds(row[sc.facultyCol]);
      const continuous = num(row[sc.contCol]) || 1;

      if (hours <= 0) continue;
      if (facultyIds.length === 0) {
        throw new Error(`Missing faculty ID for section ${sc.section}, subject ${subjectId}.`);
      }

      const secKey = sectionKey(year, sc.section);
      if (!subjectsBySection.has(secKey)) subjectsBySection.set(secKey, new Map());
      sectionMeta.set(secKey, { year, section: sc.section });
      sectionLookup.set(`${year}:${sc.section}`, secKey);

      subjectsBySection.get(secKey).set(subjectId, {
        subjectId,
        facultyIds,
        totalHours: hours,
        remainingHours: hours,
        preferredContinuous: Math.max(1, continuous),
      });
    }
  }

  for (const [secKey, subjMap] of subjectsBySection.entries()) {
    const sum = [...subjMap.values()].reduce((acc, s) => acc + s.totalHours, 0);
    if (sum !== TOTAL_WEEKLY_HOURS) {
      const meta = sectionMeta.get(secKey);
      throw new Error(
        `Section ${meta.section} (Year ${meta.year}) totals ${sum} hours (expected ${TOTAL_WEEKLY_HOURS}).`
      );
    }
  }

  return { sectionCols, sectionMeta, sectionLookup, subjectsBySection };
}

function parseFacultyAvailability(filePath) {
  const rows = readWorkbookRows(filePath);
  const availability = new Map();

  for (const row of rows) {
    const facultyId = num(row['Faculty ID'] ?? row['faculty id'] ?? row['FACULTY ID']);
    if (!facultyId) continue;
    const allowed = new Set();
    for (const day of DAYS) {
      const raw = row[day] ?? row[day.toLowerCase()] ?? row[day.toUpperCase()];
      const periods = parseIntList(raw);
      const dayIdx = DAY_INDEX[day.toLowerCase()];
      for (const p of periods) {
        if (p >= 1 && p <= 7) allowed.add(slotKey(dayIdx, p));
      }
    }
    availability.set(facultyId, allowed);
  }

  return availability;
}

function parseLabs(filePath) {
  const rows = readWorkbookRows(filePath);
  return rows
    .map((r) => ({
      year: num(r.YEAR ?? r.year),
      section: normSection(r.SECTION ?? r.section),
      subjectId: num(r['SUBJECT ID'] ?? r.subject ?? r.SUBJECT),
      day: num(r.DAY ?? r.day),
      periods: parseIntList(r.HOURS ?? r.hours),
      venue: r.VENUE ?? r.venue ?? null,
    }))
    .filter((x) => x.year && x.section && x.subjectId && x.day && x.periods.length > 0);
}

function parseShared(filePath) {
  if (!fs.existsSync(filePath)) return [];
  const rows = readWorkbookRows(filePath);
  return rows
    .map((r) => {
      const yearRaw = r.year ?? r.YEAR;
      const sectionsRaw = r.sections ?? r.SECTIONS;
      const subject = num(r.subject ?? r.SUBJECT ?? r['subject id'] ?? r['SUBJECT ID']);
      let year = num(yearRaw);
      if (!year && yearRaw != null) {
        const match = String(yearRaw).match(/\d+/);
        if (match) year = Number(match[0]);
      }
      return {
        year,
        sections: String(sectionsRaw || '')
          .split(',')
          .map((s) => normSection(s))
          .filter(Boolean),
        subjectId: subject,
      };
    })
    .filter((x) => x.year && x.sections.length >= 2 && x.subjectId);
}

function parseIdMap(filePath, idKeyCandidates, nameKeyCandidates) {
  if (!fs.existsSync(filePath)) return new Map();
  const rows = readWorkbookRows(filePath);
  const map = new Map();
  for (const row of rows) {
    let id = 0;
    let name = null;
    for (const k of idKeyCandidates) {
      id = id || num(row[k]);
    }
    for (const k of nameKeyCandidates) {
      name = name || row[k];
    }
    if (id && name) map.set(id, String(name).trim());
  }
  return map;
}

function parseContinuousRules(filePath) {
  if (!fs.existsSync(filePath)) return new Map();
  const rows = readWorkbookRows(filePath);
  const map = new Map();
  for (const row of rows) {
    const subjectId = num(row.SUBJECT_ID ?? row.subject_id ?? row.subject ?? row.SUBJECT);
    const ch = num(
      row.COMPULSORY_CONTINUOUS_HOURS ?? row.compulsory_continuous_hours ?? row.continuous
    );
    if (subjectId && ch > 1) map.set(subjectId, ch);
  }
  return map;
}

function createEmptyGrid() {
  return Array.from({ length: 6 }, () => Array.from({ length: 7 }, () => null));
}

function isFacultyAvailable(availability, facultyId, dayIdx, period) {
  const allowed = availability.get(facultyId);
  if (!allowed) return false;
  return allowed.has(slotKey(dayIdx, period));
}

function assignCell(state, assignment) {
  const { sections, facultyId, dayIdx, period, subjectId, type } = assignment;

  for (const section of sections) {
    if (state.sectionGrid.get(section)[dayIdx][period - 1] !== null) return false;
  }
  if (state.facultyGrid.get(facultyId)[dayIdx][period - 1] !== null) return false;
  if (!isFacultyAvailable(state.availability, facultyId, dayIdx, period)) return false;

  for (const section of sections) {
    state.sectionGrid.get(section)[dayIdx][period - 1] = {
      subjectId,
      facultyId,
      type,
      sharedSections: sections.length > 1 ? sections.join(',') : null,
    };
    state.sectionDayLoad.get(section)[dayIdx] += 1;
  }

  state.facultyGrid.get(facultyId)[dayIdx][period - 1] = {
    subjectId,
    sections: sections.slice(),
    type,
  };

  return true;
}

function unassignCell(state, assignment) {
  const { sections, facultyId, dayIdx, period } = assignment;
  for (const section of sections) {
    state.sectionGrid.get(section)[dayIdx][period - 1] = null;
    state.sectionDayLoad.get(section)[dayIdx] -= 1;
  }
  state.facultyGrid.get(facultyId)[dayIdx][period - 1] = null;
}

function buildState(config, availability) {
  const sections = [...config.subjectsBySection.keys()].sort();
  const facultyIds = new Set();
  for (const subjMap of config.subjectsBySection.values()) {
    for (const s of subjMap.values()) {
      for (const fid of s.facultyIds) facultyIds.add(fid);
    }
  }

  const sectionGrid = new Map();
  const sectionDayLoad = new Map();
  for (const section of sections) {
    sectionGrid.set(section, createEmptyGrid());
    sectionDayLoad.set(section, Array.from({ length: 6 }, () => 0));
  }

  const facultyGrid = new Map();
  for (const fid of facultyIds) {
    facultyGrid.set(fid, createEmptyGrid());
  }

  return {
    sections,
    sectionGrid,
    facultyGrid,
    sectionDayLoad,
    availability,
    sharedPlacements: [],
  };
}

function validateAvailabilityFeasibility(config, availability, sharedRows) {
  const facultyLoad = new Map();
  for (const [section, subjMap] of config.subjectsBySection.entries()) {
    for (const subject of subjMap.values()) {
      if (subject.facultyIds.length === 1) {
        const fid = subject.facultyIds[0];
        facultyLoad.set(fid, (facultyLoad.get(fid) || 0) + subject.totalHours);
      }
    }
  }

  for (const shared of sharedRows) {
    const sections = shared.sections
      .map((s) => config.sectionLookup.get(`${shared.year}:${s}`))
      .filter((s) => s && config.subjectsBySection.has(s));
    if (sections.length < 2) continue;

    const first = config.subjectsBySection.get(sections[0]).get(shared.subjectId);
    if (!first || first.facultyIds.length !== 1) continue;

    let valid = true;
    for (let i = 1; i < sections.length; i += 1) {
      const cur = config.subjectsBySection.get(sections[i]).get(shared.subjectId);
      if (
        !cur ||
        cur.facultyIds.length !== 1 ||
        cur.facultyIds[0] !== first.facultyIds[0] ||
        cur.totalHours !== first.totalHours
      ) {
        valid = false;
        break;
      }
    }
    if (valid) {
      const reduction = first.totalHours * (sections.length - 1);
      const fid = first.facultyIds[0];
      facultyLoad.set(fid, (facultyLoad.get(fid) || 0) - reduction);
    }
  }

  for (const [facultyId, load] of facultyLoad.entries()) {
    const available = availability.get(facultyId);
    const cap = available ? available.size : 0;
    if (load > cap) {
      throw new Error(
        `Faculty ${facultyId} requires ${load} hours but has only ${cap} available slots.`
      );
    }
  }
}

function allocateLabs(config, state, labs) {
  for (const lab of labs) {
    const { section, year, subjectId, day, periods } = lab;
    const secKey = config.sectionLookup.get(`${year}:${section}`);
    if (!secKey || !config.subjectsBySection.has(secKey)) continue;

    const subject = config.subjectsBySection.get(secKey).get(subjectId);
    if (!subject) {
      throw new Error(`Lab subject ${subjectId} not found in main config for section ${section} (Year ${year}).`);
    }

    const dayIdx = day - 1;
    if (dayIdx < 0 || dayIdx >= 6) {
      throw new Error(`Invalid lab day ${day} for section ${section}.`);
    }

    const viableFaculty = subject.facultyIds.filter((fid) =>
      periods.every((p) =>
        canPlaceBlock(
          state,
          { sections: [secKey], facultyOptions: [fid] },
          dayIdx,
          p,
          1,
          fid
        )
      )
    );
    if (viableFaculty.length === 0) {
      throw new Error(
        `Cannot place fixed lab for section ${section} (Year ${year}), subject ${subjectId} due to faculty availability/conflict.`
      );
    }

    const chosenFaculty = viableFaculty[0];
    for (const p of periods) {
      const ok = assignCell(state, {
        sections: [secKey],
        facultyId: chosenFaculty,
        dayIdx,
        period: p,
        subjectId,
        type: 'LAB',
      });
      if (!ok) {
        throw new Error(
          `Cannot place fixed lab for section ${section} (Year ${year}), subject ${subjectId} on day ${day}, period ${p}.`
        );
      }
      subject.remainingHours -= 1;
      if (subject.remainingHours < 0) {
        throw new Error(
          `Lab hours exceed configured hours for section ${section} (Year ${year}), subject ${subjectId}.`
        );
      }
    }
  }
}

function buildTasks(config, sharedRows, compulsoryContinuous) {
  const tasks = [];
  const sharedTaskKeys = new Set();

  for (const shared of sharedRows) {
    const sections = shared.sections
      .map((s) => config.sectionLookup.get(`${shared.year}:${s}`))
      .filter((s) => s && config.subjectsBySection.has(s));
    if (sections.length < 2) continue;

    const base = config.subjectsBySection.get(sections[0]).get(shared.subjectId);
    if (!base) {
      throw new Error(`Shared class subject ${shared.subjectId} missing for section ${sections[0]}.`);
    }

    for (let i = 1; i < sections.length; i += 1) {
      const cur = config.subjectsBySection.get(sections[i]).get(shared.subjectId);
      if (!cur) {
        throw new Error(`Shared class subject ${shared.subjectId} missing for section ${sections[i]}.`);
      }
      if (cur.remainingHours !== base.remainingHours) {
        throw new Error(
          `Shared class subject ${shared.subjectId} has mismatched remaining hours across sections ${sections.join(',')}.`
        );
      }
    }

    if (base.remainingHours === 0) continue;
    const compulsoryBlock = compulsoryContinuous.get(shared.subjectId) || 1;
    if (compulsoryBlock > 1 && base.remainingHours % compulsoryBlock !== 0) {
      throw new Error(
        `Subject ${shared.subjectId} requires block ${compulsoryBlock} but remaining ${base.remainingHours} is not divisible.`
      );
    }

    let sharedFacultyOptions = base.facultyIds.slice();
    for (let i = 1; i < sections.length; i += 1) {
      const cur = config.subjectsBySection.get(sections[i]).get(shared.subjectId);
      sharedFacultyOptions = sharedFacultyOptions.filter((fid) => cur.facultyIds.includes(fid));
    }
    if (sharedFacultyOptions.length === 0) {
      throw new Error(
        `Shared class subject ${shared.subjectId} has no common faculty across sections ${sections.join(',')}.`
      );
    }

    tasks.push({
      id: `SHARED:${sections.sort().join('+')}:${shared.subjectId}`,
      type: 'SHARED',
      sections: sections.sort(),
      subjectId: shared.subjectId,
      facultyOptions: sharedFacultyOptions,
      remaining: base.remainingHours,
      preferredContinuous: base.preferredContinuous,
      compulsoryBlock,
    });

    for (const section of sections) {
      sharedTaskKeys.add(`${section}:${shared.subjectId}`);
    }
  }

  for (const [section, subjMap] of config.subjectsBySection.entries()) {
    for (const subject of subjMap.values()) {
      if (subject.remainingHours <= 0) continue;
      if (sharedTaskKeys.has(`${section}:${subject.subjectId}`)) continue;

      const compulsoryBlock = compulsoryContinuous.get(subject.subjectId) || 1;
      if (compulsoryBlock > 1 && subject.remainingHours % compulsoryBlock !== 0) {
        throw new Error(
          `Section ${section}, subject ${subject.subjectId} requires block ${compulsoryBlock} but remaining ${subject.remainingHours} is not divisible.`
        );
      }

      tasks.push({
        id: `SECTION:${section}:${subject.subjectId}`,
        type: 'SECTION',
        sections: [section],
        subjectId: subject.subjectId,
        facultyOptions: subject.facultyIds.slice(),
        remaining: subject.remainingHours,
        preferredContinuous: subject.preferredContinuous,
        compulsoryBlock,
      });
    }
  }

  return tasks;
}

function canPlaceBlock(state, task, dayIdx, startPeriod, blockLen, facultyId) {
  if (startPeriod + blockLen - 1 > 7) return false;
  const fid = facultyId || task.facultyOptions?.[0];
  if (!fid) return false;
  for (let p = startPeriod; p < startPeriod + blockLen; p += 1) {
    for (const section of task.sections) {
      if (state.sectionGrid.get(section)[dayIdx][p - 1] !== null) return false;
    }
    if (state.facultyGrid.get(fid)[dayIdx][p - 1] !== null) return false;
    if (!isFacultyAvailable(state.availability, fid, dayIdx, p)) return false;
  }
  return true;
}

function estimateTaskDomain(state, task) {
  let count = 0;
  const minLen = task.compulsoryBlock > 1 ? task.compulsoryBlock : 1;
  for (const fid of task.facultyOptions) {
    for (let d = 0; d < 6; d += 1) {
      for (let p = 1; p <= 7; p += 1) {
        if (canPlaceBlock(state, task, d, p, minLen, fid)) count += 1;
      }
    }
  }
  return count;
}

function generateCandidates(state, task) {
  const candidates = [];
  const maxLen = Math.min(task.remaining, Math.max(1, task.preferredContinuous));

  let blockLens = [];
  if (task.compulsoryBlock > 1) {
    blockLens = [task.compulsoryBlock];
  } else {
    for (let l = maxLen; l >= 1; l -= 1) blockLens.push(l);
  }

  for (const len of blockLens) {
    if (len > task.remaining) continue;
    if (task.compulsoryBlock > 1 && len !== task.compulsoryBlock) continue;
    for (let d = 0; d < 6; d += 1) {
      for (let p = 1; p <= 7; p += 1) {
        for (const fid of task.facultyOptions) {
          if (!canPlaceBlock(state, task, d, p, len, fid)) continue;

          let loadScore = 0;
          for (const section of task.sections) loadScore += state.sectionDayLoad.get(section)[d];
          const scarcity = 7 - [...state.facultyGrid.get(fid)[d]].filter(Boolean).length;

          candidates.push({
            dayIdx: d,
            startPeriod: p,
            length: len,
            facultyId: fid,
            score: loadScore * 10 + scarcity,
          });
        }
      }
    }
    if (candidates.length > 0 && task.compulsoryBlock > 1) break;
  }

  candidates.sort((a, b) => {
    if (b.length !== a.length) return b.length - a.length;
    if (a.score !== b.score) return a.score - b.score;
    if (a.dayIdx !== b.dayIdx) return a.dayIdx - b.dayIdx;
    return a.startPeriod - b.startPeriod;
  });

  return candidates;
}

function applyCandidate(state, task, cand) {
  const placed = [];
  for (let p = cand.startPeriod; p < cand.startPeriod + cand.length; p += 1) {
    const assignment = {
      sections: task.sections,
      facultyId: cand.facultyId,
      dayIdx: cand.dayIdx,
      period: p,
      subjectId: task.subjectId,
      type: task.type,
    };
    const ok = assignCell(state, assignment);
    if (!ok) {
      for (const a of placed.reverse()) unassignCell(state, a);
      return null;
    }
    placed.push(assignment);
  }

  task.remaining -= cand.length;
  if (task.type === 'SHARED') {
    state.sharedPlacements.push({
      sections: task.sections.slice(),
      subjectId: task.subjectId,
      facultyId: cand.facultyId,
      day: DAYS[cand.dayIdx],
      startPeriod: cand.startPeriod,
      endPeriod: cand.startPeriod + cand.length - 1,
      hours: cand.length,
    });
  }

  return placed;
}

function rollbackCandidate(state, task, cand, placed) {
  if (task.type === 'SHARED') {
    state.sharedPlacements.pop();
  }
  task.remaining += cand.length;
  for (const a of placed.reverse()) unassignCell(state, a);
}

function solveTasks(state, tasks, deadEnd) {
  const pending = tasks.filter((t) => t.remaining > 0);
  if (pending.length === 0) return true;

  let chosen = null;
  let chosenDomain = null;

  for (const t of pending) {
    const domain = estimateTaskDomain(state, t);
    if (domain === 0) {
      deadEnd.reason = `No available slot for task ${t.id} with strict faculty availability.`;
      return false;
    }
    if (
      chosen === null ||
      domain < chosenDomain ||
      (domain === chosenDomain && t.remaining > chosen.remaining)
    ) {
      chosen = t;
      chosenDomain = domain;
    }
  }

  const cands = generateCandidates(state, chosen);
  if (cands.length === 0) {
    deadEnd.reason = `No candidate placements for task ${chosen.id} after filtering by availability/conflicts.`;
    return false;
  }

  for (const cand of cands) {
    const placed = applyCandidate(state, chosen, cand);
    if (!placed) continue;
    if (solveTasks(state, tasks, deadEnd)) return true;
    rollbackCandidate(state, chosen, cand, placed);
  }

  deadEnd.reason = `Backtracking exhausted for task ${chosen.id}.`;
  return false;
}

function ensureNoMissingOrExtra(config, tasks) {
  for (const t of tasks) {
    if (t.remaining !== 0) {
      throw new Error(`Task ${t.id} not fully assigned. Remaining ${t.remaining} hour(s).`);
    }
  }

  for (const [section, subjMap] of config.subjectsBySection.entries()) {
    for (const subj of subjMap.values()) {
      if (subj.remainingHours < 0) {
        throw new Error(`Section ${section} subject ${subj.subjectId} over-allocated.`);
      }
    }
  }
}

function writeSectionTimetable(outPath, state, config, subjectNames, facultyNames) {
  const wb = XLSX.utils.book_new();

  for (const section of state.sections) {
    const meta = config.sectionMeta.get(section);
    const sectionLabel = meta ? `${meta.section}-Y${meta.year}` : section;
    const grid = state.sectionGrid.get(section);
    const rows = [];
    rows.push(['Day/Period', ...PERIODS.map(String)]);

    for (let d = 0; d < 6; d += 1) {
      const row = [DAYS[d]];
      for (let p = 0; p < 7; p += 1) {
        const cell = grid[d][p];
        if (!cell) {
          row.push('FREE');
        } else {
          const sName = subjectNames.get(cell.subjectId) || `SUB-${cell.subjectId}`;
          const fName = facultyNames.get(cell.facultyId) || `FAC-${cell.facultyId}`;
          row.push(`${sName} [${fName}]`);
        }
      }
      rows.push(row);
    }

    const ws = XLSX.utils.aoa_to_sheet(rows);
    XLSX.utils.book_append_sheet(wb, ws, sectionLabel.slice(0, 31));
  }

  XLSX.writeFile(wb, outPath);
}

function writeFacultyReports(outWorkloadPath, outAvailabilityPath, state, config, subjectNames, facultyNames) {
  const required = new Map();
  for (const subjMap of config.subjectsBySection.values()) {
    for (const subj of subjMap.values()) {
      if (subj.facultyIds.length === 1) {
        const fid = subj.facultyIds[0];
        required.set(fid, (required.get(fid) || 0) + subj.totalHours);
      }
    }
  }

  const assigned = new Map();
  for (const [fid, grid] of state.facultyGrid.entries()) {
    let c = 0;
    for (let d = 0; d < 6; d += 1) {
      for (let p = 0; p < 7; p += 1) if (grid[d][p] !== null) c += 1;
    }
    assigned.set(fid, c);
  }

  const workloadRows = [];
  workloadRows.push([
    'Faculty ID',
    'Faculty Name',
    'Required Hours',
    'Assigned Hours',
    'Availability Slots',
    'Utilization %',
  ]);

  const availabilityRows = [];
  availabilityRows.push([
    'Faculty ID',
    'Faculty Name',
    'Available Slots',
    'Assigned Slots',
    'Unassigned Available Slots',
    'Strict Availability Respected',
  ]);

  const facultyIds = [...new Set([...required.keys(), ...state.facultyGrid.keys()])].sort((a, b) => a - b);
  for (const fid of facultyIds) {
    const avail = state.availability.get(fid) ? state.availability.get(fid).size : 0;
    const req = required.get(fid) || 0;
    const asn = assigned.get(fid) || 0;
    const name = facultyNames.get(fid) || `FAC-${fid}`;

    workloadRows.push([
      fid,
      name,
      req,
      asn,
      avail,
      avail > 0 ? Number(((asn / avail) * 100).toFixed(2)) : 0,
    ]);

    availabilityRows.push([fid, name, avail, asn, avail - asn, 'YES']);
  }

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(workloadRows), 'Workload');

  const detailRows = [['Faculty ID', 'Day', 'Period', 'Section(s)', 'Subject']];
  for (const [fid, grid] of state.facultyGrid.entries()) {
    for (let d = 0; d < 6; d += 1) {
      for (let p = 0; p < 7; p += 1) {
        const cell = grid[d][p];
        if (!cell) continue;
        detailRows.push([
          fid,
          DAYS[d],
          p + 1,
          cell.sections.join(','),
          subjectNames.get(cell.subjectId) || `SUB-${cell.subjectId}`,
        ]);
      }
    }
  }
  XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(detailRows), 'Assignments');
  XLSX.writeFile(wb, outWorkloadPath);

  const wb2 = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb2, XLSX.utils.aoa_to_sheet(availabilityRows), 'AvailabilityUsage');
  XLSX.writeFile(wb2, outAvailabilityPath);
}

function writeSharedReport(outPath, state, subjectNames, facultyNames) {
  const rows = [['Sections', 'Subject', 'Faculty', 'Day', 'Start Period', 'End Period', 'Hours']];
  for (const sp of state.sharedPlacements) {
    rows.push([
      sp.sections.join(','),
      subjectNames.get(sp.subjectId) || `SUB-${sp.subjectId}`,
      facultyNames.get(sp.facultyId) || `FAC-${sp.facultyId}`,
      sp.day,
      sp.startPeriod,
      sp.endPeriod,
      sp.hours,
    ]);
  }

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(rows), 'SharedClasses');
  XLSX.writeFile(wb, outPath);
}

function writeConstraintReport(outPath, ok, reason) {
  const rows = [['status', 'message']];
  if (ok) {
    rows.push(['SUCCESS', 'All hard constraints satisfied.']);
  } else {
    rows.push(['FAILED', reason]);
  }
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(rows), 'ConstraintReport');
  XLSX.writeFile(wb, outPath);
}

function main() {
  const files = {
    mainConfig: process.argv[2] || 'UPDATED TIMETABLE TOTAL.xlsx',
    labs: process.argv[3] || 'LAB.xlsx',
    shared: process.argv[4] || 'shared-classes-template.xlsx',
    availability: process.argv[5] || 'faculty-availability-template.xlsx',
    facultyMap: process.argv[6] || 'FACULTY ID MAPPING.xlsx',
    subjectMap: process.argv[7] || 'SUBJECT ID MAPPING.xlsx',
    continuous: process.argv[8] || 'subject-continuous-rules-template.xlsx',
  };

  const output = {
    sectionTimetable: 'generated_section_timetables.xlsx',
    facultyWorkload: 'generated_faculty_workload_report.xlsx',
    facultyAvailability: 'generated_faculty_availability_usage.xlsx',
    sharedReport: 'generated_shared_classes_report.xlsx',
    constraintReport: 'generated_constraint_report.xlsx',
  };

  try {
    const config = parseMainConfig(files.mainConfig);
    const availability = parseFacultyAvailability(files.availability);
    const labs = parseLabs(files.labs);
    const sharedRows = parseShared(files.shared);
    const compulsoryContinuous = parseContinuousRules(files.continuous);

    const facultyNames = parseIdMap(files.facultyMap, ['id assigned', 'id', 'ID'], ['faculty name', 'name']);
    const subjectNames = parseIdMap(files.subjectMap, ['id', 'ID'], ['subject name', 'name']);

    validateAvailabilityFeasibility(config, availability, sharedRows);

    const state = buildState(config, availability);

    allocateLabs(config, state, labs);

    const tasks = buildTasks(config, sharedRows, compulsoryContinuous);

    const deadEnd = { reason: 'Unknown scheduling dead-end.' };
    const solved = solveTasks(state, tasks, deadEnd);
    if (!solved) {
      const msg = `Valid timetable cannot be generated due to constraint conflict: ${deadEnd.reason}`;
      writeConstraintReport(output.constraintReport, false, msg);
      console.error(msg);
      process.exit(2);
    }

    for (const task of tasks) {
      for (const section of task.sections) {
        const subj = config.subjectsBySection.get(section).get(task.subjectId);
        subj.remainingHours = task.remaining;
      }
    }

    ensureNoMissingOrExtra(config, tasks);

    writeSectionTimetable(output.sectionTimetable, state, config, subjectNames, facultyNames);
    writeFacultyReports(
      output.facultyWorkload,
      output.facultyAvailability,
      state,
      config,
      subjectNames,
      facultyNames
    );
    writeSharedReport(output.sharedReport, state, subjectNames, facultyNames);
    writeConstraintReport(output.constraintReport, true, 'All constraints satisfied, including strict faculty availability.');

    console.log('Timetable generation successful. Outputs:');
    Object.values(output).forEach((f) => console.log(`- ${f}`));
  } catch (err) {
    const msg = `Valid timetable cannot be generated due to constraint conflict: ${err.message}`;
    writeConstraintReport('generated_constraint_report.xlsx', false, msg);
    console.error(msg);
    process.exit(1);
  }
}

main();
