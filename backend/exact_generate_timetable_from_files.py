from __future__ import annotations

import argparse
import sys
from pathlib import Path

from services.exact_timetable_generator import MainConfigValidationError, generate_timetable_from_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Exact prompt-compliant timetable generator (file-driven).")
    parser.add_argument("--main-config", required=True, help="Main Config File")
    parser.add_argument("--lab-timetable", required=True, help="Lab Timetable File")
    parser.add_argument("--shared-class", required=True, help="Shared Class File")
    parser.add_argument("--faculty-id-name", required=True, help="Faculty ID <-> Name Mapping file")
    parser.add_argument("--subject-id-name", required=True, help="Subject ID <-> Name Mapping file")
    parser.add_argument("--continuous-hours", required=True, help="Continuous Hours Mapping file")
    parser.add_argument("--faculty-availability", required=True, help="Faculty Availability file")
    parser.add_argument("--out-dir", required=True, help="Output directory")

    args = parser.parse_args()

    try:
        result = generate_timetable_from_files(
            main_config_path=args.main_config,
            lab_timetable_path=args.lab_timetable,
            shared_class_path=args.shared_class,
            faculty_id_name_path=args.faculty_id_name,
            subject_id_name_path=args.subject_id_name,
            continuous_hours_mapping_path=args.continuous_hours,
            faculty_availability_path=args.faculty_availability,
            out_dir=args.out_dir,
        )
    except MainConfigValidationError as e:
        print(
            f"ValidationError: Year={e.year} Section={e.section} actual_hours={e.actual_hours}"
        )
        return 2
    except Exception as e:
        print(f"ERROR: {e}")
        return 2

    print("Generated:")
    for k, p in result.items():
        print(f"- {k}: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

