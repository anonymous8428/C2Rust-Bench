
import os
import sys
import shutil
import subprocess
import traceback
import tempfile
from pathlib import Path

import time
from IPython import embed
from textwrap import wrap
import toml
import ollama

instructions = "Behave like you are an expert of C and Rust. Behave like you are a translator from C language to Rust language. Can you translate C code given above into Rust code? \n" +\
                    "Do not explain the code to me! Only return Rust code correspoding to the given C code. " +\
                    "Follow these intructions strictly in translation: \n" +\
                    "(1) Do not add any extra error handling, \n" +\
                    "(2) Do not merge functions, \n" +\
                    "(3) Do not change variable names, \n" +\
                    "(4) use no_mangle for each function, \n" +\
                    "(5) make each function public, \n" +\
                    "(6) translate the standard C library function calls by placing a decoy function call (leave the decoy function body empty if possible) with the same name, and \n" +\
                    "(7) Only return a Rust code and nothing else!\n"

fix_compilation_inst = "When attempted to compile the recently generated rust code, I obtained the compilation errors given above. Fix those errors and only return the modified Rust code. Do not explain the code or changes to me!"

no_mangle_and_pub_inst = "Make a pass on the code given above and add #[no_mangle] and pub to each functions if they are missing. Do not change anything else. Only return a Rust code and nothing else!\n"

BASE_DIR = os.getcwd()

## Tested models
# llama3.1:8b, gemma2:9b, mistral:7b, llama3.2:3b, codegeex4:9b
# codestral:22b, qwen2.5:7b, qwen2.5:14b, qwen2.5:32b

MODEL = "qwen2.5-coder:7b"
def llm_request(req_text, messages):
    print("Waiting for response...")
    current_message = [{
                        "role": "user",
                        "content": req_text,
                    }]
    
    response = ollama.chat(
        model=MODEL,
        messages=messages + current_message,
    )
    
    return response, current_message + [response['message']]

def check_format_and_clean(transpiled_rust_code):
    if transpiled_rust_code[:8] == "```rust\n" and transpiled_rust_code[-3:] == "```":
        transpiled_rust_code = transpiled_rust_code[8:]
        transpiled_rust_code = transpiled_rust_code[:-3]
    elif transpiled_rust_code[:8] == "```rust\n" and transpiled_rust_code[-4:] == "```\n":
        transpiled_rust_code = transpiled_rust_code[8:]
        transpiled_rust_code = transpiled_rust_code[:-4]
    elif transpiled_rust_code[:7] == "```rust" and transpiled_rust_code[-3:] == "```":
        transpiled_rust_code = transpiled_rust_code[7:]
        transpiled_rust_code = transpiled_rust_code[:-3]
    elif transpiled_rust_code[:9] == " ```rust\n" and transpiled_rust_code[-3:] == "```":
        transpiled_rust_code = transpiled_rust_code[9:]
        transpiled_rust_code = transpiled_rust_code[:-3]
    else:
        print("The returned format unrecognized!")
        print(transpiled_rust_code)
        transpiled_rust_code = "TryAgain"

    return transpiled_rust_code

def transpile_with_chatgpt_web(input_C):

    input_text = "\n" + input_C + "\n" + instructions
    response, messages = llm_request(input_text, [])
    
    if not response:
        return False
    transpiled_rust_code = response["message"]["content"]

    transpiled_rust_code = check_format_and_clean(transpiled_rust_code)

    if not transpiled_rust_code:
        print("Output is empty for some reason")

    return transpiled_rust_code, messages

def _update_cargo_toml(toml_path):
    
    toml_data = toml.load(toml_path)
    if "lib" in toml_data.keys():
        if not "crate-type" in toml_data["lib"].keys():
            toml_data["lib"]["crate-type"] = ["cdylib"]
    else:
        toml_data["lib"] = {"crate-type":["cdylib"]}
    with open("Cargo.toml", "w") as f:
        toml.dump(toml_data, f)

