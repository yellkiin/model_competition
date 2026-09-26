# 独立数值复核

状态：PASS_SCOPED；模式：csv。

主表展示配置：1500；配对记录：500；核对正文统计行：20。

| 核数 | 第一问均值 | 第二问均值 | 第三问均值 |
|---:|---:|---:|---:|
| 1 | 1.0000 | 1.0000 | 1.1008 |
| 2 | 1.9832 | 2.1168 | 2.1222 |
| 3 | 2.7106 | 3.0153 | 3.0320 |
| 4 | 3.3852 | 3.7868 | 3.8376 |
| 5 | 3.9180 | 4.4538 | 4.5978 |

## 计算结果

```json
{
  "comparisons_n5": {
    "q2_vs_q1_makespan": {
      "improved": 89,
      "same": 9,
      "worse": 2
    },
    "q2_vs_q1_added_copy_bytes": {
      "improved": 50,
      "same": 12,
      "worse": 38
    },
    "q3_vs_q2_makespan": {
      "improved": 66,
      "same": 18,
      "worse": 16
    }
  },
  "q1_over_q2_n5": {
    "mean": 1.1728166309575971,
    "median": 1.0912692587546262
  },
  "cache_stats": {
    "1": {
      "count": 100,
      "mean_ratio": 1.0002844524850667,
      "median_ratio": 1.0,
      "mean_hit_rate": 0.05988487431312221,
      "improved": 28,
      "same": 72,
      "worse": 0
    },
    "2": {
      "count": 100,
      "mean_ratio": 1.0046769687655241,
      "median_ratio": 1.0000746801895541,
      "mean_hit_rate": 0.175706624426544,
      "improved": 58,
      "same": 42,
      "worse": 0
    },
    "3": {
      "count": 100,
      "mean_ratio": 1.015586806149891,
      "median_ratio": 1.0009292183142593,
      "mean_hit_rate": 0.2341885008711454,
      "improved": 66,
      "same": 34,
      "worse": 0
    },
    "4": {
      "count": 100,
      "mean_ratio": 1.0303863218628446,
      "median_ratio": 1.0018087621911755,
      "mean_hit_rate": 0.2469830287093025,
      "improved": 71,
      "same": 28,
      "worse": 1
    },
    "5": {
      "count": 100,
      "mean_ratio": 1.0558429548125037,
      "median_ratio": 1.007735024354472,
      "mean_hit_rate": 0.3017429252710123,
      "improved": 77,
      "same": 23,
      "worse": 0
    }
  },
  "spill_n5": {
    "q1": {
      "zero_count": 88,
      "positive_count": 12,
      "mean": 206080.96
    },
    "q2": {
      "zero_count": 74,
      "positive_count": 26,
      "mean": 2645062.08
    },
    "q3": {
      "zero_count": 73,
      "positive_count": 27,
      "mean": 2721567.68
    }
  }
}
```

grid：
{"records": 66, "fixed": 54, "readapted": 12, "examples": {"case_080": [79170, 80014, 81744], "case_044": [50723, 36208, 44299]}}

anytime_q1_n5_30：
{"rows": 100, "distinct_cases": 100, "has_solution": 93}

unreported_reference_spill：
[{"q": 1, "case": "case_072", "n": 1}, {"q": 1, "case": "case_091", "n": 1}, {"q": 2, "case": "case_072", "n": 1}, {"q": 2, "case": "case_091", "n": 1}]

## 核验边界

- No official evaluator or solver rerun.
- No PDF compilation, page or hyperlink verification.
- Numeric agreement is not evidence of same-plan byte identity.
