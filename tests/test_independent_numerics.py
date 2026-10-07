"""Independent adaptive ODE references for the complete 0D integration path."""

import math
from itertools import pairwise

import pytest

np = pytest.importorskip("numpy")
solve_ivp = pytest.importorskip("scipy.integrate").solve_ivp

from cardiflow import CardiFlowService
from cardiflow.validation import validation_request


@pytest.mark.parametrize("seed", range(16))
def test_full_waveform_matches_adaptive_ode_and_integrated_outflow(seed):
    rng = np.random.default_rng(seed)
    rp, rd, c = rng.uniform(0.1, 3, size=3)
    pd = float(rng.uniform(-2, 20))
    flow = rng.uniform(-3, 60, size=12)
    times = np.r_[5.0, 5.0 + np.cumsum(rng.uniform(0.001, 0.3, size=11))]
    initial = float(rng.uniform(0, 100))
    request = validation_request(flow, initial=initial, rp=rp, rd=rd, compliance=c, distal=pd)
    request.settings.pop("dt_s")
    request.settings["time_s"] = times.tolist()
    result = CardiFlowService().simulate(request)
    expected = [initial]
    volumes = []
    pc = initial
    for q, (a, b) in zip(flow[:-1], pairwise(times)):

        def derivative(t, state, q=q):
            distal = (state[0] - pd) / rd
            return [(q - distal) / c, distal]

        reference = solve_ivp(derivative, (a, b), [pc, 0], method="DOP853", rtol=2e-12, atol=1e-12)
        assert reference.success
        pc = float(reference.y[0, -1])
        expected.append(pc)
        volumes.append(float(reference.y[1, -1]))
    assert result.series_outputs["capacitor_pressure"] == pytest.approx(
        expected, rel=2e-10, abs=2e-9
    )
    assert result.series_outputs["interval_distal_outflow_volume"] == pytest.approx(
        volumes, rel=2e-10, abs=2e-9
    )
    duration = times[-1] - times[0]
    pressure_area = math.fsum(
        pd * (b - a) + rd * v + rp * q * (b - a)
        for q, v, (a, b) in zip(flow[:-1], volumes, pairwise(times))
    )
    assert result.scalar_outputs["mean_outlet_pressure"] == pytest.approx(
        pressure_area / duration, abs=2e-9
    )
    assert result.qc.passed
