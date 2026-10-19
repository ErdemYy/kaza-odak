# SAFEROUTE 3D — MASTER PROJECT SPECIFICATION
Version: 1.0  
Project Type: Machine Learning + Geospatial Analytics + Interactive 3D Web Application  
Development Language: English for code identifiers, Turkish for application UI, reports and academic explanations.

## 1. Project Vision

Develop SafeRoute 3D, a professional, interactive, 3D road-safety analytics platform using real New York City motor vehicle collision records.

The application must discover geographic collision concentration patterns using unsupervised machine learning and visualize them on a real geographically aligned 3D city map.

This is an academic machine learning project and a functional software product, not merely a UI prototype.

The project must prioritize reproducible scientific results, correct geospatial analysis, interpretable machine learning, realistic 3D assets, and professional frontend design.

## 2. Geographical Scope

Support all five New York City boroughs:

- Manhattan
- Brooklyn
- Queens
- Bronx
- Staten Island

Users must be able to analyze the entire city or select individual boroughs.

The system must distinguish the dataset's reported borough value from a geometrically inferred borough, when boundary-based enrichment is implemented.

## 3. Official Dataset

Primary source:
https://data.cityofnewyork.us/d/h9gi-nx95

Catalog:
https://catalog.data.gov/dataset/motor-vehicle-collisions-crashes

Dataset ID: h9gi-nx95

Each row represents a reported crash event.

Important requirements:

- Retrieve the real source data, never generate fake crash records.
- Record source URL, download timestamp, data version where available, row count, column count, coverage dates and file checksum.
- Check the source's update status and explicitly disclose data freshness limitations.
- Preserve immutable raw datasets.
- Do not assume historical row counts or field completeness.
- Do not silently replace missing data with fabricated values.
- Download using a documented export or API method with pagination/retry support as appropriate.
- Handle incomplete downloads and external service failures gracefully.

## 4. Machine Learning Objective

Primary objective:

Identify spatial concentrations of recorded traffic crashes and analyze how these concentrations vary with selected date ranges, time intervals, boroughs and crash attributes.

The application is not a future collision prediction system.

Collision density is not automatically equivalent to crash risk per vehicle or pedestrian.

### Primary Algorithm: DBSCAN

Use DBSCAN with geographically valid distance calculations.

For geographic coordinates, support the Haversine metric with latitude/longitude converted to radians. Express the user-facing distance parameter in meters, converted internally to angular distance.

Avoid Euclidean distance on unprocessed latitude/longitude degrees.

DBSCAN must support:

- eps in meters
- min_samples
- cluster membership
- noise identification
- number of clusters
- cluster counts and geographic summaries
- parameter sensitivity experiments

### Comparison Algorithms

K-Means:
- Use an appropriate projected coordinate system or metric coordinate representation.
- Support multiple values of k.
- Explain its limitations for irregular density-based geographic patterns.

HDBSCAN:
- Support variable-density clustering.
- Expose min_cluster_size and relevant parameters.
- Record noise and cluster stability information when available.

Do not declare one algorithm universally best without experimental evidence.

## 5. Features and Data Processing

The raw dataset includes fields for coordinates, collision date/time, injuries, fatalities, vehicle types and contributing factors.

Separate features into categories:

### Model Features
- Latitude
- Longitude
- Experimental temporal features, where justified

### Filtering Features
- Borough
- Date/year
- Time range
- Vehicle type
- Contributing factor
- Injury/fatality status

### Descriptive and Evaluation Features
- Injury counts
- Fatality counts
- Collision counts
- Cluster temporal profiles
- Vehicle categories

### Excluded or Non-predictive Model Fields
- Collision identifiers
- Duplicated geographic representations
- Metadata that does not meaningfully contribute to the selected feature space

The initial production clustering experiment must use geographic coordinates.

Time-inclusive clustering is an experimental alternative and requires an explicitly documented space-time distance strategy.

Required preprocessing:
- Missing-value audit
- Duplicate identifier investigation
- Coordinate validation
- Geographic boundary checks
- Date/time parsing
- Invalid-value detection
- Clear exclusion reasons and counts
- Feature engineering
- Feature-selection rationale
- Reproducible pipeline execution

Preserve records with missing coordinates in the raw source; exclude them only from analyses requiring valid geography.

## 6. Academic Evaluation

Implement scientifically justified comparisons.

Evaluate:
- Cluster count
- Noise proportion where applicable
- Cluster sizes
- Spatial interpretability
- Silhouette Score where appropriate
- Davies–Bouldin Index where appropriate
- Density-based evaluation such as DBCV where feasible
- Temporal stability
- Parameter sensitivity
- Execution time and memory use

Do not treat noise points as ordinary clusters when evaluating density-based models.

Explain when a metric is undefined or inappropriate.

Use comparable datasets, explicit preprocessing and clearly documented feature spaces for fair comparisons.

Keep training/fit experiments and evaluation reproducible using recorded configuration, software versions and random seeds where applicable.

## 7. Interactive Application

Build the following screens:

### Dashboard
- Total available collision records
- Analyzed records
- Date coverage
- Borough-level summaries
- Model experiment summaries
- Data freshness information

