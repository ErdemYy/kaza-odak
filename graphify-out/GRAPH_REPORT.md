# Graph Report - SAFEROUTE 3D  (2026-10-22)

## Corpus Check
- 375 files · ~7,908,827 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 75 file(s) not represented in the graph (top: .log 32, .glb 15, .csv 11)

## Summary
- 2666 nodes · 7018 edges · 132 communities (108 shown, 24 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 304 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7b4c0cbb`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Development Workflow (7 steps)
- profile.py
- cn
- download_snapshot
- download.py
- SAFEROUTE 3D — MASTER PROJECT SPECIFICATION
- clustering/report.py
- README.md
- test_profile.py
- Faz 1 — Otomatik EDA Raporu
- standardize
- saferoute
- pipeline.py
- 2. Sınıflar
- Faz 1 Tamamlanma Raporu — Veri Seti Temeli, Proje İskeleti ve Keşifsel Veri Analizi
- Faz 2 kararları
- Veri Kökeni (Provenance)
- Phase3Runner
- JobStore
- run_phase1.sh
- Kaza Odak — Ön Yüz (Faz 5 analiz uygulaması; önceki adı SafeRoute 3D)
- CityMap.tsx
- validate.py
- Faz 2 Kapanış Raporu — Veri Ön İşleme, Öznitelik Mühendisliği ve Öznitelik Seçimi
- LabelResult
- LabPage.tsx
- SafeRoute 3D — Faz 5 Teknik Raporu: Profesyonel Ön Yüz, İnteraktif Analiz ve Kümeleme Laboratuvarı
- JobManager
- json
- SafeRoute 3D — Faz 8 Teknik Raporu: Profesyonel Arayüz Cilası, Logo Yenileme ve Tam İşlevsel Denetim
- Faz 2 — Otomatik Ön İşleme Raporu
- evaluation.py
- FilterSpec
- metadata.py
- run_phase2.sh
- phase8b.visual.ts
- numpy
- algorithms.py
- filters.ts
- Faz 3 — Otomatik Kümeleme Deney Raporu
- phase6_geo_benchmark.py
- geo.py
- lab_worker.py
- vehicles.py
- ExperimentResults.tsx
- pandas
- create_app
- run_phase3.sh
- geo.ts
- CityModelsLayer
- test_viz_layers_api.py
- package.json
- cli.py
- SafeRoute 3D — Faz 4 Teknik Raporu: Gerçek NYC 3D Şehir Görüntüleyici ve GLB Varlıkları
- optimize-assets.mjs
- phase8b.test.tsx
- devDependencies
- App.tsx
- run_pipeline
- ModelPreview.tsx
- compilerOptions
- eda/report.py
- viewer.spec.ts
- test_preprocess_geo.py
- jobs.py
- audit-building-heights.mjs
- ._run
- scripts
- ui-logic.test.ts
- dependencies
- register
- run_phase4.sh
- phase8.spec.ts
- ExplorerPage.tsx
- columns_from_frame
- components.json
- phase5-components.test.tsx
- catalog.py
- phase5.spec.ts
- assets.test.ts
- store.ts
- time
- test_analytics.py
- SafeRoute 3D — Faz 6 Teknik Raporu: Sistem Stabilizasyonu, Güvenilirlik, Performans ve Uçtan Uca Entegrasyon
- Registry
- phase8_brand.py
- perf.py
- phase6.spec.ts
- test_loader.py
- casualties.py
- PreprocessConfig
- ._recover
- phase8b.spec.ts
- phase6-restart.spec.ts
- common.tsx
- SafeRoute 3D — Logo Kullanım Kuralları (Faz 8)
- Ayrıntılar
- SafeRoute 3D — Faz 8: Arayüz Kalite Raporu
- start_saferoute.ps1
- 3D varlık kaydı (Faz 4)
- Analytics
- runner.py
- ._finish
- ExportMenu
- test_clustering_pipeline.py
- 7. Interactive Application
- SafeRoute 3D — Faz 8B Regresyon Sonuçları
- smoothTextureSampling
- conftest.py
- GELISTIRME.md
- execute_notebook.py
- 5. Features and Data Processing
- 2. Ekran bazında değerlendirme
- .stage_review
- SafeRoute 3D — Faz 8: Fonksiyonel Test Envanteri
- SafeRoute 3D — Faz 8: Bulunan ve Düzeltilen Hatalar
- .submit
- reporting.py
- Karar Günlüğü
- Kaza Odak — Geliştirici Rehberi
- SafeRoute 3D — Faz 8B Teknik Raporu: Görsel İyileştirme ve 3D Deneyim Kalitesi
- duplicates.py

## God Nodes (most connected - your core abstractions)
1. `cn()` - 120 edges
2. `register()` - 58 edges
3. `fmtInt()` - 51 edges
4. `run_pipeline()` - 47 edges
5. `react` - 44 edges
6. `JobManager` - 40 edges
7. `ExplorerPage()` - 40 edges
8. `FilterSpec` - 39 edges
9. `Phase3Runner` - 39 edges
10. `_save()` - 38 edges

## Surprising Connections (you probably didn't know these)
- `6. Filtreleme işlevleri` --references--> `FilterSpec`  [INFERRED]
  docs/phase5/TEKNIK_RAPOR.md → backend/src/saferoute/analytics/filters.py
- `K-08 — Depo yapısında şartname örneğinden farklar (2026-10-19, Faz 1)` --references--> `profile()`  [INFERRED]
  docs/decision_log.md → backend/src/saferoute/analytics/results.py
- `17. Test sonuçları` --references--> `map_uniques()`  [INFERRED]
  docs/phase2/TEKNIK_RAPOR.md → backend/src/saferoute/preprocess/standardize.py
- `9. Tarih/saat ve anomali işlemleri` --references--> `time_period()`  [INFERRED]
  docs/phase2/TEKNIK_RAPOR.md → backend/src/saferoute/preprocess/temporal.py
- `H06 — GLB modelini kaldırma (Düşük)` --references--> `AssetInspector()`  [INFERRED]
  docs/phase8/BULUNAN_VE_DUZELTILEN_HATALAR.md → frontend/src/components/AssetInspector.tsx

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **SafeRoute 3D development principles** — claude_phase_based_development, claude_graphify_not_single_source_of_truth, claude_preserve_user_code, claude_tests_and_technical_report, claude_turkish_language_rule [EXTRACTED 1.00]
- **Graphify CLI investigation and maintenance toolset** — claude_graphify_query, claude_graphify_path, claude_graphify_explain, claude_graphify_update, claude_graphify_out [EXTRACTED 1.00]

## Communities (132 total, 24 thin omitted)

### Community 0 - "Development Workflow (7 steps)"
Cohesion: 0.12
Nodes (13): Graphify Skill (.claude/skills/graphify/SKILL.md), Development Workflow (7 steps), graphify-out/graph.json, GRAPH_REPORT.md, graphify explain, graphify-out/ Knowledge Graph, graphify path, graphify query (+5 more)

### Community 1 - "profile.py"
Cohesion: 0.11
Nodes (27): borough_status(), _n(), _pct(), render_data_dictionary(), _as_text(), _blank_mask(), borough_by_coordinate_class(), boroughs() (+19 more)

### Community 2 - "cn"
Cohesion: 0.06
Nodes (54): Checkbox(), DialogContent(), DialogDescription(), DialogFooter(), DialogHeader(), DialogOverlay(), DialogPortal(), DialogTitle() (+46 more)

### Community 4 - "download_snapshot"
Cohesion: 0.21
Nodes (17): download_snapshot(), DownloadError, FakeSession, read_manifest(), test_client_error_is_not_retried(), test_completed_snapshot_is_never_overwritten(), test_exhausted_retries_leave_resumable_state(), test_full_download_writes_parts_manifest_and_checksums() (+9 more)

### Community 5 - "download.py"
Cohesion: 0.11
Nodes (10): count_csv_rows(), _download_page(), _make_read_only(), _TransientError, _utc_now(), _write_json(), make_session(), download_boundaries() (+2 more)

### Community 6 - "SAFEROUTE 3D — MASTER PROJECT SPECIFICATION"
Cohesion: 0.12
Nodes (15): 10. Technology Stack, 11. Performance and Safety, 12. Development Phases, 13. Academic Integrity and Presentation Readiness, 14. Definition of Done, 1. Project Vision, 2. Geographical Scope, 3. Official Dataset (+7 more)

### Community 7 - "clustering/report.py"
Cohesion: 0.10
Nodes (55): _exp_label(), _f(), fig_dbscan_grid(), fig_equivalence(), fig_hdbscan(), fig_kdistance(), fig_kmeans_elbow(), fig_maps() (+47 more)

### Community 8 - "README.md"
Cohesion: 0.14
Nodes (13): Akademik teslim dosyaları, Depo yapısı, Ekranlar, Hızlı başlangıç, İçindekiler, Makine Öğrenmesi ile Trafik Kazalarının Mekânsal Analizi ve 3D Görselleştirilmesi, Mimari, Sınırlılıklar (+5 more)

### Community 9 - "test_profile.py"
Cohesion: 0.10
Nodes (8): to_frame(), test_candidate_identifier_detected(), test_empty_input_produces_zero_profile(), test_missing_column_raises_schema_error(), test_missing_values_separates_null_and_blank(), test_profile_does_not_mutate_and_is_json_serialisable(), test_quality_by_year(), test_unexpected_and_lowercase_borough_labels()

### Community 10 - "Faz 1 — Otomatik EDA Raporu"
Cohesion: 0.15
Nodes (13): 10. Metin alanları, 11. Çalışma süresi ve bellek, 1. Kaynak ve anlık görüntü, 2. Veri güncelliği, 3. Eksik değerler, 4. Kimlik ve tekrar analizi, 5. Zaman alanları, 6. Koordinatlar ve coğrafi sınır kontrolü (+5 more)

### Community 11 - "standardize"
Cohesion: 0.15
Nodes (11): Komutlar, Kurulum, Modüller, SafeRoute 3D — Arka Uç (Python), Testler, _clean_text(), location_consistency(), map_uniques() (+3 more)

### Community 13 - "pipeline.py"
Cohesion: 0.08
Nodes (14): experiment_id(), ConfigError, load_config(), stable_hash(), file_sha256(), _software_versions(), IntegrityError, read_manifest() (+6 more)

### Community 15 - "2. Sınıflar"
Cohesion: 0.12
Nodes (15): 1. Sınıflandırma ilkeleri, 2. Sınıflar, 3. Önerilen deneyler (Faz 3 — bu fazda çalıştırılmadı), 4. Geometrik ilçe zenginleştirme stratejisi (Faz 2), A. Coğrafi model özellikleri, B. Zamansal model özellikleri (deneysel), C. Yalnızca filtre alanları, D. Betimleyici / sonuç alanları (+7 more)

### Community 16 - "Faz 1 Tamamlanma Raporu — Veri Seti Temeli, Proje İskeleti ve Keşifsel Veri Analizi"
Cohesion: 0.13
Nodes (14): 10. Çalıştırılan testler ve sonuçları, 11. Önemli sınırlılıklar, 12. Faz 2 için önerilen adımlar, 1. Uygulananlar, 2. Gerçek satır sayısı, 3. Gerçek sütun sayısı, 4. İndirme ve kaynak durumu, 5. Eksik koordinat istatistikleri (+6 more)

### Community 17 - "Faz 2 kararları"
Cohesion: 0.10
Nodes (20): Faz 2 kararları, K-11 — Katman yapısı ve idempotentlik (2026-10-19, Faz 2), K-12 — İlçe çıkarımında yüklem: `covered_by` (intersects) ve belirsizlik politikası (2026-10-19, Faz 2), K-13 — Kıyıya yakınlık tamponu 500 m (2026-10-19, Faz 2), K-14 — Eksik değer doldurma yapılmaz (2026-10-19, Faz 2), K-15 — Bildirilen ilçe çelişkide korunur (2026-10-19, Faz 2), K-16 — Yedek geokodlama şüphesi bayrağı (2026-10-19, Faz 2), K-17 — 00:00 kayıtları: bayrak, dönüşüm yok (2026-10-19, Faz 2) (+12 more)

### Community 18 - "Veri Kökeni (Provenance)"
Cohesion: 0.22
Nodes (8): status(), Bu projede kullanılan anlık görüntü, Edinim yöntemi, Faz 2'de indirilen anlık görüntü, Gelecekteki ilçe sınırı kaynağı (Faz 2), Güncellik değerlendirmesi, Kaynak, Veri Kökeni (Provenance)

### Community 22 - "Kaza Odak — Ön Yüz (Faz 5 analiz uygulaması; önceki adı SafeRoute 3D)"
Cohesion: 0.40
Nodes (4): Kaza Odak — Ön Yüz (Faz 5 analiz uygulaması; önceki adı SafeRoute 3D), Komutlar, Yapı, Çalıştırma

### Community 24 - "CityMap.tsx"
Cohesion: 0.09
Nodes (38): MapSource, ViewportInfo, CityMap, CityMapProps, endpoints(), hoverCard(), INITIAL_BOUNDS, LoadState (+30 more)

### Community 25 - "validate.py"
Cohesion: 0.10
Nodes (15): check_schema(), null_percentage(), parse_crash_date(), parse_crash_time(), require_columns(), SchemaError, SchemaReport, test_borough_status() (+7 more)

### Community 26 - "Faz 2 Kapanış Raporu — Veri Ön İşleme, Öznitelik Mühendisliği ve Öznitelik Seçimi"
Cohesion: 0.08
Nodes (24): 10. Araç türü eşleme sonuçları, 11. Oluşturulan yeni öznitelikler (processed katmanı, 56 yeni sütun), 12. Elenen veya yalnızca filtrede kullanılan öznitelikler, 13. DBSCAN için hazırlanan matris (Model A), 14. K-Means için hazırlanan matris (Model B), 15. HDBSCAN için hazırlanan matris (Model C) ve deneysel Model D, 16. Notebook doğrulama sonucu, 17. Test sonuçları (+16 more)

### Community 27 - "LabelResult"
Cohesion: 0.13
Nodes (7): days_to_date(), group_quantile(), LabelResult, profile(), size_histogram(), utm_to_wgs84(), test_label_result_summary_and_kmeans_noise_na()

### Community 28 - "LabPage.tsx"
Cohesion: 0.08
Nodes (44): DictRow, AlgorithmControls(), ALGOS, Algorithm, budgetWarnings(), DEFAULT_PARAMS, defaultForm(), LabForm (+36 more)

### Community 29 - "SafeRoute 3D — Faz 5 Teknik Raporu: Profesyonel Ön Yüz, İnteraktif Analiz ve Kümeleme Laboratuvarı"
Cohesion: 0.10
Nodes (21): FeatureSpec, 0. Başlangıç incelemesi, 10. Zaman oynatma, 11. Küme detayları, 12. Erişilebilirlik, 13. Responsive tasarım, 14. Performans ölçümleri, 15. Görsel test bulguları (+13 more)

### Community 31 - "json"
Cohesion: 0.12
Nodes (9): snapshot_to_parquet(), load_parquet(), acquisition_record(), test_full_acquisition_record(), test_parquet_copy_is_lossless_and_idempotent(), test_record_requires_snapshot_files(), cell(), main() (+1 more)

### Community 32 - "SafeRoute 3D — Faz 8 Teknik Raporu: Profesyonel Arayüz Cilası, Logo Yenileme ve Tam İşlevsel Denetim"
Cohesion: 0.14
Nodes (14): 0. Başlangıç incelemesi, 10. Regresyon testleri, 11. Responsive ve erişilebilirlik, 12. Bilinen sınırlılıklar, 14. Git, 2. Değiştirilen ve eklenen dosyalar, 3. Görsel kalite iyileştirmeleri, 4. Etkileşim testleri (Playwright, gerçek sunucu) (+6 more)

### Community 33 - "Faz 2 — Otomatik Ön İşleme Raporu"
Cohesion: 0.17
Nodes (12): 10. Öznitelik matrisleri, 11. Çalışma süresi ve bellek, 1. Soy (lineage) ve katmanlar, 2. Faz 1 sayılarının doğrulanması, 3. Resmî ilçe sınırları, 4. Koordinat kalitesi, 5. İlçe çıkarımı, 6. Zaman öznitelikleri ve 00:00 (+4 more)

### Community 34 - "evaluation.py"
Cohesion: 0.14
Nodes (12): ari(), cluster_stats(), compare_partitions(), davies_bouldin(), dbcv(), footprint(), jaccard(), match_centroids() (+4 more)

### Community 36 - "metadata.py"
Cohesion: 0.15
Nodes (9): assess_freshness(), check_source(), _days_between(), _now(), _epoch_to_iso(), fetch_metadata(), fetch_server_stats(), test_assess_freshness() (+1 more)

### Community 39 - "phase8b.visual.ts"
Cohesion: 0.28
Nodes (7): Cam, CAMS, consoleErrors, idle(), openExplorer(), OUT, scenes

### Community 40 - "numpy"
Cohesion: 0.10
Nodes (29): haversine_m(), project(), projection_check(), to_radians(), _duplicated_sample(), _pts(), test_cluster_stats_and_noise_handling(), test_degree_input_is_rejected_as_non_radian() (+21 more)

### Community 41 - "algorithms.py"
Cohesion: 0.17
Nodes (11): _check_radians(), count_neighbor_pairs(), dbscan_haversine(), hdbscan_projected(), InvalidParameter, kmeans_projected(), ResourceLimitExceeded, validate_dbscan() (+3 more)

### Community 42 - "filters.ts"
Cohesion: 0.11
Nodes (13): activeCount(), applySlice(), DOWS_TR, EMPTY_FILTERS, FatalFilter, InjuryFilter, MONTHS_TR, normalize() (+5 more)

### Community 43 - "Faz 3 — Otomatik Kümeleme Deney Raporu"
Cohesion: 0.07
Nodes (27): 1. Amaç ve kapsam, 2. Yöntem, 3. Deney envanteri, 4.1 Seçilen konfigürasyonlar, 4.2 `eps=25 m, min_samples=100` seçiminin yeniden değerlendirilmesi, 4.3 Zamansal kararlılık ve kaza hacmi, 4.4 Veri kalitesi duyarlılığı, 4.5 En önemli gerçek kaza kümeleri (seçilen DBSCAN, olay sayısına göre) (+19 more)

### Community 44 - "phase6_geo_benchmark.py"
Cohesion: 0.18
Nodes (4): run_benchmark(), fetch(), main(), tile_xy()

### Community 45 - "geo.py"
Cohesion: 0.08
Nodes (15): cluster_profiles(), load_profile_columns(), _top(), assert_geographic_nyc(), BoundaryValidationError, CRSMismatchError, ensure_same_crs(), load_boundaries() (+7 more)

### Community 46 - "lab_worker.py"
Cohesion: 0.16
Nodes (8): _metrics(), ResourceRejected, run_job(), st_dbscan(), _stage(), _write_json(), available_memory_mb(), peak_memory_mb()

### Community 47 - "vehicles.py"
Cohesion: 0.22
Nodes (5): add_vehicle_features(), build_mapping_table(), categorize(), mapping_summary(), normalize_label()

### Community 48 - "ExperimentResults.tsx"
Cohesion: 0.11
Nodes (68): 3. Tasarım sistemi, AXIS, BarDatum, CHART, ColumnChart(), RowChart(), SweepChart(), TipBox() (+60 more)

### Community 49 - "pandas"
Cohesion: 0.14
Nodes (17): make_row(), make_events(), _dup_frame(), _interim(), test_casualty_flags_never_overwrite_raw(), test_duplicate_coordinates_are_preserved_with_weights(), test_geocode_fallback_flag(), test_location_consistency_handles_socrata_prefix() (+9 more)

### Community 50 - "create_app"
Cohesion: 0.08
Nodes (11): allowed_hosts(), _cluster_light(), create_app(), cluster_geometries(), clusters(), density(), points(), LayerStore (+3 more)

### Community 53 - "geo.ts"
Cohesion: 0.14
Nodes (27): CameraAction, CityMapHandle, anchorMatrix(), bearingDeg(), closestPointOnSegment(), EARTH_RADIUS_M, fromMercator(), haversineM() (+19 more)

### Community 54 - "CityModelsLayer"
Cohesion: 0.23
Nodes (4): AssetRecord, CityModelsLayer, prepare(), radialTexture()

### Community 55 - "test_viz_layers_api.py"
Cohesion: 0.07
Nodes (30): latest_boundaries(), borough_layer(), build_layers(), check_lon_lat_order(), walk(), cluster_records(), density_grid(), _json_list() (+22 more)

### Community 56 - "package.json"
Cohesion: 0.09
Nodes (23): name, private, type, version, clsx, @fontsource/manrope, @fontsource/plus-jakarta-sans, jsdom (+15 more)

### Community 57 - "cli.py"
Cohesion: 0.27
Nodes (16): _cmd_boundaries(), _cmd_check_source(), _cmd_cluster(), _cmd_download(), _cmd_eda(), _cmd_parquet(), _cmd_phase5_bench(), _cmd_preprocess() (+8 more)

### Community 58 - "SafeRoute 3D — Faz 4 Teknik Raporu: Gerçek NYC 3D Şehir Görüntüleyici ve GLB Varlıkları"
Cohesion: 0.10
Nodes (20): 10. Gürültü noktalarının yönetimi, 11. Harita katmanları, 13. Etkileşim özellikleri, 14. Animasyonlar, 15. Performans ölçümleri, 16. Ekran görüntüleri, 17. Test sonuçları, 19. Git commit kimliği (+12 more)

### Community 59 - "optimize-assets.mjs"
Cohesion: 0.10
Nodes (15): glbToJSONDocument(), readZip(), DOWNLOADS, here, io, KENNEY, NOT_USED, OUT (+7 more)

### Community 60 - "phase8b.test.tsx"
Cohesion: 0.08
Nodes (34): 1. Önceki görsel sorunlar ve kök nedenleri, 3. 3D şehir iyileştirmeleri, LAYERS, addDataLayers(), applyVisibility(), CENTROID_SCALE, COLORS, EMPTY (+26 more)

### Community 61 - "devDependencies"
Cohesion: 0.09
Nodes (23): devDependencies, @axe-core/playwright, @gltf-transform/core, @gltf-transform/extensions, @gltf-transform/functions, jsdom, @mapbox/vector-tile, meshoptimizer (+15 more)

### Community 62 - "App.tsx"
Cohesion: 0.09
Nodes (38): 13. Graphify güncellemesi, 1. Yenilenen logo, App(), DataPage, LabPage, ModelsPage, OverviewPage, hashFor() (+30 more)

### Community 63 - "run_pipeline"
Cohesion: 0.10
Nodes (19): build_feature_sets(), feature_selection_table(), feature_set_summary(), build_summary(), _counts(), output_paths(), _phase1_crosscheck(), run_pipeline() (+11 more)

### Community 64 - "ModelPreview.tsx"
Cohesion: 0.18
Nodes (17): Faz 8B yeni testleri, 13. Graphify, 5. GLB önizleme özellikleri, act(), debug(), Engine, HOME_DIR, ModelPreview() (+9 more)

### Community 65 - "compilerOptions"
Cohesion: 0.11
Nodes (17): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noEmit, noFallthroughCasesInSwitch (+9 more)

### Community 66 - "eda/report.py"
Cohesion: 0.17
Nodes (8): freshness(), _n(), _p(), _parse_ts(), render_markdown(), run_eda(), StepTimer, test_freshness_measures_lags_and_recent_months()

### Community 67 - "viewer.spec.ts"
Cohesion: 0.24
Nodes (10): clusterAtScreen(), HERE, idle(), LngLat, measurements, modelDrift(), open(), PERF (+2 more)

### Community 68 - "test_preprocess_geo.py"
Cohesion: 0.16
Nodes (9): d(), pipeline_rows(), synthetic_boroughs(), _rows(), classified(), test_boundary_point_handling(), test_input_frame_is_not_mutated(), test_nearshore_eligibility_is_configurable() (+1 more)

### Community 69 - "jobs.py"
Cohesion: 0.11
Nodes (10): dynamic_experiment_id(), EmptyScope, NotRetryable, QueueFull, capabilities(), _int(), LabRequestError, _num() (+2 more)

### Community 70 - "audit-building-heights.mjs"
Cohesion: 0.15
Nodes (9): all, here, OUT, result, SAMPLES, tj, @mapbox/vector-tile, pbf (+1 more)

### Community 71 - "._run"
Cohesion: 0.13
Nodes (5): create_time(), kill_tree(), Sampler, _win_structs(), WorkerGuard

### Community 72 - "scripts"
Cohesion: 0.22
Nodes (9): scripts, assets, build, dev, e2e, preview, test, tiles:audit (+1 more)

### Community 73 - "ui-logic.test.ts"
Cohesion: 0.26
Nodes (12): BOROUGH_ORDER, boroughTarget(), cityTarget(), clusterTarget(), DEFAULT_BEARING, DEFAULT_PITCH, durationFor(), FlyTarget (+4 more)

### Community 74 - "dependencies"
Cohesion: 0.13
Nodes (15): dependencies, class-variance-authority, clsx, @fontsource/manrope, @fontsource/plus-jakarta-sans, lucide-react, maplibre-gl, radix-ui (+7 more)

### Community 75 - "register"
Cohesion: 0.09
Nodes (26): _bbox(), register(), export_records(), export_result(), job_or_404(), jobs(), lab_cancel(), lab_capabilities() (+18 more)

### Community 79 - "phase8.spec.ts"
Cohesion: 0.08
Nodes (20): 12. Kamera özellikleri, a11y, failures, flyTo(), HERE, logs, mapIdle(), measurements (+12 more)

### Community 80 - "ExplorerPage.tsx"
Cohesion: 0.10
Nodes (43): 0. Ön inceleme, 1. Geliştirilen altyapı, AssetInspector(), Field(), BUTTONS, CameraControls(), Legend(), Badge() (+35 more)

### Community 81 - "columns_from_frame"
Cohesion: 0.13
Nodes (7): columns_from_frame(), density_cells(), EventColumns, test_columns_from_frame_handles_plain_strings(), test_real_store_matches_phase4_layer(), world(), real()

### Community 82 - "components.json"
Cohesion: 0.11
Nodes (17): aliases, components, hooks, lib, ui, utils, iconLibrary, rsc (+9 more)

### Community 83 - "phase5-components.test.tsx"
Cohesion: 0.15
Nodes (7): Tabs(), TabsContent(), TabsList(), tabsListVariants, TabsTrigger(), DataPage(), COMPARISON

### Community 84 - "catalog.py"
Cohesion: 0.13
Nodes (12): get_overview(), data_dictionary(), _group_of(), _latest(), overview(), parquet_null_counts(), Phase3Catalog, _read_json() (+4 more)

### Community 85 - "phase5.spec.ts"
Cohesion: 0.18
Nodes (6): a11y, HERE, mapIdle(), measurements, openExplorer(), SHOTS

### Community 86 - "assets.test.ts"
Cohesion: 0.18
Nodes (12): bufferCache, fetchGlb(), loader(), loadGlb(), ModelLoadError, validateGlbHeader(), PUB, registry (+4 more)

### Community 87 - "store.ts"
Cohesion: 0.20
Nodes (16): AppState, FocusRequest, initialMotion(), Route, FilterState, Granularity, TimeSlice, defaultVisibility() (+8 more)

### Community 88 - "time"
Cohesion: 0.13
Nodes (19): api(), write_catalog(), client(), make_client(), pdir(), _sleeper(), test_cancel_running_job_terminates_worker(), test_completed_job_and_result_survive_restart() (+11 more)

### Community 89 - "test_analytics.py"
Cohesion: 0.11
Nodes (20): _bool(), build_mask(), _date(), date_to_days(), FilterError, _hour(), _ints(), parse_filters() (+12 more)

### Community 90 - "SafeRoute 3D — Faz 6 Teknik Raporu: Sistem Stabilizasyonu, Güvenilirlik, Performans ve Uçtan Uca Entegrasyon"
Cohesion: 0.05
Nodes (40): lifespan(), test_real_saved_models_match_phase3_registry(), 0. Hazırlık (sunumdan önce, bir kez), 1. Senaryo, 2. Bağlantı kaybı ve yeniden deneme davranışı, 3. Otomatik doğrulama, SafeRoute 3D — Faz 6 Akademik Demo Test Planı, 1. Güvenlik sınırı (internete açık dağıtım için HAZIR DEĞİLDİR) (+32 more)

### Community 91 - "Registry"
Cohesion: 0.18
Nodes (4): ExperimentRecord, Registry, software_versions(), test_registry_rejects_silent_failures()

### Community 92 - "phase8_brand.py"
Cohesion: 0.09
Nodes (19): 1. Marka ve logo, 2. Güncellenen kullanıcıya görünen alanlar, 3. Düzeltilen kalite sorunları, 4. Akademik teslim dosyaları, 5. Test sonuçları (son derleme, yeniden başlatılmış sunucu), 6. Görsel kontroller, 7. Bilinen sınırlılıklar, Kaza Odak — Marka Geçişi ve Sürüm Cilası (+11 more)

### Community 93 - "perf.py"
Cohesion: 0.20
Nodes (3): run_benchmark(), current_memory_mb(), _win_process_counters()

### Community 94 - "phase6.spec.ts"
Cohesion: 0.15
Nodes (7): a11y, HERE, mapIdle(), measurements, openExplorer(), SHOTS, VIEWPORTS

### Community 95 - "test_loader.py"
Cohesion: 0.30
Nodes (9): latest_snapshot(), load_raw(), _snapshot(), test_latest_snapshot_missing(), test_latest_snapshot_picks_newest_completed(), test_load_raw_roundtrip_keeps_text_and_nulls(), test_multiline_quoted_values_count_as_one_row(), test_na_like_strings_are_preserved_as_data() (+1 more)

### Community 96 - "casualties.py"
Cohesion: 0.31
Nodes (4): add_casualty_features(), _arr(), casualty_summary(), quality_flag()

### Community 97 - "PreprocessConfig"
Cohesion: 0.16
Nodes (5): PreprocessConfig, add_temporal_features(), cyclical(), minute_heaping(), time_period()

### Community 98 - "._recover"
Cohesion: 0.15
Nodes (3): sample_events(), sha256_file(), is_our_worker()

### Community 99 - "phase8b.spec.ts"
Cohesion: 0.10
Nodes (13): HERE, results, SHOTS, FILE, HERE, HERE, idle(), jump() (+5 more)

### Community 100 - "phase6-restart.spec.ts"
Cohesion: 0.18
Nodes (7): getJSON(), HERE, LAB, log, PY, ROOT, waitReady()

### Community 101 - "common.tsx"
Cohesion: 0.31
Nodes (7): SCOPE_LABEL, SCOPE_TONE, Alert(), AlertDescription(), AlertTitle(), alertVariants, Skeleton()

### Community 102 - "SafeRoute 3D — Logo Kullanım Kuralları (Faz 8)"
Cohesion: 0.20
Nodes (10): 1. Kavram, 2. Varlıklar, 3. Renkler, 4. Tipografi, 5. Boyut ve boşluk, 6. Yapılmaması gerekenler, 7. Uygulamadaki kullanım, 8. Erişilebilirlik ve güvenlik (+2 more)

### Community 103 - "Ayrıntılar"
Cohesion: 0.20
Nodes (10): Ayrıntılar, H01 — Kaza katmanları altlık servisine bağlıydı (Yüksek), H02 — "Haritada aç" yarış durumu: 409 ve konsol hataları (Orta), H03 — Tablet düzeni (Orta), H04 — HDBSCAN → DBSCAN geçişinde örneklemin taşınması (Orta), H05 — Boş filtre sonucu (Orta), H06 — GLB modelini kaldırma (Düşük), H07 — Mobil animasyon seçicisi (Düşük) (+2 more)

### Community 104 - "SafeRoute 3D — Faz 8: Arayüz Kalite Raporu"
Cohesion: 0.25
Nodes (5): 1. Önce / sonra karşılaştırması, 3. Responsive sonuçları (gerçek tarayıcı), 4. Erişilebilirlik, 5. Yalnızca kod incelemesiyle değerlendirilenler, SafeRoute 3D — Faz 8: Arayüz Kalite Raporu

### Community 105 - "start_saferoute.ps1"
Cohesion: 0.53
Nodes (8): Fail(), Get-Json(), Ok(), Say(), Show-Ready(), Wait-Ready(), Warm-Demo(), Warn()

### Community 106 - "3D varlık kaydı (Faz 4)"
Cohesion: 0.33
Nodes (4): 3D varlık kaydı (Faz 4), Kaynak paketler, Optimizasyon, Seçilen modeller

### Community 108 - "runner.py"
Cohesion: 0.10
Nodes (11): AlignmentError, EventData, load_events(), processed_dir(), subset_mask(), verify_integrity(), weighted_view(), execute() (+3 more)

### Community 110 - "ExportMenu"
Cohesion: 0.60
Nodes (5): ExportMenu(), DropdownMenu(), DropdownMenuContent(), DropdownMenuItem(), DropdownMenuTrigger()

### Community 112 - "test_clustering_pipeline.py"
Cohesion: 0.15
Nodes (11): final_choice(), _cfg(), _hashes(), run_results(), test_experiments_are_resumed_deterministically(), test_original_data_is_unchanged(), test_outputs_and_count_conservation(), test_resource_limited_experiments_are_recorded_not_faked() (+3 more)

### Community 113 - "7. Interactive Application"
Cohesion: 0.33
Nodes (6): 3D City Explorer, 7. Interactive Application, Clustering Lab, Dashboard, Data Explorer, Model Comparison

### Community 114 - "SafeRoute 3D — Faz 8B Regresyon Sonuçları"
Cohesion: 0.40
Nodes (4): Bilinen, düzeltilmeyen bulgu, Konsol ve ağ, SafeRoute 3D — Faz 8B Regresyon Sonuçları, Son durum

### Community 115 - "smoothTextureSampling"
Cohesion: 0.14
Nodes (12): Değerlendirme, Geri alınan / düzeltilen ara denemeler, GLB doku gürültüsü (kanıt), SafeRoute 3D — Faz 8B Görsel Karşılaştırma (Önce / Sonra), Sahne kameraları, GLB önizleyici maliyeti, SafeRoute 3D — Faz 8B Performans Ölçümü, Sonuçlar (+4 more)

### Community 116 - "conftest.py"
Cohesion: 0.12
Nodes (6): csv_text(), d(), FakeResponse, frame(), rows(), sample_rows()

### Community 117 - "GELISTIRME.md"
Cohesion: 0.13
Nodes (8): Veri Sözlüğü — Motor Vehicle Collisions - Crashes (`h9gi-nx95`), Gözlemlenen ama nedeni belirlenemeyen örüntüler, Kapsam ve yorum sınırlılıkları, Koordinat sınıflandırması, Veri Kalitesi Raporu — Faz 1, Özet, Model öznitelik matrisleri, Öznitelik Seçimi Raporu — Faz 2

### Community 119 - "5. Features and Data Processing"
Cohesion: 0.40
Nodes (5): 5. Features and Data Processing, Descriptive and Evaluation Features, Excluded or Non-predictive Model Fields, Filtering Features, Model Features

### Community 120 - "2. Ekran bazında değerlendirme"
Cohesion: 0.33
Nodes (6): 2. Ekran bazında değerlendirme, 3D Şehir Keşfi, Genel Bakış, Genel (kabuk, gezinme), Kümeleme Laboratuvarı, Model Karşılaştırma ve Veri Gezgini

### Community 122 - "SafeRoute 3D — Faz 8: Fonksiyonel Test Envanteri"
Cohesion: 0.33
Nodes (5): Düzeltmeler öncesi ve sonrası, Kapsam dışında kalan / yalnızca kodla doğrulanan, SafeRoute 3D — Faz 8: Fonksiyonel Test Envanteri, Sonuçlar, Yöntem

### Community 125 - "SafeRoute 3D — Faz 8: Bulunan ve Düzeltilen Hatalar"
Cohesion: 0.40
Nodes (4): Düzeltilmeyen / bilinen sınırlılıklar, SafeRoute 3D — Faz 8: Bulunan ve Düzeltilen Hatalar, Uygulama hatası OLMAYAN, test kodu kaynaklı bulgular, Özet

### Community 132 - "reporting.py"
Cohesion: 0.29
Nodes (5): _fmt(), _jsonable(), render(), ReportDocument, test_report_formats()

### Community 133 - "Karar Günlüğü"
Cohesion: 0.18
Nodes (11): K-01 — Edinim yöntemi: SODA API ile sayfalı CSV (2026-10-19, Faz 1), K-02 — Sıralama: `$order=:id` (2026-10-19, Faz 1), K-03 — Ham veri her zaman metin olarak yüklenir (2026-10-19, Faz 1), K-04 — Ham verinin değişmezliği (2026-10-19, Faz 1), K-05 — Parquet kopyası kayıpsız ve tamamı metin (2026-10-19, Faz 1), K-06 — Koordinat geçerliliği: dışlayıcı sınıflar ve kaba kutu (2026-10-19, Faz 1), K-07 — Eksik değerler bu fazda doldurulmaz (2026-10-19, Faz 1), K-08 — Depo yapısında şartname örneğinden farklar (2026-10-19, Faz 1) (+3 more)

### Community 134 - "Kaza Odak — Geliştirici Rehberi"
Cohesion: 0.18
Nodes (11): Belgeler, Depo yapısı, Faz 1, Faz 2, Faz 3, Faz 4 — 3D şehir görüntüleyici, Hatları çalıştırma, Kaza Odak — Geliştirici Rehberi (+3 more)

### Community 135 - "SafeRoute 3D — Faz 8B Teknik Raporu: Görsel İyileştirme ve 3D Deneyim Kalitesi"
Cohesion: 0.14
Nodes (16): 0. Ön inceleme, 10. Test sonuçları, 11. Performans sonuçları, 12. Bilinen sınırlılıklar, 14. Git, 2. Değiştirilen ve eklenen dosyalar, 4. Kaza kümesi görünümü, 6. Küme detay paneli (+8 more)

### Community 139 - "duplicates.py"
Cohesion: 0.19
Nodes (4): assign_location_ids(), geocode_fallback_flags(), location_table(), repetition_analysis()

## Knowledge Gaps
- **21 isolated node(s):** `saferoute`, `react-is`, `@testing-library/dom`, `@types/geojson`, `@types/react` (+16 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1081 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ExplorerPage()` connect `ExplorerPage.tsx` to `cn`, `Ayrıntılar`, `filters.ts`, `ExperimentResults.tsx`, `phase5-components.test.tsx`, `CityMap.tsx`, `LabPage.tsx`, `SafeRoute 3D — Faz 5 Teknik Raporu: Profesyonel Ön Yüz, İnteraktif Analiz ve Kümeleme Laboratuvarı`, `App.tsx`?**
  _High betweenness centrality (0.271) - this node is a cross-community bridge._
- **What connects `saferoute`, `react-is`, `@testing-library/dom` to the rest of the system?**
  _21 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Development Workflow (7 steps)` be split into smaller, more focused modules?**
  _Cohesion score 0.12418300653594772 - nodes in this community are weakly interconnected._
- **Why does `18. Graphify durumu` connect `SafeRoute 3D — Faz 5 Teknik Raporu: Profesyonel Ön Yüz, İnteraktif Analiz ve Kümeleme Laboratuvarı` to `FilterSpec`, `register`, `ExplorerPage.tsx`, `catalog.py`, `LabelResult`, `JobManager`?**
  _High betweenness centrality (0.258) - this node is a cross-community bridge._
- **Should `profile.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11175616835994194 - nodes in this community are weakly interconnected._
- **Why does `EventStore` connect `FilterSpec` to `._recover`, `jobs.py`, `Analytics`, `register`, `columns_from_frame`, `LabelResult`, `SafeRoute 3D — Faz 5 Teknik Raporu: Profesyonel Ön Yüz, İnteraktif Analiz ve Kümeleme Laboratuvarı`, `JobManager`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Should `cn` be split into smaller, more focused modules?**
  _Cohesion score 0.06172839506172839 - nodes in this community are weakly interconnected._