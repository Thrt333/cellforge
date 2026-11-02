PYTHON ?= python3

.PHONY: check check-policy check-access check-probe check-authorization check-adb check-module check-module-syntax check-module-assets check-workspace check-diff probe-module
check:
	$(PYTHON) -m unittest discover -s tests -v

check-policy:
	$(PYTHON) -m unittest discover -s tests -p 'test_policy.py' -v

check-access:
	$(PYTHON) -m unittest discover -s tests -p 'test_module_access.py' -v

check-probe:
	$(PYTHON) -m unittest discover -s tests -p 'test_probe_module.py' -v

check-authorization:
	$(PYTHON) -m unittest discover -s tests -p 'test_qadbkey.py' -v
	$(PYTHON) -m unittest discover -s tests -p 'test_authorization.py' -v

check-adb:
	$(PYTHON) -m unittest discover -s tests -p 'test_adb_inspect.py' -v

check-module: check-module-syntax
	$(PYTHON) -m unittest discover -s tests -p 'test_module_policy.py' -v

check-module-syntax:
	sh -n module/cellforge.sh
	sh -n module/startup.sh

check-module-assets:
	$(PYTHON) scripts/check_module_assets.py

check-workspace:
	$(PYTHON) scripts/check_workspace.py
	$(PYTHON) scripts/cellforge.py --help
	$(PYTHON) scripts/module_access.py --help
	$(PYTHON) scripts/adb_inspect.py --help

check-diff:
	git diff --check

probe-module:
	$(PYTHON) -B scripts/probe_module.py
