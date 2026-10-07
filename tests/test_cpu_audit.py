import math

import pytest
from test_windkessel import _request

from cardiflow import FlowQC, FlowSimulationResult, FluidProperties
from cardiflow.reduced_order import Windkessel3ElementBackend


def test_terminal_pressure_is_at_last_sample_not_an_extra_step():
    request = _request([2, 2])
    request.settings["initial_capacitor_pressure"] = 0
    result = Windkessel3ElementBackend().simulate(request)
    assert result.scalar_outputs["terminal_capacitor_pressure"] == pytest.approx(
        8 * -math.expm1(-0.01 / 2)
    )
    assert (
        result.scalar_outputs["terminal_capacitor_pressure"]
        == result.series_outputs["capacitor_pressure"][-1]
    )


def test_tiny_step_does_not_lose_pressure_increment():
    request = _request([1, 1])
    request.settings.update(dt_s=1e-20, initial_capacitor_pressure=0)
    result = Windkessel3ElementBackend().simulate(request)
    assert result.series_outputs["capacitor_pressure"][1] == pytest.approx(2e-20, rel=1e-12, abs=0)


@pytest.mark.parametrize("setting,value", [("unknown", 1), ("inlet_flow_unit", "m^3/s")])
def test_ignored_or_contradictory_settings_fail(setting, value):
    request = _request()
    request.settings[setting] = value
    with pytest.raises(ValueError):
        Windkessel3ElementBackend().simulate(request)


@pytest.mark.parametrize("value", [float("inf"), float("nan")])
def test_nonfinite_result_and_qc_rejected(value):
    with pytest.raises(ValueError):
        FlowSimulationResult(subject_id="s", backend="b", scalar_outputs={"p": value})
    with pytest.raises(ValueError):
        FlowQC(passed=True, metrics={"error": value})


def test_infinite_fluid_density_rejected():
    with pytest.raises(ValueError):
        FluidProperties(density=float("inf"), dynamic_viscosity=0.0035)


@pytest.mark.parametrize("rd,c", [(1e300, 1e300), (1e-300, 1e-300)])
def test_unrepresentable_time_constant_fails_explicitly(rd, c):
    request = _request()
    request.boundary_conditions[0].parameters.update(distal_resistance=rd, compliance=c)
    with pytest.raises(ValueError, match="time constant"):
        Windkessel3ElementBackend().simulate(request)


def test_pulse_pressure_includes_left_limit_at_flow_jump():
    request = _request([1.0, 0.0])
    request.settings.update(dt_s=0.01, initial_capacitor_pressure=0.0)
    result = Windkessel3ElementBackend().simulate(request)
    # Just before the final jump, pressure is Pc(t_end)+Rp; just after it is Pc(t_end).
    # The minimum is the latter, so the complete waveform pulse pressure equals Rp.
    assert result.scalar_outputs["pulse_pressure"] == pytest.approx(1.0)
    sampled = result.series_outputs["outlet_pressure"]
    assert max(sampled) - min(sampled) < result.scalar_outputs["pulse_pressure"]
