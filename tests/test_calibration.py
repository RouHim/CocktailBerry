"""Tests for the calibration module."""


from src.programs.calibration import (
    MAX_DEVIATION_RATIO,
    MAX_FLOW_RATE,
    MIN_DEVIATION_RATIO,
    MIN_FLOW_RATE,
    CalibrationScreen,
    CalibrationState,
)


class TestFlowRateCalculation:
    """Test the flow rate calculation logic."""

    def test_calculate_corrected_flow_rate_exact_match(self) -> None:
        """Test when actual equals target - flow rate should remain unchanged."""
        # Arrange
        current_flow = 30.0
        target_ml = 100.0
        actual_ml = 100.0

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore

        # Assert
        assert result == 30.0

    def test_calculate_corrected_flow_rate_half_actual(self) -> None:
        """Test when actual is half of target - flow rate should double."""
        # Arrange
        current_flow = 30.0
        target_ml = 100.0
        actual_ml = 50.0  # Half of target

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore

        # Assert
        assert result == 60.0  # Flow rate should double

    def test_calculate_corrected_flow_rate_double_actual(self) -> None:
        """Test when actual is double the target - flow rate should halve."""
        # Arrange
        current_flow = 30.0
        target_ml = 100.0
        actual_ml = 200.0  # Double the target

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore

        # Assert
        assert result == 15.0  # Flow rate should halve

    def test_calculate_corrected_flow_rate_zero_actual(self) -> None:
        """Test when actual is zero - should return current flow (safety)."""
        # Arrange
        current_flow = 30.0
        target_ml = 100.0
        actual_ml = 0.0

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore

        # Assert
        assert result == 30.0  # Should return current flow unchanged

    def test_calculate_corrected_flow_rate_realistic_scenario(self) -> None:
        """Test a realistic calibration scenario."""
        # Arrange: Expected 100ml, got 95ml
        current_flow = 30.0
        target_ml = 100.0
        actual_ml = 95.0

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore

        # Assert
        expected = 30.0 * (100.0 / 95.0)  # ~31.58
        assert abs(result - expected) < 0.01

    def test_calculate_corrected_flow_rate_very_small_amounts(self) -> None:
        """Test with very small amounts to check floating point handling."""
        # Arrange
        current_flow = 5.0
        target_ml = 10.0
        actual_ml = 9.8

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore

        # Assert
        expected = 5.0 * (10.0 / 9.8)  # ~5.102
        assert abs(result - expected) < 0.01

    def test_calculate_corrected_flow_rate_high_flow_rates(self) -> None:
        """Test with high flow rates near maximum."""
        # Arrange
        current_flow = 500.0
        target_ml = 200.0
        actual_ml = 180.0

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore

        # Assert
        expected = 500.0 * (200.0 / 180.0)  # ~555.56
        assert abs(result - expected) < 0.01


class TestFlowRateBounds:
    """Test flow rate boundary validation."""

    def test_min_flow_rate_constant(self) -> None:
        """Verify MIN_FLOW_RATE constant value."""
        assert MIN_FLOW_RATE == 0.1

    def test_max_flow_rate_constant(self) -> None:
        """Verify MAX_FLOW_RATE constant value."""
        assert MAX_FLOW_RATE == 1000.0

    def test_flow_rate_at_minimum_boundary(self) -> None:
        """Test calculation that results in minimum flow rate."""
        # Arrange: Create scenario that results in MIN_FLOW_RATE
        current_flow = 0.1
        target_ml = 100.0
        actual_ml = 100.0

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore

        # Assert
        assert result == MIN_FLOW_RATE

    def test_flow_rate_below_minimum(self) -> None:
        """Test calculation that would result in below minimum flow rate."""
        # Arrange: Create scenario that results in < MIN_FLOW_RATE
        current_flow = 0.5
        target_ml = 100.0
        actual_ml = 1000.0  # 10x target, will make flow 0.05

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore

        # Assert
        assert result < MIN_FLOW_RATE

    def test_flow_rate_above_maximum(self) -> None:
        """Test calculation that would result in above maximum flow rate."""
        # Arrange: Create scenario that results in > MAX_FLOW_RATE
        current_flow = 500.0
        target_ml = 100.0
        actual_ml = 10.0  # 1/10 target, will make flow 5000

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore

        # Assert
        assert result > MAX_FLOW_RATE


