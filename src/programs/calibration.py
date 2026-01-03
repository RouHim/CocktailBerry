import sys
from enum import Enum, auto
from typing import Callable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMainWindow

from src.config.config_manager import CONFIG as cfg
from src.config.errors import ConfigError
from src.dialog_handler import DIALOG_HANDLER as DH
from src.display_controller import DP_CONTROLLER
from src.error_handler import logerror
from src.logger_handler import LoggerHandler
from src.tabs import maker
from src.ui_elements.calibration import Ui_CalibrationWindow

logger = LoggerHandler("calibration_module")

# Flow rate validation constants
MIN_FLOW_RATE = 0.1  # ml/s
MAX_FLOW_RATE = 1000.0  # ml/s
MAX_DEVIATION_RATIO = 3.0  # Warn if calculated flow is >300% of original
MIN_DEVIATION_RATIO = 0.5  # Warn if calculated flow is <50% of original


class CalibrationState(Enum):
    """Tracks the workflow state of the calibration process."""

    PRE_DISPENSE = auto()  # User sets target amount, hasn't dispensed yet
    POST_DISPENSE = auto()  # User dispensed, now entering actual amount


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
        self.state = CalibrationState.PRE_DISPENSE  # Track workflow state
        self.on_accept_callback = on_accept_callback

        # Calculate 1-indexed channel number once (for consistency)
        self.channel_number = (pump_index + 1) if pump_index is not None else 1

        # Set window flags based on mode
        if standalone:
            self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowStaysOnTopHint)  # type: ignore
        else:
            self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowStaysOnTopHint)  # type: ignore
            self.setWindowModality(Qt.ApplicationModal)  # type: ignore
            # Ensure window is deleted when closed to avoid memory leaks
            self.setAttribute(Qt.WA_DeleteOnClose)  # type: ignore

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

            # Show pump info using pre-calculated channel_number
            pump_info = DH.get_translation(
                "pump_info_format",
                index=self.channel_number,
                pin=self.pin,
                flow=self.current_flow_rate
            )
            self.pump_info_label.setText(pump_info)
            self.pump_info_label.show()
        else:
            # Standalone mode: hide pump info
            self.pump_info_label.hide()

        # Initially hide post-dispense elements (STATE: PRE_DISPENSE)
        self._hide_post_dispense_ui()

    def _hide_post_dispense_ui(self) -> None:
        """Hide all UI elements related to the post-dispense state."""
        self.actual_amount.hide()
        self.actual_amount_plus.hide()
        self.actual_amount_minus.hide()
        self.label_actual.hide()
        self.calculated_flow_rate.hide()
        self.warning_label.hide()
        self.PB_accept.hide()

    def output_volume(self) -> None:
        """Output the set number of volume according to defined volume flow."""
        # Determine channel number based on mode
        channel_number = int(self.channel.text()) if not self.pump_mode else self.channel_number
        amount = int(self.amount.text())
        maker.calibrate(channel_number, amount)

        # Switch to post-dispense state
        self.state = CalibrationState.POST_DISPENSE
        self._switch_to_post_dispense_ui()

    def _switch_to_post_dispense_ui(self) -> None:
        """Switch UI to post-dispense state for entering actual amount.

        UI State Transition: PRE_DISPENSE -> POST_DISPENSE
        - In pump mode: Hide dispense button (one-time calibration)
        - In standalone mode: Keep dispense button visible (allow multiple runs)
        - Hide target amount inputs (already dispensed)
        - Show actual amount inputs (user enters what was actually dispensed)
        - Show calculated flow rate and warnings
        - In pump mode: Show accept button to save calibration
        """
        # Hide dispense button only in pump mode (standalone allows repeated runs)
        if self.pump_mode:
            self.PB_start.hide()
        else:
            self.PB_start.show()

        # Hide target amount inputs (we've already dispensed, no changing it now)
        self._hide_target_amount_inputs()

        # Show actual amount input section
        self._show_actual_amount_inputs()

        # Set initial actual amount to match target (user can adjust)
        target_amount = int(self.amount.text())
        self.actual_amount.setText(str(target_amount))

        # Calculate initial flow rate based on target=actual assumption
        self.on_actual_amount_changed()

    def _hide_target_amount_inputs(self) -> None:
        """Hide the target amount input controls."""
        self.amount.hide()
        self.amount_plus.hide()
        self.amount_minus.hide()
        self.label_2.hide()

    def _show_actual_amount_inputs(self) -> None:
        """Show the actual amount input controls and related displays."""
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

    def on_actual_amount_changed(self) -> None:
        """Recalculate flow rate when actual amount is changed.

        Validates user input, calculates the corrected flow rate, and provides
        warnings for out-of-bounds or unrealistic values.
        """
        try:
            # Parse amounts - these should always be valid due to UI constraints,
            # but we catch ValueError just in case
            target_amount = float(self.amount.text())
            actual_amount = float(self.actual_amount.text())

            # Validate actual amount is positive
            if actual_amount <= 0:
                self._show_invalid_flow_rate(DH.get_translation("flow_rate_out_of_bounds"))
                return

            # Calculate corrected flow rate
            self.calculated_flow = round(
                self.calculate_corrected_flow_rate(
                    self.current_flow_rate, target_amount, actual_amount
                ),
                2,
            )

            # Check bounds (MIN_FLOW_RATE - MAX_FLOW_RATE)
            if self.calculated_flow < MIN_FLOW_RATE or self.calculated_flow > MAX_FLOW_RATE:
                self.calculated_flow_rate.setText(
                    f"{DH.get_translation('new_flow_rate_label')}: {self.calculated_flow:.2f} ml/s"
                )
                self._show_invalid_flow_rate(DH.get_translation("flow_rate_out_of_bounds"))
                return

            # Check for unrealistic deviation (outside MIN_DEVIATION_RATIO - MAX_DEVIATION_RATIO)
            deviation_ratio = self.calculated_flow / self.current_flow_rate
            if deviation_ratio > MAX_DEVIATION_RATIO or deviation_ratio < MIN_DEVIATION_RATIO:
                self.warning_label.setText(DH.get_translation("flow_rate_unrealistic_warning"))
            else:
                self.warning_label.setText("")

            # Update display with valid flow rate
            self.calculated_flow_rate.setText(
                f"{DH.get_translation('new_flow_rate_label')}: {self.calculated_flow:.2f} ml/s"
            )
            self.PB_accept.setEnabled(True)

        except (ValueError, ZeroDivisionError) as e:
            # This should rarely happen due to UI input constraints,
            # but handle gracefully if it does
            logger.log_debug(f"Failed to parse amount values: {e}")
            self._show_invalid_flow_rate()

    def _show_invalid_flow_rate(self, warning_text: str = "") -> None:
        """Display invalid flow rate state and disable accept button."""
        self.calculated_flow_rate.setText(DH.get_translation("new_flow_rate_label") + ": -- ml/s")
        if warning_text:
            self.warning_label.setText(warning_text)
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
        """Accept the calibration and update the pump config.

        Updates the pump configuration with the newly calculated flow rate,
        validates the configuration, saves to file, and refreshes the parent UI.
        """
        if not self.pump_mode or self.pump_index is None:
            DH.standard_box(
                DH.get_translation("calibration_accept_pump_mode_only"), DH.get_translation("error")
            )
            return

        try:
            # Update pump config - convert PumpConfig objects to dicts
            pump_configs = cfg.PUMP_CONFIG

            # Validate pump index is within bounds
            if self.pump_index >= len(pump_configs):
                raise IndexError(f"Pump index {self.pump_index} out of range (max: {len(pump_configs) - 1})")

            pump_configs[self.pump_index].volume_flow = self.calculated_flow

            # Convert all PumpConfig objects to dicts for validation
            pump_config_dicts = [pc.to_config() for pc in pump_configs]
            cfg.set_config({"PUMP_CONFIG": pump_config_dicts}, validate=True)
            cfg.sync_config_to_file()

            # Call callback to refresh parent UI (may raise exceptions)
            if self.on_accept_callback:
                try:
                    self.on_accept_callback()
                except Exception as callback_error:
                    logger.log_exception(callback_error)
                    # Continue anyway - config was saved successfully

            self.close()  # Close window

        except (ConfigError, IndexError, AttributeError, OSError) as e:
            # Handle known exception types that can occur during config update
            logger.log_exception(e)
            DH.standard_box(
                DH.get_translation("calibration_update_failed_format", error=str(e)),
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
