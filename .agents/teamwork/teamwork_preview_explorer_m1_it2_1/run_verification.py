import sys
from pathlib import Path
sys.path.insert(0, ".")

import importlib.util
spec = importlib.util.spec_from_file_location("proposed_config", ".agents/teamwork/teamwork_preview_explorer_m1_it2_1/proposed_config.py")
proposed_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proposed_config)

# Replace module in sys.modules so `from src.web.core.config import ...` gets proposed_config!
sys.modules["src.web.core.config"] = proposed_config

print("sys.modules replaced with proposed_config! Running pytest...")
import pytest
ret = pytest.main([
    "tests/test_m1_core.py::TestConfigAndCookies",
    "tests/test_m1_challenger2_edge_cases.py::TestYamlConfigPersistenceAndInvariants",
    "tests/test_m1_challenger2_edge_cases.py::TestCookieParsingAndHeaderSync",
    "-v", "-s", "--tb=short"
])
print("Pytest exit code:", ret)
sys.exit(int(ret))
