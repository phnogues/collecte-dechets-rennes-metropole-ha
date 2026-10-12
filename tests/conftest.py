"""Les tests de tests/ha nécessitent Home Assistant (Linux, Python >= 3.13) : ignorés sinon."""

import importlib.util

collect_ignore_glob = [] if importlib.util.find_spec("pytest_homeassistant_custom_component") else ["ha/*"]
