# HeartTwin integration

Capabilities:

- `flow.health`
- `flow.simulate`

HeartTwin passes a CardiAnatomy flow-domain reference, explicit fluid properties and boundary conditions, plus optional CardiMech/circulation artifact references.

For the built-in `windkessel-3element-v1` reference backend, `mechanics_ref` is now an active data dependency: it must reference a local `mechanics_timeseries` JSON artifact containing aligned `time_s` and `aortic_flow_ml_s` arrays. The artifact SHA-256 is verified when present, the sampling interval is checked, and the aortic-flow series becomes the Windkessel inlet waveform. Supplying both `mechanics_ref` and a separate `settings.inlet_flow` is rejected so a declared mechanics coupling cannot be silently bypassed.

This is a real reduced-order Mechanics→Flow handoff, but it is not moving-wall CFD. `moving_wall_ref` remains reserved for spatial flow backends.

## Registry entry

```yaml
- name: CardiFlow
  repository: Virelion-Biotech/Virelion-CardiFlow
  capabilities: [flow.health, flow.simulate]
  builtin: cardiflow
  endpoint: ${CARDIFLOW_URL}
```

HeartTwin retains `FlowSimulationResult` as a typed canonical flow artifact. Flow provenance records the anatomy artifact/bundle fingerprint and, when coupled, the exact mechanics artifact ID/SHA-256 consumed by the backend.

Flow calibration and uncertainty propagation should use CardiInfer rather than embedding another statistical framework in CardiFlow.
