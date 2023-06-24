from decimal import Decimal

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QSlider, QCheckBox, QWidget


_SLIDER_STYLE = """
QSlider::groove:horizontal {
    border: 1px solid;
    border-color: #669fd4;
    height: 0px;
    margin: 0px;
}

QSlider::groove:horizontal:disabled {
    border-color: #cccccc;
}

QSlider::handle:horizontal {
    background-color: #005fb8;
    border: 0px solid;
    height: 1px;
    width: 6px;
    margin: -12px 0px;
}

QSlider::handle:horizontal:disabled {
    background-color: #cccccc;
}
"""


class _ParamLabel(QLabel):
    def __init__(self, name: str, tooltip="", parent=None):
        super().__init__(parent)
        self._name = name
        self.set_value(None)
        self.setToolTip(tooltip)

    def set_value(self, value: None | str):
        if value is None:
            self.setText(self._name)
        else:
            self.setText(f"{self._name} = {value}")


class _SliderGroup(QWidget):
    default_set = pyqtSignal()
    value_set = pyqtSignal(float)

    def __init__(
        self,
        param_name: str,
        min_value: int,
        max_value: int,
        single_step=1,
        denominator=100,
        initial_value=None,
        tooltip="",
    ):
        super().__init__()
        self._denominator = denominator

        self.label = _ParamLabel(param_name, tooltip=tooltip)
        self.checkbox = QCheckBox("Default")

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(min_value, max_value)
        self.slider.setSingleStep(single_step)
        self.slider.setMaximumHeight(12)
        self.slider.setStyleSheet(_SLIDER_STYLE)
        if initial_value is not None:
            self.slider.setValue(initial_value)

        self.slider.valueChanged.connect(self._on_value_set)

        self.checkbox.stateChanged.connect(self._on_check_change)
        self.checkbox.setChecked(True)

        # self.slider.setDisabled(True)

    def _get_value(self):
        return Decimal(self.slider.value() / self._denominator)

    def _on_check_change(self, checked: bool):
        self.slider.setDisabled(checked)
        if checked:
            self.label.set_value(None)
            self.default_set.emit()
        else:
            self._on_value_set()

    def _on_value_set(self):
        value = self._get_value()
        self.label.set_value("{:.2f}".format(value))
        self.value_set.emit(float(value))

    def install(self, layout: QGridLayout, row: int):
        layout.addWidget(self.label, row, 0, 1, 2)
        layout.addWidget(self.checkbox, row + 1, 0)
        layout.addWidget(self.slider, row + 1, 1, 1, 3)


class ParamsControl(QFrame):
    # passing on signals from _SliderGroup objects
    temperature_set_default = pyqtSignal()
    temperature_set = pyqtSignal(float)

    top_p_set_default = pyqtSignal()
    top_p_set = pyqtSignal(float)

    pres_penalty_set_default = pyqtSignal()
    pres_penalty_set = pyqtSignal(float)

    freq_penalty_set_default = pyqtSignal()
    freq_penalty_set = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._layout = QGridLayout()
        self._layout.setContentsMargins(10, 30, 60, 60)
        self._layout.setHorizontalSpacing(10)
        self.setLayout(self._layout)

        self._temperature = _SliderGroup(
            "Temperature",
            min_value=0,
            max_value=200,
            initial_value=100,
            tooltip="Higher values make the output more random",
        )
        self._temperature.install(self._layout, row=0)
        self._temperature.default_set.connect(self.temperature_set_default.emit)
        self._temperature.value_set.connect(self.temperature_set.emit)

        self._add_space(row=2)

        self._top_p = _SliderGroup(
            "Top P",
            min_value=0,
            max_value=100,
            initial_value=100,
            tooltip="Restrict the model's sampling to top-p probability mass",
        )
        self._top_p.install(self._layout, row=3)
        self._top_p.default_set.connect(self.top_p_set_default.emit)
        self._top_p.value_set.connect(self.top_p_set.emit)

        self._add_space(row=5)

        self._pres_penalty = _SliderGroup(
            "Presence Penalty",
            min_value=-200,
            max_value=200,
            initial_value=0,
            tooltip="Positive values encourage the model to talk about new topics",
        )
        self._pres_penalty.install(self._layout, row=6)
        self._pres_penalty.default_set.connect(self.pres_penalty_set_default.emit)
        self._pres_penalty.value_set.connect(self.pres_penalty_set.emit)

        self._add_space(row=8)

        self._freq_penalty = _SliderGroup(
            "Frequency Penalty",
            min_value=-200,
            max_value=200,
            initial_value=0,
            tooltip="Positive values discourage repetition",
        )
        self._freq_penalty.install(self._layout, row=9)
        self._freq_penalty.default_set.connect(self.freq_penalty_set_default.emit)
        self._freq_penalty.value_set.connect(self.freq_penalty_set.emit)

    def _add_space(self, row: int, height: int = 10):
        spacer = QWidget()
        spacer.setFixedSize(0, height)
        self._layout.addWidget(spacer, row, 0)
