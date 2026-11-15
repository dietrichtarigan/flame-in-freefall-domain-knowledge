# Claude Opus Master Build Brief
## Original NASA FLEX Open Virtual Laboratory — Evidence-First, Physics-First, Uncertainty-Aware

**Purpose:** Use this brief to guide Claude Opus in designing and implementing a real, research-oriented browser laboratory based strictly on the **original NASA Flame Extinguishment Experiment (FLEX)**. The result should be an open platform for students, researchers and aerospace engineers. It must combine a 3D interactive apparatus, replay of original evidence, parameter-tunable physical modelling, statistical and machine-learning uncertainty quantification, a reproducible open repository and a research discussion forum.

**Primary research baseline:** Original FLEX campaign and original FLEX publications/data only. Do not silently include FLEX-2, DCE, later Cool Flames investigations or unrelated ISS droplet experiments as if they were original FLEX. Later literature may be used as a *methodological reference* if clearly labelled and never confused with original FLEX data.

**Start by reading the complete document** `FLEX_Original_Research_Open_Platform_AI_Uncertainty_Opus_Guide.docx` and its source register. Also read the original NASA technical report `NASA/TP-2015-216046`, the original FLEX payload description, the original FLEX peer-reviewed overview paper and any other source files supplied by the user. Read source content directly; do not rely only on the file's summary or this prompt.

---

# 1. Your role and operating rules

Act as the lead software architect and scientific-computing implementation assistant for a combustion-research virtual laboratory. Work carefully across frontend, Python backend, scientific modelling, data engineering and reproducible research. Do not claim specialist validation you have not performed.

## Scientific constitution — non-negotiable

1. **Every scientific claim must be traceable to original evidence.** Store a source ID plus exact locator (page, section, equation, figure, table, test ID, or data-file row). Separate primary source statements, peer-reviewed interpretations, model assumptions, derived measurements, numerical results and AI predictions.
2. **Every object has a unique identity.** Physical experiments, simulation runs, model predictions, datasets, models, claims, sources and reviews each receive immutable unique IDs. Preserve NASA's original FLEX test numbers and CIR engineering identifiers as legacy aliases; never replace them with platform IDs.
3. **Every prediction carries measurable uncertainty.** No AI prediction may be displayed or exported as a bare point value. It must include a prediction interval or an explicit uncalibrated / exploratory warning, the method, calibration evidence, validity domain and OOD status.
4. Never invent missing FLEX data, instrument accuracy, chemistry mechanism validation, NASA endorsement, CAD dimensions, unobserved image frames or experimental results. Use `unknown`, `not reported`, `not available`, `not quantified` or `not validated` when that is what the sources support.
5. Never alter original source files. Preserve them, hash them and create separate, versioned derivative artefacts.
6. A visual rendering is not automatically a physical simulation. Label original NASA photographs/video, diagrams, educational animations, measured outputs, physics-solver fields and AI predictions distinctly.
7. NASA review is not implied by using NASA data. A “NASA-validated” status requires documented authorization, a named authorized reviewer or NASA review process, an exact review scope and written evidence that the claim is permitted. A NASA employee's informal comments or affiliation must not be represented as institutional endorsement.
8. Build in small, tested phases. Do not generate a giant untested codebase in one pass. Report what has actually run and what remains a design proposal.

## Project scope

The original FLEX campaign investigated isolated liquid-fuel droplet combustion and flame extinction in microgravity. The original fuels include methanol and n-heptane. Reported conditions span initial droplet diameters around 1.5–5 mm, oxygen mole fractions around 0.1–0.4 and ambient pressures around 0.7–3.0 atm, with O2/N2 mixtures and CO2 or helium dilution. Check the exact range and each test's actual conditions against the cited source before implementing UI slider limits.

Original FLEX measurements include camera-derived droplet and flame histories. They do **not** provide a complete spatial 3D ground-truth temperature/species field for each test. Do not imply that an FNO trained only on FLEX videos is recovering a measured 3D temperature field.

---

