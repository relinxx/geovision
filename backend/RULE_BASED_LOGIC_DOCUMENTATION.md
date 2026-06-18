# Rule-Based Logic Documentation

## Overview

This document clarifies the role of rule-based logic in the GeoVision backend and explains why certain rules are retained (not redundant) while others serve specific purposes.

## Rule-Based Components

### 1. Rule-Based Risk Score Computation (`compute_rule_risk`)

**Location**: `agent/environment_agent/main.py`

**Purpose**: Generate training labels for XGBoost model training

**Usage**: 
- Used during training pipeline execution only
- Creates `rule_risk_score` by applying weighted hazard flags
- This score becomes the target variable for XGBoost training

**Status**: **NOT REDUNDANT** - Required for supervised learning

**Why Not Removed**:
- No labeled training data exists - rule-based scores serve as training labels
- XGBoost model requires labeled data for training
- Removing this would break the training pipeline

**Production Usage**:
- NOT used for predictions in production
- Only used as rare fallback when XGBoost scores are missing
- XGBoost predictions (`xgb_risk_score`) are primary

### 2. Rule-Based Risk Score Fallback (`agent.py`)

**Location**: `agent/environment_agent/agent.py` (load_data method)

**Purpose**: Fallback mechanism when XGBoost scores unavailable

**Usage**:
- Only triggers when `xgb_risk_score` is completely missing
- Should rarely occur in production (training pipeline generates both)
- Logs warning when fallback is used

**Status**: **KEPT** - Safety fallback, rarely used

**Why Kept**:
- Provides graceful degradation for edge cases
- Ensures system continues working even with incomplete data
- Minimal performance impact (only checked when XGBoost score missing)

### 3. Suitability Conversion Rules (`agent.py` predict method)

**Location**: `agent/environment_agent/agent.py` (predict method)

**Purpose**: Convert environmental risk scores to land-use suitability scores

**Rules**:
```python
# Residential: High penalty for risk (base 0.8, subtract risk)
residential = max(0.0, 0.8 - risk_norm)

# Commercial: Moderate penalty (base 0.7, subtract 80% of risk)
commercial = max(0.0, 0.7 - risk_norm * 0.8)

# Industrial: Lower penalty (base 0.6, subtract 50% of risk)
industrial = max(0.0, 0.6 - risk_norm * 0.5)

# Green space: Positive relationship (base 0.2, add risk)
green = min(1.0, 0.2 + risk_norm)
```

**Status**: **KEPT** - Currently used for predictions, heuristic rules based on planning best practices

**Why Kept**:
- Currently necessary for production predictions
- Based on established planning principles (residential most risk-averse, etc.)
- Could be replaced with ML model in future, but would require retraining

**Future Improvement**:
- Could train separate ML models for each land-use type suitability
- Would require labeled suitability data (may not be available)
- Current heuristic rules are reasonable and explainable

## Decision Summary

| Component | Used For | Redundant? | Action |
|-----------|----------|------------|--------|
| `compute_rule_risk` | Training labels | ❌ No | Keep - Required for training |
| Rule score fallback | Edge case handling | ❌ No | Keep - Safety mechanism |
| Suitability rules | Production predictions | ⚠️ Possibly | Keep - Currently necessary, documented for future ML replacement |

## Architecture Notes

### Training Pipeline Flow:
1. Load hazard layers (flood, fault, etc.)
2. Join with parcels → create hazard flags
3. **Compute rule_risk_score** (weighted sum) ← Training label generation
4. Train XGBoost to predict rule_risk_score
5. Export both rule-based and XGBoost scores

### Production Prediction Flow:
1. Load pre-computed GeoJSON with scores
2. Use `xgb_risk_score` as primary (ML prediction)
3. Fallback to `rule_risk_score` only if XGBoost missing
4. **Apply suitability conversion rules** ← Heuristic conversion
5. Return suitability scores to frontend

## Code Locations

- **Training label generation**: `agent/environment_agent/main.py::compute_rule_risk()`
- **Fallback logic**: `agent/environment_agent/agent.py::load_data()`
- **Suitability rules**: `agent/environment_agent/agent.py::predict()`

## Recommendations

1. **Keep all rule-based logic** - System currently depends on it
2. **Document usage clearly** - Done via docstrings and comments
3. **Future enhancement**: Train ML models for suitability conversion if labeled data becomes available
4. **Monitor fallback usage** - If rule_risk_score fallback triggers frequently, investigate data quality issues

## Conclusion

The rule-based logic in the codebase serves essential functions:
- Training label generation (required for ML)
- Safety fallback mechanism (defensive programming)
- Suitability conversion (currently necessary for predictions)

None of these should be removed as they would break the system. The documentation now clearly explains their purposes and usage patterns.

