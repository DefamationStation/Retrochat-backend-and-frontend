import sys
import subprocess
import json
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit, QLineEdit, QScrollArea, QHBoxLayout, QFrame, QLabel
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QPoint
from PyQt5.QtGui import QTextCursor, QFont, QIcon, QPixmap
from ctypes import windll, byref, c_int, sizeof

def set_amoled_black_title_bar(window):
    if sys.platform == 'win32':
        hwnd = int(window.winId())

        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        DWMWA_BORDER_COLOR = 34
        DWMWA_CAPTION_COLOR = 35
        
        windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, byref(c_int(1)), sizeof(c_int))
        
        black_color = 0x000000
        windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_BORDER_COLOR, byref(c_int(black_color)), sizeof(c_int))
        windll.dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_CAPTION_COLOR, byref(c_int(black_color)), sizeof(c_int))

class Chatbox(QWidget):
    def __init__(self):
        super().__init__()
        self.fontsize = 20
        self.is_moving = False
        self.startPos = QPoint(0, 0)
        self.help_message_displayed = False
        self.resizing = False
        self.resize_direction = None
        self.oldPos = QPoint(0, 0)
        self.is_full_screen = False
        self.backend_process = None
        self.initUI()

        self.setWindowIcon(self.create_transparent_icon())

    def create_transparent_icon(self):
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        return QIcon(pixmap)

    def initUI(self):
        self.setGeometry(300, 300, 1100, 550)
        self.setWindowFlags(Qt.Window)
        self.setWindowTitle(" ")

        main_layout = QVBoxLayout()
        chat_layout = QVBoxLayout()
        input_layout = QHBoxLayout()

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setFont(QFont("Courier New", self.fontsize))
        self.load_theme("default")

        self.chat_scroll_area = QScrollArea()
        self.chat_scroll_area.setWidgetResizable(True)
        self.chat_scroll_area.setWidget(self.chat_history)
        self.chat_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.chat_scroll_area.setFrameShape(QFrame.NoFrame)
        chat_layout.addWidget(self.chat_scroll_area)

        self.prompt_label = QLabel(">")
        self.prompt_label.setStyleSheet(self.get_prompt_style())
        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("Type your message here...")
        self.user_input.returnPressed.connect(self.process_input)
        self.user_input.setFont(QFont("Courier New", self.fontsize))
        self.user_input.setStyleSheet(self.get_input_style())

        input_layout.addWidget(self.prompt_label, 0, Qt.AlignLeft)
        input_layout.addWidget(self.user_input, 1)

        main_layout.addLayout(chat_layout)
        main_layout.addLayout(input_layout)

        self.setLayout(main_layout)
        self.setStyleSheet(self.get_global_style())

    def load_theme(self, theme_name):
        try:
            with open(f"themes/{theme_name}.json", "r") as theme_file:
                theme = json.load(theme_file)
                self.set_theme(theme)
        except FileNotFoundError:
            print(f"Theme {theme_name} not found, using default settings.")

    def set_theme(self, theme):
        self.setStyleSheet(self.get_global_style(theme))
        self.chat_history.setStyleSheet(self.get_chat_style(theme))
        self.prompt_label.setStyleSheet(self.get_prompt_style(theme))
        self.user_input.setStyleSheet(self.get_input_style(theme))

    def get_global_style(self, theme=None):
        theme = theme or {
            "background_color": "#000000",
            "font_color": "#00FF00",
            "font_family": "Courier New",
            "font_size": self.fontsize
        }
        return f"""
            QWidget {{
                background-color: {theme['background_color']};
                color: {theme['font_color']};
                font-family: '{theme['font_family']}';
                font-size: {theme['font_size']}px;
                border: none;
            }}
        """

    def get_chat_style(self, theme=None):
        theme = theme or {
            "background_color": "#000000",
            "font_color": "#00FF00"
        }
        return f"padding: 5px; background-color: {theme['background_color']}; color: {theme['font_color']};"

    def get_prompt_style(self, theme=None):
        theme = theme or {
            "font_color": "#00FF00",
            "font_size": self.fontsize
        }
        return f"color: {theme['font_color']}; font-size: {theme['font_size']}px; font-family: 'Courier New'; margin: 0; padding: 0;"

    def get_input_style(self, theme=None):
        theme = theme or {
            "background_color": "#000000",
            "font_color": "#00FF00"
        }
        return f"margin: 0; padding: 0; background-color: {theme['background_color']}; color: {theme['font_color']}; border: none;"

    def process_input(self):
        user_message = self.user_input.text().strip()
        if user_message:
            self.append_message(f"{user_message}", Qt.green)
            self.user_input.clear()
            self.send_to_backend(user_message)

    def append_message(self, message, color):
        self.chat_history.setTextColor(color)
        self.chat_history.append(message)
        self.chat_history.setTextColor(Qt.green)  # Reset to default color

    def send_to_backend(self, message):
        if self.backend_process:
            self.backend_process.stdin.write(f"{message}\n")
            self.backend_process.stdin.flush()

    def start_backend(self):
        self.backend_process = subprocess.Popen(
            ["python3", "retrochat.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        self.read_output_thread = OutputReader(self.backend_process.stdout, self)
        self.read_output_thread.new_line.connect(self.append_message)
        self.read_output_thread.start()

    def closeEvent(self, event):
        if self.backend_process:
            self.backend_process.terminate()
        event.accept()

class OutputReader(QThread):
    new_line = pyqtSignal(str, object)  # Custom signal to emit new lines read from stdout

    def __init__(self, stream, parent=None):
        super().__init__(parent)
        self.stream = stream

    def run(self):
        for line in iter(self.stream.readline, ''):
            self.new_line.emit(line.strip(), Qt.yellow)  # Emit new line signal with the line read and color
        self.stream.close()

if __name__ == "__main__":
    app = QApplication([])
    chatbox = Chatbox()
    set_amoled_black_title_bar(chatbox)  # Apply AMOLED black title bar
    chatbox.start_backend()  # Start the backend process
    chatbox.show()
    sys.exit(app.exec_())
