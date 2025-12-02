import os
import subprocess
import re
import math
from typing import List

# Configuration
CHUNKSIZE = 1_000_000  # Final full chunk size
PRECHECKSIZE = 10_000  # Precheck small chunk size
SMALL_TESTS = ["Frequency", "BlockFrequency", "CumulativeSums", "Runs", "LongestRun", "FFT"]

def convert_to_string_of_bits(input_path: str) -> str:
    bits = []
    with open(input_path, 'rb') as file:
        byte_data = file.read()
        for byte in byte_data:
            bits.append(f"{byte:08b}")
    return ''.join(bits)

def chunking(chunk_size: int, bitstream: str) -> List[str]:
    chunks = []
    num_chunks = len(bitstream) // chunk_size
    print(f"Number of chunks in input file: {num_chunks}")
    for i in range(num_chunks):
        chunk_str = bitstream[i * chunk_size : i * chunk_size + chunk_size]
        chunks.append(chunk_str)
    return chunks

def write_to_epsilon(chunk_to_write: str, nist_path: str):
    # Write epsilon into the STS data folder so `assess` (run with cwd=nist_path)
    # can read `data/epsilon` as the input file.
    data_dir = os.path.join(nist_path, "data")
    os.makedirs(data_dir, exist_ok=True)
    epsilon_path = os.path.join(data_dir, "epsilon")
    with open(epsilon_path, "w") as file:
        file.write(chunk_to_write + "\n")

def parse_results(results_path: str, tests_to_check: List[str]) -> bool:
    all_passed = True

    for test in tests_to_check:
        test_dir = os.path.join(results_path, test)
        results_file = os.path.join(test_dir, "results.txt")

        if not os.path.isfile(results_file):
            print(f"    ❌ Missing results.txt for '{test}'")
            all_passed = False
            continue

        with open(results_file, "r") as file:
            lines = file.readlines()

        p_values = []
        for line in lines:
            line = line.strip()
            if "p-value" in line.lower():
                match = re.search(r"([0-9]*\.?[0-9]+)", line)
                if match:
                    p_values.append(float(match.group(1)))
            else:
                try:
                    val = float(line)
                    p_values.append(val)
                except ValueError:
                    continue

        if not p_values:
            print(f"    ❌ No P-values found in '{test}'")
            all_passed = False
            continue

        # NonOverlappingTemplate test
        if test == "NonOverlappingTemplate":
            m = len(p_values)  # normally 148 templates
            alpha = 0.01
            actual_passes = sum(p >= alpha for p in p_values)

            # Threshold: at least 143 out of 148 must pass
            required_passes = 143  

            if actual_passes >= required_passes:
                print(f"    ✅ Test '{test}' PASSED ({actual_passes}/{m} templates passed, required {required_passes})")
            else:
                print(f"    ❌ Test '{test}' FAILED ({actual_passes}/{m} templates passed, required {required_passes})")
                all_passed = False

        else:
            # General test: fail if p < 0.01
            failed_values = [p for p in p_values if (p < 0.01 and p != 0.0)]
            if failed_values:
                print(f"    ❌ Test '{test}' FAILED (P-values < 0.01): {failed_values}")
                all_passed = False
            else:
                print(f"    ✅ Test '{test}' PASSED")


    return all_passed

def run_STS(path_to_nist: str, epsilon_bit_length: int, tests_to_check: List[str]) -> bool:
    print(f"    ▶️ Running assess on {epsilon_bit_length} bits...")

    assess_inputs = "\n".join([
        "0",             # User Input File
        "data/epsilon",  # Input file path
        "1",             # All tests
        "0",             # Default parameters
        "1",             # One bitstream
        "0"              # ASCII input mode
    ]) + "\n"

    result = subprocess.run(["./assess", str(epsilon_bit_length)],
               cwd=path_to_nist,
               input=assess_inputs.encode(),
               stdout=subprocess.PIPE,
               stderr=subprocess.PIPE
    )

    print(f"    ✅ assess complete.")

    results_path = os.path.join(path_to_nist, "experiments", "AlgorithmTesting")
    if not os.path.isdir(results_path):
        print("    ❌ Results directory missing. This chunk likely failed to run.")
        return False

    return parse_results(results_path, tests_to_check)

