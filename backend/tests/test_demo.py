import importlib.util
from pathlib import Path


def test_demo_offline_prints_report(capsys):
    path = Path(__file__).resolve().parents[1] / "scripts" / "demo_offline.py"
    spec = importlib.util.spec_from_file_location("demo_offline", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()
    out = capsys.readouterr().out
    assert "Top 10 skills" in out and "Gauteng" in out and "Salaries" in out
    assert module.rand(None) == "-" and module.rand(450000) == "R450 000"
