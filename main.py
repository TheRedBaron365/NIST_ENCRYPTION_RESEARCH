import os
import subprocess
from typing import List

CHUNKSIZE = 1000000 # default 1,000,000


def convert_to_string_of_bits(input_path: str):
    bits = []
    with open(input_path, 'rb') as file: # opening as rb since it is binary data
        byte_data = file.read()
        for byte in byte_data:
            bits.append(f"{byte:08b}")
    return ''.join(bits)

#print(convert_to_string_of_bits("tester.dat"))

def chunking(chunk_size: int, bitstream: str) -> List[int]:
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

    with open(final_report) as file:
        content = file.read()
        if "0/1" in content or " 0/" in content:
            return False
    return True
            


def run_STS(path_to_nist: str, epsilon_bit_length: int) -> bool:
    print(f"    ▶️ Running assess on {epsilon_bit_length} bits...")

    assess_inputs = "\n".join([
        "0",  # Generator: User Input File
        "1",  # Use all statistical tests
        "0",  # Keep default parameters
        "1",  # Number of bitstreams
        "0"   # Input mode: ASCII (0's and 1's)
    ]) + "\n"

    assess_path = os.path.join(path_to_nist, "assess")

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
        print(f"\n===Round #{round_number}===")

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
    print(f"\nSanitized bitstream after processing, written to {output_path}.")





######################## 
# Testing Area
########################
testing_demo_path = "tester.dat"
real_testing_path = "sts-2.1.2/data/BBS.dat"
final_sanitization(
    input_path=real_testing_path,
    epsilon_path="sts-2.1.2/data/epsilon",
    nist_path="sts-2.1.2",
    chunk_size=CHUNKSIZE,
    output_path="results/cleaned_output.bit"
)