# 2. Evidence, data and identifiers

## Source hierarchy

Use the following order:

1. Original NASA FLEX records, payload descriptions, original FLEX videos/images, test matrices and NASA technical reports.
2. Peer-reviewed papers reporting or interpreting original FLEX results.
3. Peer-reviewed droplet-combustion models used as methodological references, with the fact they are not original FLEX data clearly stated.
4. Official software documentation for implementation capabilities.
5. Model assumptions, which must be explicit and reviewable.

For each source create a record with:

- `source_id` (UUID or stable internal ID)
- bibliographic citation, author / NASA centre, year, DOI or stable URL
- version / publication date / retrieval date
- exact locator(s)
- local source file path where permissible
- SHA-256 checksum
- source class (`NASA_PRIMARY`, `PEER_REVIEWED`, `SOFTWARE_DOC`, `POLICY`, `OTHER`)
- licence / rights status and reuse note

For each atomic scientific claim create:

- `claim_id`
- concise, verifiable `claim_text`
- `evidence_class` (`NASA_REPORTED`, `RAW_MEASUREMENT`, `DERIVED_MEASUREMENT`, `PEER_REVIEWED_RESULT`, `MODEL_ASSUMPTION`, `PHYSICS_SIMULATION`, `AI_PREDICTION`, `PLATFORM_INFERENCE`)
- one or more `source_id` references and exact locator(s)
- support relation (`direct`, `partial`, `contextual`, `contradictory`)
- extraction method and reviewer state
- optional short quotation / faithful paraphrase

Do not allow a result page to render a scientific statement without a source link or an explicit “model assumption / unverified” badge.

## Identity model

Use Python `uuid.uuid4()` for platform identities and `hashlib.sha256()` for file/content integrity. Keep UUID and hash semantics separate.

Minimum independent IDs:

- `experiment_id`: physical experiment record. For original NASA tests preserve `FLEX-xxx` and the original CIR identifier as legacy fields, plus platform UUID. Community physical tests receive their own UUID and must be labelled community experiments.
- `simulation_run_id`: one solver execution, even when inputs match another execution.
- `prediction_id`: one model inference, including the exact input, model and interval.
- `dataset_id` + semantic version: immutable release of source/derived data.
- `model_id` + version + model-weights hash: explicit algorithm and frozen weights/mechanism.
- `claim_id`, `source_id`, `review_id`, `artifact_id`.

Each simulation and prediction must include parent IDs, input hashes, dataset version, code commit, software environment / container digest, start time (UTC), settings and output artefacts. Never overwrite a released dataset; release a new version with a changelog.

## Data packaging and provenance

Use PostgreSQL for structured metadata; S3-compatible object storage (MinIO locally) for videos, images, arrays, meshes and checkpoints. Package releases with RO-Crate metadata and provenance. Use W3C PROV-O concepts for entities, activities and agents. Track computation/training using MLflow, but keep the platform's scientific database authoritative for the research record. Follow FAIR principles where legal and rights conditions permit.

---

# 3. Measurement uncertainty: use the real NASA baseline

NASA/TP-2015-216046 reports the following estimates for its original FLEX image analyses:

| Measurement channel | NASA-reported estimate | Evidence / caveat |
|---|---:|---|
| HiBMs backlit droplet size | ±50 µm | Includes camera spatial resolution, segmentation threshold and image noise. Minimum spatial resolution reported as ±29.5 µm for most full-frame tests. |
| LLUV flame size | ±200 µm | Based on 512 × 512 binned images; dim/noisy flame and ambiguous outer OH* boundary definition. |
| MDCA colour-camera flame size | ±250 µm | Based on 640 × 480 video; visible flame edge has segmentation and noise ambiguity. |
| MDCA radiometer flame output | Not reliably quantified in the reported campaign | NASA states the installed radiometers were not sensitive enough to provide reliable quantitative radiometric output; do not invent measured heat-flux data. |

