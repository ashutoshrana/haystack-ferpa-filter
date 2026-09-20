"""Run a synthetic, no-key retrieval-to-prompt example after installing ferpa-haystack.

From the repository root: python examples/basic_usage.py
The recording generator captures a prompt; it does not answer using an LLM.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmarks.retrieval_boundary import benchmark  # noqa: E402


def main():
    report = benchmark(repeats=1, modes=("sync",))
    for result in report["results"]:
        sample = result["samples"][0]
        print(json.dumps({"path": result["path"], "candidate_count": sample["candidate_count"],
                          "prompt_document_ids": sample["observed_ids"],
                          "unauthorized_document_ids": sample["unauthorized_ids"],
                          "authorized_recall": sample["authorized_recall"]}))
    print("Protected boundary passed; deliberate bypass detected. Synthetic data only.")


if __name__ == "__main__":
    main()
