# Mismatch triage

Failures: 24 in 2 clusters. Harness errors: 0.

## Cluster 1: 16 cases (66.7% of failures)

Differs at: frame_mad (value)

First guess (hypothesis, test it): replica content runs 0.25 s ahead of the original (its cut starts late); resolution 0.25 s, raise --fps for finer

Over-represented inputs: `source="frame"` (100% here vs 42% overall)

Smallest failing case `frame@000.000`:

    input: {"t": 0.0}
    frame_mad: original=0 replica=8.56  (mean abs grey diff, tol 6; timeline: replica content runs 0.25 s ahead of the original (its cut starts late); resolution 0.25 s, raise --fps for finer)

Cases: frame@000.000, frame@000.250, frame@000.500, frame@000.750, frame@001.000, frame@001.250, frame@001.500, frame@001.750, frame@002.000, frame@002.250, frame@002.500, frame@002.750, frame@003.000, frame@003.250, frame@003.500, frame@003.750

## Cluster 2: 8 cases (33.3% of failures)

Differs at: rms_db (value)

First guess (hypothesis, test it): replica content runs 0.25 s ahead of the original (its cut starts late); resolution 0.25 s, raise --fps for finer

Over-represented inputs: `source="audio"` (100% here vs 42% overall)

Smallest failing case `audio@000.000`:

    input: {"t": 0.0}
    rms_db: original=-18.96 replica=-21.08  (tol 1.5 dB; timeline: replica content runs 0.25 s ahead of the original (its cut starts late); resolution 0.25 s, raise --fps for finer)

Cases: audio@000.000, audio@000.750, audio@001.000, audio@001.750, audio@002.000, audio@002.750, audio@003.000, audio@003.750

