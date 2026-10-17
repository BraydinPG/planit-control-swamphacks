from app.db.seed import seed_database


def test_seed_command_does_not_insert_demo_rows(monkeypatch) -> None:
    calls: list[str] = []

    def initialize() -> None:
        calls.append("initialize")

    def connect() -> None:
        calls.append("connect")

    monkeypatch.setattr("app.db.seed.load_env_file", lambda: None)
    monkeypatch.setattr("app.db.seed.initialize_database", initialize)
    monkeypatch.setattr("app.db.seed.get_database_url", lambda: "postgresql://localhost/planit")
    monkeypatch.setattr("app.db.seed.to_driver_url", lambda url: url)

    class Connection:
        def execute(self, statement) -> None:
            calls.append("select")

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

    class Engine:
        def connect(self):
            connect()
            return Connection()

    monkeypatch.setattr("app.db.seed.create_engine", lambda *args, **kwargs: Engine())
    seed_database()
    assert calls == ["initialize", "connect", "select"]