def is_compilable(Input_C):

    print("Test Rust compilation")

    tmp_dir = tempfile.TemporaryDirectory()
    os.chdir(tmp_dir.name)
    with open("tmp.rs", 'w') as f:
        f.write(Input_C + "\n")
        
    cargo_proj_name = "tmp_proj_dir"

    if not os.path.exists(cargo_proj_name):
        cmd = ["cargo", "new", cargo_proj_name]
        subprocess.run(cmd)

    shutil.copy("tmp.rs", os.path.join(cargo_proj_name, "src", "main.rs"))

    shutil.move(os.path.join(cargo_proj_name, "src", "main.rs"), os.path.join(cargo_proj_name, "src", "lib.rs"))
    os.chdir(cargo_proj_name)
    
    cmd = ["cargo", "add", "libc@0.2", "f128@0.2"]
    subprocess.run(cmd)

    _update_cargo_toml("Cargo.toml")

    cmd = ["cargo", "rustc", "--", "-C", "opt-level=0", "-C", "overflow-checks=off"]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, err = process.communicate()
    if os.path.exists(os.path.join("target/debug/", "lib" + cargo_proj_name + ".so")):
        os.chdir(BASE_DIR)
        shutil.rmtree(tmp_dir.name)
        print("Compilation is successful")
        return True, None
    
    os.chdir(BASE_DIR)
    shutil.rmtree(tmp_dir.name)
    print("Compilation is failed")
    return False, err.decode("utf-8")

def fix_compilation_errors(err, messages):

    input_text = "\n" + err + "\n" + fix_compilation_inst

    response, curr_messages = llm_request(input_text, messages)
    if not response:
        return False
    transpiled_rust_code = response["message"]["content"]

    transpiled_rust_code = check_format_and_clean(transpiled_rust_code)
    
    if not transpiled_rust_code:
        print("Output is empty for some reason")
    
    if transpiled_rust_code != "TryAgain":
        return transpiled_rust_code, messages + curr_messages
    else:
        return transpiled_rust_code, messages

def fix_pub_no_mangle(input_Rust):
    input_text = "\n" + input_Rust + "\n" + no_mangle_and_pub_inst
    messages = []
    response, curr_messages = llm_request(input_text, messages)
    if not response:
        return False
    final_rust_code = response["message"]["content"]

    final_rust_code = check_format_and_clean(final_rust_code)
    if not final_rust_code:
        print("Output is empty for some reason")
    
    if final_rust_code != "TryAgain":
        return final_rust_code, messages + curr_messages
    else:
        return final_rust_code, messages

def transpilation(input_C):
    try_count = 0
    while try_count < 5:
        print("Transpilation...")
        messages = []
        output_Rust, messages = transpile_with_chatgpt_web(input_C)
        # print(messages)
        print(output_Rust)
        if output_Rust != "TryAgain":
            break
        output_Rust = ''
        try_count = try_count + 1
    return output_Rust, messages

def check_and_fix_compilation(output_Rust, messages):
    fix_count = 0
    while fix_count < 20:
        print("Check compilation..")
        res, err = is_compilable(output_Rust)
        if not res:
            try_count = 0
            while try_count < 5:
                print("Fixing compilation errors: attempt " + str(fix_count + 1))
                output_Rust, messages = fix_compilation_errors(err, messages)
                fix_count += 1
                # print(messages)
                print(output_Rust)
                if output_Rust != "TryAgain":
                    break
                output_Rust = ''
                try_count = try_count + 1
        else:
            break
    return output_Rust, fix_count, res

def check_pub_no_mangle(output_Rust):
    try_count = 0
    prev_output_rust = output_Rust
    while try_count < 5:
        print("Fixing missing pub and no_mangle")
        output_Rust, messages = fix_pub_no_mangle(prev_output_rust)
        # print(messages)
        print(output_Rust)
        
        if output_Rust != "TryAgain":
            print("Check compilation..")
            res, err = is_compilable(output_Rust)
            if res:
                break
        output_Rust = ''
        try_count = try_count + 1

    if output_Rust == "TryAgain" or output_Rust == "":
        return prev_output_rust, try_count
    else:
        return output_Rust, try_count + 1

