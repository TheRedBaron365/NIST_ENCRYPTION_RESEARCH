import os 
import subprocess
import re
from typing import List

CHUNKSIZE = 1000000  # Adjust as needed

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
        chunk_str = bitstream[i*chunk_size:i*chunk_size+chunk_size]
        chunks.append(chunk_str)
    return chunks

def write_to_epsilon(chunk_to_write: str):
    epsilon_path = os.path.join("data", "epsilon")
    with open(epsilon_path, "w") as file:
        file.write(chunk_to_write + "\n")

def parse_results(results_path: str) -> bool:
    required_tests = [
        "Frequency", "BlockFrequency", "CumulativeSums", "Runs", "LongestRun",
        "Rank", "FFT", "Universal", "ApproximateEntropy", "Serial",
        "LinearComplexity", "RandomExcursions", "RandomExcursionsVariant"
    ]

    all_passed = True

    for test in required_tests:
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

        failed_values = [p for p in p_values if p < 0.01]
        if failed_values:
            print(f"    ❌ Test '{test}' FAILED (P-values < 0.01): {failed_values}")
            all_passed = False
        else:
            print(f"    ✅ Test '{test}' PASSED")

    return all_passed

def run_STS(path_to_nist: str, epsilon_bit_length: int) -> bool:
    print(f"    ▶️ Running assess on {epsilon_bit_length} bits...")

    assess_inputs = "\n".join([
        "0",             # User Input File
        "data/epsilon",  # Inputing ASCII of input
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

    return parse_results(results_path)

def filter_chunks(chunk_array: List[str], nist_path: str) -> List[str]:
    passing_chunks = []
    for i, chunk in enumerate(chunk_array):
        print(f"Testing chunk {i + 1}/{len(chunk_array)}")
        write_to_epsilon(chunk)
        passed = run_STS(nist_path, len(chunk))
        if passed:
            print("✅ Chunk PASSED")
            passing_chunks.append(chunk)
        else:
            print("❌ Chunk FAILED")
    return passing_chunks

def final_sanitization(input_path: str, nist_path: str, chunk_size: int, output_path: str):
    bitstream = convert_to_string_of_bits(input_path)
    round_number = 1

    while True:
        print(f"\n=== Round #{round_number} ===")
        chunks = chunking(chunk_size, bitstream)
        passing_chunks = filter_chunks(chunks, nist_path)

        if len(passing_chunks) == len(chunks):
            print("All chunks passed.")
            break
        elif len(passing_chunks) == 0:
            print("No chunks passed. Stopping.")
            break
        else:
            print(f"{len(chunks) - len(passing_chunks)} chunks failed. Retesting...")
            bitstream = ''.join(passing_chunks)
            round_number += 1

    if passing_chunks:
        final_output = ''.join(passing_chunks)
        with open(output_path, "w") as file:
            file.write(final_output)
        print(f"\nSanitized bitstream written to: {output_path}")
    else:
        print("\n⚠️ No passing chunks to write. Output file was not created.")

######################## 
# Testing Area
########################

real_testing_path = r"C:\\Users\\braya\\Downloads\\sts-2_1_2\\sts-2.1.2\\sts-2.1.2\\data\\BBS.dat" #location of data input

final_sanitization(
    input_path=real_testing_path,
    nist_path=r"C:\\Users\\braya\\Downloads\\sts-2_1_2\\sts-2.1.2\\sts-2.1.2",
    chunk_size=CHUNKSIZE,
    output_path=r"C:\\Users\\braya\\Downloads\\sts-2_1_2\\sts-2.1.2\\sts-2.1.2\\results\\cleaned_output.bit"
)
