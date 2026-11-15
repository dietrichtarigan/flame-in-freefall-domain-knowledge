---
noteId: "089470e0e0e311f1871fa33237f5b37b"
tags: []

---

# Evaluasi asisten — eval/assistant_eval_flare.jsonl

## mode deepseek — 16 pertanyaan

| metrik | nilai |
|---|---|
| pass | 0.625 |
| tool_ok | 1.0 |
| contain_ok | 1.0 |
| forbid_ok | 1.0 |
| ui_ok | 1.0 |
| grounded | 0.812 |
| cites_ok | 0.938 |
| media_ok | 1.0 |
| cite_ok | 0.875 |
| ms_median | 14912 |

| id | lulus | alat | isi | UI | grounded | media | sitasi | ms | angka tanpa sumber | alat dipakai |
|---|---|---|---|---|---|---|---|---|---|---|
| f01 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 21669 |  | find_equations find_equations |
| f02 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 8542 |  | find_figures |
| f03 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 11604 |  | gravity_flammability ui_action |
| f04 | ✘ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 7391 |  | make_plot |
| f05 | ✘ | ✔ | ✔ | ✔ | ✔ | ✔ | ✘ | 10334 |  | rank_investigations scenario_evidence |
| f06 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 14912 |  | compare_investigations get_investigation get_investigation rank_investigations |
| f07 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 33665 |  | search_papers search_papers find_figures search_papers search_papers rank_investigations scenario_evidence coverage search_papers |
| f08 | ✘ | ✔ | ✔ | ✔ | ✘ | ✔ | ✔ | 18102 | 2024 | search_papers find_figures |
| f09 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 5672 |  | make_plot |
| f10 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 49127 |  | model_cards make_plot predict_smoke_point predict_smoke_point predict_smoke_point |
| f11 | ✘ | ✔ | ✔ | ✔ | ✔ | ✔ | ✘ | 8208 |  | find_equations |
| f12 | ✘ | ✔ | ✔ | ✔ | ✘ | ✔ | ✔ | 13134 | 1.780 | rank_investigations scenario_evidence get_investigation |
| f13 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 31255 |  | get_investigation find_tests get_investigation get_investigation get_investigation get_investigation get_investigation find_tests find_tests find_tests |
| f14 | ✘ | ✔ | ✔ | ✔ | ✘ | ✔ | ✔ | 16737 | 0.5 0.9 0.05 | search_papers search_papers find_equations |
| f15 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 12865 |  | find_figures get_investigation get_investigation find_figures |
| f16 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 20167 |  | model_cards uncertainty_stats |

