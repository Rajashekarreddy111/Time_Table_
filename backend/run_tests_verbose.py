import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

loader = unittest.TestLoader()
suite = loader.loadTestsFromName("test_solver_backtracking")

with open("test_results_detailed.txt", "w") as f:
    runner = unittest.TextTestRunner(verbosity=2, stream=f)
    result = runner.run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