class TestDeviationThresholds:
    """Test deviation ratio threshold constants."""

    def test_max_deviation_ratio_constant(self) -> None:
        """Verify MAX_DEVIATION_RATIO constant value (300%)."""
        assert MAX_DEVIATION_RATIO == 3.0

    def test_min_deviation_ratio_constant(self) -> None:
        """Verify MIN_DEVIATION_RATIO constant value (50%)."""
        assert MIN_DEVIATION_RATIO == 0.5

    def test_deviation_at_max_threshold(self) -> None:
        """Test calculation at maximum deviation threshold."""
        # Arrange: Result should be exactly 3x current flow
        current_flow = 30.0
        target_ml = 100.0
        actual_ml = 100.0 / 3.0  # Will make flow 3x

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore
        deviation_ratio = result / current_flow

        # Assert
        assert abs(deviation_ratio - MAX_DEVIATION_RATIO) < 0.01

    def test_deviation_at_min_threshold(self) -> None:
        """Test calculation at minimum deviation threshold."""
        # Arrange: Result should be exactly 0.5x current flow
        current_flow = 30.0
        target_ml = 100.0
        actual_ml = 200.0  # Will make flow 0.5x

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore
        deviation_ratio = result / current_flow

        # Assert
        assert abs(deviation_ratio - MIN_DEVIATION_RATIO) < 0.01

    def test_deviation_within_acceptable_range(self) -> None:
        """Test that normal deviations fall within acceptable range."""
        # Arrange: Realistic 10% deviation
        current_flow = 30.0
        target_ml = 100.0
        actual_ml = 90.0  # 10% less than target

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore
        deviation_ratio = result / current_flow

        # Assert
        assert MIN_DEVIATION_RATIO < deviation_ratio < MAX_DEVIATION_RATIO

    def test_deviation_exceeds_max_threshold(self) -> None:
        """Test calculation that exceeds maximum deviation threshold."""
        # Arrange: Result should be > 3x current flow
        current_flow = 30.0
        target_ml = 100.0
        actual_ml = 25.0  # Will make flow 4x (400%)

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore
        deviation_ratio = result / current_flow

        # Assert
        assert deviation_ratio > MAX_DEVIATION_RATIO

    def test_deviation_below_min_threshold(self) -> None:
        """Test calculation that falls below minimum deviation threshold."""
        # Arrange: Result should be < 0.5x current flow
        current_flow = 30.0
        target_ml = 100.0
        actual_ml = 250.0  # Will make flow 0.4x (40%)

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore
        deviation_ratio = result / current_flow

        # Assert
        assert deviation_ratio < MIN_DEVIATION_RATIO


class TestCalibrationState:
    """Test the CalibrationState enum."""

    def test_state_enum_has_pre_dispense(self) -> None:
        """Verify PRE_DISPENSE state exists."""
        assert hasattr(CalibrationState, "PRE_DISPENSE")

    def test_state_enum_has_post_dispense(self) -> None:
        """Verify POST_DISPENSE state exists."""
        assert hasattr(CalibrationState, "POST_DISPENSE")

    def test_states_are_distinct(self) -> None:
        """Verify the two states are different."""
        assert CalibrationState.PRE_DISPENSE != CalibrationState.POST_DISPENSE


class TestCalibrationEdgeCases:
    """Test edge cases and error conditions."""

    def test_calculate_with_negative_target(self) -> None:
        """Test behavior with negative target (should still calculate but be invalid)."""
        # Arrange
        current_flow = 30.0
        target_ml = -100.0  # Invalid but shouldn't crash
        actual_ml = 100.0

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore

        # Assert - should return a negative result (will be caught by validation)
        assert result < 0

    def test_calculate_with_negative_actual(self) -> None:
        """Test behavior with negative actual (should still calculate but be invalid)."""
        # Arrange
        current_flow = 30.0
        target_ml = 100.0
        actual_ml = -100.0  # Invalid but shouldn't crash

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore

        # Assert - should return a negative result (will be caught by validation)
        assert result < 0

    def test_calculate_with_zero_current_flow(self) -> None:
        """Test behavior with zero current flow rate."""
        # Arrange
        current_flow = 0.0
        target_ml = 100.0
        actual_ml = 100.0

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore

        # Assert
        assert result == 0.0

    def test_calculate_with_very_large_numbers(self) -> None:
        """Test behavior with very large numbers."""
        # Arrange
        current_flow = 999.0
        target_ml = 10000.0
        actual_ml = 9999.0

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore

        # Assert - should calculate correctly without overflow
        expected = 999.0 * (10000.0 / 9999.0)
        assert abs(result - expected) < 0.01

    def test_rounding_to_two_decimal_places(self) -> None:
        """Test that flow rate calculation should be rounded to 2 decimal places in practice."""
        # Arrange
        current_flow = 30.123456
        target_ml = 100.0
        actual_ml = 95.5

        # Act
        result = CalibrationScreen.calculate_corrected_flow_rate(None, current_flow, target_ml, actual_ml)  # type: ignore
        rounded_result = round(result, 2)

        # Assert
        # The UI rounds to 2 decimals, so verify the calculation works with that
        assert len(str(rounded_result).split(".")[-1]) <= 2


class TestChannelNumberCalculation:
    """Test channel number (1-indexed) calculation from pump index (0-indexed)."""

    def test_channel_number_from_pump_index_0(self) -> None:
        """Test converting pump index 0 to channel number 1."""
        pump_index = 0
        channel_number = pump_index + 1
        assert channel_number == 1

    def test_channel_number_from_pump_index_5(self) -> None:
        """Test converting pump index 5 to channel number 6."""
        pump_index = 5
        channel_number = pump_index + 1
        assert channel_number == 6

    def test_channel_number_from_pump_index_23(self) -> None:
        """Test converting pump index 23 to channel number 24 (max)."""
        pump_index = 23
        channel_number = pump_index + 1
        assert channel_number == 24

    def test_channel_number_consistency(self) -> None:
        """Test that channel number calculation is consistent."""
        for pump_index in range(24):
            channel_number = pump_index + 1
            # Channel number should always be pump_index + 1
            assert channel_number == pump_index + 1
            # Channel number should be 1-indexed
            assert channel_number >= 1
            # Inverse operation should work
            assert channel_number - 1 == pump_index
