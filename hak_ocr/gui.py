"""PySide6 desktop UI. Processing runs on a worker QThread, SQLite writes on UI thread."""
from __future__ import annotations
from pathlib import Path
import json
import sys

from PySide6.QtCore import Qt, QThread, Signal, QRectF
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QFont, QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QSplitter, QListWidget, QListWidgetItem, QLabel, QPushButton, QFileDialog,
    QMessageBox, QTabWidget, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QTextEdit, QHeaderView, QInputDialog, QComboBox, QProgressBar, QToolBar,
    QStatusBar, QFrame, QLineEdit, QDialog, QDialogButtonBox, QScrollArea, QCheckBox,
)

from .storage import Repository
from .processing import process_file, render_preview, check_ocr_ready
from .exporting import export_result
from .backup import backup_complete
from .templates import DEFAULT_ATTENDANCE_TEMPLATE


APP_STYLESHEET = '''
QMainWindow, QWidget { background-color:#F5F7FB; color:#19283C; font: 10pt "Segoe UI"; }
QFrame#Panel { background:#FFFFFF; border:1px solid #DDE5EF; border-radius:10px; }
QListWidget, QTableWidget, QTextEdit { background:#FFFFFF; border:1px solid #DDE5EF;
    border-radius:7px; alternate-background-color:#F4F8FD; selection-background-color:#DDEEFF;
    selection-color:#122D49; }
QHeaderView::section { background:#EDF3F9; color:#244869; padding:7px; border:0px;
    border-right:1px solid #DDE5EF; border-bottom:1px solid #DDE5EF; font-weight:600; }
QPushButton { border:1px solid #D2DBE6; background:#FFF; padding:7px 11px; border-radius:7px; }
QPushButton:hover { background:#E5F1FF; border-color:#9AC4EB; }
QPushButton#Primary { background:#1763A7; color:#FFFFFF; border-color:#1763A7; font-weight:600; }
QPushButton#Primary:hover { background:#0D4C83; }
QTabWidget::pane {border:1px solid #DDE5EF; background:#FFF; border-radius:7px;}
QTabBar::tab {background:#EDF3F9; padding:9px 15px; margin:2px; border-radius:5px;}
QTabBar::tab:selected {background:#1763A7; color:#FFF;}
QProgressBar { border:1px solid #DDE5EF; border-radius:6px; text-align:center; background:#FFF; }
QProgressBar::chunk {background:#2980B9; border-radius:5px;}
QToolBar { background:#FFFFFF; border-bottom:1px solid #DDE5EF; padding:8px; spacing:8px; }
QLineEdit, QComboBox { background:#FFF; border:1px solid #D5E0EA; border-radius:6px; padding:6px;}
'''


from .advanced_engines import engine_report,DocUnwarpLocal
from .evidence_ai import extract_evidence_claims, suggest_document_matches,LocalGGUFExtractor
from .handwriting import HandwritingLocal


class UnwarpWorker(QThread):
    done=Signal(object)
    failed=Signal(str)
    def __init__(self,image):
        super().__init__();self.image=image
    def run(self):
        try:self.done.emit(DocUnwarpLocal().unwarp(self.image))
        except Exception as exc:self.failed.emit(f'{type(exc).__name__}: {exc}')


class EvidenceWorker(QThread):
    done=Signal(object)
    failed=Signal(str)
    def __init__(self,text):
        super().__init__();self.text=text
    def run(self):
        try:self.done.emit(LocalGGUFExtractor().extract(self.text))
        except Exception as exc:self.failed.emit(f'{type(exc).__name__}: {exc}')


class HandwritingWorker(QThread):
    done=Signal(object)
    failed=Signal(str)

    def __init__(self,crop):
        super().__init__();self.crop=crop

    def run(self):
        try:self.done.emit(HandwritingLocal().recognize(self.crop))
        except Exception as exc:self.failed.emit(f'{type(exc).__name__}: {exc}')


class ProcessWorker(QThread):
    progress = Signal(int,int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self,path: str,doc_id: str,digest: str,templates: list[dict],deep: bool=False,force_type: str | None=None,
                 ocr_engine: str='tesseract',docling: bool=False, perspective: bool=False):
        super().__init__();self.path=path;self.doc_id=doc_id;self.digest=digest;self.templates=templates;self.deep=deep;self.force_type=force_type
        self.ocr_engine=ocr_engine;self.docling=docling;self.perspective=perspective

    def run(self):
        try:
            result=process_file(self.path,self.doc_id,self.digest,progress=lambda a,b:self.progress.emit(a,b),custom_templates=self.templates,deep_cells=self.deep,force_type=self.force_type,
                                ocr_engine=self.ocr_engine,docling_enabled=self.docling,
                                auto_perspective=self.perspective)
            self.done.emit(result)
        except Exception as e:
            self.failed.emit(f'{type(e).__name__}: {e}')


