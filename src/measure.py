import sys
import os
import subprocess
from pathlib import Path
from IPython import embed
import csv
import json
from io import StringIO
import numpy as np
import pandas

import logging
from colorlog import ColoredFormatter

from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

p = subprocess.Popen(['docker', 'ps', '-qf', 'ancestor=ccccc-docker:latest'], stdout=subprocess.PIPE, stdin=subprocess.PIPE)
out, err = p.communicate()
container_id = out.decode().strip("\n")

def get_comp_attempt_measure(rust_file_dir, proj_name, transpiler_name):

    logger.info("Calculating compilation metrics for transpilation")
    transpilation_log_file = os.path.join(rust_file_dir, "transpilation.log")
    if not os.path.exists(transpilation_log_file):
        logger.error("tranpilation log file not found!")
        embed()
        sys.exit(1)

    comp_attempt_dict = {}
    comp_attemp_ls = []
    columns = ["id", "comp_attempt"]
    columns = ["id"] + [transpiler_name + "_" + x for x in columns if not str(x) == "id"]
    
    logger.debug("Processing: " + str(transpilation_log_file))
    with open(transpilation_log_file, "r") as fp:
        csv_file = csv.reader(fp,  delimiter=';')
        csv_lines = []
        for line in csv_file:
            csv_lines.append(line)
    for line in csv_lines:
        elems = line[0].split("#")
        if len(elems) == 2:
            filename, funcname = line[0].split("#")
        elif len(elems) == 3:
            proj_name = elems[0]
            filename = elems[1]
            funcname = elems[2]
        else:
            logger.warning("File name format is not recognized")        
        funcname = Path(funcname).stem
        comp_attempt_dict[proj_name + ":" + filename + ":" + funcname] = line[4]
        comp_attemp_ls.append([str(proj_name + ":" + filename + ":" + funcname), int(line[4])])

    comp_attemp_df = pandas.DataFrame(comp_attemp_ls, columns = columns)
    return comp_attempt_dict, comp_attemp_df

