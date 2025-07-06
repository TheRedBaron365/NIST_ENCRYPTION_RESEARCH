import os
import subprocess
from typing import List

CHUNKSIZE = 1000000  # You can adjust this as needed

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


def write_to_epsilon(epsilon_path: str, chunk_to_write: str):
    with open(epsilon_path, "w") as file:
        file.write(chunk_to_write + "\n")


def parse_results(results_path: str) -> bool:
    final_report = os.path.join(results_path, "finalAnalysisReport.txt")
    if not os.path.isfile(final_report):
        print("    ❌ finalAnalysisReport.txt not found.")
        return False

    # Required statistical tests and their expected "1/1" pass result
    required_tests = [
        "Frequency",
        "BlockFrequency",
        "CumulativeSums",
        "Runs",
        "LongestRun",
        "Rank",
        "FFT",
        "Universal",
        "ApproximateEntropy",
        "Serial",
        "LinearComplexity"
    ]

    with open(final_report, "r") as file:
        lines = file.readlines()

    for test in required_tests:
        found = False
        for line in lines:
            if test in line and "1/1" in line:
                found = True
                break
        if not found:
            print(f"    ❌ Test '{test}' did not pass with 1/1.")
            return False

    return True


def run_STS(path_to_nist: str, epsilon_bit_length: int) -> bool:
    print(f"    ▶️ Running assess on {epsilon_bit_length} bits...")

    assess_inputs = "\n".join([
        "0",  # Generator: User Input File
        "data/BBS_fail.dat",  # Must match what assess expects
        "1",  # Use all statistical tests
        "0",  # Keep default parameters
        "1",  # Number of bitstreams
        "1"   # Input mode: ASCII
    ]) + "\n"

    result = subprocess.run(["./assess", str(epsilon_bit_length)],
               cwd=path_to_nist,
               input=assess_inputs.encode(),
               stdout=subprocess.DEVNULL,
               stderr=subprocess.DEVNULL)

    print(f"    ✅ assess complete.")
    
    results_path = os.path.join(path_to_nist, "experiments", "AlgorithmTesting")
    if not os.path.isdir(results_path):
        print("    ❌ Results directory missing. This chunk likely failed to run.")
        return False

    return parse_results(results_path)


def filter_chunks(chunk_array: List[str], epsilon_path: str, nist_path: str):
    passing_chunks = []
    
    for i, chunk in enumerate(chunk_array):
        print(f"Testing chunk {i + 1}/{len(chunk_array)}")

        write_to_epsilon(epsilon_path, chunk)
        passed = run_STS(nist_path, len(chunk))

        if passed:
            print("✅ Chunk PASSED")
            passing_chunks.append(chunk)
        else:
            print("❌ Chunk FAILED")

    return passing_chunks


def final_sanitization(input_path: str, epsilon_path: str, nist_path: str, chunk_size: int, output_path: str):
    bitstream = convert_to_string_of_bits(input_path)
    round_number = 1

    while True:
        print(f"\n=== Round #{round_number} ===")

        chunks = chunking(chunk_size, bitstream)
        passing_chunks = filter_chunks(chunks, epsilon_path, nist_path)

        if len(passing_chunks) == len(chunks):
            print("All chunks passed.")
            break
        else:
            print(f"{len(chunks) - len(passing_chunks)} chunks failed. Retesting...")

        bitstream = ''.join(passing_chunks)
        round_number += 1

    with open(output_path, "w") as file:
        file.write(bitstream)

    print(f"\nSanitized bitstream written to: {output_path}")


######################## 
# Testing Area
########################

testing_demo_path = "tester.dat"
real_testing_path = r"C:\Users\braya\Downloads\sts-2_1_2\sts-2.1.2\sts-2.1.2\data\BBS_fail.dat"

final_sanitization(
    input_path=real_testing_path,
    epsilon_path=r"C:\Users\braya\Downloads\sts-2_1_2\sts-2.1.2\sts-2.1.2\data\epsilon",  
    nist_path=r"C:\Users\braya\Downloads\sts-2_1_2\sts-2.1.2\sts-2.1.2",
    chunk_size=CHUNKSIZE,
    output_path=r"C:\Users\braya\Downloads\sts-2_1_2\sts-2.1.2\sts-2.1.2\results\cleaned_output.bit"
)
