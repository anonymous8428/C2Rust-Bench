# 1. Environment Setup
## 1.1 Create virtual environment and install required Python modules
Create a virtual environment:
```shell 
python3 -m venv .venv
```
Activate the virtual environement:
```shell 
source .venv/bin/activate
```

Install the required python modules:
```shell
pip install -r requirements.txt
```

## 1.2 Obtain and build the container for MI metric of C

Pull the docker image for the ccccc tool:
```shell
docker pull registry.git.fh-aachen.de/embeddedtools/ccccc-docker:latest
```

Rename the docker image:
```shell
docker tag registry.git.fh-aachen.de/embeddedtools/ccccc-docker:latest ccccc-docker:latest
```

Run a docker container in detached mode:
```shell
docker run -dit ccccc-docker:latest
```

## 1.3 Install Rustc 

Install rustc:
```shell
apt-get install rustc
```

Get the nightly release:
```shell
rustup update nightly-x86_64-unknown-linux-gnu
```

Set the nightly release as default
```shell
rustup default nightly-x86_64-unknown-linux-gnu
```

## 1.4 Build rust-code-analysis tool for MI metric of Rust
Change directory into the rust-code-analysis root directory: 
```shell
cd src/rust-code-analysis/
```

Build the rust-code-analysis-cli tool:
```shell
cargo build -p rust-code-analysis-cli
```

## 1.5 Benchmark
Download the benchmark from `https://huggingface.co/datasets/anonymous4review/C2Rust-Bench/blob/main/Benchmark.tar` and place it into the root directory of github repo. Under `Benchmark` directory, there are three folders:

- `microbenchmark_set`: contains C and corresponding Rust functions transpiled with 9 different LLMs that is used for preliminary experiment.
- `large_set`: contains 15,503 C functions coming from 65 programs and corresponding Rust functions transpiled with the chosen LLM.
- `C2Rust-Bench`: contains the proposed C2RUST-BENCH including C and corresponding Rust functions for transpilation evaluation.

## 1.6 (Optional) Install Ollama and Transpile Functions
This step is optional. If you want to use transpilation module, follow below instructions to prepare LLM environment for transpilation. Otherwise, skip Ollama installation.
- Install Ollama following instructions in https://ollama.com/download and run Ollama server

- Pull the qwen2.5-coder:32b LLM:
```shell
ollama pull qwen2.5-coder:32b
```
To transpile functions from C to Rust:
```shell
python3 src/llm_transpile_with_compilation_fixing.py Benchmark/large_set/
```

It iterates the folder `Benchmark/large_set/large_set/preprocessed_sf` and transpiles the functions placed into individual C files. The output transpiled Rust functions are saved into individual Rust files and placed into the folder `Benchmark/large_set/large_set/rust_qwen2_5_coder_32b_sf_withfixing`. In addition, the metrics related to the transpilation process are saved into the file `Benchmark/large_set/large_set/rust_qwen2_5_coder_32b_sf_withfixing/transpilation.log`

# 2. Running the FuncSelector
## 2.1 Obtaining metrics and performing selection 
### 2.1.1 Obtaining metrics

The source code complexity metrics are saved in pickle and csv formats in the root directory for large set and microbenchmark set. To recollect the metrics, follow instructions given below:

- To run calculation and collection of the complexity metrics from the large set:<br > 
```shell 
python3 src/main.py -m get -d Benchmark/large_set -c preprocessed_sf -r rust_qwen2_5_coder_32b_sf_withfixing -f new_large_set_all_metrics
```

It will generate two new files named `new_large_set_all_metrics.pkl` and `new_large_set_all_metrics.csv`

- To run calculation and collection of the complexity metrics from the microbenchmark set: <br >
```shell
python3 src/main.py -m get -d Benchmark/microbenchmark_set -c preprocessed_sf -r rust_qwen2_5_coder_32b_sf_withfixing -f new_microbenchmark_set_all_metrics
```

It will generate two new file named `new_microbenchmark_set_all_metrics.pkl` and `new_microbenchmark_set_all_metrics.csv`

### 2.1.2 Performing selection
- To run the hyperparameter tuning preliminary experiment:<br>
```shell
python3 src/main.py -m tune -f large_set_all_metrics -o out/large_set/selected_func_lists/
```

It will save the selected functions in text files under `out/large_set/selected_func_lists/`. The text files are named in the format of selected_funcs#{num_of_partition}#{ratio_of_sampling}#{number_of_nonempty_bins}.txt.

- To run the selection process using the tuned hyperparameters as default:<br>
```shell
python3 src/main.py -m select -f large_set_all_metrics -o out/large_set/selected_func_lists/
```

It will save a single text file containing selected functions with the default hyperparameters under `out/large_set/selected_func_lists/`. The name of the text file will be `selected_funcs#9#0_166#206.txt` for the default hyperparameters. 


## 2.2 Running the evaluation of selections
### 2.2.1 Running the hyperparameter tuning evaluation
- To calculate the relative difference score for each selection using different hyperparameter combinations: 
```shell
python3 src/evaluate_selections.py Benchmark/large_set/large_set/rust_qwen2_5_coder_32b_sf_withfixing/merged_transpilation.log out/large_set/selected_func_lists/ out/large_set/histograms/
```

It generates a plot from the distribution of compilation error fixing attempt of each selection using different hyperparameters under `out/large_set/selected_func_lists/` and saves the plots under `out/large_set/histograms/`. Also, it generates a diagram showing the change in relative difference score and saves it under `out/large_set/histograms/`.  

### 2.2.2 Running the cross-LLM evaluation
- To calculate the relative difference score for each LLM based on the selected set obtained with the chosen LLM:
```shell
python3 src/evaluate_selections_cross_llm.py Benchmark/microbenchmark_set/microbenchmark_set/ out/microbenchmark_set/other_models/selected_func_lists/ out/microbenchmark_set/other_models/histograms/
```

It generates plot from the distribution of compilation error fixing attempt for each LLM and saves under `out/microbenchmark_set/other_models/histograms`. Also, it generates a diagram showing the change in relative difference score among LLMs and saves it under `out/microbenchmark_set/other_models/histograms`.
