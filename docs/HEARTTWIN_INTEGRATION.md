# HeartTwin integration

Initial capabilities:

- `flow.health`
- `flow.simulate`

HeartTwin should pass a CardiAnatomy flow-domain reference, explicit fluid properties and boundary conditions, plus optional CardiMech moving-wall and circulation artifacts.

## Proposed registry entry

```yaml
- name: CardiFlow
  repository: Virelion-Biotech/Virelion-CardiFlow
  capabilities: [flow.health, flow.simulate]
  builtin: cardiflow
  endpoint: ${CARDIFLOW_URL}
```

HeartTwin should retain `FlowSimulationResult` as a typed artifact with backend, domain, boundary-condition provenance, QC, validation status, and output digests.

Flow calibration and uncertainty propagation should use CardiInfer rather than embedding another statistical framework in CardiFlow.
