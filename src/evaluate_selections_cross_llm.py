import sys
import os
from IPython import embed
import evaluate_selections
import matplotlib.pyplot as plt
import pandas
import logging

logger = logging.getLogger(__name__)

model_ls = {
    "codegeex4_9b": "codegeex4:9b",
    "codestral_22b": "codestral:22b",
    "gemma2_9b": "gemma2:9b",
    "llama3_2_3b": "llama3.2:3b",
    "llama_3_1_8b": "llama3.1:8b",
    "mistral_7b": "mistral:7b",
    "qwen2_5_coder_7b": "qwen2.5-coder:7b",
    "qwen2_5_coder_14b": "qwen2.5-coder:14b",
    "qwen2_5_coder_32b": "qwen2.5-coder:32b",
}

def draw_diff_plot_cross_llm(out_path, diff_ls, model_names):
    fig, ax = plt.subplots()
    plt.plot(model_names, diff_ls, marker='o', color='b', linestyle='-', label='Numbers', markersize=2)

    plt.xlabel('Large Language Models')
    plt.ylabel('Relative Difference (%)')
    ax.tick_params(axis='x', rotation=45, labelsize=9)
    ax.tick_params(axis='y', labelsize=9)

    plt.grid(True)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.clf()
    plt.close()

def main():
    args = sys.argv
    
    if len(args) < 3:
        print("Error: Missing argument")
        print("Usage: python3 src/evaluate_selections_cross_llm.py Benchmark/microbenchmark_set/microbenchmark_set/ out/microbenchmark_set/other_models/selected_func_lists/ out/microbenchmark_set/other_models/histograms/")
        sys.exit(1)
    
    root_dir = args[1]
    selected_functions_path = args[2]
    out_dir = args[3]

    all_projs_merged = pandas.read_pickle("microbenchmark_set_all_metrics.pkl")
    alive_funcs = []
    for e in list(all_projs_merged["id"]):
        alive_funcs.append(e.replace(":", "#") + str(".c"))
    
    files = [file for file in os.listdir(selected_functions_path) if file.endswith(".txt")]
    files.sort(key = evaluate_selections.extract_number)
    for selected_functions_file in files:
        diff_ls = []
        model_names = []
        for model in model_ls.keys():
            logger.info("Processing: " + str(model))
            model_dir = "rust_" + model + "_sf_withfixing"
            model_path = os.path.join(root_dir, model_dir)
            transpilation_log_file = os.path.join(model_path, "transpilation.log")

            if not os.path.isdir(selected_functions_path):
                evaluate_selections.process_files(transpilation_log_file, selected_functions_path)
            else:
                with open(transpilation_log_file, "r") as f:
                    transpilation_log_lines = [line.strip() for line in f.readlines()]
                
                transpilation_log_dict = {}
                for line in transpilation_log_lines:
                    elems = line.split(";")

                    if not elems[0] in transpilation_log_dict.keys() and elems[0] in alive_funcs:
                        transpilation_log_dict[elems[0]] = elems
                diff_dict = {}
                
                out_file = model + "_" + selected_functions_file.replace(".txt", ".pdf")
                total_abs_diff, num_of_selected  = evaluate_selections.process_files(transpilation_log_dict, os.path.join(selected_functions_path, selected_functions_file), os.path.join(out_dir, out_file))
                logger.info("Diff score: " + str(total_abs_diff) + "\n")

                diff_ls.append(total_abs_diff)
                model_names.append(model_ls[model])
                diff_dict[out_file] = total_abs_diff

                diff_dict = {k: v for k, v in sorted(diff_dict.items(), key=lambda item: item[1])}

        draw_diff_plot_cross_llm(os.path.join(out_dir, "diff_plot_cross_llm" + str(selected_functions_file) + ".pdf"), diff_ls, model_names)

if __name__ == "__main__":
    main() 