import sys
import subprocess
from IPython import embed
import os
import csv
from collections import Counter
import matplotlib.pyplot as plt
import random
import pandas
import numpy as np
import re

import logging
import log
logger = log.init_log(logging.INFO)

plt.rcParams.update({'font.size': 13})

def get_logs_for_selected(transpilation_log_dict, selected_functions_list):
    selected_transpilation_log_dict = {}
    for line in selected_functions_list:
        if not line in selected_transpilation_log_dict.keys():
            selected_transpilation_log_dict[line] = transpilation_log_dict[line]

    return selected_transpilation_log_dict

def get_comp_attempts(transpilation_log_dict):

    comp_attemps = []
    for k in transpilation_log_dict.keys():
        comp_attemps.append(transpilation_log_dict[k][4])

    return comp_attemps

def get_frequencies(comp_attempts, selected_comp_attempts):
    # Normalize the distribution for the original set to overcome differences between two sets
    ratio = len(selected_comp_attempts) / len(comp_attempts)
    
    freq = Counter(comp_attempts)
    freq = {key: np.ceil(value * ratio) for key, value in freq.items()}

    selected_freq = Counter(selected_comp_attempts)

    all_keys = [str(key) for key in range(0,21)]

    # Get the frequency values for each list (default to 1.0 if the number is not in the list)
    freq_values = [freq.get(str(key), 1.0) for key in all_keys]
    selected_freq_values = [selected_freq.get(str(key), 0) for key in all_keys]

    return freq_values, selected_freq_values, all_keys

def draw_histogram(freq_values, selected_freq_values, all_keys, out_file):

    fig, ax = plt.subplots()
    width = 0.4
    
    ax.bar([float(key) - width / 2 for key in all_keys], freq_values, width, label='Fuctions in Microbenchmark Set', color='blue')
    ax.bar([float(key) + width / 2 for key in all_keys], selected_freq_values, width, label='Selected Functions', color='orange')
    all_keys = [int(k) for k in all_keys]

    ax.set_xlabel('Compilation Error Fixing Attempts')
    ax.set_ylabel('Frequency (#)')
    ax.tick_params(labelsize=9)
    ax.set_xticks(all_keys)
    ax.set_xticklabels(all_keys)
    ax.legend(fontsize=11)
    plt.savefig(out_file)
    plt.clf()
    plt.close()

def process_files(transpilation_log_dict, selected_functions_file, out_file):

    with open(selected_functions_file, "r") as f:
        selected_functions_lines = [line.strip() for line in f.readlines()]
        num_of_selected = len(selected_functions_lines)

    # Change the format to match IDs from both file
    selected_functions_list = [line.split(":")[0] + "#" + line.split(":")[1] + "#" + line.split(":")[2] + ".c" for line in selected_functions_lines]

    selected_transpilation_log_dict = get_logs_for_selected(transpilation_log_dict, selected_functions_list)

    comp_attempts = get_comp_attempts(transpilation_log_dict)
    selected_comp_attempts = get_comp_attempts(selected_transpilation_log_dict)
    
    freq_values, selected_freq_values, all_keys = \
                        get_frequencies(comp_attempts,selected_comp_attempts)
    
    # Calculate the relative difference score
    denom = min(len(freq_values), len(selected_freq_values))
    relative_diff = (sum((abs(a - b) / a) for a, b in zip(freq_values, selected_freq_values)) / denom) * 100

    draw_histogram(freq_values, selected_freq_values, all_keys, out_file)

    return relative_diff, num_of_selected

def extract_number(filename):
    
    numbers = re.findall(r'\d+', filename)
    return tuple(map(int, numbers))

def draw_diff_plot(out_path, diff_ls, num_of_selected_ls):
    fig, ax1 = plt.subplots()
    
    ax1.set_xlabel('Combinations (Index)')
    ax1.set_ylabel('Relative Difference (%)')
    ax1.tick_params(labelsize=9)

    plt.axvline(x=883, ymin=0.01, ymax=0.99, color='tab:red', linestyle='--', linewidth=1, dashes=(4, 11))

    plt.grid(True)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.clf()
    plt.close()

def main():
    args = sys.argv
    
    if len(args) < 3:
        print("Error: Missing argument")
        print("Usage: python3 src/evaluate_selections.py Benchmark/large_set/large_set/rust_qwen2_5_coder_32b_sf_withfixing/merged_transpilation.log out/large_set/selected_func_lists/ out/large_set/histograms/")
        sys.exit(1)
    
    transpilation_log_file = args[1]
    selected_functions_path = args[2]
    out_dir = args[3]
    
    if not os.path.isdir(selected_functions_path):
        process_files(transpilation_log_file, selected_functions_path)
    else:
        files = [file for file in os.listdir(selected_functions_path) if file.endswith(".txt")]
        files.sort(key = extract_number)
        diff_ls = []
        num_of_selected_ls = []
        min_diff = sys.maxsize
        min_diff_file = ()
        sorted_diff_ls = []
        with open(transpilation_log_file, "r") as f:
            transpilation_log_lines = [line.strip() for line in f.readlines()]
        
        all_projs_merged = pandas.read_pickle("large_set_all_metrics.pkl")

        alive_funcs = []
        for e in list(all_projs_merged["id"]):
            alive_funcs.append(e.replace(":", "#") + str(".c"))

        transpilation_log_dict = {}
        for line in transpilation_log_lines:
            elems = line.split(";")
            
            if not elems[0] in transpilation_log_dict.keys() and elems[0] in alive_funcs:
                transpilation_log_dict[elems[0]] = elems

        for selected_functions_file in files:
            logger.info(selected_functions_file)
            out_file = selected_functions_file.replace(".txt", ".pdf")
            relative_diff, num_of_selected = process_files(transpilation_log_dict, os.path.join(selected_functions_path, selected_functions_file), os.path.join(out_dir, out_file))
            logger.info("Diff score: " + str(round(relative_diff,2)))

            diff_ls.append(relative_diff)
            num_of_selected_ls.append(num_of_selected)
            sorted_diff_ls.append((selected_functions_file, relative_diff))
            if relative_diff < min_diff:
                min_diff = relative_diff
                min_diff_file = selected_functions_file


        draw_diff_plot(os.path.join(out_dir, "diff_plot.pdf"), diff_ls, num_of_selected_ls)

        logger.info("Minimum diff score: " + str(min_diff))
        logger.info("Minimum diff comb: " + str(min_diff_file))
        sorted_diff_ls.sort(key = lambda tup: tup[1])


if __name__ == "__main__":
    main() 