Important: the report does not define these ± estimates as 1σ or 95% intervals. Store them as `reported_measurement_uncertainty`, with `coverage_factor = not stated` and `distribution = not specified`. Do not convert them to a normal distribution without independent evidence.

Also preserve the instrument definitions:
- HiBMs backlit view: droplet geometry/dynamics.
- LLUV: OH* chemiluminescence image / outer OH* edge, not automatically the peak-temperature flame radius.
- MDCA colour camera: visible flame boundary; not interchangeable with LLUV boundary.
- Radiometer: installed but not a reliable quantitative validation channel in the reported tests.

NASA reports g-level low enough that buoyant flow was considered negligible, but g-jitter caused droplet drift and sometimes field-of-view loss. Ideal 0-g modelling is appropriate for the baseline body-force term; do not claim the physical acceleration was identically zero.

---

# 4. Uncertainty quantification implementation

The uncertainty budget must distinguish:

1. **Measurement uncertainty:** spatial calibration, segmentation, threshold, noise, temporal sampling, camera alignment, tracking, field-of-view clipping and missing frames.
2. **Input / parameter uncertainty:** D0, chamber pressure, gas mole fractions, initial temperature, fuel properties, transport properties, kinetic parameters, residual acceleration.
3. **Numerical uncertainty:** radial grid, time step, domain size, solver tolerance, chemistry stiffness tolerance, radiative angular resolution and convergence.
4. **Model-form uncertainty:** D² fit vs reduced quasi-steady model vs transient spherical reacting-droplet model; radiation / Soret / transport closures; spherical-symmetry assumptions.
5. **ML epistemic uncertainty:** model uncertainty from finite data and model choice; use deep ensembles or another justified approach.
6. **Aleatoric / observation variability:** only estimate this where genuine measurement or replicate variability supports it. Do not automatically interpret a network variance head as physical randomness.

## Required methods

- Start with uncertainty ranges and transparent deterministic sensitivity checks.
- Use Monte Carlo propagation as the general baseline. Report distributions/quantiles, sample count, random seed, input distributions and convergence of estimates.
- Use bootstrap for image-measurement / curve-fit uncertainty while accounting for time dependence. Do not treat every adjacent video frame as independent.
- Use SALib Sobol / Morris to rank influential uncertain inputs; sensitivity indices are not themselves uncertainty intervals.
- Use Chaospy polynomial-chaos expansions only when the response is sufficiently smooth and the input dimension/distributions are defensible; compare against Monte Carlo.
- Use deep ensembles for model disagreement and MAPIE conformal prediction for empirical interval calibration on held-out data.
- Split by whole physical FLEX test ID, not random frames. Calibration/test sets must not share frames from the same original test.
- MAPIE's standard conformal guarantees are marginal under exchangeability; do not claim per-condition/subgroup guarantees without testing those groups.
- Do not assume ±2σ means 95%. Report empirical coverage and interval width.
- Add OOD screening; flag or disable predictions outside the trained/validated region.

## Required prediction record

Every AI prediction must store:

`prediction_id`, `experiment_or_case_id`, `model_id`, `model_version`, `weights_sha256`, `simulation_run_id` (if applicable), `dataset_id/version`, `input_hash`, `created_utc`, `output_name`, `output_value`, `output_unit`, `interval_lower`, `interval_upper`, `nominal_coverage`, `interval_method`, `calibration_dataset_id`, `empirical_coverage`, `interval_width`, `epistemic_component`, `aleatoric_component`, `input_uncertainty`, `numerical_uncertainty`, `model_form_uncertainty`, `ood_flag`, `validity_domain`, `physics_residual`, `conservation_error`, `source_claim_ids` and `status`.

Prediction UI card must show point estimate + units, the nominal interval and its calibration status, uncertainty components, validity domain, OOD state, model version, prediction ID and evidence/validation links. If not calibrated, prominently say **“Exploratory prediction — interval not calibrated.”**

---

# 5. Physics model and software selection

## Recommended hierarchy

### Stage 0 — Original evidence replay
Load original test metadata and images/videos. Reproduce source values, camera labels and plots. No new physical prediction.