def main():

    args = sys.argv
    
    if len(args) < 1:
        print("Error: Missing argument")
        print("Usage: python3 src/llm_transpile_with_compilation_fixing.py Benchmark/large_set/")
        sys.exit(1)
    
    input_C = ""
    llm_model = "qwen2_5_coder_32b"
    DATASET_ROOT = args[1]
    projects = [x for x in os.listdir(DATASET_ROOT) if os.path.isdir(os.path.join(DATASET_ROOT, x))]

    for proj_name in projects:
        INPUT_DIR = os.path.join(DATASET_ROOT, proj_name, "preprocessed_sf")
        OUT_DIR = os.path.join(DATASET_ROOT, proj_name, "rust_" + llm_model + "_sf_withfixing")
        log_file = open(os.path.join(OUT_DIR, "transpilation.log"), "a")

        print("Current model: " + str(MODEL))
        for file in os.listdir(INPUT_DIR):
            print("Processing: " + str(file))
            if os.path.exists(os.path.join(OUT_DIR, os.path.splitext(file)[0] + '.rs')):
                print("Already analyzed, Skipping!")
                continue
            with open(os.path.join(INPUT_DIR, file), "r") as fp:
                try:
                    input_C = fp.read()
                except Exception as ex:
                    print("Error in reading Input C file: " + str(traceback.format_exc()))
                    log_file.write(str(file) + ": " + str(ex).replace("\n", " ") + "\n")
                    continue
            transpilation_res = None
            compilation_res = None
            number_of_compilation_iteration = 0
            number_of_post_process_iter = 0
            transpilation_time = 0
            compilation_fixing_time = 0
            post_process_fixing_time = 0
            if input_C:
                try:
                    while True:
                        transpilation_res = None
                        compilation_res = None
                        number_of_compilation_iteration = 0
                        number_of_post_process_iter = 0
                        transpilation_time = 0
                        compilation_fixing_time = 0
                        post_process_fixing_time = 0

                        start_time = time.time()
                        messages = []
                        output_Rust, messages = transpilation(input_C)
                        end_time = time.time()
                        transpilation_time = round(end_time - start_time)
                        if output_Rust == '':
                            transpilation_res = False
                        else:
                            transpilation_res = True
                            start_time = time.time()
                            output_Rust, fix_count, res = check_and_fix_compilation(output_Rust, messages)
                            end_time = time.time()
                            compilation_fixing_time = round(end_time - start_time)
                            number_of_compilation_iteration = fix_count
                            if res:
                                compilation_res = True
                            else:
                                compilation_res = False
                                break

                        if output_Rust == '':
                            continue
                        else:
                            start_time = time.time()
                            output_Rust, fix_count = check_pub_no_mangle(output_Rust)
                            end_time = time.time()
                            post_process_fixing_time = round(end_time - start_time)
                            number_of_post_process_iter = fix_count
                            break
                except Exception as ex:
                    print("Error in transpilation: " + str(traceback.format_exc()))
                    log_file.write(str(file) + ": " + str(ex).replace("\n", " ") + "\n")
                    continue
            else:
                print("Input file is empty!")
                log_file.write(str(file) + ": " + "Input file is empty!" + "\n")
                continue
            
            end_time = time.time()
            with open(os.path.join(OUT_DIR, os.path.splitext(file)[0] + '.rs'), "w") as fp:
                fp.write(output_Rust)

            print(str(file) + ": " + "Successful transpilation!" + "\n")
            log_file.write(str(file) + ";" + str(transpilation_res) + ";" + str(compilation_res) + ";"  +\
                            str(transpilation_time) + ";" + str(number_of_compilation_iteration) + ";" +\
                            str(compilation_fixing_time) + ";" + str(number_of_post_process_iter) + ";" +\
                            str(post_process_fixing_time) + "\n")
            log_file.flush()
        log_file.close()

if __name__ == "__main__":
    main()