# HeartTwin integration

Capabilities:

- `flow.health`
- `flow.simulate`
- `flow.validate.reference`
- `flow.validate.spatial`

HeartTwin passes a CardiAnatomy flow-domain reference, explicit fluid properties and boundary conditions, plus optional CardiMech/circulation artifact references.

For the built-in `windkessel-3element-v1` reference backend, `mechanics_ref` is now an active data dependency: it must reference a local `mechanics_timeseries` JSON artifact containing aligned `time_s` and `aortic_flow_ml_s` arrays. The artifact SHA-256 is verified when present, declared units and identity are checked, and actual timestamps are retained, and the aortic-flow series becomes the Windkessel inlet waveform. Supplying both `mechanics_ref` and a separate `settings.inlet_flow` is rejected so a declared mechanics coupling cannot be silently bypassed.

This is a real reduced-order Mechanics→Flow handoff, but it is not moving-wall CFD. `moving_wall_ref` and `circulation_ref` are rejected by the built-in backend; Neither native backend currently consumes these inputs. Nonuniform mechanics timestamps are supported. N samples define N-1 integration intervals, and the terminal capacitor pressure is at the final supplied time.

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

Native results include field units, interval volumes and actual mechanics SHA-256. Anatomy identity is declared lineage; it does not mean an unused 0D anatomy mesh was read or validated. See [the numerical contract](SCIENTIFIC_VALIDATION.md).

## Spatial backend

Select `rigid-pipe-navier-stokes-v1` and install the optional `cfd` dependencies. HeartTwin must supply an explicit `rigid_pipe_geometry` artifact with matching subject identity; arbitrary CardiAnatomy mesh references cannot be substituted. The geometry is consumed and hashed. Pressure boundaries and actual fluid properties drive native radial velocity, flow and wall-shear outputs. Read [SPATIAL_REFERENCE.md](SPATIAL_REFERENCE.md) for units, flattened field shape, numerical QC and limits. OSI/TAWSS apply to the supplied window. This is an idealized vascular reference, not ventricular FSI, and the two native backends are not automatically coupled.
