from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .constants import APP_NAME, ROUTING_CLASSES, get_default_db_path
from .db import Database
from .exporter import export_manifest
from .roster import RosterValidationError, load_roster
from .scanner import scan_image_root


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 840)

        self.settings = QSettings('RickeyJGreen', APP_NAME)
        self.database = Database(get_default_db_path())
        self.current_job_id: int | None = None
        self.folder_rows_by_table_row: dict[int, int] = {}
        self.current_folder_id: int | None = None

        self._build_ui()
        self._restore_settings()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._persist_settings()
        self.database.close()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        controls_box = QGroupBox('Job setup')
        controls_layout = QGridLayout(controls_box)

        self.roster_path_edit = QLineEdit()
        self.image_root_edit = QLineEdit()
        self.status_log = QTextEdit()
        self.status_log.setReadOnly(True)
        self.status_log.setMaximumHeight(140)

        browse_roster_button = QPushButton('Browse Ready_ CSV')
        browse_roster_button.clicked.connect(self._choose_roster_file)
        browse_root_button = QPushButton('Browse Image Root')
        browse_root_button.clicked.connect(self._choose_image_root)
        ingest_button = QPushButton('Ingest Job')
        ingest_button.clicked.connect(self._ingest_job)
        export_button = QPushButton('Export Manifest')
        export_button.clicked.connect(self._export_manifest)
        save_review_button = QPushButton('Save Folder Review')
        save_review_button.clicked.connect(self._save_folder_review)

        controls_layout.addWidget(QLabel('Ready_ roster CSV'), 0, 0)
        controls_layout.addWidget(self.roster_path_edit, 0, 1)
        controls_layout.addWidget(browse_roster_button, 0, 2)
        controls_layout.addWidget(QLabel('Image root folder'), 1, 0)
        controls_layout.addWidget(self.image_root_edit, 1, 1)
        controls_layout.addWidget(browse_root_button, 1, 2)
        controls_layout.addWidget(ingest_button, 2, 1)
        controls_layout.addWidget(export_button, 2, 2)
        controls_layout.addWidget(save_review_button, 2, 0)

        layout.addWidget(controls_box)

        body_layout = QHBoxLayout()
        self.folders_table = QTableWidget(0, 7)
        self.folders_table.setHorizontalHeaderLabels([
            'Folder', 'Matched', 'Student', 'Group', 'Access Code', 'Barcode', 'Images'
        ])
        self.folders_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.folders_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.folders_table.itemSelectionChanged.connect(self._load_selected_folder_images)
        self.folders_table.verticalHeader().setVisible(False)

        self.images_table = QTableWidget(0, 6)
        self.images_table.setHorizontalHeaderLabels([
            'Order', 'Filename', 'Class Label', 'Final', 'Review Reason', 'Path'
        ])
        self.images_table.verticalHeader().setVisible(False)

        body_layout.addWidget(self.folders_table, stretch=3)
        body_layout.addWidget(self.images_table, stretch=4)
        layout.addLayout(body_layout)
        layout.addWidget(QLabel('Activity'))
        layout.addWidget(self.status_log)

        self.setCentralWidget(root)

    def _restore_settings(self) -> None:
        self.roster_path_edit.setText(self.settings.value('roster_path', '', str))
        self.image_root_edit.setText(self.settings.value('image_root', '', str))

    def _persist_settings(self) -> None:
        self.settings.setValue('roster_path', self.roster_path_edit.text().strip())
        self.settings.setValue('image_root', self.image_root_edit.text().strip())

    def _choose_roster_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Ready_ CSV', '', 'CSV Files (*.csv)')
        if file_path:
            self.roster_path_edit.setText(file_path)

    def _choose_image_root(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, 'Select image root')
        if directory:
            self.image_root_edit.setText(directory)

    def _append_status(self, message: str) -> None:
        self.status_log.append(message)

    def _clear_folder_selection_state(self) -> None:
        self.current_folder_id = None
        self.folder_rows_by_table_row.clear()
        self.folders_table.clearSelection()
        self.images_table.setRowCount(0)

    def _ingest_job(self) -> None:
        roster_path = self.roster_path_edit.text().strip()
        image_root = self.image_root_edit.text().strip()
        if not roster_path or not image_root:
            QMessageBox.warning(self, APP_NAME, 'Choose both a Ready_ CSV and an image root folder.')
            return

        try:
            roster = load_roster(roster_path)
            scans = scan_image_root(image_root, roster)
            self.current_job_id = self.database.create_job(roster, image_root, scans)
            self._populate_folders_table()
            self._append_status(
                f'Job {self.current_job_id} ingested: {len(roster.rows)} roster rows, {len(scans)} folders scanned.'
            )
        except (FileNotFoundError, NotADirectoryError, RosterValidationError, OSError, ValueError) as exc:
            self._clear_folder_selection_state()
            QMessageBox.critical(self, APP_NAME, str(exc))
            self._append_status(f'Ingest failed: {exc}')

    def _populate_folders_table(self) -> None:
        if self.current_job_id is None:
            self._clear_folder_selection_state()
            return
        folders = self.database.fetch_folders(self.current_job_id)
        self._clear_folder_selection_state()
        self.folders_table.setRowCount(len(folders))
        for table_row, folder in enumerate(folders):
            self.folder_rows_by_table_row[table_row] = int(folder['id'])
            student_name = f"{folder['first_name'] or ''} {folder['last_name'] or ''}".strip()
            matched_text = 'Yes' if int(folder['matched']) else 'No'
            values = [
                folder['folder_name'],
                matched_text,
                student_name,
                folder['group_name'] or '',
                folder['access_code'] or folder['folder_key'],
                folder['barcode_raw'] or '',
                str(folder['image_count']),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.folders_table.setItem(table_row, column, item)
        self.folders_table.resizeColumnsToContents()
        if folders:
            self.folders_table.selectRow(0)

    def _load_selected_folder_images(self) -> None:
        selected_items = self.folders_table.selectionModel().selectedRows()
        if not selected_items:
            self.current_folder_id = None
            self.images_table.setRowCount(0)
            return
        table_row = selected_items[0].row()
        folder_id = self.folder_rows_by_table_row.get(table_row)
        if folder_id is None:
            self.current_folder_id = None
            self.images_table.setRowCount(0)
            return
        self.current_folder_id = folder_id
        images = self.database.fetch_images_for_folder(folder_id)
        self.images_table.setRowCount(len(images))
        for row_index, image in enumerate(images):
            order_item = QTableWidgetItem(str(image['order_index']))
            filename_item = QTableWidgetItem(str(image['filename']))
            reason_item = QTableWidgetItem(str(image['review_reason']))
            path_item = QTableWidgetItem(str(image['file_path']))
            for item in (order_item, filename_item, reason_item, path_item):
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)

            self.images_table.setItem(row_index, 0, order_item)
            self.images_table.setItem(row_index, 1, filename_item)
            self.images_table.setItem(row_index, 4, reason_item)
            self.images_table.setItem(row_index, 5, path_item)

            combo = QComboBox()
            combo.addItems(ROUTING_CLASSES)
            combo.setCurrentText(str(image['class_label']))
            combo.setProperty('image_id', int(image['id']))
            self.images_table.setCellWidget(row_index, 2, combo)

            checkbox = QCheckBox()
            checkbox.setChecked(bool(image['selected_final']))
            checkbox.setProperty('image_id', int(image['id']))
            checkbox.setProperty('folder_id', folder_id)
            container = QWidget()
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setAlignment(Qt.AlignCenter)
            container_layout.addWidget(checkbox)
            self.images_table.setCellWidget(row_index, 3, container)

        self.images_table.resizeColumnsToContents()
        self._append_status(f'Loaded {len(images)} images for folder id {folder_id}.')

    def _save_folder_review(self) -> None:
        if self.current_folder_id is None:
            QMessageBox.information(self, APP_NAME, 'Select a folder first.')
            return

        checked_image_ids: list[int] = []
        for row_index in range(self.images_table.rowCount()):
            combo = self.images_table.cellWidget(row_index, 2)
            checkbox_container = self.images_table.cellWidget(row_index, 3)
            if not isinstance(combo, QComboBox) or checkbox_container is None:
                continue
            checkbox = checkbox_container.findChild(QCheckBox)
            if checkbox is None:
                continue
            image_id = int(combo.property('image_id'))
            class_label = combo.currentText()
            is_final = checkbox.isChecked()
            if is_final:
                checked_image_ids.append(image_id)
            self.database.update_image_review(image_id=image_id, class_label=class_label, selected_final=is_final)

        if len(checked_image_ids) > 1:
            keep_id = checked_image_ids[-1]
            self.database.clear_folder_final_selection(self.current_folder_id, keep_id)
            self.database.update_image_review(keep_id, self._current_class_label_for_image(keep_id), True)
            self._append_status('Multiple final selections were checked. Kept only the last checked image as final.')

        self._load_selected_folder_images()
        self._append_status(f'Folder {self.current_folder_id} review saved.')

    def _current_class_label_for_image(self, image_id: int) -> str:
        for row_index in range(self.images_table.rowCount()):
            combo = self.images_table.cellWidget(row_index, 2)
            if isinstance(combo, QComboBox) and int(combo.property('image_id')) == image_id:
                return combo.currentText()
        return 'review_required'

    def _export_manifest(self) -> None:
        if self.current_job_id is None:
            QMessageBox.information(self, APP_NAME, 'Ingest a job before exporting.')
            return
        export_dir = QFileDialog.getExistingDirectory(self, 'Select export folder')
        if not export_dir:
            return
        rows = self.database.fetch_export_rows(self.current_job_id)
        csv_path, json_path = export_manifest(rows, export_dir)
        self._append_status(f'Export complete: {csv_path} and {json_path}')
        QMessageBox.information(self, APP_NAME, f'Exported manifest files:\n- {csv_path}\n- {json_path}')


def launch() -> None:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