### Stage 1 — Measured-image pipeline
Camera calibration, segmentation, object tracking, D(t), D²(t), flame diameter by camera definition, FSR and measurement uncertainty. Preserve FOV gaps/censored records.

### Stage 2 — Reduced D² baseline
Fit `D²(t) = D0² - K t` over an explicitly selected and documented interval. Report fit residuals, interval, regression and uncertainty. Do not present this as the full physics model.

### Stage 3 — Transient spherical 1-D reacting-droplet model
Implement a transparent gas/liquid spherical model with moving droplet interface, evaporation, species conservation, energy, chemistry, gas transport, heat transfer, surface conditions and optional radiation. This is the principal physics model for the baseline FLEX virtual lab.

### Stage 4 — PINN / FNO surrogate
Train only after the numerical solver has a validated parameter sweep and a test split by full FLEX test ID. Keep trusted solver accessible for comparisons.

### Stage 5 — Optional 2-D / 3-D reacting CFD
Only when a research question requires asymmetry, chamber interactions or residual acceleration effects and the custom liquid-droplet interface/evaporation model is implemented. This is advanced work.

## Correct microgravity implementation

For ideal microgravity, set the gravitational acceleration vector in the body-force term to `g = 0`, so the contribution `rho*g` is zero. **Do not set density `rho` to zero.** Keep normal thermodynamic density. A residual acceleration vector may be a separately documented sensitivity case, or a source-aligned forcing history if real accelerometer data and time alignment are available.

## Spherical governing-physics checklist

Derive the precise equation form from the selected peer-reviewed droplet-combustion formulation and document all assumptions. At minimum:

- Spherical continuity: transient density plus radial divergence of mass flux, using the correct `r²` geometry.
- Species conservation: transient species accumulation + spherical convective/diffusive flux divergence = chemical production/consumption for each species.
- Energy conservation: transient energy / enthalpy, convection, conduction, diffusive enthalpy transport, reaction heat (depending on the chosen energy formulation) and radiative source/sink.
- Liquid droplet heat/species balance as required; moving surface radius; evaporation mass flux and Stefan flow; latent heat; mass/species/energy interface conditions; equilibrium / vapour-pressure closure.
- Thermodynamic and transport closure: equation of state, species thermodynamics, viscosity, thermal conductivity, molecular diffusion and kinetic source terms.
- Radiation closure only if optical properties and gas/radiation model are available and independently checked.
- Distinguish radiative extinction, diffusive extinction and visible-light extinction.

Avoid double counting chemical formation enthalpy / heat release. Do not allow the language model to invent an interface condition or closure: implement only after locating a suitable peer-reviewed formulation and unit tests.

## Cantera integration

Use Cantera for gas-phase kinetics, thermodynamics and gas transport. Cantera is **not** the complete transient spherical moving-droplet solver. The application still needs its own radial PDE / finite-volume or method-of-lines solver and liquid-gas interface model. Cantera supports multicomponent transport; Soret/thermal diffusion must be explicitly enabled and is only available with multicomponent transport. Expose it as a tested optional model switch.

## Mechanism policy — critical

- Original FLEX used methanol and n-heptane.
- **Do not use GRI-Mech 3.0 as the default.** The mechanism documentation describes it as methane/air chemistry.
- Methanol: Held–Dryer 1998 is a candidate mechanism. Verify exact CHEMKIN/Cantera mechanism files, species, thermodynamic polynomials, transport data and validation coverage before use.
- n-Heptane: identify a mechanism linked to peer-reviewed n-heptane droplet-combustion modelling (e.g., Farouk & Dryer microgravity two-stage droplet work); compare the candidate mechanism's validation envelope against actual FLEX test conditions. An LLNL mechanism is a candidate source, not automatic validation for all FLEX tests.
- CO2 and He dilution are physically different. Preserve exact mixture fractions and choose property / transport data accordingly.
- Hash and archive mechanism files; record source, version, licence, species/reactions and conversion history.