### 3D City Explorer
- Real georeferenced NYC map
- Extruded 3D buildings
- Camera orbit/pan/zoom/pitch controls
- Collision point visualization
- Cluster visualization
- Animated geographic focus
- Borough selection
- Day/night visual mode
- Time-based collision playback
- Clear distinction between recorded collision data and decorative animation

### Clustering Lab
- Algorithm selector
- Dynamic parameter controls
- Filter controls
- Feature selection with validity constraints
- Actual backend computation
- Progress, errors and result handling
- Cluster statistics
- Comparison views

### Data Explorer
- Dataset metadata
- Raw and cleaned record counts
- Missing-value summaries
- Feature dictionary
- Data-cleaning transformations
- Exploratory charts

### Model Comparison
- Algorithm configuration
- Evaluation metrics
- Experiment metadata
- Parameter sensitivity
- Comparison tables and plots

No fabricated algorithm results or static metrics may masquerade as live results.

## 8. 3D Assets and Geospatial Rendering

Use MapLibre GL JS for georeferenced map visualization and 3D building extrusions.

Use Three.js for GLB/glTF models, custom geographic overlays and animated visual elements where technically appropriate.

Use actual downloadable, appropriately licensed third-party 3D assets for detailed cars, buses, traffic lights and urban props.

Preferred licensing: CC0 or compatible Creative Commons licenses with fulfilled attribution requirements.

Maintain an asset registry recording:
- Asset name
- Source URL
- Author
- License
- Attribution obligations
- File size
- Polycount/triangle count when available
- Optimization status

Optimize assets for browser rendering.

Avoid loading thousands of high-poly vehicles into the scene.

Never confuse decorative traffic animation with historically observed vehicle movement.

## 9. Design System

Direction: Premium Dark Urban Intelligence.

Typography:
- Plus Jakarta Sans: headings and primary metrics
- Manrope: paragraphs, control labels and navigation
- Tabular numerals for quantitative dashboards

Color tokens:
- Background: #0B1120
- Surface: #111C30
- Primary: #38BDF8
- Warning: #F59E0B
- Hotspot: #F87171
- Text: #E2E8F0

Use restrained gradients, professional panel layouts, fine borders, balanced whitespace and purposeful motion.

Avoid excessive neon effects and generic AI-generated dashboard aesthetics.

Frontend must be responsive, accessible and usable on desktop.

Provide meaningful loading, empty, error and success states.

Ensure Turkish text is natural and properly rendered.

## 10. Technology Stack

Frontend:
- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- MapLibre GL JS
- Three.js
- Recharts or Plotly

Backend and ML:
- Python
- FastAPI
- pandas
- NumPy
- scikit-learn
- HDBSCAN-compatible implementation
- GeoPandas and Shapely where needed
- pytest

Data:
- Parquet for reproducible intermediate data
- PostgreSQL + PostGIS for production-oriented geographic queries in later phases

Testing:
- pytest
- frontend unit/component tests
- Playwright for end-to-end testing

Use currently compatible stable dependency versions after checking their official documentation.

## 11. Performance and Safety

Do not run expensive clustering on the frontend main thread.

For large workloads use backend jobs, progress reporting and caching.

Avoid naive algorithms on the full multimillion-row dataset without measuring runtime and memory use.

Spatial aggregation or spatially indexed strategies may be necessary for whole-city analysis.

Document how aggregation changes the meaning of the result; do not claim equivalence to exact record-level DBSCAN without justification.

Validate all user inputs and API parameters.

Do not expose secrets in source control.

## 12. Development Phases

Phase 1 — Dataset Foundation and EDA

Phase 2 — Preprocessing, Feature Engineering and Feature Selection

Phase 3 — Clustering Models, Evaluation and Comparison

Phase 4 — Real NYC 3D City and Licensed GLB Assets

Phase 5 — Professional Frontend and Interactive Analysis Screens

Phase 6 — Backend Integration, Performance Optimization and End-to-End Tests

Phase 7 — Academic Report, Presentation and Demo Preparation

Do not implement a future phase prematurely.

Each phase requires:
- Working code
- Automated tests where relevant
- Documentation
- Measured results
- Known limitations
- Explicit acceptance checklist
- Git commit after successful verification, if repository access permits

## 13. Academic Integrity and Presentation Readiness

Every analytical claim must be traceable to:
- Dataset
- Source version
- Preprocessing transformation
- Algorithm
- Parameters
- Output artifact

Maintain readable, modular code.

Document important functions in Turkish where this helps academic presentation.

Never claim model accuracy for an unsupervised clustering result without an appropriate ground-truth evaluation design.

Never invent dataset statistics, training outcomes, performance improvements or model evaluation scores.

## 14. Definition of Done

SafeRoute 3D is complete when:

- Real NYC collision data is successfully processed.
- All five boroughs are supported.
- DBSCAN clustering works on genuine selected records.
- K-Means and HDBSCAN comparisons are reproducible.
- Feature selection and preprocessing can be defended academically.
- The application displays genuine results in a geographically accurate 3D environment.
- Licensed GLB models are integrated and optimized.
- Interactive user controls trigger real analysis.
- Tests and documentation are available.
- The project can be demonstrated locally with a repeatable setup.
- The academic presentation explains the full pipeline from raw data to 3D interpretation.

The goal is a scientifically credible, visually sophisticated, professionally engineered application.
