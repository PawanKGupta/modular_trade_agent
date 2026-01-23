from datetime import date
from types import SimpleNamespace

from server.app.services import pdf_generator as pdf_module
from src.infrastructure.db.models import TradeMode


class FakeDoc:
    def __init__(self, buffer, pagesize=None, leftMargin=None, rightMargin=None):
        self.buffer = buffer

    def build(self, story):
        self.buffer.write(b"FAKEPDF")


class FakeParagraph:
    def __init__(self, text, style):
        self.text = text
        self.style = style


class FakeSpacer:
    def __init__(self, *args, **kwargs):
        pass


class FakeTable:
    def __init__(self, data, colWidths):
        FakeTable.records.append(data)

    def setStyle(self, style):
        pass


class FakeLinePlot:
    last_instance = None

    def __init__(self):
        self.lines = [SimpleNamespace(strokeColor=None)]
        self.data = []
        self.xValueAxis = SimpleNamespace(
            labels=SimpleNamespace(angle=None),
            valueMin=None,
            valueMax=None,
        )
        self.yValueAxis = SimpleNamespace(valueMin=None, valueMax=None)
        FakeLinePlot.last_instance = self


class FakeDrawing:
    def __init__(self, width, height):
        self.axes = []

    def add(self, item):
        self.axes.append(item)


class DummyRepo:
    def __init__(self, entries):
        self.entries = entries

    def range(self, user_id, start, end):
        return self.entries


def _patch_reporting(monkeypatch):
    FakeTable.records = []
    monkeypatch.setattr(pdf_module, "SimpleDocTemplate", FakeDoc)
    monkeypatch.setattr(pdf_module, "Paragraph", FakeParagraph)
    monkeypatch.setattr(pdf_module, "Spacer", FakeSpacer)
    monkeypatch.setattr(pdf_module, "Table", FakeTable)
    monkeypatch.setattr(pdf_module, "TableStyle", lambda value: value)
    monkeypatch.setattr(pdf_module, "LinePlot", FakeLinePlot)
    monkeypatch.setattr(pdf_module, "Drawing", FakeDrawing)
    monkeypatch.setattr(
        pdf_module,
        "colors",
        SimpleNamespace(HexColor=lambda value: value, white="white"),
    )
    monkeypatch.setattr(
        pdf_module,
        "getSampleStyleSheet",
        lambda: {
            "Title": "title",
            "Normal": "normal",
            "Heading3": "heading",
        },
    )


def _build_record(dt, realized, unrealized, fees):
    return SimpleNamespace(date=dt, realized_pnl=realized, unrealized_pnl=unrealized, fees=fees)


def test_generate_pnl_report_includes_unrealized(monkeypatch):
    records = [
        _build_record(date(2025, 1, 1), 100.0, 50.0, 5.0),
        _build_record(date(2025, 1, 2), -20.0, 10.0, 1.0),
    ]
    monkeypatch.setattr(pdf_module, "PnlRepository", lambda db: DummyRepo(records))
    _patch_reporting(monkeypatch)

    generator = pdf_module.PdfGenerator()
    output = generator.generate_pnl_report(
        db=SimpleNamespace(),
        user_id=1,
        trade_mode=TradeMode.PAPER,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
        include_unrealized=True,
    )

    assert output == b"FAKEPDF"
    assert FakeTable.records[0][-1][1] == "134.00"
    assert FakeLinePlot.last_instance.lines[0].strokeColor == "#22c55e"


def test_generate_pnl_report_excludes_unrealized(monkeypatch):
    records = [_build_record(date(2025, 2, 1), 70.0, 30.0, 10.0)]
    monkeypatch.setattr(pdf_module, "PnlRepository", lambda db: DummyRepo(records))
    _patch_reporting(monkeypatch)

    generator = pdf_module.PdfGenerator()
    output = generator.generate_pnl_report(
        db=SimpleNamespace(),
        user_id=2,
        trade_mode=TradeMode.BROKER,
        start_date=date(2025, 2, 1),
        end_date=date(2025, 2, 1),
        include_unrealized=False,
    )

    assert output == b"FAKEPDF"
    assert FakeTable.records[0][-1][1] == "60.00"
    assert FakeLinePlot.last_instance.lines[0].strokeColor == "#22c55e"