def precheck_filter(input_path: str, nist_path: str, small_chunk_size: int) -> str:
    print(f"\n=== Starting Precheck Filtering (Chunks of {small_chunk_size} bits) ===")
    bitstream = convert_to_string_of_bits(input_path)
    chunks = chunking(small_chunk_size, bitstream)
    passing_bits = []

    for i, chunk in enumerate(chunks):
        print(f"Precheck: Testing chunk {i + 1}/{len(chunks)}")
        write_to_epsilon(chunk, nist_path)
        passed = run_STS(nist_path, len(chunk), SMALL_TESTS)
        if passed:
            passing_bits.append(chunk)
        else:
            print("    ❌ Precheck chunk FAILED")

    print(f"\n✅ Precheck complete. {len(passing_bits)} / {len(chunks)} chunks passed.")
    return ''.join(passing_bits)

def filter_chunks(chunk_array: List[str], nist_path: str) -> List[str]:
    passing_chunks = []
    for i, chunk in enumerate(chunk_array):
        print(f"Full Test: Testing chunk {i + 1}/{len(chunk_array)}")
        write_to_epsilon(chunk, nist_path)
        passed = run_STS(nist_path, len(chunk), [
            "Frequency", "BlockFrequency", "CumulativeSums", "Runs", "LongestRun",
            "Rank", "FFT", "Universal", "ApproximateEntropy", "Serial",
            "LinearComplexity", "OverlappingTemplate", 
            "NonOverlappingTemplate", "RandomExcursions", "RandomExcursionsVariant"
        ])
        if passed:
            print("✅ Chunk PASSED")
            passing_chunks.append(chunk)
        else:
            print("❌ Chunk FAILED")
    return passing_chunks

def final_sanitization(input_path: str, nist_path: str, chunk_size: int, output_path: str):
    # Stage 1: Precheck filter
    filtered_bitstream = precheck_filter(input_path, nist_path, PRECHECKSIZE)

    # Stage 2: Full test filtering on large chunks
    round_number = 1
    while True:
        print(f"\n=== Round #{round_number} of Full Testing ===")
        chunks = chunking(chunk_size, filtered_bitstream)
        passing_chunks = filter_chunks(chunks, nist_path)

        if len(passing_chunks) == len(chunks):
            print("✅ All full-size chunks passed.")
            break
        elif len(passing_chunks) == 0:
            print("❌ No full-size chunks passed. Stopping.")
            break
        else:
            print(f"⚠️ {len(chunks) - len(passing_chunks)} chunks failed. Retesting...")
            filtered_bitstream = ''.join(passing_chunks)
            round_number += 1

    if passing_chunks:
        final_output = ''.join(passing_chunks)
        with open(output_path, "w") as file:
            file.write(final_output)
        print(f"\n✅ Sanitized bitstream written to: {output_path}")
    else:
        print("\n⚠️ No passing chunks to write. Output file was not created.")

######################## 
# Execution Starts Here
########################

# Simple relative resolution: prefer the STS folder placed next to this script.
# This keeps your original code/logic intact but avoids hardcoded Windows paths.
script_dir = os.path.dirname(os.path.abspath(__file__))
# Candidate 1: a common folder name used in this workspace
candidate = os.path.join(script_dir, "sts-2.1.2 2", "sts-2.1.2")
if not os.path.isdir(candidate):
    # Fallback to a plain `sts-2.1.2` at the same level as this script
    candidate = os.path.join(script_dir, "sts-2.1.2")

if not os.path.isdir(candidate):
    print("❌ Could not find an STS folder next to `main.py`. Please place `sts-2.1.2` (or `sts-2.1.2 2/sts-2.1.2`) next to `main.py`.")
    raise SystemExit(1)

nist_root = candidate
real_testing_path = os.path.join(nist_root, "data", "BBS.dat")
output_path = os.path.join(nist_root, "results", "cleaned_output.bit")

print(f"Using STS root: {nist_root}")
print(f"Using input file: {real_testing_path}")
print(f"Using output file: {output_path}")

final_sanitization(
    input_path=real_testing_path,
    nist_path=nist_root,
    chunk_size=CHUNKSIZE,
    output_path=output_path
)
