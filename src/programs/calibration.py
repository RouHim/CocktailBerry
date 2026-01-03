import sys
from typing import Callable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMainWindow

from src.config.config_manager import CONFIG as cfg
from src.dialog_handler import DIALOG_HANDLER as DH
from src.display_controller import DP_CONTROLLER
from src.error_handler import logerror
from src.logger_handler import LoggerHandler
from src.tabs import maker
from src.ui_elements.calibration import Ui_CalibrationWindow

logger = LoggerHandler("calibration_module")


class CalibrationScreen(QMainWindow, Ui_CalibrationWindow):
    def __init__(
        self,
        parent: QMainWindow | None = None,
        standalone: bool = True,
        pump_index: int | None = None,
        current_flow_rate: float | None = None,
        pin: int | None = None,
        on_accept_callback: Callable[[], None] | None = None,
    ) -> None:
        """Init the calibration Screen.

        Args:
            parent: Parent window (for modal dialog)
            standalone: If True, runs as standalone app; if False, runs as dialog
            pump_index: The 0-indexed pump number (for pump mode)
            current_flow_rate: Current flow rate in ml/s (for pump mode)
            pin: GPIO pin number (for pump mode)
            on_accept_callback: Optional callback to run after accepting calibration

        """
        super().__init__(parent)
        self.setupUi(self)
        self.standalone = standalone
        self.pump_mode = pump_index is not None
        self.pump_index = pump_index
        self.current_flow_rate = current_flow_rate or 30.0
        self.pin = pin or 0
        self.calculated_flow = 0.0
        self.dispensed = False  # Track workflow state
        self.on_accept_callback = on_accept_callback

        # Set window flags based on mode
        if standalone:
            self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowStaysOnTopHint)  # type: ignore
        else:
            self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowStaysOnTopHint)  # type: ignore
            self.setWindowModality(Qt.ApplicationModal)  # type: ignore

        # Connect buttons
        bottles = cfg.MAKER_NUMBER_BOTTLES
        self.PB_start.clicked.connect(self.output_volume)
        self.PB_accept.clicked.connect(self.accept_calibration)
        self.channel_plus.clicked.connect(lambda: DP_CONTROLLER.change_input_value(self.channel, 1, bottles, 1))
        self.channel_minus.clicked.connect(lambda: DP_CONTROLLER.change_input_value(self.channel, 1, bottles, -1))
        self.amount_plus.clicked.connect(lambda: DP_CONTROLLER.change_input_value(self.amount, 10, 200, 10))
        self.amount_minus.clicked.connect(lambda: DP_CONTROLLER.change_input_value(self.amount, 10, 200, -10))
        self.actual_amount_plus.clicked.connect(
            lambda: DP_CONTROLLER.change_input_value(self.actual_amount, 0, 200, 10, self.on_actual_amount_changed)
        )
        self.actual_amount_minus.clicked.connect(
            lambda: DP_CONTROLLER.change_input_value(self.actual_amount, 0, 200, -10, self.on_actual_amount_changed)
        )
        self.button_exit.clicked.connect(self.close)

        # Apply translations for UI text
        self._apply_translations()

        # Setup UI based on mode
        self._setup_ui_mode()

        # Show window
        if standalone:
            self.showFullScreen()
        else:
            self.resize(780, 600)

        DP_CONTROLLER.inject_stylesheet(self)
        DP_CONTROLLER.set_display_settings(self)
        logger.log_start_program("calibration")

    def _apply_translations(self) -> None:
        """Apply language translations to static UI labels."""
        self.setWindowTitle(DH.get_translation("calibration_window_title"))
        self.label_2.setText(DH.get_translation("calibration_amount_label"))
        self.label.setText(DH.get_translation("calibration_channel_label"))
        self.label_4.setText(DH.get_translation("calibration_header"))
        self.PB_start.setText(DH.get_translation("dispense_button"))
        self.button_exit.setText(DH.get_translation("calibration_exit_button"))
        self.label_actual.setText(DH.get_translation("actual_amount_label"))
        self.PB_accept.setText(DH.get_translation("accept_button"))
        self.calculated_flow_rate.setText(DH.get_translation("new_flow_rate_label") + ": -- ml/s")

    def _setup_ui_mode(self) -> None:
        """Set up UI elements based on standalone or pump mode."""
        if self.pump_mode:
            # Pump mode: hide channel selector, show pump info
            self.channel.hide()
            self.channel_plus.hide()
            self.channel_minus.hide()
            self.label.hide()  # "Channel" label

            # Show pump info
            pump_num = self.pump_index + 1 if self.pump_index is not None else 0
            pump_info = DH.get_translation("pump_info_format", index=pump_num, pin=self.pin, flow=self.current_flow_rate)
            self.pump_info_label.setText(pump_info)
            self.pump_info_label.show()
        else:
            # Standalone mode: hide pump info
            self.pump_info_label.hide()

        # Initially hide post-dispense elements
        self.actual_amount.hide()
        self.actual_amount_plus.hide()
        self.actual_amount_minus.hide()
        self.label_actual.hide()
        self.calculated_flow_rate.hide()
        self.warning_label.hide()
        self.PB_accept.hide()

    def output_volume(self) -> None:
        """Output the set number of volume according to defined volume flow."""
        if not self.pump_mode:
            channel_number = int(self.channel.text())
        else:
            channel_number = (self.pump_index + 1) if self.pump_index is not None else 1
        amount = int(self.amount.text())
        maker.calibrate(channel_number, amount)

        # Switch to post-dispense state
        self.dispensed = True
        self._switch_to_post_dispense_ui()

    def _switch_to_post_dispense_ui(self) -> None:
        """Switch UI to post-dispense state for entering actual amount."""
        # Hide dispense button only in pump mode (standalone allows repeated runs)
        if self.pump_mode:
            self.PB_start.hide()
        else:
            self.PB_start.show()

        # Hide target amount inputs while entering the actual value
        self.amount.hide()
        self.amount_plus.hide()
        self.amount_minus.hide()
        self.label_2.hide()

        # Show actual amount input
        self.actual_amount.show()
        self.actual_amount_plus.show()
        self.actual_amount_minus.show()
        self.label_actual.show()
        self.calculated_flow_rate.show()
        self.warning_label.show()
        if self.pump_mode:
            self.PB_accept.show()
        else:
            self.PB_accept.hide()

        # Set initial actual amount to match target
        target_amount = int(self.amount.text())
        self.actual_amount.setText(str(target_amount))

        # Calculate initial flow rate
        self.on_actual_amount_changed()

    def on_actual_amount_changed(self) -> None:
        """Recalculate flow rate when actual amount is changed."""
        try:
            target_amount = float(self.amount.text())
            actual_amount = float(self.actual_amount.text())

            if actual_amount <= 0:
                self.calculated_flow_rate.setText(
                    DH.get_translation("new_flow_rate_label") + ": -- ml/s"
                )
                self.warning_label.setText(DH.get_translation("flow_rate_out_of_bounds"))
                self.PB_accept.setEnabled(False)
                return

            # Calculate corrected flow rate
            self.calculated_flow = round(
                self.calculate_corrected_flow_rate(
                self.current_flow_rate, target_amount, actual_amount
                ),
                2,
            )

            # Check bounds (0.1 - 1000 ml/s)
            if self.calculated_flow < 0.1 or self.calculated_flow > 1000:
                self.calculated_flow_rate.setText(
                    f"{DH.get_translation('new_flow_rate_label')}: {self.calculated_flow:.2f} ml/s"
                )
                self.warning_label.setText(DH.get_translation("flow_rate_out_of_bounds"))
                self.PB_accept.setEnabled(False)
                return

            # Check for unrealistic deviation (>200% or <50%)
            deviation_ratio = self.calculated_flow / self.current_flow_rate
            if deviation_ratio > 3.0 or deviation_ratio < 0.5:
                self.warning_label.setText(DH.get_translation("flow_rate_unrealistic_warning"))
            else:
                self.warning_label.setText("")

            # Update display
            self.calculated_flow_rate.setText(
                f"{DH.get_translation('new_flow_rate_label')}: {self.calculated_flow:.2f} ml/s"
            )
            self.PB_accept.setEnabled(True)

        except (ValueError, ZeroDivisionError):
            self.calculated_flow_rate.setText(DH.get_translation("new_flow_rate_label") + ": -- ml/s")
            self.PB_accept.setEnabled(False)

    def calculate_corrected_flow_rate(self, current_flow: float, target_ml: float, actual_ml: float) -> float:
        """Calculate the corrected flow rate based on target vs actual amount.

        Args:
            current_flow: Current flow rate in ml/s
            target_ml: Target amount in ml
            actual_ml: Actual amount dispensed in ml

        Returns:
            Corrected flow rate in ml/s

        """
        if actual_ml == 0:
            return current_flow
        return current_flow * (target_ml / actual_ml)

    def accept_calibration(self) -> None:
        """Accept the calibration and update the pump config."""
        if not self.pump_mode or self.pump_index is None:
            DH.standard_box(
                DH.get_translation("calibration_accept_pump_mode_only"), DH.get_translation("error")
            )
            return

        try:
            # Update pump config - convert PumpConfig objects to dicts
            pump_configs = cfg.PUMP_CONFIG
            pump_configs[self.pump_index].volume_flow = self.calculated_flow

            # Convert all PumpConfig objects to dicts for validation
            pump_config_dicts = [pc.to_config() for pc in pump_configs]
            cfg.set_config({"PUMP_CONFIG": pump_config_dicts}, validate=True)
            cfg.sync_config_to_file()

            # Call callback to refresh parent UI
            if self.on_accept_callback:
                self.on_accept_callback()

            self.close()  # Close window

        except Exception as e:
            logger.log_exception(e)
            DH.standard_box(
                DH.get_translation("calibration_update_failed_format", error=e),
                DH.get_translation("error"),
            )


@logerror
def run_calibration(standalone: bool = True) -> None:
    """Execute the calibration screen."""
    if standalone:
        app = QApplication(sys.argv)
    # this assignment is needed, otherwise the window will close in an instant
    # pylint: disable=unused-variable
    calibration = CalibrationScreen()  # noqa
    if standalone:
        sys.exit(app.exec_())  # type: ignore