## PINNs and neural operators

- **DeepXDE:** good first PINN framework for a reduced 1-D PDE or inverse problem. Choose one backend, preferably PyTorch for integration with the ML stack, then pin exact compatible versions.
- **NVIDIA PhysicsNeMo:** optional for GPU-scaled PINNs, neural operators, UQ and active learning. It is a larger stack; add only after a stable baseline exists and verify whether an API is experimental.
- **FNO / TFNO via NeuralOperator:** useful to approximate a mapping from input parameter functions/fields to radial-time solution fields. Original FLEX observations do not supply 3-D field ground truth. Train on verified solver-generated fields; use FLEX to calibrate and validate observables. Start with a 1-D radial-time operator. A 3-D field predictor is a later research project, not MVP.
- Use PINNs for inverse estimation / parameter identification / PDE constrained surrogate where helpful. Do not use a PINN to replace a stable stiff chemical kinetics solver without evidence.
- Compare ML against numerical baseline, test conservation and boundary/interface residuals, measure speed-up and calibrated interval quality.

## OpenFOAM

`reactingFoam` supports transient compressible reacting-flow and heat-transfer cases, and `fvDOM` is a discrete-ordinates radiative-transfer model for participating media with its own angular and radiation assumptions. Neither is a ready-made isolated liquid-droplet moving-interface FLEX solver. Use OpenFOAM only in an optional later phase after implementing and validating the custom droplet geometry, evaporation, interface coupling and chemistry. Treat radiation modelling as a distinct validation task.

---

# 6. Web application architecture

## Frontend

- HTML + TypeScript/JavaScript with Vite.
- Three.js for 3D apparatus and droplet visualisation.
- Plotly.js for time series, uncertainty bands, radial fields, sensitivity, residuals and validation plots.
- Optional vtk.js later for large field / volume rendering.
- Clickable information bubbles on every hardware component and every plotted scientific variable.
- Parameter sliders / selectors with valid-domain bounds, unit labels, source references and immediate warning states.
- Time controller synchronizing original NASA video, camera view, measurements and computed fields. Mark original video vs simulated render visibly.

## Python backend

- FastAPI REST API for source/data queries, simulation submission, model inference and result download.
- WebSocket or server-sent events for long-job status / result streaming.
- Python services: ingestion, evidence ledger, image measurement, D² analysis, 1-D spherical solver, Cantera adapter, UQ, ML inference, validation and RO-Crate export.
- Heavy solver / training jobs must run in a separate worker or process; do not block the API server.
- PostgreSQL structured database; MinIO object storage; MLflow for model/run tracking; Git for code/version history.
- Docker Compose for local development. Pin dependencies in `pyproject.toml` / lockfile.
- SQLite may be used only for the first single-user mock, but design migrations to PostgreSQL early.

## Repository / forum

- Public repository for versioned source-linked datasets, simulation packages, predictions and replication reports.
- Upload flow accepts physical lab data, model predictions, scripts and analysis packages but marks each record type distinctly.
- Attach a discussion / forum thread to every `experiment_id`, `simulation_run_id` or `prediction_id`.
- Other users can clone a case, reproduce analysis, submit validation/replication, comment on evidence and create a new linked record rather than editing the original.
- Use Discourse or GitHub Discussions for an MVP forum; later integrate deeper permissions/roles if needed.
- Roles: contributor, experiment owner, moderator, independent replicator, domain expert reviewer, platform administrator and authorized institutional reviewer.
- Version everything. Keep history of data changes, code releases, model releases and review decisions.

## Validation labels

Only use truthful states such as:
- `SOURCE-TRACEABLE`
- `NASA-DATA-REPLAYED` (the stated source dataset was replayed, not endorsed)
- `COMMUNITY-REPRODUCED`
- `INDEPENDENTLY-REVIEWED` (named reviewer and scope)
- `EXPERT-REVIEWED` (verified expertise and review scope)
- `NASA-AFFILIATED-INDIVIDUAL-REVIEWED` only if affiliation and permission verified; this is not institutional endorsement
- `NASA-INSTITUTIONALLY-VALIDATED` only with formal written authorization and documented institutional review scope

