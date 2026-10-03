# ============================================================
# Alfa Commander - Crack Tab
# تبويب كسر كلمات المرور
# ============================================================

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QFormLayout, QComboBox,
    QLineEdit, QSpinBox, QMessageBox, QListWidget,
    QListWidgetItem, QTextEdit, QProgressBar, QFileDialog,
    QTabWidget, QCheckBox,
)

from app.gui.signal_bus import get_signal_bus
from app.logger import get_logger

logger = get_logger()


class CrackTab(QWidget):
    """تبويب الكسر."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bus = get_signal_bus()
        self.hash_file: Path | None = None
        self.cracked_password: str | None = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ---- اختيار الملف ----
        file_box = QGroupBox("ملف الهاش")
        file_layout = QHBoxLayout(file_box)

        self.file_label = QLabel("لم يتم اختيار ملف")
        self.file_label.setStyleSheet("color: #a6adc8;")
        file_layout.addWidget(self.file_label, 1)

        browse_btn = QPushButton("📂 اختيار")
        browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_box)

        # ---- إعدادات الكسر ----
        settings = QGroupBox("إعدادات الكسر")
        form = QFormLayout(settings)

        self.hash_mode = QComboBox()
        self.hash_mode.addItem("22000 - WPA-PBKDF2-PMKID+EAPOL", 22000)
        self.hash_mode.addItem("2500 - WPA-EAPOL-PBKDF2", 2500)
        self.hash_mode.addItem("16800 - WPA-PMKID-PBKDF2", 16800)
        form.addRow("نوع الهاش:", self.hash_mode)

        self.wordlist_combo = QComboBox()
        self._load_wordlists()
        form.addRow("قائمة الكلمات:", self.wordlist_combo)

        self.rules_combo = QComboBox()
        self.rules_combo.addItem("بدون قواعد", None)
        self._load_rules()
        form.addRow("قواعد:", self.rules_combo)

        self.workload = QSpinBox()
        self.workload.setRange(1, 4)
        self.workload.setValue(2)
        form.addRow("مستوى الجهد:", self.workload)

        self.use_gpu = QCheckBox("استخدام GPU")
        self.use_gpu.setChecked(True)
        form.addRow("", self.use_gpu)

        layout.addWidget(settings)

        # ---- الأزرار ----
        btn_layout = QHBoxLayout()

        self.start_btn = QPushButton("▶ بدء الكسر")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self._start_crack)
        btn_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("⏹ إيقاف")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_crack)
        btn_layout.addWidget(self.stop_btn)

        btn_layout.addStretch()

        self.aircrack_btn = QPushButton("🔨 استخدام aircrack-ng")
        self.aircrack_btn.clicked.connect(self._use_aircrack)
        btn_layout.addWidget(self.aircrack_btn)

        layout.addLayout(btn_layout)

        # ---- النتائج ----
        results_box = QGroupBox("النتائج")
        results_layout = QVBoxLayout(results_box)

        self.password_label = QLabel("—")
        self.password_label.setStyleSheet(
            "color: #a6e3a1; font-size: 16pt; font-weight: bold; padding: 8px;"
        )
        self.password_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        results_layout.addWidget(self.password_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        results_layout.addWidget(self.progress)

        self.speed_label = QLabel("—")
        self.speed_label.setStyleSheet("color: #a6adc8;")
        self.speed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        results_layout.addWidget(self.speed_label)

        layout.addWidget(results_box)

        # ---- السجل ----
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(200)
        layout.addWidget(QLabel("السجل:"))
        layout.addWidget(self.log)

        layout.addStretch()

    def _load_wordlists(self):
        try:
            from app.core.crack import list_wordlists
            lists = list_wordlists()
            self.wordlist_combo.clear()
            self.wordlist_combo.addItem("اختر قائمة...", None)
            for w in lists[:20]:
                label = f"{w.name} ({w.size_mb:.1f}MB)"
                self.wordlist_combo.addItem(label, str(w.path))
        except Exception as e:
            logger.warning(f"فشل تحميل القوائم: {e}")

    def _load_rules(self):
        try:
            from app.core.crack import list_rules
            rules = list_rules()
            for r in rules:
                self.rules_combo.addItem(r.name, str(r.path))
        except Exception:
            pass

    def _connect_signals(self):
        self.bus.crack_progress.connect(self._on_crack_progress)
        self.bus.crack_succeeded.connect(self._on_crack_succeeded)
        self.bus.crack_finished.connect(self._on_crack_finished)

    # ============================================================
    # الواجهة العامة
    # ============================================================
    def add_hash_file(self, filepath: str):
        self.hash_file = Path(filepath)
        self.file_label.setText(str(self.hash_file))
        self.file_label.setStyleSheet("color: #a6e3a1;")

    def _browse_file(self):
        from app.constants import EVIDENCE_DIR
        file, _ = QFileDialog.getOpenFileName(
            self, "اختر ملف هاش",
            str(EVIDENCE_DIR),
            "Hash Files (*.22000 *.16800 *.hccapx *.cap *.pcapng);;All Files (*)",
        )
        if file:
            self.add_hash_file(file)

    # ============================================================
    # الكسر
    # ============================================================
    def _start_crack(self):
        if not self.hash_file or not self.hash_file.exists():
            QMessageBox.warning(self, "تنبيه", "اختر ملف هاش صالح.")
            return

        wordlist = self.wordlist_combo.currentData()
        if not wordlist:
            QMessageBox.warning(self, "تنبيه", "اختر قائمة كلمات.")
            return

        rules = None
        if self.rules_combo.currentData():
            rules = [self.rules_combo.currentData()]

        mode = self.hash_mode.currentData()
        workload = self.workload.value()

        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.password_label.setText("جارٍ الكسر...")
        self.password_label.setStyleSheet(
            "color: #f9e2af; font-size: 16pt; font-weight: bold; padding: 8px;"
        )
        self.log.append(f"بدء hashcat -m {mode}")

        def _run():
            import asyncio
            from app.core.crack import HashcatRunner, HashcatOptions

            opts = HashcatOptions(
                hash_file=self.hash_file,
                hash_mode=mode,
                wordlist=Path(wordlist),
                rules=rules,
                workload=workload,
            )

            async def _do():
                runner = HashcatRunner(opts)
                await runner.start()
                while runner._process and runner._process.running:
                    await asyncio.sleep(1)
                    p = runner.progress
                    self.bus.crack_progress.emit({
                        "recovered": p.recovered,
                        "total": p.total,
                        "progress": p.progress_percent,
                        "speed": p.speed_hps,
                    })
                    if p.password:
                        self.bus.crack_succeeded.emit({
                            "password": p.password,
                            "file": str(self.hash_file),
                        })
                        break

                self.bus.crack_finished.emit({
                    "file": str(self.hash_file),
                    "password": runner.progress.password,
                    "status": runner.progress.status,
                })

            asyncio.run(_do())

        import threading
        threading.Thread(target=_run, daemon=True).start()

    def _stop_crack(self):
        self.stop_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.log.append("إيقاف...")

    def _use_aircrack(self):
        if not self.hash_file or not self.hash_file.exists():
            QMessageBox.warning(self, "تنبيه", "اختر ملف هاش.")
            return
        wordlist = self.wordlist_combo.currentData()
        if not wordlist:
            QMessageBox.warning(self, "تنبيه", "اختر قائمة كلمات.")
            return

        self.log.append(f"aircrack-ng على {self.hash_file}")

        def _run():
            import asyncio
            from app.core.crack import AircrackRunner

            async def _do():
                runner = AircrackRunner(
                    cap_file=self.hash_file,
                    wordlist=Path(wordlist),
                )
                await runner.start()
                while runner._process and runner._process.running:
                    await asyncio.sleep(1)
                    p = runner.progress
                    self.bus.crack_progress.emit({
                        "progress": p.progress_percent,
                        "speed": p.keys_per_second,
                    })

            asyncio.run(_do())

        import threading
        threading.Thread(target=_run, daemon=True).start()

    # ============================================================
    # الأحداث
    # ============================================================
    def _on_crack_progress(self, data: dict):
        progress = data.get("progress", 0)
        speed = data.get("speed", 0)
        self.progress.setValue(int(progress))
        self.speed_label.setText(f"السرعة: {speed:,} H/s")

    def _on_crack_succeeded(self, data: dict):
        pwd = data.get("password", "")
        self.cracked_password = pwd
        self.password_label.setText(f"🔓 {pwd}")
        self.password_label.setStyleSheet(
            "color: #a6e3a1; font-size: 18pt; font-weight: bold; padding: 8px;"
        )
        self.log.append(f"✓ تم الكسر: {pwd}")

    def _on_crack_finished(self, data: dict):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress.setVisible(False)
        if not data.get("password"):
            self.password_label.setText("✗ لم يتم الكسر")
            self.password_label.setStyleSheet(
                "color: #f38ba8; font-size: 14pt; font-weight: bold; padding: 8px;"
            )
