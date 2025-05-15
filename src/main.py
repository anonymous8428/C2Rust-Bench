import sys
import os
from IPython import embed
from pathlib import Path
import pandas
import measure
from optparse import OptionParser

import log
logger = log.init_log()

PROGRAM_USAGE = "Usage: \n"\
                "%prog -m get -d [main_benchmark_dir] -c [csubdir] -r [rustsubdir]\n"\
                "%prog -m select -o [output_path_for_selection]\n" \
                "%prog -m tune -o [output_path_for_selection]\n"

def parse_args():
    """Parse and validate command line arguments."""
    parser = OptionParser(usage=PROGRAM_USAGE)

    parser.add_option('-m', '--mode', action='store', type='str',
            default=None, help="The mode of operation. Options: get, tune, select")
    
    parser.add_option('-d', '--dir', action='store', type='str',
            default=None, help="Main benchmark directory")
    parser.add_option('-c', '--csubdir', action='store', type='str',
            default=None, help="Name of the subdirectory containing C files")
    parser.add_option('-r', '--rustsubdir', action='store', type='str',
            default=None, help="Name of the subdirectory containing Rust files")
    
    parser.add_option('-f', '--metricfile', action='store', type='str',
            default=None, help="Name of the metric file to read/write collected metrics to/from")
    
    parser.add_option('--num_of_partition', action='store', type='int',
            default=9, help="Hyperparameter specifying the number of partition per dimension")
    parser.add_option('--ratio_of_sampling', action='store', type='float', 
            default=0.166, help="Hyperparameter specifying the ratio of sampling per bin")

    parser.add_option('-o', '--out', action="store", type="str", 
            default="out/metrics#4_fullset_v1/selected_func_lists/",
            help="Specify the output path for selections")

    opts, args = parser.parse_args()

    # Input validation

    if opts.mode is None:
        parser.print_help()
        print("Mode of operation is not set", file=sys.stderr)
        sys.exit(1)
    else:
        opts.mode = opts.mode.lower()
        if opts.mode == "get":
            if opts.dir is None or opts.csubdir is None or opts.rustsubdir is None:
                parser.print_help()
                print("Main benchmark directory, C subdirectory and Rust subdirectory must be set", file=sys.stderr)
                sys.exit(1)
        elif opts.mode == "select" or opts.mode == "tune":
            if opts.out is None:
                parser.print_help()
                print("Output path must be specified for selection or parameter tuning", file=sys.stderr)
                sys.exit(1)
        else:
            parser.print_help()
            print("The mode sohuld be set to one of these: get, tune, select", file=sys.stderr)
            sys.exit(1)    

    return (opts, args)

def get_metrics(projects_root_dir, c_sub_dir, rust_dir, metricfile):
    projects_root_dir = Path(projects_root_dir)
    proj_dirs = [x for x in projects_root_dir.iterdir() if x.is_dir()]

    all_projs_merged = pandas.DataFrame()
    
    for proj_dir in proj_dirs:
        proj_dir = str(proj_dir)
        logger.info("Processing: " + str(proj_dir))
        c_dir_fpath = os.path.join(proj_dir, c_sub_dir)

        dir = rust_dir
        dir = dir.strip("/")
        prefix = "rust_"
        suffix = "_sf_withfixing"
            
        if dir.startswith(prefix) and dir.endswith(suffix):
            transpiler_name = dir[len(prefix):-len(suffix)]
        
        rust_dirs_proj = (transpiler_name, os.path.join(proj_dir, dir))

        metrics_dict, metrics_sum_dict, merged_df = \
            measure.get_metrics(c_dir_fpath, rust_dirs_proj)
        all_projs_merged = pandas.concat([all_projs_merged, merged_df])
    
    all_projs_merged.to_pickle(metricfile + '.pkl')
    all_projs_merged.to_csv(metricfile + ".csv", sep=";", index=False)


def select_funcs(outpath, num_of_partition, ratio_of_sampling, metricfile):

    all_projs_merged = pandas.read_pickle(metricfile + ".pkl")

    chosen_metrics = [
                    'MI_C',
                    'qwen2_5_coder_32b_MI_R',
                    'qwen2_5_coder_32b_avg_unsafe_stmt_R',
                    'qwen2_5_coder_32b_total_uniq_type_R'
                    ]

    # Partition and select from bins 
    logger.info("Number of partitions: " + str(num_of_partition))
    logger.info("Ratio of sampling per bin: " + str(ratio_of_sampling))
    bins = measure.partition(all_projs_merged, chosen_metrics, num_of_partition)
    logger.info("Number of bins: " + str(len(bins)))
    selected_funcs_df = measure.select_from_bins(bins, ratio_of_sampling)

    # Save the selected list of functions
    selected_funcs_ls = list(selected_funcs_df["id"])
    out_filename = "selected_funcs#" + str(num_of_partition) + "#" + str(ratio_of_sampling).replace(".", "_") + "#" + str(len(bins)) + ".txt"
    out = os.path.join(outpath, out_filename) 
    with open(out, "w") as f:
        for s in selected_funcs_ls:
            f.write(s + "\n")

def main():

    opts, args = parse_args()

    if opts.mode == "get":
        get_metrics(opts.dir, opts.csubdir, opts.rustsubdir, opts.metricfile)
    elif opts.mode == "select":
        select_funcs(opts.out, opts.num_of_partition, opts.ratio_of_sampling, opts.metricfile)
    elif opts.mode == "tune":
        for num_of_partition in range(1,21):
            for ratio_of_sampling in [round(x * 0.002, 3) for x in range(1, 101)]:
                select_funcs(opts.out, num_of_partition, ratio_of_sampling, opts.metricfile)

if __name__ == "__main__":
    main()