Do not have an automated system grant a NASA badge. A NASA reviewer may access the platform only if they choose to participate and are granted permission.

---

# 7. 3D lab experience and information bubbles

The first apparatus model is a **conceptual schematic**, not a manufactured-exact CAD reconstruction. Include:

- CIR chamber and rack context.
- MDCA insert / chamber interface.
- Fuel reservoir and syringe/line.
- Paired droplet deployment needles / motors.
- Liquid droplet with scale reference.
- Hot-wire igniters and retract motion.
- HiBMs backlight/camera path.
- LLUV camera path.
- MDCA colour camera and illumination.
- FOMA gas/environment control as a CIR facility subsystem, not an MDCA sensor.
- TSC/ground operator connection as a control / operations layer if shown.

Every object must have a hotspot bubble with:

1. Name and function.
2. What it measures / controls.
3. What happens during the original test sequence.
4. Source-linked evidence.
5. Measurement capability and uncertainty.
6. Limitations / what it cannot measure.
7. Adjustable parameters (if any) and their valid ranges.
8. Whether a displayed state is original evidence, computed physics, or an educational illustration.

The scene should let the learner pause at the stages: chamber preparation → fuel priming → droplet formation → needle separation/stretch → recording start → needle retraction/deployment → hot-wire ignition → igniter retraction → burn → recording stop. Use original NASA figure/video frames for comparison where licence permits.

---

# 8. Build phases and required deliverables

Do not attempt the entire platform at once. For each phase deliver a runnable artefact, tests, short report and known limitations.

### Phase 0 — source and data audit

Deliver:
- Source manifest and claim ledger.
- Test-data schema and unit convention.
- ID/provenance design.
- Data dictionary for original FLEX variables.
- Explicit list of missing / inaccessible original data or files.

Acceptance:
- No FLEX-2 contamination in the original-FLEX baseline.
- Each imported datum has source/test locator and original units preserved.
- NASA original IDs remain visible.

### Phase 1 — front-end skeleton

Deliver:
- Vite + HTML + TypeScript project.
- Responsive 3D scene with schematic apparatus.
- Hotspots and bubbles containing real linked source references.
- Parameter panel and clear `not yet simulated` placeholders.
- Basic Plotly chart layout.

Acceptance:
- No unsupported scientific values are displayed.
- A user can navigate the scene and inspect source notes.

### Phase 2 — original evidence replay and image analysis

Deliver:
- Original FLEX sample case page.
- Video/frame display with original test ID.
- Calibration and segmentation workflow.
- D(t), D²(t), visible flame size / LLUV OH* flame edge as separate series.
- FOV gap and uncertainty display.

Acceptance:
- Reproduce at least one documented source example and compare to NASA values.
- Manual review or ground-truth mask comparison documented.
- Measurement uncertainty visible and not rebranded as 95% CI.

### Phase 3 — statistics and reduced physical baseline

Deliver:
- D² fitting with selectable but documented time window.
- Regression residuals and fit uncertainty.
- Monte Carlo / bootstrap input propagation.
- SALib sensitivity for a small set of variables.
- Prediction/result cards with unique IDs and evidence lineage.

Acceptance:
- Every fit is a distinct `analysis_run_id` / `simulation_run_id`.
- Random seed and intervals recorded.
- No claims outside the fitted interval/domain.

### Phase 4 — transient spherical 1-D physics solver

Deliver:
- Documented equations, assumptions and interface conditions.
- Custom radial solver with Cantera chemistry/thermo/transport adapter.
- Fuel-specific mechanism manifests for methanol and n-heptane.
- Conservation, grid/time-step convergence and validation reports.

Acceptance:
- Conservation residuals and mesh/time convergence are reported.
- Validation on complete held-out FLEX test IDs by fuel and conditions.
- Model-form uncertainty / mechanism applicability limits visible.