class Preview(QLabel):
    """Image preview with source-linked coordinates (normalised bbox)."""
    def __init__(self):
        super().__init__()
        self.setMinimumSize(350,390)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet('background:#E9EDF2; border:1px solid #CAD7E5; border-radius:7px;')
        self.image=None;self.highlights=[];self.selection=None;self.drag_start=None
        self.setText('Chọn tài liệu để xem ảnh/PDF')

    def set_image(self,image):
        self.image=image.copy() if image else None
        self.selection=None;self.drag_start=None
        self.repaint()

    def set_highlights(self,highlights: list[list[float]]):
        self.highlights=highlights
        self.repaint()

    def _canvas_position(self,x:float,y:float):
        if self.image is None:return None
        im=self.image
        scale=min((self.width()-16)/im.width,(self.height()-16)/im.height)
        if scale<=0:return None
        left=(self.width()-im.width*scale)/2;top=(self.height()-im.height*scale)/2
        return (max(0.0,min(1.0,(x-left)/(im.width*scale))),
                max(0.0,min(1.0,(y-top)/(im.height*scale))))

    def mousePressEvent(self,event):
        if self.image is None:return super().mousePressEvent(event)
        if event.button()==Qt.MouseButton.LeftButton:
            self.drag_start=self._canvas_position(event.position().x(),event.position().y())
            self.selection=None
        self.repaint()

    def mouseMoveEvent(self,event):
        if self.drag_start:
            target=self._canvas_position(event.position().x(),event.position().y())
            if target:
                x0,y0=self.drag_start;x1,y1=target
                self.selection=[min(x0,x1),min(y0,y1),max(x0,x1),max(y0,y1)]
                self.repaint()

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self.drag_start:
            self.mouseMoveEvent(event)
            self.drag_start=None
            if self.selection and ((self.selection[2]-self.selection[0])<.01 or
                                   (self.selection[3]-self.selection[1])<.01):
                self.selection=None
            self.repaint()

    def crop_selection(self):
        if self.image is None or self.selection is None:return None
        w,h=self.image.size
        x0,y0,x1,y1=self.selection
        return self.image.crop((int(x0*w),int(y0*h),int(x1*w),int(y1*h)))

    def paintEvent(self,event):
        if self.image is None:
            super().paintEvent(event);return
        painter=QPainter(self)
        painter.fillRect(self.rect(),QColor('#E9EDF2'))
        im=self.image.convert('RGB')
        raw=im.tobytes('raw','RGB')
        qim=QImage(raw,im.width,im.height,im.width*3,QImage.Format.Format_RGB888).copy()
        scale=min((self.width()-16)/im.width,(self.height()-16)/im.height)
        nw=im.width*scale;nh=im.height*scale
        left=(self.width()-nw)/2;top=(self.height()-nh)/2
        painter.drawImage(QRectF(left,top,nw,nh),qim)
        painter.setPen(QPen(QColor('#D8580C'),2))
        painter.setBrush(QColor(249,168,37,38))
        for bbox in self.highlights:
            if not bbox or len(bbox)!=4:continue
            x0,y0,x1,y1=bbox
            painter.drawRect(QRectF(left+x0*nw,top+y0*nh,(x1-x0)*nw,(y1-y0)*nh))
        if self.selection:
            x0,y0,x1,y1=self.selection
            painter.setPen(QPen(QColor('#009E92'),2))
            painter.setBrush(QColor(15,161,148,45))
            painter.drawRect(QRectF(left+x0*nw,top+y0*nh,(x1-x0)*nw,(y1-y0)*nh))
        painter.end()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.repo=Repository()
        self.current_id=None;self.current_result=None;self.current_page=0
        self.worker=None;self.htr_worker=None;self.unwarp_worker=None;self.evidence_worker=None;self.table_ref=None
        self.setWindowTitle('HAK Smart OCR AI 1.2.1 — Offline OCR Studio (Tesseract mặc định)')
        self.resize(1480,890)
        self.setMinimumSize(980,640)
        self._create_ui()
        self.reload_documents()
        self.reload_rules()
        self.reload_templates()

    def _button(self,title,callback,primary=False):
        b=QPushButton(title)
        if primary:b.setObjectName('Primary')
        b.clicked.connect(callback)
        return b

    def _create_ui(self):
        toolbar=QToolBar('Tác vụ');toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for label,handler in [('+ Thêm ảnh/PDF',self.import_files),('+ Thêm thư mục',self.import_folder),
                              ('▶ OCR',self.start_ocr),('◈ OCR sâu từng ô',self.start_deep_ocr),('↓ Xuất dữ liệu',self.export_data),
                              ('⛁ Sao lưu đầy đủ',self.backup_db)]:
            a=QAction(label,self);a.triggered.connect(handler);toolbar.addAction(a)
        toolbar.addSeparator()
        a=QAction('Kiểm tra OCR offline',self);a.triggered.connect(self.check_engine);toolbar.addAction(a)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel(' Bộ nhận dạng: '))
        self.engine_mode=QComboBox()
        for label,code in [('Tesseract','tesseract'),('PaddleOCR Offline','paddle'),('Hybrid (đối chiếu)','hybrid')]:
            self.engine_mode.addItem(label,code)
        toolbar.addWidget(self.engine_mode)
        self.perspective_box=QCheckBox('Sửa phối cảnh ảnh')
        toolbar.addWidget(self.perspective_box)
        self.docling_box=QCheckBox('Docling PDF')
        toolbar.addWidget(self.docling_box)
        a=QAction('✍ Đọc chữ viết tay (vùng chọn)',self)
        a.triggered.connect(self.run_handwriting);toolbar.addAction(a)
        a=QAction('Xem trang cong (UVDoc)',self)
        a.triggered.connect(self.run_unwarp);toolbar.addAction(a)

        self.tabs=QTabWidget()
        self.setCentralWidget(self.tabs)
        self.review=QWidget();self.tabs.addTab(self.review,'Tài liệu & Review Studio')
        self.learning=QWidget();self.tabs.addTab(self.learning,'Learning Center')
        self.template_studio=QWidget();self.tabs.addTab(self.template_studio,'Template Studio')
        self._create_review()
        self._create_learning()
        self._create_templates()

        self.status=QStatusBar();self.setStatusBar(self.status)
        self.progress=QProgressBar();self.progress.setVisible(False)
        self.progress.setMinimumWidth(140)
        self.status.addPermanentWidget(self.progress)
        self.status.showMessage('Chạy cục bộ. Không sử dụng API hay Internet.')

    def _create_review(self):
        root=QVBoxLayout(self.review)
        title=QHBoxLayout()
        heading=QLabel('DOCUMENT REVIEW STUDIO')
        heading.setStyleSheet('font-size:16pt; font-weight:700; color:#163F6B;')
        title.addWidget(heading);title.addStretch(1)
        title.addWidget(QLabel('Loại chứng từ:'))
        self.type_combo=QComboBox()
        self.type_combo.addItems(['generic','bang_cham_cong','phieu_can','hoa_don','hop_dong','ung_luong'])
        self.type_combo.currentIndexChanged.connect(self.set_doc_type)
        title.addWidget(self.type_combo)
        root.addLayout(title)

        split=QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(split,1)

        left=QWidget();lay=QVBoxLayout(left)
        self.filter=QLineEdit();self.filter.setPlaceholderText('Tìm tên tài liệu...')
        self.filter.textChanged.connect(self.filter_docs)
        lay.addWidget(self.filter)
        self.docs=QListWidget()
        self.docs.currentItemChanged.connect(self.document_selected)
        lay.addWidget(self.docs,1)
        self.doc_note=QLabel('Chưa chọn tài liệu');self.doc_note.setWordWrap(True)
        lay.addWidget(self.doc_note)
        split.addWidget(left)

        middle=QWidget();ml=QVBoxLayout(middle)
        preview_bar=QHBoxLayout()
        self.page_select=QComboBox();self.page_select.currentIndexChanged.connect(self.change_page)
        preview_bar.addWidget(QLabel('Trang'));preview_bar.addWidget(self.page_select)
        self.zoom_note=QLabel('Vùng chọn được đánh dấu theo tọa độ nguồn')
        self.zoom_note.setStyleSheet('color:#59728E;')
        preview_bar.addWidget(self.zoom_note,1)
        ml.addLayout(preview_bar)
        self.preview=Preview();ml.addWidget(self.preview,1)
        split.addWidget(middle)

        right=QWidget();rl=QVBoxLayout(right)
        self.details=QTabWidget();rl.addWidget(self.details,1)
        field_page=QWidget();fields_l=QVBoxLayout(field_page)
        self.field_table=QTableWidget(0,4)
        self.field_table.setHorizontalHeaderLabels(['Trường','Giá trị','Duyệt','Trang'])
        self.field_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        self.field_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        self.field_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.field_table.itemSelectionChanged.connect(self.highlight_field)
        fields_l.addWidget(self.field_table)
        fb=QHBoxLayout()
        fb.addWidget(self._button('Thêm trường',self.add_field))
        fb.addWidget(self._button('Lưu & duyệt các trường',self.save_fields,True))
        fields_l.addLayout(fb)
        self.suggestions=QLabel('Gợi ý học: chưa có')
        self.suggestions.setWordWrap(True)
        fields_l.addWidget(self.suggestions)
        self.details.addTab(field_page,'Trường dữ liệu')

        table_page=QWidget();tl=QVBoxLayout(table_page)
        self.table_choice=QComboBox();self.table_choice.currentIndexChanged.connect(self.select_table)
        tl.addWidget(self.table_choice)
        self.table_grid=QTableWidget();self.table_grid.setAlternatingRowColors(True)
        self.table_grid.horizontalHeader().setDefaultSectionSize(77)
        self.table_grid.verticalHeader().setDefaultSectionSize(28)
        self.table_grid.currentCellChanged.connect(self.highlight_cell)
        tl.addWidget(self.table_grid,1)
        self.table_status=QLabel('Chưa xác định được bảng có lưới')
        self.table_status.setWordWrap(True);tl.addWidget(self.table_status)
        table_actions=QHBoxLayout()
        table_actions.addWidget(self._button('+ Hàng',self.add_grid_row))
        table_actions.addWidget(self._button('+ Cột',self.add_grid_column))
        table_actions.addWidget(self._button('− Hàng',self.remove_grid_row))
        table_actions.addWidget(self._button('− Cột',self.remove_grid_column))
        tl.addLayout(table_actions)
        tl.addWidget(self._button('Lưu & duyệt bảng này',self.save_table,True))
        self.details.addTab(table_page,'Bảng biểu')

        attendance_page=QWidget();al=QVBoxLayout(attendance_page)
        al.addWidget(QLabel('Dữ liệu chuẩn hóa & cảnh báo OCR. Ô trống khác 0.'))
        self.attendance_preview=QTableWidget(0,7)
        self.attendance_preview.setHorizontalHeaderLabels(['Trang','Nhân sự','Ngày','Chỉ tiêu','Giá trị OCR','Số','Duyệt'])
        self.attendance_preview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.attendance_preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        al.addWidget(self.attendance_preview,1)
        self.attendance_issues=QTextEdit();self.attendance_issues.setReadOnly(True)
        self.attendance_issues.setMaximumHeight(110)
        al.addWidget(self.attendance_issues)
        self.details.addTab(attendance_page,'Phân tích chấm công')

        evidence_page=QWidget();el=QVBoxLayout(evidence_page)
        el.addWidget(QLabel('Liên kết ảnh tin nhắn/xác nhận với bảng công để người dùng đối chiếu; KHÔNG tự phê duyệt.'))
        self.evidence_items=QTableWidget(0,3)
        self.evidence_items.setHorizontalHeaderLabels(['Quan hệ','Chứng từ','Ghi chú'])
        self.evidence_items.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.evidence_items.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        el.addWidget(self.evidence_items,1)
        self.evidence_target=QComboBox();el.addWidget(self.evidence_target)
        self.evidence_relation=QComboBox()
        self.evidence_relation.addItem('Chứng từ hỗ trợ', 'SUPPORTS')
        self.evidence_relation.addItem('Có mâu thuẫn, cần soát', 'CONTRADICTS')
        self.evidence_relation.addItem('Chỉ để tham khảo', 'REFERENCE')
        el.addWidget(self.evidence_relation)
        self.evidence_note=QLineEdit();self.evidence_note.setPlaceholderText('Lý do liên kết / số ngày công cần xác minh')
        el.addWidget(self.evidence_note)
        eb=QHBoxLayout();eb.addWidget(self._button('Liên kết chứng từ',self.add_evidence))
        eb.addWidget(self._button('Xóa liên kết',self.remove_evidence));el.addLayout(eb)
        el.addWidget(QLabel('Gợi ý nội dung tin nhắn (không tự xác nhận công):'))
        self.llm_evidence=QCheckBox('Dùng AI GGUF offline (nếu đã nhập model)')
        el.addWidget(self.llm_evidence)
        self.claim_items=QTableWidget(0,3)
        self.claim_items.setHorizontalHeaderLabels(['Trạng thái','Nội dung trích','Cảnh báo'])
        self.claim_items.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.claim_items.setMaximumHeight(165)
        el.addWidget(self.claim_items)
        claim_actions=QHBoxLayout()
        claim_actions.addWidget(self._button('Phân tích tin nhắn OCR',self.analyze_message))
        claim_actions.addWidget(self._button('Duyệt nội dung trích',self.confirm_claim))
        claim_actions.addWidget(self._button('Loại bỏ đề xuất',self.reject_claim))
        el.addLayout(claim_actions)
        self.match_suggestions=QTextEdit()
        self.match_suggestions.setReadOnly(True);self.match_suggestions.setMaximumHeight(82)
        el.addWidget(self.match_suggestions)
        self.details.addTab(evidence_page,'Bằng chứng')

        text_page=QWidget();ttl=QVBoxLayout(text_page)
        self.ocr_text=QTextEdit();self.ocr_text.setReadOnly(False)
        ttl.addWidget(self.ocr_text)
        ttl.addWidget(self._button('Lưu văn bản OCR đã hiệu đính (giữ bản gốc)',self.save_corrected_text,True))
        ttl.addWidget(QLabel('Ứng viên mâu thuẫn giữa Tesseract/PaddleOCR — cần người duyệt:'))
        self.ocr_conflicts=QTextEdit();self.ocr_conflicts.setReadOnly(True)
        self.ocr_conflicts.setMaximumHeight(120);ttl.addWidget(self.ocr_conflicts)
        self.details.addTab(text_page,'Văn bản OCR')
        layout_page=QWidget();lll=QVBoxLayout(layout_page)
        self.docling_view=QTextEdit();self.docling_view.setReadOnly(True)
        lll.addWidget(self.docling_view)
        self.details.addTab(layout_page,'Docling / Cấu trúc')
        rl.addWidget(self._button('Xác nhận toàn bộ tài liệu',self.verify_document))
        split.addWidget(right)
        split.setSizes([240,620,600]);split.setChildrenCollapsible(False)

    def _create_learning(self):
        outer=QVBoxLayout(self.learning)
        text=QLabel('LEARNING ENGINE — Lưu sửa lỗi → Đề xuất → Kiểm thử → Duyệt → Kích hoạt')
        text.setStyleSheet('font-size:15pt; font-weight:700; color:#163F6B;')
        outer.addWidget(text)
        note=QLabel('Các quy tắc chưa kiểm chứng KHÔNG tự động sửa chứng từ. Quy tắc đã kích hoạt chỉ hiển thị như gợi ý để người dùng duyệt.')
        note.setWordWrap(True);outer.addWidget(note)
        self.rules_table=QTableWidget(0,6)
        self.rules_table.setHorizontalHeaderLabels(['Loại tài liệu','Trường','OCR sai','Đã sửa','Trạng thái','Số mẫu'])
        self.rules_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.rules_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.rules_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        outer.addWidget(self.rules_table,1)
        actions=QHBoxLayout()
        actions.addWidget(self._button('Làm mới',self.reload_rules))
        actions.addWidget(self._button('Kiểm thử quy tắc',self.test_rule))
        actions.addWidget(self._button('Phê duyệt',self.approve_rule))
        actions.addWidget(self._button('Kích hoạt',self.activate_rule))
        actions.addWidget(self._button('Vô hiệu hóa',self.disable_rule))
        actions.addStretch()
        outer.addLayout(actions)
        self.learning_notes=QTextEdit();self.learning_notes.setReadOnly(True)
        self.learning_notes.setMaximumHeight(130)
        self.learning_notes.setPlainText('Phiên bản này học bằng bộ nhớ chỉnh sửa có kiểm soát; chưa fine-tune trọng số mô hình OCR.')
        outer.addWidget(self.learning_notes)

    def _create_templates(self):
        root=QVBoxLayout(self.template_studio)
        label=QLabel('TEMPLATE STUDIO — Mẫu trích xuất trường dựa trên biểu thức chính quy')
        label.setStyleSheet('font-size:15pt; font-weight:700; color:#163F6B;')
        root.addWidget(label)
        note=QLabel('Chỉnh sửa JSON mẫu, thử OCR lại để áp dụng. Mẫu chỉ gợi ý trường; người dùng vẫn phải xác nhận. Không sử dụng biểu thức regex quá phức tạp.')
        note.setWordWrap(True);root.addWidget(note)
        self.template_choice=QComboBox();self.template_choice.currentIndexChanged.connect(self.choose_template)
        root.addWidget(self.template_choice)
        self.template_editor=QTextEdit();self.template_editor.setStyleSheet('font:10pt Consolas;')
        root.addWidget(self.template_editor,1)
        btns=QHBoxLayout()
        btns.addWidget(self._button('Mẫu chấm công mặc định',self.default_template))
        btns.addWidget(self._button('Mẫu mới',self.new_template))
        btns.addWidget(self._button('Lưu mẫu',self.save_template,True))
        btns.addStretch();root.addLayout(btns)

    def reload_templates(self):
        self.template_choice.blockSignals(True)
        self.template_choice.clear()
        for row in self.repo.list_templates():
            self.template_choice.addItem(row['name'],row['spec_json'])
        self.template_choice.blockSignals(False)
        if self.template_choice.count():self.choose_template(0)
        else:self.default_template()

    def choose_template(self,index):
        data=self.template_choice.currentData()
        if data:self.template_editor.setPlainText(json.dumps(json.loads(data),ensure_ascii=False,indent=2))

    def default_template(self):
        self.template_editor.setPlainText(json.dumps(DEFAULT_ATTENDANCE_TEMPLATE,ensure_ascii=False,indent=2))

    def new_template(self):
        self.template_editor.setPlainText(json.dumps({
            'id':'my-template-v1','name':'Mẫu chứng từ mới','document_type':'generic',
            'fields':[{'key':'field_1','label':'Trường 1','pattern':'(?i)Số\\s*[:\\s]+([A-Z0-9-]+)','group':1}]},
            ensure_ascii=False,indent=2))

    def save_template(self):
        try:
            spec=json.loads(self.template_editor.toPlainText())
            self.repo.save_template(spec)
            self.reload_templates()
            self.status.showMessage(f'Đã lưu mẫu: {spec["name"]}')
        except Exception as e:QMessageBox.warning(self,'Mẫu không hợp lệ',str(e))

    def import_files(self):
        files,_=QFileDialog.getOpenFileNames(self,'Nhập chứng từ','','Hình ảnh/PDF (*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.pdf)')
        self._import_many(files)

    def import_folder(self):
        folder=QFileDialog.getExistingDirectory(self,'Chọn thư mục chứng từ')
        if folder:
            files=[p for p in Path(folder).iterdir() if p.suffix.lower() in {'.jpg','.jpeg','.png','.bmp','.tif','.tiff','.pdf'}]
            self._import_many(files)

    def _import_many(self,files):
        added=0;already=0;errors=[]
        for src in files:
            try:
                _,is_new=self.repo.add_file(src)
                added+=int(is_new);already+=int(not is_new)
            except Exception as e:errors.append(f'{Path(src).name}: {e}')
        self.reload_documents()
        self.status.showMessage(f'Đã nhập {added} tài liệu, {already} file trùng; lỗi: {len(errors)}')
        if errors:QMessageBox.warning(self,'Lỗi nhập liệu','\n'.join(errors[:8]))

    def reload_documents(self):
        old=self.current_id
        self.docs.blockSignals(True);self.docs.clear()
        for doc in self.repo.list_docs():
            item=QListWidgetItem(f"{doc['original_name']}\n{doc['status']} · {doc['document_type']}")
            item.setData(Qt.ItemDataRole.UserRole,doc['id'])
            self.docs.addItem(item)
            if doc['id']==old:self.docs.setCurrentItem(item)
        self.docs.blockSignals(False)
        self.filter_docs(self.filter.text())
        self.reload_evidence_targets()

    def reload_evidence_targets(self):
        self.evidence_target.clear()
        for doc in self.repo.list_docs():
            if doc['id']!=self.current_id:
                self.evidence_target.addItem(doc['original_name'],doc['id'])

    def reload_evidence(self):
        self.evidence_items.setRowCount(0)
        if self.current_id is None:return
        self.refresh_claims()
        for link in self.repo.list_evidence(self.current_id):
            row=self.evidence_items.rowCount();self.evidence_items.insertRow(row)
            item=QTableWidgetItem(link['relationship'])
            item.setData(Qt.ItemDataRole.UserRole,link['id'])
            self.evidence_items.setItem(row,0,item)
            self.evidence_items.setItem(row,1,QTableWidgetItem(link['related_filename']))
            self.evidence_items.setItem(row,2,QTableWidgetItem(link['note']))

    def refresh_claims(self):
        self.claim_items.setRowCount(0)
        if not self.current_id:return
        for rec in self.repo.list_evidence_claims(self.current_id):
            row=self.claim_items.rowCount();self.claim_items.insertRow(row)
            status=QTableWidgetItem(rec['review_state'])
            status.setData(Qt.ItemDataRole.UserRole,rec['id'])
            claim=rec['claim']
            self.claim_items.setItem(row,0,status)
            self.claim_items.setItem(row,1,QTableWidgetItem(claim.get('excerpt','')[:250]))
            self.claim_items.setItem(row,2,QTableWidgetItem('; '.join(claim.get('warnings',[]))[:220]))

    def analyze_message(self):
        if not self.current_result or not self.current_id:return
        text='\n'.join(p.get('text','') for p in self.current_result['pages'])
        # Verified personnel names from available DB fields only; no invented identities.
        names=[str(f['final_value']) for d in self.repo.list_docs() for f in self.repo.get_fields(d['id'])
               if f['verified'] and ('ten' in f['field_key'].casefold() or 'name' in f['field_key'].casefold())]
        if self.llm_evidence.isChecked():
            if self.evidence_worker and self.evidence_worker.isRunning():return
            self.evidence_doc=self.current_id
            self.evidence_worker=EvidenceWorker(text)
            self.evidence_worker.done.connect(self.evidence_llm_done)
            self.evidence_worker.failed.connect(lambda err:QMessageBox.warning(self,'AI GGUF offline',err))
            self.evidence_worker.start()
            self.status.showMessage('AI GGUF đang xử lý nội dung cục bộ...')
            return
        claims=extract_evidence_claims(text,names)
        self._save_claim_suggestions(claims)

    def evidence_llm_done(self,claims):
        if self.current_id!=self.evidence_doc:return
        self._save_claim_suggestions(claims)

    def _save_claim_suggestions(self,claims):
        if not claims:
            QMessageBox.information(self,'Không có gợi ý','OCR chưa tìm thấy nội dung nghiệp vụ đáng tin. Hãy kiểm tra văn bản và sửa OCR trước.')
            return
        try:
            self.repo.add_evidence_claims(self.current_id,claims,run_id=self.current_result.get('run_id'))
            self.refresh_claims()
            documents=[]
            for d in self.repo.list_docs():
                r=self.repo.get_result(d['id'])
                documents.append({'id':d['id'],'text':'\n'.join(p.get('text','') for p in (r or {}).get('pages',[]))})
            suggestions=suggest_document_matches(claims,documents,source_id=self.current_id)
            self.match_suggestions.setPlainText('Đề xuất liên kết tham khảo (phải kiểm tra):\n'+
                '\n'.join(x['reason']+' — '+str(self.repo.get(x['document_id'])['original_name']) for x in suggestions[:20]))
            self.status.showMessage(f'Đã tạo {len(claims)} đề xuất từ chứng từ; không tự cập nhật công/lương.')
        except Exception as exc:QMessageBox.warning(self,'Phân tích bằng chứng',str(exc))

    def _review_claim(self,approve:bool):
        row=self.claim_items.currentRow()
        if self.current_id is None or row<0:return
        claim_id=self.claim_items.item(row,0).data(Qt.ItemDataRole.UserRole)
        try:
            self.repo.review_evidence_claim(self.current_id,claim_id,approve)
            self.refresh_claims()
        except Exception as exc:QMessageBox.warning(self,'Duyệt trích đoạn',str(exc))

    def confirm_claim(self):
        QMessageBox.information(self,'Chỉ duyệt nội dung','Xác nhận chỉ công nhận nội dung trích từ tin nhắn. KHÔNG tạo điều chỉnh công hoặc phê duyệt tiền lương.')
        self._review_claim(True)

    def reject_claim(self):self._review_claim(False)

    def save_corrected_text(self):
        if self.current_id is None or not self.current_result:return
        text=self.ocr_text.toPlainText()
        existing=self.current_result['pages'][self.current_page]['text']
        if text==existing:
            self.status.showMessage('Nội dung OCR chưa thay đổi.')
            return
        answer=QMessageBox.question(self,'Hiệu đính OCR',
            'Lưu bản sửa riêng để phân tích nội dung? Bản OCR gốc và ảnh gốc vẫn giữ nguyên. Các đoạn sửa cần được soát xét.')
        if answer!=QMessageBox.StandardButton.Yes:return
        try:
            self.repo.correct_page_text(self.current_id,self.current_page,text)
            self.current_result=self.repo.get_result(self.current_id)
            self.populate_result()
            self.status.showMessage('Đã lưu bản hiệu đính OCR; nội dung mới có thể dùng để kiểm tra tin nhắn.')
        except Exception as exc:QMessageBox.warning(self,'Hiệu đính OCR',str(exc))

    def run_unwarp(self):
        if not self.current_id or self.preview.image is None:return
        if self.unwarp_worker and self.unwarp_worker.isRunning():return
        self.unwarp_doc=self.current_id
        self.unwarp_worker=UnwarpWorker(self.preview.image.copy())
        self.unwarp_worker.done.connect(self.unwarp_done)
        self.unwarp_worker.failed.connect(lambda err:QMessageBox.warning(self,'UVDoc offline',err))
        self.unwarp_worker.start()
        self.status.showMessage('Đang chỉnh cong trang bằng UVDoc offline; chưa có mapping tọa độ ngược.')

    def unwarp_done(self,result):
        if self.current_id!=self.unwarp_doc:return
        dialog=QDialog(self);dialog.setWindowTitle('Ảnh làm phẳng — CHƯA KIỂM DUYỆT')
        dialog.resize(730,780)
        layout=QVBoxLayout(dialog)
        layout.addWidget(QLabel('UVDoc tạo ảnh tham khảo. Hãy kiểm tra, lưu thành file mới rồi nhập lại nếu phù hợp. Không tự sửa file gốc.'))
        image=result.copy();image.thumbnail((670,640))
        raw=image.convert('RGB').tobytes('raw','RGB')
        qim=QImage(raw,image.width,image.height,image.width*3,QImage.Format.Format_RGB888).copy()
        picture=QLabel();picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        picture.setPixmap(QPixmap.fromImage(qim))
        layout.addWidget(picture)
        buttons=QHBoxLayout()
        def save():
            name='anh-da-lam-phang-chua-duyet.png'
            path,_=QFileDialog.getSaveFileName(dialog,'Lưu ảnh dẫn xuất',name,'PNG (*.png)')
            if path:
                try:result.save(path)
                except Exception as exc:QMessageBox.warning(dialog,'Không thể lưu',str(exc))
                else:dialog.accept()
        buttons.addWidget(self._button('Lưu ảnh PNG để kiểm tra / nhập lại',save,True))
        buttons.addWidget(self._button('Đóng',dialog.reject))
        layout.addLayout(buttons)
        dialog.exec()

    def run_handwriting(self):
        if not self.current_id or self.preview.selection is None:
            QMessageBox.information(self,'Chưa chọn vùng','Kéo chuột trên ảnh để chọn vùng chữ viết tay rồi bấm nút này.')
            return
        if self.htr_worker and self.htr_worker.isRunning():return
        crop=self.preview.crop_selection()
        if crop is None:return
        self.htr_bbox=list(self.preview.selection)
        self.htr_page=self.current_page;self.htr_doc=self.current_id
        self.htr_worker=HandwritingWorker(crop)
        self.htr_worker.done.connect(self.handwriting_done)
        self.htr_worker.failed.connect(lambda err:QMessageBox.warning(self,'OCR chữ viết tay',err))
        self.htr_worker.start()
        self.status.showMessage('Đang đọc vùng chữ viết tay bằng model offline...')

    def handwriting_done(self,candidate):
        if self.current_id!=self.htr_doc:return
        key,ok=QInputDialog.getText(self,'Kết quả chữ viết tay – chưa duyệt',
                f"Ứng viên: {candidate['text']}\nNhập mã trường mới (không ghi đè trường hiện có):")
        if not ok or not key.strip():return
        try:
            self.repo.add_candidate_field(self.current_id,key.strip(),key.strip(),candidate['text'],
                                          self.htr_page,self.htr_bbox)
            self.current_result=self.repo.get_result(self.current_id)
            self.populate_result()
            self.status.showMessage('Đã lưu ứng viên OCR viết tay CHƯA DUYỆT.')
        except Exception as exc:QMessageBox.warning(self,'Lưu ứng viên viết tay',str(exc))

    def add_evidence(self):
        if not self.current_id or not self.evidence_target.currentData():return
        try:
            self.repo.add_evidence(self.current_id,self.evidence_target.currentData(),
                self.evidence_relation.currentData(),self.evidence_note.text())
            self.current_result=self.repo.get_result(self.current_id)
            self.reload_evidence();self.evidence_note.clear()
            self.status.showMessage('Đã liên kết chứng từ. Chỉ là bằng chứng, không tự ghi công.')
        except Exception as ex:QMessageBox.warning(self,'Liên kết chứng từ',str(ex))

    def remove_evidence(self):
        selected=self.evidence_items.currentRow()
        if not self.current_id or selected<0:return
        link_id=self.evidence_items.item(selected,0).data(Qt.ItemDataRole.UserRole)
        try:
            self.repo.remove_evidence(self.current_id,link_id)
            self.current_result=self.repo.get_result(self.current_id)
            self.reload_evidence()
        except Exception as ex:QMessageBox.warning(self,'Xóa liên kết',str(ex))

    def filter_docs(self,text):
        for i in range(self.docs.count()):
            item=self.docs.item(i);item.setHidden(text.casefold() not in item.text().casefold())

    def document_selected(self,item,previous):
        if item is None:return
        doc_id=item.data(Qt.ItemDataRole.UserRole)
        self.current_id=doc_id
        record=self.repo.get(doc_id)
        self.current_result=self.repo.get_result(doc_id)
        self.doc_note.setText(f"{record['status']}\nSHA-256: {record['sha256'][:20]}…")
        self.type_combo.blockSignals(True)
        index=self.type_combo.findText(record['document_type'])
        if index<0:
            self.type_combo.addItem(record['document_type']);index=self.type_combo.findText(record['document_type'])
        self.type_combo.setCurrentIndex(index);self.type_combo.blockSignals(False)
        self.reload_evidence_targets()
        self.populate_result()

    def populate_result(self):
        self.field_table.setRowCount(0)
        self.table_choice.blockSignals(True);self.table_choice.clear()
        if not self.current_result:
            self.page_select.blockSignals(True);self.page_select.clear();self.page_select.addItem('Trang 1',0)
            self.page_select.blockSignals(False)
            self.table_choice.blockSignals(False)
            self.ocr_text.clear();self.docling_view.clear();self.preview.set_image(None)
            self.attendance_preview.setRowCount(0)
            self.attendance_issues.clear();self.reload_evidence()
            return
        self.page_select.blockSignals(True);self.page_select.clear()
        for p in self.current_result['pages']:
            self.page_select.addItem(str(p['number']+1),p['number'])
            for t in p['tables']:
                self.table_choice.addItem(f"Trang {p['number']+1} – Bảng {t['table_id']}",(p['number'],t['table_id']))
        self.page_select.blockSignals(False);self.table_choice.blockSignals(False)
        for f in self.current_result['fields']:
            n=self.field_table.rowCount();self.field_table.insertRow(n)
            self.field_table.setItem(n,0,QTableWidgetItem(f['label']))
            value=QTableWidgetItem(str(f['value']));value.setData(Qt.ItemDataRole.UserRole,f['key'])
            self.field_table.setItem(n,1,value)
            flag=QTableWidgetItem('Đã duyệt' if f['verified'] else 'Chưa duyệt')
            flag.setFlags(flag.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.field_table.setItem(n,2,flag)
            pg=QTableWidgetItem(str(f['page']+1));pg.setFlags(pg.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.field_table.setItem(n,3,pg)
        if self.table_choice.count():self.select_table(0)
        else:
            self.table_grid.setRowCount(0);self.table_grid.setColumnCount(0)
            self.table_status.setText('Chưa phát hiện bảng có lưới đủ rõ; sử dụng tab Văn bản OCR hoặc bổ sung trường thủ công.')
        layout=self.current_result.get('layout_extraction',{})
        self.docling_view.setPlainText(layout.get('markdown','Chưa chạy Docling cho tài liệu này.') if layout else 'Chưa chạy Docling cho tài liệu này.')
        self.change_page(0)
        self.reload_attendance()
        self.reload_evidence()

    def reload_attendance(self):
        self.attendance_preview.setRowCount(0)
        issues=[]
        for table in (self.current_result or {}).get('attendance_analysis',[]):
            issues.extend([f"Trang {table['page']+1}: {v}" for v in table['issues']])
            for record in table['records'][:3000]:
                n=self.attendance_preview.rowCount();self.attendance_preview.insertRow(n)
                values=[str(table['page']+1), record.get('person') or '',str(record['day']),
                        record['metric'],str(record['raw']),
                        '' if record['value'] is None else str(record['value']),
                        'Có' if table['verified'] else 'Chưa']
                for c,value in enumerate(values):self.attendance_preview.setItem(n,c,QTableWidgetItem(value))
        self.attendance_issues.setPlainText('\n'.join(issues) if issues else 'Chưa có cảnh báo từ bảng đã phân tích.')

    def change_page(self,index):
        if self.current_id is None:return
        number=self.page_select.currentData()
        if number is None:number=0
        self.current_page=number
        result=self.current_result
        if result and number < len(result['pages']):
            p=result['pages'][number]
            self.ocr_text.setPlainText(p['text'])
            conflicts=p.get('ocr_alternatives',[])
            self.ocr_conflicts.setPlainText('\n'.join(
                f"Tesseract: {v['tesseract']}  |  Paddle: {v['paddle']}" for v in conflicts) or 'Không phát hiện vùng mâu thuẫn; vẫn cần kiểm duyệt thông tin quan trọng.')
            angle=p.get('orientation',0)
        else:
            self.ocr_text.clear();self.ocr_conflicts.clear();angle=0
        try:
            image=render_preview(self.repo.get(self.current_id)['original_path'],number,angle,geometry=p.get('geometry') if result else None)
            self.preview.set_image(image)
            self.preview.set_highlights([])
        except Exception as ex:self.status.showMessage(str(ex))

    def select_table(self,index):
        self.table_ref=None
        selected=self.table_choice.currentData()
        if selected is None or not self.current_result:return
        pn,tid=selected
        t=next((t for p in self.current_result['pages'] for t in p['tables'] if t['table_id']==tid and p['number']==pn),None)
        if not t:return
        self.table_ref=t
        grid=t['grid']
        suggestions={(s['row'],s['col']):s for s in t.get('cell_suggestions',[])}
        self.table_grid.blockSignals(True)
        self.table_grid.setRowCount(len(grid));self.table_grid.setColumnCount(max(map(len,grid),default=0))
        for row_index,row in enumerate(grid):
            for col_index,v in enumerate(row):
                item=QTableWidgetItem(str(v))
                hint=suggestions.get((row_index,col_index))
                if hint and not t.get('verified'):
                    item.setBackground(QColor('#FFF2CA'))
                    item.setToolTip('ĐỀ XUẤT OCR, CHƯA DUYỆT — '+hint['method']+'; kiểm tra lại trên ảnh gốc.')
                self.table_grid.setItem(row_index,col_index,item)
        self.table_grid.blockSignals(False)
        note=f"{len(grid)} hàng × {max(map(len,grid),default=0)} cột | "
        note+=('Đã duyệt' if t.get('verified') else 'Chưa duyệt; ô vàng là gợi ý OCR chưa xác nhận.')
        if t.get('geometry_warning'): note+=' | '+t['geometry_warning']
        self.table_status.setText(note)
        if self.page_select.currentData()!=pn:self.page_select.setCurrentIndex(pn)

    def add_grid_row(self):
        row=self.table_grid.currentRow()
        self.table_grid.insertRow(row+1 if row>=0 else self.table_grid.rowCount())

    def add_grid_column(self):
        col=self.table_grid.currentColumn()
        self.table_grid.insertColumn(col+1 if col>=0 else self.table_grid.columnCount())

    def remove_grid_row(self):
        if self.table_grid.rowCount()>1 and self.table_grid.currentRow()>=0:
            self.table_grid.removeRow(self.table_grid.currentRow())

    def remove_grid_column(self):
        if self.table_grid.columnCount()>1 and self.table_grid.currentColumn()>=0:
            self.table_grid.removeColumn(self.table_grid.currentColumn())

    def highlight_cell(self,row,col,prevrow,prevcol):
        if not self.table_ref or row<0 or col<0:return
        boxes=self.table_ref['cell_boxes']
        if row<len(boxes) and col<len(boxes[row]):
            self.preview.set_highlights([boxes[row][col]])

    def highlight_field(self):
        index=self.field_table.currentRow()
        if index<0 or not self.current_result:return
        field=self.current_result['fields'][index]
        if field['page']!=self.page_select.currentData():
            self.page_select.setCurrentIndex(field['page'])
        self.preview.set_highlights([field['bbox']] if field.get('bbox') else [])
        suggestions=self.repo.propose_suggestions(self.current_id,field['key'],str(field['value']))
        if suggestions:
            self.suggestions.setText('Learning Engine gợi ý (không tự sửa): '+ ', '.join(v['value'] for v in suggestions[:3]))
        else:self.suggestions.setText('Không có quy tắc học đã kích hoạt cho trường này.')

    def set_doc_type(self,index):
        if self.current_id is None:return
        typ=self.type_combo.currentText()
        if typ:
            self.repo.change_document_type(self.current_id,typ)
            self.status.showMessage('Đã lưu loại tài liệu. OCR cũ không bị xóa.')

    def add_field(self):
        if self.current_id is None:return
        label,ok=QInputDialog.getText(self,'Thêm trường dữ liệu','Tên trường:')
        if not ok or not label.strip():return
        val,ok=QInputDialog.getText(self,'Giá trị','Nhập giá trị trên chứng từ:')
        if not ok:return
        self.repo.add_field(self.current_id,label,val,self.current_page)
        self.current_result=self.repo.get_result(self.current_id)
        self.populate_result()

    def save_fields(self):
        if not self.current_id or not self.current_result:return
        try:
            for n in range(self.field_table.rowCount()):
                entry=self.field_table.item(n,1)
                if entry:
                    self.repo.verify_field(self.current_id,entry.data(Qt.ItemDataRole.UserRole),entry.text())
            self.current_result=self.repo.get_result(self.current_id)
            self.populate_result();self.reload_rules();self.reload_documents()
            self.status.showMessage('Đã lưu, xác nhận trường và ghi lại các hiệu chỉnh làm dữ liệu học.')
        except Exception as ex:QMessageBox.critical(self,'Lỗi khi lưu trường',str(ex))

    def save_table(self):
        if not self.table_ref or not self.current_id:return
        grid=[]
        for r in range(self.table_grid.rowCount()):
            row=[]
            for c in range(self.table_grid.columnCount()):
                item=self.table_grid.item(r,c)
                row.append(item.text().strip() if item else '')
            grid.append(row)
        self.repo.table_edit(self.current_id,self.table_ref['table_id'],self.table_ref['page'],grid,True)
        self.current_result=self.repo.get_result(self.current_id)
        self.populate_result();self.reload_rules();self.reload_documents()
        self.status.showMessage('Đã duyệt bảng, lưu các ô hiệu chỉnh và đề xuất quy tắc học.')

    def verify_document(self):
        if self.current_id is None:return
        try:
            self.repo.verify_document(self.current_id)
            self.current_result=self.repo.get_result(self.current_id)
            self.reload_documents()
            QMessageBox.information(self,'Đã xác nhận','Tài liệu đã được đánh dấu VERIFIED. Hãy kiểm tra lại trước khi nhập phần mềm lương/kế toán.')
        except Exception as ex:QMessageBox.warning(self,'Chưa thể xác nhận',str(ex))

    def start_deep_ocr(self):
        self._start_processing(deep=True)

    def start_ocr(self):
        self._start_processing(deep=False)

    def _start_processing(self,deep=False):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self,'Đang xử lý','Vui lòng chờ lượt OCR hiện tại hoàn thành.');return
        if not self.current_id:
            QMessageBox.information(self,'Chưa chọn file','Hãy nhập và chọn một ảnh hoặc PDF.');return
        doc=self.repo.get(self.current_id)
        # Preflight optional engines BEFORE changing document status or starting
        # a worker.  Base Windows installer intentionally ships Tesseract only.
        selected_engine=self.engine_mode.currentData() or 'tesseract'
        use_docling=self.docling_box.isChecked()
        fallback_notes=[]
        if selected_engine in ('paddle','hybrid') or use_docling:
            report=engine_report()
            models=report.get('models',{})
            libraries=report.get('libraries',{})
            if selected_engine in ('paddle','hybrid'):
                missing=[name for name in ('paddle_detection','paddle_recognition') if not models.get(name)]
                if not libraries.get('paddleocr'):
                    missing.append('thư viện PaddleOCR')
                if not libraries.get('paddle'):
                    missing.append('thư viện PaddlePaddle')
                if missing:
                    detail=', '.join(missing)
                    answer=QMessageBox.question(
                        self,'Thiếu PaddleOCR offline',
                        'Bản Windows hiện tại không có đủ bộ PaddleOCR offline: '
                        +detail+'\\n\\n'
                        'Chọn Yes để dùng Tesseract tiếng Việt sẵn có, '
                        'hoặc No để giữ chế độ đang chọn và dừng OCR. '
                        'Kết quả đã duyệt sẽ không bị thay đổi.',
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes)
                    if answer!=QMessageBox.StandardButton.Yes:
                        self.status.showMessage('Đã hủy OCR: thiếu PaddleOCR offline.')
                        return
                    selected_engine='tesseract'
                    self.engine_mode.setCurrentIndex(self.engine_mode.findData('tesseract'))
                    fallback_notes.append('Đã chuyển PaddleOCR/Hybrid sang Tesseract (thiếu model offline).')
            if use_docling and (not models.get('docling') or not libraries.get('docling')):
                self.docling_box.setChecked(False)
                use_docling=False
                fallback_notes.append('Đã tắt Docling vì thiếu model/thư viện offline.')
        try:
            check_ocr_ready()
        except Exception as e:
            QMessageBox.critical(self,'Chưa sẵn sàng OCR',
                'Không khởi động được Tesseract tiếng Việt/Anh. '+str(e))
            return
        self.repo.set_status(self.current_id,'PROCESSING')
        self.worker=ProcessWorker(doc['original_path'],doc['id'],doc['sha256'],
            [json.loads(x['spec_json']) for x in self.repo.list_templates()],deep,doc['document_type'],
            selected_engine,use_docling,self.perspective_box.isChecked())
        self.worker.progress.connect(self.processing_progress)
        self.worker.done.connect(self.finished_ocr)
        self.worker.failed.connect(self.ocr_failed)
        self.progress.setVisible(True);self.progress.setRange(0,0)
        self.worker.start()
        self.status.showMessage((' '.join(fallback_notes)+' ' if fallback_notes else '')+'Đang OCR offline, không sử dụng mạng Internet...')

    def processing_progress(self,part,total):
        self.progress.setRange(0,max(1,total));self.progress.setValue(part)
        self.status.showMessage(f'Đã xử lý {part}/{total} trang')

    def finished_ocr(self,result):
        self.repo.save_result(result)
        self.progress.setVisible(False)
        self.current_result=self.repo.get_result(result.document_id)
        self.populate_result();self.reload_documents()
        self.status.showMessage(f'OCR hoàn thành: {len(result.pages)} trang. Hãy kiểm tra và xác nhận dữ liệu.')

    def ocr_failed(self,message):
        if self.current_id:self.repo.set_status(self.current_id,'FAILED')
        self.progress.setVisible(False)
        QMessageBox.critical(self,'Không thể OCR',message)
        self.reload_documents()

    def export_data(self):
        if not self.current_id:return
        result=self.repo.get_result(self.current_id)
        if not result:
            QMessageBox.information(self,'Chưa có dữ liệu','Hãy OCR tài liệu trước.');return
        if result['status']!='VERIFIED':
            response=QMessageBox.warning(self,'Chưa kiểm duyệt','Tài liệu chưa VERIFIED. Vẫn xuất bản có trạng thái chưa duyệt?',
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if response!=QMessageBox.StandardButton.Yes:return
        name=Path(self.repo.get(self.current_id)['original_name']).stem
        path,_=QFileDialog.getSaveFileName(self,'Xuất dữ liệu',str(self.repo.home/'exports'/f'{name}.xlsx'),
                                          'Excel (*.xlsx);;JSON (*.json);;CSV (*.csv);;Text (*.txt)')
        if path:
            try:
                export_result(result,path)
                self.status.showMessage(f'Đã xuất: {path}')
            except Exception as e:QMessageBox.critical(self,'Xuất thất bại',str(e))

    def backup_db(self):
        path,_=QFileDialog.getSaveFileName(self,'Sao lưu cơ sở dữ liệu',str(self.repo.home/'backups'/'hak-ocr-backup.zip'),'ZIP (*.zip)')
        if path:
            try:
                backup_complete(self.repo,Path(path))
                QMessageBox.information(self,'Sao lưu đầy đủ','Đã lưu CSDL và tài liệu gốc vào ZIP có checksum. Phục hồi được thực hiện bằng CLI vào thư mục trống.')
            except Exception as e:QMessageBox.critical(self,'Lỗi sao lưu',str(e))

    def check_engine(self):
        try:
            report=engine_report()
            lang=check_ocr_ready()
            QMessageBox.information(self,'OCR Offline',f'Tesseract: {lang}\n'
                f'Model cục bộ: {json.dumps(report["models"],ensure_ascii=False)}\n'
                f'Thư viện: {json.dumps(report["libraries"],ensure_ascii=False)}\n'
                'Mọi model nâng cao phải được cài sẵn; không tự tải về.')
        except Exception as e:QMessageBox.warning(self,'OCR Offline',str(e))

    def reload_rules(self):
        self.rule_cache=self.repo.list_rules()
        self.rules_table.setRowCount(len(self.rule_cache))
        for ri,rule in enumerate(self.rule_cache):
            for ci,value in enumerate((rule['document_type'],rule['field_key'],rule['from_value'],rule['to_value'],rule['state'],rule['example_count'])):
                self.rules_table.setItem(ri,ci,QTableWidgetItem(str(value)))

    def selected_rule(self):
        index=self.rules_table.currentRow()
        return self.rule_cache[index] if 0<=index<len(self.rule_cache) else None

    def test_rule(self):
        rule=self.selected_rule()
        if not rule:return
        ok,report=self.repo.test_learning_rule(rule['id'])
        self.learning_notes.setPlainText(report)
        self.reload_rules()

    def approve_rule(self):
        self.transition_rule('APPROVED')

    def activate_rule(self):
        self.transition_rule('ACTIVE')

    def disable_rule(self):
        self.transition_rule('DISABLED')

    def transition_rule(self,state):
        rule=self.selected_rule()
        if not rule:return
        try:
            self.repo.change_rule_state(rule['id'],state)
            self.reload_rules()
        except Exception as e:QMessageBox.warning(self,'Quy tắc học',str(e))

    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self,'Đang xử lý','Chờ OCR kết thúc trước khi đóng.')
            event.ignore();return
        self.repo.close();event.accept()


def main():
    app=QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet(APP_STYLESHEET)
    w=MainWindow();w.show()
    return app.exec()
