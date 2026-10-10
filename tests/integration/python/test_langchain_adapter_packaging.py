from pathlib import Path

import tomllib


def test_langchain_distribution_owns_only_its_namespace() -> None:
    root = Path(__file__).resolve().parents[3]
    package = root / "packages" / "python" / "langchain"
    configuration = tomllib.loads((package / "pyproject.toml").read_text())
    project = configuration["project"]
    assert project["name"] == "ygo74-agent-runtime-langchain"
    assert project["version"] == "1.0.0"
    assert project["dependencies"] == [
        "ygo74-agent-runtime-agents>=1.0.0,<2",
        "langchain-core>=1.6.3,<1.7",
    ]
    finder = configuration["tool"]["setuptools"]["packages"]["find"]
    assert finder["include"] == [
        "ygo74.agent_runtime.integrations.langchain",
        "ygo74.agent_runtime.integrations.langchain.*",
    ]
    assert finder["namespaces"] is True
    namespace = package / "ygo74" / "agent_runtime" / "integrations"
    assert (namespace / "langchain" / "py.typed").is_file()
    for directory in (namespace, namespace.parent, namespace.parent.parent):
        assert not (directory / "__init__.py").exists()
        assert not (directory / "py.typed").exists()
