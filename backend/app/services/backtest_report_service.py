import json
import math
from io import BytesIO
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.backtest import BacktestRecordDetailResponse
from app.schemas.uploaded_file import UploadedFileResponse
from app.services.backtest_record_service import get_backtest_record
from app.services.file_service import create_uploaded_file_from_bytes

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SHEET_MAIN_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
)
SHEET_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"
)
STYLES_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"
)
RELATIONSHIP_CONTENT_TYPE = (
    "application/vnd.openxmlformats-package.relationships+xml"
)
OFFICE_DOCUMENT_REL = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)
WORKSHEET_REL = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
)
STYLES_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
SheetDefinition = tuple[str, list[list[object]], set[int]]


def export_backtest_report(
    db: Session,
    owner: User,
    task_id: int,
) -> UploadedFileResponse | None:
    detail = get_backtest_record(db, owner, task_id)
    if detail is None:
        return None

    report_bytes = build_backtest_report_xlsx(detail)
    filename = (
        f"回测报告_{detail.symbol}_{detail.timeframe}_{detail.start_date}_"
        f"{detail.end_date}_{detail.id}.xlsx"
    )
    return create_uploaded_file_from_bytes(
        db,
        owner,
        filename=filename,
        content=report_bytes,
        content_type=XLSX_CONTENT_TYPE,
        business_type="backtest",
        business_id=detail.id,
        visibility="private",
    )


def build_backtest_report_xlsx(detail: BacktestRecordDetailResponse) -> bytes:
    sheets = [
        ("摘要", _summary_rows(detail), {1, 3, 12}),
        ("交易明细", _trade_rows(detail), {1}),
        ("策略时间线", _timeline_rows(detail), {1}),
        ("资金曲线", _equity_rows(detail), {1}),
        ("策略积木", _strategy_rows(detail), {1}),
    ]

    output = BytesIO()
    with ZipFile(output, mode="w", compression=ZIP_DEFLATED) as archive:
        _write_static_xlsx_parts(archive, sheets)
        archive.writestr("xl/workbook.xml", _workbook_xml(sheets))
        archive.writestr("xl/_rels/workbook.xml.rels", _workbook_rels_xml(sheets))
        archive.writestr("xl/styles.xml", _styles_xml())
        for index, (_, rows, header_rows) in enumerate(sheets, start=1):
            archive.writestr(
                f"xl/worksheets/sheet{index}.xml",
                _worksheet_xml(rows, header_rows=header_rows),
            )
    return output.getvalue()


def _summary_rows(detail: BacktestRecordDetailResponse) -> list[list[object]]:
    return [
        ["STS 回测报告"],
        [],
        ["基础信息", ""],
        ["报告编号", detail.id],
        ["运行编号", detail.run_id],
        ["市场", _format_market(detail.market)],
        ["股票代码", detail.symbol],
        ["K线周期", _format_timeframe(detail.timeframe)],
        ["回测区间", f"{detail.start_date} 至 {detail.end_date}"],
        ["模拟账户", detail.simulation_account_name or "未绑定"],
        ["生成来源", "个人空间-我的回测"],
        [],
        ["核心指标", ""],
        ["总收益率", f"{detail.summary.totalReturnPercent:.2f}%"],
        ["最大回撤", f"{detail.summary.maxDrawdownPercent:.2f}%"],
        ["胜率", f"{detail.summary.winRatePercent:.2f}%"],
        ["初始资金", detail.config.initialCash],
        ["最终权益", detail.summary.endingEquity],
        ["交易次数", detail.summary.tradeCount],
        ["策略积木数量", len(detail.strategy.nodes)],
        ["连接数量", len(detail.strategy.edges)],
    ]


def _trade_rows(detail: BacktestRecordDetailResponse) -> list[list[object]]:
    rows: list[list[object]] = [
        [
            "时间",
            "方向",
            "价格",
            "数量",
            "成交金额",
            "交易成本",
            "滑点",
            "现金变化",
            "原因",
            "成本明细",
        ]
    ]
    for trade in detail.trades:
        rows.append(
            [
                trade.time,
                trade.side,
                trade.price,
                trade.quantity,
                trade.gross_amount,
                trade.cost_amount,
                trade.slippage_amount,
                trade.net_cash_change,
                trade.reason,
                json.dumps(trade.cost_breakdown, ensure_ascii=False),
            ]
        )
    return rows


def _timeline_rows(detail: BacktestRecordDetailResponse) -> list[list[object]]:
    rows: list[list[object]] = [
        ["时间", "事件类型", "标题", "说明", "级别", "方向", "价格", "数量", "规则", "积木"]
    ]
    for item in detail.timeline:
        rows.append(
            [
                item.time,
                item.event_type,
                item.title,
                item.description,
                item.severity,
                item.side or "",
                item.price if item.price is not None else "",
                item.quantity if item.quantity is not None else "",
                item.rule or "",
                item.node_label or item.node_type or "",
            ]
        )
    return rows


def _equity_rows(detail: BacktestRecordDetailResponse) -> list[list[object]]:
    rows: list[list[object]] = [["时间", "权益"]]
    rows.extend([[point.time, point.equity] for point in detail.equityCurve])
    return rows


