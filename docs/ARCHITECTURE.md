# CardiFlow architecture

CardiFlow is the detailed hemodynamics layer of HeartTwin.

```text
CardiAnatomy flow domain
        |
        +---- CardiMech moving-wall motion
        +---- 0D circulation / outlet states
        |
        v
 fluid + boundary conditions
        |
 registered flow backend
        |
 velocity / pressure / wall shear / derived metrics
        |
 conservation + numerical QC
        |
 CardiInfer / HeartTwin
```

## Responsibility boundary

CardiFlow owns detailed flow simulation and flow-specific contracts. CardiMech owns myocardial deformation and lightweight circulation coupling. CardiInfer owns calibration/UQ. CardiAnatomy owns geometry and frames.

A 0D circulation model may be referenced by CardiFlow, but detailed CFD equations and flow meshes should not be copied into CardiMech.

## Backend roadmap

Potential backend families include reduced-order flow, finite-volume/finite-element CFD, moving-wall/ALE formulations, and external solver adapters. Heavy solver dependencies belong in optional backend packages or container images.

## Validation ladder

1. Contract/software checks.
2. Mesh and boundary-condition consistency.
3. Conservation and numerical convergence.
4. Canonical CFD benchmark problems.
5. Held-out imaging/flow agreement.
6. External patient/cohort validation.

Mass conservation and solver convergence are necessary quality checks, not evidence of clinical validity.
