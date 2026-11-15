# Evaluasi asisten — eval/assistant_eval_flare.jsonl

## mode deepseek — 16 pertanyaan

| metrik | nilai |
|---|---|
| pass | 0.938 |
| tool_ok | 1.0 |
| contain_ok | 1.0 |
| forbid_ok | 1.0 |
| ui_ok | 1.0 |
| grounded | 0.938 |
| cites_ok | 1.0 |
| media_ok | 1.0 |
| cite_ok | 1.0 |
| ms_median | 16542 |

| id | lulus | alat | isi | UI | grounded | media | sitasi | ms | angka tanpa sumber | alat dipakai |
|---|---|---|---|---|---|---|---|---|---|---|
| f01 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 12946 |  | find_equations |
| f02 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 16542 |  | find_figures find_figures find_figures search_papers |
| f03 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 5934 |  | gravity_flammability |
| f04 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 5401 |  | make_plot |
| f05 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 12025 |  | rank_investigations scenario_evidence |
| f06 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 18211 |  | compare_investigations get_investigation get_investigation rank_investigations |
| f07 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 29400 |  | search_papers find_tests search_papers rank_investigations coverage search_papers find_tests search_papers |
| f08 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 12914 |  | search_papers find_figures |
| f09 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 5231 |  | make_plot |
| f10 | ✘ | ✔ | ✔ | ✔ | ✘ | ✔ | ✔ | 44422 | 90 90 | predict_smoke_point predict_smoke_point predict_smoke_point predict_smoke_point make_plot |
| f11 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 19571 |  | find_equations |
| f12 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 8726 |  | rank_investigations |
| f13 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 14289 |  | get_investigation rank_investigations get_investigation get_investigation |
| f14 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 19792 |  | search_papers search_papers find_tests |
| f15 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 21696 |  | get_investigation find_figures get_investigation get_investigation get_investigation get_investigation get_investigation get_investigation ui_action |
| f16 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 16865 |  | model_cards uncertainty_stats |