def _strategy_rows(detail: BacktestRecordDetailResponse) -> list[list[object]]:
    rows: list[list[object]] = [["积木ID", "类型", "名称", "X", "Y", "参数"]]
    for node in detail.strategy.nodes:
        rows.append(
            [
                node.id,
                node.type,
                node.label,
                node.x,
                node.y,
                json.dumps(node.params, ensure_ascii=False),
            ]
        )
    rows.append([])
    rows.append(["连接ID", "起点", "终点"])
    rows.extend([[edge.id, edge.from_, edge.to] for edge in detail.strategy.edges])
    return rows


def _write_static_xlsx_parts(archive: ZipFile, sheets: list[SheetDefinition]) -> None:
    archive.writestr("[Content_Types].xml", _content_types_xml(len(sheets)))
    archive.writestr("_rels/.rels", _root_rels_xml())


def _content_types_xml(sheet_count: int) -> str:
    overrides = "\n".join(
        (
            f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
            f'ContentType="{SHEET_CONTENT_TYPE}"/>'
        )
        for index in range(1, sheet_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="{RELATIONSHIP_CONTENT_TYPE}"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="{SHEET_MAIN_CONTENT_TYPE}"/>
  <Override PartName="/xl/styles.xml" ContentType="{STYLES_CONTENT_TYPE}"/>
  {overrides}
</Types>"""


def _root_rels_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="{OFFICE_DOCUMENT_REL}" Target="xl/workbook.xml"/>
</Relationships>"""


def _workbook_xml(sheets: list[SheetDefinition]) -> str:
    sheet_xml = "\n".join(
        (
            f'<sheet name={quoteattr(name)} sheetId="{index}" '
            f'r:id="rId{index}"/>'
        )
        for index, (name, _, _) in enumerate(sheets, start=1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    {sheet_xml}
  </sheets>
</workbook>"""


def _workbook_rels_xml(sheets: list[SheetDefinition]) -> str:
    worksheet_rels = "\n".join(
        (
            f'<Relationship Id="rId{index}" '
            f'Type="{WORKSHEET_REL}" Target="worksheets/sheet{index}.xml"/>'
        )
        for index in range(1, len(sheets) + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {worksheet_rels}
  <Relationship Id="rId{len(sheets) + 1}" Type="{STYLES_REL}" Target="styles.xml"/>
</Relationships>"""


def _styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="3">
    <font><sz val="11"/><color rgb="FF111827"/><name val="Calibri"/></font>
    <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>
    <font><b/><sz val="16"/><color rgb="FF111827"/><name val="Calibri"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill>
      <patternFill patternType="solid">
        <fgColor rgb="FF5B35D5"/><bgColor indexed="64"/>
      </patternFill>
    </fill>
  </fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="3">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
    <xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>
  </cellXfs>
</styleSheet>"""


def _worksheet_xml(rows: list[list[object]], *, header_rows: set[int]) -> str:
    row_xml = "\n".join(
        _row_xml(row_number, row, _row_style(row_number, header_rows))
        for row_number, row in enumerate(rows, start=1)
    )
    column_xml = "\n".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(_column_widths(rows), start=1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews>
    <sheetView workbookViewId="0">
      <pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>
    </sheetView>
  </sheetViews>
  <cols>{column_xml}</cols>
  <sheetData>{row_xml}</sheetData>
</worksheet>"""


def _row_xml(row_number: int, row: list[object], style_id: int | None) -> str:
    cells = "".join(
        _cell_xml(_cell_ref(row_number, col_number), value, style_id)
        for col_number, value in enumerate(row, start=1)
        if value is not None
    )
    return f'<row r="{row_number}">{cells}</row>'


def _cell_xml(ref: str, value: object, style_id: int | None) -> str:
    style_attr = f' s="{style_id}"' if style_id is not None else ""
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return f'<c r="{ref}" t="n"{style_attr}><v>{value}</v></c>'

    text = escape(str(value))
    space_attr = ' xml:space="preserve"' if text.strip() != text else ""
    return f'<c r="{ref}" t="inlineStr"{style_attr}><is><t{space_attr}>{text}</t></is></c>'


def _row_style(row_number: int, header_rows: set[int]) -> int | None:
    if row_number == 1 and 1 not in header_rows:
        return 2
    if row_number in header_rows:
        return 1
    return None


def _column_widths(rows: list[list[object]]) -> list[int]:
    column_count = max((len(row) for row in rows), default=1)
    widths: list[int] = []
    for column_index in range(column_count):
        max_length = max(
            (len(str(row[column_index])) for row in rows if column_index < len(row)),
            default=8,
        )
        widths.append(max(10, min(38, max_length + 4)))
    return widths


def _cell_ref(row_number: int, column_number: int) -> str:
    letters = ""
    current = column_number
    while current:
        current, remainder = divmod(current - 1, 26)
        letters = chr(65 + remainder) + letters
    return f"{letters}{row_number}"


def _format_market(market: str) -> str:
    return "美股" if market == "US_STOCK" else "A股"


def _format_timeframe(timeframe: str) -> str:
    return "1分钟" if timeframe == "1m" else "5分钟"