def get_MI_for_C(c_file_dir, proj_name):

    logger.info("Collecting MI metrics for C functions")
    MI_C_dict = {}
    MI_C_ls = []
    columns = ["id", "LOCphy_C", "MVG_C", "Volume_C", "MI_C"]
    tmp_count = 0
    for c_filename in os.listdir(c_file_dir):
        if not c_filename.endswith(".c"):
            continue
        c_file = os.path.join(c_file_dir, c_filename)

        logger.debug("Processing: " + str(c_file))
        docker_file_path = os.path.join("/tmp", os.path.basename(c_file))
        cmd1 = ['docker', 'cp', c_file, container_id + ":" + docker_file_path]
        p = subprocess.Popen(cmd1, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        out, err = p.communicate()
        
        # ccccc tool is from https://github.com/Jarod42/ccccc
        cmd2 = ['docker', 'exec', '-i', container_id, 'bash', '-c', 'ccccc --extra-option=-ferror-limit=0 --template-file=/opt/html_static/template/csv/template.csv ' + docker_file_path + ' 2>/dev/null ' + '; rm ' + docker_file_path]
        p = subprocess.Popen(cmd2, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        out, err = p.communicate()

        reader = csv.reader(StringIO(out.decode()), delimiter=";")

        for line in reader:
            if line[0] == "Filename":
                tmp = line
                continue

            garb, file_func_name = line[0].split("/")
            file_func_name = Path(file_func_name).stem
            # funcname = line[4].split("(")[0]
            elems = file_func_name.split("#")
            tmp_count += 1
            if len(elems) == 2:
                filename, funcname = file_func_name.split("#")
            elif len(elems) == 3:
                proj_name = elems[0]
                filename = elems[1]
                funcname = elems[2]
            else:
                logger.error("File name format is not recognized")
                embed()
            MI_C_dict[proj_name + ":" + filename + ":" + funcname] = line
            MI_C_ls.append([str(proj_name + ":" + filename + ":" + funcname), float(line[5]), float(line[9]), \
                float(line[13]), float(line[20])])
    MI_C_df = pandas.DataFrame(MI_C_ls, columns = columns)
    return MI_C_dict, MI_C_df

def get_MI_for_Rust(rust_file_dir, proj_name, transpiler_name):
    logger.info("Collecting MI metrics for Rust functions")

    MI_Rust_dict = {}
    MI_C_ls = []
    columns = ["id", "SLOC_R", "Cyclomatic_R", "Volume_R", "MI_R"]
    columns = ["id"] + [transpiler_name + "_" + x for x in columns if not str(x) == "id"]

    for rust_filename in os.listdir(rust_file_dir):
        
        if not rust_filename.endswith(".rs"):
            continue
        rust_file = os.path.join(rust_file_dir, rust_filename)

        logger.debug("Processing: " + str(rust_file))
        # rust-code-analysis tool is from https://www.sciencedirect.com/science/article/pii/S2352711020303484
        bin = "src/rust-code-analysis/target/debug/rust-code-analysis-cli"
        cmd = [bin, '-m', '-O', 'json', '-p', rust_file]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        out, err = p.communicate()
        if out == b'':
            continue

        basename = Path(os.path.basename(rust_file)).stem
        elems = basename.split("#")
        if len(elems) == 2:
            filename = elems[0]
            target_func_name = elems[1]
        elif len(elems) == 3:
            proj_name = elems[0]
            filename = elems[1]
            target_func_name = elems[2]
        else:
            logger.warning("File name format is not recognized")

        json_out = json.loads(out.decode())

        if json_out["spaces"]:
            for func in json_out["spaces"]:
                funcname = func["name"]
                if funcname != target_func_name:
                    continue

                MI_Rust_dict[proj_name + ":" + filename + ":" + funcname] = json_out
                MI_C_ls.append([str(proj_name + ":" + filename + ":" + funcname), \
                    float(func["metrics"]["loc"]["sloc"]), \
                    float(func["metrics"]["cyclomatic"]["sum"]),\
                    float(func["metrics"]["halstead"]["volume"]),\
                    float(func["metrics"]["mi"]["mi_original"])])
        else:
            logger.warning("Rust MI metrics are empty for " + json_out["name"])

    MI_Rust_df = pandas.DataFrame(MI_C_ls, columns = columns)
    return MI_Rust_dict, MI_Rust_df

def get_unsafe_measure(rust_file_dir, proj_name, transpiler_name):
    bin = "src/bin/dump-unsafe-usage"

    logger.info("Collecting unsafe metrics for Rust functions")

    unsafe_measure_dict = {}
    unsafe_measure_ls = []
    columns = ["id", "total_unsafe_block_R", "avg_unsafe_stmt_R"]
    columns = ["id"] + [transpiler_name + "_" + x for x in columns if not str(x) == "id"]

    for rust_filename in os.listdir(rust_file_dir):
        if not rust_filename.endswith(".rs"):
            continue
        rust_file = os.path.join(rust_file_dir, rust_filename)

        logger.debug("Processing: " + str(rust_file))
        cmd = [bin, rust_file]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        reader = csv.reader(StringIO(out.decode()), delimiter=";")

        basename = Path(os.path.basename(rust_file)).stem
        elems = basename.split("#")
        if len(elems) == 2:
            filename = elems[0]
            target_func_name = elems[1]
        elif len(elems) == 3:
            proj_name = elems[0]
            filename = elems[1]
            target_func_name = elems[2]
        else:
            logger.warning("File name format is not recognized")

        for line in reader:
            funcname = line[0]
            if target_func_name != funcname:
                continue
            unsafe_measure_dict[proj_name + ":" + filename + ":" + funcname] = line
            total_unsafe_block = int(line[1])
            if total_unsafe_block > 0:
                sum = 0
                for i in range(2, total_unsafe_block + 2):
                    sum += int(line[i])
                avg = sum / total_unsafe_block
            else:
                avg = 0
            
            unsafe_measure_ls.append([str(proj_name + ":" + filename + ":" + funcname), \
                int(total_unsafe_block), float(avg)])

    unsafe_measure_df = pandas.DataFrame(unsafe_measure_ls, columns = columns)
    return unsafe_measure_dict, unsafe_measure_df

def get_type_cat(line):
    cat = ""
    if "NotIdentified#" in line[2]:
        return None
    
    if "*" == line[2][:1] or "&" == line[2][:1] \
        or line[2] == "libc::c_void" or line[2] == "libc :: c_void":
        cat = "pointer"
    elif line[2] == "i64" or line[2] == "i32" \
            or line[2] == "u64" or line[2] == "u32" \
            or line[2] == "c_uint" or line[2] == "c_int" or line[2] == "libc :: c_int" \
            or line[2][-7:] == "c_ulong" or line[2][-6:] == "c_long" \
            or line[2] == "libc :: size_t" or line[2] == "size_t" or line[2] == "c_size_t"\
            or line[2] == "usize" or line[2] == "isize" \
            or line[2] == "u8" or line[2] == "i8" \
            or line[2] == "i128" or line[2] == "u_int" or line[2] == "int":
        cat = "integer"
    elif line[2] == "f64" or line[2] == "f32" or line[2] == "float" \
            or line[2] == "c_double":
        cat = "float"
    elif line[2] == "string":
        cat = "string"
    elif line[2] == "char" or line[2] == "c_char" or line[2] == "libc :: c_char":
        cat = "char"
    elif line[2] == "bool":
        cat = "bool"
    elif line[2][:4] == "enum":
        cat = "enum"
    elif line[2][:5] == "array":
        cat = "array"
    elif line[2][:5] == "tuple":
        cat = "tuple"
    elif line[2][:6] == "struct" \
        or line[2] == "libc::timespec" or line[2] == "libc::timespec":
        cat = "struct"
    elif line[2] == "Vec<u8>" or line[2] == "Vec < u8 >":
        cat = "vector"
    elif line[2][:7] == "HashMap":
        cat = "hashmap"
    elif line[2][:6] == "Option":
        cat = "option"
    else:
        # logger.debug(line)
        cat = None

    return cat

def get_var_type_measure(rust_file_dir, proj_name, transpiler_name):
    bin = "src/bin/dump-var-types"
    logger.info("Collecting variable-type metric for Rust functions")

    var_type_measure_dict = {}
    var_type_measure_ls = []
    columns = ["id", "total_uniq_type_R"]
    columns = ["id"] + [transpiler_name + "_" + x for x in columns if not str(x) == "id"]
    for rust_filename in os.listdir(rust_file_dir):
        if not rust_filename.endswith(".rs"):
            continue
        rust_file = os.path.join(rust_file_dir, rust_filename)

        logger.debug("Processing: " + str(rust_file))
        cmd = [bin, rust_file]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        reader = csv.reader(StringIO(out.decode()), delimiter=";")

        basename = Path(os.path.basename(rust_file)).stem
        elems = basename.split("#")
        if len(elems) == 2:
            filename = elems[0]
            target_func_name = elems[1]
        elif len(elems) == 3:
            proj_name = elems[0]
            filename = elems[1]
            target_func_name = elems[2]
        else:
            logger.warning("File name format is not recognized")
        flag = 0
        tmp_set = set()
        tmp_ls = []
        funcname = ""

        for line in reader:

            if line[0] == "Function" and line[1] == target_func_name:
                if flag == 0:
                    flag = 1 
            elif line[0] == "Function" and line[1] != target_func_name:
                if flag == 1:
                    flag = 0

            if flag == 0:
                continue
            if line[0] == "Function":
                funcname = line[1]
            elif line[0] == "Argument":
                cat = get_type_cat(line)
                if not cat is None:
                    tmp_ls.append(cat)
            elif line[0] == "Return":
                pass
            elif line[0] == "Local":
                cat = get_type_cat(line)
                if not cat is None:
                    tmp_ls.append(cat)

        if funcname == target_func_name:
            var_type_measure_dict[proj_name + ":" + filename + ":" + funcname] = set(tmp_ls)
            var_type_measure_ls.append([str(proj_name + ":" + filename + ":" + funcname), \
                int(len(tmp_ls))])

    var_type_measure_df = pandas.DataFrame(var_type_measure_ls, columns = columns)
    return var_type_measure_dict, var_type_measure_df

def get_metrics(c_file_dir, rust_dirs):
    # Get each metric for the functions
    metrics_dict = {"MI_Rust":{}, "unsafe_measure":{},\
                     "var_type_measure":{}}
    metrics_sum_dict = {"MI_Rust":{}, "unsafe_measure":{},\
                        "var_type_measure":{}}

    proj_name = Path(c_file_dir).parts[-2]

    if len(rust_dirs) == 0:
        metrics_dict["MI_C"], metrics_sum_dict["MI_C"] = get_MI_for_C(c_file_dir, proj_name)
        merged_df = metrics_sum_dict["MI_C"]
    else:
        metrics_dict["MI_C"], metrics_sum_dict["MI_C"] = get_MI_for_C(c_file_dir, proj_name)
        merged_df = metrics_sum_dict["MI_C"]
        
        for transpiler_name, rust_dir in [rust_dirs]:
            tmp1, tmp2 = get_MI_for_Rust(rust_dir, proj_name, transpiler_name)
            metrics_dict["MI_Rust"][transpiler_name] = tmp1
            metrics_sum_dict["MI_Rust"][transpiler_name] = tmp2
            merged_df = pandas.merge(merged_df, tmp2, on="id")
            tmp1, tmp2 = get_unsafe_measure(rust_dir, proj_name, transpiler_name)
            metrics_dict["unsafe_measure"][transpiler_name] = tmp1
            metrics_sum_dict["unsafe_measure"][transpiler_name] = tmp2
            merged_df = pandas.merge(merged_df, tmp2, on="id")
            tmp1, tmp2 = get_var_type_measure(rust_dir, proj_name, transpiler_name)
            metrics_dict["var_type_measure"][transpiler_name] = tmp1
            metrics_sum_dict["var_type_measure"][transpiler_name] = tmp2
            merged_df = pandas.merge(merged_df, tmp2, on="id")
    
    return metrics_dict, metrics_sum_dict, merged_df

def PCA_analysis(df, chosen_metrics):
    # Calculate single pca complexity metric from 4 metrics
    X = df[chosen_metrics]
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    pca = PCA(n_components=1)
    df['summary_complexity_pca'] = pca.fit_transform(X_scaled) * -1

    # Sort the df by the PCA summary complexity score
    df_sorted = df.sort_values(by=['summary_complexity_pca', 'id'], ascending=[False, True])

    return df_sorted

def select_from_bins(bins, ratio_of_sampling):
    # Select samples from the bins based on the ratio_of_sampling
    logger.info("Selecting..")
    selected_funcs_df = pandas.DataFrame()
    for bin in bins:
        sample_size = max(1, int(np.ceil(len(bin)*(ratio_of_sampling))))
        interval = int(len(bin) / sample_size)
        selected = bin.iloc[::interval]
        selected_funcs_df = pandas.concat([selected_funcs_df, selected], ignore_index=True)
    
    return selected_funcs_df

def partition(df, features, num_bins = 5):
    # Create bins for each feature
    bin_columns = []
    for feature in features:
        if feature == "MI_C" or feature == "qwen2_5_coder_32b_MI_R":
            bins = pandas.cut(df[feature], bins=num_bins, labels=[f'Bin_{i}' for i in range(num_bins, 0, -1)])
        else:
            bins = pandas.cut(df[feature], bins=num_bins, labels=[f'Bin_{i}' for i in range(1, num_bins + 1)])
        bin_columns.append(bins)

    # Create a new df for the bin columns
    bins_df = pandas.DataFrame({
        "id": df["id"],
        **{f"{feature}_bin": bin for feature, bin in zip(features, bin_columns)},
        **{feature: df[feature] for feature in features}
    })

    # Get summarized pca compexity metric
    df_with_pca = PCA_analysis(bins_df, features)

    # Group the samples by the  combinations 
    grouped = df_with_pca.groupby([f"{feature}_bin" for feature in features])
    sorted_group_keys = sorted(grouped.groups.keys())
    bins = []
    for key in sorted_group_keys:
        bins.append(grouped.get_group(key))
    
    return bins