### Phase 5 — PINN and neural-operator surrogate

Deliver:
- A reduced DeepXDE PINN or PhysicsNeMo prototype.
- An FNO/TFNO model trained on verified solver sweeps if dataset size/quality justify it.
- Benchmark: accuracy, speed, physics residual, interval coverage and OOD.

Acceptance:
- Solver is retained as ground/reference model.
- Test leakage is prevented at physical test ID level.
- Prediction uncertainty is calibrated or clearly marked exploratory.

### Phase 6 — open repository, forum and release workflow

Deliver:
- Upload, immutable dataset/model/run versions, review/replication pages.
- RO-Crate export and persistent release identifiers.
- Public discussion thread linked to experiment/run/prediction.
- Role-based review and badge workflow.

Acceptance:
- A second user can reproduce a released analysis using the package.
- No user can overwrite source record; new submissions are versioned.
- NASA badge is impossible without documented human authorization.

### Phase 7 — optional high-fidelity CFD

Only proceed with a defined research question and a custom coupled droplet model. Document numerical equations, boundary/interface treatment, radiation assumptions and independent benchmark. Do not label a generic reactingFoam case as validated original FLEX physics.

---

# 9. Testing and quality standards

Create:

- Unit tests for units/conversions, chemical mixture composition, ID creation, hashing, uncertainty functions, derived D² fit and FSR.
- Regression tests against selected published FLEX table values and defined source locators.
- Physics tests for positivity, conservation, limiting cases and convergence.
- Image tests with stable test fixtures and manually reviewed masks.
- API tests for job submission, status, authorization, immutable releases and version lineage.
- UQ tests for empirical coverage and interval width on held-out whole-test groups.
- Frontend tests that guarantee each state has the right evidence class / badge and shows an uncertainty status.
- End-to-end reproducibility test: clone a released RO-Crate, rerun analysis, compare output hashes/within documented tolerances.

Every figure exported from the app should include a caption/metadata footer: case ID, result class, source IDs, run/prediction ID, model/version, interval method, date and units.

---

# 10. Suggested repo structure

```text
flex-open-lab/
  README.md
  LICENSES.md
  CITATION.cff
  pyproject.toml
  uv.lock (or another single chosen lockfile)
  docker-compose.yml
  frontend/
    index.html
    src/components/
    src/scenes/
    src/data-viewers/
    src/api/
    tests/
  backend/
    app/api/
    app/schemas/
    app/services/
    app/repositories/
    app/workers/
  science/
    evidence/
    image_measurement/
    d2_baseline/
    spherical_droplet/
    cantera_adapter/
    mechanisms_manifest/
    uncertainty/
    ml/
    validation/
  data/
    manifests/
    sample_fixtures/
  experiments/
    schema/
    migrations/
    seed/
  models/
    model_cards/
    checkpoints_manifest/
  provenance/
    claims.yml
    sources.yml
    ro-crate-profiles/
  docs/
    architecture/
    scientific_model/
    validation/
    user_guide/
  tests/
    unit/
    integration/
    regression/
    physics/
    uncertainty/
    data_integrity/
  examples/
    original_flex_replay/
    synthetic_solver_case/
```

Do not commit large original raw media into Git. Use object storage and small rights-cleared sample fixtures.

---

# 11. How to work with the user

First inspect available files and source material, then return a precise Phase 0 plan and source audit. If a source cannot be opened, say so; do not guess its content. Before implementing each major phase, show the proposed deliverable and the scientific assumptions. After implementation, run tests and report exact pass/fail results. Keep the interface accessible and educational: students should understand what a parameter changes, which equation governs it, and how much uncertainty remains.

**Final north star:** build an open, evidence-traceable research environment in which a student can explore the actual original FLEX apparatus, a researcher can reproduce the source analysis, an engineer can change supported physical parameters, a validated physics solver predicts the corresponding behaviour, AI accelerates the work with quantified uncertainty, and another researcher can independently challenge or reproduce every released result